import streamlit as st
import gspread
import pandas as pd
import toml
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import time

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Solicitudes - Conjunto Residencial",
#    page_icon="🏢",
#    layout="wide",
#    initial_sidebar_state="expanded"
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
            st.success(f"✅ Conexión exitosa a Google Sheets!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
        
        return client
    
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def create_or_get_sheet(client, sheet_name="gestion-conjuntos"):
    """Crear o obtener la hoja de cálculo"""
    try:
        # Intentar abrir la hoja existente
        sheet = client.open(sheet_name)
        st.info(f"📊 Hoja '{sheet_name}' encontrada")
        return sheet
    except gspread.SpreadsheetNotFound:
        # Crear nueva hoja si no existe
        sheet = client.create(sheet_name)
        st.success(f"✨ Nueva hoja '{sheet_name}' creada")
        return sheet
    except Exception as e:
        st.error(f"❌ Error al acceder/crear la hoja: {str(e)}")
        return None

def setup_solicitudes_worksheet(sheet):
    """Configurar la hoja de trabajo 'solicitudes' con las columnas necesarias"""
    try:
        # Intentar obtener la hoja de trabajo 'solicitudes'
        try:
            worksheet = sheet.worksheet('solicitudes')
            st.info("📋 Hoja 'solicitudes' encontrada")
        except gspread.WorksheetNotFound:
            # Crear la hoja de trabajo si no existe
            worksheet = sheet.add_worksheet(title='solicitudes', rows=1000, cols=15)
            st.success("✨ Hoja 'solicitudes' creada")
        
        # Definir las columnas necesarias
        headers = [
            'ID_Solicitud',
            'Fecha_Solicitud', 
            'Nombre_Completo',
            'Unidad_Residencial',
            'Telefono',
            'Email',
            'Tipo_Solicitante',
            'Tipo_Solicitud',
            'Descripcion',
            'Prioridad',
            'Estado',
            'Fecha_Respuesta',
            'Respuesta_Admin',
            'Observaciones',
            'Fecha_Actualizacion'
        ]
        
        # Verificar si ya hay encabezados
        try:
            existing_headers = worksheet.row_values(1)
            if not existing_headers or existing_headers != headers:
                worksheet.update('A1:O1', [headers])
                st.success("📝 Encabezados de la hoja actualizados")
        except:
            worksheet.update('A1:O1', [headers])
            st.success("📝 Encabezados de la hoja configurados")
        
        return worksheet
        
    except Exception as e:
        st.error(f"❌ Error configurando la hoja 'solicitudes': {str(e)}")
        return None

def send_email_to_admin(nombre, unidad, tipo_solicitud, descripcion, email_residente, telefono, tipo_solicitante, prioridad):
    """
    Envía correo electrónico a la administración con la nueva solicitud
    """
    try:
        # Configuración del servidor SMTP utilizando st.secrets
        smtp_server = 'smtp.gmail.com'
        smtp_port = 465
        
        # Asegurarse de tener las credenciales necesarias
        if 'emails' not in st.secrets or 'smtp_user' not in st.secrets['emails'] or 'smtp_password' not in st.secrets['emails']:
            return False, "Error: Faltan credenciales de correo en secrets.toml"
            
        smtp_user = st.secrets['emails']['smtp_user']
        smtp_password = st.secrets['emails']['smtp_password']
        admin_email = "josegarjagt@gmail.com"   #"laceibacondominio@gmail.com"
        
        # Crear mensaje
        message = MIMEMultipart()
        message['From'] = smtp_user
        message['To'] = admin_email
        message['Subject'] = f"Nueva Solicitud: {tipo_solicitud} - Unidad {unidad}"
        
        # Definir colores según la prioridad
        if prioridad == "Alta":
            color = "#C73E1D"
            icon = "🔴"
        elif prioridad == "Media":
            color = "#F18F01"
            icon = "🟡"
        else:  # Baja
            color = "#2E86AB"
            icon = "🟢"
        
        body = f"""                               
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            background-color: {color};
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            padding: 20px;
            background-color: #f9f9f9;
            border: 1px solid #ddd;
        }}
        .footer {{
            background-color: #333;
            color: white;
            padding: 15px;
            text-align: center;
            border-radius: 0 0 10px 10px;
            font-size: 12px;
        }}
        .info-box {{
            background-color: white;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid {color};
            border-radius: 5px;
        }}
        .detail-row {{
            margin: 8px 0;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>{icon} Nueva Solicitud de Residente</h2>
        <h3>Prioridad: {prioridad}</h3>
    </div>
    <div class="content">
        <p>Se ha recibido una nueva solicitud:</p>
        
        <div class="info-box">
            <h4>📋 Información del Solicitante</h4>
            <div class="detail-row">
                <span class="label">Nombre:</span> {nombre}
            </div>
            <div class="detail-row">
                <span class="label">Unidad:</span> {unidad}
            </div>
            <div class="detail-row">
                <span class="label">Tipo:</span> {tipo_solicitante}
            </div>
            <div class="detail-row">
                <span class="label">Teléfono:</span> {telefono}
            </div>
            <div class="detail-row">
                <span class="label">Email:</span> {email_residente}
            </div>
        </div>
        
        <div class="info-box">
            <h4>📝 Detalles de la Solicitud</h4>
            <div class="detail-row">
                <span class="label">Tipo de Solicitud:</span> {tipo_solicitud}
            </div>
            <div class="detail-row">
                <span class="label">Descripción:</span>
                <p style="margin-top: 10px; padding: 10px; background-color: #f5f5f5; border-radius: 5px;">
                    {descripcion}
                </p>
            </div>
        </div>
        
        <p><b>📅 Fecha de Solicitud:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    </div>
    <div class="footer">
        <p>Sistema de Gestión de Solicitudes - La Ceiba Condominio<br>
        Este es un mensaje automático del sistema de solicitudes.</p>
    </div>
</body>
</html>
        """
        
        # Adjuntar el cuerpo del mensaje como HTML
        message.attach(MIMEText(body, 'html'))
        
        # Conexión con el servidor SMTP
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        
        # Inicio de sesión
        server.login(smtp_user, smtp_password)
        
        # Enviar correo
        text = message.as_string()
        server.sendmail(smtp_user, admin_email, text)
        server.quit()
        
        return True, "Notificación enviada exitosamente a la administración"
        
    except Exception as e:
        return False, f"Error al enviar notificación: {str(e)}"

def save_solicitud_to_sheet(worksheet, solicitud_data):
    """Guardar la solicitud en Google Sheets"""
    try:
        # Generar ID único basado en timestamp
        timestamp = datetime.now()
        id_solicitud = f"SOL{timestamp.strftime('%Y%m%d%H%M%S')}"
        
        # Preparar los datos para insertar
        row_data = [
            id_solicitud,
            timestamp.strftime('%d/%m/%Y %H:%M'),
            solicitud_data['nombre'],
            solicitud_data['unidad'],
            solicitud_data['telefono'],
            solicitud_data['email'],
            solicitud_data['tipo_solicitante'],
            solicitud_data['tipo_solicitud'],
            solicitud_data['descripcion'],
            solicitud_data['prioridad'],
            'Pendiente',  # Estado inicial
            '',  # Fecha_Respuesta
            '',  # Respuesta_Admin
            '',  # Observaciones
            timestamp.strftime('%d/%m/%Y %H:%M')  # Fecha_Actualizacion
        ]
        
        # Insertar la fila
        worksheet.append_row(row_data)
        
        return True, id_solicitud
        
    except Exception as e:
        return False, f"Error guardando en Google Sheets: {str(e)}"

def solicitudes_main():
    # Título principal
    st.title("🏢 Sistema de Solicitudes - Conjunto Residencial")
    st.markdown("---")
    
    # Sidebar con información del sistema
    with st.sidebar:
        st.header("ℹ️ Información del Sistema")
        st.info("""
        **Sistema de Gestión de Solicitudes**
        
        Este sistema permite a los residentes y propietarios enviar solicitudes a la administración del conjunto.
        
        **Características:**
        - ✅ Formulario intuitivo
        - 📊 Registro en Google Sheets
        - 📧 Notificación automática por email
        - 🏷️ Clasificación por prioridad
        """)
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión con Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Crear o obtener la hoja de cálculo
    sheet = create_or_get_sheet(client)
    if not sheet:
        st.stop()
    
    # Configurar la hoja de trabajo 'solicitudes'
    worksheet = setup_solicitudes_worksheet(sheet)
    if not worksheet:
        st.stop()
    
    # Formulario principal
    st.header("📝 Nueva Solicitud")
    
    with st.form("solicitud_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👤 Información Personal")
            nombre = st.text_input("Nombre Completo *", placeholder="Ej: Juan Pérez Gómez")
            unidad = st.text_input("Unidad Residencial *", placeholder="Ej: Apto 101, Casa 15, Torre A-202")
            telefono = st.text_input("Teléfono *", placeholder="Ej: +57 300 123 4567")
            email = st.text_input("Correo Electrónico *", placeholder="Ej: juan.perez@email.com")
            
            tipo_solicitante = st.selectbox(
                "Tipo de Solicitante *",
                ["Propietario", "Residente/Arrendatario", "Familiar Autorizado"]
            )
        
        with col2:
            st.subheader("📋 Detalles de la Solicitud")
            tipo_solicitud = st.selectbox(
                "Tipo de Solicitud *",
                [
                    "Mantenimiento General",
                    "Reparaciones Urgentes", 
                    "Servicios Públicos",
                    "Seguridad",
                    "Áreas Comunes",
                    "Administración",
                    "Quejas y Reclamos",
                    "Autorizaciones",
                    "Certificados y Documentos",
                    "Otros"
                ]
            )
            
            prioridad = st.selectbox(
                "Prioridad *",
                ["Baja", "Media", "Alta"],
                help="Alta: Urgente, Media: Importante, Baja: Rutinaria"
            )
            
            st.markdown("**Descripción Detallada ***")
            descripcion = st.text_area(
                "",
                placeholder="Describe detalladamente tu solicitud. Incluye ubicación específica, horarios, y cualquier información relevante...",
                height=150
            )
        
        st.markdown("---")
        
        # Botones
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("📤 Enviar Solicitud", type="primary", use_container_width=True)
        
        # Procesar el formulario
        if submitted:
            # Validaciones
            if not all([nombre, unidad, telefono, email, descripcion]):
                st.error("❌ Por favor completa todos los campos marcados con (*)")
            elif "@" not in email:
                st.error("❌ Por favor ingresa un correo electrónico válido")
            else:
                # Mostrar mensaje de procesamiento
                with st.spinner("📤 Enviando solicitud..."):
                    # Preparar datos
                    solicitud_data = {
                        'nombre': nombre.strip(),
                        'unidad': unidad.strip(),
                        'telefono': telefono.strip(),
                        'email': email.strip().lower(),
                        'tipo_solicitante': tipo_solicitante,
                        'tipo_solicitud': tipo_solicitud,
                        'descripcion': descripcion.strip(),
                        'prioridad': prioridad
                    }
                    
                    # Guardar en Google Sheets
                    success_sheet, result = save_solicitud_to_sheet(worksheet, solicitud_data)
                    
                    if success_sheet:
                        # Enviar correo a la administración
                        success_email, message = send_email_to_admin(
                            nombre, unidad, tipo_solicitud, descripcion, 
                            email, telefono, tipo_solicitante, prioridad
                        )
                        
                        if success_email:
                            st.success(f"""
                            ✅ **Solicitud enviada exitosamente**
                            
                            **ID de Solicitud:** {result}
                            
                            - ✅ Solicitud registrada en el sistema
                            - ✅ Notificación enviada a la administración
                            - 📧 Recibirás respuesta en tu correo electrónico
                            
                            **Tiempo estimado de respuesta:** 24-48 horas hábiles
                            """)
                        else:
                            st.warning(f"""
                            ⚠️ **Solicitud registrada con advertencia**
                            
                            **ID de Solicitud:** {result}
                            
                            - ✅ Solicitud registrada en el sistema
                            - ❌ Error enviando notificación: {message}
                            
                            Tu solicitud fue guardada correctamente, pero la administración será notificada manualmente.
                            """)
                    else:
                        st.error(f"❌ **Error procesando la solicitud:** {result}")
    
    # Información adicional
    st.markdown("---")
    st.header("📞 Información de Contacto")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **📧 Correo Administración:**  
        laceibacondominio@gmail.com
        
        **⏰ Horarios de Atención:**  
        Lunes a Viernes: 8:00 AM - 5:00 PM  
        Sábados: 8:00 AM - 12:00 PM
        """)
    
    with col2:
        st.info("""
        **🚨 Para Emergencias:**  
        Contacta directamente por teléfono
        
        **📋 Estado de Solicitudes:**  
        Recibirás actualizaciones por correo electrónico  
        Tiempo de respuesta: 24-48 horas hábiles
        """)

#if __name__ == "__main__":
#    solicitudes_main()