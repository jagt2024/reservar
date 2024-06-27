#import pip-system-certs
#pip install pip_system_certs
import streamlit as st
from streamlit_option_menu import option_menu
from sendemail import send_email2
from send_emails import send_email
from google_sheets import GoogleSheet
from google_calendar import GoogleCalendar
import numpy as np
import datetime as dt
import datetime
import re
import uuid
import pandas as pd

page_title = 'Club de Barberias' 
page_icon= "assets/barberia.png" 
title="barbería iconos"
layout = 'centered'

st.set_page_config(page_title=page_title, page_icon=page_icon,layout=layout)

st.title('***BARBERIA STYLOS MODERNOS***')
st.text(f"""Calle xx con yyyy barrio zzzz en Girardot
            Telefonos : 300x1x2x3""")

selected = option_menu(menu_title=None, options=['Inicio','Reservar','Servicios','Informacion'],
                       icons=['bi bi-app-indicator',
                              'bi bi-calendar2-date', 
                              'bi bi-award','clip',
                              'bi bi-clipboard-minus-fill'],
                       default_index=1,
                       styles= {
                         "container":{ "padding": "5!important", "background-color":'grey'},
                         "icon":{"color":"white","font-size":"23px"},
                         "nav-lik":{"color":"white","font-size":"23px","text-aling":"center"},
                         "nav-lik-selected":{"backgroud-color":"#02ab21"},},
                       orientation='horizontal')

def validate_email(email):
  pattern = re.compile('^[\w\.-]+@[\w\.-]+\.\w+$')
  if re.match(pattern, email):
    return True
  else:
    return False
  
def add_hour_and_half(time):
  parsed_time = dt.datetime.strptime(time, "%H:%M").time()
  new_time = (dt.datetime.combine(dt.date.today(), parsed_time) + dt.timedelta(hours=1, minutes=0)).time()
  return new_time.strftime("%H:%M")

def generate_uid():
  return str(uuid.uuid4())

if selected == 'Inicio':
#!= 'Reservar' or selected != 'Servicios' or selected != 'Informacion':
  #st.write('##')
  st.image('assets/barberia1.webp')
  st.text('Calle xx No. yy-yy Barrio zzzz en Girardot')

elif selected == 'Informacion':
  
    #st.write('##') 
    #st.image('assets/Girardot.png')
    st.subheader('Ubicacion')
    st.markdown('''<iframe src="https://www.google.com/maps/embed?pb=!1m10!1m8!1m3!1d31828.22712981875!2d-74.7930811!3d4.3113089!3m2!1i1024!2i768!4f13.1!5e0!3m2!1ses!2sco!4v1715792084638!5m2!1ses!2sco" width="600" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>''',unsafe_allow_html=True)
    #st.markdown('Pulsa [aqui](https://www.google.com/maps/@4.3113089,-74.7930811,14z?entry=ttu) para ver la direccion')

    st.subheader('Horarios')
    dia, hora = st.columns(2)
       
    dia.text('Lunes')
    hora.text('10:00 am - 08:00 pm')
    dia.text('Martes')
    hora.text('10:00 am - 08:00 pm')
    dia.text('Miercoles')
    hora.text('10:00 am - 08:00 pm')
    dia.text('Jueves')
    hora.text('10:00 am - 08:00 pm')
    dia.text('Viernes')
    hora.text('10:00 am - 08:00 pm')
    dia.text('Sabado')
    hora.text('10:00 am - 06:00 pm')
  
    st.subheader('Contacto')
    st.image('assets/telephone-fill.svg')
    st.text('Cel. 320551091')
  
    st.subheader('Instagram')
    st.markdown('siguenos [aqui](https://www.instagram.com) en instagram')
  
elif selected == 'Servicios':
    #st.write('##') 
    st.image('assets/corte-hombre1.jpg',caption='Servicio de Corte Caballero')
    st.image('assets/cabello-dama1.jpg',caption='Servicio de Corte y Peinado Damas')
    st.image('assets/corte-barba.jpg',caption='Servicio de Corte Barba')
    st.image('assets/afeitar1.jpg',caption='Servicio de Afeitar Caballero')

elif selected == 'Reservar':

    st.subheader('Genera tus Reservas en Linea y Recibiras confirmacion a tu correo')
  
    horas = ['10:00','11:00','12:00','13:00','14:00','15:00','16:00','17:00','18:00','19:00','20:00']
    servicio = ["Corte Hombre","Corte Mujer", "Arreglo Barba", "Afeitar", "Otro Servicio"]
    estilistas = ['Jose Alfaro','Andres Garcia','Mario Vargas','Stella Gomez']
    document='gestion-reservas'
    sheet = 'reservas'
    credentials = st.secrets['sheets']['credentials_sheet']
    time_zone = 'GMT-05:00' # 'South America'
  
    idcalendar = "josegarjagt@gmail.com"
    idcalendar1 = "ba6000578facbb0df71389d7c4b76555afe42838fc641f417d7cc3a91bf86b7f@group.calendar.google.com"
    idcalendar2 = "ebd1ed404fd7c23d10dc5ee277f470bc28942fdd19879aec16a61add832897f2@group.calendar.google.com"
    idcalendar3 = "cba31f328b4ec714869a2becbecd214ddf68c8bf74cc0aac984fc0f9c5ddb36f@group.calendar.google.com"
    idcalendar4 = "ed26cef01eaf4ba394d77252c097fc4da150a2624db87bf96b25f900483201bd@group.calendar.google.com"
    idcalendars = "afe8f37afe5e919952f780062fd693d57680899895c7dbad0878f2dbf8c91be2@group.calendar.google.com"
      
    st.subheader('Reservar')
    
    c1, c2 = st.columns(2)
    nombre = c1.text_input('Tu Nombre*: ', placeholder='Nombre') # label_visibility='hidden')
    email  = c2.text_input('Tu Email*:', placeholder='Email')
    fecha  = c1.date_input('Fecha*: ')
    servicio = c1.selectbox('Servicios', servicio)
    #estilista = c2.selectbox('Estilista',estilistas)
    #hora = c2.selectbox('Hora: ',horas)
    notas = c1.text_area('Nota o Mensaje(Opcional)')
    whatsapp = c2.checkbox('Envio a WhatsApp Si/No')
    
    if fecha:
        if servicio == "Corte Hombre":
            id = idcalendars
        elif servicio == "servicio1":
            id = idcalendar1
        elif servicio == "servicio2":
            id = idcalendar2
        elif servicio == "servicio3":
            id = idcalendar3
        elif servicio == "servicio4":
            id = idcalendar4
            
    estilista = c2.selectbox('Estilista',estilistas)
    #hora = c2.selectbox('Hora: ',horas)
     
    calendar = GoogleCalendar(id) #credentials, idcalendar
      
    if estilista == "Jose Alfaro":
        email_estilista = "josealfaro@gmail.com"
    elif estilista ==  "Andres Garcia":
        email_estilista = "andresgarcia@gmail.com"
    elif estilista ==  "Mario Vargas":
        email_estilista = "mariovargas@gmail.com"
    elif estilista ==  "Stella Gomez":
        email_estilista = "stellagomez@gmail.com"
    else:
        email_estilista = "otroemail@gmail.com"
    
    attendees = [email_estilista, email]
      
    hours_blocked = calendar.list_upcoming_events()
    result_hours = np.setdiff1d(horas, hours_blocked) 
    hora = c2.selectbox('Hora: ',result_hours)

def crear_reserva():

    enviar = st.button('Reservar')

    #Backend
    if enviar:
      with st.spinner('Cargando...'):
        if not nombre or not email or not servicio or not estilista:
          st.warning('Se Require completar los campos con * son obligatorios')
        
        elif not validate_email(email):
          st.warning('El email no es valido')
        
        else:
          
          parsed_time = dt.datetime.strptime(hora, "%H:%M").time()
          hours1 = parsed_time.hour
          minutes1 =  parsed_time.minute
                    
          end_hours = add_hour_and_half(hora)
          
          parsed_time2 = dt.datetime.strptime(end_hours, "%H:%M").time()
          hours2 = parsed_time2.hour
          minutes2 =  parsed_time2.minute

          start_time = dt.datetime(fecha.year, fecha.month, fecha.day, hours1-5,minutes1).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
          
          #.isoformat() + "Z"
          
          end_time = dt.datetime(fecha.year, fecha.month, fecha.day, hours2-5,minutes2).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
          
          #isoformat() +"Z"
          
          uid = generate_uid()
          values = [(nombre,email,str(fecha),hora,servicio,estilista, notas, uid, whatsapp)]
          gs = GoogleSheet(credentials, document, sheet)
          
          range = gs.get_last_row_range()
          gs.write_data(range,values)
                    
          calendar.create_event(servicio+". "+nombre, start_time, end_time, time_zone,attendees=attendees)
          
          #send_email(email, nombre, fecha, hora, servicio, estilista,  notas)
          send_email2(email, nombre, fecha, hora, servicio, estilista,  notas)
          st.success('Su solicitud ha sido reservada de forrma exitosa')
    
def modificar_reserva():

    actualizar = st.button('Actualizar')

    if actualizar:
      with st.spinner('Cargando...'):
        if not nombre or not email or not servicio or not estilista:
          st.warning('Se Require completar los campos con * son obligatorios')
        
        elif not validate_email(email):
          st.warning('El email no es valido')
        
        else:
          parsed_time = dt.datetime.strptime(hora, "%H:%M").time()
          hours1 = parsed_time.hour
          minutes1 =  parsed_time.minute
                    
          end_hours = add_hour_and_half(hora)
          
          parsed_time2 = dt.datetime.strptime(end_hours, "%H:%M").time()
          hours2 = parsed_time2.hour
          minutes2 =  parsed_time2.minute

          start_time = dt.datetime(fecha.year, fecha.month, fecha.day, hours1-5,minutes1).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
          
          #.isoformat() + "Z"
          
          end_time = dt.datetime(fecha.year, fecha.month, fecha.day, hours2-5,minutes2).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
          
          #isoformat() +"Z"
          
          gs = GoogleSheet(credentials, document, sheet)
                   
          last_row = len(gs.sheet.get_all_values()) +1
          #print(f'last_row {last_row}')
          data = gs.sheet.get_values()
          #print(f'data {data}')
          range_start = f"A{last_row}"
          #print(f'range_start {range_start}')
          range_end = f"{chr(ord('A')+len(data[0])-1)}{last_row}"
          #print(f'range_end {range_end}')
          
          for row in data:
            nom = [row[0]]
            serv = [row[4]]
            fech = str(row[2])
            hora2 = str(row[3])
            uid1 = str(row[7])

            if nom != ['DATA']:
              
              if nom == [nombre] and serv == [servicio]:
                
                fech2 = datetime.datetime.strptime(fech,'%Y-%m-%d')
                #print(f'Esto es fech2 {fech2}')
                
                fech1 = int(fech2.strftime("%Y%m%d"))
                
                hora3 = datetime.datetime.strptime(hora2,'%H:%M')
                #print(hora3)
                
                fechahora_ini = int(hora3.strftime('%H%M'))
                 
                parsed_time = dt.datetime.strptime(hora2, "%H:%M").time()
                hours3 = parsed_time.hour
                minutes3 =  parsed_time.minute
                  
                end_hours = add_hour_and_half(hora2)
          
                parsed_time2 = dt.datetime.strptime(end_hours, "%H:%M").time()
                hours4 = parsed_time2.hour
                minutes4 =  parsed_time2.minute
                              
                hoy = dt.datetime.now()
                fechoy = int(hoy.strftime("%Y%m%d"))
                
                horahoy = dt.datetime.now()
                horahoy2 = int(horahoy.strftime("%H%M"))
                #print(f'ESto es fechahora_ini y horahoy2 {fechahora_ini}, {horahoy2}')
                
                if fech1 >= fechoy and fechahora_ini >= horahoy2:
                  
                  print('Igrese por el if')
                  
                  #fecha1 = dt.datetime(fech2.year, fech2.month, fech2.day, hours3-5, minutes3).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

                  #endtime = dt.datetime(fech2.year, fech2.month, fech2.day, hours4-5,minutes4).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                    
                  print(f'Cambio format fecha1 {fech1}, {fechoy},{fechahora_ini}, {horahoy2}')
                  
                  #calendar.update_event(servicio+". "+nombre, start_time, end_time, time_zone,attendees=attendees)
                                    
                  #uid = uid1
                  #values = [(nombre,email,str(fecha),hora,servicio,estilista, notas, uid, whatsapp)]
                  #gs = GoogleSheet(credentials, document, sheet)

                  #range = gs.write_data_by_uid(uid, values)
                                           
                  #send_email(email, nombre, fecha, hora, servicio, estilista,  notas)
                  #send_email2(email, nombre, fecha, hora, servicio, estilista,  notas='Por su solicitud su reserva se reprogramo. Gracias por su atencion.')
          
                  #st.success('Su solicitud ha sido actualizada de forrma exitosa')  
                
                elif fech1 == fechoy and serv == [servicio] and fechahora_ini < horahoy2:
                   #st.warning('Para el Cliente se hallo una Agenda Vencida')
                   print('El Cliente tiene Agenda Vencida')
                   
              else:   #nom == [nombre] and serv == [servicio] and fech1 < fechoy:
                st.warning('El cliente No tiene agenda.')
                print('El cliente No tiene agenda.')
                break

          #else:
          #   st.warning('No se encontro agenda para este cliente'
          # #   print('No se encontro agenda para este cliente')

def eliminar_reserva():
             
    eliminar = st.button('Eliminar')

    if eliminar:
            
       with st.spinner('Cargando...'):
        if not nombre or not email or not servicio or not estilista:
          st.warning('Se Require completar los campos con * son obligatorios')
        
        elif not validate_email(email):
          st.warning('El email no es valido')
        
        gs = GoogleSheet(credentials, document, sheet)
                   
        last_row = len(gs.sheet.get_all_values()) +1
        #print(f'last_row {last_row}')
        data = gs.sheet.get_values()
        #print(f'data {data}')
        range_start = f"A{last_row}"
        #print(f'range_start {range_start}')
        range_end = f"{chr(ord('A')+len(data[0])-1)}{last_row}"
        #print(f'range_end {range_end}')
          
        for row in data:
            nom = [row[0]]
            serv = [row[4]]
            fech = str(row[2])
            hora2 = str(row[3])
            uid1 = str(row[7])

            if nom != ['DATA']:
              
              if nom == [nombre] and serv == [servicio]:

                fech2 = datetime.datetime.strptime(fech,'%Y-%m-%d')
                #print(f'Esto es fech2 {fech2}')
                
                fech1 = int(fech2.strftime("%Y%m%d"))
                
                hora3 = datetime.datetime.strptime(hora2,'%H:%M')
                #print(hora3)
                
                fechahora_ini = int(hora3.strftime('%H%M'))
                 
                parsed_time = dt.datetime.strptime(hora2, "%H:%M").time()
                hours3 = parsed_time.hour
                minutes3 =  parsed_time.minute
                  
                end_hours = add_hour_and_half(hora2)
          
                parsed_time2 = dt.datetime.strptime(end_hours, "%H:%M").time()
                hours4 = parsed_time2.hour
                minutes4 =  parsed_time2.minute
                              
                hoy = dt.datetime.now()
                fechoy = int(hoy.strftime("%Y%m%d"))
                
                horahoy = dt.datetime.now()
                horahoy2 = int(horahoy.strftime("%H%M"))
                #print(f'ESto es fechahora_ini y horahoy2 {fechahora_ini}, {horahoy2}')
                
                if fech1 >= fechoy and fechahora_ini >= horahoy2:

                  calendar.delete_event()
                                    
                  uid = uid1
                  values = [(nombre,email,str(fecha),hora,servicio,estilista, 'Reserva Cancelada', uid, whatsapp)]
                  gs = GoogleSheet(credentials, document, sheet)

                  range = gs.write_data_by_uid(uid,values)
                                           
                  send_email2(email, nombre, fecha, hora, servicio, estilista,  notas='Por su solicitud se cancelo la reserva. Gracias por su atencion.')
