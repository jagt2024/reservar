import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
import uuid
import base64
from io import BytesIO
import time
import os

# Configuración de la página
#st.set_page_config(
#    page_title="Registro de Pagos - Administración",
#    page_icon="💳",
#    layout="wide"
#)

def create_upload_directory():
    """Crear directorio para archivos subidos si no existe"""
    upload_dir = "archivos_subidos"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        st.info(f"📁 Directorio '{upload_dir}' creado exitosamente")
    return upload_dir

def save_uploaded_file(uploaded_file, unique_id):
    """Guardar archivo subido en el directorio local"""
    if uploaded_file is not None:
        try:
            # Crear directorio si no existe
            upload_dir = create_upload_directory()
            
            # Obtener extensión del archivo
            file_extension = uploaded_file.name.split('.')[-1]
            
            # Crear nombre único para el archivo
            filename = f"{unique_id}_{uploaded_file.name}"
            filepath = os.path.join(upload_dir, filename)
            
            # Guardar archivo
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            return filepath, filename
            
        except Exception as e:
            st.error(f"❌ Error guardando archivo: {str(e)}")
            return None, None
    
    return None, None

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
            st.success(f"✅ Conexión exitosa! y disponible")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=300)
def load_existing_data(_client):
    """Cargar datos existentes para obtener información de referencia"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Administracion_Financiera")
        data = worksheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            return df
        else:
            return pd.DataFrame()
            
    except gspread.WorksheetNotFound:
        st.warning("⚠️ La hoja 'Administracion_Financiera' no existe, se creará automáticamente")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando datos existentes: {str(e)}")
        return pd.DataFrame()

def get_unique_values(df, column):
    """Obtener valores únicos de una columna para los selectbox"""
    if column in df.columns and not df.empty:
        return sorted(df[column].dropna().unique().tolist())
    return []

def generate_unique_id(unidad):
    """Generar ID único para el registro"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    #random_suffix = str(uuid.uuid4())[:8].upper()
    return f"PAG_{unidad}_{timestamp}"

def create_or_update_worksheet(_client):
    """Crear o verificar la estructura de la hoja de trabajo"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        
        # Columnas requeridas
        required_columns = [
            'ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 
            'Fecha', 'Banco', 'Estado', 'Metodo_Pago', 'Soporte_Pago', 'Ruta_Archivo', 'Observaciones'
        ]
        
        try:
            worksheet = spreadsheet.worksheet("Administracion_Financiera")
            # Verificar si tiene encabezados
            headers = worksheet.row_values(1)
            if not headers or headers != required_columns:
                worksheet.clear()
                worksheet.append_row(required_columns)
                st.info("✅ Encabezados actualizados en la hoja existente")
        except gspread.WorksheetNotFound:
            # Crear nueva hoja
            worksheet = spreadsheet.add_worksheet(
                title="Administracion_Financiera", 
                rows=1000, 
                cols=len(required_columns)
            )
            worksheet.append_row(required_columns)
            st.success("✅ Hoja 'Administracion_Financiera' creada exitosamente")
        
        return worksheet
        
    except Exception as e:
        st.error(f"❌ Error creando/verificando hoja: {str(e)}")
        return None

def save_payment_record(_client, payment_data):
    """Guardar registro de pago en Google Sheets"""
    try:
        worksheet = create_or_update_worksheet(_client)
        if worksheet is None:
            return False
        
        # Preparar fila de datos
        row_data = [
            payment_data['ID'],
            payment_data['Tipo_Operacion'],
            payment_data['Unidad'],
            payment_data['Concepto'],
            payment_data['Monto'],
            payment_data['Fecha'],
            payment_data['Banco'],
            payment_data['Estado'],
            payment_data['Metodo_Pago'],
            payment_data['Soporte_Pago'],
            payment_data['Ruta_Archivo'],
            payment_data['Observaciones']
        ]
        
        # Agregar fila
        worksheet.append_row(row_data)
        return True
        
    except Exception as e:
        st.error(f"❌ Error guardando registro: {str(e)}")
        return False

def encode_file_to_base64(uploaded_file):
    """Codificar archivo subido a base64"""
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        return base64.b64encode(bytes_data).decode()
    return ""

def pago_main():
    st.title("💳 Sistema de Registro de Pagos")
    st.subheader("Cuotas de Administración y Extraordinarias")
    st.markdown("---")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    
    if creds is None:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    
    if client is None:
        st.stop()
    
    # Cargar datos existentes para referencia
    with st.spinner("Cargando información de referencia..."):
        df_existing = load_existing_data(client)
    
    # Información del sistema
    if not df_existing.empty:
        st.info(f"📊 Registros existentes en el sistema: {len(df_existing)}")
    
    # Crear formulario de captura
    st.header("📝 Registro de Nuevo Pago")
    
    with st.form("payment_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Tipo de Operación
            tipo_operacion = st.selectbox(
                "💰 Tipo de Operación *",
                options=["Cuota de Administración", "Cuota Extraordinaria", "Multa", "Otro"],
                help="Seleccione el tipo de pago que está registrando"
            )
            
            # Unidad
            unidades_existentes = get_unique_values(df_existing, 'Unidad')
            if unidades_existentes:
                unidad_option = st.radio(
                    "🏠 Seleccionar Unidad *",
                    options=["Seleccionar existente", "Escribir nueva"]
                )
                
                if unidad_option == "Seleccionar existente":
                    unidad = st.selectbox("Unidad/Casa/Lote", unidades_existentes)
                else:
                    unidad = st.text_input("Nueva Unidad", placeholder="Ej: Apto 101, Casa 5, etc.")
            else:
                unidad = st.text_input(
                    "🏠 Unidad *", 
                    placeholder="Ej: Apto 101, Casa 5, Local 3, etc.",
                    help="Ingrese la unidad que realiza el pago"
                )
            
            # Concepto
            conceptos_default = [
                "Cuota de Administración - Enero",
                "Cuota de Administración - Febrero", 
                "Cuota de Administración - Marzo",
                "Cuota de Administración - Abril",
                "Cuota de Administración - Mayo",
                "Cuota de Administración - Junio",
                "Cuota de Administración - Julio",
                "Cuota de Administración - Agosto",
                "Cuota de Administración - Septiembre",
                "Cuota de Administración - Octubre",
                "Cuota de Administración - Noviembre",
                "Cuota de Administración - Diciembre",
                "Cuota Extraordinaria - Reparaciones",
                "Cuota Extraordinaria - Mejoras",
                "Multa por ruido",
                "Multa por mascotas",
                "Otro"
            ]
            
            concepto_option = st.radio(
                "📋 Concepto del Pago *",
                options=["Seleccionar predefinido", "Escribir personalizado"]
            )
            
            if concepto_option == "Seleccionar predefinido":
                concepto = st.selectbox("Concepto", conceptos_default)
            else:
                concepto = st.text_input("Concepto Personalizado", placeholder="Describa el concepto del pago")
            
            # Monto
            monto = st.number_input(
                "💵 Monto *",
                min_value=0.0,
                step=1000.0,
                format="%.2f",
                help="Ingrese el monto del pago"
            )
            
            # Fecha
            fecha = st.date_input(
                "📅 Fecha del Pago *",
                value=date.today(),
                help="Seleccione la fecha en que se realizó el pago"
            )
        
        with col2:
            # Banco
            bancos_colombia = [
                "Bancolombia",
                "Banco de Bogotá",
                "Davivienda", 
                "BBVA Colombia",
                "Banco Popular",
                "Banco Caja Social",
                "Banco AV Villas",
                "Banco Agrario",
                "Banco Santander",
                "Citibank",
                "Banco GNB Sudameris",
                "Banco Falabella",
                "Banco Pichincha",
                "Nequi",
                "Daviplata",
                "Efectivo",
                "Otro"
            ]
            
            banco = st.selectbox(
                "🏦 Banco/Entidad *",
                options=bancos_colombia,
                help="Seleccione el banco o entidad de pago"
            )
            
            if banco == "Otro":
                banco = st.text_input("Especificar Banco/Entidad")
            
            # Estado
            estado = st.selectbox(
                "📊 Estado del Pago *",
                options=["Pagado", "Pendiente", "En Verificación", "Rechazado"],
                index=0,
                help="Estado actual del pago"
            )
            
            # Método de Pago
            metodo_pago = st.selectbox(
                "💳 Método de Pago *",
                options=[
                    "Transferencia Bancaria",
                    "PSE",
                    "Tarjeta de Crédito", 
                    "Tarjeta de Débito",
                    "Efectivo",
                    "Cheque",
                    "Consignación",
                    "Otro"
                ],
                help="Método utilizado para realizar el pago"
            )
            
            # Soporte de Pago (archivo)
            soporte_pago = st.file_uploader(
                "📎 Soporte de Pago",
                type=['pdf', 'jpg', 'jpeg', 'png'],
                help="Suba el comprobante o soporte del pago (se guardará en la carpeta 'archivos_subidos')"
            )
            
            # Mostrar información del archivo subido
            if soporte_pago is not None:
                st.info(f"📄 Archivo seleccionado: {soporte_pago.name}")
                st.info(f"📦 Tamaño: {soporte_pago.size / 1024:.2f} KB")
            
            # Observaciones
            observaciones = st.text_area(
                "📝 Observaciones",
                placeholder="Ingrese observaciones adicionales (opcional)",
                height=100
            )
        
        st.markdown("---")
        
        # Botones de acción
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            submitted = st.form_submit_button(
                "💾 Registrar Pago",
                type="primary",
                use_container_width=True
            )
    
    # Procesar formulario
    if submitted:
        # Validaciones
        errors = []
        
        if not unidad.strip():
            errors.append("La unidad es obligatoria")
        
        if not concepto.strip():
            errors.append("El concepto es obligatorio")
        
        if monto <= 0:
            errors.append("El monto debe ser mayor a 0")
        
        if errors:
            st.error("❌ **Errores en el formulario:**")
            for error in errors:
                st.error(f"• {error}")
        else:
            # Generar ID único
            unique_id = generate_unique_id(unidad)
            
            # Guardar archivo subido si existe
            filepath = None
            filename = None
            if soporte_pago is not None:
                with st.spinner("Guardando archivo..."):
                    filepath, filename = save_uploaded_file(soporte_pago, unique_id)
                
                if filepath:
                    st.success(f"✅ Archivo guardado: {filename}")
                else:
                    st.warning("⚠️ No se pudo guardar el archivo, pero el registro continuará")
            
            # Preparar datos del pago
            payment_data = {
                'ID': unique_id,
                'Tipo_Operacion': tipo_operacion,
                'Unidad': unidad.strip(),
                'Concepto': concepto.strip(),
                'Monto': monto,
                'Fecha': fecha.strftime('%Y-%m-%d'),
                'Banco': banco,
                'Estado': estado,
                'Metodo_Pago': metodo_pago,
                'Soporte_Pago': filename if filename else "Sin soporte",
                'Ruta_Archivo': filepath if filepath else "Sin archivo",
                'Observaciones': observaciones.strip() if observaciones else "Sin observaciones"
            }
            
            # Guardar en Google Sheets
            with st.spinner("Guardando registro de pago..."):
                success = save_payment_record(client, payment_data)
            
            if success:
                st.success("✅ **¡Pago registrado exitosamente!**")
                
                # Mostrar resumen del registro
                st.info("📋 **Resumen del registro:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**ID:** {payment_data['ID']}")
                    st.write(f"**Tipo:** {payment_data['Tipo_Operacion']}")
                    st.write(f"**Unidad:** {payment_data['Unidad']}")
                    st.write(f"**Concepto:** {payment_data['Concepto']}")
                    st.write(f"**Monto:** ${payment_data['Monto']:,.2f}")
                
                with col2:
                    st.write(f"**Fecha:** {payment_data['Fecha']}")
                    st.write(f"**Banco:** {payment_data['Banco']}")
                    st.write(f"**Estado:** {payment_data['Estado']}")
                    st.write(f"**Método:** {payment_data['Metodo_Pago']}")
                    st.write(f"**Soporte:** {payment_data['Soporte_Pago']}")
                    if filepath:
                        st.write(f"**Archivo guardado en:** {filepath}")
                
                # Limpiar cache para refrescar datos
                st.cache_data.clear()
                
                # Opción para registrar otro pago
                if st.button("➕ Registrar Otro Pago"):
                    st.experimental_rerun()
            
            else:
                st.error("❌ **Error al registrar el pago**")
                st.error("Por favor, verifique la conexión e intente nuevamente")
    
    # Información adicional
    st.markdown("---")
    
    # Mostrar últimos pagos registrados
    if not df_existing.empty:
        st.header("📊 Últimos Pagos Registrados")
        
        # Mostrar últimos 5 registros
        df_recent = df_existing.tail(5).sort_values('Fecha', ascending=False) if 'Fecha' in df_existing.columns else df_existing.tail(5)
        
        # Seleccionar columnas para mostrar
        columns_to_show = ['ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha', 'Estado']
        available_columns = [col for col in columns_to_show if col in df_recent.columns]
        
        st.dataframe(
            df_recent[available_columns],
            use_container_width=True,
            hide_index=True
        )
    
    # Panel de información
    with st.expander("ℹ️ Información del Sistema"):
        st.markdown("""
        **Funcionalidades del Sistema:**
        - ✅ Registro de cuotas de administración
        - ✅ Registro de cuotas extraordinarias  
        - ✅ Captura de multas y otros pagos
        - ✅ Subida y guardado local de soportes de pago
        - ✅ Validación automática de datos
        - ✅ Generación de IDs únicos
        - ✅ Integración con Google Sheets
        - ✅ Almacenamiento de archivos en carpeta local
        
        **Campos Obligatorios:**
        - Tipo de Operación
        - Unidad
        - Concepto
        - Monto
        - Fecha
        - Banco/Entidad
        - Estado
        - Método de Pago
        
        **Formatos de Archivo Soportados:**
        - PDF, JPG, JPEG, PNG
        
        **Almacenamiento de Archivos:**
        - Los archivos se guardan en la carpeta 'archivos_subidos'
        - Se genera un nombre único para cada archivo
        - La ruta del archivo se registra en Google Sheets
        
        **Estados Disponibles:**
        - Pagado: Pago confirmado y procesado
        - Pendiente: Pago no realizado
        - En Verificación: Pago en proceso de validación
        - Rechazado: Pago no válido o rechazado
        """)
    
    # Mostrar información del directorio de archivos
    upload_dir = "archivos_subidos"
    if os.path.exists(upload_dir):
        files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
        st.info(f"📁 Archivos guardados en '{upload_dir}': {files_count}")

#if __name__ == "__main__":
#    pago_main()