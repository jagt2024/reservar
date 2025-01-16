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

# Constants
RESERVAS_COLUMNS = ['NOMBRE', 'EMAIL', 'FECHA', 'HORA', 'SERVICIOS', 'TELEFONO', 'PRECIO', 'ENCARGADO', 'ZONA']
PAGOS_COLUMNS = ['Fecha_Pago', 'Nombre', 'Email', 'Fecha_Servicio' ,'Hora_Servicio', 'Servicio', 'Valor',  'Estado_Pago', 'Referencia_Pago', 'Encargado', 'Quien_Registra', 'Identificacion']

def validate_search_date(search_date):
    """Validates if the search date is within the allowed range (today to 5 days ahead)"""
    today = datetime.now().date()
    max_date = today + timedelta(days=5)
    
    if search_date < today:
        return False, "La fecha de búsqueda no puede ser anterior a la fecha actual"
    elif search_date > max_date:
        return False, f"La fecha máxima permitida es {max_date.strftime('%Y-%m-%d')}"
    return True, ""

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

def register_payment(sheet, reference, reserva_data, payment_amount, quien_registra, identificacion):
    """Registers the payment in the payments sheet"""
    try:
        pagos_worksheet = sheet.worksheet('pagos')
        
        payment_data = [
            datetime.now().strftime('%Y-%m-%d %H:%M'),  # Fecha_Pago
            reserva_data['NOMBRE'],                      # Nombre
            reserva_data['EMAIL'],                      # Email
            reserva_data['FECHA'],                     # Fecha_Servicio
            reserva_data['HORA'],                       # Hora_Servicio
            reserva_data['SERVICIOS'],                  # Servicio
            payment_amount,                             # Valor
            'PAGADO',                                   # Estado_Pago
            reference,                                 # Referencia_Pago
            reserva_data['ENCARGADO'],                 # Encargado
            quien_registra,                            # Quien_Registra
            identificacion                             # Identificacion
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

def main():
    st.title("Sistema de Pagos - Reservas")
    
    # Load credentials
    credentials = load_credentials_from_toml('./.streamlit/secrets.toml')
    if credentials is None:
        return

    # Get Google Sheets data
    sheet, worksheet, df = get_google_sheet_data(credentials, 'reservas')
    if df is None:
        return

    # Search section with date validation
    st.subheader("Buscar Reserva")
    col1, col2 = st.columns(2)
    
    with col1:
        search_name = st.text_input("Buscar por Nombre")
    with col2:
        # Configure date input with min and max values
        today = datetime.now().date()
        max_date = today + timedelta(days=5)
        search_date = st.date_input(
            "Buscar por Fecha",
            min_value=today,
            max_value=max_date,
            value=today,
            help="Seleccione una fecha entre hoy y los próximos 5 días"
        )

    if st.button("Buscar"):
        # Validate search date before proceeding
        is_valid_date, error_message = validate_search_date(search_date)
        if not is_valid_date:
            st.error(error_message)
            return
            
        filtered_df = search_reservations(df, search_name, search_date)
        
        if filtered_df.empty:
            st.warning("No se encontraron reservas con los criterios especificados.")
        else:
            st.subheader(f"Resultados encontrados: {len(filtered_df)}")
            
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
                    payment_col1, payment_col2 = st.columns(2)
                    
                    with payment_col1:
                        quien = st.text_input('Nombre Quien Registra:', key=f"quien_{index}")
                        identifica = st.text_input('Identificación:', key=f"identif_{index}")
                        payment_amount = st.number_input(
                            "Monto del pago",
                            min_value=0.0,
                            value=float(row['PRECIO']),
                            step=1000.0,
                            key=f"amount_{index}"
                        )
                    
                    with payment_col2:
                        if st.button("Registrar Pago", key=f"pay_{index}"):
                            if not quien or not identifica:
                                st.error("Por favor complete todos los campos requeridos")
                                return
                                
                            timestamp = datetime.now().strftime('%Y%m%d%H%M')
                            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                            reference = f"REF-{timestamp}-{random_chars}"
                            
                            st.info(f"""
                            **Información del Pago:**
                            - Referencia: {reference}
                            - Monto: ${payment_amount:,.2f}
                            - Registrado por: {quien}
                            """)
                            
                            if register_payment(sheet, reference, row, payment_amount, quien, identifica):
                                st.success("¡Pago registrado exitosamente!")
                                st.balloons()
                            else:
                                st.error("Error al registrar el pago. Por favor contacta al administrador.")

if __name__ == "__main__":
    main()