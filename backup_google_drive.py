import streamlit as st
import os
import toml
import zipfile
import io
import time
import random
from datetime import datetime
from google.oauth2.service_account import Credentials
from google.auth.exceptions import RefreshError
from requests.exceptions import RequestException, ConnectionError
from socket import error as SocketError
import urllib3
import gspread
import requests

st.set_page_config(
    page_title="Google Sheets Backup Tool",
    page_icon="📊",
    layout="wide"
)

# Nombres de los archivos a respaldar
SHEET_NAMES = [
    'gestion-reservas-dp',
    'gestion-reservas-emp',
    'gestion-reservas-abo'
]

def load_credentials():
    with open('./.streamlit/secrets.toml', 'r') as toml_file:
        config = toml.load(toml_file)
        creds = config['sheetsemp']['credentials_sheet']
    return creds

def get_sheet_id_by_name(client, name):
    """Busca el ID de la hoja por su nombre."""
    try:
        sheet_list = client.list_spreadsheet_files()
        for sheet in sheet_list:
            if sheet['name'].lower() == name.lower():
                return sheet['id']
        return None
    except Exception as e:
        st.warning(f"Error al buscar la hoja {name}: {str(e)}")
        return None

def download_excel_file(sheet_id, credentials):
    """Descarga el archivo de Excel completo."""
    try:
        # URL para exportar como Excel
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        
        # Crear una sesión con las credenciales
        session = requests.Session()
        session.headers = {
            'Authorization': f'Bearer {credentials.token}'
        }
        
        response = session.get(export_url)
        response.raise_for_status()
        
        return response.content
    except Exception as e:
        raise Exception(f"Error al descargar el archivo Excel: {str(e)}")

def backup_specific_sheets(backup_dir):
    max_retries = 5
    base_delay = 3  # segundos
    
    def exponential_backoff(attempt):
        return base_delay * (2 ** attempt) + random.uniform(0, 1)
    
    for attempt in range(max_retries):
        try:
            creds = load_credentials()
            scope = ['https://spreadsheets.google.com/feeds', 
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets']
            credentials = Credentials.from_service_account_info(creds, scopes=scope)
            client = gspread.authorize(credentials)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"excel_backup_{timestamp}.zip"
            zip_path = os.path.join(backup_dir, zip_filename)

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_sheets = len(SHEET_NAMES)
            processed_sheets = 0

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for sheet_name in SHEET_NAMES:
                    try:
                        status_text.text(f"Procesando: {sheet_name}")
                        
                        # Obtener ID de la hoja
                        sheet_id = get_sheet_id_by_name(client, sheet_name)
                        
                        if sheet_id:
                            # Descargar archivo Excel
                            excel_content = download_excel_file(sheet_id, credentials)
                            
                            # Guardar en el ZIP
                            zipf.writestr(f"{sheet_name}.xlsx", excel_content)
                            
                            processed_sheets += 1
                            progress_bar.progress(processed_sheets / total_sheets)
                        else:
                            st.warning(f"No se encontró la hoja: {sheet_name}")
                        
                    except Exception as e:
                        st.warning(f"Error al procesar la hoja {sheet_name}: {str(e)}")
                        continue

            status_text.text("¡Backup completado con éxito!")
            return zip_path

        except (RefreshError, RequestException, ConnectionError, SocketError, urllib3.exceptions.HTTPError) as e:
            if attempt < max_retries - 1:
                delay = exponential_backoff(attempt)
                st.warning(f"Intento {attempt + 1} falló. Reintentando en {delay:.2f} segundos... Error: {str(e)}")
                time.sleep(delay)
            else:
                raise Exception(f"No se pudo realizar el backup después de {max_retries} intentos: {str(e)}")

    raise Exception("Error inesperado en la función backup_specific_sheets")

def main():
    st.title("📊 Backup de Archivos de Excel de Google Drive")
    
    st.markdown("""
    Esta aplicación realiza un backup de los siguientes archivos de Excel de Google Drive:
    - gestion-reservas-dp
    - gestion-reservas-emp
    - gestion-reservas-abo
    
    Los archivos se descargarán en formato XLSX y se empaquetarán en un archivo ZIP.
    """)

    # Crear directorio de backup si no existe
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    if st.button("Iniciar Backup", type="primary"):
        try:
            with st.spinner('Realizando backup...'):
                zip_path = backup_specific_sheets(backup_dir)
                
                # Leer el archivo ZIP para permitir la descarga
                with open(zip_path, 'rb') as f:
                    zip_data = f.read()
                
                st.success("¡Backup completado exitosamente!")
                
                # Botón de descarga
                st.download_button(
                    label="Descargar Backup",
                    data=zip_data,
                    file_name=os.path.basename(zip_path),
                    mime="application/zip"
                )
                
        except Exception as e:
            st.error(f"Error durante el backup: {str(e)}")

if __name__ == "__main__":
    main()