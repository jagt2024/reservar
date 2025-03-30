import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
import pandas as pd
from datetime import date, datetime
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import fpdf
import tempfile
import os

# Maximum retry attempts for connection
MAX_RETRIES = 3

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

def load_credentials_from_toml():
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales: {str(e)}")
        return None

def connect_to_gsheets():
    for intento in range(MAX_RETRIES):
        try:
            # Cargar credenciales desde el archivo .toml
            creds = load_credentials_from_toml()
            if not creds:
                return None

            # Definir el alcance
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            
            # Crear credenciales
            credentials = Credentials.from_service_account_info(creds, scopes=scope)
            
            # Autorizar el cliente
            client = gspread.authorize(credentials)
            
            # Abrir la hoja existente
            spreadsheet = client.open('gestion-reservas-amo')
            
            # Obtener las hojas específicas
            try:
                patients_sheet = spreadsheet.worksheet('historia_clinica')
                evoluciones_sheet = spreadsheet.worksheet('evolucion_paciente')
            except Exception as e:
                st.error(f"Error al acceder a las hojas: {e}")
                return None

            return {
                'historia_clinica': patients_sheet, 
                'evolucion_paciente': evoluciones_sheet
            }
        
        except Exception as e:
            st.error(f"Error al conectar con Google Sheets: {e}")
            return None

def get_patients_data(sheets):
    """Obtener datos de pacientes de la hoja de historia clínica"""
    try:
        patients_data = sheets['historia_clinica'].get_all_records()
        return pd.DataFrame(patients_data)
    except Exception as e:
        st.error(f"Error al obtener datos de pacientes: {e}")
        return pd.DataFrame()

def get_diagnostics_data(sheets):
    """Obtener datos de diagnósticos de la hoja de evolución de paciente"""
    try:
        diagnostics_data = sheets['evolucion_paciente'].get_all_records()
        return pd.DataFrame(diagnostics_data)
    except Exception as e:
        st.error(f"Error al obtener datos de diagnósticos: {e}")
        return pd.DataFrame()


def normalize_id(id_value):
    """Normalizar el ID para comparación"""
    return str(id_value).strip().lower()

def find_patient_by_id(patients_df, patient_id):
    """Encontrar paciente por ID con comparación flexible"""
    normalized_id = normalize_id(patient_id)
    
    # Intentar encontrar el paciente de múltiples maneras
    patient = patients_df[
        patients_df['ID'].apply(normalize_id) == normalized_id
    ]
    
    # Si no se encuentra, intentar búsqueda parcial
    if patient.empty:
        patient = patients_df[
            patients_df['ID'].apply(normalize_id).str.contains(normalized_id)
        ]
    
    return patient

def find_patient_diagnostics(patient_id, diagnostics_df):
    """Encontrar diagnósticos de un paciente específico por ID"""
    normalized_id = normalize_id(patient_id)
    return diagnostics_df[
        diagnostics_df['ID'].apply(normalize_id) == normalized_id
    ]

def add_diagnostic(sheets, patient_id, patient_name, diagnostic_info):
    """Agregar un nuevo diagnóstico"""
    try:
        evoluciones_sheet = sheets['evolucion_paciente']
        
        # Preparar la fila para agregar
        row_to_add = [
            patient_id, 
            patient_name,
            diagnostic_info.get('Sexo', ''),
            diagnostic_info.get('Edad', ''),
            diagnostic_info.get('Motivo Consulta', ''),
            diagnostic_info.get('Resultado Examen', ''),
            diagnostic_info.get('Codigo Diagnostico', ''),
            diagnostic_info.get('Diagnostico', ''),
            diagnostic_info.get('Clasificacion', ''),
            diagnostic_info.get('Fecha Registro', str(datetime.now().date())),
            diagnostic_info.get('Objetivos Tratamiento', ''),
            diagnostic_info.get('Tecnicas', ''),
            diagnostic_info.get('Terapeuta', ''),
            diagnostic_info.get('Medicamentos', ''),
            diagnostic_info.get('Examenes Adicionales', ''),
            diagnostic_info.get('Evoluciones', ''),
            diagnostic_info.get('Avances', ''),
            diagnostic_info.get('Estado Mental', ''),
            diagnostic_info.get('Intervencion', ''),
            diagnostic_info.get('Plan Proxima', ''),
            diagnostic_info.get('Fecha Modificacion', str(datetime.now().date())),
            diagnostic_info.get('Notas', ''),
            diagnostic_info.get('Principal', '')
        ]
        
        evoluciones_sheet.append_row(row_to_add)
        st.success("Diagnóstico agregado exitosamente")
    except Exception as e:
        st.error(f"Error al agregar diagnóstico: {e}")

def update_diagnostic(sheets, actual_row_index, diagnostic_info):
    """Modificar un diagnóstico existente"""
    try:
        evoluciones_sheet = sheets['evolucion_paciente']
        
        # Preparar la lista de valores a actualizar
        values_to_update = [
            diagnostic_info.get('ID', ''), 
            diagnostic_info.get('Nombre', ''),
            diagnostic_info.get('Sexo', ''),
            diagnostic_info.get('Edad', ''),
            diagnostic_info.get('Motivo Consulta', ''),
            diagnostic_info.get('Resultado Examen', ''),
            diagnostic_info.get('Codigo Diagnostico', ''),
            diagnostic_info.get('Diagnostico', ''),
            diagnostic_info.get('Clasificacion', ''),
            diagnostic_info.get('Fecha Registro', ''),
            diagnostic_info.get('Objetivos Tratamiento', ''),
            diagnostic_info.get('Tecnicas', ''),
            diagnostic_info.get('Terapeuta', ''),
            diagnostic_info.get('Medicamentos', ''),
            diagnostic_info.get('Examenes Adicionales', ''),
            diagnostic_info.get('Evoluciones', ''),
            diagnostic_info.get('Avances', ''),
            diagnostic_info.get('Estado Mental', ''),
            diagnostic_info.get('Intervencion', ''),
            diagnostic_info.get('Plan Proxima', ''),
            str(datetime.now().date()),  # Fecha Modificacion actualizada
            diagnostic_info.get('Notas', ''),
            diagnostic_info.get('Principal', '')
        ]
        
        # La fila en la hoja de cálculo comienza en 2 (1 para los encabezados)
        # +2 porque la fila 1 es el encabezado y las filas en gsheets comienzan en 1
        evoluciones_sheet.update(
            values=[values_to_update], 
            range_name=f'A{actual_row_index + 2}:W{actual_row_index + 2}'
        )
        st.success("Diagnóstico actualizado exitosamente")
    except Exception as e:
        st.error(f"Error al actualizar diagnóstico: {e}")


def delete_diagnostic(sheets, actual_row_index):
    """Eliminar un diagnóstico"""
    try:
        evoluciones_sheet = sheets['evolucion_paciente']
        # +2 porque la fila 1 es el encabezado y las filas en gsheets comienzan en 1
        evoluciones_sheet.delete_rows(actual_row_index + 2)
        st.success("Diagnóstico eliminado exitosamente")
    except Exception as e:
        st.error(f"Error al eliminar diagnóstico: {e}")

def generate_diagnostic_pdf(patient_info, diagnostic_info, pdf_type="detalle"):
    """Generar PDF para un diagnóstico específico"""
    try:
        pdf = fpdf.FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Configuración de fuentes
        pdf.set_font("Arial", "B", 16)
        
        # Título según el tipo de PDF
        if pdf_type == "detalle":
            title = f"Detalle de Diagnóstico - {patient_info['Nombre']}"
        elif pdf_type == "historia":
            title = f"Historia Clínica - {patient_info['Nombre']}"
        else:
            title = f"Diagnóstico - {patient_info['Nombre']}"
        
        # Centrar título
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Información básica del paciente
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Información del Paciente", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 7, "ID:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('ID', '')}", ln=True)
        pdf.cell(40, 7, "Nombre:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Nombre', '')}", ln=True)
        pdf.cell(40, 7, "Sexo:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Sexo', '')}", ln=True)
        pdf.cell(40, 7, "Edad:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Edad', '')}", ln=True)
        pdf.ln(5)
        
        # Sección de diagnóstico
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Información de Diagnóstico", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(60, 7, "Fecha Registro:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Fecha Registro', '')}", ln=True)
        pdf.cell(60, 7, "Motivo Consulta:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Motivo Consulta', '')}", ln=True)
        pdf.cell(60, 7, "Código Diagnóstico:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Codigo Diagnostico', '')}", ln=True)
        pdf.cell(60, 7, "Diagnóstico:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Diagnostico', '')}", ln=True)
        pdf.cell(60, 7, "Clasificación:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Clasificacion', '')}", ln=True)
        pdf.cell(60, 7, "Principal:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Principal', '')}", ln=True)
        pdf.ln(5)
        
        # Sección de tratamiento
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Información de Tratamiento", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(60, 7, "Terapeuta:", 0)
        pdf.cell(0, 7, f"{diagnostic_info.get('Terapeuta', '')}", ln=True)
        
        # Campos con posible texto largo - usar MultiCell
        pdf.cell(60, 7, "Objetivos Tratamiento:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Objetivos Tratamiento', '')}")
        
        pdf.cell(60, 7, "Técnicas:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Tecnicas', '')}")
        
        pdf.cell(60, 7, "Medicamentos:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Medicamentos', '')}")
        pdf.ln(5)
        
        # Sección de evolución
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Evolución del Paciente", ln=True)
        pdf.set_font("Arial", "", 10)
        
        pdf.cell(60, 7, "Evoluciones:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Evoluciones', '')}")
        
        pdf.cell(60, 7, "Avances:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Avances', '')}")
        
        pdf.cell(60, 7, "Estado Mental:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Estado Mental', '')}")
        
        pdf.cell(60, 7, "Intervención:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Intervencion', '')}")
        
        pdf.cell(60, 7, "Plan Próxima:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Plan Proxima', '')}")
        pdf.ln(5)
        
        # Sección de información adicional
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Información Adicional", ln=True)
        pdf.set_font("Arial", "", 10)
        
        pdf.cell(60, 7, "Exámenes Adicionales:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Examenes Adicionales', '')}")
        
        pdf.cell(60, 7, "Resultado Examen:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Resultado Examen', '')}")
        
        pdf.cell(60, 7, "Notas:", 0)
        pdf.ln(7)
        pdf.multi_cell(0, 7, f"{diagnostic_info.get('Notas', '')}")
        
        # Pie de página
        pdf.set_y(-30)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 10, f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True, align="C")
        pdf.cell(0, 10, "Confidencial - Solo para uso médico autorizado", ln=True, align="C")
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_path = tmp_file.name
        
        # Guardar PDF en archivo temporal
        pdf.output(tmp_path)
        
        return tmp_path
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")
        return None

def generate_patient_history_pdf(patient_info, all_diagnostics):
    """Generar PDF con el historial completo del paciente"""
    try:
        pdf = fpdf.FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Configuración de fuentes
        pdf.set_font("Arial", "B", 16)
        
        # Título
        title = f"Historia Clínica Completa - {patient_info['Nombre']}"
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Información básica del paciente
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Información del Paciente", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 7, "ID:", 0)
        pdf.cell(0, 7, f"{patient_info['ID']}", ln=True)
        pdf.cell(40, 7, "Nombre:", 0)
        pdf.cell(0, 7, f"{patient_info['Nombre']}", ln=True)
        
        # Si hay otros campos relevantes en patient_info, agregarlos aquí
        if 'Sexo' in patient_info:
            pdf.cell(40, 7, "Sexo:", 0)
            pdf.cell(0, 7, f"{patient_info['Sexo']}", ln=True)
        if 'Edad' in patient_info:
            pdf.cell(40, 7, "Edad:", 0)
            pdf.cell(0, 7, f"{patient_info['Edad']}", ln=True)
        if 'Fecha_Nacimiento' in patient_info:
            pdf.cell(40, 7, "Fecha de Nacimiento:", 0)
            pdf.cell(0, 7, f"{patient_info['Fecha_Nacimiento']}", ln=True)
        
        pdf.ln(5)
        
        # Resumen de diagnósticos
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Resumen de Diagnósticos ({len(all_diagnostics)} registros)", ln=True)
        pdf.ln(2)
        
        # Tabla de resumen
        pdf.set_font("Arial", "B", 9)
        pdf.cell(30, 7, "Fecha", 1)
        pdf.cell(60, 7, "Diagnóstico", 1)
        pdf.cell(40, 7, "Código", 1)
        pdf.cell(60, 7, "Terapeuta", 1, ln=True)
        
        pdf.set_font("Arial", "", 9)
        for idx, diag in all_diagnostics.iterrows():
            pdf.cell(30, 7, f"{diag.get('Fecha Registro', '')}", 1)
            pdf.cell(60, 7, f"{diag.get('Diagnostico', '')[:25]}...", 1)
            pdf.cell(40, 7, f"{diag.get('Codigo Diagnostico', '')}", 1)
            pdf.cell(60, 7, f"{diag.get('Terapeuta', '')}", 1, ln=True)
        
        pdf.ln(10)
        
        # Detalle de cada diagnóstico
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Detalle de Diagnósticos", ln=True)
        
        for idx, diag in all_diagnostics.iterrows():
            # Agregar una nueva página para cada diagnóstico (excepto el primero)
            if idx > 0:
                pdf.add_page()
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 10, f"Diagnóstico {idx+1} - {diag.get('Fecha Registro', '')}", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # Datos principales
            pdf.set_font("Arial", "B", 10)
            pdf.cell(60, 7, "Diagnóstico:", 0)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 7, f"{diag.get('Diagnostico', '')}", ln=True)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(60, 7, "Código Diagnóstico:", 0)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 7, f"{diag.get('Codigo Diagnostico', '')}", ln=True)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(60, 7, "Motivo Consulta:", 0)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 7, f"{diag.get('Motivo Consulta', '')}", ln=True)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(60, 7, "Terapeuta:", 0)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 7, f"{diag.get('Terapeuta', '')}", ln=True)
            
            # Evolución
            pdf.ln(5)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 7, "Evolución:", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 7, f"{diag.get('Evoluciones', '')}")
            
            pdf.ln(3)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 7, "Avances:", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 7, f"{diag.get('Avances', '')}")
            
            # Indicar si hay más páginas
            if idx < len(all_diagnostics) - 1:
                pdf.set_font("Arial", "I", 8)
                pdf.cell(0, 10, "Continúa en la siguiente página...", ln=True, align="C")
        
        # Pie de página
        pdf.set_y(-30)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 10, f"Historia clínica generada el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True, align="C")
        pdf.cell(0, 10, "Confidencial - Solo para uso médico autorizado", ln=True, align="C")
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_path = tmp_file.name
        
        # Guardar PDF en archivo temporal
        pdf.output(tmp_path)
        
        return tmp_path
    except Exception as e:
        st.error(f"Error al generar PDF del historial completo: {e}")
        return None

def gestion_diagnostico():
    st.title("Gestión de Diagnósticos de Pacientes")
    
    # Conectar a Google Sheets
    sheets = connect_to_gsheets()
    if not sheets:
        st.error("No se pudo conectar a las hojas de cálculo")
        return
    
    # Obtener datos de pacientes y diagnósticos
    patients_df = get_patients_data(sheets)
    diagnostics_df = get_diagnostics_data(sheets)
    
    # Sección de búsqueda de paciente horizontal
    st.subheader("Buscar Paciente")
    
    # Dividir en columnas la sección de búsqueda
    search_col1, search_col2, search_col3 = st.columns([2, 3, 2])
    
    with search_col1:
        patient_id = st.text_input("Ingrese Identificacion del Paciente")
    
    patient_name = ""
    patient_found = False
    
    if patient_id:
        patient_info = find_patient_by_id(patients_df, patient_id)
        
        if not patient_info.empty:
            try:
                patient_name = patient_info.iloc[0]['Nombre']
                patient_found = True
                
                with search_col2:
                    st.success(f"Paciente: {patient_name}")
                
                # Encontrar diagnósticos del paciente
                patient_diagnostics = find_patient_diagnostics(patient_id, diagnostics_df)
                
                if not patient_diagnostics.empty:
                    # Almacenar los índices originales de las filas en la hoja de cálculo
                    original_indices = patient_diagnostics.index.tolist()
                    
                    # Selector de diagnóstico específico
                    diagnostic_options = [
                        f"Diagnóstico {idx+1} - {diag['Fecha Registro']}" 
                        for idx, diag in patient_diagnostics.iterrows()
                    ]
                    
                    with search_col3:
                        selected_option_index = st.selectbox(
                            "Seleccionar Diagnóstico", 
                            range(len(diagnostic_options)), 
                            format_func=lambda x: diagnostic_options[x],
                            key="diagnostic_selector"
                        )
                    
                    # Obtener el índice real en la hoja de cálculo
                    actual_row_index = original_indices[selected_option_index]
                    
                    # Opciones de acción en horizontal
                    st.write("---")
                    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                    
                    with action_col1:
                        visualizar = st.button("Visualizar", use_container_width=True)
                    with action_col2:
                        modificar = st.button("Modificar", use_container_width=True)
                    with action_col3:
                        eliminar = st.button("Eliminar", use_container_width=True)
                    with action_col4:
                        agregar = st.button("Agregar Nuevo", use_container_width=True)
                    
                    # Establecer la acción seleccionada
                    action = None
                    if visualizar:
                        action = "Visualizar"
                    elif modificar:
                        action = "Modificar"
                    elif eliminar:
                        action = "Eliminar"
                    elif agregar:
                        action = "Agregar Nuevo"
                    
                    # Si no hay acción seleccionada y no hay una previa, usar Visualizar por defecto
                    if action is None:
                        if 'current_action' not in st.session_state:
                            action = "Visualizar"
                            st.session_state.current_action = action
                        else:
                            action = st.session_state.current_action
                    else:
                        st.session_state.current_action = action
                    
                    st.write("---")
                    
                    # Contenedor principal para mostrar los diagnósticos
                    main_container = st.container()
                    
                    # Obtener el diagnóstico seleccionado
                    selected_diagnostic = patient_diagnostics.iloc[selected_option_index]
                    
                    # Mostrar el detalle del diagnóstico si la acción es "Visualizar"
                    if action == "Visualizar":
                        with main_container:
                            st.subheader(f"Detalle de Diagnóstico")
                            
                            # Botón para generar PDF del diagnóstico actual
                            pdf_col1, pdf_col2, pdf_col3 = st.columns([2, 1, 2])
                            with pdf_col2:
                                if st.button("Generar PDF", use_container_width=True):
                                    pdf_path = generate_diagnostic_pdf(
                                        patient_info.iloc[0], 
                                        selected_diagnostic, 
                                        "detalle"
                                    )
                                    if pdf_path:
                                        with open(pdf_path, "rb") as pdf_file:
                                            pdf_bytes = pdf_file.read()
                                        
                                        st.download_button(
                                            label="Descargar PDF",
                                            data=pdf_bytes,
                                            file_name=f"diagnostico_{patient_id}_{selected_diagnostic.get('Fecha Registro', 'actual')}.pdf",
                                            mime="application/pdf"
                                        )
                                        # Eliminar archivo temporal después de la descarga
                                        try:
                                            os.unlink(pdf_path)
                                        except:
                                            pass
                            
                            # Mostrar diagnóstico en formato horizontal
                            col1, col2, col3 = st.columns(3)
                            
                            # Columna 1: Información básica
                            with col1:
                                st.markdown("**Información Básica**")
                                st.write(f"**ID:** {selected_diagnostic.get('ID', '')}")
                                st.write(f"**Nombre:** {selected_diagnostic.get('Nombre', '')}")
                                st.write(f"**Sexo:** {selected_diagnostic.get('Sexo', '')}")
                                st.write(f"**Edad:** {selected_diagnostic.get('Edad', '')}")
                                st.write(f"**Fecha Registro:** {selected_diagnostic.get('Fecha Registro', '')}")
                                st.write(f"**Fecha Modificación:** {selected_diagnostic.get('Fecha Modificacion', '')}")
                            
                            # Columna 2: Diagnóstico y clasificación
                            with col2:
                                st.markdown("**Diagnóstico**")
                                st.write(f"**Motivo Consulta:** {selected_diagnostic.get('Motivo Consulta', '')}")
                                st.write(f"**Código Diagnóstico:** {selected_diagnostic.get('Codigo Diagnostico', '')}")
                                st.write(f"**Diagnóstico:** {selected_diagnostic.get('Diagnostico', '')}")
                                st.write(f"**Clasificación:** {selected_diagnostic.get('Clasificacion', '')}")
                                st.write(f"**Resultado Examen:** {selected_diagnostic.get('Resultado Examen', '')}")
                                st.write(f"**Principal:** {selected_diagnostic.get('Principal', '')}")
                            
                            # Columna 3: Tratamiento
                            with col3:
                                st.markdown("**Tratamiento**")
                                st.write(f"**Terapeuta:** {selected_diagnostic.get('Terapeuta', '')}")
                                st.write(f"**Objetivos Tratamiento:** {selected_diagnostic.get('Objetivos Tratamiento', '')}")
                                st.write(f"**Técnicas:** {selected_diagnostic.get('Tecnicas', '')}")
                                st.write(f"**Medicamentos:** {selected_diagnostic.get('Medicamentos', '')}")
                            
                            # Segunda fila de columnas para más información
                            col4, col5, col6 = st.columns(3)
                            
                            # Columna 4: Evolución
                            with col4:
                                st.markdown("**Evolución**")
                                st.write(f"**Evoluciones:** {selected_diagnostic.get('Evoluciones', '')}")
                                st.write(f"**Avances:** {selected_diagnostic.get('Avances', '')}")
                            
                            # Columna 5: Estado y plan
                            with col5:
                                st.markdown("**Estado y Plan**")
                                st.write(f"**Estado Mental:** {selected_diagnostic.get('Estado Mental', '')}")
                                st.write(f"**Intervención:** {selected_diagnostic.get('Intervencion', '')}")
                                st.write(f"**Plan Próxima:** {selected_diagnostic.get('Plan Proxima', '')}")
                            
                            # Columna 6: Adicionales
                            with col6:
                                st.markdown("**Información Adicional**")
                                st.write(f"**Exámenes Adicionales:** {selected_diagnostic.get('Examenes Adicionales', '')}")
                                st.write(f"**Notas:** {selected_diagnostic.get('Notas', '')}")
                    
                    # Mostrar formularios según la acción seleccionada
                    if action == "Modificar":
                        with main_container:
                            st.subheader("Modificar Diagnóstico")
                            with st.form(key="modify_diagnostic_form"):
                                form_fields = [
                                    'Sexo', 'Edad', 'Motivo Consulta', 'Resultado Examen', 
                                    'Codigo Diagnostico', 'Diagnostico', 'Clasificacion', 
                                    'Objetivos Tratamiento', 'Tecnicas', 'Terapeuta', 
                                    'Medicamentos', 'Examenes Adicionales', 'Evoluciones', 
                                    'Avances', 'Estado Mental', 'Intervencion', 'Plan Proxima', 
                                    'Notas', 'Principal'
                                ]
                                
                                # Crear campos de formulario con valores actuales
                                modified_diagnostic = selected_diagnostic.to_dict()
                                
                                # Organizar campos en columnas
                                col1, col2, col3 = st.columns(3)
                                
                                # Distribuir campos en las columnas
                                for i, field in enumerate(form_fields):
                                    col_num = i % 3
                                    if col_num == 0:
                                        with col1:
                                            modified_diagnostic[field] = st.text_input(
                                                field, 
                                                value=selected_diagnostic.get(field, ''),
                                                key=f"modify_{field}"
                                            )
                                    elif col_num == 1:
                                        with col2:
                                            modified_diagnostic[field] = st.text_input(
                                                field, 
                                                value=selected_diagnostic.get(field, ''),
                                                key=f"modify_{field}"
                                            )
                                    else:
                                        with col3:
                                            modified_diagnostic[field] = st.text_input(
                                                field, 
                                                value=selected_diagnostic.get(field, ''),
                                                key=f"modify_{field}"
                                            )
                                
                                submit_modify = st.form_submit_button("Guardar Modificación")
                                
                                if submit_modify:
                                    # Actualizar diagnóstico
                                    modified_diagnostic['ID'] = patient_id
                                    modified_diagnostic['Nombre'] = patient_name
                                    update_diagnostic(
                                        sheets, 
                                        actual_row_index,  # Usar el índice real de la fila
                                        modified_diagnostic
                                    )
                                    st.rerun()
                    
                    elif action == "Eliminar":
                        with main_container:
                            st.subheader("Eliminar Diagnóstico")
                            
                            col1, col2, col3 = st.columns([3, 2, 3])
                            
                            with col2:
                                st.warning(f"¿Está seguro que desea eliminar el diagnóstico del {selected_diagnostic.get('Fecha Registro', '')}?")
                                
                                # Mostrar información resumida del diagnóstico a eliminar
                                st.info(f"Diagnóstico: {selected_diagnostic.get('Diagnostico', '')}")
                                st.info(f"Motivo: {selected_diagnostic.get('Motivo Consulta', '')}")
                                
                                if st.button("Confirmar Eliminación", key="confirm_delete"):
                                    delete_diagnostic(sheets, actual_row_index)  # Usar el índice real de la fila
                                    st.rerun()
                    
                    elif action == "Agregar Nuevo":
                        with main_container:
                            st.subheader("Agregar Nuevo Diagnóstico")
                            with st.form(key="add_diagnostic_form"):
                                form_fields = [
                                    'Sexo', 'Edad', 'Motivo Consulta', 'Resultado Examen', 
                                    'Codigo Diagnostico', 'Diagnostico', 'Clasificacion', 
                                    'Objetivos Tratamiento', 'Tecnicas', 'Terapeuta', 
                                    'Medicamentos', 'Examenes Adicionales', 'Evoluciones', 
                                    'Avances', 'Estado Mental', 'Intervencion', 'Plan Proxima', 
                                    'Notas', 'Principal'
                                ]
                                
                                # Crear campos de formulario en blanco
                                new_diagnostic = {}
                                
                                # Organizar campos en columnas
                                col1, col2, col3 = st.columns(3)
                                
                                # Distribuir campos en las columnas
                                for i, field in enumerate(form_fields):
                                    col_num = i % 3
                                    if col_num == 0:
                                        with col1:
                                            new_diagnostic[field] = st.text_input(field, key=f"add_{field}")
                                    elif col_num == 1:
                                        with col2:
                                            new_diagnostic[field] = st.text_input(field, key=f"add_{field}")
                                    else:
                                        with col3:
                                            new_diagnostic[field] = st.text_input(field, key=f"add_{field}")
                                
                                submit_add = st.form_submit_button("Guardar Nuevo Diagnóstico")
                                
                                if submit_add:
                                    # Agregar nuevo diagnóstico
                                    add_diagnostic(
                                        sheets, 
                                        patient_id, 
                                        patient_name, 
                                        new_diagnostic
                                    )
                                    st.rerun()
                
                else:
                    st.info("No hay diagnósticos para este paciente")
                    
                    # Opción de agregar primer diagnóstico
                    if st.button("Agregar Primer Diagnóstico", key="add_first"):
                        st.subheader("Agregar Primer Diagnóstico")
                        with st.form(key="first_diagnostic_form"):
                            form_fields = [
                                'Sexo', 'Edad', 'Motivo Consulta', 'Resultado Examen', 
                                'Codigo Diagnostico', 'Diagnostico', 'Clasificacion', 
                                'Objetivos Tratamiento', 'Tecnicas', 'Terapeuta', 
                                'Medicamentos', 'Examenes Adicionales', 'Evoluciones', 
                                'Avances', 'Estado Mental', 'Intervencion', 'Plan Proxima', 
                                'Notas', 'Principal'
                            ]
                            
                            # Crear campos de formulario en blanco
                            new_diagnostic = {}
                            
                            # Organizar campos en columnas
                            col1, col2, col3 = st.columns(3)
                            
                            # Distribuir campos en las columnas
                            for i, field in enumerate(form_fields):
                                col_num = i % 3
                                if col_num == 0:
                                    with col1:
                                        new_diagnostic[field] = st.text_input(field, key=f"first_{field}")
                                elif col_num == 1:
                                    with col2:
                                        new_diagnostic[field] = st.text_input(field, key=f"first_{field}")
                                else:
                                    with col3:
                                        new_diagnostic[field] = st.text_input(field, key=f"first_{field}")
                            
                            submit_add = st.form_submit_button("Guardar Primer Diagnóstico")
                            
                            if submit_add:
                                # Agregar primer diagnóstico
                                add_diagnostic(
                                    sheets, 
                                    patient_id, 
                                    patient_name, 
                                    new_diagnostic
                                )
                                st.rerun()
            except SystemError as err:
                clear_session_state()
            except Exception as e:
                clear_session_state()
                  
        else:
            with search_col2:
                st.error("No se encontró un paciente con ese ID")

#if __name__ == "__main__":
#    gestion_diagnostico()