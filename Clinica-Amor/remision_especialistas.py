import streamlit as st
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
import io
import base64

def crear_pdf_remision(datos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    subtitulo_style = ParagraphStyle(
        'SubtituloStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=5
    )
    
    normal_style = styles['Normal']
    
    # Elementos del documento
    elementos = []
    
    # Encabezado con información de la institución remitente
    encabezado_data = [
        [Paragraph(f"<b>{datos['institucion_remitente']}</b>", normal_style)],
        [Paragraph(f"NIT: {datos['nit_institucion']}", normal_style)],
        [Paragraph(f"Dirección: {datos['direccion_institucion']}", normal_style)],
        [Paragraph(f"Teléfono: {datos['telefono_institucion']}", normal_style)]
    ]
    
    tabla_encabezado = Table(encabezado_data, colWidths=[6*inch])
    tabla_encabezado.setStyle(TableStyle([
        ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Título
    elementos.append(Paragraph("REMISIÓN A ESPECIALISTA", titulo_style))
    elementos.append(Spacer(1, 0.1 * inch))
    
    # Fecha y número de remisión
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    fecha_remision = datos['fecha_remision'] if datos['fecha_remision'] else fecha_actual
    
    fecha_data = [
        ["Fecha de Remisión:", fecha_remision],
        ["Número de Remisión:", datos['numero_remision']],
        ["Prioridad:", datos['prioridad']]
    ]
    
    tabla_fecha = Table(fecha_data, colWidths=[2*inch, 4*inch])
    tabla_fecha.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla_fecha)
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Datos del paciente
    elementos.append(Paragraph("1. DATOS DEL PACIENTE", subtitulo_style))
    tabla_paciente = [
        ["Nombre completo:", datos['nombre_paciente']],
        ["Identificación:", datos['identificacion_paciente']],
        ["Fecha de nacimiento:", datos['fecha_nacimiento']],
        ["Edad:", datos['edad_paciente']],
        ["Género:", datos['genero_paciente']],
        ["Teléfono:", datos['telefono_paciente']],
        ["Dirección:", datos['direccion_paciente']],
        ["EPS/Aseguradora:", datos['eps_paciente']]
    ]
    tabla = Table(tabla_paciente, colWidths=[2*inch, 4*inch])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Información clínica
    elementos.append(Paragraph("2. INFORMACIÓN CLÍNICA", subtitulo_style))
    elementos.append(Paragraph(f"<b>Diagnóstico principal:</b> {datos['diagnostico_principal']}", normal_style))
    elementos.append(Paragraph(f"<b>Código CIE-10:</b> {datos['codigo_cie10']}", normal_style))
    
    if datos['diagnosticos_secundarios']:
        elementos.append(Paragraph(f"<b>Diagnósticos secundarios:</b> {datos['diagnosticos_secundarios']}", normal_style))
    
    elementos.append(Spacer(1, 0.1 * inch))
    elementos.append(Paragraph("<b>Resumen de historia clínica:</b>", normal_style))
    elementos.append(Paragraph(datos['resumen_historia'], normal_style))
    
    if datos['medicamentos_actuales']:
        elementos.append(Spacer(1, 0.1 * inch))
        elementos.append(Paragraph(f"<b>Medicamentos actuales:</b> {datos['medicamentos_actuales']}", normal_style))
    
    if datos['alergias']:
        elementos.append(Paragraph(f"<b>Alergias:</b> {datos['alergias']}", normal_style))
    
    elementos.append(Spacer(1, 0.2 * inch))
    
    # Información de la remisión
    elementos.append(Paragraph("3. REMISIÓN", subtitulo_style))
    tabla_remision = [
        ["Especialidad solicitada:", datos['especialidad_solicitada']],
        ["Servicio solicitado:", datos['servicio_solicitado']],
        ["Motivo de remisión:", datos['motivo_remision']]
    ]
    tabla = Table(tabla_remision, colWidths=[2*inch, 4*inch])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.1 * inch))
    
    elementos.append(Paragraph("<b>Observaciones adicionales:</b>", normal_style))
    elementos.append(Paragraph(datos['observaciones'], normal_style))
    elementos.append(Spacer(1, 0.3 * inch))
    
    # Médico remitente
    elementos.append(Paragraph("4. MÉDICO REMITENTE", subtitulo_style))
    tabla_medico = [
        ["Nombre del médico:", datos['nombre_medico']],
        ["Especialidad:", datos['especialidad_medico']],
        ["Registro médico:", datos['registro_medico']],
        ["Teléfono de contacto:", datos['telefono_medico']]
    ]
    tabla = Table(tabla_medico, colWidths=[2*inch, 4*inch])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.4 * inch))
    
    # Firma
    elementos.append(Paragraph("____________________________", normal_style))
    elementos.append(Paragraph("Firma del médico remitente", normal_style))
    
    # Nota legal
    elementos.append(Spacer(1, 0.3 * inch))
    nota_style = ParagraphStyle(
        'NotaStyle',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER
    )
    elementos.append(Paragraph("Este documento tiene validez como remisión médica según los lineamientos establecidos por el Ministerio de Salud.", nota_style))
    
    # Generar PDF
    doc.build(elementos)
    buffer.seek(0)
    return buffer

def remision_especialistas():
    #st.set_page_config(page_title="Generador de Remisiones a Especialistas", layout="wide")
    
    #st.title("Generador de Remisiones a Especialistas")
    st.write("Complete el siguiente formulario para generar una remisión médica a especialista.")
    
    # Sección para guardar las remisiones
    if 'remisiones' not in st.session_state:
        st.session_state.remisiones = []
    
    # Tabs para diferentes funcionalidades
    tab1, tab2 = st.tabs(["Crear Remisión", "Historial de Remisiones"])
    
    with tab1:
        with st.form("formulario_remision"):
            st.header("Institución Remitente")
            col1, col2 = st.columns(2)
            
            with col1:
                institucion_remitente = st.text_input("Nombre de la institución", "")
                direccion_institucion = st.text_input("Dirección", "")
            
            with col2:
                nit_institucion = st.text_input("NIT", "")
                telefono_institucion = st.text_input("Teléfono", "")
            
            st.header("Información de la Remisión")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                fecha_remision = st.date_input("Fecha de remisión", datetime.datetime.now())
                fecha_remision = fecha_remision.strftime("%d/%m/%Y")
            
            with col2:
                numero_remision = st.text_input("Número de remisión", "")
            
            with col3:
                prioridad = st.selectbox("Prioridad", ["Normal", "Urgente", "Prioritaria"])
            
            st.header("Datos del Paciente")
            col1, col2 = st.columns(2)
            
            with col1:
                nombre_paciente = st.text_input("Nombre completo del paciente", "")
                fecha_nacimiento = st.date_input("Fecha de nacimiento", datetime.date(1980, 1, 1))
                fecha_nacimiento = fecha_nacimiento.strftime("%d/%m/%Y")
                genero_paciente = st.selectbox("Género", ["", "Masculino", "Femenino", "Otro"])
                direccion_paciente = st.text_input("Dirección", "", key="dir_paciente")
            
            with col2:
                identificacion_paciente = st.text_input("Número de identificación", "")
                edad_paciente = st.text_input("Edad", "")
                telefono_paciente = st.text_input("Teléfono", "", key="tel_paciente")
                eps_paciente = st.text_input("EPS/Aseguradora", "")
            
            st.header("Información Clínica")
            col1, col2 = st.columns(2)
            
            with col1:
                diagnostico_principal = st.text_input("Diagnóstico principal", "")
                diagnosticos_secundarios = st.text_input("Diagnósticos secundarios (opcional)", "")
                alergias = st.text_input("Alergias (opcional)", "")
            
            with col2:
                codigo_cie10 = st.text_input("Código CIE-10", "")
                medicamentos_actuales = st.text_input("Medicamentos actuales (opcional)", "")
            
            resumen_historia = st.text_area("Resumen de historia clínica", "", height=150)
            
            st.header("Información de la Remisión")
            col1, col2 = st.columns(2)
            
            with col1:
                especialidad_solicitada = st.text_input("Especialidad solicitada", "")
            
            with col2:
                servicio_solicitado = st.text_input("Servicio solicitado", "")
            
            motivo_remision = st.text_area("Motivo de remisión", "", height=100)
            observaciones = st.text_area("Observaciones adicionales (opcional)", "", height=100)
            
            st.header("Médico Remitente")
            col1, col2 = st.columns(2)
            
            with col1:
                nombre_medico = st.text_input("Nombre del médico", "")
                registro_medico = st.text_input("Registro médico", "")
            
            with col2:
                especialidad_medico = st.text_input("Especialidad", "")
                telefono_medico = st.text_input("Teléfono de contacto", "")
            
            submitted = st.form_submit_button("Generar Remisión")
            
            if submitted:
                campos_requeridos = [
                    (institucion_remitente, "Nombre de la institución"),
                    (nit_institucion, "NIT de la institución"),
                    (direccion_institucion, "Dirección de la institución"),
                    (telefono_institucion, "Teléfono de la institución"),
                    (numero_remision, "Número de remisión"),
                    (nombre_paciente, "Nombre del paciente"),
                    (identificacion_paciente, "Identificación del paciente"),
                    (edad_paciente, "Edad del paciente"),
                    (diagnostico_principal, "Diagnóstico principal"),
                    (codigo_cie10, "Código CIE-10"),
                    (resumen_historia, "Resumen de historia clínica"),
                    (especialidad_solicitada, "Especialidad solicitada"),
                    (motivo_remision, "Motivo de remisión"),
                    (nombre_medico, "Nombre del médico"),
                    (especialidad_medico, "Especialidad del médico"),
                    (registro_medico, "Registro médico")
                ]
                
                campos_faltantes = [campo[1] for campo in campos_requeridos if not campo[0]]
                
                if campos_faltantes:
                    st.error(f"Por favor complete los siguientes campos obligatorios: {', '.join(campos_faltantes)}")
                else:
                    datos = {
                        'institucion_remitente': institucion_remitente,
                        'nit_institucion': nit_institucion,
                        'direccion_institucion': direccion_institucion,
                        'telefono_institucion': telefono_institucion,
                        'fecha_remision': fecha_remision,
                        'numero_remision': numero_remision,
                        'prioridad': prioridad,
                        'nombre_paciente': nombre_paciente,
                        'identificacion_paciente': identificacion_paciente,
                        'fecha_nacimiento': fecha_nacimiento,
                        'edad_paciente': edad_paciente,
                        'genero_paciente': genero_paciente,
                        'telefono_paciente': telefono_paciente,
                        'direccion_paciente': direccion_paciente,
                        'eps_paciente': eps_paciente,
                        'diagnostico_principal': diagnostico_principal,
                        'codigo_cie10': codigo_cie10,
                        'diagnosticos_secundarios': diagnosticos_secundarios,
                        'resumen_historia': resumen_historia,
                        'medicamentos_actuales': medicamentos_actuales,
                        'alergias': alergias,
                        'especialidad_solicitada': especialidad_solicitada,
                        'servicio_solicitado': servicio_solicitado,
                        'motivo_remision': motivo_remision,
                        'observaciones': observaciones,
                        'nombre_medico': nombre_medico,
                        'especialidad_medico': especialidad_medico,
                        'registro_medico': registro_medico,
                        'telefono_medico': telefono_medico
                    }
                    
                    pdf_buffer = crear_pdf_remision(datos)
                    b64_pdf = base64.b64encode(pdf_buffer.read()).decode()
                    pdf_display = f'<a href="data:application/pdf;base64,{b64_pdf}" download="remision_{numero_remision}.pdf">Descargar Remisión a Especialista (PDF)</a>'
                    
                    # Guardar en historial
                    st.session_state.remisiones.append({
                        'id': len(st.session_state.remisiones) + 1,
                        'fecha': fecha_remision,
                        'numero': numero_remision,
                        'paciente': nombre_paciente,
                        'especialidad': especialidad_solicitada,
                        'medico': nombre_medico,
                        'pdf_b64': b64_pdf
                    })
                    
                    st.success("¡Remisión generada con éxito!")
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    # Vista previa
                    st.header("Vista previa")
                    vista_previa_remision(datos)
    
    with tab2:
        if not st.session_state.remisiones:
            st.info("No hay remisiones generadas en esta sesión.")
        else:
            st.header("Remisiones Generadas")
            for remision in st.session_state.remisiones:
                with st.expander(f"Remisión #{remision['numero']} - {remision['paciente']} - {remision['fecha']}"):
                    st.write(f"**Paciente:** {remision['paciente']}")
                    st.write(f"**Especialidad:** {remision['especialidad']}")
                    st.write(f"**Médico remitente:** {remision['medico']}")
                    st.markdown(f'<a href="data:application/pdf;base64,{remision["pdf_b64"]}" download="remision_{remision["numero"]}.pdf">Descargar PDF</a>', unsafe_allow_html=True)

def vista_previa_remision(datos):
    st.markdown(f"""
    <div style="border: 1px solid grey; padding: 20px;">
        <div style="text-align: center; border: 1px solid black; padding: 10px; background-color: #f0f0f0;">
            <b>{datos['institucion_remitente']}</b><br>
            NIT: {datos['nit_institucion']}<br>
            Dirección: {datos['direccion_institucion']}<br>
            Teléfono: {datos['telefono_institucion']}
        </div>
        
        <h2 style="text-align: center;">REMISIÓN A ESPECIALISTA</h2>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Fecha de Remisión:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['fecha_remision']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Número de Remisión:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['numero_remision']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Prioridad:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['prioridad']}</td>
            </tr>
        </table>
        
        <h3>1. DATOS DEL PACIENTE</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Nombre completo:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['nombre_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Identificación:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['identificacion_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Fecha de nacimiento:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['fecha_nacimiento']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Edad:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['edad_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Género:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['genero_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Teléfono:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['telefono_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Dirección:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['direccion_paciente']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>EPS/Aseguradora:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['eps_paciente']}</td>
            </tr>
        </table>
        
        <h3>2. INFORMACIÓN CLÍNICA</h3>
        <p><b>Diagnóstico principal:</b> {datos['diagnostico_principal']}</p>
        <p><b>Código CIE-10:</b> {datos['codigo_cie10']}</p>
        {f"<p><b>Diagnósticos secundarios:</b> {datos['diagnosticos_secundarios']}</p>" if datos['diagnosticos_secundarios'] else ""}
        <p><b>Resumen de historia clínica:</b><br>{datos['resumen_historia']}</p>
        {f"<p><b>Medicamentos actuales:</b> {datos['medicamentos_actuales']}</p>" if datos['medicamentos_actuales'] else ""}
        {f"<p><b>Alergias:</b> {datos['alergias']}</p>" if datos['alergias'] else ""}
        
        <h3>3. REMISIÓN</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Especialidad solicitada:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['especialidad_solicitada']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Servicio solicitado:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['servicio_solicitado']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Motivo de remisión:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['motivo_remision']}</td>
            </tr>
        </table>
        <p><b>Observaciones adicionales:</b><br>{datos['observaciones']}</p>
        
        <h3>4. MÉDICO REMITENTE</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Nombre del médico:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['nombre_medico']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Especialidad:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['especialidad_medico']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Registro médico:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['registro_medico']}</td>
            </tr>
            <tr>
                <td style="background-color: #f0f0f0; border: 1px solid grey; padding: 5px;"><b>Teléfono de contacto:</b></td>
                <td style="border: 1px solid grey; padding: 5px;">{datos['telefono_medico']}</td>
            </tr>
        </table>
        
        <p style="margin-top: 30px; text-align: center;">____________________________<br>Firma del médico remitente</p>
        
        <p style="margin-top: 30px; text-align: center; font-size: 10px;">Este documento tiene validez como remisión médica según los lineamientos establecidos por el Ministerio de Salud.</p>
    </div>
    """, unsafe_allow_html=True)

#if __name__ == "__main__":
#    remision_especialistas()
