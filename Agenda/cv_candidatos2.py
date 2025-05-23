import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
#from gspread_dataframe import set_with_dataframe
import time
import json
import toml
import backoff
import re
import ssl
import time
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Constantes
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(page_title="Sistema de Gestión de Candidatos", layout="wide")
#st.title("Sistema de Gestión de Candidatos")

def load_credentials_from_toml():
    #Load credentials from secrets.toml file
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    #Establish connection with Google Sheets
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

# Función para autenticar y conectar a Google Sheets
def connect_to_google_sheets():
    #st.sidebar.header("Conexión a Google Drive")
    
    # Cargar credenciales desde el archivo toml
    creds, config = load_credentials_from_toml()
    
    if creds:
        gc = get_google_sheets_connection(creds)
        if gc:
            #st.sidebar.success("✅ Conexión exitosa a Google Drive usando secrets.toml")
            return gc
    
    # Si no se pudieron cargar las credenciales desde toml, solicitar al usuario
    st.sidebar.warning("No se pudieron cargar credenciales automáticamente. Por favor, súbelas manualmente.")
    uploaded_file = st.sidebar.file_uploader("Subir archivo JSON de credenciales", type="json")
    
    if uploaded_file is not None:
        try:
            # Crear credenciales a partir del archivo subido
            credentials_dict = pd.read_json(uploaded_file).to_dict()
            
            # Definir el alcance
            SCOPES = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Autenticar con Google
            credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
            gc = gspread.authorize(credentials)
            
            st.sidebar.success("✅ Conexión exitosa a Google Drive")
            return gc
        except Exception as e:
            st.sidebar.error(f"Error de autenticación: {e}")
            return None
    return None

# Función para abrir la hoja de cálculo
def open_spreadsheet(gc):
    if gc is None:
        return None
    
    # Intentar obtener el ID de la hoja de cálculo desde las credenciales
    creds, config = load_credentials_from_toml()
    spreadsheet_id = None
    spreadsheet_name = "gestion-agenda"
    
    # Crear contenedor horizontal para los mensajes de estado
    status_container = st.container()
    
    if config and 'sheetsemp' in config and 'spreadsheet_id' in config['sheetsemp']:
        spreadsheet_id = config['sheetsemp']['spreadsheet_id']
        try:
            # Abrir por ID
            spreadsheet = gc.open_by_key(spreadsheet_id)
            with status_container:
                st.success(f"✅ Hoja encontrada por ID configurado")
            return spreadsheet
        except Exception as e:
            with status_container:
                st.warning(f"No se pudo abrir la hoja con el ID configurado: {e}")
    
    try:
        # Intentar abrir la hoja por nombre
        spreadsheet = gc.open(spreadsheet_name)
        with status_container:
            pass
            #st.success(f"✅ Hoja '{spreadsheet_name}' encontrada")
        return spreadsheet
    except Exception as e:
        with status_container:
            st.warning(f"No se pudo abrir la hoja de cálculo por nombre: {e}")
        
        # Crear un diseño horizontal para la entrada de URL
        col1, col2 = st.columns([3, 1])
        with col1:
            sheet_url = st.text_input("Introduce la URL de la hoja de cálculo:")
        with col2:
            submit_button = st.button("Conectar")
            
        if sheet_url and submit_button:
            try:
                spreadsheet = gc.open_by_url(sheet_url)
                with status_container:
                    st.success("✅ Hoja encontrada por URL")
                return spreadsheet
            except Exception as e:
                with status_container:
                    st.error(f"No se pudo abrir la hoja por URL: {e}")
                return None
    return None

# Función para obtener hojas específicas con manejo de reintentos
@backoff.on_exception(backoff.expo, 
                     (gspread.exceptions.APIError, 
                      gspread.exceptions.SpreadsheetNotFound),
                     max_tries=5,
                     base=INITIAL_RETRY_DELAY)
def get_worksheet_data(spreadsheet, worksheet_name):
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener datos de la hoja '{worksheet_name}': {e}")
        return pd.DataFrame()

# Función para guardar datos en la hoja de candidatos con manejo de reintentos
@backoff.on_exception(backoff.expo, 
                     (gspread.exceptions.APIError),
                     max_tries=5,
                     base=INITIAL_RETRY_DELAY)
def save_to_candidates(spreadsheet, candidates_df):
    try:
        # Verificar si la hoja candidatos existe, si no, crearla
        try:
            worksheet = spreadsheet.worksheet("candidatos")
            existing_data = pd.DataFrame(worksheet.get_all_records())
        except:
            worksheet = spreadsheet.add_worksheet(title="candidatos", rows="1000", cols="20")
            existing_data = pd.DataFrame()
            
        # Definir cabeceras si es necesario
        headers = [
            "cargo", "nombre", "identificacion", "telefono", "email", 
            "entrevista", "fecha", "encargado", "calificacion", "puntaje",
            "elegido", "fecha inicio", "fecha fin", "observaciones"
        ]
        
        # Si la hoja está vacía, añadir cabeceras
        #if worksheet.row_count == 0 or existing_data.empty:
        #    worksheet.append_row(headers)
        #    existing_data = pd.DataFrame(columns=headers)
        
        # Verificar duplicados por identificación y cargo
        if not existing_data.empty:
            # Crear un identificador único combinando identificación y cargo
            if 'identificacion' in existing_data.columns and 'cargo' in existing_data.columns:
                existing_data['id_cargo'] = existing_data['identificacion'].astype(str) + '_' + existing_data['cargo'].astype(str)
                
                # Hacer lo mismo para los nuevos candidatos
                candidates_df['id_cargo'] = candidates_df['identificacion'].astype(str) + '_' + candidates_df['cargo'].astype(str)
                
                # Filtrar para obtener solo registros no duplicados
                new_candidates = candidates_df[~candidates_df['id_cargo'].isin(existing_data['id_cargo'])]
                
                # Eliminar la columna temporal
                if 'id_cargo' in new_candidates.columns:
                    new_candidates = new_candidates.drop('id_cargo', axis=1)
                
                if new_candidates.empty:
                    st.warning("No hay nuevos candidatos para agregar. Todos los candidatos ya existen con el mismo cargo.")
                    return existing_data
                
                # Contar cuántos candidatos nuevos se añadirán
                num_new_candidates = len(new_candidates)
                
                # Preparar para guardar solo los nuevos
                candidates_to_save = new_candidates
            else:
                # Si no existen las columnas necesarias, tratar todos como nuevos
                candidates_to_save = candidates_df
                num_new_candidates = len(candidates_df)
        else:
            # Si no hay datos existentes, todos son nuevos
            candidates_to_save = candidates_df
            num_new_candidates = len(candidates_df)
        
        # Guardar solo los nuevos candidatos al final de la hoja existente
        if not candidates_to_save.empty:
            # Convertir a lista de listas para agregar
            values_to_append = candidates_to_save.values.tolist()
            
            # Añadir los nuevos registros uno por uno
            for row in values_to_append:
                worksheet.append_row(row)
            
            st.success(f"✅ Se han guardado {num_new_candidates} nuevos candidatos en la hoja.")
        
        # Retornar todos los datos para mostrar
        updated_df = pd.DataFrame(worksheet.get_all_records())
        return updated_df
    except Exception as e:
        st.error(f"Error al guardar en la hoja de candidatos: {e}")
        return pd.DataFrame()

# Función para verificar si una vacante coincide con el cargo del CV
def match_cargo(cargo_cv, cargo_vacante):
    """
    Verifica si el cargo del CV coincide con una vacante.
    Una coincidencia es válida si el cargo_cv contiene las palabras clave del cargo_vacante.
    
    Args:
        cargo_cv (str): Cargo mencionado en el CV
        cargo_vacante (str): Cargo de la vacante
        
    Returns:
        bool: True si hay coincidencia, False en caso contrario
    """
    if not isinstance(cargo_cv, str) or not isinstance(cargo_vacante, str):
        return False
    
    cargo_cv = cargo_cv.lower()
    cargo_vacante = cargo_vacante.lower()
    
    # Dividir el cargo de la vacante en palabras clave
    palabras_vacante = cargo_vacante.split()
    
    # Verificar si todas las palabras del cargo de la vacante están en el cargo del CV
    # O si el cargo completo de la vacante está contenido en el CV
    if cargo_vacante in cargo_cv:
        return True
    
    # Verificar si al menos una palabra clave del cargo de la vacante está en el CV
    # Se consideran solo palabras con longitud > 3 para evitar preposiciones
    palabras_clave = [palabra for palabra in palabras_vacante if len(palabra) > 3]
    
    for palabra in palabras_clave:
        if palabra in cargo_cv:
            return True
    
    return False

# Función para enviar correo electrónico al candidato
def send_email_to_candidate(email_to, nombre, cargo, fecha, hora, encargado):
    try:
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
        message['From'] = smtp_user  # Usando el mismo usuario como remitente
        message['To'] = email_to
        message['Subject'] = f"Invitación a entrevista para el cargo de {cargo}"
        
        # Contenido del correo
        body = f"""                               
<html>
<body>
<h2>Invitación a Entrevista</h2>
<p>Estimado(a) <b>{nombre}</b>,</p>
<p>Nos complace informarle que ha sido seleccionado(a) para una entrevista para el cargo de <b>{cargo}</b>.</p>
<p>Los detalles de la entrevista son los siguientes:</p>
<ul>
    <li><b>Fecha:</b> {fecha}</li>
    <li><b>Hora:</b> {hora}</li>
    <li><b>Encargado:</b> {encargado}</li>
    <li><b>Lugar:</b> Oficina principal - Sala de reuniones</li>
</ul>
<p>Por favor confirme su asistencia respondiendo a este correo.</p>
<p>Atentamente,<br>
Equipo de Recursos Humanos</p>
</body>
</html>
        """
        
        # Adjuntar el cuerpo del mensaje como HTML
        message.attach(MIMEText(body, 'html'))
        
        # Conexión con el servidor SMTP
        context = ssl.create_default_context()  # Para conexión SSL
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
        # Error específico que estás experimentando
        return False, f"Error al enviar correo - Archivo no encontrado: {str(e)}"

    except Exception as e:
        return False, f"Error al enviar correo: {str(e)}"


# Función principal para procesar los datos
def process_data(spreadsheet):
    # Obtener datos de las hojas con reintentos
    resumen_cv_df = get_worksheet_data(spreadsheet, "resumen-cv")
    vacantes_df = get_worksheet_data(spreadsheet, "vacantes")
    
    if resumen_cv_df.empty or vacantes_df.empty:
        st.error("No se pudieron obtener los datos necesarios de las hojas.")
        return
    
    # Mostrar los datos cargados
    with st.expander("Ver datos de resumen-cv"):
        st.dataframe(resumen_cv_df)
    
    with st.expander("Ver datos de vacantes"):
        st.dataframe(vacantes_df)
    
    # Crear lista para almacenar candidatos encontrados
    candidates = []
    
    # Barra de progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Procesar cada registro en resumen-cv
    total_records = len(resumen_cv_df)
    
    for i, cv_row in enumerate(resumen_cv_df.itertuples()):
        # Actualizar progreso
        progress = (i + 1) / total_records
        progress_bar.progress(progress)
        status_text.text(f"Procesando registro {i+1} de {total_records}...")
        
        # Obtener nombre e identificación
        nombre = getattr(cv_row, 'nombre', None)
        identificacion = getattr(cv_row, 'identificacion', None)
        
        if not nombre or not identificacion:
            continue
        
        # Buscar cargo en las columnas de página
        cargo = None
        
        # Primero buscar si existe la etiqueta "cargo" en cualquier página
        for page_num in range(1, 6):
            page_col = f'pagina{page_num}'
            if hasattr(cv_row, page_col) and getattr(cv_row, page_col):
                page_text = getattr(cv_row, page_col)
                
                # Si es un string, buscar la etiqueta "cargo"
                if isinstance(page_text, str) and page_text.strip():
                    # Buscar patrones comunes para cargo
                    cargo_patterns = [
                        r'cargo:?\s*([^\n\r.]*)',
                        r'puesto:?\s*([^\n\r.]*)',
                        r'posición:?\s*([^\n\r.]*)',
                        r'posicion:?\s*([^\n\r.]*)',
                        r'empleo:?\s*([^\n\r.]*)'
                    ]
                    
                    for pattern in cargo_patterns:
                        matches = re.search(pattern, page_text, re.IGNORECASE)
                        if matches:
                            extracted_cargo = matches.group(1).strip()
                            if extracted_cargo:  # Si se encontró algo después de la etiqueta
                                cargo = extracted_cargo
                                break
                
                if cargo:  # Si ya encontramos un cargo, salir del bucle
                    break
        
        # Si no se encontró con etiqueta, usar el método anterior (tomar el texto de la primera página)
        if not cargo:
            for page_num in range(1, 6):
                page_col = f'pagina{page_num}'
                if hasattr(cv_row, page_col) and getattr(cv_row, page_col):
                    cargo_text = getattr(cv_row, page_col)
                    # Si es un string, intentar extraer información de cargo
                    if isinstance(cargo_text, str) and cargo_text.strip():
                        cargo = cargo_text
                        break        
        if not cargo:
            continue
        
        # Obtener teléfono y email
        telefono = None
        email = None
        
        # Buscar teléfono y email en las columnas de página con expresiones regulares
        for page_num in range(1, 6):
            page_col = f'pagina{page_num}'
            if hasattr(cv_row, page_col) and getattr(cv_row, page_col):
                text = getattr(cv_row, page_col)
                
                # Buscar patrones de email y teléfono si no se han encontrado aún
                if isinstance(text, str):
                    # Buscar email si aún no se ha encontrado
                    if not email:
                        email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
                        email_matches = re.findall(email_pattern, text)
                        if email_matches:
                            email = email_matches[0]
                    
                    # Buscar teléfono si aún no se ha encontrado
                    if not telefono:
                        # Patrones para teléfonos colombianos (celular o fijo)
                        phone_patterns = [
                            r'3\d{9}',  # Celular formato 3xxxxxxxxx
                            r'\d{7,10}', # Teléfono genérico de 7-10 dígitos
                            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Formato xxx-xxx-xxxx
                        ]
                        
                        for pattern in phone_patterns:
                            phone_matches = re.findall(pattern, text.replace(" ", "").replace("-", ""))
                            if phone_matches:
                                telefono = phone_matches[0]
                                break
        
        # Verificar si el cargo del CV coincide con alguna vacante
        for vac_row in vacantes_df.itertuples():
          vac_estado = getattr(vac_row, 'estado', '') 
          vac_cargo = getattr(vac_row, 'cargo', '')
          if vac_estado == "Activo":  
            # Verificar coincidencia usando la nueva función
            if match_cargo(cargo, vac_cargo):
                # Añadir a la lista de candidatos
                candidates.append({
                    'cargo': vac_cargo,
                    'nombre': nombre,
                    'identificacion': str(identificacion),
                    'telefono': str(telefono) if telefono else '',
                    'email': email or '',
                    'entrevista': '',
                    'fecha': '',
                    'encargado': '',
                    'calificacion': '',
                    'puntaje': '',
                    'elegido': '',
                    'fecha inicio': '',
                    'fecha fin': '',
                    'observaciones': ''
                })
                # No salir del bucle para permitir que un candidato coincida con múltiples vacantes
                # break
          else:
            st.warning("El Cargo No esta Activo")  
            break
    # Crear DataFrame de candidatos
    candidates_df = pd.DataFrame(candidates)
    
    # Verificar si se encontraron candidatos
    if candidates_df.empty:
        st.warning("No se encontraron coincidencias entre CV y vacantes.")
        return
    
    # Mostrar candidatos encontrados
    st.subheader(f"Candidatos encontrados: {len(candidates_df)}")
    st.dataframe(candidates_df)
    
    # Opción para guardar
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Guardar candidatos", key="save_candidates_btn"):
            saved_df = save_to_candidates(spreadsheet, candidates_df)
            if not saved_df.empty:
                st.subheader("Datos guardados en la hoja 'candidatos'")
                st.dataframe(saved_df)
    
    with col2:
        st.info("Al guardar, solo se añadirán candidatos nuevos (combinación única de identificación y cargo).")

# Modificación en la función edit_candidates para manejar el botón de envío de correo
# Interfaz principal
def edit_candidates(spreadsheet):
    if spreadsheet is None:
        return
    
    # Importaciones necesarias (asegúrate de tenerlas en tu script principal)
    import time
    
    # Inicializar variables de estado si no existen
    if 'update_successful' not in st.session_state:
        st.session_state.update_successful = False
    if 'update_failed' not in st.session_state:
        st.session_state.update_failed = False
    if 'email_sent' not in st.session_state:
        st.session_state.email_sent = False
    
    # Mostrar mensajes de estado si existen
    if st.session_state.update_successful:
        st.success("✅ La información del candidato se actualizó exitosamente.")
        # Limpiar el estado después de mostrar el mensaje
        st.session_state.update_successful = False
    
    if st.session_state.update_failed:
        st.error("❌ Hubo un problema al actualizar la información del candidato.")
        st.session_state.update_failed = False
    
    if st.session_state.email_sent:
        st.success("✅ El correo de entrevista se envió exitosamente.")
        st.session_state.email_sent = False
    
    st.subheader("Gestión de Candidatos")
    
    try:
        # Cargar datos existentes con reintentos
        try:
            worksheet = spreadsheet.worksheet("candidatos")
            candidates_df = pd.DataFrame(worksheet.get_all_records())
        except Exception as e:
            st.info(f"No existe aún la hoja de candidatos o está vacía. {str(e)}")
            return
        
        if candidates_df.empty:
            st.info("No hay candidatos registrados.")
            return
        
        # Mostrar datos
        st.dataframe(candidates_df)
        
        # Opción para editar un candidato específico
        st.subheader("Editar información de candidato")
        
        # Seleccionar candidato por ID y cargo
        if 'identificacion' in candidates_df.columns and 'cargo' in candidates_df.columns:
            # Convertir columnas a string para evitar problemas de comparación
            candidates_df['identificacion'] = candidates_df['identificacion'].astype(str)
            candidates_df['cargo'] = candidates_df['cargo'].astype(str)
            
            # Crear opciones combinando ID y cargo para mejor selección
            options = [f"{row['identificacion']} - {row['cargo']}" for _, row in candidates_df.iterrows()]
            
            if not options:
                st.info("No hay candidatos disponibles para editar.")
                return
                
            selected_option = st.selectbox(
                "Seleccione candidato:",
                options=options
            )
            
            # Extraer ID y cargo del candidato seleccionado
            selected_parts = selected_option.split(" - ", 1)  # Limitar a una división para manejar cargos con guiones
            if len(selected_parts) >= 2:
                selected_id = selected_parts[0].strip()
                selected_cargo = selected_parts[1].strip()
                
                # Filtrar candidato por ID y cargo exactos
                filtered_df = candidates_df[
                    (candidates_df['identificacion'] == selected_id) & 
                    (candidates_df['cargo'] == selected_cargo)
                ]
                
                # Si no se encuentra coincidencia exacta, buscar de forma menos estricta
                if filtered_df.empty:
                    st.warning("No se encontró coincidencia exacta, buscando de forma menos estricta...")
                    filtered_df = candidates_df[
                        (candidates_df['identificacion'] == selected_id) &
                        (candidates_df['cargo'].str.contains(selected_cargo, case=False, na=False) | 
                         candidates_df['cargo'].apply(lambda x: selected_cargo.lower() in x.lower() if isinstance(x, str) else False))
                    ]
                
                if not filtered_df.empty:
                    candidate_idx = filtered_df.index[0]
                    candidate = candidates_df.iloc[candidate_idx]
                    
                    # Formulario de edición
                    with st.form("edit_candidate_form"):
                        # Campos no editables
                        st.text(f"Nombre: {candidate['nombre']}")
                        st.text(f"Cargo: {candidate['cargo']}")
                        st.text(f"Identificación: {candidate['identificacion']}")
                        
                        # Campos editables - Convertir a string seguro y manejar valores NaN
                        telefono = st.text_input("Teléfono:", value=str(candidate['telefono']) if not pd.isna(candidate['telefono']) else "")
                        email = st.text_input("Email:", value=str(candidate['email']) if not pd.isna(candidate['email']) else "")
                        
                        # Determinar el índice correcto para el selectbox de entrevista
                        entrevista_options = ['', 'Programada', 'Realizada', 'Cancelada']
                        entrevista_value = str(candidate['entrevista']) if not pd.isna(candidate['entrevista']) else ""
                        # Limpiar valor para comparación segura
                        entrevista_value = entrevista_value.strip()
                        entrevista_index = entrevista_options.index(entrevista_value) if entrevista_value in entrevista_options else 0
                        entrevista = st.selectbox("Entrevista:", options=entrevista_options, index=entrevista_index)
                        
                        # Manejo de fecha con valor predeterminado seguro
                        fecha_default = None
                        try:
                            if 'fecha' in candidate and not pd.isna(candidate['fecha']) and str(candidate['fecha']).strip():
                                fecha_str = str(candidate['fecha']).strip()
                                if fecha_str:
                                    fecha_default = pd.to_datetime(fecha_str).date()
                        except Exception as e:
                            st.warning(f"No se pudo convertir la fecha: {e}")
                            
                        fecha = st.date_input("Fecha:", value=fecha_default)
                        
                        # Agregar campo de hora para la entrevista
                        hora_default = datetime.now().time()  # Valor predeterminado actual
                        try:
                            if 'hora' in candidate and not pd.isna(candidate['hora']) and str(candidate['hora']).strip():
                                hora_str = str(candidate['hora']).strip()
                                if hora_str:
                                    hora_parts = hora_str.split(':')
                                    if len(hora_parts) >= 2:
                                        hora_default = datetime.time(int(hora_parts[0]), int(hora_parts[1]))
                        except Exception as e:
                            st.warning(f"No se pudo convertir la hora: {e}")
                            
                        hora = st.time_input("Hora de entrevista:", value=hora_default)
                        
                        encargado = st.text_input("Encargado:", value=str(candidate['encargado']) if not pd.isna(candidate['encargado']) else "")
                        
                        # Determinar el índice correcto para el selectbox de calificación
                        calificacion_options = ['', 'Excelente', 'Bueno', 'Regular', 'Malo']
                        calificacion_value = str(candidate['calificacion']) if not pd.isna(candidate['calificacion']) else ""
                        # Limpiar valor para comparación segura
                        calificacion_value = calificacion_value.strip()
                        calificacion_index = calificacion_options.index(calificacion_value) if calificacion_value in calificacion_options else 0
                        calificacion = st.selectbox("Calificación:", options=calificacion_options, index=calificacion_index)
                        
                        # Manejo seguro del puntaje
                        puntaje_value = 0
                        try:
                            if 'puntaje' in candidate and not pd.isna(candidate['puntaje']):
                                puntaje_str = str(candidate['puntaje']).strip()
                                if puntaje_str and puntaje_str.replace('.', '', 1).isdigit():
                                    puntaje_value = int(float(puntaje_str))
                        except Exception as e:
                            st.warning(f"No se pudo convertir el puntaje: {e}")
                            
                        puntaje = st.number_input("Puntaje:", min_value=0, max_value=100, value=puntaje_value)
                        
                        # Checkbox para elegido
                        elegido_value = False
                        if 'elegido' in candidate and not pd.isna(candidate['elegido']):
                            elegido_str = str(candidate['elegido']).strip().lower()
                            elegido_value = elegido_str in ['sí', 'si', 'yes', 'true', '1']
                            
                        elegido = st.checkbox("Elegido", value=elegido_value)
                        
                        # Manejo de fechas inicio/fin
                        fecha_inicio_default = None
                        try:
                            if 'fecha inicio' in candidate and not pd.isna(candidate['fecha inicio']) and str(candidate['fecha inicio']).strip():
                                fecha_inicio_str = str(candidate['fecha inicio']).strip()
                                if fecha_inicio_str:
                                    fecha_inicio_default = pd.to_datetime(fecha_inicio_str).date()
                        except Exception as e:
                            st.warning(f"No se pudo convertir la fecha de inicio: {e}")
                            
                        fecha_inicio = st.date_input("Fecha inicio:", value=fecha_inicio_default)
                        
                        fecha_fin_default = None
                        try:
                            if 'fecha fin' in candidate and not pd.isna(candidate['fecha fin']) and str(candidate['fecha fin']).strip():
                                fecha_fin_str = str(candidate['fecha fin']).strip()
                                if fecha_fin_str:
                                    fecha_fin_default = pd.to_datetime(fecha_fin_str).date()
                        except Exception as e:
                            st.warning(f"No se pudo convertir la fecha de fin: {e}")
                            
                        fecha_fin = st.date_input("Fecha fin:", value=fecha_fin_default)
                        
                        observaciones = st.text_area(
                            "Observaciones:", 
                            value=str(candidate['observaciones']) if 'observaciones' in candidate and not pd.isna(candidate['observaciones']) else ""
                        )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            submit_button = st.form_submit_button("Actualizar candidato")
                        
                        with col2:
                            send_email_button = st.form_submit_button("Enviar correo de entrevista")
                        
                    # ¡IMPORTANTE! Mover fuera del bloque with st.form() para que se ejecute después de procesar el formulario
                    # Manejar acciones de los botones
                    if submit_button:
                            try:
                                # Guardar valores originales para verificación
                                original_values = candidates_df.iloc[candidate_idx].copy()
                                
                                # Actualizar datos - conversión segura a string
                                candidates_df.at[candidate_idx, 'telefono'] = str(telefono)
                                candidates_df.at[candidate_idx, 'email'] = str(email)
                                candidates_df.at[candidate_idx, 'entrevista'] = str(entrevista)
                                candidates_df.at[candidate_idx, 'fecha'] = fecha.strftime('%Y-%m-%d') if fecha else ''
                                candidates_df.at[candidate_idx, 'hora'] = hora.strftime('%H:%M') if hora else ''
                                candidates_df.at[candidate_idx, 'encargado'] = str(encargado)
                                candidates_df.at[candidate_idx, 'calificacion'] = str(calificacion)
                                candidates_df.at[candidate_idx, 'puntaje'] = str(puntaje)
                                candidates_df.at[candidate_idx, 'elegido'] = 'Sí' if elegido else 'No'
                                candidates_df.at[candidate_idx, 'fecha inicio'] = fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else ''
                                candidates_df.at[candidate_idx, 'fecha fin'] = fecha_fin.strftime('%Y-%m-%d') if fecha_fin else ''
                                candidates_df.at[candidate_idx, 'observaciones'] = str(observaciones)
                                
                                # Verificar si hubo cambios
                                current_values = candidates_df.iloc[candidate_idx]
                                changes_made = False
                                
                                for col in candidates_df.columns:
                                    if str(original_values[col]) != str(current_values[col]):
                                        changes_made = True
                                        break
                                
                                if not changes_made:
                                    st.info("No se detectaron cambios en la información.")
                                    return
                                
                                # Guardar cambios con reintentos
                                try:
                                    # Actualizar toda la hoja
                                    headers = candidates_df.columns.tolist()
                                    
                                    # Asegurarse de que los valores sean strings para evitar errores
                                    for col in candidates_df.columns:
                                        candidates_df[col] = candidates_df[col].astype(str)
                                    
                                    # Convertir DataFrame a lista de listas
                                    values = [headers] + candidates_df.values.tolist()
                                    worksheet.clear()
                                    worksheet.update(values)
                                    
                                    st.success("✅ Información actualizada correctamente")
                                    # Crear banderas de sesión para indicar actualización exitosa
                                    st.session_state.update_successful = True
                                    
                                    # Forzar refresco de la página
                                    time.sleep(1)  # Breve pausa para que el usuario vea el mensaje
                                    st.rerun()
                                    
                                except gspread.exceptions.APIError as e:
                                    # Reintentar con exponential backoff
                                    for attempt in range(5):
                                        try:
                                            time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))  # Backoff exponencial
                                            worksheet.clear()
                                            worksheet.update(values)
                                            st.success("✅ Información actualizada correctamente después de reintentos")
                                            st.session_state.update_successful = True
                                            time.sleep(1)
                                            st.rerun()
                                            break
                                        except Exception as retry_e:
                                            if attempt == 4:  # Último intento
                                                st.error(f"Error después de varios reintentos: {retry_e}")
                                                st.session_state.update_failed = True
                            
                            except Exception as e:
                                st.error(f"Error al actualizar información: {e}")
                                st.exception(e)
                                
                    # Manejar envío de correo (fuera del bloque de formulario)
                    if send_email_button:
                        if not email or email == 'nan':
                            st.error("El candidato no tiene email registrado")
                        elif not fecha:
                            st.error("Debe programar una fecha para la entrevista")
                        elif not hora:
                            st.error("Debe indicar una hora para la entrevista")
                        elif not encargado or encargado == 'nan':
                            st.error("Debe indicar un encargado para la entrevista")
                        else:
                            try:
                                # Formatear fecha y hora para el correo
                                fecha_str = fecha.strftime('%d/%m/%Y') if fecha else ''
                                hora_str = hora.strftime('%H:%M') if hora else ''
                                
                                # Enviar correo
                                success, message = send_email_to_candidate(
                                    email_to=email,
                                    nombre=candidate['nombre'],
                                    cargo=candidate['cargo'],
                                    fecha=fecha_str,
                                    hora=hora_str,
                                    encargado=encargado
                                )
                                
                                if success:
                                    # Actualizar estado de entrevista si fue exitoso
                                    candidates_df.at[candidate_idx, 'entrevista'] = 'Programada'
                                    candidates_df.at[candidate_idx, 'fecha'] = fecha.strftime('%Y-%m-%d') if fecha else ''
                                    candidates_df.at[candidate_idx, 'hora'] = hora.strftime('%H:%M') if hora else ''
                                    candidates_df.at[candidate_idx, 'encargado'] = encargado
                                    
                                    # Actualizar observaciones con información del correo enviado
                                    current_obs = str(candidates_df.at[candidate_idx, 'observaciones'])
                                    if current_obs and current_obs != 'nan':
                                        # Añadir la información del correo al texto existente
                                        correo_info = f"\n\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Correo enviado para entrevista: Fecha: {fecha_str}, Hora: {hora_str}, Encargado: {encargado}"
                                        candidates_df.at[candidate_idx, 'observaciones'] = current_obs + correo_info
                                    else:
                                        # Crear nueva entrada de observaciones
                                        correo_info = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Correo enviado para entrevista: Fecha: {fecha_str}, Hora: {hora_str}, Encargado: {encargado}"
                                        candidates_df.at[candidate_idx, 'observaciones'] = correo_info
                                    
                                    # Guardar los cambios en la hoja de forma directa
                                    try:
                                        headers = candidates_df.columns.tolist()
                                        for col in candidates_df.columns:
                                            candidates_df[col] = candidates_df[col].astype(str)
                                        values = [headers] + candidates_df.values.tolist()
                                        worksheet.clear()
                                        worksheet.update(values)
                                        
                                        st.success(f"✅ {message}")
                                        st.session_state.email_sent = True
                                        
                                        # Recargar página para mostrar cambios
                                        time.sleep(1)
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"Error al guardar después de enviar correo: {e}")
                                else:
                                    st.error(f"❌ {message}")
                            except Exception as e:
                                st.error(f"Error al enviar correo: {e}")
                                st.exception(e)
                else:
                    st.error(f"No se encontró el candidato seleccionado con ID '{selected_id}' y cargo '{selected_cargo}'.")
            else:
                st.error("Formato de selección incorrecto. No se pudo extraer ID y cargo.")
        else:
            st.error("No se encontraron las columnas necesarias en los datos.")
            
    except Exception as e:
        st.error(f"Error al cargar datos de candidatos: {e}")
        st.exception(e)  # Mostrar detalles completos de la excepción para depuración

def candidatos():
    st.title("Sistema de Gestión de Candidatos")
    
    # Crear un contenedor para opciones en la parte superior
    options_container = st.container()
    
    # Conectar a Google Sheets usando las credenciales del archivo toml
    gc = connect_to_google_sheets()
    spreadsheet = None
    
    if gc:
        spreadsheet = open_spreadsheet(gc)
    
    if spreadsheet:
        # Menú de opciones con tabs en lugar de radio buttons
        with options_container:
            tab1, tab2 = st.tabs(["Procesar CV y Vacantes", "Gestionar Candidatos"])
            
            with tab1:
                if st.button("Cargar Procesamiento de CV", use_container_width=True):
                    process_data(spreadsheet)
            
            with tab2:
                if st.button("Cargar Gestión de Candidatos", use_container_width=True):
                    edit_candidates(spreadsheet)
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info("""
            ### Sistema de Gestión de Candidatos
            
            Para usar esta aplicación necesitas tener:
            1. Un archivo de credenciales de Google configurado en `.streamlit/secrets.toml`
            2. O puedes subir manualmente tus credenciales usando las opciones de conexión
            
            La aplicación conectará con la hoja "gestion-agenda" y procesará las hojas "resumen-cv" y "vacantes".
            """)
        
        with col2:
            st.markdown("""
            ### Instrucciones:
            
            La aplicación tiene dos funcionalidades principales:
            
            1. **Procesar CV y Vacantes**:
               - Cruza información de CV y vacantes
               - Extrae datos personales y profesionales
               - Coincidencia por palabras clave
               - Guarda en hoja "candidatos"
            
            2. **Gestionar Candidatos**:
               - Ver y editar información
               - Actualizar entrevistas y calificaciones
            """)
        
        # Área para subir credenciales (opcional)
        with st.expander("Subir credenciales manualmente"):
            uploaded_file = st.file_uploader("Seleccione su archivo de credenciales JSON", type=['json'])
            if uploaded_file:
                # Aquí iría el código para procesar el archivo subido
                st.success("Credenciales cargadas correctamente")
if __name__ == "__main__":
    candidatos()