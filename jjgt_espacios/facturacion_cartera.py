# ══════════════════════════════════════════════════════════════════════════════
#  SUITE SALITRE · Espacios de Descanso Personal — Terminal de Transportes
#  MÓDULO: FACTURACIÓN MENSUAL + CONTROL DE CARTERA · Convenios Empresariales
# ══════════════════════════════════════════════════════════════════════════════
#
#  Este módulo se importa desde pagos_convenios.py:
#
#      from facturacion_cartera import (
#          generar_facturacion_mensual,
#          calcular_cartera,
#          actualizar_estado_reserva,
#          show_facturacion_cartera,
#      )
#
#  Requiere set_context(globals()) en main() de pagos_convenios.py antes de
#  que el operador acceda al módulo.
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import re as _re
from datetime import datetime, timedelta
import streamlit as st

# ── Configuración de envío de email ──────────────────────────────────────────
EMAIL_SENDER = st.secrets['emails']['smtp_user']   # 🔧 Reemplazar con el correo remitente
EMAIL_PASS   = st.secrets['emails']['smtp_password']    # 🔧 Reemplazar con la contraseña de app Gmail



# ══════════════════════════════════════════════════════════════════════════════
# ENVÍO DE FACTURA POR EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def enviar_factura_email(destinatario: str, asunto: str, cuerpo: str,
                         pdf_bytes: bytes, nombre_pdf: str, email_from: str, nombre_from: str) -> bool:
    """
    Envía una factura PDF por email usando yagmail (Gmail).
    Requiere: pip install yagmail
    Configura EMAIL_SENDER y EMAIL_PASS al inicio del módulo.

    Parámetros:
        destinatario — dirección de correo del cliente.
        asunto       — asunto del mensaje.
        cuerpo       — cuerpo en texto plano o HTML.
        pdf_bytes    — contenido del PDF generado (bytes).
        nombre_pdf   — nombre del archivo adjunto (ej. "FAC-EMP01-202504.pdf").
    Retorna True si el envío fue exitoso, False en caso contrario.
    """
    import tempfile, os
    tmp_path = None
    try:
        # yagmail requiere una ruta de archivo real, no bytes en memoria.
        # Se escribe el PDF en un archivo temporal y se elimina tras el envio.
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", prefix="fac_"
        ) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        import yagmail
        # Se autentica con EMAIL_SENDER/EMAIL_PASS pero el campo "De" visible
        # en el correo mostrará email_from / nombre_from.
        yag = yagmail.SMTP(
            user=EMAIL_SENDER,
            password=EMAIL_PASS,
            smtp_starttls=True,
            smtp_ssl=False,
        )
        # Construir el encabezado From visible para el destinatario
        remitente = f"{nombre_from} <{email_from}>" if nombre_from else email_from

        yag.send(
            to=destinatario,
            subject=asunto,
            contents=cuerpo,
            attachments=tmp_path,   # ruta real en disco
            headers={"From": remitente},
        )
        return True
    except Exception as e:
        print("Error email:", e)
        return False
    finally:
        # Limpieza garantizada del archivo temporal
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ── Contexto compartido ───────────────────────────────────────────────────────
_ctx: dict = {}

def set_context(ctx: dict):
    global _ctx
    _ctx = ctx

def _g(name):
    val = _ctx.get(name)
    if val is None:
        raise RuntimeError(
            f"facturacion_cartera: símbolo '{name}' no en contexto. "
            "¿Se llamó set_context() en main()?"
        )
    return val


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════

def _fecha_mes_anio(valor) -> tuple:
    """
    Extrae (mes, año) sin convertir zona horaria.
    Soporta: datetime, pd.Timestamp, ISO-8601 con offset, YYYY-MM-DD, DD/MM/YYYY.
    """
    if valor is None or valor == "":
        return None, None
    if isinstance(valor, datetime):
        return valor.month, valor.year
    if isinstance(valor, pd.Timestamp):
        return valor.month, valor.year
    texto = str(valor).strip()
    if not texto:
        return None, None
    # Intento 1: YYYY-MM-DD al inicio (ISO 8601 con/sin offset)
    m = _re.match(r'(\d{4})-(\d{2})-(\d{2})', texto)
    if m:
        return int(m.group(2)), int(m.group(1))
    # Intento 2: DD/MM/YYYY
    m = _re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', texto)
    if m:
        return int(m.group(2)), int(m.group(3))
    # Fallback pandas — formatos explícitos para evitar UserWarning
    for _fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            ts = pd.to_datetime(texto, format=_fmt, errors="coerce")
            if not pd.isna(ts):
                return ts.month, ts.year
        except Exception:
            pass
    return None, None


def _fld(row: dict, *keys, default=""):
    """Busca la primera clave que exista en el dict, ignorando mayúsculas."""
    row_lower = {k.lower(): v for k, v in row.items()}
    for k in keys:
        v = row_lower.get(k.lower())
        if v is not None:
            return v
    return default


def actualizar_estado_reserva(sh, numero_reserva: str, nuevo_estado: str) -> bool:
    """Actualiza Estado_Pago de una reserva en la hoja Reservas de jjgt_convenios."""
    try:
        _gs_get_or_create_ws = _g("_gs_get_or_create_ws")
        _gs_with_retry       = _g("_gs_with_retry")

        def _do():
            ws   = _gs_get_or_create_ws(sh, "Reservas")
            vals = ws.get_all_values()
            if not vals or len(vals) < 2:
                return False
            hdr = vals[0]
            if "Numero_Reserva" not in hdr or "Estado_Pago" not in hdr:
                return False
            ci_nr = hdr.index("Numero_Reserva")
            ci_ep = hdr.index("Estado_Pago")
            for i, row in enumerate(vals[1:], start=2):
                if len(row) > ci_nr and str(row[ci_nr]).strip() == str(numero_reserva).strip():
                    ws.update_cell(i, ci_ep + 1, nuevo_estado)
                    return True
            return False

        return bool(_gs_with_retry(_do, operacion=f"actualizar estado reserva {numero_reserva}"))
    except Exception as e:
        st.warning(f"⚠️ Error actualizando reserva {numero_reserva}: {e}")
        return False


def _leer_facturas_convenio() -> list:
    """
    Lee de jjgt_convenios solo las facturas generadas por Facturación Mensual
    (Num_Factura con prefijo 'FAC-'). Las facturas individuales de reservas
    tienen otro formato y no se muestran en Ver & Imprimir.
    """
    try:
        get_active_client_convenios = _g("get_active_client_convenios")
        _gs_get_or_create_ws        = _g("_gs_get_or_create_ws")
        _, sh = get_active_client_convenios()
        if not sh:
            return []
        ws    = _gs_get_or_create_ws(sh, "Facturas")
        todas = ws.get_all_records()
        return [
            f for f in todas
            if str(_fld(f, "Num_Factura", "numero", default=""))
               .strip().upper().startswith("FAC-")
        ]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# PDF DE FACTURA CONSOLIDADA
# ══════════════════════════════════════════════════════════════════════════════

def generar_factura_pdf(factura: dict, reservas_detalle: list = None) -> bytes:
    """
    Genera un PDF A4 de una factura consolidada de convenio.
    `factura`  — dict con los campos de la hoja Facturas de jjgt_convenios.
    `reservas_detalle` — lista opcional de dicts de reservas incluidas.
    Retorna bytes del PDF, o b"" si ReportLab no está disponible.
    """
    REPORTLAB_AVAILABLE = _g("REPORTLAB_AVAILABLE")
    if not REPORTLAB_AVAILABLE:
        return b""

    # Imports de ReportLab (disponibles si REPORTLAB_AVAILABLE=True)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    import io, base64 as _b64

    # Constantes del negocio desde contexto
    NEGOCIO   = _g("NEGOCIO")
    TAGLINE   = _g("TAGLINE")
    DIRECCION = _g("DIRECCION")
    TELEFONO  = _g("TELEFONO")
    NIT       = _g("NIT")
    EMAIL     = _g("EMAIL")
    fmt_cop   = _g("fmt_cop")
    ahora_col = _g("ahora_col")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm,  bottomMargin=18*mm,
    )

    # ── Paleta de colores ────────────────────────────────────────────────────
    AZUL_OSCURO  = colors.HexColor("#0A1628")
    AZUL_MEDIO   = colors.HexColor("#0E7490")
    AZUL_CLARO   = colors.HexColor("#E0F7FA")
    GRIS_TEXTO   = colors.HexColor("#64748B")
    GRIS_CLARO   = colors.HexColor("#F8FAFC")
    BORDE        = colors.HexColor("#CBD5E1")
    ROJO         = colors.HexColor("#EF4444")
    VERDE        = colors.HexColor("#22C55E")

    # ── Estilos ──────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    titulo  = ParagraphStyle("T",  fontSize=20, fontName="Helvetica-Bold",
                              textColor=AZUL_OSCURO, alignment=TA_CENTER, spaceAfter=2)
    subtit  = ParagraphStyle("S",  fontSize=9,  fontName="Helvetica",
                              textColor=GRIS_TEXTO,  alignment=TA_CENTER, spaceAfter=1)
    sec     = ParagraphStyle("Se", fontSize=11, fontName="Helvetica-Bold",
                              textColor=AZUL_MEDIO,  spaceBefore=8, spaceAfter=3)
    normal  = ParagraphStyle("N",  fontSize=9,  fontName="Helvetica",
                              textColor=AZUL_OSCURO, spaceAfter=2)
    normal_r= ParagraphStyle("NR", fontSize=9,  fontName="Helvetica",
                              textColor=AZUL_OSCURO, alignment=TA_RIGHT)
    bold    = ParagraphStyle("B",  fontSize=9,  fontName="Helvetica-Bold",
                              textColor=AZUL_OSCURO)
    pie     = ParagraphStyle("P",  fontSize=7,  fontName="Helvetica",
                              textColor=GRIS_TEXTO,  alignment=TA_CENTER, spaceBefore=4)

    def hr(color=BORDE, t=0.5):
        return HRFlowable(width="100%", thickness=t, color=color,
                          spaceAfter=4, spaceBefore=2)
    def sp(h=4): return Spacer(1, h*mm)
    def p(txt, st=normal): return Paragraph(txt, st)

    # ── Extracción de campos ─────────────────────────────────────────────────
    def fv(k, *alt, d=""):
        return str(_fld(factura, k, *alt, default=d)).strip()

    num_fac      = fv("Num_Factura",        "numero")
    tipo_fac     = fv("Tipo",               "tipo",          d="Factura Consolidada Convenio")
    empresa      = fv("Nombre_Empresa",     "Cliente_Nombre","cliente_nombre", d="—")
    nit_emp      = fv("Nit_Empresa",        "nit_empresa",   d="")
    cli_email    = fv("Cliente_Email",      "cliente_email", d="")
    descripcion  = fv("Descripcion",        "descripcion",   d="")
    fecha_emis   = fv("Fecha_Emision",      "fecha_emision", d="")[:10]
    fecha_venc   = fv("Fecha_Vencimiento",  "fecha_vencimiento", d="")[:10]
    subtotal_v   = float(fv("Subtotal",  "subtotal",  d="0") or 0)
    descuento_v  = float(fv("Descuento", "descuento", d="0") or 0)
    iva_v        = float(fv("IVA",       "iva",       d="0") or 0)
    total_v      = float(fv("Total_COP", "total",     d="0") or 0)
    estado       = fv("Estado", "estado", d="pendiente")
    id_emp       = fv("Id_Empresa", "id_empresa", d="")
    metodo       = fv("Metodo_Pago", "metodo_pago", d="Convenio")
    ahora_str    = ahora_col().strftime("%d/%m/%Y %H:%M")

    # ── Completar datos de empresa desde hoja Clientes si faltan ─────────────
    # La hoja Clientes de jjgt_convenios tiene columnas:
    #   Nombre, Email, Nit_Empresa, Id_Empresa, Nombre_Empresa
    # Se busca por Id_Empresa (más preciso) o Nombre_Empresa / Cliente_Nombre.
    if not nit_emp or not cli_email or not id_emp:
        try:
            _gac = _g("get_active_client_convenios")
            _gwc = _g("_gs_get_or_create_ws")
            _, _sh_c = _gac()
            if _sh_c:
                _ws_c    = _gwc(_sh_c, "Clientes")
                _cli_all = _ws_c.get_all_records()
                # Claves de búsqueda desde la factura
                _id_bus  = id_emp.lower()
                _nom_bus = empresa.lower()
                for _cr in _cli_all:
                    # Id_Empresa e Id_empresa son posibles nombres de columna
                    _id_c  = str(_fld(_cr, "Id_Empresa",  "id_empresa",  default="")).strip().lower()
                    # Nombre_Empresa o Nombre son posibles columnas en Clientes
                    _nom_c = str(_fld(_cr, "Nombre_Empresa", "nombre_empresa",
                                      "Nombre", "nombre", default="")).strip().lower()
                    if (_id_bus  and _id_c  and _id_bus  == _id_c) or                        (_nom_bus and _nom_c and _nom_bus == _nom_c):
                        # NIT: columna Nit_Empresa en Clientes
                        if not nit_emp:
                            nit_emp = str(_fld(_cr,
                                "Nit_Empresa", "nit_empresa", "NIT", "nit",
                                default="")).strip()
                        # Email: columna Email en Clientes (no Cliente_Email)
                        if not cli_email:
                            cli_email = str(_fld(_cr,
                                "Email", "email",
                                "Cliente_Email", "cliente_email",
                                default="")).strip()
                        # Id_Empresa si estaba vacío
                        if not id_emp:
                            id_emp = str(_fld(_cr,
                                "Id_Empresa", "id_empresa",
                                default="")).strip()
                        # Nombre_Empresa como nombre de empresa si empresa era "—"
                        if empresa in ("—", ""):
                            empresa = str(_fld(_cr,
                                "Nombre_Empresa", "nombre_empresa",
                                "Nombre", "nombre", default=empresa)).strip()
                        break
        except Exception:
            pass  # No bloquear generación del PDF si falla la consulta

    estado_color = ROJO if estado.lower() in ("pendiente", "vencida") else VERDE

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # ENCABEZADO
    # ══════════════════════════════════════════════════════════════════════════
    ancho = doc.width

    # Tabla encabezado: logo/negocio izq | datos factura der
    # ── Logo en el PDF de factura ────────────────────────────────────────────
    encab_izq = []
    try:
        _logo_b64_fac = _g("_LOGO_B64")
        if _logo_b64_fac:
            from reportlab.platypus import Image as RLImage
            _logo_buf_fac = io.BytesIO(_b64.b64decode(_logo_b64_fac))
            _logo_img_fac = RLImage(_logo_buf_fac, width=30*mm, height=40*mm)
            _logo_img_fac.hAlign = "LEFT"
            encab_izq.append(_logo_img_fac)
            encab_izq.append(Spacer(1, 3))
    except Exception:
        pass
    encab_izq += [
        p(f"<b>{NEGOCIO}</b>", bold),
        p(TAGLINE,    subtit),
        p(DIRECCION,  subtit),
        p(f"Tel: {TELEFONO}  ·  NIT: {NIT}", subtit),
        p(EMAIL,      subtit),
    ]
    estado_txt = estado.upper()
    encab_der = [
        p(f"<b>FACTURA DE CONVENIO</b>", bold),
        p(f"N° <b>{num_fac}</b>",        bold),
        p(f"Tipo: {tipo_fac}",           normal),
        p(f"Emisión:    {fecha_emis}",   normal),
        p(f"Vence:      {fecha_venc}",   normal),
        p(f"Generado:   {ahora_str}",    normal),
    ]

    tbl_enc = Table(
        [[encab_izq, encab_der]],
        colWidths=[ancho * 0.55, ancho * 0.45],
    )
    tbl_enc.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING",(0,0), (-1,-1), 0),
    ]))
    story += [tbl_enc, sp(2), hr(AZUL_MEDIO, 1.5), sp(3)]

    # Badge de estado
    est_bg = ROJO if estado.lower() == "pendiente" else AZUL_MEDIO
    badge = Table([[estado_txt]], colWidths=[ancho])
    badge.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), est_bg),
        ("TEXTCOLOR",     (0,0), (-1,-1), colors.white),
        ("FONTNAME",      (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 11),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [badge, sp(4)]

    # ══════════════════════════════════════════════════════════════════════════
    # DATOS DE LA EMPRESA (CLIENTE)
    # ══════════════════════════════════════════════════════════════════════════
    story.append(p("FACTURAR A:", sec))
    story.append(hr())
    datos_cli = [
        [p("<b>Empresa:</b>",   bold), p(empresa,   normal)],
        [p("<b>NIT:</b>",       bold), p(nit_emp or "—",  normal)],
        [p("<b>Email:</b>",     bold), p(cli_email or "—", normal)],
        [p("<b>ID Empresa:</b>",bold), p(id_emp or "—",   normal)],
        [p("<b>Método:</b>",    bold), p(metodo,    normal)],
    ]
    tbl_cli = Table(datos_cli, colWidths=[ancho * 0.25, ancho * 0.75])
    tbl_cli.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), AZUL_CLARO),
        ("GRID",         (0,0), (-1,-1), 0.3, BORDE),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    story += [tbl_cli, sp(4)]

    # ══════════════════════════════════════════════════════════════════════════
    # DESCRIPCIÓN / CONCEPTO
    # ══════════════════════════════════════════════════════════════════════════
    if descripcion:
        story.append(p("CONCEPTO:", sec))
        story.append(hr())
        story.append(p(descripcion, normal))
        story.append(sp(3))

    # ══════════════════════════════════════════════════════════════════════════
    # DETALLE DE RESERVAS (si se pasa la lista)
    # ══════════════════════════════════════════════════════════════════════════
    if reservas_detalle:
        story.append(p("RESERVAS INCLUIDAS:", sec))
        story.append(hr())
        hdr_res = ["N° Reserva", "Cubículo", "Fecha", "Horas", "Cliente", "Total COP"]
        col_w   = [ancho*0.18, ancho*0.10, ancho*0.14, ancho*0.08, ancho*0.30, ancho*0.20]
        tbl_data = [hdr_res]
        for r in reservas_detalle:
            num_r  = str(_fld(r, "Numero_Reserva",  "numero_reserva",  default="")).strip()
            cub_r  = str(_fld(r, "Cubiculo_Num",    "cubiculo_num",    default="")).strip()
            fch_r  = str(_fld(r, "Creado_En",       "creado_en",       default=""))[:10]
            hrs_r  = str(_fld(r, "Horas_Contratadas","horas",          default="")).strip()
            cli_r  = str(_fld(r, "Cliente_Nombre",   "cliente_nombre", default="")).strip()
            tot_r  = float(_fld(r, "Total_COP", "total", default=0) or 0)
            tbl_data.append([num_r, cub_r, fch_r, hrs_r, cli_r, fmt_cop(tot_r)])

        tbl_res = Table(tbl_data, colWidths=col_w)
        tbl_res.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), AZUL_MEDIO),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, GRIS_CLARO]),
            ("GRID",          (0,0), (-1,-1), 0.3, BORDE),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("RIGHTPADDING",  (0,0), (-1,-1), 5),
            ("ALIGN",         (3,0), (3,-1), "CENTER"),
            ("ALIGN",         (5,0), (5,-1), "RIGHT"),
        ]))
        story += [tbl_res, sp(4)]

    # ══════════════════════════════════════════════════════════════════════════
    # TOTALES
    # ══════════════════════════════════════════════════════════════════════════
    story.append(p("RESUMEN FINANCIERO:", sec))
    story.append(hr())

    col_lbl = ancho * 0.60
    col_val = ancho * 0.40

    totales_data = [
        [p("Subtotal:",  normal), p(fmt_cop(subtotal_v),  normal_r)],
        [p("Descuento:", normal), p(fmt_cop(descuento_v), normal_r)],
        [p("IVA:",       normal), p(fmt_cop(iva_v),       normal_r)],
    ]
    tbl_sub = Table(totales_data, colWidths=[col_lbl, col_val])
    tbl_sub.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), GRIS_CLARO),
        ("GRID",         (0,0), (-1,-1), 0.3, BORDE),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(tbl_sub)

    # Fila de TOTAL destacada
    total_estilo = ParagraphStyle("TT", fontSize=14, fontName="Helvetica-Bold",
                                  textColor=colors.white, alignment=TA_RIGHT)
    tbl_total = Table(
        [[p("TOTAL A PAGAR:", total_estilo),
          p(f"{fmt_cop(total_v)} COP", total_estilo)]],
        colWidths=[col_lbl, col_val],
    )
    tbl_total.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), AZUL_OSCURO),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story += [tbl_total, sp(5)]

    # ══════════════════════════════════════════════════════════════════════════
    # PIE DE PÁGINA
    # ══════════════════════════════════════════════════════════════════════════
    story.append(hr(AZUL_MEDIO, 1))
    story.append(p(
        f"Documento generado el {ahora_str} · {NEGOCIO} · {DIRECCION} · Tel: {TELEFONO}",
        pie,
    ))
    story.append(p(
        "Este documento es una factura de cobro por servicios de convenio empresarial. "
        "Ante dudas comuníquese al número indicado.",
        pie,
    ))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 1. FACTURACIÓN AUTOMÁTICA MENSUAL POR EMPRESA
# ══════════════════════════════════════════════════════════════════════════════

def generar_facturacion_mensual(mes: int = None, anio: int = None) -> dict:
    """
    Genera una factura consolidada mensual por empresa con todas las reservas
    a crédito (Metodo_Pago='Convenio', Estado_Pago='pendiente') del mes/año
    indicado.  Retorna dict con resumen de la operación.
    """
    get_active_client_convenios     = _g("get_active_client_convenios")
    _gs_get_or_create_ws            = _g("_gs_get_or_create_ws")
    gs_escribir_factura_convenio    = _g("gs_escribir_factura_convenio")
    _gs_invalidate_cache_conv       = _g("_gs_invalidate_cache_conv")
    ahora_col                       = _g("ahora_col")

    resumen = {
        "facturas_generadas": 0,
        "reservas_marcadas":  0,
        "empresas":           [],
        "errores":            [],
    }

    _, sh = get_active_client_convenios()
    if not sh:
        resumen["errores"].append("Sin conexión a jjgt_convenios.")
        return resumen

    hoy      = ahora_col()
    mes_obj  = mes  if mes  else hoy.month
    anio_obj = anio if anio else hoy.year

    try:
        ws_res   = _gs_get_or_create_ws(sh, "Reservas")
        reservas = ws_res.get_all_records()
    except Exception as e:
        resumen["errores"].append(f"Error leyendo Reservas: {e}")
        return resumen

    empresas: dict = {}
    _dbg_total      = len(reservas)
    _dbg_conv       = 0
    _dbg_pend       = 0
    _dbg_mes_ok     = 0
    _dbg_fechas_fail= []

    for r in reservas:
        metodo = str(_fld(r, "Metodo_Pago", "metodo_pago")).strip()
        if metodo != "Convenio":
            continue
        _dbg_conv += 1

        estado = str(_fld(r, "Estado_Pago", "estado_pago")).strip().lower()
        if estado != "pendiente":
            continue
        _dbg_pend += 1

        fecha_raw = _fld(r, "Creado_En", "creado_en")
        mes_r, anio_r = _fecha_mes_anio(fecha_raw)
        if mes_r is None:
            _dbg_fechas_fail.append(str(fecha_raw)[:50])
        if mes_r != mes_obj or anio_r != anio_obj:
            continue
        _dbg_mes_ok += 1

        emp_id  = str(_fld(r, "Id_Empresa",    "id_empresa",    default="SIN_ID")).strip()
        emp_nom = str(_fld(r, "Nombre_Empresa", "nombre_empresa", default="Sin nombre")).strip()
        total   = float(_fld(r, "Total_COP", "total", default=0) or 0)
        num_res = str(_fld(r, "Numero_Reserva", "numero_reserva", default="")).strip()

        if emp_id not in empresas:
            empresas[emp_id] = {
                "nombre":   emp_nom,
                "total":    0.0,
                "reservas": [],
                "filas":    [],        # guardamos la fila completa para detalle PDF
            }
        empresas[emp_id]["total"]    += total
        empresas[emp_id]["reservas"].append(num_res)
        empresas[emp_id]["filas"].append(r)

    if not empresas:
        detalle = (
            f"Filas leídas: {_dbg_total} | "
            f"Metodo_Pago=Convenio: {_dbg_conv} | "
            f"Estado_Pago=pendiente: {_dbg_pend} | "
            f"En {mes_obj:02d}/{anio_obj}: {_dbg_mes_ok}"
        )
        if _dbg_fechas_fail:
            detalle += f" | Fechas no parseadas: {_dbg_fechas_fail[:3]}"
        resumen["errores"].append(
            f"No se encontraron reservas de Convenio pendientes para "
            f"{mes_obj:02d}/{anio_obj}. [{detalle}]"
        )
        return resumen

    # Cargar hoja Clientes para obtener Nit_Empresa y Email de cada empresa
    _cli_map: dict = {}   # clave: id_empresa.lower() o nombre.lower() → fila cliente
    try:
        _ws_cli_men = _gs_get_or_create_ws(sh, "Clientes")
        for _cr in _ws_cli_men.get_all_records():
            _id_k  = str(_fld(_cr, "Id_Empresa",  "id_empresa",  default="")).strip().lower()
            _nom_k = str(_fld(_cr, "Nombre_Empresa", "nombre_empresa",
                              "Nombre", "nombre", default="")).strip().lower()
            if _id_k:
                _cli_map[_id_k] = _cr
            if _nom_k and _nom_k not in _cli_map:
                _cli_map[_nom_k] = _cr
    except Exception:
        pass  # No bloqueante: la factura se genera aunque falle la lectura

    for emp_id, data in empresas.items():
        factura_id = f"FAC-{emp_id}-{anio_obj}{mes_obj:02d}"

        # Buscar datos de empresa en Clientes
        _cr_emp   = _cli_map.get(emp_id.lower()) or                     _cli_map.get(data["nombre"].lower()) or {}
        _nit_men  = str(_fld(_cr_emp, "Nit_Empresa", "nit_empresa",
                             "NIT", "nit", default="")).strip()
        _email_men= str(_fld(_cr_emp, "Email", "email",
                             "Cliente_Email", "cliente_email", default="")).strip()

        datos_factura = {
            "id":               factura_id,
            "numero":           factura_id,
            "tipo":             "Factura Consolidada Convenio",
            "cliente_nombre":   data["nombre"],
            "nit_empresa":      _nit_men,
            "cliente_email":    _email_men,
            "descripcion":      (
                f"Factura mensual convenio — {data['nombre']} — "
                f"{mes_obj:02d}/{anio_obj} — "
                f"{len(data['reservas'])} reserva(s)"
            ),
            "subtotal":         data["total"],
            "descuento":        0,
            "iva":              0,
            "total":            data["total"],
            "estado":           "pendiente",
            "metodo_pago":      "Convenio",
            "moneda":           "COP",
            "fecha_emision":    hoy.strftime("%Y-%m-%d"),
            "fecha_vencimiento":(hoy + timedelta(days=30)).strftime("%Y-%m-%d"),
            "creado_en":        hoy.isoformat(),
            "actualizado_en":   hoy.isoformat(),
            "Id_Empresa":       emp_id,
            "Nombre_Empresa":   emp_nom,

        }
        try:
            # gs_escribir_factura_convenio escribe las 26 columnas incluyendo
            # Id_Empresa y Nombre_Empresa en jjgt_convenios
            gs_escribir_factura_convenio(sh, datos_factura, emp_id, data["nombre"])
            resumen["facturas_generadas"] += 1
            resumen["empresas"].append({
                "nombre":     data["nombre"],
                "total":      data["total"],
                "factura_id": factura_id,
                "reservas":   len(data["reservas"]),
            })
        except Exception as e:
            resumen["errores"].append(f"Error generando {factura_id}: {e}")
            continue

        # ── Envío automático de factura por email ─────────────────────────────
        if _email_men:
            try:
                REPORTLAB_AVAILABLE = _g("REPORTLAB_AVAILABLE")
                NEGOCIO             = _g("NEGOCIO")
                fmt_cop_local       = _g("fmt_cop")

                asunto_email = (
                    f"Factura {factura_id} — {data['nombre']} — "
                    f"{mes_obj:02d}/{anio_obj}"
                )
                cuerpo_email = (
                    f"Estimado cliente de {data['nombre']},\n\n"
                    f"Adjunto encontrará la factura de convenio correspondiente al período "
                    f"{mes_obj:02d}/{anio_obj}.\n\n"
                    f"  • Número de factura : {factura_id}\n"
                    f"  • Total a pagar     : {fmt_cop_local(data['total'])} COP\n"
                    f"  • Fecha de vencimiento: {(hoy + timedelta(days=30)).strftime('%d/%m/%Y')}\n\n"
                    f"Por favor realice el pago antes de la fecha de vencimiento.\n"
                    f"Para cualquier consulta, comuníquese con nosotros.\n\n"
                    f"Atentamente,\n{NEGOCIO}"
                )

                if REPORTLAB_AVAILABLE:
                    pdf_bytes_email = generar_factura_pdf(datos_factura, data["filas"])
                else:
                    pdf_bytes_email = b""

                enviado = enviar_factura_email(
                    destinatario=_email_men,
                    asunto=asunto_email,
                    cuerpo=cuerpo_email,
                    pdf_bytes=pdf_bytes_email,
                    nombre_pdf=f"{factura_id}.pdf",
                    email_from="suitesalitre@gmail.com",
                    nombre_from="suitesalitre@gmail.com"
                )
                if not enviado:
                    resumen["errores"].append(
                        f"Factura {factura_id} generada, pero no se pudo enviar el email a {_email_men}."
                    )
            except Exception as e_mail:
                resumen["errores"].append(
                    f"Factura {factura_id} generada, error al enviar email: {e_mail}"
                )

        for num_res in data["reservas"]:
            if num_res:
                ok = actualizar_estado_reserva(sh, num_res, "facturado")
                if ok:
                    resumen["reservas_marcadas"] += 1
                else:
                    resumen["errores"].append(f"No se marcó reserva {num_res}.")

    try:
        _gs_invalidate_cache_conv("Reservas", "Facturas")
    except Exception:
        pass

    return resumen


# ══════════════════════════════════════════════════════════════════════════════
# 2. CONTROL DE CARTERA
# ══════════════════════════════════════════════════════════════════════════════

def calcular_cartera() -> dict:
    """
    Calcula el estado de cartera (cuentas por cobrar) de cada empresa
    con facturas de convenio pendientes en jjgt_convenios.
    """
    get_active_client_convenios = _g("get_active_client_convenios")
    _gs_get_or_create_ws        = _g("_gs_get_or_create_ws")
    ahora_col                   = _g("ahora_col")

    _, sh = get_active_client_convenios()
    if not sh:
        return {}

    try:
        ws       = _gs_get_or_create_ws(sh, "Facturas")
        facturas = ws.get_all_records()
    except Exception as e:
        st.warning(f"⚠️ Error leyendo Facturas: {e}")
        return {}

    cartera: dict = {}
    hoy = ahora_col()

    for f in facturas:
        estado = str(_fld(f, "Estado", "estado")).strip().lower()
        if estado != "pendiente":
            continue

        emp   = str(_fld(f, "Nombre_Empresa", "nombre_empresa",
                         "Cliente_Nombre", "cliente_nombre", default="Sin empresa")).strip()
        total = float(_fld(f, "Total_COP", "total", default=0) or 0)
        fv_raw = _fld(f, "Fecha_Vencimiento", "fecha_vencimiento")

        try:
            fv_str = str(fv_raw).strip()
            venc   = pd.NaT
            for _fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                _ts = pd.to_datetime(fv_str, format=_fmt, errors="coerce")
                if not pd.isna(_ts):
                    venc = _ts
                    break
        except Exception:
            venc = pd.NaT

        if emp not in cartera:
            cartera[emp] = {"total": 0.0, "vencido": 0.0, "al_dia": 0.0, "facturas": 0}

        cartera[emp]["total"]    += total
        cartera[emp]["facturas"] += 1

        if pd.isna(venc):
            cartera[emp]["vencido"] += total
        elif venc.to_pydatetime().replace(tzinfo=None) < hoy.replace(tzinfo=None):
            cartera[emp]["vencido"] += total
        else:
            cartera[emp]["al_dia"]  += total

    return cartera


# ══════════════════════════════════════════════════════════════════════════════
# 3. UI — show_facturacion_cartera()
# ══════════════════════════════════════════════════════════════════════════════

def show_facturacion_cartera():
    """
    Panel completo: Facturación Mensual · Control de Cartera · Ver & Imprimir.
    Llamada desde mod_map en show_operador() de pagos_convenios.py.
    """
    fmt_cop   = _g("fmt_cop")
    ahora_col = _g("ahora_col")
    REPORTLAB_AVAILABLE = _g("REPORTLAB_AVAILABLE")
    WHATSAPP_OP         = _g("WHATSAPP_OP")

    st.markdown("## 💳 Facturación & Cartera de Convenios")

    tab_fac, tab_ver, tab_cart = st.tabs([
        "🔄 Facturación Mensual",
        "🧾 Ver & Imprimir Facturas",
        "📊 Control de Cartera",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — FACTURACIÓN MENSUAL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_fac:
        st.markdown("### 🔄 Facturación Automática Mensual por Empresa")
        st.info(
            "Agrupa todas las reservas de convenio **pendientes** del mes "
            "seleccionado, genera **una factura por empresa** y marca las "
            "reservas como **facturadas**."
        )
        hoy = ahora_col()
        col_m, col_a, _ = st.columns([1, 1, 2])
        with col_m:
            mes_sel = st.selectbox(
                "Mes", options=list(range(1, 13)), index=hoy.month - 1,
                format_func=lambda m: [
                    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
                    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
                ][m - 1],
                key="fac_mes_sel",
            )
        with col_a:
            anio_sel = st.number_input(
                "Año", min_value=2020, max_value=hoy.year + 1,
                value=hoy.year, step=1, key="fac_anio_sel",
            )
        st.divider()

        if st.button("⚡ GENERAR FACTURACIÓN MENSUAL", type="primary",
                     use_container_width=True, key="btn_gen_fac_mensual"):
            with st.spinner("⏳ Procesando reservas y generando facturas..."):
                resumen = generar_facturacion_mensual(mes=int(mes_sel), anio=int(anio_sel))

            if resumen["facturas_generadas"] > 0:
                st.success(
                    f"✅ **{resumen['facturas_generadas']} factura(s)** generadas · "
                    f"**{resumen['reservas_marcadas']} reserva(s)** marcadas como facturadas."
                )
                df_emp = pd.DataFrame(resumen["empresas"])
                if not df_emp.empty:
                    df_emp = df_emp.rename(columns={
                        "nombre": "Empresa", "factura_id": "ID Factura",
                        "total": "Total (COP)", "reservas": "Reservas incluidas",
                    })
                    df_emp["Total (COP)"] = df_emp["Total (COP)"].apply(fmt_cop)
                    st.dataframe(df_emp, use_container_width=True, hide_index=True)
                st.info("👉 Ve a la pestaña **🧾 Ver & Imprimir Facturas** para descargar los PDFs.")
            else:
                st.warning("⚠️ No se generó ninguna factura.")

            if resumen["errores"]:
                with st.expander(f"⚠️ Errores / Advertencias ({len(resumen['errores'])})"):
                    for err in resumen["errores"]:
                        st.caption(f"• {err}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — VER & IMPRIMIR FACTURAS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_ver:
        st.markdown("### 🧾 Ver, Imprimir y Enviar Facturas de Convenio")

        col_rf1, col_rf2 = st.columns([3, 1])
        with col_rf2:
            if st.button("🔄 Actualizar lista", use_container_width=True, key="btn_refresca_fac"):
                try:
                    _gs_invalidate_cache_conv = _g("_gs_invalidate_cache_conv")
                    _gs_invalidate_cache_conv("Facturas")
                except Exception:
                    pass
                st.rerun()

        with st.spinner("Cargando facturas..."):
            facturas_raw = _leer_facturas_convenio()

        if not facturas_raw:
            st.info("No hay facturas registradas en jjgt_convenios.")
            return

        # ── Filtros ───────────────────────────────────────────────────────────
        with col_rf1:
            col_f1, col_f2, col_f3 = st.columns(3)
            todas_emp = sorted(set(
                str(_fld(f, "Nombre_Empresa", "nombre_empresa",
                         "Cliente_Nombre", default="—")).strip()
                for f in facturas_raw
            ))
            with col_f1:
                filtro_emp = st.selectbox(
                    "Empresa", ["Todas"] + todas_emp, key="ver_fac_emp")
            with col_f2:
                filtro_est = st.selectbox(
                    "Estado", ["Todos", "pendiente", "pagada", "anulada", "facturado"],
                    key="ver_fac_est")
            with col_f3:
                filtro_txt = st.text_input(
                    "Buscar N° factura", placeholder="FAC-...", key="ver_fac_busca")

        # ── Aplicar filtros ───────────────────────────────────────────────────
        facturas_filtradas = []
        for f in facturas_raw:
            emp_f = str(_fld(f, "Nombre_Empresa", "nombre_empresa",
                             "Cliente_Nombre", default="—")).strip()
            est_f = str(_fld(f, "Estado", "estado", default="")).strip().lower()
            num_f = str(_fld(f, "Num_Factura", "numero", default="")).strip()

            if filtro_emp != "Todas" and emp_f != filtro_emp:
                continue
            if filtro_est != "Todos" and est_f != filtro_est.lower():
                continue
            if filtro_txt and filtro_txt.upper() not in num_f.upper():
                continue
            facturas_filtradas.append(f)

        if not facturas_filtradas:
            st.warning("No hay facturas que coincidan con los filtros.")
            return

        # ── Tabla resumen ─────────────────────────────────────────────────────
        filas_tabla = []
        for f in facturas_filtradas:
            est_f = str(_fld(f, "Estado", "estado", default="")).strip().lower()
            icono = {"pendiente": "🔴", "pagada": "🟢",
                     "anulada": "⚫", "facturado": "🔵"}.get(est_f, "⚪")
            filas_tabla.append({
                "Est.": icono,
                "N° Factura": str(_fld(f, "Num_Factura", "numero", default="")),
                "Empresa":    str(_fld(f, "Nombre_Empresa", "nombre_empresa",
                                       "Cliente_Nombre", default="—")),
                "Emisión":    str(_fld(f, "Fecha_Emision",  "fecha_emision",  default=""))[:10],
                "Vencimiento":str(_fld(f, "Fecha_Vencimiento","fecha_vencimiento",default=""))[:10],
                "Total":      fmt_cop(float(_fld(f,"Total_COP","total",default=0) or 0)),
                "Estado":     est_f.capitalize(),
            })
        st.dataframe(pd.DataFrame(filas_tabla), use_container_width=True, hide_index=True)
        st.caption(f"{len(facturas_filtradas)} factura(s) mostradas")
        st.divider()

        # ── Seleccionar una factura para PDF / WhatsApp ───────────────────────
        st.markdown("#### 📄 Selecciona una factura para imprimir o enviar")

        opciones_fac = {
            f"{str(_fld(f,'Num_Factura','numero',default=''))}"
            f"  ·  {str(_fld(f,'Nombre_Empresa','nombre_empresa','Cliente_Nombre',default='—'))}"
            f"  ·  {fmt_cop(float(_fld(f,'Total_COP','total',default=0) or 0))}"
            f"  [{str(_fld(f,'Estado','estado',default=''))}]":
            i
            for i, f in enumerate(facturas_filtradas)
            if _fld(f, "Num_Factura", "numero")
        }

        if not opciones_fac:
            st.info("No hay facturas seleccionables.")
            return

        sel_label = st.selectbox(
            "Factura", list(opciones_fac.keys()),
            key="ver_fac_sel_pdf",
        )
        factura_sel = facturas_filtradas[opciones_fac[sel_label]]
        num_sel     = str(_fld(factura_sel, "Num_Factura", "numero", default="")).strip()
        emp_sel     = str(_fld(factura_sel, "Nombre_Empresa", "nombre_empresa",
                               "Cliente_Nombre", default="")).strip()
        total_sel   = float(_fld(factura_sel, "Total_COP", "total", default=0) or 0)
        vence_sel   = str(_fld(factura_sel, "Fecha_Vencimiento", "fecha_vencimiento",
                               default=""))[:10]

        # ── Vista previa rápida ───────────────────────────────────────────────
        with st.expander("👁 Vista previa de datos", expanded=False):
            col_p1, col_p2 = st.columns(2)
            col_p1.markdown(f"**N° Factura:** {num_sel}")
            col_p1.markdown(f"**Empresa:** {emp_sel}")
            col_p1.markdown(f"**Emisión:** {str(_fld(factura_sel,'Fecha_Emision','fecha_emision',default=''))[:10]}")
            col_p2.markdown(f"**Total:** {fmt_cop(total_sel)}")
            col_p2.markdown(f"**Estado:** {_fld(factura_sel,'Estado','estado',default='')}")
            col_p2.markdown(f"**Vence:** {vence_sel}")
            desc = _fld(factura_sel, "Descripcion", "descripcion", default="")
            if desc:
                st.caption(f"Concepto: {desc}")

        # Buscar reservas de esta factura (para incluir detalle en PDF)
        reservas_de_fac = []
        try:
            get_active_client_convenios = _g("get_active_client_convenios")
            _gs_get_or_create_ws        = _g("_gs_get_or_create_ws")
            _, sh_r = get_active_client_convenios()
            if sh_r:
                ws_r      = _gs_get_or_create_ws(sh_r, "Reservas")
                todas_res = ws_r.get_all_records()
                for r in todas_res:
                    num_fac_r = str(_fld(r, "Num_Factura", "num_factura", default="")).strip()
                    emp_res_r = str(_fld(r, "Nombre_Empresa", "nombre_empresa", default="")).strip()
                    est_res_r = str(_fld(r, "Estado_Pago", "estado_pago", default="")).strip().lower()
                    # Incluir reservas de esta empresa que estén facturadas
                    if emp_res_r == emp_sel and est_res_r in ("facturado", "facturada"):
                        reservas_de_fac.append(r)
                    # O que tengan el Num_Factura coincidente
                    elif num_fac_r == num_sel:
                        if r not in reservas_de_fac:
                            reservas_de_fac.append(r)
        except Exception:
            pass

        st.caption(
            f"Se encontraron **{len(reservas_de_fac)}** reserva(s) "
            f"vinculadas a esta factura."
        )

        # ── Botones de acción ─────────────────────────────────────────────────
        col_a1, col_a2, col_a3 = st.columns(3)

        # ── PDF ───────────────────────────────────────────────────────────────
        with col_a1:
            if not REPORTLAB_AVAILABLE:
                st.warning("⚠️ reportlab no instalado. Ejecuta:\n`pip install reportlab`")
            else:
                if st.button("📄 Generar PDF", use_container_width=True,
                             type="primary", key="btn_pdf_fac"):
                    with st.spinner("Generando PDF..."):
                        pdf_bytes = generar_factura_pdf(
                            factura_sel, reservas_de_fac or None
                        )
                    if pdf_bytes:
                        st.download_button(
                            label="⬇️ Descargar PDF",
                            data=pdf_bytes,
                            file_name=f"factura_{num_sel}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="dl_pdf_fac",
                        )
                    else:
                        st.error("❌ No se pudo generar el PDF.")

        # ── WhatsApp ──────────────────────────────────────────────────────────
        with col_a2:
            wa_num = str(WHATSAPP_OP).replace("+","").replace(" ","")
            wa_msg = (
                f"Factura N° {num_sel} | "
                f"Empresa: {emp_sel} | "
                f"Total: {fmt_cop(total_sel)} COP | "
                f"Vence: {vence_sel} | "
                f"{_g('NEGOCIO')}"
            )
            wa_url = f"https://wa.me/{wa_num}?text={wa_msg.replace(' ','%20')}"
            st.markdown(
                f'''<a href="{wa_url}" target="_blank" style="text-decoration:none">
                <button style="width:100%;padding:14px 0;margin-top:4px;
                  background:rgba(37,211,102,0.15);
                  border:2px solid rgba(37,211,102,0.5);
                  border-radius:12px;color:#25d366;
                  font-weight:700;font-size:15px;cursor:pointer">
                  📱 Enviar por WhatsApp
                </button></a>''',
                unsafe_allow_html=True,
            )

        # ── CSV de reservas ───────────────────────────────────────────────────
        with col_a3:
            if reservas_de_fac:
                df_res_csv = pd.DataFrame(reservas_de_fac)
                csv_bytes = df_res_csv.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📊 Exportar reservas CSV",
                    data=csv_bytes,
                    file_name=f"reservas_{num_sel}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_csv_res_fac",
                )
            else:
                st.caption("Sin reservas vinculadas para exportar.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — CONTROL DE CARTERA
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cart:
        st.markdown("### 📊 Control de Cartera — Cuentas por Cobrar")
        st.info(
            "Facturas de convenio **pendientes** en jjgt_convenios. "
            "Muestra montos vencidos y al día por empresa."
        )

        if st.button("🔄 Actualizar cartera", use_container_width=True,
                     key="btn_refresh_cartera"):
            st.rerun()

        with st.spinner("Cargando cartera..."):
            cartera = calcular_cartera()

        if not cartera:
            st.info("✅ No hay facturas pendientes.")
            return

        total_global   = sum(v["total"]   for v in cartera.values())
        vencido_global = sum(v["vencido"] for v in cartera.values())
        al_dia_global  = sum(v["al_dia"]  for v in cartera.values())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏢 Empresas",      len(cartera))
        c2.metric("💰 Total",         fmt_cop(total_global))
        c3.metric("🔴 Vencido",       fmt_cop(vencido_global))
        c4.metric("🟢 Al día",        fmt_cop(al_dia_global))
        st.divider()

        rows = []
        for emp, vals in sorted(cartera.items(), key=lambda x: x[1]["vencido"], reverse=True):
            pct = round(vals["vencido"] / vals["total"] * 100, 1) if vals["total"] > 0 else 0
            rows.append({
                "Est.":      "🔴" if vals["vencido"] > 0 else "🟢",
                "Empresa":   emp,
                "Facturas":  vals["facturas"],
                "Total":     fmt_cop(vals["total"]),
                "Vencido":   fmt_cop(vals["vencido"]),
                "Al día":    fmt_cop(vals["al_dia"]),
                "% Vencido": f"{pct:.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("#### 🔍 Detalle por empresa")
        for emp, vals in sorted(cartera.items(), key=lambda x: x[1]["vencido"], reverse=True):
            icono = "🔴" if vals["vencido"] > 0 else "🟢"
            with st.expander(
                f"{icono} **{emp}** — Total: {fmt_cop(vals['total'])} "
                f"| Vencido: {fmt_cop(vals['vencido'])} "
                f"| Al día: {fmt_cop(vals['al_dia'])}",
                expanded=(vals["vencido"] > 0),
            ):
                cv1, cv2, cv3 = st.columns(3)
                cv1.metric("Total",        fmt_cop(vals["total"]))
                cv2.metric("🔴 Vencido",   fmt_cop(vals["vencido"]))
                cv3.metric("🟢 Al día",    fmt_cop(vals["al_dia"]))
                if vals["vencido"] > 0:
                    wa_num = str(WHATSAPP_OP).replace("+","").replace(" ","")
                    wa_msg_c = (
                        f"Recordatorio de pago — {emp} — "
                        f"Saldo vencido: {fmt_cop(vals['vencido'])} COP — "
                        f"{_g('NEGOCIO')}"
                    )
                    wa_url_c = f"https://wa.me/{wa_num}?text={wa_msg_c.replace(' ','%20')}"
                    st.warning(
                        f"⚠️ **{fmt_cop(vals['vencido'])} COP** vencidos. "
                        "Considera enviar un recordatorio."
                    )
                    st.markdown(
                        f'<a href="{wa_url_c}" target="_blank">'
                        f'<button style="padding:8px 16px;background:rgba(37,211,102,0.15);'
                        f'border:1.5px solid rgba(37,211,102,0.5);border-radius:8px;'
                        f'color:#25d366;font-weight:700;cursor:pointer">'
                        f'📱 Enviar recordatorio WhatsApp</button></a>',
                        unsafe_allow_html=True,
                    )
