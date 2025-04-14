import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import toml
import base64
import re
from io import BytesIO
from gspread.exceptions import APIError
from googleapiclient.errors import HttpError

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

st.set_page_config(page_title="Personal Information Form", page_icon="📝", layout="wide")

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.8rem;
        color: #34495e;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        color: #155724;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .warning-message {
        padding: 1rem;
        background-color: #fff3cd;
        color: #856404;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem;
        font-size: 1.1rem;
        border-radius: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

def load_credentials_from_toml():
    """Carga las credenciales desde el archivo secrets.toml"""
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

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    """Establece conexión con Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {str(e)}")
        return None

def get_all_data(client):
    """Obtiene todos los datos guardados en la hoja"""
    try:
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('ordenes')
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        st.error(f"Error al obtener los datos: {str(e)}")
        return []

def check_duplicate_email(client, email):
    """Comprueba si ya existe un registro con el mismo correo electrónico"""
    try:
        # Obtener todos los registros
        records = get_all_data(client)
        
        # Identificar el nombre de la columna de email
        # (puede variar dependiendo de la estructura de tu hoja)
        email_column = None
        if records and len(records) > 0:
            # Tomar el primer registro para ver las claves disponibles
            first_record = records[0]
            # Buscar la columna que podría contener emails
            possible_email_columns = ['email', 'Email', 'correo', 'Correo', 'E-mail']
            for col in possible_email_columns:
                if col in first_record:
                    email_column = col
                    break
        
        # Si no encontramos una columna de email, no podemos verificar duplicados
        if not email_column:
            st.warning("No se pudo identificar la columna de email en la hoja.")
            return False
        
        # Buscar el email en los registros
        for record in records:
            record_email = record.get(email_column, '').strip().lower()
            if record_email == email.strip().lower():
                return True
        
        return False
    except Exception as e:
        st.error(f"Error al verificar duplicados: {str(e)}")
        # En caso de error, permitimos continuar (mejor opción que bloquear)
        return False

def save_form_data(client, data):
    """Guarda los datos del formulario en Google Sheets"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Guardando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                # Abre la hoja de cálculo y la hoja específica
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                
                # Añade la nueva fila con los datos
                worksheet.append_row([
                    data['first_name'],
                    data['last_name'],
                    data['email'],
                    data['phone'],
                    data['estate']
                ])
                
                return True
        
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
            st.error(f"Error al guardar los datos: {str(e)}")
            return False
    
    return False

def validate_email(email):
    """Valida formato de email"""
    if not email:
        return False
    pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
    return bool(re.match(pattern, email))

def to_excel(df):
    """Convierte un DataFrame a Excel y genera un link de descarga"""
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Datos')
    writer.close()
    processed_data = output.getvalue()
    b64 = base64.b64encode(processed_data).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="datos_agenda.xlsx">Descargar archivo Excel</a>'

def limpiar_campos_formulario():
    
    try:
        # Lista de campos a limpiar
         valores_default = {
            'first_name': '',
            'last_name': '',
            'email': '',
            'phone': '',
            'estate': ''
         }
        
         # Actualizar el session state con los valores por defecto
         for campo, valor in valores_default.items():
            if campo in st.session_state:
                # Eliminar la entrada actual del session state
                del st.session_state[campo]
        
         # Forzar la recarga de la página para reiniciar los widgets
         st.rerun()
        
         return True
        
    except Exception as e:
        st.error(f"Error al limpiar los campos del formulario: {str(e)}")
        logging.error(f"Error en limpiar_campos_formulario: {str(e)}")
        return False

def inicializar_valores_default():
    
    valores_default = {
            'first_name': '',
            'last_name': '',
            'email': '',
            'phone': '',
            'estate': ''
            }
    
    for campo, valor in valores_default.items():
        if campo not in st.session_state:
            st.session_state[campo] = valor

# Inicialización de las variables de estado
if 'show_success_message' not in st.session_state:
    st.session_state.show_success_message = False

if 'show_duplicate_message' not in st.session_state:
    st.session_state.show_duplicate_message = False

def main():
    st.header('Please fill in your details below')
    st.write("---")
    st.markdown('<h1 class="main-header">Formulario de Captura de Datos</h1>', unsafe_allow_html=True)
    
    # Cargar credenciales
    creds = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales. Verifica el archivo secrets.toml")
        return
    
    # Establecer conexión con Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        return
    
    # Inicializar valores por defecto
    inicializar_valores_default()
    
    # Crear columnas para el diseño
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        #st.markdown('<h2 class="section-header">Formulario de Registro</h2>', unsafe_allow_html=True)
        
        # Mostrar mensajes de estado
        if st.session_state.show_success_message:
            st.markdown('<div class="success-message">¡Datos guardados exitosamente!</div>', unsafe_allow_html=True)
            st.session_state.show_success_message = False
            
        if st.session_state.show_duplicate_message:
            st.markdown('<div class="warning-message">¡Este correo electrónico ya está registrado!</div>', unsafe_allow_html=True)
            st.session_state.show_duplicate_message = False
        
        # Formulario de contacto
        with st.form(key='contact_form'):
            first_name = st.text_input("First Name", placeholder="Input First Name")
            last_name = st.text_input("Last Name", placeholder="Input Last Name")
            email = st.text_input("Email", placeholder="Input Email")
            phone = st.text_input("Phone Number", placeholder="Input Phone Number")
            
            # Opciones para Estate (Estado/Propiedad)
            #estate_options = ["Seleccione un estado", "Activo", "Inactivo", "Pendiente", "Completado"]
            estate = st.text_input("Estate",  placeholder="Input Estate")
            #selectbox("Estado", estate_options)
            
            submit_button = st.form_submit_button(label="Guardar Información", type="primary")
            
            if submit_button:
                # Validación de campos obligatorios
                if not (first_name and last_name and email and phone and estate != "Seleccione un estado"):
                    st.error("Por favor, complete todos los campos.")
                    return
                
                # Validación de formato de email
                if not validate_email(email):
                    st.warning('El email no es válido')
                    return
                
                # Verificación de duplicados
                if check_duplicate_email(client, email):
                    st.session_state.show_duplicate_message = True
                    st.rerun()  # Usamos rerun para mostrar el mensaje inmediatamente
                
                # Guardar datos
                data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                    'estate': estate
                }
                
                if save_form_data(client, data):
                    # Mostrar mensaje de éxito y reiniciar el formulario
                    st.session_state.show_success_message = True
                    st.rerun()  # Esto reinicia la aplicación y limpia el formulario
                    
                if limpiar_campos_formulario():
                    st.session_state.show_success_message = []
    
    #clear_session_state()  
    
    # Mostrar datos guardados
    st.markdown('<h2 class="section-header">Registros Guardados</h2>', unsafe_allow_html=True)
    
    # Obtener y mostrar datos
    records = get_all_data(client)
    if records:
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True)
        
        # Generar botón de descarga Excel
        st.markdown('<h3>Exportar datos</h3>', unsafe_allow_html=True)
        excel_link = to_excel(df)
        st.markdown(excel_link, unsafe_allow_html=True)
    else:
        st.info("No hay registros guardados todavía.")

if __name__ == "__main__":
    main()