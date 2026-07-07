# ═══════════════════════════════════════════════════════════════════════════════
# modulo_cableado.py  —  Cálculo de cableado FV según RETIE / IEC 60364-7-712
# Metodología: 3 criterios simultáneos
#   1. Ampacidad  (con factores de temperatura y agrupamiento)
#   2. Caída de tensión  (DC y AC mono/trifásica)
#   3. El calibre final = máximo entre los dos criterios anteriores
# ═══════════════════════════════════════════════════════════════════════════════
import math
import io
import streamlit as st
from datetime import datetime
from collections import defaultdict

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Tablas de referencia ─────────────────────────────────────────────────────
# Calibres comerciales (mm²) ordenados
CALIBRES_MM2 = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]

# Ampacidad referencial (cobre, enterrado en tubo, 30°C) — orientativa
# Fuente: IEC 60364-5-52 / RETIE tabla orientativa
AMPACIDAD_CU = {
    1.5: 18, 2.5: 24, 4: 32, 6: 41, 10: 57, 16: 76,
    25: 101, 35: 125, 50: 151, 70: 192, 95: 232, 120: 269, 150: 306, 185: 348, 240: 409
}
AMPACIDAD_AL = {
    4: 24, 6: 32, 10: 44, 16: 60, 25: 79, 35: 98,
    50: 118, 70: 150, 95: 183, 120: 210, 150: 239, 185: 272, 240: 321
}

# Factores de corrección por temperatura (base 30°C, aislamiento XLPE/PVC)
FACTOR_TEMP = {
    25: 1.04, 30: 1.00, 35: 0.96, 40: 0.91, 45: 0.87, 50: 0.82, 55: 0.76, 60: 0.71
}

# Factores de corrección por agrupamiento (número de circuitos)
FACTOR_AGRUP = {1: 1.00, 2: 0.80, 3: 0.70, 4: 0.65, 5: 0.60, 6: 0.57, 7: 0.54, 8: 0.52, 9: 0.50}

# Conductividad (m/Ω·mm²)
GAMMA_CU = 56.0
GAMMA_AL = 35.0

# Límites de caída de tensión recomendados (RETIE / IEC 60364-7-712)
CDT_LIMITES = {
    "paneles_mppt":   2.0,   # Paneles → Controlador/MPPT
    "mppt_baterias":  1.0,   # MPPT/Controlador → Baterías
    "baterias_inv":   1.0,   # Baterías → Inversor
    "salida_ac":      3.0,   # Salida AC (circuitos de distribución)
    "total":          5.0,   # Total sistema
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def _calibre_superior(s_mm2: float) -> float:
    """Devuelve el calibre comercial inmediatamente superior a s_mm2."""
    for c in CALIBRES_MM2:
        if c >= s_mm2:
            return c
    return CALIBRES_MM2[-1]

def _ampacidad(cal: float, material: str) -> float:
    tabla = AMPACIDAD_CU if material == "Cobre" else AMPACIDAD_AL
    return tabla.get(cal, 0.0)

def _factor_temp(t: int) -> float:
    temps = sorted(FACTOR_TEMP.keys())
    for i, tv in enumerate(temps):
        if t <= tv:
            if i == 0: return FACTOR_TEMP[tv]
            # interpolación lineal
            t0, t1 = temps[i-1], temps[i]
            f0, f1 = FACTOR_TEMP[t0], FACTOR_TEMP[t1]
            return f0 + (f1-f0)*(t-t0)/(t1-t0)
    return FACTOR_TEMP[60]

def _factor_agrup(n: int) -> float:
    if n >= 9: return 0.50
    return FACTOR_AGRUP.get(n, 1.0)

def calcular_tramo(
    nombre: str,
    corriente_a: float,
    longitud_m: float,
    voltaje_v: float,
    tipo: str = "DC",          # "DC" | "AC_mono" | "AC_tri"
    material: str = "Cobre",
    cdt_max_pct: float = 2.0,
    factor_seg: float = 1.25,
    temp_amb: int = 35,
    n_agrup: int = 1,
    fp: float = 0.95,
) -> dict:
    """
    Calcula el calibre mínimo para un tramo según los 3 criterios:
      1. Ampacidad corregida   → sección mínima por corriente
      2. Caída de tensión      → sección mínima por caída
      Resultado = calibre comercial que satisface ambos
    """
    gamma = GAMMA_CU if material == "Cobre" else GAMMA_AL
    i_dis  = corriente_a * factor_seg           # corriente de diseño

    # ── 1. Sección por AMPACIDAD
    ft = _factor_temp(temp_amb)
    fa = _factor_agrup(n_agrup)
    factor_total = ft * fa

    # Necesitamos: ampacidad_tabla × ft × fa ≥ i_dis
    # → ampacidad_tabla ≥ i_dis / (ft × fa)
    i_tabla_min = i_dis / max(factor_total, 0.01)
    s_amp = None
    for cal in CALIBRES_MM2:
        amp_cal = _ampacidad(cal, material)
        if amp_cal >= i_tabla_min:
            s_amp = cal
            break
    if s_amp is None:
        s_amp = CALIBRES_MM2[-1]
    amp_real = _ampacidad(s_amp, material) * factor_total

    # ── 2. Sección por CAÍDA DE TENSIÓN
    dv_max = voltaje_v * (cdt_max_pct / 100)
    if tipo == "DC":
        s_cdt = (2 * longitud_m * corriente_a) / (gamma * dv_max)
    elif tipo == "AC_mono":
        s_cdt = (2 * longitud_m * corriente_a) / (gamma * dv_max)
    else:  # AC_tri
        s_cdt = (math.sqrt(3) * longitud_m * corriente_a) / (gamma * dv_max)
    s_cdt = max(s_cdt, 0.0)

    # ── 3. Calibre final = máximo de los dos criterios
    s_final = max(s_amp, _calibre_superior(s_cdt))
    cal_final = _calibre_superior(s_final)
    amp_final = _ampacidad(cal_final, material) * factor_total

    # Caída real con calibre final
    if tipo in ("DC", "AC_mono"):
        dv_real_v = (2 * longitud_m * corriente_a) / (gamma * cal_final)
    else:
        dv_real_v = (math.sqrt(3) * longitud_m * corriente_a) / (gamma * cal_final)
    dv_real_pct = (dv_real_v / voltaje_v) * 100

    return {
        "nombre":        nombre,
        "corriente_a":   corriente_a,
        "i_dis":         i_dis,
        "longitud_m":    longitud_m,
        "voltaje_v":     voltaje_v,
        "tipo":          tipo,
        "material":      material,
        "cdt_max_pct":   cdt_max_pct,
        "factor_seg":    factor_seg,
        "temp_amb":      temp_amb,
        "n_agrup":       n_agrup,
        "ft":            ft,
        "fa":            fa,
        "factor_total":  factor_total,
        "s_amp_mm2":     s_amp,
        "s_cdt_mm2":     _calibre_superior(s_cdt),
        "s_cdt_raw":     s_cdt,
        "cal_final_mm2": cal_final,
        "amp_final_a":   amp_final,
        "dv_real_v":     dv_real_v,
        "dv_real_pct":   dv_real_pct,
        "cumple_cdt":    dv_real_pct <= cdt_max_pct,
        "criterio_gov":  "Caída de tensión" if _calibre_superior(s_cdt) >= s_amp else "Ampacidad",
    }


def calcular_cableado_sistema(params: dict) -> list:
    """
    Calcula todos los tramos del sistema FV dado un dict de parámetros.
    Retorna lista de resultados por tramo.
    """
    vdc      = params["vdc"]
    p_inv_w  = params["pot_inv_w"]
    isc      = params["isc"]
    n_pan    = params["n_pan"]
    n_str    = params.get("n_strings", 1)
    mat      = params["material"]
    temp     = params["temp_amb"]
    n_agr    = params["n_agrup"]
    fp       = params.get("fp_ac", 0.95)
    v_ac     = params.get("v_ac", 220)
    trifasico= params.get("trifasico", False)
    tipo_ac  = "AC_tri" if trifasico else "AC_mono"

    tramos = []

    # ── TRAMO 1: Paneles → Controlador / MPPT
    i_str  = isc                          # corriente de un string
    L1     = params.get("L_pan_mppt", 15)
    t1 = calcular_tramo(
        "🔆 Paneles → Controlador/MPPT",
        i_str, L1, vdc, tipo="DC",
        material=mat, cdt_max_pct=CDT_LIMITES["paneles_mppt"],
        factor_seg=1.25, temp_amb=temp, n_agrup=n_agr,
    )
    tramos.append(t1)

    # Si hay más de 1 string en paralelo → cable de combinación (bus DC)
    if n_str > 1:
        i_bus = isc * n_str
        L_bus = params.get("L_bus_dc", 3)
        t_bus = calcular_tramo(
            f"⚡ Bus DC ({n_str} strings en paralelo)",
            i_bus, L_bus, vdc, tipo="DC",
            material=mat, cdt_max_pct=CDT_LIMITES["paneles_mppt"],
            factor_seg=1.25, temp_amb=temp, n_agrup=n_agr,
        )
        tramos.append(t_bus)

    # ── TRAMO 2: Controlador/MPPT → Baterías
    i_ctrl_bat = p_inv_w / vdc if vdc > 0 else 0
    L2 = params.get("L_mppt_bat", 2)
    t2 = calcular_tramo(
        "🔋 Controlador/MPPT → Baterías",
        i_ctrl_bat, L2, vdc, tipo="DC",
        material=mat, cdt_max_pct=CDT_LIMITES["mppt_baterias"],
        factor_seg=1.25, temp_amb=temp, n_agrup=n_agr,
    )
    tramos.append(t2)

    # ── TRAMO 3: Baterías → Inversor
    i_bat_inv = p_inv_w / vdc if vdc > 0 else 0
    L3 = params.get("L_bat_inv", 2)
    t3 = calcular_tramo(
        "⚡ Baterías → Inversor",
        i_bat_inv, L3, vdc, tipo="DC",
        material=mat, cdt_max_pct=CDT_LIMITES["baterias_inv"],
        factor_seg=1.25, temp_amb=temp, n_agrup=n_agr,
    )
    tramos.append(t3)

    # ── TRAMO 4: Salida AC (Inversor → Distribución)
    if trifasico:
        i_ac = p_inv_w / (math.sqrt(3) * v_ac * fp) if v_ac > 0 else 0
    else:
        i_ac = p_inv_w / (v_ac * fp) if v_ac > 0 else 0
    L4 = params.get("L_ac", 15)
    t4 = calcular_tramo(
        f"🔌 Salida AC ({'Trifásico' if trifasico else 'Monofásico'} {v_ac}V)",
        i_ac, L4, v_ac, tipo=tipo_ac,
        material=mat, cdt_max_pct=CDT_LIMITES["salida_ac"],
        factor_seg=1.0, temp_amb=temp, n_agrup=n_agr, fp=fp,
    )
    tramos.append(t4)

    return tramos


def _color_cdt(cumple: bool, pct: float, limite: float) -> str:
    if not cumple:       return "#FF5252"
    if pct > limite*0.8: return "#FFB300"
    return "#00E676"

def _criterio_badge(crit: str) -> str:
    if crit == "Caída de tensión":
        return "<span style='background:#1A3A55;color:#00BCD4;padding:2px 7px;border-radius:4px;font-size:0.72rem;'>ΔV</span>"
    return "<span style='background:#1A3520;color:#00E676;padding:2px 7px;border-radius:4px;font-size:0.72rem;'>AMP</span>"


def generar_pdf_cableado(tramos: list, params: dict,
                          proyecto_nombre: str = "—",
                          proyecto_municipio: str = "—") -> bytes:
    """Genera PDF técnico del dimensionamiento de cableado FV.
    Incluye: portada, tabla resumen, fichas por tramo, cuadro de materiales y nota normativa."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    # ── Paleta de colores ─────────────────────────────────────────────────────
    SOL   = colors.HexColor("#FFB300")
    DARK  = colors.HexColor("#0A0E1A")
    CARD  = colors.HexColor("#1A2235")
    CARD2 = colors.HexColor("#111A2E")
    TEXT  = colors.HexColor("#E8EDF5")
    TEXT2 = colors.HexColor("#8A9BBD")
    GREEN = colors.HexColor("#00E676")
    CYAN  = colors.HexColor("#00BCD4")
    MONO  = colors.HexColor("#FFD54F")
    RED   = colors.HexColor("#FF5252")
    WARN  = colors.HexColor("#FFB300")
    PURP  = colors.HexColor("#A78BFA")
    BORD  = colors.HexColor("#2A3A55")
    WHITE = colors.white

    # ── Estilos de párrafo ────────────────────────────────────────────────────
    titulo_st = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=16,
                                textColor=SOL, alignment=TA_CENTER, spaceAfter=4)
    sub_st    = ParagraphStyle("sub",    fontName="Helvetica",      fontSize=9,
                                textColor=TEXT2, alignment=TA_CENTER, spaceAfter=8)
    sec_st    = ParagraphStyle("sec",    fontName="Helvetica-Bold", fontSize=11,
                                textColor=SOL, spaceBefore=10, spaceAfter=4)
    body_st   = ParagraphStyle("body",   fontName="Helvetica",      fontSize=8,
                                textColor=TEXT, spaceAfter=2)
    mono_st   = ParagraphStyle("mono",   fontName="Courier",        fontSize=8,
                                textColor=MONO)
    note_st   = ParagraphStyle("note",   fontName="Helvetica",      fontSize=7.5,
                                textColor=TEXT2, spaceAfter=3)

    def tbl_style_base(header_rows=1):
        return TableStyle([
            # Header
            ("BACKGROUND",   (0, 0), (-1, header_rows-1), CARD),
            ("TEXTCOLOR",    (0, 0), (-1, header_rows-1), WARN),
            ("FONTNAME",     (0, 0), (-1, header_rows-1), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, header_rows-1), 7.5),
            ("ALIGN",        (0, 0), (-1, header_rows-1), "CENTER"),
            # Body
            ("FONTNAME",     (0, header_rows), (-1, -1), "Helvetica"),
            ("FONTSIZE",     (0, header_rows), (-1, -1), 7.5),
            ("TEXTCOLOR",    (0, header_rows), (-1, -1), TEXT),
            ("ROWBACKGROUNDS",(0, header_rows), (-1, -1), [DARK, CARD2]),
            ("ALIGN",        (1, header_rows), (-1, -1), "CENTER"),
            ("ALIGN",        (0, header_rows), (0, -1),  "LEFT"),
            # Grid
            ("GRID",         (0, 0), (-1, -1), 0.3, BORD),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])

    story = []

    # ── Portada / Encabezado ──────────────────────────────────────────────────
    story.append(Paragraph("SOLARCALC PRO — MEMORIA TECNICA DE CABLEADO FV", titulo_st))
    story.append(Paragraph(
        f"Proyecto: <b>{proyecto_nombre}</b>  |  Municipio: {proyecto_municipio}  |  "
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub_st))
    story.append(Paragraph(
        "Metodologia: RETIE (Colombia) | IEC 60364-7-712 | IEC 62548 | IEC 60228  |  "
        "3 criterios: Ampacidad + Caida de tension + Calibre comercial",
        sub_st))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SOL, spaceAfter=10))

    # ── Parametros generales ──────────────────────────────────────────────────
    story.append(Paragraph("1. PARAMETROS GENERALES DEL SISTEMA", sec_st))
    mat = params.get("material", "Cobre")
    gamma = "56 m/(ohm*mm2)" if mat == "Cobre" else "35 m/(ohm*mm2)"
    ft = _factor_temp(params.get("temp_amb", 35))
    fa = _factor_agrup(params.get("n_agrup", 1))
    v_ac = params.get("v_ac", 220)
    trifasico = params.get("trifasico", False)
    vdc = params.get("vdc", 24)
    inv_w = params.get("pot_inv_w", 0)
    isc = params.get("isc", 0)
    nstr = params.get("n_strings", 1)

    gen_data = [
        ["Parametro", "Valor", "Parametro", "Valor"],
        ["Material conductor",     mat,
         "Tension DC banco/MPPT",  f"{vdc} V"],
        ["Conductividad (gamma)",  gamma,
         "Potencia inversor",      f"{inv_w:,.0f} W"],
        ["Temp. ambiente",         f"{params.get('temp_amb',35)} degC",
         "Corriente Isc panel",    f"{isc:.2f} A"],
        ["Factor temp. Ft",        f"{ft:.2f}",
         "Strings en paralelo",    str(nstr)],
        ["Circuitos agrupados",    str(params.get("n_agrup",1)),
         "Factor agrupamiento Fa", f"{fa:.2f}"],
        ["Factor seguridad DC",    "x1.25 (IEC 62548)",
         "Tension AC salida",      f"{'3x' if trifasico else '1x'}{v_ac} V"],
    ]
    gen_tbl = Table(gen_data, colWidths=[5.5*cm, 4.5*cm, 5.5*cm, 4.5*cm])
    ts_gen = tbl_style_base(1)
    ts_gen.add("SPAN", (0,0), (1,0))
    ts_gen.add("SPAN", (2,0), (3,0))
    ts_gen.add("TEXTCOLOR", (0,1), (0,-1), CYAN)
    ts_gen.add("TEXTCOLOR", (2,1), (2,-1), CYAN)
    ts_gen.add("FONTNAME",  (1,1), (1,-1), "Courier")
    ts_gen.add("FONTNAME",  (3,1), (3,-1), "Courier")
    ts_gen.add("TEXTCOLOR", (1,1), (1,-1), MONO)
    ts_gen.add("TEXTCOLOR", (3,1), (3,-1), MONO)
    gen_tbl.setStyle(ts_gen)
    story.append(gen_tbl)
    story.append(Spacer(1, 10))

    # ── Tabla resumen de tramos ───────────────────────────────────────────────
    story.append(Paragraph("2. TABLA RESUMEN DE TRAMOS", sec_st))
    story.append(Paragraph(
        "Criterio gobernante: AMP = ampacidad | DV = caida de tension. "
        "El calibre final satisface ambos criterios simultaneamente.",
        note_st))

    hdr_res = ["Tramo", "I\n(A)", "I_dis\n(A)", "Long.\n(m)",
               "S_amp\n(mm2)", "S_DV\n(mm2)", "Calibre\nfinal", "Amp.\nreal (A)",
               "DV\nreal (%)", "Limite\n(%)", "Estado"]
    res_data = [hdr_res]

    cdt_total = 0.0
    for t in tramos:
        cumple = t["cumple_cdt"]
        estado = "CUMPLE" if cumple else "REVISAR"
        if "AC" not in t["tipo"]:
            cdt_total += t["dv_real_pct"]
        res_data.append([
            t["nombre"].replace("🔆","").replace("🔋","").replace("⚡","").replace("🔌","").strip(),
            f"{t['corriente_a']:.1f}",
            f"{t['i_dis']:.1f}",
            f"{t['longitud_m']:.0f}",
            f"{t['s_amp_mm2']}",
            f"{t['s_cdt_mm2']}",
            f"{t['cal_final_mm2']} mm2",
            f"{t['amp_final_a']:.1f}",
            f"{t['dv_real_pct']:.3f}",
            f"{t['cdt_max_pct']:.1f}",
            estado,
        ])
    # Fila total DV DC
    res_data.append([
        "DV TOTAL DC (Paneles+MPPT+Bat+Inv)", "", "", "", "", "", "",
        "", f"{cdt_total:.2f}", "5.0",
        "CUMPLE" if cdt_total <= 5.0 else "REVISAR"
    ])

    col_w_res = [5.5*cm, 1.2*cm, 1.2*cm, 1.2*cm, 1.3*cm, 1.3*cm,
                 2.0*cm, 1.5*cm, 1.4*cm, 1.2*cm, 1.5*cm]
    res_tbl = Table(res_data, colWidths=col_w_res, repeatRows=1)
    ts_res = tbl_style_base(1)
    # Color calibre final
    for row_i in range(1, len(res_data)):
        if row_i < len(res_data) - 1:
            cumple_row = tramos[row_i-1]["cumple_cdt"]
            ts_res.add("TEXTCOLOR", (6, row_i), (6, row_i), GREEN)
            ts_res.add("FONTNAME",  (6, row_i), (6, row_i), "Courier-Bold")
            ts_res.add("TEXTCOLOR", (8, row_i), (8, row_i), GREEN if cumple_row else RED)
            ts_res.add("TEXTCOLOR", (10,row_i), (10,row_i), GREEN if cumple_row else RED)
    # Fila total
    last = len(res_data) - 1
    ts_res.add("SPAN",      (0, last), (7, last))
    ts_res.add("FONTNAME",  (0, last), (-1, last), "Helvetica-Bold")
    ts_res.add("BACKGROUND",(0, last), (-1, last), CARD)
    ts_res.add("TEXTCOLOR", (0, last), (7, last), WARN)
    ts_res.add("TEXTCOLOR", (8, last), (8, last), GREEN if cdt_total<=5.0 else RED)
    ts_res.add("TEXTCOLOR",(10, last),(10, last), GREEN if cdt_total<=5.0 else RED)
    res_tbl.setStyle(ts_res)
    story.append(res_tbl)
    story.append(Spacer(1, 10))

    # ── Fichas tecnicas por tramo ─────────────────────────────────────────────
    story.append(Paragraph("3. FICHA TECNICA POR TRAMO", sec_st))

    for t in tramos:
        cumple = t["cumple_cdt"]
        estado = "CUMPLE" if cumple else "NO CUMPLE"
        nombre_clean = t["nombre"].replace("🔆","").replace("🔋","").replace("⚡","").replace("🔌","").strip()

        ficha_hdr = [[Paragraph(f"<b>{nombre_clean}</b>  —  Tipo: {t['tipo']}  |  Material: {t['material']}",
                                ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=8,
                                               textColor=SOL))]]
        ficha_hdr_tbl = Table(ficha_hdr, colWidths=[27*cm])
        ficha_hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CARD),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ]))
        story.append(ficha_hdr_tbl)

        ficha_data = [
            ["Parametro", "Valor", "Parametro", "Valor", "Parametro", "Valor"],
            ["Corriente nominal", f"{t['corriente_a']:.2f} A",
             "Factor seguridad",  f"x{t['factor_seg']:.2f}",
             "I diseno",         f"{t['i_dis']:.2f} A"],
            ["Longitud tramo",   f"{t['longitud_m']} m",
             "Tension referencia",f"{t['voltaje_v']} V",
             "DV maximo",        f"{t['cdt_max_pct']}%"],
            ["F. temperatura",   f"({t['temp_amb']}C) = {t['ft']:.2f}",
             "F. agrupamiento",  f"({t['n_agrup']} circ.) = {t['fa']:.2f}",
             "F. total",         f"{t['factor_total']:.2f}"],
            ["S minima amp.",    f"{t['s_amp_mm2']} mm2",
             "S minima DV",      f"{t['s_cdt_raw']:.2f} -> {t['s_cdt_mm2']} mm2",
             "Criterio gov.",    t["criterio_gov"]],
            ["CALIBRE FINAL",   f"{t['cal_final_mm2']} mm2",
             "Ampacidad real",   f"{t['amp_final_a']:.1f} A",
             "DV real",         f"{t['dv_real_pct']:.3f}% — {estado}"],
        ]
        ficha_tbl = Table(ficha_data, colWidths=[3.5*cm, 3.5*cm, 3.5*cm, 4.5*cm, 3.5*cm, 4.5*cm])
        ts_f = tbl_style_base(1)
        # Resaltar fila de resultado final
        ts_f.add("FONTNAME",   (0, 5), (-1, 5), "Helvetica-Bold")
        ts_f.add("TEXTCOLOR",  (0, 5), (0, 5),  WARN)
        ts_f.add("TEXTCOLOR",  (1, 5), (1, 5),  GREEN)
        ts_f.add("FONTNAME",   (1, 5), (1, 5),  "Courier-Bold")
        ts_f.add("TEXTCOLOR",  (5, 5), (5, 5),  GREEN if cumple else RED)
        ts_f.add("BACKGROUND", (0, 5), (-1, 5), CARD)
        ficha_tbl.setStyle(ts_f)
        story.append(ficha_tbl)
        story.append(Spacer(1, 5))

    # ── Cuadro de materiales ──────────────────────────────────────────────────
    story.append(Paragraph("4. CUADRO DE MATERIALES — CONDUCTORES", sec_st))
    mat_agrup = defaultdict(float)
    for t in tramos:
        clave = f"{t['material']} {t['cal_final_mm2']} mm2"
        mat_agrup[clave] += t["longitud_m"] * 2 * (3 if t["tipo"] == "AC_tri" else 2) / 2

    mat_hdr = [["Conductor", "Calibre", "Longitud estimada", "Tipo recomendado", "Norma"]]
    mat_body = []
    for cab, metros in sorted(mat_agrup.items()):
        parts = cab.split(" ")
        mat_body.append([
            parts[0],
            " ".join(parts[1:]),
            f"{metros:.1f} m",
            "Cable FV PV1-F / H07RN-F",
            "IEC 62930 / UL 4703",
        ])
    mat_data = mat_hdr + mat_body
    mat_tbl = Table(mat_data, colWidths=[3*cm, 3*cm, 4*cm, 7*cm, 4*cm])
    ts_m = tbl_style_base(1)
    ts_m.add("TEXTCOLOR", (1, 1), (1, -1), GREEN)
    ts_m.add("FONTNAME",  (1, 1), (1, -1), "Courier-Bold")
    ts_m.add("TEXTCOLOR", (2, 1), (2, -1), MONO)
    mat_tbl.setStyle(ts_m)
    story.append(mat_tbl)
    story.append(Spacer(1, 10))

    # ── Limites de caida de tension ───────────────────────────────────────────
    story.append(Paragraph("5. LIMITES DE CAIDA DE TENSION (RETIE / IEC 60364-7-712)", sec_st))
    lim_data = [
        ["Tramo", "Limite recomendado", "Referencia normativa"],
        ["Paneles -> Controlador/MPPT",  "<=2%",  "IEC 62548 §10 / RETIE Art.11"],
        ["Controlador/MPPT -> Baterias", "<=1%",  "RETIE Art.11"],
        ["Baterias -> Inversor DC",      "<=1%",  "RETIE Art.11"],
        ["Salida AC (distribucion)",     "<=3%",  "IEC 60364-7-712 / NTC 2050"],
        ["Total sistema DC",             "<=5%",  "IEC 60364-7-712 §712.52.1"],
    ]
    lim_tbl = Table(lim_data, colWidths=[8*cm, 4.5*cm, 7*cm])
    ts_l = tbl_style_base(1)
    ts_l.add("TEXTCOLOR", (1, 1), (1, -1), GREEN)
    ts_l.add("FONTNAME",  (1, 1), (1, -1), "Courier-Bold")
    ts_l.add("TEXTCOLOR", (2, 1), (2, -1), TEXT2)
    lim_tbl.setStyle(ts_l)
    story.append(lim_tbl)
    story.append(Spacer(1, 8))

    # ── Nota normativa ────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORD, spaceAfter=6))
    notas = [
        "<b>Notas normativas y metodologicas:</b>",
        "• RETIE (Colombia) | IEC 60364-7-712 (instalaciones FV) | IEC 62548 (diseno arrays FV) | IEC 60228 (conductores)",
        f"• Factor de seguridad: x1.25 en circuitos DC (cargas continuas) — IEC 62548 §10.4",
        f"• Conductividad usada: {gamma}",
        f"• Factor de temperatura ({params.get('temp_amb',35)}C) = {ft:.2f}  |  "
        f"Factor de agrupamiento ({params.get('n_agrup',1)} circuitos) = {fa:.2f}",
        "• Los calibres indicados son MINIMOS de diseno. Verificar con el instalador segun metodo de "
        "instalacion y temperatura ambiente especifica del proyecto.",
        "• Criterio final: el calibre comercial seleccionado satisface SIMULTANEAMENTE ampacidad "
        "corregida Y caida de tension dentro de los limites.",
        f"• Generado por SOLARCALC PRO — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]
    for n in notas:
        story.append(Paragraph(n, note_st))

    doc.build(story)
    return buf.getvalue()


def mostrar_cableado(proyecto_id: int, session_state: dict) -> None:
    """
    Módulo completo de cableado FV. Diseñado para ser llamado desde solar_app.py
    dentro de tab12 o desde los módulos híbrido/ongrid.
    """
    ss = session_state

    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.5rem;font-weight:700;
                color:#FFB300;letter-spacing:2px;margin-bottom:0.5rem;'>
        🔌 DIMENSIONAMIENTO DE CABLEADO
    </div>
    <div class='formula-box'>
        Metodología RETIE / IEC 60364-7-712 / IEC 62548 · 3 criterios simultáneos:<br>
        <b>① Ampacidad</b> (con factores de temperatura y agrupamiento) ·
        <b>② Caída de tensión</b> (DC/AC mono/trifásica) ·
        <b>③ Calibre final = mayor de ambos criterios</b>
    </div>
    """, unsafe_allow_html=True)

    # ── 1. Leer datos del proyecto / session_state ────────────────────────────
    from db_utils import get_conn
    conn = get_conn()
    p_row = conn.execute(
        "SELECT tension_dc, hsp FROM proyectos WHERE id=?", (proyecto_id,)
    ).fetchone()
    panel_row = conn.execute(
        "SELECT potencia_wp, voc, isc FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)
    ).fetchone()
    conn.close()

    vdc_db   = p_row[0] if p_row and p_row[0] else 24
    isc_db   = panel_row[2] if panel_row and panel_row[2] else 8.02

    vdc      = int(ss.get("calc_vdc",     vdc_db))
    isc      = float(ss.get("calc_isc",   isc_db))
    n_pan    = int(ss.get("calc_num_paneles", 4))
    inv_w    = float(ss.get("calc_inv_w", ss.get("calc_inv_kw", 3) * 1000))
    n_str    = max(1, int(ss.get("calc_paralelo", n_pan)))

    # ── 2. Parámetros globales del cableado ──────────────────────────────────
    st.markdown("### ⚙ Parámetros generales", unsafe_allow_html=False)
    c1, c2, c3 = st.columns(3)
    with c1:
        material   = st.selectbox("Material del conductor", ["Cobre", "Aluminio"],
                                   key="cab_material")
        temp_amb   = st.selectbox("Temperatura ambiente (°C)",
                                   [25, 30, 35, 40, 45, 50, 55, 60], index=2,
                                   key="cab_temp")
    with c2:
        n_agrup    = st.number_input("Circuitos agrupados (agrupamiento)",
                                      min_value=1, max_value=9, value=1, key="cab_nagrup",
                                      help="Número de circuitos en la misma canalización")
        v_ac       = st.selectbox("Tensión AC salida (V)", [110, 120, 127, 208, 220, 240, 380, 480],
                                   index=4, key="cab_vac")
    with c3:
        trifasico  = st.checkbox("Sistema AC trifásico", value=False, key="cab_tri")
        fp_ac      = st.slider("Factor de potencia AC (FP)", 0.80, 1.00, 0.95, 0.01,
                                key="cab_fp")

    st.markdown("---")

    # ── 3. Longitudes por tramo ───────────────────────────────────────────────
    st.markdown("### 📏 Longitudes de tramos (m — un solo sentido)")
    lc1, lc2, lc3, lc4, lc5 = st.columns(5)
    with lc1:
        L1 = st.number_input("Paneles → MPPT", 1.0, 200.0, 15.0, 1.0, key="cab_L1")
    with lc2:
        L_bus = st.number_input("Bus DC (strings)", 1.0, 50.0, 3.0, 0.5, key="cab_Lbus",
                                 help="Solo aplica si hay más de 1 string en paralelo")
    with lc3:
        L2 = st.number_input("MPPT → Baterías", 1.0, 50.0, 2.0, 0.5, key="cab_L2")
    with lc4:
        L3 = st.number_input("Baterías → Inversor", 1.0, 50.0, 2.0, 0.5, key="cab_L3")
    with lc5:
        L4 = st.number_input("Salida AC", 1.0, 200.0, 15.0, 1.0, key="cab_L4")

    st.markdown("---")

    # ── 4. Parámetros DC: VDC, Isc, N° strings ───────────────────────────────
    st.markdown("### ⚡ Datos del sistema (auto-completados desde tus módulos)")
    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        vdc_i   = st.number_input("Tensión DC banco/MPPT (V)", 12, 1000, vdc, key="cab_vdc")
    with dc2:
        isc_i   = st.number_input("Corriente Isc panel (A)", 0.1, 50.0,
                                   round(isc, 2), 0.1, key="cab_isc")
    with dc3:
        nstr_i  = st.number_input("Strings en paralelo", 1, 50, n_str, key="cab_nstr")
    with dc4:
        inv_w_i = st.number_input("Potencia inversor (W)", 500, 100000,
                                   int(inv_w), 100, key="cab_inv_w")

    # ── 5. Calcular tramos ────────────────────────────────────────────────────
    params_calc = {
        "vdc":        vdc_i,
        "pot_inv_w":  inv_w_i,
        "isc":        isc_i,
        "n_pan":      n_pan,
        "n_strings":  nstr_i,
        "material":   material,
        "temp_amb":   temp_amb,
        "n_agrup":    n_agrup,
        "fp_ac":      fp_ac,
        "v_ac":       v_ac,
        "trifasico":  trifasico,
        "L_pan_mppt": L1,
        "L_bus_dc":   L_bus,
        "L_mppt_bat": L2,
        "L_bat_inv":  L3,
        "L_ac":       L4,
    }
    tramos = calcular_cableado_sistema(params_calc)

    # ── 6. Tabla resumen visual ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.15rem;font-weight:700;
                color:#00BCD4;letter-spacing:1px;margin-bottom:0.8rem;'>
        📋 RESUMEN DE CABLEADO — TODOS LOS TRAMOS
    </div>""", unsafe_allow_html=True)

    # Encabezado de tabla
    st.markdown("""
    <div style='display:grid;grid-template-columns:2.5fr 0.8fr 0.8fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 1fr;
                gap:2px;background:#1A2440;border-radius:8px 8px 0 0;
                padding:0.5rem 0.8rem;font-size:0.72rem;color:#8A9BBD;
                text-transform:uppercase;letter-spacing:1px;font-weight:600;'>
        <span>Tramo</span><span>I (A)</span><span>I_dis (A)</span>
        <span>Long. (m)</span><span>S_amp (mm²)</span><span>S_ΔV (mm²)</span>
        <span>✅ Calibre</span><span>Amp. real (A)</span><span>ΔV real (%)</span>
    </div>""", unsafe_allow_html=True)

    cdt_total_pct = 0.0
    for i, t in enumerate(tramos):
        bg = "#0F1525" if i % 2 == 0 else "#111A2E"
        cdt_color  = _color_cdt(t["cumple_cdt"], t["dv_real_pct"], t["cdt_max_pct"])
        criterio   = _criterio_badge(t["criterio_gov"])
        if "AC" not in t["tipo"]:
            cdt_total_pct += t["dv_real_pct"]

        st.markdown(f"""
        <div style='display:grid;grid-template-columns:2.5fr 0.8fr 0.8fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 1fr;
                    gap:2px;background:{bg};padding:0.45rem 0.8rem;font-size:0.8rem;
                    border-bottom:1px solid #1A2440;'>
            <span style='color:#E0E6F0;font-weight:500;'>{t["nombre"]} {criterio}</span>
            <span style='font-family:Share Tech Mono;color:#FFD54F;'>{t["corriente_a"]:.1f}</span>
            <span style='font-family:Share Tech Mono;color:#FFB300;'>{t["i_dis"]:.1f}</span>
            <span style='font-family:Share Tech Mono;color:#8A9BBD;'>{t["longitud_m"]:.0f}</span>
            <span style='font-family:Share Tech Mono;color:#00BCD4;'>{t["s_amp_mm2"]}</span>
            <span style='font-family:Share Tech Mono;color:#A78BFA;'>{t["s_cdt_mm2"]}</span>
            <span style='font-family:Share Tech Mono;color:#00E676;font-weight:700;font-size:0.9rem;'>{t["cal_final_mm2"]} mm²</span>
            <span style='font-family:Share Tech Mono;color:#FFD54F;'>{t["amp_final_a"]:.1f}</span>
            <span style='font-family:Share Tech Mono;color:{cdt_color};font-weight:600;'>
                {t["dv_real_pct"]:.2f}% ≤{t["cdt_max_pct"]}%</span>
        </div>""", unsafe_allow_html=True)

    # ── Total caída DC
    cdt_total_color = "#00E676" if cdt_total_pct <= CDT_LIMITES["total"] else "#FF5252"
    st.markdown(f"""
    <div style='background:#0A1020;padding:0.5rem 0.8rem;border-radius:0 0 8px 8px;
                display:flex;justify-content:space-between;align-items:center;
                border-top:2px solid #FFB300;'>
        <span style='color:#8A9BBD;font-size:0.8rem;'>
            ΔV total lado DC (Paneles→MPPT + MPPT→Bat + Bat→Inv)</span>
        <span style='font-family:Share Tech Mono;font-weight:700;font-size:1rem;
                     color:{cdt_total_color};'>
            {cdt_total_pct:.2f}% (límite: {CDT_LIMITES["total"]}%)</span>
    </div>""", unsafe_allow_html=True)

    # ── 7. Fichas técnicas por tramo ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.15rem;font-weight:700;
                color:#00BCD4;letter-spacing:1px;margin-bottom:0.8rem;'>
        🔍 DESGLOSE TÉCNICO POR TRAMO
    </div>""", unsafe_allow_html=True)

    cols_tramos = st.columns(min(len(tramos), 3))
    for idx, t in enumerate(tramos):
        col = cols_tramos[idx % len(cols_tramos)]
        cdt_color = _color_cdt(t["cumple_cdt"], t["dv_real_pct"], t["cdt_max_pct"])
        estado    = "✅ CUMPLE" if t["cumple_cdt"] else "❌ NO CUMPLE"
        with col:
            st.markdown(f"""
            <div class='sol-card' style='margin-bottom:0.6rem;'>
                <div style='color:#FFB300;font-family:Rajdhani,sans-serif;
                            font-weight:600;margin-bottom:0.5rem;font-size:0.9rem;'>
                    {t["nombre"]}</div>
                <table style='width:100%;font-size:0.77rem;border-collapse:collapse;'>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.28rem 0;'>Corriente</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{t["corriente_a"]:.2f} A</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>I diseño (×{t["factor_seg"]:.2f})</td>
                        <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{t["i_dis"]:.2f} A</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>Longitud</td>
                        <td style='font-family:Share Tech Mono;color:#8A9BBD;text-align:right;'>{t["longitud_m"]} m</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>F. temperatura ({t["temp_amb"]}°C)</td>
                        <td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{t["ft"]:.2f}</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>F. agrupamiento ({t["n_agrup"]} circ.)</td>
                        <td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{t["fa"]:.2f}</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>S mínima por ampacidad</td>
                        <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{t["s_amp_mm2"]} mm²</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>S mínima por ΔV ({t["cdt_max_pct"]}%)</td>
                        <td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{t["s_cdt_raw"]:.2f} → {t["s_cdt_mm2"]} mm²</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'>
                        <td style='color:#FFB300;font-weight:600;'>✅ Calibre seleccionado</td>
                        <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;font-weight:700;font-size:1rem;'>{t["cal_final_mm2"]} mm²</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>Criterio gobernante</td>
                        <td style='text-align:right;'>{_criterio_badge(t["criterio_gov"])}</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;'>Ampacidad real</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{t["amp_final_a"]:.1f} A</td>
                    </tr>
                    <tr>
                        <td style='color:#8A9BBD;'>ΔV real</td>
                        <td style='font-family:Share Tech Mono;color:{cdt_color};text-align:right;font-weight:600;'>
                            {t["dv_real_pct"]:.3f}% — {estado}</td>
                    </tr>
                </table>
            </div>""", unsafe_allow_html=True)

    # ── 8. Cuadro de materiales ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.15rem;font-weight:700;
                color:#00BCD4;letter-spacing:1px;margin-bottom:0.8rem;'>
        🛒 CUADRO DE MATERIALES — CONDUCTORES
    </div>""", unsafe_allow_html=True)

    # Agrupar calibres y longitudes
    from collections import defaultdict
    resumen_cables = defaultdict(float)
    for t in tramos:
        clave = f"{material} {t['cal_final_mm2']} mm²"
        # ×2 porque la fórmula ya considera ida y vuelta, pero para material se necesita solo la longitud real × 2 conductores
        resumen_cables[clave] += t["longitud_m"] * 2 * (3 if t["tipo"] == "AC_tri" else 2) / 2
        # simplificado: longitud de cable (metros de conductor por polo)

    mat_rows = ""
    for cab, metros in sorted(resumen_cables.items()):
        mat_rows += f"""
        <tr style='border-bottom:1px solid #2A3A55;'>
            <td style='color:#E0E6F0;padding:0.4rem 0.6rem;'>{cab}</td>
            <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:center;padding:0.4rem;'>{metros:.1f} m</td>
            <td style='font-family:Share Tech Mono;color:#8A9BBD;text-align:center;padding:0.4rem;'>Cable FV tipo PV1-F / H07RN-F</td>
        </tr>"""

    st.markdown(f"""
    <table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>
        <thead>
            <tr style='background:#1A2440;color:#8A9BBD;font-size:0.75rem;text-transform:uppercase;letter-spacing:1px;'>
                <th style='padding:0.5rem 0.6rem;text-align:left;'>Conductor</th>
                <th style='padding:0.5rem;text-align:center;'>Longitud estimada</th>
                <th style='padding:0.5rem;text-align:center;'>Tipo recomendado</th>
            </tr>
        </thead>
        <tbody>{mat_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # ── 9. Nota normativa ─────────────────────────────────────────────────────
    ft_val  = _factor_temp(temp_amb)
    fa_val  = _factor_agrup(n_agrup)
    gamma_u = "56 m/(Ω·mm²)" if material == "Cobre" else "35 m/(Ω·mm²)"
    st.markdown(f"""
    <div class='info-note' style='margin-top:1.2rem;font-size:0.8rem;'>
        <b>Notas normativas:</b><br>
        • RETIE (Colombia) · IEC 60364-7-712 (instalaciones FV) · IEC 62548 (diseño arrays FV) · IEC 60228 (conductores)<br>
        • Factor de seguridad: ×1.25 en circuitos DC (cargas continuas) según IEC 62548 §10.4<br>
        • Conductividad usada: Cu = {gamma_u} · Factor temperatura {temp_amb}°C = {ft_val:.2f} ·
          Factor agrupamiento ({n_agrup} circ.) = {fa_val:.2f}<br>
        • Los calibres indicados son <b>mínimos de diseño</b>. Verificar con el instalador la
          ampacidad real según método de instalación y temperatura ambiente específica del proyecto.<br>
        • Caída de tensión límite total DC ≤ {CDT_LIMITES["total"]}% |
          Paneles→MPPT ≤ {CDT_LIMITES["paneles_mppt"]}% |
          MPPT→Bat ≤ {CDT_LIMITES["mppt_baterias"]}% |
          Bat→Inv ≤ {CDT_LIMITES["baterias_inv"]}% |
          AC ≤ {CDT_LIMITES["salida_ac"]}%
    </div>
    """, unsafe_allow_html=True)

    # ── 10. Botón descarga PDF ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
                color:#FFB300;letter-spacing:1px;margin-bottom:0.6rem;'>
        📄 EXPORTAR MEMORIA TÉCNICA DE CABLEADO
    </div>""", unsafe_allow_html=True)

    col_pdf1, col_pdf2 = st.columns([1, 2])
    with col_pdf1:
        if st.button("📄 Generar PDF de Cableado", use_container_width=True,
                     key="btn_gen_pdf_cableado"):
            st.session_state["_gen_pdf_cab"] = True

    if st.session_state.get("_gen_pdf_cab", False):
        with st.spinner("Generando PDF de cableado..."):
            try:
                # Obtener nombre del proyecto
                from db_utils import get_conn as _get_conn_pdf
                _conn_pdf = _get_conn_pdf()
                _p_row = _conn_pdf.execute(
                    "SELECT nombre, municipio FROM proyectos WHERE id=?",
                    (proyecto_id,)).fetchone()
                _conn_pdf.close()
                _proy_nom = _p_row[0] if _p_row else "Proyecto"
                _proy_mun = _p_row[1] if _p_row and len(_p_row) > 1 else "—"

                pdf_bytes = generar_pdf_cableado(
                    tramos            = tramos,
                    params            = params_calc,
                    proyecto_nombre   = _proy_nom,
                    proyecto_municipio= _proy_mun,
                )
                fname_pdf = f"cableado_{_proy_nom.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                st.download_button(
                    label       = "⬇ Descargar Memoria Técnica PDF",
                    data        = pdf_bytes,
                    file_name   = fname_pdf,
                    mime        = "application/pdf",
                    use_container_width=True,
                    key         = "dl_pdf_cableado",
                )
                st.session_state["_gen_pdf_cab"] = False
                st.markdown(f"""
                <div class='info-note' style='margin-top:0.5rem;'>
                    ✅ PDF generado: <b>{fname_pdf}</b><br>
                    Incluye: parámetros generales · tabla resumen · fichas técnicas por tramo ·
                    cuadro de materiales · límites normativos · notas RETIE/IEC
                </div>""", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error generando PDF: {e}")
                st.session_state["_gen_pdf_cab"] = False
