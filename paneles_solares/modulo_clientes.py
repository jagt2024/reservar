"""
modulo_clientes.py — Gestión de Clientes (CRM)
SolarCalc Pro · Módulo externo

Lleva el registro comercial de clientes y prospectos (leads): datos de
contacto, en qué etapa del embudo de ventas están, quién los tiene
asignados, su historial de interacciones (llamadas, correos, visitas...) y
tareas de seguimiento con fecha límite. Se integra con los proyectos ya
creados en la app: un cliente puede tener uno o varios proyectos
vinculados, y desde aquí se pueden asociar proyectos existentes sin tener
que volver a capturar sus datos.

Uso desde solar_app.py:
    from modulo_clientes import init_clientes_db, mostrar_clientes
    init_clientes_db()
    ...
    if modulo_activo == "clientes":
        mostrar_clientes()
"""
import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

from db_utils import get_conn

try:
    from zoneinfo import ZoneInfo
    _TZ_CO = ZoneInfo("America/Bogota")
except Exception:
    _TZ_CO = timezone(timedelta(hours=-5))


def _ahora_co() -> datetime:
    return datetime.now(_TZ_CO).replace(tzinfo=None)


def _now() -> str:
    return _ahora_co().strftime("%Y-%m-%d %H:%M:%S")


def _hoy() -> str:
    return _ahora_co().strftime("%Y-%m-%d")


# ─── Colores (coherentes con el resto de la app) ─────────────────────────────
SOL   = "#FFB300"; GREEN = "#00E676"; RED  = "#FF5252"; CYAN = "#00BCD4"
YEL   = "#FFD54F"; PUR   = "#A78BFA"; TEXT2 = "#8A9BBD"; BRD = "#2A3A55"
CARD  = "#1A2235"

ETAPAS = ["Lead", "Contactado", "Cotizado", "En negociación", "Ganado", "Perdido"]
COLOR_ETAPA = {
    "Lead": CYAN, "Contactado": YEL, "Cotizado": SOL,
    "En negociación": PUR, "Ganado": GREEN, "Perdido": RED,
}
FUENTES = ["Referido", "Redes sociales", "Página web", "Feria / evento",
           "Llamada en frío", "Google / SEO", "Otro"]
TIPOS_INTERACCION = ["📞 Llamada", "✉ Email", "💬 WhatsApp", "🤝 Reunión",
                      "🏠 Visita técnica", "📝 Nota"]
PRIORIDADES = ["Alta", "Media", "Baja"]
COLOR_PRIORIDAD = {"Alta": RED, "Media": YEL, "Baja": TEXT2}


# ═══════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════
def init_clientes_db():
    """Crea las tablas del CRM si no existen y agrega, de forma segura, la
    columna `cliente_id` a la tabla `proyectos` para poder vincularlos."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre                TEXT NOT NULL,
            tipo_persona          TEXT DEFAULT 'Natural',
            documento             TEXT,
            email                 TEXT,
            telefono              TEXT,
            direccion             TEXT,
            municipio             TEXT,
            departamento          TEXT,
            etapa                 TEXT DEFAULT 'Lead',
            fuente                TEXT,
            valor_estimado        REAL DEFAULT 0,
            motivo_perdida        TEXT,
            propietario_id        INTEGER,
            propietario_username  TEXT,
            creado_por_id         INTEGER,
            creado_por            TEXT,
            notas                 TEXT,
            creado                TEXT,
            actualizado           TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS interacciones_clientes (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id         INTEGER,
            tipo               TEXT,
            descripcion        TEXT,
            usuario_id         INTEGER,
            usuario_username   TEXT,
            fecha              TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tareas_clientes (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id             INTEGER,
            titulo                 TEXT,
            fecha_limite           TEXT,
            responsable_id         INTEGER,
            responsable_username   TEXT,
            estado                 TEXT DEFAULT 'Pendiente',
            prioridad              TEXT DEFAULT 'Media',
            creado                 TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
    """)
    conn.commit()

    # Vínculo opcional cliente <-> proyecto (columna agregada de forma
    # segura si la tabla `proyectos` ya existía sin ella, igual que se hizo
    # con `creado_por_id` en su momento).
    cols = [r[1] for r in c.execute("PRAGMA table_info(proyectos)").fetchall()]
    if cols and "cliente_id" not in cols:
        try:
            c.execute("ALTER TABLE proyectos ADD COLUMN cliente_id INTEGER")
        except Exception:
            pass
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# CLIENTES — CRUD
# ═══════════════════════════════════════════════════════════════════════════
def crear_cliente(datos: dict, usuario: dict) -> int:
    conn = get_conn()
    ahora = _now()
    conn.execute("""
        INSERT INTO clientes
            (nombre, tipo_persona, documento, email, telefono, direccion,
             municipio, departamento, etapa, fuente, valor_estimado,
             propietario_id, propietario_username, creado_por_id, creado_por,
             notas, creado, actualizado)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datos["nombre"], datos.get("tipo_persona", "Natural"), datos.get("documento", ""),
        datos.get("email", ""), datos.get("telefono", ""), datos.get("direccion", ""),
        datos.get("municipio", ""), datos.get("departamento", ""),
        datos.get("etapa", "Lead"), datos.get("fuente", ""),
        datos.get("valor_estimado", 0) or 0,
        datos.get("propietario_id", usuario["id"]),
        datos.get("propietario_username", usuario["username"]),
        usuario["id"], usuario["username"], datos.get("notas", ""), ahora, ahora,
    ))
    conn.commit()
    nuevo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return nuevo_id


def actualizar_cliente(cliente_id: int, datos: dict):
    conn = get_conn()
    conn.execute("""
        UPDATE clientes SET
            nombre=?, tipo_persona=?, documento=?, email=?, telefono=?,
            direccion=?, municipio=?, departamento=?, fuente=?,
            valor_estimado=?, notas=?, actualizado=?
        WHERE id=?
    """, (
        datos["nombre"], datos.get("tipo_persona", "Natural"), datos.get("documento", ""),
        datos.get("email", ""), datos.get("telefono", ""), datos.get("direccion", ""),
        datos.get("municipio", ""), datos.get("departamento", ""),
        datos.get("fuente", ""), datos.get("valor_estimado", 0) or 0,
        datos.get("notas", ""), _now(), cliente_id,
    ))
    conn.commit()
    conn.close()


def cambiar_etapa(cliente_id: int, nueva_etapa: str, motivo_perdida: str = None):
    conn = get_conn()
    if nueva_etapa == "Perdido":
        conn.execute("UPDATE clientes SET etapa=?, motivo_perdida=?, actualizado=? WHERE id=?",
                     (nueva_etapa, motivo_perdida or "", _now(), cliente_id))
    else:
        conn.execute("UPDATE clientes SET etapa=?, motivo_perdida=NULL, actualizado=? WHERE id=?",
                     (nueva_etapa, _now(), cliente_id))
    conn.commit()
    conn.close()


def reasignar_propietario(cliente_id: int, propietario_id: int, propietario_username: str):
    conn = get_conn()
    conn.execute(
        "UPDATE clientes SET propietario_id=?, propietario_username=?, actualizado=? WHERE id=?",
        (propietario_id, propietario_username, _now(), cliente_id))
    conn.commit()
    conn.close()


def eliminar_cliente(cliente_id: int):
    """Elimina el cliente, su historial de interacciones y sus tareas.
    Los proyectos que tenía vinculados NO se borran: solo quedan sin
    cliente asociado (cliente_id = NULL)."""
    conn = get_conn()
    conn.execute("DELETE FROM interacciones_clientes WHERE cliente_id=?", (cliente_id,))
    conn.execute("DELETE FROM tareas_clientes WHERE cliente_id=?", (cliente_id,))
    conn.execute("UPDATE proyectos SET cliente_id=NULL WHERE cliente_id=?", (cliente_id,))
    conn.execute("DELETE FROM clientes WHERE id=?", (cliente_id,))
    conn.commit()
    conn.close()


def obtener_clientes(usuario: dict, es_admin: bool) -> pd.DataFrame:
    """Un usuario normal solo ve/gestiona los clientes que tiene asignados
    como encargado; un administrador ve todos, igual que con los
    proyectos."""
    conn = get_conn()
    if es_admin:
        df = pd.read_sql("SELECT * FROM clientes ORDER BY actualizado DESC", conn)
    else:
        df = pd.read_sql(
            "SELECT * FROM clientes WHERE propietario_id=? ORDER BY actualizado DESC",
            conn, params=(usuario["id"],))
    conn.close()
    return df


def obtener_cliente(cliente_id: int):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _obtener_usuarios() -> pd.DataFrame:
    """Lista de usuarios del sistema, para asignar/reasignar clientes.
    Si la consulta falla por cualquier motivo, devuelve una tabla vacía
    en vez de interrumpir el módulo."""
    try:
        conn = get_conn()
        df = pd.read_sql("SELECT id, username FROM usuarios ORDER BY username", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "username"])


# ═══════════════════════════════════════════════════════════════════════════
# INTERACCIONES (línea de tiempo comercial)
# ═══════════════════════════════════════════════════════════════════════════
def registrar_interaccion(cliente_id: int, tipo: str, descripcion: str, usuario: dict):
    conn = get_conn()
    conn.execute("""
        INSERT INTO interacciones_clientes
            (cliente_id, tipo, descripcion, usuario_id, usuario_username, fecha)
        VALUES (?,?,?,?,?,?)
    """, (cliente_id, tipo, descripcion, usuario["id"], usuario["username"], _now()))
    conn.execute("UPDATE clientes SET actualizado=? WHERE id=?", (_now(), cliente_id))
    conn.commit()
    conn.close()


def obtener_interacciones(cliente_id: int) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        "SELECT * FROM interacciones_clientes WHERE cliente_id=? ORDER BY fecha DESC",
        conn, params=(cliente_id,))
    conn.close()
    return df


def eliminar_interaccion(interaccion_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM interacciones_clientes WHERE id=?", (interaccion_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# TAREAS DE SEGUIMIENTO
# ═══════════════════════════════════════════════════════════════════════════
def crear_tarea(cliente_id: int, titulo: str, fecha_limite: str, prioridad: str, usuario: dict):
    conn = get_conn()
    conn.execute("""
        INSERT INTO tareas_clientes
            (cliente_id, titulo, fecha_limite, responsable_id, responsable_username,
             estado, prioridad, creado)
        VALUES (?,?,?,?,?,'Pendiente',?,?)
    """, (cliente_id, titulo, fecha_limite, usuario["id"], usuario["username"],
          prioridad, _now()))
    conn.commit()
    conn.close()


def marcar_tarea(tarea_id: int, estado: str):
    conn = get_conn()
    conn.execute("UPDATE tareas_clientes SET estado=? WHERE id=?", (estado, tarea_id))
    conn.commit()
    conn.close()


def eliminar_tarea(tarea_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM tareas_clientes WHERE id=?", (tarea_id,))
    conn.commit()
    conn.close()


def obtener_tareas(cliente_id: int = None, usuario: dict = None, es_admin: bool = False,
                    solo_pendientes: bool = False) -> pd.DataFrame:
    conn = get_conn()
    q = """SELECT t.*, c.nombre AS cliente_nombre FROM tareas_clientes t
           LEFT JOIN clientes c ON c.id = t.cliente_id WHERE 1=1"""
    params = []
    if cliente_id:
        q += " AND t.cliente_id=?"; params.append(cliente_id)
    if not es_admin and usuario:
        q += " AND t.responsable_id=?"; params.append(usuario["id"])
    if solo_pendientes:
        q += " AND t.estado='Pendiente'"
    q += " ORDER BY t.fecha_limite ASC"
    df = pd.read_sql(q, conn, params=params)
    conn.close()
    return df


# ═══════════════════════════════════════════════════════════════════════════
# VINCULACIÓN CON PROYECTOS
# ═══════════════════════════════════════════════════════════════════════════
def vincular_proyecto(proyecto_id: int, cliente_id: int):
    conn = get_conn()
    conn.execute("UPDATE proyectos SET cliente_id=? WHERE id=?", (cliente_id, proyecto_id))
    conn.commit()
    conn.close()


def desvincular_proyecto(proyecto_id: int):
    conn = get_conn()
    conn.execute("UPDATE proyectos SET cliente_id=NULL WHERE id=?", (proyecto_id,))
    conn.commit()
    conn.close()


def obtener_proyectos_cliente(cliente_id: int) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        "SELECT id, nombre, municipio, creado, creado_por FROM proyectos "
        "WHERE cliente_id=? ORDER BY id DESC", conn, params=(cliente_id,))
    conn.close()
    return df


def obtener_proyectos_vinculables(usuario: dict, es_admin: bool) -> pd.DataFrame:
    """Proyectos que todavía no tienen cliente asociado, candidatos para
    vincular a este cliente. Un usuario normal solo puede vincular sus
    propios proyectos; un administrador puede vincular cualquiera."""
    conn = get_conn()
    if es_admin:
        df = pd.read_sql(
            "SELECT id, nombre, municipio, creado_por FROM proyectos "
            "WHERE cliente_id IS NULL ORDER BY id DESC", conn)
    else:
        df = pd.read_sql(
            "SELECT id, nombre, municipio, creado_por FROM proyectos "
            "WHERE cliente_id IS NULL AND creado_por_id=? ORDER BY id DESC",
            conn, params=(usuario["id"],))
    conn.close()
    return df


# ═══════════════════════════════════════════════════════════════════════════
# INTERFAZ
# ═══════════════════════════════════════════════════════════════════════════
def mostrar_clientes(usuario_activo_fn=None, tiene_permiso_fn=None, registrar_auditoria_fn=None):
    """Punto de entrada del módulo. Los tres parámetros son opcionales —
    si no se pasan, se importan directamente desde `modulo_seguridad`,
    igual que hace `modulo_monitoreo.py` — para que a solar_app.py le
    baste con llamar `mostrar_clientes()`."""
    from modulo_seguridad import tiene_permiso, usuario_activo, registrar_auditoria
    tiene_permiso_fn = tiene_permiso_fn or tiene_permiso
    usuario_activo_fn = usuario_activo_fn or usuario_activo
    registrar_auditoria_fn = registrar_auditoria_fn or registrar_auditoria

    _u = usuario_activo_fn()
    if not _u:
        st.warning("Debes iniciar sesión para usar la Gestión de Clientes.")
        return

    init_clientes_db()
    es_admin = tiene_permiso_fn("ver_usuarios")

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>🧑‍💼 GESTIÓN DE CLIENTES</div>
        <div class='hero-sub'>CRM · SEGUIMIENTO COMERCIAL · VINCULACIÓN CON PROYECTOS</div>
    </div>""", unsafe_allow_html=True)

    df_clientes = obtener_clientes(_u, es_admin)
    _mostrar_metricas_rapidas(df_clientes)

    tabP, tabL, tabN, tabT, tabM = st.tabs([
        "🗂 Pipeline", "👥 Clientes", "➕ Nuevo cliente", "🗓 Tareas", "📊 Métricas"
    ])

    with tabP:
        _mostrar_pipeline(df_clientes)

    with tabL:
        _mostrar_lista_y_detalle(df_clientes, _u, es_admin, registrar_auditoria_fn)

    with tabN:
        _formulario_nuevo_cliente(_u, es_admin, registrar_auditoria_fn)

    with tabT:
        _mostrar_tareas_dashboard(_u, es_admin)

    with tabM:
        _mostrar_metricas(df_clientes)


def _mostrar_metricas_rapidas(df: pd.DataFrame):
    total = len(df)
    ganados = int((df["etapa"] == "Ganado").sum()) if total else 0
    abiertos = int((~df["etapa"].isin(["Ganado", "Perdido"])).sum()) if total else 0
    valor_pipeline = df.loc[~df["etapa"].isin(["Ganado", "Perdido"]), "valor_estimado"].sum() if total else 0
    tasa_cierre = (ganados / total * 100) if total else 0

    st.markdown(f"""
    <div class='metric-grid'>
        <div class='metric-box'><div class='metric-val' style='color:{CYAN};'>{total}</div>
            <div class='metric-unit'>clientes</div><div class='metric-label'>TOTAL EN CRM</div></div>
        <div class='metric-box'><div class='metric-val' style='color:{SOL};'>{abiertos}</div>
            <div class='metric-unit'>en curso</div><div class='metric-label'>OPORTUNIDADES ABIERTAS</div></div>
        <div class='metric-box'><div class='metric-val' style='color:{GREEN};'>{ganados}</div>
            <div class='metric-unit'>cerrados</div><div class='metric-label'>GANADOS</div></div>
        <div class='metric-box'><div class='metric-val' style='color:{YEL};font-size:1.3rem;'>${valor_pipeline:,.0f}</div>
            <div class='metric-unit'>COP</div><div class='metric-label'>VALOR EN PIPELINE</div></div>
        <div class='metric-box'><div class='metric-val' style='color:{PUR};'>{tasa_cierre:.0f}%</div>
            <div class='metric-unit'>tasa</div><div class='metric-label'>CIERRE</div></div>
    </div>
    """, unsafe_allow_html=True)


def _mostrar_pipeline(df: pd.DataFrame):
    if df.empty:
        st.info("Aún no hay clientes registrados. Créalos desde la pestaña "
                "“➕ Nuevo cliente”.")
        return
    cols = st.columns(len(ETAPAS))
    for col, etapa in zip(cols, ETAPAS):
        sub = df[df["etapa"] == etapa]
        color = COLOR_ETAPA[etapa]
        with col:
            st.markdown(f"""
            <div style='text-align:center;padding:0.4rem;border-bottom:2px solid {color};
                        margin-bottom:0.5rem;'>
                <div style='font-family:Rajdhani,sans-serif;font-weight:700;color:{color};'>
                    {etapa.upper()}</div>
                <div style='font-size:0.72rem;color:{TEXT2};'>
                    {len(sub)} · ${sub['valor_estimado'].sum():,.0f}</div>
            </div>""", unsafe_allow_html=True)
            for _, r in sub.iterrows():
                st.markdown(f"""
                <div class='sol-card' style='padding:0.7rem 0.8rem;margin-bottom:0.5rem;
                            border-left:3px solid {color};'>
                    <div style='font-weight:600;font-size:0.85rem;color:#E8EDF5;'>{r['nombre']}</div>
                    <div style='font-size:0.7rem;color:{TEXT2};'>{r['municipio'] or '—'}</div>
                    <div style='font-size:0.72rem;color:{YEL};margin-top:0.2rem;'>
                        ${r['valor_estimado']:,.0f}</div>
                    <div style='font-size:0.65rem;color:{TEXT2};margin-top:0.2rem;'>
                        👤 {r['propietario_username'] or '—'}</div>
                </div>""", unsafe_allow_html=True)


def _mostrar_lista_y_detalle(df: pd.DataFrame, usuario, es_admin, registrar_auditoria_fn):
    if df.empty:
        st.info("Aún no hay clientes registrados.")
        return

    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        busqueda = st.text_input("🔎 Buscar por nombre, documento o teléfono", key="crm_busqueda")
    with fc2:
        filtro_etapa = st.selectbox("Etapa", ["Todas"] + ETAPAS, key="crm_filtro_etapa")
    with fc3:
        orden = st.selectbox("Ordenar por", ["Más recientes", "Nombre A-Z", "Valor estimado"],
                              key="crm_orden")

    vista = df.copy()
    if busqueda:
        b = busqueda.lower().strip()
        vista = vista[vista.apply(
            lambda r: b in str(r["nombre"]).lower()
            or b in str(r["documento"]).lower()
            or b in str(r["telefono"]).lower(), axis=1)]
    if filtro_etapa != "Todas":
        vista = vista[vista["etapa"] == filtro_etapa]
    if orden == "Nombre A-Z":
        vista = vista.sort_values("nombre")
    elif orden == "Valor estimado":
        vista = vista.sort_values("valor_estimado", ascending=False)

    if vista.empty:
        st.warning("Ningún cliente coincide con el filtro.")
        return

    etiquetas = {int(r["id"]): f"#{int(r['id'])} {r['nombre']} · {r['etapa']}"
                 for _, r in vista.iterrows()}
    cliente_sel_id = st.selectbox("Cliente:", list(etiquetas.keys()),
                                   format_func=lambda i: etiquetas[i], key="crm_cliente_sel")

    st.markdown("<hr class='sep'>", unsafe_allow_html=True)
    _mostrar_detalle_cliente(cliente_sel_id, usuario, es_admin, registrar_auditoria_fn)


def _mostrar_detalle_cliente(cliente_id, usuario, es_admin, registrar_auditoria_fn):
    c = obtener_cliente(cliente_id)
    if not c:
        st.error("Este cliente ya no existe. Puede que haya sido eliminado.")
        return

    puede_editar = es_admin or c["propietario_id"] == usuario["id"]
    color = COLOR_ETAPA.get(c["etapa"], TEXT2)

    st.markdown(f"""
    <div class='sol-card'>
        <div style='display:flex;justify-content:space-between;align-items:center;
                    flex-wrap:wrap;gap:0.5rem;'>
            <div>
                <div style='font-family:Rajdhani,sans-serif;font-size:1.4rem;
                            font-weight:700;color:#E8EDF5;'>{c['nombre']}</div>
                <div style='font-size:0.78rem;color:{TEXT2};'>
                    {c['tipo_persona']} · {c['documento'] or 'Sin documento'} ·
                    👤 Encargado: {c['propietario_username'] or '—'}</div>
            </div>
            <div style='background:rgba(255,255,255,0.05);border:1px solid {color};
                 color:{color};padding:0.3rem 0.8rem;border-radius:20px;
                 font-family:Rajdhani,sans-serif;font-weight:700;font-size:0.85rem;'>
                {c['etapa'].upper()}
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    dtab1, dtab2, dtab3, dtab4, dtab5 = st.tabs(
        ["ℹ Datos", "📈 Etapa", "📁 Proyectos", "🗒 Interacciones", "✅ Tareas"])

    # ── Datos generales ────────────────────────────────────────────────────
    with dtab1:
        with st.form(f"form_editar_{cliente_id}"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre / Razón social", value=c["nombre"] or "")
                tipo_persona = st.selectbox(
                    "Tipo de persona", ["Natural", "Jurídica"],
                    index=(0 if c["tipo_persona"] != "Jurídica" else 1))
                documento = st.text_input("Documento (CC / NIT)", value=c["documento"] or "")
                email = st.text_input("Email", value=c["email"] or "")
                telefono = st.text_input("Teléfono", value=c["telefono"] or "")
            with col2:
                direccion = st.text_input("Dirección", value=c["direccion"] or "")
                municipio = st.text_input("Municipio", value=c["municipio"] or "")
                departamento = st.text_input("Departamento", value=c["departamento"] or "")
                fuente = st.selectbox(
                    "Fuente", FUENTES,
                    index=FUENTES.index(c["fuente"]) if c["fuente"] in FUENTES else 0)
                valor_estimado = st.number_input(
                    "Valor estimado del negocio (COP)", min_value=0.0, step=100000.0,
                    value=float(c["valor_estimado"] or 0))
            notas = st.text_area("Notas generales", value=c["notas"] or "", height=90)

            guardar = st.form_submit_button(
                "💾 Guardar cambios", use_container_width=True, disabled=not puede_editar)
            if guardar:
                if not nombre.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    actualizar_cliente(cliente_id, dict(
                        nombre=nombre.strip(), tipo_persona=tipo_persona,
                        documento=documento.strip(), email=email.strip(),
                        telefono=telefono.strip(), direccion=direccion.strip(),
                        municipio=municipio.strip(), departamento=departamento.strip(),
                        fuente=fuente, valor_estimado=valor_estimado, notas=notas.strip()))
                    registrar_auditoria_fn(
                        usuario["id"], usuario["username"], "EDITAR_CLIENTE",
                        f"Cliente #{cliente_id} '{nombre.strip()}' actualizado", "clientes")
                    st.success("✓ Datos actualizados")
                    st.rerun()
        if not puede_editar:
            st.caption("🔒 Solo el encargado de este cliente o un administrador puede editarlo.")

        if es_admin:
            with st.expander("👤 Reasignar encargado"):
                usuarios_df = _obtener_usuarios()
                if usuarios_df.empty:
                    st.caption("No se pudo cargar la lista de usuarios.")
                else:
                    opciones_u = {int(r["id"]): r["username"] for _, r in usuarios_df.iterrows()}
                    ids_u = list(opciones_u.keys())
                    idx_actual = ids_u.index(c["propietario_id"]) if c["propietario_id"] in ids_u else 0
                    nuevo_prop = st.selectbox(
                        "Nuevo encargado", ids_u, format_func=lambda i: opciones_u[i],
                        index=idx_actual, key=f"reasignar_{cliente_id}")
                    if st.button("Reasignar", key=f"btn_reasignar_{cliente_id}"):
                        reasignar_propietario(cliente_id, nuevo_prop, opciones_u[nuevo_prop])
                        registrar_auditoria_fn(
                            usuario["id"], usuario["username"], "REASIGNAR_CLIENTE",
                            f"Cliente #{cliente_id} reasignado a '{opciones_u[nuevo_prop]}'",
                            "clientes")
                        st.success("✓ Encargado actualizado")
                        st.rerun()

        if puede_editar:
            with st.expander("🗑 Eliminar cliente"):
                st.markdown(f"""
                <div class='warn-box'>⚠ Esto elimina permanentemente a
                    <b>{c['nombre']}</b>, su historial de interacciones y sus tareas.
                    Los proyectos vinculados NO se borran, solo quedan sin cliente asociado.
                </div>""", unsafe_allow_html=True)
                confirmar = st.text_input("Escribe el nombre para confirmar",
                                           key=f"conf_del_{cliente_id}")
                if st.button("🗑 Eliminar definitivamente", key=f"btn_del_{cliente_id}"):
                    if confirmar.strip() == (c["nombre"] or "").strip():
                        eliminar_cliente(cliente_id)
                        registrar_auditoria_fn(
                            usuario["id"], usuario["username"], "ELIMINAR_CLIENTE",
                            f"Cliente #{cliente_id} '{c['nombre']}' eliminado", "clientes")
                        st.success("✓ Cliente eliminado")
                        st.session_state.pop("crm_cliente_sel", None)
                        st.rerun()
                    else:
                        st.error("El nombre no coincide.")

    # ── Etapa del embudo ───────────────────────────────────────────────────
    with dtab2:
        st.markdown("Mover a otra etapa del embudo de ventas:")
        cols_etapa = st.columns(len(ETAPAS))
        for col, etapa in zip(cols_etapa, ETAPAS):
            with col:
                activo = c["etapa"] == etapa
                if st.button(etapa, key=f"etapa_{cliente_id}_{etapa}",
                             disabled=activo or not puede_editar,
                             use_container_width=True):
                    if etapa == "Perdido":
                        st.session_state[f"_pedir_motivo_{cliente_id}"] = True
                        st.rerun()
                    else:
                        cambiar_etapa(cliente_id, etapa)
                        registrar_interaccion(cliente_id, "📝 Nota",
                                               f"Etapa cambiada a '{etapa}'", usuario)
                        registrar_auditoria_fn(
                            usuario["id"], usuario["username"], "CAMBIAR_ETAPA_CLIENTE",
                            f"Cliente #{cliente_id} → {etapa}", "clientes")
                        st.rerun()

        if st.session_state.get(f"_pedir_motivo_{cliente_id}"):
            motivo = st.text_input("Motivo de la pérdida", key=f"motivo_perdida_{cliente_id}")
            if st.button("Confirmar pérdida", key=f"confirmar_perdida_{cliente_id}"):
                cambiar_etapa(cliente_id, "Perdido", motivo)
                registrar_interaccion(cliente_id, "📝 Nota",
                                       f"Marcado como Perdido. Motivo: {motivo or '—'}", usuario)
                registrar_auditoria_fn(
                    usuario["id"], usuario["username"], "CAMBIAR_ETAPA_CLIENTE",
                    f"Cliente #{cliente_id} → Perdido ({motivo})", "clientes")
                del st.session_state[f"_pedir_motivo_{cliente_id}"]
                st.rerun()

        if c["etapa"] == "Perdido" and c["motivo_perdida"]:
            st.markdown(f"<div class='warn-box'>Motivo de la pérdida: {c['motivo_perdida']}</div>",
                        unsafe_allow_html=True)

    # ── Proyectos vinculados ───────────────────────────────────────────────
    with dtab3:
        proys = obtener_proyectos_cliente(cliente_id)
        if proys.empty:
            st.caption("Este cliente todavía no tiene proyectos vinculados.")
        else:
            for _, p in proys.iterrows():
                pc1, pc2 = st.columns([5, 1])
                with pc1:
                    st.markdown(f"""
                    <div class='sol-card' style='padding:0.7rem 0.9rem;'>
                        <b style='color:{SOL};'>#{p['id']} {p['nombre']}</b><br>
                        <span style='color:{TEXT2};font-size:0.78rem;'>
                        📍 {p['municipio'] or '—'} · Creado por {p['creado_por'] or '—'}</span>
                    </div>""", unsafe_allow_html=True)
                with pc2:
                    if puede_editar and st.button("Desvincular", key=f"desv_{cliente_id}_{p['id']}"):
                        desvincular_proyecto(int(p["id"]))
                        registrar_auditoria_fn(
                            usuario["id"], usuario["username"], "DESVINCULAR_PROYECTO",
                            f"Proyecto #{p['id']} desvinculado del cliente #{cliente_id}",
                            "clientes")
                        st.rerun()

        if puede_editar:
            st.markdown("<hr class='sep' style='margin:1rem 0;'>", unsafe_allow_html=True)
            disponibles = obtener_proyectos_vinculables(usuario, es_admin)
            if disponibles.empty:
                st.caption("No tienes proyectos sin vincular. Crea uno nuevo desde el panel "
                           "lateral y vuelve aquí para asociarlo a este cliente.")
            else:
                opciones_p = {int(r["id"]): f"#{r['id']} {r['nombre']}"
                              for _, r in disponibles.iterrows()}
                proy_sel = st.selectbox(
                    "Vincular un proyecto existente:", list(opciones_p.keys()),
                    format_func=lambda i: opciones_p[i], key=f"vincular_sel_{cliente_id}")
                if st.button("🔗 Vincular proyecto", key=f"vincular_btn_{cliente_id}"):
                    vincular_proyecto(proy_sel, cliente_id)
                    registrar_auditoria_fn(
                        usuario["id"], usuario["username"], "VINCULAR_PROYECTO",
                        f"Proyecto #{proy_sel} vinculado al cliente #{cliente_id}", "clientes")
                    st.success("✓ Proyecto vinculado")
                    st.rerun()

    # ── Interacciones (línea de tiempo) ────────────────────────────────────
    with dtab4:
        with st.form(f"nueva_interaccion_{cliente_id}", clear_on_submit=True):
            ic1, ic2 = st.columns([1, 3])
            with ic1:
                tipo_int = st.selectbox("Tipo", TIPOS_INTERACCION, key=f"tipo_int_{cliente_id}")
            with ic2:
                desc_int = st.text_input("¿Qué pasó?", key=f"desc_int_{cliente_id}")
            if st.form_submit_button("➕ Registrar"):
                if desc_int.strip():
                    registrar_interaccion(cliente_id, tipo_int, desc_int.strip(), usuario)
                    registrar_auditoria_fn(
                        usuario["id"], usuario["username"], "REGISTRAR_INTERACCION",
                        f"Interacción registrada con cliente #{cliente_id}", "clientes")
                    st.rerun()
                else:
                    st.error("Describe brevemente la interacción.")

        interacciones = obtener_interacciones(cliente_id)
        if interacciones.empty:
            st.caption("Sin interacciones registradas todavía.")
        else:
            for _, it in interacciones.iterrows():
                ii1, ii2 = st.columns([6, 1])
                with ii1:
                    st.markdown(f"""
                    <div style='padding:0.5rem 0;border-bottom:1px solid {BRD};'>
                        <b>{it['tipo']}</b> — {it['descripcion']}<br>
                        <span style='font-size:0.7rem;color:{TEXT2};'>
                        {it['usuario_username']} · {it['fecha']}</span>
                    </div>""", unsafe_allow_html=True)
                with ii2:
                    if puede_editar and st.button("🗑", key=f"del_int_{it['id']}"):
                        eliminar_interaccion(int(it["id"]))
                        st.rerun()

    # ── Tareas del cliente ─────────────────────────────────────────────────
    with dtab5:
        with st.form(f"nueva_tarea_{cliente_id}", clear_on_submit=True):
            tc1, tc2, tc3 = st.columns([3, 1, 1])
            with tc1:
                titulo_t = st.text_input("Tarea de seguimiento", key=f"titulo_t_{cliente_id}")
            with tc2:
                fecha_t = st.date_input("Vence", key=f"fecha_t_{cliente_id}")
            with tc3:
                prioridad_t = st.selectbox("Prioridad", PRIORIDADES, key=f"prio_t_{cliente_id}")
            if st.form_submit_button("➕ Crear tarea"):
                if titulo_t.strip():
                    crear_tarea(cliente_id, titulo_t.strip(), str(fecha_t), prioridad_t, usuario)
                    st.rerun()
                else:
                    st.error("Escribe una descripción para la tarea.")

        tareas_c = obtener_tareas(cliente_id=cliente_id)
        if tareas_c.empty:
            st.caption("Sin tareas para este cliente.")
        else:
            for _, t in tareas_c.iterrows():
                _fila_tarea(t, mostrar_cliente=False, contexto=f"det_{cliente_id}")


def _fila_tarea(t: pd.Series, mostrar_cliente: bool = True, contexto: str = "det"):
    """`contexto` distingue las keys de los widgets según desde dónde se
    llama esta función (detalle de un cliente vs. dashboard general de
    tareas), porque `st.tabs` renderiza el contenido de TODAS las pestañas
    en cada corrida — si la misma tarea aparece en dos lugares con la
    misma key, Streamlit lanza StreamlitDuplicateElementKey."""
    hecha = t["estado"] == "Hecha"
    vencida = (not hecha) and str(t["fecha_limite"]) < _hoy()
    color_p = COLOR_PRIORIDAD.get(t["prioridad"], TEXT2)

    c1, c2, c3 = st.columns([0.6, 5, 0.8])
    with c1:
        nuevo_estado = st.checkbox("", value=hecha, key=f"chk_tarea_{contexto}_{t['id']}")
        if nuevo_estado != hecha:
            marcar_tarea(int(t["id"]), "Hecha" if nuevo_estado else "Pendiente")
            st.rerun()
    with c2:
        cliente_txt = ""
        if mostrar_cliente and "cliente_nombre" in t and t["cliente_nombre"]:
            cliente_txt = f" · 👤 {t['cliente_nombre']}"
        estilo = f"text-decoration:line-through;color:{TEXT2};" if hecha else ""
        venc_txt = f"<span style='color:{RED};'> · ⚠ VENCIDA</span>" if vencida else ""
        st.markdown(f"""
        <div style='{estilo}padding:0.3rem 0;'>
            <b style='border-left:3px solid {color_p};padding-left:0.5rem;'>{t['titulo']}</b>{cliente_txt}<br>
            <span style='font-size:0.72rem;color:{TEXT2};'>
            Vence: {t['fecha_limite']} · Prioridad: {t['prioridad']}</span>{venc_txt}
        </div>""", unsafe_allow_html=True)
    with c3:
        if st.button("🗑", key=f"del_tarea_{contexto}_{t['id']}"):
            eliminar_tarea(int(t["id"]))
            st.rerun()


def _mostrar_tareas_dashboard(usuario, es_admin):
    solo_pendientes = st.checkbox("Mostrar solo pendientes", value=True, key="crm_solo_pend")
    tareas = obtener_tareas(usuario=usuario, es_admin=es_admin, solo_pendientes=solo_pendientes)
    if tareas.empty:
        st.info("No hay tareas de seguimiento" + (" pendientes." if solo_pendientes else "."))
        return
    vencidas = tareas[(tareas["estado"] == "Pendiente") & (tareas["fecha_limite"] < _hoy())]
    if not vencidas.empty:
        st.markdown(f"<div class='warn-box'>⚠ Tienes {len(vencidas)} tarea(s) vencida(s).</div>",
                    unsafe_allow_html=True)
    for _, t in tareas.iterrows():
        _fila_tarea(t, mostrar_cliente=True, contexto="dash")


def _barra_html(etiqueta: str, valor, maximo, color: str, sufijo: str = ""):
    """Una fila de barra horizontal en HTML/CSS puro — sin depender de
    altair/vega (que en algunos entornos de despliegue, p. ej. Python 3.14
    en Streamlit Cloud, falla al importarse)."""
    pct = 0 if not maximo else max(2, round(valor / maximo * 100))
    st.markdown(f"""
    <div style='margin-bottom:0.55rem;'>
        <div style='display:flex;justify-content:space-between;font-size:0.78rem;
                    color:{TEXT2};margin-bottom:0.15rem;'>
            <span>{etiqueta}</span>
            <span style='color:{color};font-family:Share Tech Mono,monospace;'>{valor}{sufijo}</span>
        </div>
        <div style='background:{BRD};border-radius:5px;height:10px;overflow:hidden;'>
            <div style='background:{color};width:{pct}%;height:100%;border-radius:5px;'></div>
        </div>
    </div>""", unsafe_allow_html=True)


def _mostrar_metricas(df: pd.DataFrame):
    if df.empty:
        st.info("Aún no hay datos suficientes para mostrar métricas.")
        return

    st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
        font-weight:600;margin-bottom:0.4rem;'>DISTRIBUCIÓN POR ETAPA</div>""",
        unsafe_allow_html=True)
    conteo_etapa = df["etapa"].value_counts().reindex(ETAPAS, fill_value=0)
    max_etapa = int(conteo_etapa.max()) if len(conteo_etapa) else 0
    for etapa, valor in conteo_etapa.items():
        _barra_html(etapa, int(valor), max_etapa, COLOR_ETAPA.get(etapa, SOL))

    fuente_conteo = df["fuente"].replace("", None).dropna().value_counts()
    if not fuente_conteo.empty:
        st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
            font-weight:600;margin:1rem 0 0.4rem;'>CLIENTES POR FUENTE</div>""",
            unsafe_allow_html=True)
        max_fuente = int(fuente_conteo.max())
        for fuente, valor in fuente_conteo.items():
            _barra_html(fuente, int(valor), max_fuente, CYAN)

    if df["propietario_username"].nunique(dropna=True) > 1:
        st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
            font-weight:600;margin:1rem 0 0.4rem;'>CLIENTES POR ENCARGADO</div>""",
            unsafe_allow_html=True)
        resumen = (df.groupby("propietario_username")
                     .agg(Clientes=("id", "count"), Valor_pipeline=("valor_estimado", "sum"))
                     .reset_index().sort_values("Clientes", ascending=False))
        resumen.columns = ["Encargado", "Clientes", "Valor pipeline (COP)"]
        st.dataframe(resumen, use_container_width=True, hide_index=True)


def _formulario_nuevo_cliente(usuario, es_admin, registrar_auditoria_fn):
    st.markdown("Registra un nuevo cliente o prospecto (lead). Podrás vincularlo a un "
                "proyecto ya creado, o a uno nuevo, desde su pestaña “📁 Proyectos”.")
    with st.form("form_nuevo_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre / Razón social *")
            tipo_persona = st.selectbox("Tipo de persona", ["Natural", "Jurídica"])
            documento = st.text_input("Documento (CC / NIT)")
            email = st.text_input("Email")
            telefono = st.text_input("Teléfono")
        with col2:
            direccion = st.text_input("Dirección")
            municipio = st.text_input("Municipio")
            departamento = st.text_input("Departamento")
            fuente = st.selectbox("¿Cómo llegó?", FUENTES)
            valor_estimado = st.number_input(
                "Valor estimado del negocio (COP)", min_value=0.0, step=100000.0)
        etapa_inicial = st.selectbox("Etapa inicial", ETAPAS, index=0)
        notas = st.text_area("Notas", height=80)

        propietario_id, propietario_username = usuario["id"], usuario["username"]
        if es_admin:
            usuarios_df = _obtener_usuarios()
            if not usuarios_df.empty:
                opciones_u = {int(r["id"]): r["username"] for _, r in usuarios_df.iterrows()}
                ids_u = list(opciones_u.keys())
                idx_actual = ids_u.index(usuario["id"]) if usuario["id"] in ids_u else 0
                sel_prop = st.selectbox("Encargado", ids_u, format_func=lambda i: opciones_u[i],
                                         index=idx_actual)
                propietario_id, propietario_username = sel_prop, opciones_u[sel_prop]

        crear = st.form_submit_button("✦ Crear cliente", use_container_width=True)
        if crear:
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                nuevo_id = crear_cliente(dict(
                    nombre=nombre.strip(), tipo_persona=tipo_persona,
                    documento=documento.strip(), email=email.strip(),
                    telefono=telefono.strip(), direccion=direccion.strip(),
                    municipio=municipio.strip(), departamento=departamento.strip(),
                    etapa=etapa_inicial, fuente=fuente, valor_estimado=valor_estimado,
                    propietario_id=propietario_id, propietario_username=propietario_username,
                    notas=notas.strip(),
                ), usuario)
                registrar_auditoria_fn(
                    usuario["id"], usuario["username"], "CREAR_CLIENTE",
                    f"Cliente #{nuevo_id} '{nombre.strip()}' creado", "clientes")
                st.success(f"✓ Cliente #{nuevo_id} creado")
                st.rerun()
