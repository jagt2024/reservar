import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
import gspread
import toml
import time

st.cache_data.clear()
st.cache_resource.clear()

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1

# Configuración de caché
class Cache:
    def __init__(self, ttl_minutes=5):
        self.data = None
        self.last_fetch = None
        self.ttl = timedelta(minutes=ttl_minutes)

    def is_valid(self):
        if self.last_fetch is None or self.data is None:
            return False
        return datetime.now() - self.last_fetch < self.ttl

    def set_data(self, data):
        self.data = data
        self.last_fetch = datetime.now()

    def get_data(self):
        return self.data

# Inicializar caché en session state
if 'cache' not in st.session_state:
    st.session_state.cache = Cache()

FACTURAS_COLUMNS = [
    'FECHA_FACTURA', 'NUMERO_FACTURA', 'CLIENTE_NOMBRE', 'CLIENTE_NIT', 'CLIENTE_EMAIL', 'SERVICIOS', 'SUBTOTAL','TOTAL', 'IVA'
]

def api_call_handler(func):
    for i in range(0, 10):
        try:
            return func()
        except Exception as e:
            print(e)
            time.sleep(2 ** i)
    print("No se pudo conectar a la API de Google Spreadsheet después de 10 intentos.")
    raise SystemError

def load_credentials_from_toml(file_path):
    with open(file_path, 'r') as toml_file:
        config = toml.load(toml_file)
        credentials = config['sheetsemp']['credentials_sheet']
    return credentials

def get_google_sheet_data(creds):
  for intento in range(MAX_RETRIES):
    try:
      with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        sheet = client.open('gestion-reservas-dlv')
        worksheet = sheet.worksheet('facturacion')
        data = api_call_handler(lambda: worksheet.get_all_values())
        
        if not data:
            st.error("No se encontraron datos en la hoja de facturación.")
            return None
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        if df.empty:
            st.error("El DataFrame está vacío después de cargar los datos.")
            return None
            
        date_columns = ['FECHA_FACTURA']
        for col in date_columns:
            df[col] = pd.to_datetime(df[col])
        
        df['TOTAL'] = pd.to_numeric(df['TOTAL'], errors='coerce')
        
        return df
        
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
        st.error(f"Error al cargar los datos: {str(e)}")
        return None

def consulta_facturas():
    st.title('Sistema de Consulta de Facturas')   
    try:
        creds = load_credentials_from_toml('./.streamlit/secrets.toml')
        df = get_google_sheet_data(creds)

    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return
    
    if df is not None:
        st.header('Filtros de búsqueda')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            productos = st.multiselect(
                'CLIENTE_NIT',
                options=sorted(df['CLIENTE_NIT'].unique())
            )
        
        with col2:
            estados = st.multiselect(
                'NUMERO_FACTURA',
                options=sorted(df['NUMERO_FACTURA'].unique())
            )
        
        with col3:
            cliente_nombres = st.multiselect(
                'CLIENTE_NOMBRE',
                options=sorted(df['CLIENTE_NOMBRE'].unique())
            )
        
        st.subheader('Rango de Fechas de Facturación')
        fecha_min = df['FECHA_FACTURA'].min()
        fecha_max = df['FECHA_FACTURA'].max()
        
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                'Fecha inicial',
                fecha_min,
                min_value=fecha_min,
                max_value=fecha_max
            )
        
        with col2:
            end_date = st.date_input(
                'Fecha final',
                fecha_max,
                min_value=fecha_min,
                max_value=fecha_max
            )
                
        mask = (
            (df['FECHA_FACTURA'] >= pd.to_datetime(start_date)) & 
            (df['FECHA_FACTURA'] <= pd.to_datetime(end_date))
        )
        
        if productos:
            mask &= df['CLIENTE_NIT'].isin(productos)
        if estados:
            mask &= df['NUMERO_FACTURA'].isin(estados)
        if cliente_nombres:
            mask &= df['CLIENTE_NOMBRE'].isin(cliente_nombres)
            
        filtered_df = df[mask]
        
        st.markdown("---")
        st.subheader('Resultados de la búsqueda')
        
        if not filtered_df.empty:
            met1, met2, met3, met4 = st.columns(4)
            with met1:
                st.metric("Total Facturas", len(filtered_df))
            with met2:
                st.metric("SubTotal CLIENTE", len(filtered_df['SUBTOTAL'].unique()))
            with met3:
                st.metric("Total", f"${filtered_df['TOTAL'].sum():,.2f}")
            with met4:
                st.metric("Promedio por Factura", f"${filtered_df['TOTAL'].mean():,.2f}")
            
            st.write(f'Se encontraron {len(filtered_df)} registros')
            st.dataframe(filtered_df)
            
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Descargar resultados como CSV",
                data=csv,
                file_name="resultados_facturas.csv",
                mime="text/csv"
            )
        else:
            st.warning('No se encontraron registros con los filtros seleccionados')

#if __name__ == '__main__':
#    consulta_facturas()
