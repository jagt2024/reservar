import smtplib
from email.message import EmailMessage
import streamlit as st
import imghdr
    
def send_email2(email, nombre, fecha, hora, servicio, estilista, notas):
   
  destinatarios = []
  user = st.secrets['emails']['smtp_user'] 
  password = st.secrets['emails']['smtp_password']
  smtp_server = 'smtp.gmail.com'
  smtp_port = 465
  
  #smtp_username = os.getenv('smtp_username')
  #smtp_password = os.getenv('smtp_password')
    
  msg = EmailMessage()
  msg["Subject"] = "Reserva de Servicio"
  msg["From"] = user
  msg["To"] = email
  msg["Cc"] = destinatarios
  
  css_style_alternative = """
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #222222;
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 600px;
        margin: 0 auto;
        padding: 20px;
      }
      .header {
        text-align: center;
        margin-bottom: 20px;
      }
      .header img{
        max-width: 200px;
      }
  """
  #msg.add_alternative("""\
  #<!DOCTYPE html>
  #<html>
  #    <body>
  #          <h2 style="color:SlateGray;">Su reserva se ha realizado con exito!</h2>
  #          <p> Un cordial saludo.</p>
  #    </body>
  #</html>
  # """, subtype = "html" )
  
  asunto = f"""Cordial saludo Sr(a) : {nombre},
      Esperando se encuentre bien, queremos confirmar que su reserva se ha realizado con exito en Stilos Modernos asi :
      Fecha: {fecha},
      Hora: {hora},
      Servicio: {servicio},
      Estilista: {estilista},
      Notas: {notas},
      Si necesita cancelar o reprogramar su cita, le agradecemos ponerse en contacto con anticipacion, asi mismo si tiene alguna pregunta o inquietud por favor comuniquese a la linea: 3205511091. Gracias por confiar en nosotros.
      
      Atentamente,
      
      El Equipo de Stilos Modernos
      emil: josegarjagt@gmail.com
      """
  msg.set_content(asunto)
  
  if user in destinatarios:
        
    with open("C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas/assets/barberia.png","rb") as f:
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
    
    with open("C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas/assets/barberia.png","rb") as f1:
          
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
        
  st.success('Email enviado correctamnte')
