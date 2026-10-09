"""
db_utils.py — Conexión compartida de base de datos para SolarCalc Pro

ARQUITECTURA (migrado a Turso):
- Antes este módulo abría sqlite3.connect() sobre un archivo local
  (resuelto vía SOLARCALC_DB_PATH, fijado por solar_app.py). En Streamlit
  Community Cloud ese archivo se pierde en cada reinicio del contenedor
  (no hay disco persistente), así que ahora se usa Turso (libSQL) a
  través de db_conn.py, que imita la misma API de sqlite3 (execute,
  cursor, fetchone/fetchall, row_factory, executemany, commit, close,
  excepciones) para que el resto de este archivo casi no cambie.
- get_conn() crea las tablas si no existen, pero SOLO LA PRIMERA VEZ por
  proceso (ver _ESQUEMA_LISTO). Antes lo hacía en cada llamada: con sqlite3
  local eso costaba microsegundos, pero contra Turso son ~11 sentencias
  CREATE TABLE IF NOT EXISTS = 11 viajes de red EXTRA antes de cada
  consulta real, en cada uno de los módulos que usan get_conn().
- Configuración necesaria: ver las instrucciones al inicio de db_conn.py
  (variables TURSO_DATABASE_URL / TURSO_AUTH_TOKEN).
"""
import threading

import db_conn

_ESQUEMA_LISTO = False
_ESQUEMA_LOCK = threading.Lock()


def get_conn():
    global _ESQUEMA_LISTO
    conn = db_conn.connect()
    if not _ESQUEMA_LISTO:
        with _ESQUEMA_LOCK:
            if not _ESQUEMA_LISTO:  # doble verificación: otro hilo pudo ganar la carrera
                _ensure_tables(conn)
                # Solo se marca como listo si _ensure_tables terminó sin
                # error; si falló (p. ej. red caída), se reintentará en la
                # próxima llamada en vez de dar el esquema por creado.
                _ESQUEMA_LISTO = True
    return conn


def _ensure_tables(conn):
    """Crea las tablas adicionales si no existen. Idempotente."""
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS materiales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT, categoria TEXT NOT NULL, descripcion TEXT NOT NULL,
        unidad TEXT NOT NULL, precio_ref REAL DEFAULT 0,
        retie INTEGER DEFAULT 0, activo INTEGER DEFAULT 1, notas TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS equipos_herramientas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL, categoria TEXT NOT NULL, descripcion TEXT NOT NULL,
        unidad TEXT NOT NULL, precio_ref REAL DEFAULT 0,
        rendimiento TEXT, activo INTEGER DEFAULT 1)""")

    c.execute("""CREATE TABLE IF NOT EXISTS personal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cargo TEXT NOT NULL, perfil TEXT NOT NULL, certificacion TEXT,
        salario_dia REAL DEFAULT 0, retie INTEGER DEFAULT 0, activo INTEGER DEFAULT 1)""")

    c.execute("""CREATE TABLE IF NOT EXISTS presupuesto_capitulos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER NOT NULL, orden INTEGER DEFAULT 0,
        nombre TEXT NOT NULL, descripcion TEXT,
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS presupuesto_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        capitulo_id INTEGER NOT NULL, proyecto_id INTEGER NOT NULL,
        item TEXT NOT NULL, descripcion TEXT NOT NULL,
        unidad TEXT, cantidad REAL DEFAULT 1, valor_unitario REAL DEFAULT 0,
        tipo_recurso TEXT, recurso_id INTEGER, notas TEXT,
        FOREIGN KEY(capitulo_id) REFERENCES presupuesto_capitulos(id),
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS simulaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER NOT NULL, nombre TEXT,
        consumo_wh REAL, consumo_fs_wh REAL, hsp REAL, vdc INTEGER,
        num_paneles INTEGER, pot_panel_wp REAL, pot_instalada_wp REAL,
        num_baterias INTEGER, bat_cap_ah REAL, ah_total REAL, energia_kwh REAL,
        corriente_mppt REAL, mppt_modelo TEXT, inversor_kva REAL,
        serie INTEGER, paralelo INTEGER, irradiacion_mes REAL, municipio TEXT,
        tarifa_kwh REAL, ahorro_mensual REAL, co2_kg_anual REAL,
        tir REAL, vpn REAL, payback_anos REAL, costo_sistema REAL,
        generado TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    # También asegurar tablas principales en caso de BD nueva
    c.execute("""CREATE TABLE IF NOT EXISTS proyectos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, municipio TEXT, tension_dc INTEGER,
        hsp REAL, creado TEXT DEFAULT (datetime('now')))""")

    c.execute("""CREATE TABLE IF NOT EXISTS cargas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER, electrodomestico TEXT NOT NULL,
        cantidad INTEGER DEFAULT 1, potencia_w REAL DEFAULT 0,
        horas_dia REAL DEFAULT 0, es_motor INTEGER DEFAULT 0,
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS paneles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER, modelo TEXT,
        potencia_wp REAL, voc REAL, isc REAL,
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS recibos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER, periodo TEXT,
        kwh_periodo REAL, dias_periodo INTEGER DEFAULT 30,
        estrato TEXT, tarifa_kwh REAL, valor_total REAL,
        observaciones TEXT, creado TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS resultados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER, consumo_dia_wh REAL, consumo_con_fs REAL,
        tension_dc INTEGER, hsp REAL, potencia_instalada_w REAL,
        num_paneles INTEGER, capacidad_baterias_ah REAL,
        num_baterias INTEGER, corriente_mppt REAL,
        generado TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(proyecto_id) REFERENCES proyectos(id))""")

    conn.commit()


def init_modulos_db():
    """Compatibilidad — get_conn() ya llama _ensure_tables automáticamente."""
    conn = get_conn()
    conn.close()


# Compatibilidad: nada en el código usa esto directamente (se verificó),
# pero se deja por si algo externo llegara a llamarlo — ya no hay una
# "ruta de archivo" real porque los datos viven en Turso, no en disco local.
def get_db_path() -> str:
    return "(usando Turso vía db_conn.py — ya no aplica una ruta de archivo local)"


DB_PATH = get_db_path()
