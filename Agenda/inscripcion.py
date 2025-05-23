import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import toml
import base64
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from io import BytesIO
from gspread.exceptions import APIError
from googleapiclient.errors import HttpError

# Constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Cargar configuraciones desde config.toml
with open("./.streamlit/config.toml", "r") as f:
    config = toml.load(f)

# Custom CSS styles
# [CSS styles remain unchanged]

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

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
    
    if 'pdf_file' not in st.session_state:
        st.session_state.pdf_file = None
    
    if 'show_email_sent' not in st.session_state:
        st.session_state.show_email_sent = False
    
    if 'duplicate_type' not in st.session_state:
        st.session_state.duplicate_type = None
    
    if 'clear_form' not in st.session_state:
        st.session_state.clear_form = False
    
    # Initialize form fields - using different keys for storage vs widget keys
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate', 'send_email', 'acepto','uploaded_file']
    for field in form_fields:
        if field not in st.session_state:
            if field == 'send_email':
                st.session_state[field] = True  # Default to True
            elif field == 'acepto':
                st.session_state[field] = False
            elif field == 'uploaded_file':
                st.session_state[field] = None
            else:
                st.session_state[field] = ""

def clear_form_fields():
    """Clear all form fields and reset to default values"""
    st.session_state.first_name = ""
    st.session_state.last_name = ""
    st.session_state.email = ""
    st.session_state.phone = ""
    st.session_state.estate = ""
    st.session_state.send_email = True  # Reset to default True
    st.session_state.acepto = False
    st.session_state.uploaded_file = None
    
    # Remove widget keys to force recreation with default values
    widget_keys = [
        'first_name_input', 'last_name_input', 'email_input', 
        'phone_input', 'estate_input', 'send_email_input', 
        'aceptar', 'uploaded_file_input', 'authorization_text'
    ]
    
    for key in widget_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    st.session_state.clear_form = True

def load_credentials_from_toml():
    """Load credentials from secrets.toml file"""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    """Establish connection with Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def get_all_data(client):
    """Get all data saved in the sheet"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                records = worksheet.get_all_records()
                return records

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
            return []

        except Exception as e:
            st.error(f"Error retrieving data: {str(e)}")
            return []

def check_duplicate_record(client, email, first_name, last_name):
    """Check if a record with the same email or full name already exists"""
    try:
        # Get all records
        records = get_all_data(client)
        
        # If no records or empty list, no duplicates possible
        if not records:
            return False, None
        
        # Identify column names - check multiple possible column names
        if len(records) > 0:
            first_record = records[0]
            
            # Find email column
            email_column = None
            possible_email_columns = ['email', 'Email', 'correo', 'Correo', 'E-mail', 'e-mail', 'EMAIL']
            for col in possible_email_columns:
                if col in first_record:
                    email_column = col
                    break
            
            # Find name columns
            first_name_column = None
            possible_first_name_columns = ['first_name', 'First Name', 'nombre', 'Nombre', 'nombres', 'Nombres']
            for col in possible_first_name_columns:
                if col in first_record:
                    first_name_column = col
                    break
            
            last_name_column = None
            possible_last_name_columns = ['last_name', 'Last Name', 'apellido', 'Apellido', 'apellidos', 'Apellidos']
            for col in possible_last_name_columns:
                if col in first_record:
                    last_name_column = col
                    break
        
        # Search for duplicates in records
        for record in records:
            # Check email duplicate
            if email_column:
                record_email = str(record.get(email_column, '')).strip().lower()
                input_email = str(email).strip().lower()
                if record_email and input_email and record_email == input_email:
                    return True, "email"
            
            # Check name duplicate (first name + last name combination)
            if first_name_column and last_name_column:
                record_first_name = str(record.get(first_name_column, '')).strip().lower()
                record_last_name = str(record.get(last_name_column, '')).strip().lower()
                input_first_name = str(first_name).strip().lower()
                input_last_name = str(last_name).strip().lower()
                
                if (record_first_name and record_last_name and 
                    input_first_name and input_last_name and
                    record_first_name == input_first_name and 
                    record_last_name == input_last_name):
                    return True, "nombre"
        
        return False, None
        
    except Exception as e:
        st.error(f"Error verificando duplicados: {str(e)}")
        # In case of error, allow continuation but log the issue
        return False, None

def save_form_data(client, data):
    """Save form data to Google Sheets"""
    for attempt in range(MAX_RETRIES):
        try:
            with st.spinner(f'Saving data... (Attempt {attempt + 1}/{MAX_RETRIES})'):
                # Open spreadsheet and specific worksheet
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                
                # Prepare email status and date fields
                actions = ""
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                email_status = "Sent" if data['send_email'] else "Not Sent"
                shipping_date = current_datetime if data['send_email'] else ""
                pdf_uploaded = "Si" if data['pdf_uploaded'] else "No"
                
                # Add new row with data
                worksheet.append_row([
                    data['first_name'],
                    data['last_name'],
                    data['email'],
                    data['phone'],
                    data['estate'],
                    actions,
                    email_status,
                    shipping_date,
                    data['acepto'],
                    pdf_uploaded,
                    data['pdf_filename']
                ])
                
                return True
        
        except HttpError as error:
            if error.resp.status == 429:  # Rate limit exceeded
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    st.warning(f"Rate limit exceeded. Waiting {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    st.error("Maximum retry attempts exceeded. Please try again later.")
            else:
                st.error(f"API Error: {str(error)}")
            return False
                
        except Exception as e:
            st.error(f"Error saving data: {str(e)}")
            return False
    
    return False

def send_confirmation_email(email_address, first_name, last_name, pdf_file=None, pdf_filename=None):
    """Send confirmation email to the provided address"""
    try:
        # Get email credentials from secrets
        email_user = st.secrets['emails']['smtp_user']
        email_password = st.secrets['emails']['smtp_password']
        email_from = "josegarjagt@gmail.com"  # config['email']['from']
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Get current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_address
        msg['Subject'] = "Confirmación de Registro"
        
        # Email body
        body = f"""
        <html>
          <body>
            <h2>Confirmación de registro</h2>
            <p>Estimado(a) {first_name} {last_name},</p>
            <p>Gracias por enviar su información. Hemos recibido su registro correctamente.</p>
            <p>Fecha y hora de inscripción: {current_datetime}</p>
            <p>Le contactaremos pronto con más detalles</p>
            <p>Atentamente,<br>El equipo</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF file if provided
        if pdf_file is not None and pdf_filename is not None:
            attachment = MIMEApplication(pdf_file.getvalue())
            attachment["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
            msg.attach(attachment)
        
        # Connect to server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        text = msg.as_string()
        server.sendmail(email_from, email_address, text)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        return False

def send_notification_to_admin(admin_email, registrant_info, pdf_file=None, pdf_filename=None):
    """Send notification email to admin"""
    try:
        # Get email credentials from secrets
        email_user = st.secrets['emails']['smtp_user']
        email_password = st.secrets['emails']['smtp_password']
        email_from = "josegarjagt@gmail.com"  # config['email']['from']
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Get current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = admin_email
        msg['Subject'] = "Nuevo Registro de Notificacion"
        
        # Email body
        body = f"""
        <html>
          <body>
            <h2>Nueva alerta de registro</h2>
            <p>Se ha registrado una nueva persona:</p>
            <ul>
              <li><strong>Nombre:</strong> {registrant_info['first_name']} {registrant_info['last_name']}</li>
              <li><strong>Email:</strong> {registrant_info['email']}</li>
              <li><strong>Telefono:</strong> {registrant_info['phone']}</li>
              <li><strong>Ciudad:</strong> {registrant_info['estate']}</li>
              <li><strong>Fecha/hora de registro:</strong> {current_datetime}</li>
              <li><strong>PDF subido:</strong> {"Si" if pdf_file is not None else "No"}</li>
            </ul>
            <p>Por favor consulte el sistema de registro para más detalles.</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF file if provided
        if pdf_file is not None and pdf_filename is not None:
            attachment = MIMEApplication(pdf_file.getvalue())
            attachment["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
            msg.attach(attachment)
        
        # Connect to server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        text = msg.as_string()
        server.sendmail(email_from, admin_email, text)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error sending admin notification: {str(e)}")
        return False

def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
    return bool(re.match(pattern, email))

def validate_pdf(file):
    """Validate that the file is a PDF"""
    if file is None:
        return True  # File is optional
    
    # Check file type
    if file.type != "application/pdf":
        return False
    
    # Check file size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return False
    
    return True

def inscripcion_main():
    # Initialize all session state variables
    initialize_session_state()
    
    st.header('Formulario de Inscripcion Personal')
    st.write("---")
    
    # Load credentials
    creds, config = load_credentials_from_toml()
    if not creds:
        st.error("Could not load credentials. Please verify the secrets.toml file")
        return
    
    # Connect to Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        return
    
    # Display status messages BEFORE the form
    if st.session_state.show_success_message:
        st.success("¡Datos guardados exitosamente!")
        st.session_state.show_success_message = False
    
    if st.session_state.show_duplicate_message:
        duplicate_type = st.session_state.get('duplicate_type', 'registro')
        if duplicate_type == 'email':
            st.warning("⚠️ Este email ya está registrado! Por favor use un email diferente.")
        elif duplicate_type == 'nombre':
            st.warning("⚠️ Ya existe un registro con este nombre completo! Por favor verifique la información.")
        else:
            st.warning("⚠️ Este registro ya existe! Por favor verifique la información.")
        st.session_state.show_duplicate_message = False
    
    if st.session_state.get('show_email_sent', False):
        st.success("¡Email de confirmación enviado exitosamente!")
        st.session_state.show_email_sent = False

    # Contact form using session state for values
    with st.form(key='contact_form'):

        texto_hd = ["Declaro de manera libre, expresa e informada que AUTORIZO a la empresa de la referencia, para que de acuerdo con el literal a) del articulo 6 de la La Ley 1581 de 2012, también conocida como la Ley de Protección de Datos Personales en Colombia. Para que realice la recolección, almacenamento y uso en general de mis datos personales y sensibles aqui suministrados.  Declaro que conozco y acepto la Politica para el Tratamiento y Protección de Datos Personales, y que tengo derecho a conocer, actualizar y rectificar los datos personales sumnistrados y como garantia de guardar la privacidad de mis datos personales"]

        # Use empty string as default if clear_form is True, otherwise use session state
        default_acepto = False if st.session_state.clear_form else st.session_state.acepto
        acepto = st.checkbox("Acepto los términos y condiciones", 
                           value=default_acepto, 
                           key="aceptar")

        # Solo mostrar el texto de autorización si NO se han aceptado los términos
        if not acepto:
            st.write("**Autorización:**")
            st.text_area(
                "Texto de autorización y tratamiento de datos personales", 
                value=texto_hd[0], 
                height=150, 
                disabled=True, 
                key="authorization_text",
                label_visibility="collapsed"
            )
        else:
            st.success("✅ Términos y condiciones aceptados")

        col1, col2 = st.columns(2)
        
        with col1:
            # Use empty string as default if clear_form is True, otherwise use session state
            default_first_name = "" if st.session_state.clear_form else st.session_state.first_name
            first_name = st.text_input("First Name - Nombre(s)", 
                                     value=default_first_name,
                                     placeholder="Input First Name", 
                                     key="first_name_input")
        
        with col2:
            default_last_name = "" if st.session_state.clear_form else st.session_state.last_name
            last_name = st.text_input("Last Name - Apellido(s)", 
                                    value=default_last_name,
                                    placeholder="Input Last Name", 
                                    key="last_name_input")
        
        default_email = "" if st.session_state.clear_form else st.session_state.email
        email = st.text_input("Email", 
                            value=default_email,
                            placeholder="Input Email", 
                            key="email_input")
        
        default_phone = "" if st.session_state.clear_form else st.session_state.phone
        phone = st.text_input("Phone Number - Telefono", 
                            value=default_phone,
                            placeholder="Input Phone Number", 
                            key="phone_input")
        
        default_estate = "" if st.session_state.clear_form else st.session_state.estate
        estate = st.text_input("Estate - Ciudad", 
                             value=default_estate,
                             placeholder="Input Estate or City", 
                             key="estate_input")
        
        # PDF file upload - file uploader doesn't need default value handling
        uploaded_file = st.file_uploader("Cargar Documento Hoja de Vida - Upload PDF Document (Optional)", 
                                        type=["pdf"],
                                        key="uploaded_file_input")
        
        # New checkbox for sending email confirmation
        default_send_email = True if st.session_state.clear_form else st.session_state.send_email
        send_email = st.checkbox("Send email - Envío Correo", 
                                value=default_send_email,
                                key="send_email_input")
        
        submit_button = st.form_submit_button(label="Guardar Información", type="primary")
        
        if submit_button:
            # Reset clear_form flag after form submission
            st.session_state.clear_form = False
            
            # Validation for acceptance of terms
            if not acepto:
                st.error("Debe aceptar los términos y condiciones para continuar.")
                return
            
            # Required field validation
            if not (first_name and last_name and email and phone and estate):
                st.error("Por favor complete todos los campos obligatorios.")
                return
            
            # Email format validation
            if not validate_email(email):
                st.error('Formato de email inválido. Por favor ingrese un email válido.')
                return
            
            # PDF validation if a file was uploaded
            if uploaded_file is not None and not validate_pdf(uploaded_file):
                st.error("Archivo PDF inválido. Por favor suba un archivo PDF válido menor a 5MB.")
                return
            
            # Check for duplicate records (email or name)
            is_duplicate, duplicate_type = check_duplicate_record(client, email, first_name, last_name)
            if is_duplicate:
                st.session_state.show_duplicate_message = True
                st.session_state.duplicate_type = duplicate_type
                st.rerun()
                return
            
            # Get PDF filename if available, otherwise use empty string
            pdf_filename = uploaded_file.name if uploaded_file is not None else ""
            
            # Save data
            data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'estate': estate,
                'send_email': send_email,
                'acepto': acepto,
                'pdf_uploaded': uploaded_file is not None,
                'pdf_filename': pdf_filename
            }
            
            # Try to save the form data
            save_success = save_form_data(client, data)
            
            if save_success:
                # Set success message
                st.session_state.show_success_message = True
                
                # Send confirmation email if enabled
                email_sent = False
                if send_email:
                    email_sent = send_confirmation_email(email, first_name, last_name, uploaded_file, pdf_filename)
                    if email_sent:
                        st.session_state.show_email_sent = True
                    
                    # Send notification to admin with the registration details
                    admin_email = st.secrets.get('emails', {}).get('admin_email', 'josegarjagt@gmail.com')
                    send_notification_to_admin(admin_email, data, uploaded_file, pdf_filename)
                
                # Clear the form fields after successful submission
                clear_form_fields()

                #Rerun to show cleared form and success message
                st.rerun()

clear_session_state()
          
                
#if __name__ == "__main__":
#   inscripcion_main()