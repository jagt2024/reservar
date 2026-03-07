"""
JJGT — Estilos CSS globales para Streamlit
"""

def get_css() -> str:
    return """
<style>
/* ── GOOGLE FONTS ── */
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700;800&display=swap');

/* ── VARIABLES ── */
:root {
    --primary: #C41E3A;
    --primary-dark: #9B1729;
    --secondary: #1A1A2E;
    --accent: #F5A623;
    --success: #00C9A7;
    --info: #2979FF;
    --warning: #F5A623;
    --error: #E53935;
    --bg: #F4F5F7;
    --surface: #FFFFFF;
    --text: #1A1A2E;
    --text2: #6B6B8A;
    --border: #E0E0EC;
    --radius: 18px;
    --font-display: 'Bebas Neue', 'Arial Black', sans-serif;
    --font-body: 'DM Sans', 'Segoe UI', sans-serif;
}

/* ── RESET & BASE ── */
* { font-family: var(--font-body) !important; }

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
}

/* ── HIDE STREAMLIT DEFAULTS ── */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* ── MAIN CONTENT ── */
[data-testid="stAppViewContainer"] > .main .block-container {
    padding: 1rem 2rem 2rem !important;
    max-width: 1200px !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #1A1A2E !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}
[data-testid="stSidebar"] * {
    color: #EAEAF5 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #EAEAF5 !important;
    border-radius: 12px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
    margin-bottom: 4px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(196,30,58,0.25) !important;
    border-color: rgba(196,30,58,0.5) !important;
    transform: translateX(3px);
}
[data-testid="stSidebar"] .stButton > [data-baseweb="button"][kind="primary"] > button,
[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, #C41E3A, #9B1729) !important;
    border-color: transparent !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1) !important;
}

/* ── BUTTONS ── */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: all 0.2s ease !important;
    border: none !important;
    padding: 10px 20px !important;
}
.stButton > button[kind="primary"],
button[kind="primary"] {
    background: linear-gradient(135deg, #C41E3A, #9B1729) !important;
    color: white !important;
    box-shadow: 0 4px 14px rgba(196,30,58,0.35) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(196,30,58,0.45) !important;
}
.stButton > button[kind="secondary"] {
    background: #F4F5F7 !important;
    color: #1A1A2E !important;
    border: 1.5px solid #E0E0EC !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #E8E9EE !important;
    transform: translateY(-1px) !important;
}

/* ── INPUTS ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    border-radius: 12px !important;
    border: 1.5px solid var(--border) !important;
    background: white !important;
    font-size: 14px !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(196,30,58,0.12) !important;
}
label {
    font-weight: 600 !important;
    font-size: 13px !important;
    color: var(--text2) !important;
}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {
    background: rgba(196,30,58,0.04) !important;
    border: 2px dashed rgba(196,30,58,0.3) !important;
    border-radius: 14px !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--primary) !important;
    background: rgba(196,30,58,0.07) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: white !important;
    border-radius: 14px !important;
    padding: 16px !important;
    box-shadow: 0 4px 20px rgba(26,26,46,0.08) !important;
    border: 1px solid var(--border) !important;
}
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: var(--primary) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 12px !important;
    color: var(--text2) !important;
}

/* ── EXPANDER ── */
.stExpander > details {
    background: white !important;
    border-radius: 12px !important;
    border: 1px solid var(--border) !important;
    margin-bottom: 8px !important;
}
.stExpander > details > summary {
    font-weight: 600 !important;
    padding: 14px 16px !important;
    font-size: 14px !important;
}

/* ── TABS (radio used as tabs) ── */
.stRadio > div {
    display: flex !important;
    gap: 8px !important;
    flex-wrap: wrap !important;
}
.stRadio label {
    background: #F4F5F7 !important;
    border-radius: 10px !important;
    padding: 8px 16px !important;
    cursor: pointer !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border: 1.5px solid transparent !important;
    transition: all 0.2s !important;
}
.stRadio label:hover {
    background: rgba(196,30,58,0.08) !important;
    border-color: rgba(196,30,58,0.3) !important;
}

/* ── DIVIDER ── */
hr {
    border: none !important;
    height: 1px !important;
    background: var(--border) !important;
    margin: 16px 0 !important;
}

/* ── ALERTS ── */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 12px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
.stSuccess { background: rgba(0,201,167,0.1) !important; }
.stInfo { background: rgba(41,121,255,0.1) !important; }
.stWarning { background: rgba(245,166,35,0.1) !important; }
.stError { background: rgba(229,57,53,0.1) !important; }

/* ── IMAGES ── */
[data-testid="stImage"] img {
    border-radius: 14px !important;
    max-height: 280px !important;
    object-fit: cover !important;
}

/* ── VIDEO ── */
[data-testid="stVideo"] video {
    border-radius: 14px !important;
}

/* ── TOGGLE ── */
.stCheckbox > label,
[data-testid="stCheckbox"] label {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--text) !important;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(196,30,58,0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(196,30,58,0.6); }

/* ── FORM ── */
[data-testid="stForm"] {
    background: white !important;
    border-radius: 18px !important;
    padding: 24px !important;
    box-shadow: 0 4px 20px rgba(26,26,46,0.08) !important;
    border: 1px solid var(--border) !important;
}

/* ── NUMBER INPUT BUTTONS ── */
[data-testid="stNumberInput"] button {
    border-radius: 8px !important;
    background: #F4F5F7 !important;
    border: 1px solid var(--border) !important;
}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {
    [data-testid="stAppViewContainer"] > .main .block-container {
        padding: 0.5rem 1rem 1rem !important;
    }
}

/* ── HEADING STYLES ── */
h1, h2, h3 {
    font-family: var(--font-display) !important;
    color: var(--text) !important;
    letter-spacing: 0.5px !important;
}
h2 { font-size: 32px !important; }
h3 { font-size: 24px !important; }

/* ── DATE INPUT ── */
[data-testid="stDateInput"] input {
    border-radius: 12px !important;
    border: 1.5px solid var(--border) !important;
}

/* ── SELECT BOX ── */
.stSelectbox > div [data-baseweb="select"] {
    border-radius: 12px !important;
}

/* ── CAPTION ── */
.stCaption {
    color: var(--text2) !important;
    font-size: 12px !important;
}
</style>
"""
