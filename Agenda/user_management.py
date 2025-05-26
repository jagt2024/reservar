import streamlit as st
import hashlib
import gspread
from google.oauth2.service_account import Credentials
import json
import toml

st.cache_data.clear()
st.cache_resource.clear()

class TicketGoogleSheets:
    def __init__(self):
        self.creds = self.load_credentials()
        self.sheet_name = 'gestion-agenda'
        self.worksheet_name = 'users'
        
    def load_credentials(self):
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
            
    def _get_worksheet(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            credentials = Credentials.from_service_account_info(self.creds, scopes=scope)
            client = gspread.authorize(credentials)
            sheet = client.open(self.sheet_name)
            return sheet.worksheet(self.worksheet_name)
        except Exception as e:
            st.error(f"Error al acceder a Google Sheets: {str(e)}")
            return None

def init_db():
    gs = TicketGoogleSheets()
    worksheet = gs._get_worksheet()
    
    if worksheet:
        # Check if headers exist
        headers = worksheet.row_values(1)
        if not headers:
            worksheet.append_row(['username', 'password', 'role'])
        
        # Check if admin exists
        try:
            cell = worksheet.find('admin')
            if not cell:
                hashed_password = hashlib.sha256('admin4321'.encode()).hexdigest()
                worksheet.append_row(['admin4321', hashed_password, 'admin4321'])
        except gspread.exceptions.CellNotFound:
            hashed_password = hashlib.sha256('admin'.encode()).hexdigest()
            worksheet.append_row(['admin', hashed_password, 'admin4321'])

def add_user(username, password, role):
    gs = TicketGoogleSheets()
    worksheet = gs._get_worksheet()
    
    if worksheet:
        try:
            # Check if user exists
            cell = worksheet.find(username)
            if cell:
                # Update existing user
                row = cell.row
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                worksheet.update(f'A{row}:C{row}', [[username, hashed_password, role]])
            else:
                # Add new user
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                worksheet.append_row([username, hashed_password, role])
            return True
        except Exception as e:
            st.error(f"Error al agregar usuario: {str(e)}")
            return False

def check_credentials(username, password):
    gs = TicketGoogleSheets()
    worksheet = gs._get_worksheet()
    
    if worksheet:
        try:
            cell = worksheet.find(username)
            if cell:
                row = worksheet.row_values(cell.row)
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                if row[1] == hashed_password:
                    return row[2]  # Return role
        except gspread.exceptions.CellNotFound:
            pass
    return None

def login():
    login_container = st.empty()
    
    with login_container.container():
        username = ""
        password = ""
        
        st.write("Por favor, inicie sesión para acceder a la aplicación")
        st.subheader("Inicio de Sesión")

        with st.form("login_form"):
            username = st.text_input("Nombre de usuario", key="login_username")
            password = st.text_input("Contraseña", type="password", key="login_password")
            submit_button = st.form_submit_button("Iniciar Sesión")

        if submit_button:
            role = check_credentials(username, password)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['role'] = role
                login_container.empty()
                return True
            else:
                st.error("Nombre de usuario o contraseña incorrectos")
    
    return False

def signup():
    st.subheader("Registro de Usuario")
    if st.session_state.get('role') == 'admin':
        with st.form("signup_form"):
            new_username = st.text_input("Nuevo nombre de usuario", key="signup_username")
            new_password = st.text_input("Nueva contraseña", type="password", key="signup_password")
            new_role = st.selectbox("Rol", ["user", "admin", "soporte"])
            submit_button = st.form_submit_button("Registrarse")

        if submit_button:
            if new_username and new_password:
                if add_user(new_username, new_password, new_role):
                    st.success("Usuario registrado con éxito.")
                else:
                    st.error("Error al registrar el usuario.")
            else:
                st.error("Por favor, introduzca un nombre de usuario y una contraseña.")
    else:
        st.error("Solo los administradores pueden registrar nuevos usuarios.")

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.session_state['username'] = ""
    st.session_state['password'] = ""
    st.rerun()

def user_management_system():
    init_db()
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        if login():
           st.rerun()
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Bienvenido, {st.session_state['username']}!")
        with col2:
            if st.button("Cerrar Sesión"):
                logout()
        
        if st.session_state.get('role') == 'admin':
            st.markdown("---")
            signup()
        
        return True

    return False

if __name__ == "__main__":
   if user_management_system():
      st.write("Acceso concedido a la aplicación principal")
      # Aquí iría el código de tu aplicación principal
   else:
      st.write("Por favor, inicie sesión para acceder a la aplicación")