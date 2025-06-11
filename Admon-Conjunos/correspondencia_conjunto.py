import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from googleapiclient.errors import HttpError
from datetime import datetime, date
import time
import ssl
from googleapiclient.errors import HttpError
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(
#    page_title="📮 Gestión de Correspondencia",
#    page_icon="📮",
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
            st.success(f"✅ Conexión exitosa y disponible!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
        
        return client
    
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

# Función para enviar correo electrónico
def send_email_to_resident(email_to, nombre, asunto, mensaje, tipo_mensaje="Correspondencia"):
    """
    Envía correo electrónico a residentes
    """
    try:
        # Validar entrada de datos
        if not email_to or not nombre or not asunto or not mensaje:
            return False, "Error: Faltan datos requeridos (email, nombre, asunto o mensaje)"
        
        # Configuración del servidor SMTP utilizando st.secrets
        smtp_server = 'smtp.gmail.com'
        smtp_port = 465
        
        # Asegurarse de tener las credenciales necesarias
        if 'emails' not in st.secrets or 'smtp_user' not in st.secrets['emails'] or 'smtp_password' not in st.secrets['emails']:
            return False, "Error: Faltan credenciales de correo en secrets.toml"
            
        smtp_user = st.secrets['emails']['smtp_user']
        smtp_password = st.secrets['emails']['smtp_password']
        
        # Crear mensaje
        message = MIMEMultipart()
        message['From'] = smtp_user
        message['To'] = email_to
        message['Subject'] = asunto
        
        # Contenido del correo basado en el tipo de mensaje
        if tipo_mensaje == "Correspondencia":
            icon = "📮"
            color = "#2E86AB"
        elif tipo_mensaje == "Anuncio General":
            icon = "📢"
            color = "#2E86AB"
        elif tipo_mensaje == "Aviso Importante":
            icon = "⚠️"
            color = "#F18F01"
        elif tipo_mensaje == "Recordatorio":
            icon = "⏰"
            color = "#C73E1D"
        elif tipo_mensaje == "Convocatoria":
            icon = "📋"
            color = "#A23B72"
        else:  # Mensaje Individual
            icon = "💬"
            color = "#4A90E2"
        
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
        .message-box {{
            background-color: white;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid {color};
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>{icon} {tipo_mensaje}</h2>
        <h3>{asunto}</h3>
    </div>
    <div class="content">
        <p>Estimado(a) <b>{nombre}</b>,</p>
        <div class="message-box">
            <p>{mensaje}</p>
        </div>
        <p><b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    </div>
    <div class="footer">
        <p>Administración del Conjunto Residencial<br>
        Este es un mensaje automático, por favor no responder a este correo.</p>
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
        server.sendmail(smtp_user, email_to, text)
        server.quit()
        
        return True, "Correo enviado exitosamente"
        
    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación con el servidor SMTP. Verifique las credenciales."
    except smtplib.SMTPServerDisconnected:
        return False, "Desconexión del servidor SMTP. Verifique su conexión a internet."
    except smtplib.SMTPSenderRefused:
        return False, "Remitente rechazado por el servidor. Verifique la dirección de correo remitente."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Destinatario rechazado por el servidor. Verifique la dirección de correo: {email_to}"
    except smtplib.SMTPDataError:
        return False, "Error en los datos del mensaje. Verifique el contenido del correo."
    except smtplib.SMTPConnectError:
        return False, "Error al conectar con el servidor SMTP. Verifique su conexión a internet y la configuración del servidor."
    except smtplib.SMTPException as e:
        return False, f"Error SMTP general: {str(e)}"
    except FileNotFoundError as e:
        return False, f"Error al enviar correo - Archivo no encontrado: {str(e)}"
    except Exception as e:
        return False, f"Error al enviar correo: {str(e)}"

def get_resident_email(client, destinatario, apartamento):
    """Obtener email del residente desde la hoja de residentes"""
    try:
        spreadsheet = client.open("gestion-conjuntos")
        
        # Buscar en la hoja de residentes
        try:
            worksheet = spreadsheet.worksheet("Control_Residentes")
            data = worksheet.get_all_records()
            
            if data:
                df_residentes = pd.DataFrame(data)
                
                # Buscar por nombre y apartamento
                resident = df_residentes[(df_residentes['Nombre'].str.contains(destinatario, case=False, na=False)) | (df_residentes['Apellido'].str.contains(destinatario, case=False, na=False)) | (df_residentes['Unidad'].astype(str) == str(apartamento))]
                
                if not resident.empty:
                    email = resident.iloc[0].get('Email', '').strip()
                    return email if email else None
                    
        except gspread.WorksheetNotFound:
            # Si no existe la hoja de residentes, devolver None
            return None
            
        return None
        
    except Exception as e:
        st.warning(f"Error al buscar email del residente: {str(e)}")
        return None

def send_correspondence_notification(client, correspondencia_data):
    """Enviar notificación por email sobre nueva correspondencia"""
    try:
        # Obtener email del residente
        email_residente = get_resident_email(client, correspondencia_data['Destinatario'], correspondencia_data['Apartamento'])
        
        if not email_residente:
            return False, "No se encontró email del residente"
        
        # Preparar datos del mensaje
        asunto = f"📮 Nueva Correspondencia - {correspondencia_data['Tipo_Correspondencia']}"
        
        mensaje = f"""
        <p>Hemos recibido nueva correspondencia para usted:</p>
        
        <ul>
            <li><b>Tipo:</b> {correspondencia_data['Tipo_Correspondencia']}</li>
            <li><b>Remitente:</b> {correspondencia_data['Remitente']}</li>
            <li><b>Fecha de Recepción:</b> {correspondencia_data['Fecha_Recepcion']}</li>
            <li><b>Descripción:</b> {correspondencia_data['Descripcion']}</li>
            <li><b>ID de seguimiento:</b> {correspondencia_data['ID']}</li>
        </ul>
        
        <p>La correspondencia está disponible para retiro en portería durante el horario de atención.</p>
        
        <p><b>Horario de Portería:</b><br>
        - Lunes a Viernes: 6:00 AM - 10:00 PM<br>
        - Sábados y Domingos: 8:00 AM - 8:00 PM</p>
        
        <p>Por favor presente su cédula al momento del retiro.</p>
        """
        
        # Enviar email
        return send_email_to_resident(
            email_residente, 
            correspondencia_data['Destinatario'], 
            asunto, 
            mensaje, 
            "Correspondencia"
        )
        
    except Exception as e:
        return False, f"Error al enviar notificación: {str(e)}"

#@st.cache_data(ttl=60)
def load_correspondencia_data(client):
  """Cargar datos de correspondencia desde Google Sheets"""
  for intento in range(MAX_RETRIES):
    try:
      with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
        spreadsheet = client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Correspondencia")
        
        # Obtener todos los datos
        data = worksheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            
            # FIX: Manejo seguro de fechas
            # Convertir fechas de manera más robusta
            for col in ['Fecha_Recepcion', 'Fecha_Entrega']:
                if col in df.columns:
                    # Reemplazar valores vacíos con None antes de la conversión
                    df[col] = df[col].replace('', None)
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df
        else:
            # Si no hay datos, crear DataFrame vacío con las columnas esperadas
            columns = [
                'ID', 'Fecha_Recepcion', 'Destinatario', 'Apartamento', 'Torre', 
                'Tipo_Correspondencia', 'Remitente', 'Descripcion', 'Estado', 
                'Fecha_Entrega', 'Entregado_Por', 'Recibido_Por', 'Observaciones'
            ]
            df_empty = pd.DataFrame(columns=columns)
            # Asegurar que las columnas de fecha sean datetime
            df_empty['Fecha_Recepcion'] = pd.to_datetime(df_empty['Fecha_Recepcion'])
            df_empty['Fecha_Entrega'] = pd.to_datetime(df_empty['Fecha_Entrega'])
            return df_empty
    
    except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                    time.sleep(delay)
                    continue
                else:
                    st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
            else:
                st.error(f"Error de la API: {str(error)}")
            return False
    
    except gspread.SpreadsheetNotFound:
        st.error("❌ Hoja de cálculo 'gestion-conjuntos' no encontrada")
        return None
    except gspread.WorksheetNotFound:
        st.error("❌ Hoja 'Correspondencia' no encontrada en el archivo 'gestion-conjuntos'")
        return None
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return None

def save_correspondencia_data(client, data):
    """Guardar datos de correspondencia en Google Sheets"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Guardando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                # FIX: Usar el mismo nombre que en load_correspondencia_data
                spreadsheet = client.open("gestion-conjuntos")
                
                try:
                    worksheet = spreadsheet.worksheet("Correspondencia")
                except gspread.WorksheetNotFound:
                    # Crear la hoja si no existe
                    worksheet = spreadsheet.add_worksheet(title="Correspondencia", rows="1000", cols="20")
                    # Agregar encabezados
                    headers = [
                        'ID', 'Fecha_Recepcion', 'Destinatario', 'Apartamento', 'Torre', 
                        'Tipo_Correspondencia', 'Remitente', 'Descripcion', 'Estado', 
                        'Fecha_Entrega', 'Entregado_Por', 'Recibido_Por', 'Observaciones'
                    ]
                    worksheet.append_row(headers)
                
                # Limpiar la hoja y agregar los datos
                worksheet.clear()
                
                # Convertir DataFrame a lista de listas
                if not data.empty:
                    # Convertir fechas a string para Google Sheets
                    data_copy = data.copy()
                    
                    # FIX: Manejo seguro de fechas
                    for col in ['Fecha_Recepcion', 'Fecha_Entrega']:
                        if col in data_copy.columns:
                            # Convertir a datetime si no lo es ya
                            data_copy[col] = pd.to_datetime(data_copy[col], errors='coerce')
                            # Convertir a string, manejando valores NaT y None
                            data_copy[col] = data_copy[col].apply(
                                lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else ''
                            )
                    
                    # Agregar encabezados
                    headers = data_copy.columns.tolist()
                    worksheet.append_row(headers)
                    
                    # Agregar datos
                    for _, row in data_copy.iterrows():
                        # Convertir valores NaN/None a string vacío
                        row_values = []
                        for val in row.tolist():
                            if pd.isna(val) or val is None:
                                row_values.append('')
                            else:
                                row_values.append(str(val))
                        worksheet.append_row(row_values)
                else:
                    # Solo agregar encabezados si no hay datos
                    headers = [
                        'ID', 'Fecha_Recepcion', 'Destinatario', 'Apartamento', 'Torre', 
                        'Tipo_Correspondencia', 'Remitente', 'Descripcion', 'Estado', 
                        'Fecha_Entrega', 'Entregado_Por', 'Recibido_Por', 'Observaciones'
                    ]
                    worksheet.append_row(headers)
                
                st.success("✅ Datos guardados exitosamente")
                return True
        
        except gspread.SpreadsheetNotFound:
            st.error("❌ Hoja de cálculo 'gestion-conjuntos' no encontrada")
            return False
            
        except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                    time.sleep(delay)
                    continue
                else:
                    st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
            else:
                st.error(f"Error de la API de Google: {str(error)}")
            return False

        except Exception as e:
            st.error(f"❌ Error guardando datos: {str(e)}")
            # Debug: mostrar el tipo de excepción
            st.error(f"Tipo de error: {type(e).__name__}")
            return False
    
    return False

def generar_id_correspondencia(df):
    """Generar ID único para nueva correspondencia"""
    if df.empty or 'ID' not in df.columns:
        return "CORR-001"
    
    # Obtener el último ID
    try:
        ids_numericos = df['ID'].str.extract(r'CORR-(\d+)')[0].astype(int)
        ultimo_id = ids_numericos.max()
        nuevo_id = f"CORR-{ultimo_id + 1:03d}"
        return nuevo_id
    except:
        return f"CORR-{len(df) + 1:03d}"

def correspondencia_main():
    st.title("📮 Sistema de Gestión de Correspondencia")
    st.markdown("### Conjunto Residencial - Control de Paquetes y Cartas")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("🏢 Menú Principal")
    opcion = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["📥 Recibir Correspondencia", "📊 Consultar Correspondencia", 
         "✅ Entregar Correspondencia", "📈 Dashboard", "📧 Notificaciones", "⚙️ Configuración"]
    )
    
    # Cargar datos
    df_correspondencia = load_correspondencia_data(client)
    if df_correspondencia is None:
        st.stop()
    
    if opcion == "📥 Recibir Correspondencia":
        st.header("📥 Registrar Nueva Correspondencia")
        
        col1, col2 = st.columns(2)
        
        with col1:
            destinatario = st.text_input("👤 Destinatario *", placeholder="Nombre completo del destinatario")
            apartamento = st.text_input("🏠 Apartamento *", placeholder="Ej: 101, 205A")
            torre = st.selectbox("🏗️ Torre", ["Torre A", "Torre B", "Torre C", "Torre D", "N/A"], index=4)
            tipo_correspondencia = st.selectbox(
                "📦 Tipo de Correspondencia *",
                ["Paquete", "Carta", "Revista", "Documento", "Telegrama", "Encomienda", "Otro"]
            )
        
        with col2:
            fecha_recepcion = st.date_input("📅 Fecha de Recepción", value=date.today())
            remitente = st.text_input("📤 Remitente", placeholder="Empresa o persona que envía")
            descripcion = st.text_area("📝 Descripción", placeholder="Detalles adicionales sobre la correspondencia")
            entregado_por = st.text_input("👮 Recibido por (Portería)", placeholder="Nombre del portero/vigilante")
        
        # Opción para enviar notificación por email
        enviar_notificacion = st.checkbox("📧 Enviar notificación por email al residente", value=True)
        
        st.markdown("---")
        
        if st.button("💾 Registrar Correspondencia", type="primary"):
            if destinatario and apartamento and tipo_correspondencia:
                # Generar nuevo ID
                nuevo_id = generar_id_correspondencia(df_correspondencia)
                
                # Crear nueva fila
                nueva_correspondencia = {
                    'ID': nuevo_id,
                    'Fecha_Recepcion': fecha_recepcion,
                    'Destinatario': destinatario,
                    'Apartamento': apartamento,
                    'Torre': torre if torre != "N/A" else "",
                    'Tipo_Correspondencia': tipo_correspondencia,
                    'Remitente': remitente,
                    'Descripcion': descripcion,
                    'Estado': 'Pendiente',
                    'Fecha_Entrega': None,
                    'Entregado_Por': entregado_por,
                    'Recibido_Por': "",
                    'Observaciones': ""
                }
                
                # Agregar al DataFrame
                if df_correspondencia.empty:
                    df_correspondencia = pd.DataFrame([nueva_correspondencia])
                else:
                    df_correspondencia = pd.concat([df_correspondencia, pd.DataFrame([nueva_correspondencia])], ignore_index=True)
                
                # Guardar en Google Sheets
                if save_correspondencia_data(client, df_correspondencia):
                    st.success(f"✅ Correspondencia registrada exitosamente con ID: {nuevo_id}")

                    # Enviar notificación por email si está habilitada
                    if enviar_notificacion:
                        with st.spinner("📧 Enviando notificación por email..."):
                            email_success, email_message = send_correspondence_notification(client, nueva_correspondencia)
                            
                            if email_success:
                                st.success("📧 Notificación enviada por email exitosamente")
                            else:
                                st.warning(f"⚠️ Correspondencia registrada pero no se pudo enviar email: {email_message}")

                    st.balloons()
                    time.sleep(2)
                    st.rerun()
            else:
                st.error("❌ Por favor completa todos los campos obligatorios (*)")
    
    elif opcion == "📊 Consultar Correspondencia":
        st.header("📊 Consultar Correspondencia")
        
        if df_correspondencia.empty:
            st.info("📭 No hay correspondencia registrada")
            return
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtro_estado = st.selectbox("Estado", ["Todos"] + df_correspondencia['Estado'].unique().tolist())
        
        with col2:
            filtro_tipo = st.selectbox("Tipo", ["Todos"] + df_correspondencia['Tipo_Correspondencia'].unique().tolist())
        
        with col3:
            filtro_apartamento = st.text_input("Apartamento", placeholder="Filtrar por apartamento")
        
        # Aplicar filtros
        df_filtrado = df_correspondencia.copy()
        
        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Estado'] == filtro_estado]
        
        if filtro_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Tipo_Correspondencia'] == filtro_tipo]
        
        if filtro_apartamento:
            df_filtrado = df_filtrado[df_filtrado['Apartamento'].str.contains(filtro_apartamento, case=False, na=False)]
        
        # Mostrar resultados
        st.markdown(f"**Total de registros: {len(df_filtrado)}**")
        
        if not df_filtrado.empty:
            # Formatear fechas para mostrar - manejo seguro
            df_display = df_filtrado.copy()
            for col in ['Fecha_Recepcion', 'Fecha_Entrega']:
                if col in df_display.columns:
                    # Convertir a datetime si no lo es ya
                    df_display[col] = pd.to_datetime(df_display[col], errors='coerce')
                    # Formatear a string
                    df_display[col] = df_display[col].apply(
                        lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else ''
                    )
            
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )

            # Opción para reenviar notificación
            st.markdown("### 📧 Reenviar Notificaciones")
            selected_rows = st.multiselect(
                "Seleccionar correspondencia para reenviar notificación:",
                options=df_filtrado['ID'].tolist(),
                format_func=lambda x: f"{x} - {df_filtrado[df_filtrado['ID'] == x]['Destinatario'].iloc[0]} (Apto: {df_filtrado[df_filtrado['ID'] == x]['Apartamento'].iloc[0]})"
            )
            
            if selected_rows and st.button("📧 Reenviar Notificaciones"):
                for corr_id in selected_rows:
                    row_data = df_filtrado[df_filtrado['ID'] == corr_id].iloc[0].to_dict()
                    email_success, email_message = send_correspondence_notification(client, row_data)
                    
                    if email_success:
                        st.success(f"✅ Notificación reenviada para {corr_id}")
                    else:
                        st.error(f"❌ Error enviando notificación para {corr_id}: {email_message}")

        else:
            st.info("🔍 No se encontraron registros con los filtros aplicados")
    
    elif opcion == "✅ Entregar Correspondencia":
        st.header("✅ Entregar Correspondencia")
        
        # Mostrar correspondencia pendiente
        correspondencia_pendiente = df_correspondencia[df_correspondencia['Estado'] == 'Pendiente']
        
        if correspondencia_pendiente.empty:
            st.info("📭 No hay correspondencia pendiente por entregar")
            return
        
        st.subheader("📋 Correspondencia Pendiente")
        
        # Crear una tabla más visual
        for _, row in correspondencia_pendiente.iterrows():
            with st.expander(f"🆔 {row['ID']} - {row['Destinatario']} (Apto: {row['Apartamento']})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Fecha Recepción:** {row['Fecha_Recepcion']}")
                    st.write(f"**Tipo:** {row['Tipo_Correspondencia']}")
                    st.write(f"**Remitente:** {row['Remitente']}")
                
                with col2:
                    st.write(f"**Torre:** {row['Torre']}")
                    st.write(f"**Descripción:** {row['Descripcion']}")
                    st.write(f"**Recibido por:** {row['Entregado_Por']}")
                
                # Formulario de entrega
                st.markdown("#### 📝 Registrar Entrega")
                fecha_entrega = st.date_input(f"Fecha de Entrega", value=date.today(), key=f"fecha_{row['ID']}")
                recibido_por = st.text_input(f"Recibido por", placeholder="Nombre de quien recibe", key=f"recibido_{row['ID']}")
                observaciones = st.text_area(f"Observaciones", placeholder="Comentarios adicionales", key=f"obs_{row['ID']}")
                
                if st.button(f"✅ Marcar como Entregado", key=f"entregar_{row['ID']}", type="primary"):
                    if recibido_por:
                        # Actualizar el registro
                        idx = df_correspondencia[df_correspondencia['ID'] == row['ID']].index[0]
                        df_correspondencia.loc[idx, 'Estado'] = 'Entregado'
                        df_correspondencia.loc[idx, 'Fecha_Entrega'] = fecha_entrega
                        df_correspondencia.loc[idx, 'Recibido_Por'] = recibido_por
                        df_correspondencia.loc[idx, 'Observaciones'] = observaciones
                        
                        # Guardar cambios
                        if save_correspondencia_data(client, df_correspondencia):
                            st.success(f"✅ Correspondencia {row['ID']} marcada como entregada")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("❌ Por favor indica quién recibió la correspondencia")
    
    elif opcion == "📈 Dashboard":
        st.header("📈 Dashboard de Correspondencia")
        
        if df_correspondencia.empty:
            st.info("📭 No hay datos disponibles para mostrar")
            return
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_correspondencia = len(df_correspondencia)
            st.metric("📦 Total Correspondencia", total_correspondencia)
        
        with col2:
            pendiente = len(df_correspondencia[df_correspondencia['Estado'] == 'Pendiente'])
            st.metric("⏳ Pendientes", pendiente)
        
        with col3:
            entregadas = len(df_correspondencia[df_correspondencia['Estado'] == 'Entregado'])
            st.metric("✅ Entregadas", entregadas)
        
        with col4:
            if total_correspondencia > 0:
                porcentaje_entrega = (entregadas / total_correspondencia) * 100
                st.metric("📊 % Entregadas", f"{porcentaje_entrega:.1f}%")
        
        st.markdown("---")
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Estado de Correspondencia")
            estado_counts = df_correspondencia['Estado'].value_counts()
            st.bar_chart(estado_counts)
        
        with col2:
            st.subheader("📦 Tipos de Correspondencia")
            tipo_counts = df_correspondencia['Tipo_Correspondencia'].value_counts()
            st.bar_chart(tipo_counts)
        
        # Correspondencia por fecha
        st.subheader("📅 Correspondencia por Fecha de Recepción")
        if 'Fecha_Recepcion' in df_correspondencia.columns and not df_correspondencia.empty:
            # Asegurar que sea datetime y filtrar valores válidos
            df_correspondencia['Fecha_Recepcion'] = pd.to_datetime(df_correspondencia['Fecha_Recepcion'], errors='coerce')
            df_fechas_validas = df_correspondencia[df_correspondencia['Fecha_Recepcion'].notna()]
            
            if not df_fechas_validas.empty:
                correspondencia_por_fecha = df_fechas_validas.groupby(df_fechas_validas['Fecha_Recepcion'].dt.date).size()
                st.line_chart(correspondencia_por_fecha)
            else:
                st.info("No hay fechas válidas para mostrar el gráfico")
    
    elif opcion == "⚙️ Configuración":
        st.header("⚙️ Configuración del Sistema")
        
        st.subheader("🔧 Opciones de Mantenimiento")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Actualizar Datos", help="Recargar datos desde Google Sheets"):
                st.cache_data.clear()
                st.success("✅ Datos actualizados")
                time.sleep(1)
                st.rerun()
        
        with col2:
            if st.button("📥 Descargar Backup", help="Descargar copia de seguridad en CSV"):
                if not df_correspondencia.empty:
                    csv = df_correspondencia.to_csv(index=False)
                    st.download_button(
                        label="💾 Descargar CSV",
                        data=csv,
                        file_name=f"correspondencia_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
        
        st.subheader("📊 Información del Sistema")
        
        info_cols = st.columns(2)
        with info_cols[0]:
            st.info(f"📦 Total de registros: {len(df_correspondencia)}")
            st.info(f"📅 Último registro: {df_correspondencia['Fecha_Recepcion'].max() if not df_correspondencia.empty else 'N/A'}")
        
        with info_cols[1]:
            st.info(f"🔗 Archivo: gestion-conjuntos")
            st.info(f"📋 Hoja: Correspondencia")

#if __name__ == "__main__":
#    correspondencia_main()