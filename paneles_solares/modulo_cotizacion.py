# modulo_cotizacion.py — SolarCalc Pro · Módulo de Cotización Comercial
# ─────────────────────────────────────────────────────────────────────────────
"""
Genera cotizaciones comerciales completas para sistemas fotovoltaicos:
  • OFF-GRID / ON-GRID / HÍBRIDO
  • Lee el proyecto activo desde la base de datos
  • Formulario de precios con catálogo de equipos editables
  • Datos del cliente y empresa instaladora
  • Descuentos, IVA y total final
  • Validez y condiciones comerciales
  • Exporta PDF profesional con ReportLab + logo/firma opcionales
  • Historial de cotizaciones guardadas por proyecto
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import io
import os
import pathlib
import tempfile
from datetime import datetime, date, timedelta

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─── DB ───────────────────────────────────────────────────────────────────────
def _db_path() -> str:
    env = os.environ.get("SOLARCALC_DB_PATH")
    if env:
        return env
    script_dir = pathlib.Path(__file__).parent.resolve()
    candidate  = script_dir / "solar_calc.db"
    try:
        t = script_dir / ".wt"; t.touch(); t.unlink()
        return str(candidate)
    except Exception:
        return str(pathlib.Path(tempfile.gettempdir()) / "solar_calc.db")

DB_PATH = _db_path()

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ─── INIT DB — tabla cotizaciones ─────────────────────────────────────────────
def init_cotizacion_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cotizaciones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            tipo_sistema TEXT DEFAULT 'OFF-GRID',
            numero      TEXT,
            cliente_nombre TEXT,
            cliente_nit    TEXT,
            cliente_tel    TEXT,
            cliente_email  TEXT,
            cliente_ciudad TEXT,
            cliente_dir    TEXT,
            empresa_nombre TEXT,
            empresa_nit    TEXT,
            empresa_tel    TEXT,
            empresa_email  TEXT,
            empresa_web    TEXT,
            empresa_dir    TEXT,
            items_json  TEXT,
            subtotal    REAL,
            descuento   REAL DEFAULT 0,
            iva_pct     REAL DEFAULT 0,
            total       REAL,
            moneda      TEXT DEFAULT 'COP',
            validez_dias INTEGER DEFAULT 30,
            condiciones TEXT,
            notas       TEXT,
            estado      TEXT DEFAULT 'BORRADOR',
            creado      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    conn.commit()
    conn.close()

# ─── CATÁLOGOS DE EQUIPOS ─────────────────────────────────────────────────────
CATALOGO_PANELES = [
    {"Fabricante": "JinkoSolar",    "Modelo": "Tiger Neo 550W",   "Wp": 550, "Voc": 49.8},
    {"Fabricante": "Trina Solar",   "Modelo": "Vertex 550W",      "Wp": 550, "Voc": 49.5},
    {"Fabricante": "Canadian Solar","Modelo": "HiKu6 550W",       "Wp": 550, "Voc": 49.7},
    {"Fabricante": "LONGi",         "Modelo": "Hi-MO 6 550W",     "Wp": 550, "Voc": 50.2},
    {"Fabricante": "JA Solar",      "Modelo": "JAM72D30 550W",    "Wp": 550, "Voc": 49.6},
    {"Fabricante": "Risen",         "Modelo": "RSM132-8-650M",    "Wp": 650, "Voc": 56.4},
]

CATALOGO_INVERSORES = [
    {"Marca": "Growatt",       "Modelo": "MOD 5000TL3-X",   "Tipo": "ON-GRID",  "kW": 5},
    {"Marca": "Sungrow",       "Modelo": "SG5.0RS",          "Tipo": "ON-GRID",  "kW": 5},
    {"Marca": "Huawei",        "Modelo": "SUN2000-6KTL",     "Tipo": "ON-GRID",  "kW": 6},
    {"Marca": "Deye",          "Modelo": "SUN-5K-SG04LP1",   "Tipo": "HÍBRIDO",  "kW": 5},
    {"Marca": "Growatt",       "Modelo": "SPF 5000ES",        "Tipo": "HÍBRIDO",  "kW": 5},
    {"Marca": "Solis",         "Modelo": "RHI-5K-48ES",       "Tipo": "HÍBRIDO",  "kW": 5},
    {"Marca": "Victron Energy","Modelo": "MultiPlus II 5kVA", "Tipo": "OFF-GRID", "kW": 5},
    {"Marca": "Growatt",       "Modelo": "SPF 3000TL LVM",   "Tipo": "OFF-GRID", "kW": 3},
]

CATALOGO_BATERIAS = [
    {"Marca": "Pylontech",  "Modelo": "US5000",        "kWh": 4.8,  "V": 48,   "Quim": "LiFePO4"},
    {"Marca": "Dyness",     "Modelo": "BX51100",       "kWh": 5.12, "V": 51.2, "Quim": "LiFePO4"},
    {"Marca": "BYD",        "Modelo": "Battery Box",   "kWh": 5.1,  "V": 51.2, "Quim": "LiFePO4"},
    {"Marca": "CATL",       "Modelo": "EnerOne Plus",  "kWh": 5.0,  "V": 48,   "Quim": "LiFePO4"},
    {"Marca": "Sunsynk",    "Modelo": "LBSA016",       "kWh": 5.12, "V": 51.2, "Quim": "LiFePO4"},
    {"Marca": "Hubble",     "Modelo": "AM-5",          "kWh": 5.5,  "V": 51.2, "Quim": "LiFePO4"},
    {"Marca": "Genérica",   "Modelo": "AGM 200Ah",     "kWh": 2.4,  "V": 12,   "Quim": "AGM"},
    {"Marca": "Genérica",   "Modelo": "GEL 200Ah",     "kWh": 2.4,  "V": 12,   "Quim": "GEL"},
]

ITEMS_OTROS = [
    "Estructura soporte paneles (aluminio)",
    "Cable DC 10mm² (m)",
    "Cable DC 6mm² (m)",
    "Cable AC 4mm² (m)",
    "Fusible DC 20A",
    "Fusible DC 40A",
    "Breaker DC 2P 63A",
    "Breaker AC 2P 32A",
    "Breaker AC 2P 63A",
    "DPS DC Tipo II 1000V 40kA",
    "DPS AC Tipo II 275V 40kA",
    "Caja de conexiones (combiner box)",
    "Medidor bidireccional",
    "Mano de obra instalación",
    "Transporte y logística",
    "Puesta en servicio y capacitación",
    "Garantía extendida 5 años",
    "Mantenimiento anual (contrato)",
]

# ─── HELPER: calcular totales de un proyecto ──────────────────────────────────
def leer_dimensionamiento(proyecto_id: int, tipo_sistema: str, ss: dict) -> dict:
    """Lee la BD y session_state para obtener el dimensionamiento actual."""
    conn = get_conn()
    p    = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    pan  = conn.execute("SELECT * FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
                        (proyecto_id,)).fetchone()
    cargas = pd.read_sql("SELECT cantidad,potencia_w,horas_dia,es_motor FROM cargas WHERE proyecto_id=?",
                         conn, params=(proyecto_id,))
    recibo = conn.execute(
        "SELECT kwh_periodo,dias_periodo FROM recibos WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    conn.close()

    hsp      = (p[4] if p and p[4] else None) or ss.get("calc_hsp", 4.2)
    vdc      = (p[3] if p and p[3] else None) or ss.get("calc_vdc", 48)
    pot_pan  = (pan[3] if pan else None) or ss.get("calc_pot_panel_wp", 550)
    voc_pan  = (pan[4] if pan else 49.9)
    isc_pan  = (pan[5] if pan else 14.0)
    mod_pan  = (pan[2] if pan else "Panel solar 550Wp")

    consumo_inv = (cargas["cantidad"] * cargas["potencia_w"] * cargas["horas_dia"]).sum() \
                  if not cargas.empty else 0.0
    consumo_rec = (recibo[0] / recibo[1] * 1000) if recibo else 0.0
    consumo_base = max(consumo_inv, consumo_rec) if consumo_rec > 0 else consumo_inv
    consumo_fs   = consumo_base * 1.20

    n_pan   = ss.get("calc_num_paneles")  or math.ceil(consumo_fs / max(hsp * 0.75, 0.1) / max(pot_pan, 1))
    n_bat   = ss.get("calc_num_baterias") or math.ceil(consumo_fs / (vdc * 0.8))
    bat_cap = ss.get("calc_bat_cap_ah", 100)

    if not cargas.empty:
        def _inv_pot(r):
            return r["cantidad"] * r["potencia_w"] * (4 if int(r["es_motor"]) else 1)
        pot_cargas = cargas.apply(_inv_pot, axis=1).sum()
    else:
        pot_cargas = consumo_fs

    inv_w = pot_cargas * 1.2
    kw_std = [1,2,3,5,8,10,15,20,25,30,40,50]
    inv_kw = float(next((k for k in kw_std if k * 1000 >= inv_w), math.ceil(inv_w / 1000)))

    return {
        "tipo_sistema": tipo_sistema,
        "proyecto":     p[1] if p else "Proyecto",
        "municipio":    p[2] if p else "",
        "hsp":          hsp,
        "vdc":          vdc,
        "n_paneles":    int(n_pan),
        "pot_panel_wp": int(pot_pan),
        "voc_pan":      voc_pan,
        "isc_pan":      isc_pan,
        "modelo_panel": mod_pan,
        "n_baterias":   int(n_bat),
        "bat_cap_ah":   int(bat_cap),
        "inv_kw":       inv_kw,
        "consumo_fs":   consumo_fs,
        "consumo_base": consumo_base,
    }

# ─── GENERADOR PDF COTIZACIÓN ─────────────────────────────────────────────────
def generar_pdf_cotizacion(datos: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=2*cm,    bottomMargin=1.8*cm)

    TIPO  = datos.get("tipo_sistema", "OFF-GRID")
    COLOR_MAP = {"OFF-GRID": "#FFB300", "ON-GRID": "#FF6B35", "HIBRIDO": "#F59E0B", "HÍBRIDO": "#F59E0B"}
    col_hex = COLOR_MAP.get(TIPO, "#FFB300")

    SOL    = colors.HexColor(col_hex)
    DARK   = colors.HexColor("#0A0E1A")
    CARD   = colors.HexColor("#1A2235")
    CARD2  = colors.HexColor("#1E2A3F")
    TEXT   = colors.HexColor("#E8EDF5")
    TEXT2  = colors.HexColor("#8A9BBD")
    GREEN  = colors.HexColor("#00E676")
    CYAN   = colors.HexColor("#00BCD4")
    MONO   = colors.HexColor("#FFD54F")
    BORDER = colors.HexColor("#2A3A55")
    WHITE  = colors.white
    BLACK  = colors.black
    LGRAY  = colors.HexColor("#F5F5F5")
    MGRAY  = colors.HexColor("#E0E0E0")
    DGRAY  = colors.HexColor("#424242")
    BLUE   = colors.HexColor("#1565C0")

    # ─ Estilos ────────────────────────────────────────────────────────────────
    sts = getSampleStyleSheet()
    def estilo(name, font="Helvetica", size=9, color=DGRAY, align=TA_LEFT,
               bold=False, space_before=0, space_after=4):
        return ParagraphStyle(name, fontName=font+("-Bold" if bold else ""),
                               fontSize=size, textColor=color, alignment=align,
                               spaceBefore=space_before, spaceAfter=space_after,
                               leading=size*1.3)

    st_titulo   = estilo("titulo",  size=20, color=SOL, align=TA_LEFT, bold=True)
    st_sub      = estilo("sub",     size=9,  color=TEXT2, align=TA_LEFT)
    st_sec      = estilo("sec",     size=11, color=SOL,  bold=True, space_before=10, space_after=4)
    st_body     = estilo("body",    size=9,  color=DGRAY)
    st_label    = estilo("label",   size=8,  color=TEXT2)
    st_val      = estilo("val",     size=9,  color=DGRAY, bold=True)
    st_center   = estilo("center",  size=9,  color=DGRAY, align=TA_CENTER)
    st_total    = estilo("total",   size=11, color=DARK,  bold=True, align=TA_RIGHT)
    st_footer   = estilo("footer",  size=7,  color=TEXT2, align=TA_CENTER)
    st_cond     = estilo("cond",    size=8,  color=DGRAY)
    st_estado   = estilo("estado",  size=14, color=SOL,  bold=True, align=TA_CENTER)

    def hr(color=BORDER, thick=0.8, space=6):
        return HRFlowable(width="100%", thickness=thick, color=color,
                          spaceAfter=space, spaceBefore=2)

    def p(text, style=None, **kw):
        return Paragraph(text, style or st_body)

    story = []
    items = datos.get("items", [])
    emp   = datos.get("empresa", {})
    cli   = datos.get("cliente", {})
    fin   = datos.get("financiero", {})
    dim   = datos.get("dimensionamiento", {})
    meta  = datos.get("meta", {})

    subtotal  = fin.get("subtotal", 0)
    desc_pct  = fin.get("descuento_pct", 0)
    desc_val  = subtotal * desc_pct / 100
    base_iva  = subtotal - desc_val
    iva_pct   = fin.get("iva_pct", 0)
    iva_val   = base_iva * iva_pct / 100
    total     = base_iva + iva_val
    moneda    = fin.get("moneda", "COP")

    def fmt_money(v):
        return f"$ {v:,.0f} {moneda}"

    # ══════════════════════════════════════════════════════════════════════════
    # CABECERA
    # ══════════════════════════════════════════════════════════════════════════
    header_data = [[
        # Columna izquierda: empresa
        Table([[
            [p(f"<b>{emp.get('nombre','SolarCalc Pro')}</b>",
               estilo("en", size=14, color=SOL, bold=True))],
            [p(emp.get("nit",""), st_label)],
            [p(emp.get("dir",""), st_label)],
            [p(f"Tel: {emp.get('tel','')}  |  {emp.get('email','')}", st_label)],
            [p(emp.get("web",""), st_label)],
        ]], colWidths=[9.5*cm]),
        # Columna derecha: número de cotización
        Table([[
            [p("COTIZACIÓN", estilo("ct", size=22, color=SOL, bold=True, align=TA_RIGHT))],
            [p(f"N° {meta.get('numero','001-2025')}",
               estilo("cn", size=11, color=DGRAY, bold=True, align=TA_RIGHT))],
            [p(f"Fecha: {meta.get('fecha', date.today().strftime('%d/%m/%Y'))}",
               estilo("cf", size=9, color=TEXT2, align=TA_RIGHT))],
            [p(f"Válida hasta: {meta.get('valida_hasta','')}",
               estilo("cv", size=9, color=TEXT2, align=TA_RIGHT))],
            [p(f"Estado: {meta.get('estado','BORRADOR')}",
               estilo("ces", size=9, color=SOL, bold=True, align=TA_RIGHT))],
        ]], colWidths=[6.5*cm]),
    ]]
    t_header = Table(header_data, colWidths=[9.5*cm, 6.5*cm])
    t_header.setStyle(TableStyle([
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",(0,0), (-1,-1), 0),
        ("RIGHTPADDING",(0,0),(-1,-1), 0),
    ]))
    story.append(t_header)

    # Banda de tipo sistema
    tipo_label = {"OFF-GRID":"🔋 SISTEMA AISLADO OFF-GRID",
                  "ON-GRID":"🔌 SISTEMA INTERCONECTADO ON-GRID",
                  "HIBRIDO":"⚡ SISTEMA HÍBRIDO",
                  "HÍBRIDO":"⚡ SISTEMA HÍBRIDO"}.get(TIPO, TIPO)
    story.append(Spacer(1, 0.3*cm))
    t_banda = Table([[p(tipo_label,
                        estilo("banda", size=10, color=DARK, bold=True, align=TA_CENTER))]],
                    colWidths=[16*cm])
    t_banda.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), SOL),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("ROUNDEDCORNERS",[4]),
    ]))
    story.append(t_banda)
    story.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # DATOS CLIENTE / PROYECTO
    # ══════════════════════════════════════════════════════════════════════════
    story.append(p("DATOS DEL CLIENTE Y PROYECTO", st_sec))
    story.append(hr())

    cli_data = [
        ["CLIENTE",  cli.get("nombre",""),   "PROYECTO", dim.get("proyecto","")],
        ["NIT/CC",   cli.get("nit",""),       "MUNICIPIO", dim.get("municipio","")],
        ["Teléfono", cli.get("tel",""),       "SISTEMA",   TIPO],
        ["Email",    cli.get("email",""),     "VDC",       f"{dim.get('vdc',48)} V"],
        ["Ciudad",   cli.get("ciudad",""),    "HSP",       f"{dim.get('hsp',4.2):.2f} h/día"],
        ["Dirección",cli.get("dir",""),       "Consumo +FS", f"{dim.get('consumo_fs',0):,.0f} Wh/día"],
    ]
    t_cli = Table(cli_data, colWidths=[2.5*cm, 5.5*cm, 2.5*cm, 5.5*cm])
    t_cli.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",    (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTNAME",    (2,0), (2,-1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("TEXTCOLOR",   (0,0), (0,-1),  TEXT2),
        ("TEXTCOLOR",   (2,0), (2,-1),  TEXT2),
        ("TEXTCOLOR",   (1,0), (1,-1),  DGRAY),
        ("TEXTCOLOR",   (3,0), (3,-1),  DGRAY),
        ("BACKGROUND",  (0,0), (-1,-1), LGRAY),
        *[("BACKGROUND",(0,i),(-1,i), WHITE) for i in range(0,6,2)],
        ("GRID",        (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_cli)
    story.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # RESUMEN TÉCNICO DEL SISTEMA
    # ══════════════════════════════════════════════════════════════════════════
    story.append(p("RESUMEN TÉCNICO DEL SISTEMA", st_sec))
    story.append(hr())

    n_pan   = dim.get("n_paneles", 0)
    pot_pan = dim.get("pot_panel_wp", 550)
    n_bat   = dim.get("n_baterias", 0)
    bat_cap = dim.get("bat_cap_ah", 100)
    inv_kw  = dim.get("inv_kw", 5.0)
    voc_p   = dim.get("voc_pan", 49.8)
    isc_p   = dim.get("isc_pan", 14.0)
    mod_p   = dim.get("modelo_panel", "Panel solar")
    pot_total_kwp = round(n_pan * pot_pan / 1000, 2)

    # Protecciones calculadas
    fus_dc     = isc_p * 1.25
    fus_std    = next((f for f in [10,15,20,25,30,40,50] if f >= fus_dc), 50)
    inv_w      = inv_kw * 1000
    brk_ac_a   = (inv_w / 220) * 1.25
    brk_ac_std = next((f for f in [16,20,25,32,40,50,63] if f >= brk_ac_a), 63)
    mppt_max_v = 600
    pan_por_str = int(mppt_max_v / voc_p) if voc_p > 0 else 12
    n_strings  = math.ceil(n_pan / pan_por_str) if pan_por_str > 0 else 1

    tec_izq = [
        ["CAMPO FOTOVOLTAICO", ""],
        ["Panel solar", f"{mod_p}  –  {pot_pan} Wp"],
        ["Cantidad paneles", f"{n_pan} unidades"],
        ["Potencia instalada", f"{pot_total_kwp} kWp"],
        ["Configuración strings", f"{n_strings} strings × {pan_por_str} paneles/string"],
        ["Voc panel", f"{voc_p} V  |  Isc: {isc_p} A"],
    ]
    tec_der = [
        ["ALMACENAMIENTO Y CONVERSIÓN", ""],
        ["Batería",       f"{n_bat} und × {bat_cap} Ah  LiFePO4"],
        ["Energía banco", f"{round(n_bat * bat_cap * dim.get('vdc',48) / 1000, 2)} kWh"],
        ["Inversor",      f"{inv_kw:.0f} kW  –  {TIPO}"],
        ["Protec. DC",    f"Fusible {fus_std}A  |  DPS Tipo II 1000V/40kA"],
        ["Protec. AC",    f"Breaker 2P {brk_ac_std}A  |  DPS Tipo II 275V/40kA"],
    ]

    def fmt_tec(rows):
        t = Table(rows, colWidths=[4*cm, 4*cm])
        t.setStyle(TableStyle([
            ("FONTNAME",     (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME",     (0,0), (1,0),   "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8),
            ("TEXTCOLOR",    (0,0), (1,0),   SOL),
            ("TEXTCOLOR",    (0,1), (0,-1),  TEXT2),
            ("TEXTCOLOR",    (1,1), (1,-1),  DGRAY),
            ("BACKGROUND",   (0,0), (-1,0),  CARD),
            *[("BACKGROUND", (0,i),(-1,i), WHITE if i%2==0 else LGRAY) for i in range(1,len(rows))],
            ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
            ("SPAN",         (0,0), (1,0)),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ]))
        return t

    t_tec = Table([[fmt_tec(tec_izq), fmt_tec(tec_der)]], colWidths=[8*cm, 8*cm],
                  hAlign="LEFT")
    t_tec.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(t_tec)
    story.append(Spacer(1, 0.5*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # TABLA DE ÍTEMS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(p("DESCRIPCIÓN DE EQUIPOS Y SERVICIOS", st_sec))
    story.append(hr())

    hdr_items = [["#", "DESCRIPCIÓN", "CANT.", "UNIDAD", "V. UNITARIO", "V. TOTAL"]]
    rows_items = hdr_items[:]
    for i, item in enumerate(items, 1):
        vt = item.get("cant", 0) * item.get("precio", 0)
        rows_items.append([
            str(i),
            item.get("desc", ""),
            f"{item.get('cant', 1):,.0f}",
            item.get("unidad", "und"),
            fmt_money(item.get("precio", 0)),
            fmt_money(vt),
        ])

    COL_W = [0.8*cm, 7.2*cm, 1.5*cm, 1.5*cm, 2.5*cm, 2.5*cm]
    t_items = Table(rows_items, colWidths=COL_W, repeatRows=1)
    n_rows = len(rows_items)
    t_items.setStyle(TableStyle([
        # Encabezado
        ("BACKGROUND",  (0,0), (-1,0), SOL),
        ("TEXTCOLOR",   (0,0), (-1,0), DARK),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,0), 8),
        ("ALIGN",       (0,0), (-1,0), "CENTER"),
        # Filas alternas
        *[("BACKGROUND",(0,i),(-1,i), WHITE if i%2==1 else LGRAY) for i in range(1, n_rows)],
        ("TEXTCOLOR",   (0,1), (-1,-1), DGRAY),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,1), (-1,-1), 8),
        # Alineaciones
        ("ALIGN",       (0,0), (0,-1),  "CENTER"),
        ("ALIGN",       (2,0), (3,-1),  "CENTER"),
        ("ALIGN",       (4,0), (5,-1),  "RIGHT"),
        ("ALIGN",       (1,1), (1,-1),  "LEFT"),
        # Borde
        ("GRID",        (0,0), (-1,-1), 0.4, MGRAY),
        ("LINEBELOW",   (0,0), (-1,0),  1.0, SOL),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # TOTALES
    # ══════════════════════════════════════════════════════════════════════════
    tot_rows = [
        ["", "", "SUBTOTAL",       fmt_money(subtotal)],
        ["", "", f"DESCUENTO ({desc_pct:.0f}%)", f"- {fmt_money(desc_val)}"],
        ["", "", f"IVA ({iva_pct:.0f}%)",        fmt_money(iva_val)],
    ]
    t_tot = Table(tot_rows, colWidths=[6*cm, 3*cm, 3.5*cm, 3.5*cm])
    t_tot.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (2,0), (2,-1),  TEXT2),
        ("TEXTCOLOR", (3,0), (3,-1),  DGRAY),
        ("ALIGN",     (2,0), (3,-1),  "RIGHT"),
        ("TOPPADDING",(0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LINEABOVE", (2,0), (3,0),  0.5, MGRAY),
    ]))
    story.append(t_tot)

    # Línea total
    t_gran_total = Table([[
        p(f"TOTAL A PAGAR",
          estilo("gt_lbl", size=13, color=DARK, bold=True, align=TA_RIGHT)),
        p(fmt_money(total),
          estilo("gt_val", size=13, color=DARK, bold=True, align=TA_RIGHT)),
    ]], colWidths=[9.5*cm, 6.5*cm])
    t_gran_total.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), SOL),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_gran_total)
    story.append(Spacer(1, 0.5*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # CONDICIONES COMERCIALES
    # ══════════════════════════════════════════════════════════════════════════
    conds = datos.get("condiciones",
        "1. Precios en pesos colombianos (COP) IVA incluido según se indica.\n"
        "2. Validez de la cotización: 30 días a partir de la fecha de emisión.\n"
        "3. Forma de pago: 50% anticipo, 50% contra entrega e instalación.\n"
        "4. Tiempo de entrega estimado: 15 a 20 días hábiles después del anticipo.\n"
        "5. Garantía: paneles 12 años producto / 25 años rendimiento. Inversor 5 años. "
        "Baterías LiFePO4 5 años o 4000 ciclos.\n"
        "6. La instalación incluye puesta en servicio y capacitación al usuario.\n"
        "7. No incluye obra civil ni adecuaciones eléctricas previas no descritas.\n"
        "8. Precios sujetos a variación de TRM para equipos importados."
    )
    notas = datos.get("notas", "")

    story.append(p("CONDICIONES COMERCIALES", st_sec))
    story.append(hr())
    for i, linea in enumerate(conds.split("\n"), 1):
        if linea.strip():
            story.append(p(linea.strip(), st_cond))
    story.append(Spacer(1, 0.3*cm))

    if notas.strip():
        story.append(p("NOTAS ADICIONALES", estilo("ns", size=10, color=SOL, bold=True)))
        story.append(p(notas, st_cond))
        story.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # FIRMAS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1*cm))
    story.append(hr(thick=0.5))

    firma_data = [[
        Table([
            [p("_"*35, st_center)],
            [p(emp.get("representante", "Representante Legal"), st_center)],
            [p(emp.get("nombre","Empresa Instaladora"),         estilo("fn", size=8, color=TEXT2, align=TA_CENTER))],
            [p(f"NIT: {emp.get('nit','')}",                    estilo("fn2",size=8, color=TEXT2, align=TA_CENTER))],
        ], colWidths=[7*cm]),
        Table([
            [p("_"*35, st_center)],
            [p(cli.get("nombre","Cliente / Contratante"), st_center)],
            [p(f"CC/NIT: {cli.get('nit','')}", estilo("cf", size=8, color=TEXT2, align=TA_CENTER))],
            [p("Fecha: ___________________",   estilo("cf2",size=8, color=TEXT2, align=TA_CENTER))],
        ], colWidths=[7*cm]),
    ]]
    t_firma = Table(firma_data, colWidths=[8*cm, 8*cm])
    t_firma.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING",(0,0), (-1,-1), 0),
    ]))
    story.append(t_firma)

    # ─── Footer ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(hr(color=SOL, thick=1))
    story.append(p(
        f"SOLARCALC PRO  ·  Cotización N° {meta.get('numero','001')}  ·  "
        f"Sistema {TIPO}  ·  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  "
        f"Válido hasta: {meta.get('valida_hasta','')}",
        st_footer))

    doc.build(story)
    buf.seek(0)
    return buf.read()

# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────
def mostrar_cotizacion(proyecto_id: int, session_state: dict):
    init_cotizacion_db()

    conn = get_conn()
    p_info = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    hist   = pd.read_sql(
        "SELECT id,numero,tipo_sistema,cliente_nombre,total,moneda,estado,creado "
        "FROM cotizaciones WHERE proyecto_id=? ORDER BY id DESC",
        conn, params=(proyecto_id,))
    conn.close()

    if not p_info:
        st.error("Proyecto no encontrado.")
        return

    tipo_activo = session_state.get("tipo_sistema", "OFF-GRID")

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>💰 COTIZACIÓN COMERCIAL
            <span style='font-size:0.55em;background:#FFB300;color:#0A0E1A;padding:2px 12px;
                border-radius:20px;margin-left:10px;vertical-align:middle;letter-spacing:1px;'>
                NUEVA</span>
        </div>
        <div class='hero-sub'>PRESUPUESTO PROFESIONAL · SISTEMA FOTOVOLTAICO</div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs del módulo
    tab_nueva, tab_hist = st.tabs(["✦ Nueva Cotización", "📋 Historial"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: NUEVA COTIZACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    with tab_nueva:

        # ── Selector tipo sistema ───────────────────────────────────────────
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>1</span>
        TIPO DE SISTEMA Y DIMENSIONAMIENTO</div>
        """, unsafe_allow_html=True)

        col_ts1, col_ts2 = st.columns([1,2])
        with col_ts1:
            tipo_sel = st.selectbox("Sistema a cotizar",
                ["OFF-GRID", "ON-GRID", "HIBRIDO"],
                index=["OFF-GRID","ON-GRID","HIBRIDO"].index(
                    tipo_activo if tipo_activo in ["OFF-GRID","ON-GRID","HIBRIDO"] else "OFF-GRID"),
                key="cot_tipo")

        dim = leer_dimensionamiento(proyecto_id, tipo_sel, session_state)

        with col_ts2:
            st.markdown(f"""
            <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
                        padding:0.8rem 1.2rem;display:flex;gap:2rem;flex-wrap:wrap;
                        align-items:center;'>
                <span style='color:#8A9BBD;font-size:0.82rem;'>Proyecto:
                    <b style='color:#FFB300;'>{dim['proyecto']}</b></span>
                <span style='color:#8A9BBD;font-size:0.82rem;'>Paneles:
                    <b style='color:#FFD54F;'>{dim['n_paneles']} × {dim['pot_panel_wp']}Wp</b></span>
                <span style='color:#8A9BBD;font-size:0.82rem;'>Inv:
                    <b style='color:#FFD54F;'>{dim['inv_kw']:.0f} kW</b></span>
                <span style='color:#8A9BBD;font-size:0.82rem;'>Bat:
                    <b style='color:#FFD54F;'>{dim['n_baterias']} × {dim['bat_cap_ah']}Ah</b></span>
                <span style='color:#8A9BBD;font-size:0.82rem;'>VDC:
                    <b style='color:#00BCD4;'>{dim['vdc']}V</b></span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # ── Datos empresa ────────────────────────────────────────────────────
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>2</span>
        DATOS DE LA EMPRESA INSTALADORA</div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            emp_nombre = st.text_input("Empresa / Razón social",
                value=session_state.get("_cot_emp_nombre",""), key="cot_emp_nombre",
                placeholder="Instalaciones Solares SAS")
            emp_nit    = st.text_input("NIT",
                value=session_state.get("_cot_emp_nit",""), key="cot_emp_nit",
                placeholder="900.123.456-7")
        with c2:
            emp_tel    = st.text_input("Teléfono",
                value=session_state.get("_cot_emp_tel",""), key="cot_emp_tel",
                placeholder="+57 300 000 0000")
            emp_email  = st.text_input("Email",
                value=session_state.get("_cot_emp_email",""), key="cot_emp_email",
                placeholder="ventas@empresa.com")
        with c3:
            emp_web    = st.text_input("Sitio web",
                value=session_state.get("_cot_emp_web",""), key="cot_emp_web",
                placeholder="www.empresa.com")
            emp_rep    = st.text_input("Representante legal",
                value=session_state.get("_cot_emp_rep",""), key="cot_emp_rep",
                placeholder="Nombre del representante")
        emp_dir = st.text_input("Dirección empresa",
            value=session_state.get("_cot_emp_dir",""), key="cot_emp_dir",
            placeholder="Calle 123 # 45-67, Medellín, Antioquia")

        # Guardar empresa en session_state para persistencia
        for _k in ["nombre","nit","tel","email","web","rep","dir"]:
            session_state[f"_cot_emp_{_k}"] = session_state.get(f"cot_emp_{_k}", "")

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # ── Datos cliente ────────────────────────────────────────────────────
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>3</span>
        DATOS DEL CLIENTE</div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            cli_nombre = st.text_input("Nombre / Razón social del cliente",
                key="cot_cli_nombre", placeholder="Juan Pérez / Empresa ABC")
            cli_nit    = st.text_input("CC / NIT cliente",
                key="cot_cli_nit", placeholder="1.234.567.890")
        with c2:
            cli_tel    = st.text_input("Teléfono cliente",
                key="cot_cli_tel", placeholder="+57 311 000 0000")
            cli_email  = st.text_input("Email cliente",
                key="cot_cli_email", placeholder="cliente@email.com")
        with c3:
            cli_ciudad = st.text_input("Ciudad / Municipio",
                key="cot_cli_ciudad",
                value=dim.get("municipio",""),
                placeholder="Medellín, Antioquia")
            cli_dir    = st.text_input("Dirección del proyecto",
                key="cot_cli_dir", placeholder="Vereda El Sol, Km 3 vía...")

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # ── Meta cotización ──────────────────────────────────────────────────
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>4</span>
        DATOS DE LA COTIZACIÓN</div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            cot_numero = st.text_input("N° Cotización",
                key="cot_numero", value="COT-001-2025",
                placeholder="COT-001-2025")
        with c2:
            cot_fecha  = st.date_input("Fecha de emisión",
                key="cot_fecha", value=date.today())
        with c3:
            cot_validez = st.number_input("Validez (días)",
                key="cot_validez", min_value=1, max_value=180, value=30)
        with c4:
            cot_estado = st.selectbox("Estado",
                ["BORRADOR","ENVIADA","APROBADA","RECHAZADA","VENCIDA"],
                key="cot_estado")

        col_mon1, col_mon2 = st.columns([1, 3])
        with col_mon1:
            cot_moneda = st.selectbox("Moneda", ["COP", "USD", "EUR"], key="cot_moneda")
        fecha_validez = cot_fecha + timedelta(days=cot_validez)

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # ÍTEMS DE COTIZACIÓN
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>5</span>
        EQUIPOS Y SERVICIOS</div>
        """, unsafe_allow_html=True)

        # Precios por defecto según dimensionamiento
        _pan_precio_def = 320_000
        _bat_precio_def = 1_800_000
        _inv_precio_def = 2_500_000
        _estr_precio_def = 85_000
        _mo_precio_def  = 250_000

        # ── Items pre-cargados del dimensionamiento ──────────────────────────
        items_auto = []
        if dim["n_paneles"] > 0:
            items_auto.append({
                "desc": f"Panel solar {dim['modelo_panel']} {dim['pot_panel_wp']}Wp — Voc {dim['voc_pan']}V",
                "cant": dim["n_paneles"], "unidad": "und",
                "precio": _pan_precio_def, "key": "pan"
            })
        items_auto.append({
            "desc": f"Inversor {tipo_sel} {dim['inv_kw']:.0f} kW (según sistema seleccionado)",
            "cant": 1, "unidad": "und",
            "precio": _inv_precio_def, "key": "inv"
        })
        if dim["n_baterias"] > 0 and tipo_sel in ["OFF-GRID","HIBRIDO"]:
            items_auto.append({
                "desc": f"Batería LiFePO4 {dim['bat_cap_ah']}Ah @ {dim['vdc']}V",
                "cant": dim["n_baterias"], "unidad": "und",
                "precio": _bat_precio_def, "key": "bat"
            })
        items_auto.append({
            "desc": "Estructura soporte aluminio anodizado para paneles",
            "cant": dim["n_paneles"], "unidad": "und",
            "precio": _estr_precio_def, "key": "estr"
        })
        items_auto.append({
            "desc": "Cable DC 10mm² (rojo/negro) + conectores MC4",
            "cant": dim["n_paneles"] * 2, "unidad": "m",
            "precio": 4_500, "key": "cable"
        })

        # Protecciones calculadas
        isc_p = dim.get("isc_pan", 14.0)
        fus_dc_a = isc_p * 1.25
        fus_std_a = next((f for f in [10,15,20,25,30,40,50] if f >= fus_dc_a), 50)
        inv_w_a = dim["inv_kw"] * 1000
        brk_a = (inv_w_a / 220) * 1.25
        brk_std_a = next((f for f in [16,20,25,32,40,50,63] if f >= brk_a), 63)
        n_str_a = math.ceil(dim["n_paneles"] / max(1, int(600 / max(dim["voc_pan"],1))))

        items_auto.append({
            "desc": f"Fusible DC {fus_std_a}A para strings (protección DC)",
            "cant": n_str_a, "unidad": "und", "precio": 35_000, "key": "fus"
        })
        items_auto.append({
            "desc": f"Breaker AC 2P {brk_std_a}A + DPS Tipo II 275V/40kA",
            "cant": 1, "unidad": "und", "precio": 120_000, "key": "brk"
        })
        items_auto.append({
            "desc": "DPS DC Tipo II 1000VDC 40kA",
            "cant": 1, "unidad": "und", "precio": 180_000, "key": "dps"
        })
        items_auto.append({
            "desc": "Mano de obra instalación, puesta en servicio y capacitación",
            "cant": 1, "unidad": "gl",
            "precio": _mo_precio_def * dim["n_paneles"], "key": "mo"
        })
        items_auto.append({
            "desc": "Transporte y logística",
            "cant": 1, "unidad": "gl", "precio": 150_000, "key": "transp"
        })

        # ── Tabla editable de ítems ──────────────────────────────────────────
        st.markdown("""
        <div class='info-note' style='margin-bottom:1rem;'>
            Los ítems se pre-cargan con el dimensionamiento del proyecto.
            Edita cantidades, precios y descripción según necesidad.
            Usa los campos adicionales para agregar más equipos.
        </div>
        """, unsafe_allow_html=True)

        items_editados = []
        subtotal_calc = 0.0

        with st.expander("✏ Editar ítems de la cotización", expanded=True):
            # Encabezado visual
            _hcols = st.columns([4, 1.2, 1.2, 2, 2])
            for _hc, _ht in zip(_hcols, ["Descripción","Cantidad","Unidad","Precio Unit.","Total"]):
                _hc.markdown(f"<div style='font-size:0.75rem;color:#FFB300;font-weight:700;"
                             f"text-transform:uppercase;letter-spacing:1px;'>{_ht}</div>",
                             unsafe_allow_html=True)

            for idx, item in enumerate(items_auto):
                cols = st.columns([4, 1.2, 1.2, 2, 2])
                with cols[0]:
                    desc_v = st.text_input("", value=item["desc"],
                        key=f"cot_desc_{item['key']}", label_visibility="collapsed")
                with cols[1]:
                    cant_v = st.number_input("", min_value=0.0, value=float(item["cant"]),
                        step=1.0, key=f"cot_cant_{item['key']}", label_visibility="collapsed")
                with cols[2]:
                    unid_v = st.selectbox("", ["und","m","gl","kit","hr","mes"],
                        index=["und","m","gl","kit","hr","mes"].index(item["unidad"])
                              if item["unidad"] in ["und","m","gl","kit","hr","mes"] else 0,
                        key=f"cot_unid_{item['key']}", label_visibility="collapsed")
                with cols[3]:
                    precio_v = st.number_input("", min_value=0.0, value=float(item["precio"]),
                        step=1000.0, key=f"cot_precio_{item['key']}", label_visibility="collapsed",
                        format="%0.0f")
                with cols[4]:
                    vt = cant_v * precio_v
                    st.markdown(f"""
                    <div style='background:#1E2A3F;border-radius:6px;padding:0.45rem 0.6rem;
                                font-family:Share Tech Mono,monospace;font-size:0.82rem;
                                color:#FFD54F;text-align:right;margin-top:0.1rem;'>
                        $ {vt:,.0f}
                    </div>""", unsafe_allow_html=True)

                items_editados.append({"desc": desc_v, "cant": cant_v,
                                       "unidad": unid_v, "precio": precio_v})
                subtotal_calc += vt

            # ── Ítems adicionales ────────────────────────────────────────────
            st.markdown("<hr class='sep' style='margin:0.8rem 0;'>", unsafe_allow_html=True)
            st.markdown("**➕ Agregar ítem adicional**")
            _add_cols = st.columns([4, 1.2, 1.2, 2])

            with _add_cols[0]:
                add_tipo = st.selectbox("Tipo rápido", ["— personalizado —"] + ITEMS_OTROS,
                    key="cot_add_tipo", label_visibility="collapsed")
            with _add_cols[1]:
                add_cant = st.number_input("Cant", min_value=0.0, value=1.0,
                    step=1.0, key="cot_add_cant", label_visibility="collapsed")
            with _add_cols[2]:
                add_unid = st.selectbox("Unid", ["und","m","gl","kit","hr","mes"],
                    key="cot_add_unid", label_visibility="collapsed")
            with _add_cols[3]:
                add_precio = st.number_input("Precio", min_value=0.0, value=0.0,
                    step=1000.0, key="cot_add_precio", label_visibility="collapsed",
                    format="%0.0f")

            add_desc_custom = ""
            if add_tipo == "— personalizado —":
                add_desc_custom = st.text_input("Descripción personalizada",
                    key="cot_add_desc", placeholder="Describe el ítem...")

            if st.button("➕ Agregar ítem", use_container_width=True, key="cot_btn_add"):
                desc_add = add_tipo if add_tipo != "— personalizado —" else add_desc_custom
                if desc_add and add_cant > 0 and add_precio > 0:
                    n_extra = len(session_state.get("_cot_extra_items", [])) + 1
                    if "_cot_extra_items" not in session_state:
                        session_state["_cot_extra_items"] = []
                    session_state["_cot_extra_items"].append({
                        "desc": desc_add, "cant": add_cant,
                        "unidad": add_unid, "precio": add_precio,
                        "key": f"extra_{n_extra}"
                    })
                    st.rerun()

            # Mostrar ítems extra agregados
            for ex_item in session_state.get("_cot_extra_items", []):
                ex_cols = st.columns([4, 1.2, 1.2, 2, 2, 0.5])
                with ex_cols[0]:
                    ex_desc = st.text_input("", value=ex_item["desc"],
                        key=f"cot_ex_desc_{ex_item['key']}", label_visibility="collapsed")
                with ex_cols[1]:
                    ex_cant = st.number_input("", value=float(ex_item["cant"]),
                        step=1.0, min_value=0.0,
                        key=f"cot_ex_cant_{ex_item['key']}", label_visibility="collapsed")
                with ex_cols[2]:
                    ex_unid = st.selectbox("", ["und","m","gl","kit","hr","mes"],
                        key=f"cot_ex_unid_{ex_item['key']}", label_visibility="collapsed")
                with ex_cols[3]:
                    ex_precio = st.number_input("", value=float(ex_item["precio"]),
                        step=1000.0, min_value=0.0,
                        key=f"cot_ex_precio_{ex_item['key']}", label_visibility="collapsed",
                        format="%0.0f")
                with ex_cols[4]:
                    ex_vt = ex_cant * ex_precio
                    st.markdown(f"""
                    <div style='background:#1E2A3F;border-radius:6px;padding:0.45rem 0.6rem;
                                font-family:Share Tech Mono;font-size:0.82rem;color:#FFD54F;
                                text-align:right;margin-top:0.1rem;'>$ {ex_vt:,.0f}</div>""",
                        unsafe_allow_html=True)
                with ex_cols[5]:
                    if st.button("🗑", key=f"cot_ex_del_{ex_item['key']}"):
                        session_state["_cot_extra_items"] = [
                            x for x in session_state["_cot_extra_items"]
                            if x["key"] != ex_item["key"]]
                        st.rerun()
                items_editados.append({"desc": ex_desc, "cant": ex_cant,
                                       "unidad": ex_unid, "precio": ex_precio})
                subtotal_calc += ex_vt

        # ── Financiero ───────────────────────────────────────────────────────
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>6</span>
        RESUMEN FINANCIERO</div>""", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            descuento_pct = st.number_input("Descuento (%)", 0.0, 100.0, 0.0, 0.5,
                key="cot_desc_pct")
        with c2:
            iva_pct_sel = st.selectbox("IVA (%)", [0, 5, 19], key="cot_iva")
        with c3:
            pass

        desc_val_calc = subtotal_calc * descuento_pct / 100
        base_iva_calc = subtotal_calc - desc_val_calc
        iva_val_calc  = base_iva_calc * iva_pct_sel / 100
        total_calc    = base_iva_calc + iva_val_calc

        moneda_sym = session_state.get("cot_moneda", "COP")

        st.markdown(f"""
        <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:0.8rem;margin:0.8rem 0;'>
            <div class='metric-box'>
                <div class='metric-val'>${subtotal_calc:,.0f}</div>
                <div class='metric-unit'>{moneda_sym}</div>
                <div class='metric-label'>SUBTOTAL</div>
            </div>
            <div class='metric-box' style='border-color:rgba(255,82,82,0.4);'>
                <div class='metric-val' style='color:#FF5252;'>- ${desc_val_calc:,.0f}</div>
                <div class='metric-unit'>{moneda_sym}</div>
                <div class='metric-label'>DESCUENTO {descuento_pct:.0f}%</div>
            </div>
            <div class='metric-box' style='border-color:rgba(0,188,212,0.4);'>
                <div class='metric-val' style='color:#00BCD4;'>${iva_val_calc:,.0f}</div>
                <div class='metric-unit'>{moneda_sym}</div>
                <div class='metric-label'>IVA {iva_pct_sel}%</div>
            </div>
            <div class='metric-box' style='border-color:rgba(0,230,118,0.5);
                        background:linear-gradient(135deg,rgba(0,230,118,0.1),rgba(0,230,118,0.03));'>
                <div class='metric-val' style='color:#00E676;font-size:1.6rem;'>${total_calc:,.0f}</div>
                <div class='metric-unit'>{moneda_sym}</div>
                <div class='metric-label'>TOTAL A PAGAR</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Condiciones y notas ──────────────────────────────────────────────
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>7</span>
        CONDICIONES Y NOTAS</div>""", unsafe_allow_html=True)

        cot_condiciones = st.text_area(
            "Condiciones comerciales",
            key="cot_condiciones",
            height=150,
            value=(
                "1. Precios en pesos colombianos (COP) IVA incluido según se indica.\n"
                "2. Validez de la cotización: 30 días a partir de la fecha de emisión.\n"
                "3. Forma de pago: 50% anticipo, 50% contra entrega e instalación.\n"
                "4. Tiempo de entrega estimado: 15 a 20 días hábiles después del anticipo.\n"
                "5. Garantía: paneles 12 años producto / 25 años rendimiento. "
                "Inversor 5 años. Baterías LiFePO4 5 años o 4000 ciclos.\n"
                "6. La instalación incluye puesta en servicio y capacitación al usuario.\n"
                "7. No incluye obra civil ni adecuaciones eléctricas previas no descritas.\n"
                "8. Precios sujetos a variación de TRM para equipos importados."
            )
        )
        cot_notas = st.text_area(
            "Notas adicionales (opcional)",
            key="cot_notas",
            height=80,
            placeholder="Observaciones especiales, exclusiones, referencias técnicas..."
        )

        # ── Acciones ─────────────────────────────────────────────────────────
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        col_acc1, col_acc2, col_acc3 = st.columns(3)

        # Armar dict de datos completo
        import json
        _datos_pdf = {
            "tipo_sistema":  tipo_sel,
            "empresa": {
                "nombre":         session_state.get("cot_emp_nombre",""),
                "nit":            session_state.get("cot_emp_nit",""),
                "tel":            session_state.get("cot_emp_tel",""),
                "email":          session_state.get("cot_emp_email",""),
                "web":            session_state.get("cot_emp_web",""),
                "representante":  session_state.get("cot_emp_rep",""),
                "dir":            session_state.get("cot_emp_dir",""),
            },
            "cliente": {
                "nombre": session_state.get("cot_cli_nombre",""),
                "nit":    session_state.get("cot_cli_nit",""),
                "tel":    session_state.get("cot_cli_tel",""),
                "email":  session_state.get("cot_cli_email",""),
                "ciudad": session_state.get("cot_cli_ciudad",""),
                "dir":    session_state.get("cot_cli_dir",""),
            },
            "meta": {
                "numero":       session_state.get("cot_numero","COT-001"),
                "fecha":        cot_fecha.strftime("%d/%m/%Y"),
                "valida_hasta": fecha_validez.strftime("%d/%m/%Y"),
                "estado":       session_state.get("cot_estado","BORRADOR"),
            },
            "dimensionamiento": dim,
            "items":        items_editados,
            "financiero": {
                "subtotal":      subtotal_calc,
                "descuento_pct": descuento_pct,
                "iva_pct":       iva_pct_sel,
                "moneda":        moneda_sym,
            },
            "condiciones": session_state.get("cot_condiciones",""),
            "notas":       session_state.get("cot_notas",""),
        }

        with col_acc1:
            if st.button("💾 Guardar Cotización", use_container_width=True,
                         key="cot_btn_guardar", type="primary"):
                conn = get_conn()
                conn.execute("""
                    INSERT INTO cotizaciones(
                        proyecto_id,tipo_sistema,numero,
                        cliente_nombre,cliente_nit,cliente_tel,cliente_email,
                        cliente_ciudad,cliente_dir,
                        empresa_nombre,empresa_nit,empresa_tel,empresa_email,
                        empresa_web,empresa_dir,
                        items_json,subtotal,descuento,iva_pct,total,
                        moneda,validez_dias,condiciones,notas,estado)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    proyecto_id, tipo_sel,
                    session_state.get("cot_numero",""),
                    session_state.get("cot_cli_nombre",""),
                    session_state.get("cot_cli_nit",""),
                    session_state.get("cot_cli_tel",""),
                    session_state.get("cot_cli_email",""),
                    session_state.get("cot_cli_ciudad",""),
                    session_state.get("cot_cli_dir",""),
                    session_state.get("cot_emp_nombre",""),
                    session_state.get("cot_emp_nit",""),
                    session_state.get("cot_emp_tel",""),
                    session_state.get("cot_emp_email",""),
                    session_state.get("cot_emp_web",""),
                    session_state.get("cot_emp_dir",""),
                    json.dumps(items_editados, ensure_ascii=False),
                    subtotal_calc, descuento_pct, iva_pct_sel, total_calc,
                    moneda_sym, cot_validez,
                    session_state.get("cot_condiciones",""),
                    session_state.get("cot_notas",""),
                    session_state.get("cot_estado","BORRADOR"),
                ))
                conn.commit(); conn.close()
                st.success(f"✓ Cotización {session_state.get('cot_numero','')} guardada")
                st.rerun()

        with col_acc2:
            try:
                pdf_bytes = generar_pdf_cotizacion(_datos_pdf)
                fname_pdf = (f"Cotizacion_{session_state.get('cot_numero','001')}_"
                             f"{p_info[1].replace(' ','_')}_{date.today().strftime('%Y%m%d')}.pdf")
                st.download_button(
                    "⬇ Descargar PDF",
                    data=pdf_bytes,
                    file_name=fname_pdf,
                    mime="application/pdf",
                    use_container_width=True,
                    key="cot_dl_pdf"
                )
            except Exception as ex:
                st.error(f"Error generando PDF: {ex}")

        with col_acc3:
            if st.button("🗑 Limpiar ítems extra", use_container_width=True,
                         key="cot_btn_limpiar"):
                session_state.pop("_cot_extra_items", None)
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_hist:
        st.markdown("""
        <div class='sol-card-title'>📋 HISTORIAL DE COTIZACIONES</div>
        """, unsafe_allow_html=True)

        if hist.empty:
            st.markdown("""
            <div class='info-note' style='text-align:center;padding:2rem;'>
                No hay cotizaciones guardadas para este proyecto.
                Crea la primera en la pestaña anterior.
            </div>""", unsafe_allow_html=True)
        else:
            for _, row in hist.iterrows():
                estado_color = {
                    "BORRADOR":"#8A9BBD","ENVIADA":"#00BCD4",
                    "APROBADA":"#00E676","RECHAZADA":"#FF5252","VENCIDA":"#FF6B35"
                }.get(row["estado"],"#8A9BBD")

                st.markdown(f"""
                <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
                            padding:1rem 1.4rem;margin-bottom:0.6rem;
                            display:flex;gap:2rem;flex-wrap:wrap;align-items:center;'>
                    <span style='font-family:Rajdhani,sans-serif;font-size:1.05rem;
                                 color:#FFB300;font-weight:700;'>
                        N° {row['numero'] or row['id']}</span>
                    <span style='font-size:0.82rem;color:#8A9BBD;'>
                        Cliente: <b style='color:#E8EDF5;'>{row['cliente_nombre'] or '—'}</b></span>
                    <span style='font-size:0.82rem;color:#8A9BBD;'>
                        Sistema: <b style='color:#FFD54F;'>{row['tipo_sistema']}</b></span>
                    <span style='font-size:0.82rem;color:#8A9BBD;'>
                        Total: <b style='color:#00E676;font-family:Share Tech Mono;'>
                        $ {row['total']:,.0f} {row['moneda']}</b></span>
                    <span style='font-size:0.82rem;color:#8A9BBD;'>
                        Fecha: {row['creado'][:10]}</span>
                    <span style='background:{estado_color}22;border:1px solid {estado_color};
                                border-radius:20px;padding:2px 10px;font-size:0.72rem;
                                color:{estado_color};font-weight:700;'>
                        {row['estado']}</span>
                </div>
                """, unsafe_allow_html=True)

            # Resumen
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            total_h = hist["total"].sum()
            aprobadas = len(hist[hist["estado"] == "APROBADA"])
            c1,c2,c3,c4 = st.columns(4)
            for col_h, lbl_h, val_h, col_c in [
                (c1, "Total cotizaciones", len(hist), "#FFB300"),
                (c2, "Aprobadas",  aprobadas, "#00E676"),
                (c3, "Valor total cotizado", f"${total_h:,.0f}", "#00BCD4"),
                (c4, "Tasa aprobación",
                 f"{aprobadas/len(hist)*100:.0f}%", "#FFD54F"),
            ]:
                col_h.markdown(f"""
                <div class='metric-box' style='border-color:{col_c}44;'>
                    <div class='metric-val' style='color:{col_c};'>{val_h}</div>
                    <div class='metric-label'>{lbl_h.upper()}</div>
                </div>""", unsafe_allow_html=True)

            # Eliminar cotización
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            with st.expander("🗑 Eliminar una cotización"):
                opts_del = {
                    f"N°{r['numero'] or r['id']} — {r['cliente_nombre'] or '—'} — ${r['total']:,.0f}": int(r["id"])
                    for _, r in hist.iterrows()
                }
                sel_del = st.selectbox("Seleccionar:", list(opts_del.keys()),
                                        key="cot_del_sel")
                if st.button("🗑 Confirmar eliminación", use_container_width=True,
                             key="cot_btn_del"):
                    conn = get_conn()
                    conn.execute("DELETE FROM cotizaciones WHERE id=? AND proyecto_id=?",
                                 (opts_del[sel_del], proyecto_id))
                    conn.commit(); conn.close()
                    st.success("Cotización eliminada ✓")
                    st.rerun()
