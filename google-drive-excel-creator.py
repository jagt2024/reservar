import streamlit as st
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
import json

def load_credentials():
    try:
        with open("token.json", "r") as f:
            
            SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
           
            config = json.load(f)
            creds = Credentials(
                token=config['token'],
                refresh_token=config['refresh_token'],
                token_uri=config['token_uri'],
                client_id=config['client_id'],
                client_secret=config['client_secret'],
                scopes= SCOPES #config['scopes']
            )
            return creds
    except (KeyError, FileNotFoundError) as e:
        st.error(f"Error al cargar las credenciales: {e}")
        return None

def create_excel_file(creds, file_name):
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': file_name,
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        
        file = drive_service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')
    except HttpError as e:
        st.error(f"Error al crear el archivo de Excel: {e}")
        return None

def add_sheet(creds, spreadsheet_id, sheet_name):
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        request_body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }]
        }
        
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()
        
        return response['replies'][0]['addSheet']['properties']['sheetId']
    except HttpError as e:
        st.error(f"Error al añadir la hoja: {e}")
        return None

def create_columns(creds, spreadsheet_id, sheet_name, columns):
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        range_name = f'{sheet_name}!A1:{chr(65 + len(columns) - 1)}1'
        value_input_option = 'USER_ENTERED'
        
        value_range_body = {
            'majorDimension': 'ROWS',
            'values': [columns]
        }
        
        request = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            body=value_range_body
        )
        response = request.execute()
        
        return response
    except HttpError as e:
        st.error(f"Error al crear las columnas: {e}")
        return None

def update_sheet(creds, spreadsheet_id, sheet_name, data):
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        range_name = f'{sheet_name}!A1'
        value_input_option = 'USER_ENTERED'
        
        value_range_body = {
            'majorDimension': 'ROWS',
            'values': data
        }
        
        request = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            body=value_range_body
        )
        response = request.execute()
        
        return response
    except HttpError as e:
        st.error(f"Error al actualizar la hoja: {e}")
        return None

def main():
    st.title("Creador de Excel en Google Drive")
    
    creds = load_credentials()
    
    if not creds or not creds.valid:
        return
    
    file_name = st.text_input("Nombre del archivo Excel:")
    
    if st.button("Crear archivo Excel"):
        try:
            with st.spinner("Creando archivo..."):
                file_id = create_excel_file(creds, file_name)
            if file_id:
                st.success(f"Archivo creado con ID: {file_id}")
                st.session_state.file_id = file_id
        except HttpError as e:
            st.error(f"Error al crear el archivo de Excel: {e}")
    
    if 'file_id' in st.session_state:
        st.subheader("Añadir hoja")
        sheet_name = st.text_input("Nombre de la hoja:")
        if st.button("Añadir hoja"):
            try:
                with st.spinner("Añadiendo hoja..."):
                    sheet_id = add_sheet(creds, st.session_state.file_id, sheet_name)
                if sheet_id:
                    st.success(f"Hoja añadida con ID: {sheet_id}")
            except HttpError as e:
                st.error(f"Error al añadir la hoja: {e}")
        
        st.subheader("Crear columnas")
        column_names = st.text_input("Nombres de las columnas (separados por comas):")
        if st.button("Crear columnas"):
            columns = [col.strip() for col in column_names.split(',')]
            try:
                with st.spinner("Creando columnas..."):
                    response = create_columns(creds, st.session_state.file_id, sheet_name, columns)
                st.success("Columnas creadas correctamente")
            except HttpError as e:
                st.error(f"Error al crear las columnas: {e}")
        
        st.subheader("Añadir datos")
        uploaded_file = st.file_uploader("Cargar archivo CSV", type="csv")
        if uploaded_file is not None:
            data = pd.read_csv(uploaded_file).values.tolist()
            data.insert(0, list(pd.read_csv(uploaded_file).columns))
            if st.button("Añadir datos"):
                try:
                    with st.spinner("Añadiendo datos..."):
                        response = update_sheet(creds, st.session_state.file_id, sheet_name, data)
                    st.success("Datos añadidos correctamente")
                except HttpError as e:
                    st.error(f"Error al actualizar la hoja: {e}")

if __name__ == "__main__":
    main()