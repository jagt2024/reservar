import streamlit as st
from PIL import Image
import pandas as pd
import os
from datetime import datetime
import hashlib
import base64
import toml
import json
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Configuración de la página
st.set_page_config(
    page_title="José Alejandro - Desarrollo de Aplicaciones",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Función para convertir imagen a base64
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        print(f"Error al cargar imagen: {e}")
        return None

# Funciones de autenticación
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
        st.error("🔒 Archivo secrets.toml no encontrado en .streamlit/")
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

def send_email_gmail(nombre, email, telefono, asunto, mensaje):
    """
    Enviar email usando Gmail SMTP
    
    IMPORTANTE: Para usar Gmail necesitas:
    1. Activar "Verificación en 2 pasos" en tu cuenta de Google
    2. Generar una "Contraseña de aplicación" en: https://myaccount.google.com/apppasswords
    3. Agregar estas credenciales en secrets.toml
    """
    try:
        # Obtener credenciales de secrets.toml
        email_sender = st.secrets['emails']['smtp_user']
        email_password = st.secrets['emails']['smtp_password']
        email_receiver = "josegarjagt@gmail.com"
        
        # Crear el mensaje
        msg = MIMEMultipart('alternative')
        msg['From'] = email_sender
        msg['To'] = email_receiver
        msg['Subject'] = f"Nuevo mensaje de contacto: {asunto}"
        
        # Cuerpo del email en HTML
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">
                    <div style="background-color: #013220; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                        <h2 style="color: #ff6b35; margin: 0;">Nuevo Mensaje de Contacto</h2>
                    </div>
                    
                    <div style="background-color: white; padding: 30px; border-radius: 0 0 10px 10px;">
                        <h3 style="color: #013220; border-bottom: 2px solid #ff6b35; padding-bottom: 10px;">
                            Información del Contacto
                        </h3>
                        
                        <table style="width: 100%; margin: 20px 0;">
                            <tr>
                                <td style="padding: 10px; background-color: #f5f5f5; font-weight: bold; width: 150px;">
                                    👤 Nombre:
                                </td>
                                <td style="padding: 10px;">
                                    {nombre}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; background-color: #f5f5f5; font-weight: bold;">
                                    📧 Email:
                                </td>
                                <td style="padding: 10px;">
                                    <a href="mailto:{email}" style="color: #ff6b35; text-decoration: none;">
                                        {email}
                                    </a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; background-color: #f5f5f5; font-weight: bold;">
                                    📱 Teléfono:
                                </td>
                                <td style="padding: 10px;">
                                    {telefono if telefono else 'No proporcionado'}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; background-color: #f5f5f5; font-weight: bold;">
                                    📝 Asunto:
                                </td>
                                <td style="padding: 10px;">
                                    {asunto}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; background-color: #f5f5f5; font-weight: bold;">
                                    🕐 Fecha:
                                </td>
                                <td style="padding: 10px;">
                                    {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                                </td>
                            </tr>
                        </table>
                        
                        <h3 style="color: #013220; border-bottom: 2px solid #ff6b35; padding-bottom: 10px; margin-top: 30px;">
                            💬 Mensaje:
                        </h3>
                        <div style="background-color: #f9f9f9; padding: 20px; border-left: 4px solid #ff6b35; margin: 20px 0;">
                            <p style="margin: 0; white-space: pre-wrap;">{mensaje}</p>
                        </div>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #666;">
                            <p style="margin: 5px 0;">
                                <strong>José Alejandro</strong> - Desarrollo de Aplicaciones Seguras
                            </p>
                            <p style="margin: 5px 0; font-size: 12px;">
                                Este mensaje fue enviado desde el formulario de contacto de tu sitio web
                            </p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Adjuntar el HTML
        msg.attach(MIMEText(html_body, 'html'))
        
        # Conectar y enviar
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_sender, email_password)
            server.send_message(msg)
        
        return True, "✅ ¡Mensaje enviado exitosamente! Te responderé pronto."
        
    except KeyError:
        return False, "❌ Error: Configuración de email no encontrada en secrets.toml"
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Error de autenticación. Verifica las credenciales del email."
    except Exception as e:
        return False, f"❌ Error al enviar email: {str(e)}"

def save_contact_to_sheets(client, nombre, email, telefono, asunto, mensaje):
    """
    Guardar mensaje de contacto en Google Sheets
    """
    try:
        # Obtener o crear el archivo de Google Sheets
        try:
            sheet = client.open("autenticacion")
        except gspread.SpreadsheetNotFound:
            sheet = client.create("autenticacion")
        
        # Obtener o crear la hoja "mensajes_contacto"
        try:
            worksheet = sheet.worksheet("mensajes_contacto")  # ✅ Usar worksheet() para buscar por nombre
        except gspread.WorksheetNotFound:
            # Si no existe, crearla
            worksheet = sheet.add_worksheet(title="mensajes_contacto", rows="1000", cols="6")
            # Agregar encabezados
            worksheet.update('A1:F1', [['Fecha', 'Nombre', 'Email', 'Teléfono', 'Asunto', 'Mensaje']])
        
        # Agregar nuevo mensaje
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([fecha, nombre, email, telefono, asunto, mensaje])
        
        return True, "✅ ¡Mensaje guardado exitosamente! Te responderé pronto."
        
    except Exception as e:
        return False, f"❌ Error al guardar mensaje: {str(e)}"


def hash_password(password):
    """Encriptar contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_or_create_auth_sheet(client):
    """Obtener o crear la hoja de autenticación"""
    try:
        sheet = client.open("autenticacion")
    except gspread.SpreadsheetNotFound:
        # Crear nueva hoja de cálculo
        sheet = client.create("autenticacion")
        worksheet = sheet.get_worksheet(0)
        # Configurar encabezados
        worksheet.update('A1:E1', [['Email', 'Password', 'Nombre', 'Fecha_Registro', 'Ultimo_Acceso']])
    return sheet

def register_user(client, email, password, nombre):
    """Registrar nuevo usuario"""
    try:
        sheet = get_or_create_auth_sheet(client)
        worksheet = sheet.get_worksheet(0)
        
        # Verificar si el usuario ya existe
        users = worksheet.get_all_records()
        if any(user['Email'] == email for user in users):
            return False, "El email ya está registrado"
        
        # Agregar nuevo usuario
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        password_hash = hash_password(password)
        worksheet.append_row([email, password_hash, nombre, fecha_registro, ""])
        
        return True, "Usuario registrado exitosamente"
    except Exception as e:
        return False, f"Error al registrar usuario: {str(e)}"

def login_user(client, email, password):
    """Iniciar sesión"""
    try:
        sheet = get_or_create_auth_sheet(client)
        worksheet = sheet.get_worksheet(0)
        
        users = worksheet.get_all_records()
        password_hash = hash_password(password)
        
        for idx, user in enumerate(users):
            if user['Email'] == email and user['Password'] == password_hash:
                # Actualizar último acceso
                ultimo_acceso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worksheet.update_cell(idx + 2, 5, ultimo_acceso)
                return True, user['Nombre']
        
        return False, "Email o contraseña incorrectos"
    except Exception as e:
        return False, f"Error al iniciar sesión: {str(e)}"

# Cargar el logo
logo_base64 = get_image_base64("logo.png")

# Cargar imagen de fondo (la imagen que adjuntaste)
background_image = get_image_base64("background_tech.jpg")

# CSS personalizado
st.markdown(f"""
<style>
    /* Importar fuente sans-serif moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    /* Estilos generales */
    .stApp {{
        background-color: #013220;
    }}
    
    /* Ocultar elementos de Streamlit */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    .stFileUploader {{display: none;}}
    
    /* Navbar */
    .navbar {{
        background-color: #016b3a;
        padding: 1.5rem 3rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #ff6b35;
        margin-bottom: 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }}
    
    .brand {{
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }}
    
    .brand-logo {{
        height: 180px;
        width: auto;
        display: block;
    }}
    
    .nav-links {{
        display: flex;
        gap: 2.5rem;
    }}
    
    .nav-link {{
        color: white;
        text-decoration: none;
        font-size: 1rem;
        font-weight: 500;
        transition: color 0.3s;
        cursor: pointer;
    }}
    
    .nav-link:hover {{
        color: #ff6b35;
    }}
    
    /* Botón de login circular */
    .login-btn-container {{
        display: flex;
        align-items: center;
        justify-content: flex-end;
    }}
    
    /* Hero Section con imagen de fondo */
    .hero-container {{
        background: linear-gradient(rgba(1, 50, 32, 0.85), rgba(1,20, 232, 0.45)), 
                    url('data:image/jpeg;base64,{background_image if background_image else ""}') center/cover;
        padding: 4rem 2rem 3rem 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
        min-height: 50vh;
        background-attachment: fixed;
        background-size: cover;
        background-position: center center;
        background-repeat: no-repeat;
    }}
    
    .hero-container::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(1, 107, 58, 0.3) 0%, rgba(255, 107, 53, 0.2) 100%);
        pointer-events: none;
    }}
    
    .hero-content {{
        position: relative;
        z-index: 1;
    }}
    
    .profile-photo {{
        width: 350px;
        height: 350px;
        border-radius: 50%;
        object-fit: cover;
        border: 5px solid #ff6b35;
        margin: 0 auto 2rem auto;
        display: block;
        box-shadow: 0 10px 40px rgba(255, 107, 53, 0.5);
        background-color: #025230;
    }}
    
    .hero-title {{
        color: white;
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1.5rem;
        line-height: 1.2;
        letter-spacing: -1px;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
    }}
    
    .hero-subtitle {{
        color: #e8e8e8;
        font-size: 1.3rem;
        font-weight: 400;
        line-height: 1.8;
        max-width: 900px;
        margin: 0 auto 3rem auto;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
    }}
    
    /* Galería Section */
    .gallery-section {{
        background-color: #ff6b35;
        padding: 4rem 2rem;
        margin-top: 0;
    }}
    
    .section-title {{
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 3rem;
        letter-spacing: -0.5px;
    }}
    
    .video-container {{
        background-color: #f8f9fa;
        border-radius: 15px;
        padding: 1.5rem;
        height: 100%;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: transform 0.3s, box-shadow 0.3s;
    }}
    
    .video-container:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.2);
    }}
    
    .video-placeholder {{
        width: 100%;
        aspect-ratio: 16/9;
        background: linear-gradient(135deg, #013220 0%, #025230 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }}
    
    .video-placeholder::before {{
        content: '▶';
        font-size: 4rem;
        color: white;
        opacity: 0.7;
        transition: all 0.3s;
    }}
    
    .video-container:hover .video-placeholder::before {{
        opacity: 1;
        transform: scale(1.1);
    }}
    
    .video-title {{
        color: white;
        font-size: 1.3rem;
        font-weight: 600;
        text-align: center;
        margin-top: 1rem;
    }}
    
    /* Proyectos Section */
    .projects-section {{
        background-color: #f5f5f5;
        padding: 4rem 2rem;
    }}
    
    .project-card {{
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: transform 0.3s, box-shadow 0.3s;
        height: 100%;
        margin-bottom: 1.5rem;
    }}
    
    .project-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.2);
    }}
    
    .project-image {{
        width: 100%;
        height: 200px;
        background: linear-gradient(135deg, #013220 0%, #025230 100%);
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }}
    
    .project-title {{
        color: #013220;
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }}
    
    .project-description {{
        color: #555;
        font-size: 1rem;
        line-height: 1.7;
        margin-bottom: 1rem;
    }}
    
    .project-tags {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }}
    
    .project-tag {{
        background-color: #ff6b35;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }}
    
    /* Servicios Section */
    .services-section {{
        background-color: #ff6b35;
        padding: 4rem 2rem;
    }}
    
    .services-title {{
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 3rem;
        letter-spacing: -0.5px;
    }}
    
    .service-card {{
        background-color: white;
        padding: 2.5rem;
        border-radius: 15px;
        text-align: center;
        transition: all 0.3s;
        height: 100%;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }}
    
    .service-card:hover {{
        transform: translateY(-10px);
        box-shadow: 0 15px 40px rgba(0,0,0,0.2);
    }}
    
    .service-icon {{
        font-size: 3.5rem;
        margin-bottom: 1.5rem;
    }}
    
    .service-title {{
        color: #013220;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }}
    
    .service-description {{
        color: #555;
        font-size: 1rem;
        line-height: 1.7;
    }}
    
    /* Contacto Section */
    .contact-section {{
        background-color: #013220;
        padding: 4rem 2rem;
    }}
    
    .contact-title {{
        color: #ff6b35;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 3rem;
        letter-spacing: -0.5px;
    }}
    
    .contact-card {{
        background-color: white;
        padding: 3rem;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        margin-bottom: 2rem;
    }}
    
    .contact-info {{
        color: #013220;
        font-size: 1.1rem;
        line-height: 2.5;
    }}
    
    .contact-info strong {{
        color: #ff6b35;
        font-weight: 600;
    }}
    
    .contact-info p {{
        margin: 0.5rem 0;
    }}
    
    /* Login/Auth Section */
    .auth-section {{
        background-color: #013220;
        padding: 4rem 2rem;
        min-height: 20vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    
    .auth-card {{
        background-color: white;
        padding: 3rem;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        max-width: 500px;
        width: 60%;
        margin: 0 auto;
    }}
    
    .auth-title {{
        color: white;
        font-size: 2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 2rem;
    }}
    
    .auth-subtitle {{
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
        font-size: 1.95rem;
    }}
    
    .tab-container {{
        display: flex;
        gap: 1rem;
        margin-bottom: 2rem;
        border-bottom: 2px solid #e0e0e0;
    }}
    
    .tab-button {{
        flex: 1;
        padding: 1rem;
        background: none;
        border: none;
        color: #555;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        border-bottom: 3px solid transparent;
    }}
    
    .tab-button.active {{
        color: #ff6b35;
        border-bottom-color: #ff6b35;
    }}
    
    /* Botones de Streamlit personalizados */
    .stButton > button {{
        background-color: transparent;
        color: white;
        border: none;
        font-weight: 500;
        font-size: 1rem;
        padding: 0.5rem 1rem;
        transition: color 0.3s;
    }}
    
    .stButton > button:hover {{
        color: #ff6b35;
        background-color: transparent;
        border: none;
    }}
    
    /* Botón circular de login */
    div[data-testid="column"]:last-child .stButton > button {{
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background-color: #ff6b35;
        color: white;
        font-size: 1.2rem;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    
    div[data-testid="column"]:last-child .stButton > button:hover {{
        background-color: #ff8555;
        transform: scale(1.1);
    }}
    
    /* Formulario */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {{
        background-color: #f8f9fa;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        color: black;
        font-size: 1.5rem;
        padding: 0.75rem;
    }}
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: #ff6b35;
        box-shadow: 0 0 0 2px rgba(255, 107, 53, 0.1);
    }}
    
    /* Botón de enviar */
    div[data-testid="stFormSubmitButton"] > button {{
        background-color: #ff6b35;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1.1rem;
        transition: all 0.3s;
        width: 100%;
    }}
    
    div[data-testid="stFormSubmitButton"] > button:hover {{
        background-color: #ff8555;
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(255, 107, 53, 0.3);
    }}
    
    /* Footer */
    .footer {{
        text-align: center;
        padding: 2.5rem;
        color: white;
        background-color: #013220;
        border-top: 2px solid #ff6b35;
        font-size: 0.95rem;
    }}
    
    .footer p {{
        margin: 0.5rem 0;
    }}
    
    /* MEDIA QUERIES PARA RESPONSIVE DESIGN */
    @media screen and (max-width: 768px) {{
        .brand-logo {{
            height: 45px;
        }}
        
        .hero-container {{
            padding: 2rem 1rem;
        }}
        
        .profile-photo {{
            width: 180px;
            height: 180px;
        }}
        
        .hero-title {{
            font-size: 2.5rem;
        }}
        
        .hero-subtitle {{
            font-size: 1.1rem;
            padding: 0 1rem;
        }}
        
        .section-title {{
            font-size: 2rem;
        }}
        
        .services-title {{
            font-size: 2rem;
        }}
        
        .contact-title {{
            font-size: 2rem;
        }}
        
        .gallery-section,
        .services-section,
        .contact-section,
        .projects-section {{
            padding: 3rem 1rem;
        }}
        
        .service-card {{
            padding: 2rem;
            margin-bottom: 1rem;
        }}
        
        .contact-card {{
            padding: 2rem;
        }}
        
        .video-title {{
            font-size: 1.1rem;
        }}
        
        .auth-card {{
            padding: 2rem;
        }}
    }}
    
    @media screen and (max-width: 480px) {{
        .brand-logo {{
            height: 40px;
        }}
        
        .navbar {{
            padding: 1rem 1rem;
        }}
        
        .stButton > button {{
            font-size: 0.85rem;
            padding: 0.4rem 0.6rem;
        }}
        
        div[data-testid="column"]:last-child .stButton > button {{
            width: 45px;
            height: 45px;
            font-size: 1rem;
        }}
        
        .hero-container {{
            padding: 1.5rem 0.5rem;
        }}
        
        .profile-photo {{
            width: 150px;
            height: 150px;
            border: 3px solid #ff6b35;
        }}
        
        .hero-title {{
            font-size: 1.8rem;
            margin-bottom: 1rem;
        }}
        
        .hero-subtitle {{
            font-size: 1rem;
            padding: 0 0.5rem;
            line-height: 1.6;
        }}
        
        .section-title {{
            font-size: 1.6rem;
            margin-bottom: 2rem;
        }}
        
        .services-title {{
            font-size: 1.6rem;
            margin-bottom: 2rem;
        }}
        
        .contact-title {{
            font-size: 1.6rem;
            margin-bottom: 2rem;
        }}
        
        .auth-title {{
            font-size: 1.6rem;
        }}
        
        .gallery-section,
        .services-section,
        .contact-section,
        .projects-section {{
            padding: 2rem 0.5rem;
        }}
        
        .video-container {{
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        
        .video-placeholder::before {{
            font-size: 3rem;
        }}
        
        .video-title {{
            font-size: 1rem;
        }}
        
        .service-card {{
            padding: 1.5rem;
            margin-bottom: 1rem;
        }}
        
        .service-icon {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
        }}
        
        .service-title {{
            font-size: 1.2rem;
        }}
        
        .service-description {{
            font-size: 0.9rem;
        }}
        
        .contact-card {{
            padding: 1.5rem;
        }}
        
        .contact-card h3 {{
            font-size: 1.8rem !important;
        }}
        
        .contact-info {{
            font-size: 0.95rem;
            line-height: 2.2;
        }}
        
        .auth-card {{
            padding: 1.5rem;
        }}
        
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {{
            font-size: 0.9rem;
            padding: 0.6rem;
        }}
        
        div[data-testid="stFormSubmitButton"] > button {{
            font-size: 1rem;
            padding: 0.6rem 1.5rem;
        }}
        
        .footer {{
            padding: 1.5rem;
            font-size: 0.85rem;
        }}
    }}
    
    @media screen and (max-width: 360px) {{
        .brand-logo {{
            height: 35px;
        }}
        
        .hero-title {{
            font-size: 1.5rem;
        }}
        
        .hero-subtitle {{
            font-size: 0.9rem;
        }}
        
        .section-title,
        .services-title,
        .contact-title {{
            font-size: 1.4rem;
        }}
        
        .profile-photo {{
            width: 120px;
            height: 120px;
        }}
        
        div[data-testid="column"]:last-child .stButton > button {{
            width: 40px;
            height: 40px;
            font-size: 0.9rem;
        }}
    }}
</style>
""", unsafe_allow_html=True)

# Inicializar session state
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

if 'auth_tab' not in st.session_state:
    st.session_state.auth_tab = 'login'

def set_page(page_name):
    st.session_state.page = page_name

def logout():
    st.session_state.authenticated = False
    st.session_state.user_name = ""
    st.session_state.page = 'inicio'

# Navbar - ACTUALIZADO CON PROYECTOS
nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6 = st.columns([2, 1, 1, 1, 1, 0.5])

with nav_col1:
    if logo_base64:
        st.markdown(f'<img src="data:image/png;base64,{logo_base64}" class="brand-logo" alt="Un Futuro Mas Seguro">', unsafe_allow_html=True)
    else:
        st.markdown('<div class="brand">Un Futuro mas Seguro</div>', unsafe_allow_html=True)

with nav_col2:
    if st.button("Inicio", key="nav_inicio", use_container_width=True):
        set_page('inicio')

with nav_col3:
    if st.button("Servicios", key="nav_servicios", use_container_width=True):
        set_page('servicios')

with nav_col4:
    if st.button("Proyectos", key="nav_proyectos", use_container_width=True):
        set_page('proyectos')

with nav_col5:
    if st.button("Contacto", key="nav_contacto", use_container_width=True):
        set_page('contacto')

with nav_col6:
    if st.session_state.authenticated:
        if st.button("🚪", key="nav_logout", use_container_width=True, help="Cerrar Sesión"):
            logout()
            st.rerun()
    else:
        if st.button("👤", key="nav_login", use_container_width=True, help="Iniciar Sesión"):
            set_page('auth')

# Contenido según la página
if st.session_state.page == 'auth' and not st.session_state.authenticated:
    st.markdown('<div class="auth-section">', unsafe_allow_html=True)
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    
    # Tabs para Login y Registro
    tab1, tab2 = st.tabs(["🔓 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        st.markdown('<h2 class="auth-title">Bienvenido de nuevo</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Ingresa tus credenciales para continuar</p>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            email_login = st.text_input("📧 Email", placeholder="tucorreo@ejemplo.com", key="email_login")
            password_login = st.text_input("🔒 Contraseña", type="password", placeholder="Tu contraseña", key="password_login")
            
            submit_login = st.form_submit_button("Iniciar Sesión")
            
            if submit_login:
                if email_login and password_login:
                    # Cargar credenciales
                    creds, config = load_credentials_from_toml()
                    if creds:
                        client = get_google_sheets_connection(creds)
                        if client:
                            success, message = login_user(client, email_login, password_login)
                            if success:
                                st.session_state.authenticated = True
                                st.session_state.user_name = message
                                st.session_state.page = 'inicio'
                                st.success(f"✅ ¡Bienvenido {message}!")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                else:
                    st.error("❌ Por favor completa todos los campos")
    
    with tab2:
        st.markdown('<h2 class="auth-title">Crear cuenta nueva</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Completa el formulario para registrarte</p>', unsafe_allow_html=True)
        
        with st.form("register_form"):
            nombre_reg = st.text_input("👤 Nombre completo", placeholder="Tu nombre completo", key="nombre_reg")
            email_reg = st.text_input("📧 Email", placeholder="tucorreo@ejemplo.com", key="email_reg")
            password_reg = st.text_input("🔒 Contraseña", type="password", placeholder="Mínimo 6 caracteres", key="password_reg")
            password_confirm = st.text_input("🔒 Confirmar contraseña", type="password", placeholder="Confirma tu contraseña", key="password_confirm")
            
            submit_register = st.form_submit_button("Registrarse")
            
            if submit_register:
                if nombre_reg and email_reg and password_reg and password_confirm:
                    if password_reg != password_confirm:
                        st.error("❌ Las contraseñas no coinciden")
                    elif len(password_reg) < 6:
                        st.error("❌ La contraseña debe tener al menos 6 caracteres")
                    else:
                        # Cargar credenciales
                        creds, config = load_credentials_from_toml()
                        if creds:
                            client = get_google_sheets_connection(creds)
                            if client:
                                success, message = register_user(client, email_reg, password_reg, nombre_reg)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.info("👉 Ahora puedes iniciar sesión con tus credenciales")
                                else:
                                    st.error(f"❌ {message}")
                else:
                    st.error("❌ Por favor completa todos los campos")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == 'inicio':
    # Hero Section con foto de perfil e imagen de fondo
    st.markdown('<div class="hero-container">', unsafe_allow_html=True)
    st.markdown('<div class="hero-content">', unsafe_allow_html=True)
    
    if st.session_state.authenticated:
        st.markdown(f'<p style="color: #ff6b35; text-align: center; font-size: 1.2rem; margin-bottom: 1rem;">👋 Hola, {st.session_state.user_name}</p>', unsafe_allow_html=True)
    
    # Cargar y mostrar la imagen del usuario usando base64
    img_base64 = get_image_base64("jagt.jpg")
    
    if img_base64:
        st.markdown(f"""
            <img src="data:image/jpeg;base64,{img_base64}" class="profile-photo" alt="José Alejandro">
        """, unsafe_allow_html=True)
    else:
        # Si no encuentra la imagen, mostrar el placeholder SVG
        st.markdown("""
            <svg class="profile-photo" viewBox="0 0 250 250" xmlns="http://www.w3.org/2000/svg">
                <circle cx="125" cy="125" r="125" fill="#025230"/>
                <circle cx="125" cy="95" r="40" fill="#ff6b35"/>
                <path d="M 50 170 Q 125 130 200 170 L 200 250 L 50 250 Z" fill="#ff6b35"/>
            </svg>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        <h1 class="hero-title">¡Hola Bienvenido(a), soy José Alejandro</h1>
        <p class="hero-subtitle">
            Desarrollo Aplicaciones Seguras a la medida para tu Negocio o Actividad personal. 
            Manejo de herramientas digitales y negocios online. Asesoramiento en IA.
        </p>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Galería de Contenido
    st.markdown('<div class="gallery-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">Galería de Contenido</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown('<div class="video-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="video-title">Desarrollo de Aplicaciones Web</h3>', unsafe_allow_html=True)
        
        # Verificar si el video existe
        video_path = "video_condominio.mp4"
        if os.path.exists(video_path):
            video_file = open(video_path, 'rb')
            video_bytes = video_file.read()
            st.video(video_bytes)
        else:
            st.markdown("""
            <div class="video-placeholder"></div>
            <p style="text-align: center; color: #666; margin-top: 1rem;">
                Video no disponible. Coloca el archivo "video_condominio.mp4" en la carpeta raíz.
            </p>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="video-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="video-title">Desarrollo de Aplicaciones Web</h3>', unsafe_allow_html=True)
        # Verificar si el video existe
        video_path = "seguridad_digital.mp4"
        if os.path.exists(video_path):
            video_file = open(video_path, 'rb')
            video_bytes = video_file.read()
            st.video(video_bytes)
        else:
            st.markdown("""
            <div class="video-placeholder"></div>
            <p style="text-align: center; color: #666; margin-top: 1rem;">
                Video no disponible. Coloca el archivo "seguridad_digital.mp4" en la carpeta raíz.
            </p>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    #st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == 'proyectos':
    #st.markdown('<div class="projects-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">Mis Proyectos</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">Sistema de Gestión Empresarial</div>
            <div class="project-description">
                Plataforma integral para Administración de Conjuntos y/o Condominios, gestión de solicitudes, inventarios, ventas y facturación. 
                Desarrollada con Python y Streamlit, integrada con Google Sheets.
            </div>
            <div class="project-tags">
                <span class="project-tag">Python</span>
                <span class="project-tag">Streamlit</span>
                <span class="project-tag">Google API</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">E-commerce Seguro</div>
            <div class="project-description">
                Tiendas online con sistema de pagos integrado, gestión de productos y autenticación de usuarios. Diseño responsive y optimizado.
            </div>
            <div class="project-tags">
                <span class="project-tag">React</span>
                <span class="project-tag">Node.js</span>
                <span class="project-tag">Stripe</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">Dashboard Analytics</div>
            <div class="project-description">
                Sistema de análisis de datos en tiempo real con visualizaciones interactivas. 
                Conectado a múltiples fuentes de datos.
            </div>
            <div class="project-tags">
                <span class="project-tag">Python</span>
                <span class="project-tag">Pandas</span>
                <span class="project-tag">Plotly</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<br><br>', unsafe_allow_html=True)
    
    col4, col5, col6 = st.columns(3, gap="large")
    
    with col4:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">App Móvil de Productividad</div>
            <div class="project-description">
                Aplicación multiplataforma para gestión de tareas y proyectos. 
                Sincronización en la nube y notificaciones push.
            </div>
            <div class="project-tags">
                <span class="project-tag">React Native</span>
                <span class="project-tag">Firebase</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">Sistema de Reservas</div>
            <div class="project-description">
                Plataforma de reservas online con calendario interactivo, pagos 
                automatizados y notificaciones por email.
            </div>
            <div class="project-tags">
                <span class="project-tag">Django</span>
                <span class="project-tag">PostgreSQL</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
        <div class="project-card">
            <div class="project-image"></div>
            <div class="project-title">Portal Educativo</div>
            <div class="project-description">
                Plataforma de aprendizaje online con cursos, evaluaciones y 
                seguimiento de progreso. Interfaz intuitiva y accesible.
            </div>
            <div class="project-tags">
                <span class="project-tag">Vue.js</span>
                <span class="project-tag">Laravel</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == 'servicios':
    #st.markdown('<div class="services-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="services-title">Mis Servicios</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">💻</div>
            <div class="service-title">Desarrollo Web</div>
            <div class="service-description">
                Aplicaciones web modernas y responsivas, diseñadas con las últimas tecnologías 
                y enfocadas en la experiencia del usuario.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🔒</div>
            <div class="service-title">Seguridad Digital</div>
            <div class="service-description">
                Implementación de protocolos de seguridad, auditorías y protección de datos 
                para mantener tu negocio seguro.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🚀</div>
            <div class="service-title">Consultoría Digital</div>
            <div class="service-description">
                Asesoramiento en transformación digital, estrategias online y optimización 
                de procesos empresariales.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<br><br>', unsafe_allow_html=True)
    
    col4, col5, col6 = st.columns(3, gap="large")
    
    with col4:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">📱</div>
            <div class="service-title">Apps Móviles</div>
            <div class="service-description">
                Desarrollo de aplicaciones móviles nativas y multiplataforma para iOS y Android.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🎯</div>
            <div class="service-title">E-commerce</div>
            <div class="service-description">
                Tiendas online completas con sistemas de pago seguros y gestión de inventario.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🛠️</div>
            <div class="service-title">Mantenimiento</div>
            <div class="service-description">
                Soporte técnico continuo, actualizaciones y optimización de tus aplicaciones.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == 'contacto':
    st.markdown('<div class="contact-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="contact-title">Contáctame</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
        <div class="contact-card">
            <h3 style="color: #013220; margin-bottom: 2rem; font-size: 1.8rem;">Información de Contacto</h3>
            <div class="contact-info">
                <p><h3>📧 Email: josegarjagt@gmail.com</p></h3>
                <p><h3>📱 WhatsApp: +57 320 5511091</p></h3>
                <p><h3>📍 Ubicación:</strong> Bogota, Colombia - Ricaurte, Cundinamarca</p></h3>
                <p><strong>💼 LinkedIn:</strong> linkedin.com/in/</p>
                <p><strong>🙀 GitHub:</strong> github.com/</p>
                <p style="margin-top: 2rem; padding-top: 2rem; border-top: 2px solid #f0f0f0;">
                    <h3>Horario de atención:<br>
                    Lunes a Sabado: 8:00 AM - 6:00 PM<br>
                    Respuesta en menos de 24 horas</h3>
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown('<h3 style="color: #ff6b35; margin-bottom: 2rem; font-size: 1.8rem;">Envíame un mensaje</h3>', unsafe_allow_html=True)
        
        with st.form("contact_form", clear_on_submit=True):
            nombre = st.text_input("Nombre completo *", placeholder="Tu nombre")
            email = st.text_input("Email *", placeholder="tucorreo@ejemplo.com")
            telefono = st.text_input("Teléfono", placeholder="+57 300 000-0000")
            asunto = st.text_input("Asunto *", placeholder="¿En qué puedo ayudarte?")
            mensaje = st.text_area("Mensaje *", placeholder="Cuéntame sobre tu proyecto...", height=150)
            
            submitted = st.form_submit_button("Enviar Mensaje")
            
            if submitted:
                if nombre and email and asunto and mensaje:
                    # Mostrar spinner mientras se envía
                    with st.spinner('Enviando mensaje...'):
                        
                        # OPCIÓN 1: Enviar por Gmail
                        success, message = send_email_gmail(nombre, email, telefono, asunto, mensaje)
                        
                        # OPCIÓN 2: Enviar por SendGrid (recomendado)
                        # success, message = send_email_sendgrid(nombre, email, telefono, asunto, mensaje)
                        
                        # OPCIÓN 3: Guardar en Google Sheets (respaldo)
                        creds, config = load_credentials_from_toml()
                        if creds:
                            client = get_google_sheets_connection(creds)
                            if client:
                                success, message = save_contact_to_sheets(
                                    client, nombre, email, telefono, asunto, mensaje
                                )
                                
                                if success:
                                    st.success(message)
                                    st.info("📧 También recibirás una confirmación por email")
                                else:
                                    st.error(message)
                            else:
                                st.error("❌ Error al conectar con Google Sheets")
                        else:
                            st.error("❌ Error al cargar credenciales")
                else:
                    st.error("❌ Por favor completa todos los campos marcados con *")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="footer">
    <p><strong>José Alejandro</strong> - Desarrollo de Aplicaciones Seguras</p>
    <p>© 2025 Todos los derechos reservados | Transformando ideas en soluciones digitales</p>
</div>
""", unsafe_allow_html=True)
