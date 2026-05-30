"""
modulo_materiales.py — Catálogo de Materiales FV / RETIE
SolarCalc Pro · Módulo externo
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from db_utils import get_conn, init_modulos_db

# ── Catálogo RETIE inicial (se carga solo una vez si la tabla está vacía) ────
CATALOGO_RETIE = [
    # categoria, descripcion, unidad, precio_ref, retie
    # — Paneles y estructura —
    ("Paneles Solares",    "Panel solar monocristalino 550Wp",                   "UND",  680000, 1),
    ("Paneles Solares",    "Panel solar monocristalino 450Wp",                   "UND",  550000, 1),
    ("Paneles Solares",    "Panel solar bifacial 600Wp",                          "UND",  750000, 1),
    ("Estructura Soporte", "Estructura metálica galvanizada techo inclinado 4 pan","UND", 320000, 1),
    ("Estructura Soporte", "Estructura metálica galvanizada techo plano 4 pan",   "UND",  310000, 1),
    ("Estructura Soporte", "Estructura aluminio anodizado 2 paneles",             "UND",  180000, 0),
    ("Estructura Soporte", "Tornillo inox M8×60 mm con tuerca y arandela",        "UND",    1800, 1),
    ("Estructura Soporte", "Perfil aluminio riel 40×40 mm (ML)",                  "ML",   18000, 0),
    # — Controlador MPPT —
    ("Controlador MPPT",   "Controlador MPPT 40A / 48V (p.ej. EPSolar 4215BN)",  "UND",  420000, 1),
    ("Controlador MPPT",   "Controlador MPPT 60A / 48V (p.ej. Victron 150/60)",  "UND",  780000, 1),
    ("Controlador MPPT",   "Controlador MPPT 100A / 48V (p.ej. Victron 150/100)","UND", 1250000, 1),
    ("Controlador MPPT",   "Controlador MPPT 150A / 48V (p.ej. Victron 250/150)","UND", 2100000, 1),
    # — Baterías —
    ("Baterías",           "Batería LiFePO4 100Ah 48V (BMS incluido)",            "UND", 1850000, 1),
    ("Baterías",           "Batería LiFePO4 200Ah 48V (BMS incluido)",            "UND", 3400000, 1),
    ("Baterías",           "Batería plomo ácido AGM 100Ah 12V",                   "UND",  420000, 1),
    ("Baterías",           "Batería gel 100Ah 12V",                               "UND",  480000, 0),
    # — Inversor —
    ("Inversor",           "Inversor Off-Grid 3kVA 48V 220V (p.ej. Axpert 3000)","UND", 1200000, 1),
    ("Inversor",           "Inversor Off-Grid 5kVA 48V 220V",                    "UND", 1950000, 1),
    ("Inversor",           "Inversor Off-Grid 8kVA 48V 220V",                    "UND", 3100000, 1),
    ("Inversor",           "Inversor Híbrido 5kVA 48V On/Off Grid",              "UND", 3500000, 1),
    ("Inversor",           "Inversor Híbrido 10kVA 48V On/Off Grid",             "UND", 6200000, 1),
    # — Cableado DC ─ RETIE Art. 17 y NTC 2050 —
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 10 rojo (ML)",              "ML",    3200, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 10 negro (ML)",             "ML",    3200, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 6 rojo (ML)",               "ML",    6800, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 6 negro (ML)",              "ML",    6800, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 4 rojo (ML)",               "ML",   10500, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 4 negro (ML)",              "ML",   10500, 1),
    ("Cableado DC",        "Cable unipolar THWN-2 AWG 2/0 rojo (ML)",             "ML",   28000, 1),
    ("Cableado DC",        "Cable solar PV ZZ-F 6mm² (ML)",                       "ML",    5500, 1),
    ("Cableado DC",        "Cable solar PV ZZ-F 10mm² (ML)",                      "ML",    8200, 1),
    # — Cableado AC —
    ("Cableado AC",        "Cable THWN-2 AWG 10 3 conductores (ML)",              "ML",    9600, 1),
    ("Cableado AC",        "Cable THWN-2 AWG 8 3 conductores (ML)",               "ML",   15000, 1),
    ("Cableado AC",        "Cable THWN-2 AWG 6 3 conductores (ML)",               "ML",   20400, 1),
    # — Protecciones DC — RETIE Art. 17 —
    ("Protecciones DC",    "Portafusible DC 1000V 30A (2 polos)",                  "UND",   38000, 1),
    ("Protecciones DC",    "Fusible tipo NH DC 30A 1000V",                         "UND",   12000, 1),
    ("Protecciones DC",    "Fusible tipo NH DC 60A 1000V",                         "UND",   16000, 1),
    ("Protecciones DC",    "Interruptor termomagnético DC 2P 63A 600V",            "UND",   95000, 1),
    ("Protecciones DC",    "Interruptor termomagnético DC 2P 100A 600V",           "UND",  145000, 1),
    ("Protecciones DC",    "Seccionador DC 2P 32A 1000V",                          "UND",   75000, 1),
    ("Protecciones DC",    "Seccionador DC 2P 63A 1000V",                          "UND",  110000, 1),
    # — Protecciones AC — RETIE Art. 11 —
    ("Protecciones AC",    "Interruptor caja moldeada 3P 63A 10kA",               "UND",  185000, 1),
    ("Protecciones AC",    "Interruptor diferencial 2P 63A 30mA 10kA",            "UND",  145000, 1),
    ("Protecciones AC",    "Interruptor diferencial 4P 63A 30mA",                 "UND",  280000, 1),
    ("Protecciones AC",    "Breaker 2P 20A termomagnético riel DIN",               "UND",   32000, 1),
    # — Pararrayos / SPD — RETIE Art. 18 —
    ("Pararrayos / SPD",   "Descargador sobretensión SPD DC Tipo 2 1000V",        "UND",  120000, 1),
    ("Pararrayos / SPD",   "Descargador sobretensión SPD AC Tipo 2 220V",         "UND",   95000, 1),
    ("Pararrayos / SPD",   "SPD Tipo 1+2 Combinado DC 1000V",                     "UND",  195000, 1),
    # — Puesta a tierra — RETIE Art. 15 —
    ("Puesta a Tierra",    "Varilla copperweld 5/8\"×1.5 m",                      "UND",   38000, 1),
    ("Puesta a Tierra",    "Cable desnudo cobre 4 AWG para tierra (ML)",           "ML",    9500, 1),
    ("Puesta a Tierra",    "Conector tipo grapa bronce para varilla",              "UND",    8500, 1),
    ("Puesta a Tierra",    "Caja de inspección para tierra",                       "UND",   35000, 1),
    # — Accesorios de instalación —
    ("Accesorios",         "Conector MC4 macho+hembra (par)",                     "PAR",    8500, 1),
    ("Accesorios",         "Caja de conexiones (junction box) FV 4 entradas",     "UND",   65000, 1),
    ("Accesorios",         "Bandeja portacable PVC 60×40 mm (ML)",                "ML",    12000, 0),
    ("Accesorios",         "Conduit EMT 3/4\" (tira 3m)",                         "UND",   18000, 1),
    ("Accesorios",         "Conduit PVC 3/4\" (tira 3m)",                         "UND",    9500, 0),
    ("Accesorios",         "Amarres plásticos 30 cm (bolsa 100)",                 "BOLS",   8000, 0),
    ("Accesorios",         "Cinta autofundente 19mm×9m",                          "UND",   12000, 0),
    ("Accesorios",         "Prensaestopa PG21 para caja",                         "UND",    4500, 0),
    ("Accesorios",         "Terminal de ojo cobre 4 AWG (x10 und)",               "BLS",   15000, 1),
    ("Accesorios",         "Terminal de ojo cobre 1/0 AWG (x10 und)",             "BLS",   32000, 1),
    # — Tableros y cajas —
    ("Tableros",           "Tablero metálico 24 circuitos con puerta",            "UND",  195000, 1),
    ("Tableros",           "Tablero metálico 12 circuitos con puerta",            "UND",  120000, 1),
    ("Tableros",           "Gabinete metálico 60×40×20 cm IP65",                  "UND",  185000, 1),
    ("Tableros",           "Gabinete metálico 40×30×20 cm IP55",                  "UND",  125000, 1),
    ("Tableros",           "Riel DIN 35mm (ML)",                                  "ML",    12000, 0),
    # — Señalización — RETIE Art. 16 —
    ("Señalización RETIE", "Etiqueta adhesiva PELIGRO ALTA TENSIÓN DC",           "UND",    4500, 1),
    ("Señalización RETIE", "Etiqueta adhesiva SISTEMA FOTOVOLTAICO",              "UND",    4500, 1),
    ("Señalización RETIE", "Etiqueta cinta peligro eléctrico 50 m",               "UND",   22000, 1),
    ("Señalización RETIE", "Placa identificación circuitos (set)",                "SET",   18000, 1),
    ("Señalización RETIE", "Diagrama unifilar plastificado",                      "UND",   15000, 1),
    # — Monitoreo —
    ("Monitoreo",          "Monitor de energía WiFi 1 fase",                      "UND",  185000, 0),
    ("Monitoreo",          "Monitor de energía WiFi 3 fases",                     "UND",  320000, 0),
    ("Monitoreo",          "Sensor temperatura paneles",                           "UND",   65000, 0),
    ("Monitoreo",          "Datalogger para controlador RS485",                    "UND",  145000, 0),
    # — Consumibles de obra —
    ("Consumibles",        "Soldadura estaño rollo 60/40 (500g)",                 "UND",   28000, 0),
    ("Consumibles",        "Pasta de soldar flux (frasco)",                       "UND",   12000, 0),
    ("Consumibles",        "Silicona gris neutra (cartucho)",                     "UND",   18000, 0),
    ("Consumibles",        "Grasa dieléctrica (tubo)",                            "UND",   14000, 0),
]

def _seed_materiales():
    """Inserta el catálogo RETIE si la tabla está vacía."""
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
    if n == 0:
        conn.executemany(
            "INSERT INTO materiales(categoria,descripcion,unidad,precio_ref,retie) VALUES(?,?,?,?,?)",
            CATALOGO_RETIE)
        conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_materiales():
    init_modulos_db()
    _seed_materiales()

    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
     color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        🔩 CATÁLOGO DE MATERIALES — FV / RETIE
    </div>
    <div style='background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.25);
     border-radius:8px;padding:0.7rem 1rem;font-size:0.8rem;color:#8A9BBD;margin-bottom:1rem;'>
        Los materiales marcados con ⚡ son requeridos o referenciados por el
        RETIE (Reglamento Técnico de Instalaciones Eléctricas — Res. 40117/2014).
    </div>
    """, unsafe_allow_html=True)

    conn = get_conn()
    mats = pd.read_sql("SELECT * FROM materiales WHERE activo=1 ORDER BY categoria,descripcion", conn)
    conn.close()

    # Filtros
    fc1, fc2 = st.columns([2,1])
    with fc1:
        buscar_m = st.text_input("🔍 Buscar material", key="mat_buscar")
    with fc2:
        cats_m = ["Todas"] + sorted(mats["categoria"].unique().tolist())
        cat_sel_m = st.selectbox("Categoría", cats_m, key="mat_cat")

    df_show = mats.copy()
    if buscar_m:
        df_show = df_show[df_show["descripcion"].str.lower().str.contains(buscar_m.lower())]
    if cat_sel_m != "Todas":
        df_show = df_show[df_show["categoria"] == cat_sel_m]

    if not df_show.empty:
        df_show["RETIE"] = df_show["retie"].map({1:"⚡ Sí","":""}).fillna("—")
        df_show["precio_ref"] = df_show["precio_ref"].apply(lambda x: f"$ {x:,.0f}")
        show_cols = df_show[["id","categoria","descripcion","unidad","precio_ref","RETIE"]].copy()
        show_cols.columns = ["ID","Categoría","Descripción","Und","Precio Ref.","RETIE"]
        st.dataframe(show_cols.set_index("ID"), use_container_width=True)
        st.caption(f"{len(df_show)} materiales mostrados")

    # Agregar material
    st.markdown("<hr style='border-color:#2A3A55;'>", unsafe_allow_html=True)
    with st.expander("➕ Agregar nuevo material al catálogo"):
        ma1,ma2,ma3 = st.columns([2,2,1])
        with ma1:
            m_cat  = st.text_input("Categoría",  placeholder="Ej: Cableado DC", key="m_cat")
            m_desc = st.text_input("Descripción", key="m_desc")
        with ma2:
            m_und  = st.text_input("Unidad",  key="m_und", placeholder="UND, ML, M², GL...")
            m_ref  = st.number_input("Precio referencia ($)", 0.0, 99999999.0, 0.0, 1000.0, key="m_ref")
        with ma3:
            m_ret  = st.checkbox("⚡ RETIE", key="m_ret")
            m_not  = st.text_input("Notas",  key="m_not")

        if st.button("➕ Agregar material", use_container_width=True):
            if m_desc.strip() and m_cat.strip() and m_und.strip():
                conn = get_conn()
                conn.execute("INSERT INTO materiales(categoria,descripcion,unidad,precio_ref,retie,notas) VALUES(?,?,?,?,?,?)",
                              (m_cat.strip(), m_desc.strip(), m_und.strip(),
                               m_ref, 1 if m_ret else 0, m_not.strip()))
                conn.commit(); conn.close()
                st.success("Material agregado ✓"); st.rerun()

    # Editar / Eliminar
    with st.expander("✏ Editar precio / Eliminar"):
        conn = get_conn()
        mats_all = pd.read_sql("SELECT id,descripcion,precio_ref FROM materiales WHERE activo=1 ORDER BY descripcion", conn)
        conn.close()
        if not mats_all.empty:
            m_edit_opts = {f"{int(r['id'])} — {r['descripcion']}": int(r["id"]) for _, r in mats_all.iterrows()}
            m_edit_sel  = st.selectbox("Material:", list(m_edit_opts.keys()), key="m_edit_sel")
            m_edit_id   = m_edit_opts[m_edit_sel]
            m_edit_row  = mats_all[mats_all["id"]==m_edit_id].iloc[0]
            nuevo_precio = st.number_input("Nuevo precio referencia ($)", 0.0, 99999999.0,
                                            float(m_edit_row["precio_ref"]), 1000.0, key="m_new_price")
            eb1,eb2 = st.columns(2)
            with eb1:
                if st.button("💾 Actualizar precio", use_container_width=True, key="m_upd"):
                    conn = get_conn()
                    conn.execute("UPDATE materiales SET precio_ref=? WHERE id=?", (nuevo_precio, m_edit_id))
                    conn.commit(); conn.close(); st.success("Actualizado ✓"); st.rerun()
            with eb2:
                if st.button("🗑 Desactivar material", use_container_width=True, key="m_del"):
                    conn = get_conn()
                    conn.execute("UPDATE materiales SET activo=0 WHERE id=?", (m_edit_id,))
                    conn.commit(); conn.close(); st.success("Desactivado ✓"); st.rerun()
