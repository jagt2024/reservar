"""
db_utils.py — Conexión compartida de base de datos para SolarCalc Pro

ARQUITECTURA:
- solar_app.py resuelve DB_PATH y lo fija en os.environ["SOLARCALC_DB_PATH"]
- Este módulo SIEMPRE lee esa variable de entorno
- Si la variable aún no está seteada (import antes de solar_app), usa /tmp
- get_conn() crea las tablas si no existen en cada llamada desde módulos externos
"""
import sqlite3
import os
import pathlib
import tempfile


def _get_db_path() -> str:
    """Lee la ruta fijada por solar_app.py. Nunca resuelve por sí solo."""
    p = os.environ.get("SOLARCALC_DB_PATH", "")
    if p and p.strip():
        return p.strip()
    # Fallback solo si solar_app aún no se ejecutó (no debería pasar en producción)
    return str(pathlib.Path(tempfile.gettempdir()) / "solar_calc.db")


def get_conn():
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _ensure_tables(conn)
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


# Exponer DB_PATH como función para compatibilidad
def get_db_path() -> str:
    return _get_db_path()


DB_PATH = _get_db_path()
