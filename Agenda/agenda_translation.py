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

# Constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Cargar configuraciones desde config.toml
with open("./.streamlit/config.toml", "r") as f:
    config = toml.load(f)

# Translations dictionary for agenda module
translations = {
    "en": {
        "page_title": "Personal Information Form",
        "header": "Personal Information Form",
        "form_subtitle": "Please fill in your details below",
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email",
        "phone": "Phone Number",
        "estate": "Estate",
        "success_message": "Data saved successfully!",
        "duplicate_message": "This email is already registered!",
        "delete_message": "Record deleted successfully!",
        "save_button": "Save Information",
        "required_fields": "Please complete all fields.",
        "invalid_email": "Invalid email format",
        "saved_records": "Saved Records",
        "delete_record": "Delete Record",
        "select_record": "Select record to delete",
        "delete_button": "Delete Record",
        "delete_help": "Delete the selected record permanently",
        "export_data": "Export Data",
        "no_records": "No records saved yet.",
        "loading_data": "Loading data... (Attempt {}/{MAX_RETRIES})",
        "deleting_record": "Deleting record... (Attempt {}/{MAX_RETRIES})",
        "saving_data": "Saving data... (Attempt {}/{MAX_RETRIES})",
        "rate_limit": "Rate limit exceeded. Waiting {} seconds...",
        "max_retries": "Maximum retry attempts exceeded. Please try again later.",
        "api_error": "API Error: {}",
        "error_loading": "Error loading credentials: {}",
        "error_connecting": "Error connecting to Google Sheets: {}",
        "error_retrieving": "Error retrieving data: {}",
        "error_row_ids": "Error retrieving data with row IDs: {}",
        "error_deleting": "Error deleting record: {}",
        "error_duplicates": "Error checking for duplicates: {}",
        "error_saving": "Error saving data: {}",
        "email_column_warning": "Could not identify email column in the sheet.",
        "credentials_error": "Could not load credentials. Please verify the secrets.toml file",
        "first_name_placeholder": "Input First Name",
        "last_name_placeholder": "Input Last Name",
        "email_placeholder": "Input Email",
        "phone_placeholder": "Input Phone Number",
        "estate_placeholder": "Input Estate"
    },
    "es": {
        "page_title": "Formulario de Información Personal",
        "header": "Formulario de Información Personal",
        "form_subtitle": "Por favor, complete sus datos a continuación",
        "first_name": "Nombre",
        "last_name": "Apellido",
        "email": "Correo Electrónico",
        "phone": "Número de Teléfono",
        "estate": "Estado",
        "success_message": "¡Datos guardados exitosamente!",
        "duplicate_message": "¡Este correo electrónico ya está registrado!",
        "delete_message": "¡Registro eliminado exitosamente!",
        "save_button": "Guardar Información",
        "required_fields": "Por favor complete todos los campos.",
        "invalid_email": "Formato de correo electrónico inválido",
        "saved_records": "Registros Guardados",
        "delete_record": "Eliminar Registro",
        "select_record": "Seleccione registro para eliminar",
        "delete_button": "Eliminar Registro",
        "delete_help": "Eliminar el registro seleccionado permanentemente",
        "export_data": "Exportar Datos",
        "no_records": "Aún no hay registros guardados.",
        "loading_data": "Cargando datos... (Intento {}/{MAX_RETRIES})",
        "deleting_record": "Eliminando registro... (Intento {}/{MAX_RETRIES})",
        "saving_data": "Guardando datos... (Intento {}/{MAX_RETRIES})",
        "rate_limit": "Límite de cuota excedida. Esperando {} segundos...",
        "max_retries": "Se excedió el límite de intentos. Por favor, intenta más tarde.",
        "api_error": "Error de la API: {}",
        "error_loading": "Error al cargar credenciales: {}",
        "error_connecting": "Error al conectar con Google Sheets: {}",
        "error_retrieving": "Error al recuperar datos: {}",
        "error_row_ids": "Error al recuperar datos con IDs de fila: {}",
        "error_deleting": "Error al eliminar registro: {}",
        "error_duplicates": "Error al verificar duplicados: {}",
        "error_saving": "Error al guardar datos: {}",
        "email_column_warning": "No se pudo identificar la columna de correo electrónico en la hoja.",
        "credentials_error": "No se pudieron cargar las credenciales. Por favor verifique el archivo secrets.toml",
        "first_name_placeholder": "Ingrese Nombre",
        "last_name_placeholder": "Ingrese Apellido",
        "email_placeholder": "Ingrese Correo Electrónico",
        "phone_placeholder": "Ingrese Número de Teléfono",
        "estate_placeholder": "Ingrese Estado"
    }
}

def get_translation(key):
    """Get translation based on current language in session state"""
    # Default to English if language is not set
    lang = "en"
    if "language" in st.session_state:
        lang = st.session_state.language
    
    # Return the translated text or the key itself if not found
    return translations.get(lang, {}).get(key, key)

def initialize_session_state():
    """Initialize all session state variables if they don't exist"""
    if 'show_success_message' not in st.session_state:
        st.session_state.show_success_message = False
    
    if 'show_duplicate_message' not in st.session_state:
        st.session_state.show_duplicate_message = False
    
    if 'show_delete_message' not in st.session_state:
        st.session_state.show_delete_message = False
    
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
    # Initialize form fields
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate']
    for field in form_fields:
        if field not in st.session_state:
            st.session_state[field] = ""

def clear_session_state():
    #Clear all session state variables
    for key in list(st.session_state.keys()):
        if key not in ['show_success_message', 'show_duplicate_message', 'show_delete_message', 'language']:
            del st.session_state[key]

def load_credentials_from_toml():
    #Load credentials from secrets.toml file
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(get_translation("error_loading").format(str(e)))
        return None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    #Establish connection with Google Sheets
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(get_translation("error_connecting").format(str(e)))
        return None

def get_all_data(client):
    """Get all data saved in the sheet"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(get_translation("loading_data").format(intento + 1, MAX_RETRIES)):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                records = worksheet.get_all_records()
                return records

        except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(get_translation("rate_limit").format(delay))
                    time.sleep(delay)
                    continue
                else:
                    st.error(get_translation("max_retries"))
            else:
                st.error(get_translation("api_error").format(str(error)))
            return False

        except Exception as e:
            st.error(get_translation("error_retrieving").format(str(e)))
            return []

def get_worksheet_data_with_row_ids(client):
    """Get all data with row numbers for deletion functionality"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(get_translation("loading_data").format(intento + 1, MAX_RETRIES)):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                
                # Get all values including headers
                all_values = worksheet.get_all_values()
                
                if len(all_values) <= 1:  # Only headers or empty
                    return pd.DataFrame(), []
                    
                # Extract headers and data
                headers = all_values[0]
                data = all_values[1:]
                
                # Create DataFrame with row indices (add 2 because row 1 is header and gspread is 1-indexed)
                df = pd.DataFrame(data, columns=headers)
                row_ids = [i+2 for i in range(len(data))]
                
                return df, row_ids

        except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(get_translation("rate_limit").format(delay))
                    time.sleep(delay)
                    continue
                else:
                    st.error(get_translation("max_retries"))
            else:
                st.error(get_translation("api_error").format(str(error)))
            return False

        except Exception as e:
            st.error(get_translation("error_row_ids").format(str(e)))
            return pd.DataFrame(), []

def delete_record(client, row_num):
    """Delete a specific row from the Google Sheet"""
    for attempt in range(MAX_RETRIES):
        try:
            with st.spinner(get_translation("deleting_record").format(attempt + 1, MAX_RETRIES)):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                worksheet.delete_rows(row_num)
                return True
                
        except HttpError as error:
            if error.resp.status == 429:  # Rate limit exceeded
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    st.warning(get_translation("rate_limit").format(delay))
                    time.sleep(delay)
                    continue
                else:
                    st.error(get_translation("max_retries"))
            else:
                st.error(get_translation("api_error").format(str(error)))
            return False
                
        except Exception as e:
            st.error(get_translation("error_deleting").format(str(e)))
            return False
    
    return False

def check_duplicate_email(client, email):
    """Check if a record with the same email already exists"""
    try:
        # Get all records
        records = get_all_data(client)
        
        # Identify the email column name
        email_column = None
        if records and len(records) > 0:
            first_record = records[0]
            possible_email_columns = ['email', 'Email', 'correo', 'Correo', 'E-mail']
            for col in possible_email_columns:
                if col in first_record:
                    email_column = col
                    break
        
        # If no email column found, we can't verify duplicates
        if not email_column:
            st.warning(get_translation("email_column_warning"))
            return False
        
        # Search for the email in records
        for record in records:
            record_email = record.get(email_column, '').strip().lower()
            if record_email == email.strip().lower():
                return True
        
        return False
    except Exception as e:
        st.error(get_translation("error_duplicates").format(str(e)))
        # Allow continuation in case of error
        return False

def save_form_data(client, data):
    """Save form data to Google Sheets"""
    for attempt in range(MAX_RETRIES):
        try:
            with st.spinner(get_translation("saving_data").format(attempt + 1, MAX_RETRIES)):
                # Open spreadsheet and specific worksheet
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                
                # Add new row with data
                worksheet.append_row([
                    data['first_name'],
                    data['last_name'],
                    data['email'],
                    data['phone'],
                    data['estate']
                ])
                
                return True
        
        except HttpError as error:
            if error.resp.status == 429:  # Rate limit exceeded
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    st.warning(get_translation("rate_limit").format(delay))
                    time.sleep(delay)
                    continue
                else:
                    st.error(get_translation("max_retries"))
            else:
                st.error(get_translation("api_error").format(str(error)))
            return False
                
        except Exception as e:
            st.error(get_translation("error_saving").format(str(e)))
            return False
    
    return False

def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
    return bool(re.match(pattern, email))

def to_excel(df):
    """Convert DataFrame to Excel and generate download link"""
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Data')
    writer.close()
    processed_data = output.getvalue()
    b64 = base64.b64encode(processed_data).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="agenda_data.xlsx">Download Excel file</a>'

# Initialize form input keys
def init_form_keys():
    """Initialize form input keys in session state"""
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
    # Initialize form fields if not already present
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate']
    for field in form_fields:
        if field not in st.session_state:
            st.session_state[field] = ""

# Initialize state variables
if 'show_success_message' not in st.session_state:
    st.session_state.show_success_message = False

if 'show_duplicate_message' not in st.session_state:
    st.session_state.show_duplicate_message = False

if 'show_delete_message' not in st.session_state:
    st.session_state.show_delete_message = False

def reset_form_fields():
    """Reset all form fields after successful submission"""
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate']
    for field in form_fields:
        st.session_state[field] = ""
        # Also reset the input keys
        input_key = f"{field}_input"
        if input_key in st.session_state:
            st.session_state[input_key] = ""
    
    # Mark form as submitted to trigger reset
    st.session_state.form_submitted = True

def agenda_main():
    # Initialize all session state variables
    initialize_session_state()
    
    st.header(get_translation("header"))
    st.write("---")
    
    # Initialize form keys
    init_form_keys()
    
    # Load credentials
    creds = load_credentials_from_toml()
    if not creds:
        st.error(get_translation("credentials_error"))
        return
    
    # Connect to Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        return
    
    st.markdown(f'<h3 class="main-header">{get_translation("form_subtitle")}</h1>', unsafe_allow_html=True)

    # Contact form using session state for values
    with st.form(key='contact_form'):
            first_name = st.text_input(get_translation("first_name"), 
                                     value=st.session_state.first_name,
                                     placeholder=get_translation("first_name_placeholder"), 
                                     key="first_name_input")
            
            last_name = st.text_input(get_translation("last_name"), 
                                    value=st.session_state.last_name,
                                    placeholder=get_translation("last_name_placeholder"), 
                                    key="last_name_input")
            
            email = st.text_input(get_translation("email"), 
                                value=st.session_state.email,
                                placeholder=get_translation("email_placeholder"), 
                                key="email_input")
            
            phone = st.text_input(get_translation("phone"), 
                                value=st.session_state.phone,
                                placeholder=get_translation("phone_placeholder"), 
                                key="phone_input")
            
            estate = st.text_input(get_translation("estate"), 
                                 value=st.session_state.estate,
                                 placeholder=get_translation("estate_placeholder"), 
                                 key="estate_input")

            # Display status messages
            if st.session_state.show_success_message:
                st.markdown(f'<div class="success-message">{get_translation("success_message")}</div>', unsafe_allow_html=True)
                st.session_state.show_success_message = False
            if st.session_state.show_duplicate_message:
                st.markdown(f'<div class="warning-message">{get_translation("duplicate_message")}</div>', unsafe_allow_html=True)
                st.session_state.show_duplicate_message = False
            
            if st.session_state.show_delete_message:
                st.markdown(f'<div class="success-message">{get_translation("delete_message")}</div>', unsafe_allow_html=True)
                st.session_state.show_delete_message = False
            
            submit_button = st.form_submit_button(label=get_translation("save_button"), type="primary")

            if 'form_submitted' not in st.session_state:
                st.session_state.form_submitted = False
            
            if submit_button:
                # Update session state with current values
                st.session_state.first_name = first_name
                st.session_state.last_name = last_name
                st.session_state.email = email
                st.session_state.phone = phone
                st.session_state.estate = estate
                
                # Required field validation
                if not (first_name and last_name and email and phone and estate):
                    st.error(get_translation("required_fields"))
                    return
                
                # Email format validation
                if not validate_email(email):
                    st.warning(get_translation("invalid_email"))
                    return
                
                # Check for duplicates
                if check_duplicate_email(client, email):
                    st.session_state.show_duplicate_message = True
                    st.rerun()
                
                # Save data
                data = {
                   'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                    'estate': estate
                }
                
                if save_form_data(client, data):
                    # Show success message
                    st.session_state.show_success_message = True
        
                    # Set the form_submitted flag to True
                    st.session_state.form_submitted = True
        
                    # Rerun the app to reflect changes
                    st.rerun()

            if st.session_state.form_submitted:
                # Clear all form fields
                st.session_state.first_name = ""
                st.session_state.last_name = ""
                st.session_state.email = ""
                st.session_state.phone = ""
                st.session_state.estate = ""
                # Reset the submission flag
                st.session_state.form_submitted = False

    # Display saved records
    st.markdown(f'<h2 class="section-header">{get_translation("saved_records")}</h2>', unsafe_allow_html=True)
    
    # Get data with row IDs for deletion functionality
    df, row_ids = get_worksheet_data_with_row_ids(client)
    
    if not df.empty:
        # Display dataframe
        st.dataframe(df, use_container_width=True)
        
        # Record deletion section
        st.markdown(f'<h3>{get_translation("delete_record")}</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_row = st.selectbox(get_translation("select_record"), 
                                      options=range(len(df)),
                                      format_func=lambda x: f"Row {x+1}: {df.iloc[x, 0]} {df.iloc[x, 1]} - {df.iloc[x, 2]}")
        
        with col2:
            if st.button(get_translation("delete_button"), key="delete_btn", type="primary", 
                         help=get_translation("delete_help")):
                if delete_record(client, row_ids[selected_row]):
                    st.session_state.show_delete_message = True
                    st.rerun()
        
        # Generate Excel download button
        st.markdown(f'<h3>{get_translation("export_data")}</h3>', unsafe_allow_html=True)
        excel_link = to_excel(df)
        st.markdown(excel_link, unsafe_allow_html=True)
    else:
        st.info(get_translation("no_records"))
