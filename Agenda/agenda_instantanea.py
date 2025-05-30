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
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate', 'send_email']
    for field in form_fields:
        if field not in st.session_state:
            st.session_state[field] = "" if field != 'send_email' else False

def clear_session_state():
    #Clear all session state variables
    for key in list(st.session_state.keys()):
        if key not in ['show_success_message', 'show_duplicate_message', 'show_delete_message']:
            del st.session_state[key]

def load_credentials_from_toml():
    #Load credentials from secrets.toml file
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
    #Establish connection with Google Sheets
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
            return False

        except Exception as e:
            st.error(f"Error retrieving data: {str(e)}")
            return []

def get_worksheet_data_with_row_ids(client):
    """Get all data with row numbers for deletion functionality"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
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
                    st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                    time.sleep(delay)
                    continue
                else:
                    st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
            else:
                st.error(f"Error de la API: {str(error)}")
            return False

        except Exception as e:
            st.error(f"Error retrieving data with row IDs: {str(e)}")
            return pd.DataFrame(), []

def delete_record(client, row_num):
    """Delete a specific row from the Google Sheet"""
    for attempt in range(MAX_RETRIES):
        try:
            with st.spinner(f'Deleting record... (Attempt {attempt + 1}/{MAX_RETRIES})'):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('ordenes')
                worksheet.delete_rows(row_num)
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
            st.error(f"Error deleting record: {str(e)}")
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
            st.warning("Could not identify email column in the sheet.")
            return False
        
        # Search for the email in records
        for record in records:
            record_email = record.get(email_column, '').strip().lower()
            if record_email == email.strip().lower():
                return True
        
        return False
    except Exception as e:
        st.error(f"Error checking for duplicates: {str(e)}")
        # Allow continuation in case of error
        return False

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
                email_status = "Sent" if data['send_email'] else "Not Sent"
                shipping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if data['send_email'] else ""
                
                # Add new row with data
                worksheet.append_row([
                    data['first_name'],
                    data['last_name'],
                    data['email'],
                    data['phone'],
                    data['estate'],
                    actions,
                    email_status,
                    shipping_date
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

def send_confirmation_email(email_address, first_name, last_name, config):
    """Send confirmation email to the provided address"""
    try:
        # Get email credentials from secrets
        email_user = st.secrets['emails']['smtp_user']
        email_password = st.secrets['emails']['smtp_password']
        email_from = "josegarjagt@gmail.com" #config['email']['from']
        smtp_server =  "smtp.gmail.com"
        smtp_port = 587
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_address
        msg['Subject'] = "Registration Confirmation"
        
        # Email body
        body = f"""
        <html>
          <body>
            <h2>Registration Confirmation</h2>
            <p>Dear {first_name} {last_name},</p>
            <p>Thank you for submitting your information. We have received your registration successfully.</p>
            <p>We will contact you soon with more details.</p>
            <p>Best regards,<br>The Team</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
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
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate', 'send_email']
    for field in form_fields:
        if field not in st.session_state:
            st.session_state[field] = "" if field != 'send_email' else False

# Initialize state variables
if 'show_success_message' not in st.session_state:
    st.session_state.show_success_message = False

if 'show_duplicate_message' not in st.session_state:
    st.session_state.show_duplicate_message = False

if 'show_delete_message' not in st.session_state:
    st.session_state.show_delete_message = False

if 'show_email_sent' not in st.session_state:
    st.session_state.show_email_sent = False

def reset_form_fields():
    """Reset all form fields after successful submission"""
    form_fields = ['first_name', 'last_name', 'email', 'phone', 'estate', 'send_email']
    for field in form_fields:
        if field == 'send_email':
            st.session_state[field] = False
        else:
            st.session_state[field] = ""
        
        # Also reset the input keys
        input_key = f"{field}_input"
        if input_key in st.session_state:
            if field == 'send_email':
                st.session_state[input_key] = False
            else:
                st.session_state[input_key] = ""
    
    # Mark form as submitted to trigger reset
    st.session_state.form_submitted = True

def agenda_main():

    # Initialize all session state variables
    initialize_session_state()
    
    st.header('Personal Information Form')
    st.write("---")
    
    # Initialize form keys
    init_form_keys()
    
    # Load credentials
    creds, config = load_credentials_from_toml()
    if not creds:
        st.error("Could not load credentials. Please verify the secrets.toml file")
        return
    
    # Connect to Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        return
    
    st.markdown('<h3 class="main-header">Please fill in your details below</h1>', unsafe_allow_html=True)

    # Contact form using session state for values
    with st.form(key='contact_form'):
            first_name = st.text_input("First Name", 
                                     value=st.session_state.first_name,
                                     placeholder="Input First Name", 
                                     key="first_name_input")
            
            last_name = st.text_input("Last Name", 
                                    value=st.session_state.last_name,
                                    placeholder="Input Last Name", 
                                    key="last_name_input")
            
            email = st.text_input("Email", 
                                value=st.session_state.email,
                                placeholder="Input Email", 
                                key="email_input")
            
            phone = st.text_input("Phone Number", 
                                value=st.session_state.phone,
                                placeholder="Input Phone Number", 
                                key="phone_input")
            
            estate = st.text_input("Estate", 
                                 value=st.session_state.estate,
                                 placeholder="Input Estate", 
                                 key="estate_input")
            
            # New checkbox for sending email confirmation
            send_email = st.checkbox("Send confirmation email", 
                                   value=st.session_state.send_email,
                                   key="send_email_input")

            # Display status messages
            if st.session_state.show_success_message:
                st.markdown('<div class="success-message">Data saved successfully!</div>', unsafe_allow_html=True)
                st.session_state.show_success_message = False
            
            if st.session_state.show_duplicate_message:
                st.markdown('<div class="warning-message">This email is already registered!</div>', unsafe_allow_html=True)
                st.session_state.show_duplicate_message = False
            
            if st.session_state.show_delete_message:
                st.markdown('<div class="success-message">Record deleted successfully!</div>', unsafe_allow_html=True)
                st.session_state.show_delete_message = False
            
            if st.session_state.get('show_email_sent', False):
                st.markdown('<div class="success-message">Confirmation email sent successfully!</div>', unsafe_allow_html=True)
                st.session_state.show_email_sent = False
            
            submit_button = st.form_submit_button(label="Save Information", type="primary")

            if 'form_submitted' not in st.session_state:
                st.session_state.form_submitted = False
            
            if submit_button:
                # Update session state with current values
                st.session_state.first_name = first_name
                st.session_state.last_name = last_name
                st.session_state.email = email
                st.session_state.phone = phone
                st.session_state.estate = estate
                st.session_state.send_email = send_email
                
                # Required field validation
                if not (first_name and last_name and email and phone and estate):
                    st.error("Please complete all fields.")
                    return
                
                # Email format validation
                if not validate_email(email):
                    st.warning('Invalid email format')
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
                    'estate': estate,
                    'send_email': send_email
                }
                
                if save_form_data(client, data):
                    # Show success message
                    st.session_state.show_success_message = True
                    
                    # Send confirmation email if checkbox is checked
                    if send_email:
                        if send_confirmation_email(email, first_name, last_name, config):
                            st.session_state.show_email_sent = True
                    
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
                st.session_state.send_email = False
                # Reset the submission flag
                st.session_state.form_submitted = False

    # Display saved records
    st.markdown('<h2 class="section-header">Saved Records</h2>', unsafe_allow_html=True)
    
    # Get data with row IDs for deletion functionality
    df, row_ids = get_worksheet_data_with_row_ids(client)
    
    if not df.empty:
        # Display dataframe
        st.dataframe(df, use_container_width=True)
        
        # Record deletion section
        st.markdown('<h3>Delete Record</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_row = st.selectbox("Select record to delete", 
                                      options=range(len(df)),
                                      format_func=lambda x: f"Row {x+1}: {df.iloc[x, 0]} {df.iloc[x, 1]} - {df.iloc[x, 2]}")
        
        with col2:
            if st.button("Delete Record", key="delete_btn", type="primary", 
                         help="Delete the selected record permanently"):
                if delete_record(client, row_ids[selected_row]):
                    st.session_state.show_delete_message = True
                    st.rerun()
        
        # Generate Excel download button
        st.markdown('<h3>Export Data</h3>', unsafe_allow_html=True)
        excel_link = to_excel(df)
        st.markdown(excel_link, unsafe_allow_html=True)
    else:
        st.info("No records saved yet.")

if __name__ == "__main__":
    agenda_main()
   