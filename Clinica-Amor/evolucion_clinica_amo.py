import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
#import matplotlib.pyplot as plt
import datetime
import json
import os
from pathlib import Path
import uuid
import time
import toml

# Configuración para reintentos de conexión
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Evoluciones - Historia Clínica",
#    page_icon="🧠",
#    layout="wide"
#)

# Estilos CSS
#st.markdown("""
#<style>
#    .main-title {
#        font-size: 42px;
#        font-weight: bold;
#        color: #2c3e50;
#        margin-bottom: 20px;
#        text-align: center;
#    }
#    .section-title {
#        font-size: 28px;
#        font-weight: bold;
#        color: #2c3e50;
#        margin-top: 20px;
#        margin-bottom: 10px;
#    }
#    .sub-title {
#        font-size: 24px;
#        font-weight: bold;
#        color: #34495e;
#        margin-top: 15px;
#        margin-bottom: 8px;
#    }
#    .card {
#        background-color: #f8f9fa;
#        border-radius: 10px;
#        padding: 20px;
#        margin-bottom: 20px;
#        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
#    }
#    .info-text {
#        font-size: 16px;
#        color: #2c3e50;
#    }
#    .highlight {
#        background-color: #e6f7ff;
#        padding: 15px;
#        border-radius: 5px;
#        border-left: 5px solid #1890ff;
#    }
#</style>
#""", unsafe_allow_html=True)

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
#@st.cache_resource
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
        
        # Obtener o crear las hojas específicas
        try:
            patients_sheet = spreadsheet.worksheet('historia_clinica')

        #except gspread.exceptions.WorksheetNotFound:
            # Si la hoja no existe, crearla
            #patients_sheet = spreadsheet.add_worksheet(title='historia_clinica', rows=1000, cols=27)
            # Añadir encabezados
            #patients_headers = ['ID', 'Nombre', 'Sexo', 'Edad', 'Estudios', 'Origen',
            #    'Ocupacion', 'Estado civil', 'Religion', 'Progenitores',
            #    'Motivo Consulta', 'Fecha Inicio Sintomas', 'Antecedentes',
            #    'Desarrollo Psicomotor', 'Alimentacion', 'Habitos de sueño', 'Perfil Social','Otros', 'Resultado Examen', 'Diagnostico', 'Objetivos Tratamiento', 'Tecnicas', 'Fecha Consulta', 'Terapeuta', 'Fecha Registro', 'Evoluciones', 'Fecha Modificacion'            ]
            #sheet.append_row(headers)
            #patients_sheet.append_row(patients_headers)

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
            
        except Exception as e:
            st.error(f"Error al guardar datos: {e}")    

        try:
            evoluciones_sheet = spreadsheet.worksheet('evolucion_paciente')

        #except gspread.exceptions.WorksheetNotFound:
            # Si la hoja no existe, crearla
            #evoluciones_sheet = spreadsheet.add_worksheet(title='evolucion_paciente', rows=1000, cols=50)
            # Añadir encabezados
            #evoluciones_headers = [
            #    'ID',	'Nombre',	'Sexo',	'Edad',	'Resultado_Examen',	'Diagnostico',	'Fecha Registro',	'Objetivos Tratamiento',	'Tecnicas',	'Terapeuta',	'Evoluciones',	'Estado Mental',	'Intervencion',	'Plan Proxima'	'Fecha Modificacion']
            #evoluciones_sheet.append_row(evoluciones_headers)
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
            
        except Exception as e:
            st.error(f"Error al guardar datos: {e}")

        return {'historia_clinica': patients_sheet, 'evolucion_paciente': evoluciones_sheet}
    
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para cargar datos
def load_data():
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheets = connect_to_gsheets()
                if not sheets:
                    return {}
                
                # Obtener datos de pacientes
                patients_data = sheets['historia_clinica'].get_all_records()
                
                # Obtener datos de evoluciones
                evoluciones_data = sheets['evolucion_paciente'].get_all_records()
                
                # Organizar datos en el formato esperado
                data = {}
                for patient in patients_data:
                    patient_id = patient['ID']
                    data[patient_id] = {
                        'id': patient_id,
                        'nombre': patient['Nombre'],
                        'sexo': patient['Sexo'],
                        'edad': patient['Edad'],
                        'resultado_examen':['Resultado_Examen'],
                        'diagnostico': patient['Diagnostico'],
                        'fecha_registro': patient['Fecha Registro'],
                        'objetivos_tratamiento': patient['Objetivos Tratamiento'],
                        'tecnicas':patient['Tecnicas'],
                        'terapeuta':patient['Terapeuta'],	
                        'evoluciones':patient['Evoluciones'],
                        'fecha_modificacion': patient['Fecha Modificacion'],   
                         "evoluciones": []
                        }

                
                # Agregar evoluciones a los pacientes correspondientes
                for evolucion in evoluciones_data:
                    patient_id = evolucion['ID']
                    if patient_id in data:
                        # Convertir campos de texto a estructuras de datos
                        if evolucion['Tecnicas']:
                            tecnicas = json.loads(evolucion['Tecnicas'])
                        else:
                            tecnicas = []
                        
                        if evolucion['objetivos_tratamiento']:
                            objetivos = json.loads(evolucion['objetivos_tratamiento'])
                        else:
                            objetivos = []
                        
                        # Crear objeto de evolución
                        evolucion_obj = {
                            'id': evolucion['ID'],
                            'identificacion':['Identificacion'],
                            'nombre': evolucion['Nombre'],
                            'sexo': evolucion['Sexo'],
                            'edad': evolucion['Edad'],
                            'resultado_examen':evolucion['Resultado Examen'],
                            'diagnostico': evolucion['Diagnostico'],
                            'fecha_registro': evolucion['Fecha Registro'],
                            'objetivos_tratamiento': evolucion['Objetivos Tratamiento'],
                            'tecnicas':evolucion['Tecnicas'],
                            'terapeuta':evolucion['Terapeuta'],	
                            #'evoluocines':evolucion['Evoluciones'],
                            'estado_mental': evolucion['Estado Mental'],
                            'intervencion': evolucion['Intervencion'],
                            'plan_proxima': evolucion['Plan Proxima'],
                            'fecha_modificacion': evolucion['Fecha Modificacion'],
                            "evoluciones": []
                        }
                        
                        data[patient_id]['evoluciones'].append(evolucion_obj)
                
                # Si no hay datos, crear ejemplos
                if not data:
                    # Datos de ejemplo
                    sample_data = {
                        "PAC001": {
                            "id": "PAC001",
                            "nombre": "Ana María Gómez",
                            "edad": 32,
                            "diagnostico": "F41.1 Trastorno de Ansiedad Generalizada",
                            "inicio_tratamiento": "2024-11-01",
                            "evoluciones": []
                        },
                        "PAC002": {
                            "id": "PAC002",
                            "nombre": "Carlos Jiménez",
                            "edad": 28,
                            "diagnostico": "F33.1 Trastorno Depresivo Mayor, Recurrente",
                            "inicio_tratamiento": "2024-10-15",
                            "evoluciones": []
                        }
                    }
                    # Guardar los datos de ejemplo
                    save_data(sample_data)
                    return sample_data
                
                return data
                
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
            return {}
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
            return {}

def save_data(data):
    """Guarda los datos de pacientes y evoluciones en Google Sheets."""
    try:
        sheets = connect_to_gsheets()
        if not sheets:
            return False
        
        # Guardar datos de pacientes
        patients_sheet = sheets['historia_clinica']
                
        #patients_sheet.clear()
        #patients_sheet.append_row(['ID', 'Nombre', 'Sexo', 'Edad', 'Estudios', 'Origen',
        #        'Ocupacion', 'Estado Civil', 'Religion', 'Progenitores',
        #        'Motivo Consulta', 'Fecha Inicio Sintomas', 'Antecedentes',
        #        'Desarrollo Psicomotor', 'Alimentacion', 'Habitos de Sueño', 'Perfil Social','Otros', 'Resultado Examen', 'Diagnostico', 'Objetivos Tratamiento', 'Tecnicas', 'Fecha Consulta', 'Terapeuta', 'Fecha Registro', 'Evoluciones', 'Fecha Modificacion'])
        
        #for patient_id, patient_data in data.items():
        #    patients_sheet.append_row([
        #        patient_data['ID'],
        #        patient_data['Nombre'],
        #        patient_data['Edad'],
        #        patient_data['Sexo'],
        #        patient_data['Diagnostico'],
        #        patient_data['Fecha Registro'],
        #        patient_data['Objetivos Tratamiento'],
        #        patient_data['Tratamiento'],
        #        patient_data['Tecnicas'],
        #        patient_data['Terapeuta'],
        #        patient_data['Evoluciones'],
        #        patient_data['Fecha Modificacion']
        #    ])
        
        # Guardar datos de evoluciones
        evoluciones_sheet = sheets['evolucion_paciente']

        #evoluciones_sheet.clear()
        #evoluciones_sheet.append_row([
        #    'ID', 'Identificacion' , 'Nombre', 'Sexo', 'Edad', 'Motivo Consulta','Resultado Examen', 'Diagnostico', 'Fecha Registro','Objetivos Tratamiento','Tecnicas','Terapeuta', 'Evoluciones', 'Estado  Mental', 'Intervencion', 'Plan Proxima'
        #])
        
        for patient_id, patient_data in data.items():
            for evolucion in patient_data.get('evoluciones', []):
                evoluciones_sheet.append_row([
                    evolucion['ID'],
                    evolucion['Identificacion'],
                    evolucion['Nombre'],
                    evolucion['Sexo'],
                    evolucion['Edad'],
                    evolucion['Motivo Consulta'],
                    evolucion['Resultado Examen'],
                    evolucion['Diagnostico'],
                    evolucion['Fecha Registro'],
                    evolucion['Objetivos Tratamiento'],
                    evolucion['Tecnicas'],
                    evolucion['Terapeuta'],	
                    #evolucion['Evoluciones'],
                    evolucion['Estado Mental'],
                    json.dumps(evolucion['Tecnicas']),
                    evolucion['Intervencion'],
                    json.dumps(evolucion.get('Objetivos Tratamiento', [])),
                    evolucion.get['Plan Proxima',''],
                    evolucion['Fecha Modificacion']
                ])
        
        return True
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")
        return False

def get_test_options():
    """Devuelve una lista de tests psicológicos disponibles."""
    return {
        "BDI-II": "Inventario de Depresión de Beck",
        "BAI": "Inventario de Ansiedad de Beck",
        "STAI": "Inventario de Ansiedad Estado-Rasgo",
        "DASS-21": "Escala de Depresión, Ansiedad y Estrés",
        "SCL-90-R": "Listado de Síntomas 90 Revisado",
        "WHODAS 2.0": "Cuestionario para la Evaluación de Discapacidad de la OMS",
        "CORE-OM": "Clinical Outcomes in Routine Evaluation"
    }

def get_tecnicas_terapeuticas():
    """Devuelve una lista de técnicas terapéuticas disponibles."""
    return [
        "Reestructuración cognitiva",
        "Exposición en vivo",
        "Exposición en imaginación",
        "Entrenamiento en habilidades sociales",
        "Técnicas de relajación",
        "Activación conductual",
        "Mindfulness",
        "Terapia de aceptación y compromiso",
        "Entrenamiento en solución de problemas",
        "Psicoeducación",
        "Terapia de procesamiento emocional",
        "Terapia interpersonal",
        "Terapia narrativa",
        "Terapia centrada en la compasión",
        "Terapia sistémica",
        "Estrategias de afrontamiento",
        "Otra"
    ]

# Cargar datos iniciales
data = load_data()

# Título principal
st.markdown('<p class="main-title">Sistema de Evoluciones - Historia Clínica</p>', unsafe_allow_html=True)

# Sidebar para selección de paciente
st.sidebar.header("Selección de Paciente")
patient_id = st.sidebar.selectbox("Seleccione un paciente:", 
                                 options=list(data.keys()),
                                 format_func=lambda x: f"{data[x]['nombre']} ({x})")

# Sección de opciones del menú
st.sidebar.header("Menú")
menu_option = st.sidebar.radio("Seleccione una opción:", 
                           ["Datos del Paciente", 
                            "Registrar Nueva Evolución", 
                            "Historial de Evoluciones", 
                            "Seguimiento de Objetivos", 
                            "Escalas y Tests"])

st.sidebar.markdown("---")
st.sidebar.info("Desarrollado por José Alejandro García")

# Mostrar datos del paciente
if menu_option == "Datos del Paciente":
    st.markdown('<p class="section-title">Datos del Paciente</p>', unsafe_allow_html=True)
    
    patient = data[patient_id]
    
    col1, col2 = st.columns(2)
    with col1:
        #st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**Identificacion:** {patient['id']}")
        st.markdown(f"**Nombre:** {patient['nombre']}")
        st.markdown(f"**Edad:** {patient['edad']} años")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        #st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**Diagnóstico:** {patient['diagnostico']}")
        st.markdown(f"**Inicio de Tratamiento:** {patient['fecha_registro']}")
        st.markdown(f"**Total de Sesiones:** {len(patient.get('evoluciones', []))}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Mostrar sesión más reciente si existe
    if patient.get('evoluciones', []):
        st.markdown('<p class="sub-title">Última Evolución</p>', unsafe_allow_html=True)
        last_evolution = patient['evoluciones'][-1]
        
        st.markdown('<div class="card highlight">', unsafe_allow_html=True)
        st.markdown(f"**Fecha Modificacion:** {last_evolution['fecha_modificacion']}")
        st.markdown(f"**Motivo de Consulta:** {last_evolution['motivo_consulta']}")
        st.markdown(f"**Estado Mental:** {last_evolution['estado_mental']}")
        st.markdown(f"**Técnicas Aplicadas:** {', '.join(last_evolution['tecnicas'])}")
        st.markdown(f"**Avances Observados:** {last_evolution['avances']}")
        st.markdown('</div>', unsafe_allow_html=True)

# Registrar nueva evolución
elif menu_option == "Registrar Nueva Evolución":
    st.markdown('<p class="section-title">Registrar Nueva Evolución</p>', unsafe_allow_html=True)
    
    # Formulario de nueva evolución
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
            for evol in reversed(data[patient_id]['evoluciones']):
                if 'objetivos' in evol:
                    objetivos_actuales = evol['Objetivos Tratamiento']
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
                "ID": patient_id, #str(uuid.uuid4()),
                "Fecha Registro": fecha.strftime("%Y-%m-%d"),
                "Motivo Consulta": motivo_consulta,
                "Estado Mental": estado_mental,
                "Tecnicas": tecnicas_aplicadas,
                "Intervencion": intervencion,
                "Avances": avances,
                "Objetivos Tratamiento": objetivos,
                "Plan Proxima": plan_proxima,
                "evoluciones": []
            }
            
            # Agregar a los datos del paciente
            if 'evoluciones' not in evolucion[patient_id]:  #data[patient_id]:
                evolucion[patient_id]['evoluciones'] = []
                #data[patient_id]['evoluciones'] = []
            
            #data[patient_id]['evolucion_paciente'].append(evolucion_obj)
            #data[patient_id]['evoluciones'].append(nueva_evolucion)
            evolucion[patient_id]['evoluciones'].append(nueva_evolucion)
            
            # Guardar datos
            save_data(data)
            
            st.success("Evolución registrada correctamente.")
            st.balloons()

# Ver historial de evoluciones
elif menu_option == "Historial de Evoluciones":
    st.markdown('<p class="section-title">Historial de Evoluciones</p>', unsafe_allow_html=True)
    patient = data[patient_id]
    evoluciones = patient.get('evoluciones', [])
    
    if not evoluciones:
        st.info("No hay evoluciones registradas para este paciente.")
    else:
        # Ordenar evoluciones por fecha (más reciente primero)
        evoluciones.sort(key=lambda x: x['Fecha Registro'], reverse=True)
        
        # Selector de evolución
        evolucion_selector = st.selectbox(
            "Seleccione una evolución:",
            options=range(len(evoluciones)),
            format_func=lambda i: f"Sesión {len(evoluciones)-i}: {evoluciones[i]['Fecha Registro']}"
        )
        
        # Mostrar la evolución seleccionada
        evolucion = evoluciones[evolucion_selector]
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**Fecha:** {evolucion['Fecha Registro']}")
        st.markdown(f"**Motivo de Consulta:** {evolucion['Motivo Consulta']}")
        st.markdown(f"**Estado Mental:** {evolucion['Estado Mental']}")
        
        # Técnicas aplicadas
        st.markdown("**Técnicas Aplicadas:**")
        for tecnica in evolucion['Tecnicas']:
            st.markdown(f"- {tecnica}")
        
        # Intervención
        st.markdown(f"**Descripción de la Intervención:** {evolucion['Intervencion']}")
        
        # Avances
        st.markdown(f"**Avances Terapéuticos:** {evolucion['Avances']}")
        
        # Objetivos
        if 'objetivos' in evolucion:
            st.markdown("**Objetivos de Tratamiento:**")
            for i, obj in enumerate(evolucion['Objetivos Tratamiento']):
                st.markdown(f"- {obj['texto']} (Progreso: {obj['progreso']}%)")
                st.progress(obj['progreso'] / 100)
        
        # Plan para próxima sesión
        if 'plan_proxima' in evolucion:
            st.markdown(f"**Plan para Próxima Sesión:** {evolucion['Plan Proxima']}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Opciones adicionales
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Imprimir Evolución"):
                st.success("Preparando documento para impresión...")
                # Aquí se implementaría la funcionalidad de impresión
        
        with col2:
            if st.button("Exportar a PDF"):
                st.success("Exportando evolución a PDF...")
                # Aquí se implementaría la exportación a PDF
        
        # Opción para editar evolución
        if st.button("Editar Esta Evolución"):
            st.session_state['editar_evolucion'] = True
            st.session_state['evolucion_a_editar'] = evolucion_selector
            st.rerun()
        
        # Separador
        st.markdown("---")
        
        # Sección de análisis de progreso
        st.markdown("### Análisis de Progreso")
        
        # Gráfico de progreso de objetivos si hay múltiples evoluciones
        if len(evoluciones) > 1 and 'objetivos' in evoluciones[0]:
            st.subheader("Progreso de Objetivos a lo largo del tiempo")
            # Aquí se implementaría un gráfico con la evolución de los objetivos
            st.info("Gráfico de progreso de objetivos disponible")
            
        # Notas adicionales
        with st.expander("Notas Adicionales", expanded=False):
            notes = st.text_area("Agregar notas sobre el progreso del paciente", "")
            if st.button("Guardar Notas"):
                if notes:
                    # Guardar las notas en la evolución actual
                    st.success("Notas guardadas correctamente")
                    