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

def api_call_handler(func):
  # Number of retries
  for i in range(0, 10):
    try:
      return func()
    except Exception as e:
      print(e)
      time.sleep(2 ** i)
  print("The program couldn't connect to the Google Spreadsheet API for 10 times. Give up and check it manually.")
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
        sheet = client.open('gestion-reservas-cld')
        worksheet = sheet.worksheet('reservas')
        data = api_call_handler(lambda:worksheet.get_all_values())
        
        if not data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        if df.empty:
            st.error("El DataFrame está vacío después de cargar los datos.")
            return None
            
        # Convertir la columna de fecha a datetime
        df['FECHA'] = pd.to_datetime(df['FECHA'])
        
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
            return None

    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return None

def consulta_reserva():
    st.title('Sistema de Consulta de Reservas')
    
    # Cargar credenciales y datos
    try:
        creds = load_credentials_from_toml('./.streamlit/secrets.toml')
        df = get_google_sheet_data(creds)
    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return
    
    if df is not None:
        st.header('Filtros de búsqueda')
        
        # Crear tres columnas para los filtros de selección múltiple
        col1, col2, col3 = st.columns(3)
        
        with col1:
            servicios = st.multiselect(
                'Servicios',
                options=sorted(df['SERVICIOS'].unique())
            )
        
        with col2:
            encargados = st.multiselect(
                'Encargados',
                options=sorted(df['ENCARGADO'].unique())
            )
        
        with col3:
            zonas = st.multiselect(
                'Zonas',
                options=sorted(df['ZONA'].unique())
            )
        
        # Crear dos columnas para el rango de fechas
        st.subheader('Rango de Fechas')
        fecha_min = df['FECHA'].min()
        fecha_max = df['FECHA'].max()
        
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
        
        # Convertir las fechas seleccionadas a datetime
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        # Aplicar filtros
        mask = (df['FECHA'] >= start_date) & (df['FECHA'] <= end_date)
        
        if servicios:
            mask &= df['SERVICIOS'].isin(servicios)
        if encargados:
            mask &= df['ENCARGADO'].isin(encargados)
        if zonas:
            mask &= df['ZONA'].isin(zonas)
            
        filtered_df = df[mask]
        
        # Mostrar resultados
        st.markdown("---")  # Línea divisoria
        st.subheader('Resultados de la búsqueda')
        
        if not filtered_df.empty:
            # Métricas en una fila
            met1, met2, met3 = st.columns(3)
            with met1:
                st.metric("Total Servicios", len(filtered_df['SERVICIOS'].unique()))
            with met2:
                st.metric("Total Encargados", len(filtered_df['ENCARGADO'].unique()))
            with met3:
                st.metric("Total Zonas", len(filtered_df['ZONA'].unique()))
            
            st.write(f'Se encontraron {len(filtered_df)} registros')
            st.dataframe(filtered_df)
            
            # Botón de descarga
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Descargar resultados como CSV",
                data=csv,
                file_name="resultados_reservas.csv",
                mime="text/csv"
            )
        else:
            st.warning('No se encontraron registros con los filtros seleccionados')

#if __name__ == '__main__':
#    consulta_reserva()