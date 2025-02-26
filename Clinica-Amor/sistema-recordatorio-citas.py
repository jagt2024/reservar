import streamlit as st
import pandas as pd
import smtplib
import time
import toml
import gspread
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import pywhatkit
import schedule
import threading
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Recordatorio de Citas AMO",
    page_icon="📅",
    layout="wide"
)

# Constantes para reintentos
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1

# Función para manejar llamadas a la API
def api_call_handler(func):
    try:
        return func()
    except gspread.exceptions.APIError as e:
        if e.response.status_code == 429:
            st.warning("Límite de cuota excedida. Esperando...")
            time.sleep(10)
            return func()
        else:
            raise e

def dataBookTelEnc(hoja, encargado):
  ws1 = datos_book[hoja]
  data = []
  for row in range(1,ws1.max_row):
    _row=[]
    for col in ws1.iter_cols(1,ws1.max_column):
        _row.append(col[row].value)
        data.append(_row) 
    #print(f'El encargado es {_row[0]}, su correo es {_row[1]}')
    if _row[0] == encargado:
       data = _row[2]
       break
  return data

# Función para cargar credenciales desde el archivo secrets.toml
def load_credentials_from_secrets():
    try:
        # Cargar desde la ubicación estándar de secretos de Streamlit
        return st.secrets["sheetsemp"]["credentials_sheet"]
    except Exception as e:
        st.error(f"Error al cargar las credenciales desde .streamlit/secrets.toml: {str(e)}")
        st.info("Verifique que el archivo secrets.toml existe en la carpeta .streamlit y tiene el formato correcto.")
        return None

# Función para obtener datos de Google Sheets
def get_google_sheet_data(creds):
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                credentials = Credentials.from_service_account_info(creds, scopes=scope)
                client = gspread.authorize(credentials)
                sheet = client.open('gestion-reservas-amo')
                worksheet = sheet.worksheet('reservas')
                data = api_call_handler(lambda: worksheet.get_all_values())
                
                if not data:
                    st.error("No se encontraron datos en la hoja de cálculo.")
                    return None, None
                
                df = pd.DataFrame(data[1:], columns=data[0])
                
                if df.empty:
                    st.error("El DataFrame está vacío después de cargar los datos.")
                    return None, None
                    
                # Convertir la columna de fecha a datetime
                df['FECHA'] = pd.to_datetime(df['FECHA'])
                
                return df, worksheet
                
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
            return None, None

        except Exception as e:
            st.error(f"Error al cargar los datos: {str(e)}")
            return None, None
    
    return None, None

# Función para enviar correo electrónico
def enviar_correo(destinatario, asunto, mensaje, remitente, password):
    try:
        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = asunto
        
        msg.attach(MIMEText(mensaje, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Error al enviar correo: {str(e)}")
        return False

# Función para enviar mensaje por WhatsApp
def enviar_whatsapp(numero, mensaje):
    try:
        # Formatear número de teléfono (eliminar el + si existe)
        if numero.startswith('+'):
            numero = numero[1:]
        
        # Obtener hora actual + 1 minuto para programar el envío
        ahora = datetime.now()
        hora = ahora.hour
        minuto = ahora.minute + 1
        
        # Ajustar si el minuto es mayor a 59
        if minuto >= 60:
            hora += 1
            minuto -= 60
        
        # Usar pywhatkit para enviar mensaje
        pywhatkit.sendwhatmsg(f"+{numero}", mensaje, hora, minuto, wait_time=35, tab_close=True)
        return True
    except Exception as e:
        st.error(f"Error al enviar WhatsApp: {str(e)}")
        return False

# Función para verificar las citas y enviar recordatorios
def verificar_citas(df_citas, config):
    ahora = datetime.now()
    
    # Filtrar citas para hoy y mañana
    for _, cita in df_citas.iterrows():
        fecha_cita = cita['FECHA'].date() if isinstance(cita['FECHA'], datetime) else datetime.strptime(cita['FECHA'], '%Y-%m-%d').date()
        hora_cita = cita['HORA']
        
        tel_encargado = dataBookTelEnc("encargado",{cita['ENCARGADO']})

        # Citas para mañana - enviar recordatorio hoy
        if fecha_cita == (ahora + timedelta(days=1)).date():
            # Recordatorio al paciente por correo
            if config['correo_activo'] and cita['EMAIL']:
                mensaje_paciente = f"""
                Estimado/a {cita['NOMBRE']},
                
                Le recordamos que tiene una cita programada para mañana {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} para el servicio de {cita['SERVICIOS']} con el/la encargado {cita['ENCARGADO']}.
                
                Por favor, confirme su asistencia o comuníquese si necesita reprogramar.
                
                Saludos cordiales,
                {config['nombre_clinica']}
                """
                
                enviar_correo(
                    cita['EMAIL'], 
                    f"Recordatorio de Cita - {config['nombre_clinica']}", 
                    mensaje_paciente,
                    config['correo_remitente'],
                    config['password_correo']
                )
            
            # Recordatorio por WhatsApp
            if config['whatsapp_activo'] and cita['TELEFONO']:
                # Mensaje al paciente
                mensaje_whatsapp_paciente = f"Recordatorio: Tiene una cita mañana {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} para el servicio de {cita['SERVICIOS']} con el encargado {cita['ENCARGADO']}. {config['nombre_clinica']}"
                enviar_whatsapp(cita['TELEFONO'], mensaje_whatsapp_paciente)
                
                # Mensaje al encargado
                mensaje_whatsapp_encargado = f"Recordatorio: Tiene una cita mañana {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} con el paciente {cita['NOMBRE']} para el servicio de {cita['SERVICIOS']}. {config['nombre_clinica']}"
                enviar_whatsapp(tel_encargado, mensaje_whatsapp_encargado)
        
        # Citas para hoy - enviar recordatorio hoy temprano
        elif fecha_cita == ahora.date() and ahora.hour < 12:  # Antes de las 10 AM
            # Recordatorio al paciente por correo
            if config['correo_activo'] and cita['EMAIL']:
                mensaje_paciente = f"""
                Estimado/a {cita['NOMBRE']},
                
                Le recordamos que tiene una cita programada para HOY {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} para el servicio de {cita['SERVICIOS']} con el/la encargado {cita['ENCARGADO']}.
                
                Saludos cordiales,
                {config['nombre_clinica']}
                """
                
                enviar_correo(
                    cita['EMAIL'], 
                    f"Recordatorio de Cita HOY - {config['nombre_clinica']}", 
                    mensaje_paciente,
                    config['correo_remitente'],
                    config['password_correo']
                )
            
            # Recordatorio por WhatsApp
            if config['whatsapp_activo'] and cita['TELEFONO']:
                # Mensaje al paciente
                mensaje_whatsapp_paciente = f"Recordatorio: Tiene una cita HOY {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} para el servicio de {cita['SERVICIOS']} con el encargado {cita['ENCARGADO']}. {config['nombre_clinica']}"
                enviar_whatsapp(cita['TELEFONO'], mensaje_whatsapp_paciente)
                
                # Mensaje al encargado
                mensaje_whatsapp_encargado = f"Recordatorio: Tiene una cita HOY {fecha_cita.strftime('%d/%m/%Y')} a las {hora_cita} con el paciente {cita['NOMBRE']} para el servicio de {cita['SERVICIOS']}. {config['nombre_clinica']}"
                enviar_whatsapp(tel_encargado, mensaje_whatsapp_encargado)

# Función para ejecutar los recordatorios en segundo plano
def ejecutar_recordatorios(creds, config):
    # Programar la tarea para que se ejecute cada día a las 8 AM
    schedule.every().day.at("12:30").do(ejecutar_verificacion_citas, creds=creds, config=config)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Revisar cada minuto

def ejecutar_verificacion_citas(creds, config):
    # Obtener datos actualizados de Google Sheets
    df_citas, _ = get_google_sheet_data(creds)
    if df_citas is not None:
        verificar_citas(df_citas, config)

# Función para iniciar el hilo de recordatorios
def iniciar_sistema_recordatorios(creds, config):
    thread = threading.Thread(target=ejecutar_recordatorios, args=(creds, config))
    thread.daemon = True  # El hilo se cerrará cuando el programa principal termine
    thread.start()
    return thread

# Función para preparar datos para visualización
def preparar_datos_citas(df):
    # Asegurarse de que las columnas necesarias estén presentes
    columnas_requeridas = [
        'NOMBRE', 'EMAIL', 'TELEFONO', 'FECHA', 'HORA', 
        'SERVICIOS', 'ENCARGADO', 'CORREO ENCARGADO'
    ]
    
    # Verificar si faltan columnas
    columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
    
    if columnas_faltantes:
        st.warning(f"Faltan las siguientes columnas en la hoja de cálculo: {', '.join(columnas_faltantes)}")
        return None
    
    # Seleccionar solo las columnas necesarias
    df_citas = df[columnas_requeridas].copy()
    
    # Formatear la fecha para mejor visualización
    df_citas['FECHA'] = df_citas['FECHA'].dt.strftime('%Y-%m-%d')
    
    return df_citas

# Interfaz principal de Streamlit
def main():
    st.title("🏥 Sistema de Recordatorio de Citas")
    
    # Cargar credenciales automáticamente desde secrets.toml
    creds = load_credentials_from_secrets()
    
    if creds is not None:
        # Sidebar para configuración
        with st.sidebar:
            st.header("⚙️ Configuración del Sistema")
            
            st.subheader("Datos Generales")
            nombre_clinica = st.text_input("Nombre de la Clínica/Consultorio", "CLINICA DEL AMOR")
            
            st.subheader("Configuración de Correo")
            correo_activo = st.checkbox("Activar notificaciones por correo", value=True)
            correo_remitente = "josegarjagt@gmail.com"                                         #st.text_input("Correo Remitente (Gmail)", "ejemplo@gmail.com")
            password_correo = "ulbiiydnlgkllkub"                                              #st.text_input("Contraseña de aplicación", type="password")

            st.subheader("Configuración de WhatsApp")
            whatsapp_activo = st.checkbox("Activar notificaciones por WhatsApp", value=True)
            
            st.markdown("---")
            
            # Botón para probar conexión
            if st.button("Probar Conexión con Google Sheets"):
                with st.spinner("Conectando con Google Sheets..."):
                    df, _ = get_google_sheet_data(creds)
                    if df is not None:
                        st.success("¡Conexión exitosa! Se encontraron datos en la hoja.")
                    
            # Botón para iniciar sistema
            if st.button("Iniciar Sistema de Recordatorios"):
                config = {
                    'nombre_clinica': nombre_clinica,
                    'correo_activo': correo_activo,
                    'correo_remitente': correo_remitente,
                    'password_correo': password_correo,
                    'whatsapp_activo': whatsapp_activo
                }
                
                if correo_activo and (not correo_remitente or not password_correo):
                    st.error("Para activar notificaciones por correo, debe proporcionar un correo remitente.")
                else:
                    st.session_state['thread_recordatorios'] = iniciar_sistema_recordatorios(creds, config)
                    st.success("Sistema de recordatorios iniciado correctamente!")
                    
            # Botón para probar envío de correo
            #if st.button("Envío de Correo"):
            #    if correo_activo and correo_remitente and password_correo:
            #        resultado = enviar_correo(
            #            correo_remitente, 
            #            "Sistema de Citas", 
            #            "Este es un mensaje del sistema de recordatorio de citas.", 
            #            correo_remitente, 
            #            password_correo
            #        )
            #        if resultado:
            #            st.success("Correo enviado correctamente!")
            #        else:
            #            st.error("Error al enviar correo.")
            #    else:
            #        st.error("Para el envío de correo, debe activar las notificaciones por correo y proporcionar credenciales válidas.")
        
        # Pestañas para diferentes secciones
        tab1, tab2, tab3 = st.tabs(["📋 Gestión de Citas", "📊 Estado del Sistema", "ℹ️ Ayuda"])
        
        with tab1:
            st.header("Gestión de Citas")
            
            # Cargar datos de Google Sheets
            with st.spinner("Cargando datos de Google Sheets..."):
                df, worksheet = get_google_sheet_data(creds)
                
                if df is not None:
                    # Preparar datos para visualización
                    df_citas = preparar_datos_citas(df)
                    
                    if df_citas is not None:
                        # Mostrar tabla de citas
                        st.subheader("Citas Programadas")
                        st.dataframe(df_citas)
                        
                        # Opción para actualizar datos
                        if st.button("Actualizar Datos"):
                            st.rerun()
                else:
                    st.error("No se pudieron cargar los datos. Verifica la conexión y las credenciales.")
        
        with tab2:
            st.header("Estado del Sistema")
            
            if 'thread_recordatorios' in st.session_state:
                st.success("✅ Sistema de recordatorios activo")
                
                # Mostrar próximos recordatorios
                st.subheader("Próximos Recordatorios")
                
                # Cargar datos actualizados
                df, _ = get_google_sheet_data(creds)
                if df is not None:
                    df_citas = preparar_datos_citas(df)
                    if df_citas is not None:
                        ahora = datetime.now()
                        
                        # Convertir la columna FECHA a datetime para comparación
                        df_citas['FECHA'] = pd.to_datetime(df_citas['FECHA'])
                        
                        # Filtrar citas para hoy y mañana
                        fecha_hoy = ahora.strftime('%Y-%m-%d')
                        fecha_manana = (ahora + timedelta(days=1)).strftime('%Y-%m-%d')
                        
                        citas_proximas = df_citas[
                            (df_citas['FECHA'].dt.strftime('%Y-%m-%d') == fecha_hoy) | 
                            (df_citas['FECHA'].dt.strftime('%Y-%m-%d') == fecha_manana)
                        ]
                        
                        # Volver a formatear para visualización
                        if not citas_proximas.empty:
                            citas_proximas['FECHA'] = citas_proximas['FECHA'].dt.strftime('%Y-%m-%d')
                            st.dataframe(citas_proximas)
                        else:
                            st.info("No hay citas programadas para hoy ni mañana.")
                
                # Información adicional
                st.subheader("Log de Actividad")
                st.text("El sistema revisará las citas pendientes cada día a las 8:00 AM.")
                st.text("Se enviarán recordatorios por correo y WhatsApp a los pacientes y encargados.")
            else:
                st.warning("⚠️ Sistema de recordatorios inactivo")
                st.text("Inicie el sistema desde la configuración en el panel lateral.")
        
        with tab3:
            st.header("Ayuda y Guía de Uso")
            
            st.subheader("Configuración Inicial")
            st.markdown("""
            1. **Configuración de Correo**:
               - Active la opción "Activar notificaciones por correo"
               - Ingrese su correo de Gmail
                           
            2. **Configuración de WhatsApp**:
               - Active la opción "Activar notificaciones por WhatsApp"
               - Se abrirá automáticamente WhatsApp Web para enviar mensajes
            """)
            
            st.subheader("Funcionamiento")
            st.markdown("""
            - El sistema enviará recordatorios:
              - Un día antes de la cita (recordatorio previo)
              - El mismo día de la cita (recordatorio el día de la cita)
            - Los recordatorios se enviarán tanto al paciente como al encargado
            - Para que el sistema funcione, debe mantener esta aplicación ejecutándose
            """)
            
            st.subheader("Problemas Comunes")
            st.markdown("""
            - **Error al cargar el archivo secrets.toml**: Verifique que exista en la carpeta .streamlit y tenga el formato correcto
            - **Error de conexión con Google Sheets**: Verifique las credenciales y permisos
            - **Error al enviar correos**: Verifique que la contraseña de aplicación sea correcta
            - **Error con WhatsApp**: Asegúrese de tener WhatsApp Web disponible
            """)
    else:
        st.error("No se pudieron cargar las credenciales desde .streamlit/secrets.toml")
        
if __name__ == "__main__":
    main()