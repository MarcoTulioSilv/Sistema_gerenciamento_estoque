"""
MOD-07 · Modulo_07_patrimonio · etiqueta_builder.py

Layout único em milímetros (AD-17) e os renderizadores de etiqueta: ZPL
(impressão a cabo) e PDF vetorial (arquivo unitário e folha A4).

DIMENSÕES — Anexo A da ERS v1.8, calibradas para 203 dpi:
    etiqueta          100 x 50 mm
    QR Code           29 x 29 mm  · versão 3, ECC M, módulo 1,000 mm (8 pts)
    Code 128          42 x 8 mm   · módulo 0,375 mm (3 pts), conteúdo = tombo puro
    nome da clínica   fonte 4 mm, duas linhas ("Centro de" / "Uro-Nefrologia")
    tombo             fonte 11 mm
    ícone da clínica  10 mm de altura, canto superior direito
    zona de silêncio  QR: 4 mm · Code128: 20 mm à direita

LAYOUT — modelo aprovado em documentacao/exemplo etiqueta tombo.pdf: QR no
canto superior esquerdo, nome da clínica em duas linhas e tombo grande ao
lado, ícone da clínica (assets/etiqueta_logo_icone.png, recorte de
assets/logo_Centro_Uro_Nefrologia_sem_fundo_sem_letras.png) no canto
superior direito, Code 128 na base. A baseline do tombo (POS_TOMBO_Y_MM)
foi calibrada para nunca colidir com o ícone acima dela, testado com um
tombo de 10 caracteres — folga que sobra independe do quão longo o tombo
fique, já que o ícone ocupa uma faixa vertical fixa acima da faixa do
tombo (não uma faixa horizontal, que dependeria do comprimento da string).

O QR é desenhado a partir da MESMA matriz de módulos (segno, versão 3
forçada, boost_error desligado) tanto no ZPL (bitmap ^GFA módulo a módulo)
quanto no PDF (retângulo a retângulo) — garante equivalência dimensional
exata entre as duas saídas (AD-17), sem depender de auto-seleção de
versão/ECC pelo firmware da impressora. O Code 128 não precisa desse
cuidado: é determinístico (mesmos dados + mesma largura de módulo sempre
produzem o mesmo padrão de barras), então o ZPL usa o comando nativo ^BC e
o PDF usa python-barcode — ambos com o mesmo dado e a mesma largura de
módulo em mm.

O ícone da clínica segue o mesmo raciocínio do QR: mesma imagem de origem
para as duas saídas, convertida para bitmap ^GFA no ZPL (limiar de alfa,
_gfa_bitmap_logo) e desenhada como imagem vetorial no PDF (_desenhar_logo)
— não depende do bem, então o bitmap ZPL é gerado uma única vez por
chamada de gerar_zpl(), não por etiqueta.

LIMITAÇÃO CONHECIDA: a calibração final (módulo realmente saindo a
1,000 mm / 0,375 mm na Elgin L42Pro) não foi verificada contra a impressora
física — este ambiente não tem acesso a ela. A matemática mm→pontos usa a
aproximação de 8 pontos/mm que a própria ERS adota para 203 dpi
(203/25,4 ≈ 7,99). O ZPL nativo não tem um peso "negrito" para a fonte
escalável ^A0 sem carregar uma fonte customizada na impressora — o tombo é
aproximado por um tamanho de fonte maior (11 mm), não por negrito real.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import segno
from barcode import Code128
from barcode.writer import ImageWriter

logger = logging.getLogger(__name__)

# Ícone da clínica (já recortado sem a margem em branco do PNG original —
# ver assets/logo_Centro_Uro_Nefrologia_sem_fundo_sem_letras.png) — fundo
# transparente, RGB preto sólido com alfa variável.
_LOGO_ARQUIVO = Path(__file__).resolve().parent.parent / "assets" / "etiqueta_logo_icone.png"
_logo_dimensoes_cache: tuple[int, int] | None = None


def _dimensoes_logo() -> tuple[int, int]:
    """(largura_px, altura_px) do ícone — lido uma vez, cacheado em memória."""
    global _logo_dimensoes_cache
    if _logo_dimensoes_cache is None:
        from PIL import Image as PILImage
        with PILImage.open(_LOGO_ARQUIVO) as im:
            _logo_dimensoes_cache = im.size
    return _logo_dimensoes_cache

# ─── Layout (mm) ──────────────────────────────────────────────────────────────

ETIQUETA_LARGURA_MM = 100.0
ETIQUETA_ALTURA_MM = 50.0

QR_TAMANHO_MM = 29.0
QR_VERSAO = 3
QR_ERROR = "m"
QR_MODULOS = 29  # versão 3 = 29x29 módulos
QR_MODULO_MM = QR_TAMANHO_MM / QR_MODULOS  # 1,000 mm

CODE128_LARGURA_MM = 42.0
CODE128_ALTURA_MM = 8.0
CODE128_MODULO_MM = 0.375

# Nome da clínica em duas linhas (layout do modelo aprovado,
# documentacao/exemplo etiqueta tombo.pdf) — mais estreito que numa linha
# só, o que garante folga horizontal em relação ao ícone no canto superior
# direito, qualquer que seja o comprimento do tombo abaixo.
NOME_CLINICA_L1 = "Centro de"
NOME_CLINICA_L2 = "Uro-Nefrologia"
NOME_CLINICA_FONTE_MM = 4.0
NOME_CLINICA_ENTRELINHA_MM = 4.6
TOMBO_FONTE_MM = 11.0

LOGO_ALTURA_MM = 10.0
LOGO_MARGEM_TOPO_MM = 3.0
LOGO_MARGEM_DIREITA_MM = 3.0

ZONA_SILENCIO_QR_MM = 4.0
ZONA_SILENCIO_CODE128_MM = 20.0

DOTS_POR_MM = 8  # 203 dpi ~ 8 dots/mm — mesma aproximação usada na ERS v1.8

# Posições — distância, em mm, do canto superior esquerdo da etiqueta até o
# canto superior esquerdo de cada elemento. QR ancorado no topo (não
# centralizado): QR (29mm) + zona de silêncio (4mm) = 33mm, deixando 17mm
# livres para o Code128 (8mm) com folga entre os dois — centralizar
# verticalmente encostaria o QR no Code128 (29 + 2*10,5 = 50, sem margem
# nenhuma sobrando entre eles).
POS_QR_X_MM = ZONA_SILENCIO_QR_MM
POS_QR_Y_MM = ZONA_SILENCIO_QR_MM

POS_TEXTO_X_MM = POS_QR_X_MM + QR_TAMANHO_MM + 4.0
POS_NOME_Y_MM = 8.0
# Baseline do tombo: verificada empiricamente (não só por métrica de fonte
# teórica) renderizando um tombo de 10 caracteres e conferindo visualmente
# que nem a linha 2 do nome nem o ícone (y1 = 3+10 = 13mm) encostam nele —
# 30mm deixa folga real dos dois lados, testada com "PAT-000123".
POS_TOMBO_Y_MM = 30.0

POS_CODE128_X_MM = ZONA_SILENCIO_QR_MM
POS_CODE128_Y_MM = ETIQUETA_ALTURA_MM - CODE128_ALTURA_MM - 4.0

# Ícone da clínica: canto superior direito, y1 = 3 + 10 = 13mm — sempre
# ACIMA de POS_TOMBO_Y_MM (30mm), por design: garante zero sobreposição
# com o tombo não importa o quão largo o texto fique (tombos mais longos
# no futuro não colidem com o ícone), sem depender de calcular a largura
# real da string a cada etiqueta.
POS_LOGO_Y_MM = LOGO_MARGEM_TOPO_MM


class EtiquetaBuilderError(Exception):
    """Erro interno de geração — o service traduz para as exceções do MOD-07."""


# ─── Payload e matriz do QR ───────────────────────────────────────────────────

def montar_payload(tombo: str, host: str, porta: str) -> str:
    return f"http://{host}:{porta}/p?t={tombo}"


def _matriz_qr(payload: str) -> list[list[bool]]:
    try:
        qr = segno.make(payload, error=QR_ERROR, version=QR_VERSAO, boost_error=False)
    except Exception as exc:  # segno.DataOverflowError e afins
        raise EtiquetaBuilderError(
            f"Payload do QR excede a capacidade da versão {QR_VERSAO}/ECC {QR_ERROR.upper()}: {exc}"
        ) from exc
    return [[bool(v) for v in linha] for linha in qr.matrix]


# ─── ZPL (impressão a cabo) ───────────────────────────────────────────────────

def _gfa_bitmap_qr(matriz: list[list[bool]], modulo_dots: int) -> str:
    """
    Converte a matriz de módulos do QR num campo gráfico ^GFA do ZPL, com
    cada módulo replicado num bloco modulo_dots x modulo_dots — garante que
    o módulo impresso meça exatamente modulo_dots pontos (RNF-15).
    """
    n = len(matriz)
    largura_px = n * modulo_dots
    bytes_por_linha = (largura_px + 7) // 8

    linhas_hex: list[str] = []
    for linha_modulos in matriz:
        pixels: list[bool] = []
        for modulo in linha_modulos:
            pixels.extend([modulo] * modulo_dots)
        pixels.extend([False] * (bytes_por_linha * 8 - len(pixels)))

        linha_bytes = bytearray()
        for i in range(0, len(pixels), 8):
            byte = 0
            for bit in range(8):
                if pixels[i + bit]:
                    byte |= 1 << (7 - bit)
            linha_bytes.append(byte)
        hex_linha = linha_bytes.hex().upper()
        linhas_hex.extend([hex_linha] * modulo_dots)  # replica a linha na vertical

    dados = "".join(linhas_hex)
    total_bytes = bytes_por_linha * len(linhas_hex)
    return f"^GFA,{total_bytes},{total_bytes},{bytes_por_linha},{dados}"


_gfa_logo_cache: tuple[str, int, int] | None = None


def _gfa_bitmap_logo(altura_dots: int) -> tuple[str, int]:
    """
    Bitmap ^GFA do ícone da clínica — mesma técnica de _gfa_bitmap_qr, mas a
    partir do PNG pré-recortado (RGB preto sólido, alfa variável) em vez de
    uma matriz de módulos. Não depende do bem, então é gerado uma única vez
    por processo (cacheado), não por etiqueta. Devolve (campo_GFA, largura
    em dots), já que a largura varia com a proporção real do ícone.
    """
    global _gfa_logo_cache
    if _gfa_logo_cache is not None and _gfa_logo_cache[2] == altura_dots:
        return _gfa_logo_cache[0], _gfa_logo_cache[1]

    from PIL import Image as PILImage
    largura_px, altura_px = _dimensoes_logo()
    largura_dots = round(altura_dots * largura_px / altura_px)
    with PILImage.open(_LOGO_ARQUIVO) as im:
        im_redim = im.resize((largura_dots, altura_dots), PILImage.LANCZOS)
        alfa = im_redim.convert("RGBA").split()[3]

    bytes_por_linha = (largura_dots + 7) // 8
    linhas_hex: list[str] = []
    for y in range(altura_dots):
        linha_bytes = bytearray()
        for byte_idx in range(bytes_por_linha):
            byte = 0
            for bit in range(8):
                x = byte_idx * 8 + bit
                if x < largura_dots and alfa.getpixel((x, y)) > 127:
                    byte |= 1 << (7 - bit)
            linha_bytes.append(byte)
        linhas_hex.append(linha_bytes.hex().upper())

    dados = "".join(linhas_hex)
    total_bytes = bytes_por_linha * altura_dots
    gfa = f"^GFA,{total_bytes},{total_bytes},{bytes_por_linha},{dados}"
    _gfa_logo_cache = (gfa, largura_dots, altura_dots)
    return gfa, largura_dots


def gerar_zpl(bens, host: str, porta: str) -> bytes:
    """Um bloco ^XA...^XZ por bem, concatenados — um job só, várias etiquetas."""
    largura_dots = round(ETIQUETA_LARGURA_MM * DOTS_POR_MM)
    altura_dots = round(ETIQUETA_ALTURA_MM * DOTS_POR_MM)
    modulo_qr_dots = round(QR_MODULO_MM * DOTS_POR_MM)
    modulo_code128_dots = round(CODE128_MODULO_MM * DOTS_POR_MM)
    h_nome_dots = round(NOME_CLINICA_FONTE_MM * DOTS_POR_MM)
    h_tombo_dots = round(TOMBO_FONTE_MM * DOTS_POR_MM)
    entrelinha_dots = round(NOME_CLINICA_ENTRELINHA_MM * DOTS_POR_MM)
    h_code_dots = round(CODE128_ALTURA_MM * DOTS_POR_MM)

    x_qr = round(POS_QR_X_MM * DOTS_POR_MM)
    y_qr = round(POS_QR_Y_MM * DOTS_POR_MM)
    x_texto = round(POS_TEXTO_X_MM * DOTS_POR_MM)
    y_nome_l1 = round(POS_NOME_Y_MM * DOTS_POR_MM)
    y_nome_l2 = y_nome_l1 + entrelinha_dots
    y_tombo = round(POS_TOMBO_Y_MM * DOTS_POR_MM)
    x_code = round(POS_CODE128_X_MM * DOTS_POR_MM)
    y_code = round(POS_CODE128_Y_MM * DOTS_POR_MM)

    altura_logo_dots = round(LOGO_ALTURA_MM * DOTS_POR_MM)
    gfa_logo, largura_logo_dots = _gfa_bitmap_logo(altura_logo_dots)
    x_logo = largura_dots - round(LOGO_MARGEM_DIREITA_MM * DOTS_POR_MM) - largura_logo_dots
    y_logo = round(POS_LOGO_Y_MM * DOTS_POR_MM)

    partes: list[str] = []
    for bem in bens:
        payload = montar_payload(bem.tombo, host, porta)
        matriz = _matriz_qr(payload)
        gfa_qr = _gfa_bitmap_qr(matriz, modulo_qr_dots)

        zpl = (
            "^XA"
            f"^PW{largura_dots}^LL{altura_dots}"
            f"^FO{x_qr},{y_qr}{gfa_qr}^FS"
            f"^FO{x_logo},{y_logo}{gfa_logo}^FS"
            f"^FO{x_texto},{y_nome_l1}^A0N,{h_nome_dots},{h_nome_dots}^FD{NOME_CLINICA_L1}^FS"
            f"^FO{x_texto},{y_nome_l2}^A0N,{h_nome_dots},{h_nome_dots}^FD{NOME_CLINICA_L2}^FS"
            f"^FO{x_texto},{y_tombo}^A0N,{h_tombo_dots},{h_tombo_dots}^FD{bem.tombo}^FS"
            f"^FO{x_code},{y_code}^BY{modulo_code128_dots},2,{h_code_dots}"
            f"^BCN,{h_code_dots},N,N,N^FD{bem.tombo}^FS"
            "^XZ"
        )
        partes.append(zpl)

    return "".join(partes).encode("utf-8")


def listar_impressoras() -> list[str]:
    import win32print
    impressoras = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    return [nome for _, _, nome, _ in impressoras]


def imprimir_cabo(zpl_bytes: bytes, nome_impressora: str) -> None:
    import win32print
    try:
        handle = win32print.OpenPrinter(nome_impressora)
    except Exception as exc:
        raise EtiquetaBuilderError(f"Não foi possível abrir a impressora '{nome_impressora}': {exc}") from exc

    try:
        job = win32print.StartDocPrinter(handle, 1, ("Etiquetas MOD-07", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, zpl_bytes)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
        logger.info("Job de etiqueta enviado: impressora=%s job_id=%s", nome_impressora, job)
    except Exception as exc:
        raise EtiquetaBuilderError(f"Falha ao enviar etiqueta para '{nome_impressora}': {exc}") from exc
    finally:
        win32print.ClosePrinter(handle)


# ─── PDF vetorial (arquivo unitário e folha A4) ───────────────────────────────

def _desenhar_qr(c, matriz: list[list[bool]], x_mm: float, y_topo_mm: float,
                 tamanho_mm: float, altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM
    n = len(matriz)
    modulo_pt = (tamanho_mm * MM) / n
    y_topo_pt = (altura_pagina_mm - y_topo_mm) * MM  # y do topo do QR, origem embaixo
    x_base_pt = x_mm * MM

    for linha_idx, linha in enumerate(matriz):
        y_linha_pt = y_topo_pt - (linha_idx + 1) * modulo_pt
        for col_idx, escuro in enumerate(linha):
            if not escuro:
                continue
            x_pt = x_base_pt + col_idx * modulo_pt
            c.rect(x_pt, y_linha_pt, modulo_pt, modulo_pt, fill=1, stroke=0)


def _desenhar_code128(c, tombo: str, x_mm: float, y_topo_mm: float, altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM
    from reportlab.lib.utils import ImageReader

    code = Code128(tombo, writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf, options={
        "module_width": CODE128_MODULO_MM,
        "module_height": CODE128_ALTURA_MM,
        "quiet_zone": 0.0,
        "write_text": False,
    })
    buf.seek(0)
    imagem = ImageReader(buf)

    y_base_pt = (altura_pagina_mm - y_topo_mm - CODE128_ALTURA_MM) * MM
    c.drawImage(imagem, x_mm * MM, y_base_pt,
                width=CODE128_LARGURA_MM * MM, height=CODE128_ALTURA_MM * MM,
                preserveAspectRatio=False, mask="auto")


def _desenhar_logo(c, x_direita_mm: float, y_topo_mm: float, altura_mm: float,
                   altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM
    from reportlab.lib.utils import ImageReader

    largura_px, altura_px = _dimensoes_logo()
    largura_mm = altura_mm * (largura_px / altura_px)
    x0_mm = x_direita_mm - largura_mm
    y_base_pt = (altura_pagina_mm - y_topo_mm - altura_mm) * MM
    c.drawImage(ImageReader(str(_LOGO_ARQUIVO)), x0_mm * MM, y_base_pt,
                width=largura_mm * MM, height=altura_mm * MM,
                preserveAspectRatio=True, mask="auto")


def _desenhar_etiqueta(c, bem, host: str, porta: str, origem_x_mm: float,
                       origem_y_topo_mm: float, altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM

    payload = montar_payload(bem.tombo, host, porta)
    matriz = _matriz_qr(payload)

    _desenhar_qr(c, matriz, origem_x_mm + POS_QR_X_MM, origem_y_topo_mm + POS_QR_Y_MM,
                QR_TAMANHO_MM, altura_pagina_mm)
    _desenhar_code128(c, bem.tombo, origem_x_mm + POS_CODE128_X_MM,
                      origem_y_topo_mm + POS_CODE128_Y_MM, altura_pagina_mm)
    _desenhar_logo(c, origem_x_mm + ETIQUETA_LARGURA_MM - LOGO_MARGEM_DIREITA_MM,
                   origem_y_topo_mm + POS_LOGO_Y_MM, LOGO_ALTURA_MM, altura_pagina_mm)

    # Tamanho da fonte em pt = valor em mm da ERS convertido direto (reportlab
    # usa pt como unidade de tamanho de fonte; 1mm da ERS = 1mm nominal aqui).
    c.setFont("Helvetica-Bold", NOME_CLINICA_FONTE_MM * MM)
    y_l1_pt = (altura_pagina_mm - origem_y_topo_mm - POS_NOME_Y_MM) * MM
    c.drawString((origem_x_mm + POS_TEXTO_X_MM) * MM, y_l1_pt, NOME_CLINICA_L1)
    y_l2_pt = y_l1_pt - NOME_CLINICA_ENTRELINHA_MM * MM
    c.drawString((origem_x_mm + POS_TEXTO_X_MM) * MM, y_l2_pt, NOME_CLINICA_L2)

    c.setFont("Helvetica-Bold", TOMBO_FONTE_MM * MM)
    y_tombo_pt = (altura_pagina_mm - origem_y_topo_mm - POS_TOMBO_Y_MM) * MM
    c.drawString((origem_x_mm + POS_TEXTO_X_MM) * MM, y_tombo_pt, bem.tombo)


def _desenhar_marcas_corte(c, x0_mm: float, y0_topo_mm: float, altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM
    tam = 3.0  # mm de comprimento de cada traço de corte
    x1 = x0_mm * MM
    x2 = (x0_mm + ETIQUETA_LARGURA_MM) * MM
    y1 = (altura_pagina_mm - y0_topo_mm) * MM
    y2 = (altura_pagina_mm - y0_topo_mm - ETIQUETA_ALTURA_MM) * MM

    c.setLineWidth(0.3)
    for x in (x1, x2):
        c.line(x, y1, x, y1 - tam * MM)
        c.line(x, y2, x, y2 + tam * MM)
    for y in (y1, y2):
        c.line(x1, y, x1 + tam * MM, y)
        c.line(x2, y, x2 - tam * MM, y)


def gerar_pdf_unitario(bens, host: str, porta: str) -> bytes:
    """Uma página de 100x50mm por bem — RF-28.3."""
    from reportlab.pdfgen import canvas as rl_canvas

    tamanho_pagina = (_mm_para_pt(ETIQUETA_LARGURA_MM), _mm_para_pt(ETIQUETA_ALTURA_MM))
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=tamanho_pagina)
    for bem in bens:
        _desenhar_etiqueta(c, bem, host, porta, origem_x_mm=0, origem_y_topo_mm=0,
                          altura_pagina_mm=ETIQUETA_ALTURA_MM)
        c.showPage()
    c.save()
    return buf.getvalue()


def gerar_pdf_folha(bens, host: str, porta: str) -> bytes:
    """Folha A4 em grade, com marcas de corte — RF-28.3."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    a4_largura_mm, a4_altura_mm = 210.0, 297.0
    margem_mm = 10.0
    cols = max(1, int((a4_largura_mm - 2 * margem_mm) // ETIQUETA_LARGURA_MM))
    rows = max(1, int((a4_altura_mm - 2 * margem_mm) // ETIQUETA_ALTURA_MM))
    por_pagina = cols * rows

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    for i, bem in enumerate(bens):
        pos = i % por_pagina
        if pos == 0 and i > 0:
            c.showPage()
        col, row = pos % cols, pos // cols
        x0_mm = margem_mm + col * ETIQUETA_LARGURA_MM
        y0_topo_mm = margem_mm + row * ETIQUETA_ALTURA_MM
        _desenhar_etiqueta(c, bem, host, porta, x0_mm, y0_topo_mm, a4_altura_mm)
        _desenhar_marcas_corte(c, x0_mm, y0_topo_mm, a4_altura_mm)
    c.showPage()
    c.save()
    return buf.getvalue()


def _mm_para_pt(valor_mm: float) -> float:
    from reportlab.lib.units import mm as MM
    return valor_mm * MM
