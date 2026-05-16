═══════════════════════════
#  SUITE SALITRE S.A.S · Terminal de Transportes El Salitre — Bogotá
#  MÓDULO: Repuestos · Escáner · Seguros · Convenios · Inventario
#  FUENTE DE DATOS: PostgreSQL (única fuente de verdad)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Instalación:
#    pip install streamlit pandas pytz psycopg2-binary openpyxl plotly
#
#  Configuración en .streamlit/secrets.toml:
#
#    [postgres]
#    host     = "localhost"
#    port     = 5433
#    user     = "postgres"
#    password = "123456"
#    dbname   = "repuestos"
#    sslmode  = "disable"
#    # O bien:
#    url = "postgresql://user:pass@host:5432/dbname?sslmode=require"
#
#  Ejecución:
#    streamlit run repuestos_salitre.py
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import json
import hashlib
import io
import os
import time
import uuid
import urllib.parse
from datetime import datetime, date
from typing import Optional, List, Dict

import pandas as pd
import pytz

# ── Dependencias opcionales ───────────────────────────────────────────────────
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

PG_HOST = "aws-1-us-west-1.pooler.supabase.com"
PG_PORT = 5432
PG_USER = "postgres.nmfwunmluneqvzmhfagm"
PG_PASS = "JbVHPer5dUblreff"
PG_DB   = "postgres"

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# ── Constantes ────────────────────────────────────────────────────────────────
NEGOCIO   = "SUITE SALITRE S.A.S"
TAGLINE   = "Repuestos · Escáner · Seguros para Flotas"
DIRECCION = "Terminal de Transportes El Salitre · Bogotá"
NIT       = "902.047.871-3"
TELEFONO  = "3219714969"
EMAIL     = "suitesalitre@gmail.com"
TZ_COL    = pytz.timezone("America/Bogota")

TIPOS_VEHICULO  = ["Bus Intermunicipal","Buseta Urbana","Microbus","Van","Camioneta","Otro"]
TIPOS_EMPRESA   = ["Empresa de Transporte Flota","Transporte Público","Privada","Mixta"]
TIPOS_CONVENIO  = ["Descuento Repuestos","Descuento Escáner","Descuento Combo","Crédito","Prepago"]
TIPOS_SEGURO    = ["SOAT","Todo Riesgo","Responsabilidad Civil","Amparo de Daños","Otro"]
TIPOS_DOC       = ["NIT","CC","CE","Pasaporte"]
ESTADOS_INV     = ["Disponible","Reservado","Agotado","Descontinuado"]
CATEGORIAS_REP  = ["Motor","Frenos","Transmisión","Suspensión","Eléctrico","Carrocería",
                   "Filtros","Correas","Refrigeración","Neumáticos","Otro"]
TIPOS_ESCANER   = ["Diagnóstico OBD2","Escáner Avanzado","Revisión Técnico-Mecánica",
                   "Lectura de Fallas","Calibración de Sensores","Otro"]

# ── Estructura lógica de tablas (equivalente a DRIVE_SHEETS) ─────────────────
DRIVE_SHEETS = {
    "Empresa": [
        "Id_Empresa","Nombre_Empresa","Nit_Empresa","Tipo_Empresa",
        "Email_Empresa","Telefono_Empresa","Contacto_Nombre","Contacto_Cargo",
        "Tipo_Convenio","Descuento_Repuestos_Pct","Descuento_Escaner_Pct",
        "Credito_Maximo_COP","Observaciones","Activo","Creado_En",
    ],
    "Inventarios": [
        "Id_Item","Tipo","Codigo_SKU","Nombre","Descripcion",
        "Categoria","Marca","Referencia","Cantidad_Stock","Cantidad_Minima",
        "Precio_Compra_COP","Precio_Venta_COP","Ubicacion","Estado","Creado_En","Actualizado_En",
    ],
    "Repuestos": [
        "Id_Repuesto","Id_Empresa","Nombre_Empresa","Fecha_Solicitud",
        "Codigo_SKU","Nombre_Repuesto","Categoria","Cantidad","Precio_Unitario_COP",
        "Descuento_Pct","Total_COP","Estado_Pedido","Placa_Vehiculo",
        "Tipo_Vehiculo","Mecanico","Observaciones","Creado_Por",
    ],
    "Escaner": [
        "Id_Escaner","Id_Empresa","Nombre_Empresa","Fecha_Servicio",
        "Placa_Vehiculo","Tipo_Vehiculo","Tipo_Escaner","Tecnico",
        "Precio_Base_COP","Descuento_Pct","Total_COP","Resultado",
        "Codigos_Falla","Recomendaciones","Estado","Creado_Por",
    ],
    "Seguros": [
        "Id_Seguro","Id_Empresa","Nombre_Empresa","Placa_Vehiculo",
        "Tipo_Vehiculo","Propietario","Tipo_Seguro","Aseguradora",
        "Num_Poliza","Fecha_Inicio","Fecha_Vencimiento","Prima_COP",
        "Cobertura_COP","Estado","Observaciones","Creado_Por","Creado_En",
    ],
    "Pagos": [
        "Id_Pago","Id_Empresa","Nombre_Empresa","Fecha_Pago",
        "Tipo_Servicio","Referencia_Servicio","Monto_COP","Metodo_Pago",
        "Estado","Confirmado_Por","Observaciones",
    ],
    "Facturas": [
        "Id_Factura","Num_Factura","Id_Empresa","Nombre_Empresa",
        "Fecha_Emision","Fecha_Vencimiento","Subtotal_COP","Descuento_COP",
        "IVA_COP","Total_COP","Estado","Observaciones","Creado_Por",
    ],
    "Facturas_Items": [
        "Id_Item","Id_Factura","Num_Factura","Tipo_Servicio",
        "Descripcion","Cantidad","Precio_Unitario","Descuento_Pct","Subtotal",
    ],
    "Dashboard_Diario": [
        "Fecha","Total_Repuestos","Total_Escaner","Total_Seguros",
        "Ingresos_Repuestos","Ingresos_Escaner","Ingresos_Seguros","Total_Ingresos",
        "Num_Empresas_Activas","Nuevos_Convenios",
    ],
    "Tarifas_Config": [
        "Id_Tarifa","Tipo_Servicio","Nombre_Tarifa","Precio_COP",
        "Unidad","Descripcion","Activo",
    ],
    "Operadores": [
        "Id_Operador","Nombre","Usuario","Password_Hash","Rol",
        "Permisos","Activo","Creado_En",
    ],
    "Configuracion_Pagos": [
        "Clave","Valor","Actualizado_En",
    ],
}

# DDL → mapeo hoja → nombre tabla PG
_TABLA = {
    "Empresa":            "rs_empresa",
    "Inventarios":        "rs_inventarios",
    "Repuestos":          "rs_repuestos",
    "Escaner":            "rs_escaner",
    "Seguros":            "rs_seguros",
    "Pagos":              "rs_pagos",
    "Facturas":           "rs_facturas",
    "Facturas_Items":     "rs_facturas_items",
    "Dashboard_Diario":   "rs_dashboard_diario",
    "Tarifas_Config":     "rs_tarifas_config",
    "Operadores":         "rs_operadores",
    "Configuracion_Pagos":"rs_configuracion",
}

_DDL = """
CREATE TABLE IF NOT EXISTS rs_empresa (
    id_empresa TEXT PRIMARY KEY, nombre_empresa TEXT, nit_empresa TEXT UNIQUE,
    tipo_empresa TEXT, email_empresa TEXT, telefono_empresa TEXT,
    contacto_nombre TEXT, contacto_cargo TEXT, tipo_convenio TEXT,
    descuento_repuestos_pct TEXT DEFAULT '0', descuento_escaner_pct TEXT DEFAULT '0',
    credito_maximo_cop TEXT DEFAULT '0', observaciones TEXT,
    activo TEXT DEFAULT '1', creado_en TEXT
);
CREATE TABLE IF NOT EXISTS rs_inventarios (
    id_item TEXT PRIMARY KEY, tipo TEXT, codigo_sku TEXT UNIQUE, nombre TEXT,
    descripcion TEXT, categoria TEXT, marca TEXT, referencia TEXT,
    cantidad_stock TEXT DEFAULT '0', cantidad_minima TEXT DEFAULT '0',
    precio_compra_cop TEXT DEFAULT '0', precio_venta_cop TEXT DEFAULT '0',
    ubicacion TEXT, estado TEXT DEFAULT 'Disponible',
    creado_en TEXT, actualizado_en TEXT
);
CREATE TABLE IF NOT EXISTS rs_repuestos (
    id_repuesto TEXT PRIMARY KEY, id_empresa TEXT, nombre_empresa TEXT,
    fecha_solicitud TEXT, codigo_sku TEXT, nombre_repuesto TEXT, categoria TEXT,
    cantidad TEXT, precio_unitario_cop TEXT DEFAULT '0',
    descuento_pct TEXT DEFAULT '0', total_cop TEXT DEFAULT '0',
    estado_pedido TEXT DEFAULT 'Pendiente', placa_vehiculo TEXT,
    tipo_vehiculo TEXT, mecanico TEXT, observaciones TEXT, creado_por TEXT
);
CREATE TABLE IF NOT EXISTS rs_escaner (
    id_escaner TEXT PRIMARY KEY, id_empresa TEXT, nombre_empresa TEXT,
    fecha_servicio TEXT, placa_vehiculo TEXT, tipo_vehiculo TEXT, tipo_escaner TEXT,
    tecnico TEXT, precio_base_cop TEXT DEFAULT '0', descuento_pct TEXT DEFAULT '0',
    total_cop TEXT DEFAULT '0', resultado TEXT, codigos_falla TEXT,
    recomendaciones TEXT, estado TEXT DEFAULT 'Pendiente', creado_por TEXT
);
CREATE TABLE IF NOT EXISTS rs_seguros (
    id_seguro TEXT PRIMARY KEY, id_empresa TEXT, nombre_empresa TEXT,
    placa_vehiculo TEXT, tipo_vehiculo TEXT, propietario TEXT,
    tipo_seguro TEXT, aseguradora TEXT, num_poliza TEXT UNIQUE,
    fecha_inicio TEXT, fecha_vencimiento TEXT,
    prima_cop TEXT DEFAULT '0', cobertura_cop TEXT DEFAULT '0',
    estado TEXT DEFAULT 'Activo', observaciones TEXT,
    creado_por TEXT, creado_en TEXT
);
CREATE TABLE IF NOT EXISTS rs_pagos (
    id_pago TEXT PRIMARY KEY, id_empresa TEXT, nombre_empresa TEXT,
    fecha_pago TEXT, tipo_servicio TEXT, referencia_servicio TEXT,
    monto_cop TEXT DEFAULT '0', metodo_pago TEXT,
    estado TEXT DEFAULT 'Pendiente', confirmado_por TEXT, observaciones TEXT
);
CREATE TABLE IF NOT EXISTS rs_facturas (
    id_factura TEXT, num_factura TEXT PRIMARY KEY, id_empresa TEXT, nombre_empresa TEXT,
    fecha_emision TEXT, fecha_vencimiento TEXT,
    subtotal_cop TEXT DEFAULT '0', descuento_cop TEXT DEFAULT '0',
    iva_cop TEXT DEFAULT '0', total_cop TEXT DEFAULT '0',
    estado TEXT DEFAULT 'Emitida', observaciones TEXT, creado_por TEXT
);
CREATE TABLE IF NOT EXISTS rs_facturas_items (
    id SERIAL PRIMARY KEY, id_item TEXT, id_factura TEXT, num_factura TEXT,
    tipo_servicio TEXT, descripcion TEXT, cantidad TEXT,
    precio_unitario TEXT DEFAULT '0', descuento_pct TEXT DEFAULT '0', subtotal TEXT DEFAULT '0'
);
CREATE TABLE IF NOT EXISTS rs_dashboard_diario (
    fecha TEXT PRIMARY KEY, total_repuestos TEXT, total_escaner TEXT, total_seguros TEXT,
    ingresos_repuestos TEXT, ingresos_escaner TEXT, ingresos_seguros TEXT,
    total_ingresos TEXT, num_empresas_activas TEXT, nuevos_convenios TEXT
);
CREATE TABLE IF NOT EXISTS rs_tarifas_config (
    id_tarifa TEXT PRIMARY KEY, tipo_servicio TEXT, nombre_tarifa TEXT,
    precio_cop TEXT DEFAULT '0', unidad TEXT, descripcion TEXT, activo TEXT DEFAULT '1'
);
CREATE TABLE IF NOT EXISTS rs_operadores (
    id_operador TEXT PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE,
    password_hash TEXT, rol TEXT DEFAULT 'Operador',
    permisos TEXT, activo TEXT DEFAULT '1', creado_en TEXT
);
CREATE TABLE IF NOT EXISTS rs_configuracion (
    clave TEXT PRIMARY KEY, valor TEXT, actualizado_en TEXT
);
"""

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG + CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title=f"{NEGOCIO} · Gestión",
    page_icon="🔧", layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inconsolata:wght@400;600;700&display=swap');
:root {
  --bg-deep:#050b1a;--bg-card:#0d1f3c;--bg-card2:#0a1628;
  --cyan:#00d4ff;--green:#00ff88;--red:#ff4757;--yellow:#ffd32a;
  --orange:#ff9f43;--purple:#a29bfe;--text:#e2e8f0;--text-dim:#94a3b8;
  --border:rgba(0,212,255,0.2);--radius:16px;
}
html,body,.stApp{background:linear-gradient(135deg,var(--bg-deep) 0%,#091428 60%,var(--bg-deep) 100%) !important;color:var(--text) !important;font-family:'Syne',sans-serif !important;}
#MainMenu,footer,.stDeployButton{display:none !important;}
header[data-testid="stHeader"]{background:transparent !important;border-bottom:none !important;}
section[data-testid="stSidebar"]{background:rgba(5,11,26,0.97) !important;border-right:1px solid var(--border);}
section[data-testid="stSidebar"] *{color:#e2e8f0 !important;}
section[data-testid="stSidebar"] .stRadio label,section[data-testid="stSidebar"] .stRadio p{font-size:15px !important;font-weight:600 !important;}
section[data-testid="stSidebar"] div.stButton>button{color:#e2e8f0 !important;border-color:rgba(226,232,240,0.25) !important;}
.block-container{padding:1.2rem 2rem !important;}
div.stButton>button{min-height:48px !important;border-radius:var(--radius) !important;font-family:'Syne',sans-serif !important;font-weight:700 !important;font-size:15px !important;border:1.5px solid var(--border) !important;background:linear-gradient(135deg,var(--bg-card),var(--bg-card2)) !important;color:var(--text) !important;transition:all 0.2s ease !important;}
div.stButton>button:hover{border-color:var(--cyan) !important;box-shadow:0 0 20px rgba(0,212,255,0.3) !important;color:var(--cyan) !important;}
div.stButton>button[kind="primary"]{background:linear-gradient(135deg,#0a3d62,#1a5276) !important;border-color:var(--cyan) !important;color:var(--cyan) !important;min-height:56px !important;font-size:16px !important;}
div.stButton>button[kind="primary"]:hover{box-shadow:0 0 32px rgba(0,212,255,0.5) !important;}
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox select{background:rgba(13,31,60,0.8) !important;border:1.5px solid var(--border) !important;border-radius:10px !important;color:var(--text) !important;font-family:'Syne',sans-serif !important;}
.stTextInput input:focus,.stNumberInput input:focus{border-color:var(--cyan) !important;box-shadow:0 0 12px rgba(0,212,255,0.2) !important;}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;margin-bottom:14px;}
.card-title{font-size:18px;font-weight:800;color:var(--cyan);margin-bottom:12px;letter-spacing:1px;text-transform:uppercase;}
.card-stat{font-family:'Inconsolata',monospace;font-size:32px;font-weight:700;color:var(--green);}
.badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;}
.badge-green{background:rgba(0,255,136,0.15);color:var(--green);border:1px solid rgba(0,255,136,0.4);}
.badge-red{background:rgba(255,71,87,0.15);color:var(--red);border:1px solid rgba(255,71,87,0.4);}
.badge-yellow{background:rgba(255,211,42,0.15);color:var(--yellow);border:1px solid rgba(255,211,42,0.4);}
.badge-cyan{background:rgba(0,212,255,0.15);color:var(--cyan);border:1px solid rgba(0,212,255,0.4);}
.badge-orange{background:rgba(255,159,67,0.15);color:var(--orange);border:1px solid rgba(255,159,67,0.4);}
.stTabs [data-baseweb="tab-list"]{background:var(--bg-card) !important;border-radius:12px !important;gap:4px !important;padding:4px !important;}
.stTabs [data-baseweb="tab"]{background:transparent !important;color:var(--text-dim) !important;border-radius:8px !important;font-family:'Syne',sans-serif !important;font-weight:600 !important;}
.stTabs [aria-selected="true"]{background:rgba(0,212,255,0.15) !important;color:var(--cyan) !important;}
[data-testid="stMetric"]{background:var(--bg-card) !important;border:1px solid var(--border) !important;border-top:3px solid var(--cyan) !important;border-radius:var(--radius) !important;padding:16px !important;}
[data-testid="stMetricValue"]{font-family:'Inconsolata',monospace !important;color:var(--cyan) !important;}
[data-testid="stDataFrame"]{border:1px solid var(--border) !important;border-radius:12px !important;}
hr{border-color:var(--border) !important;}
.login-container{max-width:440px;margin:60px auto;background:var(--bg-card);border:1px solid var(--border);border-radius:24px;padding:48px 40px;box-shadow:0 0 60px rgba(0,212,255,0.12);}
.login-title{font-size:26px;font-weight:800;color:var(--cyan);text-align:center;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;}
.login-sub{font-size:14px;color:var(--text-dim);text-align:center;margin-bottom:32px;}
.page-title{font-size:24px;font-weight:800;color:var(--cyan);letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;}
.page-sub{font-size:14px;color:var(--text-dim);margin-bottom:24px;}
.alerta-stock{background:rgba(255,71,87,0.12);border:2px solid var(--red);border-radius:12px;padding:12px 16px;color:var(--red);font-weight:700;font-size:14px;}
.alerta-vencimiento{background:rgba(255,211,42,0.12);border:2px solid var(--yellow);border-radius:12px;padding:12px 16px;color:var(--yellow);font-weight:700;font-size:14px;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES GENERALES
# ═══════════════════════════════════════════════════════════════════════════════

def ahora_col() -> datetime:
    return datetime.now(TZ_COL)

def fmt_cop(v) -> str:
    try:    return f"$ {float(v):,.0f}".replace(",", ".")
    except: return "$ 0"

def gen_id(prefix: str = "") -> str:
    ts  = int(time.time() * 1000)
    rnd = uuid.uuid4().hex[:6].upper()
    return f"{prefix}{ts}-{rnd}"

def hashpw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════════
# CAPA POSTGRESQL — fuente única de datos
# ═══════════════════════════════════════════════════════════════════════════════

def _read_pg_url() -> str:
    """Lee la URL de conexión desde secrets.toml o variable de entorno."""
    def _build(host, port, user, password, dbname, sslmode="require"):
        u = urllib.parse.quote(str(user), safe="")
        p = urllib.parse.quote(str(password), safe="")
        h = str(host).strip().lstrip("@")
        return f"postgresql://{u}:{p}@{h}:{port}/{dbname}?sslmode={sslmode}&connect_timeout=15"

    try:
        if "postgres" in st.secrets:
            pg = st.secrets["postgres"]
            if "url" in pg and pg["url"]:
                return str(pg["url"]).strip()
            if pg.get("host"):
                return _build(pg["host"], int(pg.get("port", 5432)),
                               pg["user"], pg["password"],
                               pg.get("dbname", "postgres"),
                               pg.get("sslmode", "require"))
    except Exception:
        pass
    import os
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    return _build("localhost", 5433, "postgres", "123456", "repuestos", "disable")


@st.cache_resource
def _get_engine():
    return {"url": _read_pg_url()}


def get_pg_conn():
    engine = _get_engine()
    conn   = engine.get("conn")
    if conn:
        try:
            conn.cursor().execute("SELECT 1")
            return conn
        except Exception:
            pass
    new_conn = psycopg2.connect(engine["url"])
    engine["conn"] = new_conn
    return new_conn


def _pg_exec(sql: str, params=None, fetch: str = None):
    conn = get_pg_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Crea todas las tablas si no existen."""
    if not PSYCOPG2_AVAILABLE:
        st.error("❌ psycopg2 no instalado. Agrega `psycopg2-binary` a requirements.txt.")
        st.stop()
    try:
        conn = get_pg_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
    except Exception as e:
        st.error(f"❌ Error inicializando PostgreSQL: {e}")

# ── Mapeo columnas Sheets → snake_case PG ────────────────────────────────────
def _col_pg(c: str) -> str:
    return c.lower()

def _pg_read(hoja: str,
             where_col: str = None,
             where_val: str = None) -> list[dict]:
    """
    Lee todos los registros de una tabla.
    Retorna lista de dicts con claves = columnas de DRIVE_SHEETS (TitleCase).
    """
    tabla  = _TABLA.get(hoja)
    cols_s = DRIVE_SHEETS.get(hoja, [])
    if not tabla or not cols_s:
        return []
    where  = f'WHERE "{_col_pg(where_col)}" = %s' if where_col else ""
    params = [where_val] if where_col else None
    try:
        rows = _pg_exec(f"SELECT * FROM {tabla} {where} ORDER BY 1",
                        params, fetch="all") or []
    except Exception as e:
        st.warning(f"⚠️ Error leyendo {tabla}: {e}")
        return []
    result = []
    for row in rows:
        rec = {}
        for sh_col in cols_s:
            val = row.get(_col_pg(sh_col), "")
            rec[sh_col] = "" if val is None else str(val)
        result.append(rec)
    return result


def _pg_insert(hoja: str, fila: list) -> bool:
    """INSERT en la tabla PG correspondiente."""
    tabla  = _TABLA.get(hoja)
    cols_s = DRIVE_SHEETS.get(hoja, [])
    if not tabla or not cols_s:
        return False
    # Descartar columna SERIAL si existe (facturas_items tiene id SERIAL)
    cols_pg = [_col_pg(c) for c in cols_s]
    fila_s  = [str(v) if v is not None else "" for v in fila]
    fila_s  = (fila_s + [""] * len(cols_pg))[:len(cols_pg)]
    cols_sql = ", ".join(f'"{c}"' for c in cols_pg)
    ph       = ", ".join(["%s"] * len(cols_pg))
    try:
        _pg_exec(f"INSERT INTO {tabla} ({cols_sql}) VALUES ({ph})", fila_s)
        return True
    except Exception as e:
        st.warning(f"⚠️ Error insertando en {tabla}: {e}")
        return False


def _pg_upsert(hoja: str, pk_col: str, pk_val: str, fila: list) -> bool:
    """INSERT … ON CONFLICT (pk_col) DO UPDATE SET …"""
    tabla  = _TABLA.get(hoja)
    cols_s = DRIVE_SHEETS.get(hoja, [])
    if not tabla or not cols_s:
        return False
    cols_pg  = [_col_pg(c) for c in cols_s]
    fila_s   = [str(v) if v is not None else "" for v in fila]
    fila_s   = (fila_s + [""] * len(cols_pg))[:len(cols_pg)]
    pk_pg    = _col_pg(pk_col)
    cols_sql = ", ".join(f'"{c}"' for c in cols_pg)
    ph       = ", ".join(["%s"] * len(cols_pg))
    upd      = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols_pg if c != pk_pg)
    try:
        _pg_exec(
            f'INSERT INTO {tabla} ({cols_sql}) VALUES ({ph}) '
            f'ON CONFLICT ("{pk_pg}") DO UPDATE SET {upd}',
            fila_s
        )
        return True
    except Exception as e:
        st.warning(f"⚠️ Error upsert en {tabla}: {e}")
        return False


def _pg_update(hoja: str, pk_col: str, pk_val: str,
               set_col: str, new_val: str) -> bool:
    """UPDATE tabla SET set_col = new_val WHERE pk_col = pk_val."""
    tabla = _TABLA.get(hoja)
    if not tabla:
        return False
    try:
        _pg_exec(
            f'UPDATE {tabla} SET "{_col_pg(set_col)}" = %s WHERE "{_col_pg(pk_col)}" = %s',
            [new_val, pk_val]
        )
        return True
    except Exception as e:
        st.warning(f"⚠️ Error update en {tabla}: {e}")
        return False


def _pg_dup(hoja: str, campo: str, valor: str) -> bool:
    """True si ya existe campo == valor en la tabla."""
    tabla = _TABLA.get(hoja)
    if not tabla:
        return False
    try:
        row = _pg_exec(
            f'SELECT 1 FROM {tabla} WHERE LOWER("{_col_pg(campo)}") = LOWER(%s) LIMIT 1',
            [str(valor).strip()], fetch="one"
        )
        return row is not None
    except Exception:
        return False


def _pg_dup_multi(hoja: str, cv: dict) -> bool:
    """True si existe registro donde TODOS los campos coinciden."""
    tabla = _TABLA.get(hoja)
    if not tabla:
        return False
    conds  = " AND ".join(f'LOWER("{_col_pg(c)}") = LOWER(%s)' for c in cv)
    params = [str(v).strip() for v in cv.values()]
    try:
        row = _pg_exec(
            f"SELECT 1 FROM {tabla} WHERE {conds} LIMIT 1",
            params, fetch="one"
        )
        return row is not None
    except Exception:
        return False


# ── API pública (mismo nombre que antes → cero cambios en UI) ─────────────────

def gs_read(hoja: str) -> list:
    return _pg_read(hoja)

def gs_append(hoja: str, fila: list) -> bool:
    return _pg_insert(hoja, fila)

def gs_update_cell(hoja: str, pk_col: str, pk_val: str, set_col: str, new_val) -> bool:
    """
    Firma adaptada a PG: en vez de (hoja, fila_idx, col_idx, valor)
    usa (hoja, pk_col, pk_val, set_col, new_val).
    Todas las actualizaciones van directo a PostgreSQL via _pg_update.
    """
    return _pg_update(hoja, pk_col, pk_val, set_col, str(new_val))

def gs_dup(hoja: str, campo: str, valor: str) -> bool:
    return _pg_dup(hoja, campo, valor)

def gs_dup_multi(hoja: str, cv: dict) -> bool:
    return _pg_dup_multi(hoja, cv)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ═══════════════════════════════════════════════════════════════════════════════

USUARIOS_DEFAULT = {
    "admin":    {"hash": hashpw("admin2024"), "rol": "Admin",    "nombre": "Administrador"},
    "operador": {"hash": hashpw("op2024"),    "rol": "Operador", "nombre": "Operador"},
    "consulta": {"hash": hashpw("ver2024"),   "rol": "Consulta", "nombre": "Consulta"},
}

def init_state():
    for k, v in {"autenticado": False, "usuario": None, "rol": None, "pantalla": "login"}.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_login(usuario: str, password: str) -> Optional[dict]:
    try:
        for op in gs_read("Operadores"):
            if op.get("Usuario","").strip().lower() == usuario.strip().lower():
                if op.get("Activo","1") == "1" and op.get("Password_Hash","") == hashpw(password):
                    return {"nombre": op.get("Nombre", usuario), "rol": op.get("Rol","Operador")}
    except Exception:
        pass
    u = USUARIOS_DEFAULT.get(usuario.strip().lower())
    if u and u["hash"] == hashpw(password):
        return {"nombre": u["nombre"], "rol": u["rol"]}
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# PANTALLA LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

def show_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(f"""
        <div class="login-container">
          <div class="login-title">🔧 {NEGOCIO}</div>
          <div class="login-sub">{TAGLINE}<br><small>{DIRECCION}</small></div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            usuario  = st.text_input("👤 Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Contraseña")
            submit   = st.form_submit_button("INGRESAR", type="primary", use_container_width=True)
            if submit:
                if not usuario or not password:
                    st.error("Ingresa usuario y contraseña.")
                else:
                    ud = verificar_login(usuario, password)
                    if ud:
                        st.session_state.autenticado = True
                        st.session_state.usuario     = ud["nombre"]
                        st.session_state.rol         = ud["rol"]
                        st.session_state.pantalla    = "dashboard"
                        st.success(f"✅ Bienvenido/a {ud['nombre']}")
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas.")
        st.caption("Demo: admin/admin2024 · operador/op2024 · consulta/ver2024")

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:16px 0 8px">
          <div style="font-size:32px">🔧</div>
          <div style="font-weight:800;font-size:16px;color:#00d4ff;letter-spacing:1px">SUITE SALITRE</div>
          <div style="font-size:11px;color:#94a3b8">Terminal El Salitre · Bogotá</div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        rol     = st.session_state.rol or "Consulta"
        usuario = st.session_state.usuario or "—"
        st.caption(f"👤 {usuario}  ·  {rol}")
        st.divider()

        menu_all = ["📊 Dashboard","🏢 Convenios/Empresas","📦 Inventario",
                    "🔩 Repuestos","🖥️ Escáner","🛡️ Seguros",
                    "💳 Pagos","📄 Facturas","⚙️ Configuración"]
        menu_ro  = ["📊 Dashboard","📦 Inventario","🔩 Repuestos","🖥️ Escáner","🛡️ Seguros"]
        opciones = menu_ro if rol == "Consulta" else menu_all

        mapa = {
            "📊 Dashboard":          "dashboard",
            "🏢 Convenios/Empresas": "empresas",
            "📦 Inventario":         "inventario",
            "🔩 Repuestos":          "repuestos",
            "🖥️ Escáner":           "escaner",
            "🛡️ Seguros":           "seguros",
            "💳 Pagos":              "pagos",
            "📄 Facturas":           "facturas",
            "⚙️ Configuración":     "configuracion",
        }
        mapa_inv = {v: k for k, v in mapa.items()}
        actual   = mapa_inv.get(st.session_state.get("pantalla","dashboard"), opciones[0])
        if actual not in opciones:
            actual = opciones[0]

        sel = st.radio("Menú", opciones, index=opciones.index(actual), label_visibility="collapsed")
        st.session_state.pantalla = mapa.get(sel, "dashboard")

        st.divider()
        # Estado de conexión PostgreSQL
        if PSYCOPG2_AVAILABLE:
            try:
                get_pg_conn().cursor().execute("SELECT 1")
                st.success("🐘 PostgreSQL conectado")
            except Exception:
                st.error("❌ PostgreSQL sin conexión")
        else:
            st.warning("⚠️ psycopg2 no instalado")

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            for k in ["autenticado","usuario","rol","pantalla"]:
                st.session_state[k] = False if k == "autenticado" else None
            st.session_state.pantalla = "login"
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_empresas() -> list:
    return gs_read("Empresa")

def get_empresas_activas() -> list:
    return [e for e in get_empresas() if e.get("Activo","1") == "1"]

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def show_dashboard():
    st.markdown('<div class="page-title">📊 Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">Resumen general · {ahora_col().strftime("%d/%m/%Y %H:%M")}</div>',
                unsafe_allow_html=True)

    with st.spinner("Cargando datos desde PostgreSQL..."):
        repuestos  = gs_read("Repuestos")
        escaner    = gs_read("Escaner")
        seguros    = gs_read("Seguros")
        pagos      = gs_read("Pagos")
        inventario = gs_read("Inventarios")
        empresas   = gs_read("Empresa")

    total_ingresos = sum(float(p.get("Monto_COP",0) or 0) for p in pagos)
    ing_rep = sum(float(r.get("Total_COP",0) or 0) for r in repuestos)
    ing_esc = sum(float(e.get("Total_COP",0) or 0) for e in escaner)
    ing_seg = sum(float(s.get("Prima_COP",0) or 0) for s in seguros)

    bajo_stock = [i for i in inventario
                  if float(i.get("Cantidad_Stock",0) or 0) <= float(i.get("Cantidad_Minima",0) or 0)
                  and float(i.get("Cantidad_Minima",0) or 0) > 0]
    hoy = ahora_col().date()
    seg_vencer = []
    for s in seguros:
        fv = s.get("Fecha_Vencimiento","")
        if fv:
            try:
                fd = datetime.strptime(fv[:10],"%Y-%m-%d").date()
                if 0 <= (fd - hoy).days <= 30:
                    seg_vencer.append(s)
            except Exception:
                pass

    if bajo_stock:
        st.markdown(f'<div class="alerta-stock">⚠️ {len(bajo_stock)} ítem(s) con stock bajo</div>',
                    unsafe_allow_html=True)
    if seg_vencer:
        st.markdown(f'<div class="alerta-vencimiento">🛡️ {len(seg_vencer)} seguro(s) vence(n) en 30 días</div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Total Ingresos",    fmt_cop(total_ingresos))
    c2.metric("🔩 Órdenes Repuestos", len(repuestos))
    c3.metric("🖥️ Servicios Escáner", len(escaner))
    c4.metric("🛡️ Seguros Activos",  len([s for s in seguros if s.get("Estado","") == "Activo"]))
    c5.metric("🏢 Empresas Convenio", len(empresas))

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="card-title">💰 Ingresos por servicio</div>', unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            df_ing = pd.DataFrame({"Servicio":["Repuestos","Escáner","Seguros"],
                                   "Total":   [ing_rep, ing_esc, ing_seg]})
            fig = px.bar(df_ing, x="Servicio", y="Total", color="Servicio",
                         template="plotly_dark",
                         color_discrete_sequence=["#00d4ff","#00ff88","#ffd32a"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              showlegend=False, margin=dict(t=20,b=20,l=10,r=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("pip install plotly para ver gráficas")

    with col_b:
        st.markdown('<div class="card-title">📦 Estado Inventario</div>', unsafe_allow_html=True)
        if inventario and PLOTLY_AVAILABLE:
            from collections import Counter
            est = Counter(i.get("Estado","Disponible") for i in inventario)
            cm  = {"Disponible":"#00ff88","Reservado":"#00d4ff","Agotado":"#ff4757","Descontinuado":"#94a3b8"}
            fig2 = px.pie(names=list(est.keys()), values=list(est.values()),
                          template="plotly_dark", color=list(est.keys()), color_discrete_map=cm)
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20,b=20,l=10,r=10))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin datos de inventario")

    st.markdown("---")
    st.markdown('<div class="card-title">📋 Últimas 10 transacciones</div>', unsafe_allow_html=True)
    ultimas = sorted(pagos, key=lambda x: x.get("Fecha_Pago",""), reverse=True)[:10]
    if ultimas:
        st.dataframe(pd.DataFrame([{
            "Fecha":p.get("Fecha_Pago",""), "Empresa":p.get("Nombre_Empresa","—"),
            "Servicio":p.get("Tipo_Servicio",""), "Monto":fmt_cop(p.get("Monto_COP",0)),
            "Estado":p.get("Estado",""),
        } for p in ultimas]), use_container_width=True, hide_index=True)
    else:
        st.info("Sin transacciones registradas.")

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: CONVENIOS / EMPRESAS
# ═══════════════════════════════════════════════════════════════════════════════

def show_empresas():
    st.markdown('<div class="page-title">🏢 Convenios y Empresas</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Registro y gestión de empresas de transporte con convenio</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Listado","➕ Nueva Empresa","✏️ Editar/Inactivar"])

    with tab1:
        empresas = gs_read("Empresa")
        if not empresas:
            st.info("Sin empresas registradas.")
        else:
            st.dataframe(pd.DataFrame([{
                "ID":e.get("Id_Empresa",""), "Nombre":e.get("Nombre_Empresa",""),
                "NIT":e.get("Nit_Empresa",""), "Tipo":e.get("Tipo_Empresa",""),
                "Convenio":e.get("Tipo_Convenio",""),
                "Dto. Rep. %":e.get("Descuento_Repuestos_Pct","0"),
                "Dto. Esc. %":e.get("Descuento_Escaner_Pct","0"),
                "Activo":"✅" if e.get("Activo","1") == "1" else "❌",
            } for e in empresas]), use_container_width=True, hide_index=True)

    with tab2:
        with st.form("form_empresa"):
            st.markdown("**Datos de la empresa**")
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Nombre de la Empresa *")
                nit    = st.text_input("NIT *")
                tipo   = st.selectbox("Tipo de empresa", TIPOS_EMPRESA)
                email  = st.text_input("Email")
                tel    = st.text_input("Teléfono")
            with c2:
                contacto      = st.text_input("Nombre contacto")
                cargo         = st.text_input("Cargo contacto")
                tipo_convenio = st.selectbox("Tipo de convenio", TIPOS_CONVENIO)
                dto_rep  = st.number_input("Descuento Repuestos %", 0.0, 100.0, 0.0, 0.5)
                dto_esc  = st.number_input("Descuento Escáner %",   0.0, 100.0, 0.0, 0.5)
                cred_max = st.number_input("Crédito máximo COP", 0, 100_000_000, 0, 100_000)
            obs     = st.text_area("Observaciones")
            guardar = st.form_submit_button("💾 Guardar Empresa", type="primary", use_container_width=True)
            if guardar:
                nv = nombre.strip(); nitv = nit.strip()
                if not nv or not nitv:
                    st.error("❌ Nombre y NIT son obligatorios.")
                elif gs_dup("Empresa","Nit_Empresa", nitv):
                    st.warning(f"⚠️ Ya existe una empresa con NIT {nitv}.")
                elif gs_dup("Empresa","Nombre_Empresa", nv):
                    st.warning(f"⚠️ Ya existe una empresa llamada {nv}.")
                else:
                    fila = [gen_id("EMP-"), nv, nitv, tipo, email.strip(), tel.strip(),
                            contacto.strip(), cargo.strip(), tipo_convenio,
                            str(dto_rep), str(dto_esc), str(cred_max),
                            obs.strip(), "1", ahora_col().isoformat()]
                    if gs_append("Empresa", fila):
                        st.success(f"✅ Empresa **{nv}** registrada en PostgreSQL.")

    with tab3:
        empresas = gs_read("Empresa")
        if not empresas:
            st.info("Sin empresas para editar.")
        else:
            opc = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
            sel = st.selectbox("Seleccionar empresa", list(opc.keys()))
            emp = opc[sel]
            c1, c2 = st.columns(2)
            with c1:
                nd_rep = st.number_input("Dto. Repuestos %", 0.0, 100.0,
                                         float(emp.get("Descuento_Repuestos_Pct",0) or 0), 0.5)
                nd_esc = st.number_input("Dto. Escáner %", 0.0, 100.0,
                                         float(emp.get("Descuento_Escaner_Pct",0) or 0), 0.5)
            with c2:
                nd_cred = st.number_input("Crédito máximo COP", 0, 100_000_000,
                                          int(float(emp.get("Credito_Maximo_COP",0) or 0)), 100_000)
                nd_act  = st.checkbox("Empresa activa", value=emp.get("Activo","1") == "1")
            if st.button("💾 Actualizar", type="primary", use_container_width=True, key="btn_upd_emp"):
                eid = emp.get("Id_Empresa","")
                for col_n, val in [
                    ("Descuento_Repuestos_Pct", str(nd_rep)),
                    ("Descuento_Escaner_Pct",   str(nd_esc)),
                    ("Credito_Maximo_COP",      str(nd_cred)),
                    ("Activo",                  "1" if nd_act else "0"),
                ]:
                    _pg_update("Empresa", "Id_Empresa", eid, col_n, val)
                st.success("✅ Empresa actualizada en PostgreSQL.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: INVENTARIO
# ═══════════════════════════════════════════════════════════════════════════════

def show_inventario():
    st.markdown('<div class="page-title">📦 Inventario</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Control de stock de Repuestos y Equipos de Escáner</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Stock Actual","➕ Agregar Ítem","⚙️ Ajustar Stock"])

    with tab1:
        inventario = gs_read("Inventarios")
        c1,c2,c3 = st.columns(3)
        ft = c1.selectbox("Tipo",      ["Todos","Repuesto","Escáner","Otro"])
        fc = c2.selectbox("Categoría", ["Todas"] + CATEGORIAS_REP)
        fe = c3.selectbox("Estado",    ["Todos"] + ESTADOS_INV)
        items = [i for i in inventario
                 if (ft == "Todos" or i.get("Tipo") == ft)
                 and (fc == "Todas" or i.get("Categoria") == fc)
                 and (fe == "Todos" or i.get("Estado") == fe)]
        bajo = [i for i in items
                if float(i.get("Cantidad_Stock",0) or 0) <= float(i.get("Cantidad_Minima",0) or 0)
                and float(i.get("Cantidad_Minima",0) or 0) > 0]
        if bajo:
            st.markdown(f'<div class="alerta-stock">⚠️ {len(bajo)} ítem(s) bajo stock mínimo: '
                        + ", ".join(i.get("Nombre","?") for i in bajo[:5]) + "</div>",
                        unsafe_allow_html=True)
        if not items:
            st.info("Sin ítems con esos filtros.")
        else:
            st.dataframe(pd.DataFrame([{
                "SKU":i.get("Codigo_SKU",""), "Nombre":i.get("Nombre",""),
                "Tipo":i.get("Tipo",""), "Categoría":i.get("Categoria",""),
                "Marca":i.get("Marca",""), "Stock":i.get("Cantidad_Stock","0"),
                "Mín.":i.get("Cantidad_Minima","0"),
                "P. Venta":fmt_cop(i.get("Precio_Venta_COP",0)), "Estado":i.get("Estado",""),
            } for i in items]), use_container_width=True, hide_index=True)

    with tab2:
        with st.form("form_inventario"):
            c1, c2 = st.columns(2)
            with c1:
                tipo_item   = st.selectbox("Tipo de ítem", ["Repuesto","Escáner","Herramienta","Otro"])
                sku         = st.text_input("Código SKU *")
                nombre_item = st.text_input("Nombre del ítem *")
                descripcion = st.text_area("Descripción", height=80)
                categoria   = st.selectbox("Categoría", CATEGORIAS_REP)
            with c2:
                marca      = st.text_input("Marca")
                referencia = st.text_input("Referencia / Número de parte")
                qty        = st.number_input("Cantidad en stock *", 0, 100000, 0)
                qty_min    = st.number_input("Cantidad mínima (alerta)", 0, 100000, 5)
                p_compra   = st.number_input("Precio de compra COP", 0, 500_000_000, 0, 1000)
                p_venta    = st.number_input("Precio de venta COP",  0, 500_000_000, 0, 1000)
                ubicacion  = st.text_input("Ubicación en bodega")
                estado_item= st.selectbox("Estado", ESTADOS_INV)
            guardar_inv = st.form_submit_button("💾 Registrar Ítem", type="primary", use_container_width=True)
            if guardar_inv:
                skuv = sku.strip(); nomv = nombre_item.strip()
                if not skuv or not nomv:
                    st.error("❌ SKU y Nombre son obligatorios.")
                elif gs_dup("Inventarios","Codigo_SKU", skuv):
                    st.warning(f"⚠️ Ya existe un ítem con SKU {skuv}.")
                else:
                    ahora = ahora_col().isoformat()
                    fila  = [gen_id("INV-"), tipo_item, skuv, nomv, descripcion,
                             categoria, marca, referencia, str(qty), str(qty_min),
                             str(p_compra), str(p_venta), ubicacion, estado_item, ahora, ahora]
                    if gs_append("Inventarios", fila):
                        st.success(f"✅ Ítem **{nomv}** (SKU: {skuv}) registrado en PostgreSQL.")

    with tab3:
        inventario = gs_read("Inventarios")
        if not inventario:
            st.info("Sin ítems para ajustar.")
        else:
            opc_inv = {f"{i.get('Codigo_SKU','')} — {i.get('Nombre','')}": i for i in inventario}
            sel_inv = st.selectbox("Seleccionar ítem", list(opc_inv.keys()))
            item_s  = opc_inv[sel_inv]
            c1, c2  = st.columns(2)
            stock_act = int(float(item_s.get("Cantidad_Stock",0) or 0))
            c1.metric("Stock actual", stock_act)
            nuevo_stock    = c1.number_input("Nuevo stock", 0, 1_000_000, stock_act)
            nuevo_est_item = c2.selectbox("Estado", ESTADOS_INV,
                                          index=ESTADOS_INV.index(item_s.get("Estado","Disponible"))
                                          if item_s.get("Estado","") in ESTADOS_INV else 0)
            if st.button("💾 Actualizar Stock", type="primary", use_container_width=True):
                iid = item_s.get("Id_Item","")
                _pg_update("Inventarios","Id_Item", iid, "Cantidad_Stock",  str(nuevo_stock))
                _pg_update("Inventarios","Id_Item", iid, "Estado",          nuevo_est_item)
                _pg_update("Inventarios","Id_Item", iid, "Actualizado_En",  ahora_col().isoformat())
                st.success("✅ Stock actualizado en PostgreSQL.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: REPUESTOS
# ═══════════════════════════════════════════════════════════════════════════════

def _descontar_inventario(id_item: str, qty: int):
    """Descuenta qty unidades del item en rs_inventarios."""
    try:
        row = _pg_exec(
            'SELECT cantidad_stock FROM rs_inventarios WHERE id_item = %s',
            [id_item], fetch="one"
        )
        if row:
            stock_prev = int(float(row.get("cantidad_stock") or 0))
            nuevo_stk  = max(0, stock_prev - qty)
            _pg_update("Inventarios","Id_Item", id_item, "Cantidad_Stock",  str(nuevo_stk))
            _pg_update("Inventarios","Id_Item", id_item, "Actualizado_En",  ahora_col().isoformat())
            if nuevo_stk == 0:
                _pg_update("Inventarios","Id_Item", id_item, "Estado", "Agotado")
    except Exception as ex:
        st.warning(f"⚠️ No se pudo descontar inventario: {ex}")


def show_repuestos():
    st.markdown('<div class="page-title">🔩 Repuestos</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Solicitudes y despacho de repuestos para flotas</div>',
                unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Historial","➕ Nueva Solicitud"])

    with tab1:
        repuestos = gs_read("Repuestos")
        c1, c2    = st.columns(2)
        f_est = c1.selectbox("Estado", ["Todos","Pendiente","Aprobado","Despachado","Entregado","Cancelado"])
        f_emp = c2.text_input("Filtrar empresa")
        items = [r for r in repuestos
                 if (f_est == "Todos" or r.get("Estado_Pedido") == f_est)
                 and (not f_emp or f_emp.lower() in r.get("Nombre_Empresa","").lower())]
        if not items:
            st.info("Sin solicitudes.")
        else:
            st.dataframe(pd.DataFrame([{
                "ID":r.get("Id_Repuesto",""), "Fecha":r.get("Fecha_Solicitud",""),
                "Empresa":r.get("Nombre_Empresa",""), "Repuesto":r.get("Nombre_Repuesto",""),
                "Qty":r.get("Cantidad",""), "Total":fmt_cop(r.get("Total_COP",0)),
                "Placa":r.get("Placa_Vehiculo",""), "Estado":r.get("Estado_Pedido",""),
            } for r in items]), use_container_width=True, hide_index=True)

    with tab2:
        empresas = get_empresas_activas()
        if not empresas:
            st.warning("Registra al menos una empresa primero.")
            return
        inventario = gs_read("Inventarios")
        items_disp = [i for i in inventario
                      if i.get("Estado","") == "Disponible"
                      and float(i.get("Cantidad_Stock",0) or 0) > 0]

        with st.form("form_repuesto"):
            c1, c2 = st.columns(2)
            with c1:
                opc_emp = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
                sel_emp = st.selectbox("Empresa *", list(opc_emp.keys()))
                emp_r   = opc_emp[sel_emp]
                placa   = st.text_input("Placa del vehículo *")
                tipo_v  = st.selectbox("Tipo de vehículo", TIPOS_VEHICULO)
                mecanico= st.text_input("Mecánico responsable")
            with c2:
                if items_disp:
                    opc_it  = {f"{i.get('Codigo_SKU','')} — {i.get('Nombre','')}": i for i in items_disp}
                    sel_it  = st.selectbox("Repuesto (inventario) *", list(opc_it.keys()))
                    item_r  = opc_it[sel_it]
                    p_base  = float(item_r.get("Precio_Venta_COP",0) or 0)
                    dto_def = float(emp_r.get("Descuento_Repuestos_Pct",0) or 0)
                    qty_r   = st.number_input("Cantidad *", 1,
                                              int(float(item_r.get("Cantidad_Stock",999) or 999)), 1)
                    dto_r   = st.number_input("Descuento %", 0.0, 100.0, dto_def, 0.5)
                    p_unit  = st.number_input("Precio unitario COP", 0, 500_000_000, int(p_base), 100)
                else:
                    st.warning("Sin repuestos disponibles en inventario.")
                    nom_lib = st.text_input("Nombre del repuesto (manual)")
                    cat_lib = st.selectbox("Categoría", CATEGORIAS_REP)
                    qty_r   = st.number_input("Cantidad *", 1, 10000, 1)
                    dto_r   = st.number_input("Descuento %", 0.0, 100.0,
                                              float(emp_r.get("Descuento_Repuestos_Pct",0) or 0), 0.5)
                    p_unit  = st.number_input("Precio unitario COP", 0, 500_000_000, 0, 100)
                    item_r  = {"Nombre": nom_lib, "Codigo_SKU": "", "Categoria": cat_lib}
            obs_r   = st.text_area("Observaciones")
            est_rep = st.selectbox("Estado del pedido",
                                   ["Pendiente","Aprobado","Despachado","Entregado","Cancelado"])
            total_r = qty_r * p_unit * (1 - dto_r / 100)
            guardar_rep = st.form_submit_button("💾 Registrar Solicitud", type="primary", use_container_width=True)
            if guardar_rep:
                if not placa.strip():
                    st.error("❌ La placa es obligatoria.")
                elif gs_dup_multi("Repuestos",{
                    "Placa_Vehiculo":placa.strip(),
                    "Codigo_SKU":item_r.get("Codigo_SKU",""),
                    "Nombre_Empresa":emp_r.get("Nombre_Empresa",""),
                }):
                    st.warning("⚠️ Ya existe una solicitud para esta placa, empresa y repuesto.")
                else:
                    fila_r = [gen_id("REP-"), emp_r.get("Id_Empresa",""), emp_r.get("Nombre_Empresa",""),
                              ahora_col().strftime("%Y-%m-%d %H:%M"),
                              item_r.get("Codigo_SKU",""), item_r.get("Nombre",""),
                              item_r.get("Categoria",""), str(qty_r), str(p_unit),
                              str(dto_r), str(round(total_r,2)),
                              est_rep, placa.strip(), tipo_v, mecanico, obs_r,
                              st.session_state.usuario or "Sistema"]
                    if gs_append("Repuestos", fila_r):
                        num_fac = f"FAC-{ahora_col().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                        iva_val = round(total_r * 0.19, 2)
                        fila_fac = [gen_id("FAC-"), num_fac,
                                    emp_r.get("Id_Empresa",""), emp_r.get("Nombre_Empresa",""),
                                    ahora_col().strftime("%Y-%m-%d"), ahora_col().strftime("%Y-%m-%d"),
                                    str(round(total_r,2)), str(round(total_r*dto_r/100,2)),
                                    str(iva_val), str(round(total_r+iva_val,2)),
                                    "Emitida",
                                    f"Repuesto: {item_r.get('Nombre','')} · Placa: {placa.strip()}",
                                    st.session_state.usuario or "Sistema"]
                        gs_append("Facturas", fila_fac)
                        gs_append("Facturas_Items",
                                  [gen_id("FI-"), num_fac, num_fac,
                                   "Repuesto", item_r.get("Nombre",""), str(qty_r),
                                   str(p_unit), str(dto_r), str(round(total_r,2))])
                        if est_rep in ("Despachado","Entregado") and item_r.get("Id_Item",""):
                            _descontar_inventario(item_r["Id_Item"], qty_r)
                        st.success(f"✅ Solicitud registrada · Total: {fmt_cop(total_r)} · Factura: {num_fac}")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ESCÁNER
# ═══════════════════════════════════════════════════════════════════════════════

def show_escaner():
    st.markdown('<div class="page-title">🖥️ Escáner Vehicular</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Diagnóstico y servicios de escáner para flotas</div>',
                unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Historial","➕ Nuevo Servicio"])

    with tab1:
        sv = gs_read("Escaner")
        if not sv:
            st.info("Sin servicios registrados.")
        else:
            st.dataframe(pd.DataFrame([{
                "ID":s.get("Id_Escaner",""), "Fecha":s.get("Fecha_Servicio",""),
                "Empresa":s.get("Nombre_Empresa",""), "Placa":s.get("Placa_Vehiculo",""),
                "Tipo Escáner":s.get("Tipo_Escaner",""), "Técnico":s.get("Tecnico",""),
                "Total":fmt_cop(s.get("Total_COP",0)), "Estado":s.get("Estado",""),
            } for s in sv]), use_container_width=True, hide_index=True)

    with tab2:
        empresas = get_empresas_activas()
        if not empresas:
            st.warning("Registra al menos una empresa primero.")
            return
        tarifas = [t for t in gs_read("Tarifas_Config")
                   if t.get("Tipo_Servicio","") == "Escaner" and t.get("Activo","1") == "1"]

        with st.form("form_escaner"):
            c1, c2 = st.columns(2)
            with c1:
                opc_emp_e = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
                sel_emp_e = st.selectbox("Empresa *", list(opc_emp_e.keys()))
                emp_e     = opc_emp_e[sel_emp_e]
                placa_e   = st.text_input("Placa del vehículo *")
                tipo_v_e  = st.selectbox("Tipo de vehículo", TIPOS_VEHICULO)
                tecnico   = st.text_input("Técnico responsable")
            with c2:
                tipo_esc = st.selectbox("Tipo de escáner *", TIPOS_ESCANER)
                if tarifas:
                    opc_tar  = {f"{t.get('Nombre_Tarifa','')} — {fmt_cop(t.get('Precio_COP',0))}": t for t in tarifas}
                    sel_tar  = st.selectbox("Tarifa", list(opc_tar.keys()))
                    p_base_e = float(opc_tar[sel_tar].get("Precio_COP",0) or 0)
                else:
                    p_base_e = st.number_input("Precio base COP", 0, 5_000_000, 80000, 5000)
                dto_e   = st.number_input("Descuento %", 0.0, 100.0,
                                          float(emp_e.get("Descuento_Escaner_Pct",0) or 0), 0.5)
                total_e = p_base_e * (1 - dto_e / 100)
                st.info(f"Total a cobrar: **{fmt_cop(total_e)}**")
            codigos = st.text_area("Códigos de falla encontrados", height=80)
            result  = st.text_area("Resultado del diagnóstico",   height=80)
            recom   = st.text_area("Recomendaciones",             height=80)
            est_esc = st.selectbox("Estado del servicio",
                                   ["Completado","En proceso","Pendiente","Cancelado"])
            guardar_esc = st.form_submit_button("💾 Registrar Servicio", type="primary", use_container_width=True)
            if guardar_esc:
                if not placa_e.strip():
                    st.error("❌ La placa es obligatoria.")
                elif gs_dup_multi("Escaner",{
                    "Placa_Vehiculo":placa_e.strip(),
                    "Tipo_Escaner":tipo_esc,
                    "Nombre_Empresa":emp_e.get("Nombre_Empresa",""),
                }):
                    st.warning("⚠️ Ya existe un servicio de escáner para esta placa, tipo y empresa.")
                else:
                    fila_e = [gen_id("ESC-"), emp_e.get("Id_Empresa",""), emp_e.get("Nombre_Empresa",""),
                              ahora_col().strftime("%Y-%m-%d %H:%M"),
                              placa_e.strip(), tipo_v_e, tipo_esc, tecnico,
                              str(round(p_base_e,2)), str(dto_e), str(round(total_e,2)),
                              result, codigos, recom, est_esc,
                              st.session_state.usuario or "Sistema"]
                    if gs_append("Escaner", fila_e):
                        num_fac_e = f"FAC-{ahora_col().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                        iva_e     = round(total_e * 0.19, 2)
                        fila_fac_e = [gen_id("FAC-"), num_fac_e,
                                      emp_e.get("Id_Empresa",""), emp_e.get("Nombre_Empresa",""),
                                      ahora_col().strftime("%Y-%m-%d"), ahora_col().strftime("%Y-%m-%d"),
                                      str(round(total_e,2)), "0", str(iva_e),
                                      str(round(total_e+iva_e,2)),
                                      "Emitida",
                                      f"Escáner: {tipo_esc} · Placa: {placa_e.strip()}",
                                      st.session_state.usuario or "Sistema"]
                        gs_append("Facturas", fila_fac_e)
                        gs_append("Facturas_Items",
                                  [gen_id("FI-"), num_fac_e, num_fac_e,
                                   "Escaner", f"{tipo_esc} — {placa_e.strip()}", "1",
                                   str(round(p_base_e,2)), str(dto_e), str(round(total_e,2))])
                        if est_esc in ("Despachado","Entregado","Completado"):
                            inv_esc = [i for i in gs_read("Inventarios")
                                       if i.get("Tipo","") == "Escáner"
                                       and i.get("Estado","") == "Disponible"
                                       and float(i.get("Cantidad_Stock",0) or 0) > 0]
                            if inv_esc:
                                _descontar_inventario(inv_esc[0].get("Id_Item",""), 1)
                        st.success(f"✅ Servicio registrado · Total: {fmt_cop(total_e)} · Factura: {num_fac_e}")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: SEGUROS
# ═══════════════════════════════════════════════════════════════════════════════

def show_seguros():
    st.markdown('<div class="page-title">🛡️ Seguros de Vehículos</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Control de pólizas para la flota</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Pólizas Activas","➕ Registrar Seguro","⏰ Por Vencer"])

    with tab1:
        seguros = gs_read("Seguros")
        activos = [s for s in seguros if s.get("Estado","") in ("Activo","Vigente","")]
        if not activos:
            st.info("Sin pólizas activas.")
        else:
            st.dataframe(pd.DataFrame([{
                "Placa":s.get("Placa_Vehiculo",""), "Tipo Vehículo":s.get("Tipo_Vehiculo",""),
                "Empresa":s.get("Nombre_Empresa",""), "Tipo Seguro":s.get("Tipo_Seguro",""),
                "Aseguradora":s.get("Aseguradora",""), "N° Póliza":s.get("Num_Poliza",""),
                "Inicio":s.get("Fecha_Inicio",""), "Vencimiento":s.get("Fecha_Vencimiento",""),
                "Prima":fmt_cop(s.get("Prima_COP",0)), "Estado":s.get("Estado",""),
            } for s in activos]), use_container_width=True, hide_index=True)

    with tab2:
        empresas = get_empresas_activas()
        with st.form("form_seguro"):
            c1, c2 = st.columns(2)
            with c1:
                if empresas:
                    opc_emp_s = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
                    sel_emp_s = st.selectbox("Empresa (opcional)", ["— Particular —"] + list(opc_emp_s.keys()))
                    emp_s     = opc_emp_s.get(sel_emp_s, {})
                else:
                    emp_s = {}
                placa_s    = st.text_input("Placa del vehículo *")
                tipo_v_s   = st.selectbox("Tipo de vehículo", TIPOS_VEHICULO)
                propietario= st.text_input("Propietario / Conductor")
                tipo_seg   = st.selectbox("Tipo de seguro *", TIPOS_SEGURO)
            with c2:
                aseguradora= st.text_input("Aseguradora *")
                num_poliza = st.text_input("Número de póliza *")
                f_inicio   = st.date_input("Fecha inicio *", value=date.today())
                f_venc     = st.date_input("Fecha vencimiento *", value=date.today())
                prima      = st.number_input("Prima COP", 0, 500_000_000, 0, 10000)
                cobertura  = st.number_input("Cobertura máxima COP", 0, 5_000_000_000, 0, 1_000_000)
            obs_s       = st.text_area("Observaciones")
            est_seg     = st.selectbox("Estado de la póliza",
                                       ["Activo","Vigente","Vencido","Cancelado","Suspendido"])
            guardar_seg = st.form_submit_button("💾 Registrar Póliza", type="primary", use_container_width=True)
            if guardar_seg:
                if not placa_s.strip() or not aseguradora.strip() or not num_poliza.strip():
                    st.error("❌ Placa, aseguradora y número de póliza son obligatorios.")
                elif f_venc < f_inicio:
                    st.error("❌ La fecha de vencimiento debe ser posterior al inicio.")
                elif gs_dup("Seguros","Num_Poliza", num_poliza.strip()):
                    st.warning(f"⚠️ La póliza {num_poliza} ya está registrada.")
                else:
                    fila_s = [gen_id("SEG-"), emp_s.get("Id_Empresa",""), emp_s.get("Nombre_Empresa",""),
                              placa_s.strip(), tipo_v_s, propietario,
                              tipo_seg, aseguradora.strip(), num_poliza.strip(),
                              f_inicio.isoformat(), f_venc.isoformat(),
                              str(prima), str(cobertura), est_seg, obs_s,
                              st.session_state.usuario or "Sistema", ahora_col().isoformat()]
                    if gs_append("Seguros", fila_s):
                        st.success(f"✅ Póliza #{num_poliza} registrada para {placa_s}.")
                        st.rerun()

    with tab3:
        seguros = gs_read("Seguros")
        hoy = ahora_col().date()
        proximos = []
        for s in seguros:
            fv = s.get("Fecha_Vencimiento","")
            if fv:
                try:
                    fd   = datetime.strptime(fv[:10],"%Y-%m-%d").date()
                    dias = (fd - hoy).days
                    if 0 <= dias <= 60:
                        proximos.append({**s, "_dias": dias})
                except Exception:
                    pass
        proximos.sort(key=lambda x: x["_dias"])
        if not proximos:
            st.success("✅ Sin seguros venciendo en los próximos 60 días.")
        else:
            for s in proximos:
                dias  = s["_dias"]
                color = "red" if dias <= 15 else ("yellow" if dias <= 30 else "cyan")
                badge = f'<span class="badge badge-{color}">Vence en {dias} días</span>'
                st.markdown(
                    f'<div class="card"><b>{s.get("Placa_Vehiculo","")}</b> · '
                    f'{s.get("Aseguradora","")} · Póliza #{s.get("Num_Poliza","")} '
                    f'· {s.get("Tipo_Seguro","")} · {badge}</div>',
                    unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: PAGOS
# ═══════════════════════════════════════════════════════════════════════════════

def show_pagos():
    st.markdown('<div class="page-title">💳 Pagos</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Registro y control de pagos por servicios</div>',
                unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Historial de Pagos","➕ Registrar Pago"])

    with tab1:
        pagos = gs_read("Pagos")
        if not pagos:
            st.info("Sin pagos registrados.")
        else:
            total_conf = sum(float(p.get("Monto_COP",0) or 0)
                             for p in pagos if p.get("Estado","") == "Confirmado")
            st.metric("💰 Total Cobrado (confirmados)", fmt_cop(total_conf))
            st.dataframe(pd.DataFrame([{
                "Fecha":p.get("Fecha_Pago",""), "Empresa":p.get("Nombre_Empresa",""),
                "Servicio":p.get("Tipo_Servicio",""), "Referencia":p.get("Referencia_Servicio",""),
                "Monto":fmt_cop(p.get("Monto_COP",0)), "Método":p.get("Metodo_Pago",""),
                "Estado":p.get("Estado",""), "Confirmado por":p.get("Confirmado_Por",""),
            } for p in pagos]), use_container_width=True, hide_index=True)

    with tab2:
        empresas = get_empresas_activas()
        with st.form("form_pago"):
            c1, c2 = st.columns(2)
            with c1:
                if empresas:
                    opc_emp_p = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
                    sel_emp_p = st.selectbox("Empresa *", list(opc_emp_p.keys()))
                    emp_p     = opc_emp_p[sel_emp_p]
                else:
                    emp_p = {}; st.info("Sin empresas registradas.")
                tipo_svc = st.selectbox("Tipo de servicio *", ["Repuesto","Escáner","Seguro","Otro"])
                ref_svc  = st.text_input("ID / Referencia del servicio")
            with c2:
                monto_p  = st.number_input("Monto COP *", 0, 500_000_000, 0, 1000)
                metodo_p = st.selectbox("Método de pago",
                                        ["Efectivo","Transferencia","Nequi","Daviplata","Tarjeta","Cheque","Convenio"])
                estado_p = st.selectbox("Estado", ["Confirmado","Pendiente","Anulado"])
                obs_p    = st.text_area("Observaciones")
            guardar_pago = st.form_submit_button("💾 Registrar Pago", type="primary", use_container_width=True)
            if guardar_pago:
                if monto_p <= 0:
                    st.error("❌ El monto debe ser mayor a 0.")
                else:
                    fila_p = [gen_id("PAG-"), emp_p.get("Id_Empresa",""), emp_p.get("Nombre_Empresa",""),
                              ahora_col().strftime("%Y-%m-%d %H:%M"),
                              tipo_svc, ref_svc, str(monto_p), metodo_p, estado_p,
                              st.session_state.usuario or "Sistema", obs_p]
                    if gs_append("Pagos", fila_p):
                        st.success(f"✅ Pago de {fmt_cop(monto_p)} registrado en PostgreSQL.")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: FACTURAS
# ═══════════════════════════════════════════════════════════════════════════════

def _html_factura(fac: dict, items: list, empresa_info: dict) -> str:
    num      = fac.get("Num_Factura","—")
    emp_nom  = fac.get("Nombre_Empresa","—")
    emp_nit  = empresa_info.get("Nit_Empresa","—")
    emp_tel  = empresa_info.get("Telefono_Empresa","—")
    emp_email= empresa_info.get("Email_Empresa","—")
    f_emis   = fac.get("Fecha_Emision","—")
    f_venc   = fac.get("Fecha_Vencimiento","—")
    subtotal = float(fac.get("Subtotal_COP",0) or 0)
    dto      = float(fac.get("Descuento_COP",0) or 0)
    iva      = float(fac.get("IVA_COP",0) or 0)
    total    = float(fac.get("Total_COP",0) or 0)
    estado   = fac.get("Estado","Emitida")
    obs      = fac.get("Observaciones","")
    creado   = fac.get("Creado_Por","Sistema")
    badge_color = {"Pagada":"#00c853","Emitida":"#0288d1",
                   "Vencida":"#e53935","Anulada":"#757575"}.get(estado,"#0288d1")
    filas_items = ""
    if items:
        for it in items:
            desc  = it.get("Descripcion", it.get("Tipo_Servicio",""))
            qty   = it.get("Cantidad","1")
            p_u   = float(it.get("Precio_Unitario",0) or 0)
            dto_i = float(it.get("Descuento_Pct",0) or 0)
            sub_i = float(it.get("Subtotal",0) or 0)
            filas_items += f"""
            <tr>
              <td>{desc}</td><td style="text-align:center">{qty}</td>
              <td style="text-align:right">$ {p_u:,.0f}</td>
              <td style="text-align:center">{dto_i}%</td>
              <td style="text-align:right">$ {sub_i:,.0f}</td>
            </tr>"""
    else:
        filas_items = f"""<tr><td colspan="5" style="text-align:center;color:#888">
            {obs or "Sin ítems detallados"}</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Factura {num}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Inter',sans-serif;background:#f4f6f9;color:#1a1a2e;padding:20px;}}
.page{{max-width:860px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.12);overflow:hidden;}}
.header{{background:linear-gradient(135deg,#0d1f3c,#1a3a6c);color:#fff;padding:32px 40px;}}
.header-top{{display:flex;justify-content:space-between;align-items:flex-start;}}
.brand{{font-size:22px;font-weight:700;letter-spacing:1px;color:#00d4ff;}}
.brand-sub{{font-size:12px;color:#94a3b8;margin-top:4px;}}
.fac-num{{text-align:right;}}.fac-num .label{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;}}
.fac-num .num{{font-size:20px;font-weight:700;color:#fff;margin-top:4px;}}
.badge{{display:inline-block;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:700;color:#fff;background:{badge_color};margin-top:8px;}}
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0;}}
.info-box{{padding:24px 40px;border-bottom:1px solid #e8edf5;}}
.info-box:nth-child(odd){{border-right:1px solid #e8edf5;}}
.info-title{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;font-weight:600;margin-bottom:10px;}}
.info-line{{font-size:13px;color:#1e293b;margin-bottom:4px;}}
.info-line strong{{color:#0d1f3c;}}
.table-wrap{{padding:0 40px 24px;}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px;}}
thead tr{{background:#f1f5fb;}}
thead th{{padding:10px 12px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:#64748b;font-weight:600;}}
tbody tr{{border-bottom:1px solid #f1f5fb;}}tbody tr:hover{{background:#f8fafc;}}
tbody td{{padding:10px 12px;color:#334155;}}
.totals{{padding:0 40px 32px;display:flex;justify-content:flex-end;}}
.totals-box{{width:300px;}}
.totals-row{{display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:#64748b;border-bottom:1px solid #f1f5fb;}}
.totals-row.total{{font-size:16px;font-weight:700;color:#0d1f3c;border:none;padding-top:12px;}}
.footer{{background:#f8fafc;border-top:1px solid #e8edf5;padding:18px 40px;display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;}}
.obs{{padding:12px 16px;background:#fffbeb;border-left:3px solid #f59e0b;margin:0 40px 20px;border-radius:0 6px 6px 0;font-size:12px;color:#64748b;}}
@media print{{body{{background:#fff;padding:0;}}.page{{box-shadow:none;border-radius:0;}}.no-print{{display:none !important;}}}}
</style></head>
<body>
<div class="no-print" style="text-align:center;margin-bottom:20px">
  <button onclick="window.print()"
    style="background:#0d1f3c;color:#00d4ff;border:1.5px solid #00d4ff;padding:10px 32px;
           border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;letter-spacing:1px">
    🖨️ IMPRIMIR / GUARDAR PDF
  </button>
</div>
<div class="page">
  <div class="header">
    <div class="header-top">
      <div>
        <div class="brand">🔧 {NEGOCIO}</div>
        <div class="brand-sub">{TAGLINE}</div>
        <div class="brand-sub">{DIRECCION}</div>
        <div class="brand-sub">NIT {NIT} · {TELEFONO} · {EMAIL}</div>
      </div>
      <div class="fac-num">
        <div class="label">Factura de Venta</div>
        <div class="num">{num}</div>
        <div class="badge">{estado}</div>
      </div>
    </div>
  </div>
  <div class="info-grid">
    <div class="info-box">
      <div class="info-title">📋 Datos del Cliente</div>
      <div class="info-line"><strong>{emp_nom}</strong></div>
      <div class="info-line">NIT: {emp_nit}</div>
      <div class="info-line">Tel: {emp_tel}</div>
      <div class="info-line">{emp_email}</div>
    </div>
    <div class="info-box">
      <div class="info-title">📅 Fechas</div>
      <div class="info-line">Emisión: <strong>{f_emis}</strong></div>
      <div class="info-line">Vencimiento: <strong>{f_venc}</strong></div>
      <div class="info-line" style="margin-top:8px">Elaborado por: {creado}</div>
      <div class="info-line">Generado: {ahora_col().strftime("%d/%m/%Y %H:%M")}</div>
    </div>
  </div>
  <div class="table-wrap">
    <div class="info-title" style="padding-top:20px;margin-bottom:4px">📦 Detalle de Servicios</div>
    <table>
      <thead><tr>
        <th>Descripción</th><th style="text-align:center">Cant.</th>
        <th style="text-align:right">P. Unitario</th>
        <th style="text-align:center">Dto.</th>
        <th style="text-align:right">Subtotal</th>
      </tr></thead>
      <tbody>{filas_items}</tbody>
    </table>
  </div>
  {"<div class='obs'>📝 " + obs + "</div>" if obs else ""}
  <div class="totals">
    <div class="totals-box">
      <div class="totals-row"><span>Subtotal</span><span>$ {subtotal:,.0f}</span></div>
      <div class="totals-row"><span>Descuento</span><span>- $ {dto:,.0f}</span></div>
      <div class="totals-row"><span>IVA</span><span>$ {iva:,.0f}</span></div>
      <div class="totals-row total"><span>TOTAL A PAGAR</span><span>$ {total:,.0f}</span></div>
    </div>
  </div>
  <div class="footer">
    <span>Suite Salitre S.A.S · NIT {NIT}</span>
    <span>{TELEFONO} · {EMAIL}</span>
    <span>Factura #{num}</span>
  </div>
</div></body></html>"""


def show_facturas():
    st.markdown('<div class="page-title">📄 Facturas</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Consulta, impresión y generación de facturas</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Listado de Facturas","🖨️ Ver / Imprimir Factura","➕ Generar Nueva Factura"])

    with tab1:
        facturas = gs_read("Facturas")
        if not facturas:
            st.info("Sin facturas generadas.")
        else:
            c1, c2, c3 = st.columns(3)
            emp_nombres = sorted({f.get("Nombre_Empresa","") for f in facturas if f.get("Nombre_Empresa","")})
            f_emp_l = c1.selectbox("Filtrar empresa",  ["Todas"] + emp_nombres, key="list_emp")
            f_est_l = c2.selectbox("Filtrar estado",   ["Todos","Emitida","Pagada","Vencida","Anulada"], key="list_est")
            f_num_l = c3.text_input("Buscar N° factura", key="list_num")
            filtradas = [f for f in facturas
                         if (f_emp_l == "Todas" or f.get("Nombre_Empresa","") == f_emp_l)
                         and (f_est_l == "Todos" or f.get("Estado","") == f_est_l)
                         and (not f_num_l or f_num_l.lower() in f.get("Num_Factura","").lower())]
            st.caption(f"{len(filtradas)} factura(s) encontrada(s)")
            if not filtradas:
                st.info("Sin resultados para el filtro aplicado.")
            else:
                st.dataframe(pd.DataFrame([{
                    "N° Factura":f.get("Num_Factura",""), "Empresa":f.get("Nombre_Empresa",""),
                    "Emisión":f.get("Fecha_Emision",""), "Vencimiento":f.get("Fecha_Vencimiento",""),
                    "Subtotal":fmt_cop(f.get("Subtotal_COP",0)), "IVA":fmt_cop(f.get("IVA_COP",0)),
                    "Total":fmt_cop(f.get("Total_COP",0)), "Estado":f.get("Estado",""),
                    "Creado por":f.get("Creado_Por",""),
                } for f in filtradas]), use_container_width=True, hide_index=True)
            tot_fil = sum(float(f.get("Total_COP",0) or 0) for f in filtradas)
            st.markdown(f"**Total filtrado:** {fmt_cop(tot_fil)}")

    with tab2:
        st.markdown("#### 🔍 Buscar factura existente")
        facturas_all = gs_read("Facturas")
        empresas_all = gs_read("Empresa")

        if not facturas_all:
            st.info("No hay facturas registradas aún.")
        else:
            emp_con_fac = sorted({f.get("Nombre_Empresa","") for f in facturas_all if f.get("Nombre_Empresa","")})
            col_f1, col_f2 = st.columns([2, 2])
            sel_emp_imp = col_f1.selectbox("1. Seleccionar empresa",
                                           ["— Todas —"] + emp_con_fac, key="imp_emp")
            facs_empresa = [f for f in facturas_all
                            if sel_emp_imp == "— Todas —"
                            or f.get("Nombre_Empresa","") == sel_emp_imp]
            opc_fac = {
                f"{f.get('Num_Factura','?')}  ·  {f.get('Fecha_Emision','—')}  ·  {fmt_cop(f.get('Total_COP',0))}  ·  [{f.get('Estado','')}]": f
                for f in sorted(facs_empresa, key=lambda x: x.get("Fecha_Emision",""), reverse=True)
            }
            if not opc_fac:
                st.warning("No hay facturas para la empresa seleccionada.")
            else:
                sel_fac_key = col_f2.selectbox("2. Seleccionar factura", list(opc_fac.keys()), key="imp_fac")
                fac_sel     = opc_fac[sel_fac_key]
                items_all   = gs_read("Facturas_Items")
                num_sel     = fac_sel.get("Num_Factura","")
                items_fac   = [i for i in items_all
                               if i.get("Num_Factura","") == num_sel
                               or i.get("Id_Factura","") == num_sel]
                emp_info    = next((e for e in empresas_all
                                    if e.get("Nombre_Empresa","") == fac_sel.get("Nombre_Empresa","")), {})
                st.markdown("---")
                p1,p2,p3,p4 = st.columns(4)
                p1.metric("N° Factura",  fac_sel.get("Num_Factura","—"))
                p2.metric("Estado",      fac_sel.get("Estado","—"))
                p3.metric("Total",       fmt_cop(fac_sel.get("Total_COP",0)))
                p4.metric("Vencimiento", fac_sel.get("Fecha_Vencimiento","—"))
                with st.expander("📄 Ver todos los campos", expanded=False):
                    d1, d2 = st.columns(2)
                    with d1:
                        st.markdown("**Cliente**")
                        st.write(f"Empresa: {fac_sel.get('Nombre_Empresa','—')}")
                        st.write(f"NIT: {emp_info.get('Nit_Empresa','—')}")
                        st.write(f"Tel: {emp_info.get('Telefono_Empresa','—')}")
                        st.write(f"Email: {emp_info.get('Email_Empresa','—')}")
                    with d2:
                        st.markdown("**Factura**")
                        st.write(f"Emisión: {fac_sel.get('Fecha_Emision','—')}")
                        st.write(f"Vencimiento: {fac_sel.get('Fecha_Vencimiento','—')}")
                        st.write(f"Subtotal: {fmt_cop(fac_sel.get('Subtotal_COP',0))}")
                        st.write(f"IVA: {fmt_cop(fac_sel.get('IVA_COP',0))}")
                        st.write(f"Total: {fmt_cop(fac_sel.get('Total_COP',0))}")
                if items_fac:
                    st.markdown("##### 📦 Ítems")
                    st.dataframe(pd.DataFrame([{
                        "Tipo":i.get("Tipo_Servicio",""), "Descripción":i.get("Descripcion",""),
                        "Cant.":i.get("Cantidad","1"), "P. Unitario":fmt_cop(i.get("Precio_Unitario",0)),
                        "Dto. %":i.get("Descuento_Pct","0"), "Subtotal":fmt_cop(i.get("Subtotal",0)),
                    } for i in items_fac]), use_container_width=True, hide_index=True)
                st.markdown("---")
                html_fac = _html_factura(fac_sel, items_fac, emp_info)
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.download_button("⬇️ Descargar Factura HTML", html_fac.encode("utf-8"),
                                       f"Factura_{num_sel}.html", "text/html", use_container_width=True)
                with col_b2:
                    if st.button("🖨️ Abrir Vista de Impresión", use_container_width=True, key="btn_print"):
                        st.session_state["html_preview"] = html_fac
                        st.session_state["preview_num"]  = num_sel
                if st.session_state.get("preview_num","") == num_sel and "html_preview" in st.session_state:
                    st.components.v1.html(st.session_state["html_preview"], height=900, scrolling=True)

    with tab3:
        empresas = get_empresas_activas()
        with st.form("form_factura"):
            c1, c2 = st.columns(2)
            with c1:
                if empresas:
                    opc_emp_f = {f"{e['Nombre_Empresa']} ({e.get('Nit_Empresa','')})": e for e in empresas}
                    sel_emp_f = st.selectbox("Empresa *", list(opc_emp_f.keys()))
                    emp_f     = opc_emp_f[sel_emp_f]
                else:
                    emp_f = {}
                f_emision  = st.date_input("Fecha de emisión", value=date.today())
                f_venc_fac = st.date_input("Fecha de vencimiento", value=date.today())
                est_fac    = st.selectbox("Estado", ["Emitida","Pagada","Vencida","Anulada"])
            with c2:
                subtotal_fac = st.number_input("Subtotal COP *", 0, 1_000_000_000, 0, 1000)
                dto_fac      = st.number_input("Descuento COP", 0, 500_000_000, 0, 1000)
                iva_pct      = st.number_input("IVA %", 0.0, 100.0, 19.0, 0.5)
                base_grav    = max(0, subtotal_fac - dto_fac)
                iva_val      = round(base_grav * iva_pct / 100, 2)
                total_fac    = base_grav + iva_val
                st.info(f"Base: {fmt_cop(base_grav)} · IVA: {fmt_cop(iva_val)} · **Total: {fmt_cop(total_fac)}**")
            obs_fac    = st.text_area("Descripción / Observaciones")
            items_desc = st.text_area("Ítems (separa con ; )", height=60,
                                      placeholder="Repuesto REP-001 x2; Diagnóstico ESC-003")
            guardar_fac = st.form_submit_button("💾 Generar Factura", type="primary", use_container_width=True)
            if guardar_fac:
                if subtotal_fac <= 0:
                    st.error("❌ El subtotal debe ser mayor a 0.")
                else:
                    num_fac  = f"FAC-{ahora_col().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                    fila_fac = [gen_id("FAC-"), num_fac, emp_f.get("Id_Empresa",""), emp_f.get("Nombre_Empresa",""),
                                f_emision.isoformat(), f_venc_fac.isoformat(),
                                str(subtotal_fac), str(dto_fac), str(iva_val), str(round(total_fac,2)),
                                est_fac, obs_fac, st.session_state.usuario or "Sistema"]
                    if gs_append("Facturas", fila_fac):
                        if items_desc.strip():
                            for desc in items_desc.split(";"):
                                desc = desc.strip()
                                if desc:
                                    gs_append("Facturas_Items",
                                              [gen_id("FI-"), num_fac, num_fac, "General", desc, "1","0","0","0"])
                        st.success(f"✅ Factura {num_fac} generada en PostgreSQL · Total: {fmt_cop(total_fac)}")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO: CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def show_configuracion():
    if st.session_state.rol not in ("Admin",):
        st.warning("⛔ Solo los administradores pueden acceder.")
        return
    st.markdown('<div class="page-title">⚙️ Configuración</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Tarifas, operadores y parámetros del sistema</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["🐘 PostgreSQL","💲 Tarifas","👤 Operadores","🔑 Parámetros"])

    # ── TAB 1: Estado PostgreSQL ──────────────────────────────────────────────
    with tab1:
        st.markdown("#### Estado de la conexión PostgreSQL")
        if not PSYCOPG2_AVAILABLE:
            st.error("❌ psycopg2 no instalado. Agrega `psycopg2-binary` a requirements.txt.")
        else:
            try:
                get_pg_conn().cursor().execute("SELECT version()")
                st.success("✅ Conexión activa con PostgreSQL")
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")

        st.markdown("---")
        st.markdown("#### Tablas gestionadas (PostgreSQL)")
        st.info(", ".join(_TABLA.values()))

        st.markdown("---")
        st.markdown("#### Configuración en `.streamlit/secrets.toml`")
        st.code("""[postgres]
host     = "localhost"
port     = 5433
user     = "postgres"
password = "123456"
dbname   = "repuestos"
sslmode  = "disable"
# O bien usa URL directa:
# url = "postgresql://user:pass@host:5432/dbname?sslmode=require"
""", language="toml")

        if st.button("🔄 Reiniciar tablas (crear si no existen)", key="btn_init_db"):
            init_db()
            st.success("✅ Tablas verificadas / creadas en PostgreSQL.")

    # ── TAB 2: Tarifas ────────────────────────────────────────────────────────
    with tab2:
        tarifas = gs_read("Tarifas_Config")
        if tarifas:
            st.dataframe(pd.DataFrame([{
                "Servicio":t.get("Tipo_Servicio",""), "Tarifa":t.get("Nombre_Tarifa",""),
                "Precio":fmt_cop(t.get("Precio_COP",0)), "Unidad":t.get("Unidad",""),
                "Activo":"✅" if t.get("Activo","1") == "1" else "❌",
            } for t in tarifas]), use_container_width=True, hide_index=True)
        st.markdown("---")
        with st.form("form_tarifa"):
            c1, c2 = st.columns(2)
            with c1:
                tipo_svc_t = st.selectbox("Tipo de servicio", ["Escaner","Repuesto","Seguro","Otro"])
                nombre_tar = st.text_input("Nombre de la tarifa *")
                precio_tar = st.number_input("Precio COP *", 0, 100_000_000, 0, 1000)
            with c2:
                unidad_tar = st.selectbox("Unidad", ["Servicio","Hora","Ítem","Vehículo","Póliza"])
                desc_tar   = st.text_area("Descripción", height=60)
            guardar_tar = st.form_submit_button("💾 Guardar Tarifa", type="primary", use_container_width=True)
            if guardar_tar:
                if not nombre_tar.strip() or precio_tar <= 0:
                    st.error("❌ Nombre y precio son obligatorios.")
                elif gs_dup_multi("Tarifas_Config",{"Tipo_Servicio":tipo_svc_t,"Nombre_Tarifa":nombre_tar.strip()}):
                    st.warning(f"⚠️ La tarifa {nombre_tar} para {tipo_svc_t} ya existe.")
                else:
                    if gs_append("Tarifas_Config",
                                 [gen_id("TAR-"), tipo_svc_t, nombre_tar.strip(),
                                  str(precio_tar), unidad_tar, desc_tar, "1"]):
                        st.success(f"✅ Tarifa '{nombre_tar}' guardada en PostgreSQL.")
                        st.rerun()

    # ── TAB 3: Operadores ─────────────────────────────────────────────────────
    with tab3:
        operadores = gs_read("Operadores")
        if operadores:
            st.dataframe(pd.DataFrame([{
                "Nombre":o.get("Nombre",""), "Usuario":o.get("Usuario",""),
                "Rol":o.get("Rol",""), "Activo":"✅" if o.get("Activo","1") == "1" else "❌",
            } for o in operadores]), use_container_width=True, hide_index=True)
        st.markdown("---")
        with st.form("form_operador"):
            c1, c2 = st.columns(2)
            with c1:
                nombre_op  = st.text_input("Nombre completo *")
                usuario_op = st.text_input("Usuario (login) *")
                pw_op      = st.text_input("Contraseña *", type="password")
            with c2:
                rol_op   = st.selectbox("Rol", ["Admin","Operador","Consulta"])
                perms_op = st.multiselect("Permisos",
                    ["inventario","repuestos","escaner","seguros","pagos","facturas","empresas","configuracion"],
                    default=["inventario","repuestos","escaner"])
            guardar_op = st.form_submit_button("💾 Crear Operador", type="primary", use_container_width=True)
            if guardar_op:
                if not nombre_op.strip() or not usuario_op.strip() or not pw_op:
                    st.error("❌ Nombre, usuario y contraseña son obligatorios.")
                elif gs_dup("Operadores","Usuario", usuario_op.strip()):
                    st.warning(f"⚠️ El usuario {usuario_op} ya existe.")
                else:
                    if gs_append("Operadores",
                                 [gen_id("OP-"), nombre_op.strip(), usuario_op.strip(),
                                  hashpw(pw_op), rol_op, ",".join(perms_op), "1", ahora_col().isoformat()]):
                        st.success(f"✅ Operador '{nombre_op}' creado en PostgreSQL.")
                        st.rerun()

    # ── TAB 4: Parámetros ─────────────────────────────────────────────────────
    with tab4:
        cfg = gs_read("Configuracion_Pagos")
        if cfg:
            st.dataframe(pd.DataFrame([{
                "Clave":c.get("Clave",""), "Valor":c.get("Valor",""),
                "Actualizado":c.get("Actualizado_En",""),
            } for c in cfg]), use_container_width=True, hide_index=True)
        st.markdown("---")
        with st.form("form_cfg"):
            c1, c2 = st.columns(2)
            clave_cfg = c1.text_input("Clave *")
            valor_cfg = c2.text_input("Valor *")
            guardar_cfg = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
            if guardar_cfg:
                if not clave_cfg.strip():
                    st.error("❌ La clave es obligatoria.")
                else:
                    # Upsert en configuracion_pagos
                    _pg_upsert("Configuracion_Pagos", "Clave", clave_cfg.strip(),
                               [clave_cfg.strip(), valor_cfg, ahora_col().isoformat()])
                    st.success(f"✅ Parámetro '{clave_cfg}' guardado en PostgreSQL.")
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    init_state()
    init_db()          # Crea tablas si no existen
    if not st.session_state.autenticado:
        show_login()
        return
    show_sidebar()
    router = {
        "dashboard":     show_dashboard,
        "empresas":      show_empresas,
        "inventario":    show_inventario,
        "repuestos":     show_repuestos,
        "escaner":       show_escaner,
        "seguros":       show_seguros,
        "pagos":         show_pagos,
        "facturas":      show_facturas,
        "configuracion": show_configuracion,
    }
    router.get(st.session_state.get("pantalla","dashboard"), show_dashboard)()


if __name__ == "__main__":
    main()
