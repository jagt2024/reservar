import streamlit as st
import pandas as pd
import toml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import random
import string
import os
from google.oauth2 import service_account
import sys
import logging

st.cache_data.clear()
st.cache_resource.clear()

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='interface_pago_reserva.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Constants
RESERVAS_COLUMNS = ['NOMBRE', 'EMAIL', 'FECHA', 'HORA', 'SERVICIOS', 'TELEFONO', 'PRECIO', 'ENCARGADO', 'ZONA']
PAGOS_COLUMNS = ['Fecha_Pago', 'Nombre', 'Email', 'Fecha_Servicio', 'Hora_Servicio', 'Servicio', 'Valor', 'Estado_Pago', 'Referencia_Pago', 'Encargado', 'Quien_Registra', 'Correo', 'Fecha_Registro']

def load_credentials_from_toml(file_path):
    """Loads credentials from TOML file"""
    try:
        with open(file_path, 'r') as toml_file:
            config = toml.load(toml_file)
            credentials = config['sheetsemp']['credentials_sheet']
        return credentials
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de credenciales en: {file_path}")
        return None
    except KeyError:
        st.error("El archivo de credenciales no tiene el formato correcto")
        return None
    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return None

def get_google_sheet_data(creds, sheet_name='reservas'):
    """Gets data from Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = service_account.Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        sheet = client.open('gestion-reservas-dp')
        worksheet = sheet.worksheet(sheet_name)
        data = worksheet.get_all_values()
        
        if not data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None, None, None
        
        if len(data) <= 1:
            df = pd.DataFrame(columns=RESERVAS_COLUMNS)
        else:
            df = pd.DataFrame(data[1:], columns=data[0])
            
        return sheet, worksheet, df
    except Exception as e:
        st.error(f"Error al acceder a Google Sheets: {str(e)}")
        return None, None, None

def register_payment(sheet, fecha_pago, estado_pago,reference, reserva_data, quien_registra, correo, fecha_registro):
    """Registers the payment in the payments sheet"""
    try:
        pagos_worksheet = sheet.worksheet('pagos')  # Changed from 'reservas' to 'pagos'
        
        payment_data = [
            fecha_pago.strftime('%Y-%m-%d'),
            reserva_data['NOMBRE'],
            reserva_data['EMAIL'],
            reserva_data['FECHA'],
            reserva_data['HORA'],
            reserva_data['SERVICIOS'],
            reserva_data['PRECIO'],
            'PAGADO',
            reference,  
            reserva_data['ENCARGADO'],
            quien_registra,
            correo,
            fecha_registro
        ]
        
        pagos_worksheet.append_row(payment_data)
        return True
    except Exception as e:
        st.error(f"Error al registrar el pago: {str(e)}")
        return False

def search_reservations(df, nombre='', fecha=''):
    """Searches reservations by name and date"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_filtered = df.copy()
    
    if nombre:
        df_filtered = df_filtered[df_filtered['NOMBRE'].str.lower().str.contains(nombre.lower())]
    
    if fecha:
        fecha_str = fecha.strftime('%Y-%m-%d')
        df_filtered = df_filtered[df_filtered['FECHA'] == fecha_str]
    
    return df_filtered

def pago():
    st.title("Registro de Pago del Servicio")
    
    # Load credentials
    credentials = load_credentials_from_toml('./.streamlit/secrets.toml')

    if credentials is None:
        return

    # Get Google Sheets data
    sheet, worksheet, df = get_google_sheet_data(credentials, 'reservas')
    if df is None:
        return

    payment_col1, payment_col2 = st.columns(2)
                        
    with payment_col1:
            quien_registra = st.text_input('Nombre Quien Registra:', key=f"quien")
            reference = st.text_input('No.Referencia del Pago:', key=f"refer")

    with payment_col2:
            correo = st.text_input('Correo Electronico:', key=f"correoe")
            fecha_pago = st.date_input('Fecha del Pago:', key=f"fechap")
    # Add debug logging
           
    logging.debug(f"Valores del formulario - Quien: {quien_registra}, Ref: {reference}, ID: {correo}")

    # Search section
    st.subheader("Buscar Reserva")
    col1, col2 = st.columns(2)
    
    with col1:
        search_name = st.text_input("Buscar por Nombre")
    with col2:
        search_date = st.date_input("Buscar por Fecha (YYYY-MM-DD)")

    if st.button("Buscar"):
        filtered_df = search_reservations(df, search_name, search_date)
        
        if filtered_df.empty:
            st.warning("No se encontraron reservas con los criterios especificados.")
        else:
            st.subheader(f"Resultados encontrados: {len(filtered_df)}")

            # Create form for payment registration
            
            for index, row in filtered_df.iterrows():
                          with st.expander(f"Reserva: {row['NOMBRE']} - {row['FECHA']}"):
                            col1, col2, col3 = st.columns(3)
                    
                            with col1:
                                st.write(f"**Nombre:** {row['NOMBRE']}")
                                st.write(f"**Email:** {row['EMAIL']}")
                                st.write(f"**Fecha:** {row['FECHA']}")
                    
                            with col2:
                                st.write(f"**Hora:** {row['HORA']}")
                                st.write(f"**Servicio:** {row['SERVICIOS']}")
                                st.write(f"**Teléfono:** {row['TELEFONO']}")
                                st.write(f"**Precio:** ${row['PRECIO']}")
                    
                            with col3:
                                st.write(f"**Encargado:** {row['ENCARGADO']}")
                                st.write(f"**Zona:** {row['ZONA']}")
                    
                            # Payment section
                            st.divider()
                    
                            #registrar ='True'
                            with st.form(key=f'payment_form'):                    
            
                                registrar = st.form_submit_button("Registrar Pago", type="primary")
                                #if registrar:
                                logging.info("Iniciando proceso de registro de pago")
                            
                                if not quien_registra or not correo or not      reference or not fecha_pago:
                                    st.error("Por favor complete todos los campos requeridos.")
                                    logging.warning("Campos incompletos en el formulario")
                        
                                elif not registrar:
                                    logging.debug(f"Botón Registrar clickeado: {registrar}")

                                    with st.spinner('Procesando pago...'):
                                     try:
                                        fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M')
                                        estado_pago = "PAGADO"
                                        
                                        # Add debug logging for precio conversion
                                        logging.debug(f"Precio original: {row['PRECIO']}")
                                        precio = float(row['PRECIO'])
                                                                                
                                        if register_payment(
                                            sheet, 
                                            fecha_pago, 
                                            estado_pago,
                                            reference, 
                                            row, 
                                            quien_registra, 
                                            correo, 
                                            fecha_registro
                                            ):
                                            st.success(f"""
                                            ¡Pago registrado exitosamente!
                                            **Referencia:** {reference}
                                            **Monto:** ${precio:.2f}
                                            """)
                                            st.balloons()
                                            logging.info(f"Pago registrado exitosamente. Referencia: {reference}")
                                        else:
                                            st.error("Error al registrar el pago. Por favor contacte al administrador.")
                                            logging.error("Fallo en register_payment")
                                     except Exception as e:
                                        st.error(f"Error durante el registro del pago: {str(e)}")
                                        logging.error(f"Error durante el registro del pago: {str(e)}", exc_info=True)

#if __name__ == "__main__":
#    pago()