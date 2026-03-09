"""
styles.py — Hoja de estilos global para JJGT Vehículos Colombia
Importar en app.py:  from styles import get_css
Usar con:            st.markdown(get_css(), unsafe_allow_html=True)
"""

def get_css() -> str:
    return """
<style>
/* ══════════════════════════════════════════
   VARIABLES DE COLOR JJGT
══════════════════════════════════════════ */
:root {
    --jjgt-red:      #C41E3A;
    --jjgt-red-dark: #9B1729;
    --jjgt-gold:     #F5A623;
    --jjgt-navy:     #1A1A2E;
    --jjgt-navy2:    #2E2E5A;
    --jjgt-bg:       #F4F5F7;
    --jjgt-card:     #FFFFFF;
    --jjgt-text:     #1A1A2E;
    --jjgt-muted:    #6B6B8A;
    --jjgt-border:   #E5E7EB;
    --jjgt-radius:   14px;
    --jjgt-shadow:   0 2px 16px rgba(0,0,0,.08);
}

/* ══════════════════════════════════════════
   LAYOUT PRINCIPAL — igual local y web
══════════════════════════════════════════ */
/* Fondo general */
.stApp,
[data-testid="stAppViewContainer"] {
    background: var(--jjgt-bg) !important;
    font-family: 'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif !important;
}

/* Contenedor central — móvil-first, máximo 500px */
[data-testid="stMainBlockContainer"],
.block-container,
.main .block-container {
    max-width: 500px !important;
    padding: 1rem 1rem 4rem 1rem !important;
    margin: 0 auto !important;
}

/* Quitar padding extra del main en ambos entornos */
section[data-testid="stMain"] > div:first-child {
    padding-top: 0.5rem !important;
}

/* ══════════════════════════════════════════
   HEADER / FOOTER STREAMLIT — ocultar
══════════════════════════════════════════ */
#MainMenu { visibility: hidden !important; }
footer    { visibility: hidden !important; }
.stDeployButton { display: none !important; }

header[data-testid="stHeader"] {
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
}

/* Botón abrir/cerrar sidebar — siempre visible */
[data-testid="collapsedControl"],
button[data-testid="baseButton-header"] {
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    z-index: 999999 !important;
    position: fixed !important;
    top: 0.4rem !important;
    left: 0.4rem !important;
    background: rgba(196,30,58,0.85) !important;
    border-radius: 8px !important;
    color: white !important;
}

/* ══════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--jjgt-navy) 0%, var(--jjgt-navy2) 100%) !important;
}
[data-testid="stSidebar"] * {
    color: #fff !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,.08) !important;
    border: 1px solid rgba(255,255,255,.15) !important;
    color: #fff !important;
    border-radius: 10px !important;
    transition: background .2s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(196,30,58,.5) !important;
}

/* ══════════════════════════════════════════
   BOTONES GLOBALES
══════════════════════════════════════════ */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 0.5rem 1rem !important;
    transition: all .18s ease !important;
    border: none !important;
}

/* Botón primario */
.stButton > button[kind="primary"],
.stButton > button[data-testid*="primary"] {
    background: linear-gradient(135deg, var(--jjgt-red), var(--jjgt-red-dark)) !important;
    color: #fff !important;
    box-shadow: 0 3px 12px rgba(196,30,58,.3) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 18px rgba(196,30,58,.45) !important;
}

/* Botón secundario */
.stButton > button[kind="secondary"] {
    background: var(--jjgt-card) !important;
    color: var(--jjgt-text) !important;
    border: 1.5px solid var(--jjgt-border) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--jjgt-red) !important;
    color: var(--jjgt-red) !important;
}

/* ══════════════════════════════════════════
   FORMULARIOS / INPUTS
══════════════════════════════════════════ */
.stTextInput input,
.stTextArea textarea,
.stSelectbox select,
.stNumberInput input {
    border-radius: 10px !important;
    border: 1.5px solid var(--jjgt-border) !important;
    padding: 0.5rem 0.75rem !important;
    font-size: 14px !important;
    background: var(--jjgt-card) !important;
    transition: border-color .2s !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus {
    border-color: var(--jjgt-red) !important;
    box-shadow: 0 0 0 3px rgba(196,30,58,.12) !important;
}

/* Labels */
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stNumberInput label,
.stCheckbox label,
.stRadio label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--jjgt-text) !important;
}

/* ══════════════════════════════════════════
   CARDS / CONTAINERS
══════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--jjgt-radius) !important;
    border: 1px solid var(--jjgt-border) !important;
    box-shadow: var(--jjgt-shadow) !important;
    background: var(--jjgt-card) !important;
    padding: 12px !important;
}

/* ══════════════════════════════════════════
   MÉTRICAS
══════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--jjgt-card) !important;
    border-radius: var(--jjgt-radius) !important;
    padding: 12px 16px !important;
    border: 1px solid var(--jjgt-border) !important;
    box-shadow: var(--jjgt-shadow) !important;
}
[data-testid="stMetricLabel"] { font-size: 12px !important; color: var(--jjgt-muted) !important; }
[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 800 !important; color: var(--jjgt-red) !important; }

/* ══════════════════════════════════════════
   ALERTAS
══════════════════════════════════════════ */
.stAlert {
    border-radius: 12px !important;
    font-size: 13px !important;
}

/* ══════════════════════════════════════════
   TABS
══════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 6px 14px !important;
    color: var(--jjgt-muted) !important;
}
.stTabs [aria-selected="true"] {
    background: var(--jjgt-red) !important;
    color: #fff !important;
}

/* ══════════════════════════════════════════
   RADIO / TOGGLE
══════════════════════════════════════════ */
.stRadio [data-testid="stWidgetLabel"] { font-weight: 700 !important; }
.stToggle > label { font-size: 13px !important; }

/* ══════════════════════════════════════════
   DIVIDERS
══════════════════════════════════════════ */
hr {
    border: none !important;
    border-top: 1px solid var(--jjgt-border) !important;
    margin: 1rem 0 !important;
}

/* ══════════════════════════════════════════
   SCROLLBAR
══════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--jjgt-red); border-radius: 4px; }

/* ══════════════════════════════════════════
   SPINNER
══════════════════════════════════════════ */
.stSpinner > div { border-top-color: var(--jjgt-red) !important; }

/* ══════════════════════════════════════════
   IMAGEN / FOTO
══════════════════════════════════════════ */
.stImage img {
    border-radius: var(--jjgt-radius) !important;
    max-width: 100% !important;
}
</style>
"""
