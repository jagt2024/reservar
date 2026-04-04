# ══════════════════════════════════════════════════════════════════════════════
#  SUITE SALITRE · Espacios de Descanso Personal — Terminal de Transportes
#  MÓDULO DE PAGOS · Kiosco Táctil 24/7
# ══════════════════════════════════════════════════════════════════════════════
#
#  Instalación:
#    pip install streamlit pandas qrcode pillow reportlab requests
#               pytz openpyxl gspread google-auth google-auth-oauthlib
#
#  ── EJECUCIÓN LOCAL ────────────────────────────────────────────────────────
#    1. Coloca credentials.json de tu Service Account en la carpeta del proyecto
#    2. Crea .streamlit/secrets.toml con:
#
#       [sheetsemp]
#       credentials_sheet = '''{ ... pega aquí el JSON de credentials.json ... }'''
#       spreadsheet_id = "ID_DEL_SPREADSHEET_jjgt_pagos"
#
#    3. Ejecutar:  streamlit run pagos.py
#
#  ── EJECUCIÓN EN LA WEB (Streamlit Cloud) ─────────────────────────────────
#    1. Sube el repositorio a GitHub (sin credentials.json ni secrets.toml)
#    2. En Streamlit Cloud → App Settings → Secrets, pega:
#
#       [sheetsemp]
#       credentials_sheet = '''{ ... JSON de Service Account ... }'''
#       spreadsheet_id = "ID_DEL_SPREADSHEET_jjgt_pagos"
#
#    3. La BD SQLite se recrea en cada deploy (usar Google Sheets como fuente)
#
#  ── NOTAS ─────────────────────────────────────────────────────────────────
#    · La app SIEMPRE inicia en la pantalla de login de operador
#    · Cada nuevo registro (cliente, reserva, pago, factura) se escribe en
#      jjgt_pagos de Google Sheets EN EL MISMO MOMENTO que en SQLite,
#      con reintentos automáticos ante errores 429 (MAX_RETRIES=4, backoff exp.)
#    · Backup automático al cierre de turno del operador en carpeta backups/
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import sqlite3
import json
import hashlib
import io
import base64
import os
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pytz

# ── Reintentos para escrituras en Google Sheets ───────────────────────────────
MAX_RETRIES         = 4          # intentos ante error 429
INITIAL_RETRY_DELAY = 2         # segundos base del backoff exponencial

# Imports opcionales — no bloquean si no están instalados
try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import toml as toml_lib
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES GLOBALES
# ──────────────────────────────────────────────────────────────────────────────
# En Streamlit Cloud, /tmp/ persiste durante la sesión pero no entre deploys.
# Para producción real usar una BD externa (Supabase, Railway, etc.)
_IS_CLOUD = os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("HOME", "").startswith("/home/appuser")
DB_PATH = "/tmp/terminal_descanso.db" if _IS_CLOUD else "terminal_descanso.db"
NEGOCIO      = "SUITE SALITRE · Espacios de Descanso"
TAGLINE      = "Tu espacio de descanso en la terminal"
DIRECCION    = "Terminal de Transportes · Local 42"
TELEFONO     = "320 551 1091"
NIT          = "900.123.456-7"
TZ_COL       = pytz.timezone("America/Bogota")
NEQUI_NUM    = "320 551 1091"
DAVIPLATA_NUM= "320 551 1091"
CUENTA_BANCO = "Bancolombia · Cta Ahorros · 123-456789-12"
MP_LINK      = "https://mpago.la/XXXXXXX"
WHATSAPP_OP  = "573205511091"
DRIVE_FILE   = "jjgt_pagos"
EMAIL        = "josegarjagt@gmail.com"

ESTADOS_CUBICULO = {
    "libre":        {"label": "LIBRE",        "color": "#00ff88", "bg": "rgba(0,255,136,0.12)"},
    "ocupado":      {"label": "OCUPADO",      "color": "#ff4757", "bg": "rgba(255,71,87,0.12)"},
    "por_liberar":  {"label": "POR LIBERAR",  "color": "#ffd32a", "bg": "rgba(255,211,42,0.12)"},
    "mantenimiento":{"label": "MANTENIM.",    "color": "#a29bfe", "bg": "rgba(162,155,254,0.12)"},
    "reservado":    {"label": "RESERVADO",    "color": "#74b9ff", "bg": "rgba(116,185,255,0.12)"},
}

METODOS_PAGO = ["Nequi", "Daviplata", "Efectivo", "PSE", "MercadoPago", "Transferencia", "Tarjeta"]
IVA_PCT      = 0.0

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{NEGOCIO} · Pagos",
    page_icon="💤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# CSS — MODO KIOSCO TÁCTIL
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inconsolata:wght@400;600;700&display=swap');

/* ── Variables ────────────────────────────────────────────── */
:root {
  --bg-deep:    #050b1a;
  --bg-card:    #0d1f3c;
  --bg-card2:   #0a1628;
  --cyan:       #00d4ff;
  --green:      #00ff88;
  --red:        #ff4757;
  --yellow:     #ffd32a;
  --purple:     #a29bfe;
  --text:       #e2e8f0;
  --text-dim:   #94a3b8;
  --border:     rgba(0,212,255,0.2);
  --radius:     16px;
}

/* ── Base ─────────────────────────────────────────────────── */
html, body, .stApp {
  background: linear-gradient(135deg, var(--bg-deep) 0%, #091428 50%, var(--bg-deep) 100%) !important;
  color: var(--text) !important;
  font-family: 'Syne', sans-serif !important;
}

/* Estrellas animadas */
.stApp::before {
  content: '';
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background-image:
    radial-gradient(1px 1px at 10% 20%, rgba(0,212,255,0.6) 0%, transparent 100%),
    radial-gradient(1px 1px at 30% 60%, rgba(0,255,136,0.4) 0%, transparent 100%),
    radial-gradient(1px 1px at 60% 10%, rgba(0,212,255,0.5) 0%, transparent 100%),
    radial-gradient(1px 1px at 80% 40%, rgba(255,255,255,0.3) 0%, transparent 100%),
    radial-gradient(1px 1px at 45% 80%, rgba(0,212,255,0.4) 0%, transparent 100%),
    radial-gradient(2px 2px at 20% 90%, rgba(0,255,136,0.3) 0%, transparent 100%),
    radial-gradient(1px 1px at 70% 70%, rgba(162,155,254,0.4) 0%, transparent 100%),
    radial-gradient(1px 1px at 90% 85%, rgba(0,212,255,0.3) 0%, transparent 100%);
  animation: twinkle 8s ease-in-out infinite alternate;
  pointer-events: none; z-index: 0;
}
@keyframes twinkle {
  0%   { opacity: 0.4; }
  50%  { opacity: 1;   }
  100% { opacity: 0.6; }
}

/* ── Ocultar UI de Streamlit ──────────────────────────────── */
#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ── Sidebar operador ─────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: rgba(5,11,26,0.97) !important;
  border-right: 1px solid var(--border);
}

/* ── Sidebar — textos visibles sobre fondo oscuro ─────────── */
/* Fuerza todos los textos del sidebar a color claro */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
  color: #e2e8f0 !important;
}
/* Radio — opciones del menú */
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stRadio p,
section[data-testid="stSidebar"] .stRadio span,
section[data-testid="stSidebar"] [role="radiogroup"] label,
section[data-testid="stSidebar"] [role="radiogroup"] p {
  color: #e2e8f0 !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  letter-spacing: 0.3px !important;
}
/* Radio — opción seleccionada resaltada en cyan */
section[data-testid="stSidebar"] .stRadio [aria-checked="true"] ~ div p,
section[data-testid="stSidebar"] .stRadio [aria-checked="true"] ~ div span,
section[data-testid="stSidebar"] [role="radiogroup"] [data-testid*="radioOption"]:has(input:checked) p,
section[data-testid="stSidebar"] [role="radiogroup"] [data-testid*="radioOption"]:has(input:checked) span {
  color: var(--cyan) !important;
}
/* Radio — bullet activo */
section[data-testid="stSidebar"] .stRadio [aria-checked="true"],
section[data-testid="stSidebar"] [role="radiogroup"] input[type="radio"]:checked {
  accent-color: var(--cyan) !important;
  border-color: var(--cyan) !important;
}
/* Caption / texto gris secundario */
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] span,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] small {
  color: #94a3b8 !important;
  font-size: 12px !important;
}
/* Botones en el sidebar */
section[data-testid="stSidebar"] div.stButton > button {
  color: #e2e8f0 !important;
  border-color: rgba(226,232,240,0.25) !important;
  min-height: 52px !important;
  font-size: 15px !important;
}
section[data-testid="stSidebar"] div.stButton > button:hover {
  color: var(--cyan) !important;
  border-color: var(--cyan) !important;
  box-shadow: 0 0 16px rgba(0,212,255,0.25) !important;
}
/* Divider sidebar */
section[data-testid="stSidebar"] hr {
  border-color: rgba(226,232,240,0.12) !important;
}
/* Radio container — fondo suave al hover */
section[data-testid="stSidebar"] .stRadio > div > label:hover {
  background: rgba(0,212,255,0.06) !important;
  border-radius: 8px !important;
}

/* ── Todos los contenedores ───────────────────────────────── */
.block-container { padding: 1rem 2rem !important; }

/* ── Botones táctiles grandes ─────────────────────────────── */
div.stButton > button {
  min-height: 72px !important;
  border-radius: var(--radius) !important;
  font-family: 'Syne', sans-serif !important;
  font-weight: 700 !important;
  font-size: 18px !important;
  border: 1.5px solid var(--border) !important;
  background: linear-gradient(135deg, var(--bg-card), var(--bg-card2)) !important;
  color: var(--text) !important;
  transition: all 0.25s ease !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}
div.stButton > button:hover {
  border-color: var(--cyan) !important;
  box-shadow: 0 0 24px rgba(0,212,255,0.35) !important;
  transform: translateY(-2px) !important;
  color: var(--cyan) !important;
}
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0a3d62, #1a5276) !important;
  border-color: var(--cyan) !important;
  color: var(--cyan) !important;
  box-shadow: 0 0 20px rgba(0,212,255,0.2) !important;
  font-size: 20px !important;
  min-height: 88px !important;
}
div.stButton > button[kind="primary"]:hover {
  box-shadow: 0 0 40px rgba(0,212,255,0.55) !important;
  transform: translateY(-3px) !important;
}

/* ── Inputs ───────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stSelectbox select,
.stTextArea textarea {
  background: rgba(13,31,60,0.8) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: 12px !important;
  color: var(--text) !important;
  font-family: 'Syne', sans-serif !important;
  font-size: 18px !important; 
  padding: 14px 18px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: var(--cyan) !important;
  box-shadow: 0 0 16px rgba(0,212,255,0.25) !important;
}
label, .stTextInput label, .stNumberInput label, .stSelectbox label {
  font-family: 'Syne', sans-serif !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  color: var(--text-white) !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ── Tarjetas generales ───────────────────────────────────── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 16px;
}

/* ── Tarjeta cubículo ─────────────────────────────────────── */
.cubiculo-card {
  border-radius: var(--radius);
  padding: 20px 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
}
.cubiculo-libre {
  background: rgba(0,255,136,0.08);
  border-color: rgba(0,255,136,0.4);
}
.cubiculo-libre:hover {
  background: rgba(0,255,136,0.18);
  border-color: #00ff88;
  box-shadow: 0 0 30px rgba(0,255,136,0.4);
  transform: scale(1.03);
}
.cubiculo-ocupado {
  background: rgba(255,71,87,0.08);
  border-color: rgba(255,71,87,0.3);
  opacity: 0.7;
  cursor: not-allowed;
}
.cubiculo-mantenimiento {
  background: rgba(162,155,254,0.08);
  border-color: rgba(162,155,254,0.3);
  opacity: 0.6;
  cursor: not-allowed;
}
.cubiculo-selected {
  border-color: var(--cyan) !important;
  box-shadow: 0 0 40px rgba(0,212,255,0.5) !important;
  background: rgba(0,212,255,0.12) !important;
  animation: pulse-selected 1.5s ease-in-out infinite;
}
@keyframes pulse-selected {
  0%, 100% { box-shadow: 0 0 30px rgba(0,212,255,0.4); }
  50%       { box-shadow: 0 0 60px rgba(0,212,255,0.7); }
}
.cubiculo-num {
  font-family: 'Inconsolata', monospace;
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}
.estado-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 4px 12px;
  border-radius: 20px;
  text-transform: uppercase;
}
.timer-display {
  font-family: 'Inconsolata', monospace;
  font-size: 18px;
  font-weight: 600;
}
.servicios-icons {
  font-size: 16px;
  opacity: 0.8;
  margin-top: 4px;
}

/* ── Temporizador grande ──────────────────────────────────── */
.clock-big {
  font-family: 'Inconsolata', monospace;
  font-size: 72px;
  font-weight: 700;
  color: var(--green);
  text-shadow: 0 0 30px rgba(0,255,136,0.6);
  text-align: center;
  line-height: 1;
}
.clock-label {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-dim);
  text-align: center;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-top: 4px;
}

/* ── QR container ─────────────────────────────────────────── */
.qr-container {
  display: flex; flex-direction: column; align-items: center;
  padding: 24px;
  background: var(--bg-card);
  border-radius: var(--radius);
  border: 2px solid var(--cyan);
  animation: qr-pulse 2s ease-in-out infinite;
  margin: 16px auto;
  max-width: 400px;
}
@keyframes qr-pulse {
  0%, 100% { box-shadow: 0 0 20px rgba(0,212,255,0.3); }
  50%       { box-shadow: 0 0 50px rgba(0,212,255,0.6); }
}
.qr-container img {
  border-radius: 12px;
  margin-bottom: 12px;
}
.qr-instruccion {
  font-size: 15px;
  color: var(--text-dim);
  text-align: center;
  margin-top: 8px;
}

/* ── Método de pago cards ─────────────────────────────────── */
.pago-card {
  border-radius: var(--radius);
  padding: 20px 24px;
  min-height: 120px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 20px;
  font-weight: 700;
}
.pago-nequi {
  background: linear-gradient(135deg, rgba(0,100,40,0.3), rgba(0,180,80,0.15));
  border-color: rgba(0,255,100,0.3);
}
.pago-nequi:hover { border-color: #00c853; box-shadow: 0 0 24px rgba(0,200,83,0.4); }
.pago-daviplata {
  background: linear-gradient(135deg, rgba(10,40,100,0.4), rgba(20,70,180,0.2));
  border-color: rgba(50,130,246,0.3);
}
.pago-daviplata:hover { border-color: #3b82f6; box-shadow: 0 0 24px rgba(59,130,246,0.4); }
.pago-efectivo {
  background: linear-gradient(135deg, rgba(20,60,20,0.4), rgba(40,120,40,0.2));
  border-color: rgba(100,200,80,0.3);
}
.pago-efectivo:hover { border-color: #84cc16; box-shadow: 0 0 24px rgba(132,204,22,0.4); }

/* ── Métricas KPI ─────────────────────────────────────────── */
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: 3px solid var(--cyan);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
}
.kpi-value {
  font-family: 'Inconsolata', monospace;
  font-size: 36px;
  font-weight: 700;
  color: var(--cyan);
  line-height: 1;
}
.kpi-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-top: 6px;
}

/* ── Voucher ──────────────────────────────────────────────── */
.voucher-box {
  background: linear-gradient(135deg, var(--bg-card), rgba(0,212,255,0.05));
  border: 1.5px solid var(--cyan);
  border-radius: var(--radius);
  padding: 32px;
  max-width: 580px;
  margin: 0 auto;
}
.voucher-codigo {
  font-family: 'Inconsolata', monospace;
  font-size: 80px;
  font-weight: 700;
  color: var(--green);
  text-shadow: 0 0 40px rgba(0,255,136,0.6);
  text-align: center;
  letter-spacing: 16px;
  line-height: 1;
}
.voucher-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-dim);
  text-align: center;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-top: 8px;
}

/* ── Confirmación ─────────────────────────────────────────── */
.confirm-ok {
  background: linear-gradient(135deg, rgba(0,100,50,0.4), rgba(0,200,100,0.15));
  border: 2px solid var(--green);
  border-radius: var(--radius);
  padding: 40px;
  text-align: center;
  animation: confetti-bg 0.5s ease;
}
.confirm-fail {
  background: linear-gradient(135deg, rgba(100,20,20,0.4), rgba(200,50,50,0.15));
  border: 2px solid var(--red);
  border-radius: var(--radius);
  padding: 40px;
  text-align: center;
}

/* ── Header principal ─────────────────────────────────────── */
.main-header {
  text-align: center;
  padding: 24px 0 8px;
}
.main-logo {
  font-family: 'Syne', sans-serif;
  font-size: 48px;
  font-weight: 800;
  background: linear-gradient(90deg, var(--cyan), var(--green));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -1px;
  line-height: 1;
}
.main-tagline {
  font-size: 16px;
  color: var(--text-dim);
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-top: 6px;
}

/* ── Stepper ──────────────────────────────────────────────── */
.stepper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 16px 0 24px;
  flex-wrap: wrap;
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 24px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-dim);
  border: 1.5px solid rgba(148,163,184,0.2);
  background: transparent;
  white-space: nowrap;
}
.step.active {
  color: var(--cyan);
  border-color: var(--cyan);
  background: rgba(0,212,255,0.1);
  box-shadow: 0 0 16px rgba(0,212,255,0.25);
}
.step.done {
  color: var(--green);
  border-color: rgba(0,255,136,0.4);
  background: rgba(0,255,136,0.08);
}
.step-arrow {
  width: 32px;
  height: 2px;
  background: rgba(148,163,184,0.2);
  flex-shrink: 0;
}

/* ── Alerta pulsante ──────────────────────────────────────── */
.alerta-roja {
  animation: pulse-red 1s ease-in-out infinite;
  background: rgba(255,71,87,0.2);
  border: 2px solid var(--red);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  color: var(--red);
  font-weight: 700;
}
@keyframes pulse-red {
  0%, 100% { opacity: 1;   box-shadow: 0 0 10px rgba(255,71,87,0.4); }
  50%       { opacity: 0.7; box-shadow: 0 0 30px rgba(255,71,87,0.8); }
}

/* ── Live timer elements ──────────────────────────────────── */
.jjgt-timer {
  font-family: 'Inconsolata', monospace !important;
  font-size: 13px;
  font-weight: 700;
  transition: color 0.5s ease;
}
.jjgt-clock-hms {
  font-variant-numeric: tabular-nums;
  letter-spacing: 2px;
}
.jjgt-qr-countdown {
  font-family: 'Inconsolata', monospace;
  font-size: 12px;
  font-weight: 700;
  margin-top: 4px;
  transition: color 0.5s ease;
}
.jjgt-consumed {
  font-family: 'Inconsolata', monospace;
  font-size: 12px;
}

/* ── Countdown bar ────────────────────────────────────────── */
.countdown-bar {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.1);
  overflow: hidden;
  margin-top: 8px;
}
.countdown-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--green), var(--cyan));
  transition: width 1s linear;
}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--bg-card) !important;
  border-radius: 12px !important;
  gap: 4px !important;
  padding: 4px !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-dim) !important;
  border-radius: 8px !important;
  font-family: 'Syne', sans-serif !important;
  font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
  background: rgba(0,212,255,0.15) !important;
  color: var(--cyan) !important;
}

/* ── Divider ──────────────────────────────────────────────── */
hr { border-color: var(--border) !important; }

/* ── Dataframe ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  overflow: hidden;
}

/* ── Toggle / checkbox ────────────────────────────────────── */
.stCheckbox label {
  font-size: 16px !important;
  font-weight: 600 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--text) !important;
}

/* ── Metric ───────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-top: 3px solid var(--cyan) !important;
  border-radius: var(--radius) !important;
  padding: 16px !important;
}
[data-testid="stMetricValue"] {
  font-family: 'Inconsolata', monospace !important;
  color: var(--cyan) !important;
}
[data-testid="stMetricDelta"] { font-family: 'Inconsolata', monospace !important; }

/* ── Print ────────────────────────────────────────────────── */
@media print {
  .stApp::before, section[data-testid="stSidebar"], .stButton,
  [data-testid="stToolbar"] { display: none !important; }
  .voucher-box { border: 2px solid black !important; color: black !important; }
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# RELOJ Y TIMERS EN VIVO — JavaScript puro (sin recargar el servidor)
# ══════════════════════════════════════════════════════════════════════════════

def inject_live_clock():
    """
    Inyecta el motor de reloj/timers en vivo usando st.components.v1.html().
    Esto crea un <iframe> persistente que NO es destruido por los reruns de Streamlit.
    El script se comunica con el DOM padre via window.parent para actualizar
    los elementos .jjgt-clock-hms, .jjgt-timer[data-fin], etc.
    """
    import streamlit.components.v1 as components
    components.html("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;overflow:hidden;background:transparent;">
<script>
(function() {
  var DAYS_ES   = ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
  var MONTHS_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                   'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

  function pad2(n){ return n < 10 ? '0'+n : ''+n; }

  // Colombia = UTC-5 fijo (sin horario de verano)
  function getColombiaTime() {
    var now = new Date();
    var utc = now.getTime() + now.getTimezoneOffset() * 60000;
    return new Date(utc - 5 * 3600000);
  }

  // Acceder al DOM del padre (la página principal de Streamlit)
  function getParentDoc() {
    try { return window.parent.document; } catch(e) { return document; }
  }

  var alarmaDisparada = {};

  function updateClock() {
    var doc = getParentDoc();
    var t  = getColombiaTime();
    var hh = pad2(t.getHours());
    var mm = pad2(t.getMinutes());
    var ss = pad2(t.getSeconds());
    var hms = hh + ':' + mm + ':' + ss;
    var fecha = DAYS_ES[t.getDay()] + ', ' + pad2(t.getDate()) + ' DE ' +
                MONTHS_ES[t.getMonth()].toUpperCase() + ' DE ' + t.getFullYear();

    doc.querySelectorAll('.jjgt-clock-hms').forEach(function(el) {
      el.textContent = hms;
    });
    doc.querySelectorAll('.jjgt-clock-fecha').forEach(function(el) {
      el.textContent = fecha;
    });
    doc.querySelectorAll('.jjgt-clock-compact').forEach(function(el) {
      el.textContent = hh + ':' + mm;
    });
  }

  function updateTimers() {
    var doc = getParentDoc();
    var nowMs = getColombiaTime().getTime();
    doc.querySelectorAll('.jjgt-timer[data-fin]').forEach(function(el) {
      var fin = el.getAttribute('data-fin');
      if (!fin) return;
      var finMs  = new Date(fin).getTime();
      var diffMs = finMs - nowMs;
      var key    = el.getAttribute('data-key') || fin;

      if (diffMs <= 0) {
        el.textContent = '⏰ TIEMPO VENCIDO';
        el.style.color = '#ff4757';
        el.style.fontWeight = '700';
        el.style.animation = 'none';
        if (!alarmaDisparada[key]) {
          alarmaDisparada[key] = true;
          playAlarm();
          showBanner(doc);
        }
      } else {
        var totalSec = Math.floor(diffMs / 1000);
        var h = Math.floor(totalSec / 3600);
        var m = Math.floor((totalSec % 3600) / 60);
        var s = totalSec % 60;
        var label = (h > 0 ? pad2(h) + ':' : '') + pad2(m) + ':' + pad2(s);
        el.textContent = '⏱ ' + label;
        var diffMin = Math.floor(diffMs / 60000);
        if (diffMin <= 5) {
          el.style.color = '#ff4757';
          el.style.animation = 'pulse-red 1s ease-in-out infinite';
        } else if (diffMin <= 15) {
          el.style.color = '#ffd32a';
          el.style.animation = '';
        } else {
          el.style.color = '#00ff88';
          el.style.animation = '';
        }
      }
    });
  }

  function updateConsumed() {
    var doc = getParentDoc();
    var nowMs = getColombiaTime().getTime();
    doc.querySelectorAll('.jjgt-consumed[data-inicio]').forEach(function(el) {
      var inicio = el.getAttribute('data-inicio');
      if (!inicio) return;
      var diffMs  = nowMs - new Date(inicio).getTime();
      var totalSec = Math.max(0, Math.floor(diffMs / 1000));
      var h = Math.floor(totalSec / 3600);
      var m = Math.floor((totalSec % 3600) / 60);
      var s = totalSec % 60;
      el.textContent = (h > 0 ? h + 'h ' : '') + pad2(m) + ':' + pad2(s) + ' consumidos';
    });
  }

  function updateQrCountdown() {
    var doc = getParentDoc();
    var nowMs = getColombiaTime().getTime();
    doc.querySelectorAll('.jjgt-qr-countdown[data-exp]').forEach(function(el) {
      var exp = el.getAttribute('data-exp');
      if (!exp) return;
      var diffS = Math.floor((new Date(exp).getTime() - nowMs) / 1000);
      if (diffS <= 0) {
        el.textContent = '🔄 QR vencido — recargando...';
        el.style.color = '#ff4757';
      } else {
        el.textContent = '🔒 QR válido por ' + diffS + 's';
        el.style.color = diffS < 30 ? '#ffd32a' : '#00ff88';
      }
    });
  }

  function playAlarm() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      function beep(f, s, d) {
        var o = ctx.createOscillator(), g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination);
        o.frequency.value = f; o.type = 'square';
        g.gain.setValueAtTime(0.35, ctx.currentTime + s);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + s + d);
        o.start(ctx.currentTime + s);
        o.stop(ctx.currentTime + s + d + 0.05);
      }
      for (var i = 0; i < 6; i++) { beep(880, i*0.4, 0.3); beep(660, i*0.4+0.18, 0.15); }
    } catch(e) {}
  }

  function showBanner(doc) {
    try {
      var banner = doc.getElementById('jjgt-alarm-banner');
      if (!banner) {
        banner = doc.createElement('div');
        banner.id = 'jjgt-alarm-banner';
        banner.style.cssText =
          'position:fixed;top:0;left:0;right:0;z-index:99999;' +
          'background:rgba(255,71,87,0.97);color:#fff;font-weight:700;font-size:18px;' +
          'text-align:center;padding:14px;letter-spacing:1px;';
        doc.body.appendChild(banner);
      }
      banner.style.display = 'block';
      banner.textContent = '🔔 ¡TIEMPO VENCIDO! Cubículo listo para liberar — Notificar al operador';
      setTimeout(function() { banner.style.display = 'none'; }, 20000);
    } catch(e) {}
  }

  function tick() {
    updateClock();
    updateTimers();
    updateConsumed();
    updateQrCountdown();
  }

  // Arrancar inmediatamente y cada segundo
  tick();
  setInterval(tick, 1000);
})();
</script>
</body>
</html>
""", height=0, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS — CREDENCIALES, CONEXIÓN Y ESCRITURA
# Patrón basado en el ejemplo de referencia proporcionado.
# Orden: PRIMERO insertar en Google Sheets, LUEGO en SQLite.
# ══════════════════════════════════════════════════════════════════════════════

SPREADSHEET_ID = "1JmKNZ4ld2u43EU_ymn8NhFtXti2mDcPLkM42ciMTLC4"

DRIVE_SHEETS = {
    # ── reservas: columnas BD + desnormalización cubiculo/cliente/wifi ────────
    # BD: id, numero_reserva, cubiculo_id, cliente_id, factura_id,
    #     hora_inicio, hora_fin_programada, hora_fin_real,
    #     horas_contratadas, precio_hora, subtotal, iva, total,
    #     metodo_pago, estado_pago, codigo_acceso, referencia_pago, notas, creado_en
    "Reservas": [
        "ID_Reserva","Numero_Reserva","cubiculo_id","cliente_id","factura_id",
        "hora_inicio","hora_fin_programada","hora_fin_real","horas_contratadas",
        "Precio_Hora","Subtotal","IVA","Total_COP",
        "Metodo_Pago","Estado_Pago","Codigo_Acceso",
        "Referencia_Pago","Notas","creado_en",
    ],
    # ── pagos: columnas BD + num_reserva de JOIN ──────────────────────────────
    # BD: id, reserva_id, monto, metodo, referencia_externa,
    #     estado, fecha_pago, confirmado_por, notas
    "Pagos": [
        "ID_Pago","ID_Reserva","Monto_COP","Metodo","Referencia_Externa","Estado",
        "Fecha_Pago","Confirmado_Por","Notas",
    ],
    # ── clientes: todas las columnas BD ──────────────────────────────────────
    # BD: id, nombre, tipo_documento, numero_documento, telefono, email, ciudad,
    #     regimen, tipo_persona, razon_social, nit_empresa, activo, creado_en
    "Clientes": [
        "ID_Cliente","Nombre","Tipo_Doc","Num_Doc","Telefono",
        "Email","Ciudad","Regimen","Tipo_Persona",
        "Razon_Social","NIT_Empresa","Activo","Creado_En",
    ],
    # ── cubiculos_estado: columnas BD + datos de reserva activa ──────────────
    # BD: id, numero, nombre, estado, reserva_activa_id, hora_disponible,
    #     precio_hora_base, wifi_ssid, wifi_password, servicios
    # JOIN reservas: hora_inicio, hora_fin_programada, codigo_acceso, cliente
    "Cubiculos_Estado": [
        "Cubiculo_ID","Numero","Nombre","Estado",
        "Cliente_Actual","Hora_Inicio","Hora_Fin_Prog","Tiempo_Rest_Min",
        "Codigo_Acceso","WiFi_SSID","WiFi_Pass",
        "Precio_Hora_Base","Total_Reservas","Ingresos_Total","Notas",
    ],
    # ── facturas: columnas BD + desnormalización cliente/item/reserva ─────────
    # BD: id, numero, tipo, fecha_emision, fecha_vencimiento, cliente_id,
    #     subtotal, descuento, iva, retenciones, total,
    #     estado, moneda, notas, metodo_pago, creado_en, actualizado_en
    "Facturas": [
        "ID_Factura","Num_Factura","Tipo","Fecha_Emision","Fecha_Vencimieento",
        "Cliente__id","Subtotal","Descuento","IVA","Retenciones","Total_COP",
        "Estado","Moneda","notas","Metodo_Pago","Creado_En","Actualizado_En",
    ],
    # ── factura_items: columnas BD ────────────────────────────────────────────
    # BD: id, factura_id, codigo, descripcion, cantidad, unidad,
    #     precio_unitario, descuento_pct, iva_pct, subtotal
    "Factura_items": [
        "id","ID_Factura","codigo","descripcion","cantidad","unidad",
        "precio_unitario","Descuento_pct","Iva_pct","subtotal_COP",
    ],
    # ── operadores: columnas BD ───────────────────────────────────────────────
    # BD: id, nombre, pin_hash, rol, turno,
    #     hora_inicio_turno, hora_fin_turno, permisos, activo
    "Operadores": [
        "ID_Operador","Nombre","Rol","Turno",
        "Hora_Ini_Turno","Hora_Fin_Turno","Permisos","Activo",
    ],
    # ── configuracion_pagos: columnas BD ─────────────────────────────────────
    # BD: clave TEXT PRIMARY KEY, valor TEXT
    "Configuracion_Pagos": [
        "Clave","Valor",
    ],
   
    # ── tarifas: columnas BD en el mismo orden ────────────────────────────────
    # BD: id, nombre, descripcion, precio_hora, descuento_3h_pct, descuento_6h_pct,
    #     hora_inicio_especial, hora_fin_especial, aplica_festivos, activo
    "Tarifas_Config": [
        "ID","Nombre","Descripcion","Precio_Hora_COP",
        "Desc_3h_Pct","Desc_6h_Pct",
        "Hora_Ini_Espec","Hora_Fin_Espec","Aplica_Festivos","Activo",
    ],
    # ── dashboard diario: calculado, sin tabla BD directa ────────────────────
    "Dashboard_Diario": [
        "Fecha","Total_Reservas","Completadas","Canceladas",
        "Ingresos_Brutos","IVA_Recaudado","Ingresos_Netos",
        "Nequi_COP","Daviplata_COP","Efectivo_COP","PSE_COP",
        "MP_COP","Otros_COP","Ocupacion_Pct","Hora_Pico",
        "Tiempo_Prom_Min","Clientes_Nuevos","Clientes_Recur",
        "Fact_Min","Fact_Max","Ticket_Prom_COP",
    ],
    # ── log operaciones: sin tabla BD directa ────────────────────────────────
    "Log_Operaciones": [
        "Timestamp","Tipo_Op","Reserva_ID","Cubiculo",
        "Operador","Descripcion","Valor_Ant","Valor_Nuevo",
        "IP","Estado","Notas",
    ],
}


def load_credentials_from_toml():
    """
    Carga credenciales de Google Service Account desde .streamlit/secrets.toml.
    Patrón idéntico al ejemplo de referencia.
    Retorna (dict_creds, config) o (None, None) si falla.
    """
    try:
        with open('./.streamlit/secrets.toml', 'r', encoding='utf-8') as toml_file:
            config = toml_lib.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            # Reparar saltos de línea en private_key si vienen como \n literal
            pk = creds.get("private_key", "")
            if pk and "\\n" in pk and "\n" not in pk:
                creds["private_key"] = pk.replace("\\n", "\n")
            return creds, config
    except FileNotFoundError:
        st.error("📁 Archivo secrets.toml no encontrado en .streamlit/")
        st.info("Crea el archivo `.streamlit/secrets.toml` con tus credenciales de Google")
        return None, None
    except KeyError as e:
        st.error(f"🔑 Clave faltante en secrets.toml: {str(e)}")
        st.info("Verifica que exista la sección [sheetsemp] con la clave credentials_sheet")
        return None, None
    except json.JSONDecodeError as e:
        st.error(f"📄 Error al parsear JSON en secrets.toml: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"❌ Error cargando credenciales: {str(e)}")
        return None, None


@st.cache_resource(ttl=300)
def get_google_sheets_connection(_creds):
    """
    Establece conexión con Google Sheets y la cachea 5 minutos.
    Patrón idéntico al ejemplo de referencia.
    """
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets',
        ]
        credentials = Credentials.from_service_account_info(_creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None


def get_or_create_spreadsheet(client):
    """
    Abre jjgt_pagos por SPREADSHEET_ID fijo.
    - Si el ID no existe en Drive: crea el archivo.
    - Verifica hoja por hoja antes de crearla (evita error 400 'already exists').
    - Elimina hoja vacía por defecto (Sheet1, Hoja 1).
    """
    if not client:
        return None
    try:
        # Abrir por ID fijo; si no existe, crear archivo nuevo
        try:
            sh = client.open_by_key(SPREADSHEET_ID)
        except gspread.SpreadsheetNotFound:
            sh = client.create(DRIVE_FILE)
            st.warning(f"⚠️ Archivo no encontrado con ese ID. Se creó uno nuevo.")

        # Verificar/crear cada hoja individualmente para evitar error 400
        existing_titles = {ws.title for ws in sh.worksheets()}
        for name, headers in DRIVE_SHEETS.items():
            if name in existing_titles:
                continue
            try:
                ws = sh.add_worksheet(title=name,
                                      rows=5000,
                                      cols=max(len(headers), 26))
                ws.append_row(headers)
                time.sleep(0.5)
            except gspread.exceptions.APIError as api_err:
                if "already exists" in str(api_err).lower():
                    pass
                else:
                    raise

        # Eliminar hoja vacía por defecto si quedó
        for default_name in ["Sheet1", "Hoja 1", "Hoja1"]:
            try:
                sh.del_worksheet(sh.worksheet(default_name))
            except Exception:
                pass

        return sh
    except Exception as e:
        st.error(f"❌ Error abriendo spreadsheet: {str(e)}")
        return None


def get_active_client():
    """
    Flujo completo: credenciales → cliente cacheado → spreadsheet.
    Retorna (client, spreadsheet) o (None, None).
    """
    if not GSPREAD_AVAILABLE:
        return None, None
    creds, _ = load_credentials_from_toml()
    if not creds:
        return None, None
    client = get_google_sheets_connection(creds)
    if not client:
        return None, None
    sh = get_or_create_spreadsheet(client)
    return client, sh


def _reset_gs_cache():
    """Limpia la caché de conexión para forzar reconexión."""
    try:
        get_google_sheets_connection.clear()
    except Exception:
        pass


# ── Funciones internas de escritura ──────────────────────────────────────────

def _gs_get_or_create_ws(sh, hoja: str):
    """
    Devuelve el worksheet para `hoja`, creándola si no existe.
    La búsqueda es insensible a mayúsculas/minúsculas para evitar el error
    cuando las hojas fueron creadas con nombre en minúscula.
    Compatible con gspread v4, v5 y v6.
    """
    # Buscar la hoja ignorando mayúsculas/minúsculas
    meta  = sh.fetch_sheet_metadata()
    hoja_lower = hoja.lower()
    for sheet in meta.get('sheets', []):
        titulo = sheet['properties']['title']
        if titulo.lower() == hoja_lower:
            # Encontrada — retornar el worksheet usando el título real
            return sh.worksheet(titulo)

    # La hoja no existe → crearla
    headers = DRIVE_SHEETS.get(hoja, [])
    try:
        new_ws = sh.add_worksheet(
            title=hoja, rows=5000, cols=max(len(headers), 26)
        )
        if headers:
            new_ws.append_row(headers)
        return new_ws
    except gspread.exceptions.APIError as e:
        if "already exists" in str(e).lower():
            # Condición de carrera — buscar de nuevo
            meta2 = sh.fetch_sheet_metadata()
            for sheet in meta2.get('sheets', []):
                if sheet['properties']['title'].lower() == hoja_lower:
                    return sh.worksheet(sheet['properties']['title'])
        raise


def _gs_update_row(ws, row_num: int, padded: list):
    """
    Actualiza una fila completa.
    Usa kwargs nombrados para compatibilidad con gspread v4 y v6:
      v4: update(range_name, values)  →  range_name= funciona
      v6: update(values, range_name)  →  values= funciona
    """
    ws.update(values=[padded], range_name=f"A{row_num}")


def _gs_update_range(ws, range_name: str, data: list):
    """
    Escribe un bloque de datos en el rango indicado.
    Usa kwargs nombrados para compatibilidad con gspread v4 y v6.
    """
    ws.update(values=data, range_name=range_name)


def _gs_append(sh, hoja: str, fila: list) -> bool:
    """Agrega una fila. Si la hoja está vacía, escribe primero los encabezados."""
    try:
        ws = _gs_get_or_create_ws(sh, hoja)
        vals = ws.get_all_values()
        if not vals:
            ws.append_row(DRIVE_SHEETS.get(hoja, []))
        ws.append_row([str(v) if v is not None else "" for v in fila])
        return True
    except Exception as e:
        import traceback
        st.warning(f"⚠️ Error escribiendo en '{hoja}': {type(e).__name__}: {e}\n```\n{traceback.format_exc()}\n```")
        return False


def _gs_upsert(sh, hoja: str, col_clave: str, valor_clave: str, fila: list) -> bool:
    """
    Busca col_clave == valor_clave y actualiza esa fila.
    Si no existe la agrega al final (append_row).
    Compatible con gspread v4, v5 y v6.
    """
    import traceback
    try:
        ws = _gs_get_or_create_ws(sh, hoja)
        vals = ws.get_all_values()
        fila_str = [str(v) if v is not None else "" for v in fila]

        if not vals:
            ws.append_row(DRIVE_SHEETS.get(hoja, []))
            ws.append_row(fila_str)
            return True

        hdr = vals[0]
        col_idx = hdr.index(col_clave) if col_clave in hdr else -1
        if col_idx >= 0:
            for i, r in enumerate(vals[1:], start=2):
                if len(r) > col_idx and str(r[col_idx]) == str(valor_clave):
                    padded = (fila_str + [""] * len(hdr))[:len(hdr)]
                    _gs_update_row(ws, i, padded)
                    return True

        ws.append_row(fila_str)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error upsert '{hoja}': {type(e).__name__}: {e}\n```\n{traceback.format_exc()}\n```")
        return False


# ── Escritura por entidad ─────────────────────────────────────────────────────

def gs_escribir_cliente(sh, datos: dict) -> bool:
    # Columnas: ID_Cliente, Nombre, Tipo_Doc, Num_Doc, Telefono,
    #           Email, Ciudad, Regimen, Tipo_Persona,
    #           Razon_Social, NIT_Empresa, Activo,
    #           Total_Reservas, Total_Gastado_COP, Creado_En
    num_doc = str(datos.get("numero_documento", ""))
    # Calcular totales desde SQLite si el cliente ya existe
    total_res = total_gas = ""
    try:
        con = get_db()
        row = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(r.total),0) FROM reservas r "
            "JOIN clientes c ON r.cliente_id=c.id WHERE c.numero_documento=?",
            (num_doc,)).fetchone()
        con.close()
        if row:
            total_res, total_gas = str(row[0]), str(round(float(row[1]), 2))
    except Exception:
        pass
    fila = [
        str(datos.get("id", "")),
        str(datos.get("nombre", "")),
        str(datos.get("tipo_documento", "CC")),
        num_doc,
        str(datos.get("telefono", "")),
        str(datos.get("email", "")),
        str(datos.get("ciudad", "")),
        str(datos.get("regimen", "Simplificado")),
        str(datos.get("tipo_persona", "Natural")),
        str(datos.get("razon_social", "")),
        str(datos.get("nit_empresa", "")),
        str(datos.get("activo", "1")),
        total_res,
        total_gas,
        str(datos.get("creado_en", "")),
    ]
    return _gs_upsert(sh, "Clientes", "Num_Doc", num_doc, fila)


def gs_escribir_factura(sh, datos: dict) -> bool:
    # Columnas: ID_Factura, Num_Factura, Tipo, Fecha_Emision, Fecha_Venc,
    #           Cliente, Documento, Email, Razon_Social, NIT_Emp,
    #           Descripcion, Subtotal, Descuento, Base_Gravable, IVA, Retenciones, Total_COP,
    #           Metodo_Pago, Estado, Moneda,
    #           Num_Reserva, Cubiculo, Creado_En, Actualizado_En
    subtotal = float(datos.get("subtotal", 0) or 0)
    descuento = float(datos.get("descuento", 0) or 0)
    base_gravable = subtotal - descuento
    fila = [
        str(datos.get("id", "")),
        str(datos.get("numero", "")),
        str(datos.get("tipo", "Factura de Venta")),
        str(datos.get("fecha_emision", "")),
        str(datos.get("fecha_vencimiento", "")),
        str(datos.get("cliente_nombre", "")),
        str(datos.get("cliente_doc", "")),
        str(datos.get("cliente_email", "")),
        str(datos.get("razon_social", "")),
        str(datos.get("nit_empresa", "")),
        str(datos.get("descripcion", "")),
        str(subtotal),
        str(descuento),
        str(round(base_gravable, 2)),
        str(datos.get("iva", "")),
        str(datos.get("retenciones", "0")),
        str(datos.get("total", "")),
        str(datos.get("metodo_pago", "")),
        str(datos.get("estado", "pagada")),
        str(datos.get("moneda", "COP")),
        str(datos.get("num_reserva", "")),
        str(datos.get("cubiculo", "")),
        str(datos.get("creado_en", "")),
        str(datos.get("actualizado_en", "")),
    ]
    return _gs_upsert(sh, "Facturas", "Num_Factura",
                      str(datos.get("numero", "")), fila)


def gs_escribir_reserva(sh, datos: dict) -> bool:
    # Columnas: ID_Reserva, Numero_Reserva, Creado_En, Cubiculo_Num,
    #           Cliente_Nombre, Documento, Telefono, Email,
    #           Horas_Contratadas, Hora_Inicio, Hora_Fin_Prog, Hora_Fin_Real,
    #           Precio_Hora, Subtotal, IVA, Total_COP,
    #           Metodo_Pago, Estado_Pago, Codigo_Acceso,
    #           WiFi_SSID, WiFi_Pass, Num_Factura, Referencia_Pago, Operador, Notas
    fila = [
        str(datos.get("id", "")),
        str(datos.get("numero_reserva", "")),
        str(datos.get("creado_en", "")),
        str(datos.get("cubiculo_num", "")),
        str(datos.get("cliente_nombre", "")),
        str(datos.get("cliente_doc", "")),
        str(datos.get("cliente_tel", "")),
        str(datos.get("cliente_email", "")),
        str(datos.get("horas", "")),
        str(datos.get("hora_inicio", "")),
        str(datos.get("hora_fin_prog", "")),
        str(datos.get("hora_fin_real", "")),
        str(datos.get("precio_hora", "")),
        str(datos.get("subtotal", "")),
        str(datos.get("iva", "")),
        str(datos.get("total", "")),
        str(datos.get("metodo_pago", "")),
        str(datos.get("estado_pago", "confirmado")),
        str(datos.get("codigo_acceso", "")),
        str(datos.get("wifi_ssid", "")),
        str(datos.get("wifi_pass", "")),
        str(datos.get("num_factura", "")),
        str(datos.get("referencia_pago", "")),
        str(datos.get("operador", "sistema")),
        str(datos.get("notas", "")),
    ]
    return _gs_upsert(sh, "Reservas", "Numero_Reserva",
                      str(datos.get("numero_reserva", "")), fila)


def gs_escribir_pago(sh, datos: dict) -> bool:
    # Columnas: ID_Pago, ID_Reserva, Num_Reserva, Fecha_Pago,
    #           Monto_COP, Metodo, Referencia_Externa, Estado,
    #           Confirmado_Por, Notas
    fila = [
        str(datos.get("id", "")),
        str(datos.get("reserva_id", "")),
        str(datos.get("num_reserva", "")),
        str(datos.get("fecha_pago", "")),
        str(datos.get("monto", "")),
        str(datos.get("metodo", "")),
        str(datos.get("referencia_externa", "")),
        str(datos.get("estado", "confirmado")),
        str(datos.get("confirmado_por", "sistema")),
        str(datos.get("notas", "")),
    ]
    return _gs_upsert(sh, "Pagos", "Num_Reserva",
                      str(datos.get("num_reserva", "")), fila)


def gs_escribir_log(sh, tipo_op, reserva_id, cubiculo, operador, descripcion, estado="exito"):
    if sh:
        _gs_append(sh, "Log_Operaciones", [
            ahora_col().isoformat(), tipo_op, str(reserva_id), str(cubiculo),
            operador, descripcion, "", "", "", estado, ""
        ])


def gs_sync_cubiculos(sh):
    """Vuelca estado de cubículos a Cubiculos_Estado (clear + update batch)."""
    if not sh:
        return False
    try:
        # JOIN con reservas activas para obtener cliente y código de acceso
        con = get_db()
        rows = con.execute("""
            SELECT c.id, c.numero, c.nombre, c.estado,
                   c.precio_hora_base, c.wifi_ssid, c.wifi_password, c.notas,
                   r.hora_inicio, r.hora_fin_programada, r.codigo_acceso,
                   cl.nombre AS cliente_nombre,
                   (SELECT COUNT(*) FROM reservas WHERE cubiculo_id=c.id) AS total_res,
                   (SELECT COALESCE(SUM(total),0) FROM reservas WHERE cubiculo_id=c.id) AS ingresos
            FROM cubiculos c
            LEFT JOIN reservas r ON c.reserva_activa_id = r.id
            LEFT JOIN clientes cl ON r.cliente_id = cl.id
            ORDER BY c.numero
        """).fetchall()
        con.close()

        now = ahora_col()
        ws = _gs_get_or_create_ws(sh, "Cubiculos_Estado")
        ws.clear()
        headers = DRIVE_SHEETS["Cubiculos_Estado"]
        # Columnas: Cubiculo_ID, Numero, Nombre, Estado,
        #           Cliente_Actual, Hora_Inicio, Hora_Fin_Prog, Tiempo_Rest_Min,
        #           Codigo_Acceso, WiFi_SSID, WiFi_Pass,
        #           Precio_Hora_Base, Total_Reservas, Ingresos_Total, Notas
        data_rows = []
        for r in rows:
            (cub_id, numero, nombre, estado,
             precio_base, wifi_ssid, wifi_pass, notas,
             hora_ini, hora_fin, codigo_acceso,
             cliente_nombre, total_res, ingresos) = r

            min_rest = ""
            if hora_fin and estado in ("ocupado", "por_liberar"):
                try:
                    fin = datetime.fromisoformat(hora_fin)
                    if fin.tzinfo is None:
                        fin = TZ_COL.localize(fin)
                    diff = (fin - now).total_seconds() / 60
                    min_rest = str(max(0, int(diff)))
                except Exception:
                    pass

            data_rows.append([
                str(cub_id),
                str(numero),
                str(nombre or ""),
                str(estado),
                str(cliente_nombre or ""),
                str(hora_ini or ""),
                str(hora_fin or ""),
                min_rest,
                str(codigo_acceso or ""),
                str(wifi_ssid or ""),
                str(wifi_pass or ""),
                str(precio_base or ""),
                str(total_res or 0),
                str(round(float(ingresos or 0), 2)),
                str(notas or ""),
            ])

        _gs_update_range(ws, "A1", [headers] + data_rows)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error sync cubículos: {e}")
        return False


def gs_sync_dashboard(sh):
    """Actualiza la fila de hoy en Dashboard_Diario."""
    if not sh:
        return False
    try:
        today = ahora_col().strftime("%Y-%m-%d")
        con = get_db()
        s = con.execute("""
            SELECT COUNT(*), SUM(total), SUM(iva),
                   COUNT(CASE WHEN estado_pago='confirmado' THEN 1 END),
                   SUM(CASE WHEN metodo_pago='Nequi'       THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='Daviplata'   THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='Efectivo'    THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='PSE'         THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='MercadoPago' THEN total ELSE 0 END),
                   AVG(horas_contratadas)
            FROM reservas WHERE DATE(creado_en)=?
        """, (today,)).fetchone() or [0] * 10
        con.close()
        brutos = float(s[1] or 0)
        iva    = float(s[2] or 0)
        fila = [today, str(s[0]), str(s[3]), "0",
                str(brutos), str(iva), str(brutos - iva),
                str(float(s[4] or 0)), str(float(s[5] or 0)),
                str(float(s[6] or 0)), str(float(s[7] or 0)),
                str(float(s[8] or 0)), "0", "0", "",
                str(round(float(s[9] or 0) * 60)), "0", "0", "0", "0", "0"]
        return _gs_upsert(sh, "Dashboard_Diario", "Fecha", today, fila)
    except Exception as e:
        st.warning(f"⚠️ Error sync dashboard: {e}")
        return False


def gs_sync_factura_items(sh):
    """Vuelca todos los ítems de facturas a Factura_items (clear + update batch)."""
    if not sh:
        return False
    try:
        con = get_db()
        rows = con.execute("""
            SELECT fi.id, fi.factura_id, fi.codigo, fi.descripcion,
                   fi.cantidad, fi.unidad, fi.precio_unitario,
                   fi.descuento_pct, fi.iva_pct, fi.subtotal
            FROM factura_items fi
            ORDER BY fi.factura_id, fi.id
        """).fetchall()
        con.close()

        ws = _gs_get_or_create_ws(sh, "Factura_items")
        ws.clear()
        headers = DRIVE_SHEETS["Factura_items"]
        data_rows = []
        for r in rows:
            (item_id, factura_id, codigo, descripcion,
             cantidad, unidad, precio_unitario,
             descuento_pct, iva_pct, subtotal) = r
            data_rows.append([
                str(item_id),
                str(factura_id or ""),
                str(codigo or ""),
                str(descripcion or ""),
                str(cantidad or ""),
                str(unidad or ""),
                str(round(float(precio_unitario or 0), 2)),
                str(round(float(descuento_pct or 0), 2)),
                str(round(float(iva_pct or 0), 2)),
                str(round(float(subtotal or 0), 2)),
            ])

        _gs_update_range(ws, "A1", [headers] + data_rows)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error sync factura_items: {e}")
        return False


def gs_sync_operadores(sh):
    """Vuelca la tabla operadores a Operadores (clear + update batch).
    No exporta pin_hash por seguridad."""
    if not sh:
        return False
    try:
        con = get_db()
        rows = con.execute("""
            SELECT id, nombre, rol, turno,
                   hora_inicio_turno, hora_fin_turno,
                   permisos, activo
            FROM operadores
            ORDER BY id
        """).fetchall()
        con.close()

        ws = _gs_get_or_create_ws(sh, "Operadores")
        ws.clear()
        headers = DRIVE_SHEETS["Operadores"]
        data_rows = []
        for r in rows:
            (op_id, nombre, rol, turno,
             hora_ini, hora_fin,
             permisos, activo) = r
            data_rows.append([
                str(op_id),
                str(nombre or ""),
                str(rol or ""),
                str(turno or ""),
                str(hora_ini or ""),
                str(hora_fin or ""),
                str(permisos or ""),
                str(activo if activo is not None else "1"),
            ])

        _gs_update_range(ws, "A1", [headers] + data_rows)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error sync operadores: {e}")
        return False


def gs_sync_configuracion_pagos(sh):
    """Vuelca la tabla configuracion_pagos a Configuracion_Pagos (clear + update batch)."""
    if not sh:
        return False
    try:
        con = get_db()
        rows = con.execute("""
            SELECT clave, valor
            FROM configuracion_pagos
            ORDER BY clave
        """).fetchall()
        con.close()

        ws = _gs_get_or_create_ws(sh, "Configuracion_Pagos")
        ws.clear()
        headers = DRIVE_SHEETS["Configuracion_Pagos"]
        data_rows = []
        for r in rows:
            clave, valor = r
            data_rows.append([
                str(clave or ""),
                str(valor or ""),
            ])

        _gs_update_range(ws, "A1", [headers] + data_rows)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error sync configuracion_pagos: {e}")
        return False


def sincronizacion_completa() -> dict:
    """Vuelca todas las tablas SQLite → Google Sheets en batch con columnas alineadas."""
    client, sh = get_active_client()
    if not sh:
        return {"error": "Sin conexión a Google Sheets. Verifica secrets.toml y credenciales."}

    conteos = {}

    # ── Clientes ──────────────────────────────────────────────────────────────
    # Columnas: ID_Cliente,Nombre,Tipo_Doc,Num_Doc,Telefono,Email,Ciudad,
    #           Regimen,Tipo_Persona,Razon_Social,NIT_Empresa,Activo,
    #           Total_Reservas,Total_Gastado_COP,Creado_En
    try:
        con = get_db()
        rows = con.execute("""
            SELECT c.id, c.nombre, c.tipo_documento, c.numero_documento,
                   c.telefono, c.email, c.ciudad, c.regimen, c.tipo_persona,
                   c.razon_social, c.nit_empresa, c.activo,
                   COUNT(r.id), COALESCE(SUM(r.total),0),
                   c.creado_en
            FROM clientes c
            LEFT JOIN reservas r ON r.cliente_id = c.id
            GROUP BY c.id ORDER BY c.id
        """).fetchall()
        con.close()
        ws = _gs_get_or_create_ws(sh, "Clientes")
        ws.clear()
        _gs_update_range(ws, "A1", [DRIVE_SHEETS["Clientes"]] +
                  [[str(v) if v is not None else "" for v in r] for r in rows])
        conteos["Clientes"] = len(rows)
    except Exception as e:
        conteos["Clientes"] = f"Error: {e}"

    # ── Reservas ──────────────────────────────────────────────────────────────
    # Columnas: ID_Reserva,Numero_Reserva,Creado_En,Cubiculo_Num,
    #           Cliente_Nombre,Documento,Telefono,Email,
    #           Horas_Contratadas,Hora_Inicio,Hora_Fin_Prog,Hora_Fin_Real,
    #           Precio_Hora,Subtotal,IVA,Total_COP,
    #           Metodo_Pago,Estado_Pago,Codigo_Acceso,
    #           WiFi_SSID,WiFi_Pass,Num_Factura,Referencia_Pago,Operador,Notas
    try:
        con = get_db()
        rows = con.execute("""
            SELECT r.id, r.numero_reserva, r.creado_en,
                   cu.numero,
                   cl.nombre, cl.numero_documento, cl.telefono, cl.email,
                   r.horas_contratadas, r.hora_inicio, r.hora_fin_programada, r.hora_fin_real,
                   r.precio_hora, r.subtotal, r.iva, r.total,
                   r.metodo_pago, r.estado_pago, r.codigo_acceso,
                   cu.wifi_ssid, cu.wifi_password,
                   f.numero, r.referencia_pago, 'sistema', r.notas
            FROM reservas r
            LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
            LEFT JOIN clientes cl ON r.cliente_id = cl.id
            LEFT JOIN facturas f ON r.factura_id = f.id
            ORDER BY r.id
        """).fetchall()
        con.close()
        ws = _gs_get_or_create_ws(sh, "Reservas")
        ws.clear()
        _gs_update_range(ws, "A1", [DRIVE_SHEETS["Reservas"]] +
                  [[str(v) if v is not None else "" for v in r] for r in rows])
        conteos["Reservas"] = len(rows)
    except Exception as e:
        conteos["Reservas"] = f"Error: {e}"

    # ── Pagos ─────────────────────────────────────────────────────────────────
    # Columnas: ID_Pago,ID_Reserva,Num_Reserva,Fecha_Pago,
    #           Monto_COP,Metodo,Referencia_Externa,Estado,Confirmado_Por,Notas
    try:
        con = get_db()
        rows = con.execute("""
            SELECT p.id, p.reserva_id, r.numero_reserva, p.fecha_pago,
                   p.monto, p.metodo, p.referencia_externa,
                   p.estado, p.confirmado_por, p.notas
            FROM pagos p
            LEFT JOIN reservas r ON p.reserva_id = r.id
            ORDER BY p.id
        """).fetchall()
        con.close()
        ws = _gs_get_or_create_ws(sh, "Pagos")
        ws.clear()
        _gs_update_range(ws, "A1", [DRIVE_SHEETS["Pagos"]] +
                  [[str(v) if v is not None else "" for v in r] for r in rows])
        conteos["Pagos"] = len(rows)
    except Exception as e:
        conteos["Pagos"] = f"Error: {e}"

    # ── Facturas ──────────────────────────────────────────────────────────────
    # Columnas: ID_Factura,Num_Factura,Tipo,Fecha_Emision,Fecha_Venc,
    #           Cliente,Documento,Email,Razon_Social,NIT_Emp,
    #           Descripcion,Subtotal,Descuento,Base_Gravable,IVA,Retenciones,Total_COP,
    #           Metodo_Pago,Estado,Moneda,Num_Reserva,Cubiculo,Creado_En,Actualizado_En
    try:
        con = get_db()
        rows = con.execute("""
            SELECT f.id, f.numero, f.tipo, f.fecha_emision, f.fecha_vencimiento,
                   cl.nombre, cl.numero_documento, cl.email,
                   cl.razon_social, cl.nit_empresa,
                   fi.descripcion,
                   f.subtotal, f.descuento,
                   (f.subtotal - f.descuento),
                   f.iva, f.retenciones, f.total,
                   f.metodo_pago, f.estado, f.moneda,
                   r.numero_reserva, cu.numero,
                   f.creado_en, f.actualizado_en
            FROM facturas f
            LEFT JOIN clientes cl ON f.cliente_id = cl.id
            LEFT JOIN factura_items fi ON fi.factura_id = f.id
            LEFT JOIN reservas r ON r.factura_id = f.id
            LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
            GROUP BY f.id ORDER BY f.id
        """).fetchall()
        con.close()
        ws = _gs_get_or_create_ws(sh, "Facturas")
        ws.clear()
        _gs_update_range(ws, "A1", [DRIVE_SHEETS["Facturas"]] +
                  [[str(v) if v is not None else "" for v in r] for r in rows])
        conteos["Facturas"] = len(rows)
    except Exception as e:
        conteos["Facturas"] = f"Error: {e}"

    # ── Tarifas ───────────────────────────────────────────────────────────────
    # Columnas: ID,Nombre,Descripcion,Precio_Hora_COP,
    #           Desc_3h_Pct,Desc_6h_Pct,Hora_Ini_Espec,Hora_Fin_Espec,
    #           Aplica_Festivos,Activo
    try:
        con = get_db()
        rows = con.execute("""
            SELECT id, nombre, descripcion, precio_hora,
                   descuento_3h_pct, descuento_6h_pct,
                   hora_inicio_especial, hora_fin_especial,
                   aplica_festivos, activo
            FROM tarifas ORDER BY id
        """).fetchall()
        con.close()
        ws = _gs_get_or_create_ws(sh, "Tarifas_Config")
        ws.clear()
        _gs_update_range(ws, "A1", [DRIVE_SHEETS["Tarifas_Config"]] +
                  [[str(v) if v is not None else "" for v in r] for r in rows])
        conteos["Tarifas_Config"] = len(rows)
    except Exception as e:
        conteos["Tarifas_Config"] = f"Error: {e}"

    conteos["Cubiculos_Estado"] = "OK" if gs_sync_cubiculos(sh) else "Error"
    conteos["Dashboard_Diario"] = "OK" if gs_sync_dashboard(sh) else "Error"
    conteos["Factura_items"]    = "OK" if gs_sync_factura_items(sh) else "Error"
    conteos["Operadores"]       = "OK" if gs_sync_operadores(sh) else "Error"
    conteos["Configuracion_Pagos"] = "OK" if gs_sync_configuracion_pagos(sh) else "Error"
    gs_escribir_log(sh, "sync_completa", "", "", "sistema",
                    f"Sync completa ejecutada: {conteos}", "exito")
    return conteos


# ── Stubs de compatibilidad ───────────────────────────────────────────────────

def _get_module_level_client():
    return get_active_client()

def encolar_sync(event: dict):
    pass  # Reemplazado por escritura directa síncrona

def _ensure_sync_thread():
    pass

def _marcar_sync_pendiente(tabla: str, registro_id: int):
    try:
        con = get_db()
        con.execute(
            "INSERT INTO sync_log "
            "(tabla,registro_id,accion,sync_pendiente,creado_en) VALUES (?,?,?,1,?)",
            (tabla, registro_id, "upsert", ahora_col().isoformat()))
        con.commit()
        con.close()
    except Exception:
        pass

def sheets_append_row(worksheet_name: str, row_data: list) -> bool:
    _, sh = get_active_client()
    if not sh:
        return False
    return _gs_append(sh, worksheet_name, row_data)

def sheets_upsert_row(worksheet_name, col_key, key_value, row_data):
    _, sh = get_active_client()
    if not sh:
        return False
    return _gs_upsert(sh, worksheet_name, col_key, key_value, row_data)

def sheets_update_row(worksheet_name, col_key, key_value, update_data):
    _, sh = get_active_client()
    if not sh:
        return False
    try:
        ws = sh.worksheet(worksheet_name)
        vals = ws.get_all_values()
        if not vals:
            return False
        hdr = vals[0]
        col_idx = hdr.index(col_key) if col_key in hdr else -1
        if col_idx < 0:
            return False
        for i, r in enumerate(vals[1:], start=2):
            if len(r) > col_idx and str(r[col_idx]) == str(key_value):
                for col_name, new_val in update_data.items():
                    if col_name in hdr:
                        ws.update_cell(i, hdr.index(col_name) + 1, str(new_val))
                return True
        return False
    except Exception:
        return False

def load_data_from_sheet(client, sheet_name: str, worksheet_name: str) -> pd.DataFrame:
    """Carga una hoja como DataFrame. Si no existe la crea vacía con encabezados."""
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet   = _gs_get_or_create_ws(spreadsheet, worksheet_name)
        data        = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando datos de '{worksheet_name}': {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS — SQLITE
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    con = get_db()
    cur = con.cursor()

    # ── Tablas compartidas con facturacion.py ──────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tipo_documento TEXT DEFAULT 'CC',
        numero_documento TEXT,
        telefono TEXT,
        email TEXT,
        ciudad TEXT,
        regimen TEXT DEFAULT 'Simplificado',
        tipo_persona TEXT DEFAULT 'Natural',
        razon_social TEXT,
        nit_empresa TEXT,
        activo INTEGER DEFAULT 1,
        creado_en TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        tipo TEXT DEFAULT 'Factura de Venta',
        fecha_emision TEXT,
        fecha_vencimiento TEXT,
        cliente_id INTEGER,
        subtotal REAL DEFAULT 0,
        descuento REAL DEFAULT 0,
        iva REAL DEFAULT 0,
        retenciones REAL DEFAULT 0,
        total REAL DEFAULT 0,
        estado TEXT DEFAULT 'emitida',
        moneda TEXT DEFAULT 'COP',
        notas TEXT,
        metodo_pago TEXT,
        creado_en TEXT,
        actualizado_en TEXT,
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS factura_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factura_id INTEGER,
        codigo TEXT,
        descripcion TEXT,
        cantidad REAL DEFAULT 1,
        unidad TEXT DEFAULT 'hora',
        precio_unitario REAL DEFAULT 0,
        descuento_pct REAL DEFAULT 0,
        iva_pct REAL DEFAULT 19,
        subtotal REAL DEFAULT 0,
        FOREIGN KEY (factura_id) REFERENCES facturas(id)
    )""")

    # ── Tablas propias de pagos ────────────────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS cubiculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        nombre TEXT,
        estado TEXT DEFAULT 'libre',
        reserva_activa_id INTEGER,
        hora_disponible TEXT,
        precio_hora_base REAL DEFAULT 15000,
        wifi_ssid TEXT,
        wifi_password TEXT,
        servicios TEXT DEFAULT '["Baño","WiFi","Carga USB"]',
        notas TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS tarifas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        precio_hora REAL NOT NULL,
        descuento_3h_pct REAL DEFAULT 10,
        descuento_6h_pct REAL DEFAULT 20,
        hora_inicio_especial TEXT,
        hora_fin_especial TEXT,
        aplica_festivos INTEGER DEFAULT 0,
        activo INTEGER DEFAULT 1
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_reserva TEXT UNIQUE NOT NULL,
        cubiculo_id INTEGER,
        cliente_id INTEGER,
        factura_id INTEGER,
        hora_inicio TEXT,
        hora_fin_programada TEXT,
        hora_fin_real TEXT,
        horas_contratadas REAL,
        precio_hora REAL,
        subtotal REAL,
        iva REAL,
        total REAL,
        metodo_pago TEXT,
        estado_pago TEXT DEFAULT 'pendiente',
        codigo_acceso TEXT,
        referencia_pago TEXT,
        notas TEXT,
        creado_en TEXT,
        FOREIGN KEY (cubiculo_id) REFERENCES cubiculos(id),
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reserva_id INTEGER,
        monto REAL,
        metodo TEXT,
        referencia_externa TEXT,
        estado TEXT DEFAULT 'pendiente',
        fecha_pago TEXT,
        confirmado_por TEXT,
        notas TEXT,
        FOREIGN KEY (reserva_id) REFERENCES reservas(id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS operadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        rol TEXT DEFAULT 'cajero',
        turno TEXT DEFAULT 'diurno',
        hora_inicio_turno TEXT DEFAULT '06:00',
        hora_fin_turno TEXT DEFAULT '14:00',
        permisos TEXT DEFAULT 'reservas,pagos,voucher',
        activo INTEGER DEFAULT 1
    )""")

    # Migración: agregar columnas de turno/permisos si no existen (BD ya creada)
    for col_def in [
        ("turno",             "TEXT DEFAULT 'diurno'"),
        ("hora_inicio_turno", "TEXT DEFAULT '06:00'"),
        ("hora_fin_turno",    "TEXT DEFAULT '14:00'"),
        ("permisos",          "TEXT DEFAULT 'reservas,pagos,voucher'"),
    ]:
        try:
            cur.execute(f"ALTER TABLE operadores ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass  # Columna ya existe

    cur.execute("""CREATE TABLE IF NOT EXISTS configuracion_pagos (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tabla TEXT,
        registro_id INTEGER,
        accion TEXT,
        sync_pendiente INTEGER DEFAULT 1,
        creado_en TEXT
    )""")

    # ── Datos iniciales ────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM cubiculos")
    bd_vacia = cur.fetchone()[0] == 0

    if bd_vacia:
        if _IS_CLOUD:
            # En Cloud: intentar restaurar desde Google Sheets primero
            con.commit()
            con.close()
            restaurado = _restore_from_sheets()
            if not restaurado:
                # Si Sheets no está disponible aún, cargar seed mínimo
                con2 = get_db()
                _seed_data(con2.cursor())
                con2.commit()
                con2.close()
        else:
            _seed_data(cur)
            con.commit()
            con.close()
    else:
        con.commit()
        con.close()


def _restore_from_sheets() -> bool:
    """
    En entorno Cloud (SQLite vacía), restaura TODA la información desde Google Sheets
    hacia SQLite local para que el resto de la app funcione normalmente.
    Retorna True si la restauración fue exitosa y cargó al menos cubículos.
    Orden de carga respeta FK: config → clientes → facturas → factura_items
                                → cubiculos → tarifas → operadores
                                → reservas → pagos
    """
    if not GSPREAD_AVAILABLE:
        return False
    try:
        _, sh = get_active_client()
        if not sh:
            return False
    except Exception:
        return False

    con = get_db()
    cur = con.cursor()

    def _rows(hoja):
        """Devuelve lista de dicts desde una hoja de Sheets, o [] si falla."""
        try:
            ws = _gs_get_or_create_ws(sh, hoja)
            return ws.get_all_records()
        except Exception:
            return []

    def _val(row, key, default=""):
        v = row.get(key, default)
        return v if v != "" else default

    def _float(row, key, default=0.0):
        try:
            return float(_val(row, key, default))
        except Exception:
            return float(default)

    def _int(row, key, default=0):
        try:
            return int(float(_val(row, key, default)))
        except Exception:
            return int(default)

    try:
        # ── 1. configuracion_pagos ─────────────────────────────────────────
        for r in _rows("Configuracion_Pagos"):
            clave = _val(r, "Clave")
            valor = _val(r, "Valor")
            if clave:
                cur.execute("INSERT OR REPLACE INTO configuracion_pagos VALUES (?,?)",
                            (clave, valor))
        # Si no había config en Sheets, insertar valores base
        cur.execute("SELECT COUNT(*) FROM configuracion_pagos")
        if cur.fetchone()[0] == 0:
            configs_base = [
                ("negocio_nombre",    NEGOCIO),
                ("negocio_nit",       NIT),
                ("negocio_direccion", DIRECCION),
                ("negocio_telefono",  TELEFONO),
                ("negocio_email",     ""),
                ("negocio_web",       ""),
                ("nequi_numero",      NEQUI_NUM),
                ("daviplata_numero",  DAVIPLATA_NUM),
                ("cuenta_bancaria",   CUENTA_BANCO),
                ("mp_link",           MP_LINK),
                ("whatsapp_op",       WHATSAPP_OP),
                ("tiempo_minimo_h",   "0.5"),
                ("factura_prefijo",   "FACT"),
                ("factura_contador",  "0"),
                ("drive_spreadsheet_id", ""),
                ("drive_credentials_path", "credentials.json"),
            ]
            for k, v in configs_base:
                cur.execute("INSERT OR IGNORE INTO configuracion_pagos VALUES (?,?)", (k, v))

        # ── 2. clientes ────────────────────────────────────────────────────
        # Columnas Sheets: ID_Cliente,Nombre,Tipo_Doc,Num_Doc,Telefono,
        #                  Email,Ciudad,Regimen,Tipo_Persona,Razon_Social,
        #                  NIT_Empresa,Activo,…,Creado_En
        id_map_clientes = {}   # ID_Sheets → id SQLite real
        for r in _rows("Clientes"):
            sh_id = _val(r, "ID_Cliente")
            nombre = _val(r, "Nombre")
            if not nombre:
                continue
            num_doc = _val(r, "Num_Doc")
            # Evitar duplicados por documento
            existing = cur.execute(
                "SELECT id FROM clientes WHERE numero_documento=?", (num_doc,)).fetchone()
            if existing:
                id_map_clientes[sh_id] = existing[0]
                continue
            cur.execute("""INSERT INTO clientes
                (nombre,tipo_documento,numero_documento,telefono,email,ciudad,
                 regimen,tipo_persona,razon_social,nit_empresa,activo,creado_en)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_val(r, "Nombre"), _val(r, "Tipo_Doc", "CC"),
                 num_doc, _val(r, "Telefono"), _val(r, "Email"),
                 _val(r, "Ciudad"), _val(r, "Regimen", "Simplificado"),
                 _val(r, "Tipo_Persona", "Natural"), _val(r, "Razon_Social"),
                 _val(r, "NIT_Empresa"), _int(r, "Activo", 1),
                 _val(r, "Creado_En", ahora_col().isoformat())))
            id_map_clientes[sh_id] = cur.lastrowid

        # ── 3. facturas ────────────────────────────────────────────────────
        # Columnas Sheets: ID_Factura,Num_Factura,Tipo,Fecha_Emision,
        #                  Fecha_Vencimieento,Cliente__id,Subtotal,…,Actualizado_En
        id_map_facturas = {}
        for r in _rows("Facturas"):
            sh_id = _val(r, "ID_Factura")
            numero = _val(r, "Num_Factura")
            if not numero:
                continue
            existing = cur.execute(
                "SELECT id FROM facturas WHERE numero=?", (numero,)).fetchone()
            if existing:
                id_map_facturas[sh_id] = existing[0]
                continue
            # Resolver cliente_id: buscar por nombre+documento en columnas desnormalizadas
            cli_doc = _val(r, "Cliente__id")   # columna tiene el id original de sheets
            cliente_id = id_map_clientes.get(str(cli_doc))
            if not cliente_id:
                # intentar por nombre
                cli_row = cur.execute(
                    "SELECT id FROM clientes WHERE numero_documento=?", (cli_doc,)).fetchone()
                cliente_id = cli_row[0] if cli_row else None
            cur.execute("""INSERT INTO facturas
                (numero,tipo,fecha_emision,fecha_vencimiento,cliente_id,
                 subtotal,descuento,iva,retenciones,total,estado,moneda,
                 notas,metodo_pago,creado_en,actualizado_en)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (numero, _val(r, "Tipo", "Factura de Venta"),
                 _val(r, "Fecha_Emision"), _val(r, "Fecha_Vencimieento"),
                 cliente_id,
                 _float(r, "Subtotal"), _float(r, "Descuento"),
                 _float(r, "IVA"), _float(r, "Retenciones"),
                 _float(r, "Total_COP"),
                 _val(r, "Estado", "pagada"), _val(r, "Moneda", "COP"),
                 _val(r, "notas"), _val(r, "Metodo_Pago"),
                 _val(r, "Creado_En"), _val(r, "Actualizado_En")))
            id_map_facturas[sh_id] = cur.lastrowid

        # ── 4. factura_items ───────────────────────────────────────────────
        for r in _rows("Factura_items"):
            sh_fact_id = _val(r, "ID_Factura")
            factura_id = id_map_facturas.get(str(sh_fact_id))
            if not factura_id:
                continue
            cur.execute("""INSERT INTO factura_items
                (factura_id,codigo,descripcion,cantidad,unidad,
                 precio_unitario,descuento_pct,iva_pct,subtotal)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (factura_id, _val(r, "codigo"), _val(r, "descripcion"),
                 _float(r, "cantidad", 1), _val(r, "unidad", "hora"),
                 _float(r, "precio_unitario"), _float(r, "Descuento_pct"),
                 _float(r, "Iva_pct", 19), _float(r, "subtotal_COP")))

        # ── 5. cubiculos ───────────────────────────────────────────────────
        # Columnas Sheets (Cubiculos_Estado): Cubiculo_ID,Numero,Nombre,Estado,
        #   Cliente_Actual,Hora_Inicio,Hora_Fin_Prog,Tiempo_Rest_Min,
        #   Codigo_Acceso,WiFi_SSID,WiFi_Pass,Precio_Hora_Base,…
        id_map_cubiculos = {}
        for r in _rows("Cubiculos_Estado"):
            sh_id = _val(r, "Cubiculo_ID")
            numero = _val(r, "Numero")
            if not numero:
                continue
            existing = cur.execute(
                "SELECT id FROM cubiculos WHERE numero=?", (numero,)).fetchone()
            if existing:
                id_map_cubiculos[sh_id] = existing[0]
                # Actualizar estado y wifi desde Sheets
                cur.execute("""UPDATE cubiculos SET estado=?,wifi_ssid=?,
                    wifi_password=?,precio_hora_base=? WHERE id=?""",
                    (_val(r, "Estado", "libre"), _val(r, "WiFi_SSID"),
                     _val(r, "WiFi_Pass"), _float(r, "Precio_Hora_Base", 15000),
                     existing[0]))
                continue
            cur.execute("""INSERT INTO cubiculos
                (numero,nombre,estado,precio_hora_base,wifi_ssid,wifi_password,
                 servicios,notas)
                VALUES (?,?,?,?,?,?,?,?)""",
                (numero, _val(r, "Nombre", f"Cubículo {numero}"),
                 _val(r, "Estado", "libre"),
                 _float(r, "Precio_Hora_Base", 15000),
                 _val(r, "WiFi_SSID"), _val(r, "WiFi_Pass"),
                 json.dumps(["Baño", "WiFi", "Carga USB", "Carga 110V"]),
                 _val(r, "Notas")))
            id_map_cubiculos[sh_id] = cur.lastrowid

        # Si Sheets no tenía cubículos (primera vez), crear estructura base
        cur.execute("SELECT COUNT(*) FROM cubiculos")
        if cur.fetchone()[0] == 0:
            for i in range(1, 13):
                num = f"#{i:02d}"
                cur.execute("""INSERT INTO cubiculos
                    (numero,nombre,estado,precio_hora_base,wifi_ssid,wifi_password,servicios)
                    VALUES (?,?,?,?,?,?,?)""",
                    (num, f"Cubículo {num}", "libre", 15000,
                     f"JJGT-Cubiculo-{i:02d}", f"Desc{i:02d}2025",
                     json.dumps(["Baño", "WiFi", "Carga USB", "Carga 110V"])))

        # ── 6. tarifas ─────────────────────────────────────────────────────
        for r in _rows("Tarifas_Config"):
            nombre_t = _val(r, "Nombre")
            if not nombre_t:
                continue
            existing = cur.execute(
                "SELECT id FROM tarifas WHERE nombre=?", (nombre_t,)).fetchone()
            if existing:
                cur.execute("""UPDATE tarifas SET precio_hora=?,descuento_3h_pct=?,
                    descuento_6h_pct=?,activo=? WHERE id=?""",
                    (_float(r, "Precio_Hora_COP", 15000),
                     _float(r, "Desc_3h_Pct", 10), _float(r, "Desc_6h_Pct", 20),
                     _int(r, "Activo", 1), existing[0]))
            else:
                cur.execute("""INSERT INTO tarifas
                    (nombre,descripcion,precio_hora,descuento_3h_pct,descuento_6h_pct,
                     hora_inicio_especial,hora_fin_especial,aplica_festivos,activo)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (nombre_t, _val(r, "Descripcion"),
                     _float(r, "Precio_Hora_COP", 15000),
                     _float(r, "Desc_3h_Pct", 10), _float(r, "Desc_6h_Pct", 20),
                     _val(r, "Hora_Ini_Espec"), _val(r, "Hora_Fin_Espec"),
                     _int(r, "Aplica_Festivos", 0), _int(r, "Activo", 1)))
        # Seed tarifas base si Sheets no tenía
        cur.execute("SELECT COUNT(*) FROM tarifas")
        if cur.fetchone()[0] == 0:
            for t in [
                ("Estándar",  "Tarifa normal diurna",           15000, 10, 20, None, None,   0),
                ("Madrugada", "Tarifa nocturna 00:00–06:00",    10000, 10, 20, "00:00", "06:00", 0),
                ("Festivo",   "Tarifa días festivos y domingos",18000, 10, 20, None, None,   1),
            ]:
                cur.execute("""INSERT INTO tarifas
                    (nombre,descripcion,precio_hora,descuento_3h_pct,descuento_6h_pct,
                     hora_inicio_especial,hora_fin_especial,aplica_festivos,activo)
                    VALUES (?,?,?,?,?,?,?,?,1)""", t)

        # ── 7. operadores ──────────────────────────────────────────────────
        # Columnas Sheets: ID_Operador,Nombre,Rol,Turno,
        #                  Hora_Ini_Turno,Hora_Fin_Turno,Permisos,Activo
        # NOTA: pin_hash NO se exporta a Sheets — se preserva la hash existente
        #       o se asigna pin por defecto "1234" para admin si no hay ninguno.
        id_map_operadores = {}
        for r in _rows("Operadores"):
            sh_id  = _val(r, "ID_Operador")
            nombre = _val(r, "Nombre")
            if not nombre:
                continue
            existing = cur.execute(
                "SELECT id FROM operadores WHERE nombre=?", (nombre,)).fetchone()
            if existing:
                id_map_operadores[sh_id] = existing[0]
                cur.execute("""UPDATE operadores SET rol=?,turno=?,
                    hora_inicio_turno=?,hora_fin_turno=?,permisos=?,activo=?
                    WHERE id=?""",
                    (_val(r, "Rol", "cajero"), _val(r, "Turno", "diurno"),
                     _val(r, "Hora_Ini_Turno", "06:00"),
                     _val(r, "Hora_Fin_Turno", "14:00"),
                     _val(r, "Permisos", "reservas,pagos,voucher"),
                     _int(r, "Activo", 1), existing[0]))
            else:
                cur.execute("""INSERT INTO operadores
                    (nombre,pin_hash,rol,turno,hora_inicio_turno,
                     hora_fin_turno,permisos,activo)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (nombre, _hash_pin("1234"),
                     _val(r, "Rol", "cajero"), _val(r, "Turno", "diurno"),
                     _val(r, "Hora_Ini_Turno", "06:00"),
                     _val(r, "Hora_Fin_Turno", "14:00"),
                     _val(r, "Permisos", "reservas,pagos,voucher"),
                     _int(r, "Activo", 1)))
                id_map_operadores[sh_id] = cur.lastrowid
        # Seed operadores base si Sheets no tenía
        cur.execute("SELECT COUNT(*) FROM operadores")
        if cur.fetchone()[0] == 0:
            for nombre, pin, rol, turno, h_ini, h_fin, permisos in [
                ("Admin JJGT", "1234", "admin",  "diurno", "06:00","14:00",
                 "admin,reservas,pagos,voucher,reportes,configuracion"),
                ("Op. Mañana", "1111", "cajero", "mañana", "06:00","14:00",
                 "reservas,pagos,voucher"),
                ("Op. Tarde",  "2222", "cajero", "tarde",  "14:00","22:00",
                 "reservas,pagos,voucher"),
                ("Op. Noche",  "3333", "cajero", "noche",  "22:00","06:00",
                 "reservas,pagos,voucher"),
            ]:
                cur.execute("""INSERT INTO operadores
                    (nombre,pin_hash,rol,turno,hora_inicio_turno,hora_fin_turno,permisos)
                    VALUES (?,?,?,?,?,?,?)""",
                    (nombre, _hash_pin(pin), rol, turno, h_ini, h_fin, permisos))

        # ── 8. reservas ────────────────────────────────────────────────────
        # Columnas Sheets: ID_Reserva,Numero_Reserva,creado_en,Cubiculo_Num,
        #   Cliente_Nombre,Documento,Telefono,Email,Horas_Contratadas,
        #   Hora_Inicio,Hora_Fin_Prog,Hora_Fin_Real,Precio_Hora,Subtotal,IVA,
        #   Total_COP,Metodo_Pago,Estado_Pago,Codigo_Acceso,WiFi_SSID,WiFi_Pass,
        #   Num_Factura,Referencia_Pago,Operador,Notas
        id_map_reservas = {}
        for r in _rows("Reservas"):
            sh_id   = _val(r, "ID_Reserva")
            num_res = _val(r, "Numero_Reserva")
            if not num_res:
                continue
            existing = cur.execute(
                "SELECT id FROM reservas WHERE numero_reserva=?", (num_res,)).fetchone()
            if existing:
                id_map_reservas[sh_id] = existing[0]
                continue
            # Resolver cubiculo_id
            cub_num   = _val(r, "Cubiculo_Num") or _val(r, "Cubiculo")
            cub_row   = cur.execute(
                "SELECT id FROM cubiculos WHERE numero=?", (cub_num,)).fetchone()
            cub_id    = cub_row[0] if cub_row else None
            # Resolver cliente_id por documento
            cli_doc   = _val(r, "Documento")
            cli_row   = cur.execute(
                "SELECT id FROM clientes WHERE numero_documento=?", (cli_doc,)).fetchone()
            cli_id    = cli_row[0] if cli_row else None
            # Resolver factura_id por numero
            num_fact  = _val(r, "Num_Factura")
            fact_row  = cur.execute(
                "SELECT id FROM facturas WHERE numero=?", (num_fact,)).fetchone()
            fact_id   = fact_row[0] if fact_row else None

            cur.execute("""INSERT INTO reservas
                (numero_reserva,cubiculo_id,cliente_id,factura_id,
                 hora_inicio,hora_fin_programada,hora_fin_real,
                 horas_contratadas,precio_hora,subtotal,iva,total,
                 metodo_pago,estado_pago,codigo_acceso,
                 referencia_pago,notas,creado_en)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (num_res, cub_id, cli_id, fact_id,
                 _val(r, "Hora_Inicio"), _val(r, "Hora_Fin_Prog"),
                 _val(r, "Hora_Fin_Real"),
                 _float(r, "Horas_Contratadas", 1),
                 _float(r, "Precio_Hora"), _float(r, "Subtotal"),
                 _float(r, "IVA"), _float(r, "Total_COP"),
                 _val(r, "Metodo_Pago"), _val(r, "Estado_Pago", "confirmado"),
                 _val(r, "Codigo_Acceso"), _val(r, "Referencia_Pago"),
                 _val(r, "Notas"), _val(r, "creado_en", ahora_col().isoformat())))
            id_map_reservas[sh_id] = cur.lastrowid

        # Restaurar reserva_activa_id en cubículos con reservas abiertas
        rows_act = cur.execute("""
            SELECT r.id, r.cubiculo_id, r.hora_fin_programada
            FROM reservas r
            WHERE (r.hora_fin_real IS NULL OR r.hora_fin_real = '')
              AND r.estado_pago = 'confirmado'
        """).fetchall()
        for res_id, cub_id, hora_fin in rows_act:
            if cub_id:
                cur.execute("""UPDATE cubiculos SET reserva_activa_id=?,
                    hora_disponible=? WHERE id=?""",
                    (res_id, hora_fin, cub_id))

        # ── 9. pagos ───────────────────────────────────────────────────────
        for r in _rows("Pagos"):
            sh_id   = _val(r, "ID_Pago")
            num_res = _val(r, "Num_Reserva") or _val(r, "ID_Reserva")
            if not num_res:
                continue
            # Buscar reserva_id
            res_row = cur.execute(
                "SELECT id FROM reservas WHERE numero_reserva=?", (num_res,)).fetchone()
            if not res_row:
                continue
            res_id = res_row[0]
            # Evitar duplicar pago de la misma reserva
            dup = cur.execute(
                "SELECT id FROM pagos WHERE reserva_id=?", (res_id,)).fetchone()
            if dup:
                continue
            cur.execute("""INSERT INTO pagos
                (reserva_id,monto,metodo,referencia_externa,
                 estado,fecha_pago,confirmado_por,notas)
                VALUES (?,?,?,?,?,?,?,?)""",
                (res_id, _float(r, "Monto_COP"), _val(r, "Metodo"),
                 _val(r, "Referencia_Externa"),
                 _val(r, "Estado", "confirmado"), _val(r, "Fecha_Pago"),
                 _val(r, "Confirmado_Por", "sistema"), _val(r, "Notas")))

        con.commit()
        con.close()
        return True

    except Exception as e:
        try:
            con.rollback()
            con.close()
        except Exception:
            pass
        st.warning(f"⚠️ Restauración desde Sheets falló: {e}. Usando datos de seed.")
        return False


def _seed_data(cur):
    """Carga datos de demostración coherentes con el negocio."""
    now = datetime.now(TZ_COL)

    # Cubículos #01–#12
    estados_demo = [
        ("libre", None), ("libre", None), ("libre", None), ("libre", None), ("libre", None),
        ("ocupado", now - timedelta(hours=1, minutes=20)),
        ("ocupado", now - timedelta(minutes=45)),
        ("ocupado", now - timedelta(hours=2)),
        ("ocupado", now - timedelta(minutes=10)),
        ("ocupado", now - timedelta(hours=3, minutes=30)),
        ("mantenimiento", None), ("mantenimiento", None),
    ]
    for i, (estado, _) in enumerate(estados_demo, 1):
        num = f"#{i:02d}"
        cur.execute("""INSERT INTO cubiculos
            (numero, nombre, estado, precio_hora_base, wifi_ssid, wifi_password, servicios)
            VALUES (?,?,?,?,?,?,?)""",
            (num, f"Cubículo {num}", estado, 15000,
             f"JJGT-Cubiculo-{i:02d}", f"Desc{i:02d}2025",
             json.dumps(["Baño", "WiFi", "Carga USB", "Carga 110V"])))

    # Tarifas
    tarifas = [
        ("Estándar",   "Tarifa normal diurna",            15000, 10, 20, None, None,   0),
        ("Madrugada",  "Tarifa nocturna 00:00–06:00",     10000, 10, 20, "00:00", "06:00", 0),
        ("Festivo",    "Tarifa días festivos y domingos", 18000, 10, 20, None, None,   1),
    ]
    for t in tarifas:
        cur.execute("""INSERT INTO tarifas
            (nombre,descripcion,precio_hora,descuento_3h_pct,descuento_6h_pct,
             hora_inicio_especial,hora_fin_especial,aplica_festivos,activo)
            VALUES (?,?,?,?,?,?,?,?,1)""", t)

    # Operadores con turnos de 8 horas
    ops_seed = [
        ("Admin JJGT", "1234", "admin",  "diurno",   "06:00", "14:00", "admin,reservas,pagos,voucher,reportes,configuracion"),
        ("Op. Mañana", "1111", "cajero", "mañana",   "06:00", "14:00", "reservas,pagos,voucher"),
        ("Op. Tarde",  "2222", "cajero", "tarde",    "14:00", "22:00", "reservas,pagos,voucher"),
        ("Op. Noche",  "3333", "cajero", "noche",    "22:00", "06:00", "reservas,pagos,voucher"),
    ]
    for nombre, pin, rol, turno, h_ini, h_fin, permisos in ops_seed:
        cur.execute(
            "INSERT INTO operadores (nombre,pin_hash,rol,turno,hora_inicio_turno,hora_fin_turno,permisos) VALUES (?,?,?,?,?,?,?)",
            (nombre, _hash_pin(pin), rol, turno, h_ini, h_fin, permisos))

    # Configuración
    configs = [
        ("negocio_nombre",   NEGOCIO),
        ("negocio_nit",      NIT),
        ("negocio_direccion",DIRECCION),
        ("negocio_telefono", TELEFONO),
        ("negocio_email",    ""),
        ("negocio_web",      ""),
        ("nequi_numero",     NEQUI_NUM),
        ("daviplata_numero", DAVIPLATA_NUM),
        ("cuenta_bancaria",  CUENTA_BANCO),
        ("mp_link",          MP_LINK),
        ("whatsapp_op",      WHATSAPP_OP),
        ("tiempo_minimo_h",  "0.5"),
        ("factura_prefijo",  "FACT"),
        ("factura_contador", "0"),
        ("drive_spreadsheet_id", ""),
        ("drive_credentials_path", "credentials.json"),
    ]
    for k, v in configs:
        cur.execute("INSERT OR IGNORE INTO configuracion_pagos VALUES (?,?)", (k, v))

    # Sin datos de demo — la BD inicia vacía (solo estructura y configuración)


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


# Caché en memoria para configuracion_pagos — evita abrir SQLite en cada get_config
_config_cache: dict = {}
_config_cache_lock = threading.Lock()


def get_config(clave: str, default: str = "") -> str:
    """Lee configuración con caché en memoria para evitar SQLite en cada render."""
    with _config_cache_lock:
        if clave in _config_cache:
            return _config_cache[clave]
    try:
        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT valor FROM configuracion_pagos WHERE clave=?", (clave,))
        row = cur.fetchone()
        con.close()
        valor = row[0] if row else default
    except Exception:
        valor = default
    with _config_cache_lock:
        _config_cache[clave] = valor
    return valor


def set_config(clave: str, valor: str):
    """Guarda configuración en SQLite e invalida la entrada en caché."""
    try:
        con = get_db()
        con.execute("INSERT OR REPLACE INTO configuracion_pagos VALUES (?,?)", (clave, valor))
        con.commit()
        con.close()
    except Exception:
        pass
    with _config_cache_lock:
        _config_cache[clave] = valor


def verificar_pin(pin: str, rol: str = None) -> bool:
    """Verifica PIN y retorna True/False. Usa get_operador_por_pin para datos completos."""
    return get_operador_por_pin(pin, rol) is not None


def get_operador_por_pin(pin: str, rol: str = None) -> dict:
    """Retorna dict con datos del operador o None si no existe/inválido."""
    con = get_db()
    cur = con.cursor()
    q = ("SELECT id,nombre,rol,turno,hora_inicio_turno,hora_fin_turno,permisos "
         "FROM operadores WHERE pin_hash=? AND activo=1")
    params = [_hash_pin(pin)]
    if rol:
        q += " AND rol=?"
        params.append(rol)
    cur.execute(q, params)
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {
        "id": row[0], "nombre": row[1], "rol": row[2],
        "turno": row[3] or "diurno",
        "hora_inicio_turno": row[4] or "06:00",
        "hora_fin_turno":    row[5] or "14:00",
        "permisos": (row[6] or "reservas,pagos,voucher").split(","),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE NEGOCIO
# ══════════════════════════════════════════════════════════════════════════════

def ahora_col() -> datetime:
    return datetime.now(TZ_COL)


def calcular_precio(horas: float, tarifa_nombre: str = None) -> dict:
    """Calcula precio con tarifa vigente y descuentos."""
    if tarifa_nombre is None:
        hora_actual = ahora_col().hour
        if 0 <= hora_actual < 6:
            tarifa_nombre = "Madrugada"
        else:
            tarifa_nombre = "Estándar"

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT precio_hora,descuento_3h_pct,descuento_6h_pct FROM tarifas WHERE nombre=? AND activo=1", (tarifa_nombre,))
    row = cur.fetchone()
    con.close()

    precio_hora   = row[0] if row else 15000
    desc_3h       = row[1] if row else 30
    desc_6h       = row[2] if row else 40

    descuento_pct = 0
    if horas >= 6:
        descuento_pct = desc_6h
    elif horas >= 2:
        descuento_pct = desc_3h

    subtotal_bruto = precio_hora * horas
    descuento_val  = subtotal_bruto * (descuento_pct / 100)
    subtotal       = subtotal_bruto - descuento_val
    iva            = subtotal * IVA_PCT
    total          = subtotal + iva

    return {
        "precio_hora":     precio_hora,
        "horas":           horas,
        "tarifa":          tarifa_nombre,
        "descuento_pct":   descuento_pct,
        "descuento_val":   descuento_val,
        "subtotal":        subtotal,
        "iva":             iva,
        "total":           total,
    }


def get_cubiculos() -> list:
    con = get_db()
    cur = con.cursor()
    cur.execute("""SELECT c.id, c.numero, c.nombre, c.estado, c.reserva_activa_id,
                          c.hora_disponible, c.precio_hora_base, c.wifi_ssid, c.wifi_password,
                          c.servicios,
                          r.hora_fin_programada, r.hora_inicio
                   FROM cubiculos c
                   LEFT JOIN reservas r ON c.reserva_activa_id = r.id
                   ORDER BY c.numero""")
    rows = cur.fetchall()
    con.close()
    result = []
    now = ahora_col()
    for row in rows:
        cub = {
            "id": row[0], "numero": row[1], "nombre": row[2],
            "estado": row[3], "reserva_activa_id": row[4],
            "hora_disponible": row[5], "precio_hora_base": row[6],
            "wifi_ssid": row[7], "wifi_password": row[8],
            "servicios": json.loads(row[9]) if row[9] else [],
            "hora_fin": row[10], "hora_inicio": row[11],
            "minutos_restantes": None,
        }
        if row[10] and cub["estado"] == "ocupado":
            try:
                fin = datetime.fromisoformat(row[10])
                if fin.tzinfo is None:
                    fin = TZ_COL.localize(fin)
                diff = (fin - now).total_seconds() / 60
                cub["minutos_restantes"] = max(0, int(diff))
                if 0 < diff <= 15:
                    cub["estado"] = "por_liberar"
            except Exception:
                pass
        result.append(cub)
    return result


def get_cubiculos_libres() -> list:
    return [c for c in get_cubiculos() if c["estado"] == "libre"]


def generar_numero_reserva() -> str:
    now = ahora_col()
    con = get_db()
    cur = con.cursor()
    prefix = f"CR-{now.strftime('%Y%m%d')}-"
    cur.execute("SELECT COUNT(*) FROM reservas WHERE numero_reserva LIKE ?", (prefix + "%",))
    n = cur.fetchone()[0] + 1
    con.close()
    return f"{prefix}{n:04d}"


def generar_numero_factura() -> str:
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT valor FROM configuracion_pagos WHERE clave='factura_contador'")
    row = cur.fetchone()
    n = int(row[0]) + 1 if row else 1
    cur.execute("INSERT OR REPLACE INTO configuracion_pagos VALUES ('factura_contador',?)", (str(n),))
    prefix = get_config("factura_prefijo", "FACT")
    year = ahora_col().year
    con.commit()
    con.close()
    return f"{prefix}-{year}-{n:04d}"


def generar_codigo_acceso() -> str:
    import random
    return str(random.randint(1000, 9999))


def activar_cubiculo(cubiculo_id: int, reserva_id: int, hora_fin: str):
    con = get_db()
    con.execute("""UPDATE cubiculos SET estado='ocupado',
                   reserva_activa_id=?, hora_disponible=? WHERE id=?""",
                (reserva_id, hora_fin, cubiculo_id))
    con.commit()
    con.close()


def liberar_cubiculo(cubiculo_id: int):
    """Libera el cubículo en SQLite y encola actualización en Google Sheets."""
    con = get_db()
    # Obtener número de reserva activa antes de liberar
    row = con.execute("""
        SELECT cu.numero, r.numero_reserva
        FROM cubiculos cu
        LEFT JOIN reservas r ON cu.reserva_activa_id = r.id
        WHERE cu.id=?
    """, (cubiculo_id,)).fetchone()
    num_cub     = row[0] if row else ""
    num_reserva = row[1] if row else ""

    hora_fin_real = ahora_col().isoformat()
    con.execute("""UPDATE cubiculos SET estado='libre',
                   reserva_activa_id=NULL, hora_disponible=NULL WHERE id=?""",
                (cubiculo_id,))
    # Marcar hora_fin_real en la reserva
    if num_reserva:
        con.execute("UPDATE reservas SET hora_fin_real=? WHERE numero_reserva=?",
                    (hora_fin_real, num_reserva))
    con.commit()
    con.close()

    # Sync a Google Sheets — escritura directa (encolar_sync es stub)
    _, sh = get_active_client()
    if sh:
        if num_reserva:
            # Actualizar hora_fin_real en hoja Reservas
            try:
                ws = _gs_get_or_create_ws(sh, "Reservas")
                vals = ws.get_all_values()
                if vals:
                    hdr = vals[0]
                    if "Hora_Fin_Real" in hdr and "Numero_Reserva" in hdr:
                        col_res = hdr.index("Numero_Reserva")
                        col_fin = hdr.index("Hora_Fin_Real")
                        for i, r in enumerate(vals[1:], start=2):
                            if len(r) > col_res and str(r[col_res]) == str(num_reserva):
                                ws.update_cell(i, col_fin + 1, hora_fin_real)
                                break
            except Exception:
                pass
        gs_sync_cubiculos(sh)
        gs_sync_dashboard(sh)
        # Refrescar Reservas y Pagos con hora_fin_real y estado actualizados
        try:
            con_s = get_db()
            rows_r = con_s.execute("""
                SELECT r.id, r.numero_reserva, r.creado_en,
                       cu.numero,
                       cl.nombre, cl.numero_documento, cl.telefono, cl.email,
                       r.horas_contratadas, r.hora_inicio, r.hora_fin_programada, r.hora_fin_real,
                       r.precio_hora, r.subtotal, r.iva, r.total,
                       r.metodo_pago, r.estado_pago, r.codigo_acceso,
                       cu.wifi_ssid, cu.wifi_password,
                       f.numero, r.referencia_pago, 'sistema', r.notas
                FROM reservas r
                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                LEFT JOIN clientes cl ON r.cliente_id = cl.id
                LEFT JOIN facturas f ON r.factura_id = f.id
                ORDER BY r.id
            """).fetchall()
            rows_p = con_s.execute("""
                SELECT p.id, p.reserva_id, r.numero_reserva, p.fecha_pago,
                       p.monto, p.metodo, p.referencia_externa,
                       p.estado, p.confirmado_por, p.notas
                FROM pagos p
                LEFT JOIN reservas r ON p.reserva_id = r.id
                ORDER BY p.id
            """).fetchall()
            con_s.close()
            ws_res = _gs_get_or_create_ws(sh, "Reservas")
            ws_res.clear()
            _gs_update_range(ws_res, "A1", [DRIVE_SHEETS["Reservas"]] +
                             [[str(v) if v is not None else "" for v in r] for r in rows_r])
            ws_pag = _gs_get_or_create_ws(sh, "Pagos")
            ws_pag.clear()
            _gs_update_range(ws_pag, "A1", [DRIVE_SHEETS["Pagos"]] +
                             [[str(v) if v is not None else "" for v in r] for r in rows_p])
        except Exception as _e:
            st.warning(f"⚠️ Error sync Reservas/Pagos al liberar: {_e}")


def fmt_cop(valor: float) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def fmt_tiempo(minutos: int) -> str:
    if minutos is None:
        return "--:--"
    h, m = divmod(abs(int(minutos)), 60)
    return f"{h:02d}:{m:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DE QR
# ══════════════════════════════════════════════════════════════════════════════

def generar_qr_b64(data: str, fill: str = "#00d4ff", back: str = "#050b1a") -> Optional[str]:
    if not QR_AVAILABLE:
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10, border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color=fill, back_color=back)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def qr_data_para_metodo(metodo: str, monto: int, referencia: str) -> str:
    nequi  = get_config("nequi_numero",    NEQUI_NUM).replace(" ", "")
    davip  = get_config("daviplata_numero",DAVIPLATA_NUM).replace(" ", "")
    mp     = get_config("mp_link",         MP_LINK)
    banco  = get_config("cuenta_bancaria", CUENTA_BANCO)
    nit    = get_config("negocio_nit",     NIT).replace(".", "").replace("-", "")

    dispatch = {
        "Nequi":        f"nequi://transfer?phone={nequi}&amount={monto}&description={referencia}",
        "Daviplata":    f"daviplata://pay?to={davip}&amount={monto}&ref={referencia}",
        "MercadoPago":  f"{mp}?external_reference={referencia}",
        "PSE":          f"https://pse.redeban.com/RedirectionService/Rest/10/GetToken?referencia={referencia}&valor={monto}",
        "Transferencia":f"{banco}|{nit}|{monto}|{referencia}",
    }
    return dispatch.get(metodo, f"PAGO|{NEGOCIO}|{monto}|{referencia}|COP")


def mostrar_qr(metodo: str, monto: int, referencia: str, size: int = 300):
    """
    Genera QR fresco en cada render (timestamp como salt = siempre actualizado).
    Incluye countdown de validez del QR actualizado por JS en tiempo real.
    El QR de Nequi/Daviplata incluye monto y referencia exactos del pago actual.
    """
    # Salt de tiempo → QR único en cada render; evita caché del browser
    ts     = ahora_col().strftime("%Y%m%d%H%M%S")
    # Referencia enriquecida con timestamp para garantizar unicidad
    ref_qr = f"{referencia}-{ts}"
    data   = qr_data_para_metodo(metodo, monto, ref_qr)

    # Tiempo de expiración del QR: 5 minutos desde ahora
    exp_dt  = ahora_col() + timedelta(minutes=5)
    exp_iso = exp_dt.isoformat()

    b64 = generar_qr_b64(data)
    if b64:
        st.markdown(f"""
        <div class="qr-container" id="qr-{metodo.lower()}-{ts}">
            <img src="{b64}" width="{size}"
                 style="image-rendering:pixelated;border-radius:8px"
                 title="QR {metodo} — {fmt_cop(monto)} COP | Ref: {referencia}"/>
            <div style="font-family:'Inconsolata',monospace;font-size:12px;
                        color:var(--text-dim);margin-top:6px;word-break:break-all;
                        text-align:center;max-width:{size}px">{referencia}</div>
            <div class="jjgt-qr-countdown" data-exp="{exp_iso}"
                 style="font-size:12px;font-weight:700;margin-top:4px">
                🔒 QR válido por 300s
            </div>
            <div class="qr-instruccion">Escanea con tu app de pagos</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"📲 **Referencia de pago:** `{referencia}`\n\n**Monto:** {fmt_cop(monto)}")
    return data, b64


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN CON FACTURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN CON FACTURACIÓN — orden: Sheets primero, SQLite después
# ══════════════════════════════════════════════════════════════════════════════

def registrar_en_facturacion(reserva: dict, cliente: dict) -> tuple:
    """
    ORDEN: 1) Google Sheets  2) SQLite
    Retorna (numero_factura, factura_id).
    """
    now  = ahora_col()
    numf = generar_numero_factura()

    descripcion_item = (f"Espacio de descanso {reserva['cubiculo_num']} · "
                        f"WiFi · Baño · Carga · {reserva['horas']}h")
    base_gravable = float(reserva["subtotal"]) - float(reserva.get("descuento_val", 0))

    # ── PASO 1 → PASO 2: SQLite primero, luego Sheets con IDs reales ──────────
    con = get_db()
    cur = con.cursor()

    row_cli = cur.execute("SELECT id FROM clientes WHERE numero_documento=?",
                          (cliente.get("numero_documento", ""),)).fetchone()
    if row_cli:
        cliente_id = row_cli[0]
        es_nuevo   = False
    else:
        cur.execute("""INSERT INTO clientes
            (nombre,tipo_documento,numero_documento,telefono,email,
             razon_social,nit_empresa,tipo_persona,creado_en)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (cliente["nombre"], cliente.get("tipo_doc", "CC"),
             cliente.get("numero_documento", ""), cliente.get("telefono", ""),
             cliente.get("email", ""), cliente.get("razon_social", ""),
             cliente.get("nit_empresa", ""),
             "Jurídica" if cliente.get("razon_social") else "Natural",
             now.isoformat()))
        cliente_id = cur.lastrowid
        es_nuevo   = True

    cur.execute("""INSERT INTO facturas
        (numero,tipo,fecha_emision,fecha_vencimiento,cliente_id,
         subtotal,descuento,iva,retenciones,total,estado,moneda,notas,
         metodo_pago,creado_en,actualizado_en)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numf, "Factura de Venta",
         now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"),
         cliente_id,
         reserva["subtotal"], reserva.get("descuento_val", 0),
         reserva["iva"], 0, reserva["total"],
         "pagada", "COP",
         f"Cubículo {reserva['cubiculo_num']} · {reserva['horas']}h · WiFi+Baño+Carga",
         reserva["metodo_pago"], now.isoformat(), now.isoformat()))
    factura_id = cur.lastrowid

    cur.execute("""INSERT INTO factura_items
        (factura_id,codigo,descripcion,cantidad,unidad,precio_unitario,iva_pct,subtotal)
        VALUES (?,?,?,?,?,?,?,?)""",
        (factura_id, "DESCANSO-H", descripcion_item,
         reserva["horas"], "hora",
         reserva["precio_hora"], 19.0, reserva["subtotal"]))
    con.commit()
    con.close()

    # ── Sheets con IDs reales post-commit ─────────────────────────────────────
    _, sh = get_active_client()
    if sh:
        # Recuperar numero_documento del cliente para upsert key
        num_doc = cliente.get("numero_documento", "")
        gs_escribir_cliente(sh, {
            "id":               cliente_id,
            "nombre":           cliente["nombre"],
            "tipo_documento":   cliente.get("tipo_doc", "CC"),
            "numero_documento": num_doc,
            "telefono":         cliente.get("telefono", ""),
            "email":            cliente.get("email", ""),
            "ciudad":           cliente.get("ciudad", ""),
            "regimen":          cliente.get("regimen", "Simplificado"),
            "tipo_persona":     "Jurídica" if cliente.get("razon_social") else "Natural",
            "razon_social":     cliente.get("razon_social", ""),
            "nit_empresa":      cliente.get("nit_empresa", ""),
            "activo":           "1",
            "creado_en":        now.isoformat(),
        })
        gs_escribir_factura(sh, {
            "id":               factura_id,
            "numero":           numf,
            "tipo":             "Factura de Venta",
            "fecha_emision":    now.strftime("%Y-%m-%d"),
            "fecha_vencimiento":now.strftime("%Y-%m-%d"),
            "cliente_nombre":   cliente["nombre"],
            "cliente_doc":      num_doc,
            "cliente_email":    cliente.get("email", ""),
            "razon_social":     cliente.get("razon_social", ""),
            "nit_empresa":      cliente.get("nit_empresa", ""),
            "descripcion":      descripcion_item,
            "subtotal":         reserva["subtotal"],
            "descuento":        reserva.get("descuento_val", 0),
            "iva":              reserva["iva"],
            "retenciones":      "0",
            "total":            reserva["total"],
            "metodo_pago":      reserva["metodo_pago"],
            "estado":           "pagada",
            "moneda":           "COP",
            "num_reserva":      "",          # aún no existe; sync_completa lo llenará
            "cubiculo":         reserva["cubiculo_num"],
            "creado_en":        now.isoformat(),
            "actualizado_en":   now.isoformat(),
        })
        gs_sync_factura_items(sh)
    else:
        st.warning("⚠️ Sin conexión a Google Sheets — datos guardados solo en SQLite")

    return numf, factura_id


def crear_reserva_completa(cubiculo: dict, cliente: dict, calc: dict, metodo: str) -> dict:
    """
    Crea reserva, pago, factura y activa el cubículo.
    Incluye verificación atómica de duplicado dentro de la transacción SQLite.
    """
    # Guard anti-duplicado en session_state (mismo objeto voucher)
    if (st.session_state.get("voucher") and
            st.session_state.get("pago_confirmado") and
            st.session_state["voucher"].get("cubiculo") == cubiculo["numero"]):
        return st.session_state["voucher"]

    now      = ahora_col()
    hoy_str  = now.strftime("%Y-%m-%d")
    num_doc  = cliente.get("numero_documento", "")

    con = get_db()
    cur = con.cursor()

    # ── Verificación atómica 1: cubículo sigue libre ──────────────────────────
    estado_actual = cur.execute(
        "SELECT estado FROM cubiculos WHERE id=?", (cubiculo["id"],)).fetchone()
    if estado_actual and estado_actual[0] != "libre":
        con.close()
        raise Exception(f"El cubículo {cubiculo['numero']} ya no está disponible.")

    # ── Verificación atómica 2: cliente sin reserva activa hoy ───────────────
    if num_doc:
        dup = cur.execute("""
            SELECT r.numero_reserva, cu.numero
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
            WHERE c.numero_documento = ?
              AND r.estado_pago = 'confirmado'
              AND SUBSTR(r.hora_inicio, 1, 10) = ?
              AND (r.hora_fin_real IS NULL OR r.hora_fin_real = '')
            LIMIT 1
        """, (num_doc, hoy_str)).fetchone()
        if dup:
            con.close()
            raise Exception(
                f"El cliente con documento {num_doc} ya tiene la reserva activa "
                f"{dup[0]} en el cubículo {dup[1]}. "
                f"No se puede crear una nueva reserva hasta que termine la actual."
            )

    con.close()

    hora_fin = now + timedelta(hours=calc["horas"])
    num_res  = generar_numero_reserva()
    codigo   = generar_codigo_acceso()

    reserva_data = {
        "cubiculo_num":  cubiculo["numero"],
        "horas":         calc["horas"],
        "precio_hora":   calc["precio_hora"],
        "subtotal":      calc["subtotal"],
        "descuento_val": calc["descuento_val"],
        "iva":           calc["iva"],
        "total":         calc["total"],
        "metodo_pago":   metodo,
    }

    # registrar_en_facturacion ya hace Sheets primero, SQLite después
    num_fact, factura_id = registrar_en_facturacion(reserva_data, cliente)

    # Recuperar cliente_id de SQLite
    con = get_db()
    cur = con.cursor()
    row = cur.execute("SELECT id FROM clientes WHERE numero_documento=?",
                      (cliente.get("numero_documento", ""),)).fetchone()
    cliente_id = row[0] if row else None

    # ── PASO 1: Google Sheets — Reserva + Pago ───────────────────────────────
    _, sh = get_active_client()

    # ── PASO 2: SQLite — Reserva + Pago ──────────────────────────────────────
    cur.execute("""INSERT INTO reservas
        (numero_reserva,cubiculo_id,cliente_id,factura_id,hora_inicio,hora_fin_programada,
         horas_contratadas,precio_hora,subtotal,iva,total,metodo_pago,estado_pago,
         codigo_acceso,creado_en)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (num_res, cubiculo["id"], cliente_id, factura_id,
         now.isoformat(), hora_fin.isoformat(),
         calc["horas"], calc["precio_hora"],
         calc["subtotal"], calc["iva"], calc["total"],
         metodo, "confirmado", codigo, now.isoformat()))
    reserva_id = cur.lastrowid

    cur.execute("""INSERT INTO pagos (reserva_id,monto,metodo,estado,fecha_pago)
                   VALUES (?,?,?,'confirmado',?)""",
                (reserva_id, calc["total"], metodo, now.isoformat()))
    pago_id = cur.lastrowid
    con.commit()
    con.close()

    # ── Escribir en Sheets con IDs reales (una sola vez, post-commit) ─────────
    if sh:
        gs_escribir_reserva(sh, {
            "id":              reserva_id,
            "numero_reserva":  num_res,
            "creado_en":       now.isoformat(),
            "cubiculo_num":    cubiculo["numero"],
            "cliente_nombre":  cliente["nombre"],
            "cliente_doc":     cliente.get("numero_documento", ""),
            "cliente_tel":     cliente.get("telefono", ""),
            "cliente_email":   cliente.get("email", ""),
            "horas":           calc["horas"],
            "hora_inicio":     now.isoformat(),
            "hora_fin_prog":   hora_fin.isoformat(),
            "hora_fin_real":   "",
            "precio_hora":     calc["precio_hora"],
            "subtotal":        calc["subtotal"],
            "iva":             calc["iva"],
            "total":           calc["total"],
            "metodo_pago":     metodo,
            "estado_pago":     "confirmado",
            "codigo_acceso":   codigo,
            "wifi_ssid":       cubiculo.get("wifi_ssid", ""),
            "wifi_pass":       cubiculo.get("wifi_password", ""),
            "num_factura":     num_fact,
            "referencia_pago": "",
            "operador":        "sistema",
            "notas":           "",
        })
        gs_escribir_pago(sh, {
            "id":                 pago_id,
            "reserva_id":         reserva_id,
            "num_reserva":        num_res,
            "fecha_pago":         now.isoformat(),
            "monto":              calc["total"],
            "metodo":             metodo,
            "referencia_externa": "",
            "estado":             "confirmado",
            "confirmado_por":     "sistema",
            "notas":              "",
        })
        gs_escribir_log(sh, "nueva_reserva", num_res, cubiculo["numero"],
                        "sistema",
                        f"Reserva {num_res} | Factura {num_fact} | "
                        f"{metodo} | ${calc['total']:,.0f}")
        gs_sync_cubiculos(sh)
        gs_sync_dashboard(sh)
        gs_sync_factura_items(sh)

    activar_cubiculo(cubiculo["id"], reserva_id, hora_fin.isoformat())

    return {
        "numero_reserva": num_res,
        "numero_factura": num_fact,
        "cubiculo":       cubiculo["numero"],
        "codigo_acceso":  codigo,
        "wifi_ssid":      cubiculo["wifi_ssid"],
        "wifi_password":  cubiculo["wifi_password"],
        "hora_inicio":    now.strftime("%H:%M"),
        "hora_fin":       hora_fin.strftime("%H:%M"),
        "horas":          calc["horas"],
        "metodo_pago":    metodo,
        "subtotal":       calc["subtotal"],
        "iva":            calc["iva"],
        "total":          calc["total"],
        "cliente_nombre": cliente["nombre"],
    }




# ══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DE PDF (ticket térmico 80mm) (ticket térmico 80mm)
# ══════════════════════════════════════════════════════════════════════════════

def generar_ticket_pdf(voucher: dict) -> Optional[bytes]:
    if not REPORTLAB_AVAILABLE:
        return None
    buf = io.BytesIO()
    W   = 80 * mm
    doc = SimpleDocTemplate(buf, pagesize=(W, 200*mm),
                            rightMargin=4*mm, leftMargin=4*mm,
                            topMargin=4*mm, bottomMargin=4*mm)
    styles = getSampleStyleSheet()
    c_style = ParagraphStyle("Center", alignment=TA_CENTER,
                              fontName="Helvetica", fontSize=8, leading=10)
    h_style = ParagraphStyle("Header", alignment=TA_CENTER,
                              fontName="Helvetica-Bold", fontSize=11, leading=13)
    big_style= ParagraphStyle("Big", alignment=TA_CENTER,
                               fontName="Helvetica-Bold", fontSize=22, leading=26)
    elems = []

    def hr(): return HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceAfter=3, spaceBefore=3)
    def p(text, style=c_style): return Paragraph(text, style)

    elems += [
        p(NEGOCIO, h_style),
        p(TAGLINE, c_style),
        p(DIRECCION, c_style),
        p(f"Tel: {TELEFONO} · {NIT}", c_style),
        hr(),
        p(f"Reserva: <b>{voucher['numero_reserva']}</b>", c_style),
        p(f"Fecha: {ahora_col().strftime('%d/%m/%Y %H:%M')}", c_style),
        hr(),
        Spacer(1, 3),
        p(f"CUBÍCULO: <b>{voucher['cubiculo']}</b>", h_style),
        p(f"Entrada: {voucher['hora_inicio']}  →  Salida: {voucher['hora_fin']}", c_style),
        p(f"Tiempo: <b>{voucher['horas']}h</b>", c_style),
        hr(),
        p("SERVICIOS INCLUIDOS:", c_style),
        p("✓ Baño  ✓ WiFi  ✓ Carga USB/110V", c_style),
        hr(),
        p("CÓDIGO DE ACCESO:", c_style),
        Spacer(1, 4),
        p(f"<b>{voucher['codigo_acceso']}</b>", big_style),
        Spacer(1, 4),
        p(f"WiFi: <b>{voucher['wifi_ssid']}</b>", c_style),
        p(f"Clave WiFi: <b>{voucher['wifi_password']}</b>", c_style),
        hr(),
        p(f"Subtotal:    {fmt_cop(voucher['subtotal'])}", c_style),
        p(f"IVA (19%):   {fmt_cop(voucher['iva'])}", c_style),
    ]

    # Total en tabla destacada
    tabla_total = Table([[f"TOTAL: {fmt_cop(voucher['total'])} COP"]],
                        colWidths=[W - 8*mm])
    tabla_total.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#0a3d62")),
        ("TEXTCOLOR",     (0,0), (-1,-1), colors.HexColor("#00d4ff")),
        ("FONTNAME",      (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 13),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [4,4,4,4]),
    ]))
    elems.append(Spacer(1, 4))
    elems.append(tabla_total)
    elems += [
        Spacer(1, 4),
        p(f"Método: <b>{voucher['metodo_pago']}</b>", c_style),
        p(f"Factura N°: <b>{voucher['numero_factura']}</b>", c_style),
        hr(),
    ]

    # QR
    qr_data = qr_data_para_metodo("Nequi", 0, voucher["numero_reserva"])
    b64_qr  = generar_qr_b64(qr_data, fill="#000000", back="#ffffff")
    if b64_qr and QR_AVAILABLE:
        try:
            qr_bytes = base64.b64decode(b64_qr.split(",")[1])
            img_buf  = io.BytesIO(qr_bytes)
            from reportlab.platypus import Image as RLImage
            rl_img = RLImage(img_buf, width=30*mm, height=30*mm)
            elems.append(rl_img)
        except Exception:
            pass

    elems += [
        hr(),
        p("¡Gracias por tu visita!", h_style),
        p("¡Buen viaje!", c_style),
        p(f"{NEGOCIO} · Terminal de Transportes", c_style),
    ]

    doc.build(elems)
    return buf.getvalue()


def voucher_html(v: dict) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
body {{font-family:monospace;max-width:320px;margin:20px auto;
      background:#050b1a;color:#e2e8f0;padding:20px;border:2px solid #00d4ff;border-radius:12px;}}
h1{{color:#00d4ff;text-align:center;font-size:18px;}}
.cod{{font-size:56px;font-weight:700;text-align:center;color:#00ff88;
     letter-spacing:10px;text-shadow:0 0 20px rgba(0,255,136,0.6);margin:16px 0;}}
.row{{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.1);}}
.total{{font-size:20px;font-weight:700;color:#00d4ff;text-align:right;margin-top:12px;}}
</style></head><body>
<h1>💤 {NEGOCIO}</h1>
<p style="text-align:center;color:#94a3b8;font-size:12px">{TAGLINE}</p>
<hr style="border-color:rgba(0,212,255,0.3)">
<div class="row"><span>Reserva</span><b>{v['numero_reserva']}</b></div>
<div class="row"><span>Cubículo</span><b>{v['cubiculo']}</b></div>
<div class="row"><span>Entrada</span><b>{v['hora_inicio']}</b></div>
<div class="row"><span>Salida</span><b>{v['hora_fin']}</b></div>
<div class="row"><span>Tiempo</span><b>{v['horas']}h</b></div>
<div class="row"><span>WiFi</span><b>{v['wifi_ssid']}</b></div>
<div class="row"><span>Clave WiFi</span><b>{v['wifi_password']}</b></div>
<hr style="border-color:rgba(0,212,255,0.3)">
<p style="text-align:center;color:#94a3b8;font-size:12px">CÓDIGO DE ACCESO</p>
<div class="cod">{v['codigo_acceso']}</div>
<hr style="border-color:rgba(0,212,255,0.3)">
<div class="row"><span>✓ Baño</span><span>✓ WiFi</span><span>✓ Carga</span></div>
<div class="row"><span>Subtotal</span><span>{fmt_cop(v['subtotal'])}</span></div>
<div class="row"><span>IVA 19%</span><span>{fmt_cop(v['iva'])}</span></div>
<div class="total">TOTAL: {fmt_cop(v['total'])} COP</div>
<div class="row"><span>Pago</span><b>{v['metodo_pago']}</b></div>
<div class="row"><span>Factura</span><b>{v['numero_factura']}</b></div>
<hr style="border-color:rgba(0,212,255,0.3)">
<p style="text-align:center;color:#94a3b8;font-size:11px">¡Gracias por tu visita! · ¡Buen viaje!</p>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

def init_state():
    defaults = {
        "pantalla":              "operador_login",  # La app SIEMPRE inicia en login de operador
        "cubiculo_sel":          None,
        "horas_sel":             1.0,
        "calc":                  None,
        "cliente":               {},
        "metodo_pago":           None,
        "voucher":               None,
        "pago_confirmado":       False,
        "operador_ok":           False,
        "operador_info":         {},               # Datos del operador activo
        "pin_intentos":          0,
        "modulo_op":             "dashboard",
        "_backup_fecha":         "",
        "_procesando_reserva":   False,           # Guardia anti-doble-clic en confirmación
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _auto_backup_diario():
    """
    Genera backup al inicio del proceso si no se hizo hoy.
    Mantiene compatibilidad — el backup principal ahora ocurre al cerrar turno.
    """
    today_str = ahora_col().strftime("%Y-%m-%d")
    if st.session_state.get("_backup_fecha") == today_str:
        return
    try:
        os.makedirs("backups", exist_ok=True)
        data, fname, _ = generar_backup_diario()
        backup_path = os.path.join("backups", fname)
        if not os.path.exists(backup_path):
            with open(backup_path, "wb") as bf:
                bf.write(data)
        st.session_state["_backup_fecha"] = today_str
    except Exception:
        pass


def _backup_cierre_turno(operador_info: dict):
    """
    Genera y guarda un backup al momento de cerrar el turno del operador.
    El archivo queda en backups/cierre_<turno>_<operador>_<fecha_hora>.xlsx
    Solo se ejecuta en entorno local (en Cloud /tmp no persiste entre sesiones).
    """
    if _IS_CLOUD:
        return
    try:
        os.makedirs("backups", exist_ok=True)
        ahora  = ahora_col()
        turno  = operador_info.get("turno", "turno")
        nombre = operador_info.get("nombre", "op").replace(" ", "_").lower()
        ts_str = ahora.strftime("%Y-%m-%d_%H%M")
        fname  = f"cierre_{turno}_{nombre}_{ts_str}.xlsx"
        backup_path = os.path.join("backups", fname)
        data, _, _ = generar_backup_diario()
        with open(backup_path, "wb") as bf:
            bf.write(data)
        # Registrar en Google Sheets si la conexion esta activa
        try:
            _, sh_cierre = get_active_client()
            if sh_cierre:
                gs_sync_dashboard(sh_cierre)
            sheets_append_row("Log_Operaciones", [
                ahora.isoformat(), "cierre_turno", "", "",
                operador_info.get("nombre", ""),
                f"Backup cierre de turno '{turno}' — {fname}",
                "", "", "", "exito", ""
            ])
        except Exception:
            pass
    except Exception:
        pass


init_state()


def ir_a(pantalla: str):
    # Al navegar fuera de confirmación, liberar el lock de procesamiento
    if pantalla != "confirmacion":
        st.session_state["_procesando_reserva"] = False
    st.session_state.pantalla = pantalla
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENTES REUTILIZABLES
# ══════════════════════════════════════════════════════════════════════════════

def render_header(subtitulo: str = ""):
    st.markdown(f"""
    <div class="main-header">
      <div class="main-logo">💤 {NEGOCIO}</div>
      <div class="main-tagline">{subtitulo or TAGLINE}</div>
    </div>""", unsafe_allow_html=True)


def render_stepper(paso_actual: int):
    pasos = ["Cubículo", "Datos", "Pago", "Confirmación", "Voucher"]
    html  = '<div class="stepper">'
    for i, nombre in enumerate(pasos):
        cls = "active" if i == paso_actual else ("done" if i < paso_actual else "")
        ico = ["🛏️","👤","💳","✅","🎫"][i]
        html += f'<div class="step {cls}">{ico} {nombre}</div>'
        if i < len(pasos)-1:
            html += '<div class="step-arrow"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_reloj():
    """
    Reloj con hora y fecha actualizados en tiempo real por JavaScript.
    Los elementos .jjgt-clock-hms y .jjgt-clock-fecha son actualizados cada segundo
    por el script inyectado en inject_live_clock() — sin recarga del servidor.
    """
    now = ahora_col()
    st.markdown(f"""
    <div style="text-align:center;margin-bottom:12px">
      <div class="clock-big jjgt-clock-hms">{now.strftime('%H:%M:%S')}</div>
      <div class="clock-label jjgt-clock-fecha">{now.strftime('%A, %d de %B de %Y').upper()}</div>
    </div>
    """, unsafe_allow_html=True)


def render_cubiculo_card(cub: dict, seleccionado: bool = False) -> bool:
    """
    Renderiza tarjeta de cubículo con timer en vivo (actualizado por JS cada segundo).
    Retorna True si fue clickeado.
    """
    estado = cub["estado"]
    info   = ESTADOS_CUBICULO.get(estado, ESTADOS_CUBICULO["libre"])
    libre  = estado == "libre"
    cls    = f"cubiculo-{estado.replace('_','-')}"
    if seleccionado:
        cls += " cubiculo-selected"

    # Timer HTML: usa clase .jjgt-timer con data-fin para actualización JS en tiempo real
    timer_html = ""
    if cub.get("hora_fin") and not libre:
        mins  = cub.get("minutos_restantes", 999)
        color = "#ff4757" if mins <= 5 else ("#ffd32a" if mins <= 15 else "#00ff88")
        timer_html = (
            f'<div class="timer-display jjgt-timer" ' 
            f'data-fin="{cub["hora_fin"]}" data-key="cub-{cub["id"]}" ' 
            f'style="color:{color}">⏱ {fmt_tiempo(mins)}</div>'
        )
    elif cub.get("minutos_restantes") is not None and not libre:
        mins = cub["minutos_restantes"]
        color = "#ffd32a" if mins <= 15 else "#ff4757"
        timer_html = f'<div class="timer-display" style="color:{color}">⏱ {fmt_tiempo(mins)}</div>'

    st.markdown(f"""
    <div class="cubiculo-card {cls}" style="background:{info['bg']};border-color:{info['color']}40">
      <div class="cubiculo-num" style="color:{info['color']}">{cub['numero']}</div>
      <div class="estado-badge" style="background:{info['color']}22;color:{info['color']};
           border:1px solid {info['color']}55">{info['label']}</div>
      {timer_html}
      <div class="servicios-icons">🚿 🌐 🔌</div>
    </div>
    """, unsafe_allow_html=True)

    if libre:
        label = f"✅ Seleccionar {cub['numero']}"
        return st.button(label, key=f"btn_cub_{cub['id']}", use_container_width=True)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 0 — BIENVENIDA
# ══════════════════════════════════════════════════════════════════════════════

def show_bienvenida():
    # Seguridad: si no hay operador autenticado, redirigir al login
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header()
    inject_live_clock()
    render_reloj()

    # ── Auto-rerun del servidor cada 60s para refrescar estado (primer run excluido) ─
    now_ts = int(time.time())
    last_rerun_b = st.session_state.get("_bienvenida_last_rerun", 0)
    if last_rerun_b == 0:
        # Primera carga: solo registrar timestamp, no rerunear
        st.session_state["_bienvenida_last_rerun"] = now_ts
    elif now_ts - last_rerun_b >= 60:
        st.session_state["_bienvenida_last_rerun"] = now_ts
        st.rerun()

    # ── Auto-liberar cubículos vencidos en background ─────────────────────────
    cubiculos_raw = get_cubiculos()
    alarma_vencidos = []
    for cub in cubiculos_raw:
        if cub["estado"] in ("ocupado", "por_liberar"):
            mins = cub.get("minutos_restantes")
            if mins is not None and mins <= 0:
                liberar_cubiculo(cub["id"])
                alarma_vencidos.append(cub["numero"])
    if alarma_vencidos:
        st.markdown("""
        <script>
        (function(){
          try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            function beep(freq, start, dur) {
              var o = ctx.createOscillator();
              var g = ctx.createGain();
              o.connect(g); g.connect(ctx.destination);
              o.frequency.value = freq; o.type = 'square';
              g.gain.setValueAtTime(0.3, ctx.currentTime + start);
              g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
              o.start(ctx.currentTime + start);
              o.stop(ctx.currentTime + start + dur + 0.05);
            }
            for(var i=0; i<3; i++){beep(880,i*0.4,0.3); beep(660,i*0.4+0.15,0.15);}
          } catch(e){}
        })();
        </script>
        """, unsafe_allow_html=True)

    cubiculos  = get_cubiculos()  # Re-consultar después de liberaciones
    libres     = sum(1 for c in cubiculos if c["estado"] == "libre")
    total      = len(cubiculos)
    tarifa_act = "Madrugada" if 0 <= ahora_col().hour < 6 else "Estándar"
    precio_min = 10000 if tarifa_act == "Madrugada" else 15000

    # Disponibilidad
    color_disp = "#00ff88" if libres > 3 else ("#ffd32a" if libres > 0 else "#ff4757")
    icono_disp = "🟢" if libres > 3 else ("🟡" if libres > 0 else "🔴")
    st.markdown(f"""
    <div style="text-align:center;margin:12px 0 24px;
                font-size:22px;font-weight:700;color:{color_disp}">
      {icono_disp} {libres} de {total} cubículos disponibles ahora
    </div>
    """, unsafe_allow_html=True)

    # Tarifas
    hora_col = ahora_col().hour
    tarifa_badge = ""
    if 0 <= hora_col < 6:
        tarifa_badge = '<span style="background:rgba(0,212,255,0.2);color:#00d4ff;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:700;letter-spacing:1px">🌙 TARIFA MADRUGADA ACTIVA</span>'

    st.markdown(f"""
    <div style="text-align:center;margin-bottom:24px">
      <div style="font-size:18px;color:#94a3b8;margin-bottom:8px">
        Desde <b style="color:#00ff88">{fmt_cop(precio_min)}/hora</b> &nbsp;·&nbsp;
        <span>🚿 Baño</span> &nbsp;·&nbsp;
        <span>🌐 WiFi</span> &nbsp;·&nbsp;
        <span>🔌 Carga</span>
      </div>
      {tarifa_badge}
    </div>
    """, unsafe_allow_html=True)

    # Botón principal + info del operador activo
    op_bienvenida = st.session_state.get("operador_info", {})
    op_nombre_b   = op_bienvenida.get("nombre", "")
    if op_nombre_b:
        st.markdown(f"""
        <div style="text-align:center;font-size:13px;color:#94a3b8;margin-bottom:8px">
          👤 Atendido por: <b style="color:#00d4ff">{op_nombre_b}</b>
          · Turno {op_bienvenida.get("turno","").capitalize()}
        </div>
        """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        if libres > 0:
            if st.button("🛏️  RESERVAR MI ESPACIO", type="primary", use_container_width=True):
                ir_a("seleccion")
        else:
            st.markdown('<div class="alerta-roja">❌ No hay cubículos disponibles en este momento.<br>Por favor espera o consulta al operador.</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Mini grid de estado (timers actualizados por JS cada segundo)
    st.markdown("---")
    st.markdown("#### Estado en tiempo real")
    cols = st.columns(6)
    for i, cub in enumerate(cubiculos):
        with cols[i % 6]:
            estado   = cub["estado"]
            info     = ESTADOS_CUBICULO.get(estado, ESTADOS_CUBICULO["libre"])
            hora_fin = cub.get("hora_fin") or ""
            mins     = cub.get("minutos_restantes")
            if hora_fin and estado not in ("libre", "mantenimiento"):
                timer_html = (
                    f'<div class="jjgt-timer" data-fin="{hora_fin}" ' +
                    f'data-key="bien-{cub["id"]}" ' +
                    f'style="font-size:11px;color:#ffd32a">⏱{fmt_tiempo(mins)}</div>'
                )
            else:
                timer_html = ""
            st.markdown(f"""
            <div style="background:{info['bg']};border:1.5px solid {info['color']}44;
                        border-radius:10px;padding:10px;text-align:center;margin-bottom:8px">
              <div style="font-family:'Inconsolata',monospace;font-size:22px;
                          font-weight:700;color:{info['color']}">{cub['numero']}</div>
              <div style="font-size:10px;font-weight:700;color:{info['color']};
                          letter-spacing:1px">{info['label']}</div>
              {timer_html}
            </div>
            """, unsafe_allow_html=True)

    # Botones de acción del operador
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_back, _ = st.columns([2, 1, 2])
    with col_back:
        if st.button("⬅️ Volver al Panel", use_container_width=True):
            ir_a("operador")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 1 — SELECCIÓN DE CUBÍCULO Y TIEMPO
# ══════════════════════════════════════════════════════════════════════════════

def show_seleccion():
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header("Elige tu cubículo y tiempo de descanso")
    render_stepper(0)
    inject_live_clock()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### ⏱️ ¿Cuánto tiempo necesitas?")
        tiempos = {"30 min": 0.3, "1 hora": 1.0, "2 horas": 2.0,
                   "3 horas": 3.0, "4 horas": 4.0, "⚙️ Personalizar": -1}
        cols_t  = st.columns(3)
        for i, (label, val) in enumerate(tiempos.items()):
            with cols_t[i % 3]:
                sel = st.session_state.horas_sel
                activo = (sel == val) or (val == -1 and sel not in [0.3,1,2,3,4])
                if st.button(label, key=f"btn_t_{i}",
                             type="primary" if activo else "secondary",
                             use_container_width=True):
                    if val == -1:
                        st.session_state.horas_sel = 1.5
                    else:
                        st.session_state.horas_sel = val
                    st.rerun()

        horas = st.session_state.horas_sel
        if horas not in [0.3, 1.0, 2.0, 3.0, 4.0]:
            horas = st.number_input("Horas personalizadas", min_value=0.3, max_value=12.0,
                                     value=float(horas), step=0.3)
            st.session_state.horas_sel = horas

        # Cálculo en tiempo real
        calc = calcular_precio(st.session_state.horas_sel)
        st.session_state.calc = calc
        st.markdown("<br>", unsafe_allow_html=True)

        # Resumen de precio
        tarifa_badge = ""
        if calc["tarifa"] == "Madrugada":
            tarifa_badge = "🌙 Tarifa madrugada"
        elif calc["descuento_pct"] > 0:
            tarifa_badge = f"🏷️ Descuento {calc['descuento_pct']:.0f}% aplicado"

        st.markdown(f"""
        <div style="background:var(--bg-card);border:1.5px solid rgba(0,212,255,0.3);
                    border-radius:12px;padding:20px">
          <div style="font-size:13px;color:#94a3b8;letter-spacing:2px;text-transform:uppercase">
            Tarifa: {calc['tarifa']} {tarifa_badge}
          </div>
          <div style="font-size:13px;color:#94a3b8;margin-top:4px">
            {fmt_cop(calc['precio_hora'])}/hora × {calc['horas']}h
            {"  ·  -" + fmt_cop(calc['descuento_val']) if calc['descuento_val'] > 0 else ""}
          </div>
          <div style="font-size:13px;color:#94a3b8">Subtotal: {fmt_cop(calc['subtotal'])}</div>
          <div style="font-size:13px;color:#94a3b8">IVA 19%: {fmt_cop(calc['iva'])}</div>
          <div style="font-family:'Inconsolata',monospace;font-size:32px;
                      font-weight:700;color:#00d4ff;margin-top:8px">
            {fmt_cop(calc['total'])} COP
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("#### 🛏️ Selecciona tu cubículo")
        cubiculos = get_cubiculos()
        cols_c    = st.columns(4)
        for i, cub in enumerate(cubiculos):
            with cols_c[i % 4]:
                sel = st.session_state.cubiculo_sel
                clicked = render_cubiculo_card(
                    cub, seleccionado=(sel and sel["id"] == cub["id"]))
                if clicked and cub["estado"] == "libre":
                    st.session_state.cubiculo_sel = cub
                    st.rerun()

    st.markdown("---")
    col_v, col_c = st.columns([1, 1])
    with col_v:
        col_vv1, col_vv2 = st.columns(2)
        with col_vv1:
            if st.button("← Volver", use_container_width=True):
                ir_a("bienvenida")
        with col_vv2:
            if st.button("✖ Cancelar al panel", use_container_width=True):
                ir_a("operador")
    with col_c:
        if st.session_state.cubiculo_sel and st.session_state.calc:
            cub_sel = st.session_state.cubiculo_sel
            cval    = st.session_state.calc
            st.markdown(f"""
            <div style="background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.4);
                        border-radius:10px;padding:12px 16px;text-align:center;
                        font-weight:700;color:#00d4ff;margin-bottom:8px">
              {cub_sel['numero']} · {cval['horas']}h · {fmt_cop(cval['total'])} COP
            </div>
            """, unsafe_allow_html=True)
            if st.button("CONTINUAR →", type="primary", use_container_width=True):
                ir_a("datos")
        else:
            st.info("👆 Selecciona un cubículo libre para continuar")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 2 — DATOS DEL CLIENTE
# ══════════════════════════════════════════════════════════════════════════════

def show_datos():
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header("Tus datos para la reserva")
    inject_live_clock()
    render_stepper(1)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        nombre = st.text_input("👤 Nombre completo *",
                               placeholder="Ej: María García López",
                               value=st.session_state.cliente.get("nombre",""))
        c1, c2 = st.columns(2)
        with c1:
            tipo_doc = st.selectbox("Tipo documento", ["CC", "Pasaporte", "CE", "NIT"])
        with c2:
            num_doc = st.text_input("N° de documento *",
                                    placeholder="1234567890",
                                    value=st.session_state.cliente.get("numero_documento",""))
        telefono = st.text_input("📱 Teléfono celular *",
                                 placeholder="310 555 0000",
                                 value=st.session_state.cliente.get("telefono",""))
        email = st.text_input("📧 Email (opcional — para factura digital)",
                              placeholder="tu@email.com",
                              value=st.session_state.cliente.get("email",""))

        factura_emp = st.checkbox("🏢 Requiero factura a nombre de empresa")
        razon_social = ""
        nit_emp = ""
        if factura_emp:
            razon_social = st.text_input("Razón social", value=st.session_state.cliente.get("razon_social",""))
            nit_emp      = st.text_input("NIT de la empresa", value=st.session_state.cliente.get("nit_empresa",""))

        st.markdown("</div>", unsafe_allow_html=True)

        # Validación
        errores = []
        if not nombre.strip():
            errores.append("El nombre es obligatorio")
        if not num_doc.strip():
            errores.append("El número de documento es obligatorio")
        if not telefono.strip():
            errores.append("El teléfono es obligatorio")

        c_v, c_c = st.columns([1, 2])
        with c_v:
            col_dv1, col_dv2 = st.columns(2)
            with col_dv1:
                if st.button("← Volver", use_container_width=True):
                    ir_a("seleccion")
            with col_dv2:
                if st.button("✖ Panel", use_container_width=True):
                    ir_a("operador")
        with c_c:
            if st.button("CONTINUAR AL PAGO →", type="primary", use_container_width=True):
                if errores:
                    for e in errores:
                        st.error(e)
                else:
                    st.session_state.cliente = {
                        "nombre": nombre.strip(),
                        "tipo_doc": tipo_doc,
                        "numero_documento": num_doc.strip(),
                        "telefono": telefono.strip(),
                        "email": email.strip(),
                        "razon_social": razon_social,
                        "nit_empresa": nit_emp,
                    }
                    ir_a("pago")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 3 — PAGO
# ══════════════════════════════════════════════════════════════════════════════

def show_pago():
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header("Elige cómo pagar")
    render_stepper(2)
    inject_live_clock()

    calc   = st.session_state.calc
    cub    = st.session_state.cubiculo_sel
    # Referencia única por sesión + timestamp para garantizar QR fresco
    ref    = f"CR-{ahora_col().strftime('%Y%m%d%H%M')}-{cub['numero'].replace('#','')}"
    monto  = int(calc["total"])

    # Auto-refresh del QR cada 5 min: rerun de Streamlit = QR nuevo desde Python
    now_ts_pago = int(time.time())
    last_qr_rerun = st.session_state.get("_pago_qr_rerun_ts", 0)
    if now_ts_pago - last_qr_rerun >= 300:  # 5 minutos
        st.session_state["_pago_qr_rerun_ts"] = now_ts_pago
        st.rerun()

    # Resumen
    st.markdown(f"""
    <div style="background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.3);
                border-radius:12px;padding:14px 20px;display:flex;
                justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:12px">
      <div>
        <span style="color:#94a3b8;font-size:13px">Cubículo</span><br>
        <b style="font-size:20px;color:#00d4ff">{cub['numero']}</b>
      </div>
      <div>
        <span style="color:#94a3b8;font-size:13px">Tiempo</span><br>
        <b style="font-size:20px">{calc['horas']}h</b>
      </div>
      <div>
        <span style="color:#94a3b8;font-size:13px">Total a pagar</span><br>
        <b style="font-family:'Inconsolata';font-size:28px;color:#00ff88">{fmt_cop(monto)} COP</b>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab_nequi, tab_davi, tab_efect, tab_otros = st.tabs([
        "💚 Nequi", "💙 Daviplata", "💵 Efectivo", "📲 Otros métodos"])

    with tab_nequi:
        _pago_nequi(monto, ref)
    with tab_davi:
        _pago_daviplata(monto, ref)
    with tab_efect:
        _pago_efectivo(monto, ref)
    with tab_otros:
        _pago_otros(monto, ref)

    st.markdown("<br>", unsafe_allow_html=True)
    col_pb1, col_pb2 = st.columns(2)
    with col_pb1:
        if st.button("← Volver a mis datos", use_container_width=True):
            ir_a("datos")
    with col_pb2:
        if st.button("✖ Cancelar al panel", use_container_width=True):
            ir_a("operador")


def _pago_nequi(monto: int, ref: str):
    """
    Pantalla de pago con Nequi.
    Muestra el QR de cobro personal con instrucciones paso a paso para que el
    cliente abra Nequi, acceda a 'Tu QR personal' y escanee para pagar.
    El QR codifica el deep-link nequi:// con monto y referencia exactos.
    """
    nequi_num = get_config("nequi_numero", NEQUI_NUM)

    # ── Encabezado ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(0,150,60,0.25),rgba(0,220,90,0.10));
                border:2px solid rgba(0,220,90,0.45);border-radius:16px;
                padding:20px 24px;margin-bottom:18px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
        <span style="font-size:32px">💚</span>
        <div>
          <div style="font-size:22px;font-weight:800;color:#00c853;letter-spacing:-0.5px">
            Paga con Nequi
          </div>
          <div style="font-size:13px;color:#94a3b8;margin-top:2px">
            Número de cuenta: <b style="font-family:'Inconsolata';color:#00ff88">{nequi_num}</b>
          </div>
        </div>
        <div style="margin-left:auto;text-align:right">
          <div style="font-size:13px;color:#94a3b8">Total a pagar</div>
          <div style="font-family:'Inconsolata';font-size:32px;font-weight:800;
                      color:#00ff88;text-shadow:0 0 20px rgba(0,255,136,0.4)">
            {fmt_cop(monto)} COP
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_qr, col_steps = st.columns([1, 1], gap="large")

    with col_qr:
        # ── QR de cobro ───────────────────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center;font-size:13px;font-weight:700;
                    color:#00c853;letter-spacing:2px;text-transform:uppercase;
                    margin-bottom:8px">
          📷 Escanea este QR con Nequi
        </div>
        """, unsafe_allow_html=True)

        _, qr_b64 = mostrar_qr("Nequi", monto, ref, size=280)

        # Datos del pago bajo el QR
        st.markdown(f"""
        <div style="background:rgba(0,0,0,0.3);border:1px solid rgba(0,220,90,0.25);
                    border-radius:10px;padding:12px;margin-top:10px;text-align:center">
          <div style="font-size:11px;color:#94a3b8;letter-spacing:1px;
                      text-transform:uppercase;margin-bottom:4px">Referencia de pago</div>
          <div style="font-family:'Inconsolata';font-size:14px;font-weight:700;
                      color:#e2e8f0;word-break:break-all">{ref}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:6px">
            Número Nequi del comercio: <b style="color:#00c853">{nequi_num}</b>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_steps:
        # ── Instrucciones paso a paso ─────────────────────────────────────────
        st.markdown("""
        <div style="font-size:14px;font-weight:700;color:#00c853;letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:14px">
          📱 ¿Cómo pagar?
        </div>
        """, unsafe_allow_html=True)

        pasos = [
            ("1", "Abre la app <b>Nequi</b> en tu celular",
             "No necesitas iniciar sesión si ya estás autenticado"),
            ("2", 'Toca el ícono <b style="color:#00ff88">$</b> en la pantalla principal',
             "Es el botón de cobros / pagos rápidos"),
            ("3", 'Selecciona <b>"Usa tu QR"</b>',
             "Aparece en el menú de opciones de pago"),
            ("4", 'Elige <b>"Tu QR personal"</b>',
             "Para cobrar desde tu cuenta personal"),
            ("5", 'Toca <b>"Generar tu QR"</b> y muéstraselo al operador',
             "O usa el QR de la pantalla para transferir directamente"),
            ("6", f'Envía <b style="color:#00ff88">{fmt_cop(monto)} COP</b> al número <b style="color:#00ff88">{nequi_num}</b>',
             "Confirma el monto antes de aprobar"),
        ]

        for num, titulo, subtitulo in pasos:
            st.markdown(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;
                        margin-bottom:12px;padding:10px 12px;
                        background:rgba(0,100,40,0.12);
                        border-left:3px solid rgba(0,220,90,0.5);
                        border-radius:0 8px 8px 0">
              <div style="min-width:28px;height:28px;border-radius:50%;
                          background:#00c853;color:#000;font-weight:800;
                          font-size:13px;display:flex;align-items:center;
                          justify-content:center;flex-shrink:0">{num}</div>
              <div>
                <div style="font-size:14px;color:#e2e8f0">{titulo}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:2px">{subtitulo}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # Alerta de monto
        st.markdown(f"""
        <div style="background:rgba(0,200,83,0.15);border:1px solid rgba(0,200,83,0.4);
                    border-radius:10px;padding:12px;text-align:center;margin-top:4px">
          <div style="font-size:12px;color:#94a3b8;margin-bottom:4px">
            ⚠️ Verifica siempre el monto antes de confirmar
          </div>
          <div style="font-family:'Inconsolata';font-size:26px;font-weight:800;color:#00ff88">
            {fmt_cop(monto)} COP
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Botón de confirmación ─────────────────────────────────────────────────
    if st.button("✅ Ya pagué con Nequi — Confirmar pago", type="primary",
                 use_container_width=True, key="confirm_nequi"):
        _confirmar_pago("Nequi")


def _pago_daviplata(monto: int, ref: str):
    davi_num = get_config("daviplata_numero", DAVIPLATA_NUM)
    st.markdown(f"""
    <div style="background:rgba(10,40,100,0.3);border:2px solid rgba(59,130,246,0.35);
                border-radius:12px;padding:20px;margin-bottom:16px">
      <div style="font-size:20px;font-weight:700;color:#60a5fa;margin-bottom:8px">
        💙 Pago con Daviplata
      </div>
      <div style="font-size:16px;color:#e2e8f0">
        Abre <b>Daviplata</b> → <b>Pagar</b> → Escanear QR<br>
        o envía a <b style="font-family:'Inconsolata';font-size:22px;color:#60a5fa">{davi_num}</b><br>
        <b style="color:#60a5fa">Monto: {fmt_cop(monto)} COP</b>
      </div>
    </div>
    """, unsafe_allow_html=True)
    mostrar_qr("Daviplata", monto, ref)
    if st.button("✅ Ya pagué con Daviplata — Confirmar pago", type="primary",
                 use_container_width=True, key="confirm_davi"):
        _confirmar_pago("Daviplata")


def _pago_efectivo(monto: int, ref: str):
    tel_op = get_config("whatsapp_op", WHATSAPP_OP)
    cambios = {
        10000: monto - 10000, 20000: monto - 20000,
        50000: 50000 - monto, 100000: 100000 - monto,
    }
    st.markdown(f"""
    <div style="background:rgba(20,60,20,0.3);border:2px solid rgba(132,204,22,0.35);
                border-radius:12px;padding:20px;margin-bottom:16px">
      <div style="font-size:20px;font-weight:700;color:#84cc16;margin-bottom:8px">
        💵 Pago en Efectivo
      </div>
      <div style="font-size:16px;color:#e2e8f0;margin-bottom:12px">
        Dirígete a la caja del operador<br>
        o llama al <b style="color:#84cc16">{tel_op}</b>
      </div>
      <div style="font-size:28px;font-weight:700;color:#00ff88;text-align:center">
        Total: {fmt_cop(monto)} COP
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"🔔 LLAMAR AL OPERADOR — {tel_op}", use_container_width=True, key="btn_llamar"):
        st.markdown(f"""
        <audio autoplay>
          <source src="data:audio/mp3;base64," type="audio/mp3">
        </audio>
        <script>
          var audio = new AudioContext();
          var osc = audio.createOscillator();
          osc.connect(audio.destination);
          osc.frequency.value = 880;
          osc.start();
          setTimeout(() => osc.stop(), 500);
        </script>
        """, unsafe_allow_html=True)
        st.success(f"🔔 Operador notificado · Tel: {tel_op}")

    st.markdown("**Sugerencia de denominaciones:**")
    c1, c2, c3 = st.columns(3)
    for col, bill in zip([c1, c2, c3], [20000, 50000, 100000]):
        cambio = bill - monto
        if cambio >= 0:
            col.markdown(f"""
            <div style="background:rgba(0,0,0,0.3);border:1px solid rgba(132,204,22,0.3);
                        border-radius:8px;padding:12px;text-align:center">
              <div style="font-size:18px;font-weight:700;color:#84cc16">{fmt_cop(bill)}</div>
              <div style="font-size:12px;color:#94a3b8">Cambio: {fmt_cop(cambio)}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>**Confirmación del operador (requiere PIN):**")
    pin_op = st.text_input("PIN operador", type="password", max_chars=8,
                           key="pin_efectivo", placeholder="••••")
    if st.button("✅ CONFIRMAR PAGO EN EFECTIVO", type="primary",
                 use_container_width=True, key="confirm_efect"):
        if verificar_pin(pin_op):
            _confirmar_pago("Efectivo")
        else:
            st.error("PIN incorrecto")


def _pago_otros(monto: int, ref: str):
    cuenta = get_config("cuenta_bancaria", CUENTA_BANCO)
    mp_link = get_config("mp_link", MP_LINK)
    metodo_sel = st.radio("Selecciona plataforma:",
                          ["PSE", "MercadoPago", "Transferencia bancaria", "Tarjeta (Datáfono)"],
                          horizontal=True)

    if metodo_sel == "PSE":
        st.info(f"**PSE · Referencia:** `{ref}` · **Monto:** {fmt_cop(monto)}")
        mostrar_qr("PSE", monto, ref, size=250)
        if st.button("✅ Confirmar pago PSE", type="primary",
                     use_container_width=True, key="confirm_pse"):
            _confirmar_pago("PSE")

    elif metodo_sel == "MercadoPago":
        st.markdown(f"""
        <div style="background:rgba(0,158,243,0.15);border:1px solid rgba(0,158,243,0.4);
                    border-radius:12px;padding:16px;margin-bottom:12px">
          <div style="font-size:17px;font-weight:700;color:#009ef3">🔵 MercadoPago Colombia</div>
          <div style="font-size:15px;margin-top:8px">
            Link de pago: <a href="{mp_link}" style="color:#009ef3">{mp_link}</a><br>
            Referencia: <b>{ref}</b>
          </div>
        </div>
        """, unsafe_allow_html=True)
        mostrar_qr("MercadoPago", monto, ref, size=250)
        if st.button("✅ Confirmar pago MercadoPago", type="primary",
                     use_container_width=True, key="confirm_mp"):
            _confirmar_pago("MercadoPago")

    elif metodo_sel == "Transferencia bancaria":
        st.markdown(f"""
        <div style="background:rgba(100,100,0,0.15);border:1px solid rgba(200,200,0,0.3);
                    border-radius:12px;padding:16px;margin-bottom:12px">
          <div style="font-size:17px;font-weight:700;color:#eab308">🏦 Transferencia Bancaria</div>
          <div style="font-size:15px;margin-top:8px">
            <b>{cuenta}</b><br>
            NIT: {NIT}<br>
            Monto exacto: <b style="color:#00ff88">{fmt_cop(monto)} COP</b><br>
            Referencia: <b style="font-family:'Inconsolata'">{ref}</b>
          </div>
        </div>
        """, unsafe_allow_html=True)
        mostrar_qr("Transferencia", monto, ref, size=250)
        pin_op2 = st.text_input("PIN operador para confirmar", type="password",
                                 max_chars=8, key="pin_transf")
        if st.button("✅ Confirmar transferencia recibida", type="primary",
                     use_container_width=True, key="confirm_transf"):
            if verificar_pin(pin_op2):
                _confirmar_pago("Transferencia")
            else:
                st.error("PIN incorrecto")

    else:
        tel_op = get_config("whatsapp_op", WHATSAPP_OP)
        st.markdown(f"""
        <div style="background:rgba(50,50,50,0.4);border:1px solid rgba(200,200,200,0.2);
                    border-radius:12px;padding:20px;text-align:center">
          <div style="font-size:60px">💳</div>
          <div style="font-size:18px;font-weight:700;margin-top:8px">Pago con Datáfono</div>
          <div style="font-size:16px;color:#94a3b8;margin-top:8px">
            El datáfono está disponible en caja.<br>
            Solicita al operador: <b>{tel_op}</b>
          </div>
        </div>
        """, unsafe_allow_html=True)


def _confirmar_pago(metodo: str):
    st.session_state.metodo_pago = metodo
    ir_a("confirmacion")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 4 — CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def show_confirmacion():
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header("Procesando tu pago")
    render_stepper(3)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        # ── Guardia anti-doble-clic ────────────────────────────────────────────
        # Si ya hay un proceso en curso (mismo cubiculo + cliente), mostrar spinner
        # y no volver a ejecutar crear_reserva_completa.
        if st.session_state.get("_procesando_reserva"):
            st.info("⏳ Ya se está procesando una reserva, por favor espera...")
            return

        # Si ya se confirmó exitosamente en esta sesión, mostrar resultado directo
        if st.session_state.get("pago_confirmado") and st.session_state.get("voucher"):
            voucher = st.session_state["voucher"]
            st.markdown("""
            <div class="confirm-ok">
              <div style="font-size:80px">✅</div>
              <div style="font-size:32px;font-weight:800;color:#00ff88;margin:12px 0">
                ¡PAGO CONFIRMADO!
              </div>
              <div style="font-size:18px;color:#e2e8f0">
                Tu cubículo está listo. ¡Disfruta tu descanso!
              </div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.5)
            st.markdown(f"""
            <div style="text-align:center;margin:24px 0">
              <div style="font-size:16px;color:#94a3b8;letter-spacing:3px;
                          text-transform:uppercase">Tu cubículo</div>
              <div style="font-family:'Inconsolata';font-size:80px;font-weight:700;
                          color:#00d4ff;line-height:1">{voucher['cubiculo']}</div>
              <div style="font-size:16px;color:#94a3b8;letter-spacing:3px;
                          text-transform:uppercase;margin-top:8px">Código de acceso</div>
              <div style="font-family:'Inconsolata';font-size:72px;font-weight:700;
                          color:#00ff88;letter-spacing:16px;
                          text-shadow:0 0 40px rgba(0,255,136,0.6)">{voucher['codigo_acceso']}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📋 VER MI VOUCHER COMPLETO", type="primary", use_container_width=True):
                ir_a("voucher")
            return

        # ── Verificar reserva duplicada: mismo cliente con reserva activa hoy ──
        cliente_sel = st.session_state.get("cliente", {})
        num_doc     = cliente_sel.get("numero_documento", "")

        if not num_doc:
            st.session_state["_procesando_reserva"] = False
            st.error("❌ No se encontró documento del cliente en la sesión. Vuelve a ingresar los datos.")
            if st.button("← Volver a datos", use_container_width=True):
                ir_a("datos")
            return

        # Consulta de duplicado — si falla, bloquear por seguridad
        reserva_dup = None
        error_dup   = None
        try:
            _con_dup = get_db()
            hoy_str = ahora_col().strftime("%Y-%m-%d")
            reserva_dup = _con_dup.execute("""
                SELECT r.numero_reserva, r.hora_inicio, r.hora_fin_programada,
                       cu.numero AS cubiculo_num
                FROM reservas r
                JOIN clientes c ON r.cliente_id = c.id
                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                WHERE c.numero_documento = ?
                  AND r.estado_pago = 'confirmado'
                  AND SUBSTR(r.hora_inicio, 1, 10) = ?
                  AND (r.hora_fin_real IS NULL OR r.hora_fin_real = '')
                ORDER BY r.id DESC LIMIT 1
            """, (num_doc, hoy_str)).fetchone()
            _con_dup.close()
        except Exception as e_dup:
            error_dup = str(e_dup)

        if error_dup:
            st.error(f"❌ Error al verificar reservas existentes: {error_dup}. No se puede continuar.")
            if st.button("← Volver al pago", use_container_width=True, key="btn_dup_err"):
                ir_a("pago")
            return

        if reserva_dup:
            num_res_dup, hi_dup, hf_dup, cub_num_dup = reserva_dup
            st.markdown(f"""
            <div class="confirm-fail">
              <div style="font-size:50px">⚠️</div>
              <div style="font-size:22px;font-weight:700;color:#ffd32a;margin:12px 0">
                Reserva duplicada detectada
              </div>
              <div style="font-size:15px;color:#e2e8f0">
                El cliente con documento <b>{num_doc}</b> ya tiene una reserva activa hoy:<br>
                <b>Reserva {num_res_dup}</b> · Cubículo <b>{cub_num_dup or '—'}</b><br>
                {hi_dup[:16] if hi_dup else ''} → {hf_dup[:16] if hf_dup else ''}
              </div>
              <div style="font-size:13px;color:#94a3b8;margin-top:12px">
                No se puede crear una nueva reserva para un cliente
                que ya tiene una reserva activa que aún no ha terminado.
              </div>
            </div>
            """, unsafe_allow_html=True)
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                if st.button("← Volver al pago", use_container_width=True, key="btn_dup_back"):
                    ir_a("pago")
            with col_d2:
                if st.button("✖ Ir al panel", use_container_width=True, key="btn_dup_panel"):
                    ir_a("operador")
            return  # ← SIEMPRE retorna aquí si hay duplicado

        # ── Marcar proceso en curso ANTES de ejecutar ──────────────────────────
        st.session_state["_procesando_reserva"] = True

        with st.spinner("⚙️ Activando tu cubículo..."):
            time.sleep(1.2)

        try:
            voucher = crear_reserva_completa(
                st.session_state.cubiculo_sel,
                st.session_state.cliente,
                st.session_state.calc,
                st.session_state.metodo_pago,
            )
            st.session_state.voucher        = voucher
            st.session_state.pago_confirmado = True
            st.session_state["_procesando_reserva"] = False

            st.markdown("""
            <div class="confirm-ok">
              <div style="font-size:80px">✅</div>
              <div style="font-size:32px;font-weight:800;color:#00ff88;margin:12px 0">
                ¡PAGO CONFIRMADO!
              </div>
              <div style="font-size:18px;color:#e2e8f0">
                Tu cubículo está listo. ¡Disfruta tu descanso!
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Código de acceso grande
            time.sleep(0.5)
            st.markdown(f"""
            <div style="text-align:center;margin:24px 0">
              <div style="font-size:16px;color:#94a3b8;letter-spacing:3px;
                          text-transform:uppercase">Tu cubículo</div>
              <div style="font-family:'Inconsolata';font-size:80px;font-weight:700;
                          color:#00d4ff;line-height:1">{voucher['cubiculo']}</div>
              <div style="font-size:16px;color:#94a3b8;letter-spacing:3px;
                          text-transform:uppercase;margin-top:8px">Código de acceso</div>
              <div style="font-family:'Inconsolata';font-size:72px;font-weight:700;
                          color:#00ff88;letter-spacing:16px;
                          text-shadow:0 0 40px rgba(0,255,136,0.6)">{voucher['codigo_acceso']}</div>
            </div>
            """, unsafe_allow_html=True)

            time.sleep(0.8)
            if st.button("📋 VER MI VOUCHER COMPLETO", type="primary", use_container_width=True):
                ir_a("voucher")

        except Exception as e:
            st.session_state["_procesando_reserva"] = False
            st.markdown(f"""
            <div class="confirm-fail">
              <div style="font-size:60px">❌</div>
              <div style="font-size:24px;font-weight:700;color:#ff4757;margin:12px 0">
                Error al procesar el pago
              </div>
              <div style="font-size:15px;color:#94a3b8">{str(e)}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Intentar de nuevo", use_container_width=True):
                ir_a("pago")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 5 — VOUCHER
# ══════════════════════════════════════════════════════════════════════════════

def show_voucher():
    if not st.session_state.get("operador_ok"):
        ir_a("operador_login")
        return
    render_header("Tu reserva confirmada")
    render_stepper(4)
    inject_live_clock()

    v = st.session_state.voucher
    if not v:
        ir_a("bienvenida")
        return

    # Obtener hora_inicio real de la BD para el timer de tiempo consumido
    hora_inicio_iso = ""
    hora_fin_iso = ""
    try:
        con_v = get_db()
        row_v = con_v.execute(
            "SELECT hora_inicio, hora_fin_programada FROM reservas WHERE numero_reserva=?",
            (v.get("numero_reserva",""),)).fetchone()
        con_v.close()
        if row_v:
            hora_inicio_iso = row_v[0] or ""
            hora_fin_iso    = row_v[1] or ""
    except Exception:
        pass

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(f"""
        <div class="voucher-box">
          <div style="text-align:center;margin-bottom:16px">
            <div style="font-size:22px;font-weight:800;color:#00d4ff">{NEGOCIO}</div>
            <div style="font-size:13px;color:#94a3b8">{TAGLINE}</div>
          </div>
          <div style="background:rgba(0,0,0,0.3);border-radius:8px;padding:12px;margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Reserva</span>
              <b style="font-family:'Inconsolata'">{v['numero_reserva']}</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Factura</span>
              <b style="font-family:'Inconsolata'">{v['numero_factura']}</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Cubículo</span>
              <b style="color:#00d4ff;font-size:20px">{v['cubiculo']}</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Entrada → Salida</span>
              <b>{v['hora_inicio']} → {v['hora_fin']}</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Tiempo</span>
              <b>{v['horas']}h</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Tiempo restante</span>
              <b class="jjgt-timer" data-fin="{hora_fin_iso}" data-key="voucher-fin"
                 style="color:#00ff88;font-family:'Inconsolata'">calculando...</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">Consumido</span>
              <span class="jjgt-consumed" data-inicio="{hora_inicio_iso}"
                    style="color:#94a3b8;font-family:'Inconsolata'">calculando...</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid rgba(255,255,255,0.1)">
              <span style="color:#94a3b8">WiFi</span>
              <b>{v['wifi_ssid']}</b>
            </div>
            <div style="display:flex;justify-content:space-between;padding:4px 0">
              <span style="color:#94a3b8">Clave WiFi</span>
              <b style="font-family:'Inconsolata'">{v['wifi_password']}</b>
            </div>
          </div>
          <div style="text-align:center;margin:4px 0 12px">
            <div style="font-size:12px;color:#94a3b8;letter-spacing:2px;text-transform:uppercase">
              Código de acceso al cubículo
            </div>
            <div class="voucher-codigo">{v['codigo_acceso']}</div>
          </div>
          <div style="background:rgba(0,0,0,0.3);border-radius:8px;padding:12px">
            <div style="display:flex;justify-content:space-between;padding:3px 0">
              <span style="color:#94a3b8">Subtotal</span><span>{fmt_cop(v['subtotal'])}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:3px 0">
              <span style="color:#94a3b8">IVA 19%</span><span>{fmt_cop(v['iva'])}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;
                        font-family:'Inconsolata';font-size:22px;font-weight:700;color:#00ff88;
                        border-top:1px solid rgba(255,255,255,0.15);margin-top:4px">
              <span>TOTAL</span><span>{fmt_cop(v['total'])} COP</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:3px 0">
              <span style="color:#94a3b8">Pago</span><b>{v['metodo_pago']}</b>
            </div>
          </div>
          <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap;justify-content:center">
            <span style="background:rgba(0,255,136,0.15);color:#00ff88;padding:6px 14px;
                         border-radius:20px;font-size:13px;font-weight:700">✓ Baño</span>
            <span style="background:rgba(0,255,136,0.15);color:#00ff88;padding:6px 14px;
                         border-radius:20px;font-size:13px;font-weight:700">✓ WiFi</span>
            <span style="background:rgba(0,255,136,0.15);color:#00ff88;padding:6px 14px;
                         border-radius:20px;font-size:13px;font-weight:700">✓ Carga</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Botones de acción
    c1, c2, c3 = st.columns(3)
    with c1:
        wa_msg = (f"JJGT Reserva {v['numero_reserva']} · Cubículo {v['cubiculo']} · "
                  f"Código: {v['codigo_acceso']} · WiFi: {v['wifi_ssid']} Clave: {v['wifi_password']} · "
                  f"Total: {fmt_cop(v['total'])} COP · Factura: {v['numero_factura']}")
        wa_url = f"https://wa.me/?text={wa_msg.replace(' ', '%20')}"
        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="width:100%;padding:14px;'
                    f'background:rgba(37,211,102,0.2);border:2px solid rgba(37,211,102,0.5);'
                    f'border-radius:12px;color:#25d366;font-weight:700;font-size:16px;cursor:pointer">'
                    f'📱 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)

    with c2:
        if REPORTLAB_AVAILABLE:
            pdf_bytes = generar_ticket_pdf(v)
            if pdf_bytes:
                st.download_button("📄 Descargar PDF", data=pdf_bytes,
                                   file_name=f"ticket_{v['numero_reserva']}.pdf",
                                   mime="application/pdf", use_container_width=True)
        else:
            html_v = voucher_html(v)
            st.download_button("📄 Descargar Voucher HTML", data=html_v.encode(),
                               file_name=f"voucher_{v['numero_reserva']}.html",
                               mime="text/html", use_container_width=True)

    with c3:
        col_v3a, col_v3b = st.columns(2)
        with col_v3a:
            if st.button("✅ IR A MI CUBÍCULO", type="primary", use_container_width=True):
                # Reset flujo de reserva, volver a bienvenida (kiosk view)
                for k in ["cubiculo_sel","calc","metodo_pago","voucher","pago_confirmado","cliente"]:
                    if k == "horas_sel":
                        st.session_state[k] = 1.0
                    elif k in ["cubiculo_sel","calc","metodo_pago","voucher"]:
                        st.session_state[k] = None
                    elif k == "pago_confirmado":
                        st.session_state[k] = False
                    elif k == "cliente":
                        st.session_state[k] = {}
                st.session_state["pantalla"] = "bienvenida"
                st.rerun()
        with col_v3b:
            if st.button("🔧 Volver al Panel", use_container_width=True):
                for k in ["cubiculo_sel","calc","metodo_pago","voucher","pago_confirmado","cliente"]:
                    st.session_state.pop(k, None)
                st.session_state["cubiculo_sel"]    = None
                st.session_state["calc"]            = None
                st.session_state["metodo_pago"]     = None
                st.session_state["voucher"]         = None
                st.session_state["pago_confirmado"] = False
                st.session_state["cliente"]         = {}
                ir_a("operador")


# ══════════════════════════════════════════════════════════════════════════════
# PANEL OPERADOR — LOGIN
# ══════════════════════════════════════════════════════════════════════════════

def show_operador_login():
    """
    Pantalla de login de operador — PANTALLA INICIAL de la app.
    Si el operador ya está autenticado (sesión activa), va directo al panel.
    Siempre muestra título y reloj.
    """
    # Si ya está autenticado, ir directamente al panel
    if st.session_state.get("operador_ok"):
        ir_a("operador")
        return

    render_header("Acceso de Operadores")
    inject_live_clock()
    render_reloj()

    st.markdown("<br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🔐 Identificación de Operador")
        st.caption("Ingresa tu PIN para iniciar tu turno")

        # Selector de turno visual
        ahora_h = ahora_col().hour
        turno_actual = "mañana" if 6 <= ahora_h < 14 else ("tarde" if 14 <= ahora_h < 22 else "noche")
        turno_label  = {"mañana": "☀️ Turno Mañana (06:00–14:00)",
                        "tarde":  "🌤️ Turno Tarde (14:00–22:00)",
                        "noche":  "🌙 Turno Noche (22:00–06:00)"}
        st.info(f"**Turno activo:** {turno_label.get(turno_actual, turno_actual)}")

        pin = st.text_input("PIN de operador", type="password", max_chars=8,
                            placeholder="••••", key="pin_login_input")

        if st.button("✅ INGRESAR AL SISTEMA", type="primary",
                     use_container_width=True, key="btn_login"):
            op = get_operador_por_pin(pin)
            if op:
                st.session_state.operador_ok      = True
                st.session_state.operador_info    = op
                st.session_state.pin_intentos     = 0
                st.session_state.pantalla         = "operador"
                st.rerun()
            else:
                st.session_state.pin_intentos += 1
                intentos = st.session_state.pin_intentos
                if intentos >= 3:
                    st.error("🔒 Demasiados intentos incorrectos. Contacta al administrador.")
                else:
                    st.error(f"❌ PIN incorrecto ({intentos}/3)")

        st.markdown('</div>', unsafe_allow_html=True)

    # Info de PINs de acceso (solo visible en ejecución LOCAL — no en Cloud)
    if not _IS_CLOUD:
        with st.expander("ℹ️ PINs de acceso inicial (cambiar en ⚙️ Configuración → Operadores)"):
            st.markdown("""
| Operador | PIN | Turno | Permisos |
|---|---|---|---|
| Admin JJGT | `1234` | Admin | Todos |
| Op. Mañana | `1111` | 06:00–14:00 | Reservas, Pagos, Voucher |
| Op. Tarde  | `2222` | 14:00–22:00 | Reservas, Pagos, Voucher |
| Op. Noche  | `3333` | 22:00–06:00 | Reservas, Pagos, Voucher |
            """)
            st.warning("⚠️ Cambia estos PINs inmediatamente en **Configuración → Operadores**")
    else:
        con_cl = get_db()
        n_op_cloud = con_cl.execute("SELECT COUNT(*) FROM operadores").fetchone()[0]
        con_cl.close()
        if n_op_cloud > 0:
            with st.expander("ℹ️ Acceso en Cloud — lee esto si es tu primer ingreso"):
                st.info(
                    "Los operadores restaurados desde Google Sheets tienen PIN **1234** "
                    "hasta que lo cambies en ⚙️ Configuración → Operadores."
                )
        else:
            st.warning(
                "⚠️ Base de datos vacía. Ve al panel de operador → "
                "**☁️ Google Drive → Restaurar datos** para cargar la información."
            )


# ══════════════════════════════════════════════════════════════════════════════
# PANEL OPERADOR — MÓDULOS
# ══════════════════════════════════════════════════════════════════════════════

def show_operador():
    if not st.session_state.operador_ok:
        ir_a("operador_login")
        return

    op = st.session_state.get("operador_info", {})
    permisos = op.get("permisos", ["reservas","pagos","voucher"])
    es_admin = "admin" in permisos or op.get("rol") == "admin"

    # Auto-rerun: cada 30s en Dashboard, cada 60s en Cubículos
    now_ts = int(time.time())
    last_rerun = st.session_state.get("_op_last_rerun", 0)
    current_mod = st.session_state.get("modulo_op_radio", "🏠 Dashboard")
    rerun_interval = 60 if current_mod == "🏠 Dashboard" else 120
    if last_rerun == 0:
        st.session_state["_op_last_rerun"] = now_ts
    elif now_ts - last_rerun >= rerun_interval:
        if current_mod in ("🏠 Dashboard", "🛏️ Cubículos"):
            st.session_state["_op_last_rerun"] = now_ts
            st.rerun()

    # Sidebar
    with st.sidebar:
        st.markdown(f"## 💤 {NEGOCIO}")
        #st.divider()

        # Reloj en el sidebar (actualizado por JS iframe)
        inject_live_clock()
        ahora_sb = ahora_col()
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:8px">
          <div class="jjgt-clock-hms" style="font-family:'Inconsolata',monospace;
               font-size:28px;font-weight:700;color:#00d4ff;
               text-shadow:0 0 12px rgba(0,212,255,0.5)">
            {ahora_sb.strftime('%H:%M:%S')}
          </div>
          <div class="jjgt-clock-fecha" style="font-size:11px;color:#94a3b8;
               letter-spacing:1px;text-transform:uppercase">
            {ahora_sb.strftime('%a %d/%m/%Y').upper()}
          </div>
        </div>
        """, unsafe_allow_html=True)
        #st.divider()

        # Info del operador activo
        turno_icons = {"mañana":"☀️","tarde":"🌤️","noche":"🌙","diurno":"☀️","admin":"👑"}
        t_icon = turno_icons.get(op.get("turno",""), "👤")
        st.markdown(f"""
        <div style="background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.3);
                    border-radius:10px;padding:12px;margin-bottom:8px">
          <div style="font-weight:700;color:#00d4ff">{t_icon} {op.get("nombre","Operador")}</div>
          <div style="font-size:12px;color:#94a3b8">Turno: {op.get("turno","").capitalize()}</div>
          <div style="font-size:12px;color:#94a3b8">{op.get("hora_inicio_turno","--")} → {op.get("hora_fin_turno","--")}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:4px">Rol: {op.get("rol","cajero").capitalize()}</div>
        </div>
        """, unsafe_allow_html=True)

        # Módulos filtrados por permisos
        todos_modulos = [
            ("🏠 Dashboard",        True),
            ("➕ Nueva Reserva",     "reservas" in permisos or es_admin),
            ("🛏️ Cubículos",        "reservas" in permisos or es_admin),
            ("⏳ Pagos Pendientes",  "pagos"    in permisos or es_admin),
            ("📊 Reportes",         "reportes"  in permisos or es_admin),
            ("🗑️ Gestión de Datos", es_admin),
            ("☁️ Google Drive",     es_admin),
            ("⚙️ Configuración",    "configuracion" in permisos or es_admin),
        ]
        modulos_visibles = [m for m, visible in todos_modulos if visible]

        modulo = st.radio("Módulo", modulos_visibles, key="modulo_op_radio")
        st.divider()

        drive_ok = GSPREAD_AVAILABLE and bool(get_config("drive_spreadsheet_id",""))
        st.caption("🟢 Sync Drive activa" if drive_ok else "🔴 Drive sin configurar")

        if st.button("🚪 Cerrar sesión", use_container_width=True):
            # Backup al cierre de turno (solo local)
            _backup_cierre_turno(op)
            st.session_state.operador_ok   = False
            st.session_state.operador_info = {}
            ir_a("operador_login")

    render_header(f"Panel — {op.get('nombre','Operador')}")

    mod_map = {
        "🏠 Dashboard":        _op_dashboard,
        "➕ Nueva Reserva":    _op_nueva_reserva,
        "🛏️ Cubículos":        _op_cubiculos,
        "⏳ Pagos Pendientes":  _op_pagos_pendientes,
        "📊 Reportes":         _op_reportes,
        "🗑️ Gestión de Datos": _op_gestion_datos,
        "☁️ Google Drive":     _op_google_drive,
        "⚙️ Configuración":    _op_configuracion,
    }
    mod_map.get(modulo, _op_dashboard)()


def _op_nueva_reserva():
    """
    Módulo del panel de operador para crear una reserva.
    Dos modos:
    - Rápido (inline): formulario completo en el panel — ideal para operadores
    - Kiosk: activa el flujo del kiosco público paso a paso
    """
    st.markdown("### ➕ Nueva Reserva")
    op = st.session_state.get("operador_info", {})
    st.caption(f"Operador: **{op.get('nombre','—')}** · Turno: {op.get('turno','—')}")

    tab_rapido, tab_kiosk = st.tabs(["⚡ Formulario Rápido", "🖥️ Flujo Kiosco"])

    # ── TAB KIOSCO ────────────────────────────────────────────────────────────
    with tab_kiosk:
        st.markdown("Activa el flujo completo del kiosco táctil paso a paso.")
        st.info("El cliente selecciona cubículo, ingresa sus datos y elige método de pago.")
        cubiculos_k = get_cubiculos_libres()
        if cubiculos_k:
            if st.button("🛏️ INICIAR FLUJO KIOSCO", type="primary",
                         use_container_width=True, key="btn_kiosco_flow"):
                st.session_state["cubiculo_sel"]    = None
                st.session_state["horas_sel"]       = 1.0
                st.session_state["calc"]            = None
                st.session_state["cliente"]         = {}
                st.session_state["metodo_pago"]     = None
                st.session_state["voucher"]         = None
                st.session_state["pago_confirmado"] = False
                ir_a("seleccion")
        else:
            st.error("❌ No hay cubículos disponibles en este momento.")

    # ── TAB FORMULARIO RÁPIDO ─────────────────────────────────────────────────
    with tab_rapido:
        st.markdown("**Formulario rápido de asignación directa:**")

        # Paso 1: Cubículo y tiempo
        st.markdown("#### 🛏️ Paso 1 — Cubículo y tiempo")
        cubiculos_libres = get_cubiculos_libres()
        if not cubiculos_libres:
            st.error("❌ No hay cubículos disponibles.")
            return

        col_cub, col_hrs = st.columns(2)
        with col_cub:
            opciones_cub = {f"{c['numero']} — {c['nombre']}": c for c in cubiculos_libres}
            sel_label    = st.selectbox("Cubículo libre", list(opciones_cub.keys()),
                                        key="op_res_cubiculo")
            cubiculo_sel = opciones_cub[sel_label]

        with col_hrs:
            horas_sel = st.number_input("Horas a reservar",
                                        min_value=0.3, max_value=12.0,
                                        value=1.0, step=0.3, key="op_res_horas")
            calc = calcular_precio(horas_sel)
            st.markdown(f"""
            <div style="background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);
                        border-radius:8px;padding:10px;margin-top:8px;font-size:14px">
              Subtotal: <b>{fmt_cop(calc['subtotal'])}</b> ·
              IVA 19%: <b>{fmt_cop(calc['iva'])}</b><br>
              <b style="color:#00ff88;font-size:16px">Total: {fmt_cop(calc['total'])} COP</b>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Paso 2: Datos del cliente
        st.markdown("#### 👤 Paso 2 — Datos del cliente")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre   = st.text_input("Nombre completo *", key="op_res_nombre",
                                       placeholder="Nombre del pasajero")
            c_tel      = st.text_input("Teléfono", key="op_res_tel",
                                       placeholder="300 000 0000")
            c_tipo_doc = st.selectbox("Tipo documento",
                                      ["CC","CE","Pasaporte","NIT","TI"],
                                      key="op_res_tipodoc")
        with col_c2:
            c_doc   = st.text_input("Número de documento", key="op_res_doc")
            c_email = st.text_input("Email (opcional)", key="op_res_email")
            req_fact = st.checkbox("¿Requiere factura empresarial?",
                                   key="op_res_req_fact")

        razon_social = ""
        nit_empresa  = ""
        if req_fact:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                razon_social = st.text_input("Razón social", key="op_res_razon")
            with col_f2:
                nit_empresa  = st.text_input("NIT empresa",  key="op_res_nit")

        st.divider()

        # Paso 3: Método de pago con QR
        st.markdown("#### 💳 Paso 3 — Método de pago")
        metodo_pago = st.selectbox("Método de pago", METODOS_PAGO,
                                   key="op_res_metodo")

        monto_total = int(calc["total"])
        # Referencia única para este intento de pago
        ref_pago = f"OP-{ahora_col().strftime('%Y%m%d%H%M')}-{cubiculo_sel['numero'].replace('#','')}"

        # Mostrar QR según método
        METODOS_CON_QR = ["Nequi", "Daviplata", "PSE", "MercadoPago", "Transferencia"]
        if metodo_pago in METODOS_CON_QR:
            st.markdown(f"**Monto a cobrar:** `{fmt_cop(monto_total)} COP`")
            mostrar_qr(metodo_pago, monto_total, ref_pago, size=220)
            st.caption(f"Referencia: `{ref_pago}`")
        elif metodo_pago == "Efectivo":
            st.markdown(f"""
            <div style="background:rgba(132,204,22,0.1);border:1px solid rgba(132,204,22,0.3);
                        border-radius:10px;padding:16px;text-align:center">
              <div style="font-size:13px;color:#94a3b8;margin-bottom:4px">TOTAL EN EFECTIVO</div>
              <div style="font-size:36px;font-weight:700;color:#84cc16">{fmt_cop(monto_total)} COP</div>
            </div>
            """, unsafe_allow_html=True)
        else:  # Tarjeta
            st.info(f"💳 Procesar {fmt_cop(monto_total)} COP en el datáfono antes de confirmar.")

        referencia = st.text_input("Referencia / número de comprobante de pago",
                                   key="op_res_ref",
                                   placeholder="Ingresa el número de transacción o comprobante")

        st.divider()

        # Paso 4: Confirmar
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            btn_label = "✅ CONFIRMAR PAGO Y CREAR RESERVA"
            if st.button(btn_label, type="primary",
                         use_container_width=True, key="op_res_confirmar"):
                if not c_nombre.strip():
                    st.error("⚠️ El nombre del cliente es obligatorio.")
                elif metodo_pago in METODOS_CON_QR and not referencia.strip():
                    st.warning("⚠️ Se recomienda ingresar la referencia de pago para métodos digitales.")
                    # Permitir continuar igualmente (warning, no error)
                    cliente_data = {
                        "nombre":           c_nombre.strip(),
                        "tipo_doc":         c_tipo_doc,
                        "numero_documento": c_doc.strip(),
                        "telefono":         c_tel.strip(),
                        "email":            c_email.strip(),
                        "razon_social":     razon_social.strip(),
                        "nit_empresa":      nit_empresa.strip(),
                    }
                    with st.spinner("Creando reserva..."):
                        try:
                            voucher = crear_reserva_completa(
                                cubiculo_sel, cliente_data, calc, metodo_pago)
                            st.session_state["_op_last_voucher"] = voucher
                            st.session_state["_op_voucher_ref"]  = referencia or ref_pago
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    cliente_data = {
                        "nombre":           c_nombre.strip(),
                        "tipo_doc":         c_tipo_doc,
                        "numero_documento": c_doc.strip(),
                        "telefono":         c_tel.strip(),
                        "email":            c_email.strip(),
                        "razon_social":     razon_social.strip(),
                        "nit_empresa":      nit_empresa.strip(),
                    }
                    with st.spinner("Creando reserva y sincronizando..."):
                        try:
                            voucher = crear_reserva_completa(
                                cubiculo_sel, cliente_data, calc, metodo_pago)
                            st.session_state["_op_last_voucher"] = voucher
                            st.session_state["_op_voucher_ref"]  = referencia or ref_pago
                            st.success(
                                f"✅ Reserva **{voucher['numero_reserva']}** creada — "
                                f"Cubículo **{voucher['cubiculo']}** activado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al crear reserva: {e}")
        with col_btn2:
            if st.button("🔄 Limpiar formulario", use_container_width=True,
                         key="op_res_limpiar"):
                for k in ["op_res_nombre","op_res_tel","op_res_doc","op_res_email",
                          "_op_last_voucher","_op_voucher_ref"]:
                    st.session_state.pop(k, None)
                st.rerun()

        # ── Voucher de última reserva ──────────────────────────────────────────
        last_v = st.session_state.get("_op_last_voucher")
        if last_v:
            st.divider()
            st.markdown("#### 🎫 Voucher — Última reserva creada")
            col_v1, col_v2 = st.columns([2, 1])
            with col_v1:
                ref_op = st.session_state.get("_op_voucher_ref","")
                st.markdown(f"""
                <div class="voucher-box" style="max-width:100%">
                  <div style="text-align:center;margin-bottom:12px">
                    <div style="font-size:18px;font-weight:800;color:#00d4ff">{NEGOCIO}</div>
                    <div style="font-size:12px;color:#94a3b8">Reserva creada por operador</div>
                  </div>
                  <table style="width:100%;font-size:14px;border-collapse:collapse">
                    <tr><td style="color:#94a3b8;padding:3px 0">Reserva</td>
                        <td style="text-align:right;font-family:'Inconsolata';font-weight:700">{last_v["numero_reserva"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Factura</td>
                        <td style="text-align:right;font-family:'Inconsolata'">{last_v["numero_factura"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Cliente</td>
                        <td style="text-align:right;font-weight:700">{last_v["cliente_nombre"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Cubículo</td>
                        <td style="text-align:right;font-size:18px;color:#00d4ff;font-weight:700">{last_v["cubiculo"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Horario</td>
                        <td style="text-align:right">{last_v["hora_inicio"]} → {last_v["hora_fin"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">WiFi</td>
                        <td style="text-align:right;font-family:'Inconsolata'">{last_v["wifi_ssid"]} / {last_v["wifi_password"]}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Método</td>
                        <td style="text-align:right">{last_v["metodo_pago"]}{(" · " + ref_op) if ref_op else ""}</td></tr>
                    <tr><td style="color:#94a3b8;padding:3px 0">Total</td>
                        <td style="text-align:right;font-size:18px;font-weight:700;color:#00ff88">{fmt_cop(last_v["total"])} COP</td></tr>
                  </table>
                  <div style="text-align:center;margin-top:16px">
                    <div style="font-size:12px;color:#94a3b8;letter-spacing:2px;text-transform:uppercase">CÓDIGO DE ACCESO</div>
                    <div style="font-family:'Inconsolata';font-size:56px;font-weight:700;
                                color:#00ff88;letter-spacing:12px;
                                text-shadow:0 0 30px rgba(0,255,136,0.6)">{last_v["codigo_acceso"]}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            with col_v2:
                if REPORTLAB_AVAILABLE:
                    pdf_b = generar_ticket_pdf(last_v)
                    if pdf_b:
                        st.download_button("📄 Imprimir PDF",
                                           data=pdf_b,
                                           file_name=f"ticket_{last_v['numero_reserva']}.pdf",
                                           mime="application/pdf",
                                           use_container_width=True)
                html_v_str = voucher_html(last_v)
                st.download_button("🌐 Voucher HTML",
                                   data=html_v_str.encode(),
                                   file_name=f"voucher_{last_v['numero_reserva']}.html",
                                   mime="text/html",
                                   use_container_width=True)
                wa_msg = (f"JJGT Reserva {last_v['numero_reserva']} | "
                          f"Cubículo {last_v['cubiculo']} | "
                          f"Código: {last_v['codigo_acceso']} | "
                          f"WiFi: {last_v['wifi_ssid']} Clave: {last_v['wifi_password']} | "
                          f"Total: {fmt_cop(last_v['total'])} COP")
                wa_url = f"https://wa.me/?text={wa_msg.replace(' ','%20')}"
                st.markdown(
                    f'''<a href="{wa_url}" target="_blank">
                    <button style="width:100%;padding:12px;margin-top:8px;
                      background:rgba(37,211,102,0.2);border:2px solid rgba(37,211,102,0.5);
                      border-radius:12px;color:#25d366;font-weight:700;font-size:15px;
                      cursor:pointer">📱 Enviar WhatsApp</button></a>''',
                    unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🆕 Nueva reserva", use_container_width=True,
                             key="op_res_nueva", type="primary"):
                    for k in ["_op_last_voucher","_op_voucher_ref"]:
                        st.session_state.pop(k, None)
                    st.rerun()


def _op_dashboard():
    st.markdown("### 🏠 Dashboard Operacional")
    inject_live_clock()
    # El rerun automático del dashboard se maneja en show_operador() cada 30s
    cubiculos = get_cubiculos()
    libres    = sum(1 for c in cubiculos if c["estado"] == "libre")
    ocupados  = sum(1 for c in cubiculos if c["estado"] == "ocupado")
    manten    = sum(1 for c in cubiculos if c["estado"] == "mantenimiento")

    # ── Auto-liberar cubículos con tiempo vencido + alarma ────────────────────
    vencidos = []
    for cub in cubiculos:
        if cub["estado"] in ("ocupado", "por_liberar"):
            mins = cub.get("minutos_restantes")
            if mins is not None and mins <= 0:
                liberar_cubiculo(cub["id"])
                vencidos.append(cub["numero"])

    if vencidos:
        # Sonido de alarma (beeps repetidos via Web Audio API)
        st.markdown(f"""
        <div class="alerta-roja">
          🔔 ¡TIEMPO VENCIDO! Cubículos liberados automáticamente: <b>{', '.join(vencidos)}</b>
        </div>
        <script>
        (function(){{
          try {{
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            function beep(freq, start, dur) {{
              var o = ctx.createOscillator();
              var g = ctx.createGain();
              o.connect(g); g.connect(ctx.destination);
              o.frequency.value = freq;
              o.type = 'square';
              g.gain.setValueAtTime(0.3, ctx.currentTime + start);
              g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
              o.start(ctx.currentTime + start);
              o.stop(ctx.currentTime + start + dur + 0.05);
            }}
            for(var i=0; i<5; i++) {{ beep(880, i*0.4, 0.3); beep(660, i*0.4+0.15, 0.15); }}
          }} catch(e) {{}}
        }})();
        </script>
        """, unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    con = get_db()
    today = ahora_col().strftime("%Y-%m-%d")
    ingresos_hoy = con.execute(
        "SELECT COALESCE(SUM(total),0) FROM reservas WHERE DATE(creado_en)=? AND estado_pago='confirmado'",
        (today,)).fetchone()[0]
    reservas_hoy = con.execute(
        "SELECT COUNT(*) FROM reservas WHERE DATE(creado_en)=? AND estado_pago='confirmado'",
        (today,)).fetchone()[0]
    pend = con.execute(
        "SELECT COUNT(*) FROM pagos WHERE estado='pendiente'").fetchone()[0]
    con.close()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🟢 Libres",    libres)
    c2.metric("🔴 Ocupados",  ocupados)
    c3.metric("🔧 Mantenim.", manten)
    c4.metric("💰 Ingresos hoy", fmt_cop(ingresos_hoy))
    c5.metric("📋 Reservas hoy", reservas_hoy)

    if pend > 0:
        st.warning(f"⚠️ {pend} pago(s) pendientes de confirmación")

    st.markdown("---")
    st.markdown("#### Estado en tiempo real")
    inject_live_clock()
    # Recargar cubículos frescos post-liberaciones
    cubiculos = get_cubiculos()
    cols = st.columns(4)
    for i, cub in enumerate(cubiculos):
        with cols[i % 4]:
            estado    = cub["estado"]
            info      = ESTADOS_CUBICULO.get(estado, ESTADOS_CUBICULO["libre"])
            mins      = cub.get("minutos_restantes")
            hora_fin  = cub.get("hora_fin") or ""
            alerta_prefix = "⚠️ " if (mins is not None and 0 < mins <= 5) else ""
            # Timer HTML con data-fin para actualización JS en tiempo real
            if hora_fin and estado not in ("libre", "mantenimiento"):
                timer_html = (
                    f'<div class="jjgt-timer" data-fin="{hora_fin}" ' +
                    f'data-key="dash-{cub["id"]}" ' +
                    f'style="font-size:13px;color:{"#ff4757" if (mins or 999)<=5 else "#ffd32a" if (mins or 999)<=15 else "#00ff88"};">' +
                    f'⏱ {fmt_tiempo(mins)}</div>'
                )
            else:
                timer_html = ""
            st.markdown(f"""
            <div style="background:{info['bg']};border:1.5px solid {info['color']}55;
                        border-radius:10px;padding:12px;text-align:center;margin-bottom:8px">
              <div style="font-family:'Inconsolata';font-size:28px;
                          font-weight:700;color:{info['color']}">{alerta_prefix}{cub['numero']}</div>
              <div style="font-size:10px;font-weight:700;color:{info['color']};
                          letter-spacing:1px">{info['label']}</div>
              {timer_html}
            </div>
            """, unsafe_allow_html=True)


def _op_cubiculos():
    st.markdown("### 🛏️ Gestión de Cubículos")
    cubiculos = get_cubiculos()

    # Auto-liberar vencidos con alarma
    for cub in cubiculos:
        if cub["estado"] in ("ocupado", "por_liberar"):
            mins = cub.get("minutos_restantes")
            if mins is not None and mins <= 0:
                liberar_cubiculo(cub["id"])
                st.markdown(f"""
                <div class="alerta-roja">🔔 Cubículo {cub["numero"]} liberado automáticamente (tiempo vencido)</div>
                <script>
                (function(){{try{{var ctx=new(window.AudioContext||window.webkitAudioContext)();
                function b(f,s,d){{var o=ctx.createOscillator(),g=ctx.createGain();
                o.connect(g);g.connect(ctx.destination);o.frequency.value=f;o.type="square";
                g.gain.setValueAtTime(0.3,ctx.currentTime+s);
                g.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+s+d);
                o.start(ctx.currentTime+s);o.stop(ctx.currentTime+s+d+0.05);}}
                for(var i=0;i<5;i++){{b(880,i*0.4,0.3);b(660,i*0.4+0.15,0.15);}}
                }}catch(e){{}}}})()</script>
                """, unsafe_allow_html=True)
    cubiculos = get_cubiculos()  # refrescar después de liberaciones

    for cub in cubiculos:
        estado = cub["estado"]
        info   = ESTADOS_CUBICULO.get(estado, ESTADOS_CUBICULO["libre"])
        mins   = cub.get("minutos_restantes")
        label_exp = f"{cub['numero']} — {info['label']} | WiFi: {cub['wifi_ssid']}"
        if mins is not None and mins <= 10 and estado != "libre":
            label_exp += f" ⚠️ {fmt_tiempo(mins)}"
        with st.expander(label_exp):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if estado in ("ocupado", "por_liberar") and st.button(f"🔓 Liberar {cub['numero']}",
                                                     key=f"lib_{cub['id']}"):
                    liberar_cubiculo(cub["id"])
                    st.success(f"Cubículo {cub['numero']} liberado")
                    st.rerun()
            with c2:
                if estado != "mantenimiento":
                    if st.button(f"🔧 Mantenimiento {cub['numero']}",
                                 key=f"mant_{cub['id']}"):
                        con = get_db()
                        con.execute("UPDATE cubiculos SET estado='mantenimiento' WHERE id=?",
                                    (cub["id"],))
                        con.commit()
                        con.close()
                        _, sh_mant = get_active_client()
                        if sh_mant:
                            gs_sync_cubiculos(sh_mant)
                        st.rerun()
                else:
                    if st.button(f"✅ Listo {cub['numero']}", key=f"ok_{cub['id']}"):
                        con = get_db()
                        con.execute("UPDATE cubiculos SET estado='libre' WHERE id=?",
                                    (cub["id"],))
                        con.commit()
                        con.close()
                        _, sh_ok = get_active_client()
                        if sh_ok:
                            gs_sync_cubiculos(sh_ok)
                        st.rerun()
            with c3:
                new_wifi_pw = st.text_input("Nueva clave WiFi",
                                            value=cub["wifi_password"],
                                            key=f"wifi_{cub['id']}")
            with c4:
                if st.button(f"💾 Guardar WiFi", key=f"swifi_{cub['id']}"):
                    con = get_db()
                    con.execute("UPDATE cubiculos SET wifi_password=? WHERE id=?",
                                (new_wifi_pw, cub["id"]))
                    con.commit()
                    con.close()
                    _, sh_wifi = get_active_client()
                    if sh_wifi:
                        gs_sync_cubiculos(sh_wifi)
                    st.success("WiFi actualizado")
                    st.rerun()
            if cub.get("minutos_restantes") is not None:
                st.info(f"⏱ Tiempo restante: {fmt_tiempo(cub['minutos_restantes'])}")


def _op_pagos_pendientes():
    st.markdown("### ⏳ Pagos Pendientes de Confirmación")
    con = get_db()
    rows = con.execute("""
        SELECT p.id, p.reserva_id, r.numero_reserva, c.nombre, r.numero_reserva,
               r.cubiculo_id, p.monto, p.metodo, p.fecha_pago, r.horas_contratadas
        FROM pagos p
        JOIN reservas r ON p.reserva_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE p.estado = 'pendiente'
        ORDER BY p.id DESC
    """).fetchall()
    con.close()

    if not rows:
        st.success("✅ No hay pagos pendientes en este momento.")
        return

    for row in rows:
        pago_id, res_id, num_res, cliente, _, cub_id, monto, metodo, fecha, horas = row
        with st.container():
            st.markdown(f"""
            <div style="background:rgba(255,211,42,0.1);border:1px solid rgba(255,211,42,0.4);
                        border-radius:12px;padding:16px;margin-bottom:12px">
              <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
                <div>
                  <b style="color:#ffd32a">{num_res}</b> · {cliente}<br>
                  <span style="color:#94a3b8">{metodo} · {fmt_cop(monto)} COP · {horas}h</span>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                pin_conf = st.text_input("PIN para confirmar", type="password",
                                         key=f"pin_conf_{pago_id}", max_chars=8)
                if st.button(f"✅ CONFIRMAR PAGO", key=f"conf_{pago_id}",
                             type="primary", use_container_width=True):
                    if verificar_pin(pin_conf):
                        con2 = get_db()
                        con2.execute("UPDATE pagos SET estado='confirmado', confirmado_por='operador' WHERE id=?",
                                     (pago_id,))
                        con2.execute("UPDATE reservas SET estado_pago='confirmado' WHERE id=?",
                                     (res_id,))
                        con2.commit()
                        con2.close()
                        st.success(f"✅ Pago {num_res} confirmado")
                        _, sh_conf = get_active_client()
                        if sh_conf:
                            gs_escribir_pago(sh_conf, {
                                "id": pago_id, "reserva_id": res_id,
                                "num_reserva": num_res, "fecha_pago": "",
                                "monto": monto, "metodo": metodo,
                                "referencia_externa": "", "estado": "confirmado",
                                "confirmado_por": "operador", "notas": "",
                            })
                            gs_sync_cubiculos(sh_conf)
                            gs_sync_dashboard(sh_conf)
                        st.rerun()
                    else:
                        st.error("PIN incorrecto")
            with c2:
                if st.button(f"❌ Rechazar", key=f"rej_{pago_id}", use_container_width=True):
                    con2 = get_db()
                    con2.execute("UPDATE pagos SET estado='rechazado' WHERE id=?", (pago_id,))
                    con2.execute("UPDATE reservas SET estado_pago='rechazado' WHERE id=?", (res_id,))
                    con2.execute("UPDATE cubiculos SET estado='libre',reserva_activa_id=NULL WHERE id=?",
                                 (cub_id,))
                    con2.commit()
                    con2.close()
                    st.warning("Pago rechazado y cubículo liberado")
                    _, sh_rej = get_active_client()
                    if sh_rej:
                        gs_escribir_pago(sh_rej, {
                            "id": pago_id, "reserva_id": res_id,
                            "num_reserva": num_res, "fecha_pago": "",
                            "monto": monto, "metodo": metodo,
                            "referencia_externa": "", "estado": "rechazado",
                            "confirmado_por": "operador", "notas": "",
                        })
                        gs_sync_cubiculos(sh_rej)
                        gs_sync_dashboard(sh_rej)
                    st.rerun()


def generar_backup_diario() -> bytes:
    """
    Genera un backup completo de la BD en formato Excel (.xlsx) con una hoja por tabla.
    Si openpyxl no está disponible, cae a CSV ZIP.
    """
    now_str = ahora_col().strftime("%Y-%m-%d_%H%M")
    tablas  = ["reservas", "pagos", "clientes", "facturas", "factura_items",
               "cubiculos", "tarifas", "operadores", "configuracion_pagos"]
    con = get_db()

    if OPENPYXL_AVAILABLE:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for tabla in tablas:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {tabla}", con)
                    df.to_excel(writer, sheet_name=tabla[:31], index=False)
                except Exception:
                    pass
        con.close()
        return buf.getvalue(), f"backup_jjgt_{now_str}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for tabla in tablas:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {tabla}", con)
                    zf.writestr(f"{tabla}.csv", df.to_csv(index=False))
                except Exception:
                    pass
        con.close()
        return buf.getvalue(), f"backup_jjgt_{now_str}.zip", "application/zip"


def _op_reportes():
    st.markdown("### 📊 Reportes")
    periodo = st.selectbox("Período", ["Hoy", "Esta semana", "Este mes", "Histórico"])
    today   = ahora_col()

    if periodo == "Hoy":
        desde = today.strftime("%Y-%m-%d")
        hasta = desde
    elif periodo == "Esta semana":
        desde = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        hasta = today.strftime("%Y-%m-%d")
    elif periodo == "Este mes":
        desde = today.strftime("%Y-%m-01")
        hasta = today.strftime("%Y-%m-%d")
    else:
        desde = "2020-01-01"
        hasta = today.strftime("%Y-%m-%d")

    con  = get_db()
    rows = con.execute("""
        SELECT r.numero_reserva, c.nombre, cu.numero, r.horas_contratadas,
               r.total, r.metodo_pago, r.estado_pago, r.creado_en
        FROM reservas r
        JOIN clientes c ON r.cliente_id = c.id
        JOIN cubiculos cu ON r.cubiculo_id = cu.id
        WHERE DATE(r.creado_en) BETWEEN ? AND ?
        ORDER BY r.id DESC
    """, (desde, hasta)).fetchall()

    total_ing = sum(row[4] for row in rows if row[6] == "confirmado")
    total_res = len(rows)
    completadas = sum(1 for row in rows if row[6] == "confirmado")

    con.close()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total reservas",    total_res)
    c2.metric("Completadas",       completadas)
    c3.metric("Ingresos",          fmt_cop(total_ing))

    if rows:
        df = pd.DataFrame(rows, columns=[
            "Reserva","Cliente","Cubículo","Horas","Total","Método","Estado","Fecha"])
        df["Total"] = df["Total"].apply(fmt_cop)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Exportar período
        csv = pd.DataFrame(rows, columns=[
            "Reserva","Cliente","Cubículo","Horas","Total","Método","Estado","Fecha"
        ]).to_csv(index=False).encode()
        st.download_button("📥 Exportar CSV del período", data=csv,
                           file_name=f"reservas_{desde}_{hasta}.csv",
                           mime="text/csv")

        # Gráfico métodos de pago
        try:
            import plotly.express as px
            metodos_df = pd.DataFrame(rows, columns=[
                "Reserva","Cliente","Cubículo","Horas","Total","Método","Estado","Fecha"])
            metodos_df = metodos_df[metodos_df["Estado"] == "confirmado"]
            if not metodos_df.empty:
                fig = px.pie(metodos_df, names="Método", values="Total",
                             title="Distribución por método de pago",
                             template="plotly_dark",
                             color_discrete_sequence=["#00d4ff","#3b82f6","#00ff88",
                                                      "#ffd32a","#a29bfe","#f43f5e"])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.markdown("*(Instala plotly para ver gráficas: `pip install plotly`)*")
    else:
        st.info("No hay reservas para el período seleccionado.")

    # ── Descarga completa de toda la información ──────────────────────────────
    st.divider()
    st.markdown("#### 💾 Backup y Descarga Completa")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.markdown("**Backup diario completo** (todas las tablas)")
        if st.button("🗂️ Generar backup ahora", use_container_width=True):
            with st.spinner("Generando backup..."):
                backup_data, backup_name, backup_mime = generar_backup_diario()
            st.download_button(
                f"📥 Descargar {backup_name}",
                data=backup_data,
                file_name=backup_name,
                mime=backup_mime,
                use_container_width=True
            )
    with col_b2:
        st.markdown("**Exportar toda la información** (reservas históricas)")
        if st.button("📊 Exportar historial completo CSV", use_container_width=True):
            con_all = get_db()
            df_all = pd.read_sql_query("""
                SELECT r.numero_reserva, c.nombre AS cliente, c.tipo_documento,
                       c.numero_documento, c.telefono, c.email,
                       cu.numero AS cubiculo,
                       r.horas_contratadas, r.hora_inicio, r.hora_fin_programada,
                       r.hora_fin_real, r.precio_hora, r.subtotal, r.iva, r.total,
                       r.metodo_pago, r.estado_pago, r.codigo_acceso,
                       r.creado_en, f.numero AS factura
                FROM reservas r
                LEFT JOIN clientes c ON r.cliente_id = c.id
                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                LEFT JOIN facturas f ON r.factura_id = f.id
                ORDER BY r.id DESC
            """, con_all)
            con_all.close()
            csv_all = df_all.to_csv(index=False).encode()
            st.download_button(
                f"📥 Descargar historial_{ahora_col().strftime('%Y%m%d')}.csv",
                data=csv_all,
                file_name=f"historial_jjgt_{ahora_col().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )



def _op_gestion_datos():
    """
    Módulo de gestión de datos — permite al admin eliminar registros
    de reservas, pagos, clientes y facturas en cualquier momento.
    Solo accesible para operadores con rol admin.
    """
    st.markdown("### 🗑️ Gestión de Datos")
    st.warning("⚠️ **Zona de administración** — Las eliminaciones son permanentes e irreversibles.")

    op = st.session_state.get("operador_info", {})
    if op.get("rol") != "admin" and "admin" not in op.get("permisos", []):
        st.error("❌ Solo los administradores pueden acceder a esta sección.")
        return

    tab_res, tab_cli, tab_pag, tab_fact = st.tabs([
        "📋 Reservas", "👤 Clientes", "💰 Pagos", "🧾 Facturas"])

    # ── RESERVAS ──────────────────────────────────────────────────────────────
    with tab_res:
        st.markdown("#### Eliminar reservas")
        con = get_db()
        rows_r = con.execute("""
            SELECT r.id, r.numero_reserva, c.nombre, cu.numero,
                   r.hora_inicio, r.hora_fin_programada, r.total,
                   r.estado_pago, r.creado_en
            FROM reservas r
            LEFT JOIN clientes c  ON r.cliente_id  = c.id
            LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
            ORDER BY r.id DESC LIMIT 100
        """).fetchall()
        con.close()

        if not rows_r:
            st.info("No hay reservas registradas.")
        else:
            df_r = pd.DataFrame(rows_r, columns=[
                "ID","Número","Cliente","Cubículo",
                "Inicio","Fin Prog.","Total","Estado","Creada"])
            df_r["Total"] = df_r["Total"].apply(lambda x: fmt_cop(float(x)) if x else "")
            st.dataframe(df_r, use_container_width=True, hide_index=True)

            st.markdown("**Eliminar reserva específica:**")
            col_r1, col_r2 = st.columns([2,1])
            with col_r1:
                nums_r = [r[1] for r in rows_r]
                sel_num_r = st.selectbox("Seleccionar reserva", nums_r, key="del_res_sel")
            with col_r2:
                pin_del_r = st.text_input("PIN admin para confirmar",
                                          type="password", key="del_res_pin")
            if st.button("🗑️ ELIMINAR RESERVA SELECCIONADA", type="primary",
                         use_container_width=True, key="btn_del_res"):
                if not verificar_pin(pin_del_r, "admin"):
                    st.error("❌ PIN admin incorrecto")
                else:
                    con2 = get_db()
                    # Obtener ID y cubiculo_id para limpiar estado
                    row_to_del = con2.execute(
                        "SELECT id, cubiculo_id FROM reservas WHERE numero_reserva=?",
                        (sel_num_r,)).fetchone()
                    if row_to_del:
                        res_id, cub_id = row_to_del
                        con2.execute("DELETE FROM pagos    WHERE reserva_id=?", (res_id,))
                        con2.execute("DELETE FROM factura_items WHERE factura_id IN "
                                     "(SELECT id FROM facturas WHERE numero IN "
                                     "(SELECT numero FROM reservas WHERE id=?))", (res_id,))
                        con2.execute("DELETE FROM reservas WHERE id=?", (res_id,))
                        # Liberar cubículo si estaba activo
                        con2.execute(
                            "UPDATE cubiculos SET estado='libre', reserva_activa_id=NULL, "
                            "hora_disponible=NULL WHERE id=? AND reserva_activa_id=?",
                            (cub_id, res_id))
                        con2.commit()
                    con2.close()
                    st.success(f"✅ Reserva {sel_num_r} eliminada correctamente")
                    _, sh_del = get_active_client()
                    if sh_del:
                        gs_sync_cubiculos(sh_del)
                        gs_sync_factura_items(sh_del)
                        # Sync Reservas y Pagos
                        try:
                            con_sd = get_db()
                            rows_rd = con_sd.execute("""
                                SELECT r.id, r.numero_reserva, r.creado_en, cu.numero,
                                       cl.nombre, cl.numero_documento, cl.telefono, cl.email,
                                       r.horas_contratadas, r.hora_inicio, r.hora_fin_programada,
                                       r.hora_fin_real, r.precio_hora, r.subtotal, r.iva, r.total,
                                       r.metodo_pago, r.estado_pago, r.codigo_acceso,
                                       cu.wifi_ssid, cu.wifi_password,
                                       f.numero, r.referencia_pago, 'sistema', r.notas
                                FROM reservas r
                                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                                LEFT JOIN clientes cl ON r.cliente_id = cl.id
                                LEFT JOIN facturas f ON r.factura_id = f.id
                                ORDER BY r.id
                            """).fetchall()
                            rows_pd = con_sd.execute("""
                                SELECT p.id, p.reserva_id, r.numero_reserva, p.fecha_pago,
                                       p.monto, p.metodo, p.referencia_externa,
                                       p.estado, p.confirmado_por, p.notas
                                FROM pagos p LEFT JOIN reservas r ON p.reserva_id = r.id
                                ORDER BY p.id
                            """).fetchall()
                            con_sd.close()
                            ws_rd = _gs_get_or_create_ws(sh_del, "Reservas")
                            ws_rd.clear()
                            _gs_update_range(ws_rd, "A1", [DRIVE_SHEETS["Reservas"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_rd])
                            ws_pd = _gs_get_or_create_ws(sh_del, "Pagos")
                            ws_pd.clear()
                            _gs_update_range(ws_pd, "A1", [DRIVE_SHEETS["Pagos"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_pd])
                        except Exception as _ed:
                            st.warning(f"⚠️ Error sync Reservas/Pagos tras eliminar: {_ed}")
                    st.rerun()

    # ── CLIENTES ──────────────────────────────────────────────────────────────
    with tab_cli:
        st.markdown("#### Eliminar clientes")
        con = get_db()
        rows_c = con.execute(
            "SELECT id, nombre, tipo_documento, numero_documento, telefono, creado_en "
            "FROM clientes ORDER BY id DESC LIMIT 100").fetchall()
        con.close()

        if not rows_c:
            st.info("No hay clientes registrados.")
        else:
            df_c = pd.DataFrame(rows_c, columns=["ID","Nombre","Tipo Doc","Documento","Teléfono","Creado"])
            st.dataframe(df_c, use_container_width=True, hide_index=True)

            st.markdown("**Eliminar cliente:**")
            col_c1, col_c2 = st.columns([2,1])
            with col_c1:
                cli_opts = {f"{r[1]} ({r[3] or 'sin doc'})": r[0] for r in rows_c}
                sel_cli = st.selectbox("Seleccionar cliente", list(cli_opts.keys()), key="del_cli_sel")
                sel_cli_id = cli_opts[sel_cli]
            with col_c2:
                pin_del_c = st.text_input("PIN admin", type="password", key="del_cli_pin")
            st.warning("⚠️ Eliminar un cliente también eliminará sus reservas y pagos asociados.")
            if st.button("🗑️ ELIMINAR CLIENTE", type="primary",
                         use_container_width=True, key="btn_del_cli"):
                if not verificar_pin(pin_del_c, "admin"):
                    st.error("❌ PIN admin incorrecto")
                else:
                    con2 = get_db()
                    # Obtener reservas del cliente para liberar cubículos
                    res_ids = [r[0] for r in con2.execute(
                        "SELECT id FROM reservas WHERE cliente_id=?", (sel_cli_id,)).fetchall()]
                    for rid in res_ids:
                        cub = con2.execute(
                            "SELECT cubiculo_id FROM reservas WHERE id=?", (rid,)).fetchone()
                        if cub:
                            con2.execute(
                                "UPDATE cubiculos SET estado='libre', reserva_activa_id=NULL, "
                                "hora_disponible=NULL WHERE reserva_activa_id=?", (rid,))
                        con2.execute("DELETE FROM pagos WHERE reserva_id=?", (rid,))
                    if res_ids:
                        con2.execute(f"DELETE FROM reservas WHERE cliente_id=?", (sel_cli_id,))
                    con2.execute("DELETE FROM clientes WHERE id=?", (sel_cli_id,))
                    con2.commit()
                    con2.close()
                    st.success(f"✅ Cliente eliminado con {len(res_ids)} reserva(s) asociada(s)")
                    _, sh_del2 = get_active_client()
                    if sh_del2:
                        gs_sync_cubiculos(sh_del2)
                        # Sync Clientes, Reservas y Pagos
                        try:
                            con_sc = get_db()
                            rows_cc = con_sc.execute("""
                                SELECT c.id, c.nombre, c.tipo_documento, c.numero_documento,
                                       c.telefono, c.email, c.ciudad, c.regimen, c.tipo_persona,
                                       c.razon_social, c.nit_empresa, c.activo,
                                       COUNT(r.id), COALESCE(SUM(r.total),0), c.creado_en
                                FROM clientes c
                                LEFT JOIN reservas r ON r.cliente_id = c.id
                                GROUP BY c.id ORDER BY c.id
                            """).fetchall()
                            rows_rc = con_sc.execute("""
                                SELECT r.id, r.numero_reserva, r.creado_en, cu.numero,
                                       cl.nombre, cl.numero_documento, cl.telefono, cl.email,
                                       r.horas_contratadas, r.hora_inicio, r.hora_fin_programada,
                                       r.hora_fin_real, r.precio_hora, r.subtotal, r.iva, r.total,
                                       r.metodo_pago, r.estado_pago, r.codigo_acceso,
                                       cu.wifi_ssid, cu.wifi_password,
                                       f.numero, r.referencia_pago, 'sistema', r.notas
                                FROM reservas r
                                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                                LEFT JOIN clientes cl ON r.cliente_id = cl.id
                                LEFT JOIN facturas f ON r.factura_id = f.id
                                ORDER BY r.id
                            """).fetchall()
                            rows_pc = con_sc.execute("""
                                SELECT p.id, p.reserva_id, r.numero_reserva, p.fecha_pago,
                                       p.monto, p.metodo, p.referencia_externa,
                                       p.estado, p.confirmado_por, p.notas
                                FROM pagos p LEFT JOIN reservas r ON p.reserva_id = r.id
                                ORDER BY p.id
                            """).fetchall()
                            con_sc.close()
                            ws_cc = _gs_get_or_create_ws(sh_del2, "Clientes")
                            ws_cc.clear()
                            _gs_update_range(ws_cc, "A1", [DRIVE_SHEETS["Clientes"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_cc])
                            ws_rc = _gs_get_or_create_ws(sh_del2, "Reservas")
                            ws_rc.clear()
                            _gs_update_range(ws_rc, "A1", [DRIVE_SHEETS["Reservas"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_rc])
                            ws_pc = _gs_get_or_create_ws(sh_del2, "Pagos")
                            ws_pc.clear()
                            _gs_update_range(ws_pc, "A1", [DRIVE_SHEETS["Pagos"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_pc])
                        except Exception as _ec:
                            st.warning(f"⚠️ Error sync tras eliminar cliente: {_ec}")
                    st.rerun()

    # ── PAGOS ──────────────────────────────────────────────────────────────────
    with tab_pag:
        st.markdown("#### Eliminar / anular pagos")
        con = get_db()
        rows_p = con.execute("""
            SELECT p.id, r.numero_reserva, p.monto, p.metodo,
                   p.estado, p.fecha_pago
            FROM pagos p
            LEFT JOIN reservas r ON p.reserva_id = r.id
            ORDER BY p.id DESC LIMIT 100
        """).fetchall()
        con.close()

        if not rows_p:
            st.info("No hay pagos registrados.")
        else:
            df_p = pd.DataFrame(rows_p, columns=["ID","Reserva","Monto","Método","Estado","Fecha"])
            df_p["Monto"] = df_p["Monto"].apply(lambda x: fmt_cop(float(x)) if x else "")
            st.dataframe(df_p, use_container_width=True, hide_index=True)

            col_p1, col_p2 = st.columns([2,1])
            with col_p1:
                pago_opts = {f"#{r[0]} — {r[1]} — {fmt_cop(float(r[2]))}": r[0] for r in rows_p}
                sel_pago = st.selectbox("Seleccionar pago", list(pago_opts.keys()), key="del_pago_sel")
                sel_pago_id = pago_opts[sel_pago]
            with col_p2:
                pin_del_p = st.text_input("PIN admin", type="password", key="del_pago_pin")
            accion_p = st.radio("Acción", ["Anular (marcar como anulado)", "Eliminar definitivamente"],
                                key="del_pago_accion", horizontal=True)
            if st.button("✅ APLICAR ACCIÓN", type="primary",
                         use_container_width=True, key="btn_del_pago"):
                if not verificar_pin(pin_del_p, "admin"):
                    st.error("❌ PIN admin incorrecto")
                else:
                    con2 = get_db()
                    if "Anular" in accion_p:
                        con2.execute("UPDATE pagos SET estado='anulado' WHERE id=?", (sel_pago_id,))
                        st.success(f"✅ Pago #{sel_pago_id} anulado")
                    else:
                        con2.execute("DELETE FROM pagos WHERE id=?", (sel_pago_id,))
                        st.success(f"✅ Pago #{sel_pago_id} eliminado")
                    con2.commit()
                    con2.close()
                    _, sh_pag = get_active_client()
                    if sh_pag:
                        try:
                            con_sp = get_db()
                            rows_pp = con_sp.execute("""
                                SELECT p.id, p.reserva_id, r.numero_reserva, p.fecha_pago,
                                       p.monto, p.metodo, p.referencia_externa,
                                       p.estado, p.confirmado_por, p.notas
                                FROM pagos p LEFT JOIN reservas r ON p.reserva_id = r.id
                                ORDER BY p.id
                            """).fetchall()
                            con_sp.close()
                            ws_pp = _gs_get_or_create_ws(sh_pag, "Pagos")
                            ws_pp.clear()
                            _gs_update_range(ws_pp, "A1", [DRIVE_SHEETS["Pagos"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_pp])
                        except Exception as _ep:
                            st.warning(f"⚠️ Error sync Pagos: {_ep}")
                    st.rerun()

    # ── FACTURAS ──────────────────────────────────────────────────────────────
    with tab_fact:
        st.markdown("#### Eliminar / anular facturas")
        con = get_db()
        rows_f = con.execute("""
            SELECT f.id, f.numero, c.nombre, f.total, f.estado, f.fecha_emision
            FROM facturas f
            LEFT JOIN clientes c ON f.cliente_id = c.id
            ORDER BY f.id DESC LIMIT 100
        """).fetchall()
        con.close()

        if not rows_f:
            st.info("No hay facturas registradas.")
        else:
            df_f = pd.DataFrame(rows_f, columns=["ID","Número","Cliente","Total","Estado","Fecha"])
            df_f["Total"] = df_f["Total"].apply(lambda x: fmt_cop(float(x)) if x else "")
            st.dataframe(df_f, use_container_width=True, hide_index=True)

            col_f1, col_f2 = st.columns([2,1])
            with col_f1:
                fact_opts = {f"{r[1]} — {r[2]}": r[0] for r in rows_f}
                sel_fact = st.selectbox("Seleccionar factura", list(fact_opts.keys()), key="del_fact_sel")
                sel_fact_id = fact_opts[sel_fact]
            with col_f2:
                pin_del_f = st.text_input("PIN admin", type="password", key="del_fact_pin")
            accion_f = st.radio("Acción", ["Anular (marcar como anulada)", "Eliminar definitivamente"],
                                key="del_fact_accion", horizontal=True)
            if st.button("✅ APLICAR ACCIÓN", type="primary",
                         use_container_width=True, key="btn_del_fact"):
                if not verificar_pin(pin_del_f, "admin"):
                    st.error("❌ PIN admin incorrecto")
                else:
                    con2 = get_db()
                    if "Anular" in accion_f:
                        con2.execute("UPDATE facturas SET estado='anulada' WHERE id=?", (sel_fact_id,))
                        st.success(f"✅ Factura anulada")
                    else:
                        con2.execute("DELETE FROM factura_items WHERE factura_id=?", (sel_fact_id,))
                        con2.execute("DELETE FROM facturas WHERE id=?", (sel_fact_id,))
                        st.success(f"✅ Factura eliminada definitivamente")
                    con2.commit()
                    con2.close()
                    _, sh_fact = get_active_client()
                    if sh_fact:
                        try:
                            con_sf = get_db()
                            rows_ff = con_sf.execute("""
                                SELECT f.id, f.numero, f.tipo, f.fecha_emision, f.fecha_vencimiento,
                                       cl.nombre, cl.numero_documento, cl.email,
                                       cl.razon_social, cl.nit_empresa,
                                       fi.descripcion,
                                       f.subtotal, f.descuento,
                                       (f.subtotal - f.descuento),
                                       f.iva, f.retenciones, f.total,
                                       f.metodo_pago, f.estado, f.moneda,
                                       r.numero_reserva, cu.numero,
                                       f.creado_en, f.actualizado_en
                                FROM facturas f
                                LEFT JOIN clientes cl ON f.cliente_id = cl.id
                                LEFT JOIN factura_items fi ON fi.factura_id = f.id
                                LEFT JOIN reservas r ON r.factura_id = f.id
                                LEFT JOIN cubiculos cu ON r.cubiculo_id = cu.id
                                GROUP BY f.id ORDER BY f.id
                            """).fetchall()
                            con_sf.close()
                            ws_ff = _gs_get_or_create_ws(sh_fact, "Facturas")
                            ws_ff.clear()
                            _gs_update_range(ws_ff, "A1", [DRIVE_SHEETS["Facturas"]] +
                                [[str(v) if v is not None else "" for v in r] for r in rows_ff])
                            gs_sync_factura_items(sh_fact)
                        except Exception as _ef:
                            st.warning(f"⚠️ Error sync Facturas/Items: {_ef}")
                    st.rerun()

def _op_google_drive():
    """Panel de integración con Google Sheets — estado, diagnóstico y acciones."""
    st.markdown("### ☁️ Google Drive / Google Sheets")
    st.markdown(f"**Archivo de datos:** `{DRIVE_FILE}`")

    # ── Estado de la conexión ─────────────────────────────────────────────────
    _, sh_now = _get_module_level_client()
    sid_saved = get_config("drive_spreadsheet_id", "")
    global _gs_cached_creds

    if sh_now and sid_saved:
        drive_url = f"https://docs.google.com/spreadsheets/d/{sid_saved}/edit"
        st.success(f"✅ **Conectado** a `{sh_now.title}`")
        st.markdown(
            f'🔗 <a href="{drive_url}" target="_blank" style="color:#00d4ff">'
            f'Abrir {sh_now.title} en Google Sheets ↗</a>',
            unsafe_allow_html=True)
        st.info("🔄 **Sincronización automática activa** — cada reserva, pago y "
                "liberación se inserta en Google Sheets en tiempo real.")
    else:
        st.warning("⚠️ Sin conexión activa a Google Sheets.")

        # Diagnóstico de credenciales
        with st.expander("🔍 Diagnóstico de credenciales"):
            st.markdown("**Verificando fuentes de credenciales:**")

            # Test 1: st.secrets
            try:
                raw = st.secrets["sheetsemp"]["credentials_sheet"]
                st.success("✅ `st.secrets['sheetsemp']['credentials_sheet']` — encontrado")
                try:
                    c = _normalize_creds(raw)
                    if "private_key" in c and "client_email" in c:
                        st.success(f"✅ Credenciales válidas — `{c.get('client_email','?')}`")
                    else:
                        st.error(f"❌ Credenciales incompletas — faltan campos: "
                                 f"{'private_key ' if 'private_key' not in c else ''}"
                                 f"{'client_email' if 'client_email' not in c else ''}")
                except Exception as e:
                    st.error(f"❌ Error parseando credenciales: {e}")
            except Exception as e:
                st.warning(f"⚠️ `st.secrets` no disponible o incompleto: {e}")

            # Test 2: secrets.toml
            toml_paths = [
                ".streamlit/secrets.toml",
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             ".streamlit", "secrets.toml"),
            ]
            for tp in toml_paths:
                exists = os.path.isfile(tp)
                icon = "✅" if exists else "❌"
                st.markdown(f"{icon} `{tp}` — {'existe' if exists else 'NO existe'}")
                if exists and TOML_AVAILABLE:
                    try:
                        with open(tp, "r", encoding="utf-8") as _tf:
                            _cfg = toml_lib.load(_tf)
                        _raw = _cfg.get("sheetsemp", {}).get("credentials_sheet")
                        if _raw:
                            _c = _normalize_creds(_raw)
                            if "private_key" in _c and "client_email" in _c:
                                st.success(f"  ✅ JSON válido en `{tp}` — `{_c.get('client_email','?')}`")
                            else:
                                st.warning(f"  ⚠️ `{tp}` encontrado pero credenciales incompletas")
                        else:
                            st.warning(f"  ⚠️ `{tp}` existe pero falta [sheetsemp].credentials_sheet")
                    except KeyError as _e:
                        st.error(f"  🔑 Clave faltante en `{tp}`: {_e}")
                    except Exception as _e:
                        st.error(f"  ❌ Error leyendo `{tp}`: {_e}")
                elif exists and not TOML_AVAILABLE:
                    st.info("  💡 Instala toml para validar el contenido: pip install toml")

            # Test 3: Spreadsheet ID
            sid_diag = get_config("drive_spreadsheet_id", "")
            if sid_diag:
                st.success(f"✅ Spreadsheet ID configurado: `{sid_diag}`")
            else:
                st.error("❌ Spreadsheet ID no configurado — ve a ⚙️ Configuración → Google Sheets")

            # Botón para forzar re-intento
            if st.button("🔄 Reintentar conexión ahora", key="retry_conn"):
                _gs_cached_creds = None  # invalidar caché
                global _gs_module_client, _gs_module_spreadsheet  # noqa
                _gs_module_client = None
                _gs_module_spreadsheet = None
                st.rerun()

    st.divider()

    # ── Acciones manuales ─────────────────────────────────────────────────────
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("☁️ Forzar sincronización completa", type="primary",
                     use_container_width=True):
            with st.spinner("Sincronizando todas las tablas con Google Sheets..."):
                resultado = sincronizacion_completa()
                if "error" in resultado:
                    st.error(f"❌ {resultado['error']}")
                else:
                    st.success("✅ Sincronización completada")
                    st.json({k: v for k, v in resultado.items()
                             if not str(v).startswith("Error")})
    with col_s2:
        if st.button("🔄 Verificar conexión", use_container_width=True):
            with st.spinner("Probando conexión..."):
                # Invalidar caché para forzar reconexión real
                _reset_gs_cache()
                _, sh_test = _get_module_level_client()
                if sh_test:
                    st.success(f"✅ Conectado a **{sh_test.title}** — sync funcionando")
                else:
                    st.error("❌ Sin conexión — revisa las credenciales en Configuración")

    # ── Restaurar SQLite desde Sheets (solo Cloud) ────────────────────────────
    if _IS_CLOUD:
        st.divider()
        st.markdown("#### 🔁 Restaurar base de datos desde Google Sheets")
        st.info(
            "En Streamlit Cloud la base de datos SQLite es **volátil** — se pierde al "
            "reiniciar el servidor. Usa este botón para recargar todos los datos desde "
            "Google Sheets sin necesidad de reiniciar la app."
        )
        col_r1, col_r2 = st.columns([2, 1])
        with col_r1:
            if st.button("🔁 Restaurar datos desde Google Sheets ahora",
                         type="primary", use_container_width=True,
                         key="btn_restore_sheets"):
                with st.spinner("Restaurando datos desde Google Sheets..."):
                    try:
                        con_wipe = get_db()
                        for tabla in ["pagos", "reservas", "factura_items",
                                      "facturas", "clientes", "tarifas",
                                      "operadores", "cubiculos",
                                      "configuracion_pagos"]:
                            con_wipe.execute(f"DELETE FROM {tabla}")
                        con_wipe.commit()
                        con_wipe.close()
                    except Exception as _ew:
                        st.warning(f"⚠️ Error limpiando tablas: {_ew}")
                    ok = _restore_from_sheets()
                    if ok:
                        with _config_cache_lock:
                            _config_cache.clear()
                        st.success(
                            "✅ Base de datos restaurada correctamente desde Google Sheets."
                        )
                        con_chk = get_db()
                        resumen = {
                            t: con_chk.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                            for t in ["clientes","reservas","pagos",
                                      "facturas","cubiculos","operadores"]
                        }
                        con_chk.close()
                        st.json(resumen)
                    else:
                        st.error(
                            "❌ No se pudo restaurar. Verifica que Google Sheets esté "
                            "configurado y contenga datos."
                        )
        with col_r2:
            con_stat = get_db()
            n_res = con_stat.execute("SELECT COUNT(*) FROM reservas").fetchone()[0]
            n_cli = con_stat.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            n_cub = con_stat.execute("SELECT COUNT(*) FROM cubiculos").fetchone()[0]
            n_op  = con_stat.execute("SELECT COUNT(*) FROM operadores").fetchone()[0]
            con_stat.close()
            st.markdown("**Estado actual SQLite:**")
            st.markdown(f"- 🛏️ Cubículos: **{n_cub}**")
            st.markdown(f"- 👤 Clientes: **{n_cli}**")
            st.markdown(f"- 📋 Reservas: **{n_res}**")
            st.markdown(f"- 👥 Operadores: **{n_op}**")
            if n_op > 0:
                st.caption(
                    "⚠️ Operadores restaurados desde Sheets tienen PIN `1234` "
                    "si no existían antes. Cámbialo en ⚙️ → Operadores."
                )
    else:
        st.divider()
        st.info("💻 Ejecución **local** — SQLite persiste en disco. "
                "No es necesario restaurar desde Sheets al reiniciar.")

    st.divider()

    # ── Cargar datos desde Google Sheets ─────────────────────────────────────
    st.markdown("#### 📊 Consultar datos en Google Sheets")
    if sh_now:
        hoja_sel = st.selectbox("Ver hoja:", list(DRIVE_SHEETS.keys()),
                                key="gs_hoja_sel")
        if st.button("🔄 Cargar datos", use_container_width=True):
            with st.spinner(f"Cargando hoja '{hoja_sel}'..."):
                client_gs, sh_gs = get_active_client()
                if not client_gs:
                    st.error("❌ Sin conexión a Google Sheets. Verifica las credenciales.")
                else:
                    df_gs = load_data_from_sheet(client_gs, DRIVE_FILE, hoja_sel)
                    if df_gs.empty:
                        st.info(f"La hoja '{hoja_sel}' está vacía.")
                    else:
                        st.success(f"✅ {len(df_gs)} filas cargadas desde '{hoja_sel}'")
                        st.dataframe(df_gs, use_container_width=True, hide_index=True)
                        csv_gs = df_gs.to_csv(index=False).encode()
                        st.download_button(
                            f"📥 Descargar {hoja_sel}.csv",
                            data=csv_gs,
                            file_name=f"jjgt_{hoja_sel.lower()}_{ahora_col().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            use_container_width=True)
    else:
        st.info("Configura las credenciales primero para consultar los datos.")

    st.divider()
    st.markdown("**Hojas sincronizadas en `jjgt_pagos`:**")
    for nombre, cols in DRIVE_SHEETS.items():
        st.markdown(f"- **{nombre}** · {len(cols)} columnas: "
                    f"`{', '.join(cols[:5])}`{'...' if len(cols) > 5 else ''}")


def _op_configuracion():
    st.markdown("### ⚙️ Configuración del Sistema")
    tabs = st.tabs(["🏢 Negocio", "💰 Pagos", "🛏️ Tarifas", "👤 Operadores", "🔗 Google Sheets"])
    # Constantes compartidas entre tabs
    _TURNOS            = ["mañana","tarde","noche","diurno","admin"]
    _TURNO_HORAS       = {
        "mañana": ("06:00","14:00"),
        "tarde":  ("14:00","22:00"),
        "noche":  ("22:00","06:00"),
        "diurno": ("06:00","14:00"),
        "admin":  ("00:00","23:59"),
    }
    _PERMISOS_OPCIONES = ["reservas","pagos","voucher","reportes","configuracion","admin"]

    with tabs[0]:
        st.markdown("**Datos del negocio**")
        col_ng1, col_ng2 = st.columns(2)
        with col_ng1:
            nombre_n = st.text_input("Nombre del negocio",
                                      value=get_config("negocio_nombre", NEGOCIO))
            nit_n    = st.text_input("NIT / RUT",
                                      value=get_config("negocio_nit", NIT))
            dir_n    = st.text_input("Dirección en terminal",
                                      value=get_config("negocio_direccion", DIRECCION))
        with col_ng2:
            tel_n    = st.text_input("Teléfono",
                                      value=get_config("negocio_telefono", TELEFONO))
            email_n  = st.text_input("Email del negocio",
                                      value=get_config("negocio_email", ""),
                                      placeholder="contacto@jjgt.com.co")
            web_n    = st.text_input("Sitio web (opcional)",
                                      value=get_config("negocio_web", ""),
                                      placeholder="https://www.jjgt.com.co")
        if st.button("💾 Guardar datos negocio", type="primary"):
            for k, v in [
                ("negocio_nombre",   nombre_n),
                ("negocio_nit",      nit_n),
                ("negocio_direccion",dir_n),
                ("negocio_telefono", tel_n),
                ("negocio_email",    email_n),
                ("negocio_web",      web_n),
            ]:
                set_config(k, v)
            st.success("✅ Datos del negocio actualizados")
            _, sh_cfg = get_active_client()
            if sh_cfg:
                gs_sync_configuracion_pagos(sh_cfg)

    with tabs[1]:
        st.markdown("**Datos de plataformas de pago**")
        nequi_c  = st.text_input("Número Nequi", value=get_config("nequi_numero", NEQUI_NUM))
        davi_c   = st.text_input("Número Daviplata", value=get_config("daviplata_numero", DAVIPLATA_NUM))
        banco_c  = st.text_input("Cuenta bancaria", value=get_config("cuenta_bancaria", CUENTA_BANCO))
        mp_c     = st.text_input("Link MercadoPago", value=get_config("mp_link", MP_LINK))
        wa_c     = st.text_input("WhatsApp operador", value=get_config("whatsapp_op", WHATSAPP_OP))
        if st.button("💾 Guardar datos de pago", type="primary"):
            for k, v in [("nequi_numero",nequi_c),("daviplata_numero",davi_c),
                          ("cuenta_bancaria",banco_c),("mp_link",mp_c),("whatsapp_op",wa_c)]:
                set_config(k, v)
            st.success("✅ Datos de pago actualizados")
            _, sh_cfg2 = get_active_client()
            if sh_cfg2:
                gs_sync_configuracion_pagos(sh_cfg2)

    with tabs[2]:
        st.markdown("**Tarifas vigentes**")
        con = get_db()
        tfs = con.execute("SELECT id,nombre,descripcion,precio_hora,descuento_3h_pct,descuento_6h_pct,activo FROM tarifas").fetchall()
        con.close()
        df_t = pd.DataFrame(tfs, columns=["ID","Nombre","Descripción","Precio/hora","Desc 3h%","Desc 6h%","Activo"])
        df_t["Precio/hora"] = df_t["Precio/hora"].apply(fmt_cop)
        st.dataframe(df_t, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown("#### 👥 Gestión de Operadores")

        # ── Lista de operadores ────────────────────────────────────────────
        con_op = get_db()
        ops = con_op.execute(
            "SELECT id,nombre,rol,turno,hora_inicio_turno,hora_fin_turno,permisos,activo "
            "FROM operadores ORDER BY id").fetchall()
        con_op.close()

        TURNOS            = _TURNOS
        TURNO_HORAS       = _TURNO_HORAS
        PERMISOS_OPCIONES = _PERMISOS_OPCIONES

        if ops:
            st.markdown("**Operadores registrados:**")
            for op_row in ops:
                op_id, op_nombre, op_rol, op_turno, op_hi, op_hf, op_perms, op_activo = op_row
                estado_badge = "🟢" if op_activo else "🔴"
                with st.expander(f"{estado_badge} {op_nombre} · {op_rol.capitalize()} · Turno {op_turno or '-'}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        new_nombre = st.text_input("Nombre", value=op_nombre, key=f"op_nom_{op_id}")
                        new_rol    = st.selectbox("Rol", ["admin","cajero","supervisor"],
                                                  index=["admin","cajero","supervisor"].index(op_rol) if op_rol in ["admin","cajero","supervisor"] else 1,
                                                  key=f"op_rol_{op_id}")
                        new_turno  = st.selectbox("Turno", TURNOS,
                                                   index=TURNOS.index(op_turno) if op_turno in TURNOS else 0,
                                                   key=f"op_trn_{op_id}")
                        hi_def, hf_def = TURNO_HORAS.get(new_turno, ("06:00","14:00"))
                        new_hi = st.text_input("Hora inicio turno", value=op_hi or hi_def, key=f"op_hi_{op_id}")
                        new_hf = st.text_input("Hora fin turno",    value=op_hf or hf_def, key=f"op_hf_{op_id}")
                    with col_b:
                        perms_list = [p.strip() for p in (op_perms or "reservas,pagos,voucher").split(",")]
                        new_perms  = st.multiselect("Permisos", PERMISOS_OPCIONES,
                                                     default=[p for p in perms_list if p in PERMISOS_OPCIONES],
                                                     key=f"op_per_{op_id}")
                        new_activo = st.checkbox("Activo", value=bool(op_activo), key=f"op_act_{op_id}")
                        nuevo_pin  = st.text_input("Nuevo PIN (dejar vacío = no cambiar)",
                                                    type="password", max_chars=8, key=f"op_pin_{op_id}")

                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("💾 Guardar cambios", key=f"op_save_{op_id}", type="primary",
                                      use_container_width=True):
                            con2 = get_db()
                            perms_str = ",".join(new_perms) if new_perms else "reservas,pagos,voucher"
                            if nuevo_pin and len(nuevo_pin) >= 4:
                                con2.execute(
                                    "UPDATE operadores SET nombre=?,rol=?,turno=?,hora_inicio_turno=?,"
                                    "hora_fin_turno=?,permisos=?,activo=?,pin_hash=? WHERE id=?",
                                    (new_nombre, new_rol, new_turno, new_hi, new_hf,
                                     perms_str, int(new_activo), _hash_pin(nuevo_pin), op_id))
                                st.success("✅ Operador actualizado con nuevo PIN")
                            elif nuevo_pin and len(nuevo_pin) < 4:
                                st.error("El PIN debe tener al menos 4 dígitos")
                                con2.close()
                                continue
                            else:
                                con2.execute(
                                    "UPDATE operadores SET nombre=?,rol=?,turno=?,hora_inicio_turno=?,"
                                    "hora_fin_turno=?,permisos=?,activo=? WHERE id=?",
                                    (new_nombre, new_rol, new_turno, new_hi, new_hf,
                                     perms_str, int(new_activo), op_id))
                                st.success("✅ Operador actualizado")
                            con2.commit()
                            con2.close()
                            _, sh_op = get_active_client()
                            if sh_op:
                                gs_sync_operadores(sh_op)
                            st.rerun()
                    with cc2:
                        if op_id > 1:  # No eliminar admin principal
                            if st.button("🗑️ Eliminar", key=f"op_del_{op_id}",
                                          use_container_width=True):
                                con2 = get_db()
                                con2.execute("DELETE FROM operadores WHERE id=?", (op_id,))
                                con2.commit()
                                con2.close()
                                st.warning(f"Operador {op_nombre} eliminado")
                                _, sh_opdel = get_active_client()
                                if sh_opdel:
                                    gs_sync_operadores(sh_opdel)
                                st.rerun()

        st.divider()
        st.markdown("#### ➕ Crear nuevo operador")
        with st.form("form_nuevo_op", clear_on_submit=True):
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                f_nombre = st.text_input("Nombre del operador *")
                f_pin    = st.text_input("PIN (4-8 dígitos) *", type="password", max_chars=8)
                f_pin2   = st.text_input("Confirmar PIN *",     type="password", max_chars=8)
                f_rol    = st.selectbox("Rol", ["cajero","supervisor","admin"])
            with fcol2:
                f_turno  = st.selectbox("Turno", TURNOS)
                hi_def2, hf_def2 = TURNO_HORAS.get(f_turno, ("06:00","14:00"))
                f_hi     = st.text_input("Hora inicio", value=hi_def2)
                f_hf     = st.text_input("Hora fin",    value=hf_def2)
                f_perms  = st.multiselect("Permisos", PERMISOS_OPCIONES,
                                           default=["reservas","pagos","voucher"])
            submitted = st.form_submit_button("➕ Crear operador", type="primary",
                                               use_container_width=True)
            if submitted:
                if not f_nombre:
                    st.error("El nombre es obligatorio")
                elif len(f_pin) < 4:
                    st.error("El PIN debe tener al menos 4 dígitos")
                elif f_pin != f_pin2:
                    st.error("Los PINs no coinciden")
                else:
                    perms_str2 = ",".join(f_perms) if f_perms else "reservas,pagos,voucher"
                    con3 = get_db()
                    con3.execute(
                        "INSERT INTO operadores (nombre,pin_hash,rol,turno,hora_inicio_turno,hora_fin_turno,permisos) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (f_nombre, _hash_pin(f_pin), f_rol, f_turno, f_hi, f_hf, perms_str2))
                    con3.commit()
                    con3.close()
                    st.success(f"✅ Operador **{f_nombre}** creado en turno **{f_turno}**")
                    _, sh_opnew = get_active_client()
                    if sh_opnew:
                        gs_sync_operadores(sh_opnew)
                    st.rerun()

    with tabs[4]:
        st.markdown("#### 🔗 Credenciales Google Sheets")
        st.markdown("""
        La aplicación se conecta al archivo `jjgt_pagos` en Google Sheets para sincronización automática.
        """)

        # ── Entorno de ejecución ───────────────────────────────────────────
        # _IS_CLOUD se definió a nivel de módulo al inicio
        entorno = "☁️ Streamlit Cloud" if _IS_CLOUD else "💻 Ejecución local"
        st.info(f"**Entorno detectado:** {entorno}")

        # ── Estado actual de la conexión ───────────────────────────────────
        _, sh_status = _get_module_level_client()
        if sh_status:
            sid_actual = get_config("drive_spreadsheet_id","")
            drive_url_conf = f"https://docs.google.com/spreadsheets/d/{sid_actual}/edit"
            st.success(f"✅ Conectado a **{sh_status.title}**")
            st.markdown(f'🔗 <a href="{drive_url_conf}" target="_blank">Abrir {sh_status.title} en Google Sheets</a>',
                        unsafe_allow_html=True)
        else:
            st.warning("⚠️ Sin conexión activa a Google Sheets")

        st.divider()

        # ── Configurar Spreadsheet ID ──────────────────────────────────────
        st.markdown("**ID del Spreadsheet `jjgt_pagos`**")
        sid_input = st.text_input("Spreadsheet ID",
                                   value=get_config("drive_spreadsheet_id",""),
                                   placeholder="1abc...xyz",
                                   help="El ID aparece en la URL del archivo: docs.google.com/spreadsheets/d/**ID**/edit")
        if st.button("💾 Guardar Spreadsheet ID", use_container_width=True):
            if sid_input.strip():
                set_config("drive_spreadsheet_id", sid_input.strip())
                global _gs_module_spreadsheet  # noqa
                _gs_module_spreadsheet = None
                st.success("✅ Spreadsheet ID guardado. Reconectando...")
                st.rerun()
            else:
                st.error("El ID no puede estar vacío")

        st.divider()

        # ── Instrucciones según entorno ────────────────────────────────────
        if _IS_CLOUD:
            st.markdown("""
            **📋 Configuración para Streamlit Cloud:**

            En la app de Streamlit Cloud → **Settings → Secrets**, agrega:
            ```toml
            [sheetsemp]
            credentials_sheet = '''
            {
              "type": "service_account",
              "project_id": "...",
              "private_key_id": "...",
              "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
              "client_email": "...@....iam.gserviceaccount.com",
              ...
            }
            '''
            spreadsheet_id = "ID_DE_TU_SPREADSHEET"
            ```
            """)
        else:
            st.markdown("""
            **📋 Configuración para ejecución local:**

            Crea el archivo `.streamlit/secrets.toml` con:
            ```toml
            [sheetsemp]
            credentials_sheet = '''{ ... JSON de tu Service Account ... }'''
            spreadsheet_id = "ID_DE_TU_SPREADSHEET"
            ```

            O simplemente coloca `credentials.json` en el directorio raíz del proyecto.
            """)

            # Subir credentials.json localmente
            st.markdown("**O sube tu archivo credentials.json directamente:**")
            creds_file = st.file_uploader("credentials.json", type=["json"])
            if creds_file:
                creds_path = "credentials.json"
                with open(creds_path, "wb") as f:
                    f.write(creds_file.read())
                set_config("drive_credentials_path", creds_path)
                global _gs_module_client  # noqa
                _gs_module_client = None
                _gs_module_spreadsheet = None  # noqa
                try:
                    st.session_state._gs_client = None
                except Exception:
                    pass
                st.success("✅ credentials.json guardado. Reconectando...")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    init_state()
    init_db()
    # Mostrar banner informativo en Cloud si la BD se acaba de restaurar
    if _IS_CLOUD:
        con_chk = get_db()
        n_cub = con_chk.execute("SELECT COUNT(*) FROM cubiculos").fetchone()[0]
        n_op  = con_chk.execute("SELECT COUNT(*) FROM operadores").fetchone()[0]
        con_chk.close()
        if n_cub == 0 or n_op == 0:
            st.warning("⚠️ Base de datos en Cloud vacía. Configura Google Sheets y recarga la app.")
    # Backup solo en local (en Cloud /tmp no persiste y puede fallar)
#    if not _IS_CLOUD:
#        _auto_backup_diario()
    _ensure_sync_thread()  # Arrancar worker de sync a Google Sheets

    pantalla = st.session_state.pantalla
    router   = {
        "operador_login": show_operador_login,   # Pantalla inicial
        "operador":       show_operador,
        "bienvenida":     show_bienvenida,       # Kiosco (requiere auth)
        "seleccion":      show_seleccion,
        "datos":          show_datos,
        "pago":           show_pago,
        "confirmacion":   show_confirmacion,
        "voucher":        show_voucher,
    }
    # El default siempre es el login, nunca bienvenida sin autenticar
    router.get(pantalla, show_operador_login)()


if __name__ == "__main__":
    main()
