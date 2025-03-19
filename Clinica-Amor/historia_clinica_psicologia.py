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
                'Desarrollo Psicomotor', 'Alimentacion', 'Habitos de sueño', 'Perfil Social','Otros',
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

# Función para guardar datos modificados
def save_data(df, sheet):
    try:
        with st.spinner('Guardando cambios...'):
            # Convertir el DataFrame a una lista de listas
            data_to_save = [df.columns.tolist()] + df.values.tolist()
            
            # Limpiar la hoja actual
            sheet.clear()
            
            # Actualizar con los nuevos datos
            sheet.update(data_to_save)
            
        st.success('Datos guardados correctamente')
        return True
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")
        return False# Función para guardar datos modificados
def save_data(df, sheet):
    try:
        with st.spinner('Guardando cambios...'):
            # Convertir el DataFrame a una lista de listas
            data_to_save = [df.columns.tolist()] + df.values.tolist()
            
            # Limpiar la hoja actual
            sheet.clear()
            
            # Actualizar con los nuevos datos
            sheet.update(data_to_save)
            
        st.success('Datos guardados correctamente')
        return True
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")
        return False

# Función para filtrar datos por ID o Nombre
def filter_data(df, search_term):
    if not search_term:
        return df
        
    # Asegurar que los tipos de datos sean compatibles para la búsqueda
    df_copy = df.copy()
    df_copy['ID'] = df_copy['ID'].astype(str)
    
    # Buscar coincidencias parciales en ID o Nombre
    mask = (
        df_copy['ID'].str.contains(search_term, case=False, na=False) | 
        df_copy['Nombre'].str.contains(search_term, case=False, na=False)
    )
    
    return df_copy[mask]

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

def consulta_historia():
  # Título principal y descripción
  #st.title("🧠 Sistema de Gestión de Historias Clínicas Psicológicas")
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

        tecnicas_aplicar = [
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
        tecnicas = st.selectbox("Técnicas a emplear", tecnicas_aplicar)
        
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

                    # Generar PDF y crear botón de descarga
                    pdf_bytes = generate_patient_pdf(patient_data)
                    st.download_button(
                            label="Descargar Historia Clínica (PDF)",
                            data=pdf_bytes,
                            file_name=f"historia_clinica_{new_id}.pdf",
                            mime="application/pdf"
                    )
                    
                    
                else:
                    st.error("Error al guardar la historia clínica. Verifique la conexión a Google Drive.")

  with tab2:

    # Inicializar la conexión y cargar datos
        sheet = connect_to_gsheets()
        if sheet:
            df = load_data()
            st.header("Buscar Paciente")
    
            # Selector de paciente con búsqueda
            st.write("Buscar paciente específico:")
            search_patient = st.text_input("Búsqueda de paciente", "", key="search_patient",  placeholder="Ingrese ID o Nombre del paciente", label_visibility="collapsed")
            
            # Filtrar las opciones del selector basado en la búsqueda
            df_copy = df.copy()
            df_copy['ID'] = df_copy['ID'].astype(str)

             # Buscar coincidencias parciales en ID o Nombre
            mask = (
                df_copy['ID'].str.contains(search_patient, case=False, na=False) | 
                df_copy['Nombre'].str.contains(search_patient, case=False, na=False)
            )
            
            if search_patient:
                filtered_patients = df_copy[
                    df_copy['ID'].str.contains(search_patient, case=False, na=False) | 
                    df_copy['Nombre'].str.contains(search_patient, case=False, na=False)
                ]
            else:
                filtered_patients = df_copy
            
            # Crear opciones para el selector
            pacientes_opciones = []
            for _, paciente in filtered_patients.iterrows():
                pacientes_opciones.append(f"{paciente['ID']} - {paciente['Nombre']}")
            
            # Selector de paciente
            seleccion = st.selectbox(
                "Seleccionar paciente:",
                [""] + pacientes_opciones,
                key="patient_selector"
            )
            
            if seleccion:
                # Extraer el ID del paciente seleccionado
                paciente_id = seleccion.split(" - ")[0]
                
                # Filtrar el DataFrame para obtener solo el paciente seleccionado
                paciente_df = df[df['ID'].astype(str) == paciente_id]
                
                if not paciente_df.empty:
                    paciente = paciente_df.iloc[0]
                    paciente_index = paciente_df.index[0]
                    
                    # Crear formularios para cada campo
                    col1, col2, col3 = st.columns(3)
                    
                    # Primera columna - Datos personales
                    with col1:
                        st.markdown("### Datos Personales")

                        id = st.text_input("Identificacion", paciente["ID"])
                        nombre = st.text_input("Nombre", paciente["Nombre"])
                        sexo = st.selectbox("Sexo", ["Masculino", "Femenino", "Otro"], 
                                           index=["Masculino", "Femenino", "Otro"].index(paciente["Sexo"]) if paciente["Sexo"] in ["Masculino", "Femenino", "Otro"] else 0)
                        edad = st.number_input("Edad", min_value=0, value=int(paciente["Edad"]) if pd.notnull(paciente["Edad"]) else 0)
                        estudios = st.text_input("Estudios", paciente["Estudios"] if pd.notnull(paciente["Estudios"]) else "")
                        origen = st.text_input("Origen", paciente["Origen"] if pd.notnull(paciente["Origen"]) else "")
                        ocupacion = st.text_input("Ocupación", paciente["Ocupacion"] if pd.notnull(paciente["Ocupacion"]) else "")
                        estado_civil = st.text_input("Estado Civil", paciente["Estado Civil"] if pd.notnull(paciente["Estado Civil"]) else "")
                        religion = st.text_input("Religión", paciente["Religion"] if pd.notnull(paciente["Religion"]) else "")
                        progenitores = st.text_input("Progenitores", paciente["Progenitores"] if pd.notnull(paciente["Progenitores"]) else "")
                    
                    # Segunda columna - Historia clínica
                    with col2:
                        st.markdown("### Historia Clínica")
                        motivo = st.text_area("Motivo de Consulta", paciente["Motivo Consulta"] if pd.notnull(paciente["Motivo Consulta"]) else "", height=100)
                        fecha_inicio = st.text_input("Fecha Inicio Síntomas", paciente["Fecha Inicio Sintomas"] if pd.notnull(paciente["Fecha Inicio Sintomas"]) else "")
                        antecedentes = st.text_area("Antecedentes", paciente["Antecedentes"] if pd.notnull(paciente["Antecedentes"]) else "", height=100)
                        desarrollo = st.text_area("Desarrollo Psicomotor", paciente["Desarrollo Psicomotor"] if pd.notnull(paciente["Desarrollo Psicomotor"]) else "", height=100)
                        alimentacion = st.text_area("Alimentación", paciente["Alimentacion"] if pd.notnull(paciente["Alimentacion"]) else "", height=100)
                        sueno = st.text_area("Hábitos de Sueño", paciente["Habitos de Sueño"] if pd.notnull(paciente["Habitos de Sueño"]) else "", height=100)
                    
                    # Tercera columna - Diagnóstico y tratamiento
                    with col3:
                        st.markdown("### Evaluación y Tratamiento")
                        perfil_social = st.text_area("Perfil Social", paciente["Perfil Social"] if pd.notnull(paciente["Perfil Social"]) else "", height=100)
                        otros = st.text_area("Otros", paciente["Otros"] if pd.notnull(paciente["Otros"]) else "", height=100)
                        resultado = st.text_area("Resultado Examen", paciente["Resultado Examen"] if pd.notnull(paciente["Resultado Examen"]) else "", height=100)
                        diagnostico = st.text_area("Diagnóstico", paciente["Diagnostico"] if pd.notnull(paciente["Diagnostico"]) else "", height=100)
                        objetivos = st.text_area("Objetivos Tratamiento", paciente["Objetivos Tratamiento"] if pd.notnull(paciente["Objetivos Tratamiento"]) else "", height=100)
                        tecnicas = st.text_area("Técnicas", paciente["Tecnicas"] if pd.notnull(paciente["Tecnicas"]) else "", height=100)
                        fecha_consulta = st.text_input("Fecha Consulta", paciente["Fecha Consulta"] if pd.notnull(paciente["Fecha Consulta"]) else "")
                        terapeuta = st.text_input("Terapeuta", paciente["Terapeuta"] if pd.notnull(paciente["Terapeuta"]) else "")
                    
                    # Botón para guardar cambios
                    if st.button("Guardar cambios", key="save_individual"):
                        # Actualizar los datos en el DataFrame
                        df.at[paciente_index, "Nombre"] = nombre
                        df.at[paciente_index, "Sexo"] = sexo
                        df.at[paciente_index, "Edad"] = edad
                        df.at[paciente_index, "Estudios"] = estudios
                        df.at[paciente_index, "Origen"] = origen
                        df.at[paciente_index, "Ocupacion"] = ocupacion
                        df.at[paciente_index, "Estado Civil"] = estado_civil
                        df.at[paciente_index, "Religion"] = religion
                        df.at[paciente_index, "Progenitores"] = progenitores
                        df.at[paciente_index, "Motivo Consulta"] = motivo
                        df.at[paciente_index, "Fecha Inicio Sintomas"] = fecha_inicio
                        df.at[paciente_index, "Antecedentes"] = antecedentes
                        df.at[paciente_index, "Desarrollo Psicomotor"] = desarrollo
                        df.at[paciente_index, "Alimentacion"] = alimentacion
                        df.at[paciente_index, "Habitos de Sueño"] = sueno
                        df.at[paciente_index, "Perfil Social"] = perfil_social
                        df.at[paciente_index, "Otros"] = otros
                        df.at[paciente_index, "Resultado Examen"] = resultado
                        df.at[paciente_index, "Diagnostico"] = diagnostico
                        df.at[paciente_index, "Objetivos Tratamiento"] = objetivos
                        df.at[paciente_index, "Tecnicas"] = tecnicas
                        df.at[paciente_index, "Fecha Consulta"] = fecha_consulta
                        df.at[paciente_index, "Terapeuta"] = terapeuta
                        df.at[paciente_index, 'Fecha Modificacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      
                        st.success("¡Cambios guardados exitosamente!")
    
                        if save_data(df, sheet):
                            # Recargar datos para reflejar los cambios
                            df = load_data()
                            st.success(f"Datos del paciente {nombre} actualizados correctamente")
                            
                            # Generar PDF y crear botón de descarga
                            pdf_bytes = generate_patient_pdf(paciente)
                            st.download_button(
                                label="Descargar Historia Clínica (PDF)",
                                data=pdf_bytes,
                                file_name=f"historia_clinica_{nombre}.pdf",
                                mime="application/pdf"
                            )    
                            
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


# Función para generar PDF de historia clínica
def generate_patient_pdf(patient_data):

    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Crear un estilo personalizado para títulos
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=12
    )
    
    # Crear un estilo personalizado para subtítulos
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.darkblue,
        spaceAfter=10
    )
    
    # Crear un estilo personalizado para el texto normal
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6
    )
    
    # Lista para almacenar los elementos del PDF
    elements = []
    
    # Título del documento
    elements.append(Paragraph("Historia Clínica Psicológica", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Fecha de emisión
    elements.append(Paragraph(f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Datos del paciente
    elements.append(Paragraph("Datos Personales", title_style))
    
    # Tabla con datos personales
    data = [
        ["ID", patient_data.get("ID", "")],
        ["Nombre", patient_data.get("Nombre", "")],
        ["Sexo", patient_data.get("Sexo", "")],
        ["Edad", str(patient_data.get("Edad", ""))],
        ["Estudios", patient_data.get("Estudios", "")],
        ["Origen", patient_data.get("Origen", "")],
        ["Ocupación", patient_data.get("Ocupacion", "")],
        ["Estado Civil", patient_data.get("Estado Civil", "")],
        ["Religión", patient_data.get("Religion", "")],
    ]
    
    # Crear tabla
    t = Table(data, colWidths=[2*inch, 4*inch])
    
    # Estilo de la tabla
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 0.2*inch))
    
    # Motivo de consulta
    elements.append(Paragraph("Motivo de Consulta", subtitle_style))
    elements.append(Paragraph(patient_data.get("Motivo Consulta", ""), normal_style))
    elements.append(Paragraph(f"Fecha de inicio de síntomas: {patient_data.get('Fecha Inicio Sintomas', '')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Antecedentes
    elements.append(Paragraph("Antecedentes del Paciente", subtitle_style))
    elements.append(Paragraph(f"<b>Antecedentes:</b> {patient_data.get('Antecedentes', '')}", normal_style))
    elements.append(Paragraph(f"<b>Desarrollo Psicomotor:</b> {patient_data.get('Desarrollo Psicomotor', '')}", normal_style))
    elements.append(Paragraph(f"<b>Alimentación:</b> {patient_data.get('Alimentacion', '')}", normal_style))
    elements.append(Paragraph(f"<b>Hábitos de Sueño:</b> {patient_data.get('Habitos de Sueño', '')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Perfil Social
    elements.append(Paragraph("Perfil Social y Personalidad", subtitle_style))
    elements.append(Paragraph(f"<b>Perfil Social:</b> {patient_data.get('Perfil Social', '')}", normal_style))
    elements.append(Paragraph(f"<b>Otros:</b> {patient_data.get('Otros', '')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Examen Mental y Diagnóstico
    elements.append(Paragraph("Examen Mental y Diagnóstico", subtitle_style))
    elements.append(Paragraph(f"<b>Resultado del Examen:</b> {patient_data.get('Resultado Examen', '')}", normal_style))
    elements.append(Paragraph(f"<b>Diagnóstico:</b> {patient_data.get('Diagnostico', '')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Plan de Tratamiento
    elements.append(Paragraph("Plan de Tratamiento", subtitle_style))
    elements.append(Paragraph(f"<b>Objetivos del Tratamiento:</b> {patient_data.get('Objetivos Tratamiento', '')}", normal_style))
    elements.append(Paragraph(f"<b>Técnicas a Emplear:</b> {patient_data.get('Tecnicas', '')}", normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Información de la Consulta
    elements.append(Paragraph("Información de la Consulta", subtitle_style))
    elements.append(Paragraph(f"<b>Fecha de la Consulta:</b> {patient_data.get('Fecha Consulta', '')}", normal_style))
    elements.append(Paragraph(f"<b>Terapeuta:</b> {patient_data.get('Terapeuta', '')}", normal_style))
    elements.append(Paragraph(f"<b>Fecha de Registro:</b> {patient_data.get('Fecha Registro', '')}", normal_style))
    
    # Pie de página
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("Clínica de Psicología del Amor - Documento Confidencial", 
                  ParagraphStyle(name='Footer', parent=styles['Normal'], fontSize=8, alignment=1)))
    
    # Generar PDF
    doc.build(elements)
    
    # Obtener el contenido del PDF
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content

# Función para crear un botón de descarga de PDF
def get_pdf_download_link(pdf_bytes, filename="historia_clinica.pdf", text="Descargar PDF"):
    """Genera un enlace HTML para descargar un archivo PDF."""
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'

# Footer
st.markdown("---")
st.markdown("© 2025 Clínica de Psicología del Amor- Sistema de Gestión de Historias Clínicas")

#if __name__ == '__main__':
#    consulta_historia()