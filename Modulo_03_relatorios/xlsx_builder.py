"""
Modulo_03_relatorios · xlsx_builder.py
Sprint 4 — XlsxBuilder: gera arquivos .xlsx para os 4 tipos de relatório.
Lotes vencidos destacados em vermelho (RF-22).
"""
import logging
from datetime import date, datetime, timedelta
from pathlib  import Path
from decimal  import Decimal
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side 
from openpyxl import Workbook
from Modulo_06_dados import get_read_session, Movimentacao, Lote, Produto, Usuario
from sqlalchemy.orm import joinedload
from datetime import datetime as dt
import io as _io_bg


logger = logging.getLogger(__name__)
  
# Paleta de cores para o XLSX
COR_HEADER_FILL  = "1F4E79"   # azul escuro
COR_HEADER_FONT  = "FFFFFF"   # branco
COR_VENCIDO_FILL = "FCEBEB"   # vermelho claro
COR_VENCIDO_FONT = "A32D2D"   # vermelho escuro
COR_LINHA_ALT    = "F2F1ED"   # cinza claro (linhas alternadas)
COR_AMBER_FILL   = "FAEEDA"   # âmbar claro
COR_AMBER_FONT   = "854F0B"   # âmbar escuro
 
# imagem de fundo
LOGO_BG_PATH= Path("assets")/ "logo_Centro_Uro_Nefrologia_sem_fundo.png"
 
def _aplicar_background(xlsx_bytes: bytes) -> bytes:
    """
    Insere LOGO_BG_PATH como background (marca d'água) em todas as abas
    do arquivo .xlsx representado por xlsx_bytes.
 
    Retorna os bytes do arquivo modificado.
    Se a imagem não existir ou ocorrer erro, retorna xlsx_bytes sem modificação.
    """
    if not LOGO_BG_PATH.exists():
        logger.warning(
            "Logo de background não encontrada em '%s' — planilha gerada sem marca d'água.",
            LOGO_BG_PATH,
        )
        return xlsx_bytes
 
    try:
        img_bytes = LOGO_BG_PATH.read_bytes()
        img_ext   = LOGO_BG_PATH.suffix.lstrip(".").lower()   # "png" ou "jpeg"
        return _injetar_background_ooxml(xlsx_bytes, img_bytes, img_ext)
    except Exception as exc:
        logger.warning("Erro ao aplicar background na planilha: %s", exc)
        return xlsx_bytes

def _injetar_background_ooxml(
    xlsx_bytes: bytes,
    img_bytes:  bytes,
    img_ext:    str = "png",
) -> bytes:
    """
    Manipula o ZIP interno do .xlsx para injetar a imagem como background
    em todas as abas, seguindo a especificação OOXML (ECMA-376, §18.3.1.16).
 
    A tag <picture r:id="rIdBG"/> dentro de <worksheet> instrui o Excel a
    renderizar a imagem como fundo repetido/centralizado na aba — o mesmo
    comportamento de Página → Plano de Fundo no Excel.
    """
    import zipfile, io as _io
 
    buf_in  = _io.BytesIO(xlsx_bytes)
    buf_out = _io.BytesIO()
    REL_TYPE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    )
    MEDIA_PATH = f"xl/media/logo_background.{img_ext}"
    RID        = "rIdBG"
 
    with zipfile.ZipFile(buf_in, "r") as zin,          zipfile.ZipFile(buf_out, "w", zipfile.ZIP_DEFLATED) as zout:
 
        nomes  = zin.namelist()
        sheets = [
            n for n in nomes
            if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        ]
        img_gravada = False
 
        for item in nomes:
            data = zin.read(item)
 
            # Grava a imagem antes do primeiro sheet (ordem no ZIP não importa)
            if not img_gravada and item == (sheets[0] if sheets else ""):
                zout.writestr(MEDIA_PATH, img_bytes)
                img_gravada = True
 
            if item in sheets:
                xml = data.decode("utf-8")
                # Garante namespace r:
                if "xmlns:r=" not in xml:
                    xml = xml.replace(
                        "<worksheet ",
                        "<worksheet "
                        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ',
                    )
                # Injeta <picture> antes de </worksheet> (apenas uma vez)
                if "<picture " not in xml:
                    xml = xml.replace(
                        "</worksheet>",
                        f'<picture r:id="{RID}"/></worksheet>',
                    )
                zout.writestr(item, xml.encode("utf-8"))
 
            elif (
                item.startswith("xl/worksheets/_rels/")
                and item.endswith(".rels")
            ):
                xml = data.decode("utf-8")
                if RID not in xml:
                    rel = (
                        f'<Relationship Id="{RID}" Type="{REL_TYPE}" '                        f'Target="../{MEDIA_PATH[3:]}"/>'                    )
                    xml = xml.replace("</Relationships>", rel + "</Relationships>")
                zout.writestr(item, xml.encode("utf-8"))
 
            else:
                zout.writestr(item, data)
 
        # Cria _rels para sheets que ainda não tinham o arquivo de relacionamentos
        for sheet in sheets:
            rels_path = (
                sheet.replace("xl/worksheets/", "xl/worksheets/_rels/") + ".rels"
            )
            if rels_path not in nomes:
                rels_xml = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'                    '<Relationships '                    'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'                    f'<Relationship Id="{RID}" Type="{REL_TYPE}" '                    f'Target="../{MEDIA_PATH[3:]}"/>'                    "</Relationships>"
                )
                zout.writestr(rels_path, rels_xml.encode("utf-8"))
 
    buf_out.seek(0)
    return buf_out.read()

def _wb_styles():
    """Retorna os estilos reutilizáveis para o workbook."""
    header_fill = PatternFill("solid", fgColor=COR_HEADER_FILL)
    header_font = Font(bold=True, color=COR_HEADER_FONT, size=10)
    header_align= Alignment(horizontal="center", vertical="center", wrap_text=True)
 
    venc_fill = PatternFill("solid", fgColor=COR_VENCIDO_FILL)
    venc_font = Font(color=COR_VENCIDO_FONT, size=10)
 
    amber_fill = PatternFill("solid", fgColor=COR_AMBER_FILL)
    amber_font = Font(color=COR_AMBER_FONT, size=10)
 
    alt_fill  = PatternFill("solid", fgColor=COR_LINHA_ALT)
    norm_font = Font(size=10)
    center    = Alignment(horizontal="center", vertical="center")
    left      = Alignment(horizontal="left",   vertical="center")
 
    thin_border = Border(
        left   = Side(style="thin", color="D3D1C7"),
        right  = Side(style="thin", color="D3D1C7"),
        top    = Side(style="thin", color="D3D1C7"),
        bottom = Side(style="thin", color="D3D1C7"),
    )
    return {
        "hf": header_fill, "hft": header_font, "ha": header_align,
        "vf": venc_fill,   "vft": venc_font,
        "af": amber_fill,  "aft": amber_font,
        "alt": alt_fill,   "nf": norm_font,
        "center": center,  "left": left,
        "border": thin_border,
    }
 
 
def _aplicar_header(ws, colunas: list[tuple[str, int]], st: dict, row_idx: int = 1):
    """Escreve o cabeçalho na linha especificada e configura larguras de coluna."""
    for col, (titulo, largura) in enumerate(colunas, 1):
        cell = ws.cell(row=row_idx, column=col, value=titulo)
        cell.fill      = st["hf"]
        cell.font      = st["hft"]
        cell.alignment = st["ha"]
        cell.border    = st["border"]
        ws.column_dimensions[cell.column_letter].width = largura
    ws.row_dimensions[row_idx].height = 28
 
 
def _aplicar_linha(ws, row_idx: int, valores: list, st: dict,
                   fill=None, font=None, alignments=None):
    """Escreve uma linha de dados com estilo e alinhamento sob medida."""
    fundo = fill  or (st["alt"] if row_idx % 2 == 0 else None)
    fonte = font  or st["nf"]
    for col, val in enumerate(valores, 1):
        cell = ws.cell(row=row_idx, column=col, value=val)
        cell.font      = fonte
        if alignments and col - 1 < len(alignments):
            cell.alignment = alignments[col - 1]
        else:
            cell.alignment = st["center"] if isinstance(val, (int, float, Decimal)) else st["left"]
            
        cell.border    = st["border"]
        if fundo:
            cell.fill = fundo
    ws.row_dimensions[row_idx].height = 18
 
 
class XlsxBuilder:
    """Gera arquivos XLSX para os 4 tipos de relatório do SCE."""
 
    # ── Diretório temporário para os arquivos gerados ──────────────────────
 
    @staticmethod
    def _dir_temp() -> Path:
        d = Path("relatorios_temp")
        d.mkdir(exist_ok=True)
        return d
 
    @staticmethod
    def _nome_arquivo(tipo: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return XlsxBuilder._dir_temp() / f"SCE_{tipo}_{ts}.xlsx"
 
    # ── 1. Movimentação por período ────────────────────────────────────────
 
    @staticmethod
    def movimentacao(data_ini: date, data_fim: date) -> Path:
        """
        Relatório de movimentações (entradas e saídas) no período com células mescladas.
        RF-15: inclui produto, lote, NF, tipo, quantidade, usuário e data.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Movimentação"
        st = _wb_styles()
 
        colunas = [
            ("Data/Hora", 18), ("Produto", 50), ("Lote", 14),
            ("Nota Fiscal", 14), ("Tipo", 16), ("Quantidade", 12),
            ("Usuário", 20), ("Observação", 45),
        ]
        inicio = dt.combine(data_ini, dt.min.time())
        fim    = dt.combine(data_fim, dt.max.time())
        hoje = date.today()

        with get_read_session() as s:
            movs = (
                s.query(Movimentacao)
                .join(Lote)
                .join(Produto)
                .join(Usuario)
                .options(
                    joinedload(Movimentacao.lote).joinedload(Lote.produto),
                    joinedload(Movimentacao.usuario),
                )
                .filter(Movimentacao.data_hora.between(inicio, fim))
                .order_by(Movimentacao.data_hora.desc())
                .all()
            )
            
            # --- 1. CONFIGURAÇÃO DA LINHA 1 (PERÍODO E TOTAL) ---
            ws.row_dimensions[1].height = 25
            
            # Mesclagem A1:D1 para o Período
            ws.merge_cells('A1:D1')
            cell_p = ws['A1']
            cell_p.value = f"Período: {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
            cell_p.font = Font(bold=True, color=COR_HEADER_FILL, size=11)
            cell_p.alignment = Alignment(horizontal="center", vertical="center")

            # Mesclagem G1:H1 para o Total de Movimentações
            ws.merge_cells('G1:H1')
            cell_t = ws['G1']
            cell_t.value = f"Total: {len(movs)} registros"
            cell_t.font = Font(bold=True, color=COR_HEADER_FILL, size=11)
            cell_t.alignment = Alignment(horizontal="center", vertical="center")

            # --- 2. LINHA 2: TÍTULOS DAS COLUNAS ---
            _aplicar_header(ws, colunas, st, row_idx=2)
 
            # Definição de alinhamentos para os dados
            alinhamentos_da_linha = [
                st["center"], # Data/Hora
                st["left"],   # Produto
                st["center"], # Lote
                st["center"], # Nota Fiscal
                st["center"], # Tipo
                st["center"], # Quantidade
                st["center"], # Usuário
                st["left"]    # Observação
            ]

            # --- 3. LINHA 3 EM DIANTE: DADOS ---
            for i, mov in enumerate(movs, 3):
                vencido = mov.lote.data_vencimento < hoje
                fill = st["vf"] if vencido else None
                font = st["vft"] if vencido else None
                
                _aplicar_linha(ws, i, [
                    mov.data_hora.strftime("%d/%m/%Y %H:%M"),
                    mov.lote.produto.nome,
                    mov.lote.num_lote,
                    mov.numero_nf or mov.lote.nota_fiscal,
                    mov.tipo.value.replace("_", " ").title(),
                    mov.quantidade,
                    mov.usuario.nome,
                    mov.observacao or "",
                ], st, fill=fill, font=font, alignments=alinhamentos_da_linha)
                
        # Congela as duas linhas superiores
        ws.freeze_panes = "A3"

        _buf = _io_bg.BytesIO()
        wb.save(_buf)
        _bytes_final = _aplicar_background(_buf.getvalue())
        caminho = XlsxBuilder._nome_arquivo("movimentacao")
        Path(caminho).write_bytes(_bytes_final)
        logger.info("Relatório movimentação gerado: %s", caminho)
        return caminho
 
    # ── 2. Estoque atual ───────────────────────────────────────────────────
 
    @staticmethod
    def estoque_atual() -> Path:
        """
        Posição atual do estoque por lote.
        RF-16: produto, lote, NF, datas, saldo, valor e situação.
        Lotes vencidos em vermelho (RF-22).
        """
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Estoque Atual"
        st = _wb_styles()
 
        colunas = [
            ("Produto", 35), ("Centro", 14), ("Lote", 14),
            ("Nota Fiscal", 14), ("Fabricação", 14), ("Vencimento", 14),
            ("Qtd. Inicial", 12), ("Qtd. Atual", 12),
            ("Vlr. Unit. (R$)", 14), ("Vlr. Total (R$)", 14), ("Situação", 16),
        ]

 
        hoje = date.today()
        with get_read_session() as s:
            lotes = (
                s.query(Lote)
                .join(Produto)
                .options(joinedload(Lote.produto))
                .filter(Produto.ativo == True, Lote.quantidade_atual > 0)
                .order_by(Produto.nome, Lote.data_vencimento)
                .all()
            )
             # --- 1. CONFIGURAÇÃO DA LINHA 1 (PERÍODO E TOTAL) ---
            ws.row_dimensions[1].height = 25
            
            # Mesclagem A1:D1 para o Período
            ws.merge_cells('A1:K1')
            cell_p = ws['A1']
            cell_p.value = f"Estoque {date.today()}"
            cell_p.font = Font(bold=True, color=COR_HEADER_FILL, size=11)
            cell_p.alignment = Alignment(horizontal="center", vertical="center")

            # --- 2. LINHA 2: TÍTULOS DAS COLUNAS ---
            _aplicar_header(ws, colunas, st, row_idx=2)
            for i, l in enumerate(lotes, 3):
                diff  = (l.data_vencimento - hoje).days
                vencido = l.data_vencimento < hoje
 
                if vencido:
                    situacao = "VENCIDO"
                    fill, font = st["vf"], st["vft"]
                elif diff <= 7:
                    situacao = f"Vence em {diff}d"
                    fill, font = st["af"], st["aft"]
                elif diff <= 15:
                    situacao = f"Vence em {diff}d"
                    fill, font = st["af"], st["aft"]
                else:
                    situacao = "Normal"
                    fill, font = None, None
 
                _aplicar_linha(ws, i, [
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.nota_fiscal,
                    l.data_fabricacao.strftime("%d/%m/%Y") if l.data_fabricacao else "—",
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    l.quantidade_inicial,
                    l.quantidade_atual,
                    float(l.valor_unitario),
                    float(l.valor_total),
                    situacao,
                ], st, fill=fill, font=font)
 
        ws.freeze_panes = "A3"
        _buf = _io_bg.BytesIO()
        wb.save(_buf)
        _bytes_final = _aplicar_background(_buf.getvalue())
        caminho = XlsxBuilder._nome_arquivo("estoque_atual")
        Path(caminho).write_bytes(_bytes_final)
        logger.info("Relatório estoque atual gerado: %s", caminho)
        return caminho
 
    # ── 3. Produtos a vencer em 30 dias ────────────────────────────────────
 
    @staticmethod
    def a_vencer(dias: int = 30) -> Path:
        """
        Lista lotes com vencimento nos próximos N dias (padrão 30).
        RF-17: ordenado por data de vencimento crescente.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = f"A Vencer ({dias}d)"
        st = _wb_styles()
 
        colunas = [
            ("Produto", 35), ("Centro", 14), ("Lote", 14),
            ("Nota Fiscal", 14), ("Vencimento", 14),
            ("Dias restantes", 14), ("Qtd. Atual", 12), ("Situação", 16),
        ]
 
        hoje   = date.today()
        limite = hoje + timedelta(days=dias)
 
        with get_read_session() as s:
            lotes = (
                s.query(Lote)
                .join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True,
                    Lote.quantidade_atual > 0,
                    Lote.data_vencimento >= hoje,
                    Lote.data_vencimento <= limite,
                )
                .order_by(Lote.data_vencimento)
                .all()
            )
            
            # Mesclagem A1:D1 para o Período
            ws.merge_cells('A1:H1')
            cell_p = ws['A1']
            cell_p.value = f"Lotes a vencer Proximos 30 Dias consulta {date.today()}"
            cell_p.font = Font(bold=True, color=COR_HEADER_FILL, size=11)
            cell_p.alignment = Alignment(horizontal="center", vertical="center")
            
            _aplicar_header(ws, colunas, st, row_idx=2)

            for i, l in enumerate(lotes, 3):
                diff = (l.data_vencimento - hoje).days
                if diff <= 2:
                    fill, font, sit = st["vf"], st["vft"], "Crítico"
                elif diff <= 7:
                    fill, font, sit = st["af"], st["aft"], "Urgente"
                else:
                    fill, font, sit = None, None, "Atenção"
 
                _aplicar_linha(ws, i, [
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.nota_fiscal,
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    diff,
                    l.quantidade_atual,
                    sit,
                ], st, fill=fill, font=font)
 
        ws.freeze_panes = "A3"
        _buf = _io_bg.BytesIO()
        wb.save(_buf)
        _bytes_final = _aplicar_background(_buf.getvalue())
        caminho = XlsxBuilder._nome_arquivo("a_vencer")
        Path(caminho).write_bytes(_bytes_final)
        logger.info("Relatório a vencer gerado: %s (%d lotes)", caminho, len(lotes))
        return caminho
 
    # ── 4. Lotes vencidos em estoque ───────────────────────────────────────
 
    @staticmethod
    def lotes_vencidos() -> Path:
        """
        Lista lotes com data de vencimento anterior a hoje com saldo > 0.
        RF-22: todos destacados em vermelho.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Lotes Vencidos"
        st = _wb_styles()
 
        hoje = date.today()
        
        with get_read_session() as s:
            # 1. Busca os lotes primeiro para ter os dados de contagem e valor
            lotes = (
                s.query(Lote)
                .join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True,
                    Lote.quantidade_atual > 0,
                    Lote.data_vencimento < hoje,
                )
                .order_by(Lote.data_vencimento)
                .all()
            )

            # 2. Configura a Top Bar (Linha 1) - Título com a data do dia
            ws.row_dimensions[1].height = 30
            ws.merge_cells('A1:L1')
            cell_titulo = ws['A1']
            cell_titulo.value = f"Lotes vencidos em estoque no dia {hoje.strftime('%d/%m/%Y')}"
            cell_titulo.font = Font(bold=True, color=COR_HEADER_FONT, size=12)
            cell_titulo.fill = PatternFill("solid", fgColor=COR_HEADER_FILL)
            cell_titulo.alignment = Alignment(horizontal="center", vertical="center")

            # 3. Cabeçalhos das Colunas (Linha 2, Colunas A até I)
            colunas = [
                ("Produto", 35), ("Centro", 14), ("Fornecedor", 25),
                ("Lote", 14), ("Nota Fiscal", 14), ("Vencimento", 14),
                ("Dias vencido", 14), ("Qtd. em estoque", 15),
                ("Valor em estoque (R$)", 22),
            ]
            _aplicar_header(ws, colunas, st, row_idx=2)

            valor_total_geral = sum(l.valor_unitario * l.quantidade_atual for l in lotes)
            
            cell_resumo = ws['J2']
            cell_resumo.value = (
                f"Total de Lotes: {len(lotes)} vencidos")
            
            # Estilo do quadro de resumo
            cell_resumo.font = Font(bold=True, color=COR_HEADER_FONT, size=11)
            cell_resumo.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell_resumo.border = st["border"]
            cell_resumo.fill = PatternFill("solid", fgColor=COR_HEADER_FILL)

            ws.merge_cells('J3:J4')
            cell_total= ws['J3']
            cell_total.value=(f"Valor: {valor_total_geral}")

            cell_total.font = Font(bold=True, color=COR_HEADER_FONT, size=11)
            cell_total.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell_total.border = st["border"]
            cell_total.fill = PatternFill("solid", fgColor=COR_VENCIDO_FONT)

            ws.column_dimensions['J'].width = 30

            # 5. Preenchimento dos Dados (A partir da Linha 3)
            alinhamentos = [st["left"], st["center"], st["left"], st["center"], 
                            st["center"], st["center"], st["center"], st["center"], st["center"]]

            for i, l in enumerate(lotes, 3):
                dias_vencido = (hoje - l.data_vencimento).days
                valor_em_estoque = l.valor_unitario * l.quantidade_atual
 
                # Todos vencidos → destaque em vermelho (RF-22)
                _aplicar_linha(ws, i, [
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.produto.fornecedor or "—",
                    l.num_lote,
                    l.nota_fiscal,
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    dias_vencido,
                    l.quantidade_atual,
                    float(valor_em_estoque),
                ], st, fill=st["vf"], font=st["vft"], alignments=alinhamentos)
 
        ws.freeze_panes = "A3" # Congela Título e Cabeçalho
        _buf = _io_bg.BytesIO()
        wb.save(_buf)
        _bytes_final = _aplicar_background(_buf.getvalue())
        caminho = XlsxBuilder._nome_arquivo("lotes_vencidos")
        Path(caminho).write_bytes(_bytes_final)
        logger.info("Relatório lotes vencidos gerado: %s (%d lotes)", caminho, len(lotes))
        return caminho