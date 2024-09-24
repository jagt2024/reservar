import os
import json
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class GoogleCalendar:
  def __init__(self):
    self.service = self._authenticate()

  def _authenticate(self):
    creds = None
    
    if os.path.exists("token.json"):
        with open("token.json", "r") as token_file:
            token_data = json.load(token_file)
        
        # Convertir la fecha de expiración a un objeto datetime con zona horaria UTC
        expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        
        if current_time > expiry or (expiry - current_time) < timedelta(hours=6):
            # Actualizar la fecha de expiración
            new_expiry = (current_time + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
            token_data['expiry'] = new_expiry
            
            # Guardar el token actualizado
            with open("token.json", "w") as token_file:
                json.dump(token_data, token_file)
        
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file("client_secret_app_escritorio_oauth.json", SCOPES)
                creds = flow.run_local_server(port=0)
            except StopIteration as err:
                raise Exception(f'Ha ocurrido un error en def _authenticate: {err}')
        
        try:
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        except json.decoder.JSONDecodeError:
            print("Error al escribir en creds.to_json")
    
    return build("calendar", "v3", credentials=creds)
  
GoogleCalendar()