# ══════════════════════════════════════════════════════════════════════════
# MÓDULO DE SITIO Y MONTAJE — SolarCalc Pro
# ------------------------------------------------------------------------
# Permite:
#   1) Subir fotografías reales del lugar donde se instalarán los paneles
#      (techo, cubierta, terreno) para un proyecto ya creado.
#   2) Definir el área utilizable y los obstáculos (chimeneas, tanques,
#      sombras, árboles, etc.) sobre la foto, con una escala real en metros.
#   3) Calcular automáticamente la disposición más óptima (mayor número de
#      paneles, en la orientación que mejor aprovecha el área) de los
#      paneles ya dimensionados en el proyecto (Módulos 5/6/9).
#   4) Opcionalmente, usar IA (Claude con visión) para que identifique el
#      área utilizable, los obstáculos y la orientación/inclinación
#      recomendadas directamente a partir de la fotografía.
#   5) Dibujar el plano de montaje superpuesto sobre la fotografía real.
#
# Requiere únicamente Pillow (ya usada por Streamlit). El análisis con IA es
# opcional y requiere adicionalmente:  pip install anthropic
# y la variable de entorno ANTHROPIC_API_KEY configurada.
# ══════════════════════════════════════════════════════════════════════════

import base64
import io
import json
import os
import sqlite3
from datetime import datetime

import streamlit as st
from PIL import Image


# ─── CONEXIÓN A LA MISMA BASE DE DATOS QUE solar_app.py ─────────────────────
def _get_conn():
    db_path = os.environ.get("SOLARCALC_DB_PATH", "solarcalc.db")
    return sqlite3.connect(db_path, check_same_thread=False)


def init_sitio_db():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sitio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            nombre TEXT,
            media_type TEXT DEFAULT 'image/jpeg',
            imagen BLOB NOT NULL,
            ancho_px INTEGER,
            alto_px INTEGER,
            ancho_real_m REAL DEFAULT 10.0,
            alto_real_m REAL DEFAULT 8.0,
            area_x REAL DEFAULT 5.0,
            area_y REAL DEFAULT 5.0,
            area_w REAL DEFAULT 90.0,
            area_h REAL DEFAULT 90.0,
            obstaculos TEXT DEFAULT '[]',
            orientacion TEXT DEFAULT 'Sur',
            inclinacion REAL DEFAULT 10.0,
            notas TEXT,
            creado TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sitio_disposicion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            foto_id INTEGER NOT NULL,
            proyecto_id INTEGER NOT NULL,
            ancho_panel_m REAL,
            alto_panel_m REAL,
            separacion_m REAL,
            orientacion_panel TEXT,
            n_requeridos INTEGER,
            n_ubicados INTEGER,
            filas INTEGER,
            columnas INTEGER,
            metodo TEXT,
            analisis_ia TEXT,
            creado TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(foto_id) REFERENCES sitio_fotos(id)
        )
    """)
    conn.commit()
    conn.close()


# ─── CRUD DE FOTOS ───────────────────────────────────────────────────────────
def guardar_foto(proyecto_id, nombre, imagen_bytes, media_type, ancho_px, alto_px, notas=""):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sitio_fotos(proyecto_id,nombre,media_type,imagen,ancho_px,alto_px,notas) "
        "VALUES (?,?,?,?,?,?,?)",
        (proyecto_id, nombre, media_type, sqlite3.Binary(imagen_bytes), ancho_px, alto_px, notas))
    conn.commit()
    conn.close()


def listar_fotos(proyecto_id):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id,nombre,media_type,ancho_px,alto_px,ancho_real_m,alto_real_m,"
        "area_x,area_y,area_w,area_h,obstaculos,orientacion,inclinacion,notas,creado "
        "FROM sitio_fotos WHERE proyecto_id=? ORDER BY id DESC", (proyecto_id,)).fetchall()
    conn.close()
    cols = ["id", "nombre", "media_type", "ancho_px", "alto_px", "ancho_real_m", "alto_real_m",
            "area_x", "area_y", "area_w", "area_h", "obstaculos", "orientacion",
            "inclinacion", "notas", "creado"]
    return [dict(zip(cols, r)) for r in rows]


def obtener_imagen(foto_id):
    conn = _get_conn()
    row = conn.execute("SELECT imagen, media_type FROM sitio_fotos WHERE id=?", (foto_id,)).fetchone()
    conn.close()
    if not row:
        return None, None
    return bytes(row[0]), row[1]


def actualizar_config_foto(foto_id, **campos):
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    conn = _get_conn()
    conn.execute(f"UPDATE sitio_fotos SET {sets} WHERE id=?", (*campos.values(), foto_id))
    conn.commit()
    conn.close()


def eliminar_foto(foto_id):
    conn = _get_conn()
    conn.execute("DELETE FROM sitio_disposicion WHERE foto_id=?", (foto_id,))
    conn.execute("DELETE FROM sitio_fotos WHERE id=?", (foto_id,))
    conn.commit()
    conn.close()


def guardar_disposicion(foto_id, proyecto_id, ancho_panel_m, alto_panel_m, separacion_m,
                         orientacion_panel, n_requeridos, n_ubicados, filas, columnas,
                         metodo="manual", analisis_ia=None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sitio_disposicion(foto_id,proyecto_id,ancho_panel_m,alto_panel_m,"
        "separacion_m,orientacion_panel,n_requeridos,n_ubicados,filas,columnas,metodo,analisis_ia) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (foto_id, proyecto_id, ancho_panel_m, alto_panel_m, separacion_m, orientacion_panel,
         n_requeridos, n_ubicados, filas, columnas, metodo,
         json.dumps(analisis_ia, ensure_ascii=False) if analisis_ia else None))
    conn.commit()
    conn.close()


# ─── ALGORITMO DE DISPOSICIÓN ÓPTIMA (empaquetado en rejilla) ──────────────
def _rect_choca(rect, obstaculos, holgura=0.0):
    rx, ry, rw, rh = rect
    rx -= holgura; ry -= holgura; rw += 2 * holgura; rh += 2 * holgura
    for (ox, oy, ow, oh) in obstaculos:
        if rx < ox + ow and rx + rw > ox and ry < oy + oh and ry + rh > oy:
            return True
    return False


def calcular_disposicion_optima(ancho_area_m, alto_area_m, ancho_panel_m, alto_panel_m,
                                 n_requeridos, separacion_m=0.03, margen_m=0.15,
                                 obstaculos_m=None, permitir_rotacion=True):
    """
    Ubica en rejilla el mayor número posible de paneles (hasta n_requeridos)
    dentro del área utilizable (ancho_area_m x alto_area_m, origen en la
    esquina superior izquierda), evitando los obstáculos indicados
    (lista de tuplas (x,y,w,h) en metros, mismo sistema de referencia).
    Prueba orientación horizontal y vertical del panel y se queda con la que
    ubique más unidades. Devuelve un diccionario con los paneles colocados.
    """
    obstaculos_m = obstaculos_m or []
    n_requeridos = max(0, int(n_requeridos))

    def _intenta(o_w, o_h, etiqueta):
        usable_w = max(0.0, ancho_area_m - 2 * margen_m)
        usable_h = max(0.0, alto_area_m - 2 * margen_m)
        if o_w <= 0 or o_h <= 0:
            return [], 0, 0, etiqueta
        cols = int((usable_w + separacion_m) // (o_w + separacion_m)) if usable_w > 0 else 0
        filas = int((usable_h + separacion_m) // (o_h + separacion_m)) if usable_h > 0 else 0
        colocados = []
        for fi in range(max(filas, 0)):
            for ci in range(max(cols, 0)):
                if len(colocados) >= n_requeridos:
                    break
                x = margen_m + ci * (o_w + separacion_m)
                y = margen_m + fi * (o_h + separacion_m)
                rect = (x, y, o_w, o_h)
                if _rect_choca(rect, obstaculos_m):
                    continue
                colocados.append(rect)
            if len(colocados) >= n_requeridos:
                break
        return colocados, filas, cols, etiqueta

    opciones = [_intenta(ancho_panel_m, alto_panel_m, "horizontal")]
    if permitir_rotacion:
        opciones.append(_intenta(alto_panel_m, ancho_panel_m, "vertical"))

    colocados, filas, cols, orientacion = max(opciones, key=lambda o: len(o[0]))

    return {
        "paneles": colocados,          # lista de (x,y,w,h) en metros, relativos al área
        "filas": filas,
        "columnas": cols,
        "orientacion_panel": orientacion,
        "n_ubicados": len(colocados),
        "n_requeridos": n_requeridos,
        "completo": len(colocados) >= n_requeridos,
        "area_usada_m2": sum(w * h for (_, _, w, h) in colocados),
    }


# ─── ANÁLISIS OPCIONAL CON IA (Claude — visión) ────────────────────────────
def analizar_sitio_ia(imagen_bytes: bytes, media_type: str, contexto: dict) -> dict:
    """
    Envía la fotografía del sitio a Claude (modelo con visión) para que
    identifique automáticamente el área utilizable, los obstáculos visibles
    y recomiende orientación/inclinación. Requiere el paquete `anthropic`
    (`pip install anthropic`) y la variable de entorno ANTHROPIC_API_KEY.
    Lanza RuntimeError con un mensaje claro si no está disponible, para que
    la interfaz pueda ofrecer el modo manual sin romperse.
    """
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "El paquete 'anthropic' no está instalado. Ejecuta: pip install anthropic"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No se encontró la variable de entorno ANTHROPIC_API_KEY. "
            "Configúrala para habilitar el análisis automático con IA."
        )

    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.b64encode(imagen_bytes).decode("utf-8")

    prompt = f"""Eres un ingeniero especializado en diseño de instalaciones fotovoltaicas.
Analiza la fotografía adjunta del sitio donde se instalarán paneles solares.

Contexto del proyecto:
- Dimensiones reales aproximadas del área visible en la foto: {contexto.get('ancho_real_m')} m (ancho) x {contexto.get('alto_real_m')} m (alto)
- Número de paneles a ubicar: {contexto.get('n_paneles')}
- Dimensiones de cada panel: {contexto.get('ancho_panel_m')} m x {contexto.get('alto_panel_m')} m
- Ubicación del proyecto: {contexto.get('municipio', 'Colombia')}

Tareas:
1. Identifica el área utilizable para instalar paneles (techo o terreno libre de sombras
   y obstrucciones) como UN rectángulo en PORCENTAJE de la imagen (origen 0,0 en la
   esquina superior izquierda; x,y = esquina superior izquierda del rectángulo; w,h = ancho y alto).
2. Identifica hasta 5 obstáculos visibles (chimeneas, tanques, tragaluces, antenas,
   árboles, sombras proyectadas, cumbreras, cambios de pendiente) como rectángulos en porcentaje.
3. Recomienda orientación (Norte/Sur/Este/Oeste) e inclinación en grados más adecuada
   según lo observado (pendiente del techo, sombras, latitud aproximada de Colombia).
4. Da una observación técnica breve (máximo 2 líneas) sobre viabilidad y riesgos.

Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni backticks, con este formato exacto:
{{"area_util": {{"x":0,"y":0,"w":0,"h":0}}, "obstaculos": [{{"x":0,"y":0,"w":0,"h":0,"tipo":"chimenea"}}], "orientacion_recomendada": "Sur", "inclinacion_recomendada_grados": 10, "observacion": "..."}}"""

    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )

    texto = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    limpio = texto.strip().strip("`")
    if limpio.lower().startswith("json"):
        limpio = limpio[4:].strip()
    try:
        data = json.loads(limpio)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"La IA no devolvió un JSON válido ({e}). Respuesta: {texto[:400]}")

    # Saneo básico de rangos 0-100
    def _clamp(v):
        try:
            return max(0.0, min(100.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    au = data.get("area_util", {}) or {}
    data["area_util"] = {k: _clamp(au.get(k, 0)) for k in ("x", "y", "w", "h")}
    obs = []
    for o in (data.get("obstaculos") or [])[:5]:
        obs.append({
            "x": _clamp(o.get("x", 0)), "y": _clamp(o.get("y", 0)),
            "w": _clamp(o.get("w", 0)), "h": _clamp(o.get("h", 0)),
            "tipo": str(o.get("tipo", "obstáculo"))[:40],
        })
    data["obstaculos"] = obs
    return data


# ─── SVG: PLANO DE MONTAJE SUPERPUESTO SOBRE LA FOTO REAL ──────────────────
def generar_svg_plano_sitio(imagen_bytes, media_type, ancho_real_m, alto_real_m,
                             area_pct, obstaculos_pct, disposicion,
                             titulo="PLANO DE MONTAJE SOBRE FOTOGRAFÍA DEL SITIO"):
    """
    area_pct: dict {x,y,w,h} en % de la imagen (0-100), área utilizable.
    obstaculos_pct: lista de dicts {x,y,w,h,tipo} en % de la imagen.
    disposicion: salida de calcular_disposicion_optima() (paneles en metros
                 relativos al origen del área utilizable).
    Devuelve un string SVG (viewBox 0 0 1000 1000·k) con la foto como fondo.
    """
    b64 = base64.b64encode(imagen_bytes).decode("utf-8")
    ratio = (alto_real_m / ancho_real_m) if ancho_real_m else 0.75
    VB_W, VB_H = 1000, max(300, round(1000 * ratio))

    def pct_to_px(x_pct, y_pct, w_pct=0.0, h_pct=0.0):
        return (x_pct / 100 * VB_W, y_pct / 100 * VB_H, w_pct / 100 * VB_W, h_pct / 100 * VB_H)

    ax, ay, aw, ah = pct_to_px(area_pct["x"], area_pct["y"], area_pct["w"], area_pct["h"])

    obst_svg = []
    for o in obstaculos_pct:
        ox, oy, ow, oh = pct_to_px(o["x"], o["y"], o["w"], o["h"])
        obst_svg.append(f"""
            <rect x="{ox:.1f}" y="{oy:.1f}" width="{ow:.1f}" height="{oh:.1f}"
                  fill="url(#hatch)" stroke="#FF5252" stroke-width="2" stroke-dasharray="6,4" rx="4"/>
            <text x="{ox+4:.1f}" y="{oy+16:.1f}" font-size="13" fill="#FF5252"
                  font-family="Rajdhani,sans-serif" font-weight="700">{o.get('tipo','obstáculo')}</text>""")

    panel_svg = []
    for i, (pxm, pym, pwm, phm) in enumerate(disposicion.get("paneles", [])):
        px_pct = (area_pct["x"] + (pxm / ancho_real_m) * area_pct["w"]) if ancho_real_m else 0
        py_pct = (area_pct["y"] + (pym / alto_real_m) * area_pct["h"]) if alto_real_m else 0
        pw_pct = (pwm / ancho_real_m) * area_pct["w"] if ancho_real_m else 0
        ph_pct = (phm / alto_real_m) * area_pct["h"] if alto_real_m else 0
        px, py, pw, ph = pct_to_px(px_pct, py_pct, pw_pct, ph_pct)
        panel_svg.append(f"""
            <rect x="{px:.1f}" y="{py:.1f}" width="{max(pw-2,1):.1f}" height="{max(ph-2,1):.1f}"
                  fill="url(#panelGrad)" stroke="#0A0E1A" stroke-width="1.5" rx="2"/>""")

    n_ubic = disposicion.get("n_ubicados", 0)
    n_req  = disposicion.get("n_requeridos", 0)
    color_estado = "#00E676" if disposicion.get("completo") else "#FFB300"

    svg = f"""<svg viewBox="0 0 {VB_W} {VB_H+90}" xmlns="http://www.w3.org/2000/svg"
                    font-family="Barlow,sans-serif">
  <defs>
    <pattern id="hatch" width="8" height="8" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="rgba(255,82,82,0.12)"/>
      <line x1="0" y1="0" x2="0" y2="8" stroke="#FF5252" stroke-width="1.5"/>
    </pattern>
    <linearGradient id="panelGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1565C0"/>
      <stop offset="55%" stop-color="#0D47A1"/>
      <stop offset="100%" stop-color="#0A2E5C"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="{VB_W}" height="{VB_H+90}" fill="#0A0E1A"/>
  <image href="data:{media_type};base64,{b64}" x="0" y="0" width="{VB_W}" height="{VB_H}"
         preserveAspectRatio="none"/>

  <!-- Área utilizable -->
  <rect x="{ax:.1f}" y="{ay:.1f}" width="{aw:.1f}" height="{ah:.1f}"
        fill="none" stroke="#FFB300" stroke-width="3" stroke-dasharray="10,5" rx="6"/>
  <text x="{ax+6:.1f}" y="{ay+20:.1f}" font-size="14" fill="#FFB300" font-weight="700">ÁREA UTILIZABLE</text>

  {''.join(obst_svg)}
  {''.join(panel_svg)}

  <!-- Pie de plano -->
  <rect x="0" y="{VB_H}" width="{VB_W}" height="90" fill="#0F1525" stroke="#2A3A55"/>
  <text x="20" y="{VB_H+28}" font-size="20" fill="#FFB300" font-weight="700"
        font-family="Rajdhani,sans-serif">{titulo}</text>
  <text x="20" y="{VB_H+58}" font-size="15" fill="#E8EDF5">
    Paneles ubicados: <tspan fill="{color_estado}" font-weight="700">{n_ubic} / {n_req}</tspan>
  </text>
  <text x="20" y="{VB_H+80}" font-size="13" fill="#8A9BBD">
    Disposición: {disposicion.get('filas',0)} filas × {disposicion.get('columnas',0)} columnas
    ({disposicion.get('orientacion_panel','—')}) · Área utilizada: {disposicion.get('area_usada_m2',0):.1f} m²
  </text>
</svg>"""
    return svg


# ─── INTERFAZ STREAMLIT ─────────────────────────────────────────────────────
def _mostrar_imagen(imagen_bytes, caption=None):
    """
    st.image() con compatibilidad entre versiones de Streamlit: las versiones
    nuevas usan `use_container_width`, las versiones antiguas (como la de
    este entorno) usan `use_column_width`. Se intenta con la nueva y, si no
    existe ese parámetro, se cae a la antigua.
    """
    try:
        st.image(imagen_bytes, use_container_width=True, caption=caption)
    except TypeError:
        st.image(imagen_bytes, use_column_width=True, caption=caption)


def _render_svg_fallback(svg_string: str, height: int = 650) -> None:
    b64 = base64.b64encode(svg_string.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<div style="width:100%; border-radius:12px; overflow:hidden;">'
        f'<img src="data:image/svg+xml;base64,{b64}" '
        f'style="width:100%; height:{height}px; object-fit:contain; '
        f'background:#0A0E1A; border-radius:12px;" alt="Plano del Sitio"/>'
        f'</div>', unsafe_allow_html=True)


def mostrar_sitio(proyecto_id, session_state, render_svg_fn=None):
    """
    Dibuja la pestaña completa del módulo. Devuelve el último SVG generado
    (str) o None, para que solar_app.py pueda incluirlo en el informe
    completo consolidado (igual que hace con svg_code / svg10).

    render_svg_fn: función opcional (svg_string, height) -> None para
    reutilizar el renderizador de SVG ya definido en solar_app.py
    (evita necesitar una dependencia circular entre módulos).
    """
    render_svg_fn = render_svg_fn or _render_svg_fallback
    st.markdown("""
    <div class='sol-card-title'><span class='step-badge'>13</span>
    SITIO Y MONTAJE — FOTOGRAFÍA REAL DEL LUGAR</div>
    <div class='info-note'>
        Sube fotos del techo, cubierta o terreno donde se instalarán los paneles,
        define el área utilizable y los obstáculos, y calcula automáticamente
        (manualmente o con ayuda de IA) la disposición que ubica el mayor
        número de paneles ya dimensionados en el proyecto.
    </div>
    """, unsafe_allow_html=True)

    # ── 1· Subir nueva foto ──────────────────────────────────────────────
    with st.expander("📤 Subir nueva fotografía del sitio", expanded=False):
        up_nombre = st.text_input("Nombre / ubicación de la foto (ej. 'Techo lado sur')",
                                   key="st13_up_nombre")
        up_notas  = st.text_area("Notas (opcional)", key="st13_up_notas", height=68)
        up_file   = st.file_uploader("Imagen (JPG, PNG)", type=["jpg", "jpeg", "png"],
                                      key="st13_up_file")
        if up_file is not None and st.button("💾 Guardar fotografía", key="st13_btn_guardar_foto"):
            try:
                img_bytes = up_file.read()
                img = Image.open(io.BytesIO(img_bytes))
                w_px, h_px = img.size
                media_type = up_file.type or "image/jpeg"
                guardar_foto(proyecto_id, up_nombre or up_file.name, img_bytes,
                             media_type, w_px, h_px, up_notas)
                st.success("✅ Fotografía guardada. Selecciónala abajo para configurarla.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo leer la imagen: {e}")

    fotos = listar_fotos(proyecto_id)
    if not fotos:
        st.markdown("<div class='warn-box'>⚠ Aún no hay fotografías del sitio para este "
                     "proyecto. Sube una foto arriba para comenzar.</div>", unsafe_allow_html=True)
        return None

    # ── 2· Selección de foto ─────────────────────────────────────────────
    opciones = {f"#{f['id']} · {f['nombre'] or 'Sin nombre'} ({f['creado'][:16]})": f for f in fotos}
    sel_label = st.selectbox("📷 Fotografía del sitio a configurar:", list(opciones.keys()),
                              key="st13_sel_foto")
    foto = opciones[sel_label]
    imagen_bytes, media_type = obtener_imagen(foto["id"])

    col_img, col_del = st.columns([5, 1])
    with col_img:
        _mostrar_imagen(imagen_bytes,
                        caption=f"{foto['nombre']} — {foto['ancho_px']}×{foto['alto_px']} px")
    with col_del:
        if st.button("🗑 Eliminar", key=f"st13_del_{foto['id']}", use_container_width=True):
            eliminar_foto(foto["id"])
            st.success("Fotografía eliminada.")
            st.rerun()

    # ── 3· Escala real y área utilizable ─────────────────────────────────
    st.markdown("<div class='sol-card-title' style='font-size:1.05rem;'>📏 Escala real y área utilizable</div>",
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    ancho_real_m = c1.number_input("Ancho real que cubre la foto (m)", min_value=1.0, max_value=200.0,
                                    value=float(foto["ancho_real_m"]), step=0.5, key=f"st13_aw_{foto['id']}")
    alto_real_m  = c2.number_input("Alto real que cubre la foto (m)", min_value=1.0, max_value=200.0,
                                    value=float(foto["alto_real_m"]), step=0.5, key=f"st13_ah_{foto['id']}")
    st.caption("💡 Tip: mide o estima el ancho/alto reales de lo que se ve en la foto "
               "(ej. el ancho del techo). El plano se ajusta a esa escala.")

    ax_c, ay_c, aw_c, ah_c = st.columns(4)
    area_x = ax_c.slider("Área — X inicial (%)", 0, 100, int(foto["area_x"]), key=f"st13_ax_{foto['id']}")
    area_y = ay_c.slider("Área — Y inicial (%)", 0, 100, int(foto["area_y"]), key=f"st13_ay_{foto['id']}")
    area_w = aw_c.slider("Área — Ancho (%)", 1, 100, int(foto["area_w"]), key=f"st13_awp_{foto['id']}")
    area_h = ah_c.slider("Área — Alto (%)", 1, 100, int(foto["area_h"]), key=f"st13_ahp_{foto['id']}")
    area_pct = {"x": area_x, "y": area_y, "w": area_w, "h": area_h}

    # ── 4· Obstáculos ─────────────────────────────────────────────────────
    obst_guardados = json.loads(foto["obstaculos"] or "[]")
    obstaculos_pct = []
    with st.expander("🚧 Obstáculos (chimeneas, tanques, sombras, antenas...)", expanded=bool(obst_guardados)):
        n_obst = st.number_input("Número de obstáculos a definir", 0, 5,
                                  value=len(obst_guardados), key=f"st13_nobst_{foto['id']}")
        for i in range(int(n_obst)):
            base = obst_guardados[i] if i < len(obst_guardados) else {"x": 10, "y": 10, "w": 10, "h": 10, "tipo": "obstáculo"}
            st.markdown(f"**Obstáculo {i+1}**")
            oc1, oc2, oc3, oc4, oc5 = st.columns([1, 1, 1, 1, 1.4])
            ox = oc1.slider(f"X% #{i+1}", 0, 100, int(base.get("x", 10)), key=f"st13_ox_{foto['id']}_{i}")
            oy = oc2.slider(f"Y% #{i+1}", 0, 100, int(base.get("y", 10)), key=f"st13_oy_{foto['id']}_{i}")
            ow = oc3.slider(f"Ancho% #{i+1}", 1, 100, int(base.get("w", 10)), key=f"st13_ow_{foto['id']}_{i}")
            oh = oc4.slider(f"Alto% #{i+1}", 1, 100, int(base.get("h", 10)), key=f"st13_oh_{foto['id']}_{i}")
            otipo = oc5.text_input(f"Tipo #{i+1}", value=base.get("tipo", "obstáculo"), key=f"st13_ot_{foto['id']}_{i}")
            obstaculos_pct.append({"x": ox, "y": oy, "w": ow, "h": oh, "tipo": otipo})

    # ── 5· Análisis opcional con IA ──────────────────────────────────────
    st.markdown("<div class='sol-card-title' style='font-size:1.05rem;'>🤖 Análisis automático con IA (opcional)</div>",
                unsafe_allow_html=True)
    st.caption("Usa Claude (visión) para detectar el área utilizable, los obstáculos y la "
               "orientación/inclinación recomendadas directamente desde la fotografía. "
               "Requiere `pip install anthropic` y la variable de entorno `ANTHROPIC_API_KEY`.")
    n_paneles_sugerido = int(session_state.get("calc_num_paneles", 10) or 10)
    if st.button("🤖 Analizar sitio con IA", key=f"st13_ia_{foto['id']}"):
        with st.spinner("Analizando la fotografía con IA..."):
            try:
                contexto = {
                    "ancho_real_m": ancho_real_m, "alto_real_m": alto_real_m,
                    "n_paneles": n_paneles_sugerido,
                    "ancho_panel_m": session_state.get("st13_ancho_panel_m", 1.13),
                    "alto_panel_m": session_state.get("st13_alto_panel_m", 2.28),
                    "municipio": session_state.get("proyecto_municipio", "Colombia"),
                }
                resultado_ia = analizar_sitio_ia(imagen_bytes, media_type, contexto)
                session_state["st13_ia_resultado"] = resultado_ia
                st.success(
                    f"✅ IA: orientación recomendada **{resultado_ia.get('orientacion_recomendada','—')}**, "
                    f"inclinación **{resultado_ia.get('inclinacion_recomendada_grados','—')}°**. "
                    f"{resultado_ia.get('observacion','')}")
            except RuntimeError as e:
                st.warning(f"⚠ No se pudo usar la IA ({e}). Puedes continuar en modo manual con "
                           f"los controles de arriba.")
            except Exception as e:
                st.error(f"Error inesperado al consultar la IA: {e}")

    if session_state.get("st13_ia_resultado"):
        res_ia = session_state["st13_ia_resultado"]
        if st.button("↩ Aplicar sugerencia de la IA al área/obstáculos", key=f"st13_apply_ia_{foto['id']}"):
            au = res_ia.get("area_util", {})
            actualizar_config_foto(
                foto["id"], area_x=au.get("x", area_x), area_y=au.get("y", area_y),
                area_w=au.get("w", area_w) or 1, area_h=au.get("h", area_h) or 1,
                orientacion=res_ia.get("orientacion_recomendada", "Sur"),
                inclinacion=res_ia.get("inclinacion_recomendada_grados", 10),
                obstaculos=json.dumps(res_ia.get("obstaculos", []), ensure_ascii=False))
            st.success("Sugerencia de la IA aplicada. Ajusta si lo necesitas y recalcula.")
            st.rerun()

    # ── 6· Datos del panel y cálculo ─────────────────────────────────────
    st.markdown("<div class='sol-card-title' style='font-size:1.05rem;'>🔆 Panel y cálculo de disposición</div>",
                unsafe_allow_html=True)
    p1, p2, p3, p4 = st.columns(4)
    ancho_panel_m = p1.number_input("Ancho panel (m)", 0.3, 3.0, 1.13, 0.01, key="st13_ancho_panel_m")
    alto_panel_m  = p2.number_input("Alto panel (m)", 0.3, 3.0, 2.28, 0.01, key="st13_alto_panel_m")
    separacion_m  = p3.number_input("Separación entre paneles (m)", 0.0, 1.0, 0.03, 0.01, key="st13_sep_m")
    margen_m      = p4.number_input("Margen al borde del área (m)", 0.0, 3.0, 0.15, 0.05, key="st13_margen_m")

    p5, p6 = st.columns(2)
    n_requeridos = p5.number_input("Paneles a ubicar (según dimensionamiento del proyecto)",
                                    1, 2000, n_paneles_sugerido, key="st13_n_req")
    permitir_rot = p6.checkbox("Permitir rotar el panel (horizontal/vertical) para optimizar", value=True,
                                key="st13_rot")

    orientaciones = ["Sur", "Norte", "Este", "Oeste"]
    idx_or = orientaciones.index(foto["orientacion"]) if foto["orientacion"] in orientaciones else 0
    o1, o2 = st.columns(2)
    orientacion_sel = o1.selectbox("Orientación de instalación", orientaciones, index=idx_or, key=f"st13_orsel_{foto['id']}")
    inclinacion_sel = o2.slider("Inclinación de los paneles (°)", 0, 45, int(foto["inclinacion"]), key=f"st13_incl_{foto['id']}")

    svg_resultado = None
    if st.button("📐 Calcular disposición óptima", type="primary", key=f"st13_calc_{foto['id']}",
                 use_container_width=True):
        # Área utilizable y obstáculos en metros, relativos al origen del área
        ancho_area_m = ancho_real_m * area_w / 100
        alto_area_m  = alto_real_m * area_h / 100
        obst_m = []
        for o in obstaculos_pct:
            # Convertir de % de la imagen completa a metros relativos al área utilizable
            ox_img_m = o["x"] / 100 * ancho_real_m
            oy_img_m = o["y"] / 100 * alto_real_m
            ow_m = o["w"] / 100 * ancho_real_m
            oh_m = o["h"] / 100 * alto_real_m
            area_x_m = area_x / 100 * ancho_real_m
            area_y_m = area_y / 100 * alto_real_m
            obst_m.append((ox_img_m - area_x_m, oy_img_m - area_y_m, ow_m, oh_m))

        disposicion = calcular_disposicion_optima(
            ancho_area_m, alto_area_m, ancho_panel_m, alto_panel_m,
            n_requeridos, separacion_m, margen_m, obst_m, permitir_rot)

        svg_resultado = generar_svg_plano_sitio(
            imagen_bytes, media_type, ancho_real_m, alto_real_m,
            area_pct, obstaculos_pct, disposicion)
        session_state["st13_ultimo_svg"] = svg_resultado
        session_state["st13_ultima_disposicion"] = disposicion

        # Persistir configuración y resultado
        actualizar_config_foto(
            foto["id"], ancho_real_m=ancho_real_m, alto_real_m=alto_real_m,
            area_x=area_x, area_y=area_y, area_w=area_w, area_h=area_h,
            obstaculos=json.dumps(obstaculos_pct, ensure_ascii=False),
            orientacion=orientacion_sel, inclinacion=inclinacion_sel)
        guardar_disposicion(
            foto["id"], proyecto_id, ancho_panel_m, alto_panel_m, separacion_m,
            disposicion["orientacion_panel"], n_requeridos, disposicion["n_ubicados"],
            disposicion["filas"], disposicion["columnas"],
            metodo="IA + manual" if session_state.get("st13_ia_resultado") else "manual",
            analisis_ia=session_state.get("st13_ia_resultado"))

    svg_mostrar = svg_resultado or session_state.get("st13_ultimo_svg")
    if svg_mostrar:
        disp = session_state.get("st13_ultima_disposicion", {})
        st.markdown("<hr class='sep'>", unsafe_allow_html=True)
        render_svg_fn(svg_mostrar, height=650)

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"""<div class='metric-box'><div class='metric-val'>{disp.get('n_ubicados',0)}</div>
                    <div class='metric-unit'>de {disp.get('n_requeridos',0)}</div>
                    <div class='metric-label'>Paneles ubicados</div></div>""", unsafe_allow_html=True)
        m2.markdown(f"""<div class='metric-box'><div class='metric-val'>{disp.get('filas',0)}×{disp.get('columnas',0)}</div>
                    <div class='metric-unit'>filas × columnas</div>
                    <div class='metric-label'>Rejilla</div></div>""", unsafe_allow_html=True)
        m3.markdown(f"""<div class='metric-box'><div class='metric-val'>{disp.get('area_usada_m2',0):.1f}</div>
                    <div class='metric-unit'>m²</div>
                    <div class='metric-label'>Área ocupada</div></div>""", unsafe_allow_html=True)
        estado_txt = "✅ Completo" if disp.get("completo") else "⚠ Incompleto"
        m4.markdown(f"""<div class='metric-box'><div class='metric-val' style='font-size:1.1rem;'>{estado_txt}</div>
                    <div class='metric-unit'>{disp.get('orientacion_panel','—')}</div>
                    <div class='metric-label'>Estado</div></div>""", unsafe_allow_html=True)

        if not disp.get("completo"):
            faltan = disp.get("n_requeridos", 0) - disp.get("n_ubicados", 0)
            st.markdown(f"""<div class='warn-box'>⚠ El área definida solo alcanza para
                        {disp.get('n_ubicados',0)} de {disp.get('n_requeridos',0)} paneles
                        (faltan {faltan}). Amplía el área utilizable, reduce el margen/separación,
                        quita obstáculos o sube una foto de un área adicional del sitio.</div>""",
                        unsafe_allow_html=True)

        st.download_button("⬇ Descargar plano (SVG)", data=svg_mostrar.encode("utf-8"),
                            file_name=f"plano_sitio_{foto['id']}_{datetime.now().strftime('%Y%m%d')}.svg",
                            mime="image/svg+xml", use_container_width=True,
                            key=f"st13_dl_svg_{foto['id']}")

    return svg_mostrar
