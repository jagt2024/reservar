import streamlit as st
import pandas as pd
import toml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time

def load_credentials():
    with open('./.streamlit/secrets.toml', 'r') as toml_file:
        config = toml.load(toml_file)
        creds = config['sheetsemp']['credentials_sheet']
    return creds

def get_google_sheet_data(creds):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scope)
    client = gspread.authorize(credentials)
    return client

def validar_existencia_reserva(fecha, hora, servicio, encargado):
    try:
        # Cargar credenciales
        creds = load_credentials()
        
        # Obtener cliente de Google Sheets
        client = get_google_sheet_data(creds)
        
        # Abrir la hoja de cálculo
        sheet = client.open('gestion-reservas-dp').sheet1
        
        # Obtener todos los registros
        registros = sheet.get_all_records()
        
        # Convertir a DataFrame
        df = pd.DataFrame(registros)
        
        # Convertir hora a string en formato HH:MM
        hora_str = hora.strftime("%H:%M")
        
        # Validar existencia de registro
        registro_existe = df[
            (df['Fecha'] == fecha.strftime("%Y-%m-%d")) & 
            (df['Hora'] == hora_str) & 
            (df['Servicio'] == servicio) & 
            (df['Encargado'] == encargado)
        ].shape[0] > 0
        
        return registro_existe
    
    except Exception as e:
        st.error(f"Error al validar la reserva: {str(e)}")
        return None

def cargar_servicios():
    """Cargar lista de servicios desde la hoja de cálculo o definir una lista estática"""
    return ["Consulta General", "Especialidad 1", "Especialidad 2", "Tratamiento 1", "Tratamiento 2"]

def cargar_encargados():
    """Cargar lista de encargados desde la hoja de cálculo o definir una lista estática"""
    return ["Dr. García", "Dra. Rodríguez", "Dr. Martínez", "Dra. López", "Dr. Sánchez"]

def validacion_reservas_page():
    st.title("Validación de Reservas")
    
    # Crear un contenedor para el formulario
    with st.form("validacion_form"):
        # Campos de entrada
        fecha = st.date_input(
            "Seleccione la fecha",
            min_value=datetime.today()
        )
        
        hora = st.time_input(
            "Seleccione la hora",
            value=time(9, 0),  # Valor por defecto: 9:00
            step=1800  # Intervalos de 30 minutos (en segundos)
        )
        
        servicio = st.selectbox(
            "Seleccione el servicio",
            options=cargar_servicios()
        )
        
        encargado = st.selectbox(
            "Seleccione el encargado",
            options=cargar_encargados()
        )
        
        # Botón de validación
        submitted = st.form_submit_button("Validar Reserva")
        
        if submitted:
            with st.spinner('Validando reserva...'):
                existe = validar_existencia_reserva(fecha, hora, servicio, encargado)
                
                if existe is None:
                    st.error("Ocurrió un error al validar la reserva")
                elif existe:
                    st.warning("⚠️ La reserva ya existe en el sistema")
                    st.markdown("""
                        **Detalles de la reserva encontrada:**
                        * Fecha: {}
                        * Hora: {}
                        * Servicio: {}
                        * Encargado: {}
                    """.format(
                        fecha.strftime("%Y-%m-%d"),
                        hora.strftime("%H:%M"),
                        servicio,
                        encargado
                    ))
                else:
                    st.success("✅ La reserva está disponible")

    # Información adicional
    with st.expander("ℹ️ Información de uso"):
        st.markdown("""
        **Instrucciones:**
        1. Seleccione la fecha deseada para la reserva
        2. Elija la hora (en intervalos de 30 minutos)
        3. Seleccione el servicio requerido
        4. Elija el encargado
        5. Presione 'Validar Reserva' para verificar la disponibilidad
        
        **Nota:** Las reservas se validan contra el sistema de gestión en tiempo real.
        """)

if __name__ == "__main__":
    st.set_page_config(
        page_title="Validación de Reservas",
        page_icon="📅",
        layout="centered"
    )
    validacion_reservas_page()
