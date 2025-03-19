import streamlit as st
import pandas as pd
import numpy as np
import uuid
import datetime
import json
import time
import toml
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
#import matplotlib.pyplot as plt
import altair as alt

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
            patient_id = patient['ID']
            data[patient_id] = {
                'id': patient_id,
                'nombre': patient['Nombre'],
                'sexo': patient['Sexo'],
                'edad': patient['Edad'],
                'motivo_consulta': patient['Motivo Consulta'],
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
            patient_id = evolucion['ID']
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
        "Terapia Cognitivo-Conductual (TCC)",
        "Reestructuración Cognitiva",
        "Exposición",
        "Entrenamiento en Relajación",
        "Mindfulness",
        "Activación Conductual",
        "Resolución de Problemas",
        "Entrenamiento en Habilidades Sociales",
        "Psicodrama",
        "Terapia de Aceptación y Compromiso (ACT)",
        "EMDR",
        "Terapia Narrativa",
        "Terapia Sistémica",
        "Terapia Psicodinámica",
        "Otra"
    ]

# Función para mostrar escalas y tests
def display_scales_and_tests(patient_id, data):
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
    
    # Resultados del test (aquí se pueden implementar opciones específicas para cada test)
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
        st.text_area("Resultados del test", placeholder="Introduzca los resultados del test aplicado...")
    
    observaciones = st.text_area("Observaciones", placeholder="Añada observaciones relevantes sobre la aplicación o resultados del test...")
    
    # Botón para guardar test
    if st.button("Guardar Test"):
        st.success("Test guardado correctamente")
        # Aquí iría la lógica para guardar el test en Google Sheets

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

# Función principal
def main():
    st.markdown('<p class="main-header">Gestión de Evoluciones de Pacientes</p>', unsafe_allow_html=True)
    
    # Conectar con Google Sheets
    sheets = connect_to_gsheets()
    if not sheets:
        st.error("No se pudo conectar con Google Sheets. Verifica las credenciales e inténtalo de nuevo.")
        return
    
    # Cargar datos de pacientes
    data = load_patient_data(sheets)
    if not data:
        st.error("No se pudieron cargar los datos de pacientes.")
        return
    
    # Sidebar para selección de paciente
    st.sidebar.header("Selección de Paciente")
    
    # Lista de pacientes para el selector
    pacientes = [(patient_id, data[patient_id]['nombre']) for patient_id in data]
    pacientes.sort(key=lambda x: x[1])  # Ordenar por nombre
    
    patient_options = [f"{nombre} (ID: {id})" for id, nombre in pacientes]
    
    selected_patient = st.sidebar.selectbox(
        "Seleccione un paciente:",
        options=patient_options,
        index=0 if patient_options else None
    )
    
    if not selected_patient:
        st.info("No hay pacientes disponibles.")
        return
    
    # Extraer ID del paciente seleccionado
    patient_id = selected_patient.split("(ID: ")[1].split(")")[0]
    
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
    
    with tab2:
        # Mostrar historial de evoluciones
        display_evolution_history(patient_id, data)
    
    with tab3:
        # Mostrar seguimiento de objetivos
        display_objectives_tracking(patient_id, data)
    
    with tab4:
        # Mostrar escalas y tests
        display_scales_and_tests(patient_id, data)

if __name__ == "__main__":
    main()
