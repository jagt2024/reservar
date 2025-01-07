import streamlit as st
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
import glob
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import RefreshError, TransportError
from requests.exceptions import RequestException
import io
import toml
import tempfile
import base64
import time
import shutil
import random
from requests.exceptions import RequestException, ConnectionError
from socket import error as SocketError
import json 

def load_last_backup_time():
    try:
        with open('last_backup_time.json', 'r') as f:
            data = json.load(f)
            return datetime.fromisoformat(data['last_backup_time'])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None

def save_last_backup_time(time):
    with open('last_backup_time.json', 'w') as f:
        json.dump({'last_backup_time': time.isoformat()}, f)

def load_credentials():
    with open('./.streamlit/secrets.toml', 'r') as toml_file:
        config = toml.load(toml_file)
        creds = config['sheets']['credentials_sheet']
    return creds

def create_backup_directory():
    backup_dir = os.path.join(os.path.expanduser("~"), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def get_last_backup_time():
    if 'last_backup_time' not in st.session_state:
        st.session_state.last_backup_time = None
    return st.session_state.last_backup_time

def set_last_backup_time(time):
    st.session_state.last_backup_time = time

def can_perform_backup():
    last_backup_time = load_last_backup_time()
    if last_backup_time is None:
        return True
    current_time = datetime.now()
    time_difference = current_time - last_backup_time
    return time_difference.total_seconds() >= 3 * 3600  # 3 horas en segundos

def backup_databases(db_dir, backup_dir):
    backup_paths = []
    db_files = glob.glob(os.path.join(db_dir, "*.db"))
    
    for db_path in db_files:
        db_name = os.path.basename(db_path)
        backup_filename = f"{db_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        conn = sqlite3.connect(db_path)
        with open(backup_path, 'w') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line)
        conn.close()
        
        backup_paths.append(backup_path)
    
    return backup_paths

def backup_files(src_dir, backup_dir):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"app_files_backup_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                if not file.endswith('.db'):  # Excluir archivos .db
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, src_dir)
                    zipf.write(file_path, arcname)
    
    return zip_path

def backup_google_drive_sheets(backup_dir):
    max_retries = 5
    base_delay = 3  # segundos
    
    def exponential_backoff(attempt):
        return base_delay * (2 ** attempt) + random.uniform(0, 1)
    
    for attempt in range(max_retries):
        try:
            creds = load_credentials()
            #credentials = Credentials.from_service_account_info(
                #creds,
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                #scopes=[
                #    "https://www.googleapis.com/auth/spreadsheets.readonly",
                #    "https://www.googleapis.com/auth/drive.readonly",],)

            credentials = Credentials.from_service_account_info(creds, scopes=scope)

            client = gspread.authorize(credentials)

            cutoff_date = datetime.now() - timedelta(days=68)

            sheet_files = client.list_spreadsheet_files()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"google_drive_sheets_backup_{timestamp}.zip"
            zip_path = os.path.join(backup_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for sheet in sheet_files:
                    created_time = datetime.strptime(sheet['createdTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
                    if created_time >= cutoff_date:
                        spreadsheet = client.open_by_key(sheet['id'])
                        for worksheet in spreadsheet.worksheets():
                            csv_content = worksheet.get_all_values()
                            csv_buffer = io.StringIO()
                            for row in csv_content:
                                csv_buffer.write(','.join(row) + '\n')
                            
                            zipf.writestr(f"{sheet['name']}/{worksheet.title}.csv", csv_buffer.getvalue())

            return zip_path

        except (RefreshError, RequestException, ConnectionError, SocketError, TransportError) as e:
            if attempt < max_retries - 1:
                delay = exponential_backoff(attempt)
                st.warning(f"Intento {attempt + 1} falló. Reintentando en {delay:.2f} segundos... Error: {str(e)}")
                time.sleep(delay)
            else:
                raise Exception(f"No se pudo realizar el backup de las hojas de Google Drive después de {max_retries} intentos: {str(e)}")

    raise Exception("Error inesperado en la función backup_google_drive_sheets")


def create_download_link(file_path, file_name):
    with open(file_path, "rb") as f:
        bytes = f.read()
        b64 = base64.b64encode(bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}">Descargar {file_name}</a>'
        return href

def main():
    st.title("Herramienta de Backup")

    st.sidebar.header("Configuración")
    db_dir = st.sidebar.text_input("Directorio de las bases de datos SQLite ", "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas")
    app_dir = st.sidebar.text_input("Directorio de la aplicación", "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas")
    
    backup_google_drive = st.sidebar.checkbox("Incluir backup de Google Drive (últimos 8 días)")

    if st.sidebar.button("Realizar Backup"):
        if not all([db_dir, app_dir]):
            st.error("Por favor, complete todos los campos de configuración.")
        elif not can_perform_backup():
            last_backup_time = load_last_backup_time()
            next_backup_time = last_backup_time + timedelta(hours=3)
            st.warning(f"El último backup se realizó el {last_backup_time.strftime('%Y-%m-%d %H:%M:%S')}. El próximo backup estará disponible a las {next_backup_time.strftime('%Y-%m-%d %H:%M:%S')}.")
        else:
            try:
                backup_dir = create_backup_directory()
                st.info(f"Los archivos de backup se guardarán en: {backup_dir}")

                # Backup de bases de datos
                with st.spinner("Realizando backup de las bases de datos..."):
                    db_backups = backup_databases(db_dir, backup_dir)
                
                if db_backups:
                    st.success(f"Backup de las bases de datos creado. Archivos guardados en {backup_dir}")
                    for backup_path in db_backups:
                        st.write(f"- {os.path.basename(backup_path)}")
                else:
                    st.warning("No se encontraron archivos de base de datos (.db) para respaldar.")
                
                # Backup de archivos de la aplicación
                with st.spinner("Realizando backup de los archivos de la aplicación..."):
                    files_backup_path = backup_files(app_dir, backup_dir)
                st.success(f"Backup de los archivos de la aplicación creado: {os.path.basename(files_backup_path)}")
                
                # Backup de Google Drive
                if backup_google_drive:
                    with st.spinner("Realizando backup de las hojas de cálculo de Google Drive (últimos 8 días)..."):
                        try:
                            drive_backup_path = backup_google_drive_sheets(backup_dir)
                            st.success(f"Backup de las hojas de cálculo de Google Drive creado: {os.path.basename(drive_backup_path)}")
                        except Exception as e:
                            st.error(f"Error durante el backup de Google Drive: {str(e)}")
                
                #set_last_backup_time(datetime.now())

                # Guardar el tiempo del backup actual
                save_last_backup_time(datetime.now())
                
                st.balloons()
                st.success("¡Proceso de backup completado!")
                st.info("Por favor, accede a los archivos de backup en el directorio indicado arriba.")
            
            except Exception as e:
                st.error(f"Error durante el proceso de backup: {str(e)}")

if __name__ == "__main__":
    main()
