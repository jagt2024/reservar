# modulo_ongrid.py — SolarCalc Pro · Módulo ON-GRID (Sistema Conectado a la Red)
# ─────────────────────────────────────────────────────────────────────────────
"""
Dimensionamiento de sistema fotovoltaico ON-GRID (interconectado a la red):
  • Sin baterías (o batería de respaldo opcional)
  • Inversor de red / grid-tie con seguimiento MPPT integrado
  • Análisis de inyección, autoconsumo y payback económico
  • Planos: distribución de paneles + diagrama unifilar ON-GRID
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import os
import tempfile
import pathlib
from datetime import datetime

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import base64

# ─── DB ───────────────────────────────────────────────────────────────────────
def _db_path() -> str:
    env = os.environ.get("SOLARCALC_DB_PATH")
    if env:
        return env
    script_dir = pathlib.Path(__file__).parent.resolve()
    candidate = script_dir / "solar_calc.db"
    try:
        t = script_dir / ".wt"; t.touch(); t.unlink()
        return str(candidate)
    except Exception:
        return str(pathlib.Path(tempfile.gettempdir()) / "solar_calc.db")

DB_PATH = _db_path()

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ─── HELPERS MATEMÁTICOS ──────────────────────────────────────────────────────
def tension_dc_ongrid(consumo_wh: float) -> int:
    """Para ON-GRID se prefieren tensiones más altas para menor corriente."""
    if consumo_wh < 3000:
        return 48
    elif consumo_wh < 8000:
        return 360   # string de ~8 paneles en serie
    else:
        return 600   # string de ~12 paneles en serie


def calcular_string_ongrid(v_mppt_min: float, v_mppt_max: float, voc: float, vmpp: float,
                            pot_panel_wp: int, pot_inv_kw: float) -> dict:
    """
    Calcula la configuración óptima de strings para inversor grid-tie.
    v_mppt_min / v_mppt_max: rango MPPT del inversor (V)
    voc, vmpp: tensiones del panel
    """
    # Paneles en serie (string): Vmpp_string debe quedar dentro del rango MPPT
    pan_serie_min = math.ceil(v_mppt_min / vmpp)
    pan_serie_max = math.floor(v_mppt_max / vmpp)
    # Verificar que Voc del string no supere el Vmax del inversor (usamos v_mppt_max * 1.15)
    v_max_inv = v_mppt_max * 1.15
    pan_serie_max_voc = math.floor(v_max_inv / voc)
    pan_serie_opt = min(pan_serie_max, pan_serie_max_voc)

    if pan_serie_opt < pan_serie_min:
        pan_serie_opt = pan_serie_min

    # Paneles totales necesarios
    pot_total_wp = pot_inv_kw * 1000 * 1.20   # sobredimensionar 20% para ON-GRID
    n_total = math.ceil(pot_total_wp / pot_panel_wp)
    # Strings en paralelo
    n_strings = max(1, math.ceil(n_total / pan_serie_opt))
    n_total_real = n_strings * pan_serie_opt

    v_string_mpp = pan_serie_opt * vmpp
    v_string_oc  = pan_serie_opt * voc
    i_string     = pot_panel_wp / vmpp  # Impp aprox

    return {
        "pan_serie":      pan_serie_opt,
        "n_strings":      n_strings,
        "n_total":        n_total_real,
        "v_string_mpp":   v_string_mpp,
        "v_string_oc":    v_string_oc,
        "i_string":       i_string,
        "pot_instalada":  n_total_real * pot_panel_wp,
    }


def calcular_ongrid(consumo_wh_dia: float, hsp: float, pot_panel_wp: int,
                     pot_inv_kw: float, tarifa_kwh: float = 700.0,
                     precio_panel: float = 320000.0,
                     rendimiento: float = 0.80) -> dict:
    """Cálculo principal ON-GRID.
    Fórmula: Pot_array (kWp) = Consumo_diario (kWh) / (HSP × PR)
    La red actúa como batería virtual — no se aplica factor de baterías.
    consumo_fs se conserva solo para PDF/Excel (inversor y baterías auxiliares).
    """
    consumo_kwh_dia  = consumo_wh_dia / 1000.0
    consumo_fs       = consumo_wh_dia * 1.20        # solo para compatibilidad PDF/inversor

    # ── 2. Potencia mínima array: Consumo / (HSP × PR)
    pot_array_min_kw = consumo_kwh_dia / (hsp * rendimiento)
    pot_array_min_wp = pot_array_min_kw * 1000

    n_paneles        = math.ceil(pot_array_min_wp / pot_panel_wp)
    pot_instalada_wp = n_paneles * pot_panel_wp

    gen_dia_kwh  = (pot_instalada_wp / 1000) * hsp * rendimiento
    gen_mes_kwh  = gen_dia_kwh * 30
    gen_anio_kwh = gen_dia_kwh * 365

    autoconsumo_dia = min(gen_dia_kwh, consumo_kwh_dia)
    inyeccion_dia   = max(0, gen_dia_kwh - consumo_kwh_dia)
    deficit_dia     = max(0, consumo_kwh_dia - gen_dia_kwh)
    autoconsumo_pct = (autoconsumo_dia / consumo_kwh_dia * 100) if consumo_kwh_dia > 0 else 0

    ahorro_mes        = autoconsumo_dia * 30 * tarifa_kwh
    ingreso_inyeccion = inyeccion_dia   * 30 * tarifa_kwh * 0.5

    # 5. Inversor: pot_instalada × 1.2 → estándar superior
    _inv_w  = pot_instalada_wp * 1.2
    _kw_std = [1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50]
    pot_inv_rec_kw = float(next((k for k in _kw_std if k * 1000 >= _inv_w),
                                 math.ceil(_inv_w / 1000)))

    inversion_est   = n_paneles * precio_panel + pot_inv_rec_kw * 2_000_000
    beneficio_anual = (ahorro_mes + ingreso_inyeccion) * 12
    payback_anios   = inversion_est / beneficio_anual if beneficio_anual > 0 else 99
    co2_anio_kg     = gen_anio_kwh * 0.126

    return {
        "consumo_fs":       consumo_fs,
        "pot_array_min":    pot_array_min_wp,
        "n_paneles":        n_paneles,
        "pot_instalada":    pot_instalada_wp,
        "gen_dia_kwh":      gen_dia_kwh,
        "gen_mes_kwh":      gen_mes_kwh,
        "gen_anio_kwh":     gen_anio_kwh,
        "autoconsumo_dia":  autoconsumo_dia,
        "inyeccion_dia":    inyeccion_dia,
        "deficit_dia":      deficit_dia,
        "autoconsumo_pct":  autoconsumo_pct,
        "ahorro_mes":       ahorro_mes,
        "ingreso_iny":      ingreso_inyeccion,
        "pot_inv_rec_kw":   pot_inv_rec_kw,
        "inversion_est":    inversion_est,
        "beneficio_anual":  beneficio_anual,
        "payback_anios":    payback_anios,
        "co2_anio_kg":      co2_anio_kg,
        "rendimiento_pr":   rendimiento,
    }


# ─── SVG HELPERS ─────────────────────────────────────────────────────────────
def _safe(v, def_="—"):
    return str(v) if v else def_

def _svg_safe(v, def_=""):
    if not v:
        return def_
    return str(v).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')


def render_svg_og(svg_string: str, height: int = 700) -> None:
    b64 = base64.b64encode(svg_string.encode("utf-8")).decode("utf-8")
    html = (f'<div style="width:100%;border-radius:12px;overflow:hidden;">'
            f'<img src="data:image/svg+xml;base64,{b64}" '
            f'style="width:100%;height:{height}px;object-fit:contain;'
            f'background:#0A0E1A;border-radius:12px;" alt="Plano ON-GRID"/>'
            f'</div>')
    st.markdown(html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SVG PLANO 1 — DISTRIBUCIÓN DE PANELES (ON-GRID)
# ═══════════════════════════════════════════════════════════════════════════════
def svg_plano_paneles_og(n_paneles: int, pan_serie: int, n_strings: int,
                          pot_panel: int, proyecto_info=None) -> str:
    W, H = 1100, 680
    C_BG = "#0A0E1A"
    C_SOL = "#FFB300"
    C_DC = "#00BCD4"
    C_AC = "#00E676"
    C_DIM = "#8A9BBD"
    C_TEXT = "#E8EDF5"
    C_PANEL = "#1A2235"
    C_PANEL_B = "#00BCD4"
    C_GRID = "#FF6B35"   # color especial para red eléctrica

    def box(x,y,w,h,fill,stroke,rx=4,cap_h=0,gap=1):
        b=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{gap}" rx="{rx}"/>'
        if cap_h:
            b+=f'<rect x="{x}" y="{y}" width="{w}" height="{cap_h}" fill="{stroke}" opacity="0.25" rx="{rx}"/>'
        return b

    def txt(x,y,t,size=9,fill=C_TEXT,anchor="middle",weight="normal",font="Barlow,sans-serif"):
        return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{t}</text>'

    def line(x1,y1,x2,y2,stroke,sw=1.5,dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>'

    # ── Panel individual ──────────────────────────────────────────────────────
    PW, PH = 52, 32   # ancho/alto panel en SVG
    GAP_X, GAP_Y = 6, 6
    MARGIN_X, MARGIN_Y = 60, 90

    # Calcular grid de paneles
    max_cols = min(pan_serie, 18)
    max_rows = math.ceil(n_paneles / max_cols)

    # Dibujar paneles
    panels_svg = ""
    pan_count = 0
    string_colors = [C_PANEL_B, "#FFB300", "#00E676", "#FF5252", "#A78BFA", "#F472B6"]

    for row_i in range(max_rows):
        for col_i in range(max_cols):
            if pan_count >= n_paneles:
                break
            string_i = row_i % len(string_colors)
            px = MARGIN_X + col_i * (PW + GAP_X)
            py = MARGIN_Y + row_i * (PH + GAP_Y)
            sc = string_colors[string_i % len(string_colors)]
            panels_svg += box(px, py, PW, PH, C_PANEL, sc, 3)
            # Líneas de células
            for lx in range(1, 4):
                panels_svg += line(px + lx*PW//4, py+2, px + lx*PW//4, py+PH-2, "#2A3A55", 0.5)
            for ly in range(1, 3):
                panels_svg += line(px+2, py + ly*PH//3, px+PW-2, py + ly*PH//3, "#2A3A55", 0.5)
            # Número de panel
            panels_svg += txt(px+PW//2, py+PH//2+3, str(pan_count+1), 6.5, sc, "middle", "600", "Share Tech Mono,monospace")
            pan_count += 1

    # ── Etiquetas de strings ───────────────────────────────────────────────────
    string_labels = ""
    for s_i in range(n_strings):
        sc = string_colors[s_i % len(string_colors)]
        sy = MARGIN_Y + s_i * (PH + GAP_Y) + PH//2 + 3
        string_labels += txt(MARGIN_X - 8, sy, f"S{s_i+1}", 7.5, sc, "end", "700", "Share Tech Mono,monospace")

    # ── Dimensiones ──────────────────────────────────────────────────────────
    arr_ancho_m = max_cols * 1.134   # panel típico 1134mm
    arr_alto_m  = max_rows * 0.686
    arr_w_px    = max_cols * (PW + GAP_X)
    arr_h_px    = max_rows * (PH + GAP_Y)

    # Flechas de dimensión horizontal
    dim_y   = MARGIN_Y + arr_h_px + 18
    dim_x1  = MARGIN_X
    dim_x2  = MARGIN_X + arr_w_px - GAP_X
    dims_svg = f'''
    {line(dim_x1, dim_y, dim_x2, dim_y, C_DIM, 1)}
    {line(dim_x1, dim_y-4, dim_x1, dim_y+4, C_DIM, 1)}
    {line(dim_x2, dim_y-4, dim_x2, dim_y+4, C_DIM, 1)}
    {txt((dim_x1+dim_x2)//2, dim_y+11, f"↔ {arr_ancho_m:.2f} m ({max_cols} paneles en serie)", 8, C_DIM)}
    {line(MARGIN_X-20, MARGIN_Y, MARGIN_X-20, MARGIN_Y+arr_h_px-GAP_Y, C_DIM, 1)}
    {line(MARGIN_X-24, MARGIN_Y, MARGIN_X-16, MARGIN_Y, C_DIM, 1)}
    {line(MARGIN_X-24, MARGIN_Y+arr_h_px-GAP_Y, MARGIN_X-16, MARGIN_Y+arr_h_px-GAP_Y, C_DIM, 1)}
    {txt(MARGIN_X-22, MARGIN_Y + arr_h_px//2, f"{arr_alto_m:.2f}m", 7.5, C_DIM, "end")}
    '''

    # ── Panel lateral con datos ───────────────────────────────────────────────
    INFO_X = max(MARGIN_X + max_cols * (PW + GAP_X) + 40, 800)
    INFO_Y = 80
    INFO_W = W - INFO_X - 20
    if INFO_W < 140:
        INFO_W = 180
        INFO_X = W - INFO_W - 20

    proy = _svg_safe(proyecto_info[1] if proyecto_info else None, "Proyecto")
    mun  = _svg_safe(proyecto_info[2] if proyecto_info else None, "—")
    pot_inst = n_paneles * pot_panel

    info_items = [
        ("Sistema", "ON-GRID / INTERCONECTADO", C_GRID),
        ("Paneles", f"{n_paneles} × {pot_panel} Wp", C_SOL),
        ("Pot. instalada", f"{pot_inst:,} Wp  ({pot_inst/1000:.2f} kWp)", C_SOL),
        ("Config.", f"{pan_serie}S × {n_strings}P", C_DC),
        ("Strings", f"{n_strings} strings en paralelo", C_DC),
        ("Serie/string", f"{pan_serie} paneles", C_DC),
        ("Área array", f"{arr_ancho_m:.1f} × {arr_alto_m:.1f} m", C_DIM),
        ("Sup. total", f"≈ {arr_ancho_m*arr_alto_m:.1f} m²", C_DIM),
    ]
    info_svg = box(INFO_X, INFO_Y, INFO_W, 20 + len(info_items)*22 + 10, "#0F1525", "#2A3A55", 8)
    info_svg += box(INFO_X, INFO_Y, INFO_W, 20, "#FF6B35", "#FF6B35", 8, 0, 0)
    info_svg += txt(INFO_X + INFO_W//2, INFO_Y + 13, "DATOS ARRAY ON-GRID", 8, "#0A0E1A", "middle", "700", "Rajdhani,sans-serif")
    for k, (lbl, val, col) in enumerate(info_items):
        iy = INFO_Y + 30 + k * 22
        info_svg += txt(INFO_X + 8, iy + 7, lbl, 7.5, C_DIM, "start")
        info_svg += txt(INFO_X + INFO_W - 8, iy + 7, val, 7.5, col, "end", "600", "Share Tech Mono,monospace")
        if k < len(info_items)-1:
            info_svg += line(INFO_X+6, iy+13, INFO_X+INFO_W-6, iy+13, "#1A2235", 0.5)

    # ── Leyenda de strings ────────────────────────────────────────────────────
    leg_x = INFO_X
    leg_y = INFO_Y + 20 + len(info_items) * 22 + 25
    leg_items = [(string_colors[i % len(string_colors)], f"String {i+1} ({pan_serie} pan.)") for i in range(min(n_strings, 6))]
    legend_svg = box(leg_x, leg_y, INFO_W, 20 + len(leg_items)*18 + 8, "#0F1525", "#2A3A55", 6)
    legend_svg += txt(leg_x + INFO_W//2, leg_y + 13, "LEYENDA STRINGS", 7.5, C_DIM, "middle", "700")
    for k, (sc, lbl) in enumerate(leg_items):
        ly2 = leg_y + 24 + k * 18
        legend_svg += box(leg_x + 8, ly2, 12, 10, sc, sc, 2)
        legend_svg += txt(leg_x + 26, ly2 + 8, lbl, 7.5, C_TEXT, "start")

    # ── Título ────────────────────────────────────────────────────────────────
    tb_y = H - 68
    title_svg = f'''
    <rect x="0" y="{tb_y}" width="{W}" height="68" fill="#0F1525" stroke="#2A3A55" stroke-width="0.8"/>
    <line x1="0" y1="{tb_y}" x2="{W}" y2="{tb_y}" stroke="{C_GRID}" stroke-width="1.5"/>
    <text x="12" y="{tb_y+17}" font-family="Rajdhani,sans-serif" font-size="13"
          fill="{C_GRID}" font-weight="700">☀ PLANO DISTRIBUCIÓN PANELES — SISTEMA FOTOVOLTAICO ON-GRID (INTERCONECTADO)</text>
    <text x="12" y="{tb_y+31}" font-family="Rajdhani,sans-serif" font-size="9" fill="{C_TEXT}">
        Proyecto: {proy}  |  Municipio: {mun}  |  Config: {pan_serie}S×{n_strings}P  |  {n_paneles} paneles × {pot_panel}Wp</text>
    <text x="12" y="{tb_y+45}" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">
        Pot. instalada: {pot_inst/1000:.2f} kWp  |  Área: {arr_ancho_m:.2f}m × {arr_alto_m:.2f}m  |  SolarCalc Pro — ON-GRID  |  {datetime.now().strftime("%d/%m/%Y")}  |  Plano N°01</text>
    <text x="{W-12}" y="{tb_y+17}" text-anchor="end" font-family="Share Tech Mono,monospace" font-size="9" fill="{C_DIM}">Plano N°01  Rev.A</text>
    '''

    # ── Encabezado superior ───────────────────────────────────────────────────
    header_svg = f'''
    <rect x="0" y="0" width="{W}" height="58" fill="#0F1525"/>
    <line x1="0" y1="58" x2="{W}" y2="58" stroke="{C_GRID}" stroke-width="1.5"/>
    <text x="20" y="22" font-family="Rajdhani,sans-serif" font-size="18" fill="{C_SOL}" font-weight="700" letter-spacing="2">☀ SOLARCALC PRO</text>
    <text x="20" y="38" font-family="Barlow,sans-serif" font-size="9" fill="{C_DIM}" letter-spacing="3">SISTEMA FOTOVOLTAICO INTERCONECTADO A LA RED — ON-GRID</text>
    <text x="20" y="52" font-family="Share Tech Mono,monospace" font-size="8" fill="#2A3A55">DISTRIBUCIÓN FÍSICA DE PANELES  ·  VISTA EN PLANTA</text>
    <rect x="{W-220}" y="8" width="210" height="44" rx="6" fill="#1A2235" stroke="{C_GRID}" stroke-width="1"/>
    <text x="{W-115}" y="24" text-anchor="middle" font-family="Rajdhani,sans-serif" font-size="11" fill="{C_GRID}" font-weight="700">RED ELÉCTRICA CONECTADA</text>
    <text x="{W-115}" y="38" text-anchor="middle" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">Inyección / Autoconsumo</text>
    <text x="{W-115}" y="50" text-anchor="middle" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">220V AC  60Hz</text>
    '''

    svg = f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
         style="background:{C_BG};border-radius:12px;width:100%;max-height:720px;">
      <defs>
        <pattern id="grid_og1" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#12192B" stroke-width="0.3"/>
        </pattern>
        <filter id="glow_og"><feGaussianBlur stdDeviation="1.5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <rect width="{W}" height="{H-68}" fill="url(#grid_og1)"/>
      {header_svg}
      {panels_svg}
      {string_labels}
      {dims_svg}
      {info_svg}
      {legend_svg}
      {title_svg}
    </svg>'''
    return svg


# ═══════════════════════════════════════════════════════════════════════════════
# SVG PLANO 2 — DIAGRAMA UNIFILAR ON-GRID
# ═══════════════════════════════════════════════════════════════════════════════
def svg_diagrama_unifilar_og(n_paneles: int, pan_serie: int, n_strings: int,
                               pot_panel: int, pot_inv_kw: float, v_string_mpp: float,
                               v_string_oc: float, i_string: float, consumo_fs_wh: float,
                               hsp: float, proyecto_info=None) -> str:
    W, H = 1100, 680
    C_BG = "#0A0E1A"
    C_SOL = "#FFB300"
    C_DC = "#00BCD4"
    C_AC = "#00E676"
    C_GRID = "#FF6B35"
    C_DIM = "#8A9BBD"
    C_TEXT = "#E8EDF5"
    C_NEG = "#FF5252"
    C_GND = "#888"

    def box(x,y,w,h,fill,stroke,rx=4,sw=1):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx}"/>'
    def txt(x,y,t,size=9,fill=C_TEXT,anchor="middle",weight="normal",font="Barlow,sans-serif"):
        return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{_svg_safe(t)}</text>'
    def line(x1,y1,x2,y2,stroke=C_DC,sw=2,dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
    def wlbl(x,y,t,col=C_DC):
        return f'<text x="{x}" y="{y}" font-family="Share Tech Mono,monospace" font-size="7" fill="{col}" text-anchor="start">{_svg_safe(t)}</text>'

    pot_inst = n_paneles * pot_panel
    i_array  = i_string * n_strings
    v_array  = v_string_mpp

    proy = _svg_safe(proyecto_info[1] if proyecto_info else None, "Proyecto")
    mun  = _svg_safe(proyecto_info[2] if proyecto_info else None, "—")

    # ── 1. Array FV ───────────────────────────────────────────────────────────
    ARR_X=30; ARR_Y=130; ARR_W=130; ARR_H=200
    arr_block = f'''
    <g id="array_og">
      {box(ARR_X,ARR_Y,ARR_W,ARR_H,"#0F1525","#FFB300",8)}
      {box(ARR_X,ARR_Y,ARR_W,22,"#1A2235","#FFB300",8)}
      {txt(ARR_X+ARR_W//2, ARR_Y+14, "ARRAY FV ON-GRID", 7.5, C_SOL,"middle","700","Rajdhani,sans-serif")}
      {txt(ARR_X+ARR_W//2, ARR_Y+34, f"{n_paneles} paneles", 8.5, C_SOL,"middle","700","Share Tech Mono,monospace")}
      {txt(ARR_X+ARR_W//2, ARR_Y+47, f"{pot_inst/1000:.2f} kWp", 8, C_DIM)}
    '''
    # Dibujar miniatura de string
    sp_x = ARR_X + 10; sp_y = ARR_Y + 60
    sp_w = 22; sp_h = 14; sp_gap = 4
    for s in range(min(n_strings, 4)):
        arr_block += box(sp_x, sp_y + s*(sp_h+sp_gap), sp_w, sp_h, "#1E2A3F", C_DC, 2)
        arr_block += txt(sp_x+sp_w//2, sp_y+s*(sp_h+sp_gap)+sp_h//2+3, f"S{s+1}", 6, C_DC)
        if s < min(n_strings,4)-1:
            arr_block += line(sp_x+sp_w//2, sp_y+s*(sp_h+sp_gap)+sp_h,
                              sp_x+sp_w//2, sp_y+(s+1)*(sp_h+sp_gap), C_DC, 1)
    if n_strings > 4:
        arr_block += txt(sp_x+sp_w//2, sp_y+4*(sp_h+sp_gap)+6, f"...+{n_strings-4}", 6.5, C_DIM)
    arr_block += txt(sp_x+sp_w+8, sp_y+2*(sp_h+sp_gap)+7, f"{pan_serie}S", 7, C_DIM, "start")
    arr_block += txt(ARR_X+ARR_W//2, ARR_Y+ARR_H-28, f"Vmpp={v_array:.0f}V", 7, C_DC,"middle","normal","Share Tech Mono,monospace")
    arr_block += txt(ARR_X+ARR_W//2, ARR_Y+ARR_H-16, f"Icc={i_array:.1f}A", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")
    arr_block += "</g>"

    # ── 2. String combiner / caja de conexiones DC ────────────────────────────
    CB_X=225; CB_Y=165; CB_W=90; CB_H=120
    cb_block = f'''
    <g id="combiner">
      {box(CB_X,CB_Y,CB_W,CB_H,"#0F1525","#00BCD4",6)}
      {box(CB_X,CB_Y,CB_W,20,"#1A2235","#00BCD4",6)}
      {txt(CB_X+CB_W//2, CB_Y+13, "CAJA CONEX. DC", 7, C_DC,"middle","700","Rajdhani,sans-serif")}
      {txt(CB_X+CB_W//2, CB_Y+35, "String Combiner", 7.5, C_TEXT)}
      {txt(CB_X+CB_W//2, CB_Y+50, f"{n_strings} entradas DC", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {box(CB_X+12,CB_Y+60,CB_W-24,18,"#1E2A3F","#FF5252",3)}
      {txt(CB_X+CB_W//2, CB_Y+72, "Fusibles DC Array", 7, "#FF5252")}
      {txt(CB_X+CB_W//2, CB_Y+82, f"≥{i_array:.0f}A", 6.5, C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {box(CB_X+12,CB_Y+84,CB_W-24,18,"#1E2A3F","#8A9BBD",3)}
      {txt(CB_X+CB_W//2, CB_Y+96, "Seccionador DC", 7, C_DIM)}
    </g>'''

    # ── 3. Inversor Grid-Tie ──────────────────────────────────────────────────
    INV_X=390; INV_Y=120; INV_W=140; INV_H=230
    inv_kva_lbl = f"{pot_inv_kw:.1f}"
    mppt_v = f"{v_string_mpp:.0f}–{v_string_oc:.0f}V"
    inv_block = f'''
    <g id="inversor_og">
      {box(INV_X,INV_Y,INV_W,INV_H,"#0F1525","#00E676",8,1.5)}
      {box(INV_X,INV_Y,INV_W,22,"#1A2235","#00E676",8)}
      {txt(INV_X+INV_W//2, INV_Y+14, "INVERSOR GRID-TIE", 8, C_AC,"middle","700","Rajdhani,sans-serif")}
      {txt(INV_X+INV_W//2, INV_Y+38, f"{inv_kva_lbl} kW", 18, C_AC,"middle","700","Rajdhani,sans-serif")}
      {txt(INV_X+INV_W//2, INV_Y+56, "Inversor de red", 8, C_DIM)}
      {box(INV_X+10,INV_Y+66,INV_W-20,20,"#1E2A3F","#00BCD4",3)}
      {txt(INV_X+INV_W//2, INV_Y+79, "MPPT integrado", 7.5, C_DC)}
      {box(INV_X+10,INV_Y+90,INV_W-20,20,"#1E2A3F","#FFB300",3)}
      {txt(INV_X+INV_W//2, INV_Y+103, f"Rango MPPT: {mppt_v}", 7, C_SOL,"middle","normal","Share Tech Mono,monospace")}
      {box(INV_X+10,INV_Y+114,INV_W-20,20,"#1E2A3F","#00E676",3)}
      {txt(INV_X+INV_W//2, INV_Y+127, "220/380V AC · 60Hz", 7.5, C_AC)}
      {box(INV_X+10,INV_Y+138,INV_W-20,20,"#1E2A3F","#8A9BBD",3)}
      {txt(INV_X+INV_W//2, INV_Y+151, "Anti-isla / Anti-islanding", 7, C_DIM)}
      {box(INV_X+10,INV_Y+162,INV_W-20,20,"#1E2A3F","#FF6B35",3)}
      {txt(INV_X+INV_W//2, INV_Y+175, "Monitoreo WiFi/RS485", 7, C_GRID)}
      {txt(INV_X+INV_W//2, INV_Y+INV_H-14, f"η ≥ 97%  ·  THD < 3%", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")}
    </g>'''

    # ── 4. Medidor bidireccional ──────────────────────────────────────────────
    MED_X=600; MED_Y=170; MED_W=100; MED_H=120
    med_block = f'''
    <g id="medidor">
      {box(MED_X,MED_Y,MED_W,MED_H,"#0F1525","#FF6B35",6)}
      {box(MED_X,MED_Y,MED_W,20,"#1A2235","#FF6B35",6)}
      {txt(MED_X+MED_W//2, MED_Y+13, "MEDIDOR BIDIRC.", 7.5, C_GRID,"middle","700","Rajdhani,sans-serif")}
      {txt(MED_X+MED_W//2, MED_Y+35, "📟", 16)}
      {txt(MED_X+MED_W//2, MED_Y+58, "Telemedida CREG", 7, C_DIM)}
      {txt(MED_X+MED_W//2, MED_Y+70, "Generación ↑", 7, C_AC,"middle","normal","Share Tech Mono,monospace")}
      {txt(MED_X+MED_W//2, MED_Y+82, "Consumo red ↓", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {txt(MED_X+MED_W//2, MED_Y+96, "220V / 60Hz", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {txt(MED_X+MED_W//2, MED_Y+MED_H-10, "CREG 030-2018", 6.5, C_GRID)}
    </g>'''

    # ── 5. Tablero AC / cargas ────────────────────────────────────────────────
    TAC_X=600; TAC_Y=330; TAC_W=100; TAC_H=130
    tac_block = f'''
    <g id="tablero_ac">
      {box(TAC_X,TAC_Y,TAC_W,TAC_H,"#0F1525","#00E676",6)}
      {box(TAC_X,TAC_Y,TAC_W,20,"#1A2235","#00E676",6)}
      {txt(TAC_X+TAC_W//2, TAC_Y+13, "TABLERO AC", 7.5, C_AC,"middle","700","Rajdhani,sans-serif")}
      {box(TAC_X+10,TAC_Y+28,TAC_W-20,18,"#1E2A3F","#00E676",3)}
      {txt(TAC_X+TAC_W//2, TAC_Y+40, "Interruptor gral.", 7, C_AC)}
      {box(TAC_X+10,TAC_Y+50,TAC_W-20,18,"#1E2A3F","#FF5252",3)}
      {txt(TAC_X+TAC_W//2, TAC_Y+62, "Prot. diferencial", 7, "#FF5252")}
      {box(TAC_X+10,TAC_Y+72,TAC_W-20,18,"#1E2A3F","#8A9BBD",3)}
      {txt(TAC_X+TAC_W//2, TAC_Y+84, "SPD AC", 7, C_DIM)}
      {txt(TAC_X+TAC_W//2, TAC_Y+TAC_H-18, "CARGAS AC", 8, C_AC,"middle","700")}
      {txt(TAC_X+TAC_W//2, TAC_Y+TAC_H-6, f"{consumo_fs_wh/1000:.1f} kWh/día", 7, C_DIM,"middle","normal","Share Tech Mono,monospace")}
    </g>'''

    # ── 6. Red eléctrica ─────────────────────────────────────────────────────
    RED_X=790; RED_Y=155; RED_W=110; RED_H=100
    red_block = f'''
    <g id="red_electrica">
      {box(RED_X,RED_Y,RED_W,RED_H,"#0F1525","#FF6B35",8,1.5)}
      {box(RED_X,RED_Y,RED_W,22,"#FF6B35","#FF6B35",8)}
      {txt(RED_X+RED_W//2, RED_Y+14, "RED ELÉCTRICA", 8, "#0A0E1A","middle","700","Rajdhani,sans-serif")}
      {txt(RED_X+RED_W//2, RED_Y+36, "⚡", 20)}
      {txt(RED_X+RED_W//2, RED_Y+60, "220V AC · 60Hz", 8, C_GRID,"middle","600","Share Tech Mono,monospace")}
      {txt(RED_X+RED_W//2, RED_Y+74, "Operador de red", 7, C_DIM)}
      {txt(RED_X+RED_W//2, RED_Y+RED_H-10, "CREG / RETIE", 7, C_DIM)}
    </g>'''

    # ── 7. Protecciones DC/AC ─────────────────────────────────────────────────
    PR_X=380; PR_Y=390; PR_W=160; PR_H=150
    pr_block = f'''
    <g id="protecciones_og">
      {box(PR_X,PR_Y,PR_W,PR_H,"#0F1525","#8A9BBD",6)}
      {box(PR_X,PR_Y,PR_W,20,"#1A2235","#8A9BBD",6)}
      {txt(PR_X+PR_W//2, PR_Y+13, "PROTECCIONES", 7.5, C_DIM,"middle","700")}
      {box(PR_X+8,PR_Y+28,PR_W//2-12,18,"#1E2A3F","#FF5252",3)}
      {txt(PR_X+PR_W//4, PR_Y+40, "Fusible DC", 7, "#FF5252")}
      {box(PR_X+PR_W//2+4,PR_Y+28,PR_W//2-12,18,"#1E2A3F","#00E676",3)}
      {txt(PR_X+PR_W*3//4+2, PR_Y+40, "Interr. AC", 7, C_AC)}
      {box(PR_X+8,PR_Y+52,PR_W//2-12,18,"#1E2A3F","#FF5252",3)}
      {txt(PR_X+PR_W//4, PR_Y+64, "SPD DC", 7, "#FF5252")}
      {box(PR_X+PR_W//2+4,PR_Y+52,PR_W//2-12,18,"#1E2A3F","#FF5252",3)}
      {txt(PR_X+PR_W*3//4+2, PR_Y+64, "SPD AC", 7, "#FF5252")}
      {box(PR_X+8,PR_Y+76,PR_W-16,18,"#1E2A3F","#8A9BBD",3)}
      {txt(PR_X+PR_W//2, PR_Y+88, "Puesta a tierra TT/TN", 7, C_DIM)}
      {box(PR_X+8,PR_Y+100,PR_W-16,18,"#1E2A3F","#FF6B35",3)}
      {txt(PR_X+PR_W//2, PR_Y+112, "Interruptor anti-isla", 7, C_GRID)}
      {txt(PR_X+PR_W//2, PR_Y+PR_H-10, "NTC 2050 / RETIE", 6.5, C_DIM)}
    </g>'''

    # ── Cableo / conexiones ───────────────────────────────────────────────────
    wires = f'''
    <!-- Array → String combiner DC -->
    {line(ARR_X+ARR_W, ARR_Y+ARR_H*0.35, CB_X, CB_Y+CB_H*0.40, C_SOL, 2.5)}
    {line(ARR_X+ARR_W, ARR_Y+ARR_H*0.65, CB_X, CB_Y+CB_H*0.65, C_NEG, 2.5)}
    {wlbl(ARR_X+ARR_W+4, ARR_Y+ARR_H*0.35-4, f"+{v_array:.0f}V DC", C_SOL)}
    {wlbl(ARR_X+ARR_W+4, ARR_Y+ARR_H*0.65+9, "– GND", C_NEG)}
    <!-- String combiner → Inversor DC -->
    {line(CB_X+CB_W, CB_Y+CB_H//2, INV_X, INV_Y+INV_H//3, C_DC, 2.5)}
    {wlbl((CB_X+CB_W+INV_X)//2-8, CB_Y+CB_H//2-6, f"DC {v_array:.0f}V / {i_array:.1f}A", C_DC)}
    <!-- Inversor → Medidor AC -->
    {line(INV_X+INV_W, INV_Y+INV_H*0.40, MED_X, MED_Y+MED_H*0.50, C_AC, 2.5)}
    {wlbl((INV_X+INV_W+MED_X)//2-10, INV_Y+INV_H*0.40-6, "220V AC 60Hz", C_AC)}
    <!-- Medidor → Red -->
    {line(MED_X+MED_W, MED_Y+MED_H//2, RED_X, RED_Y+RED_H//2, C_GRID, 2.5)}
    {wlbl((MED_X+MED_W+RED_X)//2-20, MED_Y+MED_H//2-6, "Inyección / Importación", C_GRID)}
    <!-- Medidor → Tablero AC cargas (vertical) -->
    {line(MED_X+MED_W//2, MED_Y+MED_H, TAC_X+TAC_W//2, TAC_Y, C_AC, 2.5)}
    {wlbl(MED_X+MED_W//2+4, (MED_Y+MED_H+TAC_Y)//2, "Autoconsumo", C_AC)}
    <!-- Inversor → Protecciones -->
    {line(INV_X+INV_W//2, INV_Y+INV_H, PR_X+PR_W//2, PR_Y, C_DIM, 1.5, "4,3")}
    <!-- GND -->
    {line(INV_X+20, INV_Y+INV_H, INV_X+20, INV_Y+INV_H+40, C_GND, 1, "3,3")}
    {line(INV_X+20, INV_Y+INV_H+40, PR_X+20, INV_Y+INV_H+40, C_GND, 1, "3,3")}
    {line(PR_X+20, PR_Y+PR_H, PR_X+20, INV_Y+INV_H+40, C_GND, 1, "3,3")}
    '''

    # ── Tierra ────────────────────────────────────────────────────────────────
    GX=INV_X+20; GY=INV_Y+INV_H+40
    gnd_svg = f'''
    <g>
      {line(GX,GY,GX,GY+18,C_GND,1.5)}
      {line(GX-16,GY+18,GX+16,GY+18,C_GND,2)}
      {line(GX-10,GY+24,GX+10,GY+24,C_GND,1.5)}
      {line(GX-5,GY+30,GX+5,GY+30,C_GND,1)}
      {txt(GX,GY+42,"GND",7,C_GND)}
    </g>'''

    # ── Leyenda ───────────────────────────────────────────────────────────────
    leg_x=840; leg_y=340
    legend = f'''
    <g>
      {box(leg_x,leg_y,160,120,"#0F1525","#2A3A55",6)}
      {txt(leg_x+80,leg_y+14,"REFERENCIAS",7.5,C_DIM,"middle","700")}
      {line(leg_x+10,leg_y+28,leg_x+40,leg_y+28,C_SOL,2.5)}
      {txt(leg_x+46,leg_y+32,"Cable DC Positivo",7.5,C_TEXT,"start")}
      {line(leg_x+10,leg_y+44,leg_x+40,leg_y+44,C_NEG,2.5)}
      {txt(leg_x+46,leg_y+48,"Cable DC Negativo",7.5,C_TEXT,"start")}
      {line(leg_x+10,leg_y+60,leg_x+40,leg_y+60,C_AC,2.5)}
      {txt(leg_x+46,leg_y+64,"Cable AC 220V",7.5,C_TEXT,"start")}
      {line(leg_x+10,leg_y+76,leg_x+40,leg_y+76,C_GRID,2.5)}
      {txt(leg_x+46,leg_y+80,"Red eléctrica",7.5,C_TEXT,"start")}
      {line(leg_x+10,leg_y+92,leg_x+40,leg_y+92,C_GND,1.5,"3,3")}
      {txt(leg_x+46,leg_y+96,"Puesta a tierra",7.5,C_TEXT,"start")}
      {line(leg_x+10,leg_y+108,leg_x+40,leg_y+108,C_DIM,1.5,"4,3")}
      {txt(leg_x+46,leg_y+112,"Señal / control",7.5,C_TEXT,"start")}
    </g>'''

    # ── Título ────────────────────────────────────────────────────────────────
    tb_y = H - 68
    title_svg = f'''
    <rect x="0" y="{tb_y}" width="{W}" height="68" fill="#0F1525" stroke="#2A3A55" stroke-width="0.8"/>
    <line x1="0" y1="{tb_y}" x2="{W}" y2="{tb_y}" stroke="{C_GRID}" stroke-width="1.5"/>
    <text x="12" y="{tb_y+17}" font-family="Rajdhani,sans-serif" font-size="13"
          fill="{C_GRID}" font-weight="700">☀ DIAGRAMA UNIFILAR — SISTEMA FOTOVOLTAICO ON-GRID (INTERCONECTADO A LA RED)</text>
    <text x="12" y="{tb_y+31}" font-family="Rajdhani,sans-serif" font-size="9" fill="{C_TEXT}">
        Proyecto: {proy}  |  Municipio: {mun}  |  Config: {pan_serie}S×{n_strings}P  |  Inversor: {pot_inv_kw:.1f}kW</text>
    <text x="12" y="{tb_y+45}" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">
        Array: {n_paneles}×{pot_panel}Wp = {n_paneles*pot_panel/1000:.2f}kWp  |  Vmpp={v_array:.0f}V  |  Iarray={i_array:.1f}A  |  SolarCalc Pro ON-GRID  |  {datetime.now().strftime("%d/%m/%Y")}  |  Plano N°02</text>
    <text x="{W-12}" y="{tb_y+17}" text-anchor="end" font-family="Share Tech Mono,monospace" font-size="9" fill="{C_DIM}">Plano N°02  Rev.A</text>
    '''

    # ── Header ────────────────────────────────────────────────────────────────
    header_svg = f'''
    <rect x="0" y="0" width="{W}" height="58" fill="#0F1525"/>
    <line x1="0" y1="58" x2="{W}" y2="58" stroke="{C_GRID}" stroke-width="1.5"/>
    <text x="20" y="22" font-family="Rajdhani,sans-serif" font-size="18" fill="{C_SOL}" font-weight="700" letter-spacing="2">☀ SOLARCALC PRO</text>
    <text x="20" y="38" font-family="Barlow,sans-serif" font-size="9" fill="{C_DIM}" letter-spacing="3">SISTEMA FOTOVOLTAICO INTERCONECTADO A LA RED — ON-GRID / GRID-TIE</text>
    <text x="20" y="52" font-family="Share Tech Mono,monospace" font-size="8" fill="#2A3A55">DIAGRAMA UNIFILAR  ·  PLANO ELÉCTRICO  ·  NTC 2050 / RETIE</text>
    '''

    svg = f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
         style="background:{C_BG};border-radius:12px;width:100%;max-height:720px;">
      <defs>
        <pattern id="grid_og2" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#12192B" stroke-width="0.3"/>
        </pattern>
        <filter id="glow_og2"><feGaussianBlur stdDeviation="1.5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <rect width="{W}" height="{H-68}" fill="url(#grid_og2)"/>
      {header_svg}
      {wires}
      {arr_block}
      {cb_block}
      {inv_block}
      {med_block}
      {red_block}
      {tac_block}
      {pr_block}
      {gnd_svg}
      {legend}
      {title_svg}
    </svg>'''
    return svg


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — mostrar_ongrid()
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_ongrid(proyecto_id: int, session_state: dict) -> None:
    """Punto de entrada desde solar_app.py"""

    # ── Estilos heredados ─────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .og-badge {
        display:inline-block;background:#FF6B35;color:#0A0E1A;
        font-family:'Rajdhani',sans-serif;font-weight:700;font-size:0.75rem;
        padding:2px 10px;border-radius:20px;letter-spacing:1px;margin-left:8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>☀ SOLARCALC PRO <span class='og-badge'>ON-GRID</span></div>
        <div class='hero-sub'>DIMENSIONAMIENTO — SISTEMA FOTOVOLTAICO INTERCONECTADO A LA RED</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Leer datos del proyecto desde BD (sin depender del OFF-GRID) ──────────
    conn = get_conn()
    p_info = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    cargas_df = pd.read_sql(
        "SELECT cantidad, potencia_w, horas_dia FROM cargas WHERE proyecto_id=?",
        conn, params=(proyecto_id,))
    panel_row = conn.execute(
        "SELECT potencia_wp, voc, isc FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    # Leer último recibo de la BD directamente (no depende de session_state OFF-GRID)
    recibo_row = conn.execute(
        "SELECT kwh_periodo, dias_periodo, periodo, tarifa_kwh FROM recibos "
        "WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    conn.close()

    # Consumo desde inventario de cargas
    consumo_inv = (cargas_df["cantidad"] * cargas_df["potencia_w"] * cargas_df["horas_dia"]).sum() \
        if not cargas_df.empty else 0.0

    # Consumo desde recibo: BD tiene prioridad sobre session_state
    if recibo_row and recibo_row[0]:
        dias        = recibo_row[1] if recibo_row[1] else 30
        consumo_rec = round(float(recibo_row[0]) * 1000 / dias, 1)  # kWh/período → Wh/día
        periodo_rec = recibo_row[2] or ""
        tarifa_bd   = float(recibo_row[3]) if recibo_row[3] else 700.0
    else:
        consumo_rec = session_state.get("consumo_recibo_wh", 0.0)
        periodo_rec = session_state.get("recibo_ref_periodo", "")
        tarifa_bd   = 700.0

    hsp_guardado  = p_info[4] if p_info and p_info[4] else None
    pot_panel_def = int(panel_row[0]) if panel_row else 550
    voc_def       = float(panel_row[1]) if panel_row else 49.9
    isc_def       = float(panel_row[2]) if panel_row else 14.0


    # ── Banner de datos del proyecto ─────────────────────────────────────────
    _proy_nombre = p_info[1] if p_info else "—"
    _proy_mun    = p_info[2] if p_info and p_info[2] else "—"
    _consumo_max = max(consumo_inv, consumo_rec)
    _panel_info  = f"{pot_panel_def} Wp · Voc {voc_def}V" if panel_row else "Sin panel guardado"
    _hsp_txt     = f"{hsp_guardado} h/día" if hsp_guardado else "No guardada"
    _recibo_txt  = f"{periodo_rec} · {consumo_rec:,.0f} Wh/día" if consumo_rec > 0 else "—"
    _cargas_txt  = f"{consumo_inv:,.0f} Wh/día ({len(cargas_df)} cargas)" if consumo_inv > 0 else "—"

    st.markdown(f"""
    <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;
     padding:0.8rem 1.2rem;margin-bottom:1rem;display:grid;
     grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:0.6rem;'>
        <div>
            <div style='font-size:0.65rem;color:#8A9BBD;letter-spacing:1px;text-transform:uppercase;'>Proyecto</div>
            <div style='font-family:Rajdhani,sans-serif;font-size:1rem;color:#FFB300;font-weight:700;'>{_proy_nombre}</div>
            <div style='font-size:0.72rem;color:#8A9BBD;'>📍 {_proy_mun}</div>
        </div>
        <div>
            <div style='font-size:0.65rem;color:#8A9BBD;letter-spacing:1px;text-transform:uppercase;'>Consumo disponible</div>
            <div style='font-family:Share Tech Mono;font-size:0.95rem;color:#00E676;'>{_consumo_max:,.0f} Wh/día</div>
            <div style='font-size:0.7rem;color:#8A9BBD;'>Cargas: {_cargas_txt[:30]}</div>
        </div>
        <div>
            <div style='font-size:0.65rem;color:#8A9BBD;letter-spacing:1px;text-transform:uppercase;'>Recibo energía</div>
            <div style='font-family:Share Tech Mono;font-size:0.85rem;color:#00BCD4;'>{_recibo_txt}</div>
        </div>
        <div>
            <div style='font-size:0.65rem;color:#8A9BBD;letter-spacing:1px;text-transform:uppercase;'>Panel solar</div>
            <div style='font-family:Share Tech Mono;font-size:0.85rem;color:#FFD54F;'>{_panel_info}</div>
        </div>
        <div>
            <div style='font-size:0.65rem;color:#8A9BBD;letter-spacing:1px;text-transform:uppercase;'>HSP guardada</div>
            <div style='font-family:Share Tech Mono;font-size:0.85rem;color:#FFB300;'>{_hsp_txt}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── TABS ON-GRID ──────────────────────────────────────────────────────────
    tab_og1, tab_og2, tab_og3, tab_og4, tab_og5, tab_og6, tab_og7 = st.tabs([
        "⚡ 1 · Consumo",
        "🌞 2 · Irradiación",
        "🔆 3 · Panel",
        "📐 4 · Dimensionamiento",
        "💹 5 · Económico",
        "🔲 6 · Plano Paneles",
        "📋 7 · Diagrama Unifilar",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG1 — CONSUMO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og1:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>1</span>
        CONSUMO ENERGÉTICO DEL PROYECTO</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Para ON-GRID se usa el consumo real del recibo o el inventario de cargas.<br>
            El sistema inyecta el excedente a la red y puede importar cuando no alcanza la generación.
        </div>""", unsafe_allow_html=True)

        opciones = ["⚡ Inventario de cargas (Módulo Cargas)"]
        if consumo_rec > 0:
            opciones.append(f"🧾 Recibo de energía ({periodo_rec})")
            opciones.append("📊 Mayor de los dos (recomendado)")

        if consumo_inv == 0 and consumo_rec == 0:
            st.markdown("""
            <div class='warn-box'>
                ⚠ No hay consumo registrado para este proyecto.<br>
                Puedes registrar el consumo de dos formas:<br>
                <b>• Inventario de cargas:</b> ve al módulo <b>Dimensionamiento OFF-GRID → Tab 1 (Cargas)</b><br>
                <b>• Recibo de energía:</b> ve al módulo <b>Dimensionamiento OFF-GRID → Tab 2 (Recibo Luz)</b><br>
                Una vez guardadas las cargas o el recibo, vuelve aquí y el consumo se cargará automáticamente.
            </div>
            """, unsafe_allow_html=True)
            st.info("💡 El consumo del proyecto se comparte entre todos los sistemas "
                    "(OFF-GRID, ON-GRID e HÍBRIDO). Solo necesitas ingresarlo una vez.")
            return

        fuente = st.radio("Base de consumo:", opciones, horizontal=True, key="og_fuente")
        if "Recibo" in fuente:
            consumo_base = consumo_rec
        elif "Mayor" in fuente:
            consumo_base = max(consumo_inv, consumo_rec)
        else:
            consumo_base = consumo_inv

        consumo_fs_og = consumo_base * 1.20   # 20% FS para ON-GRID

        col1, col2, col3, col4 = st.columns(4)
        for c, val, unit, lbl, col in [
            (col1, consumo_inv, "Wh/día", "Inventario cargas", "#FFB300"),
            (col2, consumo_rec, "Wh/día", "Recibo energía", "#00BCD4"),
            (col3, consumo_base, "Wh/día", "Consumo seleccionado", "#00E676"),
            (col4, consumo_fs_og, "Wh/día", "Con 20% FS sistema", "#FF6B35"),
        ]:
            with c:
                st.markdown(f"""
                <div class='metric-box' style='border-color:rgba(0,0,0,0);border-top:2px solid {col};'>
                    <div class='metric-val' style='color:{col};'>{val:,.0f}</div>
                    <div class='metric-unit'>{unit}</div>
                    <div class='metric-label'>{lbl}</div>
                </div>""", unsafe_allow_html=True)

        session_state["_og_consumo_base"] = consumo_base
        session_state["_og_consumo_fs"]   = consumo_fs_og
        # Alias sin prefijo para compatibilidad con tabs posteriores
        session_state["og_consumo_fs"]    = consumo_fs_og

        # Mostrar nota de autonomía si viene configurada desde Tab 3
        _horas_aut_og = session_state.get("horas_autonomia_deseada", 0)
        if _horas_aut_og > 0 and "Recibo" in fuente:
            st.markdown(f"""
            <div class='info-note' style='margin-top:0.5rem;border-color:rgba(0,188,212,0.3);
                         background:rgba(0,188,212,0.05);'>
                🔋 Autonomía configurada en Módulo 2: <b style='color:#00BCD4;'>
                {_horas_aut_og:.0f} horas ({_horas_aut_og/24:.2f} días)</b> —
                se usará en OFF-GRID/Híbrido. ON-GRID no requiere baterías
                (la red actúa como respaldo).
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='info-note' style='margin-top:1rem;'>
            ℹ En sistemas ON-GRID se aplica solo <b>20% de factor de seguridad</b>
            (pérdidas de temperatura, cableado, suciedad y rendimiento inversor),
            ya que la red eléctrica cubre cualquier déficit en tiempo real.
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG2 — IRRADIACIÓN / HSP
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og2:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>2</span>
        HORA SOLAR PICO (HSP) E IRRADIACIÓN</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            HSP = Irradiación mes promedio (kWh/m²/mes) ÷ 30 días<br>
            Para ON-GRID se recomienda usar el promedio anual (no el mes menor),
            ya que la red compensa los déficits mensuales.
        </div>""", unsafe_allow_html=True)

        col_hsp1, col_hsp2 = st.columns(2)
        with col_hsp1:
            st.markdown("""
            <div class='sol-card'>
                <div style='color:#FFB300;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.8rem;'>
                    🌐 Fuentes de Irradiación Recomendadas
                </div>
                <div style='font-size:0.85rem;color:#8A9BBD;line-height:1.9;'>
                    <b style='color:#E8EDF5;'>PVGIS (Europa JRC)</b><br>
                    https://re.jrc.ec.europa.eu/pvg_tools/es/<br><br>
                    <b style='color:#E8EDF5;'>SolarGIS</b><br>
                    https://solargis.com/maps-and-gis-data<br><br>
                    <b style='color:#E8EDF5;'>NASA POWER</b><br>
                    https://power.larc.nasa.gov/data-access-viewer/<br><br>
                    <b style='color:#FF6B35;'>💡 Para ON-GRID:</b>
                    <span style='color:#8A9BBD;'>Usa el promedio anual,
                    no el mes con menor irradiación.</span>
                </div>
            </div>""", unsafe_allow_html=True)

        with col_hsp2:
            # HSP válida: entre 1.0 y 8.0 h/día. Si viene un valor fuera de rango
            # (ej: tensión DC guardada en el campo HSP), se ignora y usa 150 kWh/m²/mes
            _hsp_val     = float(hsp_guardado) if hsp_guardado else 0.0
            _hsp_valida  = 1.0 <= _hsp_val <= 8.0
            _irr_def_og  = round(_hsp_val * 30, 1) if _hsp_valida else 150.0
            _irr_def_og  = max(50.0, min(_irr_def_og, 300.0))   # clamp seguro
            irr_og = st.number_input(
                "Irradiación promedio anual (kWh/m²/mes)",
                min_value=50.0, max_value=300.0,
                value=_irr_def_og, step=0.5,
                help="Pre-cargado desde la HSP del proyecto. Ajusta según PVGIS o NASA POWER.",
                key="og_irr")
            hsp_og = irr_og / 30

            pr_og = st.slider(
                "Performance Ratio PR (%)", 70, 90, 80,
                help="Eficiencia global del sistema. Típico: 75-85% para sistemas residenciales.",
                key="og_pr")

            hsp_efectiva = hsp_og * (pr_og / 100)

            st.markdown(f"""
            <div class='result-highlight'>
                <div style='color:#8A9BBD;font-size:0.8rem;'>
                    {irr_og} kWh/m²/mes ÷ 30 =
                </div>
                <div class='val'>{hsp_og:.2f} h/día (HSP)</div>
                <div style='color:#FFD54F;font-size:0.85rem;margin-top:0.3rem;'>
                    HSP efectiva (×PR {pr_og}%) = <b>{hsp_efectiva:.2f} h/día</b>
                </div>
            </div>""", unsafe_allow_html=True)

            if st.button("💾 Guardar HSP al Proyecto", use_container_width=True, key="og_save_hsp"):
                conn = get_conn()
                conn.execute("UPDATE proyectos SET hsp=? WHERE id=?", (round(hsp_og,2), proyecto_id))
                conn.commit(); conn.close()
                st.success(f"HSP = {hsp_og:.2f} h guardado ✓")

            if hsp_guardado:
                st.markdown(f"""
                <div class='info-note' style='margin-top:0.5rem;'>
                    ✓ HSP guardado en proyecto: <b>{hsp_guardado} h</b>
                </div>""", unsafe_allow_html=True)

        # Solo guardamos valores DERIVADOS (no son keys de widgets)
        session_state["_og_hsp_calc"]    = hsp_og
        session_state["_og_hsp_ef"]      = hsp_efectiva
        session_state["_og_pr_dec"]      = pr_og / 100

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG3 — PANEL SOLAR
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og3:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>3</span>
        PARÁMETROS DEL PANEL SOLAR</div>""", unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            og_modelo = st.text_input("Modelo", placeholder="Canadian Solar CS6W-550T",
                                       value=panel_row[0] if panel_row else "", key="og_modelo") \
                        if panel_row and len(panel_row) > 0 else \
                        st.text_input("Modelo", placeholder="Canadian Solar CS6W-550T", key="og_modelo2")
            og_wp     = st.number_input("Potencia pico (Wp)", 50, 1000, pot_panel_def, key="og_wp")
            og_voc    = st.number_input("Tensión Voc (V)", 5.0, 100.0, voc_def, step=0.1, key="og_voc")
            og_vmpp   = st.number_input("Tensión Vmpp (V)", 5.0, 80.0,
                                         round(voc_def * 0.82, 1), step=0.1, key="og_vmpp")
            og_isc    = st.number_input("Corriente Isc (A)", 0.1, 30.0, isc_def, step=0.1, key="og_isc")
            og_impp   = st.number_input("Corriente Impp (A)", 0.1, 25.0,
                                         round(isc_def * 0.95, 1), step=0.1, key="og_impp")

            if st.button("💾 Guardar Panel", use_container_width=True, key="og_save_panel"):
                conn = get_conn()
                conn.execute("DELETE FROM paneles WHERE proyecto_id=?", (proyecto_id,))
                conn.execute("INSERT INTO paneles(proyecto_id,modelo,potencia_wp,voc,isc) VALUES(?,?,?,?,?)",
                             (proyecto_id,
                              st.session_state.get("og_modelo", og_modelo),
                              og_wp, og_voc, og_isc))
                conn.commit(); conn.close()
                st.success("Panel guardado ✓"); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_p2:
            impp_calc = og_wp / og_vmpp if og_vmpp > 0 else 0
            st.markdown(f"""
            <div class='sol-card'>
                <div style='color:#FFB300;font-family:Rajdhani,sans-serif;font-weight:600;
                            margin-bottom:1rem;font-size:1.1rem;'>FICHA TÉCNICA</div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.8rem;'>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#FFB300;'>{og_wp}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>Wp — POTENCIA PICO</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#00BCD4;'>{og_voc}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>V — Voc</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#FFD54F;'>{og_vmpp}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>V — Vmpp</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#00E676;'>{og_impp:.1f}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>A — Impp</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        # og_wp, og_voc, og_vmpp, og_isc, og_impp ya están en session_state
        # automáticamente porque son keys de widgets — no se deben re-escribir aquí.

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG4 — DIMENSIONAMIENTO ON-GRID
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og4:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>4</span>
        DIMENSIONAMIENTO DEL SISTEMA ON-GRID</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Pot. array (kWp) = Consumo/día (kWh) ÷ (HSP × PR)<br>
            Paneles = Pot. array / Pot. panel  |  Inversor ≈ 80–100% de la potencia del array<br>
            Strings en serie: Vmpp_string dentro del rango MPPT del inversor
        </div>""", unsafe_allow_html=True)

        # Leer valores desde session_state (escritos automáticamente por los widgets del Tab 3)
        # y desde las claves derivadas del Tab 2 (prefijo _og_)
        consumo_og = session_state.get("og_consumo_fs",
                        session_state.get("_og_consumo_fs", consumo_inv * 1.20))
        hsp_og_use = session_state.get("_og_hsp_calc", hsp_guardado or 4.2)
        pr_og_use  = session_state.get("og_pr", 80)          # valor bruto del slider (int)
        wp_og_use  = session_state.get("og_wp", pot_panel_def)
        voc_use    = session_state.get("og_voc", voc_def)
        vmpp_use   = session_state.get("og_vmpp", round(voc_def * 0.82, 1))
        impp_use   = session_state.get("og_impp", round(isc_def * 0.95, 1))

        if consumo_og == 0:
            st.markdown("<div class='warn-box'>⚠ Registra el consumo en el Tab 1 primero.</div>",
                        unsafe_allow_html=True)
            return

        col_d1, col_d2 = st.columns([1, 1.2])
        with col_d1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            st.markdown("**Parámetros de cálculo**")
            consumo_input = st.number_input(
                "Consumo diario base (Wh/día)", min_value=100.0,
                value=float(consumo_og / 1.20) if consumo_og > 0 else 1000.0,
                step=100.0, key="og_consumo_input",
                help="Consumo real sin factor de seguridad. Fórmula: Paneles = Consumo/(HSP×PR)")
            hsp_input = st.number_input(
                "HSP (h/día)", min_value=0.5, max_value=12.0,
                value=float(hsp_og_use), step=0.01, key="og_hsp_input")
            pr_input  = st.slider("Performance Ratio PR (%)", 70, 90,
                                   int(pr_og_use) if isinstance(pr_og_use, (int,float)) else 80,
                                   key="og_pr_d4")
            wp_input  = st.number_input(
                "Potencia panel (Wp)", 50, 1000, wp_og_use, key="og_wp_input")
            vmpp_input = st.number_input(
                "Vmpp panel (V)", 5.0, 80.0, float(vmpp_use), step=0.1, key="og_vmpp_inp")
            voc_input  = st.number_input(
                "Voc panel (V)", 5.0, 100.0, float(voc_use), step=0.1, key="og_voc_inp")
            impp_input = st.number_input(
                "Impp panel (A)", 0.1, 25.0, float(impp_use), step=0.1, key="og_impp_inp")

            # Rango MPPT del inversor
            st.markdown("<hr style='border-color:#2A3A55;margin:0.6rem 0;'>", unsafe_allow_html=True)
            st.markdown("<small style='color:#8A9BBD;'>Rango MPPT del inversor:</small>",
                        unsafe_allow_html=True)
            v_mppt_min = st.number_input(
                "V MPPT mínimo (V)", 50, 400, 200, key="og_vmppt_min")
            v_mppt_max = st.number_input(
                "V MPPT máximo (V)", 200, 1500, 800, key="og_vmppt_max")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_d2:
            # Calcular
            pr_dec = pr_input / 100.0
            # ON-GRID: Pot_array = Consumo_kWh / (HSP × PR)  — sin factor baterías
            consumo_kwh_calc = consumo_input / 1000.0
            pot_array_kw   = consumo_kwh_calc / (hsp_input * pr_dec) if (hsp_input * pr_dec) > 0 else 0
            pot_array_wp   = pot_array_kw * 1000
            n_pan          = math.ceil(pot_array_wp / wp_input)
            pot_inst       = n_pan * wp_input

            # ── String design ─────────────────────────────────────────────
            # Rango de paneles en serie según voltajes MPPT del inversor
            pan_serie_min = max(1, math.ceil(v_mppt_min / vmpp_input)) if vmpp_input > 0 else 1
            pan_serie_max_mppt = math.floor(v_mppt_max / vmpp_input)         if vmpp_input > 0 else 20
            pan_serie_max_voc  = math.floor((v_mppt_max * 1.15) / voc_input) if voc_input  > 0 else 20
            pan_serie_max = max(min(pan_serie_max_mppt, pan_serie_max_voc), pan_serie_min)

            # Objetivo: encontrar (serie, paralelo) tal que serie × paralelo == n_pan
            # Si no existe divisor exacto dentro del rango, buscar el que menos paneles agrega
            pan_serie  = 1
            n_strings  = n_pan
            best_extra = 10_000   # penalización por paneles extra

            for s in range(pan_serie_min, pan_serie_max + 1):
                p = math.ceil(n_pan / s)        # strings necesarios
                total = s * p
                extra = total - n_pan           # paneles "sobrantes"
                # Preferir combinación con menos sobrantes; desempate: más cuadrada
                if extra < best_extra or (extra == best_extra and abs(s - p) < abs(pan_serie - n_strings)):
                    best_extra = extra
                    pan_serie  = s
                    n_strings  = p

            # Si pan_serie_min > n_pan (pocos paneles para el rango MPPT)
            # usar 1 string con todos los paneles en serie
            if pan_serie_min > n_pan:
                pan_serie = n_pan
                n_strings = 1

            n_pan_real    = pan_serie * n_strings   # igual o muy cerca de n_pan
            pot_inst_real = n_pan_real * wp_input

            v_string_mpp = pan_serie * vmpp_input
            v_string_oc  = pan_serie * voc_input
            i_array      = impp_input * n_strings

            # Inversor recomendado
            _inv_w_og = pot_inst_real * 1.2
            _kw_std_og = [1,2,3,5,8,10,15,20,25,30,40,50]
            pot_inv_kw = float(next((k for k in _kw_std_og if k*1000 >= _inv_w_og),
                                    math.ceil(_inv_w_og/1000)))

            # Guardar resultados calculados con prefijo seguro (no son keys de widgets)
            session_state["_og_n_paneles"]  = n_pan_real
            session_state["_og_pan_serie"]  = pan_serie
            session_state["_og_n_strings"]  = n_strings
            session_state["_og_pot_inst"]   = pot_inst_real
            session_state["_og_v_str_mpp"]  = v_string_mpp
            session_state["_og_v_str_oc"]   = v_string_oc
            session_state["_og_i_array"]    = i_array
            session_state["_og_pot_inv_kw"] = pot_inv_kw

            st.markdown(f"""
            <div class='sol-card' style='border-color:rgba(255,107,53,0.4);margin-bottom:0.8rem;'>
                <div style='color:#FFB300;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.6rem;'>
                    FÓRMULA ON-GRID</div>
                <table style='width:100%;font-size:0.83rem;border-collapse:collapse;'>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.35rem 0;'>Consumo diario</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{consumo_input/1000:.3f} kWh</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.35rem 0;'>HSP × PR ({pr_input}%)</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{hsp_input} × {pr_dec:.2f} = {hsp_input*pr_dec:.2f} h ef.</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'>
                        <td style='color:#FF6B35;padding:0.35rem 0;font-weight:600;'>Pot. array mínima</td>
                        <td style='font-family:Share Tech Mono;color:#FF6B35;text-align:right;font-weight:700;'>{pot_array_wp/1000:.3f} kWp</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.35rem 0;'>{pot_array_wp:.0f} W ÷ {wp_input} Wp/panel</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{pot_array_wp/wp_input:.2f} → ↑ {n_pan} paneles</td>
                    </tr>
                    <tr style='background:#0D1B2A;'>
                        <td style='color:#8A9BBD;padding:0.35rem 0;'>Configuración strings</td>
                        <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{pan_serie}S × {n_strings}P = {n_pan_real} paneles{"" if n_pan_real == n_pan else f" (+{n_pan_real-n_pan})"}</td>
                    </tr>
                </table>
            </div>
            <div class='metric-grid'>
                <div class='metric-box' style='border-color:rgba(255,179,0,0.5);'>
                    <div class='metric-val'>{n_pan_real}</div>
                    <div class='metric-unit'>paneles</div>
                    <div class='metric-label'>CANT. TOTAL</div>
                </div>
                <div class='metric-box'>
                    <div class='metric-val'>{pot_inst_real/1000:.2f}</div>
                    <div class='metric-unit'>kWp</div>
                    <div class='metric-label'>POT. INSTALADA</div>
                </div>
                <div class='metric-box' style='border-color:rgba(0,188,212,0.5);'>
                    <div class='metric-val'>{pan_serie}S × {n_strings}P</div>
                    <div class='metric-unit'>config.</div>
                    <div class='metric-label'>STRINGS</div>
                </div>
                <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                    <div class='metric-val'>{pot_inv_kw}</div>
                    <div class='metric-unit'>kW</div>
                    <div class='metric-label'>INVERSOR REC.</div>
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div class='sol-card' style='margin-top:1rem;'>
                <div style='color:#FFB300;font-family:Rajdhani,sans-serif;font-weight:600;
                            margin-bottom:0.8rem;'>PARÁMETROS ELÉCTRICOS DEL ARRAY</div>
                <table style='width:100%;font-size:0.83rem;border-collapse:collapse;'>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Paneles en serie / string</td>
                        <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{pan_serie}</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Strings en paralelo</td>
                        <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{n_strings}</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Vmpp string</td>
                        <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{v_string_mpp:.1f} V</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Voc string (máx. riesgo)</td>
                        <td style='font-family:Share Tech Mono;color:#FF5252;text-align:right;'>{v_string_oc:.1f} V</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Corriente total array</td>
                        <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{i_array:.1f} A</td>
                    </tr>
                    <tr>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Dentro rango MPPT</td>
                        <td style='font-family:Share Tech Mono;text-align:right;
                             color:{"#00E676" if v_mppt_min <= v_string_mpp <= v_mppt_max else "#FF5252"};'>
                            {"✓ SÍ" if v_mppt_min <= v_string_mpp <= v_mppt_max else "✗ REVISAR"}</td>
                    </tr>
                </table>
            </div>""", unsafe_allow_html=True)

            if not (v_mppt_min <= v_string_mpp <= v_mppt_max):
                st.markdown(f"""
                <div class='warn-box'>⚠ Vmpp string ({v_string_mpp:.1f}V) fuera del rango MPPT
                ({v_mppt_min}–{v_mppt_max}V). Ajusta el número de paneles en serie o el inversor.</div>
                """, unsafe_allow_html=True)

            # ── PRODUCCIÓN ESTIMADA ──────────────────────────────────────
            gen_dia_og4  = (pot_inst_real / 1000) * hsp_input * pr_dec   # kWh/día
            gen_mes_og4  = gen_dia_og4 * 30                               # kWh/mes
            gen_anio_og4 = gen_dia_og4 * 365                              # kWh/año
            consumo_mes  = (consumo_input / 1000) * 30                    # kWh/mes
            consumo_anio = consumo_mes * 12
            cobertura_pct = min(gen_mes_og4 / consumo_mes * 100, 100) if consumo_mes > 0 else 0
            excedente_mes = max(0, gen_mes_og4 - consumo_mes)
            deficit_mes   = max(0, consumo_mes - gen_mes_og4)
            cob_color     = "#00E676" if cobertura_pct >= 100 else ("#FFB300" if cobertura_pct >= 80 else "#FF5252")

            st.markdown(f"""
            <div class='sol-card' style='margin-top:1rem;border-color:rgba(0,230,118,0.4);'>
                <div style='color:#00E676;font-family:Rajdhani,sans-serif;font-weight:600;
                            margin-bottom:0.8rem;'>⚡ PRODUCCIÓN ESTIMADA</div>

                <!-- Fórmula paso a paso -->
                <div style='background:#0D1B2A;border-radius:6px;padding:0.6rem 0.8rem;
                            margin-bottom:0.8rem;font-size:0.82rem;color:#8A9BBD;'>
                    <b style='color:#FFD54F;'>{pot_inst_real/1000:.2f} kWp</b>
                    &nbsp;×&nbsp;<b style='color:#FFD54F;'>{hsp_input} HSP</b>
                    &nbsp;×&nbsp;<b style='color:#FFD54F;'>{pr_dec:.2f} PR</b>
                    &nbsp;=&nbsp;<b style='color:#00E676;font-size:0.95rem;'>{gen_dia_og4:.2f} kWh/día</b>
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    ×30 =&nbsp;<b style='color:#00E676;font-size:0.95rem;'>{gen_mes_og4:.1f} kWh/mes</b>
                </div>

                <table style='width:100%;font-size:0.85rem;border-collapse:collapse;'>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Generación diaria</td>
                        <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;
                                   font-weight:700;'>{gen_dia_og4:.2f} kWh/día</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Generación mensual</td>
                        <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;
                                   font-weight:700;'>{gen_mes_og4:.1f} kWh/mes</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Generación anual</td>
                        <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>{gen_anio_og4:.0f} kWh/año</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;'>Consumo mensual</td>
                        <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{consumo_mes:.1f} kWh/mes</td>
                    </tr>
                    <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'>
                        <td style='color:#8A9BBD;padding:0.4rem 0;font-weight:600;'>Cobertura</td>
                        <td style='font-family:Share Tech Mono;text-align:right;font-weight:700;
                                   font-size:1rem;color:{cob_color};'>{cobertura_pct:.1f}%</td>
                    </tr>
                    {f"<tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;padding:0.4rem 0;'>Excedente inyección red</td><td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{excedente_mes:.1f} kWh/mes</td></tr>" if excedente_mes > 0 else ""}
                    {f"<tr><td style='color:#8A9BBD;padding:0.4rem 0;'>Déficit cubierto por red</td><td style='font-family:Share Tech Mono;color:#FF5252;text-align:right;'>{deficit_mes:.1f} kWh/mes</td></tr>" if deficit_mes > 0 else ""}
                </table>

                <!-- Badge de cobertura -->
                <div style='margin-top:0.7rem;padding:0.5rem 0.8rem;border-radius:6px;
                            background:rgba(0,230,118,0.08);border:1px solid rgba(0,230,118,0.25);
                            font-size:0.83rem;color:#8A9BBD;'>
                    {"✅ <b style='color:#00E676;'>Cubre completamente</b> los " if cobertura_pct >= 100 else "⚠ <b style='color:#FFB300;'>Cubre parcialmente</b> los "}
                    <b style='color:#FFD54F;'>{consumo_mes:.1f} kWh/mes</b>
                    {"— inyecta " + f"<b style='color:#00BCD4;'>{excedente_mes:.1f} kWh/mes</b> a la red." if excedente_mes > 0 else
                     f" — la red aporta <b style='color:#FF5252;'>{deficit_mes:.1f} kWh/mes</b>."}
                </div>
            </div>
            """, unsafe_allow_html=True)

            session_state["_og_gen_dia_kwh"]  = gen_dia_og4
            session_state["_og_gen_mes_kwh"]  = gen_mes_og4
            session_state["_og_gen_anio"]     = gen_anio_og4

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG5 — ANÁLISIS ECONÓMICO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og5:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>5</span>
        ANÁLISIS ECONÓMICO Y AMBIENTAL</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Ahorro mensual = Autoconsumo (kWh/día × 30) × Tarifa ($/kWh)<br>
            Ingreso inyección = Excedente × Precio de compra red (≈ 50% tarifa)<br>
            Payback = Inversión total ÷ Beneficio anual
        </div>""", unsafe_allow_html=True)

        consumo_og2    = session_state.get("og_consumo_fs", consumo_inv * 1.20)
        hsp_og2        = session_state.get("_og_hsp_calc", hsp_guardado or 4.2)
        pr_og2         = session_state.get("og_pr_d4", session_state.get("og_pr", 80)) / 100
        pot_inst_og2   = session_state.get("_og_pot_inst", 0.0)
        n_pan_og2      = session_state.get("_og_n_paneles", 0)
        pot_inv_og2    = session_state.get("_og_pot_inv_kw", 3.0)

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            tarifa_kwh = st.number_input(
                "Tarifa energía ($/kWh)", min_value=100.0, max_value=5000.0,
                value=tarifa_bd, step=50.0,
                help="Pre-cargada desde el recibo del proyecto. Tarifa Colombia: ~$600–$900/kWh", key="og_tarifa")
            precio_panel = st.number_input(
                "Precio panel solar ($/unidad)", min_value=50000.0, max_value=2000000.0,
                value=320000.0, step=10000.0, key="og_precio_panel")
            costo_inv_kw = st.number_input(
                "Costo inversor ($/kW)", min_value=500000.0, max_value=10000000.0,
                value=2000000.0, step=100000.0, key="og_costo_inv")
            otros_costos = st.number_input(
                "Otros costos (estructura, cableado, mano de obra) ($)",
                min_value=0.0, max_value=50000000.0, value=1500000.0,
                step=100000.0, key="og_otros")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_e2:
            if pot_inst_og2 == 0 or consumo_og2 == 0:
                st.markdown("""
                <div class='warn-box'>⚠ Completa los módulos 1 y 4 primero.</div>
                """, unsafe_allow_html=True)
            else:
                # Generación
                gen_dia = (pot_inst_og2 / 1000) * hsp_og2 * pr_og2
                gen_mes = gen_dia * 30
                gen_anio = gen_dia * 365
                consumo_dia_kwh = consumo_og2 / 1000
                autoconsumo = min(gen_dia, consumo_dia_kwh)
                inyeccion   = max(0, gen_dia - consumo_dia_kwh)
                deficit     = max(0, consumo_dia_kwh - gen_dia)
                autoconsumo_pct = autoconsumo / consumo_dia_kwh * 100 if consumo_dia_kwh > 0 else 0

                # Economía
                ahorro_mes    = autoconsumo * 30 * tarifa_kwh
                ing_iny_mes   = inyeccion * 30 * tarifa_kwh * 0.5
                beneficio_mes = ahorro_mes + ing_iny_mes
                beneficio_anio = beneficio_mes * 12

                # Inversión
                inv_paneles = n_pan_og2 * precio_panel
                inv_inv     = pot_inv_og2 * costo_inv_kw
                inv_total   = inv_paneles + inv_inv + otros_costos
                payback     = inv_total / beneficio_anio if beneficio_anio > 0 else 99
                tir_aprox   = (beneficio_anio / inv_total) * 100   # simplificado

                # CO2
                co2_anio = gen_anio * 0.126   # Colombia: 0.126 kgCO2/kWh

                st.markdown(f"""
                <div class='metric-grid'>
                    <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                        <div class='metric-val' style='color:#00E676;'>{gen_dia:.2f}</div>
                        <div class='metric-unit'>kWh/día</div><div class='metric-label'>GENERACIÓN EST.</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(255,107,53,0.5);'>
                        <div class='metric-val' style='color:#FF6B35;'>{autoconsumo_pct:.0f}%</div>
                        <div class='metric-unit'>autoconsumo</div><div class='metric-label'>COBERTURA</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(255,179,0,0.5);'>
                        <div class='metric-val'>${beneficio_mes:,.0f}</div>
                        <div class='metric-unit'>$/mes</div><div class='metric-label'>BENEFICIO MES</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                        <div class='metric-val' style='color:#00E676;'>{payback:.1f}</div>
                        <div class='metric-unit'>años</div><div class='metric-label'>PAYBACK</div>
                    </div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""
                <div class='sol-card' style='margin-top:0.8rem;'>
                    <div style='color:#FF6B35;font-family:Rajdhani,sans-serif;font-weight:600;
                                margin-bottom:0.8rem;'>RESUMEN FINANCIERO</div>
                    <table style='width:100%;font-size:0.83rem;border-collapse:collapse;'>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>Inversión paneles</td>
                            <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${inv_paneles:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>Inversión inversor</td>
                            <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${inv_inv:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>Otros (estructura+cableado)</td>
                            <td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${otros_costos:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'>
                            <td style='color:#FFB300;padding:0.4rem 0;font-weight:600;'>Inversión total</td>
                            <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;font-weight:700;'>${inv_total:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>Ahorro mensual (autoconsumo)</td>
                            <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>${ahorro_mes:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>Ingreso inyección red</td>
                            <td style='font-family:Share Tech Mono;color:#FF6B35;text-align:right;'>${ing_iny_mes:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'>
                            <td style='color:#00E676;padding:0.4rem 0;font-weight:600;'>Beneficio mensual total</td>
                            <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;font-weight:700;'>${beneficio_mes:,.0f}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>CO₂ evitado / año</td>
                            <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{co2_anio:.0f} kg</td>
                        </tr>
                        <tr>
                            <td style='color:#8A9BBD;padding:0.4rem 0;'>TIR simplificada</td>
                            <td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{tir_aprox:.1f}% / año</td>
                        </tr>
                    </table>
                </div>""", unsafe_allow_html=True)

                session_state["_og_inv_total"]      = inv_total
                session_state["_og_beneficio_anio"] = beneficio_anio
                session_state["_og_payback"]        = payback
                session_state["_og_gen_anio"]       = gen_anio
                session_state["_og_co2_anio"]       = co2_anio

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG6 — PLANO DISTRIBUCIÓN PANELES
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og6:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>6</span>
        PLANO — DISTRIBUCIÓN DE PANELES ON-GRID</div>""", unsafe_allow_html=True)

        n_pan_p6  = session_state.get("_og_n_paneles", 0)
        pan_s_p6  = session_state.get("_og_pan_serie", 6)
        n_str_p6  = session_state.get("_og_n_strings", 1)
        wp_p6     = session_state.get("og_wp", pot_panel_def)

        if n_pan_p6 == 0:
            st.markdown("<div class='warn-box'>⚠ Completa el dimensionamiento en el Tab 4 primero.</div>",
                        unsafe_allow_html=True)
        else:
            conn = get_conn()
            p_info6 = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
            conn.close()

            svg6 = svg_plano_paneles_og(n_pan_p6, pan_s_p6, n_str_p6, wp_p6, p_info6)
            render_svg_og(svg6, height=720)

            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            cols_leg = st.columns(3)
            with cols_leg[0]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    ARRAY ON-GRID</div>
                    <div style='font-size:0.82rem;line-height:1.9;'>
                        🔆 Paneles totales: <b style='color:#FFD54F;'>{n_pan_p6}</b><br>
                        📐 Configuración: <b style='color:#FFD54F;'>{pan_s_p6}S × {n_str_p6}P</b><br>
                        ⚡ Potencia panel: <b style='color:#FFD54F;'>{wp_p6} Wp</b><br>
                        🏭 Pot. instalada: <b style='color:#FFD54F;'>{n_pan_p6*wp_p6/1000:.2f} kWp</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols_leg[1]:
                arr_cols = min(pan_s_p6, 18)
                arr_rows = math.ceil(n_pan_p6 / arr_cols)
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    DIMENSIONES</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        Columnas: <b style='color:#FFD54F;'>{arr_cols} paneles</b><br>
                        Filas: <b style='color:#FFD54F;'>{arr_rows} strings</b><br>
                        Ancho: <b style='color:#00BCD4;'>≈{arr_cols*1.134:.2f} m</b><br>
                        Alto: <b style='color:#00BCD4;'>≈{arr_rows*0.686:.2f} m</b><br>
                        Área: <b style='color:#00E676;'>≈{arr_cols*1.134*arr_rows*0.686:.1f} m²</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols_leg[2]:
                v_str = session_state.get("_og_v_str_mpp", pan_s_p6 * session_state.get("og_vmpp", 40.0))
                i_arr = session_state.get("_og_i_array",   n_str_p6 * session_state.get("og_impp", 13.0))
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    ELÉCTRICO</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        Vmpp string: <b style='color:#00BCD4;'>{v_str:.0f} V</b><br>
                        Iarray total: <b style='color:#00BCD4;'>{i_arr:.1f} A</b><br>
                        Tipo: <b style='color:#FF6B35;'>ON-GRID / Grid-Tie</b><br>
                        Norm: <b style='color:#8A9BBD;'>NTC 2050 / RETIE</b>
                    </div>
                </div>""", unsafe_allow_html=True)

            fname_svg6 = f"PlanoONGRID_Paneles_{(p_info6[1] if p_info6 else 'Proyecto').replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.svg"
            st.download_button("⬇ Descargar Plano Paneles (SVG)",
                               data=svg6.encode(), file_name=fname_svg6,
                               mime="image/svg+xml", use_container_width=True, key="og_dl_pan_svg")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB OG7 — DIAGRAMA UNIFILAR ON-GRID
    # ══════════════════════════════════════════════════════════════════════════
    with tab_og7:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>7</span>
        DIAGRAMA UNIFILAR — SISTEMA ON-GRID</div>""", unsafe_allow_html=True)

        n_pan_p7  = session_state.get("_og_n_paneles", 0)
        pan_s_p7  = session_state.get("_og_pan_serie", 6)
        n_str_p7  = session_state.get("_og_n_strings", 1)
        wp_p7     = session_state.get("og_wp", pot_panel_def)
        pot_inv_p7= session_state.get("_og_pot_inv_kw", 3.0)
        v_str_p7  = session_state.get("_og_v_str_mpp", pan_s_p7 * session_state.get("og_vmpp", 40.0))
        v_oc_p7   = session_state.get("_og_v_str_oc",  pan_s_p7 * session_state.get("og_voc", voc_def))
        i_arr_p7  = session_state.get("_og_i_array",   n_str_p7 * session_state.get("og_impp", 13.0))
        consumo_p7= session_state.get("og_consumo_fs", consumo_inv * 1.20)
        hsp_p7    = session_state.get("_og_hsp_calc", hsp_guardado or 4.2)

        if n_pan_p7 == 0:
            st.markdown("<div class='warn-box'>⚠ Completa el dimensionamiento en el Tab 4 primero.</div>",
                        unsafe_allow_html=True)
        else:
            conn = get_conn()
            p_info7 = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
            conn.close()

            svg7 = svg_diagrama_unifilar_og(
                n_pan_p7, pan_s_p7, n_str_p7, wp_p7, pot_inv_p7,
                v_str_p7, v_oc_p7, i_arr_p7, consumo_p7, hsp_p7, p_info7)
            render_svg_og(svg7, height=740)

            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            cols7 = st.columns(3)
            with cols7[0]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    COMPONENTES ON-GRID</div>
                    <div style='font-size:0.82rem;line-height:1.9;'>
                        🔆 Array FV: <b style='color:#FFD54F;'>{n_pan_p7} × {wp_p7}Wp</b><br>
                        🔌 Caja combiner DC: <b style='color:#FFD54F;'>{n_str_p7} strings</b><br>
                        🔄 Inversor grid-tie: <b style='color:#FFD54F;'>{pot_inv_p7:.1f} kW</b><br>
                        📟 Medidor bidireccional: <b style='color:#FF6B35;'>CREG 030-2018</b><br>
                        🛡 Protecciones: <b style='color:#FFD54F;'>DC+AC+SPD+Tierra</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols7[1]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    PARÁMETROS ELÉCTRICOS</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        Vmpp string: <b style='color:#00BCD4;'>{v_str_p7:.0f} V DC</b><br>
                        Voc string: <b style='color:#FF5252;'>{v_oc_p7:.0f} V DC</b><br>
                        Corriente array: <b style='color:#00BCD4;'>{i_arr_p7:.1f} A</b><br>
                        Salida inversor: <b style='color:#00E676;'>220V AC 60Hz</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols7[2]:
                gen_anio_p7 = session_state.get("_og_gen_anio", 0)
                co2_p7      = session_state.get("_og_co2_anio", 0)
                payback_p7  = session_state.get("_og_payback", 0)
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#FF6B35;font-weight:600;margin-bottom:0.6rem;'>
                    INDICADORES</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        Gen. anual: <b style='color:#FFD54F;'>{gen_anio_p7:,.0f} kWh</b><br>
                        CO₂ evitado: <b style='color:#00E676;'>{co2_p7:,.0f} kg/año</b><br>
                        Payback: <b style='color:#FF6B35;'>{payback_p7:.1f} años</b><br>
                        HSP: <b style='color:#FFD54F;'>{hsp_p7:.2f} h/día</b>
                    </div>
                </div>""", unsafe_allow_html=True)

            fname_svg7 = f"UnifiliarONGRID_{(p_info7[1] if p_info7 else 'Proyecto').replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.svg"
            st.download_button("⬇ Descargar Diagrama Unifilar (SVG)",
                               data=svg7.encode(), file_name=fname_svg7,
                               mime="image/svg+xml", use_container_width=True, key="og_dl_uni_svg")

    # ── Footer ON-GRID ────────────────────────────────────────────────────────
    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem;color:#2A3A55;font-size:0.75rem;letter-spacing:2px;'>
        SOLARCALC PRO · DIMENSIONAMIENTO FOTOVOLTAICO ON-GRID · CREG 030-2018 · RETIE · NTC 2050
    </div>""", unsafe_allow_html=True)
