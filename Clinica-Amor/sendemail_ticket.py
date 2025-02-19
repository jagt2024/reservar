import smtplib
from email.message import EmailMessage
import streamlit as st
import imghdr
    
def send_email2(email, nombre, fecha, hora, servicio, id, prioridad, notas):
   
  destinatarios = []
  user = st.secrets['emails']['smtp_user'] 
  password = st.secrets['emails']['smtp_password']
  smtp_server = 'smtp.gmail.com'
  smtp_port = 465
  
  #smtp_username = os.getenv('smtp_username')
  #smtp_password = os.getenv('smtp_password')
    
  msg = EmailMessage()
  msg["Subject"] = "Ticket de Servicio"
  msg["From"] = user
  msg["To"] = email
  msg["Cc"] = destinatarios
  
  #msg.add_alternative("""\
  #<!DOCTYPE html>
  #<html>
  #    <body>
  #          <h2 style="color:SlateGray;">Su reserva se ha realizado con exito!</h2>
  #          <p> Un cordial saludo.</p>
  #    </body>
  #</html>
  # """, subtype = "html" )
  
  asunto = f"""Cordial saludo Sr(a):
      Esperando se encuentre bien, queremos confirmar que su solicitud de ticket se ha realizado con exito asi : 
      
      Fecha: {fecha},
      Hora: {hora},
      Servicio: {servicio},
      Id : {id},
      Prioridad: {prioridad},
      Notas: {notas},
      
      Si requiere una nuevva atencion de Soporte, le agradecemos ir a las opciones del menu en Soporte-PQRS, o por favor comuniquese a la linea: 3XX YYYYYY. Gracias por confiar en nosotros.
      
      Atentamente,
      
      El Equipo de Soporte
      emil: empresa@xxxx.com
      """
  msg.set_content(asunto)
  
  if user in destinatarios:
        
    with open("./assets-amo/logo-clinica.png","rb") as f:
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
    
    with open("./assets-amo/logo-clinica.png","rb") as f1:
          
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
