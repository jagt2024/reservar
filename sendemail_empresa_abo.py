import smtplib
from email.message import EmailMessage
import streamlit as st
import imghdr
    
def send_email_emp(email, nombre, fecha, hora, servicio, precio, estilista, partes, acciones, hechos, causas, attendees):
   
  destinatarios = ['attendees']
  user = st.secrets['emailsemp']['smtp_user'] 
  password = st.secrets['emailsemp']['smtp_password']
  smtp_server = 'smtp.gmail.com'
  smtp_port = 465
  
  #smtp_username = os.getenv('smtp_username')
  #smtp_password = os.getenv('smtp_password')
    
  msg = EmailMessage()
  msg["Subject"] = "Angenda y/o Reserva de Servicio"
  msg["From"] = user
  msg["To"] = "josegarjagt@gmail.com"
  msg["Cc"] = destinatarios
 
  asunto = f"""Se genero agenda y/o reserva, enviada a Email: {email} del Sr(a) : {nombre},
      Fecha: {fecha},
      Hora: {hora},
      Servicio: {servicio},
      Encargado: {estilista},
      partes : {partes},
      acciones :{acciones}, 
      hechos : {hechos}, 
      causas : {causas}
      Email Abogado Encargado : {attendees}
      
      Atentamente,
      
      El Equipo de Agendamiento
      emil: emresa@xxxx.com
      """
  msg.set_content(asunto)
  
  if user in destinatarios:
        
    with open("assets/barberia.png","rb") as f:
    #with open("C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas/gestion-reservas.xlsx","rb") as f:
      
      file_data = f.read()
      file_type = imghdr.what(f.name)
      file_name = "Image 1" + file_type
      
      msg.add_attachment(file_data, maintype = "image", subtype = file_type, filename = file_name)
      
      ##### Para enviar un archivo de Excel
      #file_name = "Archivo Excel.xlsx"
      #file_type = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
      #msg.add_attachment(file_data, maintype = "aplication", subtype = file_type, filename = file_name) 
  
  elif email not in destinatarios:
    
    with open("assets/barberia.png","rb") as f1:
          
      file_data = f1.read()
      file_type1 = imghdr.what(f1.name)
      file_name1 = "Image 1" + file_type1
    
      msg.add_attachment(file_data, maintype = "image", subtype = file_type1, filename = file_name1) 
    
  with smtplib.SMTP_SSL(smtp_server,smtp_port) as smtp:
   #with smtplib.SMTP_SSL(smtp.office365.com,587) as smtp:
     try:
        smtp.login(user, password)
        smtp.send_message(msg)
        smtp.quit()
        
     except smtplib.SMTPException as e:
   
        st.exception('Error al enviar el email')
        print(e)
        return False
        
  #st.success('Email enviado correctamnte')
