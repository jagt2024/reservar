import streamlit as st
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import base64
import os

def crear_pdf_certificado(datos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1*inch, bottomMargin=1*inch, leftMargin=1*inch, rightMargin=1*inch)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloStyle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.navy
    )
    
    subtitulo_style = ParagraphStyle(
        'SubtituloStyle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=15,
        textColor=colors.navy
    )
    
    contenido_style = ParagraphStyle(
        'ContenidoStyle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=20
    )
    
    fecha_style = ParagraphStyle(
        'FechaStyle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    firma_style = ParagraphStyle(
        'FirmaStyle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER
    )
    
    # Elementos del documento
    elementos = []
    
    # Logo (opcional)
    if datos['usar_logo'] and datos['./assets-amo/logo-clinica.png']:
        try:
            logo = Image(datos['./assets-amo/logo-clinica.png'])
            # Ajustar tamaño del logo
            logo.drawHeight = 1 * inch
            logo.drawWidth = 1 * inch
            elementos.append(logo)
        except:
            pass  # No hacer nada si el logo no se puede cargar
    
    # Título
    elementos.append(Paragraph(f"CERTIFICADO DE ASISTENCIA", titulo_style))
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Subtítulo (organización)
    elementos.append(Paragraph(f"{datos['nombre_organizacion']}", subtitulo_style))
    elementos.append(Spacer(1, 0.3 * inch))
    
    # Contenido del certificado
    texto_certificado = f"""
    Por medio de la presente, <b>{datos['nombre_organizacion']}</b> certifica que:
    <br/><br/>
    <b>{datos['nombre_asistente']}</b> con identificación número <b>{datos['identificacion']}</b>,
    asistió a <b>{datos['nombre_evento']}</b> {datos['tipo_evento'].lower()}, realizado el día {datos['fecha_evento']}
    """
    
    if datos['hora_inicio'] and datos['hora_fin']:
        texto_certificado += f", en horario de {datos['hora_inicio']} a {datos['hora_fin']} horas"
    
    if datos['duracion']:
        texto_certificado += f", con una duración total de {datos['duracion']} horas"
    
    if datos['lugar']:
        texto_certificado += f", en {datos['lugar']}"
    
    texto_certificado += "."
    
    if datos['contenido_adicional']:
        texto_certificado += f"<br/><br/>{datos['contenido_adicional']}"
    
    elementos.append(Paragraph(texto_certificado, contenido_style))
    elementos.append(Spacer(1, 0.4 * inch))
    
    # Fecha del certificado
    fecha_actual = datos['fecha_certificado'] if datos['fecha_certificado'] else datetime.datetime.now().strftime("%d de %B de %Y")
    elementos.append(Paragraph(f"Se expide el presente certificado el {fecha_actual}.", fecha_style))
    elementos.append(Spacer(1, 0.5 * inch))
    
    # Firma
    elementos.append(Paragraph("_________________________________", firma_style))
    elementos.append(Spacer(1, 0.1 * inch))
    elementos.append(Paragraph(f"{datos['nombre_firmante']}", firma_style))
    elementos.append(Paragraph(f"{datos['cargo_firmante']}", firma_style))
    
    # Generar PDF
    doc.build(elementos)
    buffer.seek(0)
    return buffer

def certificado_asistencia():
    #st.set_page_config(page_title="Generador de Certificados de Asistencia", layout="wide")
    
    #st.title("Generador de Certificados de Asistencia")
    st.write("Complete el siguiente formulario para generar certificados de asistencia en formato PDF.")
    
    with st.form("formulario_certificado"):
        st.header("Datos de la Organización")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_organizacion = st.text_input("Nombre de la organización o institución", "")
            usar_logo = st.checkbox("Incluir logo de la organización")
            logo_path = st.text_input("Ruta del archivo de logo (opcional)", "", disabled=not usar_logo)
            
        with col2:
            nombre_firmante = st.text_input("Nombre de quien firma el certificado", "")
            cargo_firmante = st.text_input("Cargo de quien firma", "")
        
        st.header("Datos del Evento")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            nombre_evento = st.text_input("Nombre del evento", "")
            tipo_evento = st.selectbox("Tipo de evento", ["al curso", "a la conferencia", "al taller", "al seminario", "al congreso", "a la capacitación", "a la jornada", "al simposio", "a la reunión", "al evento"])
            
        with col2:
            fecha_evento = st.date_input("Fecha del evento", datetime.datetime.now())
            lugar = st.text_input("Lugar del evento (opcional)", "")
            
        with col3:
            hora_inicio = st.text_input("Hora de inicio (opcional)", "")
            hora_fin = st.text_input("Hora de finalización (opcional)", "")
            duracion = st.text_input("Duración en horas (opcional)", "")
        
        st.header("Datos del Asistente")
        
        # Opción para generar múltiples certificados
        modo_multiple = st.checkbox("Generar múltiples certificados")
        
        if modo_multiple:
            asistentes_data = st.text_area(
                "Ingrese los datos de los asistentes (un asistente por línea, formato: Nombre completo,Número de identificación)", 
                height=150,
                help="Ejemplo:\nJuan Pérez,1234567890\nMaría García,0987654321"
            )
            asistentes_lista = []
            for linea in asistentes_data.split("\n"):
                if "," in linea:
                    nombre, id = linea.split(",", 1)
                    asistentes_lista.append((nombre.strip(), id.strip()))
        else:
            nombre_asistente = st.text_input("Nombre completo del asistente", "")
            identificacion = st.text_input("Número de identificación", "")
        
        contenido_adicional = st.text_area("Contenido adicional (opcional)", "", help="Información adicional que desee incluir en el certificado")
        fecha_certificado = st.text_input("Fecha de expedición del certificado (opcional)", "", help="Dejar en blanco para usar la fecha actual")
        
        submitted = st.form_submit_button("Generar Certificado(s)")
        
        if submitted:
            if modo_multiple:
                if not (nombre_organizacion and nombre_firmante and cargo_firmante and 
                        nombre_evento and asistentes_lista):
                    st.error("Por favor complete todos los campos obligatorios.")
                else:
                    st.success(f"Generando {len(asistentes_lista)} certificados...")
                    
                    for i, (nombre, id) in enumerate(asistentes_lista):
                        datos = {
                            'nombre_organizacion': nombre_organizacion,
                            'usar_logo': usar_logo,
                            'logo_path': logo_path,
                            'nombre_firmante': nombre_firmante,
                            'cargo_firmante': cargo_firmante,
                            'nombre_evento': nombre_evento,
                            'tipo_evento': tipo_evento,
                            'fecha_evento': fecha_evento.strftime("%d de %B de %Y"),
                            'lugar': lugar,
                            'hora_inicio': hora_inicio,
                            'hora_fin': hora_fin,
                            'duracion': duracion,
                            'nombre_asistente': nombre,
                            'identificacion': id,
                            'contenido_adicional': contenido_adicional,
                            'fecha_certificado': fecha_certificado
                        }
                        
                        pdf_buffer = crear_pdf_certificado(datos)
                        b64_pdf = base64.b64encode(pdf_buffer.read()).decode()
                        nombre_archivo = f"certificado_{nombre.replace(' ', '_')}.pdf"
                        pdf_display = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{nombre_archivo}">Descargar Certificado para {nombre}</a>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                        
                        # Vista previa sólo para el primero
                        if i == 0:
                            st.header("Vista previa del primer certificado")
                            vista_previa(datos)
            else:
                if not (nombre_organizacion and nombre_firmante and cargo_firmante and 
                        nombre_evento and nombre_asistente and identificacion):
                    st.error("Por favor complete todos los campos obligatorios.")
                else:
                    datos = {
                        'nombre_organizacion': nombre_organizacion,
                        'usar_logo': usar_logo,
                        'logo_path': logo_path,
                        'nombre_firmante': nombre_firmante,
                        'cargo_firmante': cargo_firmante,
                        'nombre_evento': nombre_evento,
                        'tipo_evento': tipo_evento,
                        'fecha_evento': fecha_evento.strftime("%d de %B de %Y"),
                        'lugar': lugar,
                        'hora_inicio': hora_inicio,
                        'hora_fin': hora_fin,
                        'duracion': duracion,
                        'nombre_asistente': nombre_asistente,
                        'identificacion': identificacion,
                        'contenido_adicional': contenido_adicional,
                        'fecha_certificado': fecha_certificado
                    }
                    
                    pdf_buffer = crear_pdf_certificado(datos)
                    b64_pdf = base64.b64encode(pdf_buffer.read()).decode()
                    pdf_display = f'<a href="data:application/pdf;base64,{b64_pdf}" download="certificado_asistencia.pdf">Descargar Certificado de Asistencia (PDF)</a>'
                    
                    st.success("¡Certificado generado con éxito!")
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    # Vista previa
                    st.header("Vista previa")
                    vista_previa(datos)

def vista_previa(datos):
    st.markdown(f"""
    <div style="border: 2px solid navy; padding: 20px; text-align: center;">
        <h2 style="color: navy;">CERTIFICADO DE ASISTENCIA</h2>
        <h3 style="color: navy;">{datos['nombre_organizacion']}</h3>
        <p style="text-align: justify; font-size: 16px;">
            Por medio de la presente, <b>{datos['nombre_organizacion']}</b> certifica que:
            <br/><br/>
            <b>{datos['nombre_asistente']}</b> con identificación número <b>{datos['identificacion']}</b>,
            asistió a <b>{datos['nombre_evento']}</b> {datos['tipo_evento'].lower()}, realizado el día {datos['fecha_evento']}
            {f", en horario de {datos['hora_inicio']} a {datos['hora_fin']} horas" if datos['hora_inicio'] and datos['hora_fin'] else ""}
            {f", con una duración total de {datos['duracion']} horas" if datos['duracion'] else ""}
            {f", en {datos['lugar']}" if datos['lugar'] else ""}.
            <br/><br/>
            {datos['contenido_adicional'] if datos['contenido_adicional'] else ""}
        </p>
        <p>
            Se expide el presente certificado el {datos['fecha_certificado'] if datos['fecha_certificado'] else datetime.datetime.now().strftime("%d de %B de %Y")}.
        </p>
        <br/><br/>
        <p>_________________________________<br/>
        <b>{datos['nombre_firmante']}</b><br/>
        {datos['cargo_firmante']}</p>
    </div>
    """, unsafe_allow_html=True)

#if __name__ == "__main__":
#    certificado_asistencia()
