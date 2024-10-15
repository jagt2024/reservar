import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from gspread.exceptions import APIError
import backoff
import socket
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
from urllib3.exceptions import ProtocolError, SSLError
import ssl
from requests.exceptions import RequestException
import urllib3

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CustomHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.ssl_context = kwargs.pop('ssl_context', None)
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        kwargs['ssl_context'] = context
        return super(CustomHTTPAdapter, self).init_poolmanager(*args, **kwargs)

def create_gspread_client_with_retries(creds):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scope)
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=15,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
        backoff_factor=0.5,
        raise_on_status=False
    )
    
    # Create a custom SSL context
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    
    adapter = CustomHTTPAdapter(max_retries=retry_strategy, ssl_context=ssl_context)
    http = requests.Session()
    http.mount("https://", adapter)
    
    # Increase timeout for SSL handshake
    http.request = lambda *args, **kwargs: super(requests.Session, http).request(
        *args, **{**kwargs, 'timeout': 60}
    )
    
    # Create gspread client with custom HTTP session
    return gspread.Client(auth=credentials, session=http)

@backoff.on_exception(backoff.expo, 
                      (APIError, ConnectionError, socket.error, RequestException, 
                       ProtocolError, SSLError, ssl.SSLError), 
                      max_tries=20,
                      jitter=backoff.full_jitter)
def get_google_sheet_data(creds):
    try:
        client = create_gspread_client_with_retries(creds)

        sheet_url = str(sheetUrl)
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet('reservas')
        
        # Implement chunked data retrieval with increased timeout
        all_data = []
        batch_size = 500  # Reduced batch size
        for start_row in range(1, worksheet.row_count, batch_size):
            end_row = min(start_row + batch_size - 1, worksheet.row_count)
            for attempt in range(5):  # Add retry logic for each chunk
                try:
                    chunk = worksheet.get(f'A{start_row}:Z{end_row}', timeout=60)
                    all_data.extend(chunk)
                    time.sleep(5)  # Increased delay between requests
                    break
                except Exception as e:
                    if attempt == 4:  # If this was the last attempt
                        raise
                    time.sleep(10)  # Wait before retrying
        
        if not all_data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None
        
        df = pd.DataFrame(all_data[1:], columns=all_data[0])
        
        if df.empty:
            st.error("El DataFrame está vacío después de cargar los datos.")
            return None
        
        df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
        
        # Informar sobre filas con fechas inválidas
        invalid_dates = df[df['FECHA'].isna()]
        if not invalid_dates.empty:
            st.warning(f"Se encontraron {len(invalid_dates)} filas con fechas inválidas. Estas filas serán excluidas del análisis.")
            st.write("Primeras 5 filas con fechas inválidas:")
            st.write(invalid_dates.head())
        
        if df.empty:
            st.error("El DataFrame está vacío después de eliminar las fechas inválidas.")
            return None
        
        # Eliminar filas con fechas inválidas
        df = df.dropna(subset=['FECHA'])
        
        return df

    except Exception as e:
        st.error(f"Error al obtener datos de Google Sheets: {str(e)}")
        raise  # Re-raise the exception to trigger the backoff

def download_and_process_data(creds_path):
    try:
        creds = load_credentials_from_toml(creds_path)
        st.success("Credenciales cargadas correctamente")
    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return

    try:
        with st.spinner('Descargando datos...'):
            df = get_google_sheet_data(creds)
        if df is not None and not df.empty:
            st.success('Datos descargados correctamente!')
            process_and_display_data(df)
        else:
            st.error("No se pudieron obtener datos válidos de Google Sheets.")
    except Exception as e:
        st.error(f"Error al procesar los datos: {str(e)}")
