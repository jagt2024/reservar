"""
db_utils.py — Utilidades compartidas de base de datos para SolarCalc Pro
"""
import sqlite3

DB_PATH = "solar_calc.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_modulos_db():
    """Crea todas las tablas adicionales que requieren los módulos externos."""
    conn = get_conn()
    c = conn.cursor()

    # ── Materiales (catálogo RETIE) ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS materiales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo      TEXT,
            categoria   TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            unidad      TEXT NOT NULL,
            precio_ref  REAL DEFAULT 0,
            retie       INTEGER DEFAULT 0,
            activo      INTEGER DEFAULT 1,
            notas       TEXT
        )
    """)

    # ── Equipos y Herramientas ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS equipos_herramientas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo        TEXT NOT NULL,        -- 'Equipo' | 'Herramienta'
            categoria   TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            unidad      TEXT NOT NULL,
            precio_ref  REAL DEFAULT 0,
            rendimiento TEXT,
            activo      INTEGER DEFAULT 1
        )
    """)

    # ── Personal ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS personal (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            cargo         TEXT NOT NULL,
            perfil        TEXT NOT NULL,
            certificacion TEXT,
            salario_dia   REAL DEFAULT 0,
            retie         INTEGER DEFAULT 0,
            activo        INTEGER DEFAULT 1
        )
    """)

    # ── Capítulos del presupuesto ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS presupuesto_capitulos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            orden       INTEGER DEFAULT 0,
            nombre      TEXT NOT NULL,
            descripcion TEXT,
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)

    # ── Items del presupuesto ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS presupuesto_items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            capitulo_id   INTEGER NOT NULL,
            proyecto_id   INTEGER NOT NULL,
            item          TEXT NOT NULL,
            descripcion   TEXT NOT NULL,
            unidad        TEXT,
            cantidad      REAL DEFAULT 1,
            valor_unitario REAL DEFAULT 0,
            tipo_recurso  TEXT,   -- 'Material' | 'Equipo' | 'Personal' | 'Otro'
            recurso_id    INTEGER,
            notas         TEXT,
            FOREIGN KEY(capitulo_id)  REFERENCES presupuesto_capitulos(id),
            FOREIGN KEY(proyecto_id)  REFERENCES proyectos(id)
        )
    """)

    # ── Simulaciones guardadas ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS simulaciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id     INTEGER NOT NULL,
            nombre          TEXT,
            consumo_wh      REAL,
            consumo_fs_wh   REAL,
            hsp             REAL,
            vdc             INTEGER,
            num_paneles     INTEGER,
            pot_panel_wp    REAL,
            pot_instalada_wp REAL,
            num_baterias    INTEGER,
            bat_cap_ah      REAL,
            ah_total        REAL,
            energia_kwh     REAL,
            corriente_mppt  REAL,
            mppt_modelo     TEXT,
            inversor_kva    REAL,
            serie           INTEGER,
            paralelo        INTEGER,
            irradiacion_mes REAL,
            municipio       TEXT,
            tarifa_kwh      REAL,
            ahorro_mensual  REAL,
            co2_kg_anual    REAL,
            tir             REAL,
            vpn             REAL,
            payback_anos    REAL,
            costo_sistema   REAL,
            generado        TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)

    conn.commit()
    conn.close()
