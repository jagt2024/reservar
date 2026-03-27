# ══════════════════════════════════════════════════════════════════════════════
#  JJGT · Espacios de Descanso Personal — Terminal de Transportes
#  MÓDULO DE PAGOS · Kiosco Táctil 24/7
# ══════════════════════════════════════════════════════════════════════════════
#
#  Instalación:
#    pip install streamlit pandas qrcode pillow reportlab requests
#               pytz openpyxl gspread google-auth google-auth-oauthlib
#
#  Ejecución:
#    streamlit run pagos.py
#
#  Base de datos compartida con facturacion.py:
#    terminal_descanso.db  (creada automáticamente)
#
#  Google Sheets / Google Drive:
#    Archivo "jjgt_pagos" gestionado vía gspread + st.secrets
#    Configurar credenciales en .streamlit/secrets.toml:
#
#    [sheetsemp]
#    credentials_sheet = '''{ ... JSON de Service Account ... }'''
#
#    O directamente en Streamlit Cloud → Settings → Secrets
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
DB_PATH      = "terminal_descanso.db"
NEGOCIO      = "JJGT · Espacios de Descanso"
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

ESTADOS_CUBICULO = {
    "libre":        {"label": "LIBRE",        "color": "#00ff88", "bg": "rgba(0,255,136,0.12)"},
    "ocupado":      {"label": "OCUPADO",      "color": "#ff4757", "bg": "rgba(255,71,87,0.12)"},
    "por_liberar":  {"label": "POR LIBERAR",  "color": "#ffd32a", "bg": "rgba(255,211,42,0.12)"},
    "mantenimiento":{"label": "MANTENIM.",    "color": "#a29bfe", "bg": "rgba(162,155,254,0.12)"},
    "reservado":    {"label": "RESERVADO",    "color": "#74b9ff", "bg": "rgba(116,185,255,0.12)"},
}

METODOS_PAGO = ["Nequi", "Daviplata", "Efectivo", "PSE", "MercadoPago", "Transferencia", "Tarjeta"]
IVA_PCT      = 0.19

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{NEGOCIO} · Pagos",
    page_icon="💤",
    layout="wide",
    initial_sidebar_state="collapsed",
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
  color: var(--text-dim) !important;
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
# SYNC EN LÍNEA A GOOGLE SHEETS — hilo background con cola de eventos
# ══════════════════════════════════════════════════════════════════════════════

# Cola global de eventos de sincronización (thread-safe)
_sync_queue: queue.Queue = queue.Queue(maxsize=200)
_sync_thread_started = False


def _sync_worker():
    """
    Worker que corre en hilo daemon separado: consume la cola y escribe en Google Sheets.
    - NO usa st.session_state (inaccesible fuera del hilo principal de Streamlit)
    - Usa _get_module_level_client() para obtener el cliente gspread
    - Reintentos automáticos con backoff ante errores 429
    - Sync periódico del estado de cubículos cada 30s (en el timeout)
    """
    import time as _time

    # Contadores para deduplicar eventos de baja prioridad
    _last_cubiculo_sync = 0
    _last_dashboard_sync = 0

    while True:
        try:
            event = _sync_queue.get(timeout=30)
        except queue.Empty:
            # Timeout de 30s: sync periódico del estado si hay credenciales
            now = _time.time()
            if now - _last_cubiculo_sync >= 30:
                _last_cubiculo_sync = now
                try:
                    _sync_cubiculos_estado()
                except Exception:
                    pass
            continue

        try:
            etype = event.get("type")
            retries = event.get("_retries", 0)

            if etype == "nueva_reserva":
                _sync_write_reserva(event)

            elif etype == "liberar_cubiculo":
                _sync_liberar_cubiculo_sheets(event)

            elif etype == "cubiculos_estado":
                now = _time.time()
                if now - _last_cubiculo_sync >= 5:  # Deduplicar — mínimo 5s entre syncs
                    _last_cubiculo_sync = now
                    _sync_cubiculos_estado()

            elif etype == "dashboard_diario":
                now = _time.time()
                if now - _last_dashboard_sync >= 10:
                    _last_dashboard_sync = now
                    _sync_dashboard_diario()

            elif etype == "cliente":
                _sync_write_cliente(event)

        except Exception as ex:
            # Reencolar con backoff si es error de quota (máx 3 reintentos)
            retries = event.get("_retries", 0)
            if retries < 3:
                event["_retries"] = retries + 1
                _time.sleep(2 ** retries)
                try:
                    _sync_queue.put_nowait(event)
                except queue.Full:
                    pass
        finally:
            try:
                _sync_queue.task_done()
            except Exception:
                pass
        _time.sleep(0.15)  # micro-pausa entre operaciones


def _ensure_sync_thread():
    """Arranca el worker thread una sola vez por proceso."""
    global _sync_thread_started
    if not _sync_thread_started:
        t = threading.Thread(target=_sync_worker, daemon=True, name="jjgt-sheets-sync")
        t.start()
        _sync_thread_started = True


def encolar_sync(event: dict):
    """Encola un evento de sincronización sin bloquear el hilo principal."""
    _ensure_sync_thread()
    try:
        _sync_queue.put_nowait(event)
    except queue.Full:
        pass  # Cola llena — se omite sin bloquear


def _sync_write_reserva(event: dict):
    """
    Escribe la nueva reserva directamente en Google Sheets.
    Usa _get_module_level_client() para ser seguro en worker threads
    (NO depende de st.session_state).
    """
    if not GSPREAD_AVAILABLE:
        return
    client, sh = _get_module_level_client()
    if not sh:
        _marcar_sync_pendiente("Reservas", event.get("reserva_id", 0))
        return
    try:
        reserva_id  = event["reserva_id"]
        num_reserva = event["num_reserva"]
        num_factura = event.get("num_factura", "")

        con = get_db()
        cur = con.cursor()
        cur.execute("""
            SELECT r.id, r.numero_reserva, r.creado_en,
                   cu.numero, cl.nombre, cl.numero_documento, cl.telefono, cl.email,
                   r.horas_contratadas, r.hora_inicio, r.hora_fin_programada,
                   r.hora_fin_real, r.precio_hora, r.subtotal, r.iva, r.total,
                   r.metodo_pago, r.estado_pago, r.codigo_acceso,
                   cu.wifi_ssid, cu.wifi_password, r.referencia_pago, r.notas
            FROM reservas r
            JOIN cubiculos cu ON r.cubiculo_id = cu.id
            JOIN clientes cl  ON r.cliente_id  = cl.id
            WHERE r.id = ?
        """, (reserva_id,))
        row = cur.fetchone()
        con.close()
        if not row:
            return

        fila = [
            str(row[0]), str(row[1]), str(row[2] or ""),       # ID, Num, Fecha
            str(row[3] or ""), str(row[4] or ""),              # Cubículo, Cliente
            str(row[5] or ""), str(row[6] or ""),              # Doc, Tel
            str(row[7] or ""), str(row[8] or ""),              # Email, Horas
            str(row[9] or ""), str(row[10] or ""),             # Inicio, Fin_prog
            str(row[11] or ""),                                # Fin_real
            str(row[12] or ""), str(row[13] or ""),            # Precio, Subtotal
            str(row[14] or ""), str(row[15] or ""),            # IVA, Total
            str(row[16] or ""), str(row[17] or ""),            # Método, Estado
            str(row[18] or ""),                                # Código acceso
            str(row[19] or ""), str(row[20] or ""),            # WiFi SSID, Pass
            str(num_factura),
            str(row[21] or ""), "sistema", str(row[22] or "")  # Ref, Op, Notas
        ]

        # Escribir en hoja Reservas (upsert directo sin pasar por get_active_client)
        ws = _api_call(sh.worksheet, "Reservas")
        all_vals = _api_call(ws.get_all_values)
        headers  = all_vals[0] if all_vals else DRIVE_SHEETS["Reservas"]
        col_idx  = headers.index("Numero_Reserva") if "Numero_Reserva" in headers else -1
        encontrado = False
        if col_idx >= 0:
            for i, r in enumerate(all_vals[1:], start=2):
                if len(r) > col_idx and str(r[col_idx]) == str(num_reserva):
                    padded = (fila + [""] * len(headers))[:len(headers)]
                    _api_call(ws.update, f"A{i}", [padded])
                    encontrado = True
                    break
        if not encontrado:
            _api_call(ws.append_row, fila)

        # También escribir en hoja Pagos
        con2 = get_db()
        pago_row = con2.execute(
            "SELECT id, reserva_id, monto, metodo, referencia_externa, estado, fecha_pago, confirmado_por, notas "
            "FROM pagos WHERE reserva_id=? ORDER BY id DESC LIMIT 1", (reserva_id,)).fetchone()
        con2.close()
        if pago_row:
            ws_pagos = _api_call(sh.worksheet, "Pagos")
            fila_pago = [str(v) if v is not None else "" for v in pago_row]
            fila_pago.insert(2, str(num_reserva))  # Num_Reserva
            fila_pago.append("")  # Tiempo_Proc_Min y Notas
            _api_call(ws_pagos.append_row, fila_pago)

        # Log
        ws_log = _api_call(sh.worksheet, "Log_Operaciones")
        _api_call(ws_log.append_row, [
            datetime.now().isoformat(), "nueva_reserva", str(reserva_id),
            str(row[3] or ""), "sistema",
            f"Reserva {num_reserva} | Factura {num_factura} | {row[16]} | ${float(row[15] or 0):,.0f}",
            "", "", "", "exito", ""
        ])
    except Exception as ex:
        # Marcar para reintento
        _marcar_sync_pendiente("Reservas", event.get("reserva_id", 0))


def _sync_liberar_cubiculo_sheets(event: dict):
    """Actualiza el estado del cubículo y la reserva en Sheets al liberarlo."""
    if not GSPREAD_AVAILABLE:
        return
    client, sh = _get_module_level_client()
    if not sh:
        return
    try:
        num_cub     = event.get("numero", "")
        num_reserva = event.get("num_reserva", "")
        hora_fin    = event.get("hora_fin_real", "")

        # Actualizar Hora_Fin_Real y Estado_Pago en hoja Reservas
        if num_reserva:
            ws = _api_call(sh.worksheet, "Reservas")
            all_vals = _api_call(ws.get_all_values)
            if all_vals:
                headers = all_vals[0]
                col_num = headers.index("Numero_Reserva") if "Numero_Reserva" in headers else -1
                col_fin = headers.index("Hora_Fin_Real") if "Hora_Fin_Real" in headers else -1
                col_est = headers.index("Estado_Pago") if "Estado_Pago" in headers else -1
                for i, r in enumerate(all_vals[1:], start=2):
                    if col_num >= 0 and len(r) > col_num and r[col_num] == num_reserva:
                        if col_fin >= 0:
                            _api_call(ws.update_cell, i, col_fin + 1, str(hora_fin))
                        if col_est >= 0:
                            _api_call(ws.update_cell, i, col_est + 1, "completado")
                        break

        # Log
        ws_log = _api_call(sh.worksheet, "Log_Operaciones")
        _api_call(ws_log.append_row, [
            datetime.now().isoformat(), "liberar_cubiculo", "",
            str(num_cub), "sistema",
            f"Cubículo {num_cub} liberado | Fin real: {hora_fin}",
            "", "", "", "exito", ""
        ])

        # Actualizar hoja Cubiculos_Estado
        _sync_cubiculos_estado_con_sh(sh)
    except Exception:
        pass


def _sync_cubiculos_estado():
    """Sync periódico del estado de todos los cubículos (worker-safe)."""
    if not GSPREAD_AVAILABLE:
        return
    _, sh = _get_module_level_client()
    if not sh:
        return
    _sync_cubiculos_estado_con_sh(sh)


def _sync_cubiculos_estado_con_sh(sh):
    """Sobreescribe la hoja Cubiculos_Estado con el estado actual en tiempo real."""
    try:
        from datetime import datetime as _dt
        cubiculos = get_cubiculos()
        ws = _api_call(sh.worksheet, "Cubiculos_Estado")
        _api_call(ws.clear)
        _api_call(ws.append_row, DRIVE_SHEETS["Cubiculos_Estado"])
        for c in cubiculos:
            _api_call(ws.append_row, [
                str(c["id"]), c["numero"], c["estado"],
                "",  # Cliente_Actual (no disponible aquí)
                str(c.get("hora_inicio") or ""),
                str(c.get("hora_fin") or ""),
                str(c.get("minutos_restantes") or ""),
                c.get("wifi_ssid",""), c.get("wifi_password",""), "",
                "", "", _dt.now().isoformat(), ""
            ])
            time.sleep(0.05)
    except Exception:
        pass


def _sync_dashboard_diario():
    """Actualiza la fila del Dashboard_Diario para hoy (worker-safe)."""
    if not GSPREAD_AVAILABLE:
        return
    _, sh = _get_module_level_client()
    if not sh:
        return
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        con = get_db()
        stats = con.execute("""
            SELECT COUNT(*), SUM(total), SUM(iva),
                   COUNT(CASE WHEN estado_pago='confirmado' THEN 1 END),
                   SUM(CASE WHEN metodo_pago='Nequi'       THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='Daviplata'   THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='Efectivo'    THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='PSE'         THEN total ELSE 0 END),
                   SUM(CASE WHEN metodo_pago='MercadoPago' THEN total ELSE 0 END),
                   AVG(horas_contratadas)
            FROM reservas WHERE DATE(creado_en)=?
        """, (today_str,)).fetchone() or [0]*10
        con.close()
        brutos = float(stats[1] or 0)
        iva    = float(stats[2] or 0)
        fila   = [
            today_str, str(stats[0]), str(stats[3]), "0",
            str(brutos), str(iva), str(brutos - iva),
            str(float(stats[4] or 0)), str(float(stats[5] or 0)),
            str(float(stats[6] or 0)), str(float(stats[7] or 0)),
            str(float(stats[8] or 0)), "0", "0", "",
            str(round(float(stats[9] or 0)*60)), "0", "0", "0", "0", "0"
        ]
        # Upsert directo usando el spreadsheet del módulo
        ws = _api_call(sh.worksheet, "Dashboard_Diario")
        all_vals = _api_call(ws.get_all_values)
        headers  = all_vals[0] if all_vals else DRIVE_SHEETS["Dashboard_Diario"]
        col_idx  = headers.index("Fecha") if "Fecha" in headers else 0
        encontrado = False
        for i, r in enumerate(all_vals[1:], start=2):
            if len(r) > col_idx and r[col_idx] == today_str:
                padded = (fila + [""] * len(headers))[:len(headers)]
                _api_call(ws.update, f"A{i}", [padded])
                encontrado = True
                break
        if not encontrado:
            _api_call(ws.append_row, fila)
    except Exception:
        pass


def _sync_write_cliente(event: dict):
    """Actualiza o agrega el cliente en la hoja Clientes (worker-safe)."""
    if not GSPREAD_AVAILABLE:
        return
    _, sh = _get_module_level_client()
    if not sh:
        return
    try:
        cliente_id = event.get("cliente_id")
        if not cliente_id:
            return
        con = get_db()
        row = con.execute(
            "SELECT id,nombre,tipo_documento,numero_documento,telefono,email,ciudad,"
            "razon_social,nit_empresa,creado_en FROM clientes WHERE id=?",
            (cliente_id,)).fetchone()
        con.close()
        if not row:
            return
        fila = [
            str(row[0]), str(row[1] or ""),
            str(row[2] or ""), str(row[3] or ""),
            str(row[4] or ""), str(row[5] or ""),
            str(row[6] or ""),
            "Si" if row[7] else "No",
            str(row[7] or ""), str(row[8] or ""),
            "", "", str(row[9] or ""), str(row[9] or ""), ""
        ]
        ws = _api_call(sh.worksheet, "Clientes")
        all_vals = _api_call(ws.get_all_values)
        headers  = all_vals[0] if all_vals else DRIVE_SHEETS["Clientes"]
        col_idx  = headers.index("ID_Cliente") if "ID_Cliente" in headers else 0
        encontrado = False
        for i, r in enumerate(all_vals[1:], start=2):
            if len(r) > col_idx and r[col_idx] == str(cliente_id):
                padded = (fila + [""] * len(headers))[:len(headers)]
                _api_call(ws.update, f"A{i}", [padded])
                encontrado = True
                break
        if not encontrado:
            _api_call(ws.append_row, fila)
    except Exception:
        pass


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
        activo INTEGER DEFAULT 1
    )""")

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
    if cur.fetchone()[0] == 0:
        _seed_data(cur)

    con.commit()
    con.close()


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

    # Operadores
    for nombre, pin, rol in [("Admin JJGT", "1234", "admin"), ("Cajero", "5678", "cajero")]:
        cur.execute("INSERT INTO operadores (nombre,pin_hash,rol) VALUES (?,?,?)",
                    (nombre, _hash_pin(pin), rol))

    # Configuración
    configs = [
        ("negocio_nombre",   NEGOCIO),
        ("negocio_nit",      NIT),
        ("negocio_direccion",DIRECCION),
        ("negocio_telefono", TELEFONO),
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


def get_config(clave: str, default: str = "") -> str:
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT valor FROM configuracion_pagos WHERE clave=?", (clave,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else default


def set_config(clave: str, valor: str):
    con = get_db()
    con.execute("INSERT OR REPLACE INTO configuracion_pagos VALUES (?,?)", (clave, valor))
    con.commit()
    con.close()


def verificar_pin(pin: str, rol: str = None) -> bool:
    con = get_db()
    cur = con.cursor()
    q = "SELECT id FROM operadores WHERE pin_hash=? AND activo=1"
    params = [_hash_pin(pin)]
    if rol:
        q += " AND rol=?"
        params.append(rol)
    cur.execute(q, params)
    ok = cur.fetchone() is not None
    con.close()
    return ok


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
    desc_3h       = row[1] if row else 10
    desc_6h       = row[2] if row else 20

    descuento_pct = 0
    if horas >= 6:
        descuento_pct = desc_6h
    elif horas >= 3:
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

    # Sync a Google Sheets en background
    encolar_sync({
        "type":        "liberar_cubiculo",
        "numero":      num_cub,
        "num_reserva": num_reserva,
        "hora_fin_real": hora_fin_real,
    })
    encolar_sync({"type": "cubiculos_estado"})
    encolar_sync({"type": "dashboard_diario"})


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

def registrar_en_facturacion(reserva: dict, cliente: dict) -> str:
    """Crea la factura en la BD compartida. Retorna número de factura."""
    now   = ahora_col()
    numf  = generar_numero_factura()
    con   = get_db()
    cur   = con.cursor()

    # Insertar / recuperar cliente
    cur.execute("SELECT id FROM clientes WHERE numero_documento=?",
                (cliente.get("numero_documento",""),))
    row = cur.fetchone()
    if row:
        cliente_id = row[0]
    else:
        cur.execute("""INSERT INTO clientes
            (nombre,tipo_documento,numero_documento,telefono,email,
             razon_social,nit_empresa,tipo_persona,creado_en)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (cliente["nombre"], cliente.get("tipo_doc","CC"),
             cliente.get("numero_documento",""), cliente.get("telefono",""),
             cliente.get("email",""), cliente.get("razon_social",""),
             cliente.get("nit_empresa",""),
             "Jurídica" if cliente.get("razon_social") else "Natural",
             now.isoformat()))
        cliente_id = cur.lastrowid

    # Factura
    cur.execute("""INSERT INTO facturas
        (numero,tipo,fecha_emision,fecha_vencimiento,cliente_id,
         subtotal,descuento,iva,retenciones,total,estado,moneda,notas,
         metodo_pago,creado_en,actualizado_en)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numf, "Factura de Venta",
         now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"),
         cliente_id,
         reserva["subtotal"], reserva.get("descuento_val",0),
         reserva["iva"], 0, reserva["total"],
         "pagada", "COP",
         f"Cubículo {reserva['cubiculo_num']} · {reserva['horas']}h · WiFi+Baño+Carga",
         reserva["metodo_pago"], now.isoformat(), now.isoformat()))
    factura_id = cur.lastrowid

    # Ítem
    cur.execute("""INSERT INTO factura_items
        (factura_id,codigo,descripcion,cantidad,unidad,precio_unitario,iva_pct,subtotal)
        VALUES (?,?,?,?,?,?,?,?)""",
        (factura_id, "DESCANSO-H",
         f"Espacio de descanso {reserva['cubiculo_num']} · WiFi · Baño · Carga · {reserva['horas']}h",
         reserva["horas"], "hora",
         reserva["precio_hora"], 19.0, reserva["subtotal"]))

    con.commit()
    con.close()
    return numf, factura_id


def crear_reserva_completa(cubiculo: dict, cliente: dict, calc: dict, metodo: str) -> dict:
    """Crea reserva, factura y activa el cubículo. Retorna dict con todos los datos."""
    # ── Guard anti-duplicado: si ya existe voucher en session_state con mismo cubículo
    #    y fue creado en los últimos 30s, devolver el voucher existente sin re-insertar.
    if (st.session_state.get("voucher") and
            st.session_state.get("pago_confirmado") and
            st.session_state["voucher"].get("cubiculo") == cubiculo["numero"]):
        return st.session_state["voucher"]

    # Verificar que el cubículo sigue libre antes de insertar
    con_check = get_db()
    estado_actual = con_check.execute(
        "SELECT estado FROM cubiculos WHERE id=?", (cubiculo["id"],)).fetchone()
    con_check.close()
    if estado_actual and estado_actual[0] != "libre":
        raise Exception(f"El cubículo {cubiculo['numero']} ya no está disponible.")

    now  = ahora_col()
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
    num_fact, factura_id = registrar_en_facturacion(reserva_data, cliente)

    con = get_db()
    cur = con.cursor()

    # Cliente id
    cur.execute("SELECT id FROM clientes WHERE numero_documento=?",
                (cliente.get("numero_documento",""),))
    row = cur.fetchone()
    cliente_id = row[0] if row else None

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

    # Pago
    cur.execute("""INSERT INTO pagos (reserva_id,monto,metodo,estado,fecha_pago)
                   VALUES (?,?,?,'confirmado',?)""",
                (reserva_id, calc["total"], metodo, now.isoformat()))

    con.commit()
    con.close()

    activar_cubiculo(cubiculo["id"], reserva_id, hora_fin.isoformat())

    # Sync a Drive
    _drive_sync_background(num_res, cliente, reserva_id, num_fact)

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
# GOOGLE SHEETS — ARCHIVO "jjgt_pagos"
# ══════════════════════════════════════════════════════════════════════════════
#
# Configurar .streamlit/secrets.toml:
#   [sheetsemp]
#   credentials_sheet = '''{ ... JSON de Service Account de Google Cloud ... }'''
#
# O en Streamlit Cloud → App Settings → Secrets
# ══════════════════════════════════════════════════════════════════════════════

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def init_google_drive():
    """
    Abre o crea el archivo 'jjgt_pagos' en Google Drive.
    Retorna el objeto spreadsheet o None si falla.
    """
    if not GSPREAD_AVAILABLE:
        return None
    creds, _ = load_credentials_from_toml()
    if not creds:
        return None
    client = get_google_sheets_connection(creds)
    if not client:
        return None
    return get_or_create_spreadsheet(client)


DRIVE_SHEETS = {
    "Reservas":         ["ID_Reserva","Numero_Reserva","Fecha_Hora","Cubiculo",
                         "Cliente_Nombre","Documento","Telefono","Email",
                         "Horas","Hora_Inicio","Hora_Fin_Prog","Hora_Fin_Real",
                         "Precio_Hora","Subtotal","IVA","Total_COP",
                         "Metodo_Pago","Estado_Pago","Codigo_Acceso",
                         "WiFi_SSID","WiFi_Pass","Num_Factura","Referencia","Operador","Notas"],
    "Pagos":            ["ID_Pago","ID_Reserva","Num_Reserva","Fecha_Pago",
                         "Monto_COP","Metodo","Referencia_Externa","Estado",
                         "Confirmado_Por","Tiempo_Proc_Min","Notas"],
    "Clientes":         ["ID_Cliente","Nombre","Tipo_Doc","Num_Doc","Telefono",
                         "Email","Ciudad","Req_Factura_Empresa","Razon_Social",
                         "NIT_Empresa","Total_Reservas","Total_Gastado_COP",
                         "Primera_Visita","Ultima_Visita","Notas"],
    "Cubiculos_Estado": ["Cubiculo_ID","Numero","Estado","Cliente_Actual",
                         "Hora_Inicio","Hora_Fin_Prog","Tiempo_Rest_Min",
                         "WiFi_SSID","WiFi_Pass","Codigo_Acceso","Total_Reservas",
                         "Ingresos_Total","Ultimo_Mant","Notas"],
    "Facturas":         ["Num_Factura","Fecha_Emision","Fecha_Venc",
                         "Cliente","Documento","Email","Razon_Social","NIT_Emp",
                         "Descripcion","Cantidad_Horas","Precio_Hora","Subtotal",
                         "Descuento","Base_Gravable","IVA_19pct","Total_COP",
                         "Metodo_Pago","Estado","Num_Reserva","Cubiculo","Creado_En"],
    "Dashboard_Diario": ["Fecha","Total_Reservas","Completadas","Canceladas",
                         "Ingresos_Brutos","IVA_Recaudado","Ingresos_Netos",
                         "Nequi_COP","Daviplata_COP","Efectivo_COP","PSE_COP",
                         "MP_COP","Otros_COP","Ocupacion_Pct","Hora_Pico",
                         "Tiempo_Prom_Min","Clientes_Nuevos","Clientes_Recur",
                         "Fact_Min","Fact_Max","Ticket_Prom_COP"],
    "Tarifas_Config":   ["ID","Nombre","Descripcion","Precio_Hora_COP",
                         "Hora_Ini_Espec","Hora_Fin_Espec","Desc_3h_Pct",
                         "Desc_6h_Pct","Activo","Vigente_Desde","Notas"],
    "Log_Operaciones":  ["Timestamp","Tipo_Op","Reserva_ID","Cubiculo",
                         "Operador","Descripcion","Valor_Ant","Valor_Nuevo",
                         "IP","Estado","Notas"],
}


# ══════════════════════════════════════════════════════════════════════════════
# CREDENCIALES — lee st.secrets primero, luego secrets.toml como fallback
# ══════════════════════════════════════════════════════════════════════════════

def load_credentials_from_toml():
    """
    Obtiene las credenciales de servicio de Google.
    Orden de búsqueda:
      1. st.secrets["sheetsemp"]["credentials_sheet"]  (Streamlit Cloud / local secrets.toml)
      2. Archivo .streamlit/secrets.toml leído manualmente con toml
      3. None si no se encuentra nada
    Retorna (dict_credenciales, None)
    """
    # ── Intento 1: st.secrets ────────────────────────────────────────────────
    try:
        raw = st.secrets["sheetsemp"]["credentials_sheet"]
        if isinstance(raw, str):
            creds = json.loads(raw)
        else:
            # st.secrets puede devolver AttrDict → convertir a dict plano
            creds = dict(raw)
        if "private_key" in creds and "client_email" in creds:
            return creds, None
    except Exception:
        pass  # st.secrets no disponible o clave inexistente → probar con toml

    # ── Intento 2: leer secrets.toml directamente ────────────────────────────
    toml_candidates = [
        ".streamlit/secrets.toml",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"),
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    for toml_path in toml_candidates:
        if not os.path.isfile(toml_path):
            continue
        try:
            if TOML_AVAILABLE:
                config = toml_lib.load(toml_path)
            else:
                # Fallback: leer como texto y buscar la sección manualmente
                with open(toml_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
                import re
                match = re.search(r"credentials_sheet\s*=\s*'''(.*?)'''", raw_text, re.DOTALL)
                if match:
                    creds = json.loads(match.group(1).strip())
                    if "private_key" in creds and "client_email" in creds:
                        return creds, None
                continue
            raw = config.get("sheetsemp", {}).get("credentials_sheet")
            if raw is None:
                continue
            if isinstance(raw, str):
                creds = json.loads(raw)
            else:
                creds = dict(raw)
            if "private_key" in creds and "client_email" in creds:
                return creds, None
        except Exception:
            continue

    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — reintentos ante quota 429
# ══════════════════════════════════════════════════════════════════════════════

def _is_quota_err(exc) -> bool:
    """Detecta errores 429 (quota excedida) de la API de Google."""
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate limit" in msg or "too many requests" in msg


def _api_call(fn, *args, retries: int = 4, base_wait: float = 2.0, **kwargs):
    """
    Ejecuta fn(*args, **kwargs) con reintentos exponenciales ante errores 429.
    Espera: 2s, 4s, 8s, 16s antes de lanzar la excepción final.
    """
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if _is_quota_err(exc) and attempt < retries - 1:
                wait = base_wait * (2 ** attempt)
                time.sleep(wait)
            else:
                raise


# ══════════════════════════════════════════════════════════════════════════════
# CONEXIÓN — sin @st.cache_resource para evitar problemas de hasheo con dicts
# ══════════════════════════════════════════════════════════════════════════════

# ── Cliente gspread a nivel de módulo (thread-safe, sin session_state) ────────
_gs_module_client = None
_gs_module_client_lock = threading.Lock()
_gs_module_spreadsheet = None


def get_google_sheets_connection(creds: dict):
    """
    Crea y devuelve un cliente gspread autenticado.
    Versión dual: en el hilo principal guarda en session_state;
    en hilos background usa el cache a nivel de módulo (_gs_module_client).
    Esto permite que el worker thread acceda a Sheets sin st.session_state.
    """
    global _gs_module_client
    if not GSPREAD_AVAILABLE:
        return None
    try:
        # Intentar usar session_state si estamos en el hilo principal de Streamlit
        try:
            existing = st.session_state.get("_gs_client")
            if existing is not None:
                return existing
        except Exception:
            pass  # Estamos en un worker thread — session_state no disponible

        # Cache a nivel de módulo para worker threads
        with _gs_module_client_lock:
            if _gs_module_client is not None:
                return _gs_module_client

        credentials = Credentials.from_service_account_info(creds, scopes=_SCOPES)
        client = gspread.authorize(credentials)

        # Guardar en ambos caches
        with _gs_module_client_lock:
            _gs_module_client = client
        try:
            st.session_state._gs_client = client
        except Exception:
            pass  # Worker thread — ignorar
        return client
    except Exception as e:
        try:
            st.error(f"❌ Error conectando a Google Sheets: {e}")
        except Exception:
            pass  # Worker thread
        return None


def _get_module_level_client():
    """
    Obtiene (o crea) el cliente gspread a nivel de módulo SIN depender de Streamlit.
    Usado exclusivamente por el worker thread de sincronización.
    """
    global _gs_module_client, _gs_module_spreadsheet
    if not GSPREAD_AVAILABLE:
        return None, None
    with _gs_module_client_lock:
        if _gs_module_client is not None and _gs_module_spreadsheet is not None:
            return _gs_module_client, _gs_module_spreadsheet
    # Cargar credenciales leyendo el TOML directamente (sin st.secrets)
    creds, _ = load_credentials_from_toml()
    if not creds:
        return None, None
    try:
        credentials = Credentials.from_service_account_info(creds, scopes=_SCOPES)
        client = gspread.authorize(credentials)
        # Abrir o crear el spreadsheet
        sid = get_config("drive_spreadsheet_id", "")
        if sid:
            sh = _api_call(client.open_by_key, sid)
        else:
            try:
                sh = _api_call(client.open, DRIVE_FILE)
            except Exception:
                sh = _api_call(client.create, DRIVE_FILE)
                set_config("drive_spreadsheet_id", sh.id)
        # Verificar hojas
        existing = [ws.title for ws in _api_call(sh.worksheets)]
        for name, headers in DRIVE_SHEETS.items():
            if name not in existing:
                ws = _api_call(sh.add_worksheet, title=name,
                               rows=2000, cols=max(len(headers), 26))
                _api_call(ws.append_row, headers)
                time.sleep(0.3)
        with _gs_module_client_lock:
            _gs_module_client = client
            _gs_module_spreadsheet = sh
        return client, sh
    except Exception:
        return None, None


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE UNA HOJA — robusto, sin get_all_records
# ══════════════════════════════════════════════════════════════════════════════

def _parse_sheet_values(all_values: list) -> pd.DataFrame:
    """Convierte lista de listas (get_all_values) en DataFrame limpio."""
    if not all_values or len(all_values) < 2:
        return pd.DataFrame()
    raw_headers = all_values[0]
    headers, seen = [], {}
    for h in raw_headers:
        h = str(h).strip()
        if not h:
            h = f"_col{len(headers)}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        headers.append(h)
    data_rows = []
    for row in all_values[1:]:
        padded = (row + [""] * len(headers))[:len(headers)]
        if any(str(v).strip() for v in padded):
            data_rows.append(padded)
    return pd.DataFrame(data_rows, columns=headers)


def load_data_from_sheet(client, sheet_name: str, worksheet_name: str) -> pd.DataFrame:
    """
    Carga una hoja usando get_all_values() con reintentos automáticos ante 429.
    """
    try:
        sheet      = _api_call(client.open, sheet_name)
        worksheet  = _api_call(sheet.worksheet, worksheet_name)
        all_values = _api_call(worksheet.get_all_values)
        return _parse_sheet_values(all_values)
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"⚠️ Hoja '{worksheet_name}' no existe en '{sheet_name}'.")
        return pd.DataFrame()
    except Exception as e:
        if _is_quota_err(e):
            st.warning(
                f"⚠️ Límite de solicitudes alcanzado al cargar '{worksheet_name}'. "
                f"La API permite 60 lecturas/min. Espera un momento y recarga.")
        else:
            st.warning(f"⚠️ Error cargando '{worksheet_name}': {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DEL SPREADSHEET — crear/verificar hojas
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_spreadsheet(client):
    """
    Abre 'jjgt_pagos' si existe, o lo crea. Verifica y crea las 8 hojas.
    Retorna el objeto spreadsheet o None si falla.
    """
    try:
        sid = get_config("drive_spreadsheet_id", "")
        if sid:
            sh = _api_call(client.open_by_key, sid)
        else:
            try:
                sh = _api_call(client.open, DRIVE_FILE)
            except gspread.exceptions.SpreadsheetNotFound:
                sh = _api_call(client.create, DRIVE_FILE)
                set_config("drive_spreadsheet_id", sh.id)

        # Verificar / crear hojas faltantes
        existing = [ws.title for ws in _api_call(sh.worksheets)]
        for name, headers in DRIVE_SHEETS.items():
            if name not in existing:
                ws = _api_call(sh.add_worksheet, title=name,
                               rows=2000, cols=max(len(headers), 26))
                _api_call(ws.append_row, headers)
                time.sleep(0.5)   # pausa pequeña para evitar 429 al crear muchas hojas

        # Eliminar hoja por defecto vacía si existe
        for default_name in ["Sheet1", "Hoja 1", "Hoja1"]:
            if default_name in existing:
                try:
                    _api_call(sh.del_worksheet, sh.worksheet(default_name))
                except Exception:
                    pass

        return sh
    except Exception as e:
        return None


def get_active_client():
    """
    Helper centralizado: carga credenciales → crea cliente → retorna (client, sh, error_msg).
    Usado por todas las funciones de escritura y lectura.
    """
    if not GSPREAD_AVAILABLE:
        return None, None, "gspread no instalado. Ejecuta: pip install gspread google-auth"
    creds, _ = load_credentials_from_toml()
    if not creds:
        return None, None, ("No se encontraron credenciales. Configura .streamlit/secrets.toml "
                             "con la sección [sheetsemp] y la clave credentials_sheet.")
    client = get_google_sheets_connection(creds)
    if not client:
        return None, None, "No se pudo autenticar con Google Sheets."
    sh = get_or_create_spreadsheet(client)
    if not sh:
        return client, None, "No se pudo abrir/crear el archivo jjgt_pagos."
    return client, sh, None


# ══════════════════════════════════════════════════════════════════════════════
# ESCRITURA EN SHEETS — append / update / upsert
# ══════════════════════════════════════════════════════════════════════════════

def sheets_append_row(worksheet_name: str, row_data: list) -> bool:
    """Agrega una fila al final de la hoja indicada. Retorna True si éxito."""
    _, sh, err = get_active_client()
    if err:
        _marcar_sync_pendiente(worksheet_name, 0)
        return False
    try:
        ws = _api_call(sh.worksheet, worksheet_name)
        _api_call(ws.append_row, [str(v) if v is not None else "" for v in row_data])
        return True
    except Exception as e:
        _marcar_sync_pendiente(worksheet_name, 0)
        return False


def sheets_update_row(worksheet_name: str, col_key: str, key_value: str,
                      update_data: dict) -> bool:
    """
    Busca la fila donde col_key == key_value y actualiza las columnas indicadas.
    update_data = {"NombreColumna": "NuevoValor", ...}
    """
    _, sh, err = get_active_client()
    if err:
        return False
    try:
        ws         = _api_call(sh.worksheet, worksheet_name)
        all_vals   = _api_call(ws.get_all_values)
        df         = _parse_sheet_values(all_vals)
        if df.empty or col_key not in df.columns:
            return False
        matches    = df.index[df[col_key].astype(str) == str(key_value)].tolist()
        if not matches:
            return False
        row_idx    = matches[0] + 2   # +1 header, +1 base-1 de gspread
        headers    = list(df.columns)
        for col_name, new_val in update_data.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                _api_call(ws.update_cell, row_idx, col_idx, str(new_val))
        return True
    except Exception:
        return False


def sheets_upsert_row(worksheet_name: str, col_key: str,
                      key_value: str, row_data: list) -> bool:
    """
    Si existe una fila con col_key == key_value: actualiza toda la fila.
    Si no existe: agrega nueva fila.
    """
    _, sh, err = get_active_client()
    if err:
        _marcar_sync_pendiente(worksheet_name, 0)
        return False
    try:
        ws       = _api_call(sh.worksheet, worksheet_name)
        all_vals = _api_call(ws.get_all_values)
        if not all_vals:
            _api_call(ws.append_row, DRIVE_SHEETS.get(worksheet_name, []))
            all_vals = _api_call(ws.get_all_values)

        headers  = all_vals[0] if all_vals else []
        col_idx  = headers.index(col_key) if col_key in headers else -1
        row_str  = [str(v) if v is not None else "" for v in row_data]

        if col_idx >= 0:
            for i, r in enumerate(all_vals[1:], start=2):
                if len(r) > col_idx and str(r[col_idx]) == str(key_value):
                    # Actualizar fila existente
                    padded = (row_str + [""] * len(headers))[:len(headers)]
                    _api_call(ws.update, f"A{i}", [padded])
                    return True

        # No encontrada → agregar
        _api_call(ws.append_row, row_str)
        return True
    except Exception:
        _marcar_sync_pendiente(worksheet_name, 0)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# SINCRONIZACIÓN — background y completa
# ══════════════════════════════════════════════════════════════════════════════

def _marcar_sync_pendiente(tabla: str, registro_id: int):
    """Registra en SQLite que un registro necesita ser sincronizado a Drive."""
    try:
        con = get_db()
        con.execute(
            "INSERT INTO sync_log (tabla,registro_id,accion,sync_pendiente,creado_en) VALUES (?,?,?,1,?)",
            (tabla, registro_id, "upsert", ahora_col().isoformat()))
        con.commit()
        con.close()
    except Exception:
        pass


def _drive_sync_background(num_reserva: str, cliente: dict,
                            reserva_id: int, num_factura: str):
    """
    Encola la sincronización en el worker thread — no bloquea el hilo principal.
    El worker escribirá en Google Sheets de forma asíncrona.
    """
    encolar_sync({
        "type":        "nueva_reserva",
        "num_reserva": num_reserva,
        "reserva_id":  reserva_id,
        "num_factura": num_factura,
        "cliente":     cliente,
    })
    # También encolar cliente y dashboard
    con = get_db()
    row = con.execute("SELECT id FROM clientes WHERE numero_documento=?",
                      (cliente.get("numero_documento",""),)).fetchone()
    con.close()
    if row:
        encolar_sync({"type": "cliente", "cliente_id": row[0]})
    encolar_sync({"type": "dashboard_diario"})
    encolar_sync({"type": "cubiculos_estado"})


def sincronizacion_completa() -> dict:
    """
    Exporta todo el contenido de SQLite al archivo jjgt_pagos en Google Sheets.
    Retorna dict con conteo de registros sincronizados por hoja.
    """
    client, sh, err = get_active_client()
    if err:
        return {"error": err}

    con  = get_db()
    cur  = con.cursor()
    conteos = {}

    tablas_map = [
        ("reservas",       "Reservas",       "Reservas"),
        ("pagos",          "Pagos",          "Pagos"),
        ("clientes",       "Clientes",       "Clientes"),
        ("facturas",       "Facturas",       "Facturas"),
        ("factura_items",  "Factura_Items",  "Factura_Items"),
        ("cubiculos",      "Cubiculos",      "Cubiculos"),
        ("tarifas",        "Tarifas_Config", "Tarifas_Config"),
        ("operadores",     "Operadores",     "Operadores"),
        ("configuracion_pagos",  "Configuracion_Pagos",   "Configuracion_Pagos"),
    ]

    for tabla_sql, sheet_name, _ in tablas_map:
        try:
            cur.execute(f"SELECT * FROM {tabla_sql}")
            rows = cur.fetchall()
            ws   = _api_call(sh.worksheet, sheet_name)
            _api_call(ws.clear)
            _api_call(ws.append_row, DRIVE_SHEETS[sheet_name])
            for row in rows:
                row_str = [str(v) if v is not None else "" for v in row]
                _api_call(ws.append_row, row_str)
                time.sleep(0.1)   # micro-pausa para evitar 429
            conteos[sheet_name] = len(rows)
        except Exception as e:
            conteos[sheet_name] = f"Error: {e}"

    # Cubículos en tiempo real
    try:
        cubiculos = get_cubiculos()
        ws = _api_call(sh.worksheet, "Cubiculos_Estado")
        _api_call(ws.clear)
        _api_call(ws.append_row, DRIVE_SHEETS["Cubiculos_Estado"])
        for c in cubiculos:
            _api_call(ws.append_row, [
                str(c["id"]), c["numero"], c["estado"], "",
                str(c.get("hora_inicio") or ""),
                str(c.get("hora_fin") or ""),
                str(c.get("minutos_restantes") or ""),
                c.get("wifi_ssid",""), c.get("wifi_password",""), "",
                "", "", "", ""
            ])
            time.sleep(0.1)
        conteos["Cubiculos_Estado"] = len(cubiculos)
    except Exception as e:
        conteos["Cubiculos_Estado"] = f"Error: {e}"

    # Dashboard diario
    try:
        today_str = ahora_col().strftime("%Y-%m-%d")
        cur.execute("""SELECT COUNT(*), SUM(total), SUM(iva),
                              COUNT(CASE WHEN estado_pago='confirmado' THEN 1 END),
                              SUM(CASE WHEN metodo_pago='Nequi' THEN total ELSE 0 END),
                              SUM(CASE WHEN metodo_pago='Daviplata' THEN total ELSE 0 END),
                              SUM(CASE WHEN metodo_pago='Efectivo' THEN total ELSE 0 END),
                              SUM(CASE WHEN metodo_pago='PSE' THEN total ELSE 0 END),
                              SUM(CASE WHEN metodo_pago='MercadoPago' THEN total ELSE 0 END),
                              AVG(horas_contratadas)
                       FROM reservas WHERE DATE(creado_en)=?""", (today_str,))
        stats = cur.fetchone() or [0]*10
        ingresos_brutos = float(stats[1] or 0)
        iva_rec         = float(stats[2] or 0)
        row_dash = [
            today_str, stats[0], stats[3], 0,
            ingresos_brutos, iva_rec, ingresos_brutos - iva_rec,
            float(stats[4] or 0), float(stats[5] or 0), float(stats[6] or 0),
            float(stats[7] or 0), float(stats[8] or 0), 0,
            0, "", round(float(stats[9] or 0) * 60), 0, 0, 0, 0, 0
        ]
        sheets_upsert_row("Dashboard_Diario", "Fecha", today_str, row_dash)
        conteos["Dashboard_Diario"] = 1
    except Exception as e:
        conteos["Dashboard_Diario"] = f"Error: {e}"

    # Log de la sincronización
    try:
        sheets_append_row("Log_Operaciones", [
            ahora_col().isoformat(), "sync_completa", "", "",
            "sistema", "Sincronización completa ejecutada",
            "", "", "", "exito", json.dumps({k: v for k, v in conteos.items()
                                              if not str(v).startswith("Error")})
        ])
    except Exception:
        pass

    con.commit()
    con.close()
    return conteos


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
        "pantalla":         "bienvenida",
        "cubiculo_sel":     None,
        "horas_sel":        1.0,
        "calc":             None,
        "cliente":          {},
        "metodo_pago":      None,
        "voucher":          None,
        "pago_confirmado":  False,
        "operador_ok":      False,
        "pin_intentos":     0,
        "modulo_op":        "dashboard",
        "_backup_fecha":    "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _auto_backup_diario():
    """Genera backup diario en disco si no se hizo hoy."""
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


init_state()


def ir_a(pantalla: str):
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

    # Botón principal
    _, col, _ = st.columns([1, 2, 1])
    with col:
        if libres > 0:
            if st.button("🛏️  RESERVAR MI ESPACIO", type="primary", use_container_width=True):
                ir_a("seleccion")
        else:
            st.markdown('<div class="alerta-roja">❌ No hay cubículos disponibles en este momento.<br>Por favor espera o consulta a un operador.</div>', unsafe_allow_html=True)

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

    # Acceso operador
    st.markdown("<br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([3, 1, 3])
    with c2:
        if st.button("👤 Operador", use_container_width=True):
            st.session_state.pantalla = "operador_login"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 1 — SELECCIÓN DE CUBÍCULO Y TIEMPO
# ══════════════════════════════════════════════════════════════════════════════

def show_seleccion():
    render_header("Elige tu cubículo y tiempo de descanso")
    render_stepper(0)
    inject_live_clock()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### ⏱️ ¿Cuánto tiempo necesitas?")
        tiempos = {"30 min": 0.5, "1 hora": 1.0, "2 horas": 2.0,
                   "3 horas": 3.0, "4 horas": 4.0, "⚙️ Personalizar": -1}
        cols_t  = st.columns(3)
        for i, (label, val) in enumerate(tiempos.items()):
            with cols_t[i % 3]:
                sel = st.session_state.horas_sel
                activo = (sel == val) or (val == -1 and sel not in [0.5,1,2,3,4])
                if st.button(label, key=f"btn_t_{i}",
                             type="primary" if activo else "secondary",
                             use_container_width=True):
                    if val == -1:
                        st.session_state.horas_sel = 1.5
                    else:
                        st.session_state.horas_sel = val
                    st.rerun()

        horas = st.session_state.horas_sel
        if horas not in [0.5, 1.0, 2.0, 3.0, 4.0]:
            horas = st.number_input("Horas personalizadas", min_value=0.5, max_value=12.0,
                                     value=float(horas), step=0.5)
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
        if st.button("← Volver", use_container_width=True):
            ir_a("bienvenida")
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
            if st.button("← Volver", use_container_width=True):
                ir_a("seleccion")
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
    if st.button("← Volver a mis datos", use_container_width=True):
        ir_a("datos")


def _pago_nequi(monto: int, ref: str):
    nequi_num = get_config("nequi_numero", NEQUI_NUM)
    st.markdown(f"""
    <div style="background:rgba(0,100,40,0.2);border:2px solid rgba(0,255,100,0.3);
                border-radius:12px;padding:20px;margin-bottom:16px">
      <div style="font-size:20px;font-weight:700;color:#00c853;margin-bottom:8px">
        💚 Pago con Nequi
      </div>
      <div style="font-size:16px;color:#e2e8f0">
        Envía <b style="color:#00ff88">{fmt_cop(monto)} COP</b><br>
        al número <b style="font-family:'Inconsolata';font-size:22px;color:#00ff88">{nequi_num}</b><br>
        desde tu app Nequi
      </div>
    </div>
    """, unsafe_allow_html=True)
    mostrar_qr("Nequi", monto, ref)
    st.markdown("""
    <div style="text-align:center;margin-top:8px">
      <div style="font-size:13px;color:#94a3b8">
        Abre Nequi → Pagar → Escanear QR o Enviar a número
      </div>
    </div>
    """, unsafe_allow_html=True)
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
    render_header("Procesando tu pago")
    render_stepper(3)

    _, col, _ = st.columns([1, 2, 1])
    with col:
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
        if st.button("✅ IR A MI CUBÍCULO", type="primary", use_container_width=True):
            # Reset flujo
            for k in ["pantalla","cubiculo_sel","horas_sel","calc","cliente",
                       "metodo_pago","voucher","pago_confirmado"]:
                if k == "pantalla":
                    st.session_state[k] = "bienvenida"
                elif k == "horas_sel":
                    st.session_state[k] = 1.0
                elif k in ["cubiculo_sel","calc","metodo_pago","voucher"]:
                    st.session_state[k] = None
                elif k == "pago_confirmado":
                    st.session_state[k] = False
                elif k == "cliente":
                    st.session_state[k] = {}
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PANEL OPERADOR — LOGIN
# ══════════════════════════════════════════════════════════════════════════════

def show_operador_login():
    render_header("Acceso Operador")
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🔐 Panel de Operador")
        st.caption("Ingresa tu PIN de operador para acceder")
        pin = st.text_input("PIN", type="password", max_chars=8, placeholder="••••",
                            key="pin_login_input")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Cancelar", use_container_width=True):
                ir_a("bienvenida")
        with c2:
            if st.button("✅ Entrar", type="primary", use_container_width=True):
                if verificar_pin(pin):
                    st.session_state.operador_ok = True
                    st.session_state.pantalla    = "operador"
                    st.rerun()
                else:
                    st.session_state.pin_intentos += 1
                    if st.session_state.pin_intentos >= 3:
                        st.error("Demasiados intentos. Contacta al administrador.")
                    else:
                        st.error(f"PIN incorrecto ({st.session_state.pin_intentos}/3)")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PANEL OPERADOR — MÓDULOS
# ══════════════════════════════════════════════════════════════════════════════

def show_operador():
    if not st.session_state.operador_ok:
        ir_a("operador_login")
        return

    # Auto-rerun del panel operador cada 30 segundos para refrescar cubículos y KPIs
    now_ts = int(time.time())
    last_rerun = st.session_state.get("_op_last_rerun", 0)
    if now_ts - last_rerun >= 30:
        st.session_state["_op_last_rerun"] = now_ts
        # Solo rerunear si estamos en el dashboard (no interrumpir acciones del operador)
        if st.session_state.get("modulo_op_radio", "🏠 Dashboard") == "🏠 Dashboard":
            st.rerun()

    # Sidebar operador
    with st.sidebar:
        st.markdown(f"## 🔧 {NEGOCIO}")
        st.markdown("**Panel de Operador**")
        st.divider()
        modulo = st.radio("Módulo", [
            "🏠 Dashboard",
            "🛏️ Cubículos",
            "⏳ Pagos Pendientes",
            "📊 Reportes",
            "☁️ Google Drive",
            "⚙️ Configuración",
        ], key="modulo_op_radio")
        st.divider()

        # Estado Drive
        drive_ok = os.path.exists(get_config("drive_credentials_path", "credentials.json"))
        estado_drive = "🟢 Drive configurado" if drive_ok else "🔴 Drive no configurado"
        st.caption(estado_drive)

        if st.button("🚪 Salir del panel", use_container_width=True):
            st.session_state.operador_ok = False
            ir_a("bienvenida")

    render_header("Panel de Operador")

    mod_map = {
        "🏠 Dashboard":       _op_dashboard,
        "🛏️ Cubículos":       _op_cubiculos,
        "⏳ Pagos Pendientes": _op_pagos_pendientes,
        "📊 Reportes":        _op_reportes,
        "☁️ Google Drive":    _op_google_drive,
        "⚙️ Configuración":   _op_configuracion,
    }
    mod_map.get(modulo, _op_dashboard)()


def _op_dashboard():
    st.markdown("### 🏠 Dashboard Operacional")
    inject_live_clock()
    # Auto-rerun del servidor cada 30s para refrescar KPIs y estados (sin recarga manual)
    st.markdown("""
    <script>
    (function(){
      if (!window._jjgt_dash_refresh) {
        window._jjgt_dash_refresh = true;
        setInterval(function(){
          // Simular click en cualquier botón de Streamlit para forzar rerun
          // Alternativa: usar el mecanismo interno de Streamlit
          var btn = document.querySelector('[data-testid="stBaseButton-secondary"]');
          if (!btn) {
            // Intentar forzar rerun via WebSocket message (Streamlit interno)
            try {
              window.parent.postMessage({type: "streamlit:forceRerun"}, "*");
            } catch(e) {}
          }
        }, 30000);
      }
    })();
    </script>
    """, unsafe_allow_html=True)

    # Contador de rerun cada 30s usando session_state
    if "dash_rerun_counter" not in st.session_state:
        st.session_state.dash_rerun_counter = 0
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
                        st.rerun()
                else:
                    if st.button(f"✅ Listo {cub['numero']}", key=f"ok_{cub['id']}"):
                        con = get_db()
                        con.execute("UPDATE cubiculos SET estado='libre' WHERE id=?",
                                    (cub["id"],))
                        con.commit()
                        con.close()
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


def _op_google_drive():
    st.markdown("### ☁️ Integración con Google Drive")
    st.markdown(f"**Archivo destino:** `{DRIVE_FILE}`")

    #c1, c2 = st.columns(2)
    #with c1:
    #    creds_file = st.file_uploader("📤 Subir credentials.json", type=["json"])
    #    if creds_file:
    #        creds_path = "credentials.json"
    #        with open(creds_path, "wb") as f:
    #            f.write(creds_file.read())
    #        set_config("drive_credentials_path", creds_path)
    #        # Invalidar cache del cliente para reconectar con nuevas credenciales
    #        global _gs_module_client  # noqa
    #        global _gs_module_spreadsheet  # noqa
    #        _gs_module_client = None
    #        _gs_module_spreadsheet = None
    #        try:
    #            st.session_state._gs_client = None
    #        except Exception:
    #            pass
    #        st.success("✅ Credenciales guardadas")

    #with c2:
    #    sheet_id = st.text_input("ID del Spreadsheet existente (opcional)",
    #                              value=get_config("drive_spreadsheet_id",""),
    #                              placeholder="Dejar vacío para crear/buscar automáticamente")
    #    if sheet_id:
    #        set_config("drive_spreadsheet_id", sheet_id)

    st.divider()
    creds_ok = os.path.exists(get_config("drive_credentials_path","credentials.json"))
    #st.info("✅ credentials.json presente" if creds_ok else
    #        "⚠️ Sube el archivo credentials.json de tu Service Account de Google Cloud")

    # ── Mostrar enlace al archivo si ya está configurado ──────────────────────
    sid_saved = get_config("drive_spreadsheet_id", "1SjiLLK3bVqUNWaqvDaQzB3_JLNfJYe58YjFM47c7GMw")
    if sid_saved:
        drive_url = f"https://docs.google.com/spreadsheets/d/{sid_saved}/edit"
        st.markdown(
            f'🔗 **Archivo en Drive:** <a href="{drive_url}" target="_blank">'
            f'Abrir jjgt_pagos en Google Sheets</a>',
            unsafe_allow_html=True)

    c3, c4, c5 = st.columns(3)
    with c3:
        if st.button("🔗 Probar / crear archivo", use_container_width=True):
            with st.spinner("Conectando y verificando jjgt_pagos..."):
                sh = init_google_drive()
                if sh:
                    drive_url2 = f"https://docs.google.com/spreadsheets/d/{sh.id}/edit"
                    st.success(f"✅ Conectado: **{sh.title}**")
                    st.markdown(
                        f'<a href="{drive_url2}" target="_blank" style="color:#00d4ff">'
                        f'📄 Abrir {sh.title}</a>', unsafe_allow_html=True)
                    set_config("drive_spreadsheet_id", sh.id)
                else:
                    st.error("❌ No se pudo conectar. Verifica credentials.json")

    with c4:
        if st.button("📋 Crear/verificar estructura", use_container_width=True):
            with st.spinner("Creando hojas..."):
                sh = init_google_drive()
                if sh:
                    hojas = [ws.title for ws in sh.worksheets()]
                    st.success(f"✅ Hojas: {', '.join(hojas)}")
                else:
                    st.error("❌ Sin conexión a Drive")

    with c5:
        if st.button("☁️ Sincronizar todo ahora", type="primary", use_container_width=True):
            with st.spinner("Sincronizando..."):
                resultado = sincronizacion_completa()
                if "error" in resultado:
                    st.error(resultado["error"])
                else:
                    st.success("✅ Sincronización completada")
                    st.json(resultado)

    st.divider()

    # ── Cargar y mostrar datos desde Google Sheets ────────────────────────────
    st.markdown("#### 📊 Datos en Google Sheets")
    if not GSPREAD_AVAILABLE:
        st.warning("gspread no instalado.")
    elif not creds_ok and not get_config("drive_spreadsheet_id",""):
        st.info("Configura las credenciales para ver los datos.")
    else:
        hoja_sel = st.selectbox("Ver hoja:", list(DRIVE_SHEETS.keys()), key="gs_hoja_sel")
        if st.button("🔄 Cargar datos de Google Sheets", use_container_width=True):
            with st.spinner(f"Cargando {hoja_sel}..."):
                client_gs, sh_gs, err_gs = get_active_client()
                if err_gs:
                    st.error(f"❌ {err_gs}")
                else:
                    df_gs = load_data_from_sheet(client_gs, DRIVE_FILE, hoja_sel)
                    if df_gs.empty:
                        st.info(f"La hoja '{hoja_sel}' está vacía o no existe.")
                    else:
                        st.success(f"✅ {len(df_gs)} filas cargadas desde '{hoja_sel}'")
                        st.dataframe(df_gs, use_container_width=True, hide_index=True)

                        # Botón de descarga
                        csv_gs = df_gs.to_csv(index=False).encode()
                        st.download_button(
                            f"📥 Descargar {hoja_sel} como CSV",
                            data=csv_gs,
                            file_name=f"jjgt_pagos_{hoja_sel.lower()}_{ahora_col().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

    st.divider()
    st.markdown("**Hojas que se crearán en `jjgt_pagos`:**")
    for nombre, cols in DRIVE_SHEETS.items():
        st.markdown(f"- **{nombre}** ({len(cols)} columnas): `{', '.join(cols[:6])}...`")


def _op_configuracion():
    st.markdown("### ⚙️ Configuración del Sistema")
    tabs = st.tabs(["🏢 Negocio", "💰 Pagos", "🛏️ Tarifas", "👤 Operadores"])

    with tabs[0]:
        st.markdown("**Datos del negocio**")
        nombre_n = st.text_input("Nombre del negocio",
                                  value=get_config("negocio_nombre", NEGOCIO))
        nit_n    = st.text_input("NIT", value=get_config("negocio_nit", NIT))
        dir_n    = st.text_input("Dirección en terminal",
                                  value=get_config("negocio_direccion", DIRECCION))
        tel_n    = st.text_input("Teléfono", value=get_config("negocio_telefono", TELEFONO))
        if st.button("💾 Guardar datos negocio", type="primary"):
            for k, v in [("negocio_nombre",nombre_n),("negocio_nit",nit_n),
                          ("negocio_direccion",dir_n),("negocio_telefono",tel_n)]:
                set_config(k, v)
            st.success("✅ Datos del negocio actualizados")

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

    with tabs[2]:
        st.markdown("**Tarifas vigentes**")
        con = get_db()
        tfs = con.execute("SELECT id,nombre,descripcion,precio_hora,descuento_3h_pct,descuento_6h_pct,activo FROM tarifas").fetchall()
        con.close()
        df_t = pd.DataFrame(tfs, columns=["ID","Nombre","Descripción","Precio/hora","Desc 3h%","Desc 6h%","Activo"])
        df_t["Precio/hora"] = df_t["Precio/hora"].apply(fmt_cop)
        st.dataframe(df_t, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown("**Cambiar PIN de operador**")
        pin_viejo = st.text_input("PIN actual", type="password", key="pin_v")
        pin_nuevo = st.text_input("Nuevo PIN (4-8 dígitos)", type="password", key="pin_n")
        pin_conf2 = st.text_input("Confirmar nuevo PIN", type="password", key="pin_c2")
        if st.button("🔑 Cambiar PIN", type="primary"):
            if not verificar_pin(pin_viejo):
                st.error("PIN actual incorrecto")
            elif len(pin_nuevo) < 4:
                st.error("El PIN debe tener al menos 4 dígitos")
            elif pin_nuevo != pin_conf2:
                st.error("Los PINs no coinciden")
            else:
                con = get_db()
                con.execute("UPDATE operadores SET pin_hash=? WHERE pin_hash=?",
                            (_hash_pin(pin_nuevo), _hash_pin(pin_viejo)))
                con.commit()
                con.close()
                st.success("✅ PIN actualizado correctamente")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    init_db()
    _auto_backup_diario()
    _ensure_sync_thread()   # Arrancar worker de sync a Google Sheets si no está corriendo

    pantalla = st.session_state.pantalla
    router   = {
        "bienvenida":     show_bienvenida,
        "seleccion":      show_seleccion,
        "datos":          show_datos,
        "pago":           show_pago,
        "confirmacion":   show_confirmacion,
        "voucher":        show_voucher,
        "operador_login": show_operador_login,
        "operador":       show_operador,
    }
    router.get(pantalla, show_bienvenida)()


if __name__ == "__main__":
    main()
