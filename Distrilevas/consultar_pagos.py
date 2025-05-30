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

PAGOS_COLUMNS = [
    'Fecha_Pago', 'Nombre', 'Email', 'Fecha_Servicio', 'Hora_Servicio','Servicio',
    'Producto', 'Valor', 'Estado_Pago', 'Referencia_Pago', 'Encargado',
    'Banco', 'Valor_Pagado', 'Fecha_Registro'
]

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
        sheet = client.open('gestion-reservas-dlv')
        worksheet = sheet.worksheet('pagos')
        data = api_call_handler(lambda:worksheet.get_all_values())
        
        if not data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        if df.empty:
            st.error("El DataFrame está vacío después de cargar los datos.")
            return None
            
        # Convertir las columnas de fecha a datetime
        date_columns = ['Fecha_Pago', 'Fecha_Servicio', 'Fecha_Registro']
        for col in date_columns:
            df[col] = pd.to_datetime(df[col])
        
        # Convertir Valor a numérico
        df['Valor_Pagado'] = pd.to_numeric(df['Valor_Pagado'], errors='coerce')
        
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

def consulta_pagos():
    st.title('Sistema de Consulta de Pagos')
    
    # Cargar credenciales y datos
    try:
        creds = load_credentials_from_toml('./.streamlit/secrets.toml')
        df = get_google_sheet_data(creds)
    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return
    
    if df is not None:
        st.header('Filtros de búsqueda')
        
        # Crear columnas para los filtros de selección múltiple
        col1, col2, col3 = st.columns(3)
        
        with col1:
            productos = st.multiselect(
                'Productos',
                options=sorted(df['Producto'].unique())
            )
        
        with col2:
            estados = st.multiselect(
                'Estado del Pago',
                options=sorted(df['Estado_Pago'].unique())
            )
        
        with col3:
            encargados = st.multiselect(
                'Encargados',
                options=sorted(df['Encargado'].unique())
            )
        
        # Rango de fechas para fecha de servicio
        st.subheader('Rango de Fechas del Pago')
        fecha_min = df['Fecha_Pago'].min()
        fecha_max = df['Fecha_Pago'].max()
        
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
                
        # Aplicar filtros
        mask = (
            (df['Fecha_Pago'] >= pd.to_datetime(start_date)) & 
            (df['Fecha_Pago'] <= pd.to_datetime(end_date)) 
        )
        
        if productos:
            mask &= df['Producto'].isin(productos)
        if estados:
            mask &= df['Estado_Pago'].isin(estados)
        if encargados:
            mask &= df['Encargado'].isin(encargados)
            
        filtered_df = df[mask]
        
        # Mostrar resultados
        st.markdown("---")
        st.subheader('Resultados de la búsqueda')
        
        if not filtered_df.empty:
            # Métricas en una fila
            met1, met2, met3, met4 = st.columns(4)
            with met1:
                st.metric("Total Productos", len(filtered_df['Producto'].unique()))
            with met2:
                st.metric("Total Pagos", len(filtered_df))
            with met3:
                st.metric("Valor Total", f"${filtered_df['Valor_Pagado'].sum():,.2f}")
            with met4:
                st.metric("Promedio por Producto", f"${filtered_df['Valor_Pagado'].mean():,.2f}")
            
            st.write(f'Se encontraron {len(filtered_df)} registros')
            st.dataframe(filtered_df)
            
            # Botón de descarga
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Descargar resultados como CSV",
                data=csv,
                file_name="resultados_pagos.csv",
                mime="text/csv"
            )
        else:
            st.warning('No se encontraron registros con los filtros seleccionados')

#if __name__ == '__main__':
#    consulta_pagos()