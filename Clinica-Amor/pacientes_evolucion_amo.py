import streamlit as st
import pandas as pd
import numpy as np
import uuid
import datetime
#from datetime import datetime
import json
import time
import toml
import gspread
#from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
#import matplotlib.pyplot as plt
import altair as alt
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO

st.cache_data.clear()
st.cache_resource.clear()

# Constantes para reintentos
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión de Evoluciones de Pacientes",
#    page_icon="🧠",
#    layout="wide"
#)

# Funciones de conexión y carga de datos
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

# Función para conectar con Google Sheets
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
            except HttpError as error:
                if error.resp.status == 429:  # Error de cuota excedida
                    if intento < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** intento)
                        st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                        time.sleep(delay)
                        continue
                    else:
                        st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
                else:
                    st.error(f"Error de la API: {str(error)}")
                return None
            except Exception as e:
                st.error(f"Error al acceder a la hoja de historia clínica: {e}")    
                return None

            try:
                evoluciones_sheet = spreadsheet.worksheet('evolucion_paciente')
            except HttpError as error:
                if error.resp.status == 429:  # Error de cuota excedida
                    if intento < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** intento)
                        st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                        time.sleep(delay)
                        continue
                    else:
                        st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
                else:
                    st.error(f"Error de la API: {str(error)}")
                return None
            except Exception as e:
                st.error(f"Error al acceder a la hoja de evoluciones: {e}")
                return None

            return {'historia_clinica': patients_sheet, 'evolucion_paciente': evoluciones_sheet}
        
        except Exception as e:
            st.error(f"Error al conectar con Google Sheets: {e}")
            return None

# Cargar datos de pacientes
def load_patient_data(sheets):
    try:
        # Obtener datos de historia clínica
        patients_data = sheets['historia_clinica'].get_all_records()
        
        # Obtener datos de evoluciones
        evoluciones_data = sheets['evolucion_paciente'].get_all_records()
        
        # Crear diccionario para organizar los datos
        data = {}
        
        # Procesar datos de pacientes
        for patient in patients_data:
            # Verificar que el ID existe y es válido
            if 'ID' not in patient or not patient['ID']:
                continue
                
            patient_id = str(patient['ID'])  # Convertir a string para evitar problemas con tipos de datos
            data[patient_id] = {
                'id': patient_id,
                'nombre': patient.get('Nombre', 'Sin nombre'),
                'sexo': patient.get('Sexo', ''),
                'edad': patient.get('Edad', ''),
                'motivo_consulta': patient.get('Motivo Consulta', ''),
                'resultado_examen': patient.get('Resultado Examen', ''),
                'diagnostico': patient.get('Diagnostico', ''),
                'fecha_registro': patient.get('Fecha Consulta', ''),
                'terapeuta': patient.get('Terapeuta', ''),
                'evoluciones': []
            }
            
            # Convertir campos de texto a estructuras de datos si existen
            if 'Objetivos Tratamiento' in patient and patient['Objetivos Tratamiento']:
                try:
                    data[patient_id]['objetivos_tratamiento'] = json.loads(patient['Objetivos Tratamiento'])
                except:
                    data[patient_id]['objetivos_tratamiento'] = []
            else:
                data[patient_id]['objetivos_tratamiento'] = []
                
            if 'Tecnicas' in patient and patient['Tecnicas']:
                try:
                    data[patient_id]['tecnicas'] = json.loads(patient['Tecnicas'])
                except:
                    data[patient_id]['tecnicas'] = []
            else:
                data[patient_id]['tecnicas'] = []
        
        # Procesar evoluciones
        for evolucion in evoluciones_data:
            # Verificar que el ID existe y es válido
            if 'ID' not in evolucion or not evolucion['ID']:
                continue
                
            patient_id = str(evolucion['ID'])  # Convertir a string para consistencia
            if patient_id in data:
                # Convertir campos de texto a estructuras de datos
                tecnicas = []
                if 'Tecnicas' in evolucion and evolucion['Tecnicas']:
                    try:
                        tecnicas = json.loads(evolucion['Tecnicas'])
                    except:
                        pass
                
                objetivos = []
                if 'Objetivos Tratamiento' in evolucion and evolucion['Objetivos Tratamiento']:
                    try:
                        objetivos = json.loads(evolucion['Objetivos Tratamiento'])
                    except:
                        pass
                
                # Crear objeto de evolución
                evolucion_obj = {
                    'fecha_registro': evolucion.get('Fecha Registro', ''),
                    'motivo_consulta': evolucion.get('Motivo Consulta', ''),
                    'estado_mental': evolucion.get('Estado Mental', ''),
                    'tecnicas': tecnicas,
                    'intervencion': evolucion.get('Intervencion', ''),
                    'avances': evolucion.get('Avances', ''),
                    'objetivos_tratamiento': objetivos,
                    'plan_proxima': evolucion.get('Plan Proxima', ''),
                    'fecha_modificacion': evolucion.get('Fecha Modificacion', '')
                }
                
                # Agregar evolución al paciente
                data[patient_id]['evoluciones'].append(evolucion_obj)
        
        return data
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return {}

# Función para guardar evolución en Google Sheets
def save_evolution_to_sheets(sheets, evolution_data):
    try:
        # Preparar datos para guardar en formato de fila
        row = [
            evolution_data['ID'],
            evolution_data['Nombre'],
            evolution_data['Sexo'],
            evolution_data['Edad'],
            evolution_data['Motivo Consulta'],
            evolution_data['Resultado Examen'],
            evolution_data['Diagnostico'],
            evolution_data['Fecha Registro'],
            json.dumps(evolution_data['Objetivos Tratamiento']),
            json.dumps(evolution_data['Tecnicas']),
            evolution_data['Terapeuta'],
            evolution_data.get('Evoluciones', ''),
            evolution_data['Avances'],
            evolution_data['Estado Mental'],
            evolution_data['Intervencion'],
            evolution_data['Plan Proxima'],
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        # Añadir fila a la hoja de evoluciones
        sheets['evolucion_paciente'].append_row(row)
        return True
    except Exception as e:
        st.error(f"Error al guardar evolución: {e}")
        return False

# Función para obtener las técnicas terapéuticas disponibles
def get_tecnicas_terapeuticas():
    return [
        "Reestructuración cognitiva",
            "Exposición en vivo",
            "Exposición en imaginación",
            "Entrenamiento en habilidades sociales",
            "Técnicas de relajación",
            "Activación conductual",
            "Mindfulness",
            "Entrenamiento en solución de problemas",
            "Psicoeducación",
            "Terapia de procesamiento emocional",
            "Terapia interpersonal",
            "Terapia narrativa",
            "Terapia centrada en la compasión",
            "Estrategias de afrontamiento",
            "Otra",
            "Terapia Cognitivo-Conductual (TCC)",
            "Resolución de Problemas",
            "Psicodrama",
            "Terapia de Aceptación y Compromiso (ACT)",
            "EMDR",
            "Terapia Sistémica",
            "Terapia Psicodinámica" 
    ]

# Función para crear y descargar PDF
def create_pdf(data, content_type="ficha_paciente"):
    """
    Crea un archivo PDF con la información del paciente o evoluciones.
    
    Args:
        data (dict): Datos del paciente o evolución
        content_type (str): Tipo de contenido ("ficha_paciente", "evolucion", "historia", "test")
    
    Returns:
        str: Enlace HTML para descargar el PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # Centrado
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=6
    )
    normal_style = styles['Normal']
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=normal_style,
        fontName='Helvetica-Bold',
        fontSize=11
    )
    
    # Lista de elementos para el PDF
    elements = []
    
    # Contenido según tipo
    if content_type == "ficha_paciente":
        # Título
        elements.append(Paragraph(f"Ficha de Paciente:", title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Información básica
        info_data = [
            ["ID:", data.get('id', 'N/A')],  # This uses 'N/A' if 'id' is missing
            ["Nombre:", data.get('nombre', '')],
            ["Diagnóstico:", data.get('diagnostico', '')],
            ["Sexo:", data.get('sexo','')],
            ["Edad:", data.get('edad','')],
            ["Terapeuta:", data.get('terapeuta','')],
            ["Fecha Registro:", data.get('recha_registro','')],
            ["Motivo Consulta:", data.get('motivo_consulta','')],
            ["Resultado Examen:", data.get('resultado_examen','')],
            ["Objetivos Tratamiento:", data.get('objetivos_trrattamiento','')],
            ["Estado Mental:", data.get('estado_mental','')],
            ["Tecnicas:", data.get('tecnicas','')],
            ["Intervencion:", data.get('intervencion','')],
            ["Avances:", data.get('avances','')],
            ["Objetivos Tratamiento:", data.get('objetivos_tratamiento','')],
            ["Plan Proxima:", data.get('plan_proxima','')]

        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # Motivo de consulta
        elements.append(Paragraph("Motivo de Consulta Inicial:", heading_style))
        elements.append(Paragraph(data.get('motivo_consulta', 'No registrado'), normal_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Resultado examen
        elements.append(Paragraph("Resultado Examen:", heading_style))
        elements.append(Paragraph(data.get('resultado_examen', 'No se ha registrado resultado del examen.'), normal_style))
        ##elements.append(Paragraph(data.get('resultado_examen'), normal_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Diagnóstico
        elements.append(Paragraph("Diagnóstico:", heading_style))
        elements.append(Paragraph(data.get('diagnostico', 'No se ha registrado diagnostico'), normal_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Objetivos de tratamiento
        elements.append(Paragraph("Objetivos de Tratamiento:", heading_style))
        if data.get('objetivos_tratamiento'):
            for i, obj in enumerate(data.get('objetivos_tratamiento')):
                elements.append(Paragraph(f"{i+1}. {obj.get('texto', '')} - Progreso: {obj.get('progreso', 0)}%", normal_style))
        else:
            elements.append(Paragraph("No se han definido objetivos de tratamiento.", normal_style))
        
        elements.append(Spacer(1, 0.25*inch))
        
        # Técnicas
        elements.append(Paragraph("Técnicas Terapéuticas:", heading_style))
        if data.get('tecnicas'):
            elements.append(Paragraph(", ".join(data.get('tecnicas','No se ha registrado ttecnicas')), normal_style))
        else:
            elements.append(Paragraph("No se han definido técnicas terapéuticas.", normal_style))
    
    elif content_type == "evolucion":
        # Título para la evolución
        evolucion = data['evolucion']
        elements.append(Paragraph(f"Evolución del Paciente: {data['nombre']}", title_style))
        elements.append(Paragraph(f"Fecha: {evolucion['fecha_registro']}", heading_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Motivo de consulta
        elements.append(Paragraph("Motivo de Consulta / Presentación Actual:", label_style))
        elements.append(Paragraph(evolucion.get('motivo_consulta', ''), normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Estado mental
        elements.append(Paragraph("Estado Mental:", label_style))
        elements.append(Paragraph(evolucion.get('estado_mental', ''), normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Técnicas aplicadas
        elements.append(Paragraph("Técnicas Aplicadas:", label_style))
        tecnicas = evolucion.get('tecnicas', [])
        if tecnicas:
            elements.append(Paragraph(", ".join(tecnicas), normal_style))
        else:
            elements.append(Paragraph("No se registraron técnicas", normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Intervención
        elements.append(Paragraph("Intervención:", label_style))
        elements.append(Paragraph(evolucion.get('intervencion', ''), normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Avances
        elements.append(Paragraph("Avances:", label_style))
        elements.append(Paragraph(evolucion.get('avances', ''), normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Objetivos de tratamiento
        elements.append(Paragraph("Objetivos de Tratamiento:", label_style))
        objetivos = evolucion.get('objetivos_tratamiento', [])
        if objetivos:
            for obj in objetivos:
                elements.append(Paragraph(f"- {obj.get('texto', '')}: {obj.get('progreso', 0)}%", normal_style))
        else:
            elements.append(Paragraph("No se registraron objetivos", normal_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # Plan para próxima sesión
        elements.append(Paragraph("Plan para Próxima Sesión:", label_style))
        elements.append(Paragraph(evolucion.get('plan_proxima', ''), normal_style))
    
    elif content_type == "historial":
        # Título para el historial
        elements.append(Paragraph(f"Historial de Evoluciones - Paciente: {data['nombre']}", title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Datos básicos del paciente
        info_data = [
            ["ID:", data['id']],
            ["Nombre:", data['nombre']],
            ["Diagnóstico:", data['diagnostico']]
        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # Evoluciones ordenadas por fecha
        evoluciones_ordenadas = sorted(
            data['evoluciones'], 
            key=lambda x: datetime.datetime.strptime(x['fecha_registro'], "%Y-%m-%d") if x['fecha_registro'] else datetime.datetime.min
        )
        
        for i, evolucion in enumerate(evoluciones_ordenadas):
            elements.append(Paragraph(f"Evolución {i+1} - {evolucion['fecha_registro']}", heading_style))
            
            # Motivo de consulta
            elements.append(Paragraph("Motivo de Consulta:", label_style))
            elements.append(Paragraph(evolucion.get('motivo_consulta', ''), normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Estado mental
            elements.append(Paragraph("Estado Mental:", label_style))
            elements.append(Paragraph(evolucion.get('estado_mental', ''), normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Técnicas aplicadas
            elements.append(Paragraph("Técnicas Aplicadas:", label_style))
            tecnicas = evolucion.get('tecnicas', [])
            if tecnicas:
                elements.append(Paragraph(", ".join(tecnicas), normal_style))
            else:
                elements.append(Paragraph("No se registraron técnicas", normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Intervención
            elements.append(Paragraph("Intervención:", label_style))
            elements.append(Paragraph(evolucion.get('intervencion', ''), normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Avances
            elements.append(Paragraph("Avances:", label_style))
            elements.append(Paragraph(evolucion.get('avances', ''), normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Objetivos de tratamiento
            elements.append(Paragraph("Objetivos de Tratamiento:", label_style))
            objetivos = evolucion.get('objetivos_tratamiento', [])
            if objetivos:
                for obj in objetivos:
                    elements.append(Paragraph(f"- {obj.get('texto', '')}: {obj.get('progreso', 0)}%", normal_style))
            else:
                elements.append(Paragraph("No se registraron objetivos", normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Plan para próxima sesión
            elements.append(Paragraph("Plan para Próxima Sesión:", label_style))
            elements.append(Paragraph(evolucion.get('plan_proxima', ''), normal_style))
            
            # Separador entre evoluciones
            if i < len(evoluciones_ordenadas) - 1:
                elements.append(Spacer(1, 0.25*inch))
                elements.append(Paragraph("_" * 50, normal_style))
                elements.append(Spacer(1, 0.25*inch))
                
    elif content_type == "test":
        # Título para el test
        elements.append(Paragraph(f"Resultados del Test - Paciente: {data['nombre']}", title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Datos básicos del paciente
        info_data = [
            ["ID:", data['id']],
            ["Nombre:", data['nombre']],
            ["Test:", data['test']['test_selected']],
            ["Fecha:", data['test']['fecha_test']]
        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # Mostrar puntuación si existe
        if 'puntuacion' in data['test']:
            elements.append(Paragraph(f"Puntuación: {data['test']['puntuacion']}", heading_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Interpretación si existe
            if data['test'].get('interpretacion'):
                elements.append(Paragraph(f"Interpretación: {data['test']['interpretacion']}", heading_style))
                elements.append(Spacer(1, 0.15*inch))
        
        # Resultados si existe
        if data['test'].get('resultados'):
            elements.append(Paragraph("Resultados:", heading_style))
            elements.append(Paragraph(data['test']['resultados'], normal_style))
            elements.append(Spacer(1, 0.15*inch))
        
        # Observaciones
        if data['test'].get('observaciones'):
            elements.append(Paragraph("Observaciones:", heading_style))
            elements.append(Paragraph(data['test']['observaciones'], normal_style))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el PDF como bytes
    pdf = buffer.getvalue()
    buffer.close()
    
    # Codificar a base64
   
    b64_pdf = base64.b64encode(pdf).decode()
    
    # Determinar el nombre del archivo
    if content_type == "ficha_paciente":
        pdf_filename = f"ficha_paciente_{'ID'}_{datetime.date.today().strftime('%Y%m%d')}.pdf"
    elif content_type == "evolucion":
        pdf_filename = f"evolucion_{data['nombre']}_{data['evolucion']['fecha_registro']}.pdf"
    elif content_type == "historial":
        pdf_filename = f"historial_{data['nombre']}_{datetime.date.today().strftime('%Y%m%d')}.pdf"
    elif content_type == "test":
        pdf_filename = f"test_{data['test']['test_selected']}_{data['nombre']}_{data['test']['fecha_test']}.pdf"
    
    # Crear enlace para descargar
    href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{pdf_filename}">📥 Descargar PDF</a>'
    
    return href

def save_test_to_sheets(patient_id, test_data):
    """
    Guarda los datos del test del paciente en Google Sheets.
    
    Args:
        patient_id (str): ID del paciente
        test_data (dict): Datos del test a guardar
    
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
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
        
        # Intentar obtener la hoja "test_paciente", si no existe, crearla
        try:
            worksheet = spreadsheet.worksheet("test_paciente")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="test_paciente", rows=1000, cols=8)
            # Añadir encabezados
            headers = ["Timestamp", "ID", "Nombre Test", "Fecha Aplicación", 
                       "Puntuación", "Interpretación", "Resultados", "Observaciones"]
            worksheet.append_row(headers)
        
        # Preparar los datos para insertar
        fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determinar la interpretación si es un test con puntuación numérica
        interpretacion = ""
        if "puntuacion" in test_data:
            if test_data["test_selected"] == "Escala de Depresión de Beck (BDI)":
                puntuacion = test_data["puntuacion"]
                if puntuacion <= 13:
                    interpretacion = "Depresión mínima"
                elif puntuacion <= 19:
                    interpretacion = "Depresión leve"
                elif puntuacion <= 28:
                    interpretacion = "Depresión moderada"
                else:
                    interpretacion = "Depresión grave"
            elif test_data["test_selected"] == "Inventario de Ansiedad de Beck (BAI)":
                puntuacion = test_data["puntuacion"]
                if puntuacion <= 7:
                    interpretacion = "Ansiedad mínima"
                elif puntuacion <= 15:
                    interpretacion = "Ansiedad leve"
                elif puntuacion <= 25:
                    interpretacion = "Ansiedad moderada"
                else:
                    interpretacion = "Ansiedad grave"
        
        # Crear la fila para insertar en la hoja
        row_data = [
            fecha_actual,                             # Timestamp
            patient_id,                               # ID del paciente
            test_data["test_selected"],               # Nombre del test
            test_data.get("fecha_test", ""),          # Fecha de aplicación
            test_data.get("puntuacion", ""),          # Puntuación (si aplica)
            interpretacion,                           # Interpretación (si aplica)
            test_data.get("resultados", ""),          # Resultados (para tests sin puntuación numérica)
            test_data.get("observaciones", "")        # Observaciones
        ]
        
        # Añadir la fila a la hoja
        worksheet.append_row(row_data)
        
        return True
        
    except Exception as e:
        import streamlit as st
        st.error(f"Error al guardar los datos: {str(e)}")
        return False

# Función para mostrar escalas y tests
def display_scales_and_tests(patient_id, data):
    import streamlit as st
    import datetime
    
    st.markdown('<p class="sub-header">Escalas y Tests</p>', unsafe_allow_html=True)
    
    # Selector de test
    test_options = [
        "Escala de Depresión de Beck (BDI)",
        "Inventario de Ansiedad de Beck (BAI)",
        "Escala de Ansiedad de Hamilton",
        "Escala de Depresión de Hamilton",
        "MMPI-2",
        "SCL-90-R",
        "Escala de Calidad de Vida (WHOQOL-BREF)",
        "Otro"
    ]
    
    col1, col2 = st.columns(2)
    with col1:
        test_selected = st.selectbox("Seleccionar Test", test_options)
    
    with col2:
        fecha_test = st.date_input("Fecha de aplicación", datetime.date.today())
    
    # Variables para almacenar los resultados
    puntuacion = None
    resultados = None
    interpretacion = None
    
    # Resultados del test específicos para cada tipo
    if test_selected == "Escala de Depresión de Beck (BDI)" or test_selected == "Inventario de Ansiedad de Beck (BAI)":
        puntuacion = st.slider("Puntuación", 0, 63, 0)
        
        # Interpretación del BDI
        if test_selected == "Escala de Depresión de Beck (BDI)":
            if puntuacion <= 13:
                interpretacion = "Depresión mínima"
            elif puntuacion <= 19:
                interpretacion = "Depresión leve"
            elif puntuacion <= 28:
                interpretacion = "Depresión moderada"
            else:
                interpretacion = "Depresión grave"
        # Interpretación del BAI
        else:
            if puntuacion <= 7:
                interpretacion = "Ansiedad mínima"
            elif puntuacion <= 15:
                interpretacion = "Ansiedad leve"
            elif puntuacion <= 25:
                interpretacion = "Ansiedad moderada"
            else:
                interpretacion = "Ansiedad grave"
        
        st.info(f"Interpretación: {interpretacion}")
    else:
        resultados = st.text_area("Resultados del test", placeholder="Introduzca los resultados del test aplicado...")
    
    observaciones = st.text_area("Observaciones", placeholder="Añada observaciones relevantes sobre la aplicación o resultados del test...")
    
    # Botón para guardar test
    if st.button("Guardar Test"):
        # Preparar los datos para guardar
        test_data = {
            "test_selected": test_selected,
            "fecha_test": fecha_test.strftime("%Y-%m-%d"),
            "observaciones": observaciones
        }
        
        # Añadir datos específicos según el tipo de test
        if puntuacion is not None:
            test_data["puntuacion"] = puntuacion
        if resultados is not None:
            test_data["resultados"] = resultados
        
        # Llamar a la función para guardar en Google Sheets
        if save_test_to_sheets(patient_id, test_data):
            st.success("El Test guardado correctamente")

            # Generar PDF y crear botón de descarga
            pdf_bytes =create_pdf(data, content_type="ficha_paciente")
            st.download_button(
               label="Descargar Test (PDF)",
               data=pdf_bytes,
               file_name=f"test_{patient_id}.pdf",
               mime="application/pdf"
            )

        else:
            st.error("No se pudo guardar el test. Revise los logs para más detalles.")

# Función para visualizar el seguimiento de objetivos
def display_objectives_tracking(patient_id, data):
    st.markdown('<p class="sub-header">Seguimiento de Objetivos</p>', unsafe_allow_html=True)
    
    # Verificar si hay evoluciones y objetivos
    if not data[patient_id].get('evoluciones'):
        st.info("No hay evoluciones registradas para este paciente.")
        return
    
    # Recopilar datos de objetivos de todas las evoluciones
    all_objectives = {}
    evolution_dates = []
    
    for evol in data[patient_id]['evoluciones']:
        if 'fecha_registro' in evol and 'objetivos_tratamiento' in evol:
            fecha = evol['fecha_registro']
            evolution_dates.append(fecha)
            
            for obj in evol.get('objetivos_tratamiento', []):
                objetivo_texto = obj.get('texto', '')
                if objetivo_texto:
                    if objetivo_texto not in all_objectives:
                        all_objectives[objetivo_texto] = {}
                    
                    all_objectives[objetivo_texto][fecha] = obj.get('progreso', 0)
    
    if not all_objectives:
        st.info("No hay objetivos definidos en las evoluciones.")
        return
    
    # Ordenar fechas cronológicamente
    evolution_dates = sorted(list(set(evolution_dates)))
    
    # Crear dataframe para visualización
    for objetivo, progresos in all_objectives.items():
        st.markdown(f"**Objetivo:** {objetivo}")
        
        # Crear datos para el gráfico
        chart_data = []
        for fecha in evolution_dates:
            if fecha in progresos:
                chart_data.append({"fecha": fecha, "progreso": progresos[fecha]})
            else:
                # Buscar el último valor conocido
                last_known = 0
                for prev_fecha in sorted([f for f in progresos.keys() if f <= fecha]):
                    last_known = progresos[prev_fecha]
                chart_data.append({"fecha": fecha, "progreso": last_known})
        
        df = pd.DataFrame(chart_data)
        
        # Crear gráfico con Altair
        if not df.empty and len(df) > 1:
            chart = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X('fecha:T', title='Fecha'),
                y=alt.Y('progreso:Q', title='Progreso (%)', scale=alt.Scale(domain=[0, 100])),
                tooltip=['fecha:T', 'progreso:Q']
            ).properties(
                height=200
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.write(f"Progreso actual: {df['progreso'].iloc[-1]}%" if not df.empty else "Sin datos de progreso")
        
        st.markdown("---")

# Función para mostrar el historial de evoluciones
def display_evolution_history(patient_id, data):
    st.markdown('<p class="sub-header">Historial de Evoluciones</p>', unsafe_allow_html=True)
    
    evoluciones = data[patient_id].get('evoluciones', [])
    if not evoluciones:
        st.info("No hay evoluciones registradas para este paciente.")
        return
    
    # Ordenar evoluciones por fecha (más recientes primero)
    evoluciones_ordenadas = sorted(
        evoluciones, 
        key=lambda x: datetime.datetime.strptime(x['fecha_registro'], "%Y-%m-%d") if x['fecha_registro'] else datetime.datetime.min,
        reverse=True
    )
    
    for i, evolucion in enumerate(evoluciones_ordenadas):
        with st.expander(f"Evolución {evolucion['fecha_registro']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Fecha:** {evolucion['fecha_registro']}")
            with col2:
                if evolucion.get('fecha_modificacion'):
                    st.markdown(f"**Última modificación:** {evolucion['fecha_modificacion']}")
            
            st.markdown(f"**Motivo de Consulta:**")
            st.markdown(f"<div class='highlight'>{evolucion.get('motivo_consulta', '')}</div>", unsafe_allow_html=True)
            
            st.markdown(f"**Estado Mental:**")
            st.markdown(f"<div class='highlight'>{evolucion.get('estado_mental', '')}</div>", unsafe_allow_html=True)
            
            st.markdown(f"**Técnicas Aplicadas:**")
            tecnicas = evolucion.get('tecnicas', [])
            if tecnicas:
                st.markdown(f"<div class='highlight'>{', '.join(tecnicas)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='highlight'>No se registraron técnicas</div>", unsafe_allow_html=True)
            
            st.markdown(f"**Intervención:**")
            st.markdown(f"<div class='highlight'>{evolucion.get('intervencion', '')}</div>", unsafe_allow_html=True)
            
            st.markdown(f"**Avances:**")
            st.markdown(f"<div class='highlight'>{evolucion.get('avances', '')}</div>", unsafe_allow_html=True)
            
            st.markdown(f"**Objetivos de Tratamiento:**")
            objetivos = evolucion.get('objetivos_tratamiento', [])
            if objetivos:
                for obj in objetivos:
                    st.markdown(f"- {obj.get('texto', '')}: **{obj.get('progreso', 0)}%**")
                    # Barra de progreso
                    progress_value = obj.get('progreso', 0) / 100
                    st.progress(progress_value)
            else:
                st.markdown("No se registraron objetivos")
            
            st.markdown(f"**Plan para Próxima Sesión:**")
            st.markdown(f"<div class='highlight'>{evolucion.get('plan_proxima', '')}</div>", unsafe_allow_html=True)

# Función principal modificada para quitar el sidebar
def paciente_evol():
    st.markdown('<p class="main-header">Gestión de Evoluciones de Pacientes</p>', unsafe_allow_html=True)
    
    # Conectar con Google Sheets una sola vez al inicio
    sheets = connect_to_gsheets()
    if not sheets:
        st.error("No se pudo conectar con Google Sheets. Verifica las credenciales e inténtalo de nuevo.")
        return
    
    # Obtener la lista de pacientes (solo nombres e IDs) sin cargar todos los datos
    try:
        patients_data = sheets['historia_clinica'].get_all_records()
        pacientes = []
        
        for patient in patients_data:
            if 'ID' in patient and patient['ID'] and 'Nombre' in patient:
                pacientes.append((str(patient['ID']), patient.get('Nombre', 'Sin nombre')))
        
        pacientes.sort(key=lambda x: x[1])  # Ordenar por nombre
    except Exception as e:
        st.error(f"Error al obtener la lista de pacientes: {e}")
        return
    
    # Mapa de opciones de pacientes a sus IDs
    options_map = {}
    patient_options = []
    
    for id, nombre in pacientes:
        option_text = f"{nombre} (ID: {id})"
        patient_options.append(option_text)
        options_map[option_text] = id
    
    if not patient_options:
        st.info("No hay pacientes disponibles.")
        return
    
    # Selección de paciente en la pantalla principal
    st.subheader("Selección de Paciente")
    selected_patient = st.selectbox(
        "Seleccione un paciente para ver sus detalles:",
        options=[""] + patient_options,  # Añadimos una opción vacía al inicio
        index=0
    )
    
    # Verificar si se ha seleccionado un paciente
    if not selected_patient:
        st.info("Seleccione un paciente para comenzar.")
        return
    
    # Extraer ID del paciente seleccionado usando el mapa de opciones
    patient_id = options_map[selected_patient]
    
    # Ahora que se ha seleccionado un paciente, cargar todos los datos
    data = load_patient_data(sheets)
    if not data:
        st.error("No se pudieron cargar los datos de pacientes.")
        return
    
    # Verificar que el ID existe en los datos
    if patient_id not in data:
        st.error(f"Error: El ID del paciente '{patient_id}' no existe en los datos cargados.")
        return
    
    # Mostrar información del paciente
    st.markdown('<p class="sub-header">Información del Paciente</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Nombre:** {data[patient_id]['nombre']}")
        st.markdown(f"**ID:** {patient_id}")
    with col2:
        st.markdown(f"**Sexo:** {data[patient_id]['sexo']}")
        st.markdown(f"**Edad:** {data[patient_id]['edad']}")
    with col3:
        st.markdown(f"**Terapeuta:** {data[patient_id]['terapeuta']}")
        st.markdown(f"**Fecha Registro:** {data[patient_id]['fecha_registro']}")
    
    st.markdown(f"**Motivo de Consulta Inicial:**")
    st.markdown(f"<div class='highlight'>{data[patient_id]['motivo_consulta']}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Resultado Examen:**")
        st.markdown(f"<div class='highlight'>{data[patient_id]['resultado_examen']}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**Diagnóstico:**")
        st.markdown(f"<div class='highlight'>{data[patient_id]['diagnostico']}</div>", unsafe_allow_html=True)
    
    # Pestañas para diferentes secciones
    tab1, tab2, tab3, tab4 = st.tabs(["Nueva Evolución", "Historial de Evoluciones", "Seguimiento de Objetivos", "Escalas y Tests"])
    
    with tab1:
        # Formulario de nueva evolución
        st.markdown('<p class="sub-header">Registrar Nueva Evolución</p>', unsafe_allow_html=True)
        
        with st.form("evolution_form"):
            fecha = st.date_input("Fecha de la Sesión", datetime.date.today())
            motivo_consulta = st.text_area("Motivo de Consulta / Presentación Actual", 
                                          placeholder="Describa el motivo principal de la consulta y los síntomas actuales.")
            
            estado_mental = st.text_area("Estado Mental", 
                                        placeholder="Describa el estado mental del paciente (orientación, afecto, cognición, etc.).")
            
            # Técnicas aplicadas
            st.markdown('<p class="sub-title">Técnicas Aplicadas</p>', unsafe_allow_html=True)
            tecnicas_options = get_tecnicas_terapeuticas()
            tecnicas_aplicadas = st.multiselect("Seleccione las técnicas aplicadas:", tecnicas_options)
            
            if "Otra" in tecnicas_aplicadas:
                Otra = st.text_input("Especifique otra técnica aplicada:")
                if Otra:
                    tecnicas_aplicadas.remove("Otra")
                    tecnicas_aplicadas.append(Otra)
            
            # Descripción de la intervención
            intervencion = st.text_area("Descripción de la Intervención", 
                                       placeholder="Detalle la intervención realizada durante la sesión.")
            
            # Avances terapéuticos
            avances = st.text_area("Avances Terapéuticos", 
                                  placeholder="Describa los avances observados en el paciente.")
            
            # Actualización de objetivos
            st.markdown('<p class="sub-title">Objetivos de Tratamiento</p>', unsafe_allow_html=True)
            
            objetivos_actuales = []
            if data[patient_id].get('evoluciones', []):
                # Obtener objetivos de la última evolución si existen
                for evol in sorted(
                    data[patient_id]['evoluciones'], 
                    key=lambda x: datetime.datetime.strptime(x['fecha_registro'], "%Y-%m-%d") if x['fecha_registro'] else datetime.datetime.min,
                    reverse=True
                ):
                    if 'objetivos_tratamiento' in evol and evol['objetivos_tratamiento']:
                        objetivos_actuales = evol['objetivos_tratamiento']
                        break
            
            objetivos_container = st.container()
            with objetivos_container:
                num_objetivos = st.number_input("Número de Objetivos", min_value=1, max_value=10, value=max(1, len(objetivos_actuales)))
                
                objetivos = []
                for i in range(num_objetivos):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        objetivo_text = st.text_input(f"Objetivo {i+1}", 
                                                    value=objetivos_actuales[i]['texto'] if i < len(objetivos_actuales) else "",
                                                    key=f"obj_{i}")
                    with col2:
                        progreso = st.slider("Progreso", 0, 100, 
                                             value=objetivos_actuales[i]['progreso'] if i < len(objetivos_actuales) else 0,
                                             key=f"prog_{i}")
                    
                    objetivos.append({
                        "texto": objetivo_text,
                        "progreso": progreso
                    })
            
            # Plan para próxima sesión
            plan_proxima = st.text_area("Plan para Próxima Sesión", 
                                       placeholder="Detalle el plan para la próxima sesión.")
            
            # Botón de submit
            submitted = st.form_submit_button("Guardar Evolución")
            
            if submitted:
                # Crear nueva evolución
                nueva_evolucion = {
                    "ID": patient_id,
                    "Nombre": data[patient_id]['nombre'],
                    "Sexo": data[patient_id]['sexo'],
                    "Edad": data[patient_id]['edad'],
                    "Motivo Consulta": motivo_consulta,
                    "Resultado Examen": data[patient_id]['resultado_examen'],
                    "Diagnostico": data[patient_id]['diagnostico'],
                    "Fecha Registro": fecha.strftime("%Y-%m-%d"),
                    "Objetivos Tratamiento": objetivos,
                    "Tecnicas": tecnicas_aplicadas,
                    "Terapeuta": data[patient_id]['terapeuta'],
                    "Evoluciones": "",
                    "Avances": avances,
                    "Estado Mental": estado_mental,
                    "Intervencion": intervencion,
                    "Plan Proxima": plan_proxima,
                    "Fecha Modificacion": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Guardar en Google Sheets
                if save_evolution_to_sheets(sheets, nueva_evolucion):
                    st.success("Evolución guardada correctamente")
                    # Recargar datos para reflejar cambios
                    data = load_patient_data(sheets)

                else:
                    st.error("Hubo un error al guardar la evolución")
        # Generar PDF y crear botón de descarga
        pdf_bytes =create_pdf(data, content_type="ficha_paciente")
        st.download_button(
            label="Descargar Evolucion (PDF)",
            data=pdf_bytes,
            file_name=f"Evolucion_{patient_id}.pdf",
            mime="application/pdf"
            )
    
    with tab2:
        # Mostrar historial de evoluciones
        display_evolution_history(patient_id, data)
    
    with tab3:
        # Mostrar seguimiento de objetivos
        display_objectives_tracking(patient_id, data)
    
    with tab4:
        # Mostrar escalas y tests
        display_scales_and_tests(patient_id, data)

# Función para crear un botón de descarga de PDF
def get_pdf_download_link(pdf_bytes, filename="historia_clinica.pdf", text="Descargar PDF"):
    """Genera un enlace HTML para descargar un archivo PDF."""
    b64_pdf = base64.b64encode(pdf_bytes).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'

#if __name__ == "__main__":
#    paciente_evol()

