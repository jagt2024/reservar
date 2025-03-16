import streamlit as st
import pandas as pd
import gspread
import time
import json
import toml
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError

# Configuración de la página
#st.set_page_config(
#    page_title="Editor de Historia Clínica",
#    page_icon="📋",
#    layout="wide"
#)

# Constantes para reintentos
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Función para cargar credenciales desde el archivo secrets.toml
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
                'Ocupacion', 'Estado Civil', 'Religion', 'Progenitores',
                'Motivo Consulta', 'Fecha Inicio Sintomas', 'Antecedentes',
                'Desarrollo Psicomotor', 'Alimentacion', 'Habitos de Sueño', 'Perfil Social','Otros',
                'Resultado Examen', 'Diagnostico', 'Objetivos Tratamiento', 'Tecnicas', 
                'Fecha Consulta', 'Terapeuta', 'Fecha Registro', 'Fecha Modificacion'
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

# Título principal
st.title("Editor de Historia Clínica")
st.markdown("Esta aplicación permite editar los registros de historias clínicas almacenados en Google Sheets.")

# Inicializar la conexión y cargar datos
sheet = connect_to_gsheets()
if sheet:
    df = load_data()
    
    if not df.empty:
        # Crear pestañas para diferentes funcionalidades
        tab1, tab2 = st.tabs(["Ver y Editar Todos los Registros", "Editar Registro Individual"])
        
        with tab1:
            st.subheader("Todos los Registros")
            
            # Mejorar la sección de búsqueda
            st.write("Ingrese texto para buscar por ID o Nombre:")
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input(
                    "Búsqueda", "", key="search_input", placeholder="Ingrese ID o Nombre",  label_visibility="collapsed"  # This hides the label visually but keeps it for screen readers
)
            with col2:
                search_button = st.button("Buscar", key="search_button")
            
            # Aplicar filtro
            filtered_df = filter_data(df, search_term)
            
            # Mostrar resultados de búsqueda
            if search_term:
                st.write(f"Resultados encontrados: {len(filtered_df)} registros")
                if len(filtered_df) == 0:
                    st.warning(f"No se encontraron registros con '{search_term}'")
                    st.write("Mostrando todos los registros:")
                    filtered_df = df  # Mostrar todos si no hay resultados
            
            # Mostrar el DataFrame en un editor
            edited_df = st.data_editor(
                filtered_df,
                num_rows="dynamic",
                use_container_width=True,
                key="full_editor",
                height=400
            )
            
            # Botón para guardar cambios
            if st.button("Guardar todos los cambios", key="save_all"):
                # Actualizar el DataFrame original con los cambios
                if search_term and not filtered_df.empty:
                    # Si hay filtro, actualizar solo las filas correspondientes
                    for idx, row in edited_df.iterrows():
                        id_to_update = row['ID']
                        # Encontrar el índice correspondiente en el DataFrame original
                        original_idx = df[df['ID'].astype(str) == str(id_to_update)].index
                        if not original_idx.empty:
                            df.loc[original_idx[0]] = row
                else:
                    # Si no hay filtro, simplemente reemplazar todo
                    df = edited_df
                
                # Guardar en Google Sheets
                if save_data(df, sheet):
                    # Recargar datos para reflejar los cambios
                    st.success("Cambios guardados correctamente")
                    df = load_data()
                    # Actualizar la visualización
                    filtered_df = filter_data(df, search_term)
        
        with tab2:
            st.subheader("Editar Registro Individual")
            
            # Selector de paciente con búsqueda
            st.write("Buscar paciente específico:")
            search_patient = st.text_input("Búsqueda de paciente", "", key="search_patient",  placeholder="Ingrese ID o Nombre del paciente", label_visibility="collapsed")
            
            # Filtrar las opciones del selector basado en la búsqueda
            df_copy = df.copy()
            df_copy['ID'] = df_copy['ID'].astype(str)
            
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

                            # Guardar el DataFrame actualizado (opcional)
                            df.to_csv("datos_empleados.csv", index=False)