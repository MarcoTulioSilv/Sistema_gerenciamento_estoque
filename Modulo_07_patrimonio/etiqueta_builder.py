"""
MOD-07 · Modulo_07_patrimonio · etiqueta_builder.py

Layout único em milímetros (AD-17) e os renderizadores de etiqueta: ZPL
(impressão a cabo) e PDF vetorial (arquivo unitário e folha A4).

DIMENSÕES — Anexo A da ERS v1.8, calibradas para 203 dpi:
    etiqueta          100 x 50 mm
    QR Code           29 x 29 mm  · versão 3, ECC M, módulo 1,000 mm (8 pts)
    Code 128          42 x 8 mm   · módulo 0,375 mm (3 pts), conteúdo = tombo puro
    nome da clínica   fonte 4 mm, linha única
    tombo             fonte 11 mm
    zona de silêncio  QR: 4 mm · Code128: 20 mm à direita

O QR é desenhado a partir da MESMA matriz de módulos (segno, versão 3
forçada, boost_error desligado) tanto no ZPL (bitmap ^GFA módulo a módulo)
quanto no PDF (retângulo a retângulo) — garante equivalência dimensional
exata entre as duas saídas (AD-17), sem depender de auto-seleção de
versão/ECC pelo firmware da impressora. O Code 128 não precisa desse
cuidado: é determinístico (mesmos dados + mesma largura de módulo sempre
produzem o mesmo padrão de barras), então o ZPL usa o comando nativo ^BC e
o PDF usa python-barcode — ambos com o mesmo dado e a mesma largura de
módulo em mm.

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

import segno
from barcode import Code128
from barcode.writer import ImageWriter

logger = logging.getLogger(__name__)

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

NOME_CLINICA = "Centro de Uronefrologia"
NOME_CLINICA_FONTE_MM = 4.0
TOMBO_FONTE_MM = 11.0

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
POS_TOMBO_Y_MM = 18.0

POS_CODE128_X_MM = ZONA_SILENCIO_QR_MM
POS_CODE128_Y_MM = ETIQUETA_ALTURA_MM - CODE128_ALTURA_MM - 4.0


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


def gerar_zpl(bens, host: str, porta: str) -> bytes:
    """Um bloco ^XA...^XZ por bem, concatenados — um job só, várias etiquetas."""
    largura_dots = round(ETIQUETA_LARGURA_MM * DOTS_POR_MM)
    altura_dots = round(ETIQUETA_ALTURA_MM * DOTS_POR_MM)
    modulo_qr_dots = round(QR_MODULO_MM * DOTS_POR_MM)
    modulo_code128_dots = round(CODE128_MODULO_MM * DOTS_POR_MM)
    h_nome_dots = round(NOME_CLINICA_FONTE_MM * DOTS_POR_MM)
    h_tombo_dots = round(TOMBO_FONTE_MM * DOTS_POR_MM)
    h_code_dots = round(CODE128_ALTURA_MM * DOTS_POR_MM)

    x_qr = round(POS_QR_X_MM * DOTS_POR_MM)
    y_qr = round(POS_QR_Y_MM * DOTS_POR_MM)
    x_texto = round(POS_TEXTO_X_MM * DOTS_POR_MM)
    y_nome = round(POS_NOME_Y_MM * DOTS_POR_MM)
    y_tombo = round(POS_TOMBO_Y_MM * DOTS_POR_MM)
    x_code = round(POS_CODE128_X_MM * DOTS_POR_MM)
    y_code = round(POS_CODE128_Y_MM * DOTS_POR_MM)

    partes: list[str] = []
    for bem in bens:
        payload = montar_payload(bem.tombo, host, porta)
        matriz = _matriz_qr(payload)
        gfa = _gfa_bitmap_qr(matriz, modulo_qr_dots)

        zpl = (
            "^XA"
            f"^PW{largura_dots}^LL{altura_dots}"
            f"^FO{x_qr},{y_qr}{gfa}^FS"
            f"^FO{x_texto},{y_nome}^A0N,{h_nome_dots},{h_nome_dots}^FD{NOME_CLINICA}^FS"
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


def _desenhar_etiqueta(c, bem, host: str, porta: str, origem_x_mm: float,
                       origem_y_topo_mm: float, altura_pagina_mm: float):
    from reportlab.lib.units import mm as MM

    payload = montar_payload(bem.tombo, host, porta)
    matriz = _matriz_qr(payload)

    _desenhar_qr(c, matriz, origem_x_mm + POS_QR_X_MM, origem_y_topo_mm + POS_QR_Y_MM,
                QR_TAMANHO_MM, altura_pagina_mm)
    _desenhar_code128(c, bem.tombo, origem_x_mm + POS_CODE128_X_MM,
                      origem_y_topo_mm + POS_CODE128_Y_MM, altura_pagina_mm)

    # Tamanho da fonte em pt = valor em mm da ERS convertido direto (reportlab
    # usa pt como unidade de tamanho de fonte; 1mm da ERS = 1mm nominal aqui).
    c.setFont("Helvetica", NOME_CLINICA_FONTE_MM * MM)
    y_nome_pt = (altura_pagina_mm - origem_y_topo_mm - POS_NOME_Y_MM) * MM
    c.drawString((origem_x_mm + POS_TEXTO_X_MM) * MM, y_nome_pt, NOME_CLINICA)

    c.setFont("Helvetica-Bold", TOMBO_FONTE_MM * MM)
    y_tombo_pt = (altura_pagina_mm - origem_y_topo_mm - POS_TOMBO_Y_MM-2) * MM
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
