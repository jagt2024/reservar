"""
Plan de Negocio Estratégico — Powered by Claude AI
=====================================================
"""

import streamlit as st
import anthropic
import io
import re
from datetime import datetime

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

# ═══════════════════════════════════════════════════════════════════════════
#  ESTILOS GLOBALES DE LA APP
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Plan Estratégico de Negocio",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap');

  /* ── Base ── */
  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
  .stApp { background: #0a0e1a; color: #e8eaf0; }

  /* ── Hero banner ── */
  .hero {
    background: linear-gradient(135deg, #0d1b2e 0%, #1a2a4a 50%, #0f2040 100%);
    border: 1px solid rgba(99,179,237,0.18);
    border-radius: 20px;
    padding: 3rem 3.5rem 2.5rem;
    margin-bottom: 2.5rem;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(99,179,237,0.08) 0%, transparent 70%);
    border-radius: 50%;
  }
  .hero-tag {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #63b3ed;
    background: rgba(99,179,237,0.1);
    border: 1px solid rgba(99,179,237,0.25);
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 20px;
    margin-bottom: 1rem;
  }
  .hero h1 {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 900;
    color: #f0f4ff;
    line-height: 1.15;
    margin: 0 0 0.8rem;
  }
  .hero p {
    font-size: 1.05rem;
    color: rgba(232,234,240,0.65);
    font-weight: 300;
    max-width: 520px;
    margin: 0;
    line-height: 1.7;
  }

  /* ── Card / Panel ── */
  .card {
    background: #111827;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.5rem;
  }
  .card-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #c9d6f5;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }
  .card-sub {
    font-size: 0.82rem;
    color: rgba(200,210,230,0.45);
    margin-bottom: 1.2rem;
  }

  /* ── Input overrides ── */
  textarea, input[type="text"] {
    background: #1a2235 !important;
    border: 1.5px solid rgba(99,179,237,0.2) !important;
    border-radius: 10px !important;
    color: #e8eaf0 !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: border-color 0.25s;
  }
  textarea:focus, input[type="text"]:focus {
    border-color: rgba(99,179,237,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,179,237,0.08) !important;
  }
  label { color: #a8b8d8 !important; font-size: 0.88rem !important; font-weight: 500 !important; }

  /* ── Buttons ── */
  .stButton > button {
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    font-size: 0.95rem;
    border-radius: 10px;
    padding: 0.65rem 1.8rem;
    transition: all 0.22s ease;
    border: none;
    cursor: pointer;
    letter-spacing: 0.01em;
  }
  /* Primary generate button */
  div[data-testid="stButton"]:first-of-type > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white;
    box-shadow: 0 4px 18px rgba(37,99,235,0.35);
  }
  div[data-testid="stButton"]:first-of-type > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 7px 25px rgba(37,99,235,0.5);
  }
  /* Download button */
  .stDownloadButton > button {
    background: linear-gradient(135deg, #065f46, #047857) !important;
    color: white !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 0.65rem 1.8rem !important;
    box-shadow: 0 4px 18px rgba(6,95,70,0.4) !important;
    transition: all 0.22s !important;
    border: none !important;
  }
  .stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 25px rgba(6,95,70,0.55) !important;
  }

  /* ── Result sections ── */
  .result-wrapper {
    background: #0f1926;
    border: 1px solid rgba(99,179,237,0.12);
    border-radius: 16px;
    padding: 2.5rem;
    margin-top: 1.5rem;
  }
  .section-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 0.28rem 0.85rem;
    border-radius: 20px;
    margin-bottom: 0.8rem;
  }
  .chip-blue   { background: rgba(59,130,246,0.15);  color: #93c5fd; border: 1px solid rgba(59,130,246,0.25); }
  .chip-purple { background: rgba(139,92,246,0.15);  color: #c4b5fd; border: 1px solid rgba(139,92,246,0.25); }
  .chip-green  { background: rgba(16,185,129,0.15);  color: #6ee7b7; border: 1px solid rgba(16,185,129,0.25); }
  .chip-amber  { background: rgba(245,158,11,0.15);  color: #fcd34d; border: 1px solid rgba(245,158,11,0.25); }
  .chip-rose   { background: rgba(244,63,94,0.15);   color: #fda4af; border: 1px solid rgba(244,63,94,0.25); }

  .section-heading {
    font-family: 'Playfair Display', serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: #dde6ff;
    margin: 0 0 0.7rem;
    line-height: 1.3;
  }
  .section-body {
    font-size: 0.93rem;
    color: rgba(210,220,240,0.82);
    line-height: 1.78;
    white-space: pre-wrap;
  }
  .divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 2rem 0;
  }

  /* ── Spinner ── */
  .stSpinner > div { border-top-color: #3b82f6 !important; }

  /* ── Alerts ── */
  .stAlert { border-radius: 10px !important; }

  /* ── Footer ── */
  .footer {
    text-align: center;
    font-size: 0.78rem;
    color: rgba(150,165,195,0.4);
    padding: 2rem 0 1rem;
    border-top: 1px solid rgba(255,255,255,0.05);
    margin-top: 3rem;
  }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════
SECTIONS = [
    ("📋", "RESUMEN EJECUTIVO",         "chip-blue"),
    ("🎯", "MERCADOS OBJETIVO PRIORITARIOS", "chip-purple"),
    ("⚔️",  "ANÁLISIS COMPETITIVO",      "chip-green"),
    ("💡", "PROPUESTA DE VALOR ÚNICA",  "chip-amber"),
    ("🗺️", "PLAN DE ACCIÓN ESTRATÉGICO","chip-rose"),
]

SYSTEM_PROMPT = """Eres un consultor estratégico de negocios de clase mundial con más de 20 años de experiencia en empresas Fortune 500, startups disruptivas y expansion internacional. Tu análisis es profundo, accionable y basado en datos de mercado actualizados.

Cuando generes un plan de negocio estratégico, usa EXACTAMENTE el siguiente formato de secciones con estos títulos precisos:

## RESUMEN EJECUTIVO
[Contenido aquí]

## MERCADOS OBJETIVO PRIORITARIOS
[Contenido aquí]

## ANÁLISIS COMPETITIVO
[Contenido aquí]

## PROPUESTA DE VALOR ÚNICA
[Contenido aquí]

## PLAN DE ACCIÓN ESTRATÉGICO
[Contenido aquí]

Reglas de formato:
- Usa texto rico con viñetas (•), numeración y sub-secciones donde sea relevante
- Sé específico, concreto y accionable en cada punto
- Incluye métricas, porcentajes o datos de referencia cuando sea pertinente
- Mínimo 250 palabras por sección
- Responde siempre en español
"""


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def parse_sections(raw: str) -> dict:
    """Extrae el contenido de cada sección del texto generado."""
    titles = [s[1] for s in SECTIONS]
    pattern = r"##\s+(" + "|".join(re.escape(t) for t in titles) + r")\s*\n"
    parts   = re.split(pattern, raw, flags=re.IGNORECASE)

    result = {t: "" for t in titles}
    i = 1
    while i < len(parts) - 1:
        key     = parts[i].strip().upper()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        for t in titles:
            if t in key:
                result[t] = content
                break
        i += 2
    return result


def generate_plan(business_name: str, business_desc: str) -> str:
    """Llama a la API de Claude y devuelve el texto completo."""
    client = anthropic.Anthropic()          # usa la variable de entorno ANTHROPIC_API_KEY
    prompt = (
        f"Empresa / Negocio: {business_name}\n\n"
        f"Descripción del negocio:\n{business_desc}\n\n"
        "Genera un plan de negocio estratégico completo y detallado para esta empresa, "
        "siguiendo exactamente el formato de secciones indicado."
    )
    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ── PDF ────────────────────────────────────────────────────────────────────

DARK_BG   = colors.HexColor("#0a0e1a")
MID_BG    = colors.HexColor("#111827")
ACCENT    = colors.HexColor("#3b82f6")
LIGHT_TXT = colors.HexColor("#e8eaf0")
MUTED_TXT = colors.HexColor("#8899bb")
WHITE     = colors.white

CHIP_COLORS = {
    "RESUMEN EJECUTIVO":              colors.HexColor("#3b82f6"),
    "MERCADOS OBJETIVO PRIORITARIOS": colors.HexColor("#8b5cf6"),
    "ANÁLISIS COMPETITIVO":           colors.HexColor("#10b981"),
    "PROPUESTA DE VALOR ÚNICA":       colors.HexColor("#f59e0b"),
    "PLAN DE ACCIÓN ESTRATÉGICO":     colors.HexColor("#f43f5e"),
}


def _add_page_deco(canvas_obj, doc):
    """Dibuja encabezado y pie en cada página."""
    w, h = A4
    canvas_obj.saveState()

    # Fondo oscuro total
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, w, h, stroke=0, fill=1)

    # Barra superior
    canvas_obj.setFillColor(ACCENT)
    canvas_obj.rect(0, h - 6*mm, w, 6*mm, stroke=0, fill=1)

    # Pie de página
    canvas_obj.setFillColor(colors.HexColor("#1e293b"))
    canvas_obj.rect(0, 0, w, 12*mm, stroke=0, fill=1)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(MUTED_TXT)
    canvas_obj.drawString(20*mm, 4*mm, "Plan de Negocio Estratégico — Generado con IA")
    canvas_obj.drawRightString(w - 20*mm, 4*mm,
        f"Página {doc.page}  •  {datetime.now().strftime('%d/%m/%Y')}")

    canvas_obj.restoreState()


def build_pdf(business_name: str, sections: dict) -> bytes:
    """Construye el PDF y devuelve los bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=22*mm, bottomMargin=20*mm,
    )

    base = getSampleStyleSheet()

    # Estilos personalizados
    title_style = ParagraphStyle(
        "MainTitle",
        fontName="Helvetica-Bold",
        fontSize=26,
        textColor=WHITE,
        leading=32,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "SubTitle",
        fontName="Helvetica",
        fontSize=12,
        textColor=MUTED_TXT,
        leading=16,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "Meta",
        fontName="Helvetica",
        fontSize=9,
        textColor=MUTED_TXT,
        leading=14,
    )
    chip_style = ParagraphStyle(
        "Chip",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=WHITE,
        leading=12,
    )
    sec_title_style = ParagraphStyle(
        "SecTitle",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=WHITE,
        leading=18,
        spaceBefore=6,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.HexColor("#c9d6f0"),
        leading=15,
        spaceAfter=4,
        alignment=TA_JUSTIFY,
    )

    story = []

    # ── Portada ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 18*mm))

    # Caja de portada con color de fondo simulada via tabla
    cover_data = [[
        Paragraph(
            f'<font color="#3b82f6">▬▬</font>  PLAN DE NEGOCIO ESTRATÉGICO',
            meta_style,
        )
    ]]
    cover_tbl = Table(cover_data, colWidths=[166*mm])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
        ("ROUNDEDCORNERS", [8]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 10*mm))

    story.append(Paragraph(business_name, title_style))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Análisis estratégico integral: mercados, competencia y propuesta de valor", subtitle_style))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d de %B de %Y')}  •  Powered by Claude AI",
        meta_style,
    ))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#1e3a5f"),
        spaceAfter=10*mm,
    ))

    # ── Índice rápido ─────────────────────────────────────────────────────
    index_rows = [[
        Paragraph("CONTENIDO DEL DOCUMENTO", ParagraphStyle(
            "IdxHdr", fontName="Helvetica-Bold", fontSize=8,
            textColor=ACCENT, leading=12,
        )),
    ]]
    for i, (icon, title, _) in enumerate(SECTIONS, 1):
        index_rows.append([
            Paragraph(f"{i}.  {icon}  {title}", ParagraphStyle(
                "IdxItem", fontName="Helvetica", fontSize=9,
                textColor=colors.HexColor("#a0b4d0"), leading=16,
            )),
        ])
    idx_tbl = Table(index_rows, colWidths=[166*mm])
    idx_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#0d1829")),
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#0d1829")),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor("#1e3a5f")),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("ROUNDEDCORNERS", [8]),
    ]))
    story.append(idx_tbl)
    story.append(PageBreak())

    # ── Secciones ─────────────────────────────────────────────────────────
    for icon, title, _ in SECTIONS:
        content = sections.get(title, "").strip()
        chip_color = CHIP_COLORS.get(title, ACCENT)

        # Chip de sección
        chip_data = [[Paragraph(f"{icon}  {title}", chip_style)]]
        chip_tbl = Table(chip_data, colWidths=[None])
        chip_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), chip_color),
            ("ROUNDEDCORNERS", [12]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))
        story.append(chip_tbl)
        story.append(Spacer(1, 4*mm))

        story.append(Paragraph(title, sec_title_style))

        # Línea de acento
        story.append(HRFlowable(
            width="100%", thickness=1.5,
            color=chip_color, spaceAfter=6*mm,
        ))

        # Contenido: convertir markdown bullets/bold a tags reportlab
        for raw_line in content.split("\n"):
            line = raw_line.rstrip()
            if not line:
                story.append(Spacer(1, 2*mm))
                continue
            # Convertir **texto** → <b>texto</b>
            line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            # Escapar caracteres problemáticos (excepto tags ya insertados)
            line = line.replace("&", "&amp;").replace("<b>", "<<B>>").replace("</b>", "<</B>>")
            line = line.replace("<", "&lt;").replace("<<B>>", "<b>").replace("<</B>>", "</b>")
            if line.startswith("• ") or line.startswith("- ") or line.startswith("* "):
                txt = "    •  " + line[2:]
            elif re.match(r"^\d+\.", line):
                txt = "    " + line
            else:
                txt = line
            story.append(Paragraph(txt, body_style))

        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#1e293b"),
            spaceAfter=8*mm,
        ))
        story.append(PageBreak())

    doc.build(story, onFirstPage=_add_page_deco, onLaterPages=_add_page_deco)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  UI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

# ── Hero ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-tag">🧭 Consultoría estratégica con IA</div>
  <h1>Plan de Negocio<br>Estratégico</h1>
  <p>Genera en segundos un análisis completo: mercados objetivo,
     panorama competitivo y propuesta de valor única — impulsado por Claude AI.</p>
</div>
""", unsafe_allow_html=True)

# ── Formulario ────────────────────────────────────────────────────────────
col_l, col_r = st.columns([1, 1], gap="large")

with col_l:
    st.markdown("""
    <div class="card">
      <div class="card-title">🏢 Datos del negocio</div>
      <div class="card-sub">Completa los campos para personalizar tu análisis</div>
    </div>
    """, unsafe_allow_html=True)

    business_name = st.text_input(
        "Nombre de la empresa / negocio",
        placeholder="Ej: TechNova Solutions",
        key="biz_name",
    )
    business_desc = st.text_area(
        "Descripción del tipo de negocio",
        placeholder=(
            "Describe en detalle tu negocio: sector, productos o servicios, "
            "modelo de ingresos, etapa actual, geografía de operación, "
            "clientes actuales y cualquier diferenciador que ya tengas..."
        ),
        height=220,
        key="biz_desc",
    )

with col_r:
    st.markdown("""
    <div class="card">
      <div class="card-title">🔍 ¿Qué incluye el plan?</div>
      <div class="card-sub">Cinco secciones estratégicas de alto impacto</div>
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("📋", "chip-blue",   "Resumen Ejecutivo",          "Visión general, misión y objetivos clave del negocio."),
        ("🎯", "chip-purple", "Mercados Objetivo",          "Identificación y priorización de segmentos de expansión."),
        ("⚔️",  "chip-green",  "Análisis Competitivo",       "Panorama del sector, rivales principales y brechas."),
        ("💡", "chip-amber",  "Propuesta de Valor Única",   "Diferenciadores concretos y posicionamiento de marca."),
        ("🗺️", "chip-rose",   "Plan de Acción Estratégico", "Hoja de ruta con hitos, KPIs y recursos requeridos."),
    ]
    for icon, chip, title, desc in features:
        st.markdown(f"""
        <div style="display:flex;align-items:flex-start;gap:1rem;padding:0.8rem 0;
                    border-bottom:1px solid rgba(255,255,255,0.05);">
          <span class="section-chip {chip}">{icon}</span>
          <div>
            <div style="font-weight:600;font-size:0.9rem;color:#c9d6f5;margin-bottom:2px;">{title}</div>
            <div style="font-size:0.8rem;color:rgba(180,195,220,0.55);line-height:1.5;">{desc}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── Botón Generar ─────────────────────────────────────────────────────────
st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
btn_col, _ = st.columns([1, 3])
with btn_col:
    generate_btn = st.button("⚡  Generar Plan Estratégico", use_container_width=True)

# ── Inicializar estado ────────────────────────────────────────────────────
if "plan_text"    not in st.session_state: st.session_state.plan_text    = None
if "plan_sections" not in st.session_state: st.session_state.plan_sections = {}
if "pdf_bytes"    not in st.session_state: st.session_state.pdf_bytes    = None
if "last_name"    not in st.session_state: st.session_state.last_name    = ""

# ── Lógica de generación ──────────────────────────────────────────────────
if generate_btn:
    if not business_name.strip():
        st.error("⚠️  Por favor ingresa el nombre de tu empresa o negocio.")
    elif not business_desc.strip():
        st.error("⚠️  Por favor describe el tipo de negocio para personalizar el análisis.")
    else:
        with st.spinner("🤖  Analizando tu negocio y generando el plan estratégico..."):
            try:
                raw = generate_plan(business_name.strip(), business_desc.strip())
                sections = parse_sections(raw)
                pdf_bytes = build_pdf(business_name.strip(), sections)

                st.session_state.plan_text     = raw
                st.session_state.plan_sections = sections
                st.session_state.pdf_bytes     = pdf_bytes
                st.session_state.last_name     = business_name.strip()
                st.success("✅  Plan estratégico generado con éxito.")
            except anthropic.AuthenticationError:
                st.error("🔑  Error de autenticación: verifica tu ANTHROPIC_API_KEY.")
            except Exception as e:
                st.error(f"❌  Error al generar el plan: {e}")

# ── Mostrar resultados ────────────────────────────────────────────────────
if st.session_state.plan_sections:
    sections  = st.session_state.plan_sections
    biz_name  = st.session_state.last_name
    pdf_bytes = st.session_state.pdf_bytes

    st.markdown(f"""
    <div class="result-wrapper">
      <div style="display:flex;align-items:center;justify-content:space-between;
                  flex-wrap:wrap;gap:1rem;margin-bottom:2rem;">
        <div>
          <div style="font-size:0.72rem;letter-spacing:0.18em;text-transform:uppercase;
                      color:#63b3ed;font-weight:600;margin-bottom:0.4rem;">
            Plan generado para
          </div>
          <div style="font-family:'Playfair Display',serif;font-size:1.8rem;
                      font-weight:900;color:#f0f4ff;">{biz_name}</div>
        </div>
      </div>
    """, unsafe_allow_html=True)

    for icon, title, chip in SECTIONS:
        content = sections.get(title, "Sin información generada.")
        st.markdown(f"""
        <span class="section-chip {chip}">{icon} {title}</span>
        <div class="section-heading">{title.title()}</div>
        <div class="section-body">{content}</div>
        <hr class="divider">
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Botón Descargar PDF ───────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    dl_col, _ = st.columns([1, 3])
    with dl_col:
        fname = f"plan_estrategico_{biz_name.lower().replace(' ', '_')}.pdf"
        st.download_button(
            label="📥  Descargar PDF",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  Powered by <strong>Claude AI (Anthropic)</strong> · Plan de Negocio Estratégico Generator
</div>
""", unsafe_allow_html=True)
