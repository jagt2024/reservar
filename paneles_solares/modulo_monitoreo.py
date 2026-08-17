"""
modulo_monitoreo.py — Monitoreo de sesiones conectadas
SolarCalc Pro · Módulo externo (solo administradores)

Lleva registro de qué usuarios/equipos están conectados a la aplicación en
este momento, qué módulo están usando, en qué proyecto están trabajando,
y permite a un administrador cerrar ("desconectar") la sesión de cualquier
usuario conectado. También deja un historial de conexiones y un resumen de
proyectos creados por usuario.

NOTA IMPORTANTE SOBRE EL "DESCONECTAR":
Streamlit no mantiene un socket persistente que este módulo pueda cortar
de forma remota. Lo que hacemos en su lugar es marcar la sesión como
"kicked" (expulsada) en la base de datos; la próxima vez que esa sesión
haga cualquier acción en la app (clic, cambio de campo, etc.) o la próxima
vez que Streamlit vuelva a ejecutar el script para ese navegador, se
detecta la marca, se limpia su `st.session_state` y se le regresa a la
pantalla de login. En la práctica esto ocurre casi de inmediato porque
`registrar_latido()` / `verificar_expulsion()` corren en cada rerun, pero
si el usuario deja la pestaña completamente quieta sin interactuar, el
efecto se aplica en su siguiente interacción.
"""
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, timedelta

from db_utils import get_conn

# ─── Vigilancia activa de la sesión ──────────────────────────────────────────
# Para que "Desconectar" se aplique de inmediato (y no solo hasta el próximo
# clic del usuario expulsado), forzamos un rerun periódico de Streamlit con
# streamlit-autorefresh. A diferencia de un F5 del navegador, esto SÍ
# conserva st.session_state; solo vuelve a ejecutar el script, que es
# exactamente donde revisamos si la sesión fue marcada como expulsada.
try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_DISPONIBLE = True
except ImportError:
    _AUTOREFRESH_DISPONIBLE = False

INTERVALO_VIGILANCIA_MS = 900000  # cada cuánto se revisa si la sesión sigue viva

# ─── Colores (coherentes con el resto de la app) ─────────────────────────────
SOL   = "#FFB300"; GREEN = "#00E676"; RED = "#FF5252"; CYAN = "#00BCD4"
YEL   = "#FFD54F"; TEXT2 = "#8A9BBD"; BRD  = "#2A3A55"; CARD = "#1A2235"

MINUTOS_EN_LINEA   = 3   # última actividad <= este umbral → "🟢 En línea"
MINUTOS_INACTIVO   = 15  # entre el umbral anterior y este → "🟡 Inactivo"
                          # más viejo que esto → se considera cerrada/expirada

# ═══════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════
def init_monitoreo_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_activas (
            session_id      TEXT PRIMARY KEY,
            usuario_id      INTEGER,
            username        TEXT,
            rol             TEXT,
            modulo          TEXT,
            proyecto_id     INTEGER,
            proyecto_nombre TEXT,
            ip              TEXT,
            navegador       TEXT,
            modulos_usados  TEXT DEFAULT '',
            login_time      TEXT,
            last_seen       TEXT,
            kicked          INTEGER DEFAULT 0,
            kicked_by       TEXT,
            kicked_time     TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_historial (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT,
            usuario_id      INTEGER,
            username        TEXT,
            rol             TEXT,
            modulos_usados  TEXT,
            ip              TEXT,
            login_time      TEXT,
            fin_time        TEXT,
            motivo_fin      TEXT
        )
    """)
    conn.commit()

    # Atribución de "creado por" en proyectos (columna opcional agregada
    # de forma segura si la tabla ya existía sin ella).
    cols = [r[1] for r in c.execute("PRAGMA table_info(proyectos)").fetchall()]
    if "creado_por_id" not in cols:
        try:
            c.execute("ALTER TABLE proyectos ADD COLUMN creado_por_id INTEGER")
        except Exception:
            pass
    if "creado_por" not in cols:
        try:
            c.execute("ALTER TABLE proyectos ADD COLUMN creado_por TEXT")
        except Exception:
            pass
    conn.commit()
    conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _session_id() -> str:
    """Identificador único y estable por pestaña/navegador (no por usuario:
    si el mismo usuario abre dos pestañas, cuentan como dos sesiones)."""
    if "_monitor_session_id" not in st.session_state:
        st.session_state["_monitor_session_id"] = uuid.uuid4().hex[:20]
    return st.session_state["_monitor_session_id"]


def _cliente_info():
    """Intenta obtener IP y user-agent del cliente. Depende de la versión
    de Streamlit; si no está disponible, devuelve valores vacíos sin
    interrumpir la app."""
    ip, ua = "", ""
    try:
        headers = st.context.headers
        if headers:
            ip = (headers.get("X-Forwarded-For", "") or
                  headers.get("X-Real-Ip", "")).split(",")[0].strip()
            ua = headers.get("User-Agent", "") or ""
    except Exception:
        pass
    try:
        if not ip and getattr(st.context, "ip_address", None):
            ip = st.context.ip_address
    except Exception:
        pass
    return ip, ua


# ═══════════════════════════════════════════════════════════════════════════
# LATIDO (heartbeat) — llamar en cada rerun, para todo usuario autenticado
# ═══════════════════════════════════════════════════════════════════════════
def registrar_latido(usuario: dict, modulo_activo: str = None,
                      proyecto_id: int = None, proyecto_nombre: str = None):
    if not usuario:
        return
    sid = _session_id()
    ip, ua = _cliente_info()
    now = _now()
    rol = usuario.get("rol") or usuario.get("role") or "—"

    conn = get_conn()
    row = conn.execute(
        "SELECT modulos_usados, login_time FROM sesiones_activas WHERE session_id=?",
        (sid,)).fetchone()

    if row is None:
        modulos_usados = modulo_activo or ""
        conn.execute("""
            INSERT INTO sesiones_activas
                (session_id, usuario_id, username, rol, modulo, proyecto_id,
                 proyecto_nombre, ip, navegador, modulos_usados,
                 login_time, last_seen, kicked)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)
        """, (sid, usuario.get("id"), usuario.get("username"), rol,
              modulo_activo, proyecto_id, proyecto_nombre, ip, ua,
              modulos_usados, now, now))
    else:
        usados = set(filter(None, (row[0] or "").split(",")))
        if modulo_activo:
            usados.add(modulo_activo)
        conn.execute("""
            UPDATE sesiones_activas
               SET usuario_id=?, username=?, rol=?, modulo=?, proyecto_id=?,
                   proyecto_nombre=?, ip=?, navegador=?, modulos_usados=?,
                   last_seen=?
             WHERE session_id=?
        """, (usuario.get("id"), usuario.get("username"), rol, modulo_activo,
              proyecto_id, proyecto_nombre, ip or None, ua or None,
              ",".join(sorted(usados)), now, sid))
    conn.commit()
    conn.close()

    _limpiar_sesiones_viejas()


def verificar_expulsion():
    """Si un administrador marcó esta sesión como expulsada, cierra la
    sesión localmente (limpia session_state) y detiene la ejecución
    mostrando un aviso. Debe llamarse justo después de confirmar que hay
    un usuario autenticado.

    Es esta función (la de la propia sesión expulsada) la que archiva su
    registro al historial y lo borra de las sesiones activas — así se
    garantiza que el cierre ocurre una sola vez y no se duplica si el
    administrador vuelve a intentarlo o si otra pestaña dispara la
    limpieza de sesiones viejas primero.

    Además activa un rerun periódico (streamlit-autorefresh) para que la
    desconexión se aplique en segundos, sin depender de que el usuario
    expulsado haga clic en algo."""
    sid = st.session_state.get("_monitor_session_id")
    if not sid:
        return

    if _AUTOREFRESH_DISPONIBLE:
        st_autorefresh(interval=INTERVALO_VIGILANCIA_MS, key="_monitor_watchdog")

    conn = get_conn()
    row = conn.execute(
        "SELECT kicked, usuario_id, username, rol, modulos_usados, ip, login_time "
        "FROM sesiones_activas WHERE session_id=?", (sid,)).fetchone()

    if row and row[0]:
        (_kicked, uid, uname, rol, mods, ip, login_t) = row
        conn.execute("""
            INSERT INTO sesiones_historial
                (session_id, usuario_id, username, rol, modulos_usados, ip,
                 login_time, fin_time, motivo_fin)
            VALUES (?,?,?,?,?,?,?,?,'expulsada_por_admin')
        """, (sid, uid, uname, rol, mods, ip, login_t, _now()))
        conn.execute("DELETE FROM sesiones_activas WHERE session_id=?", (sid,))
        conn.commit()
        conn.close()

        st.markdown(f"""
        <div style='max-width:480px;margin:15vh auto;text-align:center;
             background:{CARD};border:1px solid {RED};border-radius:14px;
             padding:2.5rem 2rem;'>
            <div style='font-size:2.5rem;'>🔒</div>
            <div style='font-family:Rajdhani,sans-serif;font-size:1.4rem;
                 color:{RED};font-weight:700;margin-top:0.5rem;'>
                SESIÓN FINALIZADA
            </div>
            <div style='color:{TEXT2};margin-top:0.6rem;font-size:0.9rem;'>
                Un administrador cerró tu sesión en SolarCalc Pro.<br>
                Vuelve a iniciar sesión para continuar.
            </div>
        </div>
        """, unsafe_allow_html=True)
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.stop()

    conn.close()


def _limpiar_sesiones_viejas(minutos: int = MINUTOS_INACTIVO):
    """Mueve al historial las sesiones sin actividad reciente (pestaña
    cerrada, computador apagado, etc.).

    Las sesiones marcadas como "kicked" (expulsadas) NO se tocan aquí:
    las archiva y elimina su propia sesión (ver `verificar_expulsion`) en
    cuanto detecta la marca — normalmente en segundos gracias a la
    vigilancia activa. Si esa sesión nunca vuelve a responder (p. ej. el
    navegador ya estaba cerrado cuando se pidió la desconexión), esta
    limpieza la termina archivando de todas formas una vez que su
    `last_seen` se vuelve viejo, sin crear registros duplicados."""
    limite = (datetime.now() - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    viejas = conn.execute(
        "SELECT session_id, usuario_id, username, rol, modulos_usados, ip, "
        "login_time, kicked FROM sesiones_activas "
        "WHERE last_seen < ?", (limite,)).fetchall()
    for (sid, uid, uname, rol, mods, ip, login_t, kicked) in viejas:
        motivo = "expulsada_por_admin" if kicked else "expirada"
        conn.execute("""
            INSERT INTO sesiones_historial
                (session_id, usuario_id, username, rol, modulos_usados, ip,
                 login_time, fin_time, motivo_fin)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (sid, uid, uname, rol, mods, ip, login_t, _now(), motivo))
        conn.execute("DELETE FROM sesiones_activas WHERE session_id=?", (sid,))
    conn.commit()
    conn.close()


def desconectar_sesion(session_id: str, admin_username: str):
    conn = get_conn()
    conn.execute(
        "UPDATE sesiones_activas SET kicked=1, kicked_by=?, kicked_time=? "
        "WHERE session_id=?", (admin_username, _now(), session_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# UI — Panel de administrador
# ═══════════════════════════════════════════════════════════════════════════
def _estado_conexion(last_seen_str: str):
    try:
        last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "⚪ Desconocido", TEXT2
    delta_min = (datetime.now() - last_seen).total_seconds() / 60
    if delta_min <= MINUTOS_EN_LINEA:
        return "🟢 En línea", GREEN
    elif delta_min <= MINUTOS_INACTIVO:
        return "🟡 Inactivo", YEL
    return "⚪ Desconectando…", TEXT2


def mostrar_monitoreo(usuario_activo_fn=None, tiene_permiso_fn=None,
                       registrar_auditoria_fn=None):
    """Punto de entrada del módulo. Se pasan las funciones de seguridad ya
    resueltas por la app principal para evitar import circular con
    modulo_seguridad."""
    from modulo_seguridad import tiene_permiso, usuario_activo, registrar_auditoria
    tiene_permiso_fn       = tiene_permiso_fn or tiene_permiso
    usuario_activo_fn      = usuario_activo_fn or usuario_activo
    registrar_auditoria_fn = registrar_auditoria_fn or registrar_auditoria

    init_monitoreo_db()

    # ── Acceso restringido a administradores ─────────────────────────────
    if not tiene_permiso_fn("ver_usuarios"):
        st.markdown(f"""
        <div class='sol-card' style='text-align:center;padding:3rem;'>
            <div style='font-size:2.5rem;'>⛔</div>
            <div style='font-family:Rajdhani,sans-serif;font-size:1.3rem;
                 color:{RED};margin-top:0.5rem;'>ACCESO RESTRINGIDO</div>
            <div style='color:{TEXT2};margin-top:0.4rem;'>
                Este módulo solo está disponible para administradores.</div>
        </div>""", unsafe_allow_html=True)
        return

    _limpiar_sesiones_viejas()
    _u = usuario_activo_fn()

    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#0A0E1A,#1A2235);border:1px solid {BRD};
     border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.5rem;'>
        <div style='font-family:Rajdhani,sans-serif;font-size:1.6rem;font-weight:700;
         color:{SOL};letter-spacing:2px;'>🖥 MONITOREO DE SESIONES</div>
        <div style='color:{TEXT2};font-size:0.8rem;letter-spacing:2px;margin-top:0.2rem;'>
            USUARIOS CONECTADOS · ACTIVIDAD POR MÓDULO · PROYECTOS CREADOS</div>
    </div>
    """, unsafe_allow_html=True)

    c_ref, _ = st.columns([1, 5])
    with c_ref:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()

    if not _AUTOREFRESH_DISPONIBLE:
        st.warning(
            "⚠ El paquete **streamlit-autorefresh** no está instalado. "
            "Sin él, al pulsar “Desconectar” la sesión se cerrará hasta que "
            "ese usuario haga clic en algo, no de inmediato. "
            "Instálalo con `pip install streamlit-autorefresh` y reinicia la app "
            "para que la desconexión sea instantánea.")

    mt1, mt2, mt3 = st.tabs(["🟢 Conectados ahora", "📜 Historial de sesiones",
                              "📁 Proyectos creados"])

    # ══ TAB 1 — Sesiones activas ═══════════════════════════════════════════
    with mt1:
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM sesiones_activas ORDER BY last_seen DESC", conn)
        conn.close()

        if df.empty:
            st.info("No hay usuarios conectados en este momento.")
        else:
            n_online = sum(1 for ls in df["last_seen"]
                           if _estado_conexion(ls)[0].startswith("🟢"))
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"""<div class='metric-box'>
                    <div class='metric-val' style='color:{GREEN};'>{n_online}</div>
                    <div class='metric-unit'>usuarios</div>
                    <div class='metric-label'>EN LÍNEA</div></div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class='metric-box'>
                    <div class='metric-val' style='color:{SOL};'>{len(df)}</div>
                    <div class='metric-unit'>sesiones</div>
                    <div class='metric-label'>REGISTRADAS</div></div>""", unsafe_allow_html=True)
            with m3:
                n_mod = df["modulo"].nunique()
                st.markdown(f"""<div class='metric-box'>
                    <div class='metric-val' style='color:{CYAN};'>{n_mod}</div>
                    <div class='metric-unit'>módulos</div>
                    <div class='metric-label'>EN USO</div></div>""", unsafe_allow_html=True)

            st.markdown("<hr class='sep'>" if False else
                         "<hr style='border-color:#2A3A55;margin:1rem 0;'>",
                         unsafe_allow_html=True)

            for _, r in df.iterrows():
                estado, col = _estado_conexion(r["last_seen"])
                es_propia = (r["session_id"] == st.session_state.get("_monitor_session_id"))
                cA, cB, cC, cD, cE = st.columns([2, 1.6, 1.8, 1.6, 1.2])
                with cA:
                    st.markdown(f"""
                    <div style='padding:0.3rem 0;'>
                        <b style='color:{TEXT2};'>👤 {r['username'] or '—'}</b>
                        <span style='color:#4A5A75;font-size:0.75rem;'> · {r['rol'] or '—'}</span>
                        {" <span style='color:%s;font-size:0.7rem;'>(esta sesión)</span>" % SOL if es_propia else ""}
                    </div>""", unsafe_allow_html=True)
                with cB:
                    st.markdown(f"""<div style='font-size:0.8rem;color:{YEL};'>
                        📦 {r['modulo'] or '—'}</div>""", unsafe_allow_html=True)
                with cC:
                    st.markdown(f"""<div style='font-size:0.8rem;color:{TEXT2};'>
                        📁 {r['proyecto_nombre'] or 'Sin proyecto'}</div>""", unsafe_allow_html=True)
                with cD:
                    if r["kicked"]:
                        st.markdown(f"""<div style='font-size:0.75rem;color:{RED};'>
                            🔌 Cerrando sesión…<br>
                            <span style='color:#4A5A75;'>desde {r['login_time']}</span>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div style='font-size:0.75rem;color:{col};'>
                            {estado}<br><span style='color:#4A5A75;'>desde {r['login_time']}</span>
                        </div>""", unsafe_allow_html=True)
                with cE:
                    if es_propia:
                        st.caption("—")
                    elif r["kicked"]:
                        st.caption("⏳ en proceso")
                    else:
                        if st.button("🔌 Desconectar", key=f"kick_{r['session_id']}",
                                     use_container_width=True):
                            desconectar_sesion(r["session_id"], _u["username"])
                            registrar_auditoria_fn(
                                _u["id"], _u["username"], "DESCONECTAR_USUARIO",
                                f"Sesión de '{r['username']}' cerrada por administrador",
                                "monitoreo")
                            st.success(f"Sesión de {r['username']} marcada para cierre.")
                            st.rerun()
                st.markdown("<hr style='border-color:#161D30;margin:0.2rem 0;'>",
                            unsafe_allow_html=True)

    # ══ TAB 2 — Historial ═══════════════════════════════════════════════════
    with mt2:
        conn = get_conn()
        hist = pd.read_sql(
            "SELECT id AS ID, username AS Usuario, rol AS Rol, "
            "modulos_usados AS 'Módulos usados', ip AS IP, "
            "login_time AS 'Conectado', fin_time AS 'Finalizó', "
            "motivo_fin AS Motivo FROM sesiones_historial ORDER BY id DESC LIMIT 300",
            conn)
        conn.close()
        if hist.empty:
            st.info("Aún no hay historial de sesiones cerradas.")
        else:
            hist["Motivo"] = hist["Motivo"].map({
                "expulsada_por_admin": "🔌 Expulsada por admin",
                "expirada": "⏱ Expirada / cerró pestaña"
            }).fillna(hist["Motivo"])

            hist.insert(0, "Eliminar", False)
            editado = st.data_editor(
                hist, use_container_width=True, height=420, hide_index=True,
                key="hist_editor",
                disabled=[c for c in hist.columns if c != "Eliminar"],
                column_config={
                    "Eliminar": st.column_config.CheckboxColumn(
                        "🗑", help="Marcar para eliminar este registro"),
                    "ID": st.column_config.NumberColumn(width="small"),
                },
            )
            seleccionados = editado.loc[editado["Eliminar"], "ID"].tolist()

            cdel1, cdel2 = st.columns([1.6, 3])
            with cdel1:
                if st.button(f"🗑 Eliminar seleccionados ({len(seleccionados)})",
                             use_container_width=True, disabled=not seleccionados):
                    conn = get_conn()
                    conn.executemany("DELETE FROM sesiones_historial WHERE id=?",
                                      [(i,) for i in seleccionados])
                    conn.commit()
                    conn.close()
                    registrar_auditoria_fn(
                        _u["id"], _u["username"], "ELIMINAR_HISTORIAL_SESIONES",
                        f"{len(seleccionados)} registro(s) de historial eliminados",
                        "monitoreo")
                    st.success(f"{len(seleccionados)} registro(s) eliminados.")
                    st.rerun()

            with st.expander("⚠ Vaciar todo el historial de sesiones"):
                st.caption("Esta acción borra permanentemente todos los "
                           "registros del historial (no afecta a las "
                           "sesiones activas en este momento).")
                confirmar = st.checkbox(
                    "Confirmo que deseo eliminar TODO el historial de sesiones",
                    key="confirmar_vaciar_historial")
                if st.button("🗑 Vaciar historial completo", disabled=not confirmar):
                    conn = get_conn()
                    total = conn.execute(
                        "SELECT COUNT(*) FROM sesiones_historial").fetchone()[0]
                    conn.execute("DELETE FROM sesiones_historial")
                    conn.commit()
                    conn.close()
                    registrar_auditoria_fn(
                        _u["id"], _u["username"], "VACIAR_HISTORIAL_SESIONES",
                        f"Historial de sesiones vaciado por completo ({total} registros)",
                        "monitoreo")
                    st.success("Historial de sesiones vaciado.")
                    st.rerun()

    # ══ TAB 3 — Proyectos creados ════════════════════════════════════════════
    with mt3:
        conn = get_conn()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(proyectos)").fetchall()]
        select_creador = "creado_por" if "creado_por" in cols else "NULL"
        proys = pd.read_sql(f"""
            SELECT id AS ID, nombre AS Nombre, municipio AS Municipio,
                   {select_creador} AS Creado_por, creado AS Fecha
            FROM proyectos ORDER BY id DESC
        """, conn)
        conn.close()

        if proys.empty:
            st.info("Aún no se han creado proyectos.")
        else:
            st.markdown(f"""<div class='metric-box' style='display:inline-block;
                min-width:160px;margin-bottom:1rem;'>
                <div class='metric-val' style='color:{SOL};'>{len(proys)}</div>
                <div class='metric-unit'>proyectos</div>
                <div class='metric-label'>TOTAL CREADOS</div></div>""",
                unsafe_allow_html=True)

            if proys["Creado_por"].notna().any():
                resumen = (proys.dropna(subset=["Creado_por"])
                           .groupby("Creado_por").size()
                           .reset_index(name="Proyectos creados")
                           .sort_values("Proyectos creados", ascending=False))
                st.markdown("##### Proyectos por usuario")
                st.dataframe(resumen, use_container_width=True, hide_index=True)
                st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("##### Detalle de proyectos")
            proys["Creado_por"] = proys["Creado_por"].fillna("— (sin registrar)")
            st.dataframe(proys, use_container_width=True, hide_index=True)

    st.markdown(f"""
    <div style='margin-top:1rem;font-size:0.72rem;color:#4A5A75;text-align:center;'>
        Un usuario se considera "en línea" si tuvo actividad en los últimos {MINUTOS_EN_LINEA} min,
        "inactivo" hasta {MINUTOS_INACTIVO} min sin actividad; después se archiva en el historial.
        La desconexión se aplica en la próxima interacción o recarga de esa sesión.
    </div>""", unsafe_allow_html=True)
