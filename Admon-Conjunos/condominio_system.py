import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
from control_financiero import control_main
from informe_estado_financiero import informe_estado_main
import hashlib
import time
import ssl
import os
from googleapiclient.errors import HttpError
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import orjson
except ImportError:
    orjson = None
except Exception as e:
    st.warning(f"orjson import issue: {e}. Using standard json instead.")
    orjson = None

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Administración de Condominios",
#    page_icon="🏢",
#    layout="wide",
#    initial_sidebar_state="expanded"
#)

def initialize_session_state():
    """Inicializar todas las variables de session_state necesarias"""
    if 'manager' not in st.session_state:
        st.session_state.manager = CondominiumManager()
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None

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

class CondominiumManager:
    def __init__(self):
        self.spreadsheet_name = "gestion-conjuntos"
        self.worksheets = {
            'residentes': 'Control_Residentes',
            'financiero': 'Administracion_Financiera',
            'mantenimiento': 'Gestion_Mantenimiento',
            'comunicacion': 'Comunicacion_Residentes',
            'accesos': 'Control_Accesos',
            'areas_comunes': 'Areas_Comunes',
            'ventas': 'Ventas_Lotes',
            'usuarios': 'usuarios'
        }
        self.gc = None
        self.spreadsheet = None
        self._last_connection_check = 0
        self._connection_check_interval = 300  # 5 minutos
        self.update_data = None

    def authenticate(self):
        """Autenticar con Google Drive usando las credenciales proporcionadas"""
        try:
            # Cargar credenciales
            creds, config = load_credentials_from_toml()
            if not creds:
                return False
            
            # Establecer conexión
            self.gc = get_google_sheets_connection(creds)
            if not self.gc:
                return False
            
            # Intentar abrir o crear el spreadsheet
            try:
                self.spreadsheet = self.gc.open(self.spreadsheet_name)
                st.success(f"📊 Spreadsheet '{self.spreadsheet_name}' abierto correctamente")
            except gspread.SpreadsheetNotFound:
                st.info(f"📋 Creando nuevo spreadsheet: {self.spreadsheet_name}")
                self.spreadsheet = self.gc.create(self.spreadsheet_name)
                st.success(f"✅ Spreadsheet '{self.spreadsheet_name}' creado exitosamente")
                
            # Crear hojas de trabajo si no existen
            self.create_worksheets()
            return True
            
        except Exception as e:
            st.error(f"❌ Error de autenticación: {str(e)}")
            return False

    def _reconnect_if_needed(self):
        """Verificar y reconectar si es necesario"""
        current_time = time.time()
        
        # Verificar cada 5 minutos o si no hay conexión
        if (current_time - self._last_connection_check > self._connection_check_interval 
            or self.spreadsheet is None):
            
            try:
                # Intentar reconectar
                self.authenticate() #connect()
                self._last_connection_check = current_time
                return True
            except Exception as e:
                st.error(f"Error en reconexión: {str(e)}")
                return False
        return True

    def create_worksheets(self):
        """Crear todas las hojas de trabajo necesarias"""
        if not self.spreadsheet:
            st.error("❌ No hay conexión con el spreadsheet")
            return False
            
        try:
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            
            for key, sheet_name in self.worksheets.items():
                if sheet_name not in existing_sheets:
                    try:
                        self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
                        st.info(f"📝 Creada hoja: {sheet_name}")
                        self.initialize_worksheet_headers(key, sheet_name)
                    except Exception as e:
                        st.warning(f"⚠️ No se pudo crear la hoja {sheet_name}: {str(e)}")
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error creando hojas de trabajo: {str(e)}")
            return False
    
    def initialize_worksheet_headers(self, worksheet_type, sheet_name):
        """Inicializar headers para cada tipo de hoja"""
        headers = {
            'residentes': ['ID', 'Idenificacion','Nombre', 'Apellido', 'Unidad', 'Tipo', 'Telefono', 'Email', 'Fecha_Ingreso', 'Estado', 'Observaciones'],
            'financiero': ['ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha', 'Estado', 'Metodo_Pago', 'Soporte_Pago',	'Ruta_Archivo',	'Numero_Recibo',	'Ruta_Recibo', 'Observaciones', 'Saldo_Pendiente',	'Registrado'],
            'mantenimiento': ['ID', 'Tipo_Servicio', 'Unidad', 'Descripcion', 'Fecha_Solicitud', 'Fecha_Programada', 'Estado', 'Costo', 'Proveedor'],
            'comunicacion': ['ID', 'Tipo', 'Destinatario', 'Asunto', 'Mensaje', 'Fecha_Envio', 'Estado', 'Respuesta'],
            'accesos': ['ID', 'Unidad', 'Visitante', 'Fecha', 'Hora_Entrada', 'Hora_Salida', 'Autorizado_Por', 'Observaciones'],
            'areas_comunes': ['ID', 'Area', 'Unidad', 'Fecha_Reserva', 'Hora_Inicio', 'Hora_Fin', 'Estado', 'Costo', 'Observaciones'],
            'ventas': ['ID', 'Lote', 'Cliente', 'Telefono', 'Email', 'Precio', 'Estado', 
                      'Fecha_Venta', 'Forma_Pago', 'Observaciones'],
            'usuarios': ['ID', 'Usuario', 'Password_Hash', 'Rol', 'Fecha_Creacion', 'Estado']
        }
        
        if worksheet_type in headers:
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
                worksheet.update('A1', [headers[worksheet_type]])
                st.success(f"✅ Headers inicializados para {sheet_name}")
            except Exception as e:
                st.error(f"❌ Error inicializando headers para {sheet_name}: {str(e)}")

    def get_worksheet(self, worksheet_key):
        """Obtener una hoja de trabajo específica con reconexión automática"""
        try:
            # Verificar/reconectar si es necesario
            if not self._reconnect_if_needed():
                st.error("❌ No se pudo establecer conexión con Google Sheets")
                return None
            
            if not self.spreadsheet:
                st.error("❌ No hay conexión con el spreadsheet")
                return None
                
            worksheet_name = self.worksheets.get(worksheet_key)
            if not worksheet_name:
                st.error(f"❌ Hoja de trabajo no encontrada: {worksheet_key}")
                return None
            
            # Intentar obtener la hoja
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            return worksheet
            
        except gspread.WorksheetNotFound:
            st.error(f"❌ La hoja '{worksheet_name}' no existe en el spreadsheet")
            # Intentar crear la hoja
            try:
                worksheet = self.spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
                st.success(f"✅ Hoja '{worksheet_name}' creada exitosamente")
                return worksheet
            except Exception as create_error:
                st.error(f"❌ Error creando hoja: {str(create_error)}")
                return None
        except Exception as e:
            st.error(f"❌ Error accediendo a la hoja {worksheet_name}: {str(e)}")
            return None
    
    def save_data(self, worksheet_type, data):
        """Guardar datos en la hoja correspondiente con verificación robusta"""
        try:
            # Verificar/reconectar antes de guardar
            if not self._reconnect_if_needed():
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
            
            # Verificar que la conexión existe
            if self.spreadsheet is None:
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
            
            # Verificar que el tipo de hoja existe
            if worksheet_type not in self.worksheets:
                st.error(f"Tipo de hoja '{worksheet_type}' no encontrado.")
                return False
            
            # Obtener la hoja de trabajo
            worksheet = self.get_worksheet(worksheet_type)
            if worksheet is None:
                return False
            
            # Convertir datos a lista si es necesario
            if isinstance(data, dict):
                data_to_save = [list(data.values())]
            elif isinstance(data, pd.DataFrame):
                data_to_save = data.values.tolist()
            else:
                data_to_save = data
            
            # Agregar al final de la hoja
            if len(data_to_save) == 1:
                worksheet.append_row(data_to_save[0])
                st.success("✅ Datos guardados exitosamente")
            else:
                # Para múltiples filas
                for row in data_to_save:
                    worksheet.append_row(row)
                st.success(f"✅ {len(data_to_save)} filas guardadas exitosamente")
                
            return True
        
        except gspread.exceptions.APIError as e:
            if "PERMISSION_DENIED" in str(e):
                st.error("❌ Error de permisos. Verifica que la cuenta de servicio tenga acceso al spreadsheet.")
            else:
                st.error(f"❌ Error de API de Google: {str(e)}")
            return False
        except Exception as e:
            st.error(f"❌ Error al guardar datos: {str(e)}")
            return False
    
    def load_data(self, worksheet_type):
      """Cargar datos de una hoja específica"""
      for intento in range(MAX_RETRIES):
        try:
          with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
            # Obtener la hoja de trabajo
            worksheet = self.get_worksheet(worksheet_type)
            if worksheet is None:
                return False
                       
            #worksheet = self.spreadsheet.worksheet(self.worksheets[worksheet_type])
            data = worksheet.get_all_records()
            return pd.DataFrame(data)

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

        except Exception as e:
            st.error(f"Error al cargar datos: {str(e)}")
            return pd.DataFrame()

    def delete_data(self, worksheet_type, record_id):
      """Eliminar un registro específico por ID de Google Sheets"""
      for intento in range(MAX_RETRIES):
        try:
          with st.spinner(f'Eliminando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
            # Verificar/reconectar antes de eliminar
            if not self._reconnect_if_needed():
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
        
            # Verificar que la conexión existe
            if self.spreadsheet is None:
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
        
            # Verificar que el tipo de hoja existe
            if worksheet_type not in self.worksheets:
                st.error(f"Tipo de hoja '{worksheet_type}' no encontrado.")
                return False
        
            # Obtener la hoja de trabajo
            worksheet = self.get_worksheet(worksheet_type)
            if worksheet is None:
                return False
        
            # Obtener todos los datos de la hoja
            all_records = worksheet.get_all_records()
        
            # Buscar el registro a eliminar
            row_to_delete = None
            for idx, record in enumerate(all_records):
                if record.get('ID') == record_id:
                    row_to_delete = idx + 2  # +2 porque las filas empiezan en 1 y hay header
                    break
        
            # Verificar si se encontró el registro
            if row_to_delete is None:
                st.warning(f"No se encontró el registro con ID: {record_id}")
                return False
        
            # Eliminar la fila
            worksheet.delete_rows(row_to_delete)
            st.success(f"✅ Registro con ID {record_id} eliminado exitosamente")
        
            return True
        
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

        except gspread.exceptions.APIError as e:
            if "PERMISSION_DENIED" in str(e):
                st.error("❌ Error de permisos. Verifica que la cuenta de servicio tenga acceso al spreadsheet.")
            else:
                st.error(f"❌ Error de API de Google: {str(e)}")
            return False
        except Exception as e:
            st.error(f"❌ Error al eliminar datos de {worksheet_type}: {str(e)}")
            return False

    def delete_multiple_data(self, worksheet_type, record_ids):
      """Eliminar múltiples registros por lista de IDs de Google Sheets"""
      for intento in range(MAX_RETRIES):
        try:
          with st.spinner(f'Eliminando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
            # Verificar/reconectar antes de eliminar
            if not self._reconnect_if_needed():
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return 0
        
            # Verificar que la conexión existe
            if self.spreadsheet is None:
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return 0
        
            # Verificar que el tipo de hoja existe
            if worksheet_type not in self.worksheets:
                st.error(f"Tipo de hoja '{worksheet_type}' no encontrado.")
                return 0
        
            # Obtener la hoja de trabajo
            worksheet = self.get_worksheet(worksheet_type)
            if worksheet is None:
                return 0
        
            # Obtener todos los datos de la hoja
            all_records = worksheet.get_all_records()
        
            # Buscar las filas a eliminar (en orden inverso para mantener índices)
            rows_to_delete = []
            for idx, record in enumerate(all_records):
                if record.get('ID') in record_ids:
                    rows_to_delete.append(idx + 2)  # +2 porque las filas empiezan en 1 y hay header
        
            # Verificar si se encontraron registros
            if not rows_to_delete:
                st.warning("No se encontraron registros con los IDs proporcionados")
                return 0
        
            # Eliminar filas en orden inverso para mantener índices correctos
            rows_to_delete.sort(reverse=True)
            deleted_count = 0
        
            for row_num in rows_to_delete:
                try:
                    worksheet.delete_rows(row_num)
                    deleted_count += 1
                except Exception as e:
                    st.warning(f"Error al eliminar fila {row_num}: {str(e)}")
                    continue
        
            if deleted_count > 0:
                st.success(f"✅ {deleted_count} registros eliminados exitosamente")
            else:
                st.error("❌ No se pudieron eliminar los registros")
        
            return deleted_count
        
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

        except gspread.exceptions.APIError as e:
            if "PERMISSION_DENIED" in str(e):
                st.error("❌ Error de permisos. Verifica que la cuenta de servicio tenga acceso al spreadsheet.")
            else:
                st.error(f"❌ Error de API de Google: {str(e)}")
            return 0
        except Exception as e:
            st.error(f"❌ Error al eliminar múltiples datos de {worksheet_type}: {str(e)}")
            return 0

    def delete_all_data(self, worksheet_type):
        """Eliminar todos los datos de una hoja (mantiene los headers)"""
        try:
            # Verificar/reconectar antes de eliminar
            if not self._reconnect_if_needed():
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
        
            # Verificar que la conexión existe
            if self.spreadsheet is None:
                st.error("No hay conexión con Google Sheets. Verifica la configuración.")
                return False
        
            # Verificar que el tipo de hoja existe
            if worksheet_type not in self.worksheets:
                st.error(f"Tipo de hoja '{worksheet_type}' no encontrado.")
                return False
        
            # Obtener la hoja de trabajo
            worksheet = self.get_worksheet(worksheet_type)
            if worksheet is None:
                return False
        
            # Obtener el número total de filas
            total_rows = len(worksheet.get_all_values())
        
            # Verificar si hay datos para eliminar (más de 1 fila = header + datos)
            if total_rows <= 1:
                st.info("No hay datos para eliminar en esta hoja")
                return True
        
            # Eliminar todas las filas excepto la primera (header)
            if total_rows > 1:
                worksheet.delete_rows(2, total_rows)
                st.success(f"✅ Todos los datos eliminados exitosamente de {worksheet_type}")
        
            return True
        
        except gspread.exceptions.APIError as e:
            if "PERMISSION_DENIED" in str(e):
                st.error("❌ Error de permisos. Verifica que la cuenta de servicio tenga acceso al spreadsheet.")
            else:
                st.error(f"❌ Error de API de Google: {str(e)}")
            return False
        except Exception as e:
            st.error(f"❌ Error al eliminar todos los datos de {worksheet_type}: {str(e)}")
            return False

    def backup_data(self, backup_folder="backups"):
        """Crear respaldo de todos los datos"""
        try:
            if not os.path.exists(backup_folder):
                os.makedirs(backup_folder)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_folder, f"backup_{timestamp}")
            os.makedirs(backup_path)
            
            # Copiar todos los archivos de datos
            import shutil
            for module, file_path in self.files.items():
                if os.path.exists(file_path):
                    backup_file = os.path.join(backup_path, f"{module}.json")
                    shutil.copy2(file_path, backup_file)
            
            return backup_path
        except Exception as e:
            print(f"Error al crear respaldo: {e}")
            return None
    
    def restore_data(self, backup_path):
        """Restaurar datos desde un respaldo"""
        try:
            if not os.path.exists(backup_path):
                return False
            
            # Restaurar archivos desde el respaldo
            for module in self.files.keys():
                backup_file = os.path.join(backup_path, f"{module}.json")
                if os.path.exists(backup_file):
                    import shutil
                    shutil.copy2(backup_file, self.files[module])
            
            return True
        except Exception as e:
            print(f"Error al restaurar respaldo: {e}")
            return False

# Inicializar el sistema
#if 'manager' not in st.session_state:
#    st.session_state.manager = CondominiumManager()
#    st.session_state.authenticated = False
#    st.session_state.user_role = None

def condominio_main():

    initialize_session_state()

    st.markdown('<h1 class="main-header">🏢 Sistema de Administración de Condominios</h1>', unsafe_allow_html=True)

    # Verificar autenticación
    if not st.session_state.authenticated:
        show_login_page()
    else:
        show_main_application()

def show_login_page():
    """Mostrar página de autenticación"""
    #st.markdown("### 🔐 Configuración de Acceso")
       
    # Intentar cargar credenciales automáticamente
    st.subheader("🔄 Verificando Configuración")
    
    with st.spinner("Cargando credenciales..."):
        creds, config = load_credentials_from_toml()
        
        if creds and config:
            st.success("✅ Credenciales cargadas correctamente desde secrets.toml")
            
            # Intentar conectar con Google Sheets
            with st.spinner("Conectando con Google Sheets..."):
                client = get_google_sheets_connection(creds)
                
                if client:
                    # Configurar el manager con las credenciales
                    st.session_state.manager.client = client
                    st.session_state.authenticated = True
                    st.session_state.user_role = "admin"  # Por defecto admin
                    #st.success("✅ Conectado exitosamente con Google Drive y Sheets")
                    st.rerun()
                else:
                    st.error("❌ Error al conectar con Google Sheets")
        else:
            st.error("❌ No se pudieron cargar las credenciales")
            st.info("💡 Asegúrate de que el archivo `.streamlit/secrets.toml` esté configurado correctamente")
    
    # Botón para reintentar la conexión
    if st.button("🔄 Reintentar Conexión", type="primary"):
        st.rerun()

def show_main_application():
    """Mostrar la aplicación principal"""
    
    # Sidebar para navegación
    with st.sidebar:
        st.markdown("### 🏢 Navegación")
        
        modules = {
            #"📊 Panel": "dashboard",
            "👥 Control de Residentes": "residentes",
            "💰 Administración Financiera": "financiero",
            "🔧 Gestión de Mantenimiento": "mantenimiento",
            "📢 Comunicación": "comunicacion",
            "🚪 Control de Accesos": "accesos",
            "🏊 Áreas Comunes": "areas_comunes",
            "🏡 Ventas de Lotes": "ventas"
        }

        #selected_module = st.radio(
        #    "Seleccionar Módulo:",
        #    list(modules.keys()),
        #    horizontal=False  # Para mostrarlos horizontalmente si prefieres
        #)
        #current_module = modules[selected_module]
        
        selected_module = st.selectbox("Seleccionar Módulo:", list(modules.keys()))
        current_module = modules[selected_module]
        
        st.markdown("---")
        if st.button("🔓 Cerrar Sesión"):
            st.session_state.authenticated = False
            st.rerun()
    
    # Mostrar módulo seleccionado
    if current_module == "Panel de Seleccion ":
        show_dashboard()
    elif current_module == "residentes":
        show_residents_module()
    elif current_module == "financiero":
        show_financial_module()
    elif current_module == "mantenimiento":
        show_maintenance_module()
    elif current_module == "comunicacion":
        show_communication_module()
    elif current_module == "accesos":
        show_access_module()
    elif current_module == "areas_comunes":
        show_common_areas_module()
    elif current_module == "ventas":
        show_sales_module()

def load_data_safely(sheet_name):
    """Función auxiliar para cargar datos de forma segura con mejor diagnóstico"""
    try:
        if not hasattr(st.session_state, 'manager'):
            raise ValueError("Manager no encontrado en session_state")
        
        if st.session_state.manager is None:
            raise ValueError("Manager es None")
        
        manager = st.session_state.manager
        
        if not hasattr(manager, 'load_data'):
            raise ValueError("Manager no tiene método load_data")
        
        # Intentar cargar los datos
        #data = manager.load_data(sheet_name)
        #if hasattr(st.session_state, 'spreadsheet'):
        try:
                #worksheet = st.session_state.spreadsheet.worksheet(sheet_name)
                #data = worksheet.get_all_records()
                data = manager.load_data(sheet_name)
                return pd.DataFrame(data)
            
                if data is None:
                    st.warning(f"⚠️ {sheet_name} devolvió None - puede que la hoja no exista")
                    return pd.DataFrame()
        
                if isinstance(data, pd.DataFrame):
                    return data
                else:
                    st.warning(f"⚠️ {sheet_name} no devolvió un DataFrame válido")
                    return pd.DataFrame()
            
        except Exception as e:
                st.warning(f"⚠️ Error cargando {sheet_name}: {str(e)}")
                return pd.DataFrame()

    except AttributeError as e:
        if "'NoneType' object has no attribute 'worksheet'" in str(e):
            st.error(f"❌ Error de conexión con Google Sheets para {sheet_name}")
            st.info("💡 Verifica que las credenciales estén configuradas correctamente")
        else:
            st.error(f"❌ Error de atributo en {sheet_name}: {str(e)}")
        return pd.DataFrame()
        
    except Exception as e:
        st.warning(f"⚠️ Error inesperado cargando {sheet_name}: {str(e)}")
        return pd.DataFrame()


def load_all_data_safely():
    """Cargar todos los datos de forma segura"""
    data_sources = {
        'residentes': None,
        'financiero': None,
        'mantenimiento': None,
        'ventas': None
    }
    
    sheet_names = {
        'residentes': 'residentes',
        'financiero': 'financiero',
        'mantenimiento': 'mantenimiento',
        'ventas': 'ventas'
    }
    
    for key, sheet_name in sheet_names.items():
        try:
            data_sources[key] = load_data_safely(sheet_name)
        except Exception as e:
            st.warning(f"⚠️ Error cargando {sheet_name}: {str(e)}")
            data_sources[key] = pd.DataFrame()
    
    return data_sources

def show_dashboard():
    """Mostrar dashboard principal con manejo robusto de errores"""
    st.markdown("## 📊 Panel Principal")
    
    # Verificar/inicializar manager automáticamente
    if not initialize_manager_system():
        #show_initialization_interface()
        diagnose_system()
        return
    
    try:
        # Mostrar estado del sistema si hay advertencias
        #if system_status['warnings']:
        #    with st.expander("⚠️ Advertencias del Sistema", expanded=False):
        #        for warning in system_status['warnings']:
        #            st.warning(warning)
        
        # Cargar datos de forma segura
        data_sources = load_all_data_safely()
        
        # Mostrar métricas principales
        show_main_metrics(data_sources)
        
        # Mostrar gráficos
        show_charts(data_sources)
        
        # Mostrar actividad reciente
        show_recent_activity(data_sources)
        
        # Mostrar alertas
        show_alerts(data_sources)
        
    except Exception as e:
        handle_dashboard_error(e)


def diagnose_system():
    """Diagnosticar el estado del sistema"""
    status = {
        'is_ready': False,
        'warnings': [],
        'errors': []
    }
    
    # Verificar session_state
    if not hasattr(st.session_state, 'manager'):
        status['errors'].append("Manager no encontrado en session_state")
        return status
    
    # Verificar que el manager no sea None
    if st.session_state.manager is None:
        status['errors'].append("Manager es None - conexión no inicializada")
        return status
    
    # Verificar atributos del manager
    manager = st.session_state.manager
    
    # Verificar si tiene los métodos necesarios
    if not hasattr(manager, 'load_data'):
        status['errors'].append("Manager no tiene método 'load_data'")
        return status
    
    # Verificar conexión (si tiene método de verificación)
    if hasattr(manager, 'verify_connection'):
        try:
            if not manager.verify_connection():
                status['errors'].append("Conexión al servicio de datos falló")
                return status
        except Exception as e:
            status['warnings'].append(f"No se pudo verificar conexión: {str(e)}")
    
    # Verificar credenciales o configuración
    if hasattr(manager, 'client') and manager.client is None:
        status['errors'].append("Cliente de conexión no inicializado")
        return status
    
    # Si llegamos aquí, el sistema parece estar listo
    status['is_ready'] = True
    return status


def show_system_error(status):
    """Mostrar errores del sistema y opciones de recuperación"""
    st.error("❌ **Sistema no disponible**")
    
    # Mostrar errores específicos
    for error in status['errors']:
        st.error(f"• {error}")
    
    # Información de diagnóstico
    with st.expander("🔍 Información de Diagnóstico", expanded=False):
        st.write("**Estado de session_state:**")
        st.write(f"- Tiene 'manager': {hasattr(st.session_state, 'manager')}")
        
        if hasattr(st.session_state, 'manager'):
            st.write(f"- Manager es None: {st.session_state.manager is None}")
            
            if st.session_state.manager is not None:
                st.write(f"- Tipo de manager: {type(st.session_state.manager)}")
                st.write(f"- Tiene load_data: {hasattr(st.session_state.manager, 'load_data')}")
    
    # Opciones de recuperación
    st.markdown("### 🔧 Opciones de Recuperación")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Reinicializar Sistema", type="primary"):
            #reinitialize_system()
            initialize_manager_system()
    
    with col2:
        if st.button("🧹 Limpiar Session State"):
            clear_session_state()
    
    with col3:
        if st.button("📄 Recargar Página"):
            st.rerun()
    
    # Instrucciones para el usuario
    st.markdown("### 📋 Pasos para Solucionar")
    st.markdown("""
    1. **Reinicializar Sistema**: Intenta reconectar con los servicios de datos
    2. **Limpiar Session State**: Borra todos los datos en memoria y reinicia
    3. **Verificar Configuración**: Revisa que las credenciales estén correctas
    4. **Contactar Soporte**: Si el problema persiste
    """)

def initialize_manager_system():
    """Inicializar o recuperar el sistema de manager usando tus funciones"""
    try:
        # Si ya existe y funciona, no hacer nada
        if is_manager_working():
            return True
        
        #st.info("🔄 Inicializando sistema de datos...")
        
        # Intentar crear/recuperar el manager
        success = create_or_recover_manager()
        
        if success:
            st.success("✅ Sistema inicializado correctamente")
            return True
        else:
            st.error("❌ No se pudo inicializar el sistema")
            return False
            
    except Exception as e:
        st.error(f"❌ Error en inicialización: {str(e)}")
        return False

def is_manager_working():
    """Verificar si el manager actual está funcionando"""
    try:
        # Verificar si existe el client en session_state
        if not hasattr(st.session_state, 'client') or st.session_state.client is None:
            return False
        
        # Verificar si existe la configuración
        if not hasattr(st.session_state, 'config') or st.session_state.config is None:
            return False
        
        # Intentar una operación simple para verificar conexión
        try:
            client = st.session_state.client
            # Test básico - intentar acceder a las propiedades del cliente
            if hasattr(client, 'list_permissions'):
                pass  # Cliente de gspread funciona
            return True
        except Exception:
            return False
        
    except Exception:
        return False

def create_or_recover_manager():
    """Crear o recuperar el manager usando tus funciones específicas"""
    
    # Intentar inicialización con tus funciones
    success = try_initialize_with_your_functions()
    if success:
        return True
    
    # Si falla, intentar modo offline/demo
    #return initialize_offline_manager()

def try_initialize_with_your_functions():
    """Usar tus funciones específicas de inicialización"""
    try:
        #st.info("🔄 Cargando credenciales desde secrets.toml...")
        
        # Cargar credenciales usando tu función
        creds, config = load_credentials_from_toml()
        
        if creds is None or config is None:
            st.error("❌ No se pudieron cargar las credenciales")
            return False
        
        #st.info("🔄 Estableciendo conexión con Google Sheets...")
        
        # Crear conexión usando tu función
        client = get_google_sheets_connection(creds)
        
        if client is None:
            st.error("❌ No se pudo establecer conexión con Google Sheets")
            return False
        
        # Guardar en session_state
        st.session_state.client = client
        st.session_state.config = config
        st.session_state.credentials = creds
        
        # Verificar que podemos acceder a las hojas específicas
        if verify_sheets_access(client, config):
            st.success("✅ Sistema inicializado con tus funciones personalizadas")
            return True
        else:
            st.warning("⚠️ Conexión establecida pero con acceso limitado")
            return True  # Permitir continuar aunque sea con acceso limitado
            
    except Exception as e:
        st.error(f"❌ Error en inicialización personalizada: {str(e)}")
        return False

def verify_sheets_access(client, config):
    """Verificar acceso a las hojas específicas"""
    try:
        # Intentar acceder a la hoja principal si está configurada
        if 'sheetsemp' in config and 'spreadsheet_url' in config['sheetsemp']:
            spreadsheet_url = config['sheetsemp']['spreadsheet_url']
            spreadsheet = client.open_by_url(spreadsheet_url)
            
            # Intentar acceder a hojas comunes
            common_sheets = ['Control_Residentes', 'financiero', 'mantenimiento', 'ventas']
            accessible_sheets = []
            
            for sheet_name in common_sheets:
                try:
                    worksheet = spreadsheet.worksheet(sheet_name)
                    accessible_sheets.append(sheet_name)
                except:
                    pass
            
            if accessible_sheets:
                #st.info(f"📊 Hojas accesibles: {', '.join(accessible_sheets)}")
                st.session_state.spreadsheet = spreadsheet
                st.session_state.accessible_sheets = accessible_sheets
                return True
        
        return False
        
    except Exception as e:
        st.warning(f"⚠️ Error verificando acceso a hojas: {str(e)}")
        return False


def clear_session_state():
    """Limpiar session state"""
    try:
        # Mantener solo elementos esenciales
        keys_to_keep = []  # Agrega aquí las keys que quieras mantener
        
        keys_to_remove = [key for key in st.session_state.keys() if key not in keys_to_keep]
        
        for key in keys_to_remove:
            del st.session_state[key]
        
        st.success("✅ Session state limpiado. Recargando...")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error al limpiar session state: {str(e)}")


def show_main_metrics(data_sources):
    """Mostrar métricas principales"""
    st.markdown("### 📈 Métricas Principales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_residentes = len(data_sources['residentes']) if data_sources['residentes'] is not None else 0
        st.metric("👥 Total Residentes", total_residentes)
    
    with col2:
        ingresos = calculate_ingresos(data_sources['financiero'])
        st.metric("💰 Ingresos del Mes", f"${ingresos:,.2f}")
    
    with col3:
        pendientes = calculate_mantenimientos_pendientes(data_sources['mantenimiento'])
        st.metric("🔧 Mantenimientos Pendientes", pendientes)
    
    with col4:
        ventas_mes = calculate_ventas_mes(data_sources['ventas'])
        st.metric("🏡 Ventas del Mes", ventas_mes)


def calculate_ingresos(financiero_df):
    """Calcular ingresos de forma segura"""
    try:
        if (financiero_df is not None and 
            not financiero_df.empty and 
            'Monto' in financiero_df.columns and 
            'Tipo_Operacion' in financiero_df.columns):
            
            ingresos_df = financiero_df[financiero_df['Tipo_Operacion'] == 'Ingreso']
            return ingresos_df['Monto'].sum()
        return 0
    except Exception:
        return 0


def calculate_mantenimientos_pendientes(mantenimiento_df):
    """Calcular mantenimientos pendientes de forma segura"""
    try:
        if (mantenimiento_df is not None and 
            not mantenimiento_df.empty and 
            'Estado' in mantenimiento_df.columns):
            
            return len(mantenimiento_df[mantenimiento_df['Estado'] == 'Pendiente'])
        return 0
    except Exception:
        return 0


def calculate_ventas_mes(ventas_df):
    """Calcular ventas del mes de forma segura"""
    try:
        if (ventas_df is not None and 
            not ventas_df.empty and 
            'Estado' in ventas_df.columns):
            
            return len(ventas_df[ventas_df['Estado'] == 'Vendido'])
        return 0
    except Exception:
        return 0


def show_charts(data_sources):
    """Mostrar gráficos"""
    st.markdown("### 📊 Análisis Visual")
    
    col1, col2 = st.columns(2)
    
    with col1:
        show_financial_chart(data_sources['financiero'])
    
    with col2:
        show_maintenance_chart(data_sources['mantenimiento'])


def show_financial_chart(financiero_df):
    """Mostrar gráfico financiero"""
    st.subheader("📈 Ingresos vs Gastos")
    
    try:
        if (financiero_df is not None and 
            not financiero_df.empty and 
            'Tipo_Operacion' in financiero_df.columns and 
            'Monto' in financiero_df.columns):
            
            financial_summary = financiero_df.groupby('Tipo_Operacion')['Monto'].sum().reset_index()
            
            if not financial_summary.empty:
                fig = px.bar(financial_summary, x='Tipo_Operacion', y='Monto', 
                            title="Resumen Financiero",
                            color='Tipo_Operacion',
                            color_discrete_map={
                                'Ingreso': '#2E8B57',
                                'Gasto': '#DC143C'
                            })
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📝 No hay datos financieros para mostrar")
        else:
            st.info("📝 No hay datos financieros disponibles")
            
    except Exception as e:
        st.error(f"❌ Error creando gráfico financiero: {str(e)}")


def show_maintenance_chart(mantenimiento_df):
    """Mostrar gráfico de mantenimiento"""
    st.subheader("🔧 Estado del Mantenimiento")
    
    try:
        if (mantenimiento_df is not None and 
            not mantenimiento_df.empty and 
            'Estado' in mantenimiento_df.columns):
            
            maintenance_status = mantenimiento_df['Estado'].value_counts().reset_index()
            maintenance_status.columns = ['Estado', 'Cantidad']
            
            if not maintenance_status.empty:
                fig = px.pie(maintenance_status, values='Cantidad', names='Estado', 
                            title="Estado de Mantenimientos",
                            color_discrete_map={
                                'Pendiente': '#FFA500',
                                'En Progreso': '#4169E1',
                                'Completado': '#32CD32',
                                'Cancelado': '#DC143C'
                            })
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📝 No hay datos de mantenimiento para mostrar")
        else:
            st.info("📝 No hay datos de mantenimiento disponibles")
            
    except Exception as e:
        st.error(f"❌ Error creando gráfico de mantenimiento: {str(e)}")


def show_recent_activity(data_sources):
    """Mostrar actividad reciente"""
    st.markdown("---")
    st.subheader("📋 Actividad Reciente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        show_recent_residents(data_sources['residentes'])
    
    with col2:
        show_recent_transactions(data_sources['financiero'])


def show_recent_residents(residentes_df):
    """Mostrar residentes recientes"""
    st.markdown("**🏠 Últimos Residentes Registrados**")
    
    try:
        if residentes_df is not None and not residentes_df.empty:
            required_cols = ['Unidad', 'Nombre_Propietario']
            available_cols = [col for col in required_cols if col in residentes_df.columns]
            
            if available_cols:
                recent_residents = residentes_df.tail(5)[available_cols].reset_index(drop=True)
                st.dataframe(recent_residents, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ Columnas requeridas no encontradas en datos de residentes")
        else:
            st.info("📝 No hay residentes registrados")
            
    except Exception as e:
        st.warning(f"⚠️ Error mostrando residentes recientes: {str(e)}")


def show_recent_transactions(financiero_df):
    """Mostrar transacciones recientes"""
    st.markdown("**💰 Últimas Transacciones**")
    
    try:
        if financiero_df is not None and not financiero_df.empty:
            required_cols = ['Fecha', 'Concepto', 'Monto', 'Tipo_Operacion']
            available_cols = [col for col in required_cols if col in financiero_df.columns]
            
            if len(available_cols) >= 3:  # Al menos 3 columnas importantes
                recent_transactions = financiero_df.tail(5)[available_cols].reset_index(drop=True)
                
                # Formatear monto si existe
                if 'Monto' in available_cols:
                    recent_transactions['Monto'] = recent_transactions['Monto'].apply(
                        lambda x: f"${x:,.2f}" if pd.notnull(x) else "N/A"
                    )
                
                st.dataframe(recent_transactions, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ Columnas requeridas no encontradas en datos financieros")
        else:
            st.info("📝 No hay transacciones registradas")
            
    except Exception as e:
        st.warning(f"⚠️ Error mostrando transacciones recientes: {str(e)}")


def show_alerts(data_sources):
    """Mostrar alertas y notificaciones"""
    st.markdown("---")
    st.subheader("🚨 Alertas y Notificaciones")
    
    alerts = []
    
    # Verificar mantenimientos vencidos
    try:
        mantenimiento_df = data_sources['mantenimiento']
        if (mantenimiento_df is not None and 
            not mantenimiento_df.empty and 
            'Fecha_Programada' in mantenimiento_df.columns and 
            'Estado' in mantenimiento_df.columns):
            
            today = date.today()
            mantenimiento_df['Fecha_Programada'] = pd.to_datetime(
                mantenimiento_df['Fecha_Programada'], errors='coerce'
            ).dt.date
            
            vencidos = mantenimiento_df[
                (mantenimiento_df['Fecha_Programada'] < today) & 
                (mantenimiento_df['Estado'] == 'Pendiente')
            ]
            
            if len(vencidos) > 0:
                alerts.append(f"🔧 {len(vencidos)} mantenimiento(s) vencido(s)")
    except Exception:
        pass
    
    # Verificar pagos pendientes
    try:
        financiero_df = data_sources['financiero']
        if (financiero_df is not None and 
            not financiero_df.empty and 
            'Estado' in financiero_df.columns):
            
            pendientes_pago = len(financiero_df[financiero_df['Estado'] == 'Pendiente'])
            if pendientes_pago > 0:
                alerts.append(f"💰 {pendientes_pago} pago(s) pendiente(s)")
    except Exception:
        pass
    
    # Mostrar alertas
    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("✅ No hay alertas pendientes")


def handle_dashboard_error(error):
    """Manejar errores generales del dashboard"""
    st.error(f"❌ Error general en el dashboard: {str(error)}")
    
    with st.expander("🔍 Detalles Técnicos", expanded=False):
        st.write("**Tipo de error:**", type(error).__name__)
        st.write("**Mensaje:**", str(error))
#        st.write("**Traceback:**")
#        st.code(traceback.format_exc())
    
    if st.button("🔄 Recargar Dashboard"):
        st.rerun()

# Función para enviar correo electrónico
def send_email_to_resident(email_to, nombre, asunto, mensaje, tipo_mensaje, email_from="laceibacondominio@gmail.com", nombre_from="laceibacondominio@gmail.com"):
    
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
            
        smtp_user = st.secrets['emails']['smtp_user']  # Para autenticación
        smtp_password = st.secrets['emails']['smtp_password']
        
        # Determinar el remitente que aparecerá en el correo
        if email_from:
            if nombre_from:
                display_from = f"{nombre_from} <{email_from}>"
            else:
                display_from = email_from
        else:
            # Si no se especifica, usar el email de autenticación
            display_from = smtp_user
        
        # Crear mensaje
        message = MIMEMultipart()
        message['From'] = display_from  # Este será el remitente que ve el destinatario
        message['To'] = email_to
        message['Subject'] = asunto
        
        # Opcionalmente agregar Reply-To para que las respuestas vayan al remitente personalizado
        if email_from and nombre_from != smtp_user:
            message['Reply-To'] = email_from
        
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
        
        # Inicio de sesión (siempre con las credenciales del secrets)
        server.login(smtp_user, smtp_password)
        
        # Enviar correo (el envelope sender sigue siendo smtp_user para autenticación)
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

def get_resident_emails(destinatario, unidad_especifica=None):
    """
    Obtiene los correos electrónicos según el tipo de destinatario
    """
    residentes_df = st.session_state.manager.load_data('residentes')
    
    if residentes_df.empty:
        return []
    
    emails_info = []
    
    if destinatario == "Todos los Residentes":
        for _, residente in residentes_df.iterrows():
            if pd.notna(residente.get('Email', '')):
                emails_info.append({
                    'email': residente['Email'],
                    'nombre': residente['Nombre'],
                    'unidad': residente['Unidad']
                })
    
    elif destinatario == "Propietarios":
        propietarios = residentes_df[residentes_df['Tipo'] == 'Propietario']
        for _, residente in propietarios.iterrows():
            if pd.notna(residente.get('Email', '')):
                emails_info.append({
                    'email': residente['Email'],
                    'nombre': residente['Nombre'],
                    'unidad': residente['Unidad']
                })
    
    elif destinatario == "Inquilinos":
        inquilinos = residentes_df[residentes_df['Tipo'] == 'Inquilino']
        for _, residente in inquilinos.iterrows():
            if pd.notna(residente.get('Email', '')):
                emails_info.append({
                    'email': residente['Email'],
                    'nombre': residente['Nombre'],
                    'unidad': residente['Unidad']
                })
    
    elif destinatario == "Específico" and unidad_especifica:
        residente_especifico = residentes_df[residentes_df['Unidad'] == unidad_especifica]
        for _, residente in residente_especifico.iterrows():
            if pd.notna(residente.get('Email', '')):
                emails_info.append({
                    'email': residente['Email'],
                    'nombre': residente['Nombre'],
                    'unidad': residente['Unidad']
                })
    
    return emails_info

def update_message_status(message_id, new_status, response_info=""):
    """
    Actualiza el estado de un mensaje en la base de datos
    """
    try:
        # Cargar datos actuales
        comunicacion_df = st.session_state.manager.load_data('comunicacion')
        
        if comunicacion_df.empty:
            return False
            
        # Buscar el mensaje por ID
        mask = comunicacion_df['ID'] == message_id
        
        if not mask.any():
            return False
            
        # Actualizar los campos
        comunicacion_df.loc[mask, 'Estado'] = new_status
        if response_info:
            comunicacion_df.loc[mask, 'Respuesta'] = response_info
            
        # Guardar los datos actualizados
        if hasattr(st.session_state.manager, 'data'):
            st.session_state.manager.data['comunicacion'] = comunicacion_df
        else:
            # Si no tiene atributo data, intentar guardar de otra manera
            # Esto dependerá de cómo esté implementado tu manager
            pass
            
        return True
        
    except Exception as e:
        st.error(f"Error al actualizar estado del mensaje: {str(e)}")
        return False
    """
    Envía correos masivos y retorna el resultado
    """
    total_emails = len(emails_info)
    successful_sends = 0
    failed_sends = 0
    error_details = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, email_info in enumerate(emails_info):
        status_text.text(f"Enviando correo {i+1} de {total_emails} a {email_info['nombre']}...")
        
        success, message_result = send_email_to_resident(
            email_info['email'],
            email_info['nombre'],
            asunto,
            mensaje,
            tipo_mensaje,
            "laceibacondominio@gmail.com",
            "laceibacondominio@gmail.com"
        )
        
        if success:
            successful_sends += 1
        else:
            failed_sends += 1
            error_details.append(f"Error en {email_info['nombre']} ({email_info['email']}): {message_result}")
        
        progress_bar.progress((i + 1) / total_emails)
    
    progress_bar.empty()
    status_text.empty()
    
    return successful_sends, failed_sends, error_details

def send_bulk_emails(emails_info, asunto, mensaje, tipo_mensaje):
    """
    Envía correos masivos y retorna el resultado
    """
    total_emails = len(emails_info)
    successful_sends = 0
    failed_sends = 0
    error_details = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, email_info in enumerate(emails_info):
        status_text.text(f"Enviando correo {i+1} de {total_emails} a {email_info['nombre']}...")
        
        success, message_result = send_email_to_resident(
            email_info['email'],
            email_info['nombre'],
            asunto,
            mensaje,
            tipo_mensaje,
            "laceibacondominio@gmail.com",
            "laceibacondominio@gmail.com"
        )
        
        if success:
            successful_sends += 1
        else:
            failed_sends += 1
            error_details.append(f"Error en {email_info['nombre']} ({email_info['email']}): {message_result}")
        
        progress_bar.progress((i + 1) / total_emails)
    
    progress_bar.empty()
    status_text.empty()
    
    return successful_sends, failed_sends, error_details


def show_residents_module():
    """Módulo de control de residentes"""
    st.markdown("## 👥 Control de Residentes y Propietarios")
    
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Agregar Residente", "📋 Lista de Residentes", "✏️ Modificar/Eliminar", "📊 Estadísticas"])
    
    with tab1:
      with st.form("add_resident"):
        st.subheader("Registrar Nuevo Residente")
        
        col1, col2 = st.columns(2)
        with col1:
            identificacion = st.text_input('Identificacion *')
            nombre = st.text_input("Nombre *")
            apellido = st.text_input("Apellido *")
            tipo_unidad = st.selectbox("Tipo Unidad ", ["Casa", "Apto", "Lote","Otro"])
            unidad = st.text_input("Unidad (Ej: Apto 101, Casa 15) *")
            
        with col2:
            tipo = st.selectbox("Tipo", ["Propietario", "Inquilino", "Familiar"])
            telefono = st.text_input("Teléfono")
            email = st.text_input("Email")
            fecha_ingreso = st.date_input("Fecha de Ingreso", datetime.now().date())
            estado = st.selectbox("Estado", ["Activo", "Inactivo", "Temporal"])
        
        observaciones = st.text_area("Observaciones")
        
        if st.form_submit_button("✅ Registrar Residente"):
            if nombre and apellido and unidad and identificacion:
                # Función para validar duplicados
                def validar_duplicados():
                    try:
                        # Obtener datos existentes
                        existing_data = st.session_state.manager.load_data('residentes')
                        
                        # Verificar si hay datos existentes
                        if existing_data is None:
                            return True, ""
                        
                        # Si es una lista vacía
                        if isinstance(existing_data, list) and len(existing_data) == 0:
                            return True, ""
                        
                        # Si ya es un DataFrame y está vacío
                        if isinstance(existing_data, pd.DataFrame) and existing_data.empty:
                            return True, ""
                        
                        # Convertir a DataFrame si es necesario
                        if isinstance(existing_data, list):
                            df = pd.DataFrame(existing_data)
                        else:
                            df = existing_data
                        
                        # Verificar que el DataFrame no esté vacío
                        if df.empty:
                            return True, ""
                            
                    except Exception as e:
                        # Si hay algún error, permitir el registro y mostrar advertencia
                        st.warning(f"No se pudieron validar duplicados: {str(e)}")
                        return True, ""
                    
                    # Normalizar datos para comparación (sin espacios extra, minúsculas)
                    identificacion_norm = identificacion.strip()
                    nombre_norm = nombre.strip().lower()
                    apellido_norm = apellido.strip().lower()
                    unidad_norm = unidad.strip().lower()
                    
                    # Validar duplicado por identificación
                    #if 'Identificacion' in df.columns:
                        # Convertir a string y manejar valores nulos
                    #    df_id_clean = df['Identificacion'].astype(str).str.strip()
                    #    duplicado_id = df[df_id_clean == identificacion_norm]
                    #    if not duplicado_id.empty:
                    #        return False, f"❌ Ya existe un residente registrado con la identificación: {identificacion}"
                    
                    # Validar duplicado por nombre completo y unidad
                    if all(col in df.columns for col in ['Identificacion', 'Nombre', 'Apellido', 'Unidad']):
                        # Convertir a string y manejar valores nulos
                        df_id_clean = df['Identificacion'].astype(str).str.strip()
                        df_nombre_clean = df['Nombre'].astype(str).str.strip().str.lower()
                        df_apellido_clean = df['Apellido'].astype(str).str.strip().str.lower()
                        df_unidad_clean = df['Unidad'].astype(str).str.strip().str.lower()
                        
                        duplicado_nombre_unidad = df[
                            (df_id_clean == identificacion_norm) &
                            (df_nombre_clean == nombre_norm) & 
                            (df_apellido_clean == apellido_norm) & 
                            (df_unidad_clean == unidad_norm)
                        ]
                        if not duplicado_nombre_unidad.empty:
                            return False, f"❌ Ya existe un residente con esta informacion '{nombre} {apellido}' en la unidad '{unidad}'"
                    
                    # Validar múltiples propietarios en la misma unidad (opcional)
                    if tipo == "Propietario" and all(col in df.columns for col in ['Tipo', 'Unidad', 'Estado']):
                        # Convertir a string y manejar valores nulos
                        df_unidad_prop = df['Unidad'].astype(str).str.strip().str.lower()
                        df_tipo = df['Tipo'].astype(str)
                        df_estado = df['Estado'].astype(str)
                        
                        propietario_existente = df[
                            (df_unidad_prop == unidad_norm) & 
                            (df_tipo == "Propietario") &
                            (df_estado == "Activo")  # Solo considerar activos
                        ]
                        if not propietario_existente.empty:
                            # Mostrar advertencia pero permitir registro (puede haber co-propietarios)
                            st.warning(f"⚠️ Ya existe un propietario activo en la unidad '{unidad}'. Verifique si desea registrar un co-propietario.")
                    
                    return True, ""
                
                # Ejecutar validaciones
                es_valido, mensaje_error = validar_duplicados()
                
                if es_valido:
                    # Generar ID único
                    resident_id = f"RES{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': resident_id,
                        'Identificacion': identificacion.strip(),
                        'Nombre': nombre.strip(),
                        'Apellido': apellido.strip(),
                        'Tipo_Unidad': tipo_unidad,
                        'Unidad': unidad.strip(),
                        'Tipo': tipo,
                        'Telefono': telefono.strip() if telefono else "",
                        'Email': email.strip().lower() if email else "",
                        'Fecha_Ingreso': fecha_ingreso.strftime('%Y-%m-%d'),
                        'Estado': estado,
                        'Metodo_Pago':'',
                        'Soporte_Pago':'',
                        'Ruta_Archivo':'',
                        'Numero_Recibo':'',
                        'Ruta_Recibo':'',
                        'Observaciones': observaciones.strip() if observaciones else "",
                        'Saldo_Pendiente': 0,
                        'Registrado': ''
                        
                    }
                    
                    if st.session_state.manager.save_data('residentes', data):
                        st.success("✅ Residente registrado exitosamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar residente")
                else:
                    st.error(mensaje_error)
            else:
                st.error("⚠️ Por favor, completa todos los campos obligatorios (*)")
    
    with tab2:
        st.subheader("📋 Lista de Residentes")
        residentes_df = st.session_state.manager.load_data('residentes')
        
        if not residentes_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_tipo = st.selectbox("Filtrar por Tipo:", 
                                         ["Todos"] + list(residentes_df['Tipo'].unique()))
            with col2:
                filter_estado = st.selectbox("Filtrar por Estado:", 
                                           ["Todos"] + list(residentes_df['Estado'].unique()))
            with col3:
                search_term = st.text_input("Buscar por nombre o unidad:")
            
            # Aplicar filtros
            filtered_df = residentes_df.copy()
            if filter_tipo != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo'] == filter_tipo]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            if search_term:
                filtered_df = filtered_df[
                    filtered_df['Nombre'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Apellido'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Unidad'].str.contains(search_term, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Opción de descarga
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"residentes_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("📝 No hay residentes registrados aún")
    
    with tab3:
        st.subheader("✏️ Modificar/Eliminar Residentes")
        residentes_df = st.session_state.manager.load_data('residentes')
        
        if not residentes_df.empty:
            # Selector de residente
            resident_options = []
            for _, row in residentes_df.iterrows():
                resident_options.append(f"{row['Nombre']} {row['Apellido']} - {row['Unidad']} (ID: {row['ID']})")
            
            selected_resident = st.selectbox("Seleccionar Residente:", resident_options)
            
            if selected_resident:
                # Extraer ID del residente seleccionado
                selected_id = selected_resident.split("(ID: ")[1].replace(")", "")
                resident_data = residentes_df[residentes_df['ID'] == selected_id].iloc[0]
                
                # Mostrar información actual
                st.info(f"📋 Residente seleccionado: {resident_data['Nombre']} {resident_data['Apellido']}")
                
                # Opciones de acción
                action = st.radio("Seleccionar acción:", ["Modificar", "Eliminar"])
                
                if action == "Modificar":
                    st.markdown("### ✏️ Modificar Información")
                    
                    with st.form("modify_resident"):
                        col1, col2 = st.columns(2)
                        with col1:
                            identificacion = st.text_input('Identificacion *', value=resident_data['Identificacion'])
                            nombre = st.text_input("Nombre *", value=resident_data['Nombre'])
                            apellido = st.text_input("Apellido *", value=resident_data['Apellido'])
                            tipo_unidad = st.selectbox("Tipo Unidad", ["Casa", "Apto", "Lote","Otro"], 
                                                     index=["Casa", "Apto", "Lote","Otro"].index(resident_data['Tipo_Unidad']))
                            unidad = st.text_input("Unidad (Ej: Apto 101, Casa 15) *", value=resident_data['Unidad'])
                            
                        with col2:
                            tipo = st.selectbox("Tipo", ["Propietario", "Inquilino", "Familiar"],
                                              index=["Propietario", "Inquilino", "Familiar"].index(resident_data['Tipo']))
                            telefono = st.text_input("Teléfono", value=resident_data['Telefono'] if pd.notna(resident_data['Telefono']) else "")
                            email = st.text_input("Email", value=resident_data['Email'] if pd.notna(resident_data['Email']) else "")
                            fecha_ingreso = st.date_input("Fecha de Ingreso", 
                                                        value=datetime.strptime(resident_data['Fecha_Ingreso'], '%Y-%m-%d').date())
                            estado = st.selectbox("Estado", ["Activo", "Inactivo", "Temporal"],
                                                index=["Activo", "Inactivo", "Temporal"].index(resident_data['Estado']))
                        
                        observaciones = st.text_area("Observaciones", 
                                                   value=resident_data['Observaciones'] if pd.notna(resident_data['Observaciones']) else "")
                        
                        if st.form_submit_button("💾 Guardar Cambios"):
                            if nombre and apellido and unidad:
                                updated_data = {
                                    'ID': selected_id,
                                    'Identificacion': identificacion,
                                    'Nombre': nombre,
                                    'Apellido': apellido,
                                    'Tipo_Unidad': tipo_unidad,
                                    'Unidad': unidad,
                                    'Tipo': tipo,
                                    'Telefono': telefono,
                                    'Email': email,
                                    'Fecha_Ingreso': fecha_ingreso.strftime('%Y-%m-%d'),
                                    'Estado': estado,
                                    
                                    'Observaciones': observaciones
                                }
                                
                                if st.session_state.manager.update_data('residentes', 'ID', selected_id, updated_data):
                                    st.success("✅ Residente modificado exitosamente")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al modificar residente")
                            else:
                                st.error("⚠️ Por favor, completa los campos obligatorios (*)")
                
                elif action == "Eliminar":
                    st.markdown("### 🗑️ Eliminar Residente")
                    st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar a **{resident_data['Nombre']} {resident_data['Apellido']}**?")
                    st.write("Esta acción no se puede deshacer.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Confirmar Eliminación", type="primary"):
                            if st.session_state.manager.delete_data('residentes', 'ID', selected_id):
                                st.success("✅ Residente eliminado exitosamente")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar residente")
                    
                    with col2:
                        if st.button("❌ Cancelar"):
                            st.info("Operación cancelada")
        else:
            st.info("📝 No hay residentes registrados para modificar o eliminar")
    
    with tab4:
        st.subheader("📊 Estadísticas de Residentes")
        residentes_df = st.session_state.manager.load_data('residentes')
        
        if not residentes_df.empty:
            # Métricas generales
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Residentes", len(residentes_df))
            with col2:
                activos = len(residentes_df[residentes_df['Estado'] == 'Activo'])
                st.metric("Activos", activos)
            with col3:
                propietarios = len(residentes_df[residentes_df['Tipo'] == 'Propietario'])
                st.metric("Propietarios", propietarios)
            with col4:
                inquilinos = len(residentes_df[residentes_df['Tipo'] == 'Inquilino'])
                st.metric("Inquilinos", inquilinos)
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico por tipo
                tipo_counts = residentes_df['Tipo'].value_counts()
                fig = px.pie(values=tipo_counts.values, names=tipo_counts.index, 
                           title="Distribución por Tipo")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Gráfico por estado
                estado_counts = residentes_df['Estado'].value_counts()
                fig = px.bar(x=estado_counts.index, y=estado_counts.values, 
                           title="Residentes por Estado")
                st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico por tipo de unidad
            if 'Tipo_Unidad' in residentes_df.columns:
                unidad_counts = residentes_df['Tipo_Unidad'].value_counts()
                fig = px.bar(x=unidad_counts.index, y=unidad_counts.values, 
                           title="Distribución por Tipo de Unidad")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📝 No hay datos para mostrar estadísticas")

def show_financial_module():
    """Módulo de administración financiera"""
    st.markdown("## 💰 Administración Financiera")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Proceso Actualizacion","➕ Nueva Operación", "📋 Historial", "📊 Reportes", "💳 Cuotas", "📋 Informe Estado Financiero"])

    with tab1:
        st.subheader("Actualizar Operación Financiera")
        control_main()
    
    with tab2:
        with st.form("add_financial_operation"):
            st.subheader("Registrar Operación Financiera")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                tipo_operacion = st.selectbox("Tipo de Operación", 
                                            ["Ingreso", "Gasto", "Cuota de Mantenimiento"])

                tipo_unidad = st.selectbox("Tipo de Unidad", 
                                            ["Casa", "Apto", "Lote", "Otro"])
                unidad = st.text_input("Unidad (si aplica)")               
                concepto = st.text_input("Concepto/Descripción *")
                
            with col2:
                monto = st.number_input("Monto *", min_value=0.0, format="%.2f")
                fecha = st.date_input("Fecha", datetime.now().date())
                estado = st.selectbox("Estado", ["Pendiente", "Pagado", "Vencido", "Cancelado"])
                metodo_pago = st.selectbox("Método de Pago", 
                                         ["Efectivo", "Transferencia", "Cheque", "Tarjeta"])
            
            observaciones = st.text_area("Observaciones")
            
            if st.form_submit_button("✅ Registrar Operación"):
                if concepto and monto > 0:
                    operation_id = f"FIN{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': operation_id,
                        'Tipo_Operacion': tipo_operacion,
                        'Unidad': unidad,
                        #'Tipo_Unidad': tipo_unidad,
                        'Concepto': concepto,
                        'Monto': monto,
                        'Fecha': fecha.strftime('%Y-%m-%d'),
                        'Banco': '',
                        'Estado': estado,
                        'Metodo_Pago': metodo_pago,
                        'Soporte_Pago':'',
                        'Ruta_Archivo':'',
                        'Numero_Recibo':'',
                        'Ruta_Recibo':'',
                        'Observaciones': observaciones,
                        'Saldo_Pendiente': 0,
                        'Registrado': ''
                    }
                    
                    if st.session_state.manager.save_data('financiero', data):
                        st.success("✅ Operación registrada exitosamente")
                    else:
                        st.error("❌ Error al registrar operación")
                else:
                    st.error("⚠️ Por favor, completa los campos obligatorios")
    
    with tab3:
        st.subheader("📋 Historial de Operaciones")
        financiero_df = st.session_state.manager.load_data('financiero')
        
        if not financiero_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_tipo = st.selectbox("Tipo:", 
                                         ["Todos"] + list(financiero_df['Tipo_Operacion'].unique()))
            with col2:
                filter_estado = st.selectbox("Estado:", 
                                           ["Todos"] + list(financiero_df['Estado'].unique()))
            with col3:
                fecha_desde = st.date_input("Desde:", datetime.now().date().replace(day=1))
            
            # Aplicar filtros
            filtered_df = financiero_df.copy()
            if filter_tipo != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo_Operacion'] == filter_tipo]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Resumen
            if 'Monto' in filtered_df.columns:
                ingresos = filtered_df[filtered_df['Tipo_Operacion'] == 'Ingreso']['Monto'].sum()
                gastos = filtered_df[filtered_df['Tipo_Operacion'] == 'Gasto']['Monto'].sum()
                cuotas = filtered_df[filtered_df['Tipo_Operacion'] == 'Cuota de Mantenimiento']['Monto'].sum()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("💚 Ingresos", f"${ingresos:,.2f}")
                with col2:
                    st.metric("🔴 Gastos", f"${gastos:,.2f}")
                with col3:
                    st.metric("🏢 Cuotas", f"${cuotas:,.2f}")
                with col4:
                    balance = ingresos - gastos
                    st.metric("⚖️ Balance", f"${balance:,.2f}")
        else:
            st.info("📝 No hay operaciones registradas aún")
    
    with tab4:
        st.subheader("📊 Reportes Financieros")
        financiero_df = st.session_state.manager.load_data('financiero')
        
        if not financiero_df.empty and 'Monto' in financiero_df.columns:
            # Gráfico de ingresos vs gastos por mes
            financiero_df['Fecha'] = pd.to_datetime(financiero_df['Fecha'])
            financiero_df['Mes'] = financiero_df['Fecha'].dt.strftime('%Y-%m')
            
            monthly_summary = financiero_df.groupby(['Mes', 'Tipo_Operacion'])['Monto'].sum().reset_index()
            
            fig = px.bar(monthly_summary, x='Mes', y='Monto', color='Tipo_Operacion',
                        title="Ingresos vs Gastos por Mes")
            st.plotly_chart(fig, use_container_width=True)
            
            # Estado de pagos
            estado_summary = financiero_df.groupby('Estado')['Monto'].sum().reset_index()
            fig2 = px.pie(estado_summary, values='Monto', names='Estado',
                         title="Distribución por Estado de Pago")
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab5:
        st.subheader("💳 Gestión de Cuotas")
    
        # Subtabs para diferentes tipos de cuotas
        subtab1, subtab2, subtab3 = st.tabs(["🏢 Cuotas de Mantenimiento", "⚡ Cuotas   Extraordinarias", "🗑️ Eliminar Cuotas"])
    
        # Obtener tipos de unidad únicos de los residentes
        residentes_df = st.session_state.manager.load_data('residentes')
        tipos_unidad = []
        if not residentes_df.empty and 'Tipo_Unidad' in residentes_df.columns:
            tipos_unidad = list(residentes_df['Tipo_Unidad'].unique())
    
        if not tipos_unidad:
            st.warning("⚠️ No se encontraron tipos de unidad. Asegúrate de que los residentes tengan el campo 'Tipo_Unidad' configurado.")
            return

        # Función para validar duplicados de cuotas de mantenimiento
        def validar_cuotas_mantenimiento_duplicadas(financiero_df, mes, año, unidades_activas):
            """
            Valida si ya existen cuotas de mantenimiento para el mes/año/unidades especificadas
            """
            if financiero_df.empty:
                return [], unidades_activas
        
            # Filtrar cuotas de mantenimiento existentes
            cuotas_existentes = financiero_df[
                (financiero_df['Tipo_Operacion'] == 'Cuota de Mantenimiento') &
                (financiero_df['Concepto'].str.contains(f"{mes} {año}", na=False, case=False))
            ]
        
            # Obtener unidades que ya tienen cuotas para este mes/año
            unidades_con_cuotas = set(cuotas_existentes['Unidad'].tolist()) if not cuotas_existentes.empty else set()
        
            # Filtrar unidades que no tienen cuotas
            unidades_sin_cuotas = [unidad for unidad in unidades_activas if unidad not in unidades_con_cuotas]
        
            return list(unidades_con_cuotas), unidades_sin_cuotas

        # Función para validar duplicados de cuotas extraordinarias
        def validar_cuotas_extraordinarias_duplicadas(financiero_df, concepto, fecha_vencimiento, unidades_activas):
            #Valida si ya existen cuotas extraordinarias para el concepto/fecha/unidades especificadas
            
            if financiero_df.empty:
                return [], unidades_activas
        
            # Convertir fecha a string para comparación
            fecha_str = fecha_vencimiento.strftime('%Y-%m-%d')
        
            # Filtrar cuotas extraordinarias existentes
            cuotas_existentes = financiero_df[
                   (financiero_df['Tipo_Operacion'] == 'Ingreso') &
                    (financiero_df['Concepto'].str.contains(concepto, na=False, case=False)) &
                    (financiero_df['Fecha'] == fecha_str)
            ]
        
            # Obtener unidades que ya tienen cuotas extraordinarias
            unidades_con_cuotas = set(cuotas_existentes['Unidad'].tolist()) if not cuotas_existentes.empty else set()
        
            # Filtrar unidades que no tienen cuotas
            unidades_sin_cuotas = [unidad for unidad in unidades_activas if unidad not in unidades_con_cuotas]
        
            return list(unidades_con_cuotas), unidades_sin_cuotas


        with subtab1:
          st.markdown("**🏢 Cuotas de Mantenimiento/Administración**")
    
          with st.form("generate_maintenance_fees"):
            st.markdown("**Generar Cuotas de Mantenimiento Masivas**")
        
            col1, col2 = st.columns(2)
            with col1:
                mes_cuota = st.selectbox("Mes", 
                                   ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
                año_cuota = st.number_input("Año", min_value=2020, max_value=2035, 
                                      value=datetime.now().year)
            with col2:
                fecha_vencimiento = st.date_input("Fecha de Vencimiento")
        
            st.markdown("**Configurar Montos por Tipo de Unidad:**")
        
            # Crear campos de entrada para cada tipo de unidad
            montos_por_tipo = {}
            cols = st.columns(min(len(tipos_unidad), 3))  # Máximo 3 columnas
        
            for i, tipo_unidad in enumerate(tipos_unidad):
                with cols[i % 3]:
                    monto = st.number_input(
                        f"💰 {tipo_unidad}", 
                        min_value=0.0, 
                        format="%.2f",
                        key=f"monto_mantenimiento_{tipo_unidad}",
                        help=f"Monto de cuota de mantenimiento para {tipo_unidad}"
                    )
                    montos_por_tipo[tipo_unidad] = monto
        
            # Obtener datos financieros existentes para validación
            financiero_df = st.session_state.manager.load_data('financiero')
            
            # Obtener unidades activas
            unidades_activas = []
            if not residentes_df.empty:
                unidades_activas = residentes_df[
                    (residentes_df['Estado'] == 'Activo') & 
                    (residentes_df['Tipo'] == 'Propietario')
                ]['Unidad'].tolist()
            
            # Validar duplicados
            unidades_con_cuotas, unidades_sin_cuotas = validar_cuotas_mantenimiento_duplicadas(
                financiero_df, mes_cuota, año_cuota, unidades_activas
            )
            
            # Mostrar advertencia si hay duplicados
            if unidades_con_cuotas:
                st.warning(f"⚠️ **Cuotas Duplicadas Detectadas:**\n\n"
                          f"Las siguientes unidades ya tienen cuotas de mantenimiento para **{mes_cuota} {año_cuota}**:\n\n"
                          f"{', '.join(map(str, sorted(unidades_con_cuotas)))}\n\n"
                          f"Solo se generarán cuotas para las unidades restantes.")
        
            # Mostrar resumen de cuotas a generar (solo para unidades sin cuotas)
            st.markdown("**Resumen de Cuotas de Mantenimiento a Generar:**")
            resumen_cols = st.columns(len(tipos_unidad))
        
            for i, (tipo, monto) in enumerate(montos_por_tipo.items()):
                if not residentes_df.empty:
                    # Filtrar solo unidades sin cuotas existentes
                    residentes_filtrados = residentes_df[
                        (residentes_df['Tipo_Unidad'] == tipo) & 
                        (residentes_df['Estado'] == 'Activo') &
                        (residentes_df['Tipo'] == 'Propietario') &
                        (residentes_df['Unidad'].isin(unidades_sin_cuotas))
                    ]
                    cantidad = len(residentes_filtrados)
                    total = cantidad * monto
                
                    with resumen_cols[i]:
                        st.info(f"**{tipo}**\n\n"
                           f"Unidades: {cantidad}\n\n"
                           f"Monto c/u: ${monto:,.2f}\n\n"
                           f"Total: ${total:,.2f}")
        
            if st.form_submit_button("🔄 Generar Cuotas de Mantenimiento/Administración"):
                # Validar que al menos un monto sea mayor a 0
                if not any(monto > 0 for monto in montos_por_tipo.values()):
                    st.error("⚠️ Debe configurar al menos un monto mayor a 0")
                    return
                
                # Validar que haya unidades sin cuotas
                if not unidades_sin_cuotas:
                    st.error(f"⚠️ No hay unidades disponibles para generar cuotas de {mes_cuota} {año_cuota}. "
                            f"Todas las unidades activas ya tienen cuotas generadas para este período.")
                    return
            
                if not residentes_df.empty:
                    cuotas_generadas = 0
                    total_generado = 0
                
                    for _, residente in residentes_df.iterrows():
                        if (residente['Estado'] == 'Activo' and 
                            residente['Tipo'] == 'Propietario' and 
                            residente['Unidad'] in unidades_sin_cuotas):
                            
                            tipo_unidad = residente.get('Tipo_Unidad', 'Sin Clasificar')
                            monto_cuota = montos_por_tipo.get(tipo_unidad, 0)
                        
                            if monto_cuota > 0:
                                cuota_id = f"CUOTA{datetime.now().strftime('%Y%m%d%H%M%S')}{cuotas_generadas:03d}"
                            
                                data = {
                                    'ID': cuota_id,
                                    'Tipo_Operacion': 'Cuota de Mantenimiento',
                                    'Unidad': residente['Unidad'],
                                    'Concepto': f"Cuota {mes_cuota} {año_cuota} - {tipo_unidad}",
                                    'Monto': monto_cuota,
                                    'Fecha': fecha_vencimiento.strftime('%Y-%m-%d'),
                                    'Banco': '',
                                    'Estado': 'Pendiente',
                                    'Metodo_Pago': '',
                                    'Ruta_Archivo':'',
                                    'Numero_Recibo':'',
                                    'Ruta_Recibo':'',
                                    'Observaciones': f"Cuota de mantenimiento generada automáticamente para {residente['Nombre']} {residente['Apellido']} - Tipo: {tipo_unidad}",
                                    'Saldo_Pendiente': monto_cuota,
                                    'Registrado': ''
                                }
                            
                                if st.session_state.manager.save_data('financiero', data):
                                    cuotas_generadas += 1
                                    total_generado += monto_cuota
                
                    if cuotas_generadas > 0:
                        st.success(f"✅ Se generaron {cuotas_generadas} cuotas de mantenimiento exitosamente")
                        st.info(f"💰 Total generado: ${total_generado:,.2f}")
                    
                        # Mostrar detalle por tipo de unidad
                        st.markdown("**Detalle por Tipo de Unidad:**")
                        for tipo_unidad in tipos_unidad:
                            if montos_por_tipo[tipo_unidad] > 0:
                                residentes_tipo = residentes_df[
                                    (residentes_df['Tipo_Unidad'] == tipo_unidad) & 
                                    (residentes_df['Estado'] == 'Activo') &
                                    (residentes_df['Tipo'] == 'Propietario') &
                                    (residentes_df['Unidad'].isin(unidades_sin_cuotas))
                                ]
                                cantidad = len(residentes_tipo)
                                if cantidad > 0:
                                    total_tipo = cantidad * montos_por_tipo[tipo_unidad]
                                    st.write(f"• **{tipo_unidad}**: {cantidad} cuotas × ${montos_por_tipo[tipo_unidad]:,.2f} = ${total_tipo:,.2f}")
                        
                        # Mostrar información sobre cuotas omitidas
                        if unidades_con_cuotas:
                            st.markdown("---")
                            st.info(f"**Cuotas Omitidas:** {len(unidades_con_cuotas)} unidades ya tenían cuotas para {mes_cuota} {año_cuota}")
                    else:
                        st.warning("⚠️ No se generaron cuotas. Verifique que haya residentes activos y montos configurados.")
                else:
                    st.warning("⚠️ No hay residentes registrados para generar cuotas")
    
        with subtab2:
          st.markdown("**⚡ Cuotas Extraordinarias**")
    
          with st.form("generate_extraordinary_fees"):
            st.markdown("**Generar Cuotas Extraordinarias Masivas**")
        
            col1, col2 = st.columns(2)
            with col1:
                concepto_extraordinaria = st.text_input(
                    "Concepto de la Cuota Extraordinaria *", 
                    placeholder="Ej: Reparación de ascensor, Pintura de fachada, etc."
                )
                descripcion_detallada = st.text_area(
                    "Descripción Detallada",
                    placeholder="Descripción completa del motivo de la cuota extraordinaria..."
                )
            with col2:
                fecha_vencimiento_ext = st.date_input("Fecha de Vencimiento", key="vencimiento_extraordinaria")
                estado_inicial = st.selectbox("Estado Inicial", 
                                        ["Pendiente", "Pagado"], 
                                        key="estado_extraordinaria")
        
            st.markdown("**Configurar Montos por Tipo de Unidad:**")
        
            # Crear campos de entrada para cada tipo de unidad
            montos_extraordinaria = {}
            cols = st.columns(min(len(tipos_unidad), 3))  # Máximo 3 columnas
        
            for i, tipo_unidad in enumerate(tipos_unidad):
                with cols[i % 3]:
                    monto = st.number_input(
                        f"💰 {tipo_unidad}", 
                        min_value=0.0, 
                        format="%.2f",
                        key=f"monto_extraordinaria_{tipo_unidad}",
                        help=f"Monto de cuota extraordinaria para {tipo_unidad}"
                    )
                    montos_extraordinaria[tipo_unidad] = monto
        
            # Obtener datos financieros existentes para validación
            financiero_df = st.session_state.manager.load_data('financiero')
            
            # Obtener unidades activas
            unidades_activas = []
            if not residentes_df.empty:
                unidades_activas = residentes_df[
                    (residentes_df['Estado'] == 'Activo') & 
                    (residentes_df['Tipo'] == 'Propietario')
                ]['Unidad'].tolist()
            
            # Validar duplicados para cuotas extraordinarias
            if concepto_extraordinaria.strip():
                unidades_con_cuotas_ext, unidades_sin_cuotas_ext = validar_cuotas_extraordinarias_duplicadas(
                    financiero_df, concepto_extraordinaria, fecha_vencimiento_ext, unidades_activas
                )
                
                # Mostrar advertencia si hay duplicados
                if unidades_con_cuotas_ext:
                    st.warning(f"⚠️ **Cuotas Extraordinarias Duplicadas Detectadas:**\n\n"
                              f"Las siguientes unidades ya tienen cuotas extraordinarias para **{concepto_extraordinaria}** "
                              f"con fecha **{fecha_vencimiento_ext.strftime('%Y-%m-%d')}**:\n\n"
                              f"{', '.join(map(str, sorted(unidades_con_cuotas_ext)))}\n\n"
                              f"Solo se generarán cuotas para las unidades restantes.")
            else:
                unidades_sin_cuotas_ext = unidades_activas
                unidades_con_cuotas_ext = []
        
            # Mostrar resumen de cuotas extraordinarias a generar
            st.markdown("**Resumen de Cuotas Extraordinarias a Generar:**")
            resumen_cols = st.columns(len(tipos_unidad))
        
            total_cuotas_extraordinarias = 0
            total_monto_extraordinarias = 0
        
            for i, (tipo, monto) in enumerate(montos_extraordinaria.items()):
                if not residentes_df.empty:
                    # Filtrar solo unidades sin cuotas extraordinarias existentes
                    residentes_filtrados = residentes_df[
                        (residentes_df['Tipo_Unidad'] == tipo) & 
                        (residentes_df['Estado'] == 'Activo') &
                        (residentes_df['Tipo'] == 'Propietario') &
                        (residentes_df['Unidad'].isin(unidades_sin_cuotas_ext))
                    ]
                    cantidad = len(residentes_filtrados)
                    total = cantidad * monto
                    total_cuotas_extraordinarias += cantidad
                    total_monto_extraordinarias += total
                
                    with resumen_cols[i]:
                        st.info(f"**{tipo}**\n\n"
                           f"Unidades: {cantidad}\n\n"
                           f"Monto c/u: ${monto:,.2f}\n\n"
                           f"Total: ${total:,.2f}")
        
            # Mostrar totales generales
            if total_cuotas_extraordinarias > 0:
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("📋 Total Cuotas a Generar", total_cuotas_extraordinarias)
                with col2:
                    st.metric("💰 Total General", f"${total_monto_extraordinarias:,.2f}")
        
            if st.form_submit_button("⚡ Generar Cuotas Extraordinarias"):
                # Validaciones
                if not concepto_extraordinaria.strip():
                    st.error("⚠️ Debe especificar el concepto de la cuota extraordinaria")
                    return
            
                if not any(monto > 0 for monto in montos_extraordinaria.values()):
                    st.error("⚠️ Debe configurar al menos un monto mayor a 0")
                    return
                
                # Validar que haya unidades sin cuotas
                if not unidades_sin_cuotas_ext:
                    st.error(f"⚠️ No hay unidades disponibles para generar cuotas extraordinarias de '{concepto_extraordinaria}'. "
                            f"Todas las unidades activas ya tienen esta cuota extraordinaria generada.")
                    return
            
                if not residentes_df.empty:
                    cuotas_generadas = 0
                    total_generado = 0
                
                    for _, residente in residentes_df.iterrows():
                        if (residente['Estado'] == 'Activo' and 
                            residente['Tipo'] == 'Propietario' and 
                            residente['Unidad'] in unidades_sin_cuotas_ext):
                            
                            tipo_unidad = residente.get('Tipo_Unidad', 'Sin Clasificar')
                            monto_cuota = montos_extraordinaria.get(tipo_unidad, 0)
                        
                            if monto_cuota > 0:
                                cuota_id = f"CEXT{datetime.now().strftime('%Y%m%d%H%M%S')}{cuotas_generadas:03d}"
                            
                                # Crear concepto completo
                                concepto_completo = f"Cuota Extraordinaria: {concepto_extraordinaria}"
                            
                                # Crear observaciones completas
                                observaciones_completas = f"Cuota extraordinaria generada automáticamente para {residente['Nombre']} {residente['Apellido']} - Tipo: {tipo_unidad}"
                                if descripcion_detallada:
                                    observaciones_completas += f"\n\nDescripción: {descripcion_detallada}"
                            
                                data = {
                                    'ID': cuota_id,
                                    'Tipo_Operacion': 'Ingreso',  # Como solicitas que sea "Ingreso"
                                    'Unidad': residente['Unidad'],
                                    'Concepto': concepto_completo,
                                    'Monto': monto_cuota,
                                    'Fecha': fecha_vencimiento_ext.strftime('%Y-%m-%d'),
                                    'Banco': '',
                                    'Estado': estado_inicial,
                                    'Metodo_Pago': '',
                                    'Ruta_Archivo':'',
                                    'Numero_Recibo':'',
                                    'Ruta_Recibo':'',
                                    'Observaciones': observaciones_completas,
                                    'Saldo_Pendiente': monto_cuota,
                                    'Registrado': ''
                                }
                            
                                if st.session_state.manager.save_data('financiero', data):
                                    cuotas_generadas += 1
                                    total_generado += monto_cuota
                
                    if cuotas_generadas > 0:
                        st.success(f"✅ Se generaron {cuotas_generadas} cuotas extraordinarias exitosamente")
                        st.info(f"💰 Total generado: ${total_generado:,.2f}")
                    
                        # Mostrar detalle por tipo de unidad
                        st.markdown("**Detalle por Tipo de Unidad:**")
                        for tipo_unidad in tipos_unidad:
                            if montos_extraordinaria[tipo_unidad] > 0:
                                residentes_tipo = residentes_df[
                                    (residentes_df['Tipo_Unidad'] == tipo_unidad) & 
                                    (residentes_df['Estado'] == 'Activo') &
                                    (residentes_df['Tipo'] == 'Propietario') &
                                    (residentes_df['Unidad'].isin(unidades_sin_cuotas_ext))
                                ]
                                cantidad = len(residentes_tipo)
                                if cantidad > 0:
                                    total_tipo = cantidad * montos_extraordinaria[tipo_unidad]
                                    st.write(f"• **{tipo_unidad}**: {cantidad} cuotas × ${montos_extraordinaria[tipo_unidad]:,.2f} = ${total_tipo:,.2f}")
                    
                        # Mostrar información adicional
                        st.markdown("---")
                        st.info(f"**Concepto:** {concepto_extraordinaria}\n\n**Fecha de Vencimiento:** {fecha_vencimiento_ext.strftime('%Y-%m-%d')}")
                        
                        # Mostrar información sobre cuotas omitidas
                        if unidades_con_cuotas_ext:
                            st.info(f"**Cuotas Omitidas:** {len(unidades_con_cuotas_ext)} unidades ya tenían esta cuota extraordinaria")
                    else:
                        st.warning("⚠️ No se generaron cuotas. Verifique que haya residentes activos y montos configurados.")
                else:
                    st.warning("⚠️ No hay residentes registrados para generar cuotas")
    
        with subtab3:
            st.markdown("**🗑️ Eliminar Cuotas**")
        
            financiero_df = st.session_state.manager.load_data('financiero')
        
            # Filtrar cuotas (tanto de mantenimiento como extraordinarias)
            cuotas_mantenimiento = financiero_df[financiero_df['Tipo_Operacion'] == 'Cuota de Mantenimiento'].copy() if not financiero_df.empty else pd.DataFrame()
            cuotas_extraordinarias = financiero_df[
                (financiero_df['Tipo_Operacion'] == 'Ingreso') & 
                (financiero_df['Concepto'].str.contains('Cuota Extraordinaria', case=False, na=False))
            ].copy() if not financiero_df.empty else pd.DataFrame()
        
            # Combinar ambos tipos de cuotas
            todas_cuotas = pd.concat([cuotas_mantenimiento, cuotas_extraordinarias], ignore_index=True) if not cuotas_mantenimiento.empty or not cuotas_extraordinarias.empty else pd.DataFrame()
        
            if not todas_cuotas.empty:
                # Agregar columna para identificar el tipo de cuota
                todas_cuotas['Tipo_Cuota'] = todas_cuotas.apply(
                    lambda row: 'Mantenimiento' if row['Tipo_Operacion'] == 'Cuota de Mantenimiento' else 'Extraordinaria', axis=1
                )
            
                tab_eliminar1, tab_eliminar2 = st.tabs(["🏠 Por Unidad", "📋 Registros Específicos"])
            
                with tab_eliminar1:
                    st.markdown("**Eliminar Cuotas por Unidad**")
                
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        unidades_disponibles = list(todas_cuotas['Unidad'].unique())
                        unidad_eliminar = st.selectbox(
                            "Seleccionar Unidad:", 
                            unidades_disponibles,
                            key="unidad_eliminar"
                        )
                
                    with col2:
                        # Filtro por tipo de cuota
                        tipo_cuota_filtro = st.selectbox(
                            "Tipo de Cuota:", 
                            ["Todas", "Mantenimiento", "Extraordinaria"],
                            key="tipo_cuota_filtro_eliminar"
                        )
                
                    with col3:
                        # Filtros adicionales
                        estados_cuota = list(todas_cuotas['Estado'].unique())
                        estado_filtro = st.selectbox(
                            "Estado de Cuotas:", 
                            ["Todos"] + estados_cuota,
                            key="estado_filtro_eliminar"
                        )
                
                    # Mostrar cuotas de la unidad seleccionada
                    cuotas_unidad = todas_cuotas[todas_cuotas['Unidad'] == unidad_eliminar].copy()
                
                    if tipo_cuota_filtro != "Todas":
                        cuotas_unidad = cuotas_unidad[cuotas_unidad['Tipo_Cuota'] == tipo_cuota_filtro]
                
                    if estado_filtro != "Todos":
                        cuotas_unidad = cuotas_unidad[cuotas_unidad['Estado'] == estado_filtro]
                
                    if not cuotas_unidad.empty:
                        st.markdown(f"**Cuotas encontradas para {unidad_eliminar}:**")
                    
                        # Mostrar tabla con información relevante
                        cuotas_display = cuotas_unidad[['ID', 'Tipo_Cuota', 'Concepto', 'Monto', 'Fecha', 'Estado']].copy()
                    
                        # FIXED: Handle NaT values properly
                        def safe_date_format(date_val):
                            try:
                                if pd.isna(date_val) or date_val is pd.NaT:
                                    return "Fecha no válida"
                                return pd.to_datetime(date_val).strftime('%Y-%m-%d')
                            except:
                                return "Fecha no válida"
                    
                        cuotas_display['Fecha'] = cuotas_display['Fecha'].apply(safe_date_format)
                        cuotas_display['Monto'] = cuotas_display['Monto'].apply(lambda x: f"${x:,.2f}")
                    
                        st.dataframe(cuotas_display, use_container_width=True)
                    
                        col1, col2 = st.columns(2)
                        with col1:
                            total_cuotas = len(cuotas_unidad)
                            total_monto = cuotas_unidad['Monto'].sum()
                            st.info(f"**Total:** {total_cuotas} cuotas - ${total_monto:,.2f}")
                    
                        with col2:
                            # Usar session state para manejar el estado de confirmación
                            if 'confirmar_eliminar_unidad' not in st.session_state:
                                st.session_state.confirmar_eliminar_unidad = False
                        
                            if not st.session_state.confirmar_eliminar_unidad:
                                if st.button(f"🗑️ Eliminar {total_cuotas} cuotas",  key="btn_eliminar_unidad"):
                                    st.session_state.confirmar_eliminar_unidad = True
                                    st.rerun()
                            else:
                                st.warning(f"⚠️ ¿Está seguro de eliminar {total_cuotas} cuotas de la unidad {unidad_eliminar}?")
                            
                                col_confirm1, col_confirm2 = st.columns(2)
                                with col_confirm1:
                                    if st.button("✅ Sí, Eliminar", type="primary", key="confirm_eliminar_unidad"):
                                        ids_eliminar = cuotas_unidad['ID'].tolist()
                                    
                                        # Usar delete_multiple_data si está disponible, sino usar delete_data individual
                                        if hasattr(st.session_state.manager, 'delete_multiple_data'):
                                            eliminadas = st.session_state.manager.delete_multiple_data('financiero', ids_eliminar)
                                        else:
                                            eliminadas = 0
                                            for cuota_id in ids_eliminar:
                                                if st.session_state.manager.delete_data ('financiero', cuota_id):
                                                    eliminadas += 1
                                    
                                        st.session_state.confirmar_eliminar_unidad = False
                                    
                                        if eliminadas > 0:
                                            st.success(f"✅ Se eliminaron {eliminadas} cuotas exitosamente")
                                            st.rerun()
                                        else:
                                            st.error("❌ Error al eliminar las cuotas")
                            
                                with col_confirm2:
                                    if st.button("❌ Cancelar", key="cancel_eliminar_unidad"):
                                        st.session_state.confirmar_eliminar_unidad = False
                                        st.rerun()
                    else:
                        st.info(f"No se encontraron cuotas para la unidad {unidad_eliminar} con los filtros aplicados")
            
                with tab_eliminar2:
                    st.markdown("**Eliminar Registros Específicos**")
                
                    # Filtros para búsqueda
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        filtro_unidad = st.selectbox(
                            "Filtrar por Unidad:", 
                            ["Todas"] + list(todas_cuotas['Unidad'].unique()),
                            key="filtro_unidad_especifica"
                        )
                
                    with col2:
                        filtro_tipo_cuota = st.selectbox(
                            "Tipo de Cuota:", 
                            ["Todas", "Mantenimiento", "Extraordinaria"],
                            key="filtro_tipo_cuota_especifica"
                        )
                
                    with col3:
                        filtro_estado = st.selectbox(
                            "Filtrar por Estado:", 
                            ["Todos"] + list(todas_cuotas['Estado'].unique()),
                            key="filtro_estado_especifica"
                        )
                
                    with col4:
                        filtro_concepto = st.text_input(
                            "Filtrar por Concepto:",
                            key="filtro_concepto_especifica",
                            placeholder="Ej: Enero 2024, Reparación..."
                        )
                
                    # Aplicar filtros
                    cuotas_filtradas = todas_cuotas.copy()
                
                    if filtro_unidad != "Todas":
                        cuotas_filtradas = cuotas_filtradas[cuotas_filtradas['Unidad'] == filtro_unidad]
                
                    if filtro_tipo_cuota != "Todas":
                        cuotas_filtradas = cuotas_filtradas[cuotas_filtradas['Tipo_Cuota'] == filtro_tipo_cuota]
                
                    if filtro_estado != "Todos":
                        cuotas_filtradas = cuotas_filtradas[cuotas_filtradas['Estado'] == filtro_estado]
                
                    if filtro_concepto:
                        cuotas_filtradas = cuotas_filtradas[
                            cuotas_filtradas['Concepto'].str.contains(filtro_concepto, case=False, na=False)
                        ]
                
                    if not cuotas_filtradas.empty:
                        st.markdown("**Seleccionar cuotas para eliminar:**")
                    
                        # Inicializar session state para las cuotas seleccionadas
                        if 'cuotas_seleccionadas' not in st.session_state:
                            st.session_state.cuotas_seleccionadas = set()
                    
                        if 'confirmar_eliminar_seleccionadas' not in st.session_state:
                            st.session_state.confirmar_eliminar_seleccionadas = False
                    
                        # Crear checkboxes para cada cuota con labels descriptivos
                        for idx, cuota in cuotas_filtradas.iterrows():
                            # FIXED: Handle NaT values properly for display
                            try:
                                if pd.isna(cuota['Fecha']) or cuota['Fecha'] is pd.NaT:
                                    fecha_formato = "Fecha no válida"
                                else:
                                    fecha_formato = pd.to_datetime(cuota['Fecha']).strftime('%Y-%m-%d')
                            except:
                                fecha_formato = "Fecha no válida"
                        
                            label_checkbox = f"[{cuota['Tipo_Cuota']}] {cuota['Unidad']} - {cuota['Concepto']} - ${cuota['Monto']:,.2f} - {fecha_formato} - {cuota['Estado']}"
                        
                            seleccionada = st.checkbox(
                                label_checkbox,
                                key=f"check_{cuota['ID']}",
                                value=cuota['ID'] in st.session_state.cuotas_seleccionadas
                            )
                        
                            if seleccionada:
                                st.session_state.cuotas_seleccionadas.add(cuota['ID'])
                            else:
                                st.session_state.cuotas_seleccionadas.discard(cuota['ID'])
                    
                        if st.session_state.cuotas_seleccionadas:
                            st.markdown("---")
                        
                            # Obtener información de las cuotas seleccionadas
                            cuotas_seleccionadas_info = cuotas_filtradas[
                                cuotas_filtradas['ID'].isin(st.session_state.cuotas_seleccionadas)
                            ]
                        
                            col1, col2 = st.columns(2)
                        
                            with col1:
                                total_seleccionadas = len(cuotas_seleccionadas_info)
                                total_monto_seleccionadas = cuotas_seleccionadas_info['Monto'].sum()
                            
                                # Mostrar resumen por tipo
                                mantenimiento_count = len(cuotas_seleccionadas_info[cuotas_seleccionadas_info['Tipo_Cuota'] == 'Mantenimiento'])
                                extraordinaria_count = len(cuotas_seleccionadas_info[cuotas_seleccionadas_info['Tipo_Cuota'] == 'Extraordinaria'])
                            
                                st.info(f"**Seleccionadas:** {total_seleccionadas} cuotas - ${total_monto_seleccionadas:,.2f}\n\n"
                                    f"• Mantenimiento: {mantenimiento_count}\n"
                                    f"• Extraordinarias: {extraordinaria_count}")
                        
                            with col2:
                                if not st.session_state.confirmar_eliminar_seleccionadas:
                                    if st.button(f"🗑️ Eliminar {total_seleccionadas}    cuotas seleccionadas", key="btn_eliminar_seleccionadas"):
                                        st.session_state.confirmar_eliminar_seleccionadas = True
                                        st.rerun()
                                else:
                                    st.warning(f"⚠️ ¿Está seguro de eliminar {total_seleccionadas} cuotas seleccionadas?")
                                
                                    col_confirm1, col_confirm2 = st.columns(2)
                                    with col_confirm1:
                                        if st.button("✅ Sí, Eliminar", type="primary",     key="confirm_eliminar_seleccionadas"):
                                            ids_eliminar = list(st.session_state.cuotas_seleccionadas)
                                        
                                            # Usar delete_multiple_data si está disponible, sino usar delete_data individual
                                            if hasattr(st.session_state.manager, 'delete_multiple_data'):
                                                eliminadas = st.session_state.manager.delete_multiple_data('financiero', ids_eliminar)
                                            else:
                                                eliminadas = 0
                                                for cuota_id in ids_eliminar:
                                                    if st.session_state.manager.delete_data ('financiero', cuota_id):
                                                        eliminadas += 1
    ########
                                            
                                            # Limpiar el estado
                                            st.session_state.cuotas_seleccionadas.clear()
                                            st.session_state.confirmar_eliminar_seleccionadas = False
                                            
                                            if eliminadas > 0:
                                                st.success(f"✅ Se eliminaron {eliminadas} cuotas exitosamente")
                                                st.rerun()
                                            else:
                                                st.error("❌ Error al eliminar las cuotas")
                                    
                                    with col_confirm2:
                                        if st.button("❌ Cancelar", key="cancel_eliminar_seleccionadas"):
                                            st.session_state.confirmar_eliminar_seleccionadas = False
                                            st.rerun()
                    else:
                        st.info("No se encontraron cuotas con los filtros aplicados")
            else:
                st.info("📝 No hay cuotas registradas")
        
        # Sección adicional para mostrar estadísticas de cuotas pendientes
        st.markdown("---")
        st.markdown("**📊 Estadísticas de Cuotas**")
        
        financiero_df = st.session_state.manager.load_data('financiero')
        if not financiero_df.empty:
            # Cuotas de mantenimiento pendientes
            cuotas_mantenimiento_pendientes = financiero_df[
                (financiero_df['Tipo_Operacion'] == 'Cuota de Mantenimiento') & 
                (financiero_df['Estado'] == 'Pendiente')
            ]
            
            # Cuotas extraordinarias pendientes
            cuotas_extraordinarias_pendientes = financiero_df[
                (financiero_df['Tipo_Operacion'] == 'Ingreso') & 
                (financiero_df['Concepto'].str.contains('Cuota Extraordinaria', case=False, na=False)) &
                (financiero_df['Estado'] == 'Pendiente')
            ]
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_mantenimiento = len(cuotas_mantenimiento_pendientes)
                monto_mantenimiento = cuotas_mantenimiento_pendientes['Monto'].sum() if not cuotas_mantenimiento_pendientes.empty else 0
                st.metric("🏢 Cuotas Mantenimiento Pendientes", 
                         f"{total_mantenimiento}",
                         f"${monto_mantenimiento:,.2f}")
            
            with col2:
                total_extraordinarias = len(cuotas_extraordinarias_pendientes)
                monto_extraordinarias = cuotas_extraordinarias_pendientes['Monto'].sum() if not cuotas_extraordinarias_pendientes.empty else 0
                st.metric("⚡ Cuotas Extraordinarias Pendientes", 
                         f"{total_extraordinarias}",
                         f"${monto_extraordinarias:,.2f}")
            
            with col3:
                total_cuotas_pendientes = total_mantenimiento + total_extraordinarias
                total_monto_pendiente = monto_mantenimiento + monto_extraordinarias
                st.metric("📋 Total Cuotas Pendientes", 
                         f"{total_cuotas_pendientes}",
                         f"${total_monto_pendiente:,.2f}")
            
            with col4:
                # Calcular cuotas vencidas (tanto mantenimiento como extraordinarias)
                todas_cuotas_pendientes = pd.concat([cuotas_mantenimiento_pendientes, cuotas_extraordinarias_pendientes], ignore_index=True)
                
                if not todas_cuotas_pendientes.empty:
                    todas_cuotas_pendientes['Fecha'] = pd.to_datetime(todas_cuotas_pendientes['Fecha'])
                    fecha_actual = pd.Timestamp(datetime.now().date())
                    cuotas_vencidas = todas_cuotas_pendientes[
                        todas_cuotas_pendientes['Fecha'] < fecha_actual
                    ]
                    monto_vencido = cuotas_vencidas['Monto'].sum() if not cuotas_vencidas.empty else 0
                    st.metric("⚠️ Cuotas Vencidas", 
                             f"{len(cuotas_vencidas)}",
                             f"${monto_vencido:,.2f}")
                else:
                    st.metric("⚠️ Cuotas Vencidas", "0", "$0.00")
            
            # Mostrar gráfico de distribución de cuotas si hay datos
            if not cuotas_mantenimiento_pendientes.empty or not cuotas_extraordinarias_pendientes.empty:
                st.markdown("---")
                st.markdown("**📈 Distribución de Cuotas Pendientes**")
                
                # Crear datos para el gráfico
                data_grafico = []
                if not cuotas_mantenimiento_pendientes.empty:
                    data_grafico.append({
                        'Tipo': 'Cuotas de Mantenimiento',
                        'Cantidad': len(cuotas_mantenimiento_pendientes),
                        'Monto': cuotas_mantenimiento_pendientes['Monto'].sum()
                    })
                
                if not cuotas_extraordinarias_pendientes.empty:
                    data_grafico.append({
                        'Tipo': 'Cuotas Extraordinarias',
                        'Cantidad': len(cuotas_extraordinarias_pendientes),
                        'Monto': cuotas_extraordinarias_pendientes['Monto'].sum()
                    })
                
                if data_grafico:
                    df_grafico = pd.DataFrame(data_grafico)
                    fig = px.bar(df_grafico, x='Tipo', y='Monto', 
                               title="Montos Pendientes por Tipo de Cuota",
                               text='Cantidad')
                    fig.update_traces(texttemplate='%{text} cuotas', textposition='outside')
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📝 No hay información financiera disponible")

    with tab6:
        st.subheader("📝 Informe de Estado Financiero ")
        informe_estado_main()

def show_maintenance_module():
    """Módulo de gestión de mantenimiento"""
    st.markdown("## 🔧 Gestión de Servicios y Mantenimiento")
    
    tab1, tab2, tab3 = st.tabs(["➕ Nueva Solicitud", "📋 Órdenes de Trabajo", "📊 Estadísticas"])
    
    with tab1:
        with st.form("add_maintenance"):
            st.subheader("Nueva Solicitud de Mantenimiento")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_servicio = st.selectbox("Tipo de Servicio", 
                                           ["Plomería", "Electricidad", "Pintura", "Jardinería", 
                                            "Limpieza", "Reparación General", "Mantenimiento Preventivo"])
                unidad = st.text_input("Unidad (si aplica)")
                descripcion = st.text_area("Descripción del Problema *")
                
            with col2:
                fecha_solicitud = st.date_input("Fecha de Solicitud", datetime.now().date())
                fecha_programada = st.date_input("Fecha Programada")
                estado = st.selectbox("Estado", ["Pendiente", "En Proceso", "Completado", "Cancelado"])
                costo = st.number_input("Costo Estimado", min_value=0.0, format="%.2f")
                proveedor = st.text_input("Proveedor/Técnico")
            
            if st.form_submit_button("✅ Crear Solicitud"):
                if descripcion:
                    maintenance_id = f"MNT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': maintenance_id,
                        'Tipo_Servicio': tipo_servicio,
                        'Unidad': unidad,
                        'Descripcion': descripcion,
                        'Fecha_Solicitud': fecha_solicitud.strftime('%Y-%m-%d'),
                        'Fecha_Programada': fecha_programada.strftime('%Y-%m-%d'),
                        'Estado': estado,
                        'Costo': costo,
                        'Proveedor': proveedor
                    }
                    
                    if st.session_state.manager.save_data('mantenimiento', data):
                        st.success("✅ Solicitud de mantenimiento creada exitosamente")
                    else:
                        st.error("❌ Error al crear solicitud")
                else:
                    st.error("⚠️ Por favor, describe el problema")
    
    with tab2:
        st.subheader("📋 Órdenes de Trabajo")
        mantenimiento_df = st.session_state.manager.load_data('mantenimiento')
        
        if not mantenimiento_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_tipo = st.selectbox("Tipo de Servicio:", 
                                         ["Todos"] + list(mantenimiento_df['Tipo_Servicio'].unique()))
            with col2:
                filter_estado = st.selectbox("Estado:", 
                                           ["Todos"] + list(mantenimiento_df['Estado'].unique()))
            with col3:
                search_unidad = st.text_input("Buscar por unidad:")
            
            # Aplicar filtros
            filtered_df = mantenimiento_df.copy()
            if filter_tipo != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo_Servicio'] == filter_tipo]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            if search_unidad:
                filtered_df = filtered_df[
                    filtered_df['Unidad'].str.contains(search_unidad, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Actualizar estado de mantenimiento
            if not filtered_df.empty:
                st.subheader("✏️ Actualizar Estado")
                selected_id = st.selectbox("Seleccionar ID de Mantenimiento:", 
                                         filtered_df['ID'].tolist())
                new_status = st.selectbox("Nuevo Estado:", 
                                        ["Pendiente", "En Proceso", "Completado", "Cancelado"])
                
                if st.button("🔄 Actualizar Estado"):
                    st.info("💡 Funcionalidad de actualización disponible en versión completa")
        else:
            st.info("📝 No hay solicitudes de mantenimiento registradas")
    
    with tab3:
        st.subheader("📊 Estadísticas de Mantenimiento")
        mantenimiento_df = st.session_state.manager.load_data('mantenimiento')
        
        if not mantenimiento_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Distribución por tipo de servicio
                tipo_counts = mantenimiento_df['Tipo_Servicio'].value_counts()
                fig = px.bar(x=tipo_counts.index, y=tipo_counts.values,
                           title="Solicitudes por Tipo de Servicio")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Estado de solicitudes
                estado_counts = mantenimiento_df['Estado'].value_counts()
                fig = px.pie(values=estado_counts.values, names=estado_counts.index,
                           title="Estado de Solicitudes")
                st.plotly_chart(fig, use_container_width=True)
            
            # Costos por tipo de servicio
            if 'Costo' in mantenimiento_df.columns:
                costo_por_tipo = mantenimiento_df.groupby('Tipo_Servicio')['Costo'].sum().reset_index()
                fig = px.bar(costo_por_tipo, x='Tipo_Servicio', y='Costo',
                           title="Costos por Tipo de Servicio")
                st.plotly_chart(fig, use_container_width=True)

def show_communication_module():
    """Módulo de comunicación con residentes"""
    st.markdown("## 📢 Comunicación con Residentes")
    
    tab1, tab2, tab3 = st.tabs(["📧 Enviar Mensaje", "📋 Historial", "📢 Anuncios"])
    
    with tab1:
        with st.form("send_message"):
            st.subheader("Enviar Mensaje a Residentes")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_mensaje = st.selectbox("Tipo de Mensaje", 
                                          ["Anuncio General", "Aviso Importante", "Recordatorio",
                                           "Convocatoria", "Mensaje Individual"])
                destinatario = st.selectbox("Destinatario", 
                                          ["Todos los Residentes", "Propietarios", "Inquilinos", "Específico"])
                
                if destinatario == "Específico":
                    residentes_df = st.session_state.manager.load_data('residentes')
                    if not residentes_df.empty:
                        unidades = residentes_df['Unidad'].unique().tolist()
                        unidad_especifica = st.selectbox("Seleccionar Unidad:", unidades)
                    else:
                        st.warning("No hay residentes registrados")
                        unidad_especifica = ""
                else:
                    unidad_especifica = destinatario
                    
            with col2:
                asunto = st.text_input("Asunto *")
                fecha_envio = st.date_input("Fecha de Envío", datetime.now().date())
                metodo_envio = st.selectbox("Método de Envío", ["Solo Registrar", "Registrar y Enviar Email"])
            
            mensaje = st.text_area("Mensaje *", height=150)
            
            # Mostrar preview de destinatarios
            if destinatario != "Específico" or (destinatario == "Específico" and 'unidad_especifica' in locals()):
                emails_info = get_resident_emails(destinatario, unidad_especifica if destinatario == "Específico" else None)
                if emails_info:
                    st.info(f"📧 Se enviará a {len(emails_info)} destinatario(s)")
                    with st.expander("Ver destinatarios"):
                        for email_info in emails_info:
                            st.write(f"• {email_info['nombre']} - {email_info['unidad']} - {email_info['email']}")
                else:
                    st.warning("⚠️ No se encontraron destinatarios con correo electrónico")
            
            if st.form_submit_button("📧 Enviar Mensaje"):
                if asunto and mensaje:
                    message_id = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # Registrar el mensaje
                    data = {
                        'ID': message_id,
                        'Tipo': tipo_mensaje,
                        'Destinatario': unidad_especifica if destinatario == "Específico" else destinatario,
                        'Asunto': asunto,
                        'Mensaje': mensaje,
                        'Fecha_Envio': fecha_envio.strftime('%Y-%m-%d'),
                        'Estado': 'Registrado',
                        'Metodo_Envio': metodo_envio,
                        'Respuesta': ''
                    }
                    
                    # Guardar en base de datos
                    if st.session_state.manager.save_data('comunicacion', data):
                        st.success("✅ Mensaje registrado exitosamente")
                        
                        # Enviar emails si se seleccionó esa opción
                        if metodo_envio == "Registrar y Enviar Email":
                            emails_info = get_resident_emails(destinatario, unidad_especifica if destinatario == "Específico" else None)
                            
                            if emails_info:
                                st.info("📤 Enviando correos electrónicos...")
                                successful, failed, errors = send_bulk_emails(emails_info, asunto, mensaje, tipo_mensaje)
                                
                                # Actualizar estado del mensaje
                                if failed == 0:
                                    estado_final = "Enviado Completamente"
                                elif successful > 0:
                                    estado_final = "Enviado Parcialmente"
                                else:
                                    estado_final = "Error en Envío"
                                
                                # Actualizar en la base de datos
                                data['Estado'] = estado_final
                                data['Respuesta'] = f"Enviados: {successful}, Fallidos: {failed}"
                                
                                # Actualizar estado usando la función helper
                                response_info = f"Enviados: {successful}, Fallidos: {failed}"
                                update_message_status(message_id, estado_final, response_info)
                                
                                # Mostrar resultados
                                if successful > 0:
                                    st.success(f"✅ {successful} correo(s) enviado(s) exitosamente")
                                if failed > 0:
                                    st.error(f"❌ {failed} correo(s) fallaron")
                                    with st.expander("Ver errores"):
                                        for error in errors:
                                            st.write(f"• {error}")
                                            
                            else:
                                st.warning("⚠️ No se encontraron destinatarios con correo electrónico")
                                # Actualizar estado usando la función helper
                                update_message_status(message_id, "Sin Destinatarios")
                    else:
                        st.error("❌ Error al registrar mensaje")
                else:
                    st.error("⚠️ Por favor, completa el asunto y el mensaje")
    
    with tab2:
        st.subheader("📋 Historial de Mensajes")
        comunicacion_df = st.session_state.manager.load_data('comunicacion')
        
        if not comunicacion_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_tipo = st.selectbox("Filtrar por Tipo:", 
                                         ["Todos"] + list(comunicacion_df['Tipo'].unique()))
            with col2:
                filter_estado = st.selectbox("Filtrar por Estado:", 
                                           ["Todos"] + list(comunicacion_df['Estado'].unique()))
            with col3:
                filter_metodo = st.selectbox("Filtrar por Método:", 
                                           ["Todos"] + list(comunicacion_df.get('Metodo_Envio', pd.Series()).dropna().unique()))
            
            # Aplicar filtros
            filtered_df = comunicacion_df.copy()
            if filter_tipo != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo'] == filter_tipo]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            if filter_metodo != "Todos" and 'Metodo_Envio' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Metodo_Envio'] == filter_metodo]
            
            # Mostrar mensajes
            for _, message in filtered_df.iterrows():
                estado_color = {
                    'Registrado': '🟡',
                    'Enviado Completamente': '🟢',
                    'Enviado Parcialmente': '🟠',
                    'Error en Envío': '🔴',
                    'Sin Destinatarios': '⚪'
                }.get(message.get('Estado', ''), '⚫')
                
                with st.expander(f"{estado_color} {message['Asunto']} - {message['Fecha_Envio']}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Tipo:** {message['Tipo']}")
                        st.write(f"**Destinatario:** {message['Destinatario']}")
                        st.write(f"**Mensaje:** {message['Mensaje']}")
                        if 'Respuesta' in message and message['Respuesta']:
                            st.write(f"**Resultado:** {message['Respuesta']}")
                    with col2:
                        st.write(f"**Estado:** {message['Estado']}")
                        st.write(f"**ID:** {message['ID']}")
                        if 'Metodo_Envio' in message:
                            st.write(f"**Método:** {message['Metodo_Envio']}")
        else:
            st.info("📝 No hay mensajes registrados")
    
    with tab3:
        st.subheader("📢 Tablón de Anuncios")
        
        # Mostrar anuncios activos
        comunicacion_df = st.session_state.manager.load_data('comunicacion')
        if not comunicacion_df.empty:
            anuncios = comunicacion_df[
                (comunicacion_df['Tipo'] == 'Anuncio General') & 
                (comunicacion_df['Estado'].isin(['Enviado Completamente', 'Enviado Parcialmente', 'Registrado']))
            ]
            
            if not anuncios.empty:
                for _, anuncio in anuncios.iterrows():
                    estado_badge = {
                        'Enviado Completamente': '<span style="background-color:#28a745;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">✅ Enviado</span>',
                        'Enviado Parcialmente': '<span style="background-color:#ffc107;color:black;padding:2px 8px;border-radius:12px;font-size:12px;">⚠️ Parcial</span>',
                        'Registrado': '<span style="background-color:#6c757d;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">📝 Registrado</span>'
                    }.get(anuncio.get('Estado', ''), '')
                    
                    st.markdown(f"""
                    <div style="border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin: 10px 0; background-color: #f8f9fa;">
                        <h4>📢 {anuncio['Asunto']} {estado_badge}</h4>
                        <p><strong>Fecha:</strong> {anuncio['Fecha_Envio']}</p>
                        <p><strong>Destinatario:</strong> {anuncio['Destinatario']}</p>
                        <p>{anuncio['Mensaje']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("📝 No hay anuncios activos")
        else:
            st.info("📝 No hay comunicaciones registradas")


def show_access_module():
    """Módulo de control de accesos y seguridad"""
    st.markdown("## 🚪 Control de Accesos y Seguridad")
    
    tab1, tab2, tab3 = st.tabs(["👤 Registro de Visitantes", "📋 Historial de Accesos", "📊 Reportes"])
    
    with tab1:
        with st.form("register_visit"):
            st.subheader("Registrar Visita")
            
            col1, col2 = st.columns(2)
            with col1:
                unidad = st.text_input("Unidad a Visitar *")
                visitante = st.text_input("Nombre del Visitante *")
                fecha = st.date_input("Fecha de Visita", datetime.now().date())
                hora_entrada = st.time_input("Hora de Entrada", datetime.now().time())
                
            with col2:
                hora_salida = st.time_input("Hora de Salida (opcional)")
                autorizado_por = st.text_input("Autorizado Por")
                documento = st.text_input("Documento de Identidad")
                vehiculo = st.text_input("Placa del Vehículo")
            
            observaciones = st.text_area("Observaciones")
            
            if st.form_submit_button("✅ Registrar Visita"):
                if unidad and visitante:
                    access_id = f"ACC{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': access_id,
                        'Unidad': unidad,
                        'Visitante': visitante,
                        'Fecha': fecha.strftime('%Y-%m-%d'),
                        'Hora_Entrada': hora_entrada.strftime('%H:%M'),
                        'Hora_Salida': hora_salida.strftime('%H:%M') if hora_salida else '',
                        'Autorizado_Por': autorizado_por,
                        'Observaciones': f"Doc: {documento}, Vehículo: {vehiculo}. {observaciones}"
                    }
                    
                    if st.session_state.manager.save_data('accesos', data):
                        st.success("✅ Visita registrada exitosamente")
                    else:
                        st.error("❌ Error al registrar visita")
                else:
                    st.error("⚠️ Por favor, completa los campos obligatorios")
    
    with tab2:
        st.subheader("📋 Historial de Accesos")
        accesos_df = st.session_state.manager.load_data('accesos')
        
        if not accesos_df.empty:
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filter_unidad = st.text_input("Filtrar por Unidad:")
                fecha_desde = st.date_input("Desde:", datetime.now().date().replace(day=1))
            with col2:
                search_visitante = st.text_input("Buscar Visitante:")
                fecha_hasta = st.date_input("Hasta:", datetime.now().date())
            
            # Aplicar filtros
            filtered_df = accesos_df.copy()
            if filter_unidad:
                filtered_df = filtered_df[
                    filtered_df['Unidad'].str.contains(filter_unidad, case=False, na=False)
                ]
            if search_visitante:
                filtered_df = filtered_df[
                    filtered_df['Visitante'].str.contains(search_visitante, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Estadísticas rápidas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("👥 Total Visitas", len(filtered_df))
            with col2:
                visitas_hoy = len(filtered_df[filtered_df['Fecha'] == datetime.now().strftime('%Y-%m-%d')])
                st.metric("📅 Visitas Hoy", visitas_hoy)
            with col3:
                unidades_visitadas = filtered_df['Unidad'].nunique()
                st.metric("🏠 Unidades Visitadas", unidades_visitadas)
        else:
            st.info("📝 No hay registros de accesos")
    
    with tab3:
        st.subheader("📊 Reportes de Seguridad")
        accesos_df = st.session_state.manager.load_data('accesos')
        
        if not accesos_df.empty:
            # Convertir fecha para análisis
            accesos_df['Fecha'] = pd.to_datetime(accesos_df['Fecha'])
            accesos_df['Mes'] = accesos_df['Fecha'].dt.strftime('%Y-%m')
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Visitas por mes
                visitas_mes = accesos_df.groupby('Mes').size().reset_index(name='Visitas')
                fig = px.line(visitas_mes, x='Mes', y='Visitas', 
                            title="Tendencia de Visitas por Mes")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Unidades más visitadas
                unidades_top = accesos_df['Unidad'].value_counts().head(10).reset_index()
                fig = px.bar(unidades_top, x='count', y='Unidad', 
                           title="Top 10 Unidades Más Visitadas", orientation='h')
                st.plotly_chart(fig, use_container_width=True)

def show_common_areas_module():
    """Módulo de administración de áreas comunes"""
    st.markdown("## 🏊 Administración de Áreas Comunes")
    
    tab1, tab2, tab3 = st.tabs(["📅 Nueva Reserva", "📋 Reservas Activas", "⚙️ Configuración"])
    
    with tab1:
        with st.form("reserve_area"):
            st.subheader("Reservar Área Común")
            
            areas_disponibles = [
                "Piscina", "Salón de Eventos", "BBQ/Parrilla", "Cancha de Tenis",
                "Gimnasio", "Sala de Juegos", "Terraza", "Jardín", "Cancha Múltiple"
            ]
            
            col1, col2 = st.columns(2)
            with col1:
                area = st.selectbox("Área a Reservar *", areas_disponibles)
                unidad = st.text_input("Unidad del Solicitante *")
                fecha_reserva = st.date_input("Fecha de Reserva", datetime.now().date())
                hora_inicio = st.time_input("Hora de Inicio")
                
            with col2:
                hora_fin = st.time_input("Hora de Fin")
                estado = st.selectbox("Estado", ["Confirmada", "Pendiente", "Cancelada"])
                costo = st.number_input("Costo de la Reserva", min_value=0.0, format="%.2f")
                responsable = st.text_input("Nombre del Responsable")
            
            observaciones = st.text_area("Observaciones")
            
            if st.form_submit_button("✅ Hacer Reserva"):
                if area and unidad:
                    reservation_id = f"RES{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': reservation_id,
                        'Area': area,
                        'Unidad': unidad,
                        'Fecha_Reserva': fecha_reserva.strftime('%Y-%m-%d'),
                        'Hora_Inicio': hora_inicio.strftime('%H:%M'),
                        'Hora_Fin': hora_fin.strftime('%H:%M'),
                        'Estado': estado,
                        'Costo': costo,
                        'Observaciones': f"Responsable: {responsable}. {observaciones}"
                    }
                    
                    if st.session_state.manager.save_data('areas_comunes', data):
                        st.success("✅ Reserva realizada exitosamente")
                        st.rerun()  # Refresh to show the new reservation
                    else:
                        st.error("❌ Error al realizar reserva")
                else:
                    st.error("⚠️ Por favor, completa los campos obligatorios")
    
    with tab2:
        st.subheader("📋 Reservas Activas")
        
        try:
            areas_df = st.session_state.manager.load_data('areas_comunes')
            
            # Check if DataFrame is empty or None
            if areas_df is None or areas_df.empty:
                st.info("📝 No hay reservas registradas")
                return
            
            # Verify required columns exist
            required_columns = ['Area', 'Estado', 'Fecha_Reserva', 'Hora_Inicio', 'Hora_Fin', 'Unidad', 'Costo']
            missing_columns = [col for col in required_columns if col not in areas_df.columns]
            
            if missing_columns:
                st.error(f"❌ Faltan columnas en los datos: {', '.join(missing_columns)}")
                st.write("Columnas disponibles:", list(areas_df.columns))
                return
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_area = st.selectbox("Filtrar por Área:", 
                                         ["Todas"] + sorted(areas_df['Area'].unique().tolist()))
            with col2:
                filter_estado = st.selectbox("Filtrar por Estado:", 
                                           ["Todos"] + sorted(areas_df['Estado'].unique().tolist()))
            with col3:
                fecha_filtro = st.date_input("Filtrar por Fecha:")
            
            # Aplicar filtros
            filtered_df = areas_df.copy()
            if filter_area != "Todas":
                filtered_df = filtered_df[filtered_df['Area'] == filter_area]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            
            # Filter by date if specified
            if fecha_filtro:
                fecha_str = fecha_filtro.strftime('%Y-%m-%d')
                filtered_df = filtered_df[filtered_df['Fecha_Reserva'] == fecha_str]
            
            # Mostrar calendario de reservas
            st.subheader("📅 Calendario de Reservas")
            
            # Crear vista de calendario simple
            if not filtered_df.empty:
                # Sort by date and time
                try:
                    filtered_df = filtered_df.sort_values(['Fecha_Reserva', 'Hora_Inicio'])
                except:
                    pass  # If sorting fails, continue without sorting
                
                for _, reserva in filtered_df.iterrows():
                    status_color = {
                        'Confirmada': '🟢',
                        'Pendiente': '🟡',
                        'Cancelada': '🔴'
                    }
                    
                    # Safe access to data with defaults
                    area = reserva.get('Area', 'N/A')
                    unidad = reserva.get('Unidad', 'N/A')
                    fecha = reserva.get('Fecha_Reserva', 'N/A')
                    hora_inicio = reserva.get('Hora_Inicio', 'N/A')
                    hora_fin = reserva.get('Hora_Fin', 'N/A')
                    estado = reserva.get('Estado', 'N/A')
                    costo = reserva.get('Costo', 0)
                    observaciones = reserva.get('Observaciones', '')
                    
                    st.markdown(f"""
                    <div class="module-card">
                        <h4>{status_color.get(estado, '⚪')} {area}</h4>
                        <p><strong>Unidad:</strong> {unidad}</p>
                        <p><strong>Fecha:</strong> {fecha}</p>
                        <p><strong>Horario:</strong> {hora_inicio} - {hora_fin}</p>
                        <p><strong>Estado:</strong> {estado}</p>
                        {f"<p><strong>Costo:</strong> ${costo}</p>" if costo and costo > 0 else ""}
                        {f"<p><strong>Observaciones:</strong> {observaciones}</p>" if observaciones else ""}
                    </div>
                    """, unsafe_allow_html=True)
                
                # Show summary statistics
                st.subheader("📊 Resumen")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Reservas", len(filtered_df))
                with col2:
                    confirmadas = len(filtered_df[filtered_df['Estado'] == 'Confirmada'])
                    st.metric("Confirmadas", confirmadas)
                with col3:
                    pendientes = len(filtered_df[filtered_df['Estado'] == 'Pendiente'])
                    st.metric("Pendientes", pendientes)
                with col4:
                    total_ingresos = filtered_df['Costo'].sum()
                    st.metric("Ingresos Total", f"${total_ingresos:.2f}")
            else:
                st.info("📝 No hay reservas para los filtros seleccionados")
                
        except Exception as e:
            st.error(f"❌ Error al cargar reservas: {str(e)}")
            st.write("Error details:", e)
    
    with tab3:
        st.subheader("⚙️ Configuración de Áreas")
        
        # Configurar tarifas por área
        st.markdown("**Configurar Tarifas por Área**")
        
        areas_config = {
            "Piscina": 0,
            "Salón de Eventos": 50,
            "BBQ/Parrilla": 20,
            "Cancha de Tenis": 15,
            "Gimnasio": 0,
            "Sala de Juegos": 10,
            "Terraza": 25,
            "Jardín": 30,
            "Cancha Múltiple": 20
        }
        
        st.markdown("💰 **Tarifas por Área**")
        for area, tarifa_default in areas_config.items():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{area}**")
            with col2:
                nueva_tarifa = st.number_input(f"Tarifa ${area}", key=f"tarifa_{area}", 
                                             value=float(tarifa_default), format="%.2f")
        
        # Horarios de funcionamiento
        st.markdown("🕒 **Horarios de Funcionamiento**")
        col1, col2 = st.columns(2)
        with col1:
            hora_apertura = st.time_input("Hora de Apertura", value=datetime.strptime("06:00", "%H:%M").time())
        with col2:
            hora_cierre = st.time_input("Hora de Cierre", value=datetime.strptime("22:00", "%H:%M").time())
        
        # Reglas y restricciones
        st.markdown("📋 **Reglas y Restricciones**")
        col1, col2 = st.columns(2)
        with col1:
            max_horas_reserva = st.number_input("Máximo horas por reserva", min_value=1, max_value=24, value=4)
            dias_anticipacion = st.number_input("Días mínimos de anticipación", min_value=0, max_value=30, value=1)
        with col2:
            max_reservas_mes = st.number_input("Máximo reservas por unidad/mes", min_value=1, max_value=50, value=8)
            cancelacion_limite = st.number_input("Horas límite para cancelación", min_value=1, max_value=72, value=24)
        
        if st.button("💾 Guardar Configuración"):
            # Here you could save the configuration to your data manager
            config_data = {
                'tarifas': {area: st.session_state.get(f"tarifa_{area}", tarifa) 
                           for area, tarifa in areas_config.items()},
                'horarios': {
                    'apertura': hora_apertura.strftime('%H:%M'),
                    'cierre': hora_cierre.strftime('%H:%M')
                },
                'restricciones': {
                    'max_horas_reserva': max_horas_reserva,
                    'dias_anticipacion': dias_anticipacion,
                    'max_reservas_mes': max_reservas_mes,
                    'cancelacion_limite': cancelacion_limite
                }
            }
            
            try:
                # Save configuration (you'll need to implement this in your data manager)
                # st.session_state.manager.save_config('areas_comunes_config', config_data)
                st.success("✅ Configuración guardada exitosamente")
            except Exception as e:
                st.error(f"❌ Error al guardar configuración: {str(e)}")

def show_sales_module():
    """Módulo de ventas de lotes"""
    st.markdown("## 🏡 Ventas de Lotes")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Catálogo", "📋 Gestión de Ventas", "👥 Clientes", "📊 Reportes"])
    
    with tab1:
        st.subheader("🏠 Catálogo de Lotes")
        
        # Agregar nuevo lote
        with st.expander("➕ Agregar Nuevo Lote"):
            with st.form("add_lot"):
                col1, col2 = st.columns(2)
                with col1:
                    lote_id = st.text_input("ID del Lote *")
                    area = st.number_input("Área (m²)", min_value=0.0, format="%.2f")
                    precio = st.number_input("Precio de Venta", min_value=0.0, format="%.2f")
                    ubicacion = st.text_input("Ubicación/Manzana")
                    
                with col2:
                    estado = st.selectbox("Estado", ["Disponible", "Reservado", "Vendido"])
                    tipo_lote = st.selectbox("Tipo", ["Residencial", "Comercial", "Esquina", "Interior"])
                    servicios = st.multiselect("Servicios Disponibles", 
                                             ["Agua", "Luz", "Gas", "Internet", "Alcantarillado"])
                
                descripcion = st.text_area("Descripción del Lote")
                
                if st.form_submit_button("✅ Agregar Lote"):
                    if lote_id and precio > 0:
                        # Simular agregado de lote (en implementación real iría a BD)
                        st.success(f"✅ Lote {lote_id} agregado exitosamente")
                    else:
                        st.error("⚠️ Complete los campos obligatorios")
    
    with tab2:
        with st.form("register_sale"):
            st.subheader("Registrar Nueva Venta")
            
            col1, col2 = st.columns(2)
            with col1:
                lote = st.text_input("ID del Lote *")
                cliente = st.text_input("Nombre del Cliente *")
                telefono = st.text_input("Teléfono")
                email = st.text_input("Email")
                
            with col2:
                precio = st.number_input("Precio de Venta", min_value=0.0, format="%.2f")
                estado = st.selectbox("Estado de la Venta", 
                                    ["Prospecto", "Reservado", "Vendido", "Cancelado"])
                fecha_venta = st.date_input("Fecha de Venta", datetime.now().date())
                forma_pago = st.selectbox("Forma de Pago", 
                                        ["Contado", "Financiado", "Crédito Bancario", "Mixto"])
            
            observaciones = st.text_area("Observaciones")
            
            if st.form_submit_button("✅ Registrar Venta"):
                if lote and cliente and precio > 0:
                    sale_id = f"VTA{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    data = {
                        'ID': sale_id,
                        'Lote': lote,
                        'Cliente': cliente,
                        'Telefono': telefono,
                        'Email': email,
                        'Precio': precio,
                        'Estado': estado,
                        'Fecha_Venta': fecha_venta.strftime('%Y-%m-%d'),
                        'Forma_Pago': forma_pago,
                        'Observaciones': observaciones
                    }
                    
                    if st.session_state.manager.save_data('ventas', data):
                        st.success("✅ Venta registrada exitosamente")
                    else:
                        st.error("❌ Error al registrar venta")
                else:
                    st.error("⚠️ Complete los campos obligatorios")
    
    with tab3:
        st.subheader("👥 Gestión de Clientes")
        ventas_df = st.session_state.manager.load_data('ventas')
        
        if not ventas_df.empty:
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filter_estado = st.selectbox("Estado:", 
                                           ["Todos"] + list(ventas_df['Estado'].unique()))
            with col2:
                search_cliente = st.text_input("Buscar Cliente:")
            
            # Aplicar filtros
            filtered_df = ventas_df.copy()
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_estado]
            if search_cliente:
                filtered_df = filtered_df[
                    filtered_df['Cliente'].str.contains(search_cliente, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Estadísticas de clientes
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Total Clientes", len(filtered_df))
            with col2:
                prospectos = len(filtered_df[filtered_df['Estado'] == 'Prospecto'])
                st.metric("🎯 Prospectos", prospectos)
            with col3:
                vendidos = len(filtered_df[filtered_df['Estado'] == 'Vendido'])
                st.metric("✅ Vendidos", vendidos)
            with col4:
                if len(filtered_df) > 0:
                    conversion = (vendidos / len(filtered_df)) * 100
                    st.metric("📈 Conversión", f"{conversion:.1f}%")
        else:
            st.info("📝 No hay ventas registradas")
    
    with tab4:
        st.subheader("📊 Reportes de Ventas")
        ventas_df = st.session_state.manager.load_data('ventas')
        
        if not ventas_df.empty:
            # Convertir precio a numérico si es string
            if 'Precio' in ventas_df.columns:
                ventas_df['Precio'] = pd.to_numeric(ventas_df['Precio'], errors='coerce')
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Ventas por estado
                estado_counts = ventas_df['Estado'].value_counts()
                fig = px.pie(values=estado_counts.values, names=estado_counts.index,
                           title="Distribución por Estado de Venta")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Ventas por forma de pago
                pago_counts = ventas_df['Forma_Pago'].value_counts()
                fig = px.bar(x=pago_counts.index, y=pago_counts.values,
                           title="Ventas por Forma de Pago",
                           labels={'x': 'Forma de Pago', 'y': 'Cantidad'})
                st.plotly_chart(fig, use_container_width=True)
            
            # Métricas principales
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_ventas = len(ventas_df)
                st.metric("📈 Total Ventas", total_ventas)
            
            with col2:
                ventas_realizadas = len(ventas_df[ventas_df['Estado'] == 'Vendido'])
                st.metric("✅ Ventas Realizadas", ventas_realizadas)
            
            with col3:
                if 'Precio' in ventas_df.columns:
                    ventas_vendidas = ventas_df[ventas_df['Estado'] == 'Vendido']
                    total_ingresos = ventas_vendidas['Precio'].sum()
                    st.metric("💰 Ingresos Totales", f"${total_ingresos:,.2f}")
                else:
                    st.metric("💰 Ingresos Totales", "N/A")
            
            with col4:
                if total_ventas > 0:
                    tasa_conversion = (ventas_realizadas / total_ventas) * 100
                    st.metric("📊 Tasa de Conversión", f"{tasa_conversion:.1f}%")
                else:
                    st.metric("📊 Tasa de Conversión", "0%")
            
            # Tabla resumen por mes (si existe fecha)
            if 'Fecha_Venta' in ventas_df.columns:
                st.subheader("📅 Resumen Mensual")
                try:
                    ventas_df['Fecha_Venta'] = pd.to_datetime(ventas_df['Fecha_Venta'])
                    ventas_df['Mes'] = ventas_df['Fecha_Venta'].dt.to_period('M')
                    
                    monthly_summary = ventas_df.groupby('Mes').agg({
                        'ID': 'count',
                        'Precio': 'sum'
                    }).rename(columns={'ID': 'Cantidad_Ventas', 'Precio': 'Ingresos_Mes'})
                    
                    if not monthly_summary.empty:
                        st.dataframe(monthly_summary, use_container_width=True)
                        
                        # Gráfico de tendencia mensual
                        fig = px.line(x=monthly_summary.index.astype(str), 
                                    y=monthly_summary['Cantidad_Ventas'],
                                    title="Tendencia de Ventas Mensuales",
                                    labels={'x': 'Mes', 'y': 'Cantidad de Ventas'})
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.warning(f"⚠️ Error al procesar fechas: {str(e)}")
        else:
            st.info("📝 No hay datos de ventas para mostrar reportes")
            
            # Mostrar métricas vacías
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📈 Total Ventas", 0)
            with col2:
                st.metric("✅ Ventas Realizadas", 0)
            with col3:
                st.metric("💰 Ingresos Totales", "$0.00")
            with col4:
                st.metric("📊 Tasa de Conversión", "0%")

if __name__ == "__main__":
    condominio_main()