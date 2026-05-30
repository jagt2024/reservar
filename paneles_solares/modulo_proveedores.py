"""
modulo_proveedores.py — Consulta de Precios y Proveedores FV
SolarCalc Pro · Módulo externo

Proveedores incluidos:
  Colombia:
    1. Solarity LAT     — https://shop.solarity.lat/
    2. AutoSolar CO     — https://autosolar.co/
    3. Solen Technology — https://solentechnology.com/
  Internacional:
    4. Victron Energy   — https://www.victronenergy.com/
    5. Solar-Electric   — https://www.solar-electric.com/
"""
import streamlit as st
import base64
from datetime import datetime

# ─── Catálogo de proveedores ──────────────────────────────────────────────────
PROVEEDORES = [
    {
        "id":          "solarity",
        "nombre":      "Solarity LAT",
        "pais":        "🇨🇴 Colombia",
        "ciudad":      "Bogotá / Medellín",
        "url":         "https://shop.solarity.lat/",
        "logo_color":  "#ED7D0C",
        "descripcion": (
            "Distribuidor y mayorista de sistemas fotovoltaicos para Colombia y Latinoamérica. "
            "Especializado en paneles monocristalinos, bifaciales, inversores híbridos y baterías litio. "
            "Marcas: Runergy, JinkoSolar, Growatt, Pylontech."
        ),
        "categorias": [
            ("Paneles Mono",      "https://shop.solarity.lat/paneles_c10900626997397/mono_c10900626998498"),
            ("Paneles Bifacial",  "https://shop.solarity.lat/paneles_c10900626997397/bifacial_c10900626998462"),
            ("Inversores",        "https://shop.solarity.lat/inversores_c10900626997462/inversores_c10900626997816"),
            ("Inversores Híbridos","https://shop.solarity.lat/inversores_c10900626997462/inversores-hibridos_c10900626997645"),
            ("Baterías Litio",    "https://shop.solarity.lat/baterias_c10900626997740/lithium-batteries_c10900626998242"),
            ("Accesorios",        "https://shop.solarity.lat/accesorios_c10900626997690/accesorios_c10900626998196"),
        ],
        "contacto":    "Bogotá / Medellín — shop.solarity.lat",
        "moneda":      "COP / USD",
        "tipo":        "Mayorista · Distribución nacional",
        "marcas":      "Runergy · JinkoSolar · Growatt · Pylontech · Canadian Solar",
        "embed":       True,
    },
    {
        "id":          "autosolar",
        "nombre":      "AutoSolar Colombia",
        "pais":        "🇨🇴 Colombia",
        "ciudad":      "Bogotá / Nacional",
        "url":         "https://autosolar.co/",
        "logo_color":  "#F5A623",
        "descripcion": (
            "Empresa con trayectoria en distribución de material fotovoltaico en Colombia. "
            "Catálogo amplio: paneles, inversores, baterías, kits solares, estructuras y cableado. "
            "Cobertura nacional con asesoría e instalación profesional."
        ),
        "categorias": [
            ("Paneles Solares",   "https://autosolar.co/paneles-solares"),
            ("Inversores",        "https://autosolar.co/inversores-solares"),
            ("Baterías",          "https://autosolar.co/baterias-solares"),
            ("Kits Solares",      "https://autosolar.co/kits-solares"),
            ("Estructuras",       "https://autosolar.co/estructuras-solares"),
            ("Cableado y Acces.", "https://autosolar.co/material-electrico"),
        ],
        "contacto":    "Tel: 333 602 5140 · info@autosolar.co",
        "moneda":      "COP",
        "tipo":        "Distribuidor · Instalador certificado",
        "marcas":      "Canadian Solar · JA Solar · SMA · Victron · Pylontech · Growatt",
        "embed":       True,
    },
    {
        "id":          "solen",
        "nombre":      "Solen Technology",
        "pais":        "🇨🇴 Colombia",
        "ciudad":      "Bogotá · Cartagena · Barranquilla",
        "url":         "https://solentechnology.com/",
        "logo_color":  "#1565C0",
        "descripcion": (
            "Empresa de ingeniería con +10 años en proyectos de energía solar y eólica en Colombia. "
            "Importador directo de marcas tier-1. Proyectos residenciales, comerciales e industriales. "
            "Asesoría, diseño, instalación, mantenimiento y soporte."
        ),
        "categorias": [
            ("Paneles Solares",     "https://solentechnology.com/paneles-solares-colombia"),
            ("Inversores On/Off",   "https://solentechnology.com/inversores"),
            ("Baterías Ciclo Prof.","https://solentechnology.com/baterias"),
            ("Controladores MPPT",  "https://solentechnology.com/controladores"),
            ("Bombas Solares",      "https://solentechnology.com/bombas-solares"),
            ("Proyectos Industriales","https://solentechnology.com/parques-solares/"),
        ],
        "contacto":    "Bogotá, Cartagena, Barranquilla · solentechnology.com",
        "moneda":      "COP",
        "tipo":        "Integrador · Distribuidor · Ingeniería de proyectos",
        "marcas":      "JinkoSolar · Trina · Canadian Solar · SMA · Fronius · Victron · Morningstar",
        "embed":       True,
    },
    {
        "id":          "victron",
        "nombre":      "Victron Energy",
        "pais":        "🇳🇱 Países Bajos",
        "ciudad":      "Almere, Holanda (ventas globales)",
        "url":         "https://www.victronenergy.com/",
        "logo_color":  "#003087",
        "descripcion": (
            "Fabricante líder mundial de electrónica de potencia para sistemas de energía solar off-grid. "
            "Referencia mundial en inversores MultiPlus, controladores MPPT BlueSolar/SmartSolar, "
            "baterías LiFePO4 y sistemas de monitoreo VRM. Disponible en Colombia a través de distribuidores."
        ),
        "categorias": [
            ("Inversores / Cargadores", "https://www.victronenergy.com/inverters-chargers"),
            ("MPPT Controllers",         "https://www.victronenergy.com/solar-charge-controllers"),
            ("Baterías LiFePO4",         "https://www.victronenergy.com/batteries"),
            ("Monitores BMV",            "https://www.victronenergy.com/battery-monitors"),
            ("Accesorios SmartSolar",    "https://www.victronenergy.com/accessories"),
            ("VRM Portal (monitoreo)",   "https://vrm.victronenergy.com/"),
        ],
        "contacto":    "www.victronenergy.com · Distribuidor local: Solarity / AutoSolar",
        "moneda":      "EUR / USD",
        "tipo":        "Fabricante internacional · Tier 1",
        "marcas":      "Victron Energy (MultiPlus · Quattro · BlueSolar · SmartSolar · EasySolar)",
        "embed":       True,
    },
    {
        "id":          "solar_electric",
        "nombre":      "Solar Electric Supply (EE.UU.)",
        "pais":        "🇺🇸 Estados Unidos",
        "ciudad":      "Sebastopol, California",
        "url":         "https://www.solar-electric.com/",
        "logo_color":  "#D32F2F",
        "descripcion": (
            "Distribuidor estadounidense con +35 años de experiencia en sistemas FV off-grid y on-grid. "
            "Catálogo completo: paneles, inversores Outback/SMA/Fronius, baterías Trojan, "
            "controladores MidNite Solar y Morningstar. Referencia técnica para proyectos exigentes."
        ),
        "categorias": [
            ("Solar Panels",         "https://www.solar-electric.com/solar-panels.html"),
            ("Inverters & Chargers", "https://www.solar-electric.com/inverters-chargers.html"),
            ("Batteries",            "https://www.solar-electric.com/batteries.html"),
            ("Charge Controllers",   "https://www.solar-electric.com/solar-charge-controllers.html"),
            ("Mounting Systems",     "https://www.solar-electric.com/solar-panel-mounts.html"),
            ("Wiring & Protection",  "https://www.solar-electric.com/wiring-protection.html"),
        ],
        "contacto":    "1-800-914-4131 · sales@solar-electric.com",
        "moneda":      "USD",
        "tipo":        "Distribuidor especializado · Off-grid / On-grid",
        "marcas":      "Outback · SMA · Fronius · Trojan · MidNite Solar · Morningstar · LG",
        "embed":       True,
    },
]


def _iframe_html(url: str, height: int = 700) -> str:
    """Render a provider store in an iframe."""
    return f"""
    <div style='width:100%;border-radius:12px;overflow:hidden;
                border:1px solid #2A3A55;background:#0A0E1A;'>
        <div style='background:#0F1525;padding:0.5rem 1rem;font-size:0.75rem;
                    color:#8A9BBD;font-family:Share Tech Mono,monospace;
                    display:flex;align-items:center;gap:0.5rem;'>
            <span style='width:10px;height:10px;border-radius:50%;
                         background:#FF5252;display:inline-block;'></span>
            <span style='width:10px;height:10px;border-radius:50%;
                         background:#FFB300;display:inline-block;'></span>
            <span style='width:10px;height:10px;border-radius:50%;
                         background:#00E676;display:inline-block;'></span>
            <span style='margin-left:0.5rem;'>{url}</span>
        </div>
        <iframe src="{url}"
                width="100%" height="{height}"
                style="border:none;display:block;"
                loading="lazy"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups">
        </iframe>
    </div>"""


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_proveedores():
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0A0E1A,#1A2235);
                border:1px solid #2A3A55;border-radius:12px;
                padding:1.2rem 1.5rem;margin-bottom:1.5rem;'>
        <div style='font-family:Rajdhani,sans-serif;font-size:1.6rem;
                    font-weight:700;color:#FFB300;letter-spacing:2px;'>
            🏪 PROVEEDORES Y CONSULTA DE PRECIOS</div>
        <div style='color:#8A9BBD;font-size:0.8rem;letter-spacing:2px;margin-top:0.2rem;'>
            COLOMBIA · INTERNACIONAL · CATÁLOGOS EN LÍNEA</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.25);
                border-radius:8px;padding:0.7rem 1rem;font-size:0.82rem;
                color:#8A9BBD;margin-bottom:1.5rem;'>
        💡 Consulta precios actualizados directamente en la tienda del proveedor.
        Los precios varían según el tipo de cambio, stock y negociación por volumen.
        Se recomienda solicitar cotización formal antes de presupuestar un proyecto.
    </div>
    """, unsafe_allow_html=True)

    # ── Tarjetas de resumen ──────────────────────────────────────────────────
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
                color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        🗂 DIRECTORIO DE PROVEEDORES
    </div>""", unsafe_allow_html=True)

    # 3 Colombia + 2 Internacional en dos filas
    cols_co = st.columns(3)
    cols_int = st.columns(2)
    co_provs  = [p for p in PROVEEDORES if "Colombia" in p["pais"]]
    int_provs = [p for p in PROVEEDORES if "Colombia" not in p["pais"]]

    for i, prov in enumerate(co_provs):
        with cols_co[i]:
            st.markdown(f"""
            <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:12px;
                        padding:1.2rem;height:100%;'>
                <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;
                            font-weight:700;color:{prov["logo_color"]};margin-bottom:0.4rem;'>
                    {prov["pais"]} {prov["nombre"]}</div>
                <div style='font-size:0.75rem;color:#8A9BBD;margin-bottom:0.5rem;'>
                    📍 {prov["ciudad"]}</div>
                <div style='font-size:0.78rem;color:#E8EDF5;line-height:1.5;margin-bottom:0.6rem;'>
                    {prov["descripcion"]}</div>
                <div style='font-size:0.72rem;color:#8A9BBD;'>
                    <b style='color:#FFD54F;'>Marcas:</b> {prov["marcas"]}<br>
                    <b style='color:#FFD54F;'>Tipo:</b> {prov["tipo"]}<br>
                    <b style='color:#FFD54F;'>Moneda:</b> {prov["moneda"]}
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    for i, prov in enumerate(int_provs):
        with cols_int[i]:
            st.markdown(f"""
            <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:12px;
                        padding:1.2rem;height:100%;'>
                <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;
                            font-weight:700;color:{prov["logo_color"]};margin-bottom:0.4rem;'>
                    {prov["pais"]} {prov["nombre"]}</div>
                <div style='font-size:0.75rem;color:#8A9BBD;margin-bottom:0.5rem;'>
                    📍 {prov["ciudad"]}</div>
                <div style='font-size:0.78rem;color:#E8EDF5;line-height:1.5;margin-bottom:0.6rem;'>
                    {prov["descripcion"]}</div>
                <div style='font-size:0.72rem;color:#8A9BBD;'>
                    <b style='color:#FFD54F;'>Marcas:</b> {prov["marcas"]}<br>
                    <b style='color:#FFD54F;'>Tipo:</b> {prov["tipo"]}<br>
                    <b style='color:#FFD54F;'>Moneda:</b> {prov["moneda"]}
                </div>
            </div>""", unsafe_allow_html=True)

    # ── Tabs por proveedor ───────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:2rem 0 1rem;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
                color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        🛒 ACCESO A TIENDAS EN LÍNEA
    </div>""", unsafe_allow_html=True)

    tab_labels = [f"{p['pais'].split()[0]} {p['nombre']}" for p in PROVEEDORES]
    tabs = st.tabs(tab_labels)

    for tab, prov in zip(tabs, PROVEEDORES):
        with tab:
            # Header del proveedor
            st.markdown(f"""
            <div style='background:#0F1525;border:1px solid {prov["logo_color"]}33;
                        border-radius:10px;padding:1rem 1.2rem;margin-bottom:1rem;
                        display:flex;justify-content:space-between;align-items:flex-start;
                        flex-wrap:wrap;gap:1rem;'>
                <div>
                    <div style='font-family:Rajdhani,sans-serif;font-size:1.2rem;
                                font-weight:700;color:{prov["logo_color"]};'>
                        {prov["pais"]}  {prov["nombre"]}</div>
                    <div style='font-size:0.78rem;color:#8A9BBD;margin-top:0.3rem;'>
                        {prov["contacto"]}</div>
                    <div style='font-size:0.75rem;color:#2A3A55;margin-top:0.2rem;'>
                        {prov["tipo"]}  ·  Moneda: {prov["moneda"]}</div>
                </div>
                <a href="{prov["url"]}" target="_blank"
                   style='background:{prov["logo_color"]};color:#0A0E1A;
                          padding:0.5rem 1.2rem;border-radius:6px;
                          font-family:Rajdhani,sans-serif;font-weight:700;
                          font-size:0.9rem;text-decoration:none;letter-spacing:1px;'>
                    🔗 Abrir en nueva pestaña ↗
                </a>
            </div>
            """, unsafe_allow_html=True)

            # Accesos directos por categoría
            st.markdown(f"""
            <div style='font-size:0.78rem;color:#8A9BBD;margin-bottom:0.6rem;'>
                🗂 Acceso rápido por categoría:
            </div>""", unsafe_allow_html=True)

            cat_cols = st.columns(min(len(prov["categorias"]), 3))
            for ci, (cat_name, cat_url) in enumerate(prov["categorias"]):
                with cat_cols[ci % 3]:
                    st.markdown(f"""
                    <a href="{cat_url}" target="_blank"
                       style='display:block;background:#1E2A3F;
                              border:1px solid #2A3A55;border-radius:6px;
                              padding:0.5rem 0.8rem;margin-bottom:0.4rem;
                              color:#E8EDF5;text-decoration:none;font-size:0.78rem;
                              transition:border-color 0.2s;'>
                        📂 {cat_name}
                    </a>""", unsafe_allow_html=True)

            # Iframe o nota de acceso
            st.markdown("<br>", unsafe_allow_html=True)

            iframe_h = st.slider(f"Altura del visor (px)",
                                  400, 900, 620,
                                  key=f"h_{prov['id']}")

            st.markdown(f"""
            <div style='font-size:0.75rem;color:#8A9BBD;margin-bottom:0.5rem;'>
                ⚠ Si la tienda no carga en el visor integrado (política CORS del proveedor),
                usa el botón <b style='color:{prov["logo_color"]};'>Abrir en nueva pestaña ↗</b> arriba.
            </div>""", unsafe_allow_html=True)

            st.markdown(_iframe_html(prov["url"], iframe_h), unsafe_allow_html=True)

    # ── Tabla comparativa de proveedores ─────────────────────────────────────
    st.markdown("<hr style='border-color:#2A3A55;margin:2rem 0 1rem;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-family:Rajdhani,sans-serif;font-size:1.1rem;font-weight:700;
                color:#FFB300;letter-spacing:1px;margin-bottom:1rem;'>
        📊 TABLA COMPARATIVA DE PROVEEDORES
    </div>""", unsafe_allow_html=True)

    comp_data = {
        "Proveedor":     [p["nombre"]          for p in PROVEEDORES],
        "País":          [p["pais"]             for p in PROVEEDORES],
        "Tipo":          [p["tipo"]             for p in PROVEEDORES],
        "Moneda":        [p["moneda"]           for p in PROVEEDORES],
        "Principales marcas": [p["marcas"][:50]+"…" if len(p["marcas"])>50 else p["marcas"]
                               for p in PROVEEDORES],
        "URL":           [p["url"]              for p in PROVEEDORES],
    }
    import pandas as pd
    df_comp = pd.DataFrame(comp_data)
    st.dataframe(df_comp.set_index("Proveedor"), use_container_width=True)

    # ── Notas de uso ──────────────────────────────────────────────────────────
    st.markdown("""
    <hr style='border-color:#2A3A55;'>
    <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:10px;
                padding:1rem 1.2rem;font-size:0.8rem;color:#8A9BBD;line-height:1.8;'>
        <b style='color:#FFB300;font-family:Rajdhani,sans-serif;'>📌 NOTAS IMPORTANTES</b><br>
        • Los precios en las tiendas están sujetos a cambios sin previo aviso. Siempre solicite cotización formal.<br>
        • Para compras mayores a 10 paneles o kits completos, contacte directamente al área comercial del proveedor.<br>
        • Verifique que los equipos cumplan con certificaciones NTC, IEC 61215, IEC 61730 y RETIE vigente.<br>
        • Los proveedores internacionales pueden tener tiempos de entrega de 4–12 semanas y costos de importación adicionales.<br>
        • Victron Energy se consigue en Colombia a través de Solarity, AutoSolar y distribuidores autorizados locales.<br>
        • Para proyectos mayores a 10 kWp se recomienda solicitar propuestas a mínimo 3 proveedores.
    </div>
    """, unsafe_allow_html=True)
