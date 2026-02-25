"""
Plan Estratégico de Negocio — Streamlit App
Powered by Claude AI (Anthropic)

Instalación:
    pip install streamlit anthropic

Ejecución:
    streamlit run plan_estrategico_app.py

Variables de entorno requeridas:
    ANTHROPIC_API_KEY=sk-ant-...
    (o ingresarla directamente en la barra lateral de la app)
"""

import streamlit as st
import anthropic
import random
import string
import time
from datetime import datetime

# ──────────────────────────────────────────────
# Configuración de página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Plan Estratégico con IA",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CSS personalizado
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Fondo degradado */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0f172a 100%);
        color: #f1f5f9;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.85);
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }

    /* Tarjetas / contenedores */
    .plan-card {
        background: rgba(15, 23, 42, 0.70);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
    }

    /* Badge de sección */
    .section-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }

    /* Botones principales */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all .25s;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(37, 99, 235, .35);
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1.5px solid rgba(148, 163, 184, 0.25) !important;
        color: white !important;
        border-radius: 8px !important;
    }

    /* Títulos */
    h1, h2, h3 {
        color: #f1f5f9 !important;
    }

    /* Ocultar menú hamburguesa de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Estado de sesión
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "step": "auth",           # auth | form | results
        "email": "",
        "sent_code": "",
        "authenticated": False,
        "business_name": "",
        "business_desc": "",
        "generated_plan": None,
        "api_key": "",
        "edit_section": None,
        "edit_content": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def get_client() -> anthropic.Anthropic:
    """Retorna cliente Anthropic usando la API key de la sesión o variable de entorno."""
    import os
    key = st.session_state.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        st.error("❌ Necesitas ingresar tu API Key de Anthropic en la barra lateral.")
        st.stop()
    return anthropic.Anthropic(api_key=key)


def send_mock_code(email: str) -> str:
    """Genera y 'envía' un código de 6 dígitos (simulado)."""
    code = "".join(random.choices(string.digits, k=6))
    st.toast(f"📧 Código de verificación enviado a {email}: **{code}** *(simulado)*", icon="📬")
    return code


SECTIONS = [
    "Resumen Ejecutivo",
    "Mercados Objetivo",
    "Análisis Competitivo",
    "Propuesta de Valor",
    "Plan de Acción",
]

SECTION_ICONS = {
    "Resumen Ejecutivo":   ("📋", "#3b82f6"),
    "Mercados Objetivo":   ("🎯", "#8b5cf6"),
    "Análisis Competitivo":("⚔️",  "#10b981"),
    "Propuesta de Valor":  ("💡", "#f59e0b"),
    "Plan de Acción":      ("🗺️", "#f43f5e"),
}

PROMPTS = {
    "Resumen Ejecutivo": """Eres un consultor estratégico experto. Crea un Resumen Ejecutivo profesional y detallado para:

Nombre del negocio: {name}
Descripción: {desc}

Incluye:
- Visión general del negocio y su contexto en el mercado actual
- Misión clara y concreta
- Visión a 5 años específica y medible
- 5-6 objetivos estratégicos clave con métricas
- Modelo de negocio resumido
- KPIs principales

Escribe mínimo 400 palabras. Sé específico y profesional.""",

    "Mercados Objetivo": """Eres un analista de mercado experto. Realiza un análisis de Mercados Objetivo para:

Nombre: {name}
Descripción: {desc}

Incluye:
- Marco TAM-SAM-SOM explicado con estimaciones
- 4 segmentos prioritarios específicos ordenados por prioridad
- Para cada segmento: características, estrategia de entrada, ticket promedio
- Estrategia de expansión geográfica por fases
- Mercado obtenible realista

Mínimo 400 palabras. Sé concreto y específico.""",

    "Análisis Competitivo": """Eres un estratega competitivo experto. Crea un Análisis Competitivo completo para:

Nombre: {name}
Descripción: {desc}

Incluye:
- Panorama competitivo del sector
- Categorías de competidores (directos, indirectos, potenciales)
- Análisis de las 5 Fuerzas de Porter aplicado al negocio
- 3-4 brechas u oportunidades concretas identificadas
- Posicionamiento competitivo recomendado

Mínimo 400 palabras.""",

    "Propuesta de Valor": """Eres un experto en branding y propuesta de valor. Define la Propuesta de Valor Única para:

Nombre: {name}
Descripción: {desc}

Incluye:
- Declaración de valor central específica y memorable
- 3 pilares de diferenciación concretos con argumentos
- Value Proposition Canvas: trabajos del cliente, dolores, ganancias
- Estrategia de comunicación por canal
- Cómo proteger y evolucionar la propuesta a futuro

Mínimo 400 palabras.""",

    "Plan de Acción": """Eres un consultor de implementación estratégica. Crea un Plan de Acción detallado para:

Nombre: {name}
Descripción: {desc}

Estructura en 3 fases:
- FASE 1: Fundamentos (Meses 1-3)
- FASE 2: Crecimiento (Meses 4-12)
- FASE 3: Consolidación (Meses 13-24)

Para cada fase: objetivo principal, 5-7 acciones prioritarias, KPIs específicos, recursos estimados.
Agrega: 4 riesgos principales con mitigaciones y acciones inmediatas para los próximos 30 días.

Mínimo 500 palabras. Sé práctico y accionable.""",
}


def generate_section(client: anthropic.Anthropic, section: str, name: str, desc: str) -> str:
    """Llama a la API de Claude para generar el contenido de una sección."""
    prompt = PROMPTS[section].format(name=name, desc=desc)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def generate_html_report(plan: dict) -> str:
    """Genera un HTML descargable con el plan completo."""
    sections_html = ""
    for title, content in plan["sections"].items():
        icon, _ = SECTION_ICONS.get(title, ("📄", "#2563eb"))
        paragraphs = "".join(
            f"<p>{p.strip()}</p>" for p in content.split("\n\n") if p.strip()
        )
        sections_html += f"""
        <div class="section">
            <h2>{icon} {title}</h2>
            {paragraphs}
        </div>"""

    date_str = datetime.fromisoformat(plan["created_at"]).strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Plan Estratégico — {plan["business_name"]}</title>
  <style>
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      line-height: 1.75;
      color: #1e293b;
      max-width: 820px;
      margin: 0 auto;
      padding: 48px 24px;
      background: #fff;
    }}
    .cover {{
      text-align: center;
      padding: 64px 0 40px;
      border-bottom: 3px solid #2563eb;
      margin-bottom: 48px;
    }}
    .cover h1 {{ font-size: 2.6em; color: #1e3a8a; margin-bottom: 10px; }}
    .cover .subtitle {{ color: #64748b; font-size: 1.1em; }}
    .cover .date {{ color: #94a3b8; margin-top: 16px; font-size: .9em; }}
    .section {{ margin-bottom: 48px; page-break-inside: avoid; }}
    .section h2 {{
      color: #2563eb;
      font-size: 1.5em;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 8px;
      margin-bottom: 20px;
    }}
    p {{ margin-bottom: 16px; text-align: justify; }}
    @media print {{ body {{ padding: 24px; }} }}
  </style>
</head>
<body>
  <div class="cover">
    <h1>{plan["business_name"]}</h1>
    <div class="subtitle">Plan de Negocio Estratégico · Generado con IA</div>
    <div class="date">{date_str}</div>
  </div>
  {sections_html}
</body>
</html>"""


# ──────────────────────────────────────────────
# Barra lateral — API Key
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    st.markdown("---")
    api_input = st.text_input(
        "🔑 Anthropic API Key",
        type="password",
        value=st.session_state.api_key,
        placeholder="sk-ant-...",
        help="Obtén tu API Key en console.anthropic.com",
    )
    if api_input:
        st.session_state.api_key = api_input

    st.markdown("---")
    st.markdown("**Modelo:** `claude-opus-4-6`")
    st.markdown("**Secciones generadas:** 5")
    st.markdown("**Tokens por sección:** ~2 048")

    st.markdown("---")
    if st.session_state.step == "results":
        if st.button("🔄 Nuevo Plan", use_container_width=True):
            for key in ["step", "business_name", "business_desc", "generated_plan", "edit_section", "edit_content"]:
                st.session_state[key] = ("form" if key == "step" else "" if isinstance(st.session_state[key], str) else None)
            st.rerun()

    st.markdown("---")
    st.caption("Powered by [Anthropic Claude](https://anthropic.com)")


# ──────────────────────────────────────────────
# Header principal
# ──────────────────────────────────────────────
col_h1, col_h2, col_h3 = st.columns([1, 3, 1])
with col_h2:
    st.markdown("""
    <div style='text-align:center; padding: 8px 0 24px;'>
        <div style='display:inline-block; padding:6px 18px; background:rgba(37,99,235,0.18);
                    border:1px solid rgba(37,99,235,0.35); border-radius:20px;
                    font-size:13px; font-weight:700; color:#93c5fd; margin-bottom:14px;'>
            ✨ Powered by Claude AI
        </div>
        <h1 style='font-size:clamp(26px,5vw,46px); font-weight:900; margin:10px 0;
                   background:linear-gradient(90deg,#93c5fd,#60a5fa);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
            Plan Estratégico de Negocio
        </h1>
        <p style='color:#94a3b8; font-size:17px; margin:0;'>
            Genera análisis estratégicos profesionales con inteligencia artificial
        </p>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# PASO 1 — AUTENTICACIÓN
# ══════════════════════════════════════════════
if st.session_state.step == "auth":
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown('<div class="plan-card">', unsafe_allow_html=True)
        st.markdown("### 🔐 Acceso a la Plataforma")
        st.caption("Ingresa tu email para recibir un código de acceso")
        st.divider()

        email = st.text_input("📧 Email", placeholder="tu@email.com", key="email_input")

        if not st.session_state.sent_code:
            if st.button("Enviar Código", type="primary", use_container_width=True):
                if not email or "@" not in email:
                    st.error("Por favor ingresa un email válido.")
                else:
                    code = send_mock_code(email)
                    st.session_state.sent_code = code
                    st.session_state.email = email
                    st.rerun()
        else:
            st.success(f"✅ Código enviado a **{st.session_state.email}**")
            code_input = st.text_input("🔑 Código de 6 dígitos", max_chars=6, placeholder="000000")
            if st.button("Verificar y Entrar", type="primary", use_container_width=True):
                if code_input == st.session_state.sent_code:
                    st.session_state.authenticated = True
                    st.session_state.step = "form"
                    st.success("¡Acceso concedido! Redirigiendo...")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error("Código incorrecto. Intenta de nuevo.")
            if st.button("Reenviar código", use_container_width=True):
                st.session_state.sent_code = ""
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
# PASO 2 — FORMULARIO
# ══════════════════════════════════════════════
elif st.session_state.step == "form":
    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        st.markdown('<div class="plan-card">', unsafe_allow_html=True)
        st.markdown("### 🏢 Cuéntanos sobre tu Negocio")
        st.caption("Con esta información generaremos un plan estratégico completo y personalizado.")
        st.divider()

        business_name = st.text_input(
            "Nombre del Negocio *",
            placeholder="Ej: TechStartup Colombia",
            value=st.session_state.business_name,
        )
        business_desc = st.text_area(
            "Descripción del Negocio *",
            placeholder=(
                "Describe tu negocio: ¿qué hace?, ¿a quién va dirigido?, "
                "¿cuál es tu propuesta de valor?, ¿en qué etapa está?..."
            ),
            value=st.session_state.business_desc,
            height=160,
        )

        chars = len(business_desc.strip())
        progress_color = "🟢" if chars >= 30 else "🔴"
        st.caption(f"{progress_color} {chars} / 30 caracteres mínimos")

        st.markdown('<br>', unsafe_allow_html=True)
        if st.button("✨ Generar Plan Estratégico", type="primary", use_container_width=True):
            if not business_name.strip():
                st.error("El nombre del negocio es obligatorio.")
            elif chars < 30:
                st.error("La descripción debe tener al menos 30 caracteres.")
            else:
                # Guardar datos y pasar a generación
                st.session_state.business_name = business_name.strip()
                st.session_state.business_desc = business_desc.strip()
                st.session_state.step = "generating"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
# PASO 2b — GENERACIÓN (se ejecuta en el rerun)
# ══════════════════════════════════════════════
elif st.session_state.step == "generating":
    st.markdown("---")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style='text-align:center; padding:32px 0 16px;'>
            <div style='font-size:56px; margin-bottom:12px;'>🧠</div>
            <h2>Generando tu Plan Estratégico</h2>
            <p style='color:#94a3b8;'>Claude AI está analizando tu negocio y elaborando cada sección…</p>
        </div>""", unsafe_allow_html=True)

    progress_bar = st.progress(0)
    status_text  = st.empty()

    client   = get_client()
    results  = {}
    n        = len(SECTIONS)

    for i, section in enumerate(SECTIONS):
        icon, _ = SECTION_ICONS.get(section, ("📄", ""))
        status_text.info(f"{icon} Generando **{section}**… ({i + 1}/{n})")
        progress_bar.progress((i + 1) / n)
        try:
            results[section] = generate_section(
                client,
                section,
                st.session_state.business_name,
                st.session_state.business_desc,
            )
        except Exception as e:
            st.error(f"Error generando '{section}': {e}")
            st.session_state.step = "form"
            st.stop()

    progress_bar.progress(1.0)
    status_text.success("✅ ¡Plan generado exitosamente!")

    st.session_state.generated_plan = {
        "business_name": st.session_state.business_name,
        "business_desc": st.session_state.business_desc,
        "sections": results,
        "created_at": datetime.now().isoformat(),
    }
    st.session_state.step = "results"
    time.sleep(0.6)
    st.rerun()


# ══════════════════════════════════════════════
# PASO 3 — RESULTADOS
# ══════════════════════════════════════════════
elif st.session_state.step == "results" and st.session_state.generated_plan:
    plan = st.session_state.generated_plan

    # ── Cabecera de resultados ──
    col_title, col_actions = st.columns([3, 2])
    with col_title:
        st.markdown(f"## 📊 {plan['business_name']}")
        date_str = datetime.fromisoformat(plan["created_at"]).strftime("%d %b %Y · %H:%M")
        st.caption(f"Generado el {date_str}")

    with col_actions:
        html_report = generate_html_report(plan)
        st.download_button(
            label="⬇️ Descargar HTML",
            data=html_report,
            file_name=f"plan_{plan['business_name'].replace(' ', '_')}.html",
            mime="text/html",
            use_container_width=True,
        )

    st.divider()

    # ── Secciones del plan ──
    for section, content in plan["sections"].items():
        icon, color = SECTION_ICONS.get(section, ("📄", "#2563eb"))
        is_editing  = st.session_state.edit_section == section

        with st.container():
            st.markdown(
                f'<span class="section-badge" style="background:rgba(59,130,246,.15);'
                f'border:1px solid rgba(59,130,246,.3);color:{color};">'
                f'{icon} {section.upper()}</span>',
                unsafe_allow_html=True,
            )

            col_hdr, col_btn = st.columns([9, 1])
            with col_hdr:
                st.markdown(f"### {section}")
            with col_btn:
                if not is_editing:
                    if st.button("✏️", key=f"edit_{section}", help=f"Editar {section}"):
                        st.session_state.edit_section  = section
                        st.session_state.edit_content  = content
                        st.rerun()
                else:
                    if st.button("❌", key=f"cancel_{section}", help="Cancelar edición"):
                        st.session_state.edit_section = None
                        st.rerun()

            if is_editing:
                new_content = st.text_area(
                    "Editar contenido",
                    value=st.session_state.edit_content,
                    height=350,
                    key=f"textarea_{section}",
                    label_visibility="collapsed",
                )
                col_s, col_c = st.columns(2)
                with col_s:
                    if st.button("💾 Guardar cambios", key=f"save_{section}", type="primary", use_container_width=True):
                        plan["sections"][section]       = new_content
                        st.session_state.generated_plan = plan
                        st.session_state.edit_section   = None
                        st.success(f"✅ '{section}' actualizado.")
                        st.rerun()
                with col_c:
                    if st.button("🔄 Regenerar con IA", key=f"regen_{section}", use_container_width=True):
                        with st.spinner(f"Regenerando {section}…"):
                            client = get_client()
                            plan["sections"][section] = generate_section(
                                client, section,
                                plan["business_name"], plan["business_desc"],
                            )
                            st.session_state.generated_plan = plan
                            st.session_state.edit_section   = None
                        st.success(f"✅ '{section}' regenerado.")
                        st.rerun()
            else:
                # Renderizar contenido como markdown limpio
                st.markdown(content)

            st.divider()

    # ── Pie de página ──
    st.markdown("""
    <div style='text-align:center; padding:24px 0; color:#64748b; font-size:13px;'>
        Generado con <strong>Claude AI</strong> · Plan Estratégico de Negocio
    </div>""", unsafe_allow_html=True)
