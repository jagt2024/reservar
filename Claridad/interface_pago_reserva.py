import streamlit as st
import pandas as pd
import toml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import random
import string
import os
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
import sys
import logging
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

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='interface_pago_reserva.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def api_call_handler(func):
    for i in range(0, 10):
        try:
            return func()
        except Exception as e:
            print(e)
            time.sleep(2 ** i)
    print("The program couldn't connect to the Google Spreadsheet API for 10 times. Give up and check it manually.")
    raise SystemError

def convert_price_string_to_float(price_str):
    """
    Convert a price string like "25.000,00" to float (25000.00)
    """
    try:
        # Remove any currency symbols or spaces
        price_str = price_str.strip().replace('$', '')
        # Replace dots with nothing (remove thousand separators) and comma with dot
        price_str = price_str.replace('.', '').replace(',', '.')
        return float(price_str)
    except (ValueError, AttributeError) as e:
        logging.error(f"Error converting price string '{price_str}' to float: {str(e)}")
        raise ValueError(f"Invalid price format: {price_str}")

# Constants
RESERVAS_COLUMNS = ['NOMBRE', 'EMAIL', 'FECHA', 'HORA', 'SERVICIOS', 'PRODUCTO','TELEFONO', 'PRECIO', 'ENCARGADO', 'ZONA']
PAGOS_COLUMNS = ['Fecha_Pago', 'Nombre', 'Email', 'Fecha_Servicio', 'Hora_Servicio', 'Servicio', 'Producto', 'Valor', 'Estado_Pago', 'Referencia_Pago', 'Encargado', 'Banco', 'Valor_Pagado', 'Fecha_Registro']

def load_credentials_from_toml(file_path):
    with open(file_path, 'r') as toml_file:
        config = toml.load(toml_file)
        credentials = config['sheetsemp']['credentials_sheet']
    return credentials

def get_google_sheet_data(creds, sheet_name='reservas'):
  """Gets data from Google Sheets"""
  for intento in range(MAX_RETRIES):
    try:
      with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = service_account.Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        sheet = client.open('gestion-reservas-cld')
        worksheet = sheet.worksheet(sheet_name)
        data = api_call_handler(lambda:worksheet.get_all_values())
        
        if not data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None, None, None
        
        if len(data) <= 1:
            df = pd.DataFrame(columns=RESERVAS_COLUMNS)
        else:
            df = pd.DataFrame(data[1:], columns=data[0])
            
        return sheet, worksheet, df
    
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
            return None, None, None    

    except Exception as e:
        st.error(f"Error al acceder a Google Sheets: {str(e)}")
        return None, None, None

def search_reservations(df, nombre='', fecha=None):
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

def check_duplicate_payment(pagos_worksheet, nombre, producto, valor, fecha_servicio):
    """Check if a payment with the same reference, email and service date exists"""
    try:
        # Get all payments
        payments_data = api_call_handler(lambda:pagos_worksheet.get_all_values())
        if len(payments_data) <= 1:  # Only header or empty
            return False
            
        df_payments = pd.DataFrame(payments_data[1:], columns=payments_data[0])
        
        # Check for duplicates
        duplicates = df_payments[
            (df_payments['Nombre'].str.lower() == nombre.lower()) &
            (df_payments['Producto'].str.lower() == producto.lower()) &
            (df_payments['Valor'] == valor) &
            (df_payments['Fecha_Servicio'] == fecha_servicio)
        ]
        
        return len(duplicates) > 0
    except Exception as e:
        logging.error(f"Error checking duplicates: {str(e)}")
        return False

def delete_payment(pagos_worksheet, row_index):
    """Delete a payment record by row index"""
    try:
        pagos_worksheet.delete_rows(row_index + 2)  # +2 because row_index is 0-based and we need to skip header
        return True
    except Exception as e:
        logging.error(f"Error deleting payment: {str(e)}")
        return False

def get_payments_data(sheet):
    """Get all payments data"""
    try:
        pagos_worksheet = sheet.worksheet('pagos')
        data = api_call_handler(lambda: pagos_worksheet.get_all_values())
        
        if not data or len(data) <= 1:
            return pd.DataFrame(columns=PAGOS_COLUMNS), pagos_worksheet
            
        df_pagos = pd.DataFrame(data[1:], columns=data[0])
        return df_pagos, pagos_worksheet
    except Exception as e:
        logging.error(f"Error getting payments data: {str(e)}")
        return pd.DataFrame(columns=PAGOS_COLUMNS), None

def register_payment(sheet, fecha_pago, estado_pago, reference, reserva_data, banco, valor_pagado, fecha_registro):
    """Registers the payment in the payments sheet"""
    try:
        pagos_worksheet = sheet.worksheet('pagos')
        
        # Check for duplicates before registering
        is_duplicate = check_duplicate_payment(
            pagos_worksheet,            
            reserva_data['NOMBRE'],
            reserva_data['PRODUCTO'],
            reserva_data['PRECIO'],
            reserva_data['FECHA']
        )
        
        if is_duplicate:
            st.error("Este pago ya fue registrado anteriormente (mismo nombre, producto, valor y fecha de servicio).")
            return False
        
        # Convert price string to float before processing
        try:
            #precio = convert_price_string_to_float(reserva_data['PRECIO'])
            valor_pagado_float = str(valor_pagado)  # Ensure valor_pagado is also converted properly
        except ValueError as e:
            st.error(f"Error en el formato del precio: {str(e)}")
            return False
            
        payment_data = [
            fecha_pago.strftime('%Y-%m-%d'),
            reserva_data['NOMBRE'],
            reserva_data['EMAIL'],
            reserva_data['FECHA'],
            reserva_data['HORA'],
            reserva_data['SERVICIOS'],
            reserva_data['PRODUCTO'],
            reserva_data['PRECIO'],
            'PAGADO',
            reference,  
            reserva_data['ENCARGADO'],
            banco,
            valor_pagado,  
            fecha_registro
        ]
        
        pagos_worksheet.append_row(payment_data)
        return True
    except Exception as e:
        st.error(f"Error al registrar el pago: {str(e)}")
        logging.error(f"Error registering payment: {str(e)}", exc_info=True)
        return False

def filter_payments_by_date_and_name(df_pagos, search_nombre=None, search_fecha=None):
    """Filter payments by date and name with proper handling"""
    if df_pagos.empty:
        return df_pagos
        
    filtered_pagos = df_pagos.copy()
    
    # Filter by name if provided
    if search_nombre:
        filtered_pagos = filtered_pagos[
            filtered_pagos['Nombre'].str.lower().str.contains(search_nombre.lower())
        ]
    
    # Filter by date if provided
    if search_fecha:
        fecha_str = search_fecha.strftime('%Y-%m-%d')
        filtered_pagos = filtered_pagos[filtered_pagos['Fecha_Servicio'] == fecha_str]
    
    return filtered_pagos

def pago():
    st.title("Registro de Pago del Servicio")
    
    # Add tabs for different operations
    tab1, tab2 = st.tabs(["Registrar Pago", "Eliminar Pago"])
    
    # Load credentials
    credentials = load_credentials_from_toml('./.streamlit/secrets.toml')
    if credentials is None:
        return

    # Get Google Sheets data
    sheet, worksheet, df = get_google_sheet_data(credentials, 'reservas')
    if df is None:
        return

    # Tab 1: Register Payment
    with tab1:
        payment_col1, payment_col2 = st.columns(2)
                            
        with payment_col1:
            fecha_pago = st.date_input('Fecha del Pago:', key="fechap")
            banco = st.selectbox("Banco", ["Banco de Colombia", "Banco Davivienda", "Banco de Bogota", "Banco de Occidente", "Banco Popular", "Banco Colpatria", "Banco BBVA", "Nequi", "Personal"])
            
        with payment_col2:
            valor_pagado = st.number_input('Valor Pagado :', min_value=0.0, format="%f", key="vpago")
            reference = st.text_area('Referencias del Pago:', key="refer")
            
        # Search section
        st.subheader("Buscar Reserva")
        col1, col2 = st.columns(2)
        
        with col1:
            search_name = st.text_input("Buscar por Nombre", key='nombres')
        with col2:
            search_date = st.date_input("Buscar por Fecha (YYYY-MM-DD)", key='fechas')

        if st.button("Buscar"):
            filtered_df = search_reservations(df, search_name, search_date)
            
            if filtered_df.empty:
                st.warning("No se encontraron reservas con los criterios especificados.")
            else:
                st.subheader(f"Resultados encontrados: {len(filtered_df)}")

                # Create form for payment registration
                with st.form("transaction_form"):
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
                                st.write(f"**Prodcto:** {row['PRODUCTO']}")
                        
                            with col3:
                                st.write(f"**Precio:** ${row['PRECIO']}")
                                st.write(f"**Encargado:** {row['ENCARGADO']}")
                                st.write(f"**Zona:** {row['ZONA']}")
                        
                            st.divider()
                        
                            if not banco or not fecha_pago or not valor_pagado or not reference:
                                st.error("Por favor complete todos los campos requeridos.")
                                logging.warning("Campos incompletos en el formulario")
                            
                            else:
                                #submitted = st.form_submit_button("Registrar Pago")
                    
                                #if submitted:
                                with st.spinner('Procesando pago...'):
                                        try:
                                            fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M')
                                            estado_pago = "PAGADO"
                                            precio = row['PRECIO']
                                            
                                            if register_payment(
                                                sheet, 
                                                fecha_pago, 
                                                estado_pago,
                                                reference, 
                                                row, 
                                                banco, 
                                                valor_pagado, 
                                                fecha_registro
                                                ):
                                                st.success(f"""
                                                    ¡Pago registrado exitosamente!
                                                    **Referencia:** {reference}
                                                    **Monto:** ${valor_pagado:.2f}
                                                    """)
                                                st.balloons()
                                                logging.info(f"Pago registrado exitosamente. Referencia: {reference}")
                                            else:
                                                st.error("Error al registrar el pago. Por favor contacte al administrador.")
                                                logging.error("Fallo en register_payment")
                                        except Exception as e:
                                            st.error(f"Error durante el registro del pago: {str(e)}")
                                            logging.error(f"Error durante el registro del pago: {str(e)}", exc_info=True)

    # Tab 2: Delete Payment
    with tab2:
        st.subheader("Eliminar Registro de Pago")

        #et payments data
        df_pagos, pagos_worksheet = get_payments_data(sheet)

        if not df_pagos.empty:
            # Search filters for payments
            search_col1, search_col2 = st.columns(2)
            with search_col1:
                search_nombre = st.text_input("Buscar por Nombre", key='nombre2')
        
            with search_col2:
                search_fecha = st.date_input("Buscar por Fecha Servicio", key='fecha2')    

            # Search button
            if st.button("Buscar Pagos"):
                filtered_pagos = filter_payments_by_date_and_name(df_pagos, search_nombre, search_fecha)
            
                if filtered_pagos.empty:
                    st.warning("No se encontraron pagos con los criterios especificados.")
                else:
                    st.write(f"Pagos encontrados: {len(filtered_pagos)}")
                    for idx, row in filtered_pagos.iterrows():
                        with st.expander(f"Pago: {row['Nombre']} - {row['Fecha_Servicio']}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Referencia:** {row['Referencia_Pago']}")
                                st.write(f"**Email:** {row['Email']}")
                                st.write(f"**Fecha Servicio:** {row['Fecha_Servicio']}")
                                st.write(f"**Producto:** {row['Producto']}")
                            with col2:
                                st.write(f"**Valor Pagado:** ${row['Valor_Pagado']}")
                                st.write(f"**Banco:** {row['Banco']}")
                                st.write(f"**Fecha Registro:** {row['Fecha_Registro']}")
                    
                            #if st.button(f"Eliminar Pago {row['Referencia_Pago']}", key=f"delete_{idx}"):
                            if st.session_state.get(f'confirm_delete_{idx}', True):

                                if not st.button("Eliminar Pago ", key="delete_pago"):

                                    if delete_payment(pagos_worksheet, idx):
                                        st.success("Pago eliminado exitosamente")
                                        st.rerun()
                                    else:
                                        st.error("Error al eliminar el pago")
                                else:
                                    
                                    #if st.session_state[f'confirm_delete_{idx}'] = True
                                    st.warning("¿Error  Presione el botón nuevamente para confirmar.")
            else:
                st.info("Ingrese criterios de búsqueda y presione 'Buscar Pagos' para encontrar el pago que desea eliminar.")
        else:
            st.info("No hay pagos registrados en el sistema.")