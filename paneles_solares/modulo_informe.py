"""
modulo_informe.py
──────────────────────────────────────────────────────────────────────────────
Utilidades compartidas para construir el "Informe Completo de Soporte":
un único PDF que reúne TODAS las secciones de un proyecto (cargas/recibo,
dimensionamiento, planos y diagramas, análisis económico y cableado),
sin importar si el proyecto es OFF-GRID, ON-GRID o HÍBRIDO.

Se apoya en:
- reportlab            → portada / índice (ya usado en el resto de la app)
- svglib               → convierte los planos SVG (vectoriales) en páginas PDF
- pypdf                → fusiona todos los PDF parciales en uno solo

No requiere red ni servicios externos: todo se genera localmente.
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Group

from pypdf import PdfReader, PdfWriter


# ─────────────────────────────────────────────────────────────────────────────
# 1. SVG (plano / diagrama) → página PDF independiente
# ─────────────────────────────────────────────────────────────────────────────
def svg_a_pdf_bytes(svg_string: str) -> bytes:
    """
    Convierte un SVG (como los generados para los planos de paneles y los
    diagramas unifilares) en una página PDF de tamaño A4 horizontal, con el
    dibujo centrado y escalado para que quepa completo en la hoja.

    Si el SVG no puede parsearse (formato inesperado), propaga la excepción
    para que el llamador decida si omite la sección o notifica al usuario.
    """
    drawing: Drawing = svg2rlg(io.StringIO(svg_string))
    if drawing is None:
        raise ValueError("No fue posible interpretar el SVG del plano.")

    page_w, page_h = landscape(A4)
    margin = 1.0 * cm
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin

    src_w = float(drawing.width) or 1.0
    src_h = float(drawing.height) or 1.0
    scale = min(avail_w / src_w, avail_h / src_h, 1.0)  # nunca amplía, solo reduce si es necesario
    if scale <= 0:
        scale = 1.0

    scaled_w = src_w * scale
    scaled_h = src_h * scale
    off_x = margin + (avail_w - scaled_w) / 2
    off_y = margin + (avail_h - scaled_h) / 2

    page = Drawing(page_w, page_h)
    # Fondo blanco explícito (los SVG usan fondo oscuro propio; A4 debe imprimirse bien)
    grp = Group(drawing)
    grp.transform = (scale, 0, 0, scale, off_x, off_y)
    page.add(grp)

    buf = io.BytesIO()
    renderPDF.drawToFile(page, buf, pagesize=(page_w, page_h))
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Portada + índice del informe consolidado
# ─────────────────────────────────────────────────────────────────────────────
def pagina_portada(nombre_proyecto: str, municipio: str, tipo_sistema: str,
                    secciones: list[str]) -> bytes:
    """
    Genera la portada del Informe Completo con el nombre del proyecto,
    municipio, tipo de sistema y el índice de secciones que contiene el PDF.
    """
    SOL   = colors.HexColor("#E68A00")   # ámbar más oscuro: legible sobre fondo blanco
    TEXT2 = colors.HexColor("#3E4C63")    # gris azulado oscuro, legible en impresión
    TEXT3 = colors.HexColor("#5D6B82")
    BORDER= colors.HexColor("#C7CEDB")
    _COL_TIPO = {"ON-GRID": colors.HexColor("#D9531E"),
                 "HIBRIDO": colors.HexColor("#B9720A")}.get(tipo_sistema, SOL)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             leftMargin=2.5*cm, rightMargin=2.5*cm,
                             topMargin=1.6*cm, bottomMargin=1.3*cm)

    titulo_st = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=26,
                                textColor=SOL, alignment=TA_CENTER, spaceAfter=14)
    sub_st    = ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=14,
                                textColor=_COL_TIPO, alignment=TA_CENTER, spaceAfter=18)
    meta_st   = ParagraphStyle("meta", fontName="Helvetica", fontSize=11,
                                textColor=TEXT2, alignment=TA_CENTER, spaceAfter=4)
    idx_hdr_st= ParagraphStyle("idx_hdr", fontName="Helvetica-Bold", fontSize=12,
                                textColor=SOL, spaceBefore=20, spaceAfter=8)
    idx_st    = ParagraphStyle("idx", fontName="Helvetica", fontSize=10.5,
                                textColor=TEXT2, leftIndent=6,
                                spaceAfter=4)
    foot_st   = ParagraphStyle("foot", fontName="Helvetica", fontSize=8,
                                textColor=TEXT3, alignment=TA_CENTER,
                                spaceBefore=10)

    story = []
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("SOLARCALC PRO", titulo_st))
    story.append(Paragraph("INFORME COMPLETO DE SOPORTE DEL PROYECTO", sub_st))
    story.append(HRFlowable(width="60%", thickness=1.2, color=_COL_TIPO, spaceAfter=16, hAlign="CENTER"))

    story.append(Paragraph(f"<b>Proyecto:</b> {nombre_proyecto or '—'}", meta_st))
    story.append(Paragraph(f"<b>Municipio:</b> {municipio or '—'}", meta_st))
    story.append(Paragraph(f"<b>Tipo de sistema:</b> {tipo_sistema}", meta_st))
    story.append(Paragraph(f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_st))

    story.append(Paragraph("CONTENIDO DE ESTE INFORME", idx_hdr_st))
    idx_rows = []
    for i, sec in enumerate(secciones, start=1):
        idx_rows.append([str(i), sec])
    if idx_rows:
        t = Table(idx_rows, colWidths=[1.2*cm, 18*cm])
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (0,0), (-1,-1), TEXT2),
            ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
            ("TEXTCOLOR", (0,0), (0,-1), SOL),
            ("FONTSIZE",  (0,0), (-1,-1), 10.5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Sin secciones disponibles.", idx_st))

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "Este documento reúne, en un solo archivo, la memoria de cálculo completa del "
        "dimensionamiento fotovoltaico: inventario de cargas y/o recibo de energía, tensión "
        "del sistema, hora solar pico, paneles, banco de baterías (si aplica), potencia, "
        "controlador/inversor, protecciones, planos de distribución, análisis económico-ambiental "
        "y memoria técnica de cableado. Sirve como soporte de lo realizado y para verificar la "
        "información suministrada y calculada.",
        ParagraphStyle("desc", fontName="Helvetica", fontSize=9.5,
                       textColor=TEXT3, alignment=TA_LEFT, leading=14)))

    story.append(Paragraph(f"SolarCalc Pro · Informe generado automáticamente · {datetime.now().year}", foot_st))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fusionar todos los PDF parciales en un solo documento
# ─────────────────────────────────────────────────────────────────────────────
def combinar_pdfs(partes: list[bytes]) -> bytes:
    """
    Une, en orden, una lista de PDFs (bytes) en un único documento.
    Ignora entradas vacías o None. Lanza ValueError si no queda ninguna
    parte válida para combinar.
    """
    writer = PdfWriter()
    incluidas = 0
    for parte in partes:
        if not parte:
            continue
        try:
            reader = PdfReader(io.BytesIO(parte))
            for page in reader.pages:
                writer.add_page(page)
            incluidas += 1
        except Exception:
            # Se omite la parte que no pudo leerse; el resto del informe continúa.
            continue

    if incluidas == 0:
        raise ValueError("No hay secciones válidas para generar el informe completo.")

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()
