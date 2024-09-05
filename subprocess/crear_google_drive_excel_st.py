import streamlit as st
import os
import toml
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def load_config():
    with open('./.sreamlit/secrets.toml', 'r') as f:
        return toml.load(f)

@st.cache_resource
def get_google_auth():
    config = load_config()
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('../token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_config(
                config['google_credentials'],
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob')
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.write("Please visit this URL to authorize the application:")
            st.write(auth_url)
            code = st.text_input("Enter the authorization code:")
            if code:
                flow.fetch_token(code=code)
                creds = flow.credentials
                with open('../token.json', 'w') as token:
                    token.write(creds.to_json())
    return creds

def create_spreadsheet(name):
    creds = get_google_auth()
    service = build('sheets', 'v4', credentials=creds)

    spreadsheet = {
        'properties': {
            'title': name
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                fields='spreadsheetId').execute()
    return spreadsheet.get('spreadsheetId')

def add_sheet(spreadsheet_id, sheet_name):
    creds = get_google_auth()
    service = build('sheets', 'v4', credentials=creds)

    request_body = {
        'requests': [{
            'addSheet': {
                'properties': {
                    'title': sheet_name,
                }
            }
        }]
    }

    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    return response['replies'][0]['addSheet']['properties']['sheetId']

def add_columns(spreadsheet_id, sheet_id, columns):
    creds = get_google_auth()
    service = build('sheets', 'v4', credentials=creds)

    requests = []
    for i, column in enumerate(columns):
        requests.append({
            'updateCells': {
                'rows': [{'values': [{'userEnteredValue': {'stringValue': column}}]}],
                'fields': 'userEnteredValue',
                'start': {'sheetId': sheet_id, 'rowIndex': 0, 'columnIndex': i}
            }
        })

    body = {'requests': requests}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

def format_columns(spreadsheet_id, sheet_id, formats):
    creds = get_google_auth()
    service = build('sheets', 'v4', credentials=creds)

    requests = []
    for i, format_info in enumerate(formats):
        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startColumnIndex': i,
                    'endColumnIndex': i + 1
                },
                'cell': {
                    'userEnteredFormat': format_info
                },
                'fields': 'userEnteredFormat'
            }
        })

    body = {'requests': requests}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

def main():
    st.title("Google Drive Excel Creator")

    # Crear un nuevo archivo de Excel (Spreadsheet)
    spreadsheet_name = st.text_input("Ingrese el nombre del archivo de Excel:")
    if st.button("Crear Spreadsheet"):
        spreadsheet_id = create_spreadsheet(spreadsheet_name)
        st.session_state.spreadsheet_id = spreadsheet_id
        st.success(f"Spreadsheet creado con ID: {spreadsheet_id}")

    if 'spreadsheet_id' in st.session_state:
        # Crear una nueva hoja
        sheet_name = st.text_input("Ingrese el nombre de la nueva hoja:")
        if st.button("Añadir Hoja"):
            sheet_id = add_sheet(st.session_state.spreadsheet_id, sheet_name)
            st.session_state.sheet_id = sheet_id
            st.success(f"Hoja '{sheet_name}' añadida con éxito.")

        if 'sheet_id' in st.session_state:
            # Agregar columnas
            columns = st.text_input("Ingrese los nombres de las columnas separados por coma:").split(',')
            if st.button("Añadir Columnas"):
                add_columns(st.session_state.spreadsheet_id, st.session_state.sheet_id, columns)
                st.success("Columnas añadidas con éxito.")

            # Formatear columnas
            st.subheader("Formato de Columnas")
            formats = []
            for i, column in enumerate(columns):
                with st.expander(f"Formato para '{column}'"):
                    bold = st.checkbox(f"Negrita para '{column}'")
                    italic = st.checkbox(f"Cursiva para '{column}'")
                    align = st.selectbox(f"Alineación para '{column}'", ['LEFT', 'CENTER', 'RIGHT'])
                    
                    format_info = {
                        'textFormat': {'bold': bold, 'italic': italic},
                        'horizontalAlignment': align
                    }
                    formats.append(format_info)

            if st.button("Aplicar Formato"):
                format_columns(st.session_state.spreadsheet_id, st.session_state.sheet_id, formats)
                st.success("Formato aplicado con éxito.")

        if 'spreadsheet_id' in st.session_state:
            st.success(f"Puede acceder al archivo en: https://docs.google.com/spreadsheets/d/{st.session_state.spreadsheet_id}")

if __name__ == '__main__':
    main()