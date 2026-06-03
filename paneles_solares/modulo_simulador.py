"""
modulo_simulador.py — Simulador de Dimensionamiento Fotovoltaico
SolarCalc Pro · Módulo externo
Soporta sistemas OFF-GRID, ON-GRID e HÍBRIDO
"""
import streamlit as st
import sqlite3
import pandas as pd
import math
import io
from datetime import datetime

from db_utils import get_conn, init_modulos_db

# ── ReportLab ────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Helpers ──────────────────────────────────────────────────────────────────
def tension_dc(wh: float) -> int:
    if wh < 2000: return 12
    if wh < 4000: return 24
    return 48

def num_paneles(pot_inst: float, pot_panel: float) -> int:
    if pot_panel <= 0: return 0
    return math.ceil(pot_inst / pot_panel)

def calcular_baterias(wh: float, vdc: int, dod: float = 0.80, cap: float = 100) -> dict:
    ah_bruto = wh / vdc
    ah_dod   = ah_bruto / dod
    ah_final = ah_dod / 0.85
    n        = math.ceil(ah_final / cap)
    return {"ah_bruto": ah_bruto, "ah_dod": ah_dod, "ah_final": ah_final,
            "num": n, "energia_kwh": n * cap * vdc / 1000}

def payback(costo: float, ahorro_anual: float) -> float:
    return round(costo / ahorro_anual, 1) if ahorro_anual > 0 else 0

def vpn_calc(costo: float, ahorro_anual: float, tasa: float, anos: int) -> float:
    if tasa <= 0: return ahorro_anual * anos - costo
    factor = (1 - (1 + tasa)**-anos) / tasa
    return round(ahorro_anual * factor - costo, 0)

def tir_calc(costo: float, ahorro_anual: float, anos: int = 25) -> float:
    flujos = [-costo] + [ahorro_anual] * anos
    lo, hi = -0.5, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        npv = sum(f / (1 + mid) ** i for i, f in enumerate(flujos))
        if abs(npv) < 0.01: break
        if npv > 0: lo = mid
        else: hi = mid
    return round(mid * 100, 1)

# ── INFORME PDF ───────────────────────────────────────────────────────────────
def generar_informe_pdf(sim: dict, proyecto_nombre: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    tipo_s = sim.get("tipo_sistema", "OFF-GRID")
    COLOR_MAP = {"OFF-GRID":"#FFB300","ON-GRID":"#FF6B35","HIBRIDO":"#F59E0B"}
    LABEL_MAP = {"OFF-GRID":"🔋 OFF-GRID","ON-GRID":"🔌 ON-GRID","HIBRIDO":"⚡ HÍBRIDO"}
    col_hex = COLOR_MAP.get(tipo_s, "#FFB300")
    lbl_pdf = LABEL_MAP.get(tipo_s, tipo_s)

    SOL   = colors.HexColor(col_hex)
    DARK  = colors.HexColor("#0A0E1A")
    CARD  = colors.HexColor("#1A2235")
    TEXT  = colors.HexColor("#E8EDF5")
    TEXT2 = colors.HexColor("#8A9BBD")
    GREEN = colors.HexColor("#00E676")
    CYAN  = colors.HexColor("#00BCD4")
    MONO  = colors.HexColor("#FFD54F")
    BRD   = colors.HexColor("#2A3A55")
    BAT   = colors.HexColor("#A78BFA")
    GRID  = colors.HexColor("#FF6B35")

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle("h1",  fontName="Helvetica-Bold", fontSize=20,
                          textColor=SOL, alignment=TA_CENTER, spaceAfter=6)
    h2  = ParagraphStyle("h2",  fontName="Helvetica-Bold", fontSize=13,
                          textColor=SOL, spaceBefore=14, spaceAfter=4)
    sub = ParagraphStyle("sub", fontName="Helvetica",      fontSize=9,
                          textColor=TEXT2, alignment=TA_CENTER, spaceAfter=10)
    bod = ParagraphStyle("bod", fontName="Helvetica",      fontSize=9,
                          textColor=TEXT, spaceAfter=4)

    def sec_table(title, rows):
        data = [[Paragraph(f"<b>{title}</b>", ParagraphStyle("th",fontName="Helvetica-Bold",
                 fontSize=9,textColor=DARK)),""],]
        for k, v in rows:
            data.append([Paragraph(k, ParagraphStyle("td",fontName="Helvetica",
                          fontSize=9,textColor=TEXT2)),
                         Paragraph(f"<b>{v}</b>", ParagraphStyle("tv",fontName="Helvetica-Bold",
                          fontSize=9,textColor=MONO))])
        t = Table(data, colWidths=[10*cm, 6*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0),  SOL),
            ("SPAN",         (0,0),(-1,0)),
            ("TEXTCOLOR",    (0,0),(-1,0),  DARK),
            ("ALIGN",        (0,0),(-1,0),  "LEFT"),
            *[("BACKGROUND", (0,i),(-1,i), CARD if i%2==1 else colors.HexColor("#161D30"))
              for i in range(1, len(data))],
            ("GRID",         (0,0),(-1,-1), 0.4, BRD),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",  (0,0),(-1,-1), 8),
            ("ALIGN",        (1,1),(-1,-1), "RIGHT"),
        ]))
        return t

    pr_val   = sim.get('pr', 75)
    hsp_ef_v = sim.get('hsp_ef', sim.get('hsp', 4.2) * pr_val / 100)
    gen_dia  = sim.get('gen_dia_kwh', 0)
    gen_ano  = sim.get('gen_anual_kwh', 0)
    aut_h    = sim.get('autonomia_h', 0)
    fs_map   = {"OFF-GRID": "25%", "ON-GRID": "10%", "HIBRIDO": "15%"}
    fs_lbl   = fs_map.get(tipo_s, "25%")

    story = []

    # Portada
    story.append(Paragraph("☀  SOLARCALC PRO", h1))
    story.append(Paragraph(f"INFORME DE SIMULACIÓN — {lbl_pdf}", h1))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=SOL))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Proyecto: <b>{proyecto_nombre}</b>  |  "
        f"Sistema: <b>{lbl_pdf}</b>  |  "
        f"Municipio: {sim.get('municipio','—')}  |  "
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub))
    story.append(Spacer(1, 0.5*cm))

    # 1. Consumo
    story.append(sec_table("1. ANÁLISIS DE CONSUMO ENERGÉTICO", [
        ("Tipo de sistema",                      lbl_pdf),
        ("Consumo diario base (Wh/día)",         f"{sim['consumo_wh']:,.0f} Wh"),
        (f"Factor de seguridad ({fs_lbl})",      f"× {1 + int(fs_lbl[:-1])/100:.2f}"),
        ("Consumo diario con FS (Wh/día)",       f"{sim['consumo_fs_wh']:,.0f} Wh"),
        ("Consumo mensual estimado (kWh/mes)",   f"{sim['consumo_fs_wh']*30/1000:,.1f} kWh"),
        ("Consumo anual estimado (kWh/año)",     f"{sim['consumo_fs_wh']*365/1000:,.0f} kWh"),
        ("Ubicación analizada",                  sim.get('municipio','—')),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 2. Irradiación y PR
    story.append(sec_table("2. IRRADIACIÓN SOLAR Y PERFORMANCE RATIO", [
        ("Hora Solar Pico bruta (HSP)",          f"{sim['hsp']} h/día"),
        ("Performance Ratio (PR)",               f"{pr_val}%"),
        ("HSP efectiva (HSP × PR)",              f"{hsp_ef_v:.2f} h/día"),
        ("Irradiación mes analizado",            f"{sim['hsp']*30:.1f} kWh/m²/mes"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 3. Campo FV
    vmp     = round(sim.get('voc', 49.9) * 0.80, 1)
    serie_r = max(1, round(sim['vdc'] / vmp)) if vmp > 0 else 1
    par_r   = math.ceil(sim['num_paneles'] / serie_r)
    story.append(sec_table("3. CAMPO FOTOVOLTAICO", [
        ("Panel solar (modelo)",                 sim.get('modelo_panel','—')),
        ("Potencia por panel (Wp)",              f"{sim['pot_panel_wp']:,.0f} Wp"),
        ("Potencia instalada mínima (Wp)",       f"{sim['pot_instalada_wp']:,.0f} Wp"),
        ("Número de paneles requeridos",         f"{sim['num_paneles']} paneles"),
        ("Configuración (Serie × Paralelo)",     f"{serie_r}S × {par_r}P"),
        ("Potencia real del array (kWp)",        f"{sim['num_paneles']*sim['pot_panel_wp']/1000:.2f} kWp"),
        ("Generación estimada/día",              f"{gen_dia:.2f} kWh/día"),
        ("Generación anual estimada",            f"{gen_ano:,.0f} kWh/año"),
        ("Tensión total array Voc (V)",          f"{sim.get('voc',49.9)*serie_r:.1f} V"),
        ("Corriente total array Isc (A)",        f"{sim.get('isc',14.0)*par_r:.1f} A"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 4. Baterías / Inversor según sistema
    if tipo_s == "OFF-GRID":
        story.append(sec_table("4. BANCO DE BATERÍAS", [
            ("Número de baterías",               f"{sim['num_baterias']} unidades"),
            ("Capacidad por batería",            f"{sim['bat_cap_ah']:.0f} Ah"),
            ("Energía almacenada (kWh)",         f"{sim['energia_kwh']:.2f} kWh"),
            ("Tensión del banco",                f"{sim['vdc']} V DC"),
            ("Controlador MPPT",                 sim.get('mppt_modelo','—')),
            ("Inversor DC/AC",                   f"{sim['inversor_kva']:.2f} kVA"),
        ]))
    elif tipo_s == "HIBRIDO":
        story.append(sec_table("4. INVERSOR HÍBRIDO + BANCO DE BATERÍAS", [
            ("Inversor híbrido MPPT",            f"{sim['inversor_kva']:.2f} kW"),
            ("Número de baterías",               f"{sim['num_baterias']} unidades"),
            ("Capacidad por batería",            f"{sim['bat_cap_ah']:.0f} Ah"),
            ("Energía banco baterías (kWh)",     f"{sim['energia_kwh']:.2f} kWh"),
            ("Tensión banco",                    f"{sim['vdc']} V DC"),
            ("Autonomía estimada",               f"{aut_h:.1f} horas"),
            ("Modos de operación",               "Solar puro / Solar+Red / Solar+Bat / Red+Bat"),
        ]))
    else:
        story.append(sec_table("4. INVERSOR GRID-TIE", [
            ("Inversor grid-tie MPPT",           f"{sim['inversor_kva']:.2f} kW"),
            ("Tensión salida AC",                "220 V / 60 Hz"),
            ("Función anti-isla",                "Integrada (CREG 030-2018)"),
            ("Medidor bidireccional",            "Requerido (CREG 030-2018)"),
        ]))
    story.append(PageBreak())

    # 5. Análisis financiero
    story.append(Paragraph("5. ANÁLISIS FINANCIERO Y AMBIENTAL", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRD, spaceAfter=6))

    fin_rows = [
        ("Costo estimado del sistema ($)",       f"$ {sim.get('costo_sistema',0):,.0f}"),
        ("Tarifa energía actual ($/kWh)",        f"$ {sim.get('tarifa_kwh',650):,.0f}"),
        ("Ahorro mensual (autoconsumo) ($)",     f"$ {sim.get('ahorro_mensual',0):,.0f}"),
        ("Beneficio anual total ($)",            f"$ {sim.get('ahorro_mensual',0)*12:,.0f}"),
        ("Período de retorno — Payback",         f"{sim.get('payback_anos',0):.1f} años"),
        ("Tasa Interna de Retorno — TIR",        f"{sim.get('tir',0):.1f}%"),
        ("Valor Presente Neto a 25 años ($)",    f"$ {sim.get('vpn',0):,.0f}"),
        ("Generación anual estimada",            f"{gen_ano:,.0f} kWh/año"),
        ("CO₂ evitado (kg/año)",                 f"{sim.get('co2_kg_anual',0):,.0f} kg"),
        ("CO₂ evitado en 25 años (ton)",         f"{sim.get('co2_kg_anual',0)*25/1000:.1f} ton"),
        ("Árboles equivalentes / año",           f"{sim.get('co2_kg_anual',0)/21:.0f} árboles"),
    ]
    story.append(sec_table("INDICADORES FINANCIEROS Y AMBIENTALES", fin_rows))
    story.append(Spacer(1, 0.6*cm))

    # Notas
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRD))
    story.append(Paragraph(
        "NOTAS: Los valores financieros son estimados con base en tarifas actuales y pueden variar. "
        "El dimensionamiento cumple con los criterios del RETIE (Res. 40117/2014). "
        "Sistemas ON-GRID e HÍBRIDO deben cumplir CREG 030-2018 (medidor bidireccional, anti-isla). "
        "Se recomienda verificar con un ingeniero electricista certificado antes de la instalación.",
        ParagraphStyle("nota", fontName="Helvetica", fontSize=7.5, textColor=TEXT2,
                        spaceBefore=6, leading=11)))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"<font color='#2A3A55'>SolarCalc Pro · {lbl_pdf} · Simulación generada el "
        f"{datetime.now().strftime('%d/%m/%Y a las %H:%M')} · Plano de referencia</font>",
        ParagraphStyle("ft", fontName="Helvetica", fontSize=7, alignment=TA_CENTER, spaceBefore=4)))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS PARA CARGAR DATOS DE CADA TIPO DE SISTEMA
# ══════════════════════════════════════════════════════════════════════════════
def _cargar_ongrid(ss: dict, pan, p) -> dict:
    """Lee session_state del módulo ON-GRID y devuelve dict normalizado."""
    hsp    = ss.get("_og_hsp_calc",  p[4] if p and p[4] else 4.2)
    pr     = ss.get("_og_pr_dec",    0.80)
    wp     = ss.get("og_wp",         pan[3] if pan else 550)
    voc    = ss.get("og_voc",        pan[4] if pan else 49.9)
    isc    = ss.get("og_isc",        pan[5] if pan else 14.0)
    n_pan  = ss.get("_og_n_paneles", 0)
    pot_i  = ss.get("_og_pot_inst",  0.0)
    pot_inv= ss.get("_og_pot_inv_kw",3.0)
    consumo= ss.get("_og_consumo_fs", ss.get("consumo_recibo_wh", 3000.0))
    gen_a  = ss.get("_og_gen_anio",  0.0)
    payb   = ss.get("_og_payback",   0.0)
    inv_t  = ss.get("_og_inv_total", 0.0)
    ben_a  = ss.get("_og_beneficio_anio", 0.0)
    co2_a  = ss.get("_og_co2_anio",  0.0)
    return dict(hsp=hsp, pr=pr, wp=wp, voc=voc, isc=isc, n_pan=n_pan,
                pot_inst=pot_i, pot_inv_kw=pot_inv, consumo_fs=consumo,
                gen_anio=gen_a, payback=payb, inv_total=inv_t,
                ben_anio=ben_a, co2_anio=co2_a,
                n_baterias=0, cap_bat_kwh=0, autonomia_h=0,
                pan_serie=ss.get("_og_pan_serie",1),
                n_strings=ss.get("_og_n_strings",1))

def _cargar_hibrido(ss: dict, pan, p) -> dict:
    """Lee session_state del módulo HÍBRIDO y devuelve dict normalizado."""
    hsp    = ss.get("_hib_hsp",      p[4] if p and p[4] else 4.2)
    pr     = ss.get("_hib_pr",       0.80)
    wp     = ss.get("hib_wp",        pan[3] if pan else 550)
    voc    = ss.get("hib_voc",       pan[4] if pan else 49.9)
    isc    = ss.get("hib_isc",       pan[5] if pan else 14.0)
    n_pan  = ss.get("_hib_n_pan",    0)
    pot_i  = ss.get("_hib_pot_inst", 0.0)
    pot_inv= ss.get("_hib_pot_inv",  3.0)
    consumo= ss.get("hib_consumo_fs",ss.get("consumo_recibo_wh", 3000.0))
    gen_a  = ss.get("_hib_gen_anio", 0.0)
    payb   = ss.get("_hib_payback",  0.0)
    inv_t  = ss.get("_hib_inv_tot",  0.0)
    ben_a  = ss.get("_hib_ben_anio", 0.0)
    co2_a  = ss.get("_hib_co2_anio", 0.0)
    n_bat  = ss.get("_hib_n_baterias", 0)
    cap_wh = ss.get("_hib_cap_real_wh", 0.0)
    aut_h  = ss.get("_hib_aut_horas",   0.0)
    return dict(hsp=hsp, pr=pr, wp=wp, voc=voc, isc=isc, n_pan=n_pan,
                pot_inst=pot_i, pot_inv_kw=pot_inv, consumo_fs=consumo,
                gen_anio=gen_a, payback=payb, inv_total=inv_t,
                ben_anio=ben_a, co2_anio=co2_a,
                n_baterias=n_bat, cap_bat_kwh=cap_wh/1000,
                autonomia_h=aut_h,
                pan_serie=ss.get("_hib_pan_serie",1),
                n_strings=ss.get("_hib_n_strings",1))

def _cargar_offgrid(ss: dict, pan, p, cargas) -> dict:
    """Lee session_state del módulo OFF-GRID y devuelve dict normalizado."""
    consumo_inv = (cargas["cantidad"]*cargas["potencia_w"]*cargas["horas_dia"]).sum()                   if not cargas.empty else 0.0
    consumo_rec = ss.get("consumo_recibo_wh", 0.0)
    consumo_base= max(consumo_inv, consumo_rec) if consumo_rec > 0 else consumo_inv
    hsp    = ss.get("calc_hsp",         p[4] if p and p[4] else 4.2)
    pr     = ss.get("calc_pr",          0.75)
    wp     = ss.get("calc_pot_panel_wp",pan[3] if pan else 550)
    voc    = pan[4] if pan else 49.9
    isc    = pan[5] if pan else 14.0
    n_pan  = ss.get("calc_num_paneles", 0)
    pot_i  = ss.get("calc_pot_real_wp", 0.0)
    consumo= ss.get("calc_consumo_fs_wh",consumo_base*1.25)
    n_bat  = ss.get("calc_num_baterias",0)
    vdc    = ss.get("calc_vdc",         48)
    cap_ah = ss.get("calc_bat_cap_ah",  100)
    cap_kwh= n_bat * cap_ah * int(vdc) / 1000 if n_bat else 0.0
    gen_d  = ss.get("calc_gen_dia_kwh", (pot_i/1000)*float(hsp)*float(pr))
    gen_a  = gen_d * 365
    return dict(hsp=hsp, pr=pr, wp=wp, voc=voc, isc=isc, n_pan=n_pan,
                pot_inst=pot_i, pot_inv_kw=pot_i/1000*1.25,
                consumo_fs=consumo, gen_anio=gen_a,
                payback=0.0, inv_total=0.0, ben_anio=0.0, co2_anio=gen_a*0.126,
                n_baterias=n_bat, cap_bat_kwh=cap_kwh, autonomia_h=0.0,
                pan_serie=ss.get("calc_serie",1),
                n_strings=ss.get("calc_paralelo",1))


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL DEL MÓDULO
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_simulador(proyecto_id: int, ss: dict):
    """Renderiza el módulo Simulador completo dentro del app principal."""
    init_modulos_db()

    conn = get_conn()
    p      = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    pan    = conn.execute("SELECT * FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
                          (proyecto_id,)).fetchone()
    cargas = pd.read_sql("SELECT cantidad,potencia_w,horas_dia,es_motor FROM cargas "
                         "WHERE proyecto_id=?", conn, params=(proyecto_id,))
    conn.close()

    # CSS local
    st.markdown("""
    <style>
    .sim-header{background:linear-gradient(135deg,#0A0E1A,#1A2235);border:1px solid #2A3A55;
     border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.2rem;}
    .sim-header h2{font-family:Rajdhani,sans-serif;font-size:1.6rem;font-weight:700;
     color:#FFB300;margin:0;letter-spacing:2px;}
    .sim-header p{color:#8A9BBD;font-size:0.8rem;margin:0.2rem 0 0;letter-spacing:2px;}
    .sis-pill{display:inline-block;font-family:Rajdhani,sans-serif;font-weight:700;
     font-size:0.78rem;padding:3px 12px;border-radius:20px;letter-spacing:1px;margin-left:8px;}
    </style>
    """, unsafe_allow_html=True)

    # ── Detectar tipo de sistema activo ──────────────────────────────────────
    tipo_sistema = ss.get("tipo_sistema", "OFF-GRID")
    COLOR_SIS = {"OFF-GRID": "#FFB300", "ON-GRID": "#FF6B35", "HIBRIDO": "#F59E0B"}
    LABEL_SIS = {"OFF-GRID": "🔋 OFF-GRID", "ON-GRID": "🔌 ON-GRID", "HIBRIDO": "⚡ HÍBRIDO"}
    col_sis   = COLOR_SIS.get(tipo_sistema, "#FFB300")
    lbl_sis   = LABEL_SIS.get(tipo_sistema, tipo_sistema)

    st.markdown(f"""
    <div class='sim-header'>
        <h2>🔬 SIMULADOR DE DIMENSIONAMIENTO FOTOVOLTAICO
            <span class='sis-pill' style='background:{col_sis};color:#0A0E1A;'>{lbl_sis}</span>
        </h2>
        <p>ANÁLISIS TÉCNICO · FINANCIERO · AMBIENTAL · {tipo_sistema}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Cargar datos del sistema activo ──────────────────────────────────────
    if tipo_sistema == "ON-GRID":
        datos_sis = _cargar_ongrid(ss, pan, p)
        fs_label  = "10% FS (ON-GRID)"
        fs_factor = 1.10
    elif tipo_sistema == "HIBRIDO":
        datos_sis = _cargar_hibrido(ss, pan, p)
        fs_label  = "15% FS (HÍBRIDO)"
        fs_factor = 1.15
    else:
        datos_sis = _cargar_offgrid(ss, pan, p, cargas)
        fs_label  = "25% FS (OFF-GRID)"
        fs_factor = 1.25

    # Consumo base general
    consumo_inv = (cargas["cantidad"]*cargas["potencia_w"]*cargas["horas_dia"]).sum()                   if not cargas.empty else 0.0
    consumo_rec       = ss.get("consumo_recibo_wh", 0.0)
    consumo_base_auto = max(consumo_inv, consumo_rec) if consumo_rec > 0 else consumo_inv

    # Pre-cargar defaults desde el sistema activo
    pot_pan_calc = datos_sis["wp"]
    hsp_calc     = float(datos_sis["hsp"])
    bat_cap_calc = ss.get("calc_bat_cap_ah", ss.get("hib_cap_bat", 100))
    cons_fs_calc = datos_sis["consumo_fs"] if datos_sis["consumo_fs"] > 0                    else consumo_base_auto * fs_factor

    # Tip de fuente
    tiene_datos = datos_sis["n_pan"] > 0
    if tiene_datos:
        tip_color = col_sis
        tip_txt   = (f"✓ Datos cargados desde el módulo <b>{lbl_sis}</b>: "
                     f"{datos_sis['n_pan']} paneles · {datos_sis['pot_inst']/1000:.2f} kWp "
                     f"· HSP {datos_sis['hsp']:.2f} h · PR {int(datos_sis['pr']*100)}%")
    else:
        tip_color = "#8A9BBD"
        tip_txt   = (f"ℹ Dimensiona primero en el módulo <b>{lbl_sis}</b> para cargar "
                     f"datos automáticamente, o ingresa los parámetros manualmente abajo.")

    st.markdown(f"""
    <div style='background:rgba(0,0,0,0.2);border:1px solid {tip_color}44;
     border-left:4px solid {tip_color};border-radius:8px;
     padding:0.6rem 1rem;font-size:0.82rem;color:#8A9BBD;margin-bottom:1rem;'>
        {tip_txt}
    </div>
    """, unsafe_allow_html=True)

    # ── Formulario de simulación ──────────────────────────────────────────────
    with st.expander("⚙ PARÁMETROS DE SIMULACIÓN", expanded=True):
        cola, colb, colc = st.columns(3)
        with cola:
            st.markdown(f"**⚡ Energético — {lbl_sis}**")
            consumo_default = max(100.0, min(float(consumo_base_auto) if consumo_base_auto > 0
                                             else 3000.0, 500000.0))
            hsp_default     = max(0.5, min(float(hsp_calc), 12.0))
            irrad_default   = max(10.0, min(hsp_default * 30, 300.0))

            consumo_sim = st.number_input("Consumo diario base (Wh/día)", 100.0, 500000.0,
                                          consumo_default, 100.0, key="sim_consumo")
            pr_sim      = st.slider("Performance Ratio — PR (%)", 65, 95,
                                    int(datos_sis["pr"] * 100),
                                    help="OFF-GRID:70-80% | ON-GRID:80-88% | HÍBRIDO:78-85%",
                                    key="sim_pr")
            hsp_sim     = st.number_input("Hora Solar Pico — HSP (h/día)", 0.5, 12.0,
                                          hsp_default, 0.1, key="sim_hsp")
            irrad_sim   = st.number_input("Irradiación mes menor (kWh/m²/mes)", 10.0, 300.0,
                                          irrad_default, 0.5, key="sim_irrad")
            municipio_s = st.text_input("Municipio analizado",
                                         value=p[2] if p and p[2] else "",
                                         key="sim_mun")

        with colb:
            st.markdown("**🔆 Sistema FV**")
            pp_default  = max(50,   min(int(pot_pan_calc), 1000))
            voc_default = max(10.0, min(float(datos_sis["voc"]), 100.0))
            isc_default = max(1.0,  min(float(datos_sis["isc"]),  30.0))
            bc_default  = max(50,   min(int(bat_cap_calc), 500))

            pot_panel_s = st.number_input("Potencia panel (Wp)", 50, 1000,
                                           pp_default, 50, key="sim_pp")
            voc_s       = st.number_input("Voc panel (V)", 10.0, 100.0,
                                           voc_default, 0.1, key="sim_voc")
            isc_s       = st.number_input("Isc panel (A)", 1.0, 30.0,
                                           isc_default, 0.1, key="sim_isc")
            modelo_s    = st.text_input("Modelo panel",
                                         value=pan[2] if pan else "Panel 550Wp", key="sim_mod")
            dod_s       = st.slider("DOD baterías (%)", 50, 100,
                                    80 if tipo_sistema == "OFF-GRID" else
                                    (int(ss.get("hib_dod", 80)) if tipo_sistema == "HIBRIDO" else 50),
                                    key="sim_dod")
            bat_cap_s   = st.number_input("Capacidad batería (Ah)", 50, 500,
                                           bc_default, 50, key="sim_bc")
            if tipo_sistema in ("ON-GRID", "HIBRIDO"):
                v_mppt_min_s = st.number_input("V MPPT mínimo inversor (V)", 50, 400,
                    int(ss.get("og_vmppt_min", ss.get("hib_vmppt_min", 200))),
                    key="sim_vmppt_min")
                v_mppt_max_s = st.number_input("V MPPT máximo inversor (V)", 200, 1500,
                    int(ss.get("og_vmppt_max", ss.get("hib_vmppt_max", 800))),
                    key="sim_vmppt_max")
            else:
                v_mppt_min_s, v_mppt_max_s = 0, 0

        with colc:
            st.markdown("**💰 Financiero**")
            # Pre-cargar inversión del módulo activo si existe
            inv_preload = datos_sis["inv_total"] if datos_sis["inv_total"] > 0                           else float(ss.get("presup_total", 0))
            costo_default = max(0.0, min(inv_preload, 999999999.0))

            costo_s  = st.number_input("Costo estimado sistema ($)", 0.0, 999999999.0,
                                        costo_default, 100000.0, key="sim_costo")
            tarifa_s = st.number_input("Tarifa energía ($/kWh)", 0.0, 5000.0,
                                        700.0, 10.0, key="sim_tarifa",
                                        help="Precio actual del kWh en su factura")
            tasa_s   = st.number_input("Tasa de descuento (%/año)", 0.0, 30.0,
                                        8.0, 0.5, key="sim_tasa") / 100
            anos_s   = st.number_input("Horizonte de evaluación (años)", 5, 30, 25,
                                        key="sim_anos")
            factor_co2 = st.number_input("Factor emisión CO₂ (kg/kWh)", 0.05, 1.0,
                                          0.136, 0.001, key="sim_co2",
                                          help="Colombia: ~0.136 kg CO₂/kWh (UPME 2023)")
            if tipo_sistema in ("ON-GRID", "HIBRIDO"):
                tarifa_iny_s = st.number_input(
                    "Precio compra excedente red ($/kWh)", 0.0, 5000.0, 350.0, 10.0,
                    help="Precio al que la empresa de energía compra el excedente (~50% tarifa)",
                    key="sim_tarifa_iny")
            else:
                tarifa_iny_s = 0.0

    # ── Cálculos del simulador ────────────────────────────────────────────────
    pr_dec_s     = pr_sim / 100.0
    hsp_ef_s     = hsp_sim * pr_dec_s
    consumo_fs_s = consumo_sim * fs_factor
    vdc_s        = tension_dc(consumo_fs_s)
    pot_inst_s   = consumo_fs_s / hsp_ef_s if hsp_ef_s > 0 else 0
    n_pan_s      = num_paneles(pot_inst_s, pot_panel_s)
    pot_real_s   = n_pan_s * pot_panel_s
    gen_dia_s    = (pot_real_s / 1000) * hsp_sim * pr_dec_s
    gen_anual_s  = gen_dia_s * 365

    # Baterías (sólo OFF-GRID e HÍBRIDO)
    if tipo_sistema == "ON-GRID":
        bats_s      = {"num": 0, "ah_final": 0, "energia_kwh": 0}
        n_bats_s    = 0
        autonomia_s = 0.0
    else:
        bats_s      = calcular_baterias(consumo_fs_s, vdc_s, dod_s/100, bat_cap_s)
        n_bats_s    = bats_s["num"]
        autonomia_s = bats_s["energia_kwh"] * (dod_s/100) / (consumo_fs_s/1000 / 24)                       if consumo_fs_s > 0 else 0.0
    ah_banco_s   = n_bats_s * bat_cap_s

    # Controlador MPPT (OFF-GRID) / strings (ON-GRID, HÍBRIDO)
    if tipo_sistema == "ON-GRID" or tipo_sistema == "HIBRIDO":
        vmpp_s    = voc_s * 0.82
        if v_mppt_max_s > 0 and vmpp_s > 0:
            serie_s = min(math.floor(v_mppt_max_s / vmpp_s),
                          math.floor(v_mppt_max_s * 1.15 / voc_s))
            serie_s = max(serie_s, math.ceil(v_mppt_min_s / vmpp_s))
        else:
            serie_s = max(1, round(vdc_s / (voc_s * 0.80))) if voc_s > 0 else 1
        par_s     = max(1, math.ceil(n_pan_s / serie_s))
        mppt_s    = "Inversor MPPT"
        corr_mppt_s = 0
    else:
        vmp_s       = voc_s * 0.80
        serie_s     = max(1, round(vdc_s / vmp_s)) if vmp_s > 0 else 1
        par_s       = math.ceil(n_pan_s / serie_s)
        corr_mppt_s = ah_banco_s * 0.30
        if corr_mppt_s <= 40:    mppt_s = "MPPT 40A"
        elif corr_mppt_s <= 60:  mppt_s = "MPPT 60A"
        elif corr_mppt_s <= 100: mppt_s = "MPPT 100A"
        else: mppt_s = f"MPPT {math.ceil(corr_mppt_s/50)*50}A"

    # Inversor
    if not cargas.empty:
        pot_inv_s = cargas.apply(
            lambda r: r["cantidad"]*r["potencia_w"]*(4 if int(r["es_motor"]) else 1), axis=1
        ).sum() * 1.30
    else:
        pot_inv_s = consumo_fs_s
    inv_kva_s = round(pot_inv_s / 1000, 2)

    # Financiero — diferente según sistema
    consumo_dia_kwh_s = consumo_sim / 1000
    if tipo_sistema == "OFF-GRID":
        # Ahorro = 100% consumo cubierto
        ahorro_mes_s   = consumo_dia_kwh_s * 30 * tarifa_s
        ingreso_iny_s  = 0.0
    else:
        # Autoconsumo + posible inyección
        autoconsumo_s  = min(gen_dia_s, consumo_dia_kwh_s)
        inyeccion_s    = max(0, gen_dia_s - consumo_dia_kwh_s)
        ahorro_mes_s   = autoconsumo_s * 30 * tarifa_s
        ingreso_iny_s  = inyeccion_s * 30 * tarifa_iny_s
    ahorro_anual_s = (ahorro_mes_s + ingreso_iny_s) * 12
    kwh_anual_s    = gen_anual_s
    pb_s  = payback(costo_s, ahorro_anual_s) if costo_s > 0 and ahorro_anual_s > 0 else 0
    vpn_s = vpn_calc(costo_s, ahorro_anual_s, tasa_s, int(anos_s)) if costo_s > 0 else 0
    tir_s = tir_calc(costo_s, ahorro_anual_s, int(anos_s))             if costo_s > 0 and ahorro_anual_s > 0 else 0
    co2_anual_s = kwh_anual_s * factor_co2 * 1000   # kg

    # ── Dashboard de resultados ───────────────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:1.5rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.3rem;font-weight:700;
     letter-spacing:2px;margin-bottom:1rem;'>
        <span style='color:{col_sis};'>⚡ RESULTADOS — {lbl_sis}</span>
        <span style='font-size:0.85rem;color:#8A9BBD;margin-left:1rem;'>
            HSP {hsp_sim}h × PR {pr_sim}% = {hsp_ef_s:.2f}h efectivas
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Fila 1 — métricas técnicas adaptadas al sistema
    if tipo_sistema == "ON-GRID":
        c1,c2,c3,c4,c5 = st.columns(5)
        metrics_tech = [
            (c1, str(n_pan_s),          "paneles",  f"{pot_panel_s}Wp",     "CAMPO FV"),
            (c2, f"{pot_real_s/1000:.2f}","kWp",    f"{serie_s}S×{par_s}P", "POTENCIA ARRAY"),
            (c3, f"{inv_kva_s}",         "kW",      "Inversor grid-tie",     "INVERSOR"),
            (c4, f"{gen_dia_s:.2f}",     "kWh/día", "Generación estimada",   "GENERACIÓN"),
            (c5, f"{pb_s:.1f}",          "años",    "Retorno inversión",     "PAYBACK"),
        ]
    elif tipo_sistema == "HIBRIDO":
        c1,c2,c3,c4,c5 = st.columns(5)
        metrics_tech = [
            (c1, str(n_pan_s),           "paneles",  f"{pot_panel_s}Wp",       "CAMPO FV"),
            (c2, f"{pot_real_s/1000:.2f}","kWp",     f"{serie_s}S×{par_s}P",   "POTENCIA ARRAY"),
            (c3, str(n_bats_s),          "baterías", f"{bat_cap_s}Ah@{vdc_s}V","BANCO BAT."),
            (c4, f"{inv_kva_s}",         "kW",       "Inversor híbrido",        "INVERSOR HIB."),
            (c5, f"{autonomia_s:.1f}",   "horas",    "Autonomía batería",       "AUTONOMÍA"),
        ]
    else:
        c1,c2,c3,c4,c5 = st.columns(5)
        metrics_tech = [
            (c1, str(n_pan_s),           "paneles",   f"{pot_panel_s}Wp",       "CAMPO FV"),
            (c2, f"{pot_real_s/1000:.2f}","kWp",      f"{serie_s}S×{par_s}P",   "POTENCIA ARRAY"),
            (c3, str(n_bats_s),          "baterías",  f"{bat_cap_s}Ah@{vdc_s}V","BANCO BATERÍAS"),
            (c4, mppt_s.replace("MPPT ",""), "A",     "Controlador MPPT",        "MPPT"),
            (c5, str(inv_kva_s),         "kVA",       "Inversor DC/AC",          "INVERSOR"),
        ]

    for col, val, unit, sub, label in metrics_tech:
        col.markdown(f"""
        <div style='background:#1A2235;border:1px solid {col_sis}44;border-radius:10px;
         padding:1rem;text-align:center;'>
            <div style='font-family:Share Tech Mono,monospace;font-size:1.6rem;
             color:{col_sis};font-weight:700;line-height:1;'>{val}</div>
            <div style='font-size:0.72rem;color:#FFD54F;margin-top:0.2rem;'>{unit}</div>
            <div style='font-size:0.7rem;color:#8A9BBD;margin-top:0.3rem;
             text-transform:uppercase;letter-spacing:1px;'>{label}</div>
            <div style='font-size:0.7rem;color:#2A3A55;margin-top:0.2rem;'>{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Fila 2 — Energético + Financiero + Ambiental
    col_en, col_fi, col_am = st.columns(3)
    with col_en:
        # Filas específicas por sistema
        if tipo_sistema == "ON-GRID":
            autoconsumo_show = min(gen_dia_s, consumo_sim / 1000)
            inyeccion_show   = max(0, gen_dia_s - consumo_sim / 1000)
            cobertura_pct    = autoconsumo_show / (consumo_sim / 1000) * 100 \
                               if consumo_sim > 0 else 0
            rows_extra = f"""
                <tr><td style='color:#8A9BBD;'>Autoconsumo/día</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>{autoconsumo_show:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Inyección red/día</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>{inyeccion_show:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Cobertura solar</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{cobertura_pct:.0f}%</td></tr>"""
        elif tipo_sistema == "HIBRIDO":
            autoconsumo_show = min(gen_dia_s, consumo_sim / 1000)
            inyeccion_show   = max(0, gen_dia_s - consumo_sim / 1000)
            cobertura_pct    = autoconsumo_show / (consumo_sim / 1000) * 100 \
                               if consumo_sim > 0 else 0
            rows_extra = f"""
                <tr><td style='color:#8A9BBD;'>Autoconsumo/día</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>{autoconsumo_show:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Inyección red/día</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>{inyeccion_show:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Cobertura solar</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{cobertura_pct:.0f}%</td></tr>
                <tr><td style='color:#8A9BBD;'>Banco baterías</td>
                    <td style='color:#A78BFA;text-align:right;font-family:Share Tech Mono,monospace;'>{bats_s['energia_kwh']:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Autonomía batería</td>
                    <td style='color:#A78BFA;text-align:right;font-family:Share Tech Mono,monospace;'>{autonomia_s:.1f} h</td></tr>"""
        else:
            # OFF-GRID: cubre el 100% del consumo, sin inyección a red
            rows_extra = f"""
                <tr><td style='color:#8A9BBD;'>Tensión DC</td>
                    <td style='color:#00BCD4;text-align:right;font-family:Share Tech Mono,monospace;'>{vdc_s} V</td></tr>
                <tr><td style='color:#8A9BBD;'>Energía banco bat.</td>
                    <td style='color:#A78BFA;text-align:right;font-family:Share Tech Mono,monospace;'>{bats_s['energia_kwh']:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Cobertura solar</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>100% (aislado)</td></tr>"""

        st.markdown(f"""
        <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;padding:1.2rem;'>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
             color:{col_sis};margin-bottom:0.8rem;letter-spacing:1px;'>⚡ ENERGÉTICO</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>Consumo base</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{consumo_sim:,.0f} Wh/día</td></tr>
                <tr><td style='color:#8A9BBD;'>Con FS ({fs_label})</td>
                    <td style='color:#FFB300;text-align:right;font-family:Share Tech Mono,monospace;'>{consumo_fs_s:,.0f} Wh/día</td></tr>
                <tr><td style='color:#8A9BBD;'>HSP bruta</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{hsp_sim} h/día</td></tr>
                <tr><td style='color:#8A9BBD;'>PR aplicado</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>{pr_sim}%</td></tr>
                <tr><td style='color:#8A9BBD;'>HSP efectiva</td>
                    <td style='color:#FFB300;text-align:right;font-family:Share Tech Mono,monospace;'>{hsp_ef_s:.2f} h/día</td></tr>
                {rows_extra}
                <tr><td style='color:#8A9BBD;'>Generación estimada</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{gen_dia_s:.2f} kWh/día</td></tr>
                <tr><td style='color:#8A9BBD;'>Generación anual</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{gen_anual_s:,.0f} kWh/año</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

    with col_fi:
        vpn_color  = "#00E676" if vpn_s > 0 else "#FF5252"
        if tipo_sistema in ("ON-GRID", "HIBRIDO"):
            autoconsumo_mes = min(gen_dia_s, consumo_sim/1000) * 30 * tarifa_s
            inyeccion_mes   = max(0, gen_dia_s - consumo_sim/1000) * 30 * tarifa_iny_s
            row_iny = f"""
                <tr><td style='color:#8A9BBD;'>Ahorro autoconsumo/mes</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>$ {autoconsumo_mes:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Ingreso inyección/mes</td>
                    <td style='color:#FF6B35;text-align:right;font-family:Share Tech Mono,monospace;'>$ {inyeccion_mes:,.0f}</td></tr>"""
        else:
            row_iny = ""
        st.markdown(f"""
        <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;padding:1.2rem;'>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
             color:{col_sis};margin-bottom:0.8rem;letter-spacing:1px;'>💰 FINANCIERO</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>Costo sistema</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>$ {costo_s:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Tarifa kWh</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>$ {tarifa_s:,.0f}</td></tr>
                {"<tr><td style='color:#8A9BBD;'>Precio inyección kWh</td><td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>$ " + f"{tarifa_iny_s:,.0f}" + "</td></tr>" if tipo_sistema in ("ON-GRID","HIBRIDO") else ""}
                {row_iny}
                <tr><td style='color:#8A9BBD;'>{"Ahorro mensual" if tipo_sistema=="OFF-GRID" else "Beneficio total/mes"}</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>$ {ahorro_mes_s + (ingreso_iny_s if tipo_sistema in ("ON-GRID","HIBRIDO") else 0):,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Beneficio anual total</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>$ {ahorro_anual_s:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Payback</td>
                    <td style='color:#FFB300;text-align:right;font-family:Share Tech Mono,monospace;'>{pb_s:.1f} años</td></tr>
                <tr><td style='color:#8A9BBD;'>TIR ({int(anos_s)} años)</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{tir_s:.1f}%</td></tr>
                <tr><td style='color:#8A9BBD;'>VPN ({int(anos_s)} años)</td>
                    <td style='color:{vpn_color};text-align:right;font-family:Share Tech Mono,monospace;'>$ {vpn_s:,.0f}</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

    with col_am:
        st.markdown(f"""
        <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;padding:1.2rem;'>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
             color:{col_sis};margin-bottom:0.8rem;letter-spacing:1px;'>🌱 AMBIENTAL</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>CO₂ evitado/año</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s:,.0f} kg</td></tr>
                <tr><td style='color:#8A9BBD;'>CO₂ evitado/25 años</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s*25/1000:.1f} ton</td></tr>
                <tr><td style='color:#8A9BBD;'>Árboles equivalentes</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s/21:.0f} árboles/año</td></tr>
                <tr><td style='color:#8A9BBD;'>Generación anual</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{gen_anual_s:,.0f} kWh/año</td></tr>
                <tr><td style='color:#8A9BBD;'>Factor CO₂ usado</td>
                    <td style='color:#8A9BBD;text-align:right;font-family:Share Tech Mono,monospace;'>{factor_co2:.3f} kg/kWh</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

    # ── Guardar simulación ────────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:1.5rem 0;'>", unsafe_allow_html=True)
    col_gs1, col_gs2, col_gs3 = st.columns([2,1,1])
    with col_gs1:
        sim_nombre = st.text_input(
            "Nombre de esta simulación",
            placeholder="Ej: Escenario base, Ampliación fase 2...",
            value=f"{tipo_sistema} — {datetime.now().strftime('%d/%m %H:%M')}",
            key="sim_nombre")
    with col_gs2:
        if st.button("💾 Guardar Simulación", use_container_width=True):
            conn = get_conn()
            nombre_final = sim_nombre.strip() or                            f"{tipo_sistema} {datetime.now().strftime('%d/%m %H:%M')}"
            conn.execute("""
                INSERT INTO simulaciones(proyecto_id,nombre,consumo_wh,consumo_fs_wh,hsp,vdc,
                    num_paneles,pot_panel_wp,pot_instalada_wp,num_baterias,bat_cap_ah,
                    ah_total,energia_kwh,corriente_mppt,mppt_modelo,inversor_kva,
                    serie,paralelo,irradiacion_mes,municipio,tarifa_kwh,
                    ahorro_mensual,co2_kg_anual,tir,vpn,payback_anos,costo_sistema)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (proyecto_id, nombre_final,
                  consumo_sim, consumo_fs_s, hsp_sim, vdc_s,
                  n_pan_s, pot_panel_s, pot_inst_s, n_bats_s, bat_cap_s,
                  bats_s["ah_final"], bats_s["energia_kwh"], corr_mppt_s, mppt_s, inv_kva_s,
                  serie_s, par_s, irrad_sim, municipio_s, tarifa_s,
                  ahorro_mes_s, co2_anual_s, tir_s, vpn_s, pb_s, costo_s))
            conn.commit(); conn.close()
            st.success(f"Simulación {tipo_sistema} guardada ✓")
            st.rerun()
    with col_gs3:
        sim_dict = {
            "tipo_sistema": tipo_sistema,
            "consumo_wh": consumo_sim, "consumo_fs_wh": consumo_fs_s,
            "hsp": hsp_sim, "pr": pr_sim, "hsp_ef": hsp_ef_s,
            "vdc": vdc_s, "num_paneles": n_pan_s, "pot_panel_wp": pot_panel_s,
            "pot_instalada_wp": pot_inst_s, "num_baterias": n_bats_s,
            "bat_cap_ah": bat_cap_s, "ah_total": bats_s["ah_final"],
            "energia_kwh": bats_s["energia_kwh"], "corriente_mppt": corr_mppt_s,
            "mppt_modelo": mppt_s, "inversor_kva": inv_kva_s,
            "municipio": municipio_s, "tarifa_kwh": tarifa_s,
            "ahorro_mensual": ahorro_mes_s, "co2_kg_anual": co2_anual_s,
            "tir": tir_s, "vpn": vpn_s, "payback_anos": pb_s, "costo_sistema": costo_s,
            "modelo_panel": modelo_s, "voc": voc_s, "isc": isc_s,
            "gen_dia_kwh": gen_dia_s, "gen_anual_kwh": gen_anual_s,
            "autonomia_h": autonomia_s,
        }
        pdf_bytes = generar_informe_pdf(sim_dict, p[1] if p else "Proyecto")
        proy_nom  = (p[1] if p else "Proyecto").replace(" ","_")
        st.download_button(
            "⬇ Descargar Informe PDF",
            data=pdf_bytes,
            file_name=f"Sim_{tipo_sistema}_{proy_nom}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True, key="dl_sim_pdf")

    # ── Historial de simulaciones ─────────────────────────────────────────────
    conn = get_conn()
    sims_hist = pd.read_sql(
        "SELECT id,nombre,consumo_fs_wh,vdc,num_paneles,num_baterias,payback_anos,tir,vpn,generado "
        "FROM simulaciones WHERE proyecto_id=? ORDER BY id DESC LIMIT 8",
        conn, params=(proyecto_id,))
    conn.close()

    if not sims_hist.empty:
        st.markdown("<hr style='border-color:#2A3A55;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:600;
         color:#FFB300;letter-spacing:1px;margin-bottom:0.5rem;'>📋 HISTORIAL DE SIMULACIONES</div>
        """, unsafe_allow_html=True)
        sims_hist.columns = ["ID","Nombre","Consumo(Wh)","VDC","Paneles","Baterías",
                              "Payback(años)","TIR(%)","VPN($)","Fecha"]
        st.dataframe(sims_hist.set_index("ID"), use_container_width=True)

        # Eliminar
        with st.expander("🗑 Eliminar simulación"):
            del_sim = st.selectbox("Simulación a eliminar",
                                    [f"{r['ID']} — {r['Nombre']}" for _, r in sims_hist.iterrows()],
                                    key="del_sim_sel")
            if st.button("Confirmar eliminación", key="del_sim_btn"):
                sid = int(del_sim.split(" — ")[0])
                conn = get_conn()
                conn.execute("DELETE FROM simulaciones WHERE id=? AND proyecto_id=?",
                              (sid, proyecto_id))
                conn.commit()
                conn.close()
                st.success("Eliminada ✓"); st.rerun()
