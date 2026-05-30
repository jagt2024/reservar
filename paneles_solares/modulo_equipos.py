"""
modulo_equipos.py  — Equipos y Herramientas
modulo_personal.py — Personal idóneo FV / RETIE
(Ambos módulos en un archivo, se importan por función)
SolarCalc Pro · Módulo externo
"""
import streamlit as st
import pandas as pd
from db_utils import get_conn, init_modulos_db

# ════════════════════════════════════════════════════════════════════════════
# CATÁLOGOS INICIALES
# ════════════════════════════════════════════════════════════════════════════
CATALOGO_EQUIPOS = [
    # tipo, categoria, descripcion, unidad, precio_ref (alquiler/día), rendimiento
    ("Equipo",       "Medición Eléctrica",  "Multímetro digital CAT IV 1000V",                "DÍA",   35000, "Verificación circuitos DC/AC"),
    ("Equipo",       "Medición Eléctrica",  "Pinza amperimétrica AC/DC 1000A",                "DÍA",   45000, "Medición corriente paneles"),
    ("Equipo",       "Medición Eléctrica",  "Analizador de calidad de energía trifásico",      "DÍA",  120000, "Análisis red AC"),
    ("Equipo",       "Medición Eléctrica",  "Telurómetro (medición tierra)",                  "DÍA",   85000, "RETIE Art. 15 — tierra ≤ 5Ω"),
    ("Equipo",       "Medición Eléctrica",  "Megóhmetro 1000V DC",                            "DÍA",   75000, "Prueba aislamiento cable"),
    ("Equipo",       "Medición Eléctrica",  "Irradiómetro solar portátil",                    "DÍA",   95000, "Verificación HSP en sitio"),
    ("Equipo",       "Medición Eléctrica",  "Fluke 1587 FC — Medidor aislamiento+multímetro", "DÍA",  110000, "Prueba rigidez dieléctrica"),
    ("Equipo",       "Herramienta Eléctrica","Taladro percutor 1200W + juego brocas",          "DÍA",   50000, "Fijación estructura"),
    ("Equipo",       "Herramienta Eléctrica","Esmeriladora angular 4.5\" 900W",                "DÍA",   35000, "Corte perfiles metálicos"),
    ("Equipo",       "Herramienta Eléctrica","Soldadora inversora 200A",                       "DÍA",   95000, "Estructura metálica"),
    ("Equipo",       "Herramienta Eléctrica","Pistola de calor para termo-retráctil",          "DÍA",   25000, "Empalmes de cables"),
    ("Equipo",       "Elevación",           "Andamio tubular multidireccional (m²/día)",       "M²/DÍA",4500, "Trabajos en altura"),
    ("Equipo",       "Elevación",           "Escalera extensible aluminio 8 m",               "DÍA",   30000, "Acceso cubierta"),
    ("Equipo",       "Elevación",           "Grúa telescópica 5 ton (por turno)",             "TURNO",850000, "Paneles >200 kg"),
    ("Equipo",       "Elevación",           "Polipasto eléctrico 500 kg",                     "DÍA",   95000, "Izado baterías"),
    ("Equipo",       "Seguridad",           "Equipo de protección anti-caídas (arnés+línea)",  "DÍA",   28000, "RETIE — trabajos altura >1.8m"),
    ("Equipo",       "Seguridad",           "Casco dieléctrico clase E",                      "DÍA",    8000, "RETIE obligatorio"),
    ("Equipo",       "Seguridad",           "Guantes dieléctricos clase 00 (par)",            "DÍA",   18000, "RETIE — tensiones >50V DC"),
    ("Equipo",       "Seguridad",           "Gafas de seguridad anti-UV",                     "DÍA",    5000, "Trabajo en cubierta"),
    ("Equipo",       "Seguridad",           "Detector de tensión sin contacto DC",             "DÍA",   22000, "Verificación LOTO"),
    ("Herramienta",  "Herramienta Manual",  "Llave de torque 10-80 Nm",                       "DÍA",   25000, "Apriete tornillos estructura"),
    ("Herramienta",  "Herramienta Manual",  "Juego llaves combinadas 8-22 mm",                "DÍA",   12000, "Montaje general"),
    ("Herramienta",  "Herramienta Manual",  "Pelacables AWG 10-2 profesional",                "DÍA",   18000, "Preparación cables"),
    ("Herramienta",  "Herramienta Manual",  "Crimpadora para conectores MC4",                 "DÍA",   35000, "Conexiones string"),
    ("Herramienta",  "Herramienta Manual",  "Destornillador aislado 1000V (juego)",           "DÍA",   15000, "RETIE — trabajos en vivo"),
    ("Herramienta",  "Herramienta Manual",  "Ponchadora hidráulica terminales 4-120 mm²",     "DÍA",   55000, "Terminales batería/inversor"),
    ("Herramienta",  "Herramienta Manual",  "Sierra caladora + hojas metálicas",              "DÍA",   30000, "Tableros/cajas"),
    ("Herramienta",  "Herramienta Manual",  "Nivel láser autonivelante",                      "DÍA",   45000, "Alineación paneles"),
    ("Herramienta",  "Herramienta Manual",  "Cinta métrica 50 m",                             "DÍA",    5000, "Replanteo"),
    ("Herramienta",  "Informática",         "Laptop con software SolarCalc/PVSyst",            "DÍA",   80000, "Simulación y documentación"),
    ("Herramienta",  "Informática",         "Cámara termográfica Fluke Ti400",                "DÍA",  195000, "Hotspots en paneles"),
    ("Herramienta",  "Informática",         "Drone DJI para inspección cubierta",             "SERV", 350000, "Inspección previa"),
    ("Herramienta",  "Transporte",          "Camión grúa 2 ton (ida+vuelta)",                 "SERV", 480000, "Transporte equipos pesados"),
    ("Herramienta",  "Transporte",          "Furgón para materiales",                         "DÍA",  180000, "Transporte materiales"),
]

CATALOGO_PERSONAL = [
    # cargo, perfil, certificacion, salario_dia, retie
    ("Director de proyecto / Ing. Electricista",
     "Ingeniero Electricista o Electrónico con tarjeta profesional COPNIA. "
     "Experiencia mínima 3 años en proyectos FV.",
     "Tarjeta Profesional COPNIA + Certificación instalador UPME",
     320000, 1),

    ("Ingeniero Diseñador FV",
     "Ingeniero con especialización en energías renovables. "
     "Manejo de PVSyst, AutoCAD, NEC, NTC 2050.",
     "Tarjeta Profesional COPNIA + curso ICONTEC NTC 5656",
     280000, 1),

    ("Técnico electricista RETIE",
     "Técnico electricista con licencia vigente CONTE/ICONTEC. "
     "Conocimiento NTC 2050 y RETIE. Experiencia en instalaciones FV.",
     "Licencia Técnica Electricista Vigente (Resolución 40117 art. 69)",
     150000, 1),

    ("Auxiliar electricista",
     "Técnico en electricidad o aprendiz SENA en electricidad. "
     "Conocimiento básico de circuitos DC/AC.",
     "Certificado SENA Electricidad Residencial o Industrial",
     90000, 1),

    ("Técnico en altura certificado",
     "Persona con certificación trabajo en alturas MINTRABAJO vigente. "
     "Experiencia en techos e instalaciones exteriores.",
     "Certificado Trabajo en Alturas Nivel Avanzado — MINTRABAJO (cada 3 años)",
     130000, 1),

    ("Inspector RETIE",
     "Persona natural u organismo inspector autorizado por ONAC. "
     "Verificación cumplimiento RETIE en instalaciones eléctricas.",
     "Acreditación ONAC como Organismo Inspector RETIE",
     450000, 1),

    ("Soldador estructural",
     "Soldador con certificación AWS D1.1 o equivalente. "
     "Experiencia en estructuras metálicas para soporte de paneles.",
     "Certificado soldador AWS D1.1 o ASME IX",
     175000, 0),

    ("Auxiliar de obra / Oficios varios",
     "Persona con capacitación en seguridad industrial básica. "
     "Apoyo en transporte y suministro de materiales.",
     "Curso básico SENA seguridad industrial",
     80000, 0),

    ("Asesor comercial / Gerente de ventas",
     "Profesional con experiencia en venta de sistemas de energía renovable. "
     "Conocimiento técnico básico de sistemas FV.",
     "Certificación UPME instalador FV (deseable)",
     200000, 0),

    ("Especialista en monitoreo y comisionamiento",
     "Técnico/ingeniero con experiencia en configuración de inversores, "
     "controladores MPPT y sistemas SCADA para FV.",
     "Certificado fabricante (Victron, Fronius, SMA, etc.)",
     220000, 0),

    ("Comisionista / Startup FV",
     "Ingeniero encargado de pruebas de puesta en marcha: "
     "medición IV curve, verificación protecciones, pruebas de aislamiento.",
     "Certificado comisionamiento ASOSEL o equivalente",
     300000, 1),
]

def _seed_equipos():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM equipos_herramientas").fetchone()[0]
    if n == 0:
        conn.executemany(
            "INSERT INTO equipos_herramientas(tipo,categoria,descripcion,unidad,precio_ref,rendimiento) VALUES(?,?,?,?,?,?)",
            CATALOGO_EQUIPOS)
        conn.commit()
    conn.close()

def _seed_personal():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM personal").fetchone()[0]
    if n == 0:
        conn.executemany(
            "INSERT INTO personal(cargo,perfil,certificacion,salario_dia,retie) VALUES(?,?,?,?,?)",
            CATALOGO_PERSONAL)
        conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO EQUIPOS Y HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_equipos():
    init_modulos_db()
    _seed_equipos()

    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
     color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        🔧 EQUIPOS Y HERRAMIENTAS
    </div>
    """, unsafe_allow_html=True)

    conn = get_conn()
    eqs = pd.read_sql("SELECT * FROM equipos_herramientas WHERE activo=1 ORDER BY tipo,categoria,descripcion", conn)
    conn.close()

    fe1,fe2,fe3 = st.columns([2,1,1])
    with fe1: buscar_e = st.text_input("🔍 Buscar", key="eq_buscar")
    with fe2:
        tipos_e = ["Todos"] + sorted(eqs["tipo"].unique().tolist())
        tipo_sel = st.selectbox("Tipo", tipos_e, key="eq_tipo")
    with fe3:
        cats_e = ["Todas"] + sorted(eqs["categoria"].unique().tolist())
        cat_sel_e = st.selectbox("Categoría", cats_e, key="eq_cat")

    df_e = eqs.copy()
    if buscar_e: df_e = df_e[df_e["descripcion"].str.lower().str.contains(buscar_e.lower())]
    if tipo_sel  != "Todos":  df_e = df_e[df_e["tipo"] == tipo_sel]
    if cat_sel_e != "Todas":  df_e = df_e[df_e["categoria"] == cat_sel_e]

    if not df_e.empty:
        df_e["precio_ref"] = df_e["precio_ref"].apply(lambda x: f"$ {x:,.0f}")
        show_e = df_e[["id","tipo","categoria","descripcion","unidad","precio_ref","rendimiento"]].copy()
        show_e.columns = ["ID","Tipo","Categoría","Descripción","Und/Período","Precio Ref.","Uso/Rendimiento"]
        st.dataframe(show_e.set_index("ID"), use_container_width=True)
        st.caption(f"{len(df_e)} equipos/herramientas mostrados")

    with st.expander("➕ Agregar equipo o herramienta"):
        ea1,ea2 = st.columns(2)
        with ea1:
            e_tipo = st.selectbox("Tipo", ["Equipo","Herramienta"], key="e_tipo_add")
            e_cat  = st.text_input("Categoría", key="e_cat_add")
            e_desc = st.text_input("Descripción", key="e_desc_add")
        with ea2:
            e_und  = st.text_input("Unidad/Período", placeholder="DÍA, SERV, TURNO", key="e_und_add")
            e_ref  = st.number_input("Precio ref. ($)", 0.0, 9999999.0, 0.0, 5000.0, key="e_ref_add")
            e_rend = st.text_input("Uso/Rendimiento", key="e_rend_add")
        if st.button("➕ Agregar equipo", use_container_width=True, key="e_add_btn"):
            if e_desc.strip():
                conn = get_conn()
                conn.execute("INSERT INTO equipos_herramientas(tipo,categoria,descripcion,unidad,precio_ref,rendimiento) VALUES(?,?,?,?,?,?)",
                              (e_tipo, e_cat.strip(), e_desc.strip(), e_und.strip(), e_ref, e_rend.strip()))
                conn.commit(); conn.close(); st.success("Agregado ✓"); st.rerun()

    with st.expander("✏ Editar precio / Desactivar"):
        conn = get_conn()
        all_e = pd.read_sql("SELECT id,descripcion,precio_ref FROM equipos_herramientas WHERE activo=1 ORDER BY descripcion", conn)
        conn.close()
        if not all_e.empty:
            e_edit_opts = {f"{int(r['id'])} — {r['descripcion']}": int(r["id"]) for _, r in all_e.iterrows()}
            e_edit_sel  = st.selectbox("Equipo:", list(e_edit_opts.keys()), key="e_edit_sel")
            e_edit_id   = e_edit_opts[e_edit_sel]
            e_edit_row  = all_e[all_e["id"]==e_edit_id].iloc[0]
            e_nuevo_p   = st.number_input("Nuevo precio ref.", 0.0, 9999999.0,
                                           float(e_edit_row["precio_ref"]), 5000.0, key="e_np")
            eb1e, eb2e = st.columns(2)
            with eb1e:
                if st.button("💾 Actualizar", use_container_width=True, key="e_upd"):
                    conn = get_conn()
                    conn.execute("UPDATE equipos_herramientas SET precio_ref=? WHERE id=?", (e_nuevo_p, e_edit_id))
                    conn.commit(); conn.close(); st.success("✓"); st.rerun()
            with eb2e:
                if st.button("🗑 Desactivar", use_container_width=True, key="e_del"):
                    conn = get_conn()
                    conn.execute("UPDATE equipos_herramientas SET activo=0 WHERE id=?", (e_edit_id,))
                    conn.commit(); conn.close(); st.success("✓"); st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PERSONAL
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_personal():
    init_modulos_db()
    _seed_personal()

    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
     color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        👷 PERSONAL IDÓNEO — FV / RETIE
    </div>
    <div style='background:rgba(255,82,82,0.08);border:1px solid rgba(255,82,82,0.25);
     border-radius:8px;padding:0.7rem 1rem;font-size:0.8rem;color:#8A9BBD;margin-bottom:1rem;'>
        ⚠ El RETIE (Art. 69) exige que las instalaciones eléctricas sean realizadas o supervisadas
        por profesionales y técnicos con licencia vigente. El incumplimiento puede generar
        sanciones y nulidad del certificado de conformidad.
    </div>
    """, unsafe_allow_html=True)

    conn = get_conn()
    pers = pd.read_sql("SELECT * FROM personal WHERE activo=1 ORDER BY retie DESC, cargo", conn)
    conn.close()

    fp1, fp2 = st.columns([2,1])
    with fp1: buscar_p = st.text_input("🔍 Buscar cargo", key="per_buscar")
    with fp2:
        retie_f = st.radio("Filtro RETIE", ["Todos","Solo RETIE"], horizontal=True, key="per_retie_f")

    df_p = pers.copy()
    if buscar_p: df_p = df_p[df_p["cargo"].str.lower().str.contains(buscar_p.lower())]
    if retie_f == "Solo RETIE": df_p = df_p[df_p["retie"]==1]

    if not df_p.empty:
        for _, pr in df_p.iterrows():
            retie_badge = "<span style='background:#FF5252;color:#fff;padding:1px 6px;border-radius:4px;font-size:0.7rem;'>RETIE</span>" if pr["retie"] else ""
            st.markdown(f"""
            <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
             padding:1rem 1.2rem;margin-bottom:0.7rem;'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div style='font-family:Rajdhani,sans-serif;font-size:1rem;font-weight:700;
                     color:#FFB300;'>{pr['cargo']} {retie_badge}</div>
                    <div style='font-family:Share Tech Mono,monospace;color:#00E676;font-size:0.95rem;'>
                        $ {pr['salario_dia']:,.0f} / día</div>
                </div>
                <div style='font-size:0.82rem;color:#8A9BBD;margin-top:0.4rem;line-height:1.6;'>
                    <b style='color:#E8EDF5;'>Perfil:</b> {pr['perfil']}</div>
                <div style='font-size:0.78rem;color:#FF5252;margin-top:0.3rem;'>
                    <b>Certificación requerida:</b> {pr['certificacion']}</div>
            </div>""", unsafe_allow_html=True)

    with st.expander("➕ Agregar cargo / perfil"):
        pa1,pa2 = st.columns(2)
        with pa1:
            p_cargo = st.text_input("Cargo", key="p_cargo_add")
            p_perfil= st.text_area("Perfil requerido", key="p_perfil_add", height=80)
        with pa2:
            p_cert  = st.text_area("Certificaciones requeridas", key="p_cert_add", height=80)
            p_sal   = st.number_input("Salario/día ($)", 0.0, 9999999.0, 0.0, 10000.0, key="p_sal_add")
            p_ret   = st.checkbox("⚡ Requerido por RETIE", key="p_ret_add")
        if st.button("➕ Agregar cargo", use_container_width=True, key="p_add_btn"):
            if p_cargo.strip():
                conn = get_conn()
                conn.execute("INSERT INTO personal(cargo,perfil,certificacion,salario_dia,retie) VALUES(?,?,?,?,?)",
                              (p_cargo.strip(), p_perfil.strip(), p_cert.strip(), p_sal, 1 if p_ret else 0))
                conn.commit(); conn.close(); st.success("Cargo agregado ✓"); st.rerun()

    with st.expander("✏ Editar salario / Desactivar"):
        conn = get_conn()
        all_p = pd.read_sql("SELECT id,cargo,salario_dia FROM personal WHERE activo=1 ORDER BY cargo", conn)
        conn.close()
        if not all_p.empty:
            p_edit_opts = {f"{int(r['id'])} — {r['cargo']}": int(r["id"]) for _, r in all_p.iterrows()}
            p_edit_sel  = st.selectbox("Cargo:", list(p_edit_opts.keys()), key="p_edit_sel")
            p_edit_id   = p_edit_opts[p_edit_sel]
            p_edit_row  = all_p[all_p["id"]==p_edit_id].iloc[0]
            p_nuevo_s   = st.number_input("Nuevo salario/día ($)", 0.0, 9999999.0,
                                           float(p_edit_row["salario_dia"]), 10000.0, key="p_ns")
            pb1p, pb2p = st.columns(2)
            with pb1p:
                if st.button("💾 Actualizar", use_container_width=True, key="p_upd"):
                    conn = get_conn()
                    conn.execute("UPDATE personal SET salario_dia=? WHERE id=?", (p_nuevo_s, p_edit_id))
                    conn.commit(); conn.close(); st.success("✓"); st.rerun()
            with pb2p:
                if st.button("🗑 Desactivar", use_container_width=True, key="p_del"):
                    conn = get_conn()
                    conn.execute("UPDATE personal SET activo=0 WHERE id=?", (p_edit_id,))
                    conn.commit(); conn.close(); st.success("✓"); st.rerun()
