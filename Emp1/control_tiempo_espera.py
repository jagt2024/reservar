#pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.http import HttpRequest
import httplib2

# Aumenta el tiempo de espera a 120 segundos
TIMEOUT = 120

# Crea una subclase de HttpRequest con un tiempo de espera personalizado
class TimeoutHttpRequest(HttpRequest):
    def __init__(self, *args, **kwargs):
        super(TimeoutHttpRequest, self).__init__(*args, **kwargs)
        self.timeout = TIMEOUT

# Función para crear el servicio con tiempo de espera personalizado
def create_service_with_timeout(service_name, version, creds):
    return build(service_name, version, credentials=creds, requestBuilder=TimeoutHttpRequest)

# Carga las credenciales desde token.json
creds = None
if st.secrets["token_json"]:
    creds = Credentials.from_authorized_user_file(st.secrets["token_json"], ['https://www.googleapis.com/auth/spreadsheets.readonly', 'https://www.googleapis.com/auth/calendar.readonly'])

# Si no hay credenciales válidas disponibles, solicita al usuario que se autentique
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = Flow.from_client_secrets_file(
            'path/to/your/client_secret.json',
            ['https://www.googleapis.com/auth/spreadsheets.readonly', 'https://www.googleapis.com/auth/calendar.readonly'])
        creds = flow.run_local_server(port=0)
    # Guarda las credenciales para la próxima ejecución
    with open(st.secrets["token_json"], 'w') as token:
        token.write(creds.to_json())

# Crea los servicios con el tiempo de espera personalizado
sheets_service = create_service_with_timeout('sheets', 'v4', creds)
calendar_service = create_service_with_timeout('calendar', 'v3', creds)

# Usa los servicios para hacer tus llamadas a la API
# Por ejemplo:
sheet = sheets_service.spreadsheets()
result = sheet.values().get(spreadsheetId='your-spreadsheet-id', range='Sheet1!A1:C10').execute()

