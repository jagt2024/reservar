import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

def send_email(excel_file, sheet_name):
   
  smtp_username = os.getenv("smpt_username") 
  smtp_password = os.getenv("smpt_password") 
      
  smtp_server = 'smtp.gmail.com' #"smtp-mail.outook.com"
  smtp_port = 587
  
  sender_email = os.getenv("sender_email")
  subject= "Propuesta de Automatizacion"
  
  messages="""
     Estimado {Nombre_del_destinatario}
     
     Espero que al recibo de este correo se encuentre muy bien. Mi nombre es Jose Alejandro Garcia, soy desarrollador de aplicaciones, me complace poner mis servicios y productos de automatizacion a sus ordenes, los beneficios que podemos ofrecerle incluyen : 
     1. Automatizar sus procesos manuales de dia a dia, reduciendo por tanto el ahorro de tiempo,     costos y recursos, 
     2. Mantener su informacion segura y organizada en el momento que lo requiera. 
     3. Mejorar la precision y calidad.
     4. Aumento en la productividad y por lo tanto una ventaja competitiva en el mercado.
     Nuestras soluciones automatizadas minimizan los errorres humanos, lo que grantiza mejores resultados. 
           
     Permitame tener la oportunidad de presentarle nuestras soluciones que pueden adaptarse a sus necesidades especificas de su negocio y ayudarle a alcanzar suss objetivos. Quedo disponible en el momento que lo estime conveniente para a cordar una cita. Le agradezco mucho su tiempo y consideracion.
     
     Saludos cordiales,
     
     Jose Alejandro Garcia T.
     Cel. 320 5511091
     email : josegarjagt@gmail.com 
    
  """
  excel_file = os.getenv("excel_file")
  sheet_name  = os.getenv("sheet_name")
  df = pd.read_excel(excel_file,sheet_name=sheet_name)
    
  with smtplib.SMTP(smtp_server,smtp_port) as server:
  
    for index, row in df.iterrows():
      
      name = row['Nombre']
      emailes = row['Email']
      
      if emailes != 'Email not available':
        messages = messages.replace(name,"Nombre_del_destinatario")
        receiver_email = emailes
        
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        
        msg.attach(MIMEText(messages,'plain'))
      
        try:
      
          server.starttls()
          server.login(smtp_username, smtp_password)
          server.sendmail(sender_email, receiver_email, msg.as_string())
          server.quit()
          
          print('Email envido satisfactoriamente')
          
        except smtplib.SMTPException as e:
   
          st.exception('Error al enviar el email')
          print(e)
        return False
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

def send_email(excel_file, sheet_name):
   
  smtp_username = os.getenv("smpt_username") 
  smtp_password = os.getenv("smpt_password") 
      
  smtp_server = 'smtp.gmail.com' #"smtp-mail.outook.com"
  smtp_port = 587
  
  sender_email = os.getenv("sender_email")
  subject= "Propuesta de Automatizacion"
  
  messages="""
     Estimado {Nombre_del_destinatario}
     
     Espero que al recibo de este correo se encuentre muy bien. Mi nombre es Jose Alejandro Garcia, soy desarrollador de aplicaciones, me complace poner mis servicios y productos de automatizacion a sus ordenes, los beneficios que podemos ofrecerle incluyen : 
     1. Automatizar sus procesos manuales de dia a dia, reduciendo por tanto el ahorro de tiempo,     costos y recursos, 
     2. Mantener su informacion segura y organizada en el momento que lo requiera. 
     3. Mejorar la precision y calidad.
     4. Aumento en la productividad y por lo tanto una ventaja competitiva en el mercado.
     Nuestras soluciones automatizadas minimizan los errorres humanos, lo que grantiza mejores resultados. 
           
     Permitame tener la oportunidad de presentarle nuestras soluciones que pueden adaptarse a sus necesidades especificas de su negocio y ayudarle a alcanzar suss objetivos. Quedo disponible en el momento que lo estime conveniente para a cordar una cita. Le agradezco mucho su tiempo y consideracion.
     
     Saludos cordiales,
     
     Jose Alejandro Garcia T.
     Cel. 320 5511091
     email : josegarjagt@gmail.com 
    
  """
  excel_file = os.getenv("excel_file")
  sheet_name  = os.getenv("sheet_name")
  df = pd.read_excel(excel_file,sheet_name=sheet_name)
    
  with smtplib.SMTP(smtp_server,smtp_port) as server:
  
    for index, row in df.iterrows():
      
      name = row['Nombre']
      emailes = row['Email']
      
      if emailes != 'Email not available':
        messages = messages.replace(name,"Nombre_del_destinatario")
        receiver_email = emailes
        
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        
        msg.attach(MIMEText(messages,'plain'))
      
        try:
      
          server.starttls()
          server.login(smtp_username, smtp_password)
          server.sendmail(sender_email, receiver_email, msg.as_string())
          server.quit()
          
          print('Email envido satisfactoriamente')
          
        except smtplib.SMTPException as e:
   
          st.exception('Error al enviar el email')
          print(e)
        return False
