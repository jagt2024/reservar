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
import io
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


def obtener_resumen_proyecto(proyecto_id: int) -> dict:
    """Trae un resumen técnico completo del proyecto dimensionado:
    datos básicos, cargas registradas, panel seleccionado, el último
    cálculo de dimensionamiento (tabla `resultados`) y el recibo de
    energía de referencia, si existen. Es tolerante a que alguna de estas
    tablas no exista o tenga columnas distintas en tu base de datos —
    nunca lanza una excepción, simplemente omite esa parte del resumen."""
    resumen = {
        "proyecto": None, "num_cargas": 0, "consumo_cargas_wh": 0.0,
        "panel": None, "resultado": None, "recibo": None,
    }
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
        resumen["proyecto"] = dict(row) if row else None
    except Exception:
        pass

    try:
        cargas = conn.execute(
            "SELECT cantidad, potencia_w, horas_dia FROM cargas WHERE proyecto_id=?",
            (proyecto_id,)).fetchall()
        resumen["num_cargas"] = len(cargas)
        resumen["consumo_cargas_wh"] = sum(
            (c["cantidad"] or 0) * (c["potencia_w"] or 0) * (c["horas_dia"] or 0)
            for c in cargas)
    except Exception:
        pass

    try:
        panel = conn.execute(
            "SELECT * FROM paneles WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
            (proyecto_id,)).fetchone()
        resumen["panel"] = dict(panel) if panel else None
    except Exception:
        pass

    try:
        resultado = conn.execute(
            "SELECT * FROM resultados WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
            (proyecto_id,)).fetchone()
        resumen["resultado"] = dict(resultado) if resultado else None
    except Exception:
        pass

    try:
        recibo = conn.execute(
            "SELECT * FROM recibos WHERE proyecto_id=? ORDER BY id DESC LIMIT 1",
            (proyecto_id,)).fetchone()
        resumen["recibo"] = dict(recibo) if recibo else None
    except Exception:
        pass

    conn.close()
    return resumen


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
# EXPORTAR / IMPORTAR
# ═══════════════════════════════════════════════════════════════════════════
def obtener_interacciones_de(cliente_ids: list) -> pd.DataFrame:
    """Todas las interacciones de un conjunto de clientes (para exportar
    exactamente lo que el usuario puede ver en el CRM)."""
    if not cliente_ids:
        return pd.DataFrame()
    conn = get_conn()
    marcador = ",".join("?" * len(cliente_ids))
    df = pd.read_sql(
        f"SELECT * FROM interacciones_clientes WHERE cliente_id IN ({marcador}) "
        f"ORDER BY cliente_id, fecha", conn, params=cliente_ids)
    conn.close()
    return df


def obtener_tareas_de(cliente_ids: list) -> pd.DataFrame:
    """Todas las tareas de un conjunto de clientes (para exportar)."""
    if not cliente_ids:
        return pd.DataFrame()
    conn = get_conn()
    marcador = ",".join("?" * len(cliente_ids))
    df = pd.read_sql(
        f"SELECT * FROM tareas_clientes WHERE cliente_id IN ({marcador}) "
        f"ORDER BY cliente_id, fecha_limite", conn, params=cliente_ids)
    conn.close()
    return df


def _generar_excel(df_clientes: pd.DataFrame, df_inter: pd.DataFrame,
                    df_tareas: pd.DataFrame) -> bytes:
    """Arma un .xlsx en memoria con una hoja por tabla del CRM. Siempre
    incluye la columna 'id' de cada registro para que, si el archivo se
    vuelve a cargar más adelante, los clientes existentes se actualicen en
    vez de duplicarse."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        (df_clientes if not df_clientes.empty
         else pd.DataFrame(columns=["id", "nombre"])).to_excel(
            writer, sheet_name="Clientes", index=False)
        (df_inter if not df_inter.empty
         else pd.DataFrame(columns=["id", "cliente_id"])).to_excel(
            writer, sheet_name="Interacciones", index=False)
        (df_tareas if not df_tareas.empty
         else pd.DataFrame(columns=["id", "cliente_id"])).to_excel(
            writer, sheet_name="Tareas", index=False)
    return buffer.getvalue()


def _generar_csv(df: pd.DataFrame) -> bytes:
    """CSV con codificación utf-8-sig para que Excel en Windows muestre
    bien las tildes y la ñ al abrirlo directamente."""
    return df.to_csv(index=False).encode("utf-8-sig")


COLUMNAS_IMPORT_CLIENTE = [
    "nombre", "tipo_persona", "documento", "email", "telefono", "direccion",
    "municipio", "departamento", "etapa", "fuente", "valor_estimado", "notas",
]


def importar_clientes_df(df: pd.DataFrame, usuario: dict, es_admin: bool) -> dict:
    """Crea o actualiza clientes a partir de un DataFrame (leído de un
    .xlsx o .csv exportado desde este mismo módulo, u otro archivo con las
    mismas columnas). Si una fila trae un 'id' que corresponde a un
    cliente existente sobre el que el usuario tiene permiso, se actualiza;
    si no, se crea un cliente nuevo (asignado a quien importa)."""
    resumen = {"creados": 0, "actualizados": 0, "omitidos": 0, "errores": []}
    if df is None or df.empty:
        resumen["errores"].append("El archivo está vacío.")
        return resumen
    if "nombre" not in df.columns:
        resumen["errores"].append(
            "El archivo no tiene una columna 'nombre'. Usa el archivo tal como se "
            "descarga desde “⬇ Descargar información”.")
        return resumen

    for _, fila in df.iterrows():
        nombre = str(fila.get("nombre", "") or "").strip()
        if not nombre or nombre.lower() == "nan":
            resumen["omitidos"] += 1
            continue

        datos = {}
        for col in COLUMNAS_IMPORT_CLIENTE:
            val = fila.get(col, "") if col in df.columns else ""
            if pd.isna(val):
                val = ""
            datos[col] = val
        datos["nombre"] = nombre
        try:
            datos["valor_estimado"] = float(fila.get("valor_estimado", 0) or 0)
        except (TypeError, ValueError):
            datos["valor_estimado"] = 0.0
        if datos.get("etapa") not in ETAPAS:
            datos["etapa"] = "Lead"

        cliente_existente = None
        id_val = fila.get("id") if "id" in df.columns else None
        if id_val is not None and not pd.isna(id_val):
            try:
                cliente_existente = obtener_cliente(int(id_val))
            except (TypeError, ValueError):
                cliente_existente = None

        if cliente_existente and (es_admin or cliente_existente["propietario_id"] == usuario["id"]):
            actualizar_cliente(int(id_val), datos)
            resumen["actualizados"] += 1
        else:
            crear_cliente(datos, usuario)
            resumen["creados"] += 1

    return resumen


# ═══════════════════════════════════════════════════════════════════════════
# ENVÍO DE CORREO ELECTRÓNICO
# ═══════════════════════════════════════════════════════════════════════════
# Requiere: pip install yagmail
# Credenciales de la cuenta remitente (una contraseña de aplicación de
# Gmail, no la contraseña normal de la cuenta) en st.secrets, con esta forma:
#
#   [emails]
#   smtp_user = "tu_cuenta@gmail.com"
#   smtp_password = "xxxx xxxx xxxx xxxx"
#
# No se leen a nivel de módulo (a diferencia del ejemplo original) para que
# el CRM no se caiga entero si todavía no se han configurado esos secrets en
# este despliegue: `_credenciales_email()` los busca en el momento de enviar
# y, si faltan, `enviar_email()` devuelve un mensaje de error claro en vez
# de una excepción sin manejar.
def _credenciales_email():
    try:
        return st.secrets["emails"]["smtp_user"], st.secrets["emails"]["smtp_password"]
    except Exception:
        return None, None


def email_configurado() -> bool:
    smtp_user, smtp_pass = _credenciales_email()
    return bool(smtp_user and smtp_pass)


def enviar_email(destinatario: str, asunto: str, cuerpo: str,
                  adjunto_bytes: bytes = None, nombre_adjunto: str = None,
                  email_from: str = None, nombre_from: str = None):
    """
    Envía un correo (con o sin adjunto) usando yagmail (Gmail).

    Parámetros:
        destinatario     — dirección de correo del destinatario.
        asunto           — asunto del mensaje.
        cuerpo           — cuerpo en texto plano o HTML.
        adjunto_bytes    — contenido del archivo a adjuntar (bytes), opcional.
        nombre_adjunto   — nombre visible del archivo adjunto, p. ej.
                            "ficha_cliente.xlsx". Se respeta tal cual porque
                            el adjunto se escribe con ese mismo nombre en un
                            directorio temporal (no con un nombre aleatorio).
        email_from       — correo que se muestra como remitente visible.
        nombre_from      — nombre visible del remitente.

    Retorna (True, "") si el envío fue exitoso, o (False, mensaje_de_error)
    en caso contrario — nunca lanza una excepción hacia quien la llama.
    """
    smtp_user, smtp_pass = _credenciales_email()
    if not smtp_user or not smtp_pass:
        return False, ("El envío de correo no está configurado en este despliegue. "
                        "Agrega st.secrets['emails']['smtp_user'] y ['smtp_password'] "
                        "(una contraseña de aplicación de Gmail).")
    if not destinatario or "@" not in destinatario:
        return False, "El destinatario no tiene un correo válido."

    import tempfile, os
    tmp_dir = None
    tmp_path = None
    try:
        if adjunto_bytes is not None:
            # yagmail requiere una ruta de archivo real, no bytes en memoria.
            # Se usa un directorio temporal propio (en vez de
            # NamedTemporaryFile) para poder conservar el nombre exacto que
            # verá el destinatario, en lugar de un nombre aleatorio.
            tmp_dir = tempfile.mkdtemp(prefix="crm_mail_")
            tmp_path = os.path.join(tmp_dir, nombre_adjunto or "adjunto.dat")
            with open(tmp_path, "wb") as f:
                f.write(adjunto_bytes)

        import yagmail
        yag = yagmail.SMTP(user=smtp_user, password=smtp_pass,
                            smtp_starttls=True, smtp_ssl=False)
        # Se autentica con smtp_user/smtp_pass, pero el campo "De" visible en
        # el correo puede mostrar otro nombre/correo (p. ej. el del asesor).
        kwargs = dict(to=destinatario, subject=asunto, contents=cuerpo)
        if tmp_path:
            kwargs["attachments"] = tmp_path
        if email_from:
            kwargs["headers"] = {
                "From": f"{nombre_from} <{email_from}>" if nombre_from else email_from
            }

        yag.send(**kwargs)
        return True, ""
    except ModuleNotFoundError:
        return False, "Falta instalar la librería yagmail (`pip install yagmail`)."
    except Exception as e:
        return False, str(e)
    finally:
        # Limpieza garantizada del archivo y directorio temporal.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if tmp_dir and os.path.isdir(tmp_dir):
            try:
                os.rmdir(tmp_dir)
            except Exception:
                pass


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

    tabP, tabL, tabN, tabT, tabM, tabE = st.tabs([
        "🗂 Pipeline", "👥 Clientes", "➕ Nuevo cliente", "🗓 Tareas", "📊 Métricas",
        "⬇⬆ Exportar / Importar",
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

    with tabE:
        _mostrar_exportar_importar(df_clientes, _u, es_admin, registrar_auditoria_fn)


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


def _mostrar_resumen_proyecto(resumen: dict):
    """Renderiza el resumen técnico completo de un proyecto dimensionado
    dentro de la pestaña de Proyectos de un cliente."""
    p = resumen.get("proyecto") or {}
    r = resumen.get("resultado")
    panel = resumen.get("panel")
    recibo = resumen.get("recibo")

    if not r and not panel and not resumen.get("num_cargas") and not recibo:
        st.caption("Este proyecto todavía no tiene un dimensionamiento calculado.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**☀ HSP:** {p.get('hsp') or '—'} h/día")
        st.markdown(f"**⚡ Tensión del sistema:** {p.get('tension_dc') or '—'} V")
    with c2:
        st.markdown(f"**📅 Creado:** {p.get('creado') or '—'}")
        if resumen.get("num_cargas"):
            st.markdown(f"**🔌 Cargas registradas:** {resumen['num_cargas']} "
                        f"· {resumen['consumo_cargas_wh']:,.0f} Wh/día estimados")

    if r:
        st.markdown(f"""
        <div class='metric-grid'>
            <div class='metric-box'><div class='metric-val' style='color:{CYAN};font-size:1.1rem;'>
                {(r.get('consumo_dia_wh') or 0):,.0f}</div>
                <div class='metric-unit'>Wh/día</div><div class='metric-label'>CONSUMO BASE</div></div>
            <div class='metric-box'><div class='metric-val' style='color:{SOL};font-size:1.1rem;'>
                {(r.get('consumo_con_fs') or 0):,.0f}</div>
                <div class='metric-unit'>Wh/día</div><div class='metric-label'>CON FACTOR SEGURIDAD</div></div>
            <div class='metric-box'><div class='metric-val' style='color:{YEL};font-size:1.1rem;'>
                {(r.get('potencia_instalada_w') or 0):,.0f}</div>
                <div class='metric-unit'>W</div><div class='metric-label'>POTENCIA INSTALADA</div></div>
            <div class='metric-box'><div class='metric-val' style='color:{GREEN};'>
                {int(r.get('num_paneles') or 0)}</div>
                <div class='metric-unit'>paneles</div><div class='metric-label'>CANTIDAD</div></div>
        </div>""", unsafe_allow_html=True)

        if r.get("num_baterias"):
            st.markdown(f"""
            <div class='metric-grid'>
                <div class='metric-box'><div class='metric-val' style='color:{PUR};'>
                    {int(r.get('num_baterias') or 0)}</div>
                    <div class='metric-unit'>baterías</div><div class='metric-label'>CANTIDAD</div></div>
                <div class='metric-box'><div class='metric-val' style='color:{PUR};font-size:1.1rem;'>
                    {(r.get('capacidad_baterias_ah') or 0):,.0f}</div>
                    <div class='metric-unit'>Ah</div><div class='metric-label'>CAPACIDAD</div></div>
                <div class='metric-box'><div class='metric-val' style='color:{CYAN};font-size:1.1rem;'>
                    {(r.get('corriente_mppt') or 0):,.1f}</div>
                    <div class='metric-unit'>A</div><div class='metric-label'>CORRIENTE MPPT</div></div>
            </div>""", unsafe_allow_html=True)

        st.caption(f"Último cálculo de dimensionamiento: {r.get('generado') or '—'}")
    else:
        st.caption("Este proyecto todavía no tiene un cálculo de dimensionamiento guardado.")

    if panel:
        st.markdown(f"**🔋 Panel seleccionado:** {panel.get('modelo') or '—'} "
                    f"({(panel.get('potencia_wp') or 0):.0f} Wp · "
                    f"Voc {(panel.get('voc') or 0):.1f} V · "
                    f"Isc {(panel.get('isc') or 0):.1f} A)")

    if recibo:
        texto_recibo = (f"**🧾 Recibo de referencia:** "
                        f"{(recibo.get('kwh_periodo') or 0):,.0f} kWh en "
                        f"{recibo.get('dias_periodo') or 30} días")
        if recibo.get("estrato"):
            texto_recibo += f" · Estrato {recibo['estrato']}"
        if recibo.get("periodo"):
            texto_recibo += f" · Periodo {recibo['periodo']}"
        st.markdown(texto_recibo)


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

    dtab1, dtab2, dtab3, dtab4, dtab5, dtab6 = st.tabs(
        ["ℹ Datos", "📈 Etapa", "📁 Proyectos", "🗒 Interacciones", "✅ Tareas", "✉ Correo"])

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

                with st.expander(f"📊 Ver resumen del dimensionamiento — #{p['id']} {p['nombre']}"):
                    resumen_p = obtener_resumen_proyecto(int(p["id"]))
                    _mostrar_resumen_proyecto(resumen_p)

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

    # ── Enviar correo al cliente ────────────────────────────────────────────
    with dtab6:
        if not email_configurado():
            st.markdown("""
            <div class='warn-box'>⚠ El envío de correo no está configurado en este
            despliegue. Un administrador debe agregar
            <code>st.secrets['emails']['smtp_user']</code> y
            <code>['smtp_password']</code> (una contraseña de aplicación de Gmail).</div>
            """, unsafe_allow_html=True)

        if not c["email"]:
            st.warning("Este cliente no tiene un correo registrado. Agrégalo en "
                       "la pestaña “ℹ Datos” para poder escribirle.")
        else:
            st.caption(f"Se enviará a: **{c['email']}**")
            with st.form(f"form_email_{cliente_id}"):
                asunto = st.text_input("Asunto", value=f"SolarCalc Pro — {c['nombre']}",
                                        key=f"asunto_email_{cliente_id}")
                cuerpo = st.text_area(
                    "Mensaje", height=140,
                    value=f"Hola {c['nombre']},\n\nTe escribo desde SolarCalc Pro "
                          f"con relación a tu proyecto solar.\n\nQuedo atento.\n\n"
                          f"{usuario['username']}",
                    key=f"cuerpo_email_{cliente_id}")
                adjuntar_ficha = st.checkbox(
                    "Adjuntar ficha del cliente (Excel: datos, interacciones y tareas)",
                    key=f"adjuntar_ficha_{cliente_id}")
                adjunto_extra = st.file_uploader(
                    "O adjuntar otro archivo (cotización, PDF, etc.)",
                    key=f"adjunto_email_{cliente_id}")
                enviar = st.form_submit_button("✉ Enviar correo", use_container_width=True,
                                                disabled=not puede_editar)

            if enviar:
                if not asunto.strip() or not cuerpo.strip():
                    st.error("Completa el asunto y el mensaje.")
                else:
                    adjunto_bytes = nombre_adj = None
                    if adjunto_extra is not None:
                        adjunto_bytes = adjunto_extra.getvalue()
                        nombre_adj = adjunto_extra.name
                    elif adjuntar_ficha:
                        df_uno = pd.DataFrame([c])
                        adjunto_bytes = _generar_excel(
                            df_uno, obtener_interacciones(cliente_id),
                            obtener_tareas(cliente_id=cliente_id))
                        nombre_seguro = "".join(
                            ch if ch.isalnum() else "_" for ch in (c["nombre"] or "cliente"))
                        nombre_adj = f"ficha_{nombre_seguro}.xlsx"

                    ok, error = enviar_email(
                        destinatario=c["email"], asunto=asunto.strip(), cuerpo=cuerpo,
                        adjunto_bytes=adjunto_bytes, nombre_adjunto=nombre_adj,
                        email_from=usuario.get("email"), nombre_from=usuario["username"])
                    if ok:
                        detalle_int = f"Correo enviado: '{asunto.strip()}'"
                        if nombre_adj:
                            detalle_int += f" (adjunto: {nombre_adj})"
                        registrar_interaccion(cliente_id, "✉ Email", detalle_int, usuario)
                        registrar_auditoria_fn(
                            usuario["id"], usuario["username"], "ENVIAR_EMAIL_CLIENTE",
                            f"Correo enviado a cliente #{cliente_id} ({c['email']})",
                            "clientes")
                        st.success("✓ Correo enviado y registrado en el historial de "
                                   "interacciones.")
                        st.rerun()
                    else:
                        st.error(f"No se pudo enviar el correo: {error}")


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


def _mostrar_exportar_importar(df_clientes, usuario, es_admin, registrar_auditoria_fn):
    # ── Descargar ──────────────────────────────────────────────────────────
    st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
        font-weight:600;margin-bottom:0.4rem;'>⬇ DESCARGAR INFORMACIÓN</div>""",
        unsafe_allow_html=True)
    st.caption(
        "Descarga toda la información capturada del CRM que puedes ver "
        f"({'todos los clientes' if es_admin else 'tus clientes asignados'}), incluyendo "
        "interacciones y tareas. Cada registro conserva su 'id', así que si vuelves a "
        "cargar el archivo más adelante se actualizan los clientes existentes en vez de "
        "duplicarlos.")

    cliente_ids = df_clientes["id"].astype(int).tolist() if not df_clientes.empty else []
    df_inter = obtener_interacciones_de(cliente_ids)
    df_tareas = obtener_tareas_de(cliente_ids)

    colx1, colx2 = st.columns(2)
    with colx1:
        st.download_button(
            "📊 Descargar todo en Excel (.xlsx)",
            data=_generar_excel(df_clientes, df_inter, df_tareas),
            file_name=f"crm_clientes_{_hoy()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="dl_excel_crm")
    with colx2:
        st.download_button(
            "📄 Descargar clientes en CSV (.csv)",
            data=_generar_csv(df_clientes if not df_clientes.empty
                               else pd.DataFrame(columns=["id", "nombre"])),
            file_name=f"crm_clientes_{_hoy()}.csv", mime="text/csv",
            use_container_width=True, key="dl_csv_crm")

    if not df_inter.empty or not df_tareas.empty:
        with st.expander("Descargar interacciones y tareas por separado (CSV)"):
            ce1, ce2 = st.columns(2)
            with ce1:
                if not df_inter.empty:
                    st.download_button(
                        "🗒 Interacciones (.csv)", data=_generar_csv(df_inter),
                        file_name=f"crm_interacciones_{_hoy()}.csv", mime="text/csv",
                        use_container_width=True, key="dl_inter_csv")
                else:
                    st.caption("Sin interacciones registradas.")
            with ce2:
                if not df_tareas.empty:
                    st.download_button(
                        "✅ Tareas (.csv)", data=_generar_csv(df_tareas),
                        file_name=f"crm_tareas_{_hoy()}.csv", mime="text/csv",
                        use_container_width=True, key="dl_tareas_csv")
                else:
                    st.caption("Sin tareas registradas.")

    # ── Enviar por correo ──────────────────────────────────────────────────
    st.markdown("<hr class='sep'>", unsafe_allow_html=True)
    st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
        font-weight:600;margin-bottom:0.4rem;'>✉ ENVIAR POR CORREO</div>""",
        unsafe_allow_html=True)
    st.caption("Envía el Excel con toda la información (clientes, interacciones y "
               "tareas) a una dirección de correo, por ejemplo para respaldarla o "
               "compartirla con un compañero.")

    if not email_configurado():
        st.markdown("""
        <div class='warn-box'>⚠ El envío de correo no está configurado en este
        despliegue. Un administrador debe agregar
        <code>st.secrets['emails']['smtp_user']</code> y
        <code>['smtp_password']</code> (una contraseña de aplicación de Gmail).</div>
        """, unsafe_allow_html=True)

    with st.form("form_email_export"):
        dest_export = st.text_input("Correo destino")
        asunto_export = st.text_input("Asunto", value=f"CRM SolarCalc Pro — Exportación {_hoy()}")
        enviar_export = st.form_submit_button("✉ Enviar Excel por correo",
                                               use_container_width=True)
    if enviar_export:
        if not dest_export.strip():
            st.error("Escribe un correo destino.")
        else:
            ok, error = enviar_email(
                destinatario=dest_export.strip(), asunto=asunto_export.strip(),
                cuerpo="Adjunto la exportación del CRM de SolarCalc Pro.",
                adjunto_bytes=_generar_excel(df_clientes, df_inter, df_tareas),
                nombre_adjunto=f"crm_clientes_{_hoy()}.xlsx",
                email_from=usuario.get("email"), nombre_from=usuario["username"])
            if ok:
                registrar_auditoria_fn(
                    usuario["id"], usuario["username"], "ENVIAR_EMAIL_EXPORT_CRM",
                    f"Exportación del CRM enviada por correo a {dest_export.strip()}",
                    "clientes")
                st.success("✓ Correo enviado.")
            else:
                st.error(f"No se pudo enviar el correo: {error}")

    # ── Cargar / restaurar ─────────────────────────────────────────────────
    st.markdown("<hr class='sep'>", unsafe_allow_html=True)
    st.markdown("""<div style='color:#FFB300;font-family:Rajdhani,sans-serif;
        font-weight:600;margin-bottom:0.4rem;'>⬆ CARGAR CLIENTES</div>""",
        unsafe_allow_html=True)
    st.caption(
        "Sube un archivo .xlsx (con hoja 'Clientes') o .csv exportado desde aquí, o "
        "cualquier archivo con las mismas columnas (nombre, tipo_persona, documento, "
        "email, telefono, direccion, municipio, departamento, etapa, fuente, "
        "valor_estimado, notas). Si una fila trae un 'id' que ya existe y tienes permiso "
        "sobre ese cliente, se actualiza; si no, se crea como un cliente nuevo.")

    archivo = st.file_uploader("Archivo .xlsx o .csv", type=["xlsx", "csv"],
                                key="crm_uploader")
    if archivo is not None:
        df_import = None
        try:
            if archivo.name.lower().endswith(".csv"):
                df_import = pd.read_csv(archivo)
            else:
                xls = pd.ExcelFile(archivo)
                hoja = "Clientes" if "Clientes" in xls.sheet_names else xls.sheet_names[0]
                df_import = pd.read_excel(xls, sheet_name=hoja)
            df_import.columns = [str(c).strip() for c in df_import.columns]
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

        if df_import is not None and not df_import.empty:
            st.markdown(f"**Vista previa** ({len(df_import)} fila(s)):")
            st.dataframe(df_import.head(20), use_container_width=True, hide_index=True)
            if st.button("⬆ Confirmar carga", use_container_width=True,
                         key="crm_confirmar_import"):
                resumen = importar_clientes_df(df_import, usuario, es_admin)
                registrar_auditoria_fn(
                    usuario["id"], usuario["username"], "IMPORTAR_CLIENTES",
                    f"Importación CRM: {resumen['creados']} creados, "
                    f"{resumen['actualizados']} actualizados, "
                    f"{resumen['omitidos']} omitidos", "clientes")
                if resumen["errores"]:
                    for err in resumen["errores"]:
                        st.error(err)
                else:
                    st.success(
                        f"✓ {resumen['creados']} cliente(s) creado(s), "
                        f"{resumen['actualizados']} actualizado(s), "
                        f"{resumen['omitidos']} omitido(s) por no tener nombre.")
                    st.rerun()
        elif df_import is not None:
            st.warning("El archivo no tiene filas para importar.")
