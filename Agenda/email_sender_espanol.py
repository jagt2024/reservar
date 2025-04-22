import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import toml
import json
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

def cargar_configuracion():
    try:
        config = toml.load("./.streamlit/config.toml")
        return config["clave_google"]["clave_email"]
    except FileNotFoundError:
        st.error("Archivo de configuración no encontrado.")
        return None
    except KeyError:
        st.error("Clave no encontrada en el archivo de configuración.")
        return None

def load_credentials_from_toml():
    # Load credentials from secrets.toml file
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    # Establish connection with Google Sheets
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def get_all_data(client):
    """Get all data saved in the sheet"""
    try:
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('ordenes')
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        st.error(f"Error retrieving data: {str(e)}")
        return []

def update_google_sheet(client, email, status="Sent"):
    """Update status and shipping date in Google Sheet for the given email"""
    try:
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('ordenes')
        
        # Find the row with the matching email
        cell = worksheet.find(email)
        if cell:
            row = cell.row
            
            # Get column indices for Email Status and Shipping Date
            headers = worksheet.row_values(1)
            email_status_col = headers.index("Email Status") + 1 if "Email Status" in headers else None
            shipping_date_col = headers.index("Shipping Date") + 1 if "Shipping Date" in headers else None
            
            # Current date in the appropriate format
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Update the cells if columns exist
            if email_status_col:
                worksheet.update_cell(row, email_status_col, status)
            if shipping_date_col:
                worksheet.update_cell(row, shipping_date_col, current_date)
                
            return True
        else:
            st.warning(f"No se encontró el email {email} en Google Sheets")
            return False
    except Exception as e:
        st.error(f"Error al actualizar Google Sheets: {str(e)}")
        return False

def mostrar_correo_masivo():
    st.title("📧 Sistema de Envío de Correos Masivos")

    # Crear tabs para las diferentes secciones
    tab1, tab2, tab3 = st.tabs(["Cargar Datos", "Configurar Correo", "Enviar"])

    # TAB 1: Cargar Datos
    with tab1:
        st.header("Cargar archivo Excel con destinatarios")
        
        st.info("El archivo Excel debe contener las columnas: First Name, Last Name, Email, Phone Number, Estate, Actions")
        
        # Widget para cargar el archivo
        uploaded_file = st.file_uploader("Selecciona un archivo Excel", type=["xlsx", "xls"], key="email_file_uploader")
        
        if uploaded_file is not None:
            try:
                # Cargar datos del archivo Excel
                df = pd.read_excel(uploaded_file)
                
                # Guardar una copia del archivo original para actualizar después
                if 'uploaded_file_name' not in st.session_state:
                    st.session_state['uploaded_file_name'] = uploaded_file.name
                
                # Guardar el contenido del archivo para poder actualizarlo más tarde
                if 'original_file_content' not in st.session_state:
                    # Resetear el puntero del archivo para poder leerlo de nuevo
                    uploaded_file.seek(0)
                    st.session_state['original_file_content'] = uploaded_file.read()
                
                # Verificar columnas requeridas
                required_columns = ["First Name", "Last Name", "Email", "Phone Number", "Estate", "Actions"]
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                # Asegurarse de que existan las columnas necesarias para actualizar
                if "Email Status" not in df.columns:
                    df["Email Status"] = ""
                
                if "Shipping Date" not in df.columns:
                    df["Shipping Date"] = None
                
                if missing_columns:
                    st.error(f"El archivo no contiene las siguientes columnas requeridas: {', '.join(missing_columns)}")
                else:
                    # Mostrar dataframe
                    st.success("Archivo cargado correctamente!")
                    st.write("Vista previa de los datos:")
                    st.dataframe(df)
                    
                    # Guardar en session state
                    st.session_state['df'] = df
                    
                    # Mostrar estadísticas básicas
                    st.subheader("Resumen de los datos cargados")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de destinatarios", len(df))
                    with col2:
                        st.metric("Estados únicos", len(df["Estate"].unique()))
                    with col3:
                        emails_sin_valor = df["Email"].isna().sum()
                        st.metric("Emails vacíos", emails_sin_valor)
            
            except Exception as e:
                st.error(f"Error al procesar el archivo: {str(e)}")

    # TAB 2: Configuración del correo
    with tab2:
        st.header("Configurar correo electrónico")
        
        # Comprobar si hay datos cargados
        if 'df' not in st.session_state:
            st.warning("Primero debes cargar un archivo Excel en la pestaña 'Cargar Datos'")
        else:
            # Configuración del remitente
            st.subheader("Configuración del remitente")
            
            # Checkbox para elegir entre usar secrets o ingresar credenciales manualmente
            use_secrets = st.checkbox("Usar credenciales guardadas en secrets.toml", value=True, key="email_use_secrets")
            
            if use_secrets:
                st.info("Se utilizarán las credenciales configuradas en el archivo secrets.toml")
                try:
                    # Mostrar usuario guardado en secrets para confirmar
                    smtp_user = st.secrets['emails']['smtp_user']
                    st.success(f"Usuario configurado: {smtp_user}")
                    st.session_state['use_secrets'] = True
                except Exception as e:
                    st.error(f"No se pudieron cargar las credenciales de secrets.toml: {str(e)}")
                    st.session_state['use_secrets'] = False
                    use_secrets = False
            
            if not use_secrets:
                col1, col2 = st.columns(2)
                with col1:
                    smtp_user = "" #st.secrets['emails']['smtp_user']
                    sender_email = smtp_user #st.text_input("Email del remitente")
                    st.session_state['sender_email'] = sender_email
                with col2:
                    clave_email = cargar_configuracion()

                    if clave_email is not None:
                        clave_email_codificada = clave_email
                    else:
                        # Manejar el caso cuando la clave es None
                        st.error("No se pudo obtener la clave de email para la conexión")

                    sender_password = clave_email_codificada
                    st.session_state['sender_password'] = sender_password
        
                    st.session_state['use_secrets'] = True #False
            
            # Configuración del servidor SMTP
            st.session_state['smtp_server'] = "smtp.gmail.com"
            st.session_state['smtp_port'] = 587
            
            # Nota sobre credenciales seguras
            st.info("📌 Para Gmail, es posible que necesites una contraseña de aplicación en lugar de tu contraseña habitual. [Más información](https://support.google.com/accounts/answer/185833)")
            
            # Filtrado de destinatarios
            st.subheader("Filtrar destinatarios")
            
            # Verificar que la columna "Estate" exista y sea accesible
            if isinstance(st.session_state['df'], pd.DataFrame) and "Estate" in st.session_state['df'].columns:
                # Opciones de filtrado
                filter_options = st.multiselect("Filtrar por estado", options=st.session_state['df']["Estate"].unique(), key="email_filter_options")
                
                # Aplicar filtros si se seleccionan
                filtered_df = st.session_state['df']
                if filter_options:
                    filtered_df = filtered_df[filtered_df["Estate"].isin(filter_options)]
                
                # Mostrar destinatarios filtrados
                st.write(f"Destinatarios seleccionados: {len(filtered_df)}")
                st.dataframe(filtered_df[["First Name", "Last Name", "Email", "Estate"]])
                
                # Guardar en session state
                st.session_state['filtered_df'] = filtered_df
            else:
                st.error("El DataFrame no tiene una columna 'Estate' o no es un DataFrame válido")
            
            # Configuración del mensaje
            st.subheader("Configuración del mensaje")

            sub_remitente = st.text_input("Igrese el email del Remitente", key="sub_remite")
            email_subject = st.text_input("Asunto del correo", key="email_subject_input")
            
            st.markdown("**Contenido del mensaje:**")
            st.markdown("Puedes usar las siguientes variables para personalizar el mensaje:")
            st.markdown("- `{first_name}`: Nombre del destinatario")
            st.markdown("- `{last_name}`: Apellido del destinatario")
            st.markdown("- `{email}`: Email del destinatario")
            st.markdown("- `{estate}`: Estado/Provincia del destinatario")
            st.markdown("- `{phone}`: Número telefónico del destinatario")
            
            email_content = st.text_area(f"Contenido del correo", height=200,
                                          value=f"Remitente App: {sub_remitente}\n\n""Estimado/a {first_name} {last_name},\n\nEspero que al recibo de este mensaje se encuentre bien.\n\n[Tu mensaje aquí]\n\nSaludos cordiales,\n[Tu nombre]\n\n"f"{sub_remitente}",key="email_content_input"
                                          )
            
            # Vista previa del correo
            if st.button("Generar vista previa", key="email_preview_button"):
                if isinstance(st.session_state.get('filtered_df'), pd.DataFrame) and len(st.session_state['filtered_df']) > 0:
                    preview_row = st.session_state['filtered_df'].iloc[0]
                    try:
                        preview_content = email_content.format(
                            first_name=preview_row.get("First Name", ""),
                            last_name=preview_row.get("Last Name", ""),
                            email=preview_row.get("Email", ""),
                            estate=preview_row.get("Estate", ""),
                            phone=preview_row.get("Phone Number", "")
                        )
                        
                        st.subheader("Vista previa del correo")
                        st.markdown(f"**Para:** {preview_row.get('Email', '')}")
                        st.markdown(f"**Asunto:** {email_subject}")
                        st.markdown("**Contenido:**")
                        st.markdown(preview_content)
                        
                        # Guardar en session state
                        st.session_state['email_subject'] = email_subject
                        st.session_state['email_content'] = email_content
                    except Exception as e:
                        st.error(f"Error al generar vista previa: {str(e)}")
                else:
                    st.warning("No hay destinatarios seleccionados para generar una vista previa")

    # TAB 3: Envío de correos
    with tab3:
        st.header("Enviar correos electrónicos")
        
        # Comprobar si hay datos y configuración de correo
        if not isinstance(st.session_state.get('filtered_df'), pd.DataFrame):
            st.warning("Primero debes configurar los destinatarios en la pestaña 'Configurar Correo'")
        elif 'email_subject' not in st.session_state:
            st.warning("Primero debes configurar el contenido del correo en la pestaña 'Configurar Correo'")
        else:
            # Mostrar resumen antes del envío
            st.subheader("Resumen del envío")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Total de destinatarios:** {len(st.session_state['filtered_df'])}")
                st.markdown(f"**Asunto:** {st.session_state['email_subject']}")
            with col2:
                if st.session_state.get('use_secrets', False):
                    st.markdown(f"**Remitente Dominio:** {st.secrets['emails']['smtp_user']}")
                    st.markdown(f"**Remitente App:** {sub_remitente}")
                else:
                    st.markdown(f"**Remitente Dominio:** {st.session_state.get('sender_email', 'No configurado')}")
                    st.markdown(f"**Remitente App:** {sub_remitente}")
                st.markdown(f"**Servidor SMTP:** {st.session_state.get('smtp_server', 'No configurado')}")
            
            # Función para enviar correos
            def send_emails(progress_bar, status_text):
                if not isinstance(st.session_state.get('filtered_df'), pd.DataFrame):
                    return 0, 0, [], []
                    
                df = st.session_state['filtered_df']
                total_emails = len(df)
                success_count = 0
                error_count = 0
                error_list = []
                success_list = []
                
                # Lista para almacenar correos enviados exitosamente para actualizar Excel y Google Sheets después
                successful_sends = []
                
                try:
                    # Cargar credenciales para Google Sheets
                    creds = load_credentials_from_toml()
                    if creds:
                        gs_client = get_google_sheets_connection(creds)
                    else:
                        gs_client = None
                        status_text.warning("No se pudieron cargar las credenciales para Google Sheets")
                    
                    # Determinar qué credenciales usar para SMTP
                    if st.session_state.get('use_secrets', False):
                        try:
                            # Usar credenciales de secrets.toml
                            smtp_user = st.secrets['emails']['smtp_user']
                            smtp_password = st.secrets['emails']['smtp_password']
                        except Exception as e:
                            return 0, total_emails, [f"Error al obtener credenciales de secrets: {str(e)}"], []
                    else:
                        # Usar credenciales ingresadas manualmente
                        smtp_user = st.session_state.get('sender_email')
                        smtp_password = st.session_state.get('sender_password')
                        
                        if not smtp_user or not smtp_password:
                            return 0, total_emails, ["Error: Email o contraseña no configurados"], []
                    
                    # Obtener configuración del servidor
                    smtp_server = st.session_state.get('smtp_server', 'smtp.gmail.com')
                    smtp_port = int(st.session_state.get('smtp_port', 587))
                    
                    # Mostrar información de depuración
                    status_text.text(f"Conectando a {smtp_server}:{smtp_port} con usuario {smtp_user}...")
                    
                    # Configurar servidor SMTP
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.ehlo()  # Puede ayudar con la conexión
                    server.starttls()
                    server.ehlo()  # Necesario después de STARTTLS
                    
                    # Intentar login
                    status_text.text("Intentando autenticación...")
                    server.login(smtp_user, smtp_password)
                    status_text.text("Autenticación exitosa. Iniciando envío de correos...")
                    
                    # Fecha actual para el campo Shipping Date
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    
                    # Enviar correos uno por uno
                    for i, (index, row) in enumerate(df.iterrows()):
                        try:
                            # Verificar que el email es válido
                            if pd.isna(row['Email']) or not isinstance(row['Email'], str) or '@' not in row['Email']:
                                raise ValueError("Dirección de email inválida")
                                
                            # Crear mensaje personalizado
                            msg = MIMEMultipart()
                            msg['From'] = smtp_user
                            msg['To'] = row['Email']
                            msg['Subject'] = st.session_state['email_subject']
                            
                            # Personalizar contenido con manejo seguro de valores faltantes
                            try:
                                personalized_content = st.session_state['email_content'].format(
                                    first_name=row.get("First Name", ""),
                                    last_name=row.get("Last Name", ""),
                                    email=row.get("Email", ""),
                                    estate=row.get("Estate", ""),
                                    phone=row.get("Phone Number", "")
                                )
                            except Exception as format_error:
                                # Si hay error en el formato, usar contenido genérico
                                personalized_content = f"Estimado/a destinatario,\n\n{st.session_state['email_content']}"
                            
                            msg.attach(MIMEText(personalized_content, 'plain'))
                            
                            # Enviar correo
                            server.send_message(msg)
                            success_count += 1
                            
                            # Guardar el email y su índice para actualizar el Excel y Google Sheets después
                            successful_sends.append({
                                'index': index,
                                'email': row['Email']
                            })
                            
                            # Actualizamos el Google Sheet para este email
                            if gs_client:
                                update_status = update_google_sheet(gs_client, row['Email'])
                                if update_status:
                                    success_list.append(f"Email enviado y Google Sheets actualizado: {row['Email']}")
                                else:
                                    success_list.append(f"Email enviado pero Google Sheets no se actualizó: {row['Email']}")
                            else:
                                success_list.append(f"Email enviado (sin actualización de Google Sheets): {row['Email']}")
                            
                            # Actualizar barra de progreso
                            progress_bar.progress((i + 1) / total_emails)
                            status_text.text(f"Procesando {i+1}/{total_emails}: Enviado a {row['Email']}")
                            
                            # Pequeña pausa para evitar limitaciones de envío
                            time.sleep(0.5)
                            
                        except Exception as e:
                            error_count += 1
                            error_list.append(f"{row.get('Email', 'Email desconocido')}: {str(e)}")
                            status_text.text(f"Error al enviar a {row.get('Email', 'Email desconocido')}: {str(e)}")
                            progress_bar.progress((i + 1) / total_emails)
                            time.sleep(0.5)
                    
                    # Cerrar conexión
                    server.quit()
                    
                    # Actualizar el DataFrame original con los estados
                    if 'df' in st.session_state and isinstance(st.session_state['df'], pd.DataFrame):
                        for send_info in successful_sends:
                            idx = send_info['index']
                            # Actualizar estado y fecha de envío
                            st.session_state['df'].at[idx, 'Email Status'] = 'Sent'
                            st.session_state['df'].at[idx, 'Shipping Date'] = current_date
                        
                        # Guardar los cambios en el Excel original si existe
                        if 'original_file_content' in st.session_state and 'uploaded_file_name' in st.session_state:
                            # Crear un archivo temporal con el Excel actualizado
                            updated_excel = f"updated_{st.session_state['uploaded_file_name']}"
                            st.session_state['df'].to_excel(updated_excel, index=False)
                            
                            # Permitir al usuario descargar el archivo actualizado
                            with open(updated_excel, 'rb') as f:
                                st.session_state['updated_excel_data'] = f.read()
                                st.session_state['updated_excel_name'] = updated_excel
                    
                    return success_count, error_count, error_list, success_list
                    
                except Exception as e:
                    return 0, total_emails, [f"Error de conexión: {str(e)}"], []
            
            # Botón para probar conexión SMTP
            if st.button("Probar conexión SMTP", key="email_test_connection"):
                with st.spinner("Probando conexión al servidor SMTP..."):
                    try:
                        # Determinar qué credenciales usar
                        if st.session_state.get('use_secrets', False):
                            smtp_user = st.secrets['emails']['smtp_user']
                            smtp_password = st.secrets['emails']['smtp_password']
                        else:
                            smtp_user = st.session_state.get('sender_email')
                            smtp_password = st.session_state.get('sender_password')
                        
                        # Obtener configuración del servidor
                        smtp_server = st.session_state.get('smtp_server', 'smtp.gmail.com')
                        smtp_port = int(st.session_state.get('smtp_port', 587))
                        
                        # Intentar conexión
                        server = smtplib.SMTP(smtp_server, smtp_port)
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(smtp_user, smtp_password)
                        server.quit()
                        
                        st.success(f"✅ Conexión exitosa a {smtp_server} con el usuario {smtp_user}")
                    except Exception as e:
                        st.error(f"❌ Error de conexión: {str(e)}")
                        st.warning("Si estás usando Gmail, asegúrate de utilizar una 'Contraseña de aplicación' en lugar de tu contraseña normal.")
            
            # Probar conexión a Google Sheets
            if st.button("Probar conexión a Google Sheets", key="gs_test_connection"):
                with st.spinner("Probando conexión a Google Sheets..."):
                    try:
                        creds = load_credentials_from_toml()
                        if creds:
                            client = get_google_sheets_connection(creds)
                            if client:
                                # Intentar acceder a la hoja
                                all_data = get_all_data(client)
                                if isinstance(all_data, list):
                                    st.success(f"✅ Conexión exitosa a Google Sheets. Se encontraron {len(all_data)} registros.")
                                else:
                                    st.warning("La conexión fue exitosa pero no se pudieron obtener datos.")
                            else:
                                st.error("Error al conectar con Google Sheets.")
                        else:
                            st.error("No se pudieron cargar las credenciales para Google Sheets.")
                    except Exception as e:
                        st.error(f"❌ Error de conexión a Google Sheets: {str(e)}")
            
            # Botón para iniciar el envío
            if st.button("Iniciar envío de correos", key="email_send_button"):
                if isinstance(st.session_state.get('filtered_df'), pd.DataFrame) and len(st.session_state['filtered_df']) > 0:
                    with st.spinner("Enviando correos..."):
                        # Crear elementos de progreso
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Ejecutar envío
                        success_count, error_count, error_list, success_list = send_emails(progress_bar, status_text)
                        
                        # Mostrar resultados
                        if success_count > 0:
                            st.success(f"✅ {success_count} correos enviados correctamente")
                            
                            # Ofrecer descarga del Excel actualizado
                            if 'updated_excel_data' in st.session_state and 'updated_excel_name' in st.session_state:
                                st.download_button(
                                    label="Descargar Excel actualizado",
                                    data=st.session_state['updated_excel_data'],
                                    file_name=st.session_state['updated_excel_name'],
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            
                            # Mostrar detalles de éxitos
                            if success_list:
                                with st.expander("Ver detalles de envíos exitosos"):
                                    for success in success_list:
                                        st.success(success)
                        
                        if error_count > 0:
                            st.error(f"❌ {error_count} correos no pudieron ser enviados")
                            with st.expander("Ver detalles de errores"):
                                for error in error_list:
                                    st.error(error)
                else:
                    st.warning("No hay destinatarios seleccionados para enviar correos")

#if __name__ == "__main__":
#    mostrar_correo_masivo()