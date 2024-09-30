import toml
import streamlit as st
import pandas as pd
from google_sheets import GoogleSheet
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Ruta del archivo de credenciales
#CREDENTIALS_FILE = 'appreservas-origin.json'
document='gestion-reservas'
sheet = 'reservas'
credentials = st.secrets['sheets']['credentials_sheet']

# Función para obtener los datos de la hoja de cálculo de Google Drive
def get_google_drive_excel_data(spreadsheet_url, toml_file_path):
    try:
        # Cargar las credenciales desde el archivo .toml
        config = toml.load(toml_file_path)
        cred_dict = config['sheets']['credentials_sheet']

        # Crear las credenciales a partir del diccionario
        creds = Credentials.from_service_account_info(cred_dict, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])

        # Extraer el ID de la hoja de cálculo del URL
        spreadsheet_id = spreadsheet_url.split('/d/')[1].split('/')[0]

        # Crear un servicio de Google Sheets
        sheets_service = build('sheets', 'v4', credentials=creds)

        # Obtener los valores de la hoja de cálculo
        result = sheets_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range='A:Z').execute()
        values = result.get('values', [])

        # Convertir los datos a un DataFrame
        if values:
            df = pd.DataFrame(values[1:], columns=values[0])
            return df
        else:
            print("No se encontraron datos en la hoja de cálculo.")
            return None

    except Exception as e:
        print(f"Error al obtener los datos: {str(e)}")
        return None

class ConsultarAgenda:
  
  class Model:
    pageTitle = "***Consulta de Agenda***"
  
  def view(self,model):
    st.title(model.pageTitle)

    toml_file_path = './.streamlit/secrets.toml'
    # Configuración de la aplicación Streamlit
    #st.title("Lector de Excel de Google Drive")

    # URL de la hoja de cálculo de Google Drive
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1hvqq_x2xTFzgBWNI4eqWiLrB68UqK3k_h1IIlMinkAM/edit?hl=es&pli=1&gid=0#gid=0"
    #"https://docs.google.com/spreadsheets/d/1hvqq_x2xTFzgBWNI4eqWiLrB68UqK3k_h1IIlMinkAM/edit?usp=sharing"

    # Obtener los datos de la hoja de cálculo
    data = get_google_drive_excel_data(spreadsheet_url,toml_file_path)

    if data is not None:
        # Mostrar las columnas disponibles
        st.write("Columnas disponibles:")
        columns = data.columns.tolist()
        selected_columns = st.multiselect("Seleccione las columnas:", columns)

        # Input para el número de filas a mostrar
        num_rows = st.number_input("Número de filas a mostrar:", min_value=1, max_value=len(data), value=10)
        
        # Agregar opción de ordenar los datos
        sort_by = st.selectbox("Ordenar por:", [""] + columns)
        sort_ascending = st.checkbox("Orden ascendente")

        # Filtrar y mostrar los datos
        if selected_columns:
            filtered_data = data[selected_columns].head(num_rows)
            
            # Ordenar los datos si se seleccionó una columna
            if sort_by:
                filtered_data = filtered_data.sort_values(by=sort_by, ascending=sort_ascending)

            st.write("Resultados:")
            st.dataframe(filtered_data)

        # Opción para descargar los resultados
        csv = filtered_data.to_csv(index=False)
        st.download_button(
            label="Descargar resultados como CSV",
            data=csv,
            file_name="resultados_consulta.csv",
            mime="text/csv",
        )
