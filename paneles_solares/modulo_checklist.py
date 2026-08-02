# ═══════════════════════════════════════════════════════════════════════════════
# modulo_checklist.py — Checklist de Puesta en Marcha FV
# Normas: RETIE · NTC 2050 · IEC 62446-1
# ═══════════════════════════════════════════════════════════════════════════════
import io
import math
import json
import streamlit as st
from datetime import date, datetime
from db_utils import get_conn

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable, PageBreak)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Esquema BD ────────────────────────────────────────────────────────────────
def init_checklist_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_pem (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER UNIQUE,
            -- Datos generales
            tecnico TEXT, supervisor TEXT, fecha_inst TEXT,
            tipo_sistema TEXT, pot_inst_kwp REAL, inv_modelo TEXT, n_paneles INTEGER,
            -- Secciones 1-15 en JSON
            s1_mecanica TEXT, s2_cable_dc TEXT, s3_prot_dc TEXT,
            s4_inversor TEXT, s5_baterias TEXT, s6_cable_ac TEXT,
            s7_prot_ac TEXT, s8_tierra TEXT, s9_mediciones TEXT,
            s10_config TEXT, s11_pruebas TEXT, s12_monitoreo TEXT,
            s13_seguridad TEXT, s14_documentacion TEXT, s15_resultado TEXT,
            observaciones TEXT,
            actualizado TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    conn.commit(); conn.close()

def _load(proyecto_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM checklist_pem WHERE proyecto_id=?", (proyecto_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    cols = ["id","proyecto_id","tecnico","supervisor","fecha_inst","tipo_sistema",
            "pot_inst_kwp","inv_modelo","n_paneles",
            "s1_mecanica","s2_cable_dc","s3_prot_dc","s4_inversor","s5_baterias",
            "s6_cable_ac","s7_prot_ac","s8_tierra","s9_mediciones",
            "s10_config","s11_pruebas","s12_monitoreo","s13_seguridad",
            "s14_documentacion","s15_resultado","observaciones","actualizado"]
    d = dict(zip(cols, row))
    for k in [c for c in cols if c.startswith("s") and "_" in c]:
        if d.get(k):
            try: d[k] = json.loads(d[k])
            except: d[k] = {}
    return d

def _save(proyecto_id, data):
    conn = get_conn()
    json_fields = {k: json.dumps(v) if isinstance(v, dict) else v
                   for k, v in data.items()}
    conn.execute("""
        INSERT INTO checklist_pem
            (proyecto_id,tecnico,supervisor,fecha_inst,tipo_sistema,
             pot_inst_kwp,inv_modelo,n_paneles,
             s1_mecanica,s2_cable_dc,s3_prot_dc,s4_inversor,s5_baterias,
             s6_cable_ac,s7_prot_ac,s8_tierra,s9_mediciones,
             s10_config,s11_pruebas,s12_monitoreo,s13_seguridad,
             s14_documentacion,s15_resultado,observaciones,actualizado)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(proyecto_id) DO UPDATE SET
            tecnico=excluded.tecnico, supervisor=excluded.supervisor,
            fecha_inst=excluded.fecha_inst, tipo_sistema=excluded.tipo_sistema,
            pot_inst_kwp=excluded.pot_inst_kwp, inv_modelo=excluded.inv_modelo,
            n_paneles=excluded.n_paneles,
            s1_mecanica=excluded.s1_mecanica, s2_cable_dc=excluded.s2_cable_dc,
            s3_prot_dc=excluded.s3_prot_dc, s4_inversor=excluded.s4_inversor,
            s5_baterias=excluded.s5_baterias, s6_cable_ac=excluded.s6_cable_ac,
            s7_prot_ac=excluded.s7_prot_ac, s8_tierra=excluded.s8_tierra,
            s9_mediciones=excluded.s9_mediciones, s10_config=excluded.s10_config,
            s11_pruebas=excluded.s11_pruebas, s12_monitoreo=excluded.s12_monitoreo,
            s13_seguridad=excluded.s13_seguridad,
            s14_documentacion=excluded.s14_documentacion,
            s15_resultado=excluded.s15_resultado,
            observaciones=excluded.observaciones,
            actualizado=datetime('now')
    """, (proyecto_id,
          json_fields.get("tecnico",""), json_fields.get("supervisor",""),
          json_fields.get("fecha_inst",""), json_fields.get("tipo_sistema",""),
          json_fields.get("pot_inst_kwp",0), json_fields.get("inv_modelo",""),
          json_fields.get("n_paneles",0),
          json_fields.get("s1_mecanica","{}"), json_fields.get("s2_cable_dc","{}"),
          json_fields.get("s3_prot_dc","{}"), json_fields.get("s4_inversor","{}"),
          json_fields.get("s5_baterias","{}"), json_fields.get("s6_cable_ac","{}"),
          json_fields.get("s7_prot_ac","{}"), json_fields.get("s8_tierra","{}"),
          json_fields.get("s9_mediciones","{}"), json_fields.get("s10_config","{}"),
          json_fields.get("s11_pruebas","{}"), json_fields.get("s12_monitoreo","{}"),
          json_fields.get("s13_seguridad","{}"), json_fields.get("s14_documentacion","{}"),
          json_fields.get("s15_resultado","{}"), json_fields.get("observaciones","")))
    conn.commit(); conn.close()

# ── Helper UI ─────────────────────────────────────────────────────────────────
def _chk_items(items, saved, prefix):
    """Renderiza filas de checklist OK/NO/Obs y retorna dict."""
    result = {}
    for item in items:
        key = item.replace(" ", "_").replace("/", "_").lower()[:40]
        prev = saved.get(key, {}) if isinstance(saved, dict) else {}
        cols = st.columns([3, 0.6, 0.6, 2.5])
        cols[0].markdown(f"<div style='font-size:0.83rem;color:#E0E6F0;padding-top:0.45rem;'>{item}</div>",
                          unsafe_allow_html=True)
        ok  = cols[1].checkbox("✅", value=bool(prev.get("ok", False)),
                                key=f"{prefix}_{key}_ok",   label_visibility="collapsed")
        no  = cols[2].checkbox("❌", value=bool(prev.get("no", False)),
                                key=f"{prefix}_{key}_no",   label_visibility="collapsed")
        obs = cols[3].text_input("", value=str(prev.get("obs", "")),
                                  key=f"{prefix}_{key}_obs", label_visibility="collapsed",
                                  placeholder="Observación...")
        result[key] = {"ok": ok, "no": no, "obs": obs}
    return result

def _sec_header(icon, num, title):
    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#1A2440,#0F1525);
                border-left:3px solid #FFB300;border-radius:0 8px 8px 0;
                padding:0.5rem 1rem;margin:0.8rem 0 0.4rem 0;
                font-family:Rajdhani,sans-serif;font-weight:600;font-size:1rem;color:#FFB300;'>
        {icon} {num}. {title}
    </div>""", unsafe_allow_html=True)
    st.markdown(
        "<div style='display:grid;grid-template-columns:3fr 0.6fr 0.6fr 2.5fr;"
        "gap:4px;font-size:0.75rem;color:#8A9BBD;padding:0 0 0.2rem 0;'>"
        "<span>Ítem</span><span style='text-align:center;'>OK</span>"
        "<span style='text-align:center;'>NO</span><span>Observaciones</span></div>",
        unsafe_allow_html=True)

def _chk_bool(label, saved, key, prefix):
    prev = saved.get(key, False) if isinstance(saved, dict) else False
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"<div style='font-size:0.83rem;color:#E0E6F0;padding-top:0.45rem;'>{label}</div>",
                unsafe_allow_html=True)
    val = c2.checkbox("✓", value=bool(prev), key=f"{prefix}_{key}", label_visibility="collapsed")
    return val

# ── PDF Generation ────────────────────────────────────────────────────────────
def generar_pdf_checklist(datos: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm)

    BLUE  = colors.HexColor("#1565C0")
    SOL   = colors.HexColor("#FFB300")
    GREEN = colors.HexColor("#2E7D32")
    RED   = colors.HexColor("#C62828")
    LGRAY = colors.HexColor("#F5F5F5")
    MGRAY = colors.HexColor("#E0E0E0")
    TEXT  = colors.HexColor("#212121")
    TEXT2 = colors.HexColor("#616161")
    WHITE = colors.white
    LGRN  = colors.HexColor("#E8F5E9")
    LRED  = colors.HexColor("#FFEBEE")
    YELL  = colors.HexColor("#FFF8E1")

    def sty(name, font="Helvetica", sz=9, color=TEXT, align=TA_LEFT, bold=False, sb=0, sa=3):
        return ParagraphStyle(name, fontName=font+("-Bold" if bold else ""),
                               fontSize=sz, textColor=color, alignment=align,
                               spaceBefore=sb, spaceAfter=sa, leading=sz*1.4)

    st_tit  = sty("tit",  sz=16, color=BLUE, bold=True, align=TA_CENTER)
    st_sub  = sty("sub",  sz=8,  color=TEXT2, align=TA_CENTER)
    st_sec  = sty("sec",  sz=10, color=BLUE, bold=True, sb=8, sa=3)
    st_body = sty("body", sz=8.5,color=TEXT)
    st_lbl  = sty("lbl",  sz=7.5,color=TEXT2)
    st_foot = sty("foot", sz=7,  color=TEXT2, align=TA_CENTER)
    st_ctr  = sty("ctr",  sz=8.5,color=TEXT, align=TA_CENTER)
    st_ok   = sty("ok",   sz=9,  color=GREEN, bold=True, align=TA_CENTER)
    st_no   = sty("no",   sz=9,  color=RED,   bold=True, align=TA_CENTER)

    def hr(c=MGRAY, t=0.6, sa=4): return HRFlowable(width="100%", thickness=t, color=c, spaceAfter=sa)
    def p(txt, s=None):  return Paragraph(str(txt or ""), s or st_body)
    def sp(h=0.3):       return Spacer(1, h*cm)
    def pb():            return PageBreak()
    def sec(n, title):   return p(f"{n}. {title}", st_sec)

    proy   = datos.get("proyecto", {})
    ck     = datos.get("checklist", {})
    meds   = datos.get("mediciones", {})

    story = []

    # ── PORTADA ───────────────────────────────────────────────────────────────
    story += [sp(1.5),
              p("CHECKLIST DE PUESTA EN MARCHA", st_tit),
              p("SISTEMA FOTOVOLTAICO", st_tit),
              sp(0.3), hr(BLUE, 2, 8)]

    port_data = [
        ["Proyecto:",       proy.get("nombre",""),     "Fecha:",      ck.get("fecha_inst","")],
        ["Cliente:",        proy.get("propietario",""),"Tecnico:",    ck.get("tecnico","")],
        ["Ubicacion:",      proy.get("municipio",""),  "Supervisor:", ck.get("supervisor","")],
        ["Tipo sistema:",   ck.get("tipo_sistema",""), "Inversor:",   ck.get("inv_modelo","")],
        ["Pot. instalada:", f"{ck.get('pot_inst_kwp',0):.2f} kWp",
         "N° paneles:",    str(ck.get("n_paneles",""))],
    ]
    t_port = Table(port_data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    t_port.setStyle(TableStyle([
        ("FONTNAME",     (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",     (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTNAME",     (1,0), (1,-1), "Helvetica"),
        ("FONTNAME",     (3,0), (3,-1), "Helvetica"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("TEXTCOLOR",    (0,0), (0,-1), TEXT2),
        ("TEXTCOLOR",    (2,0), (2,-1), TEXT2),
        *[("BACKGROUND", (0,i), (-1,i), LGRAY if i%2==0 else WHITE) for i in range(5)],
        ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    story += [t_port, sp(0.4),
              p("Normas: RETIE · NTC 2050 · IEC 62446-1", st_sub),
              p(f"SOLARCALC PRO — Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", st_foot),
              pb()]

    # ── Helper para secciones de checklist ───────────────────────────────────
    def _sec_table(sec_num, sec_title, items_dict, include_obs=True):
        story.append(sec(sec_num, sec_title))
        story.append(hr())
        if include_obs:
            hdr = [["ITEM / VERIFICACION", "OK", "NO", "OBSERVACIONES"]]
            col_w = [8.5*cm, 1.2*cm, 1.2*cm, 5.1*cm]
        else:
            hdr = [["ITEM / VERIFICACION", "OK", "NO"]]
            col_w = [12*cm, 1.5*cm, 1.5*cm]

        rows = list(hdr)
        for item, vals in (items_dict.items() if isinstance(items_dict, dict) else []):
            if isinstance(vals, dict):
                ok_v  = "✓" if vals.get("ok")  else ""
                no_v  = "✗" if vals.get("no")  else ""
                obs_v = vals.get("obs","")
                label = item.replace("_"," ").title()
                if include_obs:
                    rows.append([label, ok_v, no_v, obs_v])
                else:
                    rows.append([label, ok_v, no_v])

        if len(rows) <= 1:
            story.append(p("Sin datos registrados.", st_lbl))
            story.append(sp(0.2))
            return

        t = Table(rows, colWidths=col_w, repeatRows=1)
        ts = TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), BLUE),
            ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8),
            ("ALIGN",        (1,0), (2,-1), "CENTER"),
            ("ALIGN",        (0,0), (0,-1), "LEFT"),
            *[("BACKGROUND", (0,i), (-1,i),
               LGRN if rows[i][1]=="✓" and rows[i][2]==""
               else LRED if rows[i][2]=="✗"
               else (LGRAY if i%2==0 else WHITE))
              for i in range(1, len(rows))],
            ("TEXTCOLOR",    (1,1), (1,-1), GREEN),
            ("TEXTCOLOR",    (2,1), (2,-1), RED),
            ("FONTNAME",     (1,1), (2,-1), "Helvetica-Bold"),
            ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
            ("LEFTPADDING",  (0,0), (-1,-1), 5),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ])
        t.setStyle(ts)
        story.append(t)
        story.append(sp(0.3))

    s = ck  # shorthand
    _sec_table(1,  "INSPECCION MECANICA",        s.get("s1_mecanica",{}))
    _sec_table(2,  "CABLEADO DC",                s.get("s2_cable_dc",{}))
    _sec_table(3,  "PROTECCIONES DC",            s.get("s3_prot_dc",{}))
    _sec_table(4,  "INVERSOR",                   s.get("s4_inversor",{}))

    tipo_sis = s.get("tipo_sistema","OFF-GRID")
    if tipo_sis in ("OFF-GRID","Híbrido","HIBRIDO"):
        _sec_table(5, "BATERIAS (Off-Grid / Hibrido)", s.get("s5_baterias",{}))

    _sec_table(6,  "CABLEADO AC",               s.get("s6_cable_ac",{}))
    _sec_table(7,  "PROTECCIONES AC",            s.get("s7_prot_ac",{}))
    _sec_table(8,  "PUESTA A TIERRA",            s.get("s8_tierra",{}))
    story.append(pb())

    # Sección 9 — Mediciones
    story.append(sec(9, "MEDICIONES ELECTRICAS"))
    story.append(hr())
    med_dc = meds.get("dc", {})
    med_ac = meds.get("ac", {})
    med_rows_dc = [
        ["LADO DC", "PARAMETRO", "VALOR MEDIDO"],
        ["", "Voltaje String 1", med_dc.get("v_str1","____") + " V"],
        ["", "Voltaje String 2", med_dc.get("v_str2","____") + " V"],
        ["", "Corriente String 1", med_dc.get("i_str1","____") + " A"],
        ["", "Corriente String 2", med_dc.get("i_str2","____") + " A"],
        ["", "Voc Total", med_dc.get("voc_total","____") + " V"],
        ["", "Isc Total", med_dc.get("isc_total","____") + " A"],
    ]
    med_rows_ac = [
        ["LADO AC", "PARAMETRO", "VALOR MEDIDO"],
        ["", "Voltaje L-N",          med_ac.get("v_ln","____") + " V"],
        ["", "Voltaje L-L",          med_ac.get("v_ll","____") + " V"],
        ["", "Frecuencia",           med_ac.get("freq","____") + " Hz"],
        ["", "Corriente salida",     med_ac.get("i_sal","____") + " A"],
        ["", "Potencia Instantanea", med_ac.get("pot_inst","____") + " kW"],
    ]
    for m_rows in [med_rows_dc, med_rows_ac]:
        t_m = Table(m_rows, colWidths=[3*cm, 5*cm, 8*cm])
        t_m.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), BLUE),
            ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME",     (1,1), (1,-1), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8),
            ("TEXTCOLOR",    (1,1), (1,-1), TEXT2),
            ("TEXTCOLOR",    (2,1), (2,-1), TEXT),
            *[("BACKGROUND", (0,i), (-1,i), LGRAY if i%2==0 else WHITE) for i in range(1,7)],
            ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ]))
        story += [t_m, sp(0.3)]

    # Secciones 10-14 — Config, pruebas, monitoreo, seguridad, documentación
    _sec_table(10, "CONFIGURACION DEL INVERSOR",  s.get("s10_config",{}), include_obs=False)
    _sec_table(11, "PRUEBAS FUNCIONALES",         s.get("s11_pruebas",{}))
    _sec_table(12, "MONITOREO",                   s.get("s12_monitoreo",{}), include_obs=False)
    _sec_table(13, "SEGURIDAD",                   s.get("s13_seguridad",{}), include_obs=False)
    _sec_table(14, "DOCUMENTACION ENTREGADA",     s.get("s14_documentacion",{}), include_obs=False)

    # Sección 15 — Resultado final
    story.append(sec(15, "RESULTADO FINAL"))
    story.append(hr())
    res15 = s.get("s15_resultado", {})
    res_rows = [["VERIFICACION", "SI", "NO"]]
    items15 = [("Sistema energizado","energizado"),("Produccion correcta","produccion"),
               ("Alarmas presentes","alarmas"),("Cliente capacitado","capacitado"),
               ("Sistema entregado","entregado")]
    for lbl, k in items15:
        val = res15.get(k, {})
        res_rows.append([lbl,
                         "✓" if val.get("si") else "",
                         "✓" if val.get("no") else ""])
    t_res = Table(res_rows, colWidths=[10*cm, 2.5*cm, 2.5*cm])
    t_res.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), BLUE),
        ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ALIGN",        (1,0), (2,-1), "CENTER"),
        *[("BACKGROUND", (0,i), (-1,i), LGRAY if i%2==0 else WHITE) for i in range(1,6)],
        ("TEXTCOLOR",    (1,1), (1,-1), GREEN),
        ("TEXTCOLOR",    (2,1), (2,-1), RED),
        ("FONTNAME",     (1,1), (2,-1), "Helvetica-Bold"),
        ("GRID",         (0,0), (-1,-1), 0.4, MGRAY),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ]))
    story += [t_res, sp(0.4)]

    # Observaciones
    obs = s.get("observaciones","")
    if obs:
        story.append(p("OBSERVACIONES GENERALES:", sty("obs_hdr", sz=9, color=BLUE, bold=True, sb=6)))
        story.append(p(obs))
        story.append(sp(0.3))

    # Firmas
    story.append(hr(MGRAY, 0.5))
    t_firmas = Table([[
        Table([[p("_"*28, st_ctr)],[p(s.get("tecnico","Tecnico Instalador"), st_ctr)],
               [p("Firma y fecha", st_lbl)]], colWidths=[5.3*cm]),
        Table([[p("_"*28, st_ctr)],[p(s.get("supervisor","Supervisor"), st_ctr)],
               [p("Firma y fecha", st_lbl)]], colWidths=[5.3*cm]),
        Table([[p("_"*28, st_ctr)],[p(proy.get("propietario","Cliente"), st_ctr)],
               [p("Firma y fecha", st_lbl)]], colWidths=[5.3*cm]),
    ]], colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
    t_firmas.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                   ("LEFTPADDING",(0,0),(-1,-1),0)]))
    story.append(t_firmas)
    story.append(sp(0.3))
    story.append(hr(SOL, 1))
    story.append(p(f"SOLARCALC PRO | Checklist Puesta en Marcha FV | "
                   f"RETIE · NTC 2050 · IEC 62446-1 | "
                   f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", st_foot))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def mostrar_checklist(proyecto_id: int, session_state: dict) -> None:
    init_checklist_db()

    conn = get_conn()
    p_inf = conn.execute("SELECT id,nombre,municipio FROM proyectos WHERE id=?",
                          (proyecto_id,)).fetchone()
    res   = conn.execute(
        "SELECT num_paneles,pot_real_wp,inv_kw FROM resultados "
        "WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
        (proyecto_id,)).fetchone()
    conn.close()

    saved = _load(proyecto_id)

    st.markdown("""
    <div class='sol-card-title'>✅ CHECKLIST DE PUESTA EN MARCHA — FV</div>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class='info-note'>
        <b>Proyecto:</b> {p_inf[1] if p_inf else "—"} &nbsp;|&nbsp;
        <b>Normas:</b> RETIE · NTC 2050 · IEC 62446-1 &nbsp;|&nbsp;
        {"Último guardado: <b>"+saved.get('actualizado','Sin guardar')+"</b>"
         if saved.get('actualizado') else "Sin datos guardados aún"}
    </div>""", unsafe_allow_html=True)

    # ── TABS ─────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📋 General", "🔧 1-Mecánica", "🔌 2-Cable DC", "🛡 3-Prot DC",
        "⚡ 4-Inversor", "🔋 5-Baterías", "🔌 6-Cable AC", "🛡 7-Prot AC",
        "⏚ 8-Tierra", "📏 9-Mediciones", "⚙ 10-Config", "🧪 11-Pruebas",
        "📡 12-Monitor", "🔒 13-Seguridad", "📄 14-Docs", "🏁 15-Resultado",
        "📄 PDF"
    ])

    # ── TAB 0: Datos generales ────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("**Datos generales de la instalación**")
        cg1, cg2 = st.columns(2)
        with cg1:
            tecnico   = st.text_input("Técnico Responsable", saved.get("tecnico",""), key="chk_tec")
            supervisor= st.text_input("Supervisor", saved.get("supervisor",""), key="chk_sup")
            fecha_ins = st.date_input("Fecha de instalación", key="chk_fecha",
                                       value=date.today())
            tipo_sis  = st.selectbox("Tipo de Sistema",
                                      ["OFF-GRID","ON-GRID","Híbrido"],
                                      index=["OFF-GRID","ON-GRID","Híbrido"].index(
                                          saved.get("tipo_sistema","OFF-GRID"))
                                      if saved.get("tipo_sistema") else 0,
                                      key="chk_tipo")
        with cg2:
            pot_kwp   = st.number_input("Potencia instalada (kWp)", 0.0, 10000.0,
                                         float(saved.get("pot_inst_kwp",
                                               round((res[1] or 0)/1000, 2) if res else 0)),
                                         0.01, key="chk_pot")
            inv_mod   = st.text_input("Modelo inversor", saved.get("inv_modelo",""), key="chk_inv")
            n_pan     = st.number_input("Cantidad de paneles", 0, 10000,
                                         int(saved.get("n_paneles", res[0] if res else 0)),
                                         1, key="chk_npan")
        if st.button("💾 Guardar datos generales", use_container_width=True, key="chk_save_gen"):
            d = {**saved,
                 "tecnico": tecnico, "supervisor": supervisor,
                 "fecha_inst": str(fecha_ins), "tipo_sistema": tipo_sis,
                 "pot_inst_kwp": pot_kwp, "inv_modelo": inv_mod, "n_paneles": n_pan}
            _save(proyecto_id, d)
            st.success("✅ Datos generales guardados")
            st.rerun()

    # ── TABs 1-8: Secciones de verificación ──────────────────────────────────
    def _tab_section(tab_idx, sec_num, icon, title, field, items):
        with tabs[tab_idx]:
            _sec_header(icon, sec_num, title)
            result = _chk_items(items, saved.get(field, {}), f"chk_{field}")
            if st.button(f"💾 Guardar {sec_num}. {title}",
                          use_container_width=True, key=f"chk_save_{field}"):
                _save(proyecto_id, {**saved, field: result})
                st.success(f"✅ Sección {sec_num} guardada")
                st.rerun()

    _tab_section(1, 1, "🔧", "Inspección Mecánica", "s1_mecanica", [
        "Estructura completamente instalada",
        "Tornillería correctamente ajustada",
        "Paneles correctamente fijados",
        "Sin daños físicos en paneles",
        "Orientación correcta",
        "Inclinación correcta",
        "Separación adecuada entre paneles",
        "Sin sombras importantes",
        "Canalizaciones instaladas",
        "Etiquetado de strings",
    ])
    _tab_section(2, 2, "🔌", "Cableado DC", "s2_cable_dc", [
        "Cable Solar PV1-F utilizado",
        "Polaridad correcta",
        "Conectores MC4 correctamente prensados",
        "Sin cables expuestos",
        "Sin empalmes improvisados",
        "Continuidad eléctrica verificada",
        "Resistencia de aislamiento medida",
        "Tensión de cada string medida",
        "Corriente de cada string medida",
    ])
    _tab_section(3, 3, "🛡", "Protecciones DC", "s3_prot_dc", [
        "Fusibles instalados",
        "Breaker DC instalado",
        "Seccionador DC instalado",
        "DPS Tipo II DC instalado",
        "Caja combinadora correctamente cableada",
    ])
    _tab_section(4, 4, "⚡", "Inversor", "s4_inversor", [
        "Correctamente instalado",
        "Fijación adecuada",
        "Distancias de ventilación correctas",
        "Configuración país",
        "Configuración red eléctrica",
        "Firmware actualizado",
        "Comunicación WiFi/LAN configurada",
        "Hora y fecha configuradas",
    ])
    _tab_section(5, 5, "🔋", "Baterías (Off-Grid / Híbrido)", "s5_baterias", [
        "Banco correctamente ensamblado",
        "Polaridad correcta",
        "Torque de bornes verificado",
        "Fusibles instalados",
        "Breaker instalado",
        "Voltaje del banco verificado",
        "BMS operativo",
        "Comunicación con inversor",
        "Estado de carga inicial (SOC) verificado",
    ])
    _tab_section(6, 6, "🔌", "Cableado AC", "s6_cable_ac", [
        "Conductores correctamente identificados",
        "Fase correcta",
        "Neutro correcto",
        "Tierra correcta",
        "Continuidad verificada",
    ])
    _tab_section(7, 7, "🛡", "Protecciones AC", "s7_prot_ac", [
        "Breaker AC instalado",
        "DPS Tipo II AC instalado",
        "Interruptor diferencial instalado",
        "Barra de tierra instalada",
    ])
    _tab_section(8, 8, "⏚", "Puesta a Tierra", "s8_tierra", [
        "Paneles aterrizados",
        "Estructura aterrizada",
        "Inversor aterrizado",
        "Tablero aterrizado",
        "Resistencia de puesta a tierra medida",
    ])

    # ── TAB 9: Mediciones eléctricas ──────────────────────────────────────────
    with tabs[9]:
        _sec_header("📏", 9, "Mediciones Eléctricas")
        prev_m = saved.get("s9_mediciones", {})
        dc_prev = prev_m.get("dc", {}) if isinstance(prev_m, dict) else {}
        ac_prev = prev_m.get("ac", {}) if isinstance(prev_m, dict) else {}

        st.markdown("**Lado DC**")
        mc1, mc2 = st.columns(2)
        with mc1:
            v_s1 = st.text_input("Voltaje String 1 (V)", dc_prev.get("v_str1",""), key="chk_vs1")
            v_s2 = st.text_input("Voltaje String 2 (V)", dc_prev.get("v_str2",""), key="chk_vs2")
            voc  = st.text_input("Voc Total (V)",        dc_prev.get("voc_total",""), key="chk_voc")
        with mc2:
            i_s1 = st.text_input("Corriente String 1 (A)", dc_prev.get("i_str1",""), key="chk_is1")
            i_s2 = st.text_input("Corriente String 2 (A)", dc_prev.get("i_str2",""), key="chk_is2")
            isc  = st.text_input("Isc Total (A)",          dc_prev.get("isc_total",""), key="chk_isc")

        st.markdown("**Lado AC**")
        ma1, ma2 = st.columns(2)
        with ma1:
            v_ln = st.text_input("Voltaje L-N (V)",        ac_prev.get("v_ln",""), key="chk_vln")
            v_ll = st.text_input("Voltaje L-L (V)",        ac_prev.get("v_ll",""), key="chk_vll")
            freq = st.text_input("Frecuencia (Hz)",        ac_prev.get("freq",""), key="chk_freq")
        with ma2:
            i_sal= st.text_input("Corriente salida (A)",   ac_prev.get("i_sal",""), key="chk_isal")
            pot_i= st.text_input("Potencia Instantánea (kW)", ac_prev.get("pot_inst",""), key="chk_poti")
        r_tierra = st.text_input("Resistencia puesta a tierra (Ω)",
                                   dc_prev.get("r_tierra",""), key="chk_rtie")

        if st.button("💾 Guardar Mediciones", use_container_width=True, key="chk_save_med"):
            med_data = {
                "dc": {"v_str1": v_s1, "v_str2": v_s2, "i_str1": i_s1, "i_str2": i_s2,
                        "voc_total": voc, "isc_total": isc, "r_tierra": r_tierra},
                "ac": {"v_ln": v_ln, "v_ll": v_ll, "freq": freq,
                        "i_sal": i_sal, "pot_inst": pot_i},
            }
            _save(proyecto_id, {**saved, "s9_mediciones": med_data})
            st.success("✅ Mediciones guardadas")
            st.rerun()

    # ── TAB 10: Configuración inversor ────────────────────────────────────────
    with tabs[10]:
        _sec_header("⚙", 10, "Configuración del Inversor")
        prev10 = saved.get("s10_config", {})
        items10 = [
            ("Potencia máxima configurada", "pot_max"),
            ("Voltaje nominal configurado",  "v_nom"),
            ("MPPT configurado",             "mppt"),
            ("Parámetros de batería",        "param_bat"),
            ("Prioridad Solar",              "prio_solar"),
            ("Prioridad Red",                "prio_red"),
            ("Prioridad Batería",            "prio_bat"),
            ("Límites de descarga",          "lim_desc"),
            ("Límites de carga",             "lim_carga"),
            ("Exportación a red habilitada", "export_red"),
            ("Anti-isla activado",           "anti_isla"),
        ]
        result10 = {}
        for lbl, key in items10:
            result10[key] = {"si": _chk_bool(lbl, prev10.get(key, {}), "si", f"c10_{key}")}
        if st.button("💾 Guardar Configuración", use_container_width=True, key="chk_save_10"):
            _save(proyecto_id, {**saved, "s10_config": result10})
            st.success("✅ Configuración guardada"); st.rerun()

    # ── TAB 11: Pruebas funcionales ───────────────────────────────────────────
    with tabs[11]:
        _sec_header("🧪", 11, "Pruebas Funcionales")
        prev11 = saved.get("s11_pruebas", {})
        pruebas_items = [
            "El inversor detecta los paneles",
            "Los MPPT funcionan correctamente",
            "La potencia aumenta con la irradiancia",
            "No existen alarmas",
            "Sincronización correcta con la red",
            "Inyección de energía a la red",
            "Frecuencia correcta",
            "Voltaje correcto en salida AC",
            "El inversor detecta pérdida de red",
            "Cambia correctamente a modo respaldo",
            "Mantiene cargas críticas en corte",
            "Regresa automáticamente con la red",
            "Baterías cargan correctamente",
            "Baterías descargan correctamente",
            "Comunicación con BMS verificada",
            "SOC mostrado correctamente",
        ]
        result11 = _chk_items(pruebas_items, prev11, "c11")
        if st.button("💾 Guardar Pruebas", use_container_width=True, key="chk_save_11"):
            _save(proyecto_id, {**saved, "s11_pruebas": result11})
            st.success("✅ Pruebas guardadas"); st.rerun()

    # ── TABs 12-14: Monitoreo, Seguridad, Documentación ─────────────────────
    def _tab_bool_list(tab_idx, sec_num, icon, title, field, items_kv):
        with tabs[tab_idx]:
            _sec_header(icon, sec_num, title)
            prev = saved.get(field, {})
            result = {}
            for lbl, key in items_kv:
                result[key] = {"si": _chk_bool(lbl, prev.get(key, {}), "si", f"{field}_{key}")}
            if st.button(f"💾 Guardar {sec_num}. {title}",
                          use_container_width=True, key=f"chk_save_{field}"):
                _save(proyecto_id, {**saved, field: result})
                st.success(f"✅ Sección {sec_num} guardada"); st.rerun()

    _tab_bool_list(12, 12, "📡", "Monitoreo", "s12_monitoreo", [
        ("Plataforma configurada", "plataforma"),
        ("Usuario creado", "usuario"),
        ("Contraseña entregada", "contrasena"),
        ("Monitoreo remoto operativo", "remoto"),
        ("Datos visibles en tiempo real", "datos"),
    ])
    _tab_bool_list(13, 13, "🔒", "Seguridad", "s13_seguridad", [
        ("Señalización instalada", "senalizacion"),
        ("Etiquetas de advertencia", "etiquetas"),
        ("Diagramas eléctricos en tablero", "diagramas"),
        ("Extintor disponible", "extintor"),
        ("Acceso restringido", "acceso"),
        ("Manuales entregados", "manuales"),
    ])
    _tab_bool_list(14, 14, "📄", "Documentación Entregada", "s14_documentacion", [
        ("Plano unifilar", "plano_unifilar"),
        ("Plano de ubicación", "plano_ubicacion"),
        ("Memoria de cálculo", "memoria"),
        ("Garantías", "garantias"),
        ("Manual del inversor", "manual_inv"),
        ("Manual de paneles", "manual_pan"),
        ("Certificados de pruebas", "certificados"),
        ("Protocolos de medición", "protocolos"),
        ("Informe de puesta en marcha", "informe_pm"),
        ("Capacitación al cliente", "capacitacion"),
    ])

    # ── TAB 15: Resultado final ───────────────────────────────────────────────
    with tabs[15]:
        _sec_header("🏁", 15, "Resultado Final")
        prev15 = saved.get("s15_resultado", {})
        items_r = [
            ("Sistema energizado", "energizado"),
            ("Producción correcta", "produccion"),
            ("Alarmas presentes",   "alarmas"),
            ("Cliente capacitado",  "capacitado"),
            ("Sistema entregado",   "entregado"),
        ]
        result15 = {}
        for lbl, key in items_r:
            prev_val = prev15.get(key, {}) if isinstance(prev15, dict) else {}
            c1, c2, c3 = st.columns([3, 0.7, 0.7])
            c1.markdown(f"<div style='font-size:0.83rem;color:#E0E6F0;padding-top:0.45rem;'>{lbl}</div>",
                         unsafe_allow_html=True)
            si_v = c2.checkbox("SI", value=bool(prev_val.get("si",False)), key=f"r15_{key}_si")
            no_v = c3.checkbox("NO", value=bool(prev_val.get("no",False)), key=f"r15_{key}_no")
            result15[key] = {"si": si_v, "no": no_v}

        st.markdown("---")
        obs_txt = st.text_area("Observaciones generales", saved.get("observaciones",""),
                                height=100, key="chk_obs")
        if st.button("💾 Guardar Resultado Final", use_container_width=True, key="chk_save_15",
                      type="primary"):
            _save(proyecto_id, {**saved, "s15_resultado": result15, "observaciones": obs_txt})
            st.success("✅ Resultado final guardado"); st.rerun()

    # ── TAB PDF: Exportar ─────────────────────────────────────────────────────
    with tabs[16]:
        st.markdown("""
        <div class='sol-card-title'>📄 GENERAR PDF — CHECKLIST PUESTA EN MARCHA</div>""",
                    unsafe_allow_html=True)
        st.markdown("""
        <div class='info-note'>
            El PDF incluye las 15 secciones del checklist con semáforo ✅/❌,
            tabla de mediciones eléctricas DC/AC, resultado final y área de firmas.<br>
            <b>Normas:</b> RETIE · NTC 2050 · IEC 62446-1
        </div>""", unsafe_allow_html=True)

        saved_fresh = _load(proyecto_id)
        if not saved_fresh:
            st.warning("⚠ Completa y guarda el checklist primero.")
        else:
            # Progreso
            secciones_ok = sum(1 for f in [
                "s1_mecanica","s2_cable_dc","s3_prot_dc","s4_inversor","s5_baterias",
                "s6_cable_ac","s7_prot_ac","s8_tierra","s9_mediciones","s10_config",
                "s11_pruebas","s12_monitoreo","s13_seguridad","s14_documentacion","s15_resultado"
            ] if saved_fresh.get(f))
            st.progress(secciones_ok / 15, text=f"{secciones_ok}/15 secciones completadas")

            if st.button("📄 Generar PDF Checklist", use_container_width=True,
                          key="chk_gen_pdf", type="primary"):
                datos_pdf = {
                    "proyecto": {
                        "nombre":      p_inf[1] if p_inf else "",
                        "municipio":   p_inf[2] if p_inf else "",
                        "propietario": "",
                    },
                    "checklist": {
                        **{k: saved_fresh.get(k) for k in [
                            "tecnico","supervisor","fecha_inst","tipo_sistema",
                            "pot_inst_kwp","inv_modelo","n_paneles",
                            "s1_mecanica","s2_cable_dc","s3_prot_dc","s4_inversor","s5_baterias",
                            "s6_cable_ac","s7_prot_ac","s8_tierra","s10_config","s11_pruebas",
                            "s12_monitoreo","s13_seguridad","s14_documentacion","s15_resultado",
                            "observaciones"]},
                    },
                    "mediciones": saved_fresh.get("s9_mediciones", {}),
                }
                with st.spinner("Generando PDF..."):
                    pdf_bytes = generar_pdf_checklist(datos_pdf)
                nom  = (p_inf[1] if p_inf else "Proyecto").replace(" ","_")
                fname= f"Checklist_PEM_{nom}_{date.today().strftime('%Y%m%d')}.pdf"
                st.download_button("⬇ Descargar Checklist PDF", data=pdf_bytes,
                                    file_name=fname, mime="application/pdf",
                                    use_container_width=True, key="chk_dl_pdf")
                st.success(f"✅ PDF generado: {fname}")
