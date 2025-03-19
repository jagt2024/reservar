import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from datetime import datetime
import time
import json
import toml

# Configuración para reintentos de conexión
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(
#    page_title="Historia Clínica Psicológica",
#    page_icon="🧠",
#    layout="wide"
#)

# Initialize the state for the editing form
if 'editing' not in st.session_state:
    st.session_state.editing = False
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None
if 'patient' not in st.session_state:
    st.session_state.patient = {}

# Función para cargar credenciales desde el archivo .toml
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
        
        # Abrir la hoja existente - Usar el nombre correcto según tu función add_new_client
        spreadsheet = client.open('gestion-reservas-amo')
        
        # Obtener o crear la hoja específica
        try:
            sheet = spreadsheet.worksheet('historia_clinica')
        except gspread.exceptions.WorksheetNotFound:
            # Si la hoja no existe, crearla
            sheet = spreadsheet.add_worksheet(title='historia_clinica', rows=1000, cols=50)
            
            # Añadir encabezados
            headers = [
                'ID', 'Nombre', 'Sexo', 'Edad', 'Estudios', 'Origen',
                'Ocupacion', 'Estado civil', 'Religion', 'Progenitores',
                'Motivo Consulta', 'Fecha Inicio Sintomas', 'Antecedentes',
                'Desarrollo Psicomotor', 'Alimentacion', 'Habitos de sueño', 'Perfil Social','otros',
                #'Perfil social', 'Personalidad', 'Historia familiar',
                #'Apariencia', 'Estado de conciencia', 'Estado de ánimo', 'Actividad motora',
               # 'Lenguaje', 'Contenido de ideas', 'Sensorium', 'Memoria', 'Pensamiento',
                'Resultado Examen', 'Diagnostico', 'Objetivos Tratamiento', 'Tecnicas', 
                'Fecha Consulta', 'Terapeuta', 'Fecha Registro'
            ]
            sheet.append_row(headers)
        
        return sheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para cargar datos existentes
def load_data():
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = connect_to_gsheets()
                if sheet:
                    # Obtener todos los datos
                    data = sheet.get_all_records()
                    return pd.DataFrame(data)
                return pd.DataFrame()
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
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
            return pd.DataFrame()

# Función para guardar nueva historia clínica
def save_history(patient_data):
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Guardando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = connect_to_gsheets()
                if sheet:
                    # Verificar si la columna ID existe
                    headers = sheet.row_values(1)
                    if 'ID' not in headers:
                        # Añadir encabezados si el archivo está vacío
                        all_headers = ['ID'] + list(patient_data.keys())
                        sheet.append_row(all_headers)
                        new_id = 1
                    else:
                        # Obtener el último ID y calcular el siguiente
                        df = pd.DataFrame(sheet.get_all_records())
                        #if df.empty:
                        #    new_id = ['ID']
                        #else:
                        #    try:
                        #        new_id = int(df['ID'].max()) + 1
                        #    except:
                        #        new_id = len(df) + 1
                    
                    # Preparar la fila a añadir
                    row_data = list(patient_data.values())
                    sheet.append_row(row_data)
                    
                    return True #, new_id
                return False #,  None
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
            return False #, None
        except Exception as e:
            st.error(f"Error al guardar datos: {e}")
            return False #, None

# Función para buscar paciente
def search_patient(search_term, search_type):
    df = load_data()
    if df.empty:
        return pd.DataFrame()
    
    if search_type == 'ID':
        try:
            search_term = int(search_term)
            result = df[df['ID'] == search_term]
        except:
            return pd.DataFrame()
    else:  # Por nombre
        result = df[df['Nombre'].str.contains(search_term, case=False, na=False)]
    
    return result

# Función para actualizar historia clínica
def update_history(id, patient_data):
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Actualizando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = connect_to_gsheets()
                if sheet:
                    # Obtener todos los datos
                    df = pd.DataFrame(sheet.get_all_records())
                    
                    # Obtener los encabezados
                    headers = sheet.row_values(1)
                    
                    # Encontrar la fila que corresponde al ID
                    try:
                        row_to_update = df[df['ID'] == id].index[0] + 2  # +2 porque la fila 1 son los encabezados
                    except:
                        st.error("No se encontró la Identificacion del paciente")
                        return False
                    
                    # Actualizar cada celda
                    for col, value in patient_data.items():
                        if col in headers:
                            col_index = headers.index(col) + 1  # +1 porque gspread es 1-indexed
                            sheet.update_cell(row_to_update, col_index, value)
                    
                    return True
                return False
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
            return False
        except Exception as e:
            st.error(f"Error al actualizar datos: {e}")
            return False

# Función para iniciar el modo de edición
# Helper function to start editing mode
def start_editing(patient_id):
    st.session_state.editing = True
    st.session_state.edit_index = patient_id
    
# Helper function to cancel editing mode
def cancel_editing():
    st.session_state.editing = False
    st.session_state.edit_index = None
    st.session_state.patient = {}

# Título principal y descripción
st.title("🧠 Sistema de Gestión de Historias Clínicas Psicológicas")
st.markdown("Sistema para crear y gestionar historias clínicas de pacientes de psicología.")

# Pestañas principales
tab1, tab2, tab3 = st.tabs(["📝 Crear Historia Clínica", "🔍 Buscar Paciente", "📊 Estadísticas"])

with tab1:
    st.header("Nueva Historia Clínica")
    
    # Creamos un formulario con todos los campos necesarios
    with st.form(key="historia_clinica_form"):
        # Sección: Datos generales
        st.markdown('<div class="section-title"><h3>Datos Generales</h3></div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_id = st.text_input("Identificacion*")

            edad = st.number_input("Edad*", min_value=0, max_value=120, step=1) 

            ocupacion = st.text_input("Ocupación")            
        
        with col2:
            nombre = st.text_input("Nombre y apellidos*")
                   
            estado_civil = st.selectbox("Estado civil", ["", "Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Divorciado/a", "Viudo/a"])

            estudios = st.selectbox("Nivel de estudios", ["", "Sin estudios", "Primaria", "Secundaria", "Bachillerato", "Formación Profesional", "Universidad", "Postgrado"])
            
        with col3:
            sexo = st.selectbox("Sexo*", ["", "Masculino", "Femenino", "No binario", "Prefiere no decir"])
            origen = st.text_input("Origen y procedencia")
          
            religion = st.text_input("Religión")
            datos_progenitores = st.text_area("Datos de los progenitores", height=100)
        
        # Sección: Motivo de consulta
        st.markdown('<div class="section-title"><h3>Motivo de Consulta</h3></div>', unsafe_allow_html=True)
        motivo_consulta = st.text_area("Motivo de la consulta*", height=150, help="Razones por las que el paciente ha acudido a la consulta del psicólogo escritas de forma breve y textual. Incluye los síntomas, fecha de inicio, y posibles acontecimientos asociados a su aparición.")
        
        fecha_inicio_sintomas = st.date_input("Fecha de inicio de los síntomas", max_value=datetime.now())
        
        # Sección: Antecedentes del paciente
        st.markdown('<div class="section-title"><h3>Antecedentes del Paciente</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
            antecedentes = st.text_area("Problemas psicológicos anteriores", height=100)
            desarrollo_psicomotor = st.text_area("Desarrollo psicomotor y del lenguaje", height=100)
        
        with col2:
            habitos_alimentacion = st.text_area("Alimentación", height=100)
            habitos_sueno = st.text_area("Hábitos de sueño", height=100)
        
        # Sección: Perfil social
        st.markdown('<div class="section-title"><h3>Perfil Social</h3></div>', unsafe_allow_html=True)
        perfil_social = st.text_area("Perfil de relaciones sociales del paciente", height=150, help="Relaciones con pareja, amigos, familiares, compañeros del trabajo, etc. e historia de estas relaciones en la infancia y adolescencia.")
        
        # Sección: Personalidad
        st.markdown('<div class="section-title"><h3>Personalidad</h3></div>', unsafe_allow_html=True)
        otros = st.text_area("Características psicológicas relevantes, Personalidad, Historia Familiar, apariencia, conciencia, animo, motor  etc.", height=150, help="Características psicológicas más relevantes del paciente, algo que se va desgranando a través de las entrevistas psicológicas.")
        
        # Sección: Historia familiar
        #st.markdown('<div class="section-title"><h3>Historia Familiar</h3></div>', unsafe_allow_html=True)
        #historia_familiar = st.text_area("Datos relevantes sobre la familia del paciente", height=150)
        
        # Sección: Examen mental
        st.markdown('<div class="section-title"><h3>Examen Mental</h3></div>', unsafe_allow_html=True)
        #col1, col2 = st.columns(2)
        
        #with col1:
        #    apariencia = st.text_area("Apariencia general y actitud", height=80)
        #    conciencia = st.text_area("Estado de conciencia", height=80)
        #    animo = st.text_area("Estado de ánimo", height=80)
        #    motor = st.text_area("Actividad motora", height=80)
        
        #with col2:
        #    lenguaje = st.text_area("Asociación y flujo de ideas y características del lenguaje", height=80)
        #    contenido_ideas = st.text_area("Contenido de ideas", height=80)
        #    sensorium = st.text_area("Sensorium", height=80)
        #    memoria = st.text_area("Memoria", height=80)
        
        #pensamiento = st.text_area("Pensamiento", height=100)
        resultado_examen = st.text_area("Resultado del examen", height=100)
        
        # Sección: Diagnóstico
        st.markdown('<div class="section-title"><h3>Diagnóstico</h3></div>', unsafe_allow_html=True)
        diagnostico = st.text_area("Diagnóstico del paciente*", height=150, help="Incluye la fundamentación de la impresión clínica o diagnóstico")
        
        # Sección: Plan de orientación psicológica
        st.markdown('<div class="section-title"><h3>Plan de Orientación Psicológica</h3></div>', unsafe_allow_html=True)
        objetivos = st.text_area("Objetivos del tratamiento", height=100)
        tecnicas = st.text_area("Técnicas a emplear", height=100)
        
        # Fecha de la consulta
        fecha_consulta = st.date_input("Fecha de la consulta", value=datetime.now())
        
        # Terapeuta
        terapeuta = st.text_input("Nombre del terapeuta*")
        
        submit_button = st.form_submit_button(label="Guardar Historia Clínica")
        
        # Verificar campos obligatorios y guardar
        if submit_button:
            # Validaciones
            if not new_id or not nombre or not edad or not sexo or not motivo_consulta or not diagnostico or not terapeuta:
                st.error("Por favor, complete todos los campos marcados con *")
            else:
                # Crear diccionario con todos los datos
                patient_data = {
                    "ID": new_id,
                    "Nombre": nombre,
                    "Sexo": sexo,
                    "Edad": edad,
                    "Estudios": estudios,
                    "Origen": origen,
                    "Ocupacion": ocupacion,
                    "Estado Civil": estado_civil,
                    "Religion": religion,
                    "Progenitores": datos_progenitores,
                    "Motivo Consulta": motivo_consulta,
                    "Fecha Inicio Sintomas": fecha_inicio_sintomas.strftime('%Y-%m-%d'),
                    "Antecedentes": antecedentes,
                    "Desarrollo Psicomotor": desarrollo_psicomotor,
                    "Alimentacion": habitos_alimentacion,
                    "Hábitos de Sueño": habitos_sueno,
                    "Perfil Social": perfil_social,
                    "Otros": otros,
                    #"Personalidad": personalidad,
                    #"Historia familiar": historia_familiar,
                    #"Apariencia": apariencia,
                    #"Estado de conciencia": conciencia,
                    #"Estado de ánimo": animo,
                    #"Actividad motora": motor,
                    #"Lenguaje": lenguaje,
                    #"Contenido de ideas": contenido_ideas,
                    #"Sensorium": sensorium,
                    #"Memoria": memoria,
                    #"Pensamiento": pensamiento,
                    "Resultado Examen": resultado_examen,
                    "Diagnóstico": diagnostico,
                    "Objetivos Tratamiento": objetivos,
                    "Tecnicas": tecnicas,
                    "Fecha Consulta": fecha_consulta.strftime('%Y-%m-%d'),
                    "Terapeuta": terapeuta,
                    "Fecha Registro": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                success = save_history(patient_data)
                if success:
                    st.success(f"Historia clínica guardada correctamente")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Error al guardar la historia clínica. Verifique la conexión a Google Drive.")

with tab2:
    st.header("Buscar Paciente")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("Buscar paciente", placeholder="Ingrese Identificacion o nombre del paciente")
    with col2:
        search_type = st.selectbox("Buscar por", ["Nombre", "ID"])
    
    if st.button("Buscar"):
        if not search_term:
            st.warning("Por favor ingrese un término de búsqueda")
        else:
            with st.spinner("Buscando..."):
                results = search_patient(search_term, search_type)
                
                if results.empty:
                    st.warning("No se encontraron resultados")
                else:
                    st.success(f"Se encontraron {len(results)} resultados")
                    
                    # Mostrar resultados en tabla
                    st.dataframe(results[['ID', 'Nombre', 'Edad', 'Diagnostico', 'Fecha Consulta']])
                    
                    # Seleccionar paciente para ver detalles
                    if not results.empty:
                        selected_id = st.selectbox("Seleccione un paciente para ver detalles", options=results['ID'].tolist(),
                                               format_func=lambda x: f"ID: {x} - {results[results['ID']==x]['Nombre'].values[0]}")
                        
                        if selected_id:
                            patient = results[results['ID'] == selected_id].iloc[0].to_dict()
                            
                            # Mostrar detalles del paciente
                            with st.expander("Datos generales", expanded=True):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.write(f"**Identificacion:** {patient['ID']}")
                                    st.write(f"**Nombre:** {patient['Nombre']}")
                                    st.write(f"**Edad:** {patient['Edad']}")
                                    
                                with col2:
                                    st.write(f"**Origen:** {patient['Origen']}")
                                    st.write(f"**Sexo:** {patient['Sexo']}")
                                    st.write(f"**Estudios:** {patient['Estudios']}")
                                    
                                with col3:
                                    st.write(f"**Ocupación:** {patient['Ocupacion']}")
                                    st.write(f"**Estado civil:** {patient['Estado Civil']}")
                                    st.write(f"**Religión:** {patient['Religion']}")
                            
                            with st.expander("Motivo de la Consulta"):
                                st.write(f"**Motivo:** {patient['Motivo Consulta']}")
                                st.write(f"**Fecha inicio síntomas:** {patient['Fecha Inicio Sintomas']}")
                            
                            with st.expander("Diagnóstico y plan"):
                                st.write(f"**Diagnóstico:** {patient['Diagnostico']}")
                                st.write(f"**Objetivos tratamiento:** {patient['Objetivos Tratamiento']}")
                                st.write(f"**Técnicas:** {patient['Tecnicas']}")

                            # Botón para editar paciente
                            if not st.session_state.editing:
                                if st.button("Editar Consulta", key='ed_consul'):
                                    start_editing(selected_id)
                                    # Initialize the patient with the current patient data
                                    st.session_state.patient = patient.copy()
                                    # st.rerun() - Comentado para evitar bucles

                                # Si está en modo edición, mostrar el formulario
                                #if st.session_state.editing and st.session_state.edit_index == selected_id:
                            with st.form(key="edit_historia_form"):

                                    #st.rerun()     

                                    #st.write("Debug - Patient data keys 1:", list(patient.keys()))

                                    # Mostrar formulario de edición si está en modo edición
                            
                                    #if st.session_state.edit_index == selected_id:
                                    #st.session_state.patient and  

                                    #    patient = st.session_state.patient
                                    #st.write("Debug - Patient data keys 2:", list(patient.keys()))

                                    #with st.form(key="edit_historia_form"):
                                    #st.subheader(f"Editar historia clínica - {patient['Nombre']}")
                                    
                                    # Recrear el formulario pero con los valores actuales
                                    #patient = {}
                                    
                                    # Datos generales
                                    st.markdown('<div class="section-title"><h3>Datos Generales</h3></div>', unsafe_allow_html=True)
                                    col1, col2, col3 = st.columns(3)
        
                                    with col1:
                                        patient["ID"] = st.text_input("Identificacion*", value=patient.get('ID'))
                                        
                                        patient["Nombre"] = st.text_input("Nombre y apellidos*", value=patient.get('Nombre'))
                                        
                                        patient["Edad"] = st.number_input(
                                            "Edad*", 
                                            min_value=0, 
                                            max_value=120, 
                                            step=1,
                                            value=int(patient.get('Edad', 0)) if patient.get('Edad') else 0)
        
                                    with col2:
                                        patient["Origen"] = st.text_input("Origen y procedencia", value=patient.get('Origen', ''))
                                        
                                        sexo_options = ["", "Masculino", "Femenino", "No binario", "Prefiere no decir"]
                                        sexo_index = 0
                                        if patient.get('Sexo', '') in sexo_options:
                                            sexo_index = sexo_options.index(patient.get('Sexo', ''))
                                            patient["Sexo"] = st.selectbox("Sexo*", sexo_options, index=sexo_index)
            
                                            estudios_options = ["", "Sin estudios", "Primaria", "Secundaria", "Bachillerato", 
                                            "Formación Profesional", "Universidad", "Postgrado"]
                                            estudios_index = 0
                                            if patient.get('Estudios', '') in estudios_options:
                                                estudios_index = estudios_options.index(patient.get('Estudios', ''))
                                                patient["Estudios"] = st.selectbox("Estudios", estudios_options, index=estudios_index)
        
                                    with col3:
                                        patient["Ocupacion"] = st.text_input("Ocupación", value=patient.get('Ocupacion', ''))

                                        estado_civil_options = ["", "Soltero/a", "Casado/a", "Unión libre", "Separado/a", 
                                        "Divorciado/a", "Viudo/a"]
                                        estado_civil_index = 0
                                        if patient.get('Estado Civil', '') in estado_civil_options:
                                            estado_civil_index = estado_civil_options.index(patient.get('Estado Civil', ''))
                                            patient["Estado Civil"] = st.selectbox("Estado civil", estado_civil_options, 
                                                     index=estado_civil_index)
            
                                        patient["Religion"] = st.text_input("Religión", value=patient.get('Religion', ''))
                                        
                                        patient["Progenitores"] = st.text_area("Datos de los progenitores", 
                                        value=patient.get('Progenitores', ''), height=100)
        
                                    #  Motivo de consulta
                                    st.markdown('<div class="section-title"><h3>Motivo de Consulta</h3></div>', unsafe_allow_html=True)
                                    patient["Motivo Consulta"] = st.text_area("Motivo de la consulta*", 
                                    value=patient.get('Motivo Consulta', ''), height=150)
        
                                    # Fecha de inicio de síntomas
                                    try:
                                        fecha_inicio = datetime.strptime(patient.get('Fecha Inicio Sintomas', ''), '%Y-%m-%d')
                                    except (ValueError, TypeError):
                                        fecha_inicio = datetime.now()
                                        patient["Fecha Inicio Sintomas"] = st.date_input("Fecha de inicio de los síntomas", 
                                                          value=fecha_inicio).strftime('%Y-%m-%d')
        
                                    # Antecedentes
                                    st.markdown('<div class="section-title"><h3>Antecedentes del Paciente</h3></div>', unsafe_allow_html=True)
                                    col1, col2 = st.columns(2)
        
                                    with col1:
                                            patient["Antecedentes"] = st.text_area("Problemas psicológicos anteriores", 
                                                    value=patient.get('Antecedentes', ''), height=100)
                                            patient["Desarrollo Psicomotor"] = st.text_area("Desarrollo psicomotor y del lenguaje", 
                                                             value=patient.get('Desarrollo Psicomotor', ''), height=100)
        
                                    with col2:
                                            patient["Alimentacion"] = st.text_area("Alimentación", 
                                                    value=patient.get('Alimentacion', ''), height=100)
                                            patient["Habitos de Sueño"] = st.text_area("Hábitos de sueño", 
                                                        value=patient.get('Habitos de Sueño', ''), height=100)
        
                                    # Perfil social
                                    st.markdown('<div class="section-title"><h3>Perfil Social</h3></div>', unsafe_allow_html=True)
                                    patient["Perfil Social"] = st.text_area("Perfil de relaciones sociales", 
                                    value=patient.get('Perfil Social', ''), height=150)
        
                                    # Otros datos
                                    st.markdown('<div class="section-title"><h3>Otros Datos</h3></div>', unsafe_allow_html=True)
                                    patient["Otros"] = st.text_area("Características psicológicas, personalidad, etc.", 
                                    value=patient.get('Otros', ''), height=200)
        
                                    # Examen mental
                                    st.markdown('<div class="section-title"><h3>Examen Mental</h3></div>', unsafe_allow_html=True)
                                    patient["Resultado Examen"] = st.text_area("Resultado del examen", 
                                    value=patient.get('Resultado Examen', ''), height=100)
        
                                    # Diagnóstico
                                    st.markdown('<div class="section-title"><h3>Diagnóstico</h3></div>', unsafe_allow_html=True)
                                    patient["Diagnostico"] = st.text_area("Diagnóstico del paciente*", 
                                    value=patient.get('Diagnostico', ''), height=150)
        
                                    # Plan
                                    st.markdown('<div class="section-title"><h3>Plan de Orientación</h3></div>', unsafe_allow_html=True)
                                    patient["Objetivos Tratamiento"] = st.text_area("Objetivos del tratamiento", 
                                    value=patient.get('Objetivos Tratamiento', ''), height=100)
                                    patient["Tecnicas"] = st.text_area("Técnicas a emplear", 
                                    value=patient.get('Tecnicas', ''), height=100)
        
                                    # Fecha de consulta
                                    try:
                                        fecha_consulta_value = datetime.strptime(patient.get('Fecha Consulta', ''), '%Y-%m-%d')
                                    except (ValueError, TypeError):
                                        fecha_consulta_value = datetime.now()
        
                                    patient["Fecha Consulta"] = st.date_input("Fecha de la consulta", 
                                    value=fecha_consulta_value).strftime('%Y-%m-%d')

                                    patient["Terapeuta"] = st.text_input("Nombre del terapeuta*", 
                                    value=patient.get('Terapeuta', ''))

                                    patient["Fecha Modificacion"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                    st.session_state.patient = patient

                                    # Botón para editar paciente
                                    update_button = st.form_submit_button(label="Actualizar Historia Clínica")
       
                            if update_button:
                                # Validaciones
                                if not patient["ID"] or not patient["Nombre"] or not patient["Edad"]or not patient["Sexo"] or not patient["Motivo Consulta"] or not patient["Terapeuta"]:

                                    st.error("Por favor, Copmlete los camposco * y guarde los cambios *")              
                                else: 

                                            # Actualizar los datos del paciente usando la función existente
                                            with st.spinner("Actualizando historia clínica..."):
                                                success = update_history(selected_id, patient)
                                                if success:
                                                    st.success("Historia clínica actualizada correctamente")
                                                    # Salir del modo edición
                                                    st.session_state.editing = False
                                                    st.session_state.edit_index = None
                                                    st.session_state.patient = None
                                                    time.sleep(1.5)
                                                    st.rerun()
                                                else:
                                                    st.error("Error al actualizar la historia clínica. Compruebe la conexión.")

                                          
                                                    # Save to session state to preserve on rerun
                                                    #st.session_state.patient = patient_data
                                            
                                                   #     success = update_history(selected_id, patient)
                                                   #     if success:
                                                   #         st.success("Historia clínica actualizada correctamente")
                                                    
                                                            # Exit edit mode after successful update
                                                    #        cancel_editing()
                                                    #        time.sleep(2)
                                                    #        st.rerun()
                                                    #    else:
                                                    #        st.error("Error al actualizar la historia clínica")
                                    
                            if st.button("Cancelar edición"):
                               cancel_editing()
                               st.rerun()
                                
            #Provide a cancel button outside the form as a backup option
            #if st.button("Cancelar edición", key="cancel_outside_form"):
            #   cancel_editing()
            #   st.rerun()

with tab3:
    st.header("Estadísticas")
    
    # Cargar datos para estadísticas
    with st.spinner("Cargando datos..."):
        data = load_data()
        
        if data.empty:
            st.info("No hay datos disponibles para mostrar estadísticas")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Distribución por sexo")
                # Convierte a numérico y maneja NaN
                sexo_counts = data['Sexo'].value_counts()
                st.bar_chart(sexo_counts)
            
            with col2:
                st.subheader("Distribución por edad")
                # Convierte a numérico y maneja NaN
                if 'Edad' in data.columns:
                    data['Edad'] = pd.to_numeric(data['Edad'], errors='coerce')
                    edad_bins = [0, 12, 18, 30, 45, 65, 120]
                    edad_labels = ['Niños (0-12)', 'Adolescentes (13-18)', 'Jóvenes (19-30)', 
                                  'Adultos (31-45)', 'Adultos mayores (46-65)', 'Tercera edad (65+)']
                    data['Grupo edad'] = pd.cut(data['Edad'], bins=edad_bins, labels=edad_labels)
                    edad_counts = data['Grupo edad'].value_counts()
                    st.bar_chart(edad_counts)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Motivos de consulta más comunes")
                # Esta es una simplificación, idealmente usarías NLP
                if 'Motivo Consulta' in data.columns:
                    keywords = ['ansiedad', 'depresión', 'estrés', 'pareja', 'familiar', 'fobia', 'trauma']
                    motivo_counts = {}
                    
                    for keyword in keywords:
                        count = data['Motivo Consulta'].str.contains(keyword, case=False, na=False).sum()
                        if count > 0:
                            motivo_counts[keyword] = count
                    
                    if motivo_counts:
                        motivo_df = pd.DataFrame({'Conteo': motivo_counts})
                        st.bar_chart(motivo_df)
                    else:
                        st.info("No se encontraron motivos de consulta para analizar")
            
            with col2:
                st.subheader("Consultas por mes")
                if 'Fecha Consulta' in data.columns:
                    data['Fecha Consulta'] = pd.to_datetime(data['Fecha Consulta'], errors='coerce')
                    data['Mes'] = data['Fecha Consulta'].dt.strftime('%Y-%m')
                    mes_counts = data['Mes'].value_counts().sort_index()
                    st.line_chart(mes_counts)

# Footer
st.markdown("---")
st.markdown("© 2025 Clínica de Psicología - Sistema de Gestión de Historias Clínicas")