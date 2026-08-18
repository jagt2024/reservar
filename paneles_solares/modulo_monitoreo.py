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
from datetime import datetime, timedelta, timezone

from db_utils import get_conn

# ─── Zona horaria de Colombia ─────────────────────────────────────────────────
# Colombia usa UTC-5 todo el año (no aplica horario de verano). Se intenta
# usar la base de datos de zonas horarias del sistema (zoneinfo); si no está
# disponible (p. ej. imagen mínima sin tzdata), se usa el offset fijo -5.
try:
    from zoneinfo import ZoneInfo
    _TZ_CO = ZoneInfo("America/Bogota")
except Exception:
    _TZ_CO = timezone(timedelta(hours=-5))

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

INTERVALO_VIGILANCIA_MS = 600000  # cada cuánto se revisa si la sesión sigue viva
                                 # (también controla cada cuánto se actualiza
                                 # el contador de tiempo restante que ve el usuario)

# ─── Colores (coherentes con el resto de la app) ─────────────────────────────
SOL   = "#FFB300"; GREEN = "#00E676"; RED = "#FF5252"; CYAN = "#00BCD4"
YEL   = "#FFD54F"; TEXT2 = "#8A9BBD"; BRD  = "#2A3A55"; CARD = "#1A2235"

MINUTOS_EN_LINEA   = 3    # última actividad <= este umbral → "🟢 En línea"
MINUTOS_INACTIVO   = 10   # entre el umbral anterior y este → "🟡 Inactivo"
                           # al llegar a este umbral, la sesión se desconecta
                           # automáticamente (ver `_auto_desconectar_inactivos`)
SEGUNDOS_AVISO_CIERRE = 15  # cuenta regresiva que se muestra, tanto si el
                             # cierre es por inactividad como si lo hizo un
                             # administrador, antes de finalizar la sesión

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS mensajes_chat (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id          INTEGER,
            usuario_username    TEXT,
            remitente           TEXT,   -- 'admin' o 'usuario'
            remitente_username  TEXT,
            texto               TEXT,
            fecha               TEXT,
            leido_admin         INTEGER DEFAULT 0,
            leido_usuario       INTEGER DEFAULT 0
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


def _ahora_co() -> datetime:
    """Fecha/hora actual en la zona horaria de Colombia (America/Bogota,
    UTC-5), sin tzinfo adjunto para poder compararla y restarla directamente
    con los timestamps ya guardados como texto en la base de datos."""
    return datetime.now(_TZ_CO).replace(tzinfo=None)


def _now():
    return _ahora_co().strftime("%Y-%m-%d %H:%M:%S")


def _formatear_duracion(total_minutos: float) -> str:
    """Convierte minutos a un texto legible: '5 min' o '1h 12min'."""
    total_minutos = max(0, int(round(total_minutos)))
    horas, minutos = divmod(total_minutos, 60)
    if horas:
        return f"{horas}h {minutos:02d}min"
    return f"{minutos} min"


def _tiempo_conectado(login_time_str: str) -> str:
    """Tiempo transcurrido desde login_time hasta ahora, en formato legible."""
    try:
        login_t = datetime.strptime(login_time_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"
    minutos = (_ahora_co() - login_t).total_seconds() / 60
    return _formatear_duracion(minutos)


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

    _auto_desconectar_inactivos()
    _limpiar_sesiones_viejas()


def _mostrar_tiempo_restante(last_seen_str: str):
    """Widget discreto y flotante (esquina inferior derecha) que le muestra
    al usuario cuánto tiempo le queda antes de que su sesión se cierre
    automáticamente por inactividad. El valor se recalcula en cada rerun
    (cada `INTERVALO_VIGILANCIA_MS` como máximo) y se reinicia solo cada
    vez que hay actividad real, porque eso actualiza `last_seen`."""
    try:
        last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
        transcurridos = (_ahora_co() - last_seen).total_seconds()
    except Exception:
        transcurridos = 0
    restantes = max(0, int(MINUTOS_INACTIVO * 60 - transcurridos))
    m, s = divmod(restantes, 60)
    color = RED if restantes <= 60 else (YEL if restantes <= 180 else TEXT2)
    st.markdown(f"""
    <div style='position:fixed;bottom:14px;left:14px;z-index:9999;
         background:{CARD};border:1px solid {BRD};border-radius:8px;
         padding:0.4rem 0.7rem;font-family:Rajdhani,sans-serif;
         font-size:0.78rem;color:{TEXT2};box-shadow:0 2px 8px rgba(0,0,0,.4);'>
        ⏱ Sesión inactiva se cerrará en
        <b style='color:{color};'>{m}:{s:02d}</b>
    </div>
    """, unsafe_allow_html=True)


def _mostrar_aviso_cierre(mensaje: str, segundos_restantes: int):
    """Pantalla de aviso, con cuenta regresiva, que se muestra tanto si el
    cierre es por inactividad como si lo inició un administrador. La
    pantalla se refresca sola (vía el watchdog de autorefresh) hasta que
    la cuenta llega a cero y `verificar_expulsion` finaliza el cierre."""
    st.markdown(f"""
    <div style='max-width:480px;margin:15vh auto;text-align:center;
         background:{CARD};border:1px solid {YEL};border-radius:14px;
         padding:2.5rem 2rem;'>
        <div style='font-size:2.5rem;'>⏳</div>
        <div style='font-family:Rajdhani,sans-serif;font-size:1.4rem;
             color:{YEL};font-weight:700;margin-top:0.5rem;'>
            SESIÓN POR CERRAR
        </div>
        <div style='color:{TEXT2};margin-top:0.6rem;font-size:0.9rem;'>
            {mensaje}
        </div>
        <div style='font-family:Rajdhani,sans-serif;font-size:2.2rem;
             font-weight:700;color:{RED};margin-top:1rem;'>
            {segundos_restantes}s
        </div>
        <div style='color:#4A5A75;font-size:0.75rem;margin-top:0.4rem;'>
            Esta pantalla se actualiza sola.
        </div>
    </div>
    """, unsafe_allow_html=True)


def verificar_expulsion():
    """Controla el ciclo de vida de ESTA sesión frente a un cierre forzado,
    ya sea porque un administrador la desconectó o porque el sistema la
    marcó por inactividad (ver `_auto_desconectar_inactivos`). Debe
    llamarse justo después de confirmar que hay un usuario autenticado, y
    ANTES de `registrar_latido()` (así el `last_seen` que lee todavía
    refleja la última actividad real, no el latido de este mismo rerun).

    Funciona en dos fases para que el usuario nunca se quede sin aviso:
      1) Al detectar la marca `kicked`, muestra una pantalla con cuenta
         regresiva (`SEGUNDOS_AVISO_CIERRE`) en vez de cerrar de inmediato.
      2) Cuando la cuenta llega a cero, esta misma sesión archiva su
         registro al historial (con el motivo correcto: 'inactividad' o
         'expulsada_por_admin') y lo borra de las sesiones activas — así
         el cierre ocurre una sola vez y no se duplica.

    Si la sesión sigue activa (no fue marcada), en vez de cerrar nada
    muestra el contador de tiempo restante hasta la próxima desconexión
    automática por inactividad.

    Además activa un rerun periódico (streamlit-autorefresh) para que
    tanto la desconexión como el contador se mantengan al día sin
    depender de que el usuario haga clic en algo."""
    sid = st.session_state.get("_monitor_session_id")
    if not sid:
        return

    if _AUTOREFRESH_DISPONIBLE:
        st_autorefresh(interval=INTERVALO_VIGILANCIA_MS, key="_monitor_watchdog")

    conn = get_conn()
    row = conn.execute(
        "SELECT kicked, usuario_id, username, rol, modulos_usados, ip, "
        "login_time, kicked_by, last_seen FROM sesiones_activas "
        "WHERE session_id=?", (sid,)).fetchone()

    if not row:
        conn.close()
        st.session_state.pop("_kick_deadline", None)
        return

    (kicked, uid, uname, rol, mods, ip, login_t, kicked_by, last_seen) = row

    if not kicked:
        conn.close()
        st.session_state.pop("_kick_deadline", None)
        _mostrar_tiempo_restante(last_seen)
        return

    # ── La sesión fue marcada para cierre (admin o inactividad) ──────────
    es_por_inactividad = bool(kicked_by) and kicked_by.startswith("Sistema")
    ahora = _ahora_co()
    deadline = st.session_state.get("_kick_deadline")
    if deadline is None:
        deadline = ahora + timedelta(seconds=SEGUNDOS_AVISO_CIERRE)
        st.session_state["_kick_deadline"] = deadline
    segundos_restantes = int((deadline - ahora).total_seconds())

    if segundos_restantes > 0:
        conn.close()
        mensaje = ("Tu sesión se va a cerrar automáticamente por "
                   "inactividad." if es_por_inactividad else
                   "Un administrador va a cerrar tu sesión en SolarCalc Pro.")
        _mostrar_aviso_cierre(mensaje, segundos_restantes)
        st.stop()

    motivo = "inactividad" if es_por_inactividad else "expulsada_por_admin"
    conn.execute("""
        INSERT INTO sesiones_historial
            (session_id, usuario_id, username, rol, modulos_usados, ip,
             login_time, fin_time, motivo_fin)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (sid, uid, uname, rol, mods, ip, login_t, _now(), motivo))
    conn.execute("DELETE FROM sesiones_activas WHERE session_id=?", (sid,))
    conn.commit()
    conn.close()

    mensaje_final = ("Tu sesión se cerró automáticamente por inactividad."
                      if es_por_inactividad else
                      "Un administrador cerró tu sesión en SolarCalc Pro.")
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
            {mensaje_final}<br>
            Vuelve a iniciar sesión para continuar.
        </div>
    </div>
    """, unsafe_allow_html=True)
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.stop()


def _auto_desconectar_inactivos(minutos: int = MINUTOS_INACTIVO):
    """Marca como expulsada ('kicked') cualquier sesión activa que lleve
    `minutos` sin registrar un latido y que todavía no esté marcada. El
    cierre real (mostrar el aviso, archivar en el historial y limpiar la
    fila) lo hace, igual que con una expulsión manual de un administrador,
    la propia sesión afectada en `verificar_expulsion()` — normalmente en
    segundos, gracias a la vigilancia periódica.

    Nota sobre qué cuenta como "inactividad" en Streamlit: no hay forma de
    detectar aquí, desde el servidor, que el usuario dejó de mover el
    mouse o el teclado; lo que sí se puede medir es cuánto hace que su
    sesión no vuelve a ejecutar el script (`last_seen`). En la práctica
    esto se acerca bastante a "inactividad real", porque los navegadores
    suelen pausar los temporizadores de una pestaña que quedó en segundo
    plano o se cerró, deteniendo también la vigilancia activa que
    mantiene viva la sesión."""
    limite = (_ahora_co() - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""
        UPDATE sesiones_activas
           SET kicked=1, kicked_by='Sistema (inactividad)', kicked_time=?
         WHERE kicked=0 AND last_seen < ?
    """, (_now(), limite))
    conn.commit()
    conn.close()


def _limpiar_sesiones_viejas(minutos: int = MINUTOS_INACTIVO + 30):
    """Red de seguridad secundaria: archiva definitivamente cualquier
    sesión —marcada para cierre o no— cuya última actividad sea demasiado
    vieja, incluso si esa sesión nunca vuelve a ejecutarse para
    auto-archivarse (p. ej. el navegador ya estaba cerrado cuando se le
    marcó como expulsada). Usa un margen más amplio que
    `_auto_desconectar_inactivos` para no competir con el aviso de cuenta
    regresiva que esa función le da la oportunidad de mostrar al usuario."""
    limite = (_ahora_co() - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    viejas = conn.execute(
        "SELECT session_id, usuario_id, username, rol, modulos_usados, ip, "
        "login_time, kicked, kicked_by FROM sesiones_activas "
        "WHERE last_seen < ?", (limite,)).fetchall()
    for (sid, uid, uname, rol, mods, ip, login_t, kicked, kicked_by) in viejas:
        if kicked and kicked_by and kicked_by.startswith("Sistema"):
            motivo = "inactividad"
        elif kicked:
            motivo = "expulsada_por_admin"
        else:
            motivo = "expirada"
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
# CHAT — mensajería entre administrador(es) y usuario
# ═══════════════════════════════════════════════════════════════════════════
# Cada usuario tiene UN solo hilo de conversación con "Administración": no
# importa cuál administrador responda, todos ven y contestan el mismo hilo
# (identificado por usuario_id). Así evitamos depender de si hay uno o
# varios administradores en el sistema.

def enviar_mensaje(usuario_id: int, usuario_username: str,
                    remitente: str, remitente_username: str, texto: str):
    """remitente: 'admin' o 'usuario'. Quien envía ya lo tiene 'leído'."""
    texto = (texto or "").strip()
    if not texto:
        return
    conn = get_conn()
    conn.execute("""
        INSERT INTO mensajes_chat
            (usuario_id, usuario_username, remitente, remitente_username,
             texto, fecha, leido_admin, leido_usuario)
        VALUES (?,?,?,?,?,?,?,?)
    """, (usuario_id, usuario_username, remitente, remitente_username, texto,
          _now(),
          1 if remitente == "admin" else 0,
          1 if remitente == "usuario" else 0))
    conn.commit()
    conn.close()


def obtener_hilo(usuario_id: int) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        "SELECT * FROM mensajes_chat WHERE usuario_id=? ORDER BY id", conn,
        params=(usuario_id,))
    conn.close()
    return df


def marcar_leido_admin(usuario_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE mensajes_chat SET leido_admin=1 "
        "WHERE usuario_id=? AND leido_admin=0", (usuario_id,))
    conn.commit()
    conn.close()


def marcar_leido_usuario(usuario_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE mensajes_chat SET leido_usuario=1 "
        "WHERE usuario_id=? AND leido_usuario=0", (usuario_id,))
    conn.commit()
    conn.close()


def eliminar_mensaje(mensaje_id: int):
    """Elimina un único mensaje del chat por su ID."""
    conn = get_conn()
    conn.execute("DELETE FROM mensajes_chat WHERE id=?", (mensaje_id,))
    conn.commit()
    conn.close()


def eliminar_hilo_completo(usuario_id: int) -> int:
    """Elimina TODOS los mensajes de la conversación con un usuario.
    Devuelve la cantidad de mensajes que fueron eliminados."""
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM mensajes_chat WHERE usuario_id=?",
        (usuario_id,)).fetchone()[0]
    conn.execute("DELETE FROM mensajes_chat WHERE usuario_id=?", (usuario_id,))
    conn.commit()
    conn.close()
    return total


def contar_no_leidos_usuario(usuario_id: int) -> int:
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM mensajes_chat "
        "WHERE usuario_id=? AND leido_usuario=0 AND remitente='admin'",
        (usuario_id,)).fetchone()[0]
    conn.close()
    return n


def _lista_hilos_para_admin() -> pd.DataFrame:
    """Usuarios con quienes existe (o existió) contacto: cualquiera que se
    haya conectado alguna vez (activo o en historial) o que ya tenga un
    hilo de mensajes, junto con su cantidad de mensajes sin leer."""
    conn = get_conn()
    personas = pd.read_sql("""
        SELECT usuario_id, username FROM sesiones_activas WHERE usuario_id IS NOT NULL
        UNION
        SELECT usuario_id, username FROM sesiones_historial WHERE usuario_id IS NOT NULL
        UNION
        SELECT usuario_id, usuario_username AS username FROM mensajes_chat
            WHERE usuario_id IS NOT NULL
    """, conn)
    no_leidos = pd.read_sql("""
        SELECT usuario_id, COUNT(*) AS no_leidos FROM mensajes_chat
        WHERE leido_admin=0 AND remitente='usuario'
        GROUP BY usuario_id
    """, conn)
    conn.close()
    if personas.empty:
        return personas
    personas = (personas.dropna(subset=["usuario_id"])
                .drop_duplicates(subset=["usuario_id"], keep="last")
                .merge(no_leidos, on="usuario_id", how="left"))
    personas["no_leidos"] = personas["no_leidos"].fillna(0).astype(int)
    personas = personas.sort_values(["no_leidos", "username"], ascending=[False, True])
    return personas


# ═══════════════════════════════════════════════════════════════════════════
# UI — Panel de administrador
# ═══════════════════════════════════════════════════════════════════════════
def _estado_conexion(last_seen_str: str):
    try:
        last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "⚪ Desconocido", TEXT2
    delta_min = (_ahora_co() - last_seen).total_seconds() / 60
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
            "Sin él, tanto al pulsar “Desconectar” como al desconectar "
            "automáticamente por inactividad, la sesión se cerrará hasta "
            "que ese usuario haga clic en algo, no de inmediato — y el "
            "contador de tiempo restante que ve el usuario no se actualizará "
            "solo. Instálalo con `pip install streamlit-autorefresh` y "
            "reinicia la app para que todo esto funcione en tiempo real.")

    _hilos_admin = _lista_hilos_para_admin()
    n_no_leidos_total = int(_hilos_admin["no_leidos"].sum()) if not _hilos_admin.empty else 0

    mt1, mt2, mt3, mt4 = st.tabs([
        "🟢 Conectados ahora", "📜 Historial de sesiones",
        "📁 Proyectos creados",
        f"💬 Mensajes{f' ({n_no_leidos_total})' if n_no_leidos_total else ''}",
    ])

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
                duracion = _tiempo_conectado(r["login_time"])
                es_propia = (r["session_id"] == st.session_state.get("_monitor_session_id"))
                cA, cB, cC, cD, cF, cE = st.columns([1.8, 1.4, 1.6, 1.3, 1.1, 1.2])
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
                with cF:
                    st.markdown(f"""<div style='font-size:0.78rem;color:{CYAN};'>
                        ⏱ {duracion}</div>""", unsafe_allow_html=True)
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
                "inactividad": "💤 Desconectada por inactividad",
                "expirada": "⏱ Expirada / cerró pestaña"
            }).fillna(hist["Motivo"])

            def _duracion_hist(row):
                try:
                    inicio = datetime.strptime(row["Conectado"], "%Y-%m-%d %H:%M:%S")
                    fin = datetime.strptime(row["Finalizó"], "%Y-%m-%d %H:%M:%S")
                    return _formatear_duracion((fin - inicio).total_seconds() / 60)
                except Exception:
                    return "—"

            hist.insert(hist.columns.get_loc("Finalizó") + 1, "Duración",
                        hist.apply(_duracion_hist, axis=1))

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

    # ══ TAB 4 — Mensajes / Chat con usuarios ═════════════════════════════════
    with mt4:
        if _hilos_admin.empty:
            st.info("Todavía no hay usuarios con quienes chatear. En cuanto "
                     "alguien se conecte a la aplicación aparecerá aquí.")
        else:
            def _etiqueta_usuario(row):
                base = row["username"] or "—"
                n = int(row["no_leidos"])
                if n:
                    plural = "s" if n != 1 else ""
                    return f"🔴 {base} ({n} nuevo{plural})"
                return base

            etiquetas = {
                int(row["usuario_id"]): _etiqueta_usuario(row)
                for _, row in _hilos_admin.iterrows()
            }
            ids_ordenados = list(etiquetas.keys())

            cS1, cS2 = st.columns([2, 4])
            with cS1:
                usuario_sel_id = st.selectbox(
                    "Conversación con:", ids_ordenados,
                    format_func=lambda i: etiquetas[i], key="chat_usuario_sel")

            if usuario_sel_id is not None:
                marcar_leido_admin(usuario_sel_id)
                hilo = obtener_hilo(usuario_sel_id)
                nombre_usuario = (_hilos_admin.loc[
                    _hilos_admin["usuario_id"] == usuario_sel_id, "username"]
                    .iloc[0] or "usuario")

                chat_box = st.container(height=380, border=True)
                with chat_box:
                    if hilo.empty:
                        st.caption("Aún no hay mensajes con este usuario. "
                                   "Escribe abajo para iniciar la conversación.")
                    for _, m in hilo.iterrows():
                        es_admin_msg = (m["remitente"] == "admin")
                        with st.chat_message("assistant" if es_admin_msg else "user",
                                              avatar="🛡️" if es_admin_msg else "👤"):
                            st.markdown(m["texto"])
                            cap_col, del_col = st.columns([6, 1])
                            with cap_col:
                                st.caption(
                                    f"{'Administración' if es_admin_msg else nombre_usuario} · {m['fecha']}")
                            with del_col:
                                if st.button("🗑", key=f"del_msg_{m['id']}",
                                             help="Eliminar este mensaje"):
                                    eliminar_mensaje(int(m["id"]))
                                    registrar_auditoria_fn(
                                        _u["id"], _u["username"], "ELIMINAR_MENSAJE",
                                        f"Mensaje eliminado de la conversación con '{nombre_usuario}'",
                                        "monitoreo")
                                    st.rerun()

                with st.expander("⚠ Vaciar conversación completa"):
                    st.caption("Esta acción borra permanentemente todos los "
                               f"mensajes intercambiados con {nombre_usuario}.")
                    confirmar_chat = st.checkbox(
                        "Confirmo que deseo eliminar TODA esta conversación",
                        key=f"confirmar_vaciar_chat_{usuario_sel_id}")
                    if st.button("🗑 Vaciar conversación",
                                  key=f"vaciar_chat_{usuario_sel_id}",
                                  disabled=not confirmar_chat):
                        total_eliminados = eliminar_hilo_completo(usuario_sel_id)
                        registrar_auditoria_fn(
                            _u["id"], _u["username"], "VACIAR_CONVERSACION",
                            f"Conversación con '{nombre_usuario}' vaciada por completo "
                            f"({total_eliminados} mensaje(s))", "monitoreo")
                        st.success("Conversación vaciada.")
                        st.rerun()

                nuevo_msg = st.chat_input(
                    f"Escribir a {nombre_usuario}…", key=f"chat_input_{usuario_sel_id}")
                if nuevo_msg:
                    enviar_mensaje(usuario_sel_id, nombre_usuario,
                                    "admin", _u["username"], nuevo_msg)
                    registrar_auditoria_fn(
                        _u["id"], _u["username"], "ENVIAR_MENSAJE",
                        f"Mensaje enviado a '{nombre_usuario}'", "monitoreo")
                    st.rerun()

    st.markdown(f"""
    <div style='margin-top:1rem;font-size:0.72rem;color:#4A5A75;text-align:center;'>
        Un usuario se considera "en línea" si tuvo actividad en los últimos {MINUTOS_EN_LINEA} min,
        "inactivo" hasta {MINUTOS_INACTIVO} min sin actividad; al llegar a ese punto se desconecta
        automáticamente (con un aviso de {SEGUNDOS_AVISO_CIERRE}s) y se archiva en el historial.
        Toda desconexión, manual o por inactividad, se aplica en segundos gracias a la vigilancia activa.
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# UI — Widget de chat para el usuario normal (responder a Administración)
# ═══════════════════════════════════════════════════════════════════════════
def mostrar_widget_chat_usuario(usuario_activo_fn=None, tiene_permiso_fn=None):
    """Muestra, para cualquier usuario NO administrador, un panel compacto
    (pensado para el sidebar) donde puede ver los mensajes que le ha
    enviado Administración y responder. Los administradores no ven este
    widget: ellos usan la pestaña "💬 Mensajes" del monitor."""
    from modulo_seguridad import tiene_permiso, usuario_activo
    tiene_permiso_fn  = tiene_permiso_fn or tiene_permiso
    usuario_activo_fn = usuario_activo_fn or usuario_activo

    _u = usuario_activo_fn()
    if not _u or tiene_permiso_fn("ver_usuarios"):
        return  # los administradores no necesitan este widget

    init_monitoreo_db()
    n_nuevos = contar_no_leidos_usuario(_u["id"])
    etiqueta = f"💬 Mensajes de Administración{f' ({n_nuevos})' if n_nuevos else ''}"

    with st.expander(etiqueta, expanded=bool(n_nuevos)):
        hilo = obtener_hilo(_u["id"])
        marcar_leido_usuario(_u["id"])

        chat_box = st.container(height=280, border=True)
        with chat_box:
            if hilo.empty:
                st.caption("No tienes mensajes todavía. Si necesitas ayuda, "
                           "escríbele a Administración aquí abajo.")
            for _, m in hilo.iterrows():
                es_admin_msg = (m["remitente"] == "admin")
                with st.chat_message("assistant" if es_admin_msg else "user",
                                      avatar="🛡️" if es_admin_msg else "👤"):
                    st.markdown(m["texto"])
                    if es_admin_msg:
                        st.caption(f"Administración · {m['fecha']}")
                    else:
                        cap_col, del_col = st.columns([6, 1])
                        with cap_col:
                            st.caption(f"Tú · {m['fecha']}")
                        with del_col:
                            if st.button("🗑", key=f"del_msg_user_{m['id']}",
                                         help="Eliminar este mensaje"):
                                eliminar_mensaje(int(m["id"]))
                                st.rerun()

        nuevo_msg = st.chat_input("Escribe tu mensaje…", key="chat_input_usuario")
        if nuevo_msg:
            enviar_mensaje(_u["id"], _u["username"], "usuario", _u["username"], nuevo_msg)
            st.rerun()
