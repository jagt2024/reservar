import streamlit as st
import os
import sqlite3
import zipfile
from datetime import datetime
import glob
import gspread
from google.oauth2.service_account import Credentials
import io
import toml

def load_credentials():
    with open('./.streamlit/secrets.toml', 'r') as toml_file:
        config = toml.load(toml_file)
        creds = config['sheets']['credentials_sheet']
    return creds

def backup_databases(db_dir, backup_dir):
    backup_paths = []
    db_files = glob.glob(os.path.join(db_dir, "*.db"))
    
    for db_path in db_files:
        db_name = os.path.basename(db_path)
        backup_path = os.path.join(backup_dir, f"{db_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        
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
    creds = load_credentials()
    # Usar las credenciales del archivo de secretos de Streamlit
    credentials = Credentials.from_service_account_info(
    creds, 
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",],
    )
    client = gspread.authorize(credentials)

    # Obtener todos los archivos de hojas de cálculo
    sheet_files = client.list_spreadsheet_files()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"google_drive_sheets_backup_{timestamp}.zip"
    zip_path = os.path.join(creds, zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for sheet in sheet_files:
            spreadsheet = client.open_by_key(sheet['id'])
            for worksheet in spreadsheet.worksheets():
                csv_content = worksheet.get_all_values()
                csv_buffer = io.StringIO()
                for row in csv_content:
                    csv_buffer.write(','.join(row) + '\n')
                
                zipf.writestr(f"{sheet['name']}/{worksheet.title}.csv", csv_buffer.getvalue())

    return zip_path

def main():
    st.title("Herramienta de Backup")

    st.sidebar.header("Configuración")
    db_dir = st.sidebar.text_input("Directorio de las bases de datos SQLite ", "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas")
    app_dir = st.sidebar.text_input("Directorio de la aplicación", "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas")
    
    backup_dir = st.sidebar.text_input("Directorio de backup",  "C:/Users/hp  pc/Desktop/Programas practica Python/backup-app-reservas")
    
    backup_google_drive = st.sidebar.checkbox("Incluir backup de Google Drive")

    if st.sidebar.button("Realizar Backup"):
        if not all([db_dir, app_dir, backup_dir]):
            st.error("Por favor, complete todos los campos de configuración.")
        else:
            try:
                os.makedirs(backup_dir, exist_ok=True)
                
                with st.spinner("Realizando backup de las bases de datos..."):
                    db_backup_paths = backup_databases(db_dir, backup_dir)
                
                if db_backup_paths:
                    st.success("Backup de las bases de datos creado:")
                    for path in db_backup_paths:
                        st.write(f"- {path}")
                else:
                    st.warning("No se encontraron archivos de base de datos (.db) para respaldar.")
                
                with st.spinner("Realizando backup de los archivos de la aplicación..."):
                    files_backup_path = backup_files(app_dir, backup_dir)
                st.success(f"Backup de los archivos de la aplicación creado: {files_backup_path}")
                
                if backup_google_drive:
                    if "gcp_service_account" in st.secrets:
                        with st.spinner("Realizando backup de las hojas de cálculo de Google Drive..."):
                            drive_backup_path = backup_google_drive_sheets(backup_dir)
                        st.success(f"Backup de las hojas de cálculo de Google Drive creado: {drive_backup_path}")
                    else:
                        st.error("No se encontraron las credenciales de Google Drive en el archivo de secretos.")
                
                st.balloons()
                st.success("¡Backup completado con éxito!")
            except Exception as e:
                st.error(f"Error durante el proceso de backup: {str(e)}")

if __name__ == "__main__":
    main()