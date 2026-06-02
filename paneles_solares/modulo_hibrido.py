# modulo_hibrido.py — SolarCalc Pro · Sistema Fotovoltaico HÍBRIDO
# ─────────────────────────────────────────────────────────────────────────────
"""
Dimensionamiento de sistema fotovoltaico HÍBRIDO:
  • Combina generación solar (ON-GRID) + banco de baterías (OFF-GRID backup)
  • Inversor híbrido con MPPT integrado + cargador de baterías
  • Operación en 4 modos: Solar puro, Solar+Red, Solar+Batería, Red+Batería
  • Análisis de autonomía, autoconsumo, inyección y payback
  • Planos: distribución paneles + diagrama unifilar HÍBRIDO
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import os
import tempfile
import pathlib
from datetime import datetime
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

# ─── HELPERS SVG ──────────────────────────────────────────────────────────────
def _sv(v, d="—"):  return str(v) if v else d
def _se(v, d=""):
    if not v: return d
    return str(v).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

def render_svg_hib(svg_string: str, height: int = 700) -> None:
    b64 = base64.b64encode(svg_string.encode("utf-8")).decode("utf-8")
    html = (f'<div style="width:100%;border-radius:12px;overflow:hidden;">'
            f'<img src="data:image/svg+xml;base64,{b64}" '
            f'style="width:100%;height:{height}px;object-fit:contain;'
            f'background:#0A0E1A;border-radius:12px;" alt="Plano Híbrido"/></div>')
    st.markdown(html, unsafe_allow_html=True)

# ─── CÁLCULOS HÍBRIDO ────────────────────────────────────────────────────────
def calcular_hibrido(consumo_wh_dia: float, hsp: float, pot_panel_wp: int,
                     dias_autonomia: float, dod: float, v_bat: float,
                     cap_bat_ah: float, tarifa_kwh: float,
                     v_mppt_min: float, v_mppt_max: float,
                     voc_panel: float, vmpp_panel: float, impp_panel: float,
                     pr: float = 0.80) -> dict:
    """Cálculo completo del sistema híbrido."""

    # ── Array FV (igual que ON-GRID con PR)
    consumo_fs       = consumo_wh_dia * 1.15      # 15% FS híbrido
    pot_array_wp_min = consumo_fs / (hsp * pr)
    n_paneles        = math.ceil(pot_array_wp_min / pot_panel_wp)
    pot_instalada_wp = n_paneles * pot_panel_wp
    gen_dia_kwh      = (pot_instalada_wp / 1000) * hsp * pr

    # ── Configuración strings (MPPT)
    pan_serie_min      = max(1, math.ceil(v_mppt_min / vmpp_panel)) if vmpp_panel > 0 else 1
    pan_serie_max_mppt = math.floor(v_mppt_max / vmpp_panel)         if vmpp_panel > 0 else 20
    pan_serie_max_voc  = math.floor((v_mppt_max * 1.15) / voc_panel) if voc_panel  > 0 else 20
    pan_serie          = min(pan_serie_max_mppt, pan_serie_max_voc)
    pan_serie          = max(pan_serie, pan_serie_min)
    n_strings          = max(1, math.ceil(n_paneles / pan_serie))
    n_paneles_real     = n_strings * pan_serie
    pot_inst_real      = n_paneles_real * pot_panel_wp
    v_str_mpp          = pan_serie * vmpp_panel
    v_str_oc           = pan_serie * voc_panel
    i_array            = impp_panel * n_strings

    # ── Banco de baterías (OFF-GRID backup)
    energia_respaldo_wh = consumo_fs * dias_autonomia
    cap_bat_total_wh    = energia_respaldo_wh / (dod / 100)
    cap_bat_total_ah    = cap_bat_total_wh / v_bat
    n_baterias          = math.ceil(cap_bat_total_ah / cap_bat_ah)
    # Ajustar a múltiplos pares para configuración serie/paralelo
    if n_baterias % 2 != 0 and n_baterias > 1:
        n_baterias += 1
    cap_real_wh         = n_baterias * cap_bat_ah * v_bat
    autonomia_real_h    = cap_real_wh * (dod / 100) / (consumo_wh_dia / 24)

    # ── Inversor híbrido
    consumo_dia_kwh     = consumo_wh_dia / 1000
    autoconsumo_kwh     = min(gen_dia_kwh, consumo_dia_kwh)
    excedente_kwh       = max(0, gen_dia_kwh - consumo_dia_kwh)
    deficit_kwh         = max(0, consumo_dia_kwh - gen_dia_kwh)
    autoconsumo_pct     = (autoconsumo_kwh / consumo_dia_kwh * 100) if consumo_dia_kwh > 0 else 0
    # El excedente va primero a cargar baterías, luego inyecta a la red
    excedente_bat_kwh   = min(excedente_kwh, cap_real_wh * 0.3 / 1000)  # 30% cap diaria batería
    inyeccion_kwh       = max(0, excedente_kwh - excedente_bat_kwh)

    pot_inv_kw          = round(pot_inst_real / 1000 * 0.90, 1)   # 90% para híbrido

    # ── Generación anual
    gen_anio_kwh        = gen_dia_kwh * 365
    co2_anio_kg         = gen_anio_kwh * 0.126

    return {
        "consumo_fs":        consumo_fs,
        "pot_array_min":     pot_array_wp_min,
        "n_paneles":         n_paneles_real,
        "pan_serie":         pan_serie,
        "n_strings":         n_strings,
        "pot_inst":          pot_inst_real,
        "gen_dia_kwh":       gen_dia_kwh,
        "gen_anio_kwh":      gen_anio_kwh,
        "v_str_mpp":         v_str_mpp,
        "v_str_oc":          v_str_oc,
        "i_array":           i_array,
        "n_baterias":        n_baterias,
        "cap_bat_total_wh":  cap_real_wh,
        "cap_bat_total_ah":  n_baterias * cap_bat_ah,
        "autonomia_real_h":  autonomia_real_h,
        "autoconsumo_kwh":   autoconsumo_kwh,
        "inyeccion_kwh":     inyeccion_kwh,
        "deficit_kwh":       deficit_kwh,
        "autoconsumo_pct":   autoconsumo_pct,
        "excedente_bat_kwh": excedente_bat_kwh,
        "pot_inv_kw":        pot_inv_kw,
        "co2_anio_kg":       co2_anio_kg,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SVG PLANO 1 — DISTRIBUCIÓN DE PANELES (HÍBRIDO)
# ═══════════════════════════════════════════════════════════════════════════════
def svg_plano_paneles_hib(n_paneles: int, pan_serie: int, n_strings: int,
                           pot_panel: int, n_baterias: int, proyecto_info=None) -> str:
    W, H = 1100, 700
    C_BG   = "#0A0E1A"
    C_SOL  = "#FFB300"
    C_DC   = "#00BCD4"
    C_BAT  = "#A78BFA"   # violeta = baterías
    C_GRID = "#FF6B35"
    C_AC   = "#00E676"
    C_DIM  = "#8A9BBD"
    C_TEXT = "#E8EDF5"
    C_PAN  = "#1A2235"
    C_HIB  = "#F59E0B"   # ámbar híbrido

    def box(x,y,w,h,fill,stroke,rx=4,sw=1):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx}"/>'
    def txt(x,y,t,sz=9,fill=C_TEXT,anchor="middle",weight="normal",font="Barlow,sans-serif"):
        return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{sz}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{_se(t)}</text>'
    def line(x1,y1,x2,y2,stroke=C_DC,sw=1.5,dash=""):
        d=f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>'

    # Paleta de strings
    STR_COLORS = [C_DC,"#FFB300","#00E676","#FF5252","#A78BFA","#F472B6","#34D399","#FB923C"]
    PW, PH, GX, GY = 50, 30, 5, 5
    MX, MY = 55, 95

    max_cols = min(pan_serie, 18)
    max_rows = math.ceil(n_paneles / max_cols)

    panels_svg = ""
    pan_count  = 0
    for row in range(max_rows):
        for col in range(max_cols):
            if pan_count >= n_paneles: break
            sc  = STR_COLORS[row % len(STR_COLORS)]
            px  = MX + col * (PW + GX)
            py  = MY + row * (PH + GY)
            panels_svg += box(px, py, PW, PH, C_PAN, sc, 3)
            for lx in range(1,4):
                panels_svg += line(px+lx*PW//4, py+2, px+lx*PW//4, py+PH-2, "#2A3A55", 0.4)
            for ly in range(1,3):
                panels_svg += line(px+2, py+ly*PH//3, px+PW-2, py+ly*PH//3, "#2A3A55", 0.4)
            panels_svg += txt(px+PW//2, py+PH//2+3, str(pan_count+1), 6, sc, "middle","600","Share Tech Mono,monospace")
            pan_count += 1

    # Etiquetas strings
    str_labels = ""
    for s in range(n_strings):
        sc = STR_COLORS[s % len(STR_COLORS)]
        sy = MY + s*(PH+GY) + PH//2 + 3
        str_labels += txt(MX-8, sy, f"S{s+1}", 7, sc, "end","700","Share Tech Mono,monospace")

    # Dimensiones
    arr_w_m = max_cols * 1.134
    arr_h_m = max_rows * 0.686
    arr_w_px = max_cols * (PW+GX)
    arr_h_px = max_rows * (PH+GY)
    dim_y = MY + arr_h_px + 18
    dims  = f'''
    {line(MX,dim_y,MX+arr_w_px-GX,dim_y,C_DIM,1)}
    {line(MX,dim_y-4,MX,dim_y+4,C_DIM,1)}
    {line(MX+arr_w_px-GX,dim_y-4,MX+arr_w_px-GX,dim_y+4,C_DIM,1)}
    {txt((MX*2+arr_w_px-GX)//2,dim_y+11,f"↔ {arr_w_m:.2f} m  ({max_cols} paneles/string)",8,C_DIM)}
    {line(MX-22,MY,MX-22,MY+arr_h_px-GY,C_DIM,1)}
    {line(MX-26,MY,MX-18,MY,C_DIM,1)}
    {line(MX-26,MY+arr_h_px-GY,MX-18,MY+arr_h_px-GY,C_DIM,1)}
    {txt(MX-24,MY+arr_h_px//2,f"{arr_h_m:.2f}m",7.5,C_DIM,"end")}
    '''

    # Panel info lateral
    IX = max(MX + arr_w_px + 40, 790)
    IY = 75; IW = W - IX - 20
    if IW < 150: IW = 175; IX = W - IW - 18
    pot_inst = n_paneles * pot_panel
    items = [
        ("Sistema",        "HÍBRIDO ON+OFF",        C_HIB),
        ("Paneles",        f"{n_paneles} × {pot_panel} Wp", C_SOL),
        ("kWp instalado",  f"{pot_inst/1000:.2f} kWp", C_SOL),
        ("Config. array",  f"{pan_serie}S × {n_strings}P", C_DC),
        ("Baterías",       f"{n_baterias} unidades",  C_BAT),
        ("Área array",     f"≈{arr_w_m:.1f}×{arr_h_m:.1f} m", C_DIM),
        ("Sup. total",     f"≈{arr_w_m*arr_h_m:.1f} m²", C_DIM),
    ]
    info  = box(IX,IY,IW,20+len(items)*23+8,"#0F1525","#2A3A55",8)
    info += box(IX,IY,IW,20,C_HIB,C_HIB,8)
    info += txt(IX+IW//2,IY+13,"DATOS ARRAY HÍBRIDO",8,"#0A0E1A","middle","700","Rajdhani,sans-serif")
    for k,(lbl,val,col) in enumerate(items):
        iy2 = IY+28+k*23
        info += txt(IX+8,iy2+7,lbl,7.5,C_DIM,"start")
        info += txt(IX+IW-8,iy2+7,val,7.5,col,"end","600","Share Tech Mono,monospace")
        if k < len(items)-1:
            info += line(IX+6,iy2+14,IX+IW-6,iy2+14,"#1A2235",0.5)

    # Leyenda strings
    leg_x = IX; leg_y = IY+30+len(items)*23+20
    leg_items = [(STR_COLORS[i%len(STR_COLORS)],f"String {i+1} ({pan_serie} pan.)") for i in range(min(n_strings,6))]
    legend  = box(leg_x,leg_y,IW,18+len(leg_items)*18+8,"#0F1525","#2A3A55",6)
    legend += txt(leg_x+IW//2,leg_y+12,"LEYENDA STRINGS",7.5,C_DIM,"middle","700")
    for k,(sc,lb) in enumerate(leg_items):
        ly2 = leg_y+22+k*18
        legend += box(leg_x+8,ly2,12,10,sc,sc,2)
        legend += txt(leg_x+26,ly2+8,lb,7.5,C_TEXT,"start")

    # Baterías miniatura (panel inferior)
    bat_y0 = min(MY+arr_h_px+50, H-160)
    bat_count_show = min(n_baterias, 12)
    bat_w, bat_h, bat_gap = 34, 22, 6
    bat_svg = ""
    for bi in range(bat_count_show):
        bx = MX + bi*(bat_w+bat_gap)
        bat_svg += box(bx,bat_y0,bat_w,bat_h,"#1A2235",C_BAT,3)
        bat_svg += box(bx+bat_w,bat_y0+bat_h//2-4,4,8,C_BAT,C_BAT,1)   # polo +
        bat_svg += txt(bx+bat_w//2,bat_y0+bat_h//2+4,f"B{bi+1}",6,C_BAT,"middle","600","Share Tech Mono,monospace")
    if n_baterias > 12:
        bat_svg += txt(MX+12*(bat_w+bat_gap)+10,bat_y0+bat_h//2+4,f"+{n_baterias-12}",8,C_DIM,"start")
    bat_svg += txt(MX,bat_y0-10,f"BANCO DE BATERÍAS — {n_baterias} UNIDADES",8,C_BAT,"start","600","Rajdhani,sans-serif")

    proy = _se(proyecto_info[1] if proyecto_info else None,"Proyecto")
    mun  = _se(proyecto_info[2] if proyecto_info else None,"—")

    # Header
    header = f'''
    <rect x="0" y="0" width="{W}" height="60" fill="#0F1525"/>
    <line x1="0" y1="60" x2="{W}" y2="60" stroke="{C_HIB}" stroke-width="1.5"/>
    <text x="20" y="22" font-family="Rajdhani,sans-serif" font-size="18" fill="{C_SOL}" font-weight="700" letter-spacing="2">☀ SOLARCALC PRO</text>
    <text x="20" y="38" font-family="Barlow,sans-serif" font-size="9" fill="{C_DIM}" letter-spacing="3">SISTEMA FOTOVOLTAICO HÍBRIDO — ON-GRID + RESPALDO EN BATERÍAS</text>
    <text x="20" y="52" font-family="Share Tech Mono,monospace" font-size="8" fill="#2A3A55">DISTRIBUCIÓN FÍSICA DE PANELES  ·  VISTA EN PLANTA</text>
    <rect x="{W-230}" y="8" width="220" height="46" rx="6" fill="#1A2235" stroke="{C_HIB}" stroke-width="1"/>
    <text x="{W-120}" y="25" text-anchor="middle" font-family="Rajdhani,sans-serif" font-size="10" fill="{C_HIB}" font-weight="700">☀ ON-GRID + 🔋 BATERÍA</text>
    <text x="{W-120}" y="39" text-anchor="middle" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">Inversor Híbrido MPPT</text>
    <text x="{W-120}" y="51" text-anchor="middle" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">220V AC  60Hz</text>
    '''

    # Title block
    tb_y = H - 65
    title = f'''
    <rect x="0" y="{tb_y}" width="{W}" height="65" fill="#0F1525" stroke="#2A3A55" stroke-width="0.8"/>
    <line x1="0" y1="{tb_y}" x2="{W}" y2="{tb_y}" stroke="{C_HIB}" stroke-width="1.5"/>
    <text x="12" y="{tb_y+16}" font-family="Rajdhani,sans-serif" font-size="12" fill="{C_HIB}" font-weight="700">
        ☀ PLANO DISTRIBUCIÓN PANELES — SISTEMA FOTOVOLTAICO HÍBRIDO (ON-GRID + BATERÍAS)</text>
    <text x="12" y="{tb_y+30}" font-family="Rajdhani,sans-serif" font-size="9" fill="{C_TEXT}">
        Proyecto: {proy}  |  Municipio: {mun}  |  Config: {pan_serie}S×{n_strings}P  |  Baterías: {n_baterias} ud.</text>
    <text x="12" y="{tb_y+44}" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">
        Pot. instalada: {pot_inst/1000:.2f} kWp  |  Área: {arr_w_m:.2f}m × {arr_h_m:.2f}m  |  SolarCalc Pro HÍBRIDO  |  {datetime.now().strftime("%d/%m/%Y")}  |  Plano N°01</text>
    <text x="{W-12}" y="{tb_y+16}" text-anchor="end" font-family="Share Tech Mono,monospace" font-size="9" fill="{C_DIM}">N°01  Rev.A</text>
    '''

    return f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
         style="background:{C_BG};border-radius:12px;width:100%;max-height:720px;">
      <defs>
        <pattern id="grid_h1" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#12192B" stroke-width="0.3"/>
        </pattern>
      </defs>
      <rect width="{W}" height="{H-65}" fill="url(#grid_h1)"/>
      {header}{panels_svg}{str_labels}{dims}{info}{legend}{bat_svg}{title}
    </svg>'''


# ═══════════════════════════════════════════════════════════════════════════════
# SVG PLANO 2 — DIAGRAMA UNIFILAR HÍBRIDO
# ═══════════════════════════════════════════════════════════════════════════════
def svg_unifilar_hibrido(n_paneles: int, pan_serie: int, n_strings: int,
                          pot_panel: int, pot_inv_kw: float,
                          v_str_mpp: float, v_str_oc: float, i_array: float,
                          n_baterias: int, v_bat: float, cap_bat_ah: float,
                          consumo_fs_wh: float, hsp: float,
                          proyecto_info=None) -> str:
    W, H   = 1150, 700
    C_BG   = "#0A0E1A"
    C_SOL  = "#FFB300"
    C_DC   = "#00BCD4"
    C_AC   = "#00E676"
    C_BAT  = "#A78BFA"
    C_GRID = "#FF6B35"
    C_HIB  = "#F59E0B"
    C_DIM  = "#8A9BBD"
    C_TEXT = "#E8EDF5"
    C_NEG  = "#FF5252"
    C_GND  = "#556"

    def box(x,y,w,h,fill,stroke,rx=4,sw=1):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx}"/>'
    def txt(x,y,t,sz=9,fill=C_TEXT,anchor="middle",weight="normal",font="Barlow,sans-serif"):
        return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{sz}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{_se(t)}</text>'
    def line(x1,y1,x2,y2,stroke=C_DC,sw=2,dash=""):
        d=f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
    def wlbl(x,y,t,col=C_DC):
        return f'<text x="{x}" y="{y}" font-family="Share Tech Mono,monospace" font-size="7" fill="{col}" text-anchor="start">{_se(t)}</text>'

    pot_inst = n_paneles * pot_panel
    cap_bat_total_wh = n_baterias * v_bat * cap_bat_ah

    proy = _se(proyecto_info[1] if proyecto_info else None,"Proyecto")
    mun  = _se(proyecto_info[2] if proyecto_info else None,"—")

    # ── 1. ARRAY FV ──────────────────────────────────────────────────────────
    AX,AY,AW,AH = 20,120,125,210
    arr = f'''<g>
      {box(AX,AY,AW,AH,"#0F1525","#FFB300",8)}
      {box(AX,AY,AW,22,"#1A2235","#FFB300",8)}
      {txt(AX+AW//2,AY+14,"ARRAY FV",7.5,C_SOL,"middle","700","Rajdhani,sans-serif")}
      {txt(AX+AW//2,AY+32,f"{n_paneles}×{pot_panel}Wp",9,C_SOL,"middle","700","Share Tech Mono,monospace")}
      {txt(AX+AW//2,AY+46,f"{pot_inst/1000:.2f} kWp",8,C_DIM)}'''
    # Mini strings
    spx=AX+10; spy=AY+60; spw=20; sph=13; spg=4
    for s in range(min(n_strings,4)):
        arr += box(spx,spy+s*(sph+spg),spw,sph,"#1E2A3F",C_DC,2)
        arr += txt(spx+spw//2,spy+s*(sph+spg)+sph//2+3,f"S{s+1}",6,C_DC)
    if n_strings>4:
        arr += txt(spx+spw//2,spy+4*(sph+spg)+5,f"+{n_strings-4}",6.5,C_DIM)
    arr += txt(spx+spw+8,spy+2*(sph+spg)+6,f"{pan_serie}S",7,C_DIM,"start")
    arr += txt(AX+AW//2,AY+AH-28,f"Vmpp={v_str_mpp:.0f}V",7,C_DC,"middle","normal","Share Tech Mono,monospace")
    arr += txt(AX+AW//2,AY+AH-16,f"I={i_array:.1f}A",7,C_DIM,"middle","normal","Share Tech Mono,monospace")
    arr += "</g>"

    # ── 2. CAJA COMBINADORA DC ───────────────────────────────────────────────
    CBX,CBY,CBW,CBH = 200,158,85,130
    cb = f'''<g>
      {box(CBX,CBY,CBW,CBH,"#0F1525","#00BCD4",6)}
      {box(CBX,CBY,CBW,20,"#1A2235","#00BCD4",6)}
      {txt(CBX+CBW//2,CBY+13,"CAJA DC",7,C_DC,"middle","700","Rajdhani,sans-serif")}
      {txt(CBX+CBW//2,CBY+32,"Combiner",7.5,C_TEXT)}
      {txt(CBX+CBW//2,CBY+46,f"{n_strings} strings",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {box(CBX+8,CBY+58,CBW-16,18,"#1E2A3F","#FF5252",3)}
      {txt(CBX+CBW//2,CBY+70,"Fusibles DC",7,"#FF5252")}
      {box(CBX+8,CBY+80,CBW-16,18,"#1E2A3F","#8A9BBD",3)}
      {txt(CBX+CBW//2,CBY+92,"Secc. DC",7,C_DIM)}
      {box(CBX+8,CBY+102,CBW-16,18,"#1E2A3F","#FF5252",3)}
      {txt(CBX+CBW//2,CBY+114,"SPD DC",7,"#FF5252")}
    </g>'''

    # ── 3. INVERSOR HÍBRIDO (pieza central) ──────────────────────────────────
    INX,INY,INW,INH = 345,95,160,260
    inv = f'''<g>
      {box(INX,INY,INW,INH,"#0F1525",C_HIB,8,2)}
      {box(INX,INY,INW,24,"#1A2235",C_HIB,8)}
      {txt(INX+INW//2,INY+15,"INVERSOR HÍBRIDO",8.5,C_HIB,"middle","700","Rajdhani,sans-serif")}
      {txt(INX+INW//2,INY+40,f"{pot_inv_kw:.1f} kW",20,C_HIB,"middle","700","Rajdhani,sans-serif")}
      {txt(INX+INW//2,INY+60,"Grid-Tie + Charger",8,C_DIM)}
      {box(INX+10,INY+70,INW-20,20,"#1E2A3F",C_DC,3)}
      {txt(INX+INW//2,INY+83,"MPPT integrado",7.5,C_DC)}
      {box(INX+10,INY+94,INW-20,20,"#1E2A3F",C_SOL,3)}
      {txt(INX+INW//2,INY+107,f"Rango: {v_str_mpp:.0f}–{v_str_oc:.0f}V",7,C_SOL,"middle","normal","Share Tech Mono,monospace")}
      {box(INX+10,INY+118,INW-20,20,"#1E2A3F",C_BAT,3)}
      {txt(INX+INW//2,INY+131,"Charger baterías",7.5,C_BAT)}
      {box(INX+10,INY+142,INW-20,20,"#1E2A3F",C_AC,3)}
      {txt(INX+INW//2,INY+155,"220V AC  60Hz",7.5,C_AC)}
      {box(INX+10,INY+166,INW-20,20,"#1E2A3F","#8A9BBD",3)}
      {txt(INX+INW//2,INY+179,"Anti-isla / EPS",7,C_DIM)}
      {box(INX+10,INY+190,INW-20,20,"#1E2A3F",C_GRID,3)}
      {txt(INX+INW//2,INY+203,"Monitoreo WiFi",7,C_GRID)}
      {box(INX+10,INY+214,INW-20,20,"#1E2A3F","#2A3A55",3)}
      {txt(INX+INW//2,INY+227,"4 modos operación",7,C_DIM)}
      {txt(INX+INW//2,INY+INH-10,"η≥97%  THD<3%",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
    </g>'''

    # ── 4. BANCO DE BATERÍAS ─────────────────────────────────────────────────
    BAX,BAY,BAW,BAH = 200,340,240,140
    bat = f'''<g>
      {box(BAX,BAY,BAW,BAH,"#0F1525",C_BAT,8,1.5)}
      {box(BAX,BAY,BAW,22,"#1A2235",C_BAT,8)}
      {txt(BAX+BAW//2,BAY+14,"BANCO DE BATERÍAS",8,C_BAT,"middle","700","Rajdhani,sans-serif")}
      {txt(BAX+BAW//2,BAY+34,f"{n_baterias} unidades",12,C_BAT,"middle","700","Share Tech Mono,monospace")}
      {txt(BAX+BAW//2,BAY+50,f"{v_bat}V × {cap_bat_ah}Ah c/u",8,C_DIM)}
      {txt(BAX+BAW//2,BAY+64,f"Cap. total: {n_baterias*v_bat*cap_bat_ah/1000:.1f} kWh",8,C_TEXT,"middle","600","Share Tech Mono,monospace")}
      {box(BAX+10,BAY+74,BAW-20,18,"#1E2A3F",C_BAT,3)}
      {txt(BAX+BAW//2,BAY+86,"BMS / Protección",7.5,C_BAT)}
      {box(BAX+10,BAY+96,BAW-20,18,"#1E2A3F","#FF5252",3)}
      {txt(BAX+BAW//2,BAY+108,"Fusible batería",7,"#FF5252")}
      {txt(BAX+BAW//2,BAY+BAH-10,"LiFePO4 / AGM / GEL",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
    </g>'''
    # Mini baterías
    bb_w, bb_h, bb_g = 26, 14, 4
    for bi in range(min(n_baterias,6)):
        bx2 = BAX+10+bi*(bb_w+bb_g)
        bat += box(bx2,BAY+30,bb_w,bb_h,"#1E2A3F",C_BAT,2)
        bat += box(bx2+bb_w,BAY+30+bb_h//2-3,3,6,C_BAT,C_BAT,1)
        bat += txt(bx2+bb_w//2,BAY+30+bb_h//2+4,f"{bi+1}",5.5,C_BAT,"middle","600","Share Tech Mono,monospace")
    if n_baterias>6:
        bat += txt(BAX+10+6*(bb_w+bb_g)+4,BAY+30+bb_h//2+4,f"...+{n_baterias-6}",7,C_DIM,"start")

    # ── 5. MEDIDOR BIDIRECCIONAL ─────────────────────────────────────────────
    MEX,MEY,MEW,MEH = 575,148,100,120
    med = f'''<g>
      {box(MEX,MEY,MEW,MEH,"#0F1525",C_GRID,6)}
      {box(MEX,MEY,MEW,20,"#1A2235",C_GRID,6)}
      {txt(MEX+MEW//2,MEY+13,"MEDIDOR BIDIRC.",7.5,C_GRID,"middle","700","Rajdhani,sans-serif")}
      {txt(MEX+MEW//2,MEY+36,"📟",16)}
      {txt(MEX+MEW//2,MEY+56,"Telemedida CREG",7,C_DIM)}
      {txt(MEX+MEW//2,MEY+68,"Generación ↑",7,C_AC,"middle","normal","Share Tech Mono,monospace")}
      {txt(MEX+MEW//2,MEY+80,"Consumo red ↓",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {txt(MEX+MEW//2,MEY+94,"220V / 60Hz",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
      {txt(MEX+MEW//2,MEY+MEH-10,"CREG 030-2018",6.5,C_GRID)}
    </g>'''

    # ── 6. TABLERO AC / CARGAS ───────────────────────────────────────────────
    TAX,TAY,TAW,TAH = 575,315,100,130
    tac = f'''<g>
      {box(TAX,TAY,TAW,TAH,"#0F1525",C_AC,6)}
      {box(TAX,TAY,TAW,20,"#1A2235",C_AC,6)}
      {txt(TAX+TAW//2,TAY+13,"TABLERO AC",7.5,C_AC,"middle","700","Rajdhani,sans-serif")}
      {box(TAX+8,TAY+28,TAW-16,18,"#1E2A3F",C_AC,3)}
      {txt(TAX+TAW//2,TAY+40,"Interruptor gral.",7,C_AC)}
      {box(TAX+8,TAY+50,TAW-16,18,"#1E2A3F","#FF5252",3)}
      {txt(TAX+TAW//2,TAY+62,"Prot. diferencial",7,"#FF5252")}
      {box(TAX+8,TAY+72,TAW-16,18,"#1E2A3F","#8A9BBD",3)}
      {txt(TAX+TAW//2,TAY+84,"SPD AC",7,C_DIM)}
      {txt(TAX+TAW//2,TAY+TAH-18,"CARGAS AC",8,C_AC,"middle","700")}
      {txt(TAX+TAW//2,TAY+TAH-6,f"{consumo_fs_wh/1000:.1f} kWh/día",7,C_DIM,"middle","normal","Share Tech Mono,monospace")}
    </g>'''

    # ── 7. RED ELÉCTRICA ─────────────────────────────────────────────────────
    REX,REY,REW,REH = 745,148,110,100
    red = f'''<g>
      {box(REX,REY,REW,REH,"#0F1525",C_GRID,8,1.5)}
      {box(REX,REY,REW,22,C_GRID,C_GRID,8)}
      {txt(REX+REW//2,REY+14,"RED ELÉCTRICA",8,"#0A0E1A","middle","700","Rajdhani,sans-serif")}
      {txt(REX+REW//2,REY+38,"⚡",22)}
      {txt(REX+REW//2,REY+60,"220V AC · 60Hz",8,C_GRID,"middle","600","Share Tech Mono,monospace")}
      {txt(REX+REW//2,REY+74,"Operador de red",7,C_DIM)}
      {txt(REX+REW//2,REY+REH-10,"CREG / RETIE",7,C_DIM)}
    </g>'''

    # ── 8. MODOS DE OPERACIÓN ────────────────────────────────────────────────
    MOX,MOY,MOW,MOH = 745,305,170,190
    modos_items = [
        ("Modo 1","☀ Solar → Cargas",      "#FFB300"),
        ("Modo 2","☀+🔋 Solar+Bat→Cargas", "#A78BFA"),
        ("Modo 3","☀→Red inyección",        "#FF6B35"),
        ("Modo 4","Red→Bat carga nocturna", "#00BCD4"),
    ]
    modos = box(MOX,MOY,MOW,MOH,"#0F1525",C_HIB,6)
    modos += box(MOX,MOY,MOW,20,"#1A2235",C_HIB,6)
    modos += txt(MOX+MOW//2,MOY+13,"MODOS OPERACIÓN",7.5,C_HIB,"middle","700","Rajdhani,sans-serif")
    for k,(m_lbl,m_txt,m_col) in enumerate(modos_items):
        my2 = MOY+26+k*38
        modos += box(MOX+8,my2,MOW-16,34,"#1E2A3F",m_col,4)
        modos += txt(MOX+MOW//2,my2+12,m_lbl,7.5,m_col,"middle","700","Share Tech Mono,monospace")
        modos += txt(MOX+MOW//2,my2+25,m_txt,7,C_TEXT)
    modos += txt(MOX+MOW//2,MOY+MOH-8,"NTC 2050 / RETIE",6.5,C_DIM)

    # ── CABLEO ────────────────────────────────────────────────────────────────
    wires = f'''
    <!-- Array → Combiner DC -->
    {line(AX+AW,AY+AH*0.35,CBX,CBY+CBH*0.38,C_SOL,2.5)}
    {line(AX+AW,AY+AH*0.65,CBX,CBY+CBH*0.65,C_NEG,2.5)}
    {wlbl(AX+AW+3,AY+AH*0.35-4,f"+{v_str_mpp:.0f}V",C_SOL)}
    {wlbl(AX+AW+3,AY+AH*0.65+9,"– GND",C_NEG)}
    <!-- Combiner → Inversor híbrido DC -->
    {line(CBX+CBW,CBY+CBH//2,INX,INY+INH*0.30,C_DC,2.5)}
    {wlbl((CBX+CBW+INX)//2-10,CBY+CBH//2-6,f"DC {v_str_mpp:.0f}V / {i_array:.1f}A",C_DC)}
    <!-- Inversor → Medidor AC -->
    {line(INX+INW,INY+INH*0.38,MEX,MEY+MEH*0.48,C_AC,2.5)}
    {wlbl((INX+INW+MEX)//2-15,INY+INH*0.38-6,"220V AC 60Hz",C_AC)}
    <!-- Medidor → Red -->
    {line(MEX+MEW,MEY+MEH//2,REX,REY+REH//2,C_GRID,2.5)}
    {wlbl((MEX+MEW+REX)//2-25,MEY+MEH//2-6,"Inyección / Import.",C_GRID)}
    <!-- Medidor → Tablero AC -->
    {line(MEX+MEW//2,MEY+MEH,TAX+TAW//2,TAY,C_AC,2.5)}
    {wlbl(MEX+MEW//2+4,(MEY+MEH+TAY)//2,"Autoconsumo",C_AC)}
    <!-- Inversor → Baterías (bidireccional) -->
    {line(INX+INW//2,INY+INH,BAX+BAW//2,BAY,C_BAT,2.5)}
    {wlbl(INX+INW//2+4,(INY+INH+BAY)//2,f"DC {v_bat}V Bat.",C_BAT)}
    <!-- Red → Medidor (importación) -->
    {line(REX,REY+REH//2,MEX+MEW,MEY+MEH//2,C_GRID,1.5,"4,3")}
    '''

    # GND
    GX2=INX+18; GY2=INY+INH+10
    gnd = f'''<g>
      {line(GX2,GY2,GX2,GY2+16,C_GND,1.5)}
      {line(GX2-14,GY2+16,GX2+14,GY2+16,C_GND,2)}
      {line(GX2-8,GY2+22,GX2+8,GY2+22,C_GND,1.5)}
      {line(GX2-4,GY2+28,GX2+4,GY2+28,C_GND,1)}
      {txt(GX2,GY2+38,"GND",7,C_GND)}
    </g>'''

    # Leyenda
    leg2_x=890; leg2_y=330
    leg2 = f'''<g>
      {box(leg2_x,leg2_y,170,155,"#0F1525","#2A3A55",6)}
      {txt(leg2_x+85,leg2_y+14,"REFERENCIAS",7.5,C_DIM,"middle","700")}
      {line(leg2_x+10,leg2_y+28,leg2_x+42,leg2_y+28,C_SOL,2.5)}
      {txt(leg2_x+48,leg2_y+32,"Cable DC Positivo",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+44,leg2_x+42,leg2_y+44,C_NEG,2.5)}
      {txt(leg2_x+48,leg2_y+48,"Cable DC Negativo",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+60,leg2_x+42,leg2_y+60,C_AC,2.5)}
      {txt(leg2_x+48,leg2_y+64,"Cable AC 220V",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+76,leg2_x+42,leg2_y+76,C_BAT,2.5)}
      {txt(leg2_x+48,leg2_y+80,"Cable batería",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+92,leg2_x+42,leg2_y+92,C_GRID,2.5)}
      {txt(leg2_x+48,leg2_y+96,"Red eléctrica",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+108,leg2_x+42,leg2_y+108,C_GND,1.5,"3,3")}
      {txt(leg2_x+48,leg2_y+112,"Puesta a tierra",7.5,C_TEXT,"start")}
      {line(leg2_x+10,leg2_y+124,leg2_x+42,leg2_y+124,C_GRID,1.5,"4,3")}
      {txt(leg2_x+48,leg2_y+128,"Señal / importación",7.5,C_TEXT,"start")}
      {txt(leg2_x+85,leg2_y+143,"NTC 2050 / RETIE",6.5,C_DIM)}
    </g>'''

    # Header
    header = f'''
    <rect x="0" y="0" width="{W}" height="60" fill="#0F1525"/>
    <line x1="0" y1="60" x2="{W}" y2="60" stroke="{C_HIB}" stroke-width="1.5"/>
    <text x="20" y="22" font-family="Rajdhani,sans-serif" font-size="18" fill="{C_SOL}" font-weight="700" letter-spacing="2">☀ SOLARCALC PRO</text>
    <text x="20" y="38" font-family="Barlow,sans-serif" font-size="9" fill="{C_DIM}" letter-spacing="3">SISTEMA FOTOVOLTAICO HÍBRIDO — ON-GRID + RESPALDO EN BATERÍAS</text>
    <text x="20" y="52" font-family="Share Tech Mono,monospace" font-size="8" fill="#2A3A55">DIAGRAMA UNIFILAR  ·  PLANO ELÉCTRICO  ·  NTC 2050 / RETIE</text>
    '''

    # Title block
    tb_y = H - 65
    title = f'''
    <rect x="0" y="{tb_y}" width="{W}" height="65" fill="#0F1525" stroke="#2A3A55" stroke-width="0.8"/>
    <line x1="0" y1="{tb_y}" x2="{W}" y2="{tb_y}" stroke="{C_HIB}" stroke-width="1.5"/>
    <text x="12" y="{tb_y+16}" font-family="Rajdhani,sans-serif" font-size="12" fill="{C_HIB}" font-weight="700">
        ☀ DIAGRAMA UNIFILAR — SISTEMA FOTOVOLTAICO HÍBRIDO (ON-GRID + BATERÍAS)</text>
    <text x="12" y="{tb_y+30}" font-family="Rajdhani,sans-serif" font-size="9" fill="{C_TEXT}">
        Proyecto: {proy}  |  Municipio: {mun}  |  Config: {pan_serie}S×{n_strings}P  |  Baterías: {n_baterias} ud. @ {v_bat}V {cap_bat_ah}Ah  |  Inversor: {pot_inv_kw:.1f}kW</text>
    <text x="12" y="{tb_y+44}" font-family="Share Tech Mono,monospace" font-size="8" fill="{C_DIM}">
        Array: {n_paneles}×{pot_panel}Wp={pot_inst/1000:.2f}kWp  Vmpp={v_str_mpp:.0f}V  I={i_array:.1f}A  |  SolarCalc Pro HÍBRIDO  |  {datetime.now().strftime("%d/%m/%Y")}  |  Plano N°02</text>
    <text x="{W-12}" y="{tb_y+16}" text-anchor="end" font-family="Share Tech Mono,monospace" font-size="9" fill="{C_DIM}">N°02  Rev.A</text>
    '''

    return f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
         style="background:{C_BG};border-radius:12px;width:100%;max-height:720px;">
      <defs>
        <pattern id="grid_h2" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#12192B" stroke-width="0.3"/>
        </pattern>
      </defs>
      <rect width="{W}" height="{H-65}" fill="url(#grid_h2)"/>
      {header}{wires}{arr}{cb}{inv}{bat}{med}{red}{tac}{modos}{gnd}{leg2}{title}
    </svg>'''


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — mostrar_hibrido()
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_hibrido(proyecto_id: int, session_state: dict) -> None:
    """Punto de entrada desde solar_app.py"""

    st.markdown("""
    <style>
    .hib-badge {
        display:inline-block;background:linear-gradient(90deg,#F59E0B,#FF6B35);
        color:#0A0E1A;font-family:'Rajdhani',sans-serif;font-weight:700;
        font-size:0.75rem;padding:2px 10px;border-radius:20px;letter-spacing:1px;margin-left:8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>☀ SOLARCALC PRO
            <span class='hib-badge'>HÍBRIDO</span>
        </div>
        <div class='hero-sub'>DIMENSIONAMIENTO — SISTEMA FOTOVOLTAICO HÍBRIDO (ON-GRID + BATERÍAS)</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Leer BD ───────────────────────────────────────────────────────────────
    conn = get_conn()
    p_info = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    cargas_df = pd.read_sql(
        "SELECT cantidad, potencia_w, horas_dia FROM cargas WHERE proyecto_id=?",
        conn, params=(proyecto_id,))
    panel_row = conn.execute(
        "SELECT potencia_wp, voc, isc FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    conn.close()

    consumo_inv  = (cargas_df["cantidad"] * cargas_df["potencia_w"] * cargas_df["horas_dia"]).sum() \
                    if not cargas_df.empty else 0.0
    consumo_rec  = session_state.get("consumo_recibo_wh", 0.0)
    periodo_rec  = session_state.get("recibo_ref_periodo", "")
    hsp_guardado = p_info[4] if p_info and p_info[4] else None
    pot_panel_def= int(panel_row[0]) if panel_row else 550
    voc_def      = float(panel_row[1]) if panel_row else 49.9
    isc_def      = float(panel_row[2]) if panel_row else 14.0

    # ── TABS HÍBRIDO ──────────────────────────────────────────────────────────
    tab_h1,tab_h2,tab_h3,tab_h4,tab_h5,tab_h6,tab_h7,tab_h8 = st.tabs([
        "⚡ 1 · Consumo",
        "🌞 2 · Irradiación",
        "🔆 3 · Panel",
        "🔋 4 · Baterías",
        "📐 5 · Dimensionamiento",
        "💹 6 · Económico",
        "🔲 7 · Plano Paneles",
        "📋 8 · Diagrama Unifilar",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H1 — CONSUMO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h1:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>1</span>
        CONSUMO ENERGÉTICO DEL PROYECTO</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            El sistema híbrido cubre el consumo con energía solar, usa baterías de respaldo
            y puede importar/exportar energía de/a la red.<br>
            <b>Factor de seguridad: 15%</b> (incluye pérdidas térmicas, cableado y eficiencia del inversor).
        </div>""", unsafe_allow_html=True)

        opciones = ["⚡ Inventario de cargas (Módulo Cargas)"]
        if consumo_rec > 0:
            opciones.append(f"🧾 Recibo de energía ({periodo_rec})")
            opciones.append("📊 Mayor de los dos (recomendado)")

        if consumo_inv == 0 and consumo_rec == 0:
            st.markdown("""
            <div class='warn-box'>⚠ No hay consumo registrado. Ingresa las cargas en el módulo
            <b>Dimensionamiento OFF-GRID</b> → Tab 1 o registra un recibo en Tab 2 primero.</div>
            """, unsafe_allow_html=True)
            return

        fuente_h = st.radio("Base de consumo:", opciones, horizontal=True, key="hib_fuente")
        if "Recibo" in fuente_h:
            consumo_base = consumo_rec
        elif "Mayor" in fuente_h:
            consumo_base = max(consumo_inv, consumo_rec)
        else:
            consumo_base = consumo_inv

        consumo_fs_hib = consumo_base * 1.15

        col1,col2,col3,col4 = st.columns(4)
        for c_col, val, unit, lbl, col_c in [
            (col1, consumo_inv,    "Wh/día","Inventario cargas",  "#FFB300"),
            (col2, consumo_rec,    "Wh/día","Recibo energía",     "#00BCD4"),
            (col3, consumo_base,   "Wh/día","Consumo base",       "#00E676"),
            (col4, consumo_fs_hib, "Wh/día","Con 15% FS híbrido", "#F59E0B"),
        ]:
            with c_col:
                st.markdown(f"""
                <div class='metric-box' style='border-top:2px solid {col_c};'>
                    <div class='metric-val' style='color:{col_c};'>{val:,.0f}</div>
                    <div class='metric-unit'>{unit}</div>
                    <div class='metric-label'>{lbl}</div>
                </div>""", unsafe_allow_html=True)

        session_state["hib_consumo_fs"] = consumo_fs_hib

        st.markdown("""
        <div class='info-note' style='margin-top:1rem;'>
            ℹ El <b>sistema híbrido</b> aplica un 15% de factor de seguridad: mayor que ON-GRID (10%)
            porque incluye pérdidas adicionales de conversión DC→Batería→AC, y menor que OFF-GRID
            aislado puro (25%) porque la red eléctrica actúa como respaldo de último recurso.
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H2 — IRRADIACIÓN / HSP
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h2:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>2</span>
        HORA SOLAR PICO (HSP) E IRRADIACIÓN</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            HSP = Irradiación mensual (kWh/m²/mes) ÷ 30 días<br>
            Para sistemas híbridos se puede usar el promedio anual (la red y las baterías
            compensan los meses de menor irradiación).
        </div>""", unsafe_allow_html=True)

        col_h21, col_h22 = st.columns(2)
        with col_h21:
            st.markdown("""
            <div class='sol-card'>
                <div style='color:#F59E0B;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.8rem;'>
                    📊 Fuentes de Irradiación
                </div>
                <div style='font-size:0.85rem;color:#8A9BBD;line-height:1.9;'>
                    <b style='color:#E8EDF5;'>PVGIS (JRC Europa)</b><br>
                    https://re.jrc.ec.europa.eu/pvg_tools/es/<br><br>
                    <b style='color:#E8EDF5;'>NASA POWER</b><br>
                    https://power.larc.nasa.gov/data-access-viewer/<br><br>
                    <b style='color:#E8EDF5;'>SolarGIS</b><br>
                    https://solargis.com/maps-and-gis-data<br><br>
                    <b style='color:#F59E0B;'>💡 Híbrido:</b>
                    <span style='color:#8A9BBD;'>Usa el promedio anual.
                    Las baterías y la red cubren los meses bajos.</span>
                </div>
            </div>""", unsafe_allow_html=True)

        with col_h22:
            irr_hib = st.number_input(
                "Irradiación promedio (kWh/m²/mes)",
                min_value=50.0, max_value=300.0, value=150.0, step=0.5,
                key="hib_irr")
            hsp_hib = irr_hib / 30

            pr_hib = st.slider(
                "Performance Ratio PR (%)", 70, 90, 80,
                help="PR típico para híbrido: 78-85%", key="hib_pr")

            hsp_ef = hsp_hib * (pr_hib / 100)

            st.markdown(f"""
            <div class='result-highlight'>
                <div style='color:#8A9BBD;font-size:0.8rem;'>{irr_hib} kWh/m²/mes ÷ 30 =</div>
                <div class='val'>{hsp_hib:.2f} h/día (HSP)</div>
                <div style='color:#F59E0B;font-size:0.85rem;margin-top:0.3rem;'>
                    HSP efectiva (×PR {pr_hib}%) = <b>{hsp_ef:.2f} h/día</b>
                </div>
            </div>""", unsafe_allow_html=True)

            if st.button("💾 Guardar HSP", use_container_width=True, key="hib_save_hsp"):
                conn = get_conn()
                conn.execute("UPDATE proyectos SET hsp=? WHERE id=?", (round(hsp_hib,2), proyecto_id))
                conn.commit(); conn.close()
                st.success(f"HSP = {hsp_hib:.2f} h/día guardado ✓")

            if hsp_guardado:
                st.markdown(f"""
                <div class='info-note' style='margin-top:0.5rem;'>
                    ✓ HSP del proyecto: <b>{hsp_guardado} h/día</b>
                </div>""", unsafe_allow_html=True)

        session_state["_hib_hsp"]    = hsp_hib
        session_state["_hib_hsp_ef"] = hsp_ef
        session_state["_hib_pr"]     = pr_hib / 100

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H3 — PANEL SOLAR
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h3:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>3</span>
        PARÁMETROS DEL PANEL SOLAR</div>""", unsafe_allow_html=True)

        col_h31, col_h32 = st.columns(2)
        with col_h31:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            hib_modelo = st.text_input("Modelo del panel",
                placeholder="Ej: Canadian Solar CS6W-550T",
                value=_sv(panel_row[0] if panel_row else ""), key="hib_modelo")
            hib_wp   = st.number_input("Potencia pico (Wp)", 50, 1000, pot_panel_def, key="hib_wp")
            hib_voc  = st.number_input("Tensión Voc (V)", 5.0, 100.0, voc_def, step=0.1, key="hib_voc")
            hib_vmpp = st.number_input("Tensión Vmpp (V)", 5.0, 80.0,
                                        round(voc_def*0.82,1), step=0.1, key="hib_vmpp")
            hib_isc  = st.number_input("Corriente Isc (A)", 0.1, 30.0, isc_def, step=0.1, key="hib_isc")
            hib_impp = st.number_input("Corriente Impp (A)", 0.1, 25.0,
                                        round(isc_def*0.95,1), step=0.1, key="hib_impp")

            if st.button("💾 Guardar Panel", use_container_width=True, key="hib_save_panel"):
                conn = get_conn()
                conn.execute("DELETE FROM paneles WHERE proyecto_id=?", (proyecto_id,))
                conn.execute("INSERT INTO paneles(proyecto_id,modelo,potencia_wp,voc,isc) VALUES(?,?,?,?,?)",
                             (proyecto_id, hib_modelo, hib_wp, hib_voc, hib_isc))
                conn.commit(); conn.close()
                st.success("Panel guardado ✓"); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_h32:
            st.markdown(f"""
            <div class='sol-card'>
                <div style='color:#F59E0B;font-family:Rajdhani,sans-serif;font-weight:600;
                            margin-bottom:1rem;font-size:1.1rem;'>FICHA TÉCNICA</div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.8rem;'>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#FFB300;'>{hib_wp}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>Wp — POT. PICO</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#00BCD4;'>{hib_voc}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>V — Voc</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#FFD54F;'>{hib_vmpp}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>V — Vmpp</div>
                    </div>
                    <div style='background:#161D30;border-radius:8px;padding:1rem;text-align:center;'>
                        <div style='font-family:Share Tech Mono;font-size:1.8rem;color:#A78BFA;'>{hib_impp:.1f}</div>
                        <div style='font-size:0.75rem;color:#8A9BBD;margin-top:0.3rem;'>A — Impp</div>
                    </div>
                </div>
                <div style='margin-top:0.8rem;background:#161D30;border-radius:8px;padding:0.8rem;text-align:center;'>
                    <div style='font-family:Share Tech Mono;font-size:0.85rem;color:#F59E0B;'>
                        FF = Vmpp×Impp / Voc×Isc = {(hib_vmpp*hib_impp/(hib_voc*hib_isc)*100) if hib_voc*hib_isc>0 else 0:.1f}%
                    </div>
                    <div style='font-size:0.72rem;color:#8A9BBD;margin-top:0.3rem;'>Factor de Forma (≥72% ideal)</div>
                </div>
            </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H4 — BATERÍAS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h4:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>4</span>
        BANCO DE BATERÍAS (RESPALDO)</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Cap. banco (Wh) = Consumo/día × Días autonomía ÷ DoD<br>
            N° baterías = Cap. banco (Ah) ÷ Cap. batería (Ah)<br>
            En sistemas híbridos el banco actúa como <b>respaldo nocturno y ante cortes de red</b>.
        </div>""", unsafe_allow_html=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            st.markdown("<div style='color:#A78BFA;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.8rem;'>PARÁMETROS BANCO</div>", unsafe_allow_html=True)

            hib_dias_aut = st.number_input(
                "Días de autonomía", min_value=0.5, max_value=7.0, value=1.0, step=0.5,
                help="Para híbrido: 0.5–2 días. La red cubre el resto.", key="hib_dias_aut")
            hib_dod = st.slider(
                "Profundidad de descarga DoD (%)", 50, 90, 80,
                help="AGM/GEL: 50%. LiFePO4: 80-90%", key="hib_dod")
            hib_v_bat = st.selectbox(
                "Tensión nominal batería (V)", [12, 24, 48], index=2, key="hib_v_bat")
            hib_cap_bat = st.number_input(
                "Capacidad batería (Ah)", min_value=50, max_value=500, value=100, step=10,
                key="hib_cap_bat")
            hib_tipo_bat = st.selectbox(
                "Tecnología", ["LiFePO4 (recomendado)", "AGM", "GEL", "Litio NMC"],
                key="hib_tipo_bat")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_b2:
            consumo_fs_calc = session_state.get("hib_consumo_fs", consumo_inv * 1.15)
            if consumo_fs_calc > 0:
                en_resp_wh   = consumo_fs_calc * hib_dias_aut
                cap_banco_wh = en_resp_wh / (hib_dod / 100)
                cap_banco_ah = cap_banco_wh / hib_v_bat
                n_bats       = math.ceil(cap_banco_ah / hib_cap_bat)
                if n_bats % 2 != 0 and n_bats > 1: n_bats += 1
                cap_real_wh  = n_bats * hib_cap_bat * hib_v_bat
                aut_real_h   = cap_real_wh * (hib_dod/100) / (consumo_fs_calc / 24)

                st.markdown(f"""
                <div class='result-highlight' style='border-color:rgba(167,139,250,0.5);
                     background:linear-gradient(135deg,rgba(167,139,250,0.08),rgba(167,139,250,0.02));'>
                    <div style='color:#8A9BBD;font-size:0.8rem;'>Energía de respaldo requerida</div>
                    <div class='val' style='color:#A78BFA;'>{en_resp_wh/1000:.2f} kWh</div>
                </div>
                <div class='metric-grid' style='margin-top:0.8rem;'>
                    <div class='metric-box' style='border-color:rgba(167,139,250,0.5);'>
                        <div class='metric-val' style='color:#A78BFA;'>{n_bats}</div>
                        <div class='metric-unit'>unidades</div>
                        <div class='metric-label'>BATERÍAS</div>
                    </div>
                    <div class='metric-box'>
                        <div class='metric-val'>{cap_real_wh/1000:.1f}</div>
                        <div class='metric-unit'>kWh</div>
                        <div class='metric-label'>CAP. REAL</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                        <div class='metric-val'>{aut_real_h:.1f}</div>
                        <div class='metric-unit'>horas</div>
                        <div class='metric-label'>AUTONOMÍA</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(0,188,212,0.5);'>
                        <div class='metric-val'>{n_bats * hib_cap_bat}</div>
                        <div class='metric-unit'>Ah</div>
                        <div class='metric-label'>CAPACIDAD Ah</div>
                    </div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""
                <div class='sol-card' style='margin-top:0.8rem;'>
                    <div style='color:#A78BFA;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.6rem;'>
                    CONFIGURACIÓN DEL BANCO</div>
                    <table style='width:100%;font-size:0.82rem;border-collapse:collapse;'>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Tecnología</td>
                            <td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{hib_tipo_bat}</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Tensión sistema</td>
                            <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{hib_v_bat} V DC</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Cap. por batería</td>
                            <td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{hib_cap_bat} Ah</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Capacidad banco</td>
                            <td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{cap_real_wh/1000:.2f} kWh</td>
                        </tr>
                        <tr style='border-bottom:1px solid #2A3A55;'>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Energía útil (DoD {hib_dod}%)</td>
                            <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>{cap_real_wh*hib_dod/100/1000:.2f} kWh</td>
                        </tr>
                        <tr>
                            <td style='color:#8A9BBD;padding:0.35rem 0;'>Autonomía real</td>
                            <td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>{aut_real_h:.1f} h / {aut_real_h/24:.1f} días</td>
                        </tr>
                    </table>
                </div>""", unsafe_allow_html=True)

                session_state["_hib_n_baterias"]  = n_bats
                session_state["_hib_v_bat"]        = hib_v_bat
                session_state["_hib_cap_bat_ah"]   = hib_cap_bat
                session_state["_hib_cap_real_wh"]  = cap_real_wh
                session_state["_hib_aut_real_h"]   = aut_real_h
            else:
                st.markdown("<div class='warn-box'>⚠ Completa el Tab 1 (Consumo) primero.</div>",
                            unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H5 — DIMENSIONAMIENTO HÍBRIDO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h5:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>5</span>
        DIMENSIONAMIENTO COMPLETO DEL SISTEMA HÍBRIDO</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Pot. array = Consumo×1.15 ÷ (HSP × PR)  |  Strings: Vmpp×n dentro del rango MPPT<br>
            Banco bat.: Consumo × Días autonomía ÷ DoD  |  Inversor híbrido ≈ 90% pot. array
        </div>""", unsafe_allow_html=True)

        consumo_d5  = session_state.get("hib_consumo_fs", consumo_inv * 1.15)
        hsp_d5      = session_state.get("_hib_hsp",    hsp_guardado or 4.2)
        pr_d5_raw   = session_state.get("hib_pr",      80)
        wp_d5       = session_state.get("hib_wp",      pot_panel_def)
        voc_d5      = session_state.get("hib_voc",     voc_def)
        vmpp_d5     = session_state.get("hib_vmpp",    round(voc_def*0.82,1))
        impp_d5     = session_state.get("hib_impp",    round(isc_def*0.95,1))
        n_bat_d5    = session_state.get("_hib_n_baterias", 4)
        v_bat_d5    = session_state.get("_hib_v_bat",      48)
        cap_bat_d5  = session_state.get("_hib_cap_bat_ah", 100)
        dias_aut_d5 = session_state.get("hib_dias_aut", 1.0)
        dod_d5      = session_state.get("hib_dod", 80)

        if consumo_d5 == 0:
            st.markdown("<div class='warn-box'>⚠ Completa los tabs 1 y 4 primero.</div>",
                        unsafe_allow_html=True)
            return

        pr_d5 = (pr_d5_raw / 100) if isinstance(pr_d5_raw, (int,float)) else 0.80

        col_d1, col_d2 = st.columns([1, 1.2])
        with col_d1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            st.markdown("**Parámetros de cálculo**")
            consumo_inp = st.number_input("Consumo diario con FS (Wh/día)",
                min_value=100.0, value=float(consumo_d5), step=100.0, key="hib_consumo_inp")
            hsp_inp = st.number_input("HSP (h/día)", min_value=0.5, max_value=12.0,
                value=float(hsp_d5), step=0.01, key="hib_hsp_inp")
            pr_inp  = st.slider("PR (%)", 70, 90,
                int(pr_d5*100) if isinstance(pr_d5*100,(int,float)) else 80, key="hib_pr_d5")
            wp_inp  = st.number_input("Potencia panel (Wp)", 50, 1000,
                int(wp_d5), key="hib_wp_inp")
            vmpp_inp= st.number_input("Vmpp (V)", 5.0, 80.0, float(vmpp_d5), step=0.1, key="hib_vmpp_inp")
            voc_inp = st.number_input("Voc (V)", 5.0, 100.0, float(voc_d5), step=0.1, key="hib_voc_inp")
            impp_inp= st.number_input("Impp (A)", 0.1, 25.0, float(impp_d5), step=0.1, key="hib_impp_inp")

            st.markdown("<hr style='border-color:#2A3A55;margin:0.5rem 0;'>", unsafe_allow_html=True)
            st.markdown("<small style='color:#A78BFA;'>Rango MPPT del inversor híbrido:</small>",
                        unsafe_allow_html=True)
            v_mppt_min_h = st.number_input("V MPPT mín.", 50, 400, 120, key="hib_vmppt_min")
            v_mppt_max_h = st.number_input("V MPPT máx.", 200, 1500, 600, key="hib_vmppt_max")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_d2:
            pr_dec = pr_inp / 100.0
            pot_min_wp   = consumo_inp / (hsp_inp * pr_dec) if hsp_inp * pr_dec > 0 else 0
            n_pan        = math.ceil(pot_min_wp / wp_inp)
            # Strings
            pan_s_min    = max(1, math.ceil(v_mppt_min_h / vmpp_inp)) if vmpp_inp > 0 else 1
            pan_s_max_m  = math.floor(v_mppt_max_h / vmpp_inp)        if vmpp_inp > 0 else 20
            pan_s_max_v  = math.floor((v_mppt_max_h*1.15) / voc_inp)  if voc_inp  > 0 else 20
            pan_serie_h  = min(pan_s_max_m, pan_s_max_v)
            pan_serie_h  = max(pan_serie_h, pan_s_min)
            n_str_h      = max(1, math.ceil(n_pan / pan_serie_h))
            n_pan_real   = n_str_h * pan_serie_h
            pot_inst_h   = n_pan_real * wp_inp
            v_str_mpp_h  = pan_serie_h * vmpp_inp
            v_str_oc_h   = pan_serie_h * voc_inp
            i_arr_h      = impp_inp * n_str_h
            pot_inv_h    = round(pot_inst_h / 1000 * 0.90, 1)

            # Banco
            en_resp      = consumo_inp * dias_aut_d5
            cap_bat_wh   = en_resp / (dod_d5 / 100)
            cap_bat_ah_t = cap_bat_wh / v_bat_d5
            n_bats_calc  = math.ceil(cap_bat_ah_t / cap_bat_d5)
            if n_bats_calc % 2 != 0 and n_bats_calc > 1: n_bats_calc += 1
            cap_real      = n_bats_calc * cap_bat_d5 * v_bat_d5
            aut_real_hh   = cap_real * (dod_d5/100) / (consumo_inp/24)

            # Generación
            gen_dia_h     = (pot_inst_h / 1000) * hsp_inp * pr_dec
            consumo_kwh   = consumo_inp / 1000
            autocon_h     = min(gen_dia_h, consumo_kwh)
            inj_h         = max(0, gen_dia_h - consumo_kwh)
            def_h         = max(0, consumo_kwh - gen_dia_h)
            ac_pct        = autocon_h / consumo_kwh * 100 if consumo_kwh > 0 else 0

            mppt_ok = v_mppt_min_h <= v_str_mpp_h <= v_mppt_max_h

            # Guardar
            session_state["_hib_n_pan"]       = n_pan_real
            session_state["_hib_pan_serie"]   = pan_serie_h
            session_state["_hib_n_strings"]   = n_str_h
            session_state["_hib_pot_inst"]    = pot_inst_h
            session_state["_hib_v_str_mpp"]   = v_str_mpp_h
            session_state["_hib_v_str_oc"]    = v_str_oc_h
            session_state["_hib_i_array"]     = i_arr_h
            session_state["_hib_pot_inv"]     = pot_inv_h
            session_state["_hib_n_baterias"]  = n_bats_calc
            session_state["_hib_cap_real_wh"] = cap_real
            session_state["_hib_aut_horas"]   = aut_real_hh
            session_state["_hib_gen_dia"]     = gen_dia_h
            session_state["_hib_autocon_pct"] = ac_pct

            st.markdown(f"""
            <div class='result-highlight' style='border-color:rgba(245,158,11,0.5);
                 background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(245,158,11,0.02));'>
                <div style='color:#8A9BBD;font-size:0.8rem;text-transform:uppercase;'>
                    Potencia mínima del array</div>
                <div class='val' style='color:#F59E0B;'>{pot_min_wp/1000:.2f} kWp</div>
            </div>
            <div class='metric-grid'>
                <div class='metric-box' style='border-color:rgba(255,179,0,0.5);'>
                    <div class='metric-val'>{n_pan_real}</div>
                    <div class='metric-unit'>paneles</div><div class='metric-label'>TOTAL</div>
                </div>
                <div class='metric-box'>
                    <div class='metric-val'>{pot_inst_h/1000:.2f}</div>
                    <div class='metric-unit'>kWp</div><div class='metric-label'>POT. INST.</div>
                </div>
                <div class='metric-box' style='border-color:rgba(0,188,212,0.5);'>
                    <div class='metric-val'>{pan_serie_h}S×{n_str_h}P</div>
                    <div class='metric-unit'>config</div><div class='metric-label'>STRINGS</div>
                </div>
                <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                    <div class='metric-val'>{pot_inv_h}</div>
                    <div class='metric-unit'>kW</div><div class='metric-label'>INVERSOR HIB.</div>
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.6rem;margin-top:0.8rem;'>
              <div class='sol-card'>
                <div style='color:#00BCD4;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.5rem;'>ARRAY DC</div>
                <table style='width:100%;font-size:0.8rem;border-collapse:collapse;'>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Vmpp string</td><td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{v_str_mpp_h:.0f} V</td></tr>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Voc string</td><td style='font-family:Share Tech Mono;color:#FF5252;text-align:right;'>{v_str_oc_h:.0f} V</td></tr>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>I array</td><td style='font-family:Share Tech Mono;color:#FFB300;text-align:right;'>{i_arr_h:.1f} A</td></tr>
                  <tr><td style='color:#8A9BBD;'>MPPT</td><td style='text-align:right;font-family:Share Tech Mono;color:{"#00E676" if mppt_ok else "#FF5252"};'>{"✓ OK" if mppt_ok else "✗ REVISAR"}</td></tr>
                </table>
              </div>
              <div class='sol-card'>
                <div style='color:#A78BFA;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.5rem;'>BATERÍAS</div>
                <table style='width:100%;font-size:0.8rem;border-collapse:collapse;'>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>N° unidades</td><td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{n_bats_calc}</td></tr>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Cap. banco</td><td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{cap_real/1000:.1f} kWh</td></tr>
                  <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Autonomía</td><td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>{aut_real_hh:.1f} h</td></tr>
                  <tr><td style='color:#8A9BBD;'>Autoconsumo</td><td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>{ac_pct:.0f}%</td></tr>
                </table>
              </div>
            </div>""", unsafe_allow_html=True)

            if not mppt_ok:
                st.markdown(f"""
                <div class='warn-box'>⚠ Vmpp del string ({v_str_mpp_h:.0f}V) fuera del rango MPPT
                ({v_mppt_min_h}–{v_mppt_max_h}V). Ajusta el N° de paneles en serie o cambia el inversor.</div>
                """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H6 — ANÁLISIS ECONÓMICO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h6:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>6</span>
        ANÁLISIS ECONÓMICO Y AMBIENTAL</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            Ahorro = Autoconsumo×30×Tarifa  |  Ingreso = Excedente×30×Precio_red (≈50% tarifa)<br>
            Payback = Inversión total ÷ (Ahorro+Ingresos) anuales  |  CO₂ factor Colombia: 0.126 kgCO₂/kWh
        </div>""", unsafe_allow_html=True)

        pot_inst_e  = session_state.get("_hib_pot_inst",  0.0)
        n_pan_e     = session_state.get("_hib_n_pan",     0)
        n_bats_e    = session_state.get("_hib_n_baterias", 0)
        pot_inv_e   = session_state.get("_hib_pot_inv",   3.0)
        gen_dia_e   = session_state.get("_hib_gen_dia",   0.0)
        ac_pct_e    = session_state.get("_hib_autocon_pct", 0.0)
        consumo_fe  = session_state.get("hib_consumo_fs", consumo_inv * 1.15)
        cap_real_e  = session_state.get("_hib_cap_real_wh", 0.0)
        aut_h_e     = session_state.get("_hib_aut_horas", 0.0)
        hsp_e       = session_state.get("_hib_hsp",  hsp_guardado or 4.2)
        pr_e_raw    = session_state.get("hib_pr_d5", session_state.get("hib_pr", 80))
        pr_e        = pr_e_raw / 100 if isinstance(pr_e_raw, (int,float)) else 0.80

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            tarifa_h      = st.number_input("Tarifa energía ($/kWh)",   100.0, 5000.0, 700.0,  50.0, key="hib_tarifa")
            precio_pan_h  = st.number_input("Precio panel ($/unidad)", 50000.0,2e6,   320000.0,10000.0, key="hib_ppanel")
            costo_inv_h   = st.number_input("Costo inversor híbrido ($/kW)", 500000.0,15e6,3500000.0,100000.0, key="hib_cinv")
            precio_bat_h  = st.number_input("Precio batería ($/unidad)", 50000.0,5e6,  800000.0,50000.0,  key="hib_pbat")
            otros_h       = st.number_input("Otros costos (estructura, cable, MO) ($)",
                                             0.0, 50e6, 2000000.0, 200000.0, key="hib_otros")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_e2:
            if pot_inst_e == 0 or consumo_fe == 0:
                st.markdown("<div class='warn-box'>⚠ Completa el Tab 5 primero.</div>",
                            unsafe_allow_html=True)
            else:
                gen_mes_h     = gen_dia_e * 30
                gen_anio_h    = gen_dia_e * 365
                consumo_kwh_h = consumo_fe / 1000
                autocon_h2    = min(gen_dia_e, consumo_kwh_h)
                inj_h2        = max(0, gen_dia_e - consumo_kwh_h)
                def_h2        = max(0, consumo_kwh_h - gen_dia_e)

                ahorro_mes_h  = autocon_h2 * 30 * tarifa_h
                ing_iny_h     = inj_h2    * 30 * tarifa_h * 0.50
                ben_mes_h     = ahorro_mes_h + ing_iny_h
                ben_anio_h    = ben_mes_h * 12

                inv_pan_h     = n_pan_e  * precio_pan_h
                inv_inv_h     = pot_inv_e * costo_inv_h
                inv_bat_h     = n_bats_e * precio_bat_h
                inv_tot_h     = inv_pan_h + inv_inv_h + inv_bat_h + otros_h
                payback_h     = inv_tot_h / ben_anio_h if ben_anio_h > 0 else 99
                tir_h         = (ben_anio_h / inv_tot_h) * 100

                co2_h         = gen_anio_h * 0.126
                arboles_h     = co2_h / 21   # 1 árbol ≈ 21 kgCO2/año

                st.markdown(f"""
                <div class='metric-grid'>
                    <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                        <div class='metric-val' style='color:#00E676;'>{gen_dia_e:.2f}</div>
                        <div class='metric-unit'>kWh/día</div><div class='metric-label'>GENERACIÓN</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(245,158,11,0.5);'>
                        <div class='metric-val' style='color:#F59E0B;'>{ac_pct_e:.0f}%</div>
                        <div class='metric-unit'>autoconsumo</div><div class='metric-label'>COBERTURA</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(255,179,0,0.5);'>
                        <div class='metric-val'>${ben_mes_h:,.0f}</div>
                        <div class='metric-unit'>$/mes</div><div class='metric-label'>BENEFICIO</div>
                    </div>
                    <div class='metric-box' style='border-color:rgba(0,230,118,0.5);'>
                        <div class='metric-val' style='color:#00E676;'>{payback_h:.1f}</div>
                        <div class='metric-unit'>años</div><div class='metric-label'>PAYBACK</div>
                    </div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""
                <div class='sol-card' style='margin-top:0.8rem;'>
                    <div style='color:#F59E0B;font-family:Rajdhani,sans-serif;font-weight:600;margin-bottom:0.8rem;'>
                    RESUMEN FINANCIERO + AMBIENTAL</div>
                    <table style='width:100%;font-size:0.82rem;border-collapse:collapse;'>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Inversión paneles</td><td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${inv_pan_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Inversión inversor híbrido</td><td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${inv_inv_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Inversión baterías</td><td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>${inv_bat_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Otros (estructura+cable+MO)</td><td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>${otros_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'><td style='color:#F59E0B;font-weight:600;'>Inversión total</td><td style='font-family:Share Tech Mono;color:#F59E0B;text-align:right;font-weight:700;'>${inv_tot_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Ahorro autoconsumo/mes</td><td style='font-family:Share Tech Mono;color:#00E676;text-align:right;'>${ahorro_mes_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Ingreso inyección/mes</td><td style='font-family:Share Tech Mono;color:#FF6B35;text-align:right;'>${ing_iny_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;background:#1A2235;'><td style='color:#00E676;font-weight:600;'>Beneficio mensual</td><td style='font-family:Share Tech Mono;color:#00E676;text-align:right;font-weight:700;'>${ben_mes_h:,.0f}</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Gen. anual estimada</td><td style='font-family:Share Tech Mono;color:#FFD54F;text-align:right;'>{gen_anio_h:,.0f} kWh</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>CO₂ evitado / año</td><td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{co2_h:,.0f} kg</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>Árboles equivalentes</td><td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>≈{arboles_h:.0f} árboles/año</td></tr>
                        <tr style='border-bottom:1px solid #2A3A55;'><td style='color:#8A9BBD;'>TIR simplificada</td><td style='font-family:Share Tech Mono;color:#00BCD4;text-align:right;'>{tir_h:.1f}%/año</td></tr>
                        <tr><td style='color:#8A9BBD;'>Autonomía batería</td><td style='font-family:Share Tech Mono;color:#A78BFA;text-align:right;'>{aut_h_e:.1f} h</td></tr>
                    </table>
                </div>""", unsafe_allow_html=True)

                session_state["_hib_inv_tot"]   = inv_tot_h
                session_state["_hib_ben_anio"]  = ben_anio_h
                session_state["_hib_payback"]   = payback_h
                session_state["_hib_gen_anio"]  = gen_anio_h
                session_state["_hib_co2_anio"]  = co2_h

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H7 — PLANO DISTRIBUCIÓN PANELES
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h7:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>7</span>
        PLANO — DISTRIBUCIÓN DE PANELES HÍBRIDO</div>""", unsafe_allow_html=True)

        n_pan_p7  = session_state.get("_hib_n_pan",     0)
        pan_s_p7  = session_state.get("_hib_pan_serie", 6)
        n_str_p7  = session_state.get("_hib_n_strings", 1)
        wp_p7     = session_state.get("hib_wp",         pot_panel_def)
        n_bats_p7 = session_state.get("_hib_n_baterias",4)

        if n_pan_p7 == 0:
            st.markdown("<div class='warn-box'>⚠ Completa el dimensionamiento en el Tab 5 primero.</div>",
                        unsafe_allow_html=True)
        else:
            conn = get_conn()
            p_info7 = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
            conn.close()

            svg7 = svg_plano_paneles_hib(n_pan_p7, pan_s_p7, n_str_p7, wp_p7, n_bats_p7, p_info7)
            render_svg_hib(svg7, height=730)

            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            cols7 = st.columns(3)
            arr_cols7 = min(pan_s_p7, 18)
            arr_rows7 = math.ceil(n_pan_p7 / arr_cols7)
            v_str7    = session_state.get("_hib_v_str_mpp", pan_s_p7 * session_state.get("hib_vmpp", 40.0))
            i_arr7    = session_state.get("_hib_i_array",   n_str_p7 * session_state.get("hib_impp", 13.0))
            cap_rw7   = session_state.get("_hib_cap_real_wh", 0)
            aut7      = session_state.get("_hib_aut_horas", 0)

            with cols7[0]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#F59E0B;font-weight:600;margin-bottom:0.6rem;'>ARRAY HÍBRIDO</div>
                    <div style='font-size:0.82rem;line-height:1.9;'>
                        🔆 Paneles: <b style='color:#FFD54F;'>{n_pan_p7} × {wp_p7} Wp</b><br>
                        📐 Config: <b style='color:#FFD54F;'>{pan_s_p7}S × {n_str_p7}P</b><br>
                        🏭 Pot. inst.: <b style='color:#FFD54F;'>{n_pan_p7*wp_p7/1000:.2f} kWp</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols7[1]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#F59E0B;font-weight:600;margin-bottom:0.6rem;'>DIMENSIONES</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        Cols: <b style='color:#00BCD4;'>{arr_cols7}</b>  Filas: <b style='color:#00BCD4;'>{arr_rows7}</b><br>
                        Ancho: <b style='color:#00BCD4;'>≈{arr_cols7*1.134:.2f} m</b><br>
                        Alto: <b style='color:#00BCD4;'>≈{arr_rows7*0.686:.2f} m</b><br>
                        Área: <b style='color:#00E676;'>≈{arr_cols7*1.134*arr_rows7*0.686:.1f} m²</b>
                    </div>
                </div>""", unsafe_allow_html=True)
            with cols7[2]:
                st.markdown(f"""
                <div class='sol-card'>
                    <div style='font-family:Rajdhani,sans-serif;color:#A78BFA;font-weight:600;margin-bottom:0.6rem;'>BATERÍAS</div>
                    <div style='font-size:0.82rem;line-height:1.9;font-family:Share Tech Mono,monospace;'>
                        N° unidades: <b style='color:#A78BFA;'>{n_bats_p7}</b><br>
                        Cap. banco: <b style='color:#A78BFA;'>{cap_rw7/1000:.1f} kWh</b><br>
                        Autonomía: <b style='color:#00E676;'>{aut7:.1f} h</b><br>
                        Vmpp str.: <b style='color:#00BCD4;'>{v_str7:.0f} V</b>
                    </div>
                </div>""", unsafe_allow_html=True)

            proy7_nom = (p_info7[1] if p_info7 else "Proyecto").replace(" ","_")
            fname7 = f"Hibrido_Paneles_{proy7_nom}_{datetime.now().strftime('%Y%m%d')}.svg"
            st.download_button("⬇ Descargar Plano Paneles (SVG)",
                               data=svg7.encode(), file_name=fname7,
                               mime="image/svg+xml", use_container_width=True, key="hib_dl_pan")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB H8 — DIAGRAMA UNIFILAR HÍBRIDO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_h8:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>8</span>
        DIAGRAMA UNIFILAR — SISTEMA HÍBRIDO</div>""", unsafe_allow_html=True)

        n_pan_p8   = session_state.get("_hib_n_pan",      0)
        pan_s_p8   = session_state.get("_hib_pan_serie",  6)
        n_str_p8   = session_state.get("_hib_n_strings",  1)
        wp_p8      = session_state.get("hib_wp",          pot_panel_def)
        pot_inv_p8 = session_state.get("_hib_pot_inv",    3.0)
        v_str_p8   = session_state.get("_hib_v_str_mpp",  pan_s_p8 * session_state.get("hib_vmpp",40.0))
        v_oc_p8    = session_state.get("_hib_v_str_oc",   pan_s_p8 * session_state.get("hib_voc", voc_def))
        i_arr_p8   = session_state.get("_hib_i_array",    n_str_p8 * session_state.get("hib_impp",13.0))
        n_bats_p8  = session_state.get("_hib_n_baterias", 4)
        v_bat_p8   = session_state.get("hib_v_bat",       48)
        cap_bat_p8 = session_state.get("hib_cap_bat",     100)
        consumo_p8 = session_state.get("hib_consumo_fs",  consumo_inv * 1.15)
        hsp_p8     = session_state.get("_hib_hsp",        hsp_guardado or 4.2)

        if n_pan_p8 == 0:
            st.markdown("<div class='warn-box'>⚠ Completa el dimensionamiento en el Tab 5 primero.</div>",
                        unsafe_allow_html=True)
        else:
            conn = get_conn()
            p_info8 = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
            conn.close()

            svg8 = svg_unifilar_hibrido(
                n_pan_p8, pan_s_p8, n_str_p8, wp_p8, pot_inv_p8,
                v_str_p8, v_oc_p8, i_arr_p8,
                n_bats_p8, v_bat_p8, cap_bat_p8,
                consumo_p8, hsp_p8, p_info8)
            render_svg_hib(svg8, height=740)

            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            cols8 = st.columns(4)
            gen8   = session_state.get("_hib_gen_dia", 0)
            pay8   = session_state.get("_hib_payback", 0)
            co2_8  = session_state.get("_hib_co2_anio",0)
            aut_8  = session_state.get("_hib_aut_horas",0)

            for c8, icon, lbl, val, col8 in [
                (cols8[0],"☀","Array FV",      f"{n_pan_p8}×{wp_p8}Wp\n{n_pan_p8*wp_p8/1000:.2f}kWp", "#FFB300"),
                (cols8[1],"🔋","Baterías",      f"{n_bats_p8} ud.\n{session_state.get('_hib_cap_real_wh',0)/1000:.1f}kWh · {aut_8:.0f}h", "#A78BFA"),
                (cols8[2],"🔄","Inversor Híb.", f"{pot_inv_p8}kW\nMPPT+Charger", "#F59E0B"),
                (cols8[3],"🌿","CO₂ evitado",  f"{co2_8:,.0f}kg/año\nPayback:{pay8:.1f}a", "#00E676"),
            ]:
                with c8:
                    st.markdown(f"""
                    <div class='sol-card' style='text-align:center;'>
                        <div style='font-size:1.5rem;'>{icon}</div>
                        <div style='font-family:Rajdhani;font-size:0.8rem;color:{col8};font-weight:600;margin:0.3rem 0;'>{lbl}</div>
                        <div style='font-family:Share Tech Mono;font-size:0.75rem;color:#8A9BBD;white-space:pre;'>{val}</div>
                    </div>""", unsafe_allow_html=True)

            proy8_nom = (p_info8[1] if p_info8 else "Proyecto").replace(" ","_")
            fname8 = f"Hibrido_Unifilar_{proy8_nom}_{datetime.now().strftime('%Y%m%d')}.svg"
            st.download_button("⬇ Descargar Diagrama Unifilar (SVG)",
                               data=svg8.encode(), file_name=fname8,
                               mime="image/svg+xml", use_container_width=True, key="hib_dl_uni")

    # Footer
    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem;color:#2A3A55;font-size:0.75rem;letter-spacing:2px;'>
        SOLARCALC PRO · SISTEMA FOTOVOLTAICO HÍBRIDO · CREG 030-2018 · RETIE · NTC 2050
    </div>""", unsafe_allow_html=True)
