import streamlit as st
import pandas as pd
import toml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def load_credentials():
    with open('./.streamlit/secrets.toml', 'r') as toml_file:
        config = toml.load(toml_file)
        creds = config['sheetsemp']['credentials_sheet']
    return creds

def get_google_sheet_data(creds):
    #scope=["https://www.googleapis.com/auth/spreadsheets.readonly",
    #       "https://www.googleapis.com/auth/drive.readonly",
    #       ],
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scope)
    client = gspread.authorize(credentials)
    return client

@st.cache_data
def validar_existencia_reserva(fecha, hora, servicio, encargado):

    try:
        # Cargar credenciales
        creds = load_credentials()
        
        # Obtener cliente de Google Sheets
        client = get_google_sheet_data(creds)
        
        sheet = client.open('gestion-reservas-dp')
        
        worksheet = sheet.worksheet('reservas')
        
        # Abrir la hoja de cálculo
        #sheet = client.open('gestion-reservas-dp').sheet1
        
        # Obtener todos los registros
        registros = worksheet.get_all_records()
        
        # Convertir a DataFrame
        df = pd.DataFrame(registros)
        
        # Validar existencia de registro
        registro_existe = df[
            (df['FECHA'] == fecha) & 
            (df['HORA'] == hora) & 
            (df['SERVICIOS'] == servicio) & 
            (df['ENCARGADO'] == encargado)
        ].shape[0] > 0
        
        return registro_existe
    
    except Exception as e:
        print(f"Error al validar la reserva: {str(e)}")
        return None

def formatear_fecha(fecha):

    if isinstance(fecha, str):
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
            return fecha_obj.strftime('%Y-%m-%d')
        except ValueError:
            try:
                fecha_obj = datetime.strptime(fecha, '%d/%m/%Y')
                return fecha_obj.strftime('%Y-%m-%d')
            except ValueError:
                raise ValueError("Formato de fecha no válido. Use YYYY-MM-DD o DD/MM/YYYY")
    elif isinstance(fecha, datetime):
        return fecha.strftime('%Y-%m-%d')
    return fecha

def formatear_hora(hora):

    if isinstance(hora, str):
        try:
            hora_obj = datetime.strptime(hora, '%H:%M')
            return hora_obj.strftime('%H:%M')
        except ValueError:
            raise ValueError("Formato de hora no válido. Use HH:MM")
    return hora

"""
            if nombre or servicio or encargado or email:
                fecha_formateada = formatear_fecha(fecha)
                hora_formateada = formatear_hora(hora)
                print(f'fecha hora formateada : {fecha_formateada} {hora_formateada}')
            
                #fecha_ejemplo = "2024-03-21 14:30"
                resultado = calcular_diferencia_tiempo(f'{fecha_formateada} {hora_formateada}')
                print(f"Diferencia en minutos: {resultado}")
            
                #existe = validar_existencia_reserva(
                #fecha_formateada,
                #hora_formateada,
                ##servicios,
                #encargado
                #)
        
                if existe is None:
                    st.error("Error al validar la reserva")
                elif existe and resultado == 90:
                    st.warning("La reserva no esta disponible")
                else:
                    st.success("La reserva está disponible")
            """

existe = validar_existencia_reserva(
            "2024-10-21",
            "10:00",
            "Hacia el Aeropuerto",
            "encargado1"
            )
        
if existe is None:
   st.error("Error al validar la reserva")
elif existe:
   st.warning("La reserva no esta disponible")
else:
   st.success("La reserva está disponible")
