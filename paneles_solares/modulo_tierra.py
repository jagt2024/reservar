# modulo_tierra.py — SolarCalc Pro · Puesta a Tierra
# ─────────────────────────────────────────────────────────────────────────────
"""
Módulo de diseño y medición de puesta a tierra para sistemas fotovoltaicos.
Basado en norma ENEL-Codensa LA-400 (revisión 03-04-2017) y RETIE Colombia.

Funcionalidades:
  1. Diseño del sistema de tierra (electrodo, conductor, configuración)
  2. Captura medidas - Método Caída de Tensión (LA-400 Fig.1)
  3. Captura medidas - Resistividad por Método Wenner / 4 puntos (LA-400 Fig.2)
  4. Validación automática vs límites RETIE
  5. Cálculo número de varillas según resistividad del terreno
  6. Historial de mediciones por proyecto
  7. Exportación PDF informe LA-400 (formato oficial)
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import io
import os
import json
import pathlib
import tempfile
from datetime import datetime, date

from reportlab.lib.pagesizes import A4
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

# ─── INIT TABLAS ──────────────────────────────────────────────────────────────
def init_tierra_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tierra_diseno (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id     INTEGER NOT NULL,
            tipo_sistema    TEXT DEFAULT 'TT',
            electrodo_tipo  TEXT DEFAULT 'VARILLA',
            electrodo_dim   TEXT,
            n_varillas      INTEGER DEFAULT 1,
            separacion_m    REAL DEFAULT 5.0,
            conductor_cal   TEXT DEFAULT '4 AWG',
            conductor_mat   TEXT DEFAULT 'Cobre cobrizado',
            resistividad    REAL DEFAULT 50.0,
            r_objetivo      REAL DEFAULT 25.0,
            tratamiento     TEXT DEFAULT 'Ninguno',
            observaciones   TEXT,
            creado          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tierra_mediciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id     INTEGER NOT NULL,
            metodo          TEXT NOT NULL,
            lugar           TEXT,
            punto_sig       TEXT,
            direccion       TEXT,
            fecha_med       TEXT,
            estado_terreno  TEXT DEFAULT 'Seco',
            equipo          TEXT,
            mediciones_json TEXT,
            r_promedio      REAL,
            r_valido        INTEGER DEFAULT 0,
            cumple_retie    INTEGER DEFAULT 0,
            limite_retie    REAL DEFAULT 25.0,
            tipo_instalacion TEXT DEFAULT 'Sistema FV',
            observaciones   TEXT,
            creado          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tierra_wenner (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id     INTEGER NOT NULL,
            medicion_id     INTEGER,
            lugar           TEXT,
            fecha_med       TEXT,
            estado_terreno  TEXT DEFAULT 'Seco',
            equipo          TEXT,
            mediciones_json TEXT,
            observaciones   TEXT,
            creado          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    conn.commit()
    conn.close()

# ─── CONSTANTES RETIE ─────────────────────────────────────────────────────────
LIMITES_RETIE = {
    "Subestación media tensión":        10.0,
    "Estructura con cable de guarda":   20.0,
    "Neutro acometida baja tensión":    25.0,
    "Electrodo general (RETIE/NTC2050)":25.0,
    "Sistema fotovoltaico (RETIE)":     25.0,
    "Banco de condensadores":            5.0,
}

RESISTIVIDADES_TERRENO = {
    "Tierra negra húmeda":     10,
    "Tierra negra seca":       50,
    "Arcilla húmeda":          20,
    "Arcilla seca":           100,
    "Arena húmeda":            50,
    "Arena seca":             200,
    "Grava húmeda":           500,
    "Roca blanda":           1000,
    "Roca dura":             3000,
    "Concreto (relleno)":      40,
    "Bentonita (relleno)":    2.5,
    "Gel conductor":          0.5,
    "Personalizado":           50,
}

TRATAMIENTOS_SUELO = {
    "Ninguno":              None,
    "Tierra negra":         50,
    "Concreto":             40,
    "Bentonita":           2.5,
    "Gel conductor":        0.5,
    "Sales minerales":      15,
}

# ─── CÁLCULOS ────────────────────────────────────────────────────────────────
def calcular_r_varilla(rho: float, L: float = 2.44, d: float = 0.016) -> float:
    """Resistencia teórica de una varilla enterrada (Fórmula de Dwight)."""
    if rho <= 0 or L <= 0 or d <= 0:
        return 999.0
    return (rho / (2 * math.pi * L)) * (math.log(4 * L / d) - 1)

def calcular_r_n_varillas(rho: float, n: int, L: float = 2.44,
                           d: float = 0.016, s: float = 5.0) -> float:
    """Resistencia de n varillas en paralelo con factor de apantallamiento."""
    r1 = calcular_r_varilla(rho, L, d)
    if n <= 1:
        return r1
    # Factor de reducción empírico (IEEE 142)
    factor = 1 + (0.7 * r1) / (n * s)
    return r1 / (n * factor)

def varillas_necesarias(rho: float, r_obj: float,
                         L: float = 2.44, d: float = 0.016,
                         s: float = 5.0) -> int:
    """Cantidad de varillas para cumplir r_objetivo."""
    for n in range(1, 21):
        if calcular_r_n_varillas(rho, n, L, d, s) <= r_obj:
            return n
    return 20

def validar_retie(r: float, tipo: str) -> dict:
    limite = LIMITES_RETIE.get(tipo, 25.0)
    cumple = r <= limite
    margen = ((limite - r) / limite * 100) if limite > 0 else 0
    return {"cumple": cumple, "limite": limite, "margen": margen}

def promedio_con_validacion(valores: list) -> dict:
    """Calcula promedio y verifica que ningún valor difiera más de ±5%."""
    vals = [v for v in valores if v is not None and v > 0]
    if not vals:
        return {"promedio": None, "valido": False, "max_error_pct": None, "n": 0}
    prom = sum(vals) / len(vals)
    errores = [abs(v - prom) / prom * 100 for v in vals]
    max_err = max(errores) if errores else 0
    return {
        "promedio":     round(prom, 3),
        "valido":       max_err <= 5.0,
        "max_error_pct": round(max_err, 2),
        "n":            len(vals),
        "errores_pct":  [round(e, 2) for e in errores],
    }

# ─── GENERADOR PDF ────────────────────────────────────────────────────────────
def generar_pdf_tierra(datos: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=2*cm, bottomMargin=1.8*cm)

    # Paleta
    SOL    = colors.HexColor("#FFB300")
    DARK   = colors.HexColor("#0A0E1A")
    TEXT   = colors.HexColor("#212121")
    TEXT2  = colors.HexColor("#616161")
    GREEN  = colors.HexColor("#2E7D32")
    RED    = colors.HexColor("#C62828")
    LGRAY  = colors.HexColor("#F5F5F5")
    MGRAY  = colors.HexColor("#E0E0E0")
    DGRAY  = colors.HexColor("#424242")
    BORDER = colors.HexColor("#BDBDBD")
    BLUE   = colors.HexColor("#1565C0")
    WHITE  = colors.white

    def est(name, font="Helvetica", size=9, color=TEXT, align=TA_LEFT,
            bold=False, sb=0, sa=4):
        return ParagraphStyle(name, fontName=font+("-Bold" if bold else ""),
                               fontSize=size, textColor=color, alignment=align,
                               spaceBefore=sb, spaceAfter=sa, leading=size*1.4)

    st_tit  = est("tit",  size=16, color=BLUE,  bold=True, align=TA_CENTER)
    st_sub  = est("sub",  size=9,  color=TEXT2, align=TA_CENTER)
    st_sec  = est("sec",  size=11, color=BLUE,  bold=True, sb=8, sa=3)
    st_body = est("body", size=9,  color=TEXT)
    st_lbl  = est("lbl",  size=8,  color=TEXT2)
    st_val  = est("val",  size=9,  color=TEXT,  bold=True)
    st_ok   = est("ok",   size=10, color=GREEN, bold=True, align=TA_CENTER)
    st_fail = est("fail", size=10, color=RED,   bold=True, align=TA_CENTER)
    st_foot = est("foot", size=7,  color=TEXT2, align=TA_CENTER)
    st_ctr  = est("ctr",  size=9,  color=TEXT,  align=TA_CENTER)

    def hr(c=BORDER, t=0.8, sa=4):
        return HRFlowable(width="100%", thickness=t, color=c, spaceAfter=sa)
    def p(txt, s=None): return Paragraph(txt, s or st_body)
    def sp(h=0.3): return Spacer(1, h*cm)

    story = []
    proy  = datos.get("proyecto", {})
    dis   = datos.get("diseno", {})
    meds  = datos.get("mediciones", [])
    wen   = datos.get("wenner", [])
    fecha = datos.get("fecha", date.today().strftime("%d/%m/%Y"))

    # ── Cabecera ──────────────────────────────────────────────────────────────
    story.append(p("INFORME DE PUESTA A TIERRA", st_tit))
    story.append(p("Norma ENEL-Codensa LA-400 · RETIE Colombia · NTC 2050", st_sub))
    story.append(sp(0.3))
    story.append(hr(BLUE, 1.5))

    # Datos generales
    gen_data = [
        ["Proyecto:",    proy.get("nombre",""),      "Municipio:",    proy.get("municipio","")],
        ["Lugar:",       meds[0].get("lugar","") if meds else "",
         "Fecha:",       fecha],
        ["Dirección:",   meds[0].get("direccion","") if meds else "",
         "Tipo sistema:", dis.get("tipo_sistema","TT")],
        ["Elaboró:",     proy.get("elaboro",""),     "Revisó:",       proy.get("reviso","")],
    ]
    t_gen = Table(gen_data, colWidths=[2.5*cm, 5.5*cm, 2.5*cm, 5.5*cm])
    t_gen.setStyle(TableStyle([
        ("FONTNAME",     (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",     (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTNAME",     (2,0), (2,-1),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8),
        ("TEXTCOLOR",    (0,0), (0,-1),  TEXT2),
        ("TEXTCOLOR",    (2,0), (2,-1),  TEXT2),
        ("BACKGROUND",   (0,0), (-1,-1), LGRAY),
        *[("BACKGROUND", (0,i), (-1,i), WHITE) for i in range(0,4,2)],
        ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_gen)
    story.append(sp(0.4))

    # ── Diseño del sistema ────────────────────────────────────────────────────
    story.append(p("1. DISEÑO DEL SISTEMA DE PUESTA A TIERRA", st_sec))
    story.append(hr())
    dis_data = [
        ["PARÁMETRO", "VALOR", "PARÁMETRO", "VALOR"],
        ["Tipo sistema tierra", dis.get("tipo_sistema","TT"),
         "N° electrodos", str(dis.get("n_varillas",1))],
        ["Electrodo", dis.get("electrodo_dim","5/8\" × 2.44 m"),
         "Separación varillas", f"{dis.get('separacion_m',5.0):.1f} m"],
        ["Conductor", dis.get("conductor_cal","4 AWG"),
         "Material conductor", dis.get("conductor_mat","Cu cobrizado")],
        ["Resistividad terreno", f"{dis.get('resistividad',50.0):.1f} Ω·m",
         "Tratamiento suelo", dis.get("tratamiento","Ninguno")],
        ["R. objetivo (RETIE)", f"≤ {dis.get('r_objetivo',25.0):.0f} Ω",
         "R. calculada (Dwight)", f"{dis.get('r_calculada',0.0):.2f} Ω"],
    ]
    t_dis = Table(dis_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
    t_dis.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), BLUE),
        ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,0), 8),
        ("ALIGN",        (0,0), (-1,0), "CENTER"),
        *[("BACKGROUND", (0,i), (-1,i), WHITE if i%2==1 else LGRAY) for i in range(1,6)],
        ("TEXTCOLOR",    (0,1), (0,-1), TEXT2),
        ("TEXTCOLOR",    (2,1), (2,-1), TEXT2),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,1), (-1,-1), 8),
        ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_dis)
    story.append(sp(0.4))

    # ── Mediciones Caída de Tensión ────────────────────────────────────────────
    if meds:
        story.append(p("2. MEDIDA DE RESISTENCIA — MÉTODO CAÍDA DE TENSIÓN (LA-400)", st_sec))
        story.append(hr())
        story.append(p(
            "Según norma LA-400 Fig.1: D₂ = 0.62 × D₁. "
            "Se realizan 3 mediciones mínimo. El promedio es válido si ningún valor "
            "difiere más de ±5% del promedio (RETIE art. 15).", st_body))
        story.append(sp(0.2))

        for idx, med in enumerate(meds, 1):
            filas_med = med.get("filas", [])
            lugar_m   = med.get("lugar", "")
            fecha_m   = med.get("fecha_med", "")
            equipo_m  = med.get("equipo", "")
            estado_m  = med.get("estado_terreno", "Seco")
            tipo_ins  = med.get("tipo_instalacion", "Sistema FV")
            r_prom    = med.get("r_promedio")
            valido    = med.get("r_valido", False)
            cumple    = med.get("cumple_retie", False)
            limite_r  = med.get("limite_retie", 25.0)
            obs_m     = med.get("observaciones", "")

            story.append(p(f"Medición {idx}: {lugar_m} — {fecha_m} — Terreno: {estado_m} — "
                           f"Equipo: {equipo_m}", st_lbl))

            # Tabla datos medición LA-400 (formato oficial)
            rows_med = [["D₁ (m)", "D₂ (m)", "R (Ω)", "D₁* (m)", "D₂* (m)", "R* (Ω)", "OBSERVACIONES"]]
            for fila in filas_med:
                rows_med.append([
                    str(fila.get("d1","—")),
                    str(fila.get("d2","—")),
                    f"{fila.get('r','')}" if fila.get("r") not in (None,"") else "—",
                    str(fila.get("d1s","—")),
                    str(fila.get("d2s","—")),
                    f"{fila.get('rs','')}" if fila.get("rs") not in (None,"") else "—",
                    fila.get("obs",""),
                ])
            rows_med.append(["PROMEDIO", "", f"{r_prom:.3f} Ω" if r_prom else "—",
                              "", "", "", "* Segunda medición si error > 5%"])

            t_med = Table(rows_med, colWidths=[1.8*cm,1.8*cm,2*cm,1.8*cm,1.8*cm,2*cm,4.8*cm],
                          repeatRows=1)
            n_r = len(rows_med)
            t_med.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,0), BLUE),
                ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0), (-1,-1), 8),
                ("ALIGN",        (0,0), (5,-1),  "CENTER"),
                ("ALIGN",        (6,1), (6,-1),  "LEFT"),
                *[("BACKGROUND", (0,i), (-1,i), WHITE if i%2==1 else LGRAY) for i in range(1,n_r-1)],
                ("BACKGROUND",   (0,n_r-1), (-1,n_r-1),
                 colors.HexColor("#E8F5E9") if cumple else colors.HexColor("#FFEBEE")),
                ("FONTNAME",     (0,n_r-1), (-1,n_r-1), "Helvetica-Bold"),
                ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
                ("TOPPADDING",   (0,0), (-1,-1), 3),
                ("BOTTOMPADDING",(0,0), (-1,-1), 3),
                ("LEFTPADDING",  (0,0), (-1,-1), 4),
                ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ]))
            story.append(t_med)

            # Resultado validación
            col_val = GREEN if cumple else RED
            estado_val = (
                f"✓ CUMPLE RETIE: R = {r_prom:.3f} Ω ≤ {limite_r:.0f} Ω "
                f"({tipo_ins})"
            ) if cumple else (
                f"✗ NO CUMPLE RETIE: R = {r_prom:.3f} Ω > {limite_r:.0f} Ω "
                f"— Se requieren medidas correctivas"
            )
            prom_valido_txt = (
                "Promedio estadísticamente válido (error < 5%)"
                if valido else
                "AVISO: variación > 5% — repetir con D₁ y D₂ mayores (D₂ = 0.62×D₁)"
            )
            t_res = Table([[p(estado_val, est("rv", size=9, color=WHITE, bold=True,
                                               align=TA_CENTER))]],
                          colWidths=[16*cm])
            t_res.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), col_val),
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ]))
            story.append(t_res)
            story.append(p(prom_valido_txt, st_lbl))
            if obs_m:
                story.append(p(f"Observaciones: {obs_m}", st_lbl))
            story.append(sp(0.3))

    # ── Wenner ────────────────────────────────────────────────────────────────
    if wen:
        story.append(p("3. MEDIDA DE RESISTIVIDAD — MÉTODO WENNER / 4 PUNTOS (LA-400)", st_sec))
        story.append(hr())
        story.append(p(
            "Electrodos alineados e igualmente espaciados. "
            "Resistividad: ρ = 2πDR (Ω·m). Sugiere medidas con D = 1, 2, 5, 10, 20, 30 m.",
            st_body))
        story.append(sp(0.2))

        for idx, w in enumerate(wen, 1):
            filas_w = w.get("filas", [])
            story.append(p(f"Medición Wenner {idx}: {w.get('lugar','')} — "
                           f"{w.get('fecha_med','')} — Terreno: {w.get('estado_terreno','Seco')} — "
                           f"Equipo: {w.get('equipo','')}", st_lbl))
            rows_w = [["D (m)", "R (Ω)", "ρ = 2πDR (Ω·m)", "OBSERVACIONES"]]
            for fw in filas_w:
                d_v   = fw.get("d")
                r_v   = fw.get("r")
                rho_v = round(2 * math.pi * d_v * r_v, 2) if (d_v and r_v) else None
                rows_w.append([
                    str(d_v) if d_v else "—",
                    f"{r_v:.3f}" if r_v else "—",
                    f"{rho_v:.1f}" if rho_v else "—",
                    fw.get("obs",""),
                ])
            t_w = Table(rows_w, colWidths=[2*cm, 3*cm, 5*cm, 6*cm], repeatRows=1)
            t_w.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,0), BLUE),
                ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0), (-1,-1), 8),
                ("ALIGN",        (0,0), (2,-1),  "CENTER"),
                ("ALIGN",        (3,1), (3,-1),  "LEFT"),
                *[("BACKGROUND", (0,i), (-1,i), WHITE if i%2==1 else LGRAY)
                  for i in range(1, len(rows_w))],
                ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
                ("TOPPADDING",   (0,0), (-1,-1), 3),
                ("BOTTOMPADDING",(0,0), (-1,-1), 3),
                ("LEFTPADDING",  (0,0), (-1,-1), 4),
                ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ]))
            story.append(t_w)
            if w.get("observaciones"):
                story.append(p(f"Observaciones: {w['observaciones']}", st_lbl))
            story.append(sp(0.3))

    # ── Resumen RETIE ─────────────────────────────────────────────────────────
    story.append(p("4. RESUMEN VALIDACIÓN RETIE", st_sec))
    story.append(hr())
    story.append(p(
        "Valores máximos de resistencia de puesta a tierra exigidos por RETIE Colombia "
        "y NTC 2050 Sección 250-84:", st_body))
    retie_rows = [["TIPO DE INSTALACIÓN", "LÍMITE RETIE (Ω)", "NORMA"]]
    retie_info = [
        ("Subestación media tensión",        "≤ 10",  "RETIE art. 15"),
        ("Estructura con cable de guarda",   "≤ 20",  "RETIE art. 15"),
        ("Neutro acometida baja tensión",    "≤ 25",  "RETIE art. 15"),
        ("Sistema fotovoltaico (RETIE)",     "≤ 25",  "RETIE / NTC2050 §250-84"),
        ("Banco de condensadores",           "≤ 5",   "LA-400 / RETIE"),
        ("Electrodo general NTC 2050",       "≤ 25",  "NTC 2050 §250-84"),
    ]
    for tipo_r, lim_r, norma_r in retie_info:
        retie_rows.append([tipo_r, lim_r, norma_r])
    t_retie = Table(retie_rows, colWidths=[8*cm, 3.5*cm, 4.5*cm], repeatRows=1)
    t_retie.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), BLUE),
        ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8),
        ("ALIGN",        (1,0), (1,-1),  "CENTER"),
        *[("BACKGROUND", (0,i), (-1,i), WHITE if i%2==1 else LGRAY) for i in range(1,7)],
        ("TEXTCOLOR",    (0,1), (-1,-1), DGRAY),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_retie)
    story.append(sp(0.3))

    # Resultado general
    all_cumple = all(m.get("cumple_retie", False) for m in meds) if meds else None
    if all_cumple is True:
        res_txt = "RESULTADO GENERAL: SISTEMA CUMPLE con RETIE — Todas las mediciones dentro del límite"
        res_col = GREEN
    elif all_cumple is False:
        res_txt = "RESULTADO GENERAL: SISTEMA NO CUMPLE con RETIE — Revisar y corregir"
        res_col = RED
    else:
        res_txt = "RESULTADO GENERAL: Pendiente de medición"
        res_col = colors.HexColor("#FF8F00")

    t_final = Table([[p(res_txt, est("rf", size=10, color=WHITE, bold=True,
                                      align=TA_CENTER))]],
                    colWidths=[16*cm])
    t_final.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), res_col),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.append(t_final)

    # ── Firmas ────────────────────────────────────────────────────────────────
    story.append(sp(0.8))
    story.append(hr(BORDER, 0.5))
    t_firma = Table([[
        Table([
            [p("_"*30, st_ctr)],
            [p(proy.get("elaboro","Técnico responsable"), st_ctr)],
            [p("Elaboró / Midió", st_lbl)],
        ], colWidths=[7*cm]),
        Table([
            [p("_"*30, st_ctr)],
            [p(proy.get("reviso","Ing. supervisor"), st_ctr)],
            [p("Revisó / Aprobó", st_lbl)],
        ], colWidths=[7*cm]),
    ]], colWidths=[8*cm, 8*cm])
    t_firma.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                  ("LEFTPADDING",(0,0),(-1,-1),0)]))
    story.append(t_firma)

    # Footer
    story.append(sp(0.3))
    story.append(hr(SOL, 1))
    story.append(p(
        f"SOLARCALC PRO  ·  Informe Puesta a Tierra  ·  Norma LA-400 / RETIE  ·  "
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        st_foot))

    doc.build(story)
    buf.seek(0)
    return buf.read()

# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────
def mostrar_tierra(proyecto_id: int, session_state: dict):
    init_tierra_db()

    conn  = get_conn()
    p_inf = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    dis_r = conn.execute(
        "SELECT * FROM tierra_diseno WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    meds_df = pd.read_sql(
        "SELECT * FROM tierra_mediciones WHERE proyecto_id=? ORDER BY id DESC",
        conn, params=(proyecto_id,))
    wen_df  = pd.read_sql(
        "SELECT * FROM tierra_wenner WHERE proyecto_id=? ORDER BY id DESC",
        conn, params=(proyecto_id,))
    conn.close()

    if not p_inf:
        st.error("Proyecto no encontrado.")
        return

    # Cabecera
    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>⏚ PUESTA A TIERRA
            <span style='font-size:0.5em;background:#1565C0;color:#fff;padding:2px 12px;
                border-radius:20px;margin-left:10px;vertical-align:middle;letter-spacing:1px;'>
                LA-400 · RETIE</span>
        </div>
        <div class='hero-sub'>DISEÑO · MEDICIÓN · VALIDACIÓN NORMATIVA</div>
    </div>
    """, unsafe_allow_html=True)

    tab_dis, tab_cdt, tab_wen, tab_hist, tab_pdf = st.tabs([
        "⚙ Diseño", "📏 Caída de Tensión", "🔬 Wenner / 4 Puntos",
        "📋 Historial", "📄 Informe PDF"
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — DISEÑO DEL SISTEMA
    # ══════════════════════════════════════════════════════════════════════════
    with tab_dis:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>1</span>
        DISEÑO DEL SISTEMA DE PUESTA A TIERRA</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='info-note'>
            Norma LA-400: electrodo recomendado varilla cobrizada 5/8" × 2.44 m,
            conductor Cu cobrizado (copperweld) No. 4 AWG.
            Sistema TT para instalaciones FV según RETIE.
        </div>""", unsafe_allow_html=True)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            st.markdown("**Parámetros del electrodo**")

            tipo_sis = st.selectbox(
                "Sistema de tierra", ["TT", "TN-S", "TN-C-S", "IT"],
                index=0, key="t_tipo_sis",
                help="TT: neutro y masas a tierra independientes (recomendado FV)")
            electrodo_dim = st.text_input(
                "Dimensión electrodo",
                value=dis_r[4] if dis_r and dis_r[4] else '5/8" × 2.44 m (varilla Cu cobrizada)',
                key="t_elec_dim")
            conductor_cal = st.selectbox(
                "Calibre conductor tierra",
                ["4 AWG", "2 AWG", "1/0 AWG", "2/0 AWG", "4 AWG copperweld", "6 mm²", "10 mm²", "16 mm²"],
                index=0, key="t_cond_cal")
            conductor_mat = st.selectbox(
                "Material conductor",
                ["Cobre cobrizado (copperweld)", "Cobre desnudo", "Fleje de acero", "Cable Cu trenzado"],
                index=0, key="t_cond_mat")

            st.markdown("**Resistividad del terreno (ρ)**")
            tipo_retie = st.selectbox(
                "Tipo de instalación (límite RETIE)",
                list(LIMITES_RETIE.keys()),
                index=list(LIMITES_RETIE.keys()).index("Sistema fotovoltaico (RETIE)"),
                key="t_tipo_retie")
            r_objetivo = LIMITES_RETIE[tipo_retie]
            st.markdown(f"""
            <div class='formula-box'>
                Límite RETIE para <b>{tipo_retie}</b>: <b style='color:#FFB300;'>R ≤ {r_objetivo:.0f} Ω</b>
            </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_d2:
            st.markdown("<div class='sol-card'>", unsafe_allow_html=True)
            st.markdown("**Resistividad y cálculo de varillas**")

            tipo_terreno = st.selectbox(
                "Tipo de terreno",
                list(RESISTIVIDADES_TERRENO.keys()),
                key="t_tipo_terreno")
            rho_default = RESISTIVIDADES_TERRENO[tipo_terreno]

            if tipo_terreno == "Personalizado":
                rho = st.number_input("Resistividad medida (Ω·m)",
                    min_value=0.5, max_value=10000.0, value=50.0, step=5.0, key="t_rho_custom")
            else:
                rho = st.number_input("Resistividad (Ω·m) — editable",
                    min_value=0.5, max_value=10000.0,
                    value=float(dis_r[9] if dis_r and dis_r[9] else rho_default),
                    step=5.0, key="t_rho")

            tratamiento = st.selectbox(
                "Tratamiento del suelo",
                list(TRATAMIENTOS_SUELO.keys()),
                key="t_tratamiento",
                help="Bentonita: ρ≈2.5 Ω·m  |  Gel: ρ<1 Ω·m  |  Concreto: ρ≈40 Ω·m")

            rho_ef = TRATAMIENTOS_SUELO[tratamiento] or rho

            # Cálculo automático
            L = 2.44  # m — longitud varilla estándar
            d = 0.016 # m — diámetro 5/8"

            r1     = calcular_r_varilla(rho_ef, L, d)
            n_var  = varillas_necesarias(rho_ef, r_objetivo, L, d, 5.0)
            sep_var = max(2 * L, 5.0)

            n_varillas = st.number_input(
                "N° de varillas (calculado automáticamente)",
                min_value=1, max_value=20,
                value=int(dis_r[5] if dis_r and dis_r[5] else n_var),
                key="t_n_var")

            r_calc = calcular_r_n_varillas(rho_ef, n_varillas, L, d, sep_var)
            cumple_calc = r_calc <= r_objetivo

            st.markdown(f"""
            <div class='sol-card' style='margin-top:0.6rem;'>
                <div style='color:#1565C0;font-family:Rajdhani,sans-serif;font-weight:700;
                            margin-bottom:0.6rem;'>CÁLCULO (fórmula de Dwight)</div>
                <table style='width:100%;font-size:0.82rem;border-collapse:collapse;'>
                    <tr style='border-bottom:1px solid #E0E0E0;'>
                        <td style='color:#616161;padding:0.3rem 0;'>ρ efectiva</td>
                        <td style='font-family:Share Tech Mono;text-align:right;'>{rho_ef:.1f} Ω·m</td>
                    </tr>
                    <tr style='border-bottom:1px solid #E0E0E0;'>
                        <td style='color:#616161;padding:0.3rem 0;'>R₁ varilla (Dwight)</td>
                        <td style='font-family:Share Tech Mono;text-align:right;'>{r1:.2f} Ω</td>
                    </tr>
                    <tr style='border-bottom:1px solid #E0E0E0;'>
                        <td style='color:#616161;padding:0.3rem 0;'>Varillas mínimas para ≤{r_objetivo:.0f} Ω</td>
                        <td style='font-family:Share Tech Mono;color:#FFB300;font-weight:700;text-align:right;'>{n_var} und</td>
                    </tr>
                    <tr style='border-bottom:1px solid #E0E0E0;'>
                        <td style='color:#616161;padding:0.3rem 0;'>R calculada ({n_varillas} varillas)</td>
                        <td style='font-family:Share Tech Mono;color:{"#2E7D32" if cumple_calc else "#C62828"};
                                   font-weight:700;text-align:right;'>{r_calc:.2f} Ω</td>
                    </tr>
                    <tr>
                        <td style='color:#616161;padding:0.3rem 0;'>Separación mínima entre varillas</td>
                        <td style='font-family:Share Tech Mono;text-align:right;'>{sep_var:.1f} m</td>
                    </tr>
                </table>
                <div style='margin-top:0.6rem;background:{"#E8F5E9" if cumple_calc else "#FFEBEE"};
                            border-radius:6px;padding:0.5rem;text-align:center;
                            font-weight:700;font-size:0.85rem;
                            color:{"#2E7D32" if cumple_calc else "#C62828"};'>
                    {"✓ CUMPLE RETIE" if cumple_calc else "✗ NO CUMPLE — Agregar más varillas o tratamiento"}
                </div>
            </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Tabla guía de resistividades (LA-400)
        with st.expander("📋 Guía de resistividades y tratamientos (LA-400)", expanded=False):
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("**Resistividades típicas de terreno**")
                df_rho = pd.DataFrame([
                    {"Tipo terreno": k, "ρ (Ω·m)": v}
                    for k, v in RESISTIVIDADES_TERRENO.items()
                    if k != "Personalizado"
                ])
                st.dataframe(df_rho.set_index("Tipo terreno"), use_container_width=True)
            with col_g2:
                st.markdown("**Criterio N° varillas (LA-400)**")
                df_crit = pd.DataFrame([
                    {"ρ terreno":  "< 63 Ω·m",   "Varillas": 1, "Acción": "1 varilla estándar"},
                    {"ρ terreno":  "< 110 Ω·m",  "Varillas": 2, "Acción": "2 varillas interconectadas"},
                    {"ρ terreno":  "< 150 Ω·m",  "Varillas": 3, "Acción": "3 varillas interconectadas"},
                    {"ρ terreno":  "≥ 150 Ω·m",  "Varillas": "3+","Acción": "Tratamiento suelo o malla"},
                ])
                st.dataframe(df_crit.set_index("ρ terreno"), use_container_width=True)

        # Guardar diseño
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        obs_dis = st.text_area("Observaciones del diseño", key="t_obs_dis",
                                placeholder="Condiciones del sitio, materiales disponibles, etc.",
                                height=70)

        if st.button("💾 Guardar Diseño del Sistema de Tierra", use_container_width=True,
                     key="t_save_dis", type="primary"):
            conn = get_conn()
            conn.execute("DELETE FROM tierra_diseno WHERE proyecto_id=?", (proyecto_id,))
            conn.execute("""
                INSERT INTO tierra_diseno(
                    proyecto_id, tipo_sistema, electrodo_tipo, electrodo_dim,
                    n_varillas, separacion_m, conductor_cal, conductor_mat,
                    resistividad, r_objetivo, tratamiento, observaciones)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                proyecto_id,
                session_state.get("t_tipo_sis", "TT"),
                "VARILLA",
                session_state.get("t_elec_dim", '5/8" × 2.44 m'),
                n_varillas,
                sep_var,
                session_state.get("t_cond_cal", "4 AWG"),
                session_state.get("t_cond_mat", "Cobre cobrizado (copperweld)"),
                rho_ef,
                r_objetivo,
                session_state.get("t_tratamiento", "Ninguno"),
                obs_dis,
            ))
            conn.commit(); conn.close()
            st.success("Diseño guardado ✓")
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — MÉTODO CAÍDA DE TENSIÓN (LA-400 Fig. 1)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cdt:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>2</span>
        MÉTODO DE CAÍDA DE TENSIÓN — LA-400 Figura 1</div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            <b>Principio:</b> D₂ = 0.62 × D₁  |  Mínimo 3 mediciones  |
            Promedio válido si ningún valor difiere más de ±5%<br>
            <b>Distancias estándar LA-400:</b>
            D₁=25m→D₂=15m  |  D₁=30m→D₂=18m  |  D₁=36m→D₂=22m
        </div>""", unsafe_allow_html=True)

        # Datos de la medición
        st.markdown("**Datos generales de la medición**")
        cdt_c1, cdt_c2, cdt_c3 = st.columns(3)
        with cdt_c1:
            cdt_lugar   = st.text_input("Lugar de medición", key="cdt_lugar",
                placeholder="Ej: Tablero principal / Varilla AT")
            cdt_pto_sig = st.text_input("Punto significativo", key="cdt_pto_sig",
                placeholder="Ej: PT-01")
            cdt_tipo_ins = st.selectbox("Tipo instalación (RETIE)",
                list(LIMITES_RETIE.keys()),
                index=list(LIMITES_RETIE.keys()).index("Sistema fotovoltaico (RETIE)"),
                key="cdt_tipo_ins")
        with cdt_c2:
            cdt_dir     = st.text_input("Dirección / Ubicación", key="cdt_dir",
                placeholder="Ej: Finca El Sol, Km 3 vía...")
            cdt_fecha   = st.date_input("Fecha medición", key="cdt_fecha", value=date.today())
            cdt_estado  = st.selectbox("Estado terreno", ["Seco", "Húmedo"],
                key="cdt_estado")
        with cdt_c3:
            cdt_equipo  = st.text_input("Equipo (telurómetro)", key="cdt_equipo",
                placeholder="Ej: Fluke 1625 GEO / Kyoritsu 4105A")
            cdt_obs_gral = st.text_input("Observaciones generales", key="cdt_obs_gral",
                placeholder="Condiciones ambientales, etc.")

        limite_cdt = LIMITES_RETIE.get(
            session_state.get("cdt_tipo_ins", "Sistema fotovoltaico (RETIE)"), 25.0)

        st.markdown("<hr class='sep' style='margin:0.8rem 0;'>", unsafe_allow_html=True)

        # ── Tabla de mediciones (primera serie) ───────────────────────────────
        st.markdown("**PRIMERA SERIE DE MEDICIONES** (distancias estándar LA-400)")

        # Encabezado visual
        _hcols = st.columns([1.4, 1.4, 1.6, 1.4, 1.4, 1.6, 3])
        for _hc, _ht in zip(_hcols,
                ["D₁ (m)", "D₂ (m)", "R (Ω)", "D₁* (m)", "D₂* (m)", "R* (Ω)", "Observaciones"]):
            _hc.markdown(
                f"<div style='font-size:0.72rem;color:#1565C0;font-weight:700;"
                f"text-align:center;'>{_ht}</div>", unsafe_allow_html=True)

        FILAS_DEFAULT = [
            {"d1": 25, "d2": 15, "d1s": 36, "d2s": 22},
            {"d1": 30, "d2": 18, "d1s": 42, "d2s": 25},
            {"d1": 36, "d2": 22, "d1s": 50, "d2s": 30},
        ]

        r_vals     = []
        rs_vals    = []
        filas_data = []

        for i, fdef in enumerate(FILAS_DEFAULT):
            cols = st.columns([1.4, 1.4, 1.6, 1.4, 1.4, 1.6, 3])
            with cols[0]:
                d1_v = st.number_input("", value=float(fdef["d1"]),
                    step=1.0, min_value=0.0, key=f"cdt_d1_{i}", label_visibility="collapsed")
            with cols[1]:
                d2_v = st.number_input("", value=float(fdef["d2"]),
                    step=1.0, min_value=0.0, key=f"cdt_d2_{i}", label_visibility="collapsed")
            with cols[2]:
                r_v  = st.number_input("", value=0.0, step=0.001,
                    min_value=0.0, key=f"cdt_r_{i}", label_visibility="collapsed",
                    format="%.3f")
            with cols[3]:
                d1s_v = st.number_input("", value=float(fdef["d1s"]),
                    step=1.0, min_value=0.0, key=f"cdt_d1s_{i}", label_visibility="collapsed")
            with cols[4]:
                d2s_v = st.number_input("", value=float(fdef["d2s"]),
                    step=1.0, min_value=0.0, key=f"cdt_d2s_{i}", label_visibility="collapsed")
            with cols[5]:
                rs_v  = st.number_input("", value=0.0, step=0.001,
                    min_value=0.0, key=f"cdt_rs_{i}", label_visibility="collapsed",
                    format="%.3f")
            with cols[6]:
                obs_v = st.text_input("", key=f"cdt_obs_{i}",
                    label_visibility="collapsed", placeholder="...")

            if r_v > 0:   r_vals.append(r_v)
            if rs_v > 0:  rs_vals.append(rs_v)
            filas_data.append({
                "d1": d1_v, "d2": d2_v, "r": r_v if r_v > 0 else None,
                "d1s": d1s_v, "d2s": d2s_v, "rs": rs_v if rs_v > 0 else None,
                "obs": obs_v
            })

        # ── Cálculo en tiempo real ─────────────────────────────────────────────
        vals_para_prom = r_vals if r_vals else []
        res_prom = promedio_con_validacion(vals_para_prom)

        if vals_para_prom:
            r_prom     = res_prom["promedio"]
            es_valido  = res_prom["valido"]
            max_err    = res_prom["max_error_pct"]
            cumple_r   = r_prom <= limite_cdt if r_prom else False

            col_v1, col_v2, col_v3, col_v4 = st.columns(4)
            color_prom = "#00E676" if cumple_r else "#FF5252"
            color_val  = "#00BCD4" if es_valido else "#FF8F00"

            col_v1.markdown(f"""
            <div class='metric-box'>
                <div class='metric-val' style='color:{color_prom};'>{r_prom:.3f}</div>
                <div class='metric-unit'>Ω</div>
                <div class='metric-label'>R PROMEDIO</div>
            </div>""", unsafe_allow_html=True)
            col_v2.markdown(f"""
            <div class='metric-box' style='border-color:{color_val}44;'>
                <div class='metric-val' style='color:{color_val};'>{max_err:.1f}%</div>
                <div class='metric-unit'>error máx.</div>
                <div class='metric-label'>DISPERSIÓN</div>
            </div>""", unsafe_allow_html=True)
            col_v3.markdown(f"""
            <div class='metric-box' style='border-color:{"rgba(0,230,118,.4)" if es_valido else "rgba(255,143,0,.4)"};'>
                <div class='metric-val' style='color:{color_val};font-size:1rem;'>
                    {"✓ VÁLIDO" if es_valido else "⚠ REPETIR"}</div>
                <div class='metric-label'>PROMEDIO ±5%</div>
            </div>""", unsafe_allow_html=True)
            col_v4.markdown(f"""
            <div class='metric-box' style='border-color:{"rgba(0,230,118,.5)" if cumple_r else "rgba(255,82,82,.5)"};'>
                <div class='metric-val' style='color:{color_prom};font-size:1rem;'>
                    {"✓ CUMPLE" if cumple_r else "✗ NO CUMPLE"}</div>
                <div class='metric-unit'>Límite ≤ {limite_cdt:.0f} Ω</div>
                <div class='metric-label'>RETIE</div>
            </div>""", unsafe_allow_html=True)

            if not es_valido:
                st.warning(
                    f"⚠ La dispersión es {max_err:.1f}% (> 5%). "
                    "Según norma LA-400, se deben aumentar D₁ y D₂ manteniendo D₂ = 0.62 × D₁ "
                    "y repetir la medición hasta obtener error < 5%.")
        else:
            st.info("Ingresa los valores de R medidos para ver el resultado.")
            r_prom = None; es_valido = False; cumple_r = False; max_err = None

        # ── Guardar medición ───────────────────────────────────────────────────
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        if st.button("💾 Guardar Medición Caída de Tensión", use_container_width=True,
                     key="cdt_guardar", type="primary",
                     disabled=(r_prom is None)):
            conn = get_conn()
            conn.execute("""
                INSERT INTO tierra_mediciones(
                    proyecto_id, metodo, lugar, punto_sig, direccion,
                    fecha_med, estado_terreno, equipo,
                    mediciones_json, r_promedio, r_valido, cumple_retie,
                    limite_retie, tipo_instalacion, observaciones)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                proyecto_id,
                "CAIDA_TENSION",
                session_state.get("cdt_lugar",""),
                session_state.get("cdt_pto_sig",""),
                session_state.get("cdt_dir",""),
                session_state.get("cdt_fecha", date.today()).strftime("%Y-%m-%d")
                    if hasattr(session_state.get("cdt_fecha", date.today()), "strftime")
                    else str(session_state.get("cdt_fecha", date.today())),
                session_state.get("cdt_estado","Seco"),
                session_state.get("cdt_equipo",""),
                json.dumps(filas_data, ensure_ascii=False),
                r_prom,
                int(es_valido),
                int(cumple_r),
                limite_cdt,
                session_state.get("cdt_tipo_ins","Sistema fotovoltaico (RETIE)"),
                session_state.get("cdt_obs_gral",""),
            ))
            conn.commit(); conn.close()
            st.success(f"Medición guardada — R promedio: {r_prom:.3f} Ω "
                       f"{'✓ CUMPLE RETIE' if cumple_r else '✗ NO CUMPLE RETIE'}")
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — MÉTODO WENNER / 4 PUNTOS (LA-400 Fig. 2)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_wen:
        st.markdown("""
        <div class='sol-card-title'><span class='step-badge'>3</span>
        RESISTIVIDAD DEL TERRENO — MÉTODO WENNER / 4 PUNTOS (LA-400 Figura 2)</div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class='formula-box'>
            <b>Fórmula:</b> ρ = 2π × D × R  (Ω·m)<br>
            <b>Distancias sugeridas:</b> D = 1, 2, 5, 10, 20, 30 m<br>
            <b>Condición:</b> profundidad varillas ≤ 10% de D · Electrodos alineados a igual distancia D
        </div>""", unsafe_allow_html=True)

        wen_c1, wen_c2, wen_c3 = st.columns(3)
        with wen_c1:
            wen_lugar  = st.text_input("Lugar de medición", key="wen_lugar",
                placeholder="Ej: Área de instalación paneles")
            wen_pto    = st.text_input("Punto significativo", key="wen_pto",
                placeholder="Ej: WEN-01")
        with wen_c2:
            wen_fecha  = st.date_input("Fecha medición", key="wen_fecha", value=date.today())
            wen_estado = st.selectbox("Estado terreno", ["Seco", "Húmedo"], key="wen_estado")
        with wen_c3:
            wen_equipo = st.text_input("Equipo (telurómetro)", key="wen_equipo",
                placeholder="Ej: Fluke 1625 / AEMC 6472")
            wen_dir    = st.text_input("Dirección", key="wen_dir",
                placeholder="Ubicación GPS o descripción")

        st.markdown("<hr class='sep' style='margin:0.8rem 0;'>", unsafe_allow_html=True)
        st.markdown("**Ingreso de mediciones (D, R → ρ se calcula automáticamente)**")

        # Encabezado
        _whcols = st.columns([1.5, 1.8, 2.5, 3.2, 1.5])
        for _wh, _wt in zip(_whcols, ["D (m)", "R (Ω)", "ρ = 2πDR (Ω·m)", "Observaciones", ""]):
            _wh.markdown(
                f"<div style='font-size:0.72rem;color:#1565C0;font-weight:700;"
                f"text-align:center;'>{_wt}</div>", unsafe_allow_html=True)

        D_SUGERIDAS = [1, 2, 5, 10, 20, 30]
        wen_filas   = []
        rho_vals    = []

        for i, d_sug in enumerate(D_SUGERIDAS):
            wc = st.columns([1.5, 1.8, 2.5, 3.2, 1.5])
            with wc[0]:
                wd_v = st.number_input("", value=float(d_sug), step=0.5, min_value=0.1,
                    key=f"wen_d_{i}", label_visibility="collapsed")
            with wc[1]:
                wr_v = st.number_input("", value=0.0, step=0.001, min_value=0.0,
                    key=f"wen_r_{i}", label_visibility="collapsed", format="%.3f")
            with wc[2]:
                rho_v = round(2 * math.pi * wd_v * wr_v, 2) if wr_v > 0 else None
                st.markdown(f"""
                <div style='background:#1E2A3F;border-radius:6px;padding:0.42rem 0.5rem;
                            font-family:Share Tech Mono;font-size:0.82rem;
                            color:{"#FFD54F" if rho_v else "#2A3A55"};text-align:center;
                            margin-top:0.1rem;'>
                    {f"{rho_v:.1f} Ω·m" if rho_v else "—"}
                </div>""", unsafe_allow_html=True)
            with wc[3]:
                wobs_v = st.text_input("", key=f"wen_obs_{i}",
                    label_visibility="collapsed", placeholder="...")
            with wc[4]:
                if rho_v:
                    terreno_detectado = next(
                        (k for k, v in RESISTIVIDADES_TERRENO.items()
                         if k != "Personalizado" and v and abs(v - rho_v) / max(v, 1) < 0.5),
                        "—")
                    st.markdown(
                        f"<div style='font-size:0.65rem;color:#8A9BBD;margin-top:0.4rem;'>"
                        f"{terreno_detectado}</div>", unsafe_allow_html=True)

            if rho_v:
                rho_vals.append(rho_v)
            wen_filas.append({
                "d": wd_v, "r": wr_v if wr_v > 0 else None,
                "rho": rho_v, "obs": wobs_v
            })

        # Resumen resistividades
        if rho_vals:
            rho_prom = sum(rho_vals) / len(rho_vals)
            rho_min  = min(rho_vals)
            rho_max  = max(rho_vals)
            n_var_wen = varillas_necesarias(rho_prom, 25.0)

            st.markdown("<hr class='sep' style='margin:0.8rem 0;'>", unsafe_allow_html=True)
            w_col1, w_col2, w_col3, w_col4 = st.columns(4)
            for _wmc, _wlbl, _wval, _wcol in [
                (w_col1, "ρ PROMEDIO",  f"{rho_prom:.1f} Ω·m", "#FFB300"),
                (w_col2, "ρ MÍNIMA",   f"{rho_min:.1f} Ω·m",  "#00E676"),
                (w_col3, "ρ MÁXIMA",   f"{rho_max:.1f} Ω·m",  "#FF5252"),
                (w_col4, "VARILLAS RECOMENDADAS", f"{n_var_wen} und", "#00BCD4"),
            ]:
                _wmc.markdown(f"""
                <div class='metric-box' style='border-color:{_wcol}44;'>
                    <div class='metric-val' style='color:{_wcol};font-size:1.1rem;'>{_wval}</div>
                    <div class='metric-label'>{_wlbl}</div>
                </div>""", unsafe_allow_html=True)

            # Interpretación según LA-400
            if rho_prom < 63:
                interp = "ρ < 63 Ω·m → 1 varilla estándar es suficiente"
                interp_col = "#00E676"
            elif rho_prom < 110:
                interp = "ρ < 110 Ω·m → Se recomiendan 2 varillas interconectadas"
                interp_col = "#FFB300"
            elif rho_prom < 150:
                interp = "ρ < 150 Ω·m → Se recomiendan 3 varillas interconectadas"
                interp_col = "#FF8F00"
            else:
                interp = "ρ ≥ 150 Ω·m → Más de 3 varillas + tratamiento del suelo (bentonita/gel)"
                interp_col = "#FF5252"
            st.markdown(f"""
            <div style='background:{interp_col}18;border-left:3px solid {interp_col};
                        border-radius:6px;padding:0.6rem 0.8rem;font-size:0.85rem;
                        color:{interp_col};font-weight:600;margin:0.6rem 0;'>
                📊 {interp}
            </div>""", unsafe_allow_html=True)
        else:
            rho_prom = None

        wen_obs = st.text_area("Observaciones Wenner", key="wen_obs_gral",
                                placeholder="Condiciones del terreno, incidencias...", height=60)

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        if st.button("💾 Guardar Medición Wenner", use_container_width=True,
                     key="wen_guardar", type="primary",
                     disabled=(rho_prom is None)):
            conn = get_conn()
            conn.execute("""
                INSERT INTO tierra_wenner(
                    proyecto_id, lugar, fecha_med, estado_terreno,
                    equipo, mediciones_json, observaciones)
                VALUES(?,?,?,?,?,?,?)
            """, (
                proyecto_id,
                session_state.get("wen_lugar",""),
                session_state.get("wen_fecha", date.today()).strftime("%Y-%m-%d")
                    if hasattr(session_state.get("wen_fecha", date.today()), "strftime")
                    else str(session_state.get("wen_fecha", date.today())),
                session_state.get("wen_estado","Seco"),
                session_state.get("wen_equipo",""),
                json.dumps(wen_filas, ensure_ascii=False),
                wen_obs,
            ))
            conn.commit(); conn.close()
            st.success(f"Resistividad guardada — ρ promedio: {rho_prom:.1f} Ω·m")
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_hist:
        st.markdown("""
        <div class='sol-card-title'>📋 HISTORIAL DE MEDICIONES</div>""",
            unsafe_allow_html=True)

        if meds_df.empty and wen_df.empty:
            st.markdown("""
            <div class='info-note' style='text-align:center;padding:2rem;'>
                No hay mediciones guardadas para este proyecto.
                Registra la primera en las pestañas anteriores.
            </div>""", unsafe_allow_html=True)
        else:
            if not meds_df.empty:
                st.markdown("#### Caída de Tensión")
                for _, row in meds_df.iterrows():
                    c_col = "#00E676" if row["cumple_retie"] else "#FF5252"
                    v_col = "#00BCD4" if row["r_valido"]    else "#FF8F00"
                    st.markdown(f"""
                    <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
                                padding:0.8rem 1.2rem;margin-bottom:0.5rem;'>
                        <div style='display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;'>
                            <span style='color:#FFB300;font-family:Rajdhani,sans-serif;
                                         font-weight:700;'>#{row["id"]} {row["lugar"] or "—"}</span>
                            <span style='color:#8A9BBD;font-size:0.8rem;'>Punto: {row["punto_sig"] or "—"}</span>
                            <span style='color:#8A9BBD;font-size:0.8rem;'>Fecha: {row["fecha_med"] or "—"}</span>
                            <span style='color:#8A9BBD;font-size:0.8rem;'>Terreno: {row["estado_terreno"]}</span>
                            <span style='font-family:Share Tech Mono;color:{c_col};font-weight:700;'>
                                R = {row["r_promedio"]:.3f} Ω</span>
                            <span style='background:{c_col}22;border:1px solid {c_col};
                                         border-radius:20px;padding:2px 8px;font-size:0.72rem;
                                         color:{c_col};font-weight:700;'>
                                {"✓ CUMPLE" if row["cumple_retie"] else "✗ NO CUMPLE"} RETIE ≤{row["limite_retie"]:.0f}Ω</span>
                            <span style='background:{v_col}22;border:1px solid {v_col};
                                         border-radius:20px;padding:2px 8px;font-size:0.72rem;
                                         color:{v_col};font-weight:700;'>
                                {"✓ Promedio válido" if row["r_valido"] else "⚠ Repetir medición"}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)

                # Resumen
                total_m = len(meds_df)
                cumplen = meds_df["cumple_retie"].sum()
                st.markdown(f"""
                <div style='background:#1E2A3F;border-radius:8px;padding:0.6rem 1rem;
                            margin-top:0.3rem;font-size:0.82rem;color:#8A9BBD;'>
                    Total mediciones: <b style='color:#FFB300;'>{total_m}</b> |
                    Cumplen RETIE: <b style='color:#00E676;'>{cumplen}</b> |
                    No cumplen: <b style='color:#FF5252;'>{total_m - cumplen}</b>
                </div>""", unsafe_allow_html=True)

            if not wen_df.empty:
                st.markdown("#### Wenner / 4 Puntos")
                for _, row in wen_df.iterrows():
                    filas_w = json.loads(row["mediciones_json"]) if row["mediciones_json"] else []
                    rho_vs  = [f["rho"] for f in filas_w if f.get("rho")]
                    rho_pm  = round(sum(rho_vs)/len(rho_vs), 1) if rho_vs else None
                    st.markdown(f"""
                    <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
                                padding:0.8rem 1.2rem;margin-bottom:0.5rem;'>
                        <div style='display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;'>
                            <span style='color:#00BCD4;font-family:Rajdhani,sans-serif;
                                         font-weight:700;'>#{row["id"]} {row["lugar"] or "—"}</span>
                            <span style='color:#8A9BBD;font-size:0.8rem;'>Fecha: {row["fecha_med"] or "—"}</span>
                            <span style='color:#8A9BBD;font-size:0.8rem;'>Terreno: {row["estado_terreno"]}</span>
                            <span style='font-family:Share Tech Mono;color:#FFD54F;font-weight:700;'>
                                ρ = {f"{rho_pm:.1f} Ω·m" if rho_pm else "—"}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)

            # Eliminar medición
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            with st.expander("🗑 Eliminar medición"):
                opts_cdt = {f"CDT #{r['id']} — {r['lugar']} — {r['r_promedio']:.3f}Ω":
                            int(r["id"]) for _, r in meds_df.iterrows()} if not meds_df.empty else {}
                opts_wen = {f"WEN #{r['id']} — {r['lugar']}":
                            int(r["id"]) for _, r in wen_df.iterrows()} if not wen_df.empty else {}
                all_opts = {**opts_cdt, **opts_wen}
                if all_opts:
                    sel_del = st.selectbox("Medición a eliminar", list(all_opts.keys()),
                                            key="t_del_sel")
                    tipo_del = "CDT" if sel_del.startswith("CDT") else "WEN"
                    if st.button("🗑 Confirmar eliminación", key="t_btn_del",
                                 use_container_width=True):
                        conn = get_conn()
                        tbl = "tierra_mediciones" if tipo_del == "CDT" else "tierra_wenner"
                        conn.execute(f"DELETE FROM {tbl} WHERE id=? AND proyecto_id=?",
                                     (all_opts[sel_del], proyecto_id))
                        conn.commit(); conn.close()
                        st.success("Medición eliminada ✓"); st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — INFORME PDF
    # ══════════════════════════════════════════════════════════════════════════
    with tab_pdf:
        st.markdown("""
        <div class='sol-card-title'>📄 GENERAR INFORME PDF — NORMA LA-400 / RETIE</div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class='info-note'>
            El informe incluye: diseño del sistema, todas las mediciones CDT con validación
            RETIE, mediciones Wenner con ρ calculada, tabla normativa RETIE y área de firmas.
            Formato basado en norma LA-400 (ENEL-Codensa, revisión 03-04-2017).
        </div>""", unsafe_allow_html=True)

        pdf_c1, pdf_c2 = st.columns(2)
        with pdf_c1:
            pdf_elaboro = st.text_input("Elaboró", key="pdf_elaboro",
                placeholder="Nombre del técnico responsable")
            pdf_reviso  = st.text_input("Revisó / Aprobó", key="pdf_reviso",
                placeholder="Nombre del ingeniero supervisor")
        with pdf_c2:
            pdf_fecha   = st.date_input("Fecha del informe", key="pdf_fecha", value=date.today())

        if st.button("⬇ Generar y Descargar Informe PDF", use_container_width=True,
                     key="t_dl_pdf", type="primary"):
            try:
                # Armar datos para PDF
                meds_list = []
                for _, row in meds_df.iterrows():
                    filas_m = json.loads(row["mediciones_json"]) if row["mediciones_json"] else []
                    meds_list.append({
                        "lugar":           row["lugar"] or "",
                        "punto_sig":       row["punto_sig"] or "",
                        "direccion":       row["direccion"] or "",
                        "fecha_med":       row["fecha_med"] or "",
                        "estado_terreno":  row["estado_terreno"] or "Seco",
                        "equipo":          row["equipo"] or "",
                        "filas":           filas_m,
                        "r_promedio":      row["r_promedio"],
                        "r_valido":        bool(row["r_valido"]),
                        "cumple_retie":    bool(row["cumple_retie"]),
                        "limite_retie":    row["limite_retie"],
                        "tipo_instalacion":row["tipo_instalacion"] or "",
                        "observaciones":   row["observaciones"] or "",
                    })

                wen_list = []
                for _, row in wen_df.iterrows():
                    filas_w = json.loads(row["mediciones_json"]) if row["mediciones_json"] else []
                    wen_list.append({
                        "lugar":           row["lugar"] or "",
                        "fecha_med":       row["fecha_med"] or "",
                        "estado_terreno":  row["estado_terreno"] or "Seco",
                        "equipo":          row["equipo"] or "",
                        "filas":           filas_w,
                        "observaciones":   row["observaciones"] or "",
                    })

                datos_pdf = {
                    "proyecto": {
                        "nombre":   p_inf[1] if p_inf else "",
                        "municipio":p_inf[2] if p_inf and p_inf[2] else "",
                        "elaboro":  session_state.get("pdf_elaboro",""),
                        "reviso":   session_state.get("pdf_reviso",""),
                    },
                    "diseno": {
                        "tipo_sistema":   dis_r[2]  if dis_r else "TT",
                        "electrodo_dim":  dis_r[4]  if dis_r else '5/8" × 2.44 m',
                        "n_varillas":     dis_r[5]  if dis_r else 1,
                        "separacion_m":   dis_r[6]  if dis_r else 5.0,
                        "conductor_cal":  dis_r[7]  if dis_r else "4 AWG",
                        "conductor_mat":  dis_r[8]  if dis_r else "Cobre cobrizado",
                        "resistividad":   dis_r[9]  if dis_r else 50.0,
                        "r_objetivo":     dis_r[10] if dis_r else 25.0,
                        "tratamiento":    dis_r[11] if dis_r else "Ninguno",
                        "r_calculada": calcular_r_n_varillas(
                            dis_r[9]  if dis_r else 50.0,
                            dis_r[5]  if dis_r else 1),
                    },
                    "mediciones": meds_list,
                    "wenner":     wen_list,
                    "fecha": session_state.get("pdf_fecha", date.today()).strftime("%d/%m/%Y")
                             if hasattr(session_state.get("pdf_fecha", date.today()), "strftime")
                             else str(session_state.get("pdf_fecha", date.today())),
                }

                pdf_bytes = generar_pdf_tierra(datos_pdf)
                fname = (f"Informe_Tierra_{p_inf[1].replace(' ','_')}_"
                         f"{date.today().strftime('%Y%m%d')}.pdf")
                st.download_button(
                    "📥 Descargar PDF ahora",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    use_container_width=True,
                    key="t_dl_pdf_btn2"
                )
                st.success("PDF generado exitosamente ✓")
            except Exception as ex:
                st.error(f"Error generando PDF: {ex}")
