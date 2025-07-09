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
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import locale

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

def create_receipts_directory():
    """Crear directorio para recibos si no existe"""
    receipts_dir = "recibos_caja"
    if not os.path.exists(receipts_dir):
        os.makedirs(receipts_dir)
        st.info(f"📁 Directorio '{receipts_dir}' creado exitosamente")
    return receipts_dir

def number_to_words(n):
    """Convertir número a palabras en español (para recibos)"""
    # Función básica para convertir números a palabras
    # Para una implementación completa, podrías usar la librería 'num2words'
    
    unidades = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
    decenas = ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
    especiales = ["diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve"]
    centenas = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"]
    
    if n == 0:
        return "cero"
    
    if n < 10:
        return unidades[n]
    elif n < 20:
        return especiales[n - 10]
    elif n < 100:
        if n % 10 == 0:
            return decenas[n // 10]
        else:
            return decenas[n // 10] + " y " + unidades[n % 10]
    elif n < 1000:
        if n == 100:
            return "cien"
        else:
            resto = n % 100
            return centenas[n // 100] + (" " + number_to_words(resto) if resto != 0 else "")
    elif n < 1000000:
        miles = n // 1000
        resto = n % 1000
        if miles == 1:
            return "mil" + (" " + number_to_words(resto) if resto != 0 else "")
        else:
            return number_to_words(miles) + " mil" + (" " + number_to_words(resto) if resto != 0 else "")
    
    return str(n)  # Para números muy grandes, devolver como string

def generate_receipt_pdf(payment_data, receipt_number):
    """Generar recibo de caja en PDF"""
    try:
        receipts_dir = create_receipts_directory()
        filename = f"Recibo_{receipt_number}_{payment_data['ID']}.pdf"
        filepath = os.path.join(receipts_dir, filename)
        
        # Crear documento PDF
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        
        # Crear estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            alignment=TA_LEFT,
            textColor=colors.black
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_LEFT
        )
        
        # Elementos del documento
        elements = []
        
        # Encabezado del conjunto/administración
        elements.append(Paragraph("CONJUNTO RESIDENCIAL / ADMINISTRACIÓN", title_style))
        elements.append(Paragraph("RECIBO DE CAJA", title_style))
        elements.append(Spacer(1, 20))
        
        # Número de recibo y fecha
        receipt_info = [
            ["Recibo No:", receipt_number],
            ["Fecha:", payment_data['Fecha']],
            ["ID Transacción:", payment_data['ID']]
        ]
        
        receipt_table = Table(receipt_info, colWidths=[2*inch, 3*inch])
        receipt_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(receipt_table)
        elements.append(Spacer(1, 20))
        
        # Información del pagador
        elements.append(Paragraph("DATOS DEL PAGADOR", header_style))
        
        payer_info = [
            ["Unidad/Apartamento:", payment_data['Unidad']],
            ["Concepto:", payment_data['Concepto']],
            ["Tipo de Operación:", payment_data['Tipo_Operacion']]
        ]
        
        payer_table = Table(payer_info, colWidths=[2*inch, 4*inch])
        payer_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(payer_table)
        elements.append(Spacer(1, 20))
        
        # Detalle del pago
        elements.append(Paragraph("DETALLE DEL PAGO", header_style))
        
        # Formatear monto
        try:
            monto_float = float(payment_data['Monto'])
            monto_formatted = f"${monto_float:,.2f}"
            
            # Convertir a palabras (parte entera)
            parte_entera = int(monto_float)
            centavos = int((monto_float - parte_entera) * 100)
            
            monto_palabras = number_to_words(parte_entera).upper()
            if centavos > 0:
                monto_palabras += f" CON {centavos}/100"
            monto_palabras += " PESOS COLOMBIANOS"
            
        except:
            monto_formatted = f"${payment_data['Monto']}"
            monto_palabras = "MONTO EN NÚMEROS"
        
        payment_detail = [
            ["Monto en números:", monto_formatted],
            ["Monto en letras:", monto_palabras],
            ["Método de pago:", payment_data['Metodo_Pago']],
            ["Estado:", payment_data['Estado']]
        ]
        
        payment_table = Table(payment_detail, colWidths=[2*inch, 4*inch])
        payment_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),  # Resaltar monto en letras
        ]))
        
        elements.append(payment_table)
        elements.append(Spacer(1, 30))
        
        # Observaciones si existen
        if payment_data['Observaciones'] and payment_data['Observaciones'] != "Sin observaciones":
            elements.append(Paragraph("OBSERVACIONES", header_style))
            elements.append(Paragraph(payment_data['Observaciones'], normal_style))
            elements.append(Spacer(1, 20))
        
        # Firmas
        elements.append(Spacer(1, 40))
        
        signature_data = [
            ["_________________________", "_________________________"],
            ["RECIBÍ CONFORME", "ENTREGUÉ CONFORME"],
            ["Nombre:", "Nombre:"],
            ["C.C.:", "C.C.:"],
            ["Fecha:", "Fecha:"]
        ]
        
        signature_table = Table(signature_data, colWidths=[3*inch, 3*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, 1), 15),
        ]))
        
        elements.append(signature_table)
        elements.append(Spacer(1, 20))
        
        # Pie de página
        footer_text = f"Recibo generado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        elements.append(Paragraph(footer_text, footer_style))
        
        # Construir PDF
        doc.build(elements)
        
        return filepath, filename
        
    except Exception as e:
        st.error(f"❌ Error generando recibo PDF: {str(e)}")
        return None, None

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

def generate_receipt_number():
    """Generar número consecutivo para recibo de caja"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"RC-{timestamp}"

def create_or_update_worksheet(_client):
    """Crear o verificar la estructura de la hoja de trabajo"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        
        # Columnas requeridas (agregamos Numero_Recibo y Ruta_Recibo)
        required_columns = [
            'ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 
            'Fecha', 'Banco', 'Estado', 'Metodo_Pago', 'Soporte_Pago', 
            'Ruta_Archivo', 'Numero_Recibo', 'Ruta_Recibo', 'Observaciones', 'Saldo_Pendiente','Registrado'
        ]
        
        try:
            worksheet = spreadsheet.worksheet("Administracion_Financiera")
            # Verificar si tiene encabezados
            headers = worksheet.row_values(1)
            if not headers or len(headers) < len(required_columns):
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
            payment_data.get('Numero_Recibo', ''),
            payment_data.get('Ruta_Recibo', ''),
            payment_data['Observaciones'],
            payment_data['Saldo_Pendiente'],
            payment_data['Registrado']
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

def check_payment_exists(df_existing, tipo_operacion, unidad, concepto):
    """
    Verifica si ya existe un pago con los mismos parámetros
    
    Args:
        df_existing: DataFrame con registros existentes
        tipo_operacion: Tipo de operación del pago
        unidad: Unidad/Casa/Lote
        concepto: Concepto del pago
    
    Returns:
        dict: {'exists': bool, 'records': list, 'count': int}
    """
    if df_existing.empty:
        return {'exists': False, 'records': [], 'count': 0}
    
    # Buscar registros que coincidan
    mask = (
        (df_existing['Tipo_Operacion'].str.strip().str.lower() == tipo_operacion.strip().lower()) &
        (df_existing['Unidad'].str.strip().str.lower() == unidad.strip().lower()) &
        (df_existing['Concepto'].str.strip().str.lower() == concepto.strip().lower()) 
    )
    
    matching_records = df_existing[mask]
    
    return {
        'exists': len(matching_records) > 0,
        'records': matching_records.to_dict('records') if len(matching_records) > 0 else [],
        'count': len(matching_records)
    }

def get_deletable_payments(df_existing, tipo_operacion, unidad, concepto):
    """
    Obtiene los pagos que pueden ser eliminados (Estado != "Aplicado" otros)
    DataFrame con registros eliminables
    """
    if df_existing.empty:
        return pd.DataFrame()
    
    # Buscar registros que coincidan y NO estén "Aplicados"
    mask = (
        (df_existing['Tipo_Operacion'].str.strip().str.lower() == tipo_operacion.strip().lower()) &
        (df_existing['Unidad'].str.strip().str.lower() == unidad.strip().lower()) &
        (df_existing['Concepto'].str.strip().str.lower() == concepto.strip().lower()) &
        (
            (df_existing['Estado'].str.strip().str.lower().isin(["pagado"])) &
            (~df_existing['Registrado'].str.strip().str.lower().isin(["principal"]))
        )
    )
    
    return df_existing[mask]

def delete_payment_record(client, payment_id):
    """
    Elimina un registro de pago por su ID
    bool: True si se eliminó exitosamente, False en caso contrario
    """
    try:
        # Validar que el cliente esté disponible
        if client is None:
            st.error("❌ Cliente de Google Sheets no disponible")
            return False
                
        # Obtener todos los datos
        try:
            sheet = client.open("gestion-conjuntos")
            worksheet = sheet.worksheet("Administracion_Financiera")
            all_records = worksheet.get_all_records()

        except Exception as e:
            st.error(f"📊 Error al obtener los datos de la hoja: {str(e)}")
            return False
        
        if not all_records:
            st.error("📊 No se encontraron registros en la hoja")
            return False
        
        # Encontrar la fila a eliminar
        # (agregamos 2 porque: 1 para el header + 1 para indexado base-1)
        row_to_delete = None
        found_record = None
        
        for idx, record in enumerate(all_records):
            if str(record.get('ID', '')) == str(payment_id):
                row_to_delete = idx + 2  # +2 por header y indexado base-1
                found_record = record
                break
        
        if row_to_delete is None:
            st.error(f"🔍 No se encontró el registro con ID: {payment_id}")
            return False
        
        # Mostrar información del registro que se va a eliminar
        st.info(f"🗑️ Eliminando registro en fila {row_to_delete}:")
        #st.write(f"   • **ID:** {found_record.get('ID', 'N/A')}")
        #st.write(f"   • **Unidad:** {found_record.get('Unidad', 'N/A')}")
        #st.write(f"   • **Concepto:** {found_record.get('Concepto', 'N/A')}")
        #st.write(f"   • **Monto:** ${found_record.get('Monto', 0):,.2f}")
        
        # Eliminar la fila (usando worksheet en lugar de sheet)
        try:
            worksheet.delete_rows(row_to_delete)
            st.success(f"✅ Registro eliminado exitosamente!")
            st.success(f"   • **ID eliminado:** {payment_id}")
            st.success(f"   • **Fila eliminada:** {row_to_delete}")
            return True
            
        except Exception as e:
            st.error(f"❌ Error al eliminar la fila {row_to_delete}: {str(e)}")
            return False
            
    except Exception as e:
        st.error(f"❌ Error inesperado al eliminar el registro: {str(e)}")
        st.error(f"   • **ID del pago:** {payment_id}")
        st.error(f"   • **Detalles del error:** {type(e).__name__}")
        return False


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
    
    # Pestañas para diferentes funcionalidades
    tab1, tab2 = st.tabs(["📝 Registrar Pago", "🗑️ Eliminar Pago"])
    
    # ========== TAB 1: REGISTRAR PAGO ==========
    with tab1:
        st.header("📝 Registro de Nuevo Pago")
        
        with st.form("payment_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Tipo de Operación
                tipo_operacion = st.selectbox(
                    "💰 Tipo de Operación *",
                    options=["Cuota de Mantenimiento", "Cuota Extraordinaria", "Multa", "Otro"],
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
                    "Cuota - Enero",
                    "Cuota - Febrero", 
                    "Cuota - Marzo",
                    "Cuota - Abril",
                    "Cuota - Mayo",
                    "Cuota - Junio",
                    "Cuota - Julio",
                    "Cuota - Agosto",
                    "Cuota - Septiembre",
                    "Cuota - Octubre",
                    "Cuota - Noviembre",
                    "Cuota - Diciembre",
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
                
                # Verificar duplicados en tiempo real
                if unidad and concepto and tipo_operacion:
                    duplicate_check = check_payment_exists(df_existing, tipo_operacion, unidad, concepto)
                    
                    if duplicate_check['exists']:
                        st.warning(f"⚠️ **ATENCIÓN**: Ya existen {duplicate_check['count']} registro(s) con los mismos datos:")
                        
                        # Mostrar registros existentes
                        for idx, record in enumerate(duplicate_check['records']):
                            with st.expander(f"Registro {idx + 1} - ID: {record.get('ID', 'N/A')}"):
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.write(f"**Fecha:** {record.get('Fecha', 'N/A')}")
                                    st.write(f"**Monto:** ${record.get('Monto', 0):,.2f}")
                                    st.write(f"**Estado:** {record.get('Estado', 'N/A')}")
                                with col_b:
                                    st.write(f"**Banco:** {record.get('Banco', 'N/A')}")
                                    st.write(f"**Método:** {record.get('Metodo_Pago', 'N/A')}")
                                    st.write(f"**Registrado:** {record.get('Registrado', 'N/A')}")
                        
                        st.info("💡 Si desea continuar, asegúrese de que no sea un registro duplicado.")
                
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
                
                # Mostrar información especial para pagos en efectivo
                if metodo_pago == "Efectivo":
                    st.info("🧾 **Pago en Efectivo**: Se generará automáticamente un recibo de caja.")
                
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
                registrado = st.text_input(
                    "📝 Registrado por:",
                    placeholder="Ingrese el Nombre de quien Realiza el Pago (opcional)"
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
                # Verificar duplicados antes de guardar
                duplicate_check = check_payment_exists(df_existing, tipo_operacion, unidad, concepto)
                
                if duplicate_check['exists']:
                    st.warning("⚠️ **ADVERTENCIA DE DUPLICADO**")
                    st.write("Se encontraron registros similares. ¿Está seguro de que desea continuar?")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Sí, Registrar de Todas Formas", type="primary"):
                            st.session_state.confirm_duplicate = True
                    
                    with col2:
                        if st.button("❌ Cancelar Registro"):
                            st.session_state.confirm_duplicate = False
                            st.info("Registro cancelado. Revise los datos antes de continuar.")
                
                # Proceder con el registro si no hay duplicados o si se confirmó
                if not duplicate_check['exists'] or st.session_state.get('confirm_duplicate', False):
                    # Generar ID único
                    unique_id = generate_unique_id(unidad)
                    
                    # Generar número de recibo si es pago en efectivo
                    receipt_number = None
                    receipt_path = None
                    receipt_filename = None
                    
                    if metodo_pago == "Efectivo":
                        receipt_number = generate_receipt_number()
                    
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
                        'Numero_Recibo': receipt_number if receipt_number else "",
                        'Ruta_Recibo': "",  # Se actualizará después de generar el recibo
                        'Observaciones': observaciones.strip() if observaciones else "Sin observaciones",
                        "Saldo_Pendiente": 0,
                        "Registrado": registrado
                    }
                    
                    # Generar recibo de caja para pagos en efectivo
                    if metodo_pago == "Efectivo" and receipt_number:
                        with st.spinner("Generando recibo de caja..."):
                            receipt_path, receipt_filename = generate_receipt_pdf(payment_data, receipt_number)
                        
                        if receipt_path:
                            payment_data['Ruta_Recibo'] = receipt_path
                            st.success(f"✅ Recibo de caja generado: {receipt_filename}")
                        else:
                            st.warning("⚠️ No se pudo generar el recibo de caja, pero el registro continuará")
                    
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
                            
                            # Mostrar información del recibo si se generó
                            if metodo_pago == "Efectivo" and receipt_number:
                                st.write(f"**Recibo No:** {receipt_number}")
                                if receipt_path:
                                    st.write(f"**Recibo guardado en:** {receipt_path}")

                        # NUEVA FUNCIONALIDAD: Generar archivo CSV del pago registrado
                        csv_path, csv_filename = generate_enhanced_payment_csv(payment_data)
                        
                        if csv_path:
                            st.success(f"✅ Archivo CSV generado: {csv_filename}")
                        
                        # Área de descargas
                        st.markdown("---")
                        st.subheader("📥 Descargas Disponibles")
                        
                        # Crear columnas para organizar las descargas
                        download_cols = st.columns(3)
                        
                        # Botón para descargar CSV
                        if csv_path and os.path.exists(csv_path):
                            with download_cols[0]:
                                with open(csv_path, "r", encoding="utf-8") as csv_file:
                                    csv_content = csv_file.read()
                                
                                st.download_button(
                                    label="📊 Descargar CSV",
                                    data=csv_content,
                                    file_name=csv_filename,
                                    mime="text/csv",
                                    type="secondary",
                                    use_container_width=True
                                )

                        
                        # Botón para descargar recibo si existe
                        if metodo_pago == "Efectivo" and receipt_path and os.path.exists(receipt_path):
                            st.markdown("---")
                            st.subheader("🧾 Recibo de Caja")
                            
                            col1, col2, col3 = st.columns([1, 1, 1])
                            with col2:
                                # Leer archivo PDF para descarga
                                with open(receipt_path, "rb") as pdf_file:
                                    pdf_bytes = pdf_file.read()
                                
                                st.download_button(
                                    label="📄 Descargar Recibo de Caja",
                                    data=pdf_bytes,
                                    file_name=receipt_filename,
                                    mime="application/pdf",
                                    type="secondary",
                                    use_container_width=True
                                )
                            
                            st.success("💡 **Recibo generado exitosamente!** Puede descargarlo usando el botón de arriba.")
                        
                        # Limpiar cache para refrescar datos
                        st.cache_data.clear()
                        
                        # Limpiar estado de confirmación de duplicado
                        if 'confirm_duplicate' in st.session_state:
                            del st.session_state.confirm_duplicate
                        
                        # Opción para registrar otro pago
                        if st.button("➕ Registrar Otro Pago"):
                            st.rerun()
                    
                    else:
                        st.error("❌ **Error al registrar el pago**")
                        st.error("Por favor, verifique la conexión e intente nuevamente")
    
    # ========== TAB 2: ELIMINAR PAGO (VERSIÓN CORREGIDA) ==========
    with tab2:
        st.header("🗑️ Eliminar Pago")
        st.info("🔍 **Busque pagos para eliminar** - Solo se pueden eliminar pagos que NO estén marcados como 'Aplicados'")
    
        # Inicializar variables de session state
        if 'search_performed' not in st.session_state:
            st.session_state.search_performed = False
    
        if 'search_criteria' not in st.session_state:
            st.session_state.search_criteria = {}
    
        # Inicializar estado de confirmación para cada pago
        if 'pending_delete' not in st.session_state:
            st.session_state.pending_delete = {}

        with st.form("delete_search_form"):
            col1, col2 = st.columns(2)
        
            with col1:
                tipo_operacion_del = st.selectbox(
                    "💰 Tipo de Operación",
                    options=["", "Cuota de Mantenimiento", "Cuota Extraordinaria", "Multa", "Otro"],
                    help="Seleccione el tipo de operación a buscar"
                )
            
                unidades_existentes_del = get_unique_values(df_existing, 'Unidad')
                unidad_del = st.selectbox(
                    "🏠 Unidad",
                    options=[""] + unidades_existentes_del,
                    help="Seleccione la unidad"
                )
        
            with col2:
                conceptos_con_banco = df_existing[df_existing['Banco'].notna()]['Concepto'].unique()
                conceptos_existentes = sorted(conceptos_con_banco)

                concepto_del = st.selectbox("📋 Concepto", conceptos_existentes, help="Seleccione el concepto"
                )
                #conceptos_existentes = get_unique_values(df_existing, 'Concepto')
                #concepto_del = st.selectbox(
                #    "📋 Concepto",
                #    options=[""] + conceptos_existentes,
                #    help="Seleccione el concepto"
                #)
        
            search_button = st.form_submit_button("🔍 Buscar Pagos para Eliminar", type="primary")
    
        # Procesar búsqueda
        if search_button and tipo_operacion_del and unidad_del and concepto_del:
            st.session_state.search_criteria = {
                'tipo_operacion': tipo_operacion_del,
                'unidad': unidad_del,
                'concepto': concepto_del
            }
            st.session_state.search_performed = True
            st.session_state.deletable_payments = get_deletable_payments(df_existing, tipo_operacion_del, unidad_del, concepto_del)
            # Limpiar estados de confirmación al hacer nueva búsqueda
            st.session_state.pending_delete = {}
    
        elif search_button:
            st.warning("⚠️ Por favor, complete todos los campos de búsqueda (Tipo de Operación, Unidad y Concepto)")
            st.session_state.search_performed = False
    
        # Mostrar resultados de búsqueda
        if st.session_state.search_performed and 'deletable_payments' in st.session_state:
            deletable_payments = st.session_state.deletable_payments
            criteria = st.session_state.search_criteria
        
            st.markdown("---")
            st.write(f"**Criterios de búsqueda:** {criteria['tipo_operacion']} - {criteria['unidad']} - {criteria['concepto']}")
        
            if deletable_payments.empty:
                st.info("ℹ️ No se encontraron pagos eliminables con los criterios especificados.")
                st.write("**Recordatorio:** Solo se pueden eliminar pagos que NO estén marcados como 'Aplicado'")
            else:
                st.success(f"✅ Se encontraron {len(deletable_payments)} pago(s) que pueden ser eliminados:")
            
                # Mostrar cada pago con opción de eliminar
                for idx, (_, payment) in enumerate(deletable_payments.iterrows()):
                    payment_id = payment.get('ID', f'unknown_{idx}')
                
                    with st.container():
                        st.markdown(f"### 📋 Pago {idx + 1} - ID: {payment_id}")
                    
                        # Información del pago
                        info_col1, info_col2 = st.columns(2)
                    
                        with info_col1:
                            st.write(f"**Fecha:** {payment.get('Fecha', 'N/A')}")
                            st.write(f"**Monto:** ${payment.get('Monto', 0):,.2f}")
                            st.write(f"**Estado:** {payment.get('Estado', 'N/A')}")
                            st.write(f"**Registrado por:** {payment.get('Registrado', 'N/A')}")
                    
                        with info_col2:
                            st.write(f"**Banco:** {payment.get('Banco', 'N/A')}")
                            st.write(f"**Método:** {payment.get('Metodo_Pago', 'N/A')}")
                            st.write(f"**Soporte:** {payment.get('Soporte_Pago', 'N/A')}")
                            st.write(f"**Observaciones:** {payment.get('Observaciones', 'N/A')}")
                    
                        # Área de botones para eliminar
                        action_col1, action_col2, action_col3 = st.columns([1, 1, 2])
                    
                        # Verificar si este pago está en estado de confirmación
                        is_pending_delete = st.session_state.pending_delete.get(payment_id, False)
                    
                        if not is_pending_delete:
                            # Mostrar botón de eliminar
                            with action_col1:
                                if st.button(f"🗑️ Eliminar", key=f"delete_{payment_id}_{idx}", type="secondary"):
                                    st.session_state.pending_delete[payment_id] = True
                                    st.rerun()
                        else:
                            # Mostrar botones de confirmación
                            
                            with action_col1:
                                if st.button(f"✅ Confirmar Eliminación", key=f"confirm_    {payment_id}_{idx}", type="primary"):
                                    # Ejecutar eliminación CON CONFIG
                                    with st.spinner(f"Eliminando pago ID: {payment_id}..."):
                                        # Pasar la configuración como parámetro
                                        success = delete_payment_record(client, payment_id)
            
                                    if success:
                                        st.success(f"✅ Pago {payment_id} eliminado exitosamente")
                                        # Limpiar estados y recargar
                                        st.session_state.search_performed = False
                                        st.session_state.pending_delete = {}
                                        if 'deletable_payments' in st.session_state:
                                            del st.session_state.deletable_payments
                                        if 'search_criteria' in st.session_state:
                                            del st.session_state.search_criteria
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Error al eliminar el pago {payment_id}")
                                        st.session_state.pending_delete[payment_id] = False
                        
                            with action_col2:
                                if st.button(f"❌ Cancelar", key=f"cancel_{payment_id}_{idx}", type="secondary"):
                                    st.session_state.pending_delete[payment_id] = False
                                    st.rerun()
                        
                            with action_col3:
                                st.warning("⚠️ **¿Está seguro de eliminar este pago?**")
                    
                    st.markdown("---")
            
            # Botón para nueva búsqueda
            if st.button("🔄 Nueva Búsqueda", type="primary"):
                st.session_state.search_performed = False
                st.session_state.pending_delete = {}
                if 'deletable_payments' in st.session_state:
                    del st.session_state.deletable_payments
                if 'search_criteria' in st.session_state:
                    del st.session_state.search_criteria
                st.rerun() 
                                                                
        elif search_button:
            st.warning("⚠️ Por favor, complete todos los campos de búsqueda (Tipo de Operación, Unidad y Concepto)")

# ========== FUNCIÓN PARA GENERAR ARCHIVO CSV ==========
def generate_payment_csv(payment_data):
    """
    Genera un archivo CSV con los datos del pago registrado
    
    Args:
        payment_data (dict): Diccionario con los datos del pago
        
    Returns:
        tuple: (ruta_archivo, nombre_archivo) o (None, None) si hay error
    """
    try:
        import pandas as pd
        import os
        from datetime import datetime
        
        # Crear directorio si no existe
        upload_dir = "archivos_subidos"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Convertir payment_data a DataFrame
        df_payment = pd.DataFrame([payment_data])
        
        # Generar nombre único para el archivo CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        payment_id = payment_data.get('ID', 'unknown')
        csv_filename = f"pago_{payment_id}_{timestamp}.csv"
        csv_path = os.path.join(upload_dir, csv_filename)
        
        # Ordenar columnas para mejor presentación
        column_order = [
            'ID',
            'Fecha',
            'Tipo_Operacion',
            'Unidad', 
            'Concepto',
            'Monto',
            'Estado',
            'Banco',
            'Metodo_Pago',
            'Soporte_Pago',
            'Ruta_Archivo',
            'Numero_Recibo',
            'Ruta_Recibo',
            'Observaciones',
            'Saldo_Pendiente',
            'Registrado'
        ]
        
        # Reordenar DataFrame según column_order
        df_payment = df_payment.reindex(columns=column_order)
        
        # Formatear monto como moneda
        df_payment['Monto'] = df_payment['Monto'].apply(lambda x: f"${x:,.2f}")
        
        # Guardar CSV con encoding UTF-8 para caracteres especiales
        df_payment.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        return csv_path, csv_filename
        
    except Exception as e:
        print(f"Error al generar archivo CSV: {str(e)}")
        return None, None


# ========== FUNCIÓN AUXILIAR PARA CREAR HEADERS AMIGABLES ==========
def create_friendly_csv_headers(df):
    """
    Crea headers más amigables para el CSV
    
    Args:
        df (DataFrame): DataFrame con los datos
        
    Returns:
        DataFrame: DataFrame con headers amigables
    """
    try:
        # Mapeo de columnas técnicas a nombres amigables
        header_mapping = {
            'ID': 'ID del Pago',
            'Fecha': 'Fecha del Pago',
            'Tipo_Operacion': 'Tipo de Operación',
            'Unidad': 'Unidad/Apartamento',
            'Concepto': 'Concepto del Pago',
            'Monto': 'Monto del Pago',
            'Estado': 'Estado del Pago',
            'Banco': 'Banco/Entidad',
            'Metodo_Pago': 'Método de Pago',
            'Soporte_Pago': 'Archivo de Soporte',
            'Ruta_Archivo': 'Ubicación del Archivo',
            'Numero_Recibo': 'Número de Recibo',
            'Ruta_Recibo': 'Ubicación del Recibo',
            'Observaciones': 'Observaciones',
            'Saldo_Pendiente': 'Saldo Pendiente',
            'Registrado': 'Registrado Por'
        }
        
        # Renombrar columnas
        df_friendly = df.rename(columns=header_mapping)
        
        return df_friendly
        
    except Exception as e:
        print(f"Error al crear headers amigables: {str(e)}")
        return df


# ========== FUNCIÓN PARA GENERAR CSV MEJORADO ==========
def generate_enhanced_payment_csv(payment_data):
    """
    Genera un archivo CSV mejorado con los datos del pago registrado
    
    Args:
        payment_data (dict): Diccionario con los datos del pago
        
    Returns:
        tuple: (ruta_archivo, nombre_archivo) o (None, None) si hay error
    """
    try:
        import pandas as pd
        import os
        from datetime import datetime
        
        # Crear directorio si no existe
        upload_dir = "archivos_subidos"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Convertir payment_data a DataFrame
        df_payment = pd.DataFrame([payment_data])
        
        # Aplicar headers amigables
        df_payment = create_friendly_csv_headers(df_payment)
        
        # Generar nombre único para el archivo CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        payment_id = payment_data.get('ID', 'unknown')
        unidad = payment_data.get('Unidad', 'sin_unidad').replace(' ', '_').replace('/', '_')
        
        csv_filename = f"registro_pago_{unidad}_{payment_id}_{timestamp}.csv"
        csv_path = os.path.join(upload_dir, csv_filename)
        
        # Agregar información adicional al inicio del CSV
        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            # Escribir encabezado informativo
            f.write("SISTEMA DE REGISTRO DE PAGOS\n")
            f.write("="*50 + "\n")
            f.write(f"Fecha de Generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Archivo: {csv_filename}\n")
            f.write("="*50 + "\n\n")
        
        # Agregar los datos del pago
        df_payment.to_csv(csv_path, mode='a', index=False, encoding='utf-8-sig')
        
        # Agregar información adicional al final
        with open(csv_path, 'a', encoding='utf-8-sig') as f:
            f.write("\n" + "="*50 + "\n")
            f.write("NOTAS IMPORTANTES:\n")
            f.write("- Este archivo contiene información confidencial\n")
            f.write("- Mantenga este registro en lugar seguro\n")
            f.write("- Para consultas contacte al administrador\n")
            f.write("="*50 + "\n")
        
        return csv_path, csv_filename
        
    except Exception as e:
        print(f"Error al generar archivo CSV mejorado: {str(e)}")
        return None, None
    
    # Información adicional
    st.markdown("---")
    
    # Mostrar últimos pagos registrados
    if not df_existing.empty and estado =='Pagado':
        st.header("📊 Últimos Pagos Registrados")
        
        # Mostrar últimos 5 registros
        df_recent = df_existing.tail(5).sort_values('Fecha', ascending=False) if 'Fecha' in df_existing.columns else df_existing.tail(5)
        
        # Seleccionar columnas para mostrar
        columns_to_show = ['ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha', 'Estado', 'Metodo_Pago']
        available_columns = [col for col in columns_to_show if col in df_recent.columns]
        
        # Agregar columna de recibo si existe
        if 'Numero_Recibo' in df_recent.columns:
            available_columns.append('Numero_Recibo')
        
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
        - ✅ **Generación automática de recibos de caja para pagos en efectivo**
        - ✅ Validación automática de datos
        - ✅ Generación de IDs únicos
        - ✅ Integración con Google Sheets
        - ✅ Almacenamiento de archivos en carpeta local
        - ✅ **Descarga de recibos en formato PDF**
        
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
        - Los recibos de caja se guardan en la carpeta 'recibos_caja'
        - Se genera un nombre único para cada archivo
        - La ruta del archivo se registra en Google Sheets
        
        **Estados Disponibles:**
        - Pagado: Pago confirmado y procesado
        - Pendiente: Pago no realizado
        - En Verificación: Pago en proceso de validación
        - Rechazado: Pago no válido o rechazado
        
        **🧾 Recibos de Caja:**
        - Se generan automáticamente para pagos en **Efectivo**
        - Incluyen información completa del pago y pagador
        - Monto en números y letras
        - Espacios para firmas de quien recibe y entrega
        - Formato profesional en PDF
        - Numeración consecutiva automática
        - Descarga inmediata disponible
        """)
    
    # Mostrar información de directorios
    upload_dir = "archivos_subidos"
    receipts_dir = "recibos_caja"
    
    col1, col2 = st.columns(2)
    
    with col1:
        if os.path.exists(upload_dir):
            files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
            st.info(f"📁 Archivos guardados en '{upload_dir}': {files_count}")
    
    with col2:
        if os.path.exists(receipts_dir):
            receipts_count = len([f for f in os.listdir(receipts_dir) if os.path.isfile(os.path.join(receipts_dir, f)) and f.endswith('.pdf')])
            st.info(f"🧾 Recibos generados en '{receipts_dir}': {receipts_count}")



#if __name__ == "__main__":
#    pago_main()