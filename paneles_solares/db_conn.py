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
#   2) Obtén la URL (empieza con "libsql://...") y el auth token.
#   3) En Streamlit Community Cloud: panel de tu app → Settings → Secrets,
#      agrega:
#           TURSO_DATABASE_URL = "libsql://tu-base-xxxx.turso.io"
#           TURSO_AUTH_TOKEN   = "tu-token-aqui"
#      (En local, puedes usar variables de entorno con los mismos nombres,
#      o un archivo .streamlit/secrets.toml con esas mismas claves.)
#
# LIMITACIÓN CONOCIDA: la clasificación de errores en IntegrityError vs.
# OperationalError se hace revisando si la palabra "constraint" aparece en
# el código/mensaje de error que devuelve Turso (ver _traducir_error). Esto
# coincide con el formato estándar de SQLite ("UNIQUE constraint failed: ...",
# "SQLITE_CONSTRAINT..."), pero no se pudo verificar contra un servidor Turso
# real desde este entorno de desarrollo — si algún `except sqlite3.IntegrityError`
# no llegara a dispararse en producción, avisa para ajustar la heurística.
# ══════════════════════════════════════════════════════════════════════════

import os
import sqlite3  # SOLO para reutilizar sus clases de excepción y sqlite3.Row;
                 # ya no se usa sqlite3.connect() en ningún lado de este módulo.
import threading

try:
    import libsql_client
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "Falta el paquete 'libsql-client'. Instálalo con:  pip install libsql-client"
    ) from _e

try:
    import streamlit as st
except ImportError:  # por si algún script usa este módulo fuera de Streamlit
    st = None


# ─── Resolución de credenciales (env var o st.secrets) ──────────────────────
def _leer_credencial(nombre: str):
    valor = os.environ.get(nombre)
    if valor:
        return valor
    if st is not None:
        try:
            valor = st.secrets.get(nombre)
            if valor:
                return str(valor)
        except Exception:
            pass
    return None


class ConfiguracionTursoFaltante(RuntimeError):
    """Se lanza cuando no se encontró TURSO_DATABASE_URL / TURSO_AUTH_TOKEN."""
    pass


# ─── Cliente compartido (una sola conexión de red, reutilizada) ────────────
_lock = threading.Lock()
_client = None


def _get_client():
    global _client
    with _lock:
        if _client is not None and not _client.closed:
            return _client
        url = _leer_credencial(st.secrets.get("TURSO_DATABASE_URL"))
        token = _leer_credencial(st.secrets.get("TURSO_AUTH_TOKEN"))
        if not url:
            raise ConfiguracionTursoFaltante(
                "Falta configurar TURSO_DATABASE_URL (y TURSO_AUTH_TOKEN) como variable de "
                "entorno o en st.secrets. Ve a https://turso.tech, crea una base de datos "
                "gratuita, y agrega esas dos claves en Settings → Secrets de tu app en "
                "Streamlit Community Cloud.")
        _client = libsql_client.create_client_sync(url=url, auth_token=token)
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
def _traducir_error(exc: "libsql_client.LibsqlError"):
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
# libsql_client.Row YA soporta fila[0] y fila["columna"] de forma nativa,
# pero le falta el método keys() que sqlite3.Row sí tiene — y sin keys(),
# `dict(fila)` no funciona (falla con "cannot convert... to a dictionary").
# Varios módulos hacen justo eso (dict(fila_con_row_factory)), así que se
# envuelve en esta pequeña clase para igualar el comportamiento exacto de
# sqlite3.Row.
class Row:
    """Fila compatible con sqlite3.Row: fila[0], fila["columna"], dict(fila)
    e iteración por valores (list(fila)) — todo igual que sqlite3.Row."""
    __slots__ = ("_fila",)

    def __init__(self, fila_libsql):
        self._fila = fila_libsql  # instancia de libsql_client.Row

    def __getitem__(self, clave):
        return self._fila[clave]

    def __len__(self):
        return len(self._fila)

    def __iter__(self):
        return iter(self._fila.astuple())

    def keys(self):
        """Necesario para que dict(fila) funcione, igual que con sqlite3.Row."""
        return list(self._fila._fields)

    def __repr__(self):
        return repr(self._fila.astuple())


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
            # incluyendo dict(fila) (ver la clase Row más abajo).
            self._rows = [Row(r) for r in resultado.rows]
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
        except libsql_client.LibsqlError as e:
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
        except libsql_client.LibsqlError as e:
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
