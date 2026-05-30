"""
modulo_simulador.py — Simulador de Dimensionamiento Fotovoltaico
SolarCalc Pro · Módulo externo
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

    SOL   = colors.HexColor("#FFB300")
    DARK  = colors.HexColor("#0A0E1A")
    CARD  = colors.HexColor("#1A2235")
    TEXT  = colors.HexColor("#E8EDF5")
    TEXT2 = colors.HexColor("#8A9BBD")
    GREEN = colors.HexColor("#00E676")
    CYAN  = colors.HexColor("#00BCD4")
    MONO  = colors.HexColor("#FFD54F")
    BRD   = colors.HexColor("#2A3A55")

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

    story = []

    # Portada
    story.append(Paragraph("☀  SOLARCALC PRO", h1))
    story.append(Paragraph("INFORME DE SIMULACIÓN Y DIMENSIONAMIENTO FOTOVOLTAICO", h1))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=SOL))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Proyecto: <b>{proyecto_nombre}</b>  |  "
        f"Municipio: {sim.get('municipio','—')}  |  "
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub))
    story.append(Spacer(1, 0.5*cm))

    # 1. Datos del consumo
    story.append(sec_table("1. ANÁLISIS DE CONSUMO ENERGÉTICO", [
        ("Consumo diario base (Wh/día)",         f"{sim['consumo_wh']:,.0f} Wh"),
        ("Factor de seguridad (30%)",             "× 1.30"),
        ("Consumo diario con FS (Wh/día)",        f"{sim['consumo_fs_wh']:,.0f} Wh"),
        ("Consumo mensual estimado (kWh/mes)",    f"{sim['consumo_fs_wh']*30/1000:,.1f} kWh"),
        ("Consumo anual estimado (kWh/año)",      f"{sim['consumo_fs_wh']*365/1000:,.0f} kWh"),
        ("Hora Solar Pico (HSP)",                 f"{sim['hsp']} h/día"),
        ("Ubicación analizada",                   sim.get('municipio','—')),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 2. Tensión DC
    story.append(sec_table("2. TENSIÓN DC DEL SISTEMA", [
        ("Tensión DC seleccionada",               f"{sim['vdc']} V DC"),
        ("Criterio",                              "< 2kWh→12V | 2-4kWh→24V | ≥4kWh→48V"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 3. Campo fotovoltaico
    vmp = round(sim.get('voc', 49.9) * 0.80, 1)
    serie_r  = max(1, round(sim['vdc'] / vmp)) if vmp > 0 else 1
    par_r    = math.ceil(sim['num_paneles'] / serie_r)
    story.append(sec_table("3. CAMPO FOTOVOLTAICO", [
        ("Panel solar (modelo)",                  sim.get('modelo_panel','—')),
        ("Potencia por panel (Wp)",               f"{sim['pot_panel_wp']:,.0f} Wp"),
        ("Potencia instalada mínima (Wp)",        f"{sim['pot_instalada_wp']:,.0f} Wp"),
        ("Número de paneles requeridos",          f"{sim['num_paneles']} paneles"),
        ("Configuración (Serie × Paralelo)",      f"{serie_r}S × {par_r}P"),
        ("Potencia real del array (kWp)",         f"{sim['num_paneles']*sim['pot_panel_wp']/1000:.2f} kWp"),
        ("Tensión total array Voc (V)",           f"{sim.get('voc',49.9)*serie_r:.1f} V"),
        ("Corriente total array Isc (A)",         f"{sim.get('isc',14.0)*par_r:.1f} A"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 4. Baterías
    story.append(sec_table("4. BANCO DE BATERÍAS LITIO", [
        ("Capacidad Ah requeridos (bruto)",       f"{sim['ah_total']/0.85*0.80:,.1f} Ah"),
        ("DOD aplicado",                          "80%"),
        ("Pérdidas adicionales",                  "15% (inversor + cableado + controlador)"),
        ("Ah finales requeridos",                 f"{sim['ah_total']:,.1f} Ah"),
        ("Capacidad por batería",                 f"{sim['bat_cap_ah']:.0f} Ah"),
        ("Número de baterías",                    f"{sim['num_baterias']} unidades"),
        ("Tensión del banco",                     f"{sim['vdc']} V DC"),
        ("Energía total almacenada (kWh)",        f"{sim['energia_kwh']:.2f} kWh"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 5. Controlador
    story.append(sec_table("5. CONTROLADOR DE CARGA MPPT", [
        ("Corriente de carga (Ah×0.30)",          f"{sim['corriente_mppt']:.0f} A"),
        ("Controlador recomendado",               sim['mppt_modelo']),
        ("Tensión del sistema",                   f"{sim['vdc']} V"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # 6. Inversor
    story.append(sec_table("6. INVERSOR DC/AC", [
        ("Potencia inversor recomendada (kVA)",   f"{sim['inversor_kva']:.2f} kVA"),
        ("Tensión entrada (DC)",                  f"{sim['vdc']} V"),
        ("Tensión salida (AC)",                   "220 V / 60 Hz"),
    ]))
    story.append(PageBreak())

    # 7. Análisis financiero
    story.append(Paragraph("7. ANÁLISIS FINANCIERO Y AMBIENTAL", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRD, spaceAfter=6))

    fin_rows = [
        ("Costo estimado del sistema ($)",        f"$ {sim.get('costo_sistema',0):,.0f}"),
        ("Tarifa energía actual ($/kWh)",         f"$ {sim.get('tarifa_kwh',650):,.0f}"),
        ("Ahorro mensual estimado ($)",           f"$ {sim.get('ahorro_mensual',0):,.0f}"),
        ("Ahorro anual estimado ($)",             f"$ {sim.get('ahorro_mensual',0)*12:,.0f}"),
        ("Periodo de retorno simple (años)",      f"{sim.get('payback_anos',0):.1f} años"),
        ("Tasa Interna de Retorno — TIR (%)",     f"{sim.get('tir',0):.1f}%"),
        ("Valor Presente Neto a 25 años ($)",     f"$ {sim.get('vpn',0):,.0f}"),
        ("CO₂ evitado (kg/año)",                  f"{sim.get('co2_kg_anual',0):,.0f} kg"),
        ("CO₂ evitado en 25 años (ton)",          f"{sim.get('co2_kg_anual',0)*25/1000:.1f} ton"),
    ]
    story.append(sec_table("INDICADORES FINANCIEROS Y AMBIENTALES", fin_rows))
    story.append(Spacer(1, 0.6*cm))

    # Notas
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRD))
    story.append(Paragraph(
        "NOTAS: Los valores financieros son estimados con base en tarifas actuales y pueden variar. "
        "El dimensionamiento cumple con los criterios del RETIE (Resolución 40117 de 2014 y sus modificaciones). "
        "Se recomienda verificar con un ingeniero electricista certificado antes de la instalación.",
        ParagraphStyle("nota", fontName="Helvetica", fontSize=7.5, textColor=TEXT2,
                        spaceBefore=6, leading=11)))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"<font color='#2A3A55'>SolarCalc Pro · Simulación generada el "
        f"{datetime.now().strftime('%d/%m/%Y a las %H:%M')} · Plano de referencia</font>",
        ParagraphStyle("ft", fontName="Helvetica", fontSize=7, alignment=TA_CENTER, spaceBefore=4)))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL DEL MÓDULO
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_simulador(proyecto_id: int, ss: dict):
    """Renderiza el módulo Simulador completo dentro del app principal."""
    init_modulos_db()

    conn = get_conn()
    p = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    pan = conn.execute("SELECT * FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
                       (proyecto_id,)).fetchone()
    cargas = pd.read_sql("SELECT cantidad,potencia_w,horas_dia,es_motor FROM cargas WHERE proyecto_id=?",
                          conn, params=(proyecto_id,))
    sims = pd.read_sql("SELECT * FROM simulaciones WHERE proyecto_id=? ORDER BY id DESC LIMIT 10",
                        conn, params=(proyecto_id,))
    conn.close()

    # CSS local
    st.markdown("""
    <style>
    .sim-header{background:linear-gradient(135deg,#0A0E1A,#1A2235);border:1px solid #2A3A55;
     border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.5rem;}
    .sim-header h2{font-family:Rajdhani,sans-serif;font-size:1.6rem;font-weight:700;
     color:#FFB300;margin:0;letter-spacing:2px;}
    .sim-header p{color:#8A9BBD;font-size:0.8rem;margin:0.2rem 0 0;letter-spacing:2px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='sim-header'>
        <h2>🔬 SIMULADOR DE DIMENSIONAMIENTO FOTOVOLTAICO</h2>
        <p>ANÁLISIS TÉCNICO · FINANCIERO · AMBIENTAL</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Consumo base ──────────────────────────────────────────────────────────
    consumo_inv = (cargas["cantidad"]*cargas["potencia_w"]*cargas["horas_dia"]).sum() if not cargas.empty else 0.0
    consumo_rec = ss.get("consumo_recibo_wh", 0.0)
    consumo_base_auto = max(consumo_inv, consumo_rec) if consumo_rec > 0 else consumo_inv

    # Leer valores de tabs 6 y 7 si están disponibles
    n_pan_calc   = ss.get("calc_num_paneles")
    pot_pan_calc = ss.get("calc_pot_panel_wp",  pan[3] if pan else 550)
    hsp_calc     = ss.get("calc_hsp",           p[4] if p and p[4] else 4.2)
    vdc_calc     = ss.get("calc_vdc",           p[3] if p and p[3] else 48)
    cons_fs_calc = ss.get("calc_consumo_fs_wh", consumo_base_auto * 1.30)
    n_bat_calc   = ss.get("calc_num_baterias")
    bat_cap_calc = ss.get("calc_bat_cap_ah",    100)

    st.markdown("""
    <div style='background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.25);
     border-radius:8px;padding:0.7rem 1rem;font-size:0.82rem;color:#8A9BBD;margin-bottom:1rem;'>
        ℹ Los valores de los Módulos 6 (Potencia) y 7 (Baterías) se cargan automáticamente.
        Puedes ajustarlos libremente para simular distintos escenarios.
    </div>
    """, unsafe_allow_html=True)

    # ── Formulario de simulación ──────────────────────────────────────────────
    with st.expander("⚙ PARÁMETROS DE SIMULACIÓN", expanded=True):
        cola, colb, colc = st.columns(3)
        with cola:
            st.markdown("**⚡ Energético**")
            # Clamp defaults to valid ranges before passing to widgets
            consumo_default = float(consumo_base_auto) if consumo_base_auto > 0 else 3000.0
            consumo_default = max(100.0, min(consumo_default, 500000.0))

            hsp_default = float(hsp_calc) if hsp_calc else 4.2
            hsp_default = max(0.5, min(hsp_default, 12.0))

            irrad_default = float(hsp_default * 30)
            irrad_default = max(10.0, min(irrad_default, 300.0))

            consumo_sim = st.number_input("Consumo diario base (Wh/día)", 100.0, 500000.0,
                                          consumo_default, 100.0, key="sim_consumo")
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
            voc_default = max(10.0, min(float(pan[4]) if pan else 49.9, 100.0))
            isc_default = max(1.0,  min(float(pan[5]) if pan else 14.0,  30.0))
            bc_default  = max(50,   min(int(bat_cap_calc), 500))

            pot_panel_s = st.number_input("Potencia panel (Wp)", 50, 1000,
                                           pp_default, 50, key="sim_pp")
            voc_s       = st.number_input("Voc panel (V)", 10.0, 100.0,
                                           voc_default, 0.1, key="sim_voc")
            isc_s       = st.number_input("Isc panel (A)", 1.0, 30.0,
                                           isc_default, 0.1, key="sim_isc")
            modelo_s    = st.text_input("Modelo panel",
                                         value=pan[2] if pan else "Panel 550Wp", key="sim_mod")
            dod_s       = st.slider("DOD baterías (%)", 50, 100, 80, key="sim_dod")
            bat_cap_s   = st.number_input("Capacidad batería (Ah)", 50, 500,
                                           bc_default, 50, key="sim_bc")

        with colc:
            st.markdown("**💰 Financiero**")
            costo_default = max(0.0, min(float(ss.get("presup_total", 0)), 999999999.0))
            costo_s     = st.number_input("Costo estimado sistema ($)", 0.0, 999999999.0,
                                           costo_default, 100000.0, key="sim_costo")
            tarifa_s    = st.number_input("Tarifa energía ($/kWh)", 0.0, 5000.0,
                                           700.0, 10.0, key="sim_tarifa",
                                           help="Precio actual del kWh en su factura")
            tasa_s      = st.number_input("Tasa de descuento (%/año)", 0.0, 30.0,
                                           8.0, 0.5, key="sim_tasa") / 100
            anos_s      = st.number_input("Horizonte de evaluación (años)", 5, 30, 25,
                                           key="sim_anos")
            factor_co2  = st.number_input("Factor emisión CO₂ (kg/kWh)", 0.05, 1.0,
                                           0.136, 0.001, key="sim_co2",
                                           help="Colombia: ~0.136 kg CO₂/kWh (UPME 2023)")

    # ── Cálculos del simulador ────────────────────────────────────────────────
    consumo_fs_s   = consumo_sim * 1.30
    vdc_s          = tension_dc(consumo_fs_s)
    pot_inst_s     = consumo_fs_s / hsp_sim if hsp_sim > 0 else 0
    n_pan_s        = num_paneles(pot_inst_s, pot_panel_s)
    pot_real_s     = n_pan_s * pot_panel_s
    bats_s         = calcular_baterias(consumo_fs_s, vdc_s, dod_s/100, bat_cap_s)
    ah_banco_s     = bats_s["num"] * bat_cap_s
    corr_mppt_s    = ah_banco_s * 0.30

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

    # Financiero
    kwh_anual_s    = consumo_fs_s * 365 / 1000
    ahorro_mes_s   = consumo_fs_s * 30 / 1000 * tarifa_s
    ahorro_anual_s = ahorro_mes_s * 12
    pb_s           = payback(costo_s, ahorro_anual_s) if costo_s > 0 and ahorro_anual_s > 0 else 0
    vpn_s          = vpn_calc(costo_s, ahorro_anual_s, tasa_s, int(anos_s)) if costo_s > 0 else 0
    tir_s          = tir_calc(costo_s, ahorro_anual_s, int(anos_s)) if costo_s > 0 and ahorro_anual_s > 0 else 0
    co2_anual_s    = kwh_anual_s * factor_co2 * 1000   # kg

    # Serie/paralelo
    vmp_s    = voc_s * 0.80
    serie_s  = max(1, round(vdc_s / vmp_s)) if vmp_s > 0 else 1
    par_s    = math.ceil(n_pan_s / serie_s)

    # ── Dashboard de resultados ───────────────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:1.5rem 0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.3rem;font-weight:700;
     color:#FFB300;letter-spacing:2px;margin-bottom:1rem;'>⚡ RESULTADOS DE LA SIMULACIÓN</div>
    """, unsafe_allow_html=True)

    # Fila 1 — 5 métricas técnicas
    c1,c2,c3,c4,c5 = st.columns(5)
    metrics_tech = [
        (c1, str(n_pan_s), "paneles", f"{pot_panel_s}Wp", "CAMPO FV"),
        (c2, f"{pot_real_s/1000:.2f}", "kWp", f"{serie_s}S×{par_s}P", "POTENCIA ARRAY"),
        (c3, str(bats_s["num"]), "baterías", f"{bat_cap_s}Ah@{vdc_s}V", "BANCO BATERÍAS"),
        (c4, mppt_s.replace("MPPT ",""), "A", "Controlador MPPT", "MPPT"),
        (c5, str(inv_kva_s), "kVA", "Inversor DC/AC", "INVERSOR"),
    ]
    for col, val, unit, sub, label in metrics_tech:
        col.markdown(f"""
        <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
         padding:1rem;text-align:center;'>
            <div style='font-family:Share Tech Mono,monospace;font-size:1.6rem;
             color:#FFB300;font-weight:700;line-height:1;'>{val}</div>
            <div style='font-size:0.72rem;color:#FFD54F;margin-top:0.2rem;'>{unit}</div>
            <div style='font-size:0.7rem;color:#8A9BBD;margin-top:0.3rem;
             text-transform:uppercase;letter-spacing:1px;'>{label}</div>
            <div style='font-size:0.7rem;color:#2A3A55;margin-top:0.2rem;'>{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Fila 2 — Energético + Financiero + Ambiental
    col_en, col_fi, col_am = st.columns(3)
    with col_en:
        st.markdown(f"""
        <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;padding:1.2rem;'>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
             color:#FFB300;margin-bottom:0.8rem;letter-spacing:1px;'>⚡ ENERGÉTICO</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>Consumo base</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{consumo_sim:,.0f} Wh/día</td></tr>
                <tr><td style='color:#8A9BBD;'>Con FS 30%</td>
                    <td style='color:#FFB300;text-align:right;font-family:Share Tech Mono,monospace;'>{consumo_fs_s:,.0f} Wh/día</td></tr>
                <tr><td style='color:#8A9BBD;'>HSP</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{hsp_sim} h/día</td></tr>
                <tr><td style='color:#8A9BBD;'>Tensión DC</td>
                    <td style='color:#00BCD4;text-align:right;font-family:Share Tech Mono,monospace;'>{vdc_s} V</td></tr>
                <tr><td style='color:#8A9BBD;'>Energía almacenada</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{bats_s['energia_kwh']:.2f} kWh</td></tr>
                <tr><td style='color:#8A9BBD;'>Generación anual</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{kwh_anual_s:,.0f} kWh/año</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

    with col_fi:
        vpn_color = "#00E676" if vpn_s > 0 else "#FF5252"
        st.markdown(f"""
        <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;padding:1.2rem;'>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
             color:#FFB300;margin-bottom:0.8rem;letter-spacing:1px;'>💰 FINANCIERO</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>Costo sistema</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>$ {costo_s:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Tarifa kWh</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>$ {tarifa_s:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Ahorro mensual</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>$ {ahorro_mes_s:,.0f}</td></tr>
                <tr><td style='color:#8A9BBD;'>Ahorro anual</td>
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
             color:#FFB300;margin-bottom:0.8rem;letter-spacing:1px;'>🌱 AMBIENTAL</div>
            <table style='width:100%;font-size:0.8rem;'>
                <tr><td style='color:#8A9BBD;'>CO₂ evitado/año</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s:,.0f} kg</td></tr>
                <tr><td style='color:#8A9BBD;'>CO₂ evitado/25 años</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s*25/1000:.1f} ton</td></tr>
                <tr><td style='color:#8A9BBD;'>Árboles equivalentes</td>
                    <td style='color:#00E676;text-align:right;font-family:Share Tech Mono,monospace;'>{co2_anual_s/21:.0f} árboles/año</td></tr>
                <tr><td style='color:#8A9BBD;'>Consumo anual red</td>
                    <td style='color:#FFD54F;text-align:right;font-family:Share Tech Mono,monospace;'>{kwh_anual_s:,.0f} kWh/año</td></tr>
                <tr><td style='color:#8A9BBD;'>Factor CO₂ usado</td>
                    <td style='color:#8A9BBD;text-align:right;font-family:Share Tech Mono,monospace;'>{factor_co2:.3f} kg/kWh</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

    # ── Guardar simulación ────────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:1.5rem 0;'>", unsafe_allow_html=True)
    col_gs1, col_gs2, col_gs3 = st.columns([2,1,1])
    with col_gs1:
        sim_nombre = st.text_input("Nombre de esta simulación",
                                    placeholder="Ej: Escenario base, Ampliación fase 2...",
                                    key="sim_nombre")
    with col_gs2:
        if st.button("💾 Guardar Simulación", use_container_width=True):
            conn = get_conn()
            conn.execute("""
                INSERT INTO simulaciones(proyecto_id,nombre,consumo_wh,consumo_fs_wh,hsp,vdc,
                    num_paneles,pot_panel_wp,pot_instalada_wp,num_baterias,bat_cap_ah,
                    ah_total,energia_kwh,corriente_mppt,mppt_modelo,inversor_kva,
                    serie,paralelo,irradiacion_mes,municipio,tarifa_kwh,
                    ahorro_mensual,co2_kg_anual,tir,vpn,payback_anos,costo_sistema)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (proyecto_id, sim_nombre.strip() or f"Sim {datetime.now().strftime('%d/%m %H:%M')}",
                  consumo_sim, consumo_fs_s, hsp_sim, vdc_s,
                  n_pan_s, pot_panel_s, pot_inst_s, bats_s["num"], bat_cap_s,
                  bats_s["ah_final"], bats_s["energia_kwh"], corr_mppt_s, mppt_s, inv_kva_s,
                  serie_s, par_s, irrad_sim, municipio_s, tarifa_s,
                  ahorro_mes_s, co2_anual_s, tir_s, vpn_s, pb_s, costo_s))
            conn.commit()
            conn.close()
            st.success("Simulación guardada ✓")
            st.rerun()
    with col_gs3:
        # Generar PDF
        sim_dict = {
            "consumo_wh": consumo_sim, "consumo_fs_wh": consumo_fs_s, "hsp": hsp_sim,
            "vdc": vdc_s, "num_paneles": n_pan_s, "pot_panel_wp": pot_panel_s,
            "pot_instalada_wp": pot_inst_s, "num_baterias": bats_s["num"],
            "bat_cap_ah": bat_cap_s, "ah_total": bats_s["ah_final"],
            "energia_kwh": bats_s["energia_kwh"], "corriente_mppt": corr_mppt_s,
            "mppt_modelo": mppt_s, "inversor_kva": inv_kva_s,
            "municipio": municipio_s, "tarifa_kwh": tarifa_s,
            "ahorro_mensual": ahorro_mes_s, "co2_kg_anual": co2_anual_s,
            "tir": tir_s, "vpn": vpn_s, "payback_anos": pb_s, "costo_sistema": costo_s,
            "modelo_panel": modelo_s, "voc": voc_s, "isc": isc_s,
        }
        pdf_bytes = generar_informe_pdf(sim_dict, p[1] if p else "Proyecto")
        st.download_button("⬇ Descargar Informe PDF",
                           data=pdf_bytes,
                           file_name=f"Informe_Sim_{(p[1] if p else 'Proyecto').replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
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
