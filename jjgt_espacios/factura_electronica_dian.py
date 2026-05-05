# ══════════════════════════════════════════════════════════════════════════════
#  SUITE SALITRE · Espacios de Descanso Personal — Terminal de Transportes
#  MÓDULO: factura_electronica_dian.py
#  Facturación Electrónica Colombia — Integración DIAN (VPFE / SET)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Funcionalidades:
#   1. Generación de XML UBL 2.1 (formato DIAN Colombia) por cada factura
#   2. Panel Streamlit con acceso directo al portal VPFE de la DIAN
#   3. Subida de archivos de la DIAN (.xlsx / .pdf / .zip) y almacenamiento
#      en Google Sheets + disco local
#   4. Comprobante contable automático al generar la factura electrónica
#   5. Botón de exportación del XML descargable
#   6. Registro de estado DIAN (enviada / aceptada / rechazada) por factura
#
#  Configuración necesaria en Configuracion_Pagos (Google Sheets):
#   dian_nit_emisor         → NIT sin dígito verificación  ej: 9020478713
#   dian_digito_verificador → Dígito verificador           ej: 7
#   dian_razon_social       → Razón social emisor          ej: JJGT S.A.S.
#   dian_nombre_comercial   → Nombre comercial             ej: Suite Salitre
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
#
#  Dependencias Python:
#   pip install lxml streamlit pandas openpyxl pytz
#   (lxml para XML; el resto ya está en pagos_convenios.py)
#
#  Integración en pagos_convenios.py:
#   import factura_electronica_dian as _fe_mod
#   _fe_mod.set_context(globals())
#
#   En crear_reserva_completa() — al final, junto al comprobante contable:
#       try:
#           _fe_mod.generar_fe_desde_reserva(voucher, calc, cliente, metodo)
#       except Exception: pass
#
#   En show_operador() — mod_map:
#       "⚡ Factura Electrónica": _fe_mod.render_panel_fe if FE_AVAILABLE else _op_dashboard,
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import os
import re
import uuid
import zipfile
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

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────────────
TZ_COL          = pytz.timezone("America/Bogota")
URL_DIAN_LOGIN  = "https://catalogo-vpfe.dian.gov.co/User/Login"
URL_DIAN_PORTAL = "https://catalogo-vpfe.dian.gov.co"
GS_HOJA_FE      = "Facturas_Electronicas"   # Hoja en Google Sheets

# Namespaces UBL 2.1 (DIAN Colombia)
_NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
}

# Columnas hoja Google Sheets
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
    "Estado_DIAN",          # pendiente / enviada / aceptada / rechazada
    "CUFE",                  # Código Único de Factura Electrónica
    "Archivo_DIAN",          # nombre del archivo subido desde el portal DIAN
    "Observaciones",
    "Operador",
    "Creado_En",
]

_ctx: dict = {}
_ctx_lock   = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXTO — inyectado desde pagos_convenios.py
# ══════════════════════════════════════════════════════════════════════════════

def set_context(globals_dict: dict) -> None:
    """
    Llama desde main() de pagos_convenios.py:
        import factura_electronica_dian as _fe_mod
        _fe_mod.set_context(globals())
    """
    with _ctx_lock:
        _ctx.update(globals_dict)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ahora() -> datetime:
    return datetime.now(TZ_COL)


def _cfg(clave: str, default: str = "") -> str:
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


def _gs_append_fe(fila: list) -> None:
    fn = _ctx.get("_gs_append")
    if fn:
        fn(None, GS_HOJA_FE, fila)
        inv = _ctx.get("_gs_invalidate_cache")
        if inv:
            inv(GS_HOJA_FE)


def _gs_read_fe() -> list:
    fn = _ctx.get("_gs_read_sheet")
    if fn:
        try:
            return fn(GS_HOJA_FE, force=True) or []
        except Exception:
            return []
    return []


def _gs_upsert_fe(numero_fe: str, campo: str, valor: str) -> None:
    """Actualiza un campo específico de una fila en Facturas_Electronicas."""
    fn_read   = _ctx.get("_gs_read_sheet")
    fn_upsert = _ctx.get("_gs_upsert")
    fn_inv    = _ctx.get("_gs_invalidate_cache")
    fn_val    = _ctx.get("_gs_val")
    if not (fn_read and fn_upsert and fn_val):
        return
    try:
        rows = fn_read(GS_HOJA_FE, force=True) or []
        for r in rows:
            if fn_val(r, "Numero_FE", "") == numero_fe:
                # Actualizar en el dict y re-insertar (patrón del proyecto)
                r_copy = dict(r)
                r_copy[campo] = valor
                _, sh = _ctx["get_active_client"]()
                if sh:
                    fn_upsert(sh, GS_HOJA_FE, "Numero_FE", numero_fe, list(r_copy.values()))
                    if fn_inv:
                        fn_inv(GS_HOJA_FE)
                break
    except Exception:
        pass


def _nit_limpio(nit: str) -> str:
    return re.sub(r"[^0-9]", "", nit or "")


def _calcular_digito_verificacion(nit: str) -> str:
    """Algoritmo oficial DIAN para calcular dígito de verificación del NIT."""
    nit = _nit_limpio(nit)
    if not nit:
        return "0"
    factores = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_rev = nit[::-1]
    total = sum(int(d) * factores[i] for i, d in enumerate(nit_rev) if i < len(factores))
    resto = total % 11
    return str(0 if resto in (0, 1) else 11 - resto)


def _cufe_simulado(numero_fe: str, nit: str, total: float, fecha: str) -> str:
    """
    CUFE simplificado para entornos de prueba.
    En producción real se genera con la cadena DIAN + SHA-384 + clave técnica.
    """
    import hashlib
    cadena = f"{numero_fe}{nit}{total:.2f}{fecha}"
    return hashlib.sha384(cadena.encode()).hexdigest()


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


def _numero_fe_siguiente() -> str:
    """Genera el número consecutivo de la factura electrónica."""
    prefijo = _cfg("dian_prefijo_fe", "SESP")
    n = 1
    try:
        fn_read = _ctx.get("_gs_read_sheet")
        fn_val  = _ctx.get("_gs_val")
        if fn_read and fn_val:
            rows = fn_read(GS_HOJA_FE, force=True) or []
            n = len(rows) + 1
    except Exception:
        pass
    return f"{prefijo}{n:04d}"


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
    """
    if not LXML_OK:
        # Fallback sin lxml: XML básico con string formatting
        return _generar_xml_fallback(
            numero_fe, fecha_emision, hora_emision,
            nit_receptor, nombre_receptor, email_receptor,
            tipo_doc_receptor, regimen_receptor, ciudad_receptor,
            descripcion_item, cantidad, precio_unitario,
            subtotal, iva_pct, iva_valor, total,
            metodo_pago, num_reserva, cufe
        )

    # Datos del emisor desde configuración
    nit_emisor      = _nit_limpio(_cfg("dian_nit_emisor", _nit_limpio("902.047.871-3")))
    dv_emisor       = _cfg("dian_digito_verificador", _calcular_digito_verificacion(nit_emisor))
    razon_emisor    = _cfg("dian_razon_social", "JJGT S.A.S.")
    nombre_com      = _cfg("dian_nombre_comercial", "Suite Salitre")
    regimen_emisor  = _cfg("dian_regimen", "O-13")
    resolucion_num  = _cfg("dian_resolucion_num", "0")
    resolucion_fecha= _cfg("dian_resolucion_fecha", fecha_emision)
    rango_desde     = _cfg("dian_rango_desde", "1")
    rango_hasta     = _cfg("dian_rango_hasta", "5000")
    prefijo_fe      = _cfg("dian_prefijo_fe", "SESP")
    ambiente        = _cfg("dian_ambiente", "2")          # 2=pruebas
    ciudad_emisor   = _cfg("dian_ciudad_emisor", "Bogotá D.C.")
    dept_emisor     = _cfg("dian_dept_emisor", "Cundinamarca")
    cod_postal      = _cfg("dian_codigo_postal", "110221")
    email_emisor    = _cfg("dian_email_emisor", "fe@suitesalitre.com.co")
    direccion       = _cfg("negocio_direccion", "Terminal de Transportes Módulo 3 Local 230")
    telefono        = _cfg("negocio_telefono", "3219714969")

    # Número correlativo (solo dígitos del consecutivo)
    num_consec = re.sub(r"[^0-9]", "", numero_fe.replace(prefijo_fe, "")) or "1"

    # Root Invoice
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
    cbc("CustomizationID",    "10")  # 10=Factura de venta
    cbc("ProfileID",          "DIAN 2.1")
    cbc("ProfileExecutionID", ambiente)
    cbc("ID",                 numero_fe)
    cbc("UUID",               cufe,
        schemeID=ambiente,
        schemeName="CUFE-SHA384")
    cbc("IssueDate",          fecha_emision)
    cbc("IssueTime",          f"{hora_emision}-05:00")
    cbc("DueDate",            fecha_emision)
    cbc("InvoiceTypeCode",    "01")    # 01=Factura de venta
    cbc("Note",               f"Reserva {num_reserva} · Suite Salitre")
    cbc("DocumentCurrencyCode","COP")
    cbc("LineCountNumeric",   "1")

    # ── Resolución DIAN ───────────────────────────────────────────────────────
    ord_ref = sub_cac(Invoice, "OrderReference")
    sub_cbc(ord_ref, "ID", f"Res.{resolucion_num}")

    billing = sub_cac(Invoice, "BillingReference")
    inv_doc = sub_cac(billing, "InvoiceDocumentReference")
    sub_cbc(inv_doc, "ID", numero_fe)
    sub_cbc(inv_doc, "UUID", cufe)
    sub_cbc(inv_doc, "IssueDate", fecha_emision)

    # ── Información de la resolución ──────────────────────────────────────────
    sts_ns = NSMAP["sts"]
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
    etree.SubElement(auth_range, f"{{{sts_ns}}}Prefix").text     = prefijo_fe
    etree.SubElement(auth_range, f"{{{sts_ns}}}From").text       = rango_desde
    etree.SubElement(auth_range, f"{{{sts_ns}}}To").text         = rango_hasta

    # ── Emisor (AccountingSupplierParty) ──────────────────────────────────────
    supp = sub_cac(Invoice, "AccountingSupplierParty")
    sub_cbc(supp, "AdditionalAccountID", "1")  # 1=Persona Jurídica
    supp_party = sub_cac(supp, "Party")

    # Identificación
    supp_name = sub_cac(supp_party, "PartyName")
    sub_cbc(supp_name, "Name", nombre_com)

    supp_phys = sub_cac(supp_party, "PhysicalLocation")
    supp_addr = sub_cac(supp_phys, "Address")
    sub_cbc(supp_addr, "ID",           "11001")  # DIVIPOLA Bogotá
    sub_cbc(supp_addr, "CityName",     ciudad_emisor)
    sub_cbc(supp_addr, "PostalZone",   cod_postal)
    sub_cbc(supp_addr, "CountrySubentity",     dept_emisor)
    sub_cbc(supp_addr, "CountrySubentityCode", "11")
    supp_cty = sub_cac(supp_addr, "Country")
    sub_cbc(supp_cty, "IdentificationCode", "CO")
    sub_cbc(supp_cty, "Name", "Colombia",
            languageID="es")
    supp_line = sub_cac(supp_addr, "AddressLine")
    sub_cbc(supp_line, "Line", direccion)

    supp_tax_id = sub_cac(supp_party, "PartyTaxScheme")
    sub_cbc(supp_tax_id, "RegistrationName", razon_emisor)
    sub_cbc(supp_tax_id, "CompanyID", nit_emisor,
            schemeAgencyID="195",
            schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
            schemeID=dv_emisor,
            schemeName="31")           # 31 = NIT
    tax_lvl = sub_cac(supp_tax_id, "TaxLevelCode")
    tax_lvl.text = regimen_emisor
    supp_scheme = sub_cac(supp_tax_id, "TaxScheme")
    sub_cbc(supp_scheme, "ID",   "01")
    sub_cbc(supp_scheme, "Name", "IVA")

    supp_legal = sub_cac(supp_party, "PartyLegalEntity")
    sub_cbc(supp_legal, "RegistrationName", razon_emisor)
    sub_cbc(supp_legal, "CompanyID", nit_emisor,
            schemeAgencyID="195",
            schemeName="31",
            schemeID=dv_emisor)

    supp_contact = sub_cac(supp_party, "Contact")
    sub_cbc(supp_contact, "Telephone",      telefono)
    sub_cbc(supp_contact, "ElectronicMail", email_emisor)

    # ── Receptor (AccountingCustomerParty) ────────────────────────────────────
    cust = sub_cac(Invoice, "AccountingCustomerParty")
    sub_cbc(cust, "AdditionalAccountID",
            "2" if tipo_doc_receptor == "31" else "1")
    cust_party = sub_cac(cust, "Party")

    cust_name = sub_cac(cust_party, "PartyName")
    sub_cbc(cust_name, "Name", nombre_receptor)

    cust_phys = sub_cac(cust_party, "PhysicalLocation")
    cust_addr = sub_cac(cust_phys, "Address")
    sub_cbc(cust_addr, "CityName", ciudad_receptor or "Bogotá D.C.")
    cust_cty = sub_cac(cust_addr, "Country")
    sub_cbc(cust_cty, "IdentificationCode", "CO")
    sub_cbc(cust_cty, "Name", "Colombia", languageID="es")

    cust_tax = sub_cac(cust_party, "PartyTaxScheme")
    sub_cbc(cust_tax, "RegistrationName", nombre_receptor)
    sub_cbc(cust_tax, "CompanyID", _nit_limpio(nit_receptor),
            schemeAgencyID="195",
            schemeAgencyName="CO, DIAN",
            schemeID="0",
            schemeName=tipo_doc_receptor)
    cust_tax_lvl = sub_cac(cust_tax, "TaxLevelCode")
    cust_tax_lvl.text = regimen_receptor
    cust_scheme = sub_cac(cust_tax, "TaxScheme")
    sub_cbc(cust_scheme, "ID",   "ZZ")
    sub_cbc(cust_scheme, "Name", "No aplica")

    cust_legal = sub_cac(cust_party, "PartyLegalEntity")
    sub_cbc(cust_legal, "RegistrationName", nombre_receptor)
    sub_cbc(cust_legal, "CompanyID", _nit_limpio(nit_receptor),
            schemeName=tipo_doc_receptor)

    cust_contact = sub_cac(cust_party, "Contact")
    sub_cbc(cust_contact, "ElectronicMail", email_receptor or "")

    # ── Método de pago ────────────────────────────────────────────────────────
    pay_means = sub_cac(Invoice, "PaymentMeans")
    MEDIOS = {
        "Efectivo":     ("10", "1"),
        "Nequi":        ("48", "1"),
        "Daviplata":    ("48", "1"),
        "Transferencia":("42", "1"),
        "PSE":          ("42", "1"),
        "Tarjeta":      ("48", "1"),
        "MercadoPago":  ("48", "1"),
        "Convenio":     ("1",  "2"),   # crédito
    }
    medio_code, due_code = MEDIOS.get(metodo_pago, ("10", "1"))
    sub_cbc(pay_means, "ID",             medio_code)
    sub_cbc(pay_means, "PaymentMeansCode", medio_code)
    sub_cbc(pay_means, "PaymentDueDate", fecha_emision)

    # ── Totales de impuestos ──────────────────────────────────────────────────
    if iva_valor > 0:
        tax_total = sub_cac(Invoice, "TaxTotal")
        sub_cbc(tax_total, "TaxAmount", f"{iva_valor:.2f}",
                currencyID="COP")
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
    sub_cbc(line, "ID",                "1")
    sub_cbc(line, "InvoicedQuantity",  f"{cantidad:.2f}", unitCode="HUR")
    sub_cbc(line, "LineExtensionAmount", f"{subtotal:.2f}", currencyID="COP")

    line_note = sub_cac(line, "Note")
    line_note.text = num_reserva

    line_item = sub_cac(line, "Item")
    sub_cbc(line_item, "Description", descripcion_item)

    line_price = sub_cac(line, "Price")
    sub_cbc(line_price, "PriceAmount", f"{precio_unitario:.2f}", currencyID="COP")
    sub_cbc(line_price, "BaseQuantity", f"{cantidad:.2f}", unitCode="HUR")

    if iva_valor > 0:
        line_tax = sub_cac(line, "TaxTotal")
        sub_cbc(line_tax, "TaxAmount", f"{iva_valor:.2f}", currencyID="COP")
        line_tax_sub = sub_cac(line_tax, "TaxSubtotal")
        sub_cbc(line_tax_sub, "TaxableAmount", f"{subtotal:.2f}", currencyID="COP")
        sub_cbc(line_tax_sub, "TaxAmount",     f"{iva_valor:.2f}", currencyID="COP")
        line_cat = sub_cac(line_tax_sub, "TaxCategory")
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
  <cbc:Note>Reserva {num_reserva} · Suite Salitre · Resolución {resolucion}</cbc:Note>
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
  <cbc:LineCountNumeric>1</cbc:LineCountNumeric>
  <!-- Emisor -->
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
  <!-- Receptor -->
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
  <!-- Totales -->
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="COP">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount  currencyID="COP">{subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount  currencyID="COP">{total:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount       currencyID="COP">{total:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <!-- Línea -->
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
# API PÚBLICA — llamada desde pagos_convenios.py
# ══════════════════════════════════════════════════════════════════════════════

def generar_fe_desde_reserva(
    voucher: dict,
    calc: dict,
    cliente: dict,
    metodo: str,
) -> str:
    """
    Hook principal. Genera la factura electrónica XML, la registra en
    Google Sheets y devuelve el número de FE generado.

    Llamar desde crear_reserva_completa() de pagos_convenios.py:
        try:
            import factura_electronica_dian as _fe_mod
            _fe_mod.generar_fe_desde_reserva(voucher, calc, cliente, metodo)
        except Exception:
            pass
    """
    now          = _ahora()
    fecha_str    = now.strftime("%Y-%m-%d")
    hora_str     = now.strftime("%H:%M:%S")
    numero_fe    = _numero_fe_siguiente()
    num_reserva  = voucher.get("numero_reserva", "")

    # Datos del receptor
    nit_rec      = cliente.get("numero_documento", cliente.get("nit_empresa", ""))
    tipo_doc     = _mapear_tipo_doc(cliente.get("tipo_doc", "CC"))
    regimen_rec  = "O-48" if cliente.get("regimen", "") == "Común" else "O-13"
    email_rec    = cliente.get("email", "")
    ciudad_rec   = cliente.get("ciudad", "Bogotá D.C.")
    nombre_rec   = cliente.get("nombre", "Consumidor Final")

    subtotal     = float(calc.get("subtotal", 0))
    iva_pct      = float(calc.get("iva_pct", 19.0))
    iva_valor    = float(calc.get("iva", 0))
    total        = float(calc.get("total", 0))
    horas        = float(calc.get("horas", 1))
    precio_hora  = float(calc.get("precio_hora", subtotal / max(horas, 1)))
    desc_item    = (
        f"Espacio de descanso {voucher.get('cubiculo', '')} · "
        f"WiFi · Baño · Carga · {horas}h"
    )

    cufe = _cufe_simulado(numero_fe, _nit_limpio(_cfg("dian_nit_emisor", "9020478713")),
                          total, fecha_str)

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

    # Guardar XML en disco (carpeta local facturas_xml/)
    _guardar_xml_local(numero_fe, xml_bytes)

    # Registrar en Google Sheets
    _gs_append_fe([
        fecha_str,
        numero_fe,
        num_reserva,
        nit_rec,
        nombre_rec,
        f"{subtotal:.2f}",
        f"{iva_valor:.2f}",
        f"{total:.2f}",
        metodo,
        "pendiente",    # Estado DIAN — se actualiza desde el panel
        cufe,
        "",             # Archivo DIAN (vacío al inicio)
        "",             # Observaciones
        _operador(),
        now.isoformat(),
    ])

    # Comprobante contable automático
    try:
        cont_mod = _ctx.get("__fe_cont_mod__")
        if cont_mod is None:
            try:
                import contabilidad as _cm
                _ctx["__fe_cont_mod__"] = _cm
                cont_mod = _cm
            except ImportError:
                pass
        if cont_mod:
            cont_mod.comp_ingreso_factura(
                tercero        = nombre_rec,
                valor_subtotal = subtotal,
                valor_iva      = iva_valor,
                num_factura    = numero_fe,
                descripcion    = f"FE {numero_fe} · Reserva {num_reserva}",
            )
    except Exception:
        pass

    return numero_fe


def _mapear_tipo_doc(tipo: str) -> str:
    """Convierte tipo de documento interno a código DIAN."""
    mapa = {
        "CC":  "13",
        "CE":  "22",
        "NIT": "31",
        "PP":  "41",
        "TI":  "12",
        "RC":  "11",
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


# ══════════════════════════════════════════════════════════════════════════════
# PANEL STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_fe() -> None:
    """
    Panel completo de Factura Electrónica DIAN.
    Agregar en mod_map de show_operador():
        "⚡ Factura Electrónica": _fe_mod.render_panel_fe if FE_AVAILABLE else _op_dashboard,
    """
    try:
        import streamlit as st
    except ImportError:
        return

    fn_val   = _ctx.get("_gs_val")
    fn_float = _ctx.get("_gs_float")
    fn_fmt   = _ctx.get("fmt_cop", lambda v: f"${v:,.0f}".replace(",", "."))
    fn_ahora = _ctx.get("ahora_col", _ahora)
    fn_read  = _ctx.get("_gs_read_sheet")

    # ── Encabezado ────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0d1f3c,#050b1a);
                border:1px solid rgba(0,212,255,0.3);border-radius:16px;
                padding:20px 24px;margin-bottom:20px">
      <h2 style="margin:0;color:#00d4ff;font-family:'Inconsolata',monospace">
        ⚡ Facturación Electrónica DIAN
      </h2>
      <p style="margin:4px 0 0;color:#94a3b8;font-size:14px">
        Colombia · UBL 2.1 · VPFE · Numeración autorizada
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Verificar config DIAN
    resolucion = _cfg("dian_resolucion_num", "")
    prefijo    = _cfg("dian_prefijo_fe", "")
    if not resolucion or not prefijo:
        st.warning(
            "⚠️ **Configura primero la resolución DIAN** en ⚙️ Configuración → "
            "pestaña *Factura Electrónica*. Necesitas: número de resolución, "
            "prefijo, rango y NIT emisor."
        )

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Facturas emitidas",
        "🌐 Portal DIAN",
        "📤 Subir archivo DIAN",
        "⚙️ Configuración DIAN",
    ])

    # ── TAB 1: Facturas emitidas ──────────────────────────────────────────────
    with tab1:
        st.markdown("### Facturas electrónicas generadas")
        rows_fe = _gs_read_fe()

        if not rows_fe:
            st.info("No hay facturas electrónicas registradas aún. Se generan automáticamente al crear una reserva.")
        else:
            if PANDAS_OK and fn_val and fn_float:
                data = []
                for r in rows_fe:
                    data.append({
                        "Fecha":       fn_val(r, "Fecha_Emision", ""),
                        "N° FE":       fn_val(r, "Numero_FE", ""),
                        "N° Reserva":  fn_val(r, "Numero_Reserva", ""),
                        "Receptor":    fn_val(r, "Nombre_Receptor", ""),
                        "Total COP":   fn_float(r, "Total_COP", 0),
                        "Método":      fn_val(r, "Metodo_Pago", ""),
                        "Estado DIAN": fn_val(r, "Estado_DIAN", "pendiente"),
                        "Archivo DIAN":fn_val(r, "Archivo_DIAN", "—"),
                    })
                import pandas as pd
                df = pd.DataFrame(data)

                # Color por estado DIAN
                def _color_estado(val):
                    c = {"aceptada": "#00ff88", "enviada": "#74b9ff",
                         "rechazada": "#ff4757", "pendiente": "#ffd32a"}.get(val, "#fff")
                    return f"color:{c};font-weight:700"

                st.dataframe(
                    df.style.applymap(_color_estado, subset=["Estado DIAN"]),
                    use_container_width=True, hide_index=True
                )

                total_fe = df["Total COP"].sum()
                col_t1, col_t2, col_t3 = st.columns(3)
                col_t1.metric("Total facturas", len(df))
                col_t2.metric("Total facturado", fn_fmt(total_fe))
                col_t3.metric(
                    "Aceptadas DIAN",
                    len(df[df["Estado DIAN"] == "aceptada"])
                )

        st.divider()
        st.markdown("#### Generar / descargar XML de una factura")

        rows_fe2 = _gs_read_fe()
        if rows_fe2 and fn_val:
            opciones = [fn_val(r, "Numero_FE", "") for r in rows_fe2 if fn_val(r, "Numero_FE", "")]
            if opciones:
                sel_fe = st.selectbox("Selecciona factura electrónica", opciones, key="fe_sel_num")
                row_sel = next((r for r in rows_fe2 if fn_val(r, "Numero_FE", "") == sel_fe), None)

                if row_sel:
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        nuevo_estado = st.selectbox(
                            "Actualizar estado DIAN",
                            ["pendiente", "enviada", "aceptada", "rechazada"],
                            index=["pendiente", "enviada", "aceptada", "rechazada"].index(
                                fn_val(row_sel, "Estado_DIAN", "pendiente")
                            ),
                            key="fe_estado_sel",
                        )
                        if st.button("💾 Guardar estado", key="btn_fe_estado"):
                            _gs_upsert_fe(sel_fe, "Estado_DIAN", nuevo_estado)
                            st.success(f"✅ Estado actualizado → **{nuevo_estado}**")
                            st.rerun()

                    with col_b:
                        obs_fe = st.text_input(
                            "Observación / N° radicado DIAN",
                            value=fn_val(row_sel, "Observaciones", ""),
                            key="fe_obs",
                        )
                        if st.button("💾 Guardar observación", key="btn_fe_obs"):
                            _gs_upsert_fe(sel_fe, "Observaciones", obs_fe)
                            st.success("✅ Observación guardada")

                    with col_c:
                        if st.button("📄 Regenerar y descargar XML", key="btn_fe_xml",
                                     type="primary", use_container_width=True):
                            # Regenerar XML desde los datos guardados
                            cufe_saved = fn_val(row_sel, "CUFE", "")
                            nit_rec    = fn_val(row_sel, "NIT_Receptor", "")
                            nombre_rec = fn_val(row_sel, "Nombre_Receptor", "")
                            subtot     = fn_float(row_sel, "Subtotal_COP", 0)
                            iva_v      = fn_float(row_sel, "IVA_COP", 0)
                            total_v    = fn_float(row_sel, "Total_COP", 0)
                            fecha_v    = fn_val(row_sel, "Fecha_Emision", _ahora().strftime("%Y-%m-%d"))
                            metodo_v   = fn_val(row_sel, "Metodo_Pago", "Efectivo")
                            num_res_v  = fn_val(row_sel, "Numero_Reserva", "")
                            horas_v    = 1.0
                            precio_v   = subtot / max(horas_v, 1)

                            xml_b = generar_xml_factura(
                                numero_fe        = sel_fe,
                                fecha_emision    = fecha_v,
                                hora_emision     = "00:00:00",
                                nit_receptor     = nit_rec,
                                nombre_receptor  = nombre_rec,
                                email_receptor   = "",
                                tipo_doc_receptor= "13",
                                regimen_receptor = "O-13",
                                ciudad_receptor  = "Bogotá D.C.",
                                descripcion_item = f"Espacio de descanso · Reserva {num_res_v}",
                                cantidad         = horas_v,
                                precio_unitario  = precio_v,
                                subtotal         = subtot,
                                iva_pct          = 19.0,
                                iva_valor        = iva_v,
                                total            = total_v,
                                metodo_pago      = metodo_v,
                                num_reserva      = num_res_v,
                                cufe             = cufe_saved,
                            )
                            st.download_button(
                                label     = f"⬇️ Descargar {sel_fe}.xml",
                                data      = xml_b,
                                file_name = f"{sel_fe}.xml",
                                mime      = "application/xml",
                                key       = "dl_xml_btn",
                            )

    # ── TAB 2: Portal DIAN ───────────────────────────────────────────────────
    with tab2:
        st.markdown("### 🌐 Portal DIAN — Facturando Electrónicamente")

        # Instrucciones visuales
        st.markdown(f"""
        <div style="background:#0d1f3c;border:1px solid rgba(0,212,255,0.3);
                    border-radius:12px;padding:20px;margin-bottom:16px">
          <h4 style="color:#00d4ff;margin:0 0 12px">Pasos para enviar a la DIAN:</h4>
          <ol style="color:#e2e8f0;line-height:2;margin:0;padding-left:20px">
            <li>Haz clic en <b style="color:#ffd32a">Abrir portal DIAN</b> → inicia sesión con tu usuario y contraseña</li>
            <li>En el portal ve a <b>Facturar → Cargar XML</b></li>
            <li>Descarga el XML desde la pestaña <b>📋 Facturas emitidas</b></li>
            <li>Carga el XML en el portal DIAN y obtén el número de radicado</li>
            <li>Regresa aquí y actualiza el estado a <b style="color:#00ff88">aceptada</b></li>
            <li>Sube el acuse de recibo de la DIAN en la pestaña <b>📤 Subir archivo DIAN</b></li>
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

        # Información de la resolución configurada
        st.markdown("#### 📋 Resolución vigente configurada")
        res_num   = _cfg("dian_resolucion_num", "—")
        res_fecha = _cfg("dian_resolucion_fecha", "—")
        pref_fe   = _cfg("dian_prefijo_fe", "—")
        rng_d     = _cfg("dian_rango_desde", "—")
        rng_h     = _cfg("dian_rango_hasta", "—")
        amb       = "🟢 Producción" if _cfg("dian_ambiente", "2") == "1" else "🟡 Pruebas"

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("N° Resolución", res_num)
        col_r2.metric("Prefijo FE",    pref_fe)
        col_r3.metric("Ambiente",      amb)
        col_r4, col_r5, col_r6 = st.columns(3)
        col_r4.metric("Fecha resolución", res_fecha)
        col_r5.metric("Rango desde", rng_d)
        col_r6.metric("Rango hasta", rng_h)

        if res_num == "—":
            st.error("❌ No has configurado la resolución DIAN. Ve a ⚙️ Configuración → Factura Electrónica.")

    # ── TAB 3: Subir archivo DIAN ─────────────────────────────────────────────
    with tab3:
        st.markdown("### 📤 Subir acuse / respuesta de la DIAN")
        st.caption(
            "Sube el archivo que te entrega el portal DIAN tras el envío de la factura: "
            "puede ser el acuse de recibo (.pdf), el reporte de validación (.xlsx) o el ZIP del proceso."
        )

        rows_fe3 = _gs_read_fe()
        opciones3 = []
        if rows_fe3 and fn_val:
            opciones3 = [fn_val(r, "Numero_FE", "") for r in rows_fe3 if fn_val(r, "Numero_FE", "")]

        if not opciones3:
            st.info("Aún no hay facturas electrónicas. Se generarán automáticamente al crear reservas.")
        else:
            sel_up = st.selectbox(
                "¿A qué factura electrónica corresponde este archivo?",
                opciones3,
                key="fe_upload_sel",
            )

            archivo = st.file_uploader(
                "Selecciona el archivo de respuesta de la DIAN",
                type=["xlsx", "pdf", "zip", "xml"],
                key="fe_file_up",
                help="Formatos aceptados: .xlsx, .pdf, .zip, .xml"
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

                if st.button("💾 Guardar archivo y actualizar estado", key="btn_fe_guardar_arch",
                             type="primary", use_container_width=True):
                    # Guardar archivo en disco local
                    try:
                        folder_dian = "archivos_dian"
                        os.makedirs(folder_dian, exist_ok=True)
                        # Nombre único: FE + nombre original
                        nombre_guardado = f"{sel_up}_{archivo.name}"
                        ruta_local = os.path.join(folder_dian, nombre_guardado)
                        with open(ruta_local, "wb") as f:
                            f.write(archivo.getbuffer())
                        guardado_ok = True
                    except Exception as e:
                        guardado_ok = False
                        nombre_guardado = archivo.name
                        st.warning(f"No se pudo guardar en disco: {e}. Se registra solo en Sheets.")

                    # Actualizar Google Sheets
                    _gs_upsert_fe(sel_up, "Estado_DIAN",   estado_up)
                    _gs_upsert_fe(sel_up, "Archivo_DIAN",  nombre_guardado)
                    _gs_upsert_fe(sel_up, "Observaciones", obs_up)

                    st.success(
                        f"✅ Archivo **{nombre_guardado}** vinculado a {sel_up}. "
                        f"Estado actualizado a **{estado_up}**."
                    )

                    # Botón de re-descarga inmediata
                    st.download_button(
                        label     = f"⬇️ Descargar {archivo.name}",
                        data      = archivo.getbuffer(),
                        file_name = archivo.name,
                        mime      = archivo.type,
                        key       = "dl_arch_dian",
                    )

    # ── TAB 4: Configuración DIAN ─────────────────────────────────────────────
    with tab4:
        st.markdown("### ⚙️ Configuración Factura Electrónica DIAN")
        st.caption(
            "Ingresa los datos de la resolución que la DIAN te asignó. "
            "Se guardan en Google Sheets (Configuracion_Pagos) y se usan en todos los XML generados."
        )

        fn_set = _ctx.get("set_config")
        if not fn_set:
            st.error("set_config no disponible. Verifica set_context(globals()).")
            return

        col1, col2 = st.columns(2)
        with col1:
            nit_e  = st.text_input("NIT emisor (sin dígito verificador)",
                                   value=_cfg("dian_nit_emisor",
                                              _nit_limpio("902.047.871-3")),
                                   key="cfg_nit_e")
            dv_e   = st.text_input("Dígito verificador NIT",
                                   value=_cfg("dian_digito_verificador",
                                              _calcular_digito_verificacion(
                                                  _cfg("dian_nit_emisor","9020478713"))),
                                   key="cfg_dv_e",
                                   max_chars=1)
            razon  = st.text_input("Razón social emisor",
                                   value=_cfg("dian_razon_social", "JJGT S.A.S."),
                                   key="cfg_razon")
            nombre_com_cfg = st.text_input("Nombre comercial",
                                           value=_cfg("dian_nombre_comercial", "Suite Salitre"),
                                           key="cfg_nom_com")
            regimen_e = st.selectbox("Régimen emisor",
                                     ["O-13 (Simplificado)", "O-48 (Responsable de IVA)"],
                                     index=0 if _cfg("dian_regimen","O-13").startswith("O-13") else 1,
                                     key="cfg_regimen")

        with col2:
            resolucion_n = st.text_input("Número de resolución DIAN",
                                         value=_cfg("dian_resolucion_num", ""),
                                         key="cfg_res_num",
                                         placeholder="Ej: 18764065649999")
            resolucion_f = st.date_input("Fecha de resolución",
                                         value=_safe_date(_cfg("dian_resolucion_fecha", "")),
                                         key="cfg_res_fecha")
            prefijo_fe_cfg = st.text_input("Prefijo factura electrónica",
                                           value=_cfg("dian_prefijo_fe", "SESP"),
                                           key="cfg_prefijo",
                                           max_chars=4)
            rango_d = st.number_input("Rango desde (inicio numeración)",
                                      value=_safe_int(_cfg("dian_rango_desde", "1"), 1),
                                      min_value=1, key="cfg_rng_d")
            rango_h = st.number_input("Rango hasta (fin numeración)",
                                      value=_safe_int(_cfg("dian_rango_hasta", "5000"), 5000),
                                      min_value=1, key="cfg_rng_h")

        col3, col4 = st.columns(2)
        with col3:
            ambiente_cfg = st.selectbox("Ambiente DIAN",
                                        ["2 — Pruebas (Habilitación)", "1 — Producción"],
                                        index=0 if _cfg("dian_ambiente","2") == "2" else 1,
                                        key="cfg_amb")
            email_fe_cfg = st.text_input("Email notificaciones FE",
                                         value=_cfg("dian_email_emisor",""),
                                         key="cfg_email_fe",
                                         placeholder="fe@jjgt.com.co")
        with col4:
            ciudad_e = st.text_input("Ciudad emisor",
                                     value=_cfg("dian_ciudad_emisor","Bogotá D.C."),
                                     key="cfg_ciudad_e")
            dept_e   = st.text_input("Departamento emisor",
                                     value=_cfg("dian_dept_emisor","Cundinamarca"),
                                     key="cfg_dept_e")
            cp_e     = st.text_input("Código postal",
                                     value=_cfg("dian_codigo_postal","110221"),
                                     key="cfg_cp_e",
                                     max_chars=6)

        st.divider()
        if st.button("💾 Guardar configuración DIAN", type="primary",
                     use_container_width=True, key="btn_cfg_dian"):
            amb_val = "2" if "Pruebas" in ambiente_cfg else "1"
            reg_val = "O-13" if "O-13" in regimen_e else "O-48"
            # Calcular DV automáticamente si está vacío
            dv_final = dv_e.strip() or _calcular_digito_verificacion(nit_e)

            pares = [
                ("dian_nit_emisor",          _nit_limpio(nit_e)),
                ("dian_digito_verificador",  dv_final),
                ("dian_razon_social",        razon),
                ("dian_nombre_comercial",    nombre_com_cfg),
                ("dian_regimen",             reg_val),
                ("dian_resolucion_num",      resolucion_n.strip()),
                ("dian_resolucion_fecha",    str(resolucion_f)),
                ("dian_prefijo_fe",          prefijo_fe_cfg.strip().upper()),
                ("dian_rango_desde",         str(rango_d)),
                ("dian_rango_hasta",         str(rango_h)),
                ("dian_ambiente",            amb_val),
                ("dian_email_emisor",        email_fe_cfg.strip()),
                ("dian_ciudad_emisor",       ciudad_e),
                ("dian_dept_emisor",         dept_e),
                ("dian_codigo_postal",       cp_e),
            ]
            for k, v in pares:
                fn_set(k, v)

            st.success(
                f"✅ Configuración DIAN guardada. "
                f"Prefijo: **{prefijo_fe_cfg.upper()}** · "
                f"Resolución: **{resolucion_n}** · "
                f"Ambiente: **{'Pruebas' if amb_val=='2' else 'Producción'}**"
            )

            # Sincronizar con Sheets
            try:
                fn_sync = _ctx.get("gs_sync_configuracion_pagos")
                fn_get  = _ctx.get("get_active_client")
                if fn_sync and fn_get:
                    _, sh_s = fn_get()
                    if sh_s:
                        fn_sync(sh_s)
            except Exception:
                pass

            st.rerun()

        # Vista previa del DV calculado
        if nit_e:
            dv_calc = _calcular_digito_verificacion(nit_e)
            st.caption(f"Dígito verificador calculado automáticamente para NIT **{nit_e}**: **{dv_calc}**")
