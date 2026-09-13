# ══════════════════════════════════════════════════════════════════════════════
#  SUITE SALITRE · Espacios de Descanso Personal — Terminal de Transportes
#  MÓDULO: factura_electronica_dian.py
#  Facturación Electrónica Colombia — Integración DIAN (VPFE / SET)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Funcionalidades:
#   1. Generación de XML UBL 2.1 (formato DIAN Colombia) por cada factura
#   2. Generación de la representación gráfica (PDF) de cada factura, para
#      imprimir y para adjuntar en el envío al cliente (requiere reportlab)
#   3. Envío automático de la factura al cliente por correo (PDF + XML
#      adjuntos) y/o WhatsApp (PDF), reutilizando el mecanismo de envío ya
#      configurado en pagos.py (yagmail / WhatsApp Cloud API)
#   4. Reenvío manual de cualquier factura ya emitida, e impresión/descarga
#      de su XML y PDF en cualquier momento, desde el panel del operador
#   5. Panel Streamlit con acceso directo al portal VPFE de la DIAN
#   6. Subida de archivos de la DIAN (.xlsx / .pdf / .zip) y almacenamiento
#      en PostgreSQL + disco local
#   7. (La causación contable NO se hace en este módulo — la hace
#      contabilidad.py desde pagos.py, una sola vez por reserva/pago, para
#      no duplicar el ingreso. Ver contabilidad.on_reserva_creada().)
#   8. Registro de estado DIAN (enviada / aceptada / rechazada) por factura
#   9. Transmisión real por Web Service SOAP de Validación Previa
#      (SendTestSetAsync / SendBillSync / GetStatus / GetNumberingRange),
#      como alternativa a subir el XML manualmente al portal DIAN
#
#  FUENTE DE DATOS: PostgreSQL (única fuente de verdad)
#    Tabla: facturas_electronicas (creada automáticamente en init_db)
#
#  Google Sheets (jjgt_pagos / jjgt_convenios) eliminado completamente.
#
#  ⚠️ Sobre la transmisión SOAP (punto 9): requiere que el XML esté firmado
#  con Firma Digital XAdES-EPES (política DIAN) usando un certificado digital
#  vigente — ver advertencias detalladas en la sección "TRANSMISIÓN SOAP A LA
#  DIAN" más abajo. Sin eso, la DIAN rechazará el documento aunque el envío
#  SOAP en sí funcione. La subida manual al portal (pestañas 🌐 Portal DIAN /
#  📤 Subir archivo DIAN) sigue disponible y no depende de ningún certificado.
#
#  Configuración necesaria en configuracion_pagos (PostgreSQL):
#   dian_nit_emisor         → NIT sin dígito verificación  ej: 902047871
#   dian_digito_verificador → Dígito verificador           ej: 3
#   dian_razon_social       → Razón social emisor          ej: JJGT S.A.S.
#   dian_nombre_comercial   → Nombre comercial             ej: Suite Salitre Vip Vip
#   dian_regimen            → O-13 (Simplificado) | O-48 (Común)
#   dian_resolucion_num     → Número resolución DIAN       ej: 18764065649999
#   dian_resolucion_fecha   → Fecha resolución             ej: 2024-01-15
#   dian_rango_desde        → Inicio del rango autorizado  ej: 1
#   dian_rango_hasta        → Fin del rango autorizado     ej: 5000
#   dian_prefijo_fe         → Prefijo factura electrónica  ej: SESP
#   dian_ambiente           → 1=Producción / 2=Pruebas     ej: 2
#   dian_ciudad_emisor      → Ciudad emisor                ej: Bogotá D.C.
#   dian_dept_emisor        → Departamento emisor          ej: Cundinamarca
#   dian_codigo_postal      → Código postal                ej: 110221
#   dian_email_emisor       → Email para notificaciones    ej: fe@jjgt.com.co
#   dian_wsdl_habilitacion  → WSDL SOAP ambiente pruebas    (ver DIAN_WSDL_HABILITACION_DEFAULT)
#   dian_wsdl_produccion    → WSDL SOAP ambiente producción(ver DIAN_WSDL_PRODUCCION_DEFAULT)
#   dian_software_id        → SoftwareID (Catálogo DIAN)
#   dian_software_pin       → SoftwarePIN (Catálogo DIAN)
#   dian_test_set_id        → TestSetId (habilitación)
#   dian_clave_tecnica      → Clave Técnica del rango de numeración (CUFE real)
#   dian_cert_path          → Ruta al certificado .p12/.pfx en el servidor
#   dian_cert_password      → Contraseña del certificado
#   dian_transmision_automatica → "si"/"no" — transmitir por SOAP cada FE nueva
#
#  El envío al cliente reutiliza la configuración de correo/WhatsApp que ya
#  usa pagos.py (⚙️ Configuración → 📧 Envíos, y secrets.toml → [emails] /
#  [whatsapp]) — no hay configuración adicional que hacer en este módulo.
#
#  Dependencias Python:
#   pip install lxml streamlit pandas openpyxl pytz psycopg2-binary reportlab
#   pip install zeep signxml cryptography   # solo si usarás transmisión SOAP
#
#  Integración en pagos.py:
#   try:
#       import factura_electronica_dian as _fe_mod
#       FE_AVAILABLE = True
#   except ImportError:
#       _fe_mod = None
#       FE_AVAILABLE = False
#
#   Antes de operar (p.ej. al inicio de main()):
#       if FE_AVAILABLE:
#           _fe_mod.set_context(globals())
#
#   En crear_reserva_completa() — al final, junto al comprobante contable:
#       if FE_AVAILABLE:
#           try:
#               _fe_mod.generar_fe_desde_reserva(voucher, calc, cliente, metodo)
#           except Exception as _fe_err:
#               print(f"[pagos] WARN: no se pudo generar la FE DIAN: {_fe_err}")
#
#   En show_operador() — mod_map:
#       "⚡ Factura Electrónica": _fe_mod.render_panel_fe if FE_AVAILABLE else _op_dashboard,
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import os
import re
import sys
import uuid
import zipfile
import base64
import importlib
import threading
from datetime import datetime, date
from typing import Optional

import pytz

# ── Dependencias opcionales ───────────────────────────────────────────────────
try:
    from lxml import etree
    LXML_OK = True
except ImportError:
    LXML_OK = False

try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# ── Transmisión SOAP a la DIAN (Validación Previa) ──────────────────────────
# zeep: cliente SOAP para consumir el Web Service de la DIAN (WcfDianCustomerServices)
# descrito en el Anexo Técnico Cap. 11 (Descripción tecnológica del Web Service)
# y Cap. 12 (Herramienta para el consumo de Web Services - SOAP UI).
try:
    import zeep
    from zeep.wsse.username import UsernameToken
    from zeep.helpers import serialize_object
    from zeep.transports import Transport
    ZEEP_OK = True
    ZEEP_IMPORT_ERROR = ""
except Exception as _zeep_imp_err:
    # Se captura Exception (no solo ImportError) a propósito: en despliegues
    # reales (p.ej. Streamlit Cloud) un paquete "instalado" pero con una
    # subdependencia incompatible puede fallar con otro tipo de error, y
    # queremos ver ese mensaje en el panel en vez de que la app truene.
    ZEEP_OK = False
    ZEEP_IMPORT_ERROR = f"{type(_zeep_imp_err).__name__}: {_zeep_imp_err}"

# signxml: firma XML-DSig con certificado .p12/.pfx — usada como punto de
# partida para la firma digital del XML antes de transmitirlo. IMPORTANTE:
# la DIAN exige específicamente XAdES-EPES (política de firma XAdES, no un
# XML-DSig genérico) — ver advertencia y limitaciones en firmar_xml_xades_epes().
try:
    from signxml import XMLSigner, methods as _signxml_methods
    from cryptography.hazmat.primitives.serialization import pkcs12
    SIGNXML_OK = True
    SIGNXML_IMPORT_ERROR = ""
except Exception as _signxml_imp_err:
    SIGNXML_OK = False
    SIGNXML_IMPORT_ERROR = f"{type(_signxml_imp_err).__name__}: {_signxml_imp_err}"

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────────────
TZ_COL          = pytz.timezone("America/Bogota")
URL_DIAN_LOGIN  = "https://catalogo-vpfe.dian.gov.co/User/Login"
URL_DIAN_PORTAL = "https://catalogo-vpfe.dian.gov.co"

# WSDL del Web Service SOAP "WcfDianCustomerServices" de Validación Previa
# (Anexo Técnico Cap. 11). Son los endpoints públicamente documentados por la
# DIAN; verifica que coincidan con los que aparecen en tu Catálogo de
# Participante (ambiente habilitación / ambiente producción) antes de operar
# — la DIAN puede actualizarlos, y de ahí también sale la URL real a usar.
# Se pueden sobrescribir desde ⚙️ Configuración → 🚀 Transmisión SOAP.
DIAN_WSDL_HABILITACION_DEFAULT = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl"
DIAN_WSDL_PRODUCCION_DEFAULT   = "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl"

# Nombre de la tabla PostgreSQL
PG_TABLA_FE = "facturas_electronicas"

# Columnas lógicas del registro de factura electrónica
_COLS_FE = [
    "Fecha_Emision",
    "Numero_FE",
    "Numero_Reserva",
    "NIT_Receptor",
    "Nombre_Receptor",
    "Subtotal_COP",
    "IVA_COP",
    "Total_COP",
    "Metodo_Pago",
    "Estado_DIAN",       # pendiente / enviada / aceptada / rechazada
    "CUFE",              # Código Único de Factura Electrónica
    "Archivo_DIAN",      # nombre del archivo subido desde el portal DIAN
    "Observaciones",
    "Operador",
    "Creado_En",
    # ── Datos adicionales del receptor e ítem (necesarios para poder
    #    reimprimir y reenviar la factura con exactitud en cualquier momento,
    #    sin depender de que el archivo local siga existiendo en disco) ──────
    "Email_Receptor",
    "Telefono_Receptor",
    "Tipo_Doc_Receptor",
    "Regimen_Receptor",
    "Ciudad_Receptor",
    "Horas",
    "Precio_Hora",
    "Descripcion_Item",
    "Envio_Cliente",     # último resultado de envío: "email:ok · whatsapp:ok", etc.
]

# DDL de la tabla — se ejecuta en _ensure_table() al primer uso
_DDL_FE = """
CREATE TABLE IF NOT EXISTS facturas_electronicas (
    id                SERIAL PRIMARY KEY,
    fecha_emision     TEXT,
    numero_fe         TEXT UNIQUE,
    numero_reserva    TEXT,
    nit_receptor      TEXT,
    nombre_receptor   TEXT,
    subtotal_cop      NUMERIC(18,2) DEFAULT 0,
    iva_cop           NUMERIC(18,2) DEFAULT 0,
    total_cop         NUMERIC(18,2) DEFAULT 0,
    metodo_pago       TEXT,
    estado_dian       TEXT DEFAULT 'pendiente',
    cufe              TEXT,
    archivo_dian      TEXT,
    observaciones     TEXT,
    operador          TEXT,
    creado_en         TEXT,
    email_receptor    TEXT DEFAULT '',
    telefono_receptor TEXT DEFAULT '',
    tipo_doc_receptor TEXT DEFAULT '13',
    regimen_receptor  TEXT DEFAULT 'O-13',
    ciudad_receptor   TEXT DEFAULT '',
    horas             NUMERIC(10,2) DEFAULT 1,
    precio_hora       NUMERIC(18,2) DEFAULT 0,
    descripcion_item  TEXT DEFAULT '',
    envio_cliente     TEXT DEFAULT ''
);
"""

# Namespaces UBL 2.1 (DIAN Colombia)
_NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "":    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
}

_ctx: dict = {}
_ctx_lock  = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXTO — inyectado desde pagos.py
# ══════════════════════════════════════════════════════════════════════════════

def set_context(globals_dict: dict) -> None:
    """
    Llama desde main() (o al inicio de la app) de pagos.py:
        import factura_electronica_dian as _fe_mod
        _fe_mod.set_context(globals())
    """
    with _ctx_lock:
        _ctx.update(globals_dict)


# ══════════════════════════════════════════════════════════════════════════════
# ACCESO A POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════════

def _get_pg_exec():
    """Retorna la función _pg_exec del contexto inyectado."""
    fn = _ctx.get("_pg_exec")
    if fn is None:
        try:
            import pagos as _pagos_mod
            return _pagos_mod._pg_exec
        except Exception:
            pass
    return fn


def _ensure_table() -> bool:
    """Crea la tabla facturas_electronicas si no existe. Retorna True si OK.
    También agrega (ALTER TABLE ... ADD COLUMN IF NOT EXISTS) las columnas
    nuevas de datos del receptor/envío en instalaciones que ya tenían la
    tabla creada con una versión anterior de este módulo."""
    pg_exec = _get_pg_exec()
    if pg_exec is None:
        return False
    try:
        pg_exec(_DDL_FE)
        for col_sql in (
            "email_receptor    TEXT DEFAULT ''",
            "telefono_receptor TEXT DEFAULT ''",
            "tipo_doc_receptor TEXT DEFAULT '13'",
            "regimen_receptor  TEXT DEFAULT 'O-13'",
            "ciudad_receptor   TEXT DEFAULT ''",
            "horas             NUMERIC(10,2) DEFAULT 1",
            "precio_hora       NUMERIC(18,2) DEFAULT 0",
            "descripcion_item  TEXT DEFAULT ''",
            "envio_cliente     TEXT DEFAULT ''",
        ):
            try:
                pg_exec(f"ALTER TABLE {PG_TABLA_FE} ADD COLUMN IF NOT EXISTS {col_sql}")
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"[fe_dian] WARN: no se pudo crear tabla: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS GENERALES
# ══════════════════════════════════════════════════════════════════════════════

def _ahora() -> datetime:
    return datetime.now(TZ_COL)


def _cfg(clave: str, default: str = "") -> str:
    """Lee configuración desde configuracion_pagos (PostgreSQL)."""
    fn = _ctx.get("get_config")
    if fn:
        return fn(clave, default) or default
    return default


def _operador() -> str:
    try:
        import streamlit as st
        return st.session_state.get("operador_info", {}).get("nombre", "sistema")
    except Exception:
        return "sistema"


def _nit_limpio(nit: str) -> str:
    return re.sub(r"[^0-9]", "", nit or "")


def _calcular_digito_verificacion(nit: str) -> str:
    """Algoritmo oficial DIAN para calcular dígito de verificación del NIT."""
    nit = _nit_limpio(nit)
    if not nit:
        return "0"
    factores = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_rev  = nit[::-1]
    total    = sum(int(d) * factores[i] for i, d in enumerate(nit_rev) if i < len(factores))
    resto    = total % 11
    return str(0 if resto in (0, 1) else 11 - resto)


def _cufe_simulado(numero_fe: str, nit: str, total: float, fecha: str) -> str:
    """
    CUFE simplificado para entornos de prueba interna (NO es el algoritmo
    oficial DIAN). Se usa solo como respaldo cuando aún no hay una Clave
    Técnica configurada (dian_clave_tecnica) — sin ella es imposible calcular
    un CUFE válido ante la DIAN, así que no tiene sentido intentarlo.
    """
    import hashlib
    cadena = f"{numero_fe}{nit}{total:.2f}{fecha}"
    return hashlib.sha384(cadena.encode()).hexdigest()


def calcular_cufe_real(
    numero_fe: str, fecha_emision: str, hora_emision: str,
    subtotal: float, iva_valor: float, total: float,
    nit_emisor: str, nit_receptor: str, clave_tecnica: str,
    ambiente: str = "2",
) -> str:
    """
    Calcula el CUFE (Código Único de Factura Electrónica) con el algoritmo
    oficial de la DIAN: SHA-384 sobre la concatenación de los campos de la
    factura + la Clave Técnica asignada al rango de numeración autorizado.

    ⚠️ IMPORTANTE: el orden y formato exacto de concatenación de los campos
    (separadores, decimales, ceros a la izquierda, códigos de impuesto) debe
    coincidir EXACTAMENTE con el especificado en el Anexo Técnico de Factura
    Electrónica de Venta (capítulo "Generación del CUFE"), incluido en tu
    Caja de Herramientas (carpeta "Anexo Técnico"). La implementación de
    abajo sigue el formato documentado públicamente (NumFac+FecFac+HorFac+
    ValFac+CodImp+ValImp (x3)+ValFacTot+NitOFE+NumAdq+ClTec+TipoAmb), pero
    **debes validarla contra tus propios casos de ejemplo en Excel/XML de la
    Caja de Herramientas antes de usarla en producción** — un CUFE mal
    calculado hace que la DIAN rechace la factura.

    Sin `clave_tecnica` configurada (dian_clave_tecnica, obtenida vía
    GetNumberingRange o entregada por la DIAN al autorizar el rango de
    numeración) es imposible calcular un CUFE real; en ese caso se debe
    seguir usando _cufe_simulado() únicamente para pruebas internas.
    """
    import hashlib
    if not clave_tecnica:
        raise ValueError(
            "No hay Clave Técnica configurada (dian_clave_tecnica) — "
            "sin ella no se puede calcular un CUFE real. Consúltala vía "
            "GetNumberingRange en la pestaña 🚀 Transmisión SOAP."
        )
    nit_e = _nit_limpio(nit_emisor)
    nit_r = _nit_limpio(nit_receptor) or "222222222222"  # consumidor final DIAN
    cadena = (
        f"{numero_fe}"
        f"{fecha_emision}{hora_emision}"
        f"{subtotal:.2f}"
        f"01{iva_valor:.2f}"   # CodImp1=01 (IVA), ValImp1
        f"04{0.0:.2f}"         # CodImp2=04 (ICA), ValImp2 (no aplica aquí)
        f"03{0.0:.2f}"         # CodImp3=03 (INC), ValImp3 (no aplica aquí)
        f"{total:.2f}"
        f"{nit_e}"
        f"{nit_r}"
        f"{clave_tecnica}"
        f"{ambiente}"
    )
    return hashlib.sha384(cadena.encode("utf-8")).hexdigest()


def _safe_date(valor: str, default: date | None = None) -> date:
    """Convierte string ISO a date sin romper si el valor es '—' o vacío."""
    try:
        v = (valor or "").strip()
        if len(v) == 10 and v[4] == "-" and v[7] == "-":
            return date.fromisoformat(v)
    except (ValueError, AttributeError):
        pass
    return default or date.today()


def _safe_int(valor: str, default: int = 0) -> int:
    """Convierte string a int sin romper si el valor es '—' o vacío."""
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return default


def _mapear_tipo_doc(tipo: str) -> str:
    """
    Convierte tipo de documento interno a código DIAN.
    Incluye alias "PASAPORTE" porque el selectbox de tipo de documento en
    pagos.py (pantalla "Tus datos para la reserva") usa la etiqueta
    "Pasaporte" en lugar de la sigla "PP".
    """
    mapa = {
        "CC":        "13",
        "CE":        "22",
        "NIT":       "31",
        "PP":        "41",
        "PASAPORTE": "41",
        "TI":        "12",
        "RC":        "11",
    }
    return mapa.get((tipo or "CC").upper(), "13")


def _guardar_xml_local(numero_fe: str, xml_bytes: bytes) -> str:
    """Guarda el XML en la carpeta local facturas_xml/ y retorna la ruta."""
    try:
        folder = "facturas_xml"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{numero_fe}.xml")
        with open(path, "wb") as f:
            f.write(xml_bytes)
        return path
    except Exception:
        return ""


def _guardar_pdf_local(numero_fe: str, pdf_bytes: bytes) -> str:
    """Guarda la representación gráfica (PDF) en facturas_pdf/ y retorna la ruta."""
    if not pdf_bytes:
        return ""
    try:
        folder = "facturas_pdf"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{numero_fe}.pdf")
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return path
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# CAPA DE DATOS — PostgreSQL (reemplaza totalmente Google Sheets)
# ══════════════════════════════════════════════════════════════════════════════

def _pg_append_fe(datos) -> bool:
    """
    Inserta una nueva factura electrónica en PostgreSQL.

    Acepta `datos` como:
      · dict con claves _COLS_FE (recomendado — usado por generar_fe_desde_reserva)
      · list posicional de 15 elementos (compatibilidad con versiones
        anteriores del módulo / _gs_append_fe), alineada con las primeras
        15 columnas de _COLS_FE. Los campos nuevos del receptor quedan
        vacíos/con valores por defecto en ese caso.

    Reemplaza: _gs_append_fe / ws.append_row
    """
    pg_exec = _get_pg_exec()
    if pg_exec is None:
        print("[fe_dian] WARN: _pg_exec no disponible — FE no guardada")
        return False

    if isinstance(datos, dict):
        d = datos
    else:
        fila_str = [str(v) if v is not None else "" for v in (datos or [])]
        fila_str = (fila_str + [""] * 15)[:15]
        d = dict(zip(_COLS_FE[:15], fila_str))

    def _f(v):
        try:    return float(v) if v not in (None, "") else 0.0
        except: return 0.0

    def _s(clave, default=""):
        v = d.get(clave, default)
        return str(v) if v is not None else default

    sql = f"""
        INSERT INTO {PG_TABLA_FE}
            (fecha_emision, numero_fe, numero_reserva, nit_receptor,
             nombre_receptor, subtotal_cop, iva_cop, total_cop,
             metodo_pago, estado_dian, cufe, archivo_dian,
             observaciones, operador, creado_en,
             email_receptor, telefono_receptor, tipo_doc_receptor,
             regimen_receptor, ciudad_receptor, horas, precio_hora,
             descripcion_item, envio_cliente)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (numero_fe) DO NOTHING
    """
    params = [
        _s("Fecha_Emision"),
        _s("Numero_FE"),
        _s("Numero_Reserva"),
        _s("NIT_Receptor"),
        _s("Nombre_Receptor"),
        _f(d.get("Subtotal_COP")),
        _f(d.get("IVA_COP")),
        _f(d.get("Total_COP")),
        _s("Metodo_Pago"),
        _s("Estado_DIAN") or "pendiente",
        _s("CUFE"),
        _s("Archivo_DIAN"),
        _s("Observaciones"),
        _s("Operador"),
        _s("Creado_En"),
        _s("Email_Receptor"),
        _s("Telefono_Receptor"),
        _s("Tipo_Doc_Receptor") or "13",
        _s("Regimen_Receptor") or "O-13",
        _s("Ciudad_Receptor"),
        _f(d.get("Horas", 1)) or 1,
        _f(d.get("Precio_Hora")),
        _s("Descripcion_Item"),
        _s("Envio_Cliente"),
    ]
    try:
        _ensure_table()
        pg_exec(sql, params)
        return True
    except Exception as e:
        print(f"[fe_dian] ERROR al insertar FE: {e}")
        return False


def _pg_read_fe(
    fecha_ini: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> list[dict]:
    """
    Lee facturas electrónicas desde PostgreSQL.
    Retorna lista de dicts con claves = _COLS_FE (formato TitleCase).
    Reemplaza: _gs_read_fe / ws.get_all_values
    """
    pg_exec = _get_pg_exec()
    if pg_exec is None:
        return []

    where_parts: list[str] = []
    params: list = []
    if fecha_ini:
        where_parts.append("fecha_emision >= %s")
        params.append(fecha_ini)
    if fecha_fin:
        where_parts.append("fecha_emision <= %s")
        params.append(fecha_fin)

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    sql = f"""
        SELECT fecha_emision, numero_fe, numero_reserva, nit_receptor,
               nombre_receptor, subtotal_cop, iva_cop, total_cop,
               metodo_pago, estado_dian, cufe, archivo_dian,
               observaciones, operador, creado_en,
               email_receptor, telefono_receptor, tipo_doc_receptor,
               regimen_receptor, ciudad_receptor, horas, precio_hora,
               descripcion_item, envio_cliente
        FROM {PG_TABLA_FE}
        {where_sql}
        ORDER BY id ASC
    """
    try:
        _ensure_table()
        rows = pg_exec(sql, params or None, fetch="all") or []
    except Exception as e:
        print(f"[fe_dian] ERROR al leer FE: {e}")
        return []

    # Normalizar: claves PG (snake_case) → _COLS_FE (TitleCase)
    _col_map = {
        "fecha_emision":      "Fecha_Emision",
        "numero_fe":          "Numero_FE",
        "numero_reserva":     "Numero_Reserva",
        "nit_receptor":       "NIT_Receptor",
        "nombre_receptor":    "Nombre_Receptor",
        "subtotal_cop":       "Subtotal_COP",
        "iva_cop":            "IVA_COP",
        "total_cop":          "Total_COP",
        "metodo_pago":        "Metodo_Pago",
        "estado_dian":        "Estado_DIAN",
        "cufe":               "CUFE",
        "archivo_dian":       "Archivo_DIAN",
        "observaciones":      "Observaciones",
        "operador":           "Operador",
        "creado_en":          "Creado_En",
        "email_receptor":     "Email_Receptor",
        "telefono_receptor":  "Telefono_Receptor",
        "tipo_doc_receptor":  "Tipo_Doc_Receptor",
        "regimen_receptor":   "Regimen_Receptor",
        "ciudad_receptor":    "Ciudad_Receptor",
        "horas":              "Horas",
        "precio_hora":        "Precio_Hora",
        "descripcion_item":   "Descripcion_Item",
        "envio_cliente":      "Envio_Cliente",
    }
    result = []
    for row in rows:
        rec = {}
        for pg_key, sh_key in _col_map.items():
            val = row.get(pg_key, "")
            rec[sh_key] = "" if val is None else str(val)
        result.append(rec)
    return result


def _pg_upsert_fe(numero_fe: str, campo: str, valor: str) -> bool:
    """
    Actualiza un campo específico de una factura electrónica en PostgreSQL.
    Reemplaza: _gs_upsert_fe / ws.update_cell
    campo debe ser el nombre lógico (_COLS_FE) o snake_case PG.
    """
    pg_exec = _get_pg_exec()
    if pg_exec is None:
        return False

    # Normalizar campo a snake_case
    campo_pg = campo.lower().replace(" ", "_")
    # Mapeo de nombres TitleCase a snake_case si llegan del código heredado
    _alias = {
        "fecha_emision":   "fecha_emision",
        "numero_fe":       "numero_fe",
        "numero_reserva":  "numero_reserva",
        "nit_receptor":    "nit_receptor",
        "nombre_receptor": "nombre_receptor",
        "subtotal_cop":    "subtotal_cop",
        "iva_cop":         "iva_cop",
        "total_cop":       "total_cop",
        "metodo_pago":     "metodo_pago",
        "estado_dian":     "estado_dian",
        "cufe":            "cufe",
        "archivo_dian":    "archivo_dian",
        "observaciones":   "observaciones",
        "operador":        "operador",
        "creado_en":       "creado_en",
    }
    campo_pg = _alias.get(campo_pg, campo_pg)

    # Campos numéricos
    if campo_pg in ("subtotal_cop", "iva_cop", "total_cop", "horas", "precio_hora"):
        try:
            val_pg = float(valor)
        except (ValueError, TypeError):
            val_pg = 0.0
    else:
        val_pg = valor

    sql = f'UPDATE {PG_TABLA_FE} SET "{campo_pg}" = %s WHERE numero_fe = %s'
    try:
        pg_exec(sql, [val_pg, numero_fe])
        return True
    except Exception as e:
        print(f"[fe_dian] ERROR al actualizar FE {numero_fe}.{campo_pg}: {e}")
        return False


def _numero_fe_siguiente() -> str:
    """
    Genera el número consecutivo de la factura electrónica usando COUNT en PG.
    Reemplaza: len(rows) desde Google Sheets.
    """
    prefijo = _cfg("dian_prefijo_fe", "SESP")
    n = 1
    pg_exec = _get_pg_exec()
    if pg_exec:
        try:
            _ensure_table()
            row = pg_exec(
                f"SELECT COUNT(*) AS cnt FROM {PG_TABLA_FE}",
                fetch="one"
            )
            if row:
                n = int(row.get("cnt", 0)) + 1
        except Exception:
            pass
    return f"{prefijo}{n:04d}"


# ══════════════════════════════════════════════════════════════════════════════
# STUBS DE COMPATIBILIDAD (para código heredado que pueda referenciar la API GS)
# ══════════════════════════════════════════════════════════════════════════════

def _gs_append_fe(fila: list) -> None:
    """Stub de compatibilidad — redirige a _pg_append_fe."""
    _pg_append_fe(fila)


def _gs_read_fe() -> list:
    """Stub de compatibilidad — redirige a _pg_read_fe."""
    return _pg_read_fe()


def _gs_upsert_fe(numero_fe: str, campo: str, valor: str) -> None:
    """Stub de compatibilidad — redirige a _pg_upsert_fe."""
    _pg_upsert_fe(numero_fe, campo, valor)


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR XML UBL 2.1 — DIAN Colombia
# ══════════════════════════════════════════════════════════════════════════════

def generar_xml_factura(
    numero_fe: str,
    fecha_emision: str,          # "2025-05-04"
    hora_emision: str,           # "14:32:00"
    nit_receptor: str,
    nombre_receptor: str,
    email_receptor: str,
    tipo_doc_receptor: str,      # "13"=CC, "31"=NIT, "22"=CE
    regimen_receptor: str,       # "O-13" simplificado | "O-48" responsable IVA
    ciudad_receptor: str,
    descripcion_item: str,
    cantidad: float,
    precio_unitario: float,
    subtotal: float,
    iva_pct: float,
    iva_valor: float,
    total: float,
    metodo_pago: str,
    num_reserva: str,
    cufe: str,
) -> bytes:
    """
    Genera el XML de la factura electrónica en formato UBL 2.1 para la DIAN.
    Retorna bytes del XML codificado en UTF-8.
    Sin cambios respecto a la versión GS — la generación XML es independiente del storage.
    """
    if not LXML_OK:
        return _generar_xml_fallback(
            numero_fe, fecha_emision, hora_emision,
            nit_receptor, nombre_receptor, email_receptor,
            tipo_doc_receptor, regimen_receptor, ciudad_receptor,
            descripcion_item, cantidad, precio_unitario,
            subtotal, iva_pct, iva_valor, total,
            metodo_pago, num_reserva, cufe
        )

    # Datos del emisor desde configuración PostgreSQL (get_config)
    nit_emisor       = _nit_limpio(_cfg("dian_nit_emisor", _nit_limpio("902.098.424")))
    dv_emisor        = _cfg("dian_digito_verificador", _calcular_digito_verificacion(nit_emisor))
    razon_emisor     = _cfg("dian_razon_social",     "SUITE SALITRE VIP SAS")
    nombre_com       = _cfg("dian_nombre_comercial", "SUITE SALITRE VIP SAS")
    regimen_emisor   = _cfg("dian_regimen",          "O-13")
    resolucion_num   = _cfg("dian_resolucion_num",   "18764115171773")
    resolucion_fecha = _cfg("dian_resolucion_fecha", fecha_emision)
    rango_desde      = _cfg("dian_rango_desde",      "1")
    rango_hasta      = _cfg("dian_rango_hasta",      "300")
    prefijo_fe       = _cfg("dian_prefijo_fe",       "FACT")
    ambiente         = _cfg("dian_ambiente",         "4")   # 2=pruebas
    ciudad_emisor    = _cfg("dian_ciudad_emisor",    "Bogotá D.C.")
    dept_emisor      = _cfg("dian_dept_emisor",      "Bogotá D.C.")
    cod_postal       = _cfg("dian_codigo_postal",    "110221")
    email_emisor     = _cfg("dian_email_emisor",     "suitesalitrevip@gmail.com")
    direccion        = _cfg("negocio_direccion",     "Terminal de Transportes Módulo 3 Local 230")
    telefono         = _cfg("negocio_telefono",      "3219714969")

    # Número correlativo (solo dígitos del consecutivo)
    num_consec = re.sub(r"[^0-9]", "", numero_fe.replace(prefijo_fe, "")) or "1"

    NSMAP = {
        None:  "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    Invoice = etree.Element("Invoice", nsmap=NSMAP)

    def cbc(tag: str, text: str, **attrs) -> etree._Element:
        el = etree.SubElement(Invoice, f"{{{NSMAP['cbc']}}}{tag}", **attrs)
        el.text = text
        return el

    def sub_cbc(parent, tag: str, text: str, **attrs) -> etree._Element:
        el = etree.SubElement(parent, f"{{{NSMAP['cbc']}}}{tag}", **attrs)
        el.text = text
        return el

    def sub_cac(parent, tag: str) -> etree._Element:
        return etree.SubElement(parent, f"{{{NSMAP['cac']}}}{tag}")

    # ── Encabezado ────────────────────────────────────────────────────────────
    cbc("UBLVersionID",       "UBL 2.1")
    cbc("CustomizationID",    "10")
    cbc("ProfileID",          "DIAN 2.1")
    cbc("ProfileExecutionID", ambiente)
    cbc("ID",                 numero_fe)
    cbc("UUID", cufe, schemeID=ambiente, schemeName="CUFE-SHA384")
    cbc("IssueDate",          fecha_emision)
    cbc("IssueTime",          f"{hora_emision}-05:00")
    cbc("DueDate",            fecha_emision)
    cbc("InvoiceTypeCode",    "01")
    cbc("Note",               f"Reserva {num_reserva} · Suite Salitre Vip")
    cbc("DocumentCurrencyCode","COP")
    cbc("LineCountNumeric",   "1")

    # ── Resolución DIAN ───────────────────────────────────────────────────────
    ord_ref = sub_cac(Invoice, "OrderReference")
    sub_cbc(ord_ref, "ID", f"Res.{resolucion_num}")

    billing = sub_cac(Invoice, "BillingReference")
    inv_doc = sub_cac(billing, "InvoiceDocumentReference")
    sub_cbc(inv_doc, "ID",        numero_fe)
    sub_cbc(inv_doc, "UUID",      cufe)
    sub_cbc(inv_doc, "IssueDate", fecha_emision)

    # ── Información de la resolución (extensión DIAN) ─────────────────────────
    sts_ns   = NSMAP["sts"]
    dian_ext = etree.SubElement(Invoice, f"{{{NSMAP['ext']}}}UBLExtensions")
    ext_item = etree.SubElement(dian_ext, f"{{{NSMAP['ext']}}}UBLExtension")
    ext_cont = etree.SubElement(ext_item, f"{{{NSMAP['ext']}}}ExtensionContent")
    dian_ext2= etree.SubElement(ext_cont, f"{{{sts_ns}}}DianExtensions")
    inv_auth = etree.SubElement(dian_ext2, f"{{{sts_ns}}}InvoiceControl")
    etree.SubElement(inv_auth, f"{{{sts_ns}}}InvoiceAuthorization").text = resolucion_num
    auth_per = etree.SubElement(inv_auth, f"{{{sts_ns}}}AuthorizationPeriod")
    etree.SubElement(auth_per, f"{{{NSMAP['cbc']}}}StartDate").text = resolucion_fecha
    etree.SubElement(auth_per, f"{{{NSMAP['cbc']}}}EndDate").text   = "2030-12-31"
    auth_range = etree.SubElement(inv_auth, f"{{{sts_ns}}}AuthorizedInvoices")
    etree.SubElement(auth_range, f"{{{sts_ns}}}Prefix").text = prefijo_fe
    etree.SubElement(auth_range, f"{{{sts_ns}}}From").text   = rango_desde
    etree.SubElement(auth_range, f"{{{sts_ns}}}To").text     = rango_hasta

    # ── Emisor (AccountingSupplierParty) ──────────────────────────────────────
    supp       = sub_cac(Invoice, "AccountingSupplierParty")
    sub_cbc(supp, "AdditionalAccountID", "1")
    supp_party = sub_cac(supp, "Party")
    supp_name  = sub_cac(supp_party, "PartyName")
    sub_cbc(supp_name, "Name", nombre_com)
    supp_phys  = sub_cac(supp_party, "PhysicalLocation")
    supp_addr  = sub_cac(supp_phys, "Address")
    sub_cbc(supp_addr, "ID",                   "11001")
    sub_cbc(supp_addr, "CityName",             ciudad_emisor)
    sub_cbc(supp_addr, "PostalZone",           cod_postal)
    sub_cbc(supp_addr, "CountrySubentity",     dept_emisor)
    sub_cbc(supp_addr, "CountrySubentityCode", "11")
    supp_cty  = sub_cac(supp_addr, "Country")
    sub_cbc(supp_cty, "IdentificationCode", "CO")
    sub_cbc(supp_cty, "Name", "Colombia", languageID="es")
    supp_line = sub_cac(supp_addr, "AddressLine")
    sub_cbc(supp_line, "Line", direccion)
    supp_tax  = sub_cac(supp_party, "PartyTaxScheme")
    sub_cbc(supp_tax, "RegistrationName", razon_emisor)
    sub_cbc(supp_tax, "CompanyID", nit_emisor,
            schemeAgencyID="195",
            schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
            schemeID=dv_emisor, schemeName="31")
    tax_lvl = sub_cac(supp_tax, "TaxLevelCode")
    tax_lvl.text = regimen_emisor
    supp_scheme = sub_cac(supp_tax, "TaxScheme")
    sub_cbc(supp_scheme, "ID",   "01")
    sub_cbc(supp_scheme, "Name", "IVA")
    supp_legal = sub_cac(supp_party, "PartyLegalEntity")
    sub_cbc(supp_legal, "RegistrationName", razon_emisor)
    sub_cbc(supp_legal, "CompanyID", nit_emisor,
            schemeAgencyID="195", schemeName="31", schemeID=dv_emisor)
    supp_contact = sub_cac(supp_party, "Contact")
    sub_cbc(supp_contact, "Telephone",      telefono)
    sub_cbc(supp_contact, "ElectronicMail", email_emisor)

    # ── Receptor (AccountingCustomerParty) ────────────────────────────────────
    cust       = sub_cac(Invoice, "AccountingCustomerParty")
    sub_cbc(cust, "AdditionalAccountID",
            "2" if tipo_doc_receptor == "31" else "1")
    cust_party = sub_cac(cust, "Party")
    cust_name  = sub_cac(cust_party, "PartyName")
    sub_cbc(cust_name, "Name", nombre_receptor)
    cust_phys  = sub_cac(cust_party, "PhysicalLocation")
    cust_addr  = sub_cac(cust_phys, "Address")
    sub_cbc(cust_addr, "CityName", ciudad_receptor or "Bogotá D.C.")
    cust_cty   = sub_cac(cust_addr, "Country")
    sub_cbc(cust_cty, "IdentificationCode", "CO")
    sub_cbc(cust_cty, "Name", "Colombia", languageID="es")
    cust_tax   = sub_cac(cust_party, "PartyTaxScheme")
    sub_cbc(cust_tax, "RegistrationName", nombre_receptor)
    sub_cbc(cust_tax, "CompanyID", _nit_limpio(nit_receptor),
            schemeAgencyID="195", schemeAgencyName="CO, DIAN",
            schemeID="0", schemeName=tipo_doc_receptor)
    cust_tax_lvl = sub_cac(cust_tax, "TaxLevelCode")
    cust_tax_lvl.text = regimen_receptor
    cust_scheme = sub_cac(cust_tax, "TaxScheme")
    sub_cbc(cust_scheme, "ID",   "ZZ")
    sub_cbc(cust_scheme, "Name", "No aplica")
    cust_legal  = sub_cac(cust_party, "PartyLegalEntity")
    sub_cbc(cust_legal, "RegistrationName", nombre_receptor)
    sub_cbc(cust_legal, "CompanyID", _nit_limpio(nit_receptor),
            schemeName=tipo_doc_receptor)
    cust_contact = sub_cac(cust_party, "Contact")
    sub_cbc(cust_contact, "ElectronicMail", email_receptor or "")

    # ── Método de pago ────────────────────────────────────────────────────────
    MEDIOS = {
        "Efectivo":     ("10", "1"),
        "Nequi":        ("48", "1"),
        "Daviplata":    ("48", "1"),
        "Transferencia":("42", "1"),
        "PSE":          ("42", "1"),
        "Tarjeta":      ("48", "1"),
        "MercadoPago":  ("48", "1"),
        "Convenio":     ("1",  "2"),
    }
    medio_code, _ = MEDIOS.get(metodo_pago, ("10", "1"))
    pay_means = sub_cac(Invoice, "PaymentMeans")
    sub_cbc(pay_means, "ID",               medio_code)
    sub_cbc(pay_means, "PaymentMeansCode", medio_code)
    sub_cbc(pay_means, "PaymentDueDate",   fecha_emision)

    # ── Totales de impuestos ──────────────────────────────────────────────────
    if iva_valor > 0:
        tax_total = sub_cac(Invoice, "TaxTotal")
        sub_cbc(tax_total, "TaxAmount", f"{iva_valor:.2f}", currencyID="COP")
        tax_sub = sub_cac(tax_total, "TaxSubtotal")
        sub_cbc(tax_sub, "TaxableAmount", f"{subtotal:.2f}", currencyID="COP")
        sub_cbc(tax_sub, "TaxAmount",     f"{iva_valor:.2f}", currencyID="COP")
        tax_cat = sub_cac(tax_sub, "TaxCategory")
        sub_cbc(tax_cat, "Percent", f"{iva_pct:.2f}")
        tax_cat_scheme = sub_cac(tax_cat, "TaxScheme")
        sub_cbc(tax_cat_scheme, "ID",   "01")
        sub_cbc(tax_cat_scheme, "Name", "IVA")

    # ── Totales legales ───────────────────────────────────────────────────────
    legal = sub_cac(Invoice, "LegalMonetaryTotal")
    sub_cbc(legal, "LineExtensionAmount", f"{subtotal:.2f}", currencyID="COP")
    sub_cbc(legal, "TaxExclusiveAmount",  f"{subtotal:.2f}", currencyID="COP")
    sub_cbc(legal, "TaxInclusiveAmount",  f"{total:.2f}",    currencyID="COP")
    sub_cbc(legal, "AllowanceTotalAmount","0.00",            currencyID="COP")
    sub_cbc(legal, "ChargeTotalAmount",   "0.00",            currencyID="COP")
    sub_cbc(legal, "PayableAmount",       f"{total:.2f}",    currencyID="COP")

    # ── Línea de factura ──────────────────────────────────────────────────────
    line = sub_cac(Invoice, "InvoiceLine")
    sub_cbc(line, "ID",                  "1")
    sub_cbc(line, "InvoicedQuantity",    f"{cantidad:.2f}", unitCode="HUR")
    sub_cbc(line, "LineExtensionAmount", f"{subtotal:.2f}", currencyID="COP")
    line_note      = sub_cac(line, "Note")
    line_note.text = num_reserva
    line_item      = sub_cac(line, "Item")
    sub_cbc(line_item, "Description", descripcion_item)
    line_price = sub_cac(line, "Price")
    sub_cbc(line_price, "PriceAmount",  f"{precio_unitario:.2f}", currencyID="COP")
    sub_cbc(line_price, "BaseQuantity", f"{cantidad:.2f}",        unitCode="HUR")

    if iva_valor > 0:
        line_tax     = sub_cac(line, "TaxTotal")
        sub_cbc(line_tax, "TaxAmount", f"{iva_valor:.2f}", currencyID="COP")
        line_tax_sub = sub_cac(line_tax, "TaxSubtotal")
        sub_cbc(line_tax_sub, "TaxableAmount", f"{subtotal:.2f}", currencyID="COP")
        sub_cbc(line_tax_sub, "TaxAmount",     f"{iva_valor:.2f}", currencyID="COP")
        line_cat     = sub_cac(line_tax_sub, "TaxCategory")
        sub_cbc(line_cat, "Percent", f"{iva_pct:.2f}")
        line_cat_sch = sub_cac(line_cat, "TaxScheme")
        sub_cbc(line_cat_sch, "ID",   "01")
        sub_cbc(line_cat_sch, "Name", "IVA")

    return etree.tostring(Invoice, xml_declaration=True,
                          encoding="UTF-8", pretty_print=True)


def _generar_xml_fallback(
    numero_fe, fecha_emision, hora_emision,
    nit_receptor, nombre_receptor, email_receptor,
    tipo_doc_receptor, regimen_receptor, ciudad_receptor,
    descripcion_item, cantidad, precio_unitario,
    subtotal, iva_pct, iva_valor, total,
    metodo_pago, num_reserva, cufe
) -> bytes:
    """XML mínimo sin lxml — para entornos sin la librería instalada."""
    nit_emisor   = _nit_limpio(_cfg("dian_nit_emisor", "9020478713"))
    razon_emisor = _cfg("dian_razon_social", "JJGT S.A.S.")
    resolucion   = _cfg("dian_resolucion_num", "0")
    prefijo      = _cfg("dian_prefijo_fe", "SESP")
    ambiente     = _cfg("dian_ambiente", "2")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>10</cbc:CustomizationID>
  <cbc:ProfileID>DIAN 2.1</cbc:ProfileID>
  <cbc:ProfileExecutionID>{ambiente}</cbc:ProfileExecutionID>
  <cbc:ID>{numero_fe}</cbc:ID>
  <cbc:UUID schemeID="{ambiente}" schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
  <cbc:IssueDate>{fecha_emision}</cbc:IssueDate>
  <cbc:IssueTime>{hora_emision}-05:00</cbc:IssueTime>
  <cbc:DueDate>{fecha_emision}</cbc:DueDate>
  <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
  <cbc:Note>Reserva {num_reserva} · Suite Salitre Vip · Resolución {resolucion}</cbc:Note>
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
  <cbc:LineCountNumeric>1</cbc:LineCountNumeric>
  <cac:AccountingSupplierParty>
    <cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:RegistrationName>{razon_emisor}</cbc:RegistrationName>
        <cbc:CompanyID schemeID="0" schemeName="31">{nit_emisor}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:RegistrationName>{nombre_receptor}</cbc:RegistrationName>
        <cbc:CompanyID schemeName="{tipo_doc_receptor}">{_nit_limpio(nit_receptor)}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>ZZ</cbc:ID><cbc:Name>No aplica</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="COP">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount  currencyID="COP">{subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount  currencyID="COP">{total:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount       currencyID="COP">{total:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="HUR">{cantidad:.2f}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="COP">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>{descripcion_item}</cbc:Description></cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="COP">{precio_unitario:.2f}</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
</Invoice>"""
    return xml.encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# REPRESENTACIÓN GRÁFICA (PDF) DE LA FACTURA ELECTRÓNICA
# ══════════════════════════════════════════════════════════════════════════════
#
#  La DIAN exige que, además del XML (documento con validez legal ante la
#  DIAN), el emisor entregue al receptor una "representación gráfica" legible
#  por humanos de la factura electrónica. Este PDF es lo que normalmente se
#  imprime y se envía por correo/WhatsApp al cliente — el XML se adjunta
#  también por correo para quienes lo necesiten (p. ej. clientes empresa que
#  hacen su propia contabilidad), pero no se envía por WhatsApp.
#

def generar_pdf_factura(
    numero_fe: str,
    fecha_emision: str,
    hora_emision: str,
    nit_receptor: str,
    nombre_receptor: str,
    email_receptor: str,
    tipo_doc_receptor: str,
    ciudad_receptor: str,
    descripcion_item: str,
    cantidad: float,
    precio_unitario: float,
    subtotal: float,
    iva_pct: float,
    iva_valor: float,
    total: float,
    metodo_pago: str,
    num_reserva: str,
    cufe: str,
) -> Optional[bytes]:
    """
    Genera la representación gráfica (PDF, tamaño carta/A4) de la factura
    electrónica de venta, con los datos del emisor (config DIAN en
    PostgreSQL), el receptor, el detalle del servicio y el CUFE.
    Retorna None si reportlab no está instalado (dependencia opcional).
    """
    if not REPORTLAB_OK:
        return None

    nit_emisor       = _nit_limpio(_cfg("dian_nit_emisor", "902098424"))
    dv_emisor        = _cfg("dian_digito_verificador", _calcular_digito_verificacion(nit_emisor))
    razon_emisor     = _cfg("dian_razon_social",     "SUITE SALITRE VIP SAS")
    nombre_com       = _cfg("dian_nombre_comercial", razon_emisor)
    resolucion_num   = _cfg("dian_resolucion_num",   "—")
    prefijo_fe       = _cfg("dian_prefijo_fe",       "FACT")
    rango_desde      = _cfg("dian_rango_desde",      "1")
    rango_hasta      = _cfg("dian_rango_hasta",      "5000")
    ambiente         = _cfg("dian_ambiente",         "2")
    ciudad_emisor    = _cfg("dian_ciudad_emisor",    "Bogotá D.C.")
    email_emisor     = _cfg("dian_email_emisor",     "")
    direccion        = _cfg("negocio_direccion",     "")
    telefono         = _cfg("negocio_telefono",      "")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    st_title = ParagraphStyle("FETitle", parent=styles["Title"],
                               fontSize=15, leading=18, alignment=TA_CENTER,
                               textColor=colors.HexColor("#0a3d62"))
    st_h2    = ParagraphStyle("FEH2", parent=styles["Heading2"],
                               fontSize=11, leading=14,
                               textColor=colors.HexColor("#0a3d62"))
    st_norm  = ParagraphStyle("FENorm", parent=styles["Normal"],
                              fontSize=9, leading=12.5)
    st_small = ParagraphStyle("FESmall", parent=styles["Normal"],
                              fontSize=7.5, leading=10, textColor=colors.grey)
    st_right = ParagraphStyle("FERight", parent=st_norm, alignment=TA_RIGHT)
    st_center= ParagraphStyle("FECenter", parent=st_norm, alignment=TA_CENTER)

    def hr():
        return HRFlowable(width="100%", thickness=0.6,
                           color=colors.HexColor("#0a3d62"),
                           spaceBefore=4, spaceAfter=6)

    elems = []

    if ambiente == "2":
        elems.append(Paragraph(
            "DOCUMENTO EN AMBIENTE DE PRUEBAS DIAN — SIN VALIDEZ FISCAL",
            ParagraphStyle("FEAmb", parent=st_center, textColor=colors.red,
                           fontSize=9)
        ))
        elems.append(Spacer(1, 4))

    elems.append(Paragraph(nombre_com or razon_emisor, st_title))
    datos_emisor = (
        f"{razon_emisor} · NIT {nit_emisor}-{dv_emisor}<br/>"
        f"{direccion or ''}{' · ' if direccion else ''}"
        f"{ciudad_emisor}"
        f"{(' · Tel: ' + telefono) if telefono else ''}"
        f"{(' · ' + email_emisor) if email_emisor else ''}"
    )
    elems.append(Paragraph(datos_emisor, st_center))
    elems.append(Spacer(1, 8))
    elems.append(hr())

    elems.append(Paragraph(f"FACTURA ELECTRÓNICA DE VENTA N.° {numero_fe}", st_h2))
    elems.append(Paragraph(
        f"Resolución DIAN N.° {resolucion_num} · Rango autorizado "
        f"{prefijo_fe}{rango_desde} — {prefijo_fe}{rango_hasta}<br/>"
        f"Fecha de emisión: {fecha_emision} {hora_emision} &nbsp;·&nbsp; "
        f"Reserva asociada: {num_reserva}",
        st_small
    ))
    elems.append(Spacer(1, 8))

    # ── Datos del receptor ────────────────────────────────────────────────
    tabla_receptor = Table([
        [Paragraph("<b>Facturar a</b>", st_norm), ""],
        [Paragraph("Nombre / Razón social", st_small), Paragraph(nombre_receptor or "Consumidor Final", st_norm)],
        [Paragraph("Documento", st_small), Paragraph(f"{_nit_limpio(nit_receptor)} (tipo {tipo_doc_receptor})", st_norm)],
        [Paragraph("Ciudad", st_small), Paragraph(ciudad_receptor or "—", st_norm)],
        [Paragraph("Email", st_small), Paragraph(email_receptor or "—", st_norm)],
    ], colWidths=[45 * mm, None])
    tabla_receptor.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#eef6fb")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (1, 0), 0.5, colors.HexColor("#0a3d62")),
    ]))
    elems.append(tabla_receptor)
    elems.append(Spacer(1, 10))

    # ── Detalle del servicio ──────────────────────────────────────────────
    tabla_items = Table([
        ["Descripción", "Cant. (h)", "Precio unit.", "Subtotal"],
        [descripcion_item, f"{cantidad:.2f}",
         f"${precio_unitario:,.0f}", f"${subtotal:,.0f}"],
    ], colWidths=[None, 22 * mm, 30 * mm, 30 * mm])
    tabla_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a3d62")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (1, 0), (-1, -1), "RIGHT"),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(tabla_items)
    elems.append(Spacer(1, 8))

    # ── Totales ────────────────────────────────────────────────────────────
    filas_tot = [["Subtotal", f"${subtotal:,.0f}"]]
    if iva_valor > 0:
        filas_tot.append([f"IVA ({iva_pct:.0f}%)", f"${iva_valor:,.0f}"])
    filas_tot.append(["TOTAL COP", f"${total:,.0f}"])
    tabla_tot = Table(filas_tot, colWidths=[40 * mm, 30 * mm], hAlign="RIGHT")
    estilos_tot = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#0a3d62")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#0a3d62")),
    ]
    tabla_tot.setStyle(TableStyle(estilos_tot))
    elems.append(tabla_tot)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(f"<b>Método de pago:</b> {metodo_pago}", st_norm))
    elems.append(Spacer(1, 10))
    elems.append(hr())

    # ── CUFE y validación ────────────────────────────────────────────────
    elems.append(Paragraph("<b>CUFE</b> (Código Único de Factura Electrónica)", st_small))
    elems.append(Paragraph(cufe, ParagraphStyle(
        "FECufe", parent=st_small, fontName="Courier", fontSize=7.5,
        textColor=colors.HexColor("#0a3d62")
    )))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(
        "Esta es la representación gráfica de una Factura Electrónica de "
        "Venta. Puede validar su autenticidad ante la DIAN ingresando el "
        f"CUFE en {URL_DIAN_PORTAL}. El archivo XML (UBL 2.1) es el "
        "documento con validez legal; este PDF es solo su representación "
        "legible.",
        st_small
    ))

    doc.build(elems)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# ENVÍO DE LA FACTURA ELECTRÓNICA AL CLIENTE (correo / WhatsApp)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Reutiliza el mecanismo de envío ya existente en pagos.py (inyectado vía
#  set_context): smtp_disponible() / enviar_factura_email() para correo, y
#  whatsapp_api_disponible() / enviar_whatsapp_documento() / link_whatsapp_manual()
#  para WhatsApp. Este módulo no implementa su propio SMTP ni su propia
#  integración con WhatsApp — así toda la suite mantiene un único mecanismo
#  de envío configurado una sola vez en ⚙️ Configuración → 📧 Envíos.
#

def enviar_fe_cliente(
    numero_fe: str,
    cliente: dict,
    num_reserva: str,
    metodo: str,
    total: float,
    pdf_bytes: Optional[bytes] = None,
    xml_bytes: Optional[bytes] = None,
) -> dict:
    """
    Envía la factura electrónica (PDF + XML por correo; solo PDF por
    WhatsApp) al cliente, usando los datos de contacto de `cliente`
    (email / telefono) y el mecanismo de envío ya configurado en pagos.py.

    Retorna un dict:
        {"email": (bool|None, mensaje) | None,
         "whatsapp": (bool|None, mensaje) | None}
    `None` en una clave significa que no se intentó ese canal (sin dato de
    contacto). `bool` es None en whatsapp cuando se entrega solo el enlace
    manual (sin API configurada) — no se pudo confirmar el envío real.
    """
    resultado = {"email": None, "whatsapp": None}

    email_rec = (cliente.get("email") or "").strip()
    tel_rec   = (cliente.get("telefono") or "").strip()
    nombre_rec = (cliente.get("razon_social") or cliente.get("nombre")
                  or "Cliente")

    fmt_cop_fn    = _ctx.get("fmt_cop", lambda v: f"${v:,.0f}")
    negocio       = _ctx.get("NEGOCIO", "")
    direccion_neg = _ctx.get("DIRECCION", "")
    telefono_neg  = _ctx.get("TELEFONO", "")
    nit_neg       = _ctx.get("NIT", "")

    # ── Correo ─────────────────────────────────────────────────────────────
    if email_rec and "@" in email_rec:
        fn_smtp_ok = _ctx.get("smtp_disponible")
        fn_env_mail= _ctx.get("enviar_factura_email")
        fn_smtp_cfg= _ctx.get("_smtp_config", lambda: {})
        if fn_smtp_ok and fn_env_mail and fn_smtp_ok():
            cfg_smtp = fn_smtp_cfg() or {}
            asunto = f"Factura Electrónica {numero_fe} · {negocio}"
            cuerpo = (
                f"Hola {nombre_rec},\n\n"
                f"Adjuntamos tu Factura Electrónica de Venta:\n\n"
                f"  • Número FE        : {numero_fe}\n"
                f"  • Reserva asociada : {num_reserva}\n"
                f"  • Total            : {fmt_cop_fn(float(total or 0))} COP\n"
                f"  • Método de pago   : {metodo}\n\n"
                "Adjuntamos el PDF (representación gráfica) y el archivo "
                "XML (UBL 2.1) de la factura, válido ante la DIAN.\n\n"
                f"Gracias por tu visita.\n\n{negocio}\n"
                f"{direccion_neg} · Tel: {telefono_neg} · {nit_neg}"
            )
            adjuntos_extra = (
                [(xml_bytes, f"factura_electronica_{numero_fe}.xml")]
                if xml_bytes else None
            )
            try:
                ok = fn_env_mail(
                    destinatario = email_rec,
                    asunto       = asunto,
                    cuerpo       = cuerpo,
                    pdf_bytes    = pdf_bytes or b"",
                    nombre_pdf   = f"factura_electronica_{numero_fe}.pdf",
                    email_from   = cfg_smtp.get("email_from", ""),
                    nombre_from  = cfg_smtp.get("nombre_from", ""),
                    adjuntos_extra = adjuntos_extra,
                )
            except TypeError:
                # Compatibilidad si enviar_factura_email aún no acepta
                # adjuntos_extra (versión antigua de pagos.py sin ese parámetro)
                ok = fn_env_mail(
                    destinatario = email_rec, asunto = asunto, cuerpo = cuerpo,
                    pdf_bytes = pdf_bytes or b"",
                    nombre_pdf = f"factura_electronica_{numero_fe}.pdf",
                    email_from = cfg_smtp.get("email_from", ""),
                    nombre_from = cfg_smtp.get("nombre_from", ""),
                )
            except Exception as e:
                ok = False
                print(f"[fe_dian] ERROR enviando correo FE {numero_fe}: {e}")
            resultado["email"] = (
                bool(ok),
                f"Correo {'enviado' if ok else 'con error'} a {email_rec}"
            )
        else:
            resultado["email"] = (
                False,
                "Correo SMTP no configurado (secrets.toml → [emails])."
            )

    # ── WhatsApp ───────────────────────────────────────────────────────────
    if tel_rec:
        fn_wa_ok     = _ctx.get("whatsapp_api_disponible")
        fn_env_wa    = _ctx.get("enviar_whatsapp_documento")
        fn_wa_manual = _ctx.get("link_whatsapp_manual")
        voucher_like = {
            "numero_reserva": num_reserva,
            "numero_factura": numero_fe,
            "cubiculo":       "",
            "total":          total,
            "metodo_pago":    metodo,
        }
        if fn_wa_ok and fn_env_wa and fn_wa_ok():
            try:
                ok_wa, msg_wa = fn_env_wa(tel_rec, pdf_bytes or b"", voucher_like)
            except Exception as e:
                ok_wa, msg_wa = False, f"❌ Error enviando por WhatsApp: {e}"
            resultado["whatsapp"] = (ok_wa, msg_wa)
        elif fn_wa_manual:
            link = fn_wa_manual(tel_rec, voucher_like)
            resultado["whatsapp"] = (
                None,
                f"WhatsApp API no configurada — enlace manual: {link}"
            )

    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# TRANSMISIÓN SOAP A LA DIAN — VALIDACIÓN PREVIA (Anexo Técnico Cap. 11 y 12)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Implementa el consumo del Web Service SOAP "WcfDianCustomerServices" que
#  la DIAN dispone para el modelo de Validación Previa de Factura
#  Electrónica, según lo descrito en el documento "Conocimientos Requeridos
#  VP Fac-e" (DIAN, v2.0, jul-2019) y el Anexo Técnico de Factura Electrónica
#  de Venta (Resolución 000030 de 2019):
#
#    · SendTestSetAsync  → envío de facturas de prueba en AMBIENTE DE
#                           HABILITACIÓN (asíncrono — requiere GetStatus
#                           para conocer el resultado).
#    · SendBillSync      → envío de facturas en AMBIENTE DE PRODUCCIÓN
#                           (síncrono — la respuesta trae el resultado).
#    · GetStatus / GetStatusZip → consulta del resultado de un envío
#                           asíncrono (habilitación), a partir del ZipKey/
#                           TrackId devuelto por SendTestSetAsync.
#    · GetNumberingRange → consulta la Clave Técnica del rango de
#                           numeración autorizado — necesaria para calcular
#                           el CUFE real (ver calcular_cufe_real()).
#
#  ⚠️ PRERREQUISITOS QUE ESTE MÓDULO NO PUEDE RESOLVER POR TI:
#   1. Certificado digital X.509 vigente (archivo .p12/.pfx) expedido por una
#      Entidad Certificadora autorizada por la ONAC — sección 5.3 del
#      documento "Conocimientos Requeridos VP Fac-e".
#   2. El XML debe llevar Firma Digital XAdES-EPES (política de firma DIAN,
#      Capítulo 9 del Anexo Técnico) — sección 5.4 del mismo documento.
#      La función firmar_xml_xades_epes() de abajo aplica una firma XML-DSig
#      genérica con `signxml` como PUNTO DE PARTIDA; NO es una firma
#      XAdES-EPES completa (le faltan las QualifyingProperties/SignedProperties
#      que exige la política de firma de la DIAN). Antes de usarla contra el
#      servicio real de la DIAN, valida el XML firmado contra las
#      "ejemplificaciones firmadas" de tu Caja de Herramientas, o integra una
#      librería/servicio de firma XAdES-EPES certificado.
#   3. Estar registrado y habilitado en el Catálogo de Participante de la
#      DIAN (sección 7.1 y 7.2 del documento) — de ahí obtienes SoftwareID,
#      SoftwarePIN, el TestSetId y la URL real del WSDL para tu operación.
#
#  Sin (1) y (2) resueltos, `enviar_a_dian()` va a construir y enviar la
#  petición SOAP igual (útil para probar la conectividad/credenciales), pero
#  la DIAN rechazará el documento por firma inválida. El código deja avisos
#  claros (`firmado: False`) en el resultado cuando esto ocurre.
#

def _soap_cfg() -> dict:
    """Configuración SOAP/certificado leída desde configuracion_pagos (PG)."""
    return {
        "wsdl_hab":       _cfg("dian_wsdl_habilitacion", DIAN_WSDL_HABILITACION_DEFAULT),
        "wsdl_prod":      _cfg("dian_wsdl_produccion",   DIAN_WSDL_PRODUCCION_DEFAULT),
        "software_id":    _cfg("dian_software_id", ""),
        "software_pin":   _cfg("dian_software_pin", ""),
        "test_set_id":    _cfg("dian_test_set_id", ""),
        "clave_tecnica":  _cfg("dian_clave_tecnica", ""),
        "cert_path":      _cfg("dian_cert_path", ""),
        "cert_password":  _cfg("dian_cert_password", ""),
        "auto_transmitir":_cfg("dian_transmision_automatica", "no"),
    }


def _wsdl_para_ambiente(ambiente: str) -> str:
    cfg = _soap_cfg()
    return cfg["wsdl_prod"] if str(ambiente) == "1" else cfg["wsdl_hab"]


def _zip_base64(numero_fe: str, xml_bytes: bytes) -> str:
    """Empaqueta el XML en un .zip (requerido por la DIAN) y lo codifica en base64."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{numero_fe}.xml", xml_bytes)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def firmar_xml_xades_epes(xml_bytes: bytes) -> tuple:
    """
    Aplica una firma XML-DSig (enveloped) al XML usando el certificado .p12
    configurado (dian_cert_path / dian_cert_password), como punto de partida
    hacia la Firma Digital XAdES-EPES que exige la DIAN.

    Retorna (xml_firmado: bytes, firmado: bool, mensaje: str).
    Si `signxml` no está instalado o no hay certificado configurado, retorna
    el XML SIN firmar (firmado=False) — la DIAN rechazará ese documento,
    pero el resto del flujo (empaquetado/envío) puede seguir usándose para
    probar la conectividad SOAP.
    """
    cfg = _soap_cfg()
    if not SIGNXML_OK or not LXML_OK:
        faltan = ", ".join(p for p, ok in
                            (("signxml", SIGNXML_OK), ("lxml", LXML_OK)) if not ok)
        return xml_bytes, False, (
            f"Falta instalar: {faltan} — el XML se envía SIN firmar "
            "(pip install signxml cryptography lxml)."
        )
    if not cfg["cert_path"] or not os.path.exists(cfg["cert_path"]):
        return xml_bytes, False, (
            "No hay certificado digital configurado (dian_cert_path) — "
            "el XML se envía SIN firmar."
        )
    try:
        with open(cfg["cert_path"], "rb") as f:
            p12_bytes = f.read()
        clave_priv, cert, _extra = pkcs12.load_key_and_certificates(
            p12_bytes, (cfg["cert_password"] or "").encode(), None
        )
        signer = XMLSigner(
            method=_signxml_methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        )
        root = etree.fromstring(xml_bytes)
        firmado = signer.sign(root, key=clave_priv, cert=cert)
        xml_firmado = etree.tostring(firmado, xml_declaration=True,
                                      encoding="UTF-8", standalone=True)
        return xml_firmado, True, (
            "XML firmado con XML-DSig (enveloped) — recuerda que la DIAN "
            "exige XAdES-EPES completo; valida antes de producción."
        )
    except Exception as e:
        return xml_bytes, False, f"Error firmando XML: {e} — se envía SIN firmar."


def consultar_rango_numeracion_dian(ambiente: str = None) -> dict:
    """
    Invoca GetNumberingRange en el WSDL configurado para consultar el rango
    de numeración autorizado y, si viene incluida, la Clave Técnica.
    Retorna {"ok": bool, "mensaje": str, "datos": dict|None}.
    """
    if not ZEEP_OK:
        return {"ok": False, "mensaje":
                f"`zeep` no disponible en este proceso ({ZEEP_IMPORT_ERROR or 'no instalado'}). "
                "No se puede consumir el Web Service SOAP de la DIAN. Si ya lo "
                "instalaste, revisa la pestaña 🚀 Transmisión SOAP → diagnóstico, "
                "o si usas Streamlit Cloud, agrégalo a requirements.txt y reinicia.",
                "datos": None}

    cfg = _soap_cfg()
    ambiente = ambiente or _cfg("dian_ambiente", "2")
    wsdl = _wsdl_para_ambiente(ambiente)
    if not cfg["software_id"] or not cfg["software_pin"]:
        return {"ok": False, "mensaje":
                "Faltan SoftwareID / SoftwarePIN en la configuración SOAP.",
                "datos": None}
    try:
        token = UsernameToken(cfg["software_id"], cfg["software_pin"], use_digest=True)
        client = zeep.Client(wsdl=wsdl, wsse=token)
        resp = client.service.GetNumberingRange()
        datos = serialize_object(resp)
        return {"ok": True, "mensaje": "Consulta realizada.", "datos": datos}
    except Exception as e:
        return {"ok": False, "mensaje": f"Error consultando GetNumberingRange: {e}",
                "datos": None}


def consultar_estado_dian(track_id: str, ambiente: str = None) -> dict:
    """
    Invoca GetStatus (y GetStatusZip si aplica) para conocer el resultado de
    un envío asíncrono (SendTestSetAsync, ambiente de habilitación).
    Retorna {"ok": bool, "mensaje": str, "datos": dict|None}.
    """
    if not ZEEP_OK:
        return {"ok": False, "mensaje":
                f"`zeep` no disponible en este proceso ({ZEEP_IMPORT_ERROR or 'no instalado'}).",
                "datos": None}

    cfg = _soap_cfg()
    ambiente = ambiente or "2"
    wsdl = _wsdl_para_ambiente(ambiente)
    if not track_id:
        return {"ok": False, "mensaje": "Falta el TrackId/ZipKey a consultar.",
                "datos": None}
    try:
        token = UsernameToken(cfg["software_id"], cfg["software_pin"], use_digest=True)
        client = zeep.Client(wsdl=wsdl, wsse=token)
        resp = client.service.GetStatus(trackId=track_id)
        datos = serialize_object(resp)
        return {"ok": True, "mensaje": "Consulta realizada.", "datos": datos}
    except Exception as e:
        return {"ok": False, "mensaje": f"Error consultando GetStatus: {e}",
                "datos": None}


def enviar_a_dian(numero_fe: str, xml_bytes: bytes, ambiente: str = None) -> dict:
    """
    Firma (best-effort), empaqueta y transmite la factura electrónica a la
    DIAN vía el Web Service SOAP de Validación Previa:
      · ambiente "2" (Pruebas/Habilitación) → SendTestSetAsync (asíncrono;
        el resultado se consulta después con consultar_estado_dian()).
      · ambiente "1" (Producción)           → SendBillSync (síncrono; la
        respuesta ya trae IsValid / StatusCode / XmlDocumentKey).

    Retorna un dict:
        {"ok": bool, "mensaje": str, "firmado": bool, "track_id": str|None,
         "datos": dict|None}
    No lanza excepciones — cualquier error queda reflejado en "ok"/"mensaje".
    """
    if not ZEEP_OK:
        return {"ok": False, "mensaje":
                f"`zeep` no disponible en este proceso ({ZEEP_IMPORT_ERROR or 'no instalado'}) "
                "— no es posible transmitir por SOAP. El XML/PDF locales "
                "siguen disponibles para envío manual por el portal DIAN.",
                "firmado": False, "track_id": None, "datos": None}

    cfg = _soap_cfg()
    ambiente = str(ambiente or _cfg("dian_ambiente", "2"))
    wsdl = _wsdl_para_ambiente(ambiente)

    if not cfg["software_id"] or not cfg["software_pin"]:
        return {"ok": False, "mensaje":
                "Faltan SoftwareID / SoftwarePIN — configúralos en "
                "⚙️ Configuración → 🚀 Transmisión SOAP.",
                "firmado": False, "track_id": None, "datos": None}

    xml_firmado, firmado, msg_firma = firmar_xml_xades_epes(xml_bytes)
    contenido_b64 = _zip_base64(numero_fe, xml_firmado)
    nombre_zip    = f"{numero_fe}.zip"

    try:
        token  = UsernameToken(cfg["software_id"], cfg["software_pin"], use_digest=True)
        client = zeep.Client(wsdl=wsdl, wsse=token)

        if ambiente == "1":
            resp  = client.service.SendBillSync(
                fileName=nombre_zip, contentFile=contenido_b64,
            )
            datos = serialize_object(resp)
            es_valido = bool(datos.get("IsValid")) if isinstance(datos, dict) else None
            mensaje = (
                f"{msg_firma} · Respuesta DIAN (producción): "
                f"IsValid={datos.get('IsValid') if isinstance(datos, dict) else '—'}, "
                f"StatusCode={datos.get('StatusCode') if isinstance(datos, dict) else '—'}"
            )
            return {"ok": bool(es_valido), "mensaje": mensaje, "firmado": firmado,
                    "track_id": None, "datos": datos}
        else:
            resp  = client.service.SendTestSetAsync(
                fileName=nombre_zip, contentFile=contenido_b64,
                testSetId=cfg["test_set_id"],
            )
            datos    = serialize_object(resp)
            track_id = (datos.get("ZipKey") or datos.get("TrackId")
                        if isinstance(datos, dict) else None)
            mensaje  = (
                f"{msg_firma} · Enviado a habilitación (asíncrono). "
                f"Consulta el resultado en unos minutos con GetStatus "
                f"(TrackId: {track_id or '—'})."
            )
            return {"ok": True, "mensaje": mensaje, "firmado": firmado,
                    "track_id": track_id, "datos": datos}
    except Exception as e:
        return {"ok": False, "mensaje": f"Error transmitiendo a la DIAN: {e}",
                "firmado": firmado, "track_id": None, "datos": None}


# ══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA — llamada desde pagos.py
# ══════════════════════════════════════════════════════════════════════════════

def generar_fe_desde_reserva(
    voucher: dict,
    calc: dict,
    cliente: dict,
    metodo: str,
) -> str:
    """
    Hook principal. Genera la factura electrónica XML, su representación
    gráfica (PDF), la registra en PostgreSQL (tabla facturas_electronicas),
    la envía automáticamente al cliente (correo y/o WhatsApp, según los
    datos de contacto disponibles) y devuelve el número de FE.

    Llamar desde crear_reserva_completa() de pagos.py:
        if FE_AVAILABLE:
            try:
                _fe_mod.generar_fe_desde_reserva(voucher, calc, cliente, metodo)
            except Exception:
                pass
    """
    now         = _ahora()
    fecha_str   = now.strftime("%Y-%m-%d")
    hora_str    = now.strftime("%H:%M:%S")
    numero_fe   = _numero_fe_siguiente()
    num_reserva = voucher.get("numero_reserva", "")

    # Datos del receptor.
    # pagos.py permite marcar "Requiero factura a nombre de empresa"
    # (checkbox factura_emp en show_datos / _op_nueva_reserva), lo cual llena
    # cliente["razon_social"] y cliente["nit_empresa"]. En ese caso la FE se
    # emite a nombre de la empresa (NIT) en vez de la persona natural (CC).
    es_empresa  = bool((cliente.get("nit_empresa") or "").strip())
    if es_empresa:
        nit_rec    = cliente.get("nit_empresa", "")
        nombre_rec = cliente.get("razon_social") or cliente.get("nombre", "Consumidor Final")
        tipo_doc   = _mapear_tipo_doc("NIT")
    else:
        nit_rec    = cliente.get("numero_documento", "")
        nombre_rec = cliente.get("nombre", "Consumidor Final")
        tipo_doc   = _mapear_tipo_doc(cliente.get("tipo_doc", "CC"))
    regimen_rec = "O-48" if cliente.get("regimen", "") == "Común" else "O-13"
    email_rec   = cliente.get("email", "")
    ciudad_rec  = cliente.get("ciudad", "Bogotá D.C.")

    subtotal    = float(calc.get("subtotal", 0))
    iva_pct     = float(calc.get("iva_pct", 19.0))
    iva_valor   = float(calc.get("iva", 0))
    total       = float(calc.get("total", 0))
    horas       = float(calc.get("horas", 1))
    precio_hora = float(calc.get("precio_hora", subtotal / max(horas, 1)))
    desc_item   = (
        f"Espacio de descanso {voucher.get('cubiculo', '')} · "
        f"WiFi · Baño · Carga · {horas}h"
    )

    nit_emisor_limpio = _nit_limpio(_cfg("dian_nit_emisor", "902047871"))
    clave_tecnica_cfg = _cfg("dian_clave_tecnica", "")
    if clave_tecnica_cfg:
        try:
            cufe = calcular_cufe_real(
                numero_fe      = numero_fe,
                fecha_emision  = fecha_str,
                hora_emision   = hora_str,
                subtotal       = subtotal,
                iva_valor      = iva_valor,
                total          = total,
                nit_emisor     = nit_emisor_limpio,
                nit_receptor   = nit_rec,
                clave_tecnica  = clave_tecnica_cfg,
                ambiente       = _cfg("dian_ambiente", "2"),
            )
        except Exception as _cufe_err:
            print(f"[fe_dian] WARN: no se pudo calcular el CUFE real, se usa "
                  f"el simulado: {_cufe_err}")
            cufe = _cufe_simulado(numero_fe, nit_emisor_limpio, total, fecha_str)
    else:
        # Sin Clave Técnica configurada aún (ver pestaña 🚀 Transmisión SOAP
        # → GetNumberingRange) no es posible calcular un CUFE real.
        cufe = _cufe_simulado(numero_fe, nit_emisor_limpio, total, fecha_str)

    # Generar XML
    xml_bytes = generar_xml_factura(
        numero_fe        = numero_fe,
        fecha_emision    = fecha_str,
        hora_emision     = hora_str,
        nit_receptor     = nit_rec,
        nombre_receptor  = nombre_rec,
        email_receptor   = email_rec,
        tipo_doc_receptor= tipo_doc,
        regimen_receptor = regimen_rec,
        ciudad_receptor  = ciudad_rec,
        descripcion_item = desc_item,
        cantidad         = horas,
        precio_unitario  = precio_hora,
        subtotal         = subtotal,
        iva_pct          = iva_pct,
        iva_valor        = iva_valor,
        total            = total,
        metodo_pago      = metodo,
        num_reserva      = num_reserva,
        cufe             = cufe,
    )

    # Guardar XML en disco local (facturas_xml/)
    _guardar_xml_local(numero_fe, xml_bytes)

    # Generar la representación gráfica (PDF) — usada para imprimir y para
    # adjuntar en el envío por correo/WhatsApp. Si reportlab no está
    # instalado, generar_pdf_factura() retorna None y simplemente no se
    # imprime/envía PDF (el XML y el registro en PostgreSQL sí quedan OK).
    pdf_bytes = None
    try:
        pdf_bytes = generar_pdf_factura(
            numero_fe        = numero_fe,
            fecha_emision    = fecha_str,
            hora_emision     = hora_str,
            nit_receptor     = nit_rec,
            nombre_receptor  = nombre_rec,
            email_receptor   = email_rec,
            tipo_doc_receptor= tipo_doc,
            ciudad_receptor  = ciudad_rec,
            descripcion_item = desc_item,
            cantidad         = horas,
            precio_unitario  = precio_hora,
            subtotal         = subtotal,
            iva_pct          = iva_pct,
            iva_valor        = iva_valor,
            total            = total,
            metodo_pago      = metodo,
            num_reserva      = num_reserva,
            cufe             = cufe,
        )
    except Exception as _pdf_err:
        print(f"[fe_dian] WARN: no se pudo generar el PDF de la FE {numero_fe}: {_pdf_err}")

    # Guardar PDF en disco local (facturas_pdf/) — queda disponible para
    # reimprimir/reenviar más adelante desde el panel sin regenerar nada.
    if pdf_bytes:
        _guardar_pdf_local(numero_fe, pdf_bytes)

    # ── Envío automático al cliente (correo y/o WhatsApp) ─────────────────
    # No bloqueante: si falla o no hay datos de contacto, la reserva y la FE
    # ya quedaron generadas y registradas igual.
    envio_resumen = ""
    try:
        tel_rec = cliente.get("telefono", "")
        envio = enviar_fe_cliente(
            numero_fe   = numero_fe,
            cliente     = {**cliente, "telefono": tel_rec},
            num_reserva = num_reserva,
            metodo      = metodo,
            total       = total,
            pdf_bytes   = pdf_bytes,
            xml_bytes   = xml_bytes,
        )
        partes = []
        if envio.get("email") is not None:
            ok_e, msg_e = envio["email"]
            partes.append(f"email:{'ok' if ok_e else 'error'} ({msg_e})")
        if envio.get("whatsapp") is not None:
            ok_w, msg_w = envio["whatsapp"]
            estado_w = "ok" if ok_w else ("manual" if ok_w is None else "error")
            partes.append(f"whatsapp:{estado_w} ({msg_w})")
        envio_resumen = " · ".join(partes)
    except Exception as _envio_err:
        envio_resumen = f"error al enviar: {_envio_err}"
        print(f"[fe_dian] WARN: no se pudo enviar la FE {numero_fe} al cliente: {_envio_err}")

    # ── Transmisión automática a la DIAN (opcional, desactivada por defecto) ──
    # Solo se ejecuta si el operador activó "dian_transmision_automatica" en
    # ⚙️ Configuración DIAN — no bloqueante: si falla, la reserva, la FE local
    # y el envío al cliente ya quedaron OK igual. El estado real se actualiza
    # en Estado_DIAN/Observaciones para revisar luego en la pestaña
    # 🚀 Transmisión SOAP.
    estado_dian_inicial = "pendiente"
    obs_dian = ""
    if _cfg("dian_transmision_automatica", "no") == "si":
        try:
            resultado_dian = enviar_a_dian(numero_fe, xml_bytes, _cfg("dian_ambiente", "2"))
            estado_dian_inicial = "enviada" if resultado_dian["ok"] else "pendiente"
            obs_dian = resultado_dian["mensaje"][:500]
            if resultado_dian.get("track_id"):
                obs_dian += f" · TrackId: {resultado_dian['track_id']}"
        except Exception as _dian_err:
            obs_dian = f"error transmitiendo a DIAN: {_dian_err}"
            print(f"[fe_dian] WARN: no se pudo transmitir la FE {numero_fe} a la DIAN: {_dian_err}")

    # ── Registrar en PostgreSQL (reemplaza _gs_append_fe / append_row) ────────
    _pg_append_fe({
        "Fecha_Emision":     fecha_str,
        "Numero_FE":         numero_fe,
        "Numero_Reserva":    num_reserva,
        "NIT_Receptor":      nit_rec,
        "Nombre_Receptor":   nombre_rec,
        "Subtotal_COP":      f"{subtotal:.2f}",
        "IVA_COP":           f"{iva_valor:.2f}",
        "Total_COP":         f"{total:.2f}",
        "Metodo_Pago":       metodo,
        "Estado_DIAN":       estado_dian_inicial,
        "CUFE":              cufe,
        "Archivo_DIAN":      "",         # vacío al inicio
        "Observaciones":     obs_dian,
        "Operador":          _operador(),
        "Creado_En":         now.isoformat(),
        "Email_Receptor":    email_rec,
        "Telefono_Receptor": cliente.get("telefono", ""),
        "Tipo_Doc_Receptor": tipo_doc,
        "Regimen_Receptor":  regimen_rec,
        "Ciudad_Receptor":   ciudad_rec,
        "Horas":             horas,
        "Precio_Hora":       precio_hora,
        "Descripcion_Item":  desc_item,
        "Envio_Cliente":     envio_resumen,
    })

    # NOTA: este módulo YA NO registra un comprobante contable aquí.
    # Antes existía un intento de causación (comp_ingreso_factura) en este
    # mismo punto, pero eso duplicaba el ingreso: pagos.py ya causa la
    # factura Y el pago una sola vez, con el número de factura interno,
    # a través de contabilidad.on_reserva_creada() dentro de
    # crear_reserva_completa() — ese es el único punto de verdad contable.
    # Generar aquí una segunda causación con el numero_fe de la DIAN
    # habría registrado el mismo ingreso dos veces en el libro contable.

    return numero_fe


def _datos_generacion_desde_row(row: dict) -> dict:
    """
    Reconstruye los kwargs comunes de generar_xml_factura()/generar_pdf_factura()
    a partir de una fila ya almacenada en facturas_electronicas — permite
    reimprimir/reenviar una FE en cualquier momento con los datos originales
    del receptor (email, teléfono, ciudad, tipo doc, régimen, ítem), sin
    depender de que el XML/PDF sigan existiendo en disco.
    """
    def _f(v, default=0.0):
        try:    return float(v) if v not in (None, "") else default
        except: return default

    subtotal = _f(row.get("Subtotal_COP"))
    iva_v    = _f(row.get("IVA_COP"))
    total_v  = _f(row.get("Total_COP"))
    horas_v  = _f(row.get("Horas"), 1.0) or 1.0
    precio_v = _f(row.get("Precio_Hora")) or (subtotal / max(horas_v, 1))
    iva_pct  = round((iva_v / subtotal) * 100, 2) if subtotal else 19.0

    return dict(
        numero_fe        = row.get("Numero_FE", ""),
        fecha_emision    = row.get("Fecha_Emision", _ahora().strftime("%Y-%m-%d")),
        hora_emision     = "00:00:00",
        nit_receptor     = row.get("NIT_Receptor", ""),
        nombre_receptor  = row.get("Nombre_Receptor", ""),
        email_receptor   = row.get("Email_Receptor", ""),
        tipo_doc_receptor= row.get("Tipo_Doc_Receptor", "13") or "13",
        regimen_receptor = row.get("Regimen_Receptor", "O-13") or "O-13",
        ciudad_receptor  = row.get("Ciudad_Receptor", "") or "Bogotá D.C.",
        descripcion_item = row.get("Descripcion_Item", "") or (
            f"Espacio de descanso · Reserva {row.get('Numero_Reserva','')}"
        ),
        cantidad         = horas_v,
        precio_unitario  = precio_v,
        subtotal         = subtotal,
        iva_pct          = iva_pct,
        iva_valor        = iva_v,
        total            = total_v,
        metodo_pago      = row.get("Metodo_Pago", "Efectivo"),
        num_reserva      = row.get("Numero_Reserva", ""),
        cufe             = row.get("CUFE", ""),
    )


# ══════════════════════════════════════════════════════════════════════════════
# PANEL STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

def _diagnostico_dependencia(paquete: str, error_import: str) -> str:
    """
    Arma un texto de diagnóstico para cuando una dependencia opcional
    (zeep, signxml, reportlab...) no se pudo importar — muy útil porque la
    causa más común en producción NO es que falte pip install, sino que:
      · La app corre en Streamlit Community Cloud: un `pip install` manual
        (en tu computador, o incluso en una terminal dentro de la nube) NO
        persiste ni afecta el proceso desplegado. Hay que agregar el
        paquete a `requirements.txt` en el repositorio y hacer que la app
        se reinicie/redeploye (Streamlit Cloud lo instala automáticamente
        al reiniciar).
      · Se instaló en un intérprete de Python distinto al que ejecuta
        realmente la app (por eso se muestra sys.executable abajo).
      · El proceso de Streamlit sigue corriendo desde ANTES de instalar el
        paquete — los `import` ya fallaron una vez al arrancar el script y
        no se re-intentan hasta el próximo reinicio/redeploy del proceso.
    """
    intento_en_vivo = "no verificado"
    try:
        importlib.import_module(paquete)
        intento_en_vivo = ("✅ SÍ se puede importar ahora mismo con "
                          "importlib — probablemente solo falta REINICIAR "
                          "la app para que tome el paquete nuevo.")
    except Exception as e:
        intento_en_vivo = f"❌ Sigue sin poder importarse: {type(e).__name__}: {e}"

    return (
        f"Paquete: {paquete}\n"
        f"Error capturado al importar (al arrancar la app): {error_import or '—'}\n"
        f"Intento de import en vivo justo ahora: {intento_en_vivo}\n"
        f"Python en ejecución (sys.executable): {sys.executable}\n"
        f"Versión de Python: {sys.version.split()[0]}\n\n"
        "Causas más frecuentes:\n"
        "  1. App en Streamlit Community Cloud: agrega el paquete a "
        "requirements.txt del repo y reinicia/redeploya la app — un "
        "`pip install` manual no persiste ahí.\n"
        "  2. Servidor propio: revisa que lo instalaste con el MISMO "
        "intérprete que corre `streamlit run` (compara con sys.executable "
        "de arriba) y reinicia el proceso de streamlit después de instalar.\n"
        "  3. Conflicto de subdependencias (versión de lxml/urllib3/etc.) — "
        "el mensaje de error de arriba suele indicar cuál."
    )


def render_panel_fe() -> None:
    """
    Panel completo de Factura Electrónica DIAN.
    Lee y escribe exclusivamente en PostgreSQL (tabla facturas_electronicas).

    Agregar en mod_map de show_operador():
        "⚡ Factura Electrónica": _fe_mod.render_panel_fe if FE_AVAILABLE else _op_dashboard,
    """
    try:
        import streamlit as st
    except ImportError:
        return

    fn_fmt   = _ctx.get("fmt_cop", lambda v: f"${v:,.0f}".replace(",", "."))
    fn_ahora = _ctx.get("ahora_col", _ahora)

    # ── Encabezado ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0d1f3c,#050b1a);
                border:1px solid rgba(0,212,255,0.3);border-radius:16px;
                padding:20px 24px;margin-bottom:20px">
      <h2 style="margin:0;color:#00d4ff;font-family:'Inconsolata',monospace">
        ⚡ Facturación Electrónica DIAN
      </h2>
      <p style="margin:4px 0 0;color:#94a3b8;font-size:14px">
        Colombia · UBL 2.1 · VPFE · Numeración autorizada · PostgreSQL
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Verificar config DIAN (desde configuracion_pagos en PG)
    resolucion = _cfg("dian_resolucion_num", "")
    prefijo    = _cfg("dian_prefijo_fe", "")
    if not resolucion or not prefijo:
        st.warning(
            "⚠️ **Configura primero la resolución DIAN** en ⚙️ Configuración → "
            "pestaña *Factura Electrónica*. Necesitas: número de resolución, "
            "prefijo, rango y NIT emisor."
        )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Facturas emitidas",
        "🌐 Portal DIAN",
        "📤 Subir archivo DIAN",
        "⚙️ Configuración DIAN",
        "🚀 Transmisión SOAP",
    ])

    # ── TAB 1: Facturas emitidas ───────────────────────────────────────────────
    with tab1:
        st.markdown("### Facturas electrónicas generadas")

        col_reload, _ = st.columns([1, 5])
        with col_reload:
            if st.button("🔄 Recargar", key="btn_reload_fe"):
                st.rerun()

        rows_fe = _pg_read_fe()

        if not rows_fe:
            st.info(
                "No hay facturas electrónicas registradas en PostgreSQL aún. "
                "Se generan automáticamente al crear una reserva."
            )
        else:
            if PANDAS_OK:
                data = []
                for r in rows_fe:
                    try:    total_v = float(r.get("Total_COP", 0) or 0)
                    except: total_v = 0.0
                    data.append({
                        "Fecha":        r.get("Fecha_Emision", ""),
                        "N° FE":        r.get("Numero_FE", ""),
                        "N° Reserva":   r.get("Numero_Reserva", ""),
                        "Receptor":     r.get("Nombre_Receptor", ""),
                        "Total COP":    total_v,
                        "Método":       r.get("Metodo_Pago", ""),
                        "Estado DIAN":  r.get("Estado_DIAN", "pendiente"),
                        "Archivo DIAN": r.get("Archivo_DIAN", "—") or "—",
                        "Envío cliente": r.get("Envio_Cliente", "—") or "—",
                    })
                df = pd.DataFrame(data)

                def _color_estado(val):
                    c = {
                        "aceptada":  "#00ff88",
                        "enviada":   "#74b9ff",
                        "rechazada": "#ff4757",
                        "pendiente": "#ffd32a",
                    }.get(val, "#fff")
                    return f"color:{c};font-weight:700"

                st.dataframe(
                    df.style.applymap(_color_estado, subset=["Estado DIAN"]),
                    use_container_width=True, hide_index=True
                )

                total_fe = df["Total COP"].sum()
                col_t1, col_t2, col_t3 = st.columns(3)
                col_t1.metric("Total facturas",  len(df))
                col_t2.metric("Total facturado", fn_fmt(total_fe))
                col_t3.metric("Aceptadas DIAN",
                              len(df[df["Estado DIAN"] == "aceptada"]))

        st.divider()
        st.markdown("#### Gestionar, imprimir y reenviar una factura")

        rows_fe2 = _pg_read_fe()
        if rows_fe2:
            opciones = [r.get("Numero_FE", "") for r in rows_fe2 if r.get("Numero_FE")]
            if opciones:
                sel_fe   = st.selectbox("Selecciona factura electrónica",
                                        opciones, key="fe_sel_num")
                row_sel  = next((r for r in rows_fe2
                                 if r.get("Numero_FE") == sel_fe), None)

                if row_sel:
                    col_a, col_b = st.columns(2)

                    with col_a:
                        estados_opt = ["pendiente", "enviada", "aceptada", "rechazada"]
                        est_actual  = row_sel.get("Estado_DIAN", "pendiente")
                        idx_est     = estados_opt.index(est_actual) if est_actual in estados_opt else 0
                        nuevo_estado = st.selectbox(
                            "Actualizar estado DIAN", estados_opt,
                            index=idx_est, key="fe_estado_sel"
                        )
                        if st.button("💾 Guardar estado", key="btn_fe_estado"):
                            _pg_upsert_fe(sel_fe, "Estado_DIAN", nuevo_estado)
                            st.success(f"✅ Estado actualizado → **{nuevo_estado}**")
                            st.rerun()

                    with col_b:
                        obs_fe = st.text_input(
                            "Observación / N° radicado DIAN",
                            value=row_sel.get("Observaciones", "") or "",
                            key="fe_obs",
                        )
                        if st.button("💾 Guardar observación", key="btn_fe_obs"):
                            _pg_upsert_fe(sel_fe, "Observaciones", obs_fe)
                            st.success("✅ Observación guardada en PostgreSQL")

                    st.markdown("##### 🖨️ Generación / impresión")
                    kwargs_gen = _datos_generacion_desde_row(row_sel)

                    col_c, col_d = st.columns(2)
                    with col_c:
                        xml_b = generar_xml_factura(**kwargs_gen)
                        st.download_button(
                            label     = f"⬇️ Descargar XML ({sel_fe})",
                            data      = xml_b,
                            file_name = f"{sel_fe}.xml",
                            mime      = "application/xml",
                            key       = "dl_xml_btn",
                            use_container_width=True,
                        )
                    with col_d:
                        kwargs_pdf = {k: v for k, v in kwargs_gen.items()
                                      if k != "regimen_receptor"}
                        pdf_b = generar_pdf_factura(**kwargs_pdf)
                        if pdf_b:
                            st.download_button(
                                label     = f"🖨️ Imprimir / descargar PDF ({sel_fe})",
                                data      = pdf_b,
                                file_name = f"factura_electronica_{sel_fe}.pdf",
                                mime      = "application/pdf",
                                key       = "dl_pdf_btn",
                                use_container_width=True,
                            )
                        else:
                            st.caption(
                                "⚠️ Falta instalar `reportlab` para generar el PDF "
                                "(`pip install reportlab`). El XML sí está disponible."
                            )

                    st.markdown("##### 📤 Reenviar al cliente")
                    st.caption(
                        "Puedes corregir o completar el correo y el celular "
                        "antes de reenviar — se guardan para la próxima vez."
                    )
                    col_contacto1, col_contacto2 = st.columns(2)
                    with col_contacto1:
                        email_envio = st.text_input(
                            "📧 Correo electrónico",
                            value=row_sel.get("Email_Receptor", "") or "",
                            placeholder="cliente@correo.com",
                            key="fe_email_envio",
                        )
                    with col_contacto2:
                        tel_envio = st.text_input(
                            "📱 Celular / WhatsApp",
                            value=row_sel.get("Telefono_Receptor", "") or "",
                            placeholder="3001234567",
                            key="fe_tel_envio",
                        )

                    col_e, col_f = st.columns(2)
                    cliente_envio = {
                        "email":        (email_envio or "").strip(),
                        "telefono":     (tel_envio or "").strip(),
                        "nombre":       row_sel.get("Nombre_Receptor", ""),
                        "razon_social": "",
                    }
                    with col_e:
                        if st.button("✉️ Reenviar por correo", key="btn_fe_email",
                                     use_container_width=True):
                            if not cliente_envio["email"]:
                                st.warning("Escribe un correo electrónico para poder enviar la factura.")
                            else:
                                envio = enviar_fe_cliente(
                                    numero_fe   = sel_fe,
                                    cliente     = {**cliente_envio, "telefono": ""},
                                    num_reserva = row_sel.get("Numero_Reserva", ""),
                                    metodo      = row_sel.get("Metodo_Pago", ""),
                                    total       = kwargs_gen["total"],
                                    pdf_bytes   = pdf_b,
                                    xml_bytes   = xml_b,
                                )
                                ok_e, msg_e = envio.get("email", (False, "sin intento"))
                                (st.success if ok_e else st.error)(msg_e)
                                # Guardar el correo (corregido o confirmado) y el
                                # resultado del envío, para la próxima vez.
                                if cliente_envio["email"] != (row_sel.get("Email_Receptor", "") or ""):
                                    _pg_upsert_fe(sel_fe, "Email_Receptor", cliente_envio["email"])
                                _pg_upsert_fe(sel_fe, "Envio_Cliente",
                                              f"email:{'ok' if ok_e else 'error'} ({msg_e})")
                    with col_f:
                        if st.button("📱 Reenviar por WhatsApp", key="btn_fe_wa",
                                     use_container_width=True):
                            if not cliente_envio["telefono"]:
                                st.warning("Escribe un número de celular para poder enviar la factura.")
                            else:
                                envio = enviar_fe_cliente(
                                    numero_fe   = sel_fe,
                                    cliente     = {**cliente_envio, "email": ""},
                                    num_reserva = row_sel.get("Numero_Reserva", ""),
                                    metodo      = row_sel.get("Metodo_Pago", ""),
                                    total       = kwargs_gen["total"],
                                    pdf_bytes   = pdf_b,
                                    xml_bytes   = xml_b,
                                )
                                ok_w, msg_w = envio.get("whatsapp", (False, "sin intento"))
                                (st.info if ok_w is None else
                                 st.success if ok_w else st.error)(msg_w)
                                estado_w = "ok" if ok_w else ("manual" if ok_w is None else "error")
                                # Guardar el celular (corregido o confirmado) y el
                                # resultado del envío, para la próxima vez.
                                if cliente_envio["telefono"] != (row_sel.get("Telefono_Receptor", "") or ""):
                                    _pg_upsert_fe(sel_fe, "Telefono_Receptor", cliente_envio["telefono"])
                                _pg_upsert_fe(sel_fe, "Envio_Cliente",
                                              f"whatsapp:{estado_w} ({msg_w})")

    # ── TAB 2: Portal DIAN ─────────────────────────────────────────────────────
    with tab2:
        st.markdown("### 🌐 Portal DIAN — Facturando Electrónicamente")

        st.markdown(f"""
        <div style="background:#0d1f3c;border:1px solid rgba(0,212,255,0.3);
                    border-radius:12px;padding:20px;margin-bottom:16px">
          <h4 style="color:#00d4ff;margin:0 0 12px">Pasos para enviar a la DIAN:</h4>
          <ol style="color:#e2e8f0;line-height:2;margin:0;padding-left:20px">
            <li>Haz clic en <b style="color:#ffd32a">Abrir portal DIAN</b> → inicia sesión</li>
            <li>En el portal ve a <b>Facturar → Cargar XML</b></li>
            <li>Descarga el XML desde la pestaña <b>📋 Facturas emitidas</b></li>
            <li>Carga el XML en el portal DIAN y obtén el número de radicado</li>
            <li>Regresa aquí y actualiza el estado a <b style="color:#00ff88">aceptada</b></li>
            <li>Sube el acuse de recibo en la pestaña <b>📤 Subir archivo DIAN</b></li>
          </ol>
        </div>
        """, unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns([1, 2])
        with col_btn1:
            st.markdown(f"""
            <a href="{URL_DIAN_LOGIN}" target="_blank" rel="noopener noreferrer"
               style="display:block;background:linear-gradient(135deg,#00d4ff,#0095b3);
                      color:#050b1a;font-weight:700;text-align:center;
                      padding:14px 24px;border-radius:10px;text-decoration:none;
                      font-family:'Inconsolata',monospace;font-size:15px;
                      box-shadow:0 4px 20px rgba(0,212,255,0.3)">
              🌐 Abrir portal DIAN<br>
              <span style="font-size:11px;font-weight:400">catalogo-vpfe.dian.gov.co</span>
            </a>
            """, unsafe_allow_html=True)

        with col_btn2:
            st.markdown(f"""
            <div style="background:#050b1a;border:1px solid rgba(255,211,42,0.3);
                        border-radius:10px;padding:12px 16px;font-size:13px;color:#94a3b8">
              🔗 URL directa:<br>
              <code style="color:#ffd32a;font-size:12px">{URL_DIAN_LOGIN}</code><br><br>
              Si el botón no abre, copia la URL y pégala en tu navegador.
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.markdown("#### 📋 Resolución vigente configurada (PostgreSQL)")
        res_num   = _cfg("dian_resolucion_num",  "—")
        res_fecha = _cfg("dian_resolucion_fecha", "—")
        pref_fe   = _cfg("dian_prefijo_fe",       "—")
        rng_d     = _cfg("dian_rango_desde",      "—")
        rng_h     = _cfg("dian_rango_hasta",      "—")
        amb       = ("🟢 Producción" if _cfg("dian_ambiente", "2") == "1"
                     else "🟡 Pruebas")

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("N° Resolución", res_num)
        col_r2.metric("Prefijo FE",    pref_fe)
        col_r3.metric("Ambiente",      amb)
        col_r4, col_r5, col_r6 = st.columns(3)
        col_r4.metric("Fecha resolución", res_fecha)
        col_r5.metric("Rango desde",      rng_d)
        col_r6.metric("Rango hasta",      rng_h)

        if res_num == "—":
            st.error("❌ No has configurado la resolución DIAN. "
                     "Ve a ⚙️ Configuración → Factura Electrónica.")

    # ── TAB 3: Subir archivo DIAN ──────────────────────────────────────────────
    with tab3:
        st.markdown("### 📤 Subir acuse / respuesta de la DIAN")
        st.caption(
            "Sube el archivo que te entrega el portal DIAN tras el envío de la factura: "
            "puede ser el acuse de recibo (.pdf), el reporte de validación (.xlsx) o el ZIP."
        )

        rows_fe3  = _pg_read_fe()
        opciones3 = [r.get("Numero_FE", "") for r in rows_fe3 if r.get("Numero_FE")]

        if not opciones3:
            st.info("Aún no hay facturas electrónicas en PostgreSQL.")
        else:
            sel_up = st.selectbox(
                "¿A qué factura electrónica corresponde este archivo?",
                opciones3, key="fe_upload_sel",
            )
            archivo = st.file_uploader(
                "Selecciona el archivo de respuesta de la DIAN",
                type=["xlsx", "pdf", "zip", "xml"],
                key="fe_file_up",
                help="Formatos aceptados: .xlsx, .pdf, .zip, .xml",
            )

            if archivo:
                st.markdown(f"""
                <div style="background:#0d1f3c;border:1px solid rgba(0,255,136,0.3);
                            border-radius:10px;padding:12px 16px;font-size:13px">
                  📎 Archivo cargado: <b style="color:#00ff88">{archivo.name}</b>
                  &nbsp;·&nbsp; Tamaño: {archivo.size / 1024:.1f} KB
                  &nbsp;·&nbsp; Tipo: {archivo.type}
                </div>
                """, unsafe_allow_html=True)

                col_ac1, col_ac2 = st.columns(2)
                with col_ac1:
                    estado_up = st.selectbox(
                        "Estado DIAN a asignar",
                        ["enviada", "aceptada", "rechazada"],
                        key="fe_estado_up",
                    )
                with col_ac2:
                    obs_up = st.text_input(
                        "Número radicado / observación DIAN",
                        key="fe_obs_up",
                        placeholder="Ej: RAD-2025-001234",
                    )

                if st.button("💾 Guardar archivo y actualizar estado",
                             key="btn_fe_guardar_arch",
                             type="primary", use_container_width=True):
                    # 1. Guardar en disco local
                    nombre_guardado = archivo.name
                    try:
                        folder_dian = "archivos_dian"
                        os.makedirs(folder_dian, exist_ok=True)
                        nombre_guardado = f"{sel_up}_{archivo.name}"
                        ruta_local = os.path.join(folder_dian, nombre_guardado)
                        with open(ruta_local, "wb") as f:
                            f.write(archivo.getbuffer())
                    except Exception as e:
                        st.warning(f"No se pudo guardar en disco: {e}. "
                                   "Se registra solo en PostgreSQL.")

                    # 2. ── Actualizar en PostgreSQL ───────────────────────────
                    _pg_upsert_fe(sel_up, "Estado_DIAN",   estado_up)
                    _pg_upsert_fe(sel_up, "Archivo_DIAN",  nombre_guardado)
                    _pg_upsert_fe(sel_up, "Observaciones", obs_up)

                    st.success(
                        f"✅ Archivo **{nombre_guardado}** vinculado a {sel_up} "
                        f"en PostgreSQL. Estado: **{estado_up}**."
                    )
                    st.download_button(
                        label     = f"⬇️ Descargar {archivo.name}",
                        data      = archivo.getbuffer(),
                        file_name = archivo.name,
                        mime      = archivo.type,
                        key       = "dl_arch_dian",
                    )

    # ── TAB 4: Configuración DIAN ──────────────────────────────────────────────
    with tab4:
        st.markdown("### ⚙️ Configuración Factura Electrónica DIAN")
        st.caption(
            "Los datos se guardan en **configuracion_pagos** (PostgreSQL) y se usan "
            "en todos los XML generados. Se leen con get_config() en cada factura."
        )

        fn_set = _ctx.get("set_config")
        if not fn_set:
            st.error("set_config no disponible. Verifica set_context(globals()).")
            return

        col1, col2 = st.columns(2)
        with col1:
            nit_e  = st.text_input(
                "NIT emisor (sin dígito verificador)",
                value=_cfg("dian_nit_emisor", _nit_limpio("902.047.871")),
                key="cfg_nit_e"
            )
            dv_e   = st.text_input(
                "Dígito verificador NIT",
                value=_cfg("dian_digito_verificador",
                           _calcular_digito_verificacion(
                               _cfg("dian_nit_emisor", "902047871"))),
                key="cfg_dv_e", max_chars=1
            )
            razon  = st.text_input(
                "Razón social emisor",
                value=_cfg("dian_razon_social", "Suite Salitre Vip S.A.S."),
                key="cfg_razon"
            )
            nombre_com_cfg = st.text_input(
                "Nombre comercial",
                value=_cfg("dian_nombre_comercial", "Suite Salitre Vip"),
                key="cfg_nom_com"
            )
            regimen_e = st.selectbox(
                "Régimen emisor",
                ["O-13 (Simplificado)", "O-48 (Responsable de IVA)"],
                index=0 if _cfg("dian_regimen", "O-13").startswith("O-13") else 1,
                key="cfg_regimen"
            )

        with col2:
            resolucion_n = st.text_input(
                "Número de resolución DIAN",
                value=_cfg("dian_resolucion_num", ""),
                key="cfg_res_num", placeholder="Ej: 18764065649999"
            )
            resolucion_f = st.date_input(
                "Fecha de resolución",
                value=_safe_date(_cfg("dian_resolucion_fecha", "")),
                key="cfg_res_fecha"
            )
            prefijo_fe_cfg = st.text_input(
                "Prefijo factura electrónica",
                value=_cfg("dian_prefijo_fe", "SESP"),
                key="cfg_prefijo", max_chars=4
            )
            rango_d = st.number_input(
                "Rango desde (inicio numeración)",
                value=_safe_int(_cfg("dian_rango_desde", "1"), 1),
                min_value=1, key="cfg_rng_d"
            )
            rango_h = st.number_input(
                "Rango hasta (fin numeración)",
                value=_safe_int(_cfg("dian_rango_hasta", "5000"), 5000),
                min_value=1, key="cfg_rng_h"
            )

        col3, col4 = st.columns(2)
        with col3:
            ambiente_cfg = st.selectbox(
                "Ambiente DIAN",
                ["2 — Pruebas (Habilitación)", "1 — Producción"],
                index=0 if _cfg("dian_ambiente", "2") == "2" else 1,
                key="cfg_amb"
            )
            email_fe_cfg = st.text_input(
                "Email notificaciones FE",
                value=_cfg("dian_email_emisor", ""),
                key="cfg_email_fe", placeholder="fe@jjgt.com.co"
            )
        with col4:
            ciudad_e = st.text_input(
                "Ciudad emisor",
                value=_cfg("dian_ciudad_emisor", "Bogotá D.C."),
                key="cfg_ciudad_e"
            )
            dept_e   = st.text_input(
                "Departamento emisor",
                value=_cfg("dian_dept_emisor", "Cundinamarca"),
                key="cfg_dept_e"
            )
            cp_e     = st.text_input(
                "Código postal",
                value=_cfg("dian_codigo_postal", "110221"),
                key="cfg_cp_e", max_chars=6
            )

        st.divider()
        st.markdown("#### 🚀 Transmisión SOAP a la DIAN (opcional)")
        st.caption(
            "Solo necesario si vas a transmitir automáticamente por el Web "
            "Service SOAP en vez de subir el XML manualmente al portal DIAN. "
            "Datos del Catálogo de Participante DIAN."
        )
        col5, col6 = st.columns(2)
        with col5:
            wsdl_hab_cfg = st.text_input(
                "WSDL Habilitación (pruebas)",
                value=_cfg("dian_wsdl_habilitacion", DIAN_WSDL_HABILITACION_DEFAULT),
                key="cfg_wsdl_hab",
            )
            software_id_cfg = st.text_input(
                "SoftwareID",
                value=_cfg("dian_software_id", ""),
                key="cfg_software_id",
            )
            test_set_id_cfg = st.text_input(
                "TestSetId (habilitación)",
                value=_cfg("dian_test_set_id", ""),
                key="cfg_test_set_id",
            )
            clave_tec_cfg = st.text_input(
                "Clave Técnica (rango numeración)",
                value=_cfg("dian_clave_tecnica", ""),
                key="cfg_clave_tec",
                help="Se puede consultar automáticamente en la pestaña "
                     "🚀 Transmisión SOAP → GetNumberingRange.",
            )
        with col6:
            wsdl_prod_cfg = st.text_input(
                "WSDL Producción",
                value=_cfg("dian_wsdl_produccion", DIAN_WSDL_PRODUCCION_DEFAULT),
                key="cfg_wsdl_prod",
            )
            software_pin_cfg = st.text_input(
                "SoftwarePIN", type="password",
                value=_cfg("dian_software_pin", ""),
                key="cfg_software_pin",
            )
            cert_path_cfg = st.text_input(
                "Ruta certificado .p12/.pfx (en el servidor)",
                value=_cfg("dian_cert_path", ""),
                key="cfg_cert_path",
                placeholder="/ruta/segura/certificado.p12",
            )
            cert_pass_cfg = st.text_input(
                "Contraseña del certificado", type="password",
                value=_cfg("dian_cert_password", ""),
                key="cfg_cert_pass",
            )
        auto_transmitir_cfg = st.checkbox(
            "Transmitir automáticamente a la DIAN cada factura nueva "
            "(además de generarla y enviarla al cliente)",
            value=_cfg("dian_transmision_automatica", "no") == "si",
            key="cfg_auto_transmitir",
            help="No recomendado hasta validar la firma XAdES-EPES y hacer "
                 "pruebas exitosas en habilitación.",
        )
        if not ZEEP_OK:
            st.warning("⚠️ `zeep` no disponible en este proceso — no se puede "
                       "transmitir por SOAP.")
            with st.expander("🔎 Diagnóstico de instalación (zeep)"):
                st.code(_diagnostico_dependencia("zeep", ZEEP_IMPORT_ERROR), language="text")
        if not SIGNXML_OK:
            st.caption("ℹ️ `signxml` no disponible — el XML se transmitirá sin firmar.")
            with st.expander("🔎 Diagnóstico de instalación (signxml)"):
                st.code(_diagnostico_dependencia("signxml", SIGNXML_IMPORT_ERROR), language="text")

        st.divider()
        if st.button("💾 Guardar configuración DIAN", type="primary",
                     use_container_width=True, key="btn_cfg_dian"):
            amb_val  = "2" if "Pruebas" in ambiente_cfg else "1"
            reg_val  = "O-13" if "O-13" in regimen_e else "O-48"
            dv_final = dv_e.strip() or _calcular_digito_verificacion(nit_e)

            pares = [
                ("dian_nit_emisor",         _nit_limpio(nit_e)),
                ("dian_digito_verificador", dv_final),
                ("dian_razon_social",       razon),
                ("dian_nombre_comercial",   nombre_com_cfg),
                ("dian_regimen",            reg_val),
                ("dian_resolucion_num",     resolucion_n.strip()),
                ("dian_resolucion_fecha",   str(resolucion_f)),
                ("dian_prefijo_fe",         prefijo_fe_cfg.strip().upper()),
                ("dian_rango_desde",        str(rango_d)),
                ("dian_rango_hasta",        str(rango_h)),
                ("dian_ambiente",           amb_val),
                ("dian_email_emisor",       email_fe_cfg.strip()),
                ("dian_ciudad_emisor",      ciudad_e),
                ("dian_dept_emisor",        dept_e),
                ("dian_codigo_postal",      cp_e),
                ("dian_wsdl_habilitacion",  wsdl_hab_cfg.strip()),
                ("dian_wsdl_produccion",    wsdl_prod_cfg.strip()),
                ("dian_software_id",        software_id_cfg.strip()),
                ("dian_software_pin",       software_pin_cfg.strip()),
                ("dian_test_set_id",        test_set_id_cfg.strip()),
                ("dian_clave_tecnica",      clave_tec_cfg.strip()),
                ("dian_cert_path",          cert_path_cfg.strip()),
                ("dian_cert_password",      cert_pass_cfg.strip()),
                ("dian_transmision_automatica", "si" if auto_transmitir_cfg else "no"),
            ]
            for k, v in pares:
                fn_set(k, v)   # set_config → escribe en configuracion_pagos (PG)

            st.success(
                f"✅ Configuración DIAN guardada en PostgreSQL. "
                f"Prefijo: **{prefijo_fe_cfg.upper()}** · "
                f"Resolución: **{resolucion_n}** · "
                f"Ambiente: **{'Pruebas' if amb_val == '2' else 'Producción'}**"
            )
            st.rerun()

        # Vista previa del DV calculado
        if nit_e:
            dv_calc = _calcular_digito_verificacion(nit_e)
            st.caption(
                f"Dígito verificador calculado automáticamente para NIT "
                f"**{nit_e}**: **{dv_calc}**"
            )

    # ── TAB 5: Transmisión SOAP a la DIAN ─────────────────────────────────────
    with tab5:
        st.markdown("### 🚀 Transmisión SOAP — Validación Previa DIAN")
        st.caption(
            "Consume el Web Service SOAP oficial de la DIAN (Anexo Técnico "
            "Cap. 11/12: SendTestSetAsync, SendBillSync, GetStatus, "
            "GetNumberingRange) en vez de subir el XML manualmente al portal."
        )

        if not ZEEP_OK:
            st.error(
                "⚠️ `zeep` no está disponible en este proceso — no se puede "
                "usar esta pestaña. Mientras tanto, usa la pestaña "
                "🌐 Portal DIAN para el envío manual."
            )
            with st.expander("🔎 ¿Por qué, si ya lo instalé? — Diagnóstico"):
                st.code(_diagnostico_dependencia("zeep", ZEEP_IMPORT_ERROR), language="text")
                st.caption(
                    "Si estás en Streamlit Community Cloud: agrega `zeep` a "
                    "tu `requirements.txt` y reinicia la app desde "
                    "**Manage app → Reboot** — un `pip install zeep` hecho "
                    "por fuera de ese archivo no le llega al proceso desplegado."
                )
        else:
            cfg_soap = _soap_cfg()
            amb_actual = _cfg("dian_ambiente", "2")
            st.info(
                f"Ambiente activo: **{'🟢 Producción' if amb_actual == '1' else '🟡 Habilitación (pruebas)'}** "
                "· cambia el ambiente en ⚙️ Configuración DIAN."
            )
            if not cfg_soap["software_id"] or not cfg_soap["software_pin"]:
                st.warning(
                    "⚠️ Configura **SoftwareID** y **SoftwarePIN** en "
                    "⚙️ Configuración DIAN antes de transmitir (sección "
                    "'🚀 Transmisión SOAP a la DIAN')."
                )

            st.divider()
            st.markdown("#### 🔢 1. Consultar rango de numeración (Clave Técnica)")
            st.caption(
                "Necesaria para calcular el CUFE real (ver calcular_cufe_real). "
                "Solo hace falta consultarla una vez por rango autorizado."
            )
            if st.button("🔍 Consultar GetNumberingRange", key="btn_get_numbering"):
                res_num = consultar_rango_numeracion_dian(amb_actual)
                if res_num["ok"]:
                    st.success(res_num["mensaje"])
                    st.json(res_num["datos"])
                    st.caption(
                        "Si en la respuesta ves un campo con la Clave Técnica, "
                        "cópialo y pégalo en ⚙️ Configuración DIAN → "
                        "'Clave Técnica (rango numeración)', luego guarda."
                    )
                else:
                    st.error(res_num["mensaje"])

            st.divider()
            st.markdown("#### 📡 2. Transmitir una factura a la DIAN")
            rows_fe5  = _pg_read_fe()
            opciones5 = [r.get("Numero_FE", "") for r in rows_fe5 if r.get("Numero_FE")]
            if not opciones5:
                st.info("Aún no hay facturas electrónicas en PostgreSQL.")
            else:
                sel_fe5 = st.selectbox("Factura a transmitir", opciones5, key="fe_sel_soap")
                row_fe5 = next((r for r in rows_fe5 if r.get("Numero_FE") == sel_fe5), None)

                if row_fe5:
                    kwargs_gen5 = _datos_generacion_desde_row(row_fe5)
                    xml_gen5 = generar_xml_factura(**kwargs_gen5)

                    st.caption(
                        f"Estado DIAN actual: **{row_fe5.get('Estado_DIAN','pendiente')}** · "
                        f"CUFE: `{row_fe5.get('CUFE','')[:40]}…`"
                    )

                    if st.button("🚀 Transmitir esta factura a la DIAN",
                                 type="primary", use_container_width=True,
                                 key="btn_enviar_dian_soap"):
                        with st.spinner("Firmando, empaquetando y transmitiendo…"):
                            resultado = enviar_a_dian(sel_fe5, xml_gen5, amb_actual)
                        if resultado["ok"]:
                            st.success(resultado["mensaje"])
                            nuevo_estado = "enviada"
                            _pg_upsert_fe(sel_fe5, "Estado_DIAN", nuevo_estado)
                            if resultado.get("track_id"):
                                _pg_upsert_fe(sel_fe5, "Observaciones",
                                              f"TrackId SOAP: {resultado['track_id']}")
                            st.session_state["fe_last_track_id"] = resultado.get("track_id", "")
                        else:
                            st.error(resultado["mensaje"])
                        if resultado.get("datos") is not None:
                            with st.expander("Ver respuesta completa de la DIAN"):
                                st.json(resultado["datos"])
                        if not resultado.get("firmado"):
                            st.warning(
                                "⚠️ El XML se transmitió SIN una firma XAdES-EPES "
                                "válida — es muy probable que la DIAN lo rechace. "
                                "Configura el certificado digital en ⚙️ Configuración DIAN."
                            )

            st.divider()
            st.markdown("#### 🔍 3. Consultar estado de un envío asíncrono (habilitación)")
            track_id_input = st.text_input(
                "TrackId / ZipKey a consultar",
                value=st.session_state.get("fe_last_track_id", ""),
                key="fe_track_id_input",
            )
            if st.button("🔍 Consultar GetStatus", key="btn_get_status"):
                if not track_id_input:
                    st.warning("Escribe el TrackId/ZipKey devuelto por SendTestSetAsync.")
                else:
                    res_estado = consultar_estado_dian(track_id_input, amb_actual)
                    if res_estado["ok"]:
                        st.success(res_estado["mensaje"])
                        st.json(res_estado["datos"])
                    else:
                        st.error(res_estado["mensaje"])

if __name__ == '__main__':
    render_panel_fe()