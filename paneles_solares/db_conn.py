# ══════════════════════════════════════════════════════════════════════════
# db_conn.py — CAPA DE COMPATIBILIDAD sqlite3 → Turso (libSQL)
# ------------------------------------------------------------------------
# Streamlit Community Cloud NO ofrece disco persistente: cualquier archivo
# escrito en tiempo de ejecución (incluyendo un .db de sqlite3 local) se
# pierde cada vez que el contenedor se reinicia (inactividad, redeploy,
# límites de recursos). Turso es un servicio de base de datos compatible
# con SQLite (mismo motor, mismo SQL) pero con almacenamiento persistente
# real en la nube, accesible por red.
#
# Este módulo imita la API de sqlite3.Connection / sqlite3.Cursor para que
# el resto del código de la app casi no tenga que cambiar: donde antes había
#       import sqlite3
#       conn = sqlite3.connect(DB_PATH)
# ahora hay
#       import db_conn
#       conn = db_conn.connect()
# y todo lo demás sigue funcionando igual, incluyendo:
#   - cursor(), execute(sql, params), fetchone()/fetchall()/fetchmany()
#   - commit(), close(), rollback() (no-ops: ver notas abajo)
#   - executemany() — tanto en Connection como en Cursor
#   - conn.row_factory = sqlite3.Row  →  filas accesibles por índice O por
#     nombre de columna (fila[0] y fila["columna"]), igual que sqlite3.Row
#   - cursor.description  →  compatible con pandas.read_sql(sql, conn)
#   - excepciones: los errores de integridad (UNIQUE, etc.) se relanzan
#     como sqlite3.IntegrityError, y el resto como sqlite3.OperationalError,
#     para que el código existente que hace
#         except sqlite3.IntegrityError: ...
#     siga funcionando SIN modificarse.
#   - Binary(x) — equivalente a sqlite3.Binary(x) para columnas BLOB
#
# CONFIGURACIÓN NECESARIA (una sola vez):
#   1) Crea una base de datos gratuita en https://turso.tech (o con su CLI).
#   2) Obtén la URL y el auth token. Usa la URL con esquema "https://"
#      (si Turso te la da como "libsql://...", este módulo la normaliza
#      solo — ver _normalizar_url_turso).
#   3) En Streamlit Community Cloud: panel de tu app → Settings → Secrets,
#      agrega:
#           TURSO_DATABASE_URL = "https://tu-base-xxxx.turso.io"
#           TURSO_AUTH_TOKEN   = "tu-token-aqui"
#      (En local, puedes usar variables de entorno con los mismos nombres,
#      o un archivo .streamlit/secrets.toml con esas mismas claves.)
#
# NO depende del paquete `libsql-client`: habla directamente el protocolo
# HTTP de Turso (Hrana v2, endpoint /v2/pipeline) con la librería estándar
# de Python. Esto se decidió después de que `libsql-client` fallara de dos
# formas distintas y opacas contra el servidor real (handshake de WebSocket,
# y luego un HTTP 400 sin mostrar el cuerpo de la respuesta). Este cliente
# propio SIEMPRE muestra el cuerpo exacto de la respuesta del servidor
# cuando algo falla.
#
# LIMITACIÓN CONOCIDA: la clasificación de errores en IntegrityError vs.
# OperationalError se hace revisando si la palabra "constraint" aparece en
# el código/mensaje de error que devuelve Turso (ver _traducir_error). Esto
# coincide con el formato estándar de SQLite ("UNIQUE constraint failed: ...",
# "SQLITE_CONSTRAINT..."), pero no se pudo verificar contra un servidor Turso
# real desde este entorno de desarrollo — si algún `except sqlite3.IntegrityError`
# no llegara a dispararse en producción, avisa para ajustar la heurística.
# ══════════════════════════════════════════════════════════════════════════

import base64
import json
import os
import sqlite3  # SOLO para reutilizar sus clases de excepción y sqlite3.Row;
                 # ya no se usa sqlite3.connect() en ningún lado de este módulo.
import threading
import urllib.error
import urllib.request

try:
    import streamlit as st
except ImportError:  # por si algún script usa este módulo fuera de Streamlit
    st = None


# ══════════════════════════════════════════════════════════════════════════
# CLIENTE HTTP PROPIO PARA TURSO (protocolo Hrana v2 sobre HTTP)
# ------------------------------------------------------------------------
# Se usó primero el paquete oficial `libsql-client`, pero dio DOS fallos
# distintos y opacos contra el servidor real de Turso:
#   1) WSServerHandshakeError (400) al usar el transporte WebSocket.
#   2) LibsqlError: "SERVER_ERROR: Server returned HTTP status 400" al usar
#      el transporte HTTP — sin mostrar el cuerpo real de la respuesta del
#      servidor, que es justo donde está la pista de qué falla.
#
# Este cliente propio habla directamente el protocolo documentado por Turso
# (Hrana v2, endpoint POST {url}/v2/pipeline) usando solo la librería
# estándar de Python (urllib + json + base64) — sin depender de terceros, y
# SIEMPRE mostrando el cuerpo exacto de la respuesta cuando algo falla.
# Referencia del protocolo: https://github.com/tursodatabase/libsql/blob/main/docs/HRANA_3_SPEC.md
# ══════════════════════════════════════════════════════════════════════════

class LibsqlError(RuntimeError):
    """Error del servidor Turso/Hrana. Tiene los mismos atributos (code,
    explanation) que libsql_client.LibsqlError, para no romper nada que ya
    dependa de ese nombre/forma."""
    def __init__(self, message: str, code: str = "UNKNOWN"):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.explanation = message


def _valor_a_hrana(v):
    """Convierte un valor Python al formato de valor Hrana (para enviar)."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):           # bool es subclase de int: revisar ANTES que int
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode("ascii")}
    return {"type": "text", "value": str(v)}


def _valor_de_hrana(d):
    """Convierte un valor Hrana (recibido) a un valor Python nativo."""
    tipo = d.get("type")
    if tipo == "null":
        return None
    if tipo == "integer":
        return int(d["value"])
    if tipo == "float":
        return float(d["value"])
    if tipo == "text":
        return d["value"]
    if tipo == "blob":
        return base64.b64decode(d["base64"])
    return d.get("value")


class _HranaResultSet:
    """Misma forma que libsql_client.ResultSet: .rows, .columns,
    .rows_affected, .last_insert_rowid — para no tener que cambiar nada
    en _Cursor más abajo."""
    def __init__(self, columns, rows, rows_affected, last_insert_rowid):
        self.columns = columns
        self.rows = rows
        self.rows_affected = rows_affected
        self.last_insert_rowid = last_insert_rowid


class ClienteTursoHTTP:
    """
    Cliente HTTP mínimo y transparente para Turso/Hrana v2. Implementa
    execute(sql, args), batch(stmts) y close() — la misma interfaz que
    usaba libsql_client.ClientSync, así que _Cursor/Connection más abajo
    no necesitan cambiar.
    """
    def __init__(self, url: str, auth_token: str, timeout: float = 15.0):
        self._endpoint = url.rstrip("/") + "/v2/pipeline"
        self._token = auth_token
        self._timeout = timeout
        self.closed = False

    def _post(self, requests_hrana: list) -> dict:
        body = json.dumps({"baton": None, "requests": requests_hrana}).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            })
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                crudo = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            crudo_error = e.read().decode("utf-8", errors="replace")
            raise LibsqlError(
                f"El servidor Turso respondió HTTP {e.code} en {self._endpoint}. "
                f"Cuerpo de la respuesta: {crudo_error[:1000]}",
                f"HTTP_{e.code}",
            ) from e
        except urllib.error.URLError as e:
            raise LibsqlError(
                f"No se pudo conectar a {self._endpoint}: {e.reason}", "CONNECTION_ERROR"
            ) from e

        try:
            data = json.loads(crudo)
        except json.JSONDecodeError as e:
            raise LibsqlError(
                f"Respuesta de Turso no es JSON válido. Cuerpo crudo: {crudo[:1000]}",
                "INVALID_RESPONSE",
            ) from e
        return data

    def execute(self, sql, args=None) -> _HranaResultSet:
        return self.batch([(sql, args)])[0]

    def batch(self, stmts: list) -> list:
        """stmts: lista de (sql, args) o (sql,). Devuelve una lista de
        _HranaResultSet, una por statement (en el mismo orden)."""
        requests_hrana = []
        for item in stmts:
            sql, args = item if isinstance(item, tuple) else (item, None)
            stmt = {"sql": sql, "want_rows": True}
            if args:
                stmt["args"] = [_valor_a_hrana(v) for v in args]
            requests_hrana.append({"type": "execute", "stmt": stmt})
        requests_hrana.append({"type": "close"})

        data = self._post(requests_hrana)
        resultados_crudos = data.get("results", [])

        resultados = []
        for i, item in enumerate(stmts):
            if i >= len(resultados_crudos):
                raise LibsqlError(
                    f"Turso devolvió menos resultados ({len(resultados_crudos)}) de los "
                    f"statements enviados ({len(stmts)}). Respuesta completa: "
                    f"{json.dumps(data)[:1000]}", "RESULT_MISMATCH")
            r = resultados_crudos[i]
            if r.get("type") == "error":
                err = r.get("error", {})
                raise LibsqlError(err.get("message", str(err)), err.get("code", "SERVER_ERROR"))
            if r.get("type") != "ok":
                raise LibsqlError(f"Respuesta inesperada de Turso: {json.dumps(r)[:500]}",
                                   "UNEXPECTED_RESPONSE")

            resultado = r["response"]["result"]
            columnas = tuple(c.get("name") for c in resultado.get("cols", []))
            filas = [tuple(_valor_de_hrana(v) for v in fila) for fila in resultado.get("rows", [])]
            lastrowid_raw = resultado.get("last_insert_rowid")
            resultados.append(_HranaResultSet(
                columns=columnas,
                rows=filas,
                rows_affected=resultado.get("affected_row_count", 0),
                last_insert_rowid=int(lastrowid_raw) if lastrowid_raw is not None else None,
            ))
        return resultados

    def close(self):
        self.closed = True


# ─── Resolución de credenciales (env var o st.secrets) ──────────────────────
def _leer_credencial(nombre: str):
    """
    Lee una credencial de entorno o st.secrets, siempre con .strip(): un
    espacio o salto de línea pegado por accidente al copiar un token hace
    que el servidor lo rechace con un error de JWT poco claro ("JWT error:
    InvalidToken"), así que se quita aquí para no tener que depurarlo cada
    vez.

    También tolera un error de formato común en secrets.toml: escribir
        [NOMBRE]
        NOMBRE = "valor"
    (una SECCIÓN con el mismo nombre) en vez de simplemente
        NOMBRE = "valor"
    En TOML eso crea una tabla anidada, así que st.secrets.get(nombre)
    devuelve un objeto tipo diccionario en vez del texto esperado — y
    convertirlo a texto con str(...) produce algo como "{'NOMBRE': '...'}",
    que ya no es ni una URL ni un token válidos. Aquí se detecta ese caso
    y se recupera igual el valor de adentro, para que la app funcione
    aunque el secrets.toml esté mal formateado — pero lo correcto es
    corregirlo (quitar la línea "[NOMBRE]", dejar solo NOMBRE = "valor").
    """
    valor = os.environ.get(nombre)
    if valor and valor.strip():
        return valor.strip()
    if st is not None:
        try:
            valor = st.secrets.get(nombre)
            if valor is None:
                return None
            if hasattr(valor, "get") and not isinstance(valor, str):
                anidado = valor.get(nombre)  # ver nota sobre [NOMBRE] mal formateado arriba
                if anidado and str(anidado).strip():
                    return str(anidado).strip()
                return None
            if str(valor).strip():
                return str(valor).strip()
        except Exception:
            pass
    return None


class ConfiguracionTursoFaltante(RuntimeError):
    """Se lanza cuando no se encontró TURSO_DATABASE_URL / TURSO_AUTH_TOKEN."""
    pass


def _normalizar_url_turso(url: str) -> str:
    """
    El cliente HTTP necesita "https://", no "libsql://" (ese esquema es
    para el transporte WebSocket, que ya mostró fallos de handshake contra
    algunas bases/regiones de Turso). Mismo host, mismo puerto — solo
    cambia el esquema al inicio de la URL.
    """
    if url and url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url


# ─── Cliente compartido (una sola conexión de red, reutilizada) ────────────
_lock = threading.Lock()
_client = None


def _get_client():
    global _client
    with _lock:
        if _client is not None and not _client.closed:
            return _client
        url = _leer_credencial("TURSO_DATABASE_URL")
        token = _leer_credencial("TURSO_AUTH_TOKEN")
        if not url:
            raise ConfiguracionTursoFaltante(
                "Falta configurar TURSO_DATABASE_URL (y TURSO_AUTH_TOKEN) como variable de "
                "entorno o en st.secrets. Ve a https://turso.tech, crea una base de datos "
                "gratuita, y agrega esas dos claves en Settings → Secrets de tu app en "
                "Streamlit Community Cloud.")
        url = _normalizar_url_turso(url)
        _client = ClienteTursoHTTP(url=url, auth_token=token)
        return _client


def cerrar_cliente_global():
    """Cierra y descarta el cliente compartido (útil en pruebas)."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None


# ─── Traducción de errores: LibsqlError → sqlite3.IntegrityError / sqlite3.OperationalError ─
def _traducir_error(exc: "LibsqlError"):
    """
    Convierte un error del servidor Turso al equivalente de sqlite3, para
    que el código existente (`except sqlite3.IntegrityError: ...`) siga
    funcionando sin cambios. El texto original del error (p. ej. el nombre
    de la columna que violó la restricción UNIQUE) se conserva en el
    mensaje, porque varios módulos hacen `if "username" in str(e)`.
    """
    texto = f"{getattr(exc, 'code', '')}: {getattr(exc, 'explanation', str(exc))}"
    if "constraint" in texto.lower():
        return sqlite3.IntegrityError(texto)
    return sqlite3.OperationalError(texto)


# ─── Fila compatible con sqlite3.Row (acceso por índice, por nombre, Y dict()) ─
# Varios módulos hacen `conn.row_factory = sqlite3.Row` y luego
# `fila["columna"]` o `dict(fila)`. dict(fila) solo funciona si el objeto
# tiene un método keys() (así decide Python que es "como un mapping") —
# por eso esta clase lo implementa explícitamente, igual que sqlite3.Row.
class Row:
    """Fila compatible con sqlite3.Row: fila[0], fila["columna"], dict(fila)
    e iteración por valores (list(fila)) — todo igual que sqlite3.Row."""
    __slots__ = ("_columnas", "_valores")

    def __init__(self, columnas, valores):
        self._columnas = tuple(columnas)
        self._valores = tuple(valores)

    def __getitem__(self, clave):
        if isinstance(clave, str):
            try:
                return self._valores[self._columnas.index(clave)]
            except ValueError:
                raise IndexError(f"No existe la columna '{clave}'")
        return self._valores[clave]

    def __len__(self):
        return len(self._valores)

    def __iter__(self):
        return iter(self._valores)

    def keys(self):
        """Necesario para que dict(fila) funcione, igual que con sqlite3.Row."""
        return list(self._columnas)

    def __repr__(self):
        return repr(dict(zip(self._columnas, self._valores)))


# ─── Adaptadores con API estilo sqlite3 ─────────────────────────────────────
class _Cursor:
    """Imita sqlite3.Cursor: execute(), executemany(), fetchone(), fetchall(),
    fetchmany(), lastrowid, rowcount, description, close()."""

    def __init__(self, conn: "Connection"):
        self._conn = conn
        self._rows = []
        self._idx = 0
        self.lastrowid = None
        self.rowcount = -1
        self.description = None

    def _aplicar_resultado(self, resultado):
        if self._conn.row_factory:
            # sqlite3.Row (u otro row_factory "truthy") → se envuelve cada
            # fila en db_conn.Row para igualar sqlite3.Row por completo,
            # incluyendo dict(fila) (ver la clase Row más arriba).
            self._rows = [Row(resultado.columns, r) for r in resultado.rows]
        else:
            self._rows = [tuple(r) for r in resultado.rows]
        self._idx = 0
        self.lastrowid = resultado.last_insert_rowid
        self.rowcount = resultado.rows_affected
        columnas = getattr(resultado, "columns", None) or []
        self.description = tuple((c, None, None, None, None, None, None) for c in columnas) or None

    def execute(self, sql, params=()):
        args = list(params) if params else None
        try:
            resultado = self._conn._client.execute(sql, args)
        except LibsqlError as e:
            raise _traducir_error(e) from e
        self._aplicar_resultado(resultado)
        return self

    def executemany(self, sql, seq_de_params):
        """Igual que sqlite3.Cursor.executemany(): ejecuta el mismo SQL una
        vez por cada tupla de parámetros (en un solo viaje de red, vía
        ClientSync.batch())."""
        lote = [(sql, list(p)) for p in seq_de_params]
        if not lote:
            self._rows, self._idx = [], 0
            self.rowcount = 0
            return self
        try:
            resultados = self._conn._client.batch(lote)
        except LibsqlError as e:
            raise _traducir_error(e) from e
        # sqlite3.Cursor.executemany() no deja filas para leer; se deja
        # lastrowid/rowcount del ÚLTIMO statement ejecutado, igual que sqlite3.
        self._rows, self._idx = [], 0
        if resultados:
            self.lastrowid = resultados[-1].last_insert_rowid
            self.rowcount = sum(r.rows_affected for r in resultados)
        return self

    def fetchone(self):
        if self._idx < len(self._rows):
            fila = self._rows[self._idx]
            self._idx += 1
            return fila
        return None

    def fetchall(self):
        restantes = self._rows[self._idx:]
        self._idx = len(self._rows)
        return restantes

    def fetchmany(self, size=1):
        restantes = self._rows[self._idx:self._idx + size]
        self._idx += len(restantes)
        return restantes

    def close(self):
        pass

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    """Imita sqlite3.Connection: cursor(), execute(), executemany(), commit(),
    rollback(), close(), row_factory."""

    def __init__(self):
        self._client = _get_client()
        self.row_factory = None  # por defecto, igual que sqlite3: filas como tuplas

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def execute(self, sql, params=()):
        """Igual que sqlite3.Connection.execute(): atajo sin pasar por cursor()."""
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq_de_params):
        """Igual que sqlite3.Connection.executemany(): atajo sin pasar por cursor()."""
        return self.cursor().executemany(sql, seq_de_params)

    def commit(self):
        """No-op intencional: en libSQL (modo HTTP/'stateless') cada execute()
        ya queda confirmado en el servidor. Se deja el método para no romper
        el código existente que sigue llamando conn.commit()."""
        pass

    def rollback(self):
        """No-op intencional, por la misma razón que commit(): no hay una
        transacción abierta que revertir en el modo stateless de libSQL."""
        pass

    def close(self):
        """No-op intencional: el cliente de red se reutiliza entre llamadas
        (ver _get_client); cerrarlo en cada función sería muy costoso en
        latencia. Usa cerrar_cliente_global() si alguna vez necesitas forzar
        una reconexión completa (por ejemplo, en pruebas)."""
        pass


def connect(*_args, **_kwargs):
    """
    Firma compatible con sqlite3.connect(ruta, ...): los argumentos se
    ignoran (la ruta/credenciales reales se leen de TURSO_DATABASE_URL /
    TURSO_AUTH_TOKEN), para que el resto del código casi no cambie:
        conn = sqlite3.connect(DB_PATH)   →   conn = db_conn.connect()
    """
    return Connection()


# ─── Equivalentes de utilidades de sqlite3 ──────────────────────────────────
def Binary(datos: bytes) -> bytes:
    """Equivalente a sqlite3.Binary(x): libSQL acepta bytes de Python
    directamente como valor de una columna BLOB, así que esto es un alias."""
    return bytes(datos)


# Alias de las excepciones ya traducidas en _traducir_error(), para el
# código que prefiera capturarlas como db_conn.IntegrityError /
# db_conn.OperationalError en vez de sqlite3.IntegrityError / sqlite3.OperationalError
# (ambas formas funcionan igual, son las mismas clases).
IntegrityError = sqlite3.IntegrityError
OperationalError = sqlite3.OperationalError
Error = sqlite3.Error
