import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# Configuración de la página
st.set_page_config(
    page_title="Historia Clínica Psicológica",
    page_icon="🧠",
    layout="wide"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4e89ae;
        color: white;
    }
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    .section-title {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Función para conectar con Google Sheets
@st.cache_resource
def connect_to_gsheets():
    try:
        # Definir el alcance
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        # Añadir credenciales a la cuenta
        # NOTA: Necesitarás un archivo JSON con las credenciales de servicio de Google
        # Deberás crear este archivo siguiendo las instrucciones en la documentación de Google Cloud
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        # Autorizar la clientela
        client = gspread.authorize(creds)
        
        # Abrir la hoja existente
        spreadsheet = client.open('gestion-resservas-amo')
        
        # Obtener la hoja específica
        sheet = spreadsheet.worksheet('historia_clinica')
        
        return sheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para cargar datos existentes
def load_data():
    try:
        sheet = connect_to_gsheets()
        if sheet:
            # Obtener todos los datos
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

# Función para guardar nueva historia clínica
def save_history(patient_data):
    try:
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
                if df.empty:
                    new_id = 1
                else:
                    new_id = int(df['ID'].max()) + 1
            
            # Preparar la fila a añadir
            row_data = [new_id] + list(patient_data.values())
            sheet.append_row(row_data)
            
            return True, new_id
        return False, None
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")
        return False, None

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
        result = df[df['Nombre y apellidos'].str.contains(search_term, case=False, na=False)]
    
    return result

# Función para actualizar historia clínica
def update_history(id, updated_data):
    try:
        sheet = connect_to_gsheets()
        if sheet:
            # Obtener todos los datos
            df = pd.DataFrame(sheet.get_all_records())
            
            # Obtener los encabezados
            headers = sheet.row_values(1)
            
            # Encontrar la fila que corresponde al ID
            row_to_update = df[df['ID'] == id].index[0] + 2  # +2 porque la fila 1 son los encabezados
            
            # Actualizar cada celda
            for col, value in updated_data.items():
                if col in headers:
                    col_index = headers.index(col) + 1  # +1 porque gspread es 1-indexed
                    sheet.update_cell(row_to_update, col_index, value)
            
            return True
        return False
    except Exception as e:
        st.error(f"Error al actualizar datos: {e}")
        return False

# Título principal y descripción
st.title("🧠 Sistema de Gestión de Historias Clínicas Psicológicas")
st.markdown("Sistema para crear y gestionar historias clínicas de pacientes en una clínica de psicología.")

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
            nombre = st.text_input("Nombre y apellidos*")
            edad = st.number_input("Edad*", min_value=0, max_value=120, step=1)
            origen = st.text_input("Origen y procedencia")
        
        with col2:
            sexo = st.selectbox("Sexo*", ["", "Masculino", "Femenino", "No binario", "Prefiere no decir"])
            estudios = st.selectbox("Nivel de estudios", ["", "Sin estudios", "Primaria", "Secundaria", "Bachillerato", "Formación Profesional", "Universidad", "Posgrado"])
            ocupacion = st.text_input("Ocupación")
        
        with col3:
            estado_civil = st.selectbox("Estado civil", ["", "Soltero/a", "Casado/a", "Unión libre", "Separado/a", "Divorciado/a", "Viudo/a"])
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
        personalidad = st.text_area("Características psicológicas relevantes", height=150, help="Características psicológicas más relevantes del paciente, algo que se va desgranando a través de las entrevistas psicológicas.")
        
        # Sección: Historia familiar
        st.markdown('<div class="section-title"><h3>Historia Familiar</h3></div>', unsafe_allow_html=True)
        historia_familiar = st.text_area("Datos relevantes sobre la familia del paciente", height=150)
        
        # Sección: Examen mental
        st.markdown('<div class="section-title"><h3>Examen Mental</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
            apariencia = st.text_area("Apariencia general y actitud", height=80)
            conciencia = st.text_area("Estado de conciencia", height=80)
            animo = st.text_area("Estado de ánimo", height=80)
            motor = st.text_area("Actividad motora", height=80)
        
        with col2:
            lenguaje = st.text_area("Asociación y flujo de ideas y características del lenguaje", height=80)
            contenido_ideas = st.text_area("Contenido de ideas", height=80)
            sensorium = st.text_area("Sensorium", height=80)
            memoria = st.text_area("Memoria", height=80)
        
        pensamiento = st.text_area("Pensamiento", height=100)
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
            if not nombre or not edad or not sexo or not motivo_consulta or not diagnostico or not terapeuta:
                st.error("Por favor, complete todos los campos marcados con *")
            else:
                # Crear diccionario con todos los datos
                patient_data = {
                    "Nombre y apellidos": nombre,
                    "Sexo": sexo,
                    "Edad": edad,
                    "Estudios": estudios,
                    "Origen y procedencia": origen,
                    "Ocupación": ocupacion,
                    "Estado civil": estado_civil,
                    "Religión": religion,
                    "Datos de los progenitores": datos_progenitores,
                    "Motivo de la consulta": motivo_consulta,
                    "Fecha inicio síntomas": fecha_inicio_sintomas.strftime('%Y-%m-%d'),
                    "Antecedentes": antecedentes,
                    "Desarrollo psicomotor": desarrollo_psicomotor,
                    "Alimentación": habitos_alimentacion,
                    "Hábitos de sueño": habitos_sueno,
                    "Perfil social": perfil_social,
                    "Personalidad": personalidad,
                    "Historia familiar": historia_familiar,
                    "Apariencia": apariencia,
                    "Estado de conciencia": conciencia,
                    "Estado de ánimo": animo,
                    "Actividad motora": motor,
                    "Lenguaje": lenguaje,
                    "Contenido de ideas": contenido_ideas,
                    "Sensorium": sensorium,
                    "Memoria": memoria,
                    "Pensamiento": pensamiento,
                    "Resultado examen": resultado_examen,
                    "Diagnóstico": diagnostico,
                    "Objetivos tratamiento": objetivos,
                    "Técnicas": tecnicas,
                    "Fecha consulta": fecha_consulta.strftime('%Y-%m-%d'),
                    "Terapeuta": terapeuta,
                    "Fecha registro": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                with st.spinner("Guardando datos..."):
                    success, new_id = save_history(patient_data)
                    if success:
                        st.success(f"Historia clínica guardada correctamente con ID: {new_id}")
                        time.sleep(2)
                        st.experimental_rerun()
                    else:
                        st.error("Error al guardar la historia clínica. Verifique la conexión a Google Drive.")

with tab2:
    st.header("Buscar Paciente")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("Buscar paciente", placeholder="Ingrese ID o nombre del paciente")
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
                    st.dataframe(results[['ID', 'Nombre y apellidos', 'Edad', 'Diagnóstico', 'Fecha consulta']])
                    
                    # Seleccionar paciente para ver detalles
                    if not results.empty:
                        selected_id = st.selectbox("Seleccione un paciente para ver detalles", 
                                               options=results['ID'].tolist(),
                                               format_func=lambda x: f"ID: {x} - {results[results['ID']==x]['Nombre y apellidos'].values[0]}")
                        
                        if selected_id:
                            patient = results[results['ID'] == selected_id].iloc[0].to_dict()
                            
                            # Mostrar detalles del paciente
                            with st.expander("Datos generales", expanded=True):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.write(f"**Nombre:** {patient['Nombre y apellidos']}")
                                    st.write(f"**Edad:** {patient['Edad']}")
                                    st.write(f"**Origen:** {patient['Origen y procedencia']}")
                                with col2:
                                    st.write(f"**Sexo:** {patient['Sexo']}")
                                    st.write(f"**Estudios:** {patient['Estudios']}")
                                    st.write(f"**Ocupación:** {patient['Ocupación']}")
                                with col3:
                                    st.write(f"**Estado civil:** {patient['Estado civil']}")
                                    st.write(f"**Religión:** {patient['Religión']}")
                            
                            with st.expander("Motivo de consulta"):
                                st.write(f"**Motivo:** {patient['Motivo de la consulta']}")
                                st.write(f"**Fecha inicio síntomas:** {patient['Fecha inicio síntomas']}")
                            
                            with st.expander("Diagnóstico y plan"):
                                st.write(f"**Diagnóstico:** {patient['Diagnóstico']}")
                                st.write(f"**Objetivos tratamiento:** {patient['Objetivos tratamiento']}")
                                st.write(f"**Técnicas:** {patient['Técnicas']}")
                            
                            # Botón para editar paciente
                            if st.button("Editar paciente"):
                                st.session_state['editing_patient'] = patient
                                st.session_state['editing_mode'] = True
                            
                            # Mostrar formulario de edición si está en modo edición
                            if st.session_state.get('editing_mode', False) and st.session_state.get('editing_patient', {}).get('ID') == selected_id:
                                with st.form(key="edit_historia_form"):
                                    st.subheader(f"Editar historia clínica - {patient['Nombre y apellidos']}")
                                    
                                    # Recrear el formulario pero con los valores actuales
                                    edited_data = {}
                                    
                                    # Datos generales (ejemplo, puedes expandir según necesites)
                                    st.markdown('<div class="section-title"><h3>Datos Generales</h3></div>', unsafe_allow_html=True)
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        edited_data["Nombre y apellidos"] = st.text_input("Nombre y apellidos*", value=patient['Nombre y apellidos'])
                                        edited_data["Edad"] = st.number_input("Edad*", min_value=0, max_value=120, step=1, value=int(patient['Edad']))
                                        edited_data["Origen y procedencia"] = st.text_input("Origen y procedencia", value=patient['Origen y procedencia'])
                                    
                                    with col2:
                                        edited_data["Sexo"] = st.selectbox("Sexo*", ["", "Masculino", "Femenino", "No binario", "Prefiere no decir"], index=["", "Masculino", "Femenino", "No binario", "Prefiere no decir"].index(patient['Sexo']) if patient['Sexo'] in ["", "Masculino", "Femenino", "No binario", "Prefiere no decir"] else 0)
                                        edited_data["Estudios"] = st.text_input("Estudios", value=patient['Estudios'])
                                        edited_data["Ocupación"] = st.text_input("Ocupación", value=patient['Ocupación'])
                                    
                                    with col3:
                                        edited_data["Estado civil"] = st.text_input("Estado civil", value=patient['Estado civil'])
                                        edited_data["Religión"] = st.text_input("Religión", value=patient['Religión'])
                                    
                                    # Motivo de consulta
                                    st.markdown('<div class="section-title"><h3>Motivo de Consulta</h3></div>', unsafe_allow_html=True)
                                    edited_data["Motivo de la consulta"] = st.text_area("Motivo de la consulta*", value=patient['Motivo de la consulta'], height=150)
                                    
                                    # Diagnóstico
                                    st.markdown('<div class="section-title"><h3>Diagnóstico</h3></div>', unsafe_allow_html=True)
                                    edited_data["Diagnóstico"] = st.text_area("Diagnóstico del paciente*", value=patient['Diagnóstico'], height=150)
                                    
                                    # Plan
                                    st.markdown('<div class="section-title"><h3>Plan de Orientación</h3></div>', unsafe_allow_html=True)
                                    edited_data["Objetivos tratamiento"] = st.text_area("Objetivos del tratamiento", value=patient['Objetivos tratamiento'], height=100)
                                    edited_data["Técnicas"] = st.text_area("Técnicas a emplear", value=patient['Técnicas'], height=100)
                                    
                                    # Actualizar botón
                                    update_button = st.form_submit_button(label="Actualizar Historia Clínica")
                                    
                                    if update_button:
                                        # Validaciones
                                        if not edited_data["Nombre y apellidos"] or not edited_data["Edad"] or not edited_data["Sexo"] or not edited_data["Motivo de la consulta"] or not edited_data["Diagnóstico"]:
                                            st.error("Por favor, complete todos los campos marcados con *")
                                        else:
                                            with st.spinner("Actualizando datos..."):
                                                success = update_history(selected_id, edited_data)
                                                if success:
                                                    st.success("Historia clínica actualizada correctamente")
                                                    st.session_state['editing_mode'] = False
                                                    time.sleep(2)
                                                    st.experimental_rerun()
                                                else:
                                                    st.error("Error al actualizar la historia clínica")
                                
                                if st.button("Cancelar edición"):
                                    st.session_state['editing_mode'] = False
                                    st.experimental_rerun()

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
                if 'Motivo de la consulta' in data.columns:
                    keywords = ['ansiedad', 'depresión', 'estrés', 'pareja', 'familiar', 'fobia', 'trauma']
                    motivo_counts = {}
                    
                    for keyword in keywords:
                        count = data['Motivo de la consulta'].str.contains(keyword, case=False, na=False).sum()
                        if count > 0:
                            motivo_counts[keyword] = count
                    
                    if motivo_counts:
                        motivo_df = pd.DataFrame({'Conteo': motivo_counts})
                        st.bar_chart(motivo_df)
                    else:
                        st.info("No se encontraron motivos de consulta para analizar")
            
            with col2:
                st.subheader("Consultas por mes")
                if 'Fecha consulta' in data.columns:
                    data['Fecha consulta'] = pd.to_datetime(data['Fecha consulta'], errors='coerce')
                    data['Mes'] = data['Fecha consulta'].dt.strftime('%Y-%m')
                    mes_counts = data['Mes'].value_counts().sort_index()
                    st.line_chart(mes_counts)

# Instrucciones de instalación y uso
with st.expander("Instrucciones de instalación y uso"):
    st.markdown("""
    ### Requisitos previos
    1. Tener una cuenta de Google
    2. Crear un proyecto en Google Cloud Platform
    3. Habilitar la API de Google Sheets
    4. Crear credenciales de servicio y descargar el archivo JSON
    
    ### Instalación
    1. Clone este repositorio
    2. Instale las dependencias: `pip install streamlit pandas gspread oauth2client`
    3. Coloque el archivo de credenciales `credentials.json` en el mismo directorio que este script
    4. Asegúrese de tener una hoja de cálculo en Google Sheets llamada "gestion-resservas-amo" con una hoja llamada "historia_clinica"
    5. Comparta su hoja de cálculo con la dirección de correo que aparece en su archivo de credenciales
    
    ### Ejecución
    Ejecute el script con: `streamlit run app.py`
    """)

# Footer
st.markdown("---")
st.markdown("© 2025 Clínica de Psicología - Sistema de Gestión de Historias Clínicas")
