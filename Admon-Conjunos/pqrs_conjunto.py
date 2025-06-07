import streamlit as st
import gspread
import json
import toml
import time
import random
from datetime import datetime
from google.oauth2.service_account import Credentials
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema PQRS - Conjunto Residencial",
#    page_icon="📋",
#    layout="wide",
#    initial_sidebar_state="collapsed"
#)

def load_credentials_from_toml():
    """Cargar credenciales desde el archivo secrets.toml"""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except FileNotFoundError:
        st.error("📁 Archivo secrets.toml no encontrado en .streamlit/")
        st.info("Crea el archivo `.streamlit/secrets.toml` con tus credenciales")
        return None, None
    except KeyError as e:
        st.error(f"🔑 Clave faltante en secrets.toml: {str(e)}")
        st.info("Verifica la estructura del archivo secrets.toml")
        return None, None
    except json.JSONDecodeError as e:
        st.error(f"📄 Error al parsear JSON en secrets.toml: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"❌ Error cargando credenciales: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(_creds):
    """Establecer conexión con Google Sheets"""
    try:
        scope = [
            'https://spreadsheets.google.com/feeds', 
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_info(_creds, scopes=scope)
        client = gspread.authorize(credentials)
        
        # Verificar la conexión intentando listar las hojas
        try:
            sheets = client.openall()
            st.success(f"✅ Conexión exitosa y disponible!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
        
        return client
    
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

class EmailSender:
    """Clase para enviar correos electrónicos"""
    
    def __init__(self, smtp_server, port, sender_email, password):
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.password = password
    
    def send_email(self, recipient_email, subject, body_html, body_text=None, attachment=None):
        """Enviar correo electrónico"""
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            # Agregar cuerpo del mensaje
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                msg.attach(text_part)
            
            html_part = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Agregar archivo adjunto si existe
            if attachment:
                attachment_part = MIMEBase('application', 'octet-stream')
                attachment_part.set_payload(attachment.read())
                encoders.encode_base64(attachment_part)
                attachment_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment.name}'
                )
                msg.attach(attachment_part)
            
            # Enviar correo
            server = smtplib.SMTP_SSL(self.smtp_server, self.port)
            server.login(self.sender_email, self.password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error enviando correo: {str(e)}")
            return False

def create_email_template_solicitante(pqrs_data):
    """Crear plantilla de correo para el solicitante"""
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #2E86AB; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 20px; }}
            .footer {{ background-color: #333; color: white; padding: 15px; text-align: center; }}
            .highlight {{ background-color: #FFF3CD; padding: 10px; border-left: 4px solid #FFE066; }}
            .info-box {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 Confirmación de PQRS</h1>
                <h2>Conjunto Residencial</h2>
            </div>
            
            <div class="content">
                <h3>Estimado/a {pqrs_data['nombre']},</h3>
                
                <p>Su solicitud ha sido recibida exitosamente y se encuentra en proceso de revisión.</p>
                
                <div class="highlight">
                    <strong>Número de Radicado: {pqrs_data['numero_radicado']}</strong><br>
                    <em>Conserve este número para hacer seguimiento a su solicitud</em>
                </div>
                
                <div class="info-box">
                    <h4>📋 Detalles de su solicitud:</h4>
                    <ul>
                        <li><strong>Fecha de registro:</strong> {pqrs_data['fecha_registro']}</li>
                        <li><strong>Tipo de solicitud:</strong> {pqrs_data['tipo_solicitud']}</li>
                        <li><strong>Apartamento:</strong> {pqrs_data['apartamento']}</li>
                        <li><strong>Asunto:</strong> {pqrs_data['asunto']}</li>
                        <li><strong>Descripción:</strong> {pqrs_data['descripcion']}</li>
                    </ul>
                </div>
                
                <div class="info-box">
                    <h4>⏰ Tiempo de respuesta:</h4>
                    <p>Su solicitud será procesada en un plazo máximo de <strong>15 días hábiles</strong>.</p>
                </div>
                
                <div class="info-box">
                    <h4>📞 Información de contacto:</h4>
                    <ul>
                        <li><strong>Horario de atención:</strong> Lunes a Viernes 8:00 AM - 5:00 PM</li>
                        <li><strong>Teléfono:</strong> (601) 123-4567</li>
                        <li><strong>Email:</strong> laceibacondominio@gmail.com</li>
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p>Este es un mensaje automático, por favor no responda a este correo.</p>
                <p>© 2025 Condominio La Ceiba - Sistema PQRS</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    CONFIRMACIÓN DE PQRS - CONJUNTO RESIDENCIAL
    
    Estimado/a {pqrs_data['nombre']},
    
    Su solicitud ha sido recibida exitosamente.
    
    NÚMERO DE RADICADO: {pqrs_data['numero_radicado']}
    (Conserve este número para hacer seguimiento)
    
    DETALLES DE SU SOLICITUD:
    - Fecha de registro: {pqrs_data['fecha_registro']}
    - Tipo: {pqrs_data['tipo_solicitud']}
    - Apartamento: {pqrs_data['apartamento']}
    - Asunto: {pqrs_data['asunto']}
    - Descripción: {pqrs_data['descripcion']}
    
    TIEMPO DE RESPUESTA: Máximo 15 días hábiles
    
    CONTACTO:
    - Horario: Lunes a Viernes 8:00 AM - 5:00 PM
    - Teléfono: (601) 123-4567
    - Email: laceibacondominio@gmail.com
    
    Este es un mensaje automático.
    © 2025 Condominio La Ceeiba - Sistema PQRS
    """
    
    return html_body, text_body

def create_email_template_soporte(pqrs_data):
    """Crear plantilla de correo para el área de soporte"""
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #DC3545; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 20px; }}
            .urgent {{ background-color: #F8D7DA; padding: 15px; border: 1px solid #F5C6CB; border-radius: 5px; }}
            .info-box {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007BFF; }}
            .footer {{ background-color: #333; color: white; padding: 15px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚨 Nueva PQRS Recibida</h1>
                <h2>Sistema de Gestión - Conjunto Residencial</h2>
            </div>
            
            <div class="content">
                <div class="urgent">
                    <h3>⚠️ NUEVA SOLICITUD REQUIERE ATENCIÓN</h3>
                    <p><strong>Número de Radicado:</strong> {pqrs_data['numero_radicado']}</p>
                    <p><strong>Tipo:</strong> {pqrs_data['tipo_solicitud']}</p>
                    <p><strong>Fecha de registro:</strong> {pqrs_data['fecha_registro']}</p>
                </div>
                
                <div class="info-box">
                    <h4>👤 Datos del solicitante:</h4>
                    <ul>
                        <li><strong>Nombre:</strong> {pqrs_data['nombre']}</li>
                        <li><strong>Apartamento:</strong> {pqrs_data['apartamento']}</li>
                        <li><strong>Teléfono:</strong> {pqrs_data['telefono']}</li>
                        <li><strong>Email:</strong> {pqrs_data['email'] if pqrs_data['email'] else 'No proporcionado'}</li>
                    </ul>
                </div>
                
                <div class="info-box">
                    <h4>📋 Detalles de la solicitud:</h4>
                    <p><strong>Asunto:</strong> {pqrs_data['asunto']}</p>
                    <p><strong>Descripción:</strong></p>
                    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 3px; margin: 10px 0;">
                        {pqrs_data['descripcion']}
                    </div>
                    <p><strong>Archivo adjunto:</strong> {pqrs_data['archivo_nombre'] if pqrs_data['archivo_nombre'] else 'No se adjuntó archivo'}</p>
                </div>
                
                <div class="info-box">
                    <h4>⏰ Recordatorio importante:</h4>
                    <p>Esta solicitud debe ser respondida en un plazo máximo de <strong>15 días hábiles</strong>.</p>
                    <p><strong>Fecha límite de respuesta:</strong> {(datetime.now() + pd.Timedelta(days=15)).strftime('%Y-%m-%d')}</p>
                </div>
                
                <div class="info-box">
                    <h4>📊 Acciones requeridas:</h4>
                    <ol>
                        <li>Revisar y analizar la solicitud</li>
                        <li>Asignar responsable si es necesario</li>
                        <li>Investigar y resolver la solicitud</li>
                        <li>Responder al solicitante dentro del plazo establecido</li>
                        <li>Actualizar el estado en Google Sheets</li>
                    </ol>
                </div>
            </div>
            
            <div class="footer">
                <p>Sistema Automático de Notificaciones PQRS</p>
                <p>Conjunto Residencial - Área de Administración</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    NUEVA PQRS RECIBIDA - SISTEMA DE GESTIÓN
    
    INFORMACIÓN URGENTE:
    Número de Radicado: {pqrs_data['numero_radicado']}
    Tipo: {pqrs_data['tipo_solicitud']}
    Fecha: {pqrs_data['fecha_registro']}
    
    DATOS DEL SOLICITANTE:
    - Nombre: {pqrs_data['nombre']}
    - Apartamento: {pqrs_data['apartamento']}
    - Teléfono: {pqrs_data['telefono']}
    - Email: {pqrs_data['email'] if pqrs_data['email'] else 'No proporcionado'}
    
    DETALLES:
    - Asunto: {pqrs_data['asunto']}
    - Descripción: {pqrs_data['descripcion']}
    - Archivo: {pqrs_data['archivo_nombre'] if pqrs_data['archivo_nombre'] else 'Sin archivo'}
    
    PLAZO DE RESPUESTA: 15 días hábiles
    Fecha límite: {(datetime.now() + pd.Timedelta(days=15)).strftime('%Y-%m-%d')}
    
    ACCIONES REQUERIDAS:
    1. Revisar y analizar la solicitud
    2. Asignar responsable si es necesario
    3. Investigar y resolver
    4. Responder al solicitante
    5. Actualizar estado en Google Sheets
    
    Sistema Automático PQRS - Conjunto Residencial
    """
    
    return html_body, text_body

def create_email_template_respuesta(pqrs_data, respuesta_data):
    """Crear plantilla de correo de respuesta al solicitante"""
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #28A745; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 20px; }}
            .footer {{ background-color: #333; color: white; padding: 15px; text-align: center; }}
            .highlight {{ background-color: #D4EDDA; padding: 15px; border-left: 4px solid #28A745; }}
            .info-box {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .respuesta-box {{ background-color: #F8F9FA; padding: 20px; border-radius: 8px; border: 2px solid #28A745; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Respuesta a su PQRS</h1>
                <h2>Condminio La Ceiba</h2>
            </div>
            
            <div class="content">
                <h3>Estimado/a {pqrs_data['Nombre_Completo']},</h3>
                
                <p>Nos complace informarle que hemos procesado su solicitud y le proporcionamos la siguiente respuesta oficial.</p>
                
                <div class="highlight">
                    <strong>Número de Radicado: {pqrs_data['Numero_Radicado']}</strong><br>
                    <strong>Estado: {respuesta_data['nuevo_estado']}</strong><br>
                    <strong>Fecha de respuesta: {respuesta_data['fecha_respuesta']}</strong>
                </div>
                
                <div class="info-box">
                    <h4>📋 Recordatorio de su solicitud:</h4>
                    <ul>
                        <li><strong>Tipo:</strong> {pqrs_data['Tipo_Solicitud']}</li>
                        <li><strong>Asunto:</strong> {pqrs_data['Asunto']}</li>
                        <li><strong>Fecha de registro:</strong> {pqrs_data['Fecha_Registro']}</li>
                    </ul>
                </div>
                
                <div class="respuesta-box">
                    <h4>📝 RESPUESTA OFICIAL:</h4>
                    <p>{respuesta_data['respuesta_detallada']}</p>
                    
                    {f"<p><strong>Observaciones adicionales:</strong><br>{respuesta_data['observaciones']}</p>" if respuesta_data.get('observaciones') else ""}
                </div>
                
                <div class="info-box">
                    <h4>📞 ¿Necesita más información?</h4>
                    <p>Si requiere aclaraciones adicionales sobre esta respuesta, puede contactarnos:</p>
                    <ul>
                        <li><strong>Horario de atención:</strong> Lunes a Viernes 8:00 AM - 5:00 PM</li>
                        <li><strong>Teléfono:</strong> (601) 123-4567</li>
                        <li><strong>Email:</strong> administracion@condominioceiba.com</li>
                    </ul>
                </div>
                
                <p><strong>Agradecemos su confianza y esperamos haber resuelto satisfactoriamente su solicitud.</strong></p>
            </div>
            
            <div class="footer">
                <p>Cordialmente,<br>Área de Administración<br>Conjunto Residencial</p>
                <p>© 2025 Sistema PQRS</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    RESPUESTA OFICIAL A SU PQRS - CONJUNTO RESIDENCIAL
    
    Estimado/a {pqrs_data['Nombre_Completo']},
    
    Le informamos que hemos procesado su solicitud:
    
    DATOS DE SEGUIMIENTO:
    - Número de Radicado: {pqrs_data['Numero_Radicado']}
    - Estado: {respuesta_data['nuevo_estado']}
    - Fecha de respuesta: {respuesta_data['fecha_respuesta']}
    
    RECORDATORIO DE SU SOLICITUD:
    - Tipo: {pqrs_data['Tipo_Solicitud']}
    - Asunto: {pqrs_data['Asunto']}
    - Fecha de registro: {pqrs_data['Fecha_Registro']}
    
    RESPUESTA OFICIAL:
    {respuesta_data['respuesta_detallada']}
    
    {f"OBSERVACIONES ADICIONALES: {respuesta_data['observaciones']}" if respuesta_data.get('observaciones') else ""}
    
    INFORMACIÓN DE CONTACTO:
    - Horario: Lunes a Viernes 8:00 AM - 5:00 PM
    - Teléfono: (601) 123-4567
    - Email: laceibacondominio@gmail.com
    
    Agradecemos su confianza.
    
    Cordialmente,
    Área de Administración Conjunto Residencial
    Condominio La Ceiba
    © 2025 Sistema PQRS
    """
    
    return html_body, text_body

def save_pqrs_to_sheet(client, pqrs_data):
    """Guardar PQRS en Google Sheets"""
    try:
        # Abrir el archivo "gestion-conjunto"
        spreadsheet = client.open("gestion-conjuntos")
        
        # Seleccionar o crear la hoja "pqrs"
        try:
            worksheet = spreadsheet.worksheet("pqrs")
        except gspread.WorksheetNotFound:
            # Si no existe la hoja, crearla con encabezados
            worksheet = spreadsheet.add_worksheet(title="pqrs", rows=1000, cols=13)
            headers = [
                "Fecha_Registro", "Numero_Radicado", "Tipo_Solicitud", 
                "Nombre_Completo", "Apartamento", "Telefono", "Email",
                "Asunto", "Descripcion", "Estado", "Archivo_Adjunto", 
                "Fecha_Respuesta", "Respuesta_Detallada"
            ]
            worksheet.append_row(headers)
        
        # Preparar los datos para insertar
        row_data = [
            pqrs_data["fecha_registro"],
            pqrs_data["numero_radicado"],
            pqrs_data["tipo_solicitud"],
            pqrs_data["nombre"],
            pqrs_data["apartamento"],
            pqrs_data["telefono"],
            pqrs_data["email"],
            pqrs_data["asunto"],
            pqrs_data["descripcion"],
            "Pendiente",  # Estado inicial
            pqrs_data["archivo_nombre"] if pqrs_data["archivo_nombre"] else "Sin archivo",
            "",  # Fecha de respuesta vacía
            ""   # Respuesta detallada vacía
        ]
        
        # Insertar la fila
        worksheet.append_row(row_data)
        return True
        
    except Exception as e:
        st.error(f"❌ Error al guardar en Google Sheets: {str(e)}")
        return False

def pqrs_main():
    st.title("📋 Sistema PQRS")
    st.subheader("Peticiones, Quejas, Reclamos y Sugerencias")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets")
        st.stop()
    
    # CSS para cambiar el color de fondo del sidebar
    st.markdown("""
    <style>
        .css-1d391kg {
            background-color: #f0f2f6;
        }
    </style>
    """, unsafe_allow_html=True)
    # Crear sidebar para navegación
    st.sidebar.title("🏢 Condominio Ceiba")
    
    # Opciones de navegación
    pagina = st.sidebar.selectbox(
        "Seleccionar Sección:",
        ["🏠 Portal Residentes", "🛠️ Panel Soporte", "📊 Consultar PQRS"]
    )
    
    # Línea divisoria
    st.sidebar.markdown("---")
    
    # Mostrar información de contacto en sidebar
    st.sidebar.info("""
    **📞 Contacto:**
    - Tel: (601) 123-4567
    - Email: admin@condominioceiba.com
    - Horario: Lunes a Viernes
    - 8:00 AM - 5:00 PM
    """)
    
    # Navegar según la selección
    if pagina == "🏠 Portal Residentes":
        mostrar_portal_residentes(client, config)
    elif pagina == "🛠️ Panel Soporte":
        mostrar_panel_soporte(client, config)
    elif pagina == "📊 Consultar PQRS":
        mostrar_consulta_pqrs(client)


def mostrar_portal_residentes(client, config):
    st.write("### Sistema de Peticiones, Quejas, Reclamos y Sugerencias")
    
    with st.form("form_pqrs"):
        # Tipo de solicitud
        tipo_solicitud = st.selectbox(
            "Tipo de Solicitud *",
            ["Petición", "Queja", "Reclamo", "Sugerencia", "Felicitación"]
        )
        
        # Datos personales
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre Completo *")
            apartamento_pqrs = st.text_input("Número de Apartamento *")
            
        with col2:
            telefono = st.text_input("Teléfono de Contacto *")
            email = st.text_input("Correo Electrónico")
        
        # Detalles de la solicitud
        asunto = st.text_input("Asunto *")
        descripcion = st.text_area("Descripción detallada *", height=150)
        
        # Archivo adjunto
        archivo = st.file_uploader(
            "Adjuntar archivo (opcional)", 
            type=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'],
            help="Formatos permitidos: PDF, imágenes, documentos de Word"
        )
        
        # Autorización
        autorizacion = st.checkbox(
            "Autorizo el tratamiento de mis datos personales conforme a la Ley 1581 de 2012 *"
        )
        
        # Botones
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            submitted = st.form_submit_button("📤 Enviar PQRS", type="primary")
            
        with col_btn2:
            cleared = st.form_submit_button("🔄 Limpiar Formulario")
        
        # Procesar envío
        if submitted:
            if nombre and apartamento_pqrs and telefono and asunto and descripcion and autorizacion:
                # Generar número de radicado
                numero_radicado = f"PQRS-{random.randint(100000, 999999)}"
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Preparar datos para guardar
                pqrs_data = {
                    "fecha_registro": fecha_actual,
                    "numero_radicado": numero_radicado,
                    "tipo_solicitud": tipo_solicitud,
                    "nombre": nombre,
                    "apartamento": apartamento_pqrs,
                    "telefono": telefono,
                    "email": email,
                    "asunto": asunto,
                    "descripcion": descripcion,
                    "archivo_nombre": archivo.name if archivo else None
                }
                
                # Guardar en Google Sheets
                if save_pqrs_to_sheet(client, pqrs_data):
                    # Configurar envío de correos
                    try:
                        email_sender = EmailSender(
                            smtp_server="smtp.gmail.com",
                            port=465,
                            sender_email=st.secrets['emails']['smtp_user'],
                            password=st.secrets['emailsemp']['smtp_password']
                        )
                        
                        emails_sent = 0
                        
                        # Enviar correo al solicitante (si proporcionó email)
                        if email:
                            html_body_solicitante, text_body_solicitante = create_email_template_solicitante(pqrs_data)
                            if email_sender.send_email(
                                recipient_email=email,
                                subject=f"Confirmación PQRS - Radicado {numero_radicado}",
                                body_html=html_body_solicitante,
                                body_text=text_body_solicitante,
                                attachment=archivo
                            ):
                                emails_sent += 1
                        
                        # Enviar correo al área de soporte
                        html_body_soporte, text_body_soporte = create_email_template_soporte(pqrs_data)
                        if email_sender.send_email(
                            recipient_email="josegarjagt@gmail.com",
                            subject=f"🚨 Nueva PQRS - {tipo_solicitud} - Radicado {numero_radicado}",
                            body_html=html_body_soporte,
                            body_text=text_body_soporte,
                            attachment=archivo
                        ):
                            emails_sent += 1
                        
                        # Mostrar mensaje de éxito
                        st.success(f"""
                        ✅ **PQRS Enviada Exitosamente**
                        
                        **Número de Radicado:** {numero_radicado}
                        
                        Su solicitud ha sido recibida y será procesada en un plazo máximo de 15 días hábiles.
                        
                        **Datos de su solicitud:**
                        - **Tipo:** {tipo_solicitud}
                        - **Solicitante:** {nombre}
                        - **Apartamento:** {apartamento_pqrs}
                        - **Asunto:** {asunto}
                        
                        **📧 Notificaciones enviadas:**
                        - ✅ Área de soporte notificada
                        {f"- ✅ Confirmación enviada a {email}" if email and emails_sent >= 1 else "- ⚠️ No se envió confirmación (email no proporcionado)"}
                        
                        *Conserve el número de radicado para hacer seguimiento.*
                        """)
                        
                        # Mostrar información del archivo si se adjuntó
                        if archivo:
                            st.info(f"📎 Archivo adjunto registrado: {archivo.name}")
                            
                    except Exception as e:
                        st.warning(f"""
                        ✅ **PQRS Guardada Exitosamente**
                        
                        **Número de Radicado:** {numero_radicado}
                        
                        ⚠️ **Nota:** La PQRS se guardó correctamente, pero hubo un problema con el envío de correos:
                        {str(e)}
                        
                        Por favor contacte al área de administración para confirmar el registro.
                        """)
                        
                else:
                    st.error("❌ Error al guardar la PQRS. Por favor intente nuevamente.")
                    
            else:
                st.error("❌ Por favor complete todos los campos obligatorios (*) y acepte el tratamiento de datos.")
        
        if cleared:
            st.rerun()
    
    # Información adicional
    st.write("---")
    st.info("""
    **ℹ️ Información Importante:**
    
    - **Tiempo de respuesta:** Máximo 15 días hábiles
    - **Horario de atención:** Lunes a Viernes 8:00 AM - 5:00 PM
    - **Contacto directo:** Administración - Tel: (601) 123-4567
    - **Email:** administracion@condominioceiba.com
    
    *Sus datos personales serán tratados conforme a nuestra política de privacidad.*
    """)
    
   # Sección de consulta de PQRS (opcional)
    st.write("---")
    st.write("### 🔍 Consultar Estado de PQRS")
    
    with st.expander("Consultar por número de radicado"):
        numero_consulta = st.text_input("Ingrese el número de radicado:")
        if st.button("Consultar"):
            if numero_consulta:
                try:
                    spreadsheet = client.open("gestion-conjuntos")
                    worksheet = spreadsheet.worksheet("pqrs")
                    
                    # Obtener todos los valores como matriz
                    all_values = worksheet.get_all_values()
                    
                    if len(all_values) < 2:
                        st.warning("⚠️ No hay registros de PQRS en la base de datos.")
                        return
                    
                    # La primera fila son los encabezados
                    headers = all_values[0]
                    
                    # Buscar el registro
                    pqrs_encontrada = None
                    for row in all_values[1:]:  # Saltar la fila de encabezados
                        if len(row) > 0 and row[1] == numero_consulta:  # Columna 1 = Numero_Radicado
                            # Crear diccionario con los datos
                            pqrs_encontrada = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    pqrs_encontrada[header] = row[i]
                                else:
                                    pqrs_encontrada[header] = ""
                            break
                    
                    if pqrs_encontrada:
                        st.success("✅ PQRS encontrada:")
                        
                        # Mostrar información de forma más robusta
                        campos_mostrar = [
                            ("Número de Radicado", "Numero_Radicado"),
                            ("Fecha de Registro", "Fecha_Registro"),
                            ("Tipo de Solicitud", "Tipo_Solicitud"),
                            ("Nombre Completo", "Nombre_Completo"),
                            ("Apartamento", "Apartamento"),
                            ("Teléfono", "Telefono"),
                            ("Email", "Email"),
                            ("Asunto", "Asunto"),
                            ("Estado", "Estado"),
                            ("Fecha de Respuesta", "Fecha_Respuesta")
                        ]
                        
                        # Crear dos columnas para mostrar la información
                        col1, col2 = st.columns(2)
                        
                        for i, (etiqueta, campo) in enumerate(campos_mostrar):
                            valor = pqrs_encontrada.get(campo, "No disponible")
                            if valor and valor.strip():  # Solo mostrar si tiene valor
                                if i % 2 == 0:
                                    with col1:
                                        st.write(f"**{etiqueta}:** {valor}")
                                else:
                                    with col2:
                                        st.write(f"**{etiqueta}:** {valor}")
                        
                        # Mostrar descripción en una sección aparte por ser más larga
                        descripcion = pqrs_encontrada.get("Descripcion", "")
                        if descripcion and descripcion.strip():
                            st.write("---")
                            st.write("**Descripción:**")
                            st.text_area("", value=descripcion, height=100, disabled=True, key="desc_consulta")
                        
                        # Mostrar archivo adjunto si existe
                        archivo_adj = pqrs_encontrada.get("Archivo_Adjunto", "")
                        if archivo_adj and archivo_adj.strip() and archivo_adj != "Sin archivo":
                            st.write(f"**📎 Archivo Adjunto:** {archivo_adj}")
                            
                    else:
                        st.warning("⚠️ No se encontró ninguna PQRS con ese número de radicado.")
                        st.info("Verifique que el número esté escrito correctamente (ejemplo: PQRS-123456)")
                        
                except gspread.exceptions.WorksheetNotFound:
                    st.error("❌ No se encontró la hoja 'pqrs' en el archivo 'gestion-conjunto'.")
                    st.info("Asegúrese de que existe al menos una PQRS registrada para crear la hoja.")
                except gspread.exceptions.SpreadsheetNotFound:
                    st.error("❌ No se encontró el archivo 'gestion-conjunto' en Google Sheets.")
                    st.info("Verifique que el archivo existe y tiene los permisos correctos.")
                except Exception as e:
                    st.error(f"❌ Error al consultar: {str(e)}")
                    st.info("Detalles del error para diagnóstico técnico:")
                    st.code(str(type(e).__name__) + ": " + str(e))
                    
                    # Información de depuración
                    with st.expander("🔧 Información de depuración"):
                        try:
                            spreadsheet = client.open("gestion-conjunto")
                            worksheets = [ws.title for ws in spreadsheet.worksheets()]
                            st.write("Hojas disponibles:", worksheets)
                            
                            if "pqrs" in worksheets:
                                worksheet = spreadsheet.worksheet("pqrs")
                                st.write("Número de filas con datos:", len(worksheet.get_all_values()))
                                st.write("Encabezados:", worksheet.row_values(1))
                        except:
                            st.write("No se pudo obtener información de depuración")
            else:
                st.warning("Por favor ingrese un número de radicado.")

def mostrar_panel_soporte(client, config):
    """Mostrar el panel de soporte con autenticación"""
    # Verificar si ya está autenticado
    if not st.session_state.get('soporte_authenticated', False):
        st.subheader("🔐 Acceso Panel de Soporte")
        
        with st.form("login_form"):
            st.write("Ingrese las credenciales para acceder al panel de gestión:")
            
            usuario = st.text_input("Usuario:", placeholder="usuario")
            password = st.text_input("Contraseña:", type="password", placeholder="contraseña")
            
            login_button = st.form_submit_button("🔓 Iniciar Sesión", type="primary")
            
            if login_button:
                # Verificar credenciales (puedes cambiar estas credenciales)
                if usuario == "soporte" and password == "soporte1234":
                    st.session_state.soporte_authenticated = True
                    st.session_state.soporte_user = usuario
                    st.success("✅ Acceso concedido. Redirigiendo al panel...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")
        
        # Información sobre el panel
        st.info("""
        **ℹ️ Panel de Gestión de Soporte**
        
        Este panel permite:
        - 📋 Ver PQRS pendientes
        - ✅ Responder PQRS
        - 📊 Ver estadísticas del sistema
        
        *Contacte al administrador para obtener credenciales de acceso.*
        """)
    
    else:
        # Mostrar panel de soporte
        soporte_panel(client, config)

def mostrar_consulta_pqrs(client):
    """Mostrar sección de consulta de PQRS"""
    st.write("### 🔍 Consultar Estado de PQRS")
    st.write("Ingrese su número de radicado para consultar el estado de su solicitud.")
    
    with st.form("consulta_form"):
        numero_consulta = st.text_input(
            "Número de radicado:",
            placeholder="Ej: PQRS-123456",
            help="Ingrese el número de radicado que recibió al enviar su PQRS"
        )
        
        consultar_btn = st.form_submit_button("🔍 Consultar Estado", type="primary")
        
        if consultar_btn:
            if numero_consulta:
                try:
                    spreadsheet = client.open("gestion-conjuntos")
                    worksheet = spreadsheet.worksheet("pqrs")
                    
                    # Obtener todos los valores como matriz
                    all_values = worksheet.get_all_values()
                    
                    if len(all_values) < 2:
                        st.warning("⚠️ No hay registros de PQRS en la base de datos.")
                        return
                    
                    # La primera fila son los encabezados
                    headers = all_values[0]
                    
                    # Buscar el registro
                    pqrs_encontrada = None
                    for row in all_values[1:]:  # Saltar la fila de encabezados
                        if len(row) > 0 and row[1] == numero_consulta:  # Columna 1 = Numero_Radicado
                            # Crear diccionario con los datos
                            pqrs_encontrada = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    pqrs_encontrada[header] = row[i]
                                else:
                                    pqrs_encontrada[header] = ""
                            break
                    
                    if pqrs_encontrada:
                        # Determinar el estado y color
                        estado = pqrs_encontrada.get("Estado", "Pendiente")
                        if estado == "Respondida":
                            st.success("✅ PQRS encontrada - Estado: Respondida")
                        elif estado == "En Proceso":
                            st.info("🔄 PQRS encontrada - Estado: En Proceso")
                        else:
                            st.warning("⏳ PQRS encontrada - Estado: Pendiente")
                        
                        # Mostrar información de forma más robusta
                        campos_mostrar = [
                            ("Número de Radicado", "Numero_Radicado"),
                            ("Fecha de Registro", "Fecha_Registro"),
                            ("Tipo de Solicitud", "Tipo_Solicitud"),
                            ("Nombre Completo", "Nombre_Completo"),
                            ("Apartamento", "Apartamento"),
                            ("Teléfono", "Telefono"),
                            ("Email", "Email"),
                            ("Asunto", "Asunto"),
                            ("Estado", "Estado"),
                            ("Fecha de Respuesta", "Fecha_Respuesta")
                        ]
                        
                        # Crear dos columnas para mostrar la información
                        col1, col2 = st.columns(2)
                        
                        for i, (etiqueta, campo) in enumerate(campos_mostrar):
                            valor = pqrs_encontrada.get(campo, "No disponible")
                            if valor and valor.strip():  # Solo mostrar si tiene valor
                                if i % 2 == 0:
                                    with col1:
                                        st.write(f"**{etiqueta}:** {valor}")
                                else:
                                    with col2:
                                        st.write(f"**{etiqueta}:** {valor}")
                        
                        # Mostrar descripción en una sección aparte por ser más larga
                        descripcion = pqrs_encontrada.get("Descripcion", "")
                        if descripcion and descripcion.strip():
                            st.write("---")
                            st.write("**Descripción:**")
                            st.text_area("", value=descripcion, height=100, disabled=True, key="desc_consulta")
                        
                        # Mostrar respuesta si existe
                        respuesta = pqrs_encontrada.get("Respuesta", "")
                        if respuesta and respuesta.strip():
                            st.write("---")
                            st.write("**📋 Respuesta del Área de Soporte:**")
                            st.text_area("", value=respuesta, height=120, disabled=True, key="respuesta_consulta")
                        
                        # Mostrar archivo adjunto si existe
                        archivo_adj = pqrs_encontrada.get("Archivo_Adjunto", "")
                        if archivo_adj and archivo_adj.strip() and archivo_adj != "Sin archivo":
                            st.write(f"**📎 Archivo Adjunto:** {archivo_adj}")
                        
                        # Información adicional según el estado
                        if estado == "Pendiente":
                            st.info("📋 Su PQRS está pendiente de revisión. Tiempo máximo de respuesta: 15 días hábiles.")
                        elif estado == "En Proceso":
                            st.info("🔄 Su PQRS está siendo procesada por nuestro equipo de soporte.")
                        elif estado == "Respondida":
                            st.success("✅ Su PQRS ha sido respondida. Revise la respuesta arriba.")
                            
                    else:
                        st.error("❌ No se encontró ninguna PQRS con ese número de radicado.")
                        st.info("💡 Verifique que el número esté escrito correctamente (ejemplo: PQRS-123456)")
                        
                except gspread.exceptions.WorksheetNotFound:
                    st.error("❌ No se encontró la hoja 'pqrs' en el archivo 'gestion-conjunto'.")
                    st.info("Asegúrese de que existe al menos una PQRS registrada para crear la hoja.")
                except gspread.exceptions.SpreadsheetNotFound:
                    st.error("❌ No se encontró el archivo 'gestion-conjunto' en Google Sheets.")
                    st.info("Verifique que el archivo existe y tiene los permisos correctos.")
                except Exception as e:
                    st.error(f"❌ Error al consultar: {str(e)}")
                    st.info("Intente nuevamente o contacte al administrador.")
                    
                    # Información de depuración para desarrollo
                    with st.expander("🔧 Información técnica"):
                        st.code(str(type(e).__name__) + ": " + str(e))
                        
            else:
                st.warning("⚠️ Por favor ingrese un número de radicado.")
    
    # Información adicional
    st.write("---")
    st.info("""
    **ℹ️ Estados de PQRS:**
    
    - **⏳ Pendiente:** Su solicitud ha sido recibida y está en cola de revisión
    - **🔄 En Proceso:** Su solicitud está siendo procesada por nuestro equipo
    - **✅ Respondida:** Su solicitud ha sido respondida completamente
    
    **📞 ¿Necesita ayuda?**
    - Tel: (601) 123-4567
    - Email: administracion@condominioceiba.com
    """)

def get_pqrs_by_radicado(client, numero_radicado):
    """Obtener PQRS por número de radicado"""
    try:
        spreadsheet = client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("pqrs")
        
        # Obtener todos los valores como matriz
        all_values = worksheet.get_all_values()
        
        if len(all_values) < 2:
            return None, None
        
        # La primera fila son los encabezados
        headers = all_values[0]
        
        # Buscar el registro
        for row_index, row in enumerate(all_values[1:], start=2):  # +2 porque empezamos en fila 2
            if len(row) > 0 and row[1] == numero_radicado:  # Columna 1 = Numero_Radicado
                # Crear diccionario con los datos
                pqrs_data = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        pqrs_data[header] = row[i]
                    else:
                        pqrs_data[header] = ""
                return pqrs_data, row_index
        
        return None, None
        
    except Exception as e:
        st.error(f"❌ Error al consultar PQRS: {str(e)}")
        return None, None

def update_pqrs_response(client, numero_radicado, respuesta_data):
    """Actualizar la respuesta de una PQRS en Google Sheets"""
    try:
        spreadsheet = client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("pqrs")
        
        # Buscar la fila del PQRS
        _, row_index = get_pqrs_by_radicado(client, numero_radicado)
        
        if row_index:
            # Actualizar las columnas correspondientes
            # Estado (columna J = 10), Fecha_Respuesta (columna L = 12), Respuesta_Detallada (columna M = 13)
            worksheet.update_cell(row_index, 10, respuesta_data['estado'])
            worksheet.update_cell(row_index, 12, respuesta_data['fecha_respuesta'])
            worksheet.update_cell(row_index, 9, respuesta_data['descripcion'])
            
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"❌ Error al actualizar respuesta: {str(e)}")
        return False


def soporte_authentication():
    """Autenticación simple para el área de soporte"""
    if 'soporte_authenticated' not in st.session_state:
        st.session_state.soporte_authenticated = False
    
    if not st.session_state.soporte_authenticated:
        st.subheader("🔐 Acceso para Área de Soporte")
        
        with st.form("auth_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Iniciar Sesión")
            
            if submit:
                # Credenciales simples (en producción usar hash y base de datos)
                if username == "soporte" and password == "soporte1234":
                    st.session_state.soporte_authenticated = True
                    st.success("✅ Autenticación exitosa")
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")
        
        st.info("**Credenciales de prueba:**\n- Usuario: soporte\n- Contraseña: soporte1234")
        return False
    
    return True

def soporte_panel(client, config):
    """Panel de gestión para el área de soporte"""
    import streamlit as st
    import pandas as pd
    from datetime import datetime
    import time
    
    st.header("🛠️ Panel de Gestión de Soporte")
    
    # Botón de cerrar sesión
    if st.button("🚪 Cerrar Sesión", key="logout"):
        st.session_state.soporte_authenticated = False
        st.rerun()
    
    st.write("---")
    
    # Pestañas para diferentes funcionalidades
    tab1, tab2, tab3 = st.tabs(["📋 PQRS Pendientes", "✅ Responder PQRS", "📊 Estadísticas"])
    
    with tab1:
        st.subheader("📋 PQRS Pendientes de Respuesta")
        
        try:
            pending_pqrs = get_pending_pqrs_from_sheets(client)
            
            if pending_pqrs and len(pending_pqrs) > 0:
                st.write(f"**Total de PQRS pendientes:** {len(pending_pqrs)}")
                
                # Mostrar tabla de PQRS pendientes
                df = pd.DataFrame(pending_pqrs)
                columns_to_show = ['Numero_Radicado', 'Fecha_Registro', 'Tipo_Solicitud',
                                  'Nombre_Completo', 'Apartamento', 'Asunto', 'Estado']
                
                if not df.empty:
                    # Verificar qué columnas existen en el DataFrame
                    available_columns = [col for col in columns_to_show if col in df.columns]
                    st.dataframe(df[available_columns], use_container_width=True)
                    
                    # Selector para ver detalles
                    radicados = df['Numero_Radicado'].tolist()
                    selected_radicado = st.selectbox(
                        "Seleccionar PQRS para ver detalles:",
                        options=[""] + radicados,
                        key="select_pqrs_details"
                    )
                    
                    if selected_radicado:
                        # Mostrar detalles de la PQRS seleccionada
                        selected_pqrs = df[df['Numero_Radicado'] == selected_radicado].iloc[0].to_dict()
                        
                        with st.expander(f"📄 Detalles - {selected_radicado}", expanded=True):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Número de Radicado:** {selected_pqrs.get('Numero_Radicado', 'N/A')}")
                                st.write(f"**Fecha:** {selected_pqrs.get('Fecha_Registro', 'N/A')}")
                                st.write(f"**Tipo:** {selected_pqrs.get('Tipo_Solicitud', 'N/A')}")
                                st.write(f"**Estado:** {selected_pqrs.get('Estado', 'N/A')}")
                            
                            with col2:
                                st.write(f"**Nombre:** {selected_pqrs.get('Nombre_Completo', 'N/A')}")
                                st.write(f"**Apartamento:** {selected_pqrs.get('Apartamento', 'N/A')}")
                                st.write(f"**Email:** {selected_pqrs.get('Email', 'No proporcionado')}")
                                st.write(f"**Teléfono:** {selected_pqrs.get('Telefono', 'No proporcionado')}")
                            
                            st.write(f"**Asunto:** {selected_pqrs.get('Asunto', 'N/A')}")
                            st.write(f"**Descripción:**")
                            st.text_area("", value=selected_pqrs.get('Descripcion', ''), height=100, disabled=True, key="desc_display")
            else:
                st.info("🎉 ¡Excelente! No hay PQRS pendientes por responder.")
                
        except Exception as e:
            st.error(f"❌ Error al cargar PQRS pendientes: {str(e)}")
            st.info("💡 Verifica la conexión con Google Sheets")
    
    with tab2:
        st.subheader("✅ Responder PQRS")
        
        try:
            # Obtener PQRS pendientes para responder
            pending_to_respond = get_pending_pqrs_from_sheets(client)
            
            if pending_to_respond and len(pending_to_respond) > 0:
                df_respond = pd.DataFrame(pending_to_respond)
                
                # Selector de PQRS para responder
                radicados_respond = df_respond['Numero_Radicado'].tolist()
                selected_pqrs_respond = st.selectbox(
                    "Seleccionar PQRS para responder:",
                    options=[""] + radicados_respond,
                    key="select_pqrs_respond"
                )
                
                if selected_pqrs_respond:
                    pqrs_to_respond = df_respond[df_respond['Numero_Radicado'] == selected_pqrs_respond].iloc[0].to_dict()
                    
                    # Mostrar información de la PQRS
                    st.info(f"📋 **PQRS:** {selected_pqrs_respond} | **Tipo:** {pqrs_to_respond.get('Tipo_Solicitud', 'N/A')} | **Asunto:** {pqrs_to_respond.get('Asunto', 'N/A')}")
                    
                    # Formulario de respuesta
                    with st.form("response_form"):
                        st.write("**📝 Componer Respuesta:**")
                        
                        response_text = st.text_area(
                            "Respuesta:",
                            height=200,
                            placeholder="Escriba aquí la respuesta detallada para el residente..."
                        )
                        
                        # Opciones adicionales
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            priority = st.selectbox(
                                "Prioridad de seguimiento:",
                                ["Baja", "Media", "Alta"],
                                index=1
                            )
                        
                        with col2:
                            requires_followup = st.checkbox("Requiere seguimiento")
                        
                        # Archivos adjuntos (opcional)
                        attachments = st.file_uploader(
                            "Adjuntar archivos (opcional):",
                            accept_multiple_files=True,
                            type=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
                        )
                        
                        # Botones de acción
                        col1, col2, col3 = st.columns([1, 1, 2])
                        
                        with col1:
                            submit_response = st.form_submit_button("📤 Enviar Respuesta", type="primary")
                        
                        with col2:
                            save_draft = st.form_submit_button("💾 Guardar Borrador")
                        
                        if submit_response:
                            if response_text.strip():
                                try:
                                    # Actualizar la PQRS con la respuesta
                                    response_data = {
                                        'Respuesta': response_text,
                                        'Fecha_Respuesta': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'Respondido_Por': st.session_state.get('soporte_user', 'Soporte'),
                                        'Estado': 'Respondida',
                                        'Prioridad_Seguimiento': priority,
                                        'Requiere_Seguimiento': 'Sí' if requires_followup else 'No'
                                    }
                                    
                                    # Actualizar en Google Sheets
                                    success = update_pqrs_in_sheets(client, selected_pqrs_respond, response_data)
                                    
                                    if success:
                                        st.success(f"✅ Respuesta enviada exitosamente para PQRS {selected_pqrs_respond}")
                                        
                                        # Enviar notificación por email
                                        try:
                                            send_response_email_notification(pqrs_to_respond, response_text)
                                            st.success("📧 Notificación enviada al residente")
                                        except Exception as e:
                                            st.warning(f"⚠️ Respuesta guardada, pero no se pudo enviar la notificación: {str(e)}")
                                            print(f"⚠️ Respuesta guardada, pero no se pudo enviar la notificación: {str(e)}") 
                                        # Limpiar selección
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al guardar la respuesta en Google Sheets")
                                        
                                except Exception as e:
                                    st.error(f"❌ Error al procesar la respuesta: {str(e)}")
                            else:
                                st.warning("⚠️ Por favor, escriba una respuesta antes de enviar")
                        
                        if save_draft:
                            if response_text.strip():
                                # Guardar como borrador
                                draft_data = {
                                    'Borrador_Respuesta': response_text,
                                    'Fecha_Borrador': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'Estado': 'En Proceso'
                                }
                                
                                try:
                                    success = update_pqrs_in_sheets(client, selected_pqrs_respond, draft_data)
                                    if success:
                                        st.success("💾 Borrador guardado exitosamente")
                                    else:
                                        st.error("❌ Error al guardar el borrador")
                                except Exception as e:
                                    st.error(f"❌ Error al guardar borrador: {str(e)}")
                            else:
                                st.warning("⚠️ No hay contenido para guardar como borrador")
            else:
                st.info("🎉 No hay PQRS pendientes por responder")
                
        except Exception as e:
            st.error(f"❌ Error al cargar PQRS para responder: {str(e)}")
    
    with tab3:
        st.subheader("📊 Estadísticas del Sistema PQRS")
        
        try:
            # Obtener estadísticas generales
            all_pqrs = get_all_pqrs_from_sheets(client)
            
            if all_pqrs and len(all_pqrs) > 0:
                df_stats = pd.DataFrame(all_pqrs)
                
                # Métricas principales
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_pqrs = len(df_stats)
                    st.metric("📋 Total PQRS", total_pqrs)
                
                with col2:
                    pendientes = len(df_stats[df_stats['Estado'] == 'Pendiente'])
                    st.metric("⏳ Pendientes", pendientes)
                
                with col3:
                    respondidas = len(df_stats[df_stats['Estado'] == 'Respondida'])
                    st.metric("✅ Respondidas", respondidas)
                
                with col4:
                    if total_pqrs > 0:
                        tasa_respuesta = (respondidas / total_pqrs) * 100
                        st.metric("📈 Tasa Respuesta", f"{tasa_respuesta:.1f}%")
                    else:
                        st.metric("📈 Tasa Respuesta", "0%")
                
                st.write("---")
                
                # Gráficos
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 PQRS por Tipo")
                    if 'Tipo_Solicitud' in df_stats.columns:
                        tipo_counts = df_stats['Tipo_Solicitud'].value_counts()
                        st.bar_chart(tipo_counts)
                
                with col2:
                    st.subheader("📈 PQRS por Estado")
                    if 'Estado' in df_stats.columns:
                        estado_counts = df_stats['Estado'].value_counts()
                        st.bar_chart(estado_counts)
                
                # Tabla de PQRS recientes
                st.subheader("🕒 PQRS Más Recientes")
                if 'Fecha_Registro' in df_stats.columns:
                    try:
                        # Convertir fechas y ordenar
                        df_stats['Fecha_Registro'] = pd.to_datetime(df_stats['Fecha_Registro'], errors='coerce')
                        df_recent = df_stats.nlargest(10, 'Fecha_Registro')
                        
                        columns_recent = ['Numero_Radicado', 'Fecha_Registro', 'Tipo_Solicitud', 
                                        'Nombre_Completo', 'Asunto', 'Estado']
                        # Verificar qué columnas existen
                        available_columns_recent = [col for col in columns_recent if col in df_recent.columns]
                        st.dataframe(df_recent[available_columns_recent], use_container_width=True)
                    except Exception as e:
                        st.warning(f"Error al mostrar PQRS recientes: {str(e)}")
                
                # Estadísticas por mes
                st.subheader("📅 Tendencia Mensual")
                if 'Fecha_Registro' in df_stats.columns:
                    try:
                        df_stats['Fecha_Registro'] = pd.to_datetime(df_stats['Fecha_Registro'], errors='coerce')
                        df_stats = df_stats.dropna(subset=['Fecha_Registro'])
                        df_stats['Mes'] = df_stats['Fecha_Registro'].dt.to_period('M')
                        monthly_counts = df_stats.groupby('Mes').size()
                        if len(monthly_counts) > 0:
                            st.line_chart(monthly_counts)
                        else:
                            st.info("No hay datos suficientes para mostrar la tendencia mensual")
                    except Exception as e:
                        st.warning(f"No se pudo generar el gráfico mensual: {str(e)}")
            
            else:
                st.info("📊 No hay datos disponibles para mostrar estadísticas")
                
        except Exception as e:
            st.error(f"❌ Error al cargar estadísticas: {str(e)}")


# Funciones auxiliares para manejar Google Sheets
def get_pending_pqrs_from_sheets(client):
    """Obtiene las PQRS pendientes de respuesta desde Google Sheets"""
    try:
        # Intentar diferentes métodos según el tipo de cliente
        df = None
        
        # Método 1: Usando get_sheet_data
        if hasattr(client, 'get_sheet_data'):
            df = client.get_sheet_data('gestion-conjuntos', 'pqrs')
        
        # Método 2: Usando read_data
        elif hasattr(client, 'read_data'):
            df = client.read_data('gestion-conjuntos', 'pqrs')
            
        # Método 3: Usando get_data
        elif hasattr(client, 'get_data'):
            df = client.get_data('gestion-conjuntos', 'pqrs')
            
        # Método 4: Usando worksheet
        elif hasattr(client, 'open'):
            workbook = client.open('gestion-conjuntos')
            worksheet = workbook.worksheet('pqrs')
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            
        # Método 5: Usando service directo
        elif hasattr(client, 'service'):
            spreadsheet_id = get_spreadsheet_id(client, 'gestion-conjuntos')
            range_name = 'pqrs!A:Z'
            result = client.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            if values:
                df = pd.DataFrame(values[1:], columns=values[0])
        
        if df is not None and not df.empty:
            # Filtrar solo las PQRS pendientes
            pending_df = df[df['Estado'] == 'Pendiente']
            return pending_df.to_dict('records')
        
        return []
    except Exception as e:
        print(f"Error al obtener PQRS pendientes desde Sheets: {str(e)}")
        return []


def get_all_pqrs_from_sheets(client):
    """Obtiene todas las PQRS desde Google Sheets para estadísticas"""
    try:
        df = None
        
        # Intentar diferentes métodos según el tipo de cliente
        if hasattr(client, 'get_sheet_data'):
            df = client.get_sheet_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'read_data'):
            df = client.read_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'get_data'):
            df = client.get_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'open'):
            workbook = client.open('gestion-conjuntos')
            worksheet = workbook.worksheet('pqrs')
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
        elif hasattr(client, 'service'):
            spreadsheet_id = get_spreadsheet_id(client, 'gestion-conjuntos')
            range_name = 'pqrs!A:Z'
            result = client.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            if values:
                df = pd.DataFrame(values[1:], columns=values[0])
        
        if df is not None and not df.empty:
            return df.to_dict('records')
        
        return []
    except Exception as e:
        print(f"Error al obtener todas las PQRS desde Sheets: {str(e)}")
        return []


def update_pqrs_in_sheets(client, numero_radicado, response_data):
    """Actualiza una PQRS con la respuesta en Google Sheets"""
    try:
        # Leer datos actuales
        df = None
        
        if hasattr(client, 'get_sheet_data'):
            df = client.get_sheet_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'read_data'):
            df = client.read_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'get_data'):
            df = client.get_data('gestion-conjuntos', 'pqrs')
        elif hasattr(client, 'open'):
            workbook = client.open('gestion-conjuntos')
            worksheet = workbook.worksheet('pqrs')
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
        elif hasattr(client, 'service'):
            spreadsheet_id = get_spreadsheet_id(client, 'gestion-conjuntos')
            range_name = 'pqrs!A:Z'
            result = client.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            if values:
                df = pd.DataFrame(values[1:], columns=values[0])
        
        if df is not None and not df.empty:
            # Buscar la fila correspondiente al número de radicado
            row_index = df[df['Numero_Radicado'] == numero_radicado].index
            
            if len(row_index) > 0:
                # Actualizar los campos con los nuevos datos
                for key, value in response_data.items():
                    if key in df.columns:
                        df.loc[row_index[0], key] = value
                    else:
                        # Si la columna no existe, crearla
                        df[key] = ''
                        df.loc[row_index[0], key] = value
                
                # Escribir los datos actualizados de vuelta a la hoja
                success = write_data_to_sheets(client, 'gestion-conjuntos', 'pqrs', df)
                return success
            else:
                print(f"No se encontró PQRS con número de radicado: {numero_radicado}")
                return False
        
        return False
    except Exception as e:
        print(f"Error al actualizar PQRS en Sheets: {str(e)}")
        return False


def write_data_to_sheets(client, spreadsheet_name, worksheet_name, df):
    """Escribe datos de vuelta a Google Sheets"""
    try:
        # Método 1: Usando update_sheet_data
        if hasattr(client, 'update_sheet_data'):
            return client.update_sheet_data(spreadsheet_name, worksheet_name, df)
        
        # Método 2: Usando write_data
        elif hasattr(client, 'write_data'):
            return client.write_data(spreadsheet_name, worksheet_name, df)
            
        # Método 3: Usando gspread
        elif hasattr(client, 'open'):
            workbook = client.open(spreadsheet_name)
            worksheet = workbook.worksheet(worksheet_name)
            
            # Limpiar la hoja
            worksheet.clear()
            
            # Escribir headers
            headers = df.columns.tolist()
            worksheet.append_row(headers)
            
            # Escribir datos
            for _, row in df.iterrows():
                worksheet.append_row(row.tolist())
            
            return True
            
        # Método 4: Usando service directo
        elif hasattr(client, 'service'):
            spreadsheet_id = get_spreadsheet_id(client, spreadsheet_name)
            
            # Preparar datos
            values = [df.columns.tolist()] + df.values.tolist()
            
            body = {
                'values': values
            }
            
            range_name = f'{worksheet_name}!A1'
            
            # Limpiar la hoja primero
            client.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f'{worksheet_name}!A:Z'
            ).execute()
            
            # Escribir nuevos datos
            result = client.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
        
        return False
    except Exception as e:
        print(f"Error al escribir datos a Sheets: {str(e)}")
        return False


def get_spreadsheet_id(client, spreadsheet_name):
    """Obtiene el ID de la hoja de cálculo por nombre"""
    try:
        # Este es un método auxiliar que necesitarás adaptar según tu implementación
        # Por ejemplo, si tienes un diccionario de nombres a IDs
        if hasattr(client, 'get_spreadsheet_id'):
            return client.get_spreadsheet_id(spreadsheet_name)
        else:
            # Fallback - necesitarás definir esto según tu configuración
            raise Exception("Método get_spreadsheet_id no implementado")
    except Exception as e:
        raise Exception(f"Error al obtener ID de spreadsheet: {str(e)}")


def send_response_email_notification(pqrs_data, response_text):
    """Envía notificación por email al residente usando EmailSender corregido"""
    try:
        import streamlit as st
        
        # Configurar el EmailSender
        email_sender = EmailSender(
            smtp_server="smtp.gmail.com",
            port=465,
            sender_email=st.secrets['emails']['smtp_user'],
            password=st.secrets['emails']['smtp_password']
        )
        
        # Datos del destinatario
        recipient_email = pqrs_data.get('Email', '')
        if not recipient_email or recipient_email == 'No proporcionado':
            raise Exception("No se encontró email del residente")
        
        # Componer el mensaje
        subject = f"Respuesta a su PQRS - {pqrs_data.get('Numero_Radicado', 'N/A')}"
        
        body = f"""Estimado(a) {pqrs_data.get('Nombre_Completo', 'Residente')},

Esperamos que se encuentre bien. Le escribimos para darle respuesta a su PQRS registrada.

INFORMACIÓN DE SU SOLICITUD:
• Número de Radicado: {pqrs_data.get('Numero_Radicado', 'N/A')}
• Tipo de Solicitud: {pqrs_data.get('Tipo_Solicitud', 'N/A')}
• Asunto: {pqrs_data.get('Asunto', 'N/A')}
• Fecha de Registro: {pqrs_data.get('Fecha_Registro', 'N/A')}

RESPUESTA:
{response_text}

Si tiene alguna pregunta adicional o requiere aclaración sobre esta respuesta, 
no dude en contactarnos.

Gracias por su confianza.

Atentamente,
Área de Soporte
Administración del Conjunto"""
        
        # Enviar el email con los 3 parámetros
        email_sender.send_email(recipient_email, subject, body)
        
        return True
        
    except Exception as e:
        raise Exception(f"Error al enviar notificación por email: {str(e)}")

def send_email(recipient_email, subject, body):  # Agregado parámetro body
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            # Agregar cuerpo del mensaje
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Conectar al servidor SMTP
            server = smtplib.SMTP_SSL(smtp_server, port)
            server.login(sender_email, password)
            
            # Enviar email
            text = msg.as_string()
            server.sendmail(sender_email, recipient_email, text)
            server.quit()
            
            return True
        except Exception as e:
            raise Exception(f"Error en EmailSender: {str(e)}")

#if __name__ == "__main__":
#    pqrs_main()