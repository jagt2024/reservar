import streamlit as st
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
import base64

def crear_pdf(datos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloStyle',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=1,  # centrado
        spaceAfter=20
    )
    
    subtitulo_style = ParagraphStyle(
        'SubtituloStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=10
    )
    
    normal_style = styles['Normal']
    
    # Elementos del documento
    elementos = []
    
    # Título
    elementos.append(Paragraph("JUSTIFICACIÓN CLÍNICA DOCUMENTADA", titulo_style))
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Fecha
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    elementos.append(Paragraph(f"Fecha: {fecha_actual}", normal_style))
    elementos.append(Spacer(1, 0.1 * inch))
    
    # Datos del paciente
    elementos.append(Paragraph("1. DATOS DEL PACIENTE", subtitulo_style))
    tabla_datos = [
        ["Nombre completo:", datos['nombre_paciente']],
        ["Identificación:", datos['identificacion']],
        ["Edad:", datos['edad']],
        ["Género:", datos['genero']],
        ["EPS/Aseguradora:", datos['eps']]
    ]
    tabla = Table(tabla_datos, colWidths=[2.5*inch, 3.5*inch])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Diagnóstico
    elementos.append(Paragraph("2. DIAGNÓSTICO", subtitulo_style))
    elementos.append(Paragraph(f"Diagnóstico principal: {datos['diagnostico_principal']}", normal_style))
    elementos.append(Paragraph(f"Código CIE-10: {datos['codigo_cie10']}", normal_style))
    if datos['diagnosticos_secundarios']:
        elementos.append(Paragraph(f"Diagnósticos secundarios: {datos['diagnosticos_secundarios']}", normal_style))
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Justificación clínica
    elementos.append(Paragraph("3. JUSTIFICACIÓN CLÍNICA", subtitulo_style))
    elementos.append(Paragraph(datos['justificacion'], normal_style))
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Servicio o procedimiento solicitado
    elementos.append(Paragraph("4. SERVICIO/PROCEDIMIENTO SOLICITADO", subtitulo_style))
    elementos.append(Paragraph(f"Nombre del servicio/procedimiento: {datos['servicio_procedimiento']}", normal_style))
    if datos['codigo_cups']:
        elementos.append(Paragraph(f"Código CUPS: {datos['codigo_cups']}", normal_style))
    elementos.append(Paragraph(f"Cantidad: {datos['cantidad']}", normal_style))
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Médico tratante
    elementos.append(Paragraph("5. MÉDICO TRATANTE", subtitulo_style))
    elementos.append(Paragraph(f"Nombre: {datos['nombre_medico']}", normal_style))
    elementos.append(Paragraph(f"Número de registro médico: {datos['registro_medico']}", normal_style))
    elementos.append(Paragraph(f"Especialidad: {datos['especialidad']}", normal_style))
    elementos.append(Spacer(1, 0.5 * inch))
    
    # Firma
    elementos.append(Paragraph("____________________________", normal_style))
    elementos.append(Paragraph("Firma del médico", normal_style))
    
    # Generar PDF
    doc.build(elementos)
    buffer.seek(0)
    return buffer

def justificacion_clinica():
    #st.set_page_config(page_title="Justificación Clínica Documentada", layout="wide")
    
    #st.title("Generador de Justificación Clínica Documentada")
    
    with st.form("formulario_justificacion"):
        st.header("1. Datos del Paciente")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_paciente = st.text_input("Nombre completo del paciente", "")
            edad = st.text_input("Edad", "")
            eps = st.text_input("EPS/Aseguradora", "")
        
        with col2:
            identificacion = st.text_input("Número de identificación", "")
            genero = st.selectbox("Género", ["", "Masculino", "Femenino", "Otro"])
        
        st.header("2. Diagnóstico")
        diagnostico_principal = st.text_input("Diagnóstico principal", "")
        codigo_cie10 = st.text_input("Código CIE-10", "")
        diagnosticos_secundarios = st.text_area("Diagnósticos secundarios (opcional)", "")
        
        st.header("3. Justificación Clínica")
        justificacion = st.text_area("Justificación clínica detallada", "", height=200)
        
        st.header("4. Servicio o Procedimiento Solicitado")
        servicio_procedimiento = st.text_input("Nombre del servicio/procedimiento", "")
        codigo_cups = st.text_input("Código CUPS (opcional)", "")
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
        
        st.header("5. Médico Tratante")
        nombre_medico = st.text_input("Nombre del médico", "")
        registro_medico = st.text_input("Número de registro médico", "")
        especialidad = st.text_input("Especialidad", "")
        
        submitted = st.form_submit_button("Generar Justificación Clínica")
        
        if submitted:
            if not (nombre_paciente and identificacion and edad and genero and eps and 
                    diagnostico_principal and codigo_cie10 and justificacion and 
                    servicio_procedimiento and cantidad and nombre_medico and 
                    registro_medico and especialidad):
                st.error("Por favor complete todos los campos obligatorios.")
            else:
                datos = {
                    'nombre_paciente': nombre_paciente,
                    'identificacion': identificacion,
                    'edad': edad,
                    'genero': genero,
                    'eps': eps,
                    'diagnostico_principal': diagnostico_principal,
                    'codigo_cie10': codigo_cie10,
                    'diagnosticos_secundarios': diagnosticos_secundarios,
                    'justificacion': justificacion,
                    'servicio_procedimiento': servicio_procedimiento,
                    'codigo_cups': codigo_cups,
                    'cantidad': cantidad,
                    'nombre_medico': nombre_medico,
                    'registro_medico': registro_medico,
                    'especialidad': especialidad
                }
                
                pdf_buffer = crear_pdf(datos)
                b64_pdf = base64.b64encode(pdf_buffer.read()).decode()
                pdf_display = f'<a href="data:application/pdf;base64,{b64_pdf}" download="justificacion_clinica.pdf">Descargar Justificación Clínica (PDF)</a>'
                
                st.success("¡Justificación clínica generada con éxito!")
                st.markdown(pdf_display, unsafe_allow_html=True)
                
                # Vista previa
                st.header("Vista previa")
                st.markdown("""
                **JUSTIFICACIÓN CLÍNICA DOCUMENTADA**
                
                **1. DATOS DEL PACIENTE**
                - Nombre completo: {}
                - Identificación: {}
                - Edad: {}
                - Género: {}
                - EPS/Aseguradora: {}
                
                **2. DIAGNÓSTICO**
                - Diagnóstico principal: {}
                - Código CIE-10: {}
                - Diagnósticos secundarios: {}
                
                **3. JUSTIFICACIÓN CLÍNICA**
                {}
                
                **4. SERVICIO/PROCEDIMIENTO SOLICITADO**
                - Nombre del servicio/procedimiento: {}
                - Código CUPS: {}
                - Cantidad: {}
                
                **5. MÉDICO TRATANTE**
                - Nombre: {}
                - Número de registro médico: {}
                - Especialidad: {}
                """.format(
                    nombre_paciente, identificacion, edad, genero, eps,
                    diagnostico_principal, codigo_cie10, diagnosticos_secundarios,
                    justificacion, servicio_procedimiento, codigo_cups, cantidad,
                    nombre_medico, registro_medico, especialidad
                ))

#if __name__ == "__main__":
#    justificacion_clinica()
