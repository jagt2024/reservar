import streamlit as st
import pandas as pd
import os
import uuid
import datetime
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import base64
from PIL import Image as PILImage
import io
import hashlib
import json
import time

# Configuración inicial de la página
#st.set_page_config(
#    page_title="Generador de Documentos para Firma Electrónica",
#    page_icon="📝",
#    layout="wide"
#)

# Estilos y tema personalizado
#st.markdown("""
#<style>
#    .main-header {
#        font-size: 2.5rem;
#        color: #1E3A8A;
#        text-align: center;
#        margin-bottom: 1rem;
#   }
#    .sub-header {
#        font-size: 1.5rem;
#        color: #3B82F6;
#        margin-bottom: 1rem;
#    }
#    .info-box {
#        background-color: #EFF6FF;
#        padding: 1rem;
#        border-radius: 5px;
#        border-left: 5px solid #3B82F6;
#    }
#    .success-box {
#        background-color: #ECFDF5;
#        padding: 1rem;
#        border-radius: 5px;
#        border-left: 5px solid #10B981;
#        margin-top: 1rem;
#    }
#</style>
#""", unsafe_allow_html=True)

# Funciones de utilidad
def generar_codigo_verificacion():
    """Genera un código único de verificación"""
    return str(uuid.uuid4())[:8].upper()

def calcular_hash_documento(datos):
    """Calcula un hash SHA-256 de los datos del documento"""
    contenido = json.dumps(datos, sort_keys=True).encode()
    return hashlib.sha256(contenido).hexdigest()

def generar_qr(datos):
    """Genera un código QR con la información de verificación"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(datos)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir imagen a bytes para ReportLab
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

def crear_pdf(datos_documento, plantilla_seleccionada):
    """Crea un documento PDF con la información proporcionada"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    # Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Centrado', alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='Justificado', alignment=TA_LEFT, spaceAfter=12, leading=14))
    styles.add(ParagraphStyle(name='Titulo', fontSize=16, alignment=TA_CENTER, spaceAfter=16, leading=20))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=14, alignment=TA_CENTER, spaceAfter=14, leading=16))
    styles.add(ParagraphStyle(name='Pie', fontSize=8, alignment=TA_CENTER, textColor=colors.gray))
    
    contenido = []
    
    # Logo (si se proporcionó)
    if 'logo' in st.session_state and st.session_state['logo'] is not None:
        img_buffer = BytesIO(st.session_state['logo'])
        logo = Image(img_buffer, width=2*inch, height=0.75*inch)
        contenido.append(logo)
    
    # Título del documento
    contenido.append(Paragraph(datos_documento["tipo_documento"], styles["Titulo"]))
    contenido.append(Spacer(1, 12))
    
    # Información de identificación
    contenido.append(Paragraph(f"Documento N°: {datos_documento['numero_documento']}", styles["Subtitulo"]))
    contenido.append(Paragraph(f"Fecha: {datos_documento['fecha']}", styles["Centrado"]))
    contenido.append(Spacer(1, 24))
    
    # Contenido según la plantilla
    if plantilla_seleccionada == "Contrato":
        contenido.extend(generar_contenido_contrato(datos_documento, styles))
    elif plantilla_seleccionada == "Acuerdo de confidencialidad":
        contenido.extend(generar_contenido_acuerdo_confidencialidad(datos_documento, styles))
    elif plantilla_seleccionada == "Autorización":
        contenido.extend(generar_contenido_autorizacion(datos_documento, styles))
    else:  # Documento en blanco
        contenido.append(Paragraph(datos_documento["contenido_personalizado"], styles["Justificado"]))
    
    # Información de firma electrónica
    contenido.append(Spacer(1, 24))
    contenido.append(Paragraph("INFORMACIÓN PARA VERIFICACIÓN DE FIRMA ELECTRÓNICA", styles["Subtitulo"]))
    
    # Tabla con información de verificación
    datos_verificacion = [
        ["Código de verificación:", datos_documento["codigo_verificacion"]],
        ["Hash del documento:", datos_documento["hash_documento"][:20] + "..."],
        ["Fecha y hora de generación:", datos_documento["timestamp_generacion"]],
        ["ID único de documento:", datos_documento["id_documento"]]
    ]
    
    tabla_verificacion = Table(datos_verificacion, colWidths=[2*inch, 3.5*inch])
    tabla_verificacion.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    contenido.append(tabla_verificacion)
    contenido.append(Spacer(1, 12))
    
    # Código QR
    qr_data = (
        f"ID: {datos_documento['id_documento']}\n"
        f"Verificación: {datos_documento['codigo_verificacion']}\n"
        f"Hash: {datos_documento['hash_documento'][:20]}\n"
        f"Fecha: {datos_documento['timestamp_generacion']}"
    )
    qr_image = generar_qr(qr_data)
    img = Image(BytesIO(qr_image), width=1.5*inch, height=1.5*inch)
    
    # Centrar el QR
    tabla_qr = Table([[img]], colWidths=[6*inch])
    tabla_qr.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    contenido.append(tabla_qr)
    contenido.append(Spacer(1, 12))
    
    # Espacio para firmas
    firmas = [["Firmante 1", "Firmante 2"]]
    tabla_firmas = Table(firmas, colWidths=[3*inch, 3*inch])
    tabla_firmas.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 1, colors.black),
        ('LINEABOVE', (1, 0), (1, 0), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    contenido.append(tabla_firmas)
    contenido.append(Spacer(1, 24))
    
    # Pie de página con información legal
    contenido.append(Paragraph(
        "Este documento ha sido generado digitalmente y cuenta con los elementos de seguridad "
        "necesarios para su verificación. La firma electrónica aplicada a este documento tiene la misma "
        "validez que una firma manuscrita de acuerdo con la legislación vigente.",
        styles["Pie"]
    ))
    
    # Construir el PDF
    doc.build(contenido)
    return buffer

def generar_contenido_contrato(datos, styles):
    """Genera el contenido para un contrato"""
    contenido = []
    
    # Partes del contrato
    contenido.append(Paragraph("PARTES DEL CONTRATO", styles["Subtitulo"]))
    contenido.append(Paragraph(
        f"<b>PARTE A:</b> {datos['parte_a']}, identificado con documento número {datos.get('documento_parte_a', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Paragraph(
        f"<b>PARTE B:</b> {datos['parte_b']}, identificado con documento número {datos.get('documento_parte_b', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Spacer(1, 12))
    
    # Cláusulas
    contenido.append(Paragraph("CLÁUSULAS", styles["Subtitulo"]))
    
    # Objeto
    contenido.append(Paragraph("<b>PRIMERA. OBJETO:</b>", styles["Justificado"]))
    contenido.append(Paragraph(datos.get('objeto_contrato', 'El objeto del presente contrato...'), styles["Justificado"]))
    
    # Obligaciones
    contenido.append(Paragraph("<b>SEGUNDA. OBLIGACIONES DE LAS PARTES:</b>", styles["Justificado"]))
    contenido.append(Paragraph(datos.get('obligaciones', 'Las partes se comprometen a...'), styles["Justificado"]))
    
    # Duración
    contenido.append(Paragraph("<b>TERCERA. DURACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        f"El presente contrato tendrá una duración de {datos.get('duracion', 'X meses/años')} "
        f"contados a partir de la fecha de su firma.",
        styles["Justificado"]
    ))
    
    # Valor
    contenido.append(Paragraph("<b>CUARTA. VALOR:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        f"El valor del presente contrato es de {datos.get('valor', '$X')}.",
        styles["Justificado"]
    ))
    
    # Terminación
    contenido.append(Paragraph("<b>QUINTA. TERMINACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "El contrato podrá darse por terminado por mutuo acuerdo entre las partes o por incumplimiento "
        "de las obligaciones por cualquiera de ellas.",
        styles["Justificado"]
    ))
    
    # Cláusulas adicionales
    if 'clausulas_adicionales' in datos and datos['clausulas_adicionales']:
        contenido.append(Paragraph("<b>CLÁUSULAS ADICIONALES:</b>", styles["Justificado"]))
        contenido.append(Paragraph(datos['clausulas_adicionales'], styles["Justificado"]))
    
    return contenido

def generar_contenido_acuerdo_confidencialidad(datos, styles):
    """Genera el contenido para un acuerdo de confidencialidad"""
    contenido = []
    
    # Partes del acuerdo
    contenido.append(Paragraph("PARTES DEL ACUERDO", styles["Subtitulo"]))
    contenido.append(Paragraph(
        f"<b>PARTE REVELADORA:</b> {datos['parte_a']}, identificada con documento número {datos.get('documento_parte_a', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Paragraph(
        f"<b>PARTE RECEPTORA:</b> {datos['parte_b']}, identificada con documento número {datos.get('documento_parte_b', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Spacer(1, 12))
    
    # Cláusulas
    contenido.append(Paragraph("CLÁUSULAS", styles["Subtitulo"]))
    
    # Definición de Información Confidencial
    contenido.append(Paragraph("<b>PRIMERA. DEFINICIÓN DE INFORMACIÓN CONFIDENCIAL:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "Para efectos del presente acuerdo, se entiende por Información Confidencial toda información técnica, "
        "financiera, comercial, estratégica, y cualquier otra información que la Parte Reveladora comparta con "
        "la Parte Receptora, independientemente del medio en que se encuentre contenida.",
        styles["Justificado"]
    ))
    
    # Objeto
    contenido.append(Paragraph("<b>SEGUNDA. OBJETO:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "El presente acuerdo tiene como objeto establecer los términos y condiciones bajo los cuales "
        "la Parte Receptora deberá mantener la confidencialidad de la información suministrada por la Parte Reveladora.",
        styles["Justificado"]
    ))
    
    # Obligaciones
    contenido.append(Paragraph("<b>TERCERA. OBLIGACIONES DE LA PARTE RECEPTORA:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "La Parte Receptora se obliga a: (i) Mantener la información en estricta confidencialidad; "
        "(ii) No divulgar la información a terceros sin autorización previa y por escrito de la Parte Reveladora; "
        "(iii) Utilizar la información únicamente para los fines autorizados por la Parte Reveladora.",
        styles["Justificado"]
    ))
    
    # Duración
    contenido.append(Paragraph("<b>CUARTA. DURACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        f"Las obligaciones de confidencialidad establecidas en el presente acuerdo tendrán una vigencia de "
        f"{datos.get('duracion', 'X años')} contados a partir de la fecha de su firma.",
        styles["Justificado"]
    ))
    
    # Penalidades
    contenido.append(Paragraph("<b>QUINTA. PENALIDADES:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "El incumplimiento de las obligaciones de confidencialidad dará lugar a que la Parte Reveladora "
        "pueda ejercer las acciones legales correspondientes y reclamar la indemnización por los daños y "
        "perjuicios ocasionados.",
        styles["Justificado"]
    ))
    
    # Disposiciones adicionales
    if 'clausulas_adicionales' in datos and datos['clausulas_adicionales']:
        contenido.append(Paragraph("<b>DISPOSICIONES ADICIONALES:</b>", styles["Justificado"]))
        contenido.append(Paragraph(datos['clausulas_adicionales'], styles["Justificado"]))
    
    return contenido

def generar_contenido_autorizacion(datos, styles):
    """Genera el contenido para una autorización"""
    contenido = []
    
    # Partes
    contenido.append(Paragraph("PARTES", styles["Subtitulo"]))
    contenido.append(Paragraph(
        f"<b>AUTORIZANTE:</b> {datos['parte_a']}, identificado con documento número {datos.get('documento_parte_a', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Paragraph(
        f"<b>AUTORIZADO:</b> {datos['parte_b']}, identificado con documento número {datos.get('documento_parte_b', 'N/A')}",
        styles["Justificado"]
    ))
    contenido.append(Spacer(1, 12))
    
    # Contenido de la autorización
    contenido.append(Paragraph("AUTORIZACIÓN", styles["Subtitulo"]))
    contenido.append(Paragraph(
        f"Yo, {datos['parte_a']}, en pleno uso de mis facultades, autorizo expresamente a {datos['parte_b']} para:",
        styles["Justificado"]
    ))
    
    # Propósito
    contenido.append(Paragraph("<b>PROPÓSITO DE LA AUTORIZACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(datos.get('proposito_autorizacion', 'Descripción del propósito...'), styles["Justificado"]))
    
    # Alcance
    contenido.append(Paragraph("<b>ALCANCE DE LA AUTORIZACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(datos.get('alcance_autorizacion', 'Descripción del alcance...'), styles["Justificado"]))
    
    # Duración
    contenido.append(Paragraph("<b>DURACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        f"Esta autorización tiene validez por un período de {datos.get('duracion', 'X días/meses/años')} "
        f"contados a partir de la fecha de firma.",
        styles["Justificado"]
    ))
    
    # Revocación
    contenido.append(Paragraph("<b>REVOCACIÓN:</b>", styles["Justificado"]))
    contenido.append(Paragraph(
        "Esta autorización puede ser revocada en cualquier momento mediante notificación escrita al autorizado.",
        styles["Justificado"]
    ))
    
    # Disposiciones adicionales
    if 'clausulas_adicionales' in datos and datos['clausulas_adicionales']:
        contenido.append(Paragraph("<b>DISPOSICIONES ADICIONALES:</b>", styles["Justificado"]))
        contenido.append(Paragraph(datos['clausulas_adicionales'], styles["Justificado"]))
    
    return contenido

def mostrar_creador_documentos():
    """Muestra la interfaz para crear documentos"""
    st.markdown('<h2 class="sub-header">Crear Nuevo Documento</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    Complete el formulario para generar un documento con elementos de seguridad digital.
    Los documentos generados incluirán un código de verificación único, un hash criptográfico y un código QR.
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Selección de tipo de documento
    plantilla_seleccionada = st.selectbox(
        "Seleccione el tipo de documento",
        ["Contrato", "Acuerdo de confidencialidad", "Autorización", "Documento en blanco"]
    )
    
    # Iniciar form para recoger datos
    with st.form("formulario_documento"):
        # Campos comunes para todos los documentos
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_documento = st.text_input("Título del documento", 
                                           value=plantilla_seleccionada,
                                           help="Título que aparecerá en el encabezado del documento")
            numero_documento = st.text_input("Número/Referencia", 
                                            value=f"DOC-{datetime.datetime.now().strftime('%Y%m%d')}-{generar_codigo_verificacion()[:4]}",
                                            help="Número o referencia única del documento")
        
        with col2:
            fecha = st.date_input("Fecha del documento", 
                                 value=datetime.datetime.now().date(),
                                 help="Fecha oficial del documento")
            logo = st.file_uploader("Logo (opcional)", 
                                   type=["png", "jpg", "jpeg"],
                                   help="Logo que aparecerá en el encabezado del documento")
        
        # Guardar logo en session_state si se proporciona
        if logo is not None:
            bytes_data = logo.getvalue()
            st.session_state['logo'] = bytes_data
        
        # Campos específicos según el tipo de documento
        if plantilla_seleccionada in ["Contrato", "Acuerdo de confidencialidad", "Autorización"]:
            st.markdown("### Información de las partes")
            col1, col2 = st.columns(2)
            
            with col1:
                parte_a = st.text_input(
                    "Nombre completo de la Parte A" if plantilla_seleccionada == "Contrato" else
                    "Nombre de la Parte Reveladora" if plantilla_seleccionada == "Acuerdo de confidencialidad" else
                    "Nombre del Autorizante"
                )
                documento_parte_a = st.text_input("Documento de identidad")
                
            with col2:
                parte_b = st.text_input(
                    "Nombre completo de la Parte B" if plantilla_seleccionada == "Contrato" else
                    "Nombre de la Parte Receptora" if plantilla_seleccionada == "Acuerdo de confidencialidad" else
                    "Nombre del Autorizado"
                )
                documento_parte_b = st.text_input("Documento de identidad", key="doc_parte_b")
        
        # Campos específicos por tipo de documento
        if plantilla_seleccionada == "Contrato":
            st.markdown("### Información del contrato")
            
            objeto_contrato = st.text_area(
                "Objeto del contrato",
                value="El presente contrato tiene por objeto...",
                height=100
            )
            
            col1, col2 = st.columns(2)
            with col1:
                duracion = st.text_input("Duración del contrato", value="12 meses")
                obligaciones = st.text_area("Obligaciones de las partes", height=100)
            
            with col2:
                valor = st.text_input("Valor del contrato", value="$0")
                clausulas_adicionales = st.text_area("Cláusulas adicionales (opcional)", height=100)
                
        elif plantilla_seleccionada == "Acuerdo de confidencialidad":
            st.markdown("### Información del acuerdo")
            
            duracion = st.text_input("Duración de la confidencialidad", value="5 años")
            clausulas_adicionales = st.text_area("Disposiciones adicionales (opcional)", height=100)
            
        elif plantilla_seleccionada == "Autorización":
            st.markdown("### Información de la autorización")
            
            proposito_autorizacion = st.text_area(
                "Propósito de la autorización",
                value="Se autoriza para...",
                height=100
            )
            
            alcance_autorizacion = st.text_area(
                "Alcance de la autorización",
                value="Esta autorización incluye...",
                height=100
            )
            
            duracion = st.text_input("Duración de la autorización", value="30 días")
            clausulas_adicionales = st.text_area("Disposiciones adicionales (opcional)", height=100)
            
        else:  # Documento en blanco
            contenido_personalizado = st.text_area(
                "Contenido del documento",
                value="Ingrese aquí el contenido completo del documento...",
                height=300
            )
        
        # Botón para generar el documento
        submitted = st.form_submit_button("Generar Documento")
        
        if submitted:
            # Generar datos del documento
            id_documento = str(uuid.uuid4())
            codigo_verificacion = generar_codigo_verificacion()
            timestamp_generacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Recopilar datos según el tipo de documento
            datos_documento = {
                "id_documento": id_documento,
                "tipo_documento": tipo_documento,
                "numero_documento": numero_documento,
                "fecha": fecha.strftime("%d/%m/%Y"),
                "codigo_verificacion": codigo_verificacion,
                "timestamp_generacion": timestamp_generacion
            }
            
            # Añadir campos específicos según el tipo de documento
            if plantilla_seleccionada in ["Contrato", "Acuerdo de confidencialidad", "Autorización"]:
                datos_documento.update({
                    "parte_a": parte_a,
                    "documento_parte_a": documento_parte_a,
                    "parte_b": parte_b,
                    "documento_parte_b": documento_parte_b
                })
            
            if plantilla_seleccionada == "Contrato":
                datos_documento.update({
                    "objeto_contrato": objeto_contrato,
                    "duracion": duracion,
                    "obligaciones": obligaciones,
                    "valor": valor,
                    "clausulas_adicionales": clausulas_adicionales
                })
            elif plantilla_seleccionada == "Acuerdo de confidencialidad":
                datos_documento.update({
                    "duracion": duracion,
                    "clausulas_adicionales": clausulas_adicionales
                })
            elif plantilla_seleccionada == "Autorización":
                datos_documento.update({
                    "proposito_autorizacion": proposito_autorizacion,
                    "alcance_autorizacion": alcance_autorizacion,
                    "duracion": duracion,
                    "clausulas_adicionales": clausulas_adicionales
                })
            else:  # Documento en blanco
                datos_documento.update({
                    "contenido_personalizado": contenido_personalizado
                })
            
            # Calcular hash del documento
            datos_documento["hash_documento"] = calcular_hash_documento(datos_documento)
            
            # Generar PDF
            pdf_buffer = crear_pdf(datos_documento, plantilla_seleccionada)
            
            # Guardar registro del documento
            guardar_registro_documento(datos_documento)
            
            # Mostrar mensaje de éxito
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.success("¡Documento generado exitosamente!")
            st.markdown(f"**Código de verificación**: {codigo_verificacion}")
            st.markdown(f"**ID de documento**: {id_documento}")
            
            # Convertir a base64 para descarga
            b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="{tipo_documento.replace(" ", "_")}_{numero_documento}.pdf">Descargar documento PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

def mostrar_documentos_generados():
    """Muestra la lista de documentos generados en la sesión actual"""
    st.markdown('<h2 class="sub-header">Documentos Generados</h2>', unsafe_allow_html=True)
    
    if 'documentos_generados' not in st.session_state or not st.session_state['documentos_generados']:
        st.info("No hay documentos generados en esta sesión. Cree un nuevo documento desde la sección 'Crear Documento'.")
        return
    
    # Mostrar tabla de documentos generados
    documentos = pd.DataFrame(st.session_state['documentos_generados'])
    documentos = documentos.rename(columns={
        'id': 'ID', 
        'tipo': 'Tipo de Documento', 
        'fecha': 'Fecha', 
        'codigo': 'Código', 
        'partes': 'Partes', 
        'timestamp': 'Generado en'
    })
    
    st.dataframe(documentos)
    
    # Añadir opciones de filtro
    st.markdown("### Filtrar documentos")
    col1, col2 = st.columns(2)
    
    with col1:
        if 'tipo' in documentos.columns:
            tipo_filtro = st.multiselect(
                "Filtrar por tipo de documento",
                options=documentos['Tipo de Documento'].unique().tolist(),
                default=[]
            )
    
    with col2:
        if 'fecha' in documentos.columns:
            fecha_min, fecha_max = st.date_input(
                "Rango de fechas",
                value=[datetime.datetime.now().date() - datetime.timedelta(days=30), datetime.datetime.now().date()],
                key="fecha_filtro"
            )
    
    # Aplicar filtros si hay selecciones
    documentos_filtrados = documentos.copy()
    if 'tipo_filtro' in locals() and tipo_filtro:
        documentos_filtrados = documentos_filtrados[documentos_filtrados['Tipo de Documento'].isin(tipo_filtro)]
    
    if 'fecha_min' in locals() and 'fecha_max' in locals():
        # Aquí asumimos que la fecha está en formato dd/mm/yyyy, hay que convertirla primero
        documentos_filtrados['Fecha_dt'] = pd.to_datetime(documentos_filtrados['Fecha'], format='%d/%m/%Y', errors='coerce')
        fecha_min_dt = pd.to_datetime(fecha_min)
        fecha_max_dt = pd.to_datetime(fecha_max)
        documentos_filtrados = documentos_filtrados[
            (documentos_filtrados['Fecha_dt'] >= fecha_min_dt) & 
            (documentos_filtrados['Fecha_dt'] <= fecha_max_dt)
        ]
        documentos_filtrados = documentos_filtrados.drop(columns=['Fecha_dt'])
    
    # Mostrar resultados filtrados si se aplicaron filtros
    if 'tipo_filtro' in locals() and tipo_filtro or ('fecha_min' in locals() and 'fecha_max' in locals()):
        st.markdown("### Resultados filtrados")
        st.dataframe(documentos_filtrados)
    
    # Opción para regenerar un documento
    st.markdown("### Regenerar documento")
    
    # Lista de documentos para seleccionar
    opciones_documentos = [f"{doc['tipo']} - {doc['fecha']} ({doc['codigo']})" for doc in st.session_state['documentos_generados']]
    
    documento_seleccionado = st.selectbox(
        "Seleccione un documento para regenerar",
        options=opciones_documentos,
        index=0 if opciones_documentos else None
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Regenerar PDF"):
            # Obtener ID del documento seleccionado
            indice = opciones_documentos.index(documento_seleccionado)
            id_documento = st.session_state['documentos_generados'][indice]['id']
            
            if id_documento in st.session_state['documentos_datos']:
                datos = st.session_state['documentos_datos'][id_documento]
                
                # Determinar la plantilla basada en los datos disponibles
                plantilla = "Contrato" if 'objeto_contrato' in datos else \
                          "Acuerdo de confidencialidad" if 'duracion' in datos and 'parte_a' in datos else \
                          "Autorización" if 'proposito_autorizacion' in datos else \
                          "Documento en blanco"
                
                # Regenerar PDF
                pdf_buffer = crear_pdf(datos, plantilla)
                
                # Mostrar opción de descarga
                b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="{datos["tipo_documento"].replace(" ", "_")}_{datos["numero_documento"]}.pdf">Descargar documento PDF</a>'
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.success("¡Documento regenerado exitosamente!")
                st.markdown(href, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        if st.button("Ver detalles"):
            # Obtener ID del documento seleccionado
            indice = opciones_documentos.index(documento_seleccionado)
            id_documento = st.session_state['documentos_generados'][indice]['id']
            
            if id_documento in st.session_state['documentos_datos']:
                datos = st.session_state['documentos_datos'][id_documento]
                
                # Mostrar detalles del documento
                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                st.markdown(f"### Detalles del documento: {datos['tipo_documento']}")
                st.markdown(f"**Número de documento:** {datos['numero_documento']}")
                st.markdown(f"**Fecha:** {datos['fecha']}")
                st.markdown(f"**Código de verificación:** {datos['codigo_verificacion']}")
                st.markdown(f"**ID:** {datos['id_documento']}")
                st.markdown(f"**Generado en:** {datos['timestamp_generacion']}")
                
                # Mostrar información de las partes si está disponible
                if 'parte_a' in datos and 'parte_b' in datos:
                    st.markdown("#### Partes involucradas")
                    st.markdown(f"**{datos.get('parte_a', '')}** - Documento: {datos.get('documento_parte_a', 'N/A')}")
                    st.markdown(f"**{datos.get('parte_b', '')}** - Documento: {datos.get('documento_parte_b', 'N/A')}")
                
                # Mostrar información específica según el tipo de documento
                if 'objeto_contrato' in datos:  # Contrato
                    st.markdown("#### Información del contrato")
                    st.markdown(f"**Objeto:** {datos.get('objeto_contrato', 'N/A')}")
                    st.markdown(f"**Duración:** {datos.get('duracion', 'N/A')}")
                    st.markdown(f"**Valor:** {datos.get('valor', 'N/A')}")
                
                elif 'proposito_autorizacion' in datos:  # Autorización
                    st.markdown("#### Información de la autorización")
                    st.markdown(f"**Propósito:** {datos.get('proposito_autorizacion', 'N/A')}")
                    st.markdown(f"**Alcance:** {datos.get('alcance_autorizacion', 'N/A')}")
                    st.markdown(f"**Duración:** {datos.get('duracion', 'N/A')}")
                
                # Mostrar hash del documento
                st.markdown("#### Información de seguridad")
                st.markdown(f"**Hash del documento:** `{datos.get('hash_documento', 'N/A')}`")
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    # Opción para exportar listado de documentos
    st.markdown("### Exportar listado de documentos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Exportar a CSV"):
            # Convertir a CSV
            csv = documentos.to_csv(index=False)
            
            # Convertir a base64 para descarga
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:text/csv;base64,{b64}" download="documentos_generados.csv">Descargar CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
    
    with col2:
        if st.button("Exportar a Excel"):
            # Convertir a Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                documentos.to_excel(writer, sheet_name='Documentos', index=False)
            
            # Convertir a base64 para descarga
            b64 = base64.b64encode(output.getvalue()).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="documentos_generados.xlsx">Descargar Excel</a>'
            st.markdown(href, unsafe_allow_html=True)
    
    # Opción para eliminar documentos
    st.markdown("### Administrar documentos")
    
    if st.button("Eliminar todos los documentos", key="eliminar_todos"):
        confirmacion = st.checkbox("Confirmar eliminación de todos los documentos")
        
        if confirmacion:
            # Eliminar todos los documentos de la sesión
            st.session_state['documentos_generados'] = []
            st.session_state['documentos_datos'] = {}
            st.success("Se han eliminado todos los documentos de la sesión.")
            st.rerun()  # Recargar la página para reflejar los cambios

def guardar_registro_documento(datos_documento):
    """Guarda un registro del documento generado en la sesión"""
    if 'documentos_generados' not in st.session_state:
        st.session_state['documentos_generados'] = []
    
    # Crear registro simplificado para la lista
    registro = {
        'id': datos_documento['id_documento'],
        'tipo': datos_documento['tipo_documento'],
        'fecha': datos_documento['fecha'],
        'codigo': datos_documento['codigo_verificacion'],
        'partes': f"{datos_documento.get('parte_a', '')} - {datos_documento.get('parte_b', '')}",
        'timestamp': datos_documento['timestamp_generacion']
    }
    
    st.session_state['documentos_generados'].append(registro)
    
    # Guardar datos completos por ID
    if 'documentos_datos' not in st.session_state:
        st.session_state['documentos_datos'] = {}
    
    st.session_state['documentos_datos'][datos_documento['id_documento']] = datos_documento

def mostrar_verificador_documentos():
    """Muestra la interfaz para verificar documentos mediante código o ID"""
    st.markdown('<h2 class="sub-header">Verificar Documento</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    Verifique la autenticidad de un documento mediante su código de verificación o ID único. 
    Esto permite confirmar que el documento no ha sido alterado desde su generación.
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Opciones de verificación
    metodo_verificacion = st.radio(
        "Método de verificación",
        ["Código de verificación", "ID de documento", "Escanear código QR"]
    )
    
    if metodo_verificacion == "Código de verificación":
        codigo = st.text_input("Ingrese el código de verificación", max_chars=8)
        if st.button("Verificar por código"):
            if 'documentos_generados' in st.session_state and st.session_state['documentos_generados']:
                # Buscar documento por código
                documento = next((doc for doc in st.session_state['documentos_generados'] 
                                 if doc['codigo'] == codigo), None)
                if documento:
                    mostrar_resultado_verificacion(documento['id'], True)
                else:
                    st.error("Código de verificación no encontrado en esta sesión.")
            else:
                st.error("No hay documentos generados en esta sesión para verificar.")
    
    elif metodo_verificacion == "ID de documento":
        id_doc = st.text_input("Ingrese el ID del documento")
        if st.button("Verificar por ID"):
            if 'documentos_datos' in st.session_state and id_doc in st.session_state['documentos_datos']:
                mostrar_resultado_verificacion(id_doc, True)
            else:
                st.error("ID de documento no encontrado en esta sesión.")
    
    else:  # Escanear código QR
        st.warning("Esta funcionalidad requiere acceso a la cámara y no está disponible en esta versión de demostración.")
        qr_upload = st.file_uploader("Alternativamente, puede subir una imagen del código QR", type=["png", "jpg", "jpeg"])
        if qr_upload is not None:
            st.info("Procesamiento de imágenes QR no disponible en esta versión de demostración.")

def mostrar_resultado_verificacion(id_documento, es_valido):
    """Muestra el resultado de la verificación del documento"""
    if es_valido and id_documento in st.session_state['documentos_datos']:
        datos = st.session_state['documentos_datos'][id_documento]
        
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.success("✅ Documento verificado correctamente")
        st.markdown(f"### {datos['tipo_documento']}")
        st.markdown(f"**Número:** {datos['numero_documento']}")
        st.markdown(f"**Fecha:** {datos['fecha']}")
        st.markdown(f"**Generado:** {datos['timestamp_generacion']}")
        
        # Información de las partes si está disponible
        if 'parte_a' in datos:
            st.markdown(f"**Parte A:** {datos['parte_a']}")
            st.markdown(f"**Parte B:** {datos['parte_b']}")
        
        # Opción para regenerar el PDF
        if st.button("Regenerar PDF"):
            plantilla = "Contrato" if 'objeto_contrato' in datos else \
                       "Acuerdo de confidencialidad" if 'duracion' in datos and 'parte_a' in datos else \
                       "Autorización" if 'proposito_autorizacion' in datos else \
                       "Documento en blanco"
            
            pdf_buffer = crear_pdf(datos, plantilla)
            
            # Convertir a base64 para descarga
            b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="{datos["tipo_documento"].replace(" ", "_")}_{datos["numero_documento"]}.pdf">Descargar documento PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("⚠️ No se pudo verificar el documento. El documento puede haber sido alterado o no estar registrado en esta sesión.")

def mostrar_informacion():
    """Muestra información sobre la aplicación"""
    st.markdown('<h2 class="sub-header">Información sobre la aplicación</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    ### Generador de Documentos para Firma Electrónica
    
    Esta aplicación permite crear documentos legales con elementos de seguridad digital para verificar su autenticidad e integridad. Los documentos generados incluyen:
    
    - Códigos de verificación únicos
    - Hash criptográfico para verificar la integridad
    - Códigos QR para verificación rápida
    - Identificadores únicos
    - Registro de fecha y hora de generación
    
    ### Tipos de documentos disponibles
    
    - **Contratos**: Acuerdos legales entre dos partes
    - **Acuerdos de confidencialidad**: Para proteger información sensible
    - **Autorizaciones**: Permisos legales para realizar acciones específicas
    - **Documentos en blanco**: Para crear documentos personalizados
    
    ### Seguridad
    
    Todos los documentos generados utilizan técnicas criptográficas para garantizar su autenticidad e integridad. El hash del documento permite detectar cualquier alteración no autorizada.
    
    ### Nota importante
    
    Esta es una versión de demostración. En un entorno de producción, los documentos generados se almacenarían en una base de datos segura y se implementarían medidas adicionales de seguridad.
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Información sobre firma electrónica
    st.markdown('<h3 class="sub-header">Sobre la firma electrónica</h3>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    ### ¿Qué es la firma electrónica?
    
    La firma electrónica es un conjunto de datos electrónicos que acompañan a un documento digital y que permiten identificar al firmante de manera inequívoca, asegurando la integridad del documento firmado.
    
    ### Validez legal
    
    En muchos países, la firma electrónica tiene la misma validez legal que una firma manuscrita, siempre que cumpla con ciertos requisitos técnicos y legales. Es importante consultar la legislación específica de cada país.
    
    ### Ventajas
    
    - **Ahorro de tiempo y costos**: Elimina la necesidad de imprimir, firmar físicamente y enviar documentos.
    - **Mayor seguridad**: Los métodos criptográficos utilizados hacen que sea más difícil falsificar una firma electrónica que una manuscrita.
    - **Trazabilidad**: Permite llevar un registro detallado de cuándo y quién firmó un documento.
    - **Sostenibilidad**: Reduce el consumo de papel y otros recursos físicos.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# Función principal de la aplicación
def main():
    st.markdown('<h1 class="main-header">Generador de Documentos para Firma Electrónica</h1>', unsafe_allow_html=True)
    
    # Menú de navegación
    menu = st.sidebar.selectbox(
        "Menú Principal",
        ["Crear Documento", "Documentos Generados", "Verificar Documento", "Información"]
    )
    
    if menu == "Crear Documento":
        mostrar_creador_documentos()
    elif menu == "Documentos Generados":
        mostrar_documentos_generados()
    elif menu == "Verificar Documento":
        mostrar_verificador_documentos()
    else:  # Información
        mostrar_informacion()

# Ejecutar la aplicación
if __name__ == "__main__":
    main()
