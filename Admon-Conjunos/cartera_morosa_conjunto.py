import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import base64
import ssl
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Configuración de la página
#st.set_page_config(
#    page_title="🏢 Gestión de Cartera Morosa",
#    page_icon="🏢",
#    layout="wide",
#    initial_sidebar_state="expanded"
#)

def format_currency(value):
    """Formatear valores monetarios con separador de miles"""
    if pd.isna(value) or value == 0:
        return "$0"
    return f"${value:,.0f}".replace(',', '.')

# Funciones para formateo de moneda colombiana
def format_currency_cop(value):
    """Formatear valor como moneda colombiana"""
    if pd.isna(value) or value == 0:
        return "$0"
    
    try:
        # Convertir a float si es necesario
        if isinstance(value, str):
            # Remover caracteres no numéricos excepto punto y coma
            clean_value = ''.join(c for c in value if c.isdigit() or c in '.,')
            if clean_value:
                value = float(clean_value.replace(',', ''))
            else:
                return "$0"
        
        value = float(value)
        
        # Formatear con separadores de miles
        formatted = "{:,.0f}".format(value)
        # Reemplazar comas por puntos para formato colombiano
        formatted = formatted.replace(',', '.')
        
        return f"${formatted}"
    except (ValueError, TypeError):
        return "$0"

def parse_currency_cop(currency_str):
    """Convertir string de moneda colombiana a número"""
    if not currency_str or currency_str == "$0":
        return 0.0
    
    try:
        # Remover símbolo de peso y espacios
        clean_str = currency_str.replace('$', '').replace(' ', '')
        # Reemplazar puntos por nada (separadores de miles)
        clean_str = clean_str.replace('.', '')
        # Si hay coma, es separador decimal
        if ',' in clean_str:
            clean_str = clean_str.replace(',', '.')
        
        return float(clean_str) if clean_str else 0.0
    except (ValueError, TypeError):
        return 0.0

def format_currency_input(value):
    """Formatear input de moneda en tiempo real"""
    if value == 0:
        return ""
    return format_currency_cop(value)

# Función para cargar credenciales
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
        #return client
    
        # Verificar la conexión intentando listar las hojas
        try:
            sheets = client.openall()
            st.success(f"✅ Conexión exitosa! y disponible")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def get_or_create_sheet(client, sheet_name="gestion-conjuntos", worksheet_name="gestion_morosos"):
    """Obtener o crear la hoja de cálculo y worksheet"""
    try:
        # Intentar abrir la hoja existente
        sheet = client.open(sheet_name)
        #st.info(f"📊 Hoja '{sheet_name}' encontrada")
    except gspread.SpreadsheetNotFound:
        # Crear nueva hoja si no existe
        sheet = client.create(sheet_name)
        st.success(f"📊 Nueva hoja '{sheet_name}' creada")
    
    try:
        # Intentar abrir el worksheet
        worksheet = sheet.worksheet(worksheet_name)
        #st.info(f"📋 Worksheet '{worksheet_name}' encontrado")
    except gspread.WorksheetNotFound:
        # Crear nuevo worksheet si no existe
        worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        # Crear encabezados
        headers = [
            "ID", "Fecha_Registro", "Apartamento/Casa", "Propietario", "Cedula", 
            "Telefono", "Email", "Valor_Deuda", "Concepto_Deuda", "Fecha_Vencimiento",
            "Dias_Mora", "Estado_Gestion", "Tipo_Gestion", "Fecha_Ultimo_Contacto",
            "Observaciones", "Accion_Juridica", "Fecha_Accion_Juridica", "Valor_Pagado",
            "Fecha_Pago", "Saldo_Pendiente"
        ]
        worksheet.append_row(headers)
        st.success(f"📋 Nuevo worksheet '{worksheet_name}' creado con encabezados")
    
    return sheet, worksheet

def load_data(worksheet):
    """Cargar datos desde Google Sheets"""
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            # Convertir fechas
            date_columns = ['Fecha_Registro', 'Fecha_Vencimiento', 'Fecha_Ultimo_Contacto', 
                          'Fecha_Accion_Juridica', 'Fecha_Pago']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Convertir valores numéricos
            numeric_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente', 'Dias_Mora']
            for col in numeric_columns:
                if col in df.columns:
                    # Si ya son números, mantenerlos, si son strings con formato, convertirlos
                    df[col] = df[col].apply(lambda x: parse_currency_cop(str(x)) if pd.notna(x) else 0)
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando datos: {str(e)}")
        return pd.DataFrame()

def save_data(worksheet, df):
    """Guardar datos en Google Sheets"""
    try:
        # Limpiar la hoja excepto los encabezados
        worksheet.clear()
        
        # Escribir encabezados
        headers = list(df.columns)
        worksheet.append_row(headers)
        
        # Escribir datos
        if not df.empty:
            # Convertir fechas a string para Google Sheets
            df_copy = df.copy()
            date_columns = ['Fecha_Registro', 'Fecha_Vencimiento', 'Fecha_Ultimo_Contacto', 
                          'Fecha_Accion_Juridica', 'Fecha_Pago']
            for col in date_columns:
                if col in df_copy.columns:
                    df_copy[col] = df_copy[col].astype(str)

            # Guardar valores monetarios como números para cálculos, pero mostrar formateados
            numeric_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente']
            for col in numeric_columns:
                if col in df_copy.columns:
                    # Mantener como números para Google Sheets
                    df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').fillna(0)        
            
            # Convertir DataFrame a lista de listas
            data_list = df_copy.values.tolist()
            worksheet.append_rows(data_list)
        
        st.success("✅ Datos guardados exitosamente en Google Sheets")
        return True
    except Exception as e:
        st.error(f"❌ Error guardando datos: {str(e)}")
        return False

def calculate_mora_days(fecha_vencimiento):
    """Calcular días de mora"""
    if pd.isna(fecha_vencimiento):
        return 0
    
    if isinstance(fecha_vencimiento, str):
        try:
            fecha_vencimiento = pd.to_datetime(fecha_vencimiento)
        except:
            return 0
    
    today = datetime.now()
    if fecha_vencimiento < today:
        return (today - fecha_vencimiento).days
    return 0

def get_estado_by_dias_mora(dias_mora):
    """Determinar estado según días de mora"""
    if dias_mora <= 30:
        return "Al Día"
    elif dias_mora <= 60:
        return "Mora Temprana"
    elif dias_mora <= 90:
        return "Mora Media"
    elif dias_mora <= 180:
        return "Mora Tardía"
    else:
        return "Cobro Jurídico"

def cartera_morosa_main():
    # Título principal
    st.title("🏢 Sistema de Gestión de Cartera Morosa")
    st.markdown("### 📋 Control y Manejo de Cobro Prejurídico - Condominios")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Obtener o crear hoja
    sheet, worksheet = get_or_create_sheet(client)
    
    # Cargar datos existentes
    df = load_data(worksheet)
    
    # Sidebar para navegación
    st.sidebar.title("🔧 Panel de Control")
    menu_option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["📊 Panel", "➕ Nuevo Registro", "📝 Gestionar Registros", 
         "📞 Gestión de Cobro", "📈 Reportes", "⚙️ Configuración"]
    )
    
    if menu_option == "📊 Panel Principal":
        show_dashboard(df)
    elif menu_option == "➕ Nuevo Registro":
        show_new_record_form(df, worksheet)
    elif menu_option == "📝 Gestionar Registros":
        show_manage_records(df, worksheet)
    elif menu_option == "📞 Gestión de Cobro":
        show_collection_management(df, worksheet)
    elif menu_option == "📈 Reportes":
        show_reports(df)
    elif menu_option == "⚙️ Configuración":
        show_configuration()

def show_dashboard(df):
    """Mostrar dashboard principal"""
    st.header("📊 P de Cartera Morosa")
    
    if df.empty:
        st.warning("📋 No hay datos disponibles. Comienza agregando registros.")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_deudores = len(df)
        st.metric("👥 Total Deudores", format_currency_cop(total_deudores))

    
    with col2:
        total_deuda = df['Valor_Deuda'].sum()
        st.metric("💰 Deuda Total", format_currency_cop(total_deuda))
    
    with col3:
        total_pagado = df['Valor_Pagado'].sum()
        st.metric("💚 Total Pagado", format_currency_cop(total_pagado))
    
    with col4:
        saldo_pendiente = df['Saldo_Pendiente'].sum()
        st.metric("⚠️ Saldo Pendiente", format_currency_cop(saldo_pendiente))
    
    # Actualizar días de mora y estados
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    df['Estado_Calculado'] = df['Dias_Mora'].apply(get_estado_by_dias_mora)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribución por Estado de Mora")
        estado_counts = df['Estado_Calculado'].value_counts()
        fig_pie = px.pie(
            values=estado_counts.values, 
            names=estado_counts.index,
            title="Estados de Mora"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📈 Evolución de Deudas")
        df_grouped = df.groupby('Estado_Calculado').agg({
            'Valor_Deuda': 'sum',
            'Saldo_Pendiente': 'sum'
        }).reset_index()
        
        fig_bar = px.bar(
            df_grouped, 
            x='Estado_Calculado', 
            y=['Valor_Deuda', 'Saldo_Pendiente'],
            title="Deuda vs Saldo Pendiente por Estado",
            barmode='group'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabla de casos críticos
    st.subheader("🚨 Casos Críticos (Más de 90 días)")
    casos_criticos = df[df['Dias_Mora'] > 90].sort_values('Dias_Mora', ascending=False)
    if not casos_criticos.empty:
        # Formatear valores monetarios para mostrar
        casos_display = casos_criticos.copy()
        casos_display['Valor_Deuda_Fmt'] = casos_display['Valor_Deuda'].apply(format_currency_cop)
        casos_display['Saldo_Pendiente_Fmt'] = casos_display['Saldo_Pendiente'].apply(format_currency_cop)
        st.dataframe(
            casos_criticos[['Apartamento/Casa', 'Propietario', 'Valor_Deuda', 
                          'Dias_Mora', 'Estado_Calculado']],
            use_container_width=True
        )
    else:
        st.success("✅ No hay casos críticos actualmente")

def show_new_record_form(df, worksheet):
    """Formulario para nuevo registro"""
    st.header("➕ Nuevo Registro de Deuda")
    
    with st.form("nuevo_registro"):
        col1, col2 = st.columns(2)
        
        with col1:
            apartamento = st.text_input("🏠 Apartamento/Casa*", placeholder="Ej: Apto 101, Casa 15")
            propietario = st.text_input("👤 Nombre Propietario*", placeholder="Nombre completo")
            cedula = st.text_input("🆔 Cédula*", placeholder="Número de identificación")
            telefono = st.text_input("📱 Teléfono", placeholder="Número de contacto")
            email = st.text_input("📧 Email", placeholder="correo@ejemplo.com")
        
        with col2:
            valor_deuda = st.number_input("💰 Valor de la Deuda*", placeholder="Ej: 150000 o 1500000",
                help="Ingrese el valor sin puntos ni comas. Ejemplo: 150000 para $150.000")
            concepto = st.selectbox("📋 Concepto de la Deuda*", [
                "Administración", "Parqueadero", "Cuota Extraordinaria", 
                "Multas", "Servicios", "Otros"
            ])
            fecha_vencimiento = st.date_input("📅 Fecha de Vencimiento*")
            observaciones = st.text_area("📝 Observaciones", placeholder="Detalles adicionales...")

        # Mostrar preview del valor formateado
        #if valor_deuda:
        #    try:
        #        valor_preview = float(valor_deuda_input.replace('.', '').replace(',', ''))
        #        st.info(f"💰 Valor formateado: {format_currency_cop(valor_preview)}")
        #    except:
        #        st.warning("⚠️ Ingrese solo números para el valor de la deuda")
        
        submitted = st.form_submit_button("💾 Guardar Registro", type="primary")
        
        if submitted:

            #try:
            #    valor_deuda = float(valor_deuda_input.replace('.', '').replace(',', '')) if valor_deuda_input else 0
            #except:
            #    valor_deuda = 0

            if apartamento and propietario and cedula and valor_deuda > 0:
                # Crear nuevo ID
                nuevo_id = len(df) + 1 if not df.empty else 1
                
                # Calcular días de mora
                dias_mora = calculate_mora_days(pd.to_datetime(fecha_vencimiento))
                estado_gestion = get_estado_by_dias_mora(dias_mora)
                
                # Crear nuevo registro
                nuevo_registro = {
                    'ID': nuevo_id,
                    'Fecha_Registro': datetime.now().strftime('%Y-%m-%d'),
                    'Apartamento/Casa': apartamento,
                    'Propietario': propietario,
                    'Cedula': cedula,
                    'Telefono': telefono,
                    'Email': email,
                    'Valor_Deuda': valor_deuda,
                    'Concepto_Deuda': concepto,
                    'Fecha_Vencimiento': fecha_vencimiento.strftime('%Y-%m-%d'),
                    'Dias_Mora': dias_mora,
                    'Estado_Gestion': estado_gestion,
                    'Tipo_Gestion': 'Pendiente',
                    'Fecha_Ultimo_Contacto': '',
                    'Observaciones': observaciones,
                    'Accion_Juridica': 'No',
                    'Fecha_Accion_Juridica': '',
                    'Valor_Pagado': 0,
                    'Fecha_Pago': '',
                    'Saldo_Pendiente': valor_deuda
                }
                
                # Agregar al DataFrame
                if df.empty:
                    df_nuevo = pd.DataFrame([nuevo_registro])
                else:
                    df_nuevo = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
                
                # Guardar en Google Sheets
                if save_data(worksheet, df_nuevo):
                    st.success(f"✅ Registro guardado exitosamente - Valor: {format_currency_cop(valor_deuda)}")
                    st.rerun()
            else:
                st.error("❌ Por favor complete todos los campos obligatorios (*)")

def show_manage_records(df, worksheet):
    """Gestionar registros existentes"""
    st.header("📝 Gestionar Registros")
    
    if df.empty:
        st.warning("📋 No hay registros para gestionar")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filtro_estado = st.selectbox("Filtrar por Estado:", 
                                   ["Todos"] + df['Estado_Gestion'].dropna().unique().tolist())
    
    with col2:
        filtro_apartamento = st.selectbox("Filtrar por Apartamento:", 
                                        ["Todos"] + df['Apartamento/Casa'].dropna().unique().tolist())
    
    with col3:
        dias_mora_min = st.number_input("Días de mora mínimos:", min_value=0, value=0)
    
    # Aplicar filtros
    df_filtrado = df.copy()
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Estado_Gestion'] == filtro_estado]
    if filtro_apartamento != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Apartamento/Casa'] == filtro_apartamento]
    
    df_filtrado['Dias_Mora'] = df_filtrado['Fecha_Vencimiento'].apply(calculate_mora_days)
    df_filtrado = df_filtrado[df_filtrado['Dias_Mora'] >= dias_mora_min]
    
    # Mostrar tabla editable
    st.subheader(f"📊 Registros Encontrados: {len(df_filtrado)}")
    
    if not df_filtrado.empty:
        # Selección de registro para editar
        registro_seleccionado = st.selectbox(
            "Seleccionar registro para editar:",
            options=df_filtrado['ID'].tolist(),
            format_func=lambda x: f"ID {x} - {df_filtrado[df_filtrado['ID']==x]['Propietario'].iloc[0]} - {df_filtrado[df_filtrado['ID']==x]['Apartamento/Casa'].iloc[0]}"
        )
        
        if registro_seleccionado:
            registro = df_filtrado[df_filtrado['ID'] == registro_seleccionado].iloc[0]

            # Mostrar información actual del registro
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"**💰 Deuda Actual:** {format_currency_cop(registro['Valor_Deuda'])}")
                st.info(f"**💸 Pagado:** {format_currency_cop(registro['Valor_Pagado'])}")
            with col_info2:
                st.info(f"**⚠️ Saldo Pendiente:** {format_currency_cop(registro['Saldo_Pendiente'])}")
                st.info(f"**📅 Días de Mora:** {registro['Dias_Mora']} días")
            
            with st.form("editar_registro"):
                st.subheader(f"✏️ Editando Registro ID: {registro_seleccionado}")
                
                col1, col2 = st.columns(2)
                
                with col1:

                    nuevo_estado = st.selectbox("Estado de Gestión:", 
                                              ["Al Día", "Mora Temprana", "Mora Media", 
                                               "Mora Tardía", "Cobro Jurídico", "Pagado"],
                                              index=0 if pd.isna(registro['Estado_Gestion']) else 
                                              ["Al Día", "Mora Temprana", "Mora Media", 
                                               "Mora Tardía", "Cobro Jurídico", "Pagado"].index(registro['Estado_Gestion']) 
                                              if registro['Estado_Gestion'] in ["Al Día", "Mora Temprana", "Mora Media", "Mora Tardía", "Cobro Jurídico", "Pagado"] else 0)
                    
                    tipo_gestion = st.selectbox("Tipo de Gestión:", 
                                              ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"],
                                              index=0 if pd.isna(registro['Tipo_Gestion']) else 
                                              ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"].index(registro['Tipo_Gestion'])
                                              if registro['Tipo_Gestion'] in ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"] else 0)
                    
                    valor_pagado_input = st.text_input(
                        "💸 Valor Pagado:", 
                        value=str(int(registro['Valor_Pagado'])) if not pd.isna(registro['Valor_Pagado']) and registro['Valor_Pagado'] > 0 else "",
                        placeholder="Ingrese solo números", help="Ejemplo: 150000 para $150.000"
                    )
                
                with col2:
                    fecha_contacto = st.date_input("Fecha Último Contacto:", 
                                                 value=datetime.now().date())
                    
                    accion_juridica = st.selectbox("Acción Jurídica:", ["No", "Sí"],
                                                 index=1 if registro['Accion_Juridica'] == 'Sí' else 0)
                    
                    observaciones_edit = st.text_area("Observaciones:", 
                                                    value=registro['Observaciones'] if not pd.isna(registro['Observaciones']) else "")

                # Preview del valor pagado
                if valor_pagado_input:
                    try:
                        valor_pagado_preview = float(valor_pagado_input.replace('.', '').replace(',', ''))
                        st.info(f"💸 Valor a pagar formateado: {format_currency_cop(valor_pagado_preview)}")
                        nuevo_saldo = float(registro['Valor_Deuda']) - valor_pagado_preview
                        st.info(f"💰 Nuevo saldo pendiente: {format_currency_cop(nuevo_saldo)}")
                    except:
                        st.warning("⚠️ Ingrese solo números para el valor pagado")
                
                actualizar = st.form_submit_button("💾 Actualizar Registro", type="primary")
                
                if actualizar:

                    try:
                        valor_pagado = float(valor_pagado_input.replace('.', '').replace(',', '')) if valor_pagado_input else 0
                    except:
                        valor_pagado = float(registro['Valor_Pagado']) if not pd.isna(registro['Valor_Pagado']) else 0

                    # Actualizar el registro en el DataFrame
                    idx = df[df['ID'] == registro_seleccionado].index[0]
                    df.loc[idx, 'Estado_Gestion'] = nuevo_estado
                    df.loc[idx, 'Tipo_Gestion'] = tipo_gestion
                    df.loc[idx, 'Fecha_Ultimo_Contacto'] = fecha_contacto.strftime('%Y-%m-%d')
                    df.loc[idx, 'Valor_Pagado'] = valor_pagado
                    df.loc[idx, 'Saldo_Pendiente'] = float(registro['Valor_Deuda']) - valor_pagado
                    df.loc[idx, 'Accion_Juridica'] = accion_juridica
                    df.loc[idx, 'Observaciones'] = observaciones_edit
                    
                    if accion_juridica == 'Sí' and pd.isna(registro['Fecha_Accion_Juridica']):
                        df.loc[idx, 'Fecha_Accion_Juridica'] = datetime.now().strftime('%Y-%m-%d')
                    
                    # Guardar cambios
                    if save_data(worksheet, df):
                        st.success("✅ Registro actualizado exitosamente")
                        st.rerun()

# Función para enviar correo electrónico
def send_email_to_resident(email_to, nombre, asunto, mensaje, tipo_mensaje):
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
        if tipo_mensaje == "Anuncio General":
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

def send_bulk_collection_emails(emails_info, tipo_mensaje="Recordatorio"):
    """
    Envía correos masivos de cobro
    
    Args:
        emails_info: Lista de diccionarios con información de cada correo
        tipo_mensaje: Tipo de mensaje a enviar
    
    Returns:
        tuple: (successful_count, failed_count, errors_list)
    """
    successful = 0
    failed = 0
    errors = []
    
    for email_info in emails_info:
        try:
            exito, mensaje_resultado = send_email_to_resident(
                email_to=email_info['email'],
                nombre=email_info['nombre'],
                asunto=email_info['asunto'],
                mensaje=email_info['mensaje'],
                tipo_mensaje=tipo_mensaje
            )
            
            if exito:
                successful += 1
            else:
                failed += 1
                errors.append({
                    'email': email_info['email'],
                    'nombre': email_info['nombre'],
                    'error': mensaje_resultado,
                    'caso_id': email_info.get('caso_id')
                })
                
        except Exception as e:
            failed += 1
            errors.append({
                'email': email_info['email'],
                'nombre': email_info['nombre'],
                'error': str(e),
                'caso_id': email_info.get('caso_id')
            })
    
    return successful, failed, errors

def show_collection_management(df, worksheet):
    """Gestión de cobro"""
    st.header("📞 Gestión de Cobro Prejurídico")
    
    if df.empty:
        st.warning("📋 No hay registros para gestionar")
        return
    
    # Actualizar días de mora
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    
    # Casos por gestionar (con saldo pendiente > 0)
    casos_pendientes = df[(df['Saldo_Pendiente'] > 0) & (df['Estado_Gestion'] != 'Pagado')]
    
    if casos_pendientes.empty:
        st.success("✅ No hay casos pendientes de cobro")
        return
    
    st.subheader(f"📋 Casos Pendientes de Cobro: {len(casos_pendientes)}")
    
    # Priorizar casos por días de mora
    casos_priorizados = casos_pendientes.sort_values('Dias_Mora', ascending=False)
    
    # Mostrar casos críticos
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🚨 Casos Prioritarios")
        for idx, caso in casos_priorizados.head(10).iterrows():
            with st.expander(f"🏠 {caso['Apartamento/Casa']} - {caso['Propietario']} ({caso['Dias_Mora']} días)"):
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.write(f"**💰 Deuda:** {format_currency(caso['Valor_Deuda'])}")
                    st.write(f"**💸 Pagado:** {format_currency(caso['Valor_Pagado'])}")
                    st.write(f"**⚠️ Saldo:** {format_currency(caso['Saldo_Pendiente'])}")
                    st.write(f"**📱 Teléfono:** {caso['Telefono']}")
                
                with col_b:
                    st.write(f"**📅 Vencimiento:** {caso['Fecha_Vencimiento']}")
                    st.write(f"**📞 Último contacto:** {caso['Fecha_Ultimo_Contacto']}")
                    st.write(f"**📋 Estado:** {caso['Estado_Gestion']}")
                    st.write(f"**⚖️ Jurídico:** {caso['Accion_Juridica']}")
                    # Mostrar email si existe
                    if 'Email' in caso and not pd.isna(caso['Email']):
                        st.write(f"**📧 Email:** {caso['Email']}")
                
                # Acciones rápidas - Ahora con 4 columnas para incluir correo
                col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
                
                with col_btn1:
                    # Inicializar estado si no existe
                    if f"show_form_contacto_{caso['ID']}" not in st.session_state:
                        st.session_state[f"show_form_contacto_{caso['ID']}"] = False
    
                    if st.button(f"📞 Contactar", key=f"contact_{caso['ID']}"):
                        st.session_state[f"show_form_contacto_{caso['ID']}"] = True
    
                    # Mostrar formulario si está activado
                    if st.session_state[f"show_form_contacto_{caso['ID']}"]:
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
                        with st.form(f"form_contacto_{caso['ID']}"):
                            st.write("**Registrar Contacto**")
            
                            observaciones_edit = st.text_area(
                                "Observaciones del contacto:", 
                                value=caso['Observaciones'] if not pd.isna(caso['Observaciones']) else "",
                                placeholder="Describa el resultado del contacto..."
                            )

                            # Sin columnas anidadas - botones uno debajo del otro
                            contactar = st.form_submit_button("💾 Guardar Contacto", type="primary")
                            cancelar = st.form_submit_button("❌ Cancelar")
            
                            if contactar:
                                try:
                                    # Buscar la fila correspondiente en Google Sheets
                                    cell_list = worksheet.findall(str(caso['ID']))
                                    if cell_list:
                                        fila = cell_list[0].row
                        
                                        # Actualizar los campos
                                        worksheet.update(f'M{fila}', [['Llamada']])  # Tipo_Gestion
                                        worksheet.update(f'N{fila}', [[fecha_actual]])  # Fecha_Ultimo_Contacto
                                        worksheet.update(f'O{fila}', [[observaciones_edit]])  # Observaciones
                        
                                        st.success(f"✅ Contacto registrado exitosamente para {caso['Propietario']}")
                        
                                        # Resetear el estado del formulario
                                        st.session_state[f"show_form_contacto_{caso['ID']}"] = False
                                        st.rerun()
                                    else:
                                        st.error("❌ No se pudo encontrar el registro")
                                except Exception as e:
                                    st.error(f"❌ Error al actualizar: {str(e)}")
            
                            if cancelar:
                                # Resetear el estado del formulario
                                st.session_state[f"show_form_contacto_{caso['ID']}"] = False
                                st.rerun()

                
                with col_btn2:
                    # Inicializar estado si no existe
                    if f"show_form_pago_{caso['ID']}" not in st.session_state:
                        st.session_state[f"show_form_pago_{caso['ID']}"] = False
    
                    if st.button(f"💰 Pago", key=f"payment_{caso['ID']}"):
                        st.session_state[f"show_form_pago_{caso['ID']}"] = True
    
                        # Mostrar formulario si está activado
                    if st.session_state[f"show_form_pago_{caso['ID']}"]:
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
                        with st.form(f"form_pago_{caso['ID']}"):
                            st.write("**Registrar Pago**")
            
                            valor_pago = st.number_input(
                                "Valor del pago:", key=f"valor_pago_{caso['ID']}"
                            )

                            fecha_pago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
                            observaciones = st.text_area(
                                "Observaciones del pago:", value=caso['Observaciones'] if not pd.isna(caso['Observaciones']) else "",
                                placeholder="Describa los detalles del pago...",
                                key=f"obs_pago_{caso['ID']}"
                            )
            
                            # Botones sin columnas anidadas
                            guardar_pago = st.form_submit_button("💾 Guardar Pago", type="primary")
                            cancelar_pago = st.form_submit_button("❌ Cancelar")
            
                            if guardar_pago:
                                try:
                                    # Buscar la fila correspondiente en Google Sheets
                                    cell_list = worksheet.findall(str(caso['ID']))
                                    if cell_list:
                                        fila = cell_list[0].row
                        
                                        # Actualizar los campos
                                        worksheet.update(f'M{fila}', [['Llamada']])  # Tipo_Gestion
                                        worksheet.update(f'R{fila}', [[valor_pago]])  # Valor_Pagado
                                        worksheet.update(f'N{fila}', [[fecha_actual]])  # Fecha_Ultimo_Contacto
                                        worksheet.update(f'S{fila}', [[fecha_pago]])  # Fecha_Ultimo_pago

                                        nuevo_saldo = float(caso['Saldo_Pendiente']) - float(valor_pago)
                                        worksheet.update(f'T{fila}', [[nuevo_saldo]])

                                        valor_deuda = float(caso['Valor_Deuda']) - float(valor_pago)
                                        worksheet.update(f'T{fila}', [[valor_deuda]])

                                        worksheet.update(f'O{fila}', [[observaciones]])  # Observaciones
                        
                                        st.success(f"✅ Pago registrado exitosamente para {caso['Propietario']}")
                        
                                        # Resetear el estado del formulario
                                        st.session_state[f"show_form_pago_{caso['ID']}"] = False
                                        st.rerun()
                                    else:
                                        st.error("❌ No se pudo encontrar el registro")
                                except Exception as e:
                                    st.error(f"❌ Error al actualizar: {str(e)}")
            
                            if cancelar_pago:
                                # Resetear el estado del formulario
                                st.session_state[f"show_form_pago_{caso['ID']}"] = False
                                st.rerun()
                
                with col_btn3:
                    # Inicializar estado si no existe
                    if f"show_form_juridico_{caso['ID']}" not in st.session_state:
                        st.session_state[f"show_form_juridico_{caso['ID']}"] = False
    
                    if st.button(f"⚖️ Jurídico", key=f"legal_{caso['ID']}"):
                        st.session_state[f"show_form_juridico_{caso['ID']}"] = True
    
                        # Mostrar formulario si está activado
                        if st.session_state[f"show_form_juridico_{caso['ID']}"]:
                            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
                            with st.form(f"form_juridico_{caso['ID']}"):
                                st.write("**Iniciar Proceso Jurídico**")
            
                                observaciones = st.text_area(
                                    "Observaciones del proceso jurídico:", value=caso['Observaciones'] if not pd.isna(caso['Observaciones']) else "",
                                    placeholder="Describa el motivo y detalles del proceso jurídico...",
                                    key=f"obs_juridico_{caso['ID']}"
                                )
            
                                # Botones sin columnas anidadas
                                iniciar_proceso = st.form_submit_button("💾 Iniciar Proceso", type="primary")
                                cancelar_juridico = st.form_submit_button("❌ Cancelar")
            
                                if iniciar_proceso:
                                    try:
                                        # Buscar la fila correspondiente en Google Sheets
                                        cell_list = worksheet.findall(str(caso['ID']))
                                        if cell_list:
                                            fila = cell_list[0].row
                        
                                            # Actualizar los campos
                                            worksheet.update(f'M{fila}', [['Visita']])  # 

                                            worksheet.update(f'P{fila}', [['Si']])  # Tipo_Gestion
                                            worksheet.update(f'Q{fila}', [[fecha_actual]])  # Fecha_Accion_Juridica
                                            worksheet.update(f'N{fila}', [[fecha_actual]])  # Fecha_Ultimo_Contacto
                                            worksheet.update(f'O{fila}', [[observaciones]])  # Observaciones
                        
                                            st.success(f"✅ Proceso jurídico iniciado para {caso['Propietario']}")
                        
                                            # Resetear el estado del formulario
                                            st.session_state[f"show_form_juridico_{caso['ID']}"] = False
                                            st.rerun()
                                        else:
                                            st.error("❌ No se pudo encontrar el registro")
                                    except Exception as e:
                                        st.error(f"❌ Error al actualizar: {str(e)}")
            
                                if cancelar_juridico:
                                    # Resetear el estado del formulario
                                    st.session_state[f"show_form_juridico_{caso['ID']}"] = False
                                    st.rerun()

                # NUEVA FUNCIONALIDAD: Envío de correo
                with col_btn4:
                    # Verificar si tiene email antes de mostrar el botón
                    if 'Email' in caso and not pd.isna(caso['Email']) and caso['Email'].strip():
                        # Inicializar estado si no existe
                        if f"show_form_email_{caso['ID']}" not in st.session_state:
                            st.session_state[f"show_form_email_{caso['ID']}"] = False
        
                        if st.button(f"📧 Correo", key=f"email_{caso['ID']}"):
                            st.session_state[f"show_form_email_{caso['ID']}"] = True
        
                        # Mostrar formulario si está activado
                        if st.session_state[f"show_form_email_{caso['ID']}"]:
                            with st.form(f"form_email_{caso['ID']}"):
                                st.write("**Enviar Correo de Cobro**")
                                
                                # Tipo de mensaje predefinido para cobro
                                tipo_mensaje = st.selectbox(
                                    "Tipo de mensaje:",
                                    ["Recordatorio", "Aviso Importante", "Convocatoria"],
                                    key=f"tipo_email_{caso['ID']}"
                                )
                                
                                # Asunto predefinido pero editable
                                if caso['Dias_Mora'] <= 30:
                                    asunto_default = f"Recordatorio de Pago - {caso['Apartamento/Casa']}"
                                elif caso['Dias_Mora'] <= 90:
                                    asunto_default = f"Pago Pendiente - {caso['Apartamento/Casa']} - {caso['Dias_Mora']} días"
                                else:
                                    asunto_default = f"URGENTE: Deuda Vencida - {caso['Apartamento/Casa']} - {caso['Dias_Mora']} días"
                                
                                asunto = st.text_input(
                                    "Asunto:",
                                    value=asunto_default,
                                    key=f"asunto_email_{caso['ID']}"
                                )
                                
                                # Mensaje predefinido pero editable
                                if caso['Dias_Mora'] <= 30:
                                    mensaje_default = f"""Estimado(a) {caso['Propietario']},
                                    
Le recordamos que tiene un saldo pendiente de {format_currency(caso['Saldo_Pendiente'])} correspondiente a su unidad {caso['Apartamento/Casa']}.

Fecha de vencimiento: {caso['Fecha_Vencimiento']}
Días de mora: {caso['Dias_Mora']} días

Le agradecemos realizar el pago a la mayor brevedad posible para evitar inconvenientes.

Para cualquier consulta, no dude en contactarnos."""
                                
                                elif caso['Dias_Mora'] <= 90:
                                    mensaje_default = f"""Estimado(a) {caso['Propietario']},
                                    
Nos dirigimos a usted para informarle que presenta un saldo pendiente de {format_currency(caso['Saldo_Pendiente'])} por concepto de administración de su unidad {caso['Apartamento/Casa']}.

Fecha de vencimiento: {caso['Fecha_Vencimiento']}
Días de mora: {caso['Dias_Mora']} días

Es importante regularizar esta situación a la mayor brevedad posible para evitar que se generen mayores inconvenientes.

Quedamos atentos a su pronto pago."""
                                
                                else:
                                    mensaje_default = f"""Estimado(a) {caso['Propietario']},
                                    
Por medio de la presente le informamos que presenta una deuda vencida de {format_currency(caso['Saldo_Pendiente'])} correspondiente a su unidad {caso['Apartamento/Casa']}.

Fecha de vencimiento: {caso['Fecha_Vencimiento']}
Días de mora: {caso['Dias_Mora']} días

Debido al tiempo transcurrido, le solicitamos regularizar esta situación de manera INMEDIATA para evitar que se inicien acciones legales de cobro.

Si ya realizó el pago, favor hacer caso omiso a este mensaje y enviar el comprobante correspondiente."""
                                
                                mensaje = st.text_area(
                                    "Mensaje:",
                                    value=mensaje_default,
                                    height=200,
                                    key=f"mensaje_email_{caso['ID']}"
                                )
                                
                                # Botones
                                enviar_email = st.form_submit_button("📧 Enviar Correo", type="primary")
                                cancelar_email = st.form_submit_button("❌ Cancelar")
                
                                if enviar_email:
                                    try:
                                        # Enviar el correo usando la función existente
                                        exito, mensaje_resultado = send_email_to_resident(
                                            email_to=caso['Email'],
                                            nombre=caso['Propietario'],
                                            asunto=asunto,
                                            mensaje=mensaje,
                                            tipo_mensaje=tipo_mensaje
                                        )
                                        
                                        if exito:
                                            st.success(f"✅ Correo enviado exitosamente a {caso['Propietario']}")
                                            
                                            # Registrar el envío del correo en Google Sheets
                                            cell_list = worksheet.findall(str(caso['ID']))
                                            if cell_list:
                                                fila = cell_list[0].row
                                                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                                
                                                # Actualizar campos de gestión
                                                worksheet.update(f'M{fila}', [['Email']])  # Tipo_Gestion
                                                worksheet.update(f'N{fila}', [[fecha_actual]])  # Fecha_Ultimo_Contacto
                                                
                                                # Actualizar observaciones con el envío del correo
                                                obs_email = f"Email enviado: {asunto} - Fecha: {fecha_actual}"
                                                observacion_actual = caso['Observaciones'] if not pd.isna(caso['Observaciones']) else ""
                                                nueva_observacion = f"{observacion_actual}\n{obs_email}" if observacion_actual else obs_email
                                                worksheet.update(f'O{fila}', [[nueva_observacion]])
                                                
                                            # Resetear el estado del formulario
                                            st.session_state[f"show_form_email_{caso['ID']}"] = False
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Error al enviar correo: {mensaje_resultado}")
                                            
                                    except Exception as e:
                                        st.error(f"❌ Error al procesar envío de correo: {str(e)}")
                
                                if cancelar_email:
                                    # Resetear el estado del formulario
                                    st.session_state[f"show_form_email_{caso['ID']}"] = False
                                    st.rerun()
                    else:
                        # Si no tiene email, mostrar botón deshabilitado
                        st.button("📧 Sin Email", disabled=True, key=f"no_email_{caso['ID']}")
    
    with col2:
        st.subheader("📊 Resumen de Gestión")
        
        # Métricas de gestión
        total_casos = len(casos_pendientes)
        casos_criticos = len(casos_pendientes[casos_pendientes['Dias_Mora'] > 90])
        casos_juridicos = len(casos_pendientes[casos_pendientes['Accion_Juridica'] == 'Sí'])
        # Nueva métrica: casos con email
        casos_con_email = len(casos_pendientes[casos_pendientes['Email'].notna() & (casos_pendientes['Email'] != '')])
        
        st.metric("📋 Total Casos", total_casos)
        st.metric("🚨 Casos Críticos", casos_criticos)
        st.metric("⚖️ En Proceso Jurídico", casos_juridicos)
        st.metric("📧 Con Email", casos_con_email)
        
        # ============ SECCIÓN DE ENVÍO MASIVO CORREGIDA ============
        st.subheader("📧 Gestión Masiva de Correos")
        
        # Filtros para envío masivo
        dias_mora_minimo = st.number_input("Días mínimos de mora:", min_value=30, value=31, step=1)
        
        # Filtrar casos elegibles para envío masivo
        casos_para_email = casos_pendientes[
            (casos_pendientes['Dias_Mora'] >= dias_mora_minimo) & 
            (casos_pendientes['Email'].notna()) & 
            (casos_pendientes['Email'] != '') &
            (casos_pendientes['Email'].str.strip() != '')
        ]
        
        st.info(f"📊 Casos elegibles para envío: {len(casos_para_email)} de {len(casos_pendientes)}")
        
        if len(casos_para_email) > 0:
            # Mostrar vista previa de casos a enviar
            with st.expander(f"👀 Ver casos elegibles ({len(casos_para_email)})"):
                preview_df = casos_para_email[['Apartamento/Casa', 'Propietario', 'Email', 'Dias_Mora', 'Saldo_Pendiente']].head(10)
                st.dataframe(preview_df)
                if len(casos_para_email) > 10:
                    st.write(f"... y {len(casos_para_email) - 10} casos más")
            
            # Configuración del mensaje masivo
            st.subheader("⚙️ Configuración del Mensaje")
            
            # Tipo de mensaje
            tipo_mensaje_masivo = st.selectbox(
                "Tipo de mensaje:",
                ["Recordatorio", "Aviso Importante", "Convocatoria"],
                key="tipo_email_masivo"
            )
            
            # Asunto personalizable según días de mora
            asunto_masivo = st.text_input(
                "Asunto del correo:",
                value="Recordatorio de Pago - Administración",
                key="asunto_email_masivo"
            )
            
            # Mensaje personalizable
            mensaje_base = """Estimado(a) [NOMBRE],

Nos dirigimos a usted para informarle que presenta un saldo pendiente de [SALDO] correspondiente a su unidad [UNIDAD].

Días de mora: [DIAS_MORA] días
Fecha de vencimiento: [FECHA_VENCIMIENTO]

Le solicitamos regularizar esta situación a la mayor brevedad posible.

Para cualquier consulta, no dude en contactarnos.

Saludos cordiales,
Administración"""
            
            mensaje_masivo = st.text_area(
                "Mensaje (use [NOMBRE], [SALDO], [UNIDAD], [DIAS_MORA], [FECHA_VENCIMIENTO] como variables):",
                value=mensaje_base,
                height=150,
                key="mensaje_email_masivo"
            )
            
            # Botón de envío masivo
            col_envio1, col_envio2 = st.columns([1, 1])
            
            with col_envio1:
                if st.button(f"📧 Enviar a {len(casos_para_email)} casos", type="primary", key="envio_masivo"):
                    try:
                        st.info("📤 Iniciando envío masivo de correos...")
                        
                        # Preparar lista de emails con información personalizada
                        emails_info = []
                        for idx, caso in casos_para_email.iterrows():
                            # Personalizar mensaje para cada caso
                            mensaje_personalizado = mensaje_masivo.replace('[NOMBRE]', str(caso['Propietario']))
                            mensaje_personalizado = mensaje_personalizado.replace('[SALDO]', format_currency(caso['Saldo_Pendiente']))
                            mensaje_personalizado = mensaje_personalizado.replace('[UNIDAD]', str(caso['Apartamento/Casa']))
                            mensaje_personalizado = mensaje_personalizado.replace('[DIAS_MORA]', str(caso['Dias_Mora']))
                            mensaje_personalizado = mensaje_personalizado.replace('[FECHA_VENCIMIENTO]', str(caso['Fecha_Vencimiento']))
                            
                            # Personalizar asunto si es necesario
                            asunto_personalizado = asunto_masivo.replace('[UNIDAD]', str(caso['Apartamento/Casa']))
                            
                            emails_info.append({
                                'email': caso['Email'],
                                'nombre': caso['Propietario'],
                                'asunto': asunto_personalizado,
                                'mensaje': mensaje_personalizado,
                                'caso_id': caso['ID']
                            })
                        
                        # Enviar correos usando función de envío masivo
                        successful, failed, errors = send_bulk_collection_emails(emails_info, tipo_mensaje_masivo)
                        
                        # Actualizar registros en Google Sheets para casos exitosos
                        if successful > 0:
                            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            for email_info in emails_info:
                                if email_info['caso_id'] not in [error.get('caso_id') for error in errors]:
                                    try:
                                        # Buscar y actualizar registro en Google Sheets
                                        cell_list = worksheet.findall(str(email_info['caso_id']))
                                        if cell_list:
                                            fila = cell_list[0].row
                                            
                                            # Actualizar campos de gestión
                                            worksheet.update(f'M{fila}', [['Email']])  # Tipo_Gestion
                                            worksheet.update(f'N{fila}', [[fecha_actual]])  # Fecha_Ultimo_Contacto
                                            
                                            # Actualizar observaciones
                                            obs_email = f"Email masivo enviado: {asunto_personalizado} - {fecha_actual}"
                                            worksheet.update(f'O{fila}', [[obs_email]])
                                    except Exception as e:
                                        st.warning(f"Error actualizando registro {email_info['caso_id']}: {str(e)}")
                        
                        # Mostrar resultados
                        if successful > 0:
                            st.success(f"✅ {successful} correo(s) enviado(s) exitosamente")
                            if failed > 0:
                                st.warning(f"⚠️ {failed} correo(s) fallaron")
                                with st.expander("Ver errores"):
                                    for error in errors:
                                        st.write(f"• {error}")
                        else:
                            st.error("❌ No se pudo enviar ningún correo")
                            with st.expander("Ver errores"):
                                for error in errors:
                                    st.write(f"• {error}")
                                    
                    except Exception as e:
                        st.error(f"❌ Error en el envío masivo: {str(e)}")
        
        else:
            st.info("ℹ️ No hay casos elegibles para envío masivo con los filtros actuales")
            if len(casos_pendientes) > 0:
                casos_sin_email = len(casos_pendientes[casos_pendientes['Email'].isna() | (casos_pendientes['Email'] == '')])
                if casos_sin_email > 0:
                    st.warning(f"⚠️ {casos_sin_email} casos no tienen correo electrónico registrado")
        
        # Gráfico de distribución
        distribucion = casos_pendientes.copy()
        distribucion['Rango_Mora'] = distribucion['Dias_Mora'].apply(
            lambda x: '0-30 días' if x <= 30 else
                     '31-60 días' if x <= 60 else
                     '61-90 días' if x <= 90 else
                     '91-180 días' if x <= 180 else
                     '+180 días'
        )
        
        fig_dist = px.pie(
            distribucion['Rango_Mora'].value_counts().reset_index(),
            values='count',
            names='Rango_Mora',
            title="Distribución por Días de Mora"
        )
        st.plotly_chart(fig_dist, use_container_width=True)

def show_reports(df):
    """Mostrar reportes y análisis"""
    st.header("📈 Reportes y Análisis")
    
    if df.empty:
        st.warning("📋 No hay datos para generar reportes")
        return
    
    # Actualizar cálculos
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    df['Estado_Calculado'] = df['Dias_Mora'].apply(get_estado_by_dias_mora)
    
    # Tabs para diferentes reportes
    tab1, tab2, tab3, tab4 = st.tabs(["📊 General", "💰 Financiero", "📅 Temporal", "📋 Detallado"])
    
    with tab1:
        st.subheader("📊 Reporte General")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribución por estado
            estado_dist = df['Estado_Calculado'].value_counts()
            fig_estado = px.bar(
                x=estado_dist.index,
                y=estado_dist.values,
                title="Distribución por Estado de Mora",
                labels={'x': 'Estado', 'y': 'Cantidad'}
            )
            st.plotly_chart(fig_estado, use_container_width=True)
        
        with col2:
            # Top deudores con formato de moneda
            top_deudores = df.nlargest(10, 'Saldo_Pendiente')[['Propietario', 'Apartamento/Casa', 'Saldo_Pendiente']].copy()
            top_deudores['Saldo_Pendiente'] = top_deudores['Saldo_Pendiente'].apply(format_currency)
            st.subheader("🔝 Top 10 Deudores")
            st.dataframe(top_deudores, use_container_width=True)
    
    with tab2:
        st.subheader("💰 Reporte Financiero")
        
        # Métricas financieras con formato
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Deuda Total", format_currency(df['Valor_Deuda'].sum()))
        with col2:
            st.metric("💚 Total Recaudado", format_currency(df['Valor_Pagado'].sum()))
        with col3:
            st.metric("⚠️ Saldo Pendiente", format_currency(df['Saldo_Pendiente'].sum()))
        with col4:
            efectividad = (df['Valor_Pagado'].sum() / df['Valor_Deuda'].sum() * 100) if df['Valor_Deuda'].sum() > 0 else 0
            st.metric("📈 Efectividad Cobro", f"{efectividad:.1f}%")
        
        # Análisis por concepto de deuda
        col1, col2 = st.columns(2)
        
        with col1:
            concepto_analysis = df.groupby('Concepto_Deuda').agg({
                'Valor_Deuda': 'sum',
                'Saldo_Pendiente': 'sum'
            }).reset_index()
            
            fig_concepto = px.bar(
                concepto_analysis,
                x='Concepto_Deuda',
                y=['Valor_Deuda', 'Saldo_Pendiente'],
                title="Análisis por Concepto de Deuda",
                barmode='group'
            )
            st.plotly_chart(fig_concepto, use_container_width=True)
        
        with col2:
            # Tabla resumen financiero con formato
            st.subheader("📋 Resumen Financiero por Estado")
            resumen_financiero = df.groupby('Estado_Calculado').agg({
                'Valor_Deuda': 'sum',
                'Valor_Pagado': 'sum',
                'Saldo_Pendiente': 'sum',
                'ID': 'count'
            }).round(0)
            
            # Aplicar formato de moneda a las columnas monetarias
            resumen_financiero_formatted = resumen_financiero.copy()
            resumen_financiero_formatted['Valor_Deuda'] = resumen_financiero_formatted['Valor_Deuda'].apply(format_currency)
            resumen_financiero_formatted['Valor_Pagado'] = resumen_financiero_formatted['Valor_Pagado'].apply(format_currency)
            resumen_financiero_formatted['Saldo_Pendiente'] = resumen_financiero_formatted['Saldo_Pendiente'].apply(format_currency)
            
            resumen_financiero_formatted.columns = ['Deuda Total', 'Pagado', 'Saldo Pendiente', 'Casos']
            st.dataframe(resumen_financiero_formatted, use_container_width=True)
    
    with tab3:
        st.subheader("📅 Análisis Temporal")
        
        # Convertir fechas para análisis temporal
        df_temp = df.copy()
        df_temp['Fecha_Registro'] = pd.to_datetime(df_temp['Fecha_Registro'], errors='coerce')
        df_temp['Mes_Registro'] = df_temp['Fecha_Registro'].dt.to_period('M')
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Evolución mensual de registros
            if not df_temp['Mes_Registro'].isna().all():
                registros_mensuales = df_temp.groupby('Mes_Registro').size().reset_index()
                registros_mensuales['Mes_Registro'] = registros_mensuales['Mes_Registro'].astype(str)
                
                fig_temporal = px.line(
                    registros_mensuales,
                    x='Mes_Registro',
                    y=0,
                    title="Evolución Mensual de Nuevos Casos",
                    labels={'0': 'Nuevos Casos', 'Mes_Registro': 'Mes'}
                )
                st.plotly_chart(fig_temporal, use_container_width=True)
        
        with col2:
            # Distribución por días de mora
            bins = [0, 30, 60, 90, 180, float('inf')]
            labels = ['0-30', '31-60', '61-90', '91-180', '+180']
            df_temp['Rango_Mora'] = pd.cut(df_temp['Dias_Mora'], bins=bins, labels=labels, right=False)
            
            mora_dist = df_temp['Rango_Mora'].value_counts().sort_index()
            
            fig_mora = px.bar(
                x=mora_dist.index.astype(str),
                y=mora_dist.values,
                title="Distribución por Rangos de Días de Mora",
                labels={'x': 'Días de Mora', 'y': 'Cantidad'}
            )
            st.plotly_chart(fig_mora, use_container_width=True)
        
        # Timeline de acciones jurídicas con formato
        if not df[df['Accion_Juridica'] == 'Sí'].empty:
            st.subheader("⚖️ Timeline de Acciones Jurídicas")
            juridicos = df[df['Accion_Juridica'] == 'Sí'].copy()
            juridicos['Fecha_Accion_Juridica'] = pd.to_datetime(juridicos['Fecha_Accion_Juridica'], errors='coerce')
            juridicos_clean = juridicos.dropna(subset=['Fecha_Accion_Juridica'])
            
            if not juridicos_clean.empty:
                # Aplicar formato a la columna de saldo
                juridicos_display = juridicos_clean[['Fecha_Accion_Juridica', 'Propietario', 'Apartamento/Casa', 'Saldo_Pendiente']].copy()
                juridicos_display['Saldo_Pendiente'] = juridicos_display['Saldo_Pendiente'].apply(format_currency)
                
                st.dataframe(
                    juridicos_display.sort_values('Fecha_Accion_Juridica'),
                    use_container_width=True
                )
    
    with tab4:
        st.subheader("📋 Reporte Detallado")
        
        # Filtros para el reporte detallado
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtro_estado_rep = st.selectbox("Estado:", ["Todos"] + df['Estado_Calculado'].unique().tolist(), key="rep_estado")
        with col2:
            filtro_concepto_rep = st.selectbox("Concepto:", ["Todos"] + df['Concepto_Deuda'].unique().tolist(), key="rep_concepto")
        with col3:
            min_saldo = st.number_input("Saldo mínimo:", min_value=0, value=0, key="rep_saldo")
        
        # Aplicar filtros
        df_reporte = df.copy()
        if filtro_estado_rep != "Todos":
            df_reporte = df_reporte[df_reporte['Estado_Calculado'] == filtro_estado_rep]
        if filtro_concepto_rep != "Todos":
            df_reporte = df_reporte[df_reporte['Concepto_Deuda'] == filtro_concepto_rep]
        df_reporte = df_reporte[df_reporte['Saldo_Pendiente'] >= min_saldo]
        
        # Mostrar tabla detallada
        st.subheader(f"📊 Registros Filtrados: {len(df_reporte)}")
        
        if not df_reporte.empty:
            # Seleccionar columnas para mostrar
            columnas_mostrar = st.multiselect(
                "Seleccionar columnas a mostrar:",
                options=df_reporte.columns.tolist(),
                default=['Apartamento/Casa', 'Propietario', 'Valor_Deuda', 'Saldo_Pendiente', 'Dias_Mora', 'Estado_Calculado']
            )
            
            if columnas_mostrar:
                # Crear copia para mostrar con formato
                df_display = df_reporte[columnas_mostrar].copy()
                
                # Aplicar formato a columnas monetarias si están seleccionadas
                columnas_monetarias = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente']
                for col in columnas_monetarias:
                    if col in df_display.columns:
                        df_display[col] = df_display[col].apply(format_currency)
                
                st.dataframe(df_display, use_container_width=True)
                
                # Opción para descargar (con valores originales sin formato)
                csv = df_reporte[columnas_mostrar].to_csv(index=False)
                st.download_button(
                    label="📥 Descargar CSV",
                    data=csv,
                    file_name=f"reporte_cartera_morosa_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

def get_or_create_config_sheet(client, sheet_name="gestion-conjuntos", config_worksheet_name="configuracion_sistema"):
    """Obtener o crear la hoja de configuración"""
    try:
        # Intentar abrir la hoja existente
        sheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        # Crear nueva hoja si no existe
        sheet = client.create(sheet_name)
    
    try:
        # Intentar abrir el worksheet de configuración
        config_worksheet = sheet.worksheet(config_worksheet_name)
    except gspread.WorksheetNotFound:
        # Crear nuevo worksheet de configuración si no existe
        config_worksheet = sheet.add_worksheet(title=config_worksheet_name, rows=100, cols=10)
        # Crear encabezados para configuración
        headers = ["Parametro", "Valor", "Tipo", "Descripcion", "Fecha_Actualizacion"]
        config_worksheet.append_row(headers)
        st.success(f"📋 Nuevo worksheet de configuración '{config_worksheet_name}' creado")
    
    return sheet, config_worksheet

def load_system_config(config_worksheet):
    """Cargar configuración del sistema desde Google Sheets"""
    try:
        config_data = config_worksheet.get_all_records()
        config_dict = {}
        
        if config_data:
            for row in config_data:
                parametro = row.get('Parametro', '')
                valor = row.get('Valor', '')
                tipo = row.get('Tipo', 'str')
                
                # Convertir el valor según su tipo
                if tipo == 'int':
                    config_dict[parametro] = int(valor) if valor else 0
                elif tipo == 'float':
                    config_dict[parametro] = float(valor) if valor else 0.0
                elif tipo == 'bool':
                    config_dict[parametro] = valor.lower() in ['true', '1', 'yes', 'on'] if valor else False
                else:
                    config_dict[parametro] = str(valor) if valor else ""
        
        return config_dict
    except Exception as e:
        st.error(f"Error cargando configuración: {str(e)}")
        return {}

def save_system_config(config_worksheet, config_dict):
    """Guardar configuración del sistema en Google Sheets"""
    try:
        # Limpiar la hoja excepto los encabezados
        config_worksheet.clear()
        
        # Escribir encabezados
        headers = ["Parametro", "Valor", "Tipo", "Descripcion", "Fecha_Actualizacion"]
        config_worksheet.append_row(headers)
        
        # Preparar datos de configuración
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        config_rows = []
        
        # Definir descripciones para cada parámetro
        descripciones = {
            'email_notificaciones': 'Email para recibir notificaciones del sistema',
            'whatsapp_notificaciones': 'WhatsApp para recibir alertas',
            'dias_alerta_temprana': 'Días para generar alerta temprana de mora',
            'dias_alerta_critica': 'Días para generar alerta crítica de mora',
            'enviar_recordatorios': 'Activar envío automático de recordatorios',
            'frecuencia_recordatorios': 'Frecuencia de envío de recordatorios',
            'interes_mora': 'Tasa de interés mensual por mora (%)',
            'valor_minimo_juridico': 'Valor mínimo para iniciar cobro jurídico',
            'dias_gracia': 'Días de gracia antes de cobrar mora',
            'descuento_pronto_pago': 'Descuento por pronto pago (%)',
            'backup_automatico': 'Activar backup automático diario',
            'sincronizacion_tiempo_real': 'Activar sincronización en tiempo real'
        }
        
        # Crear filas de configuración
        for param, valor in config_dict.items():
            # Determinar el tipo de dato
            if isinstance(valor, bool):
                tipo = 'bool'
                valor_str = 'true' if valor else 'false'
            elif isinstance(valor, int):
                tipo = 'int'
                valor_str = str(valor)
            elif isinstance(valor, float):
                tipo = 'float'
                valor_str = str(valor)
            else:
                tipo = 'str'
                valor_str = str(valor)
            
            descripcion = descripciones.get(param, f'Configuración de {param}')
            
            config_rows.append([param, valor_str, tipo, descripcion, fecha_actual])
        
        # Escribir las filas de configuración
        if config_rows:
            config_worksheet.append_rows(config_rows)
        
        return True
    except Exception as e:
        st.error(f"❌ Error guardando configuración: {str(e)}")
        return False

def get_default_config():
    """Obtener configuración por defecto"""
    return {
        'email_notificaciones': 'admin@condominio.com',
        'whatsapp_notificaciones': '+57 300 123 4567',
        'dias_alerta_temprana': 30,
        'dias_alerta_critica': 90,
        'enviar_recordatorios': True,
        'frecuencia_recordatorios': 'Semanal',
        'interes_mora': 2.0,
        'valor_minimo_juridico': 500000,
        'dias_gracia': 5,
        'descuento_pronto_pago': 5.0,
        'backup_automatico': True,
        'sincronizacion_tiempo_real': True
    }

def show_configuration():
    """Mostrar configuración del sistema"""
    st.header("⚙️ Configuración del Sistema")
    
    # Cargar credenciales y establecer conexión
    creds, config = load_credentials_from_toml()
    if not creds:
        st.error("❌ No se pudieron cargar las credenciales")
        return
    
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("❌ No se pudo conectar a Google Sheets")
        return
    
    # Obtener o crear hoja de configuración
    sheet, config_worksheet = get_or_create_config_sheet(client)
    
    # Cargar configuración existente o usar valores por defecto
    config_actual = load_system_config(config_worksheet)
    config_default = get_default_config()
    
    # Combinar configuración actual con valores por defecto
    for key, default_value in config_default.items():
        if key not in config_actual:
            config_actual[key] = default_value
    
    # Configuración de notificaciones
    st.subheader("🔔 Configuración de Alertas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        email_notif = st.text_input("📧 Email para notificaciones", 
                                   value=config_actual.get('email_notificaciones', ''),
                                   placeholder="admin@condominio.com",
                                   key="email_config")
        dias_alerta_temprana = st.number_input("Días para alerta temprana", 
                                             min_value=1, max_value=90, 
                                             value=config_actual.get('dias_alerta_temprana', 30),
                                             key="dias_temprana_config")
        dias_alerta_critica = st.number_input("Días para alerta crítica", 
                                            min_value=1, max_value=180, 
                                            value=config_actual.get('dias_alerta_critica', 90),
                                            key="dias_critica_config")
    
    with col2:
        whatsapp_notif = st.text_input("📱 WhatsApp para notificaciones", 
                                      value=config_actual.get('whatsapp_notificaciones', ''),
                                      placeholder="+57 300 123 4567",
                                      key="whatsapp_config")
        enviar_recordatorios = st.checkbox("Enviar recordatorios automáticos", 
                                         value=config_actual.get('enviar_recordatorios', True),
                                         key="recordatorios_config")
        frecuencia_recordatorios = st.selectbox("Frecuencia de recordatorios", 
                                               ["Semanal", "Quincenal", "Mensual"],
                                               index=["Semanal", "Quincenal", "Mensual"].index(
                                                   config_actual.get('frecuencia_recordatorios', 'Semanal')),
                                               key="frecuencia_config")
    
    # Configuración de cobro
    st.subheader("💰 Configuración de Cobro")
    
    col1, col2 = st.columns(2)
    
    with col1:
        interes_mora = st.number_input("Interés de mora mensual (%)", 
                                     min_value=0.0, max_value=5.0, 
                                     value=config_actual.get('interes_mora', 2.0), 
                                     step=0.1,
                                     key="interes_config")
        valor_minimo_juridico = st.number_input("Valor mínimo para cobro jurídico", 
                                              min_value=0, 
                                              value=config_actual.get('valor_minimo_juridico', 500000), 
                                              step=50000,
                                              key="minimo_juridico_config")
    
    with col2:
        dias_gracia = st.number_input("Días de gracia", 
                                    min_value=0, max_value=15, 
                                    value=config_actual.get('dias_gracia', 5),
                                    key="gracia_config")
        descuento_pronto_pago = st.number_input("Descuento pronto pago (%)", 
                                               min_value=0.0, max_value=20.0, 
                                               value=config_actual.get('descuento_pronto_pago', 5.0), 
                                               step=0.5,
                                               key="descuento_config")
    
    # Configuración de Google Sheets
    st.subheader("📊 Configuración de Google Sheets")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.text_input("📋 Nombre de la hoja", value="gestion-conjuntos", disabled=True)
        st.text_input("📄 Nombre del worksheet", value="gestion_morosos", disabled=True)
    
    with col2:
        backup_automatico = st.checkbox("Backup automático diario", 
                                      value=config_actual.get('backup_automatico', True),
                                      key="backup_config")
        sincronizacion_tiempo_real = st.checkbox("Sincronización en tiempo real", 
                                                value=config_actual.get('sincronizacion_tiempo_real', True),
                                                key="sync_config")
    
    # Botones de acción
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Guardar Configuración", type="primary"):
            # Recopilar todos los valores de configuración
            nueva_config = {
                'email_notificaciones': email_notif,
                'whatsapp_notificaciones': whatsapp_notif,
                'dias_alerta_temprana': dias_alerta_temprana,
                'dias_alerta_critica': dias_alerta_critica,
                'enviar_recordatorios': enviar_recordatorios,
                'frecuencia_recordatorios': frecuencia_recordatorios,
                'interes_mora': interes_mora,
                'valor_minimo_juridico': valor_minimo_juridico,
                'dias_gracia': dias_gracia,
                'descuento_pronto_pago': descuento_pronto_pago,
                'backup_automatico': backup_automatico,
                'sincronizacion_tiempo_real': sincronizacion_tiempo_real
            }
            
            # Guardar en Google Sheets
            if save_system_config(config_worksheet, nueva_config):
                st.success("✅ Configuración guardada exitosamente en Google Sheets")
                st.balloons()
            else:
                st.error("❌ Error al guardar la configuración")
    
    with col2:
        if st.button("🔄 Restaurar Valores"):
            # Restaurar valores por defecto
            config_default_restore = get_default_config()
            if save_system_config(config_worksheet, config_default_restore):
                st.success("🔄 Valores restaurados a configuración por defecto")
                st.rerun()
            else:
                st.error("❌ Error al restaurar valores por defecto")
    
    with col3:
        if st.button("🧪 Probar Conexión"):
            st.info("🔗 Probando conexión con Google Sheets...")
            try:
                # Probar lectura de la hoja de configuración
                test_data = config_worksheet.get_all_records()
                st.success(f"✅ Conexión exitosa - {len(test_data)} registros de configuración encontrados")
            except Exception as e:
                st.error(f"❌ Error en la conexión: {str(e)}")
    
    # Información del sistema
    st.subheader("ℹ️ Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**📊 Versión:** 1.0.0")
        st.info("**📅 Última actualización:** 30/05/2025")
        st.info("**👨‍💻 Desarrollado por:** Sistema de Gestión")
    
    with col2:
        st.info("**🔒 Estado de seguridad:** Activo")
        st.info("**☁️ Backup en la nube:** Activo")
        st.info("**📱 Soporte móvil:** Disponible")
    
    # Manual de usuario
    with st.expander("📖 Manual de Usuario"):
        st.markdown("""
        ### 🚀 Guía de Uso del Sistema
        
        #### 1. **Dashboard (📊)**
        - Visualiza métricas generales de la cartera morosa
        - Revisa gráficos de distribución por estado
        - Identifica casos críticos que requieren atención inmediata
        
        #### 2. **Nuevo Registro (➕)**
        - Completa todos los campos obligatorios marcados con *
        - El sistema calcula automáticamente los días de mora
        - Los datos se guardan inmediatamente en Google Sheets
        
        #### 3. **Gestionar Registros (📝)**
        - Filtra registros por estado, apartamento o días de mora
        - Selecciona un registro para editar sus datos
        - Actualiza estados de gestión y pagos realizados
        
        #### 4. **Gestión de Cobro (📞)**
        - Visualiza casos priorizados por días de mora
        - Registra contactos y gestiones realizadas
        - Inicia procesos jurídicos cuando sea necesario
        
        #### 5. **Reportes (📈)**
        - Genera reportes generales, financieros y temporales
        - Exporta datos filtrados en formato CSV
        - Analiza la efectividad del proceso de cobro
        
        #### 6. **Configuración (⚙️)**
        - Ajusta parámetros de alertas y notificaciones
        - Configura tasas de interés y valores mínimos
        - Prueba la conexión con Google Sheets
        
        ### 📞 Soporte Técnico
        Para soporte técnico o sugerencias, contacta al administrador del sistema.
        """)

# Función principal para ejecutar la aplicación
if __name__ == "__main__":
    cartera_morosa_main()

# CSS personalizado para mejorar la apariencia
#st.markdown("""
#<style>
#    .main > div {
#        padding-top: 2rem;
#    }
    
#    .stMetric {
#        background-color: #f0f2f6;
#        padding: 1rem;
#        border-radius: 0.5rem;
#        border-left: 4px solid #1f77b4;
#    }
    
#    .stAlert {
#        margin-top: 1rem;
#    }
    
#    .stExpander {
#        margin-bottom: 1rem;
#    }
    
#    .stTabs [data-baseweb="tab-list"] {
#        gap: 24px;
#    }
    
#    .stTabs [data-baseweb="tab"] {
#        height: 50px;
#        white-space: pre-wrap;
#        background-color: #f0f2f6;
#        border-radius: 4px 4px 0px 0px;
#        gap: 8px;
#        padding-left: 12px;
#        padding-right: 12px;
#    }
    
#    .stSelectbox > div > div {
#        background-color: white;
#    }
    
#    .reportview-container .main .block-container {
#        max-width: 1200px;
#   }
#</style>
#""", unsafe_allow_html=True)