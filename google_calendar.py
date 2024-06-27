import os.path
import streamlit as st
from requests.exceptions import ReadTimeout
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time 
import numpy as np
import datetime
import datetime as dt
import json

SCOPES =["https://www.googleapis.com/auth/calendar"]

class GoogleCalendar:
  def __init__(self, idcalendar):
    self.service = self._authenticate()
    
    #self.credentials = credentials
    self.idcalendar = idcalendar
    
  def _authenticate(self):
    creds = None
    
    if os.path.exists("token.json"):
      creds = Credentials.from_authorized_user_file("token.json",SCOPES)
          
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
       
      else:
        try:
          
          flow = InstalledAppFlow.from_client_secrets_file("client_secret_app_escritorio_oauth.json",SCOPES)
          creds = flow.run_local_server(port=0)
                    
        except StopIteration as err:
          raise Exception(f'A ocurrido un error en def _authenticate: {err}')
      try:
        
        with open ("token.json", "w") as token:
          token.write(creds.to_json())
          
      except json.decoder.JSONDecodeError:
        print("error alescribir en creds.to_json")
        
    return build("calendar", "v3", credentials=creds) 
  
       
  def list_upcoming_events(self, max_results=5):
         
    now = dt.datetime.utcnow().isoformat() + "Z"
    hoy = dt.datetime.now().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=1)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    print(f'estoy en list_upcoming_events {hoy}, {now}, {tomorrow}')
    
    try:
               
      events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, maxResults=max_results,singleEvents=True,orderBy='startTime').execute()
     
      events = events_result.get('items',[])
      #print(f'estoy en list_upcoming_events  el events es {events}')
    
    except HttpError as err:
       raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')
          
    #except ReadTimeout as err:
    #  time.sleep(0.07)
    #  raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')  
   
    if not events:
       print('No upcoming events found.')
    else:
       start_times = []
    
       for event in events:
         #time.sleep(0.07)
         try:
            
            start = event['start'].get('dateTime',event['start'].get('date'))
            #print(f'Este es el start event', event['summary'])
 
            start_time = start  #event['start']['dateTime']
            parsed_start_time = dt.datetime.fromisoformat(start_time[:-6])
            hours_minutes = parsed_start_time.strftime("%H:%M")
            start_times.append(hours_minutes)
        
         except HttpError as err:
            raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')
            
         #except ReadTimeout as err:
              
         #  raise Exception(f'A ocurrido un error en list_upcoming_events: {err}') 
         #raise ConnectionError(err, request=request)
         #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida ya que el host conectado no ha podido responder', None, 10060, None))
      
         return start_times
    
  def create_event (self, summary, start_time, end_time, timezone, attendees = None):
      event = {
        'summary': summary,
        'start': {
          'dateTime': start_time,
          'timeZone' : timezone,
        },
        'end': {
          'dateTime': end_time,
          'timeZone' : timezone,
        },
      }
    
      if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
                
        try:
          event = self.service.events().insert(calendarId = "primary", body=event).execute()
          #print(event)
        except HttpError as err:
          raise Exception(f'A ocurrido un error en create_event: {err}')
        
        return event
  
  def update_event(self, summary, start_time, end_time, timezone, attendees = None):
    now = dt.datetime.utcnow().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=2)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    
    event = {
        'summary': summary,
        'start': {
          'dateTime': start_time,
          'timeZone' : timezone,
        },
        'end': {
          'dateTime': end_time,
          'timeZone' : timezone,
        },
    }
    
    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
    
    #fecha2 = datetime.datetime.strptime(start_time,'%Y-%m-%dT%H:%M:%S')
    #fechastart = int(fecha2.strftime("%Y%m%d"))
    
    #hoy = dt.datetime.now().isoformat() +"Z"
    #fechoy = int(hoy.strftime("%Y%m%d"))
      
    #fecha3 = datetime.datetime.strptime(str(fechastart),'%Y%m%dT%H%M:%S')

    #fecha3=dt.datetime.strptime(start_time,'%Y-%m-%dT%H:%M:%S').isoformat() +"Z"
    #endtime = dt.datetime.strptime(end_time,'%Y-%m-%dT%H:%M:%S').isoformat() +"Z"
            
    #print(f'Variables enviadas {summary}, {start_time}, {fecha3}, {endtime}') 
        
    try:
        events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, singleEvents=True).execute()
        #print(f'ESTOS SON LOS EVENTOS PROGRAMADOS {events_result}')
      
        events_result.get('items',[])
        #print(f'este es el events_result {events_result}')
        
        #eventid = events_result 
         
        if not events_result:
           #st.warning('No se encontro un evento relacionado para el cliente')
           print('No se encontro un evento relacionado para el cliente')
      
        else:
     
          for clave, element in events_result.items():
            #new_list = ("{0}) --> {1}".format(clave,element)) #, events_result[element[:1]]
            #print(f'new_list {new_list}')
            if clave == 'items':
                                
               new_list1 = dict(zip(clave,element[0].values()))
               #print(f'este es el new_list1 {new_list1}')
               new_list2 = new_list1['e']
               #print(f'new_list2 {new_list2}')
               
               eventid = str(new_list2)
               #print(f'este es el eventid {eventid}')
              
               updated_event = self.service.events().update(calendarId = 'primary', body=event,eventId = eventid).execute()
          
    except HttpError as err:
      raise Exception(f'A ocurrido un error en updated_event: {err}')
       
      #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida       
                    
    return  updated_event
  
  def delete_event(self):
    
    now = dt.datetime.utcnow().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=2)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    try:
      
        events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, singleEvents=True).execute()
        #print(f'ESTOS SON LOS EVENTOS PROGRAMADOS {events_result}')
      
        events_result.get('items',[])
        #print(f'este es el events_result {events_result}')
        
        #eventid = events_result 
         
        if not events_result:
           #st.warning('No se encontro un evento relacionado para el cliente')
           print('No se encontro un evento relacionado para el cliente')
      
        else:
     
          for clave, element in events_result.items():
            #new_list = ("{0}) --> {1}".format(clave,element)) #, events_result[element[:1]]
            #print(f'new_list {new_list}')
            if clave == 'items':
                                
               new_list1 = dict(zip(clave,element[0].values()))
               #print(f'este es el new_list1 {new_list1}')
               new_list2 = new_list1['e']
               #print(f'new_list2 {new_list2}')
               
               eventid = str(new_list2)
               #print(f'este es el eventid {eventid}')
              
               deleted_event = self.service.events().delete(calendarId='primary',eventId = eventid).execute()
               print(f'Regitro de reserva eliminado')
          
    except HttpError as err:
      raise Exception(f'A ocurrido un error en updated_event: {err}')
       
      #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida
      
        
    return deleted_event

#credentials = st.secrets["sheets"]["credentials_sheet"]
#idcalendar = "josegarjagt@gmail.com"
#google = GoogleCalendar(credentials, idcalendar)
#start_date = '2024-05-20T10:00:00+2:00'
#end_date = '2024-05-20T11:00:00+2:00'
#time_zone = 'Colombia/(GMT-05:00)'
#attendes = ''
#idevent = google.create_event("Servicio Stylos Barberia", start_date, end_date, time_zone, attendes)
#print(idevent)
#date = '2024-05-20'
#init_hours = google.get_events_start_time(date)
#print(init_hours)

#calendar = GoogleCalendar("josegarjagt@gmail.com")
#calendar.list_upcoming_events() # para regenerar el token.json
import os.path
import streamlit as st
from requests.exceptions import ReadTimeout
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time 
import numpy as np
import datetime
import datetime as dt
import json

SCOPES =["https://www.googleapis.com/auth/calendar"]

class GoogleCalendar:
  def __init__(self, idcalendar):
    self.service = self._authenticate()
    
    #self.credentials = credentials
    self.idcalendar = idcalendar
    
  def _authenticate(self):
    creds = None
    
    if os.path.exists("token.json"):
      creds = Credentials.from_authorized_user_file("token.json",SCOPES)
          
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
       
      else:
        try:
          
          flow = InstalledAppFlow.from_client_secrets_file("client_secret_app_escritorio_oauth.json",SCOPES)
          creds = flow.run_local_server(port=0)
                    
        except StopIteration as err:
          raise Exception(f'A ocurrido un error en def _authenticate: {err}')
      try:
        
        with open ("token.json", "w") as token:
          token.write(creds.to_json())
          
      except json.decoder.JSONDecodeError:
        print("error alescribir en creds.to_json")
        
    return build("calendar", "v3", credentials=creds) 
  
       
  def list_upcoming_events(self, max_results=5):
         
    now = dt.datetime.utcnow().isoformat() + "Z"
    hoy = dt.datetime.now().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=1)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    print(f'estoy en list_upcoming_events {hoy}, {now}, {tomorrow}')
    
    try:
               
      events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, maxResults=max_results,singleEvents=True,orderBy='startTime').execute()
     
      events = events_result.get('items',[])
      #print(f'estoy en list_upcoming_events  el events es {events}')
    
    except HttpError as err:
       raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')
          
    #except ReadTimeout as err:
    #  time.sleep(0.07)
    #  raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')  
   
    if not events:
       print('No upcoming events found.')
    else:
       start_times = []
    
       for event in events:
         #time.sleep(0.07)
         try:
            
            start = event['start'].get('dateTime',event['start'].get('date'))
            #print(f'Este es el start event', event['summary'])
 
            start_time = start  #event['start']['dateTime']
            parsed_start_time = dt.datetime.fromisoformat(start_time[:-6])
            hours_minutes = parsed_start_time.strftime("%H:%M")
            start_times.append(hours_minutes)
        
         except HttpError as err:
            raise Exception(f'A ocurrido un error en list_upcoming_events: {err}')
            
         #except ReadTimeout as err:
              
         #  raise Exception(f'A ocurrido un error en list_upcoming_events: {err}') 
         #raise ConnectionError(err, request=request)
         #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida ya que el host conectado no ha podido responder', None, 10060, None))
      
         return start_times
    
  def create_event (self, summary, start_time, end_time, timezone, attendees = None):
      event = {
        'summary': summary,
        'start': {
          'dateTime': start_time,
          'timeZone' : timezone,
        },
        'end': {
          'dateTime': end_time,
          'timeZone' : timezone,
        },
      }
    
      if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
                
        try:
          event = self.service.events().insert(calendarId = "primary", body=event).execute()
          #print(event)
        except HttpError as err:
          raise Exception(f'A ocurrido un error en create_event: {err}')
        
        return event
  
  def update_event(self, summary, start_time, end_time, timezone, attendees = None):
    now = dt.datetime.utcnow().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=2)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    
    event = {
        'summary': summary,
        'start': {
          'dateTime': start_time,
          'timeZone' : timezone,
        },
        'end': {
          'dateTime': end_time,
          'timeZone' : timezone,
        },
    }
    
    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
    
    #fecha2 = datetime.datetime.strptime(start_time,'%Y-%m-%dT%H:%M:%S')
    #fechastart = int(fecha2.strftime("%Y%m%d"))
    
    #hoy = dt.datetime.now().isoformat() +"Z"
    #fechoy = int(hoy.strftime("%Y%m%d"))
      
    #fecha3 = datetime.datetime.strptime(str(fechastart),'%Y%m%dT%H%M:%S')

    #fecha3=dt.datetime.strptime(start_time,'%Y-%m-%dT%H:%M:%S').isoformat() +"Z"
    #endtime = dt.datetime.strptime(end_time,'%Y-%m-%dT%H:%M:%S').isoformat() +"Z"
            
    #print(f'Variables enviadas {summary}, {start_time}, {fecha3}, {endtime}') 
        
    try:
        events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, singleEvents=True).execute()
        #print(f'ESTOS SON LOS EVENTOS PROGRAMADOS {events_result}')
      
        events_result.get('items',[])
        #print(f'este es el events_result {events_result}')
        
        #eventid = events_result 
         
        if not events_result:
           #st.warning('No se encontro un evento relacionado para el cliente')
           print('No se encontro un evento relacionado para el cliente')
      
        else:
     
          for clave, element in events_result.items():
            #new_list = ("{0}) --> {1}".format(clave,element)) #, events_result[element[:1]]
            #print(f'new_list {new_list}')
            if clave == 'items':
                                
               new_list1 = dict(zip(clave,element[0].values()))
               #print(f'este es el new_list1 {new_list1}')
               new_list2 = new_list1['e']
               #print(f'new_list2 {new_list2}')
               
               eventid = str(new_list2)
               #print(f'este es el eventid {eventid}')
              
               updated_event = self.service.events().update(calendarId = 'primary', body=event,eventId = eventid).execute()
          
    except HttpError as err:
      raise Exception(f'A ocurrido un error en updated_event: {err}')
       
      #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida       
                    
    return  updated_event
  
  def delete_event(self):
    
    now = dt.datetime.utcnow().isoformat() + "Z"
    tomorrow = (dt.datetime.now() + dt.timedelta(days=2)).replace(hour=23, minute=59,second=0,microsecond=0).isoformat() +"Z"
    try:
      
        events_result = self.service.events().list(calendarId = "primary", timeMin=now, timeMax=tomorrow, singleEvents=True).execute()
        #print(f'ESTOS SON LOS EVENTOS PROGRAMADOS {events_result}')
      
        events_result.get('items',[])
        #print(f'este es el events_result {events_result}')
        
        #eventid = events_result 
         
        if not events_result:
           #st.warning('No se encontro un evento relacionado para el cliente')
           print('No se encontro un evento relacionado para el cliente')
      
        else:
     
          for clave, element in events_result.items():
            #new_list = ("{0}) --> {1}".format(clave,element)) #, events_result[element[:1]]
            #print(f'new_list {new_list}')
            if clave == 'items':
                                
               new_list1 = dict(zip(clave,element[0].values()))
               #print(f'este es el new_list1 {new_list1}')
               new_list2 = new_list1['e']
               #print(f'new_list2 {new_list2}')
               
               eventid = str(new_list2)
               #print(f'este es el eventid {eventid}')
              
               deleted_event = self.service.events().delete(calendarId='primary',eventId = eventid).execute()
               print(f'Regitro de reserva eliminado')
          
    except HttpError as err:
      raise Exception(f'A ocurrido un error en updated_event: {err}')
       
      #requests.exceptions.ConnectionError: ('Connection aborted.', TimeoutError(10060, 'Se produjo un error durante el intento de conexión ya que la parte conectada no respondió adecuadamente tras un periodo de tiempo, o bien se produjo un error en la conexión establecida
      
        
    return deleted_event

#credentials = st.secrets["sheets"]["credentials_sheet"]
#idcalendar = "josegarjagt@gmail.com"
#google = GoogleCalendar(credentials, idcalendar)
#start_date = '2024-05-20T10:00:00+2:00'
#end_date = '2024-05-20T11:00:00+2:00'
#time_zone = 'Colombia/(GMT-05:00)'
#attendes = ''
#idevent = google.create_event("Servicio Stylos Barberia", start_date, end_date, time_zone, attendes)
#print(idevent)
#date = '2024-05-20'
#init_hours = google.get_events_start_time(date)
#print(init_hours)

#calendar = GoogleCalendar("josegarjagt@gmail.com")
#calendar.list_upcoming_events() # para regenerar el token.json
#calendar.create_event("ReservaServicio","2024-05-30T16:00:02:00", "2024-05-30T17:00:02:00","GMT-5:05",["josegarjagt@gmail.com", "josea_garciat@hotmail.com"]