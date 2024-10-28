import gspread
import pandas as pd
import streamlit as st
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import backoff
import logging
import google.auth
import time

class GoogleAuthHandler:
    credentials_path='client_secret_emp.json'
    def __init__(self, credentials_path, scopes):
        self.credentials_path = credentials_path
        self.scopes = scopes
        self.session = self._create_retry_session()

    def _create_retry_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=5,  # número total de intentos
            backoff_factor=1,  # factor de espera entre intentos
            status_forcelist=[500, 502, 503, 504, 429],  # códigos HTTP para reintentar
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, 
         google.auth.exceptions.TransportError),
        max_tries=5,
        max_time=300
    )
    def get_credentials(self):
        creds = None
        try:
            if os.path.exists('token_emp.json'):
                creds = Credentials.from_authorized_user_file('token_emp.json', self.scopes)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request(session=self.session))
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                
                with open('token_emp.json', 'w') as token:
                    token.write(creds.to_json())
                    
            return creds
        except Exception as e:
            logging.error(f"Error en la autenticación de Google: {str(e)}")
            raise

class GoogleServicesManager:
    def __init__(self, credentials_path, scopes):
        self.auth_handler = GoogleAuthHandler(credentials_path, scopes)
        
    @backoff.on_exception(
        backoff.expo,
        (HttpError, google.auth.exceptions.TransportError),
        max_tries=5,
        max_time=300
    )
    def get_service(self, service_name, version):
        try:
            creds = self.auth_handler.get_credentials()
            return build(service_name, version, credentials=creds)
        except Exception as e:
            logging.error(f"Error al crear el servicio {service_name}: {str(e)}")
            raise

class GoogleSheet:
  def __init__(self,credentials,document,sheet_name):
    self.service_manager = GoogleServicesManager(
    credentials,
           ['https://www.googleapis.com/auth/spreadsheets']
    )
    self.sheet_name = sheet_name
    
    self.gc = gspread.service_account_from_dict(credentials)

    try:
      self.sh = self.gc.open(document)
    except gspread.exceptions.SpreadsheetNotFound as e:
      st.exception('Error al abrir archivo')
      print(e)
      return None
          
    self.sheet = self.sh.worksheet(sheet_name)
  
  def read_data(self, range): 
    data = self.sheet.get(range)
    return data
  
  def read_data_by_uid(self, uid):
    data = self.sheet.get_all_records()
    df = pd.DataFrame(data)
    print(df)
    filtered_data = df[df['id-usuario'] == uid]
    return filtered_data
  
  def write_data(self, range, values):
    self.sheet.update(range, values)
    
  def write_data_by_uid(self, uid, values):
    cell = self.sheet.find(uid)
    row_index = cell.row
    self.sheet.update(f'A{row_index}:P{row_index}', values)

  def delete_data_by_uid(self, uid, values):
      cell = self.sheet.find(uid)
      row_index = cell.row
      print(f'row index {row_index}')
      self.sheet.delete_rows(f'A{row_index}:P{row_index}', values)
            
  def get_last_row_range(self):
    last_row = len(self.sheet.get_all_values()) +1
    data = self.sheet.get_values()
    range_start = f"A{last_row}"
    range_end = f"{chr(ord('A')+len(data[0])-1)}{last_row}"
    #range_end = f"J{last_row}""
    return f"{range_start}:{range_end}"
  
  def get_all_values(self):
    return self.sheet.get_all_records()
  
  def get_column_values(self, column):
    table = self.get_all_values()
    df = pd.DataFrame(table)
    values = df[column].tolist()
    return values
