import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import toml
import base64

def load_credentials_from_toml(file_path):
    with open(file_path, 'r') as toml_file:
        config = toml.load(toml_file)
        credentials = config['sheetsemp']['credentials_sheet']
    return credentials
    #config['credentials_sheet']

def get_google_sheet_data(creds):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scope)
    client = gspread.authorize(credentials)

    sheet_url = 'https://docs.google.com/spreadsheets/d/1N_nVB02dmzHTCNkufR2fmuRBY7Lf8FUbhTpqAEWRWF4/edit?gid=0#gid=0'
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet('reservas')
    data = worksheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}">Descargar {file_label}</a>'
    return href

def process_and_display_data(df):
    
    #st.write("Primeros 5 registros de la hoja:")
    #st.dataframe(df.head())

    #st.write("Últimos 5 registros de la hoja:")
    #st.dataframe(df.tail())

    temp_file_path = "./archivos/temp_gestion-reservas-abo.xlsx"
    df.to_excel(temp_file_path, index=False)
    
    #st.markdown(get_binary_file_downloader_html(temp_file_path, 'Excel'), #unsafe_allow_html=True)

    #st.write("Estadísticas básicas:")
    #st.write(df.describe())

    #if 'fecha' in df.columns and 'monto' in df.columns:
    #    st.write("Gráfico de Reservas por Fecha:")
    #    chart_data = df.groupby('fecha')['monto'].sum().reset_index()
    #    st.bar_chart(chart_data.set_index('fecha'))

def download_and_process_data(creds_path):
    try:
        #creds = load_credentials_from_toml('./.streamlit/secrets.toml')
        creds = load_credentials_from_toml(creds_path)
        st.success("Credenciales cargadas correctamente")
    except Exception as e:
        st.error(f"Error al cargar las credenciales: {str(e)}")
        return

    try:
        with st.spinner('Descargando datos...'):
            df = get_google_sheet_data(creds)
        st.success('Datos descargados correctamente! en /archivos/temp_gestion-reservas-abo.xlsx')
        process_and_display_data(df)
 
    except Exception as e:
        st.error(f"Error al procesar los datos: {str(e)}")

# Esta función main() puede ser eliminada si no se va a usar este script directamente
#def main():
#    st.title('Descarga de Google Sheets')
#    if st.button('Descargar Datos'):
#        download_and_process_data('path/to/your/credentials.toml')

#if __name__ == "__main__":
#    main()