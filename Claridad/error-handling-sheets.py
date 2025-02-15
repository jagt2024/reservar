import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
from datetime import datetime, timedelta
import json

# Configuración de la página
st.set_page_config(
    page_title="Gestión de Reservas",
    page_icon="📅",
    layout="wide"
)

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1
SPREADSHEET_ID = 'TU-ID-DE-SPREADSHEET'  # Reemplaza con tu ID
SCOPE = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

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

def create_google_sheets_service():
    """Crear y retornar el servicio de Google Sheets."""
    try:
        # Cargar credenciales desde secrets
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPE
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error al configurar el servicio de Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=300)  # Cache de 5 minutos
def cargar_datos_con_reintento():
    """Cargar datos de Google Sheets con sistema de reintentos."""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                service = create_google_sheets_service()
                if not service:
                    return None

                result = service.spreadsheets().values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range='A1:Z'  # Ajusta según tu rango de datos
                ).execute()

                # Convertir datos a DataFrame
                data = result.get('values', [])
                if not data:
                    st.warning('No se encontraron datos en la hoja de cálculo.')
                    return None

                df = pd.DataFrame(data[1:], columns=data[0])
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
            st.error(f"Error inesperado: {str(e)}")
            return None

    return None

def main():
    st.title("📊 Gestión de Reservas")

    # Botón para forzar recarga de datos
    if st.button("🔄 Recargar Datos"):
        st.session_state.cache = Cache()  # Resetear caché
        st.cache_data.clear()  # Limpiar caché de Streamlit

    try:
        # Intentar cargar datos
        with st.spinner("Cargando datos..."):
            if st.session_state.cache.is_valid():
                df = st.session_state.cache.get_data()
                st.success("Datos cargados desde caché")
            else:
                df = cargar_datos_con_reintento()
                if df is not None:
                    st.session_state.cache.set_data(df)
                    st.success("Datos actualizados correctamente")

        if df is not None:
            # Mostrar datos
            st.subheader("Vista previa de datos")
            st.dataframe(df, use_container_width=True)

            # Agregar filtros y visualizaciones según necesites
            with st.expander("📊 Análisis de Datos"):
                # Aquí puedes agregar más visualizaciones o análisis
                st.write("Resumen de datos:")
                st.write(f"Total de registros: {len(df)}")
                # Agrega más análisis según tus necesidades

    except Exception as e:
        st.error(f"Error en la aplicación: {str(e)}")
        st.info("Por favor, intenta recargar la página o contacta al administrador.")

if __name__ == "__main__":
    main()
