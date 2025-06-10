import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, date
import time
import io
import zipfile
from typing import Dict, List, Any

# Configuración de la página
#st.set_page_config(
#    page_title="🛠️ Mantenimiento Gestión Conjuntos",
#    page_icon="🛠️",
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

#@st.cache_data(ttl=60)
def get_spreadsheet_info(client):
    """Obtener información completa del spreadsheet"""
    try:
        spreadsheet = client.open("gestion-conjuntos")
        
        # Información básica
        info = {
            'id': spreadsheet.id,
            'title': spreadsheet.title,
            'url': spreadsheet.url,
            'created_time': None,
            'modified_time': None,
            'worksheets': []
        }
        
        # Obtener información de cada hoja
        worksheets = spreadsheet.worksheets()
        for ws in worksheets:
            ws_info = {
                'id': ws.id,
                'title': ws.title,
                'row_count': ws.row_count,
                'col_count': ws.col_count,
                'cell_count': ws.row_count * ws.col_count,
                'has_data': False,
                'data_rows': 0
            }
            
            # Verificar si tiene datos
            try:
                all_values = ws.get_all_values()
                if all_values and any(any(row) for row in all_values):
                    ws_info['has_data'] = True
                    ws_info['data_rows'] = len([row for row in all_values if any(row)])
            except Exception:
                pass
            
            info['worksheets'].append(ws_info)
        
        return info, spreadsheet
    
    except Exception as e:
        st.error(f"❌ Error obteniendo información del spreadsheet: {str(e)}")
        return None, None

def backup_worksheet_to_csv(worksheet):
    """Crear backup de una hoja en formato CSV"""
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            return df.to_csv(index=False)
        else:
            # Si no hay registros, obtener valores raw
            values = worksheet.get_all_values()
            if values:
                df = pd.DataFrame(values[1:], columns=values[0])
                return df.to_csv(index=False)
            return ""
    except Exception as e:
        st.error(f"Error creando backup de {worksheet.title}: {str(e)}")
        return None

def create_full_backup(spreadsheet):
    """Crear backup completo de todas las hojas"""
    backup_files = {}
    
    try:
        worksheets = spreadsheet.worksheets()
        
        for ws in worksheets:
            csv_data = backup_worksheet_to_csv(ws)
            if csv_data is not None:
                backup_files[f"{ws.title}.csv"] = csv_data
            
        # Crear archivo ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in backup_files.items():
                zip_file.writestr(filename, content)
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    except Exception as e:
        st.error(f"❌ Error creando backup completo: {str(e)}")
        return None

def restore_worksheet_from_csv(worksheet, csv_content):
    """Restaurar datos de una hoja desde CSV"""
    try:
        # Leer CSV
        df = pd.read_csv(io.StringIO(csv_content))
        
        # Limpiar la hoja
        worksheet.clear()
        
        # Escribir encabezados
        headers = df.columns.tolist()
        worksheet.append_row(headers)
        
        # Escribir datos
        for _, row in df.iterrows():
            worksheet.append_row(row.tolist())
        
        return True
    
    except Exception as e:
        st.error(f"❌ Error restaurando datos: {str(e)}")
        return False

def create_new_worksheet(spreadsheet, name, headers=None):
    """Crear nueva hoja de trabajo"""
    try:
        # Verificar si ya existe
        try:
            existing_ws = spreadsheet.worksheet(name)
            st.warning(f"⚠️ La hoja '{name}' ya existe")
            return existing_ws
        except gspread.WorksheetNotFound:
            pass
        
        # Crear nueva hoja
        worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=26)
        
        # Agregar encabezados si se proporcionan
        if headers:
            worksheet.append_row(headers)
        
        st.success(f"✅ Hoja '{name}' creada exitosamente")
        return worksheet
    
    except Exception as e:
        st.error(f"❌ Error creando hoja '{name}': {str(e)}")
        return None

def delete_worksheet(spreadsheet, worksheet_name):
    """Eliminar hoja de trabajo"""
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        spreadsheet.del_worksheet(worksheet)
        st.success(f"✅ Hoja '{worksheet_name}' eliminada exitosamente")
        return True
    except Exception as e:
        st.error(f"❌ Error eliminando hoja '{worksheet_name}': {str(e)}")
        return False

def duplicate_worksheet(spreadsheet, source_name, target_name):
    """Duplicar hoja de trabajo"""
    try:
        source_ws = spreadsheet.worksheet(source_name)
        
        # Obtener todos los datos
        data = source_ws.get_all_values()
        
        # Crear nueva hoja
        target_ws = create_new_worksheet(spreadsheet, target_name)
        if target_ws:
            # Copiar datos
            if data:
                target_ws.clear()
                for row in data:
                    target_ws.append_row(row)
            
            st.success(f"✅ Hoja '{source_name}' duplicada como '{target_name}'")
            return True
        
        return False
    
    except Exception as e:
        st.error(f"❌ Error duplicando hoja: {str(e)}")
        return False

def analyze_worksheet_data(worksheet):
    """Analizar datos de una hoja específica"""
    try:
        data = worksheet.get_all_records()
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        analysis = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'empty_cells': df.isnull().sum().sum(),
            'duplicate_rows': df.duplicated().sum(),
            'column_info': {}
        }
        
        # Análisis por columna
        for col in df.columns:
            col_info = {
                'type': str(df[col].dtype),
                'unique_values': df[col].nunique(),
                'null_count': df[col].isnull().sum(),
                'sample_values': df[col].dropna().unique()[:5].tolist()
            }
            analysis['column_info'][col] = col_info
        
        return analysis
    
    except Exception as e:
        st.error(f"❌ Error analizando hoja: {str(e)}")
        return None

def mantenimiento_main():
    st.title("🛠️ Sistema de Mantenimiento")
    st.markdown("### Gestión de Archivos e Información - gestion-conjuntos")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Obtener información del spreadsheet
    spreadsheet_info, spreadsheet = get_spreadsheet_info(client)
    if not spreadsheet_info:
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("🛠️ Panel de Control")
    opcion = st.sidebar.selectbox(
        "Selecciona una opción:",
        [
            "📊 Dashboard General", 
            "📋 Gestión de Hojas", 
            "💾 Backups y Restauración",
            "🔧 Herramientas de Datos",
            "📈 Análisis y Reportes",
            "⚙️ Configuración Avanzada"
        ]
    )
    
    if opcion == "📊 Dashboard General":
        st.header("📊 Dashboard General del Sistema")
        
        # Información del archivo
        st.subheader("📄 Información del Archivo")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📑 Total de Hojas", len(spreadsheet_info['worksheets']))
        with col2:
            total_rows = sum(ws['data_rows'] for ws in spreadsheet_info['worksheets'])
            st.metric("📊 Total de Registros", total_rows)
        with col3:
            hojas_con_datos = len([ws for ws in spreadsheet_info['worksheets'] if ws['has_data']])
            st.metric("✅ Hojas con Datos", hojas_con_datos)
        
        # Información detallada
        st.subheader("📋 Detalle de Hojas de Trabajo")
        
        # Crear DataFrame para mostrar información
        ws_data = []
        for ws in spreadsheet_info['worksheets']:
            ws_data.append({
                'Hoja': ws['title'],
                'Filas': ws['row_count'],
                'Columnas': ws['col_count'],
                'Registros con Datos': ws['data_rows'],
                'Estado': '✅ Con datos' if ws['has_data'] else '⭕ Vacía'
            })
        
        df_worksheets = pd.DataFrame(ws_data)
        st.dataframe(df_worksheets, use_container_width=True, hide_index=True)
        
        # Enlaces útiles
        st.subheader("🔗 Enlaces de Acceso")
        st.markdown(f"**📎 URL del Archivo:** [Abrir en Google Sheets]({spreadsheet_info['url']})")
        st.markdown(f"**🆔 ID del Archivo:** `{spreadsheet_info['id']}`")
        
        # Gráfico de distribución de datos
        if ws_data:
            st.subheader("📈 Distribución de Registros por Hoja")
            chart_data = pd.DataFrame({
                'Hoja': [ws['Hoja'] for ws in ws_data if ws['Registros con Datos'] > 0],
                'Registros': [ws['Registros con Datos'] for ws in ws_data if ws['Registros con Datos'] > 0]
            })
            if not chart_data.empty:
                st.bar_chart(chart_data.set_index('Hoja'))
    
    elif opcion == "📋 Gestión de Hojas":
        st.header("📋 Gestión de Hojas de Trabajo")
        
        # Tabs para diferentes operaciones
        tab1, tab2, tab3, tab4 = st.tabs(["➕ Crear Hoja", "🗑️ Eliminar Hoja", "📄 Duplicar Hoja", "✏️ Renombrar Hoja"])
        
        with tab1:
            st.subheader("➕ Crear Nueva Hoja")
            
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre de la nueva hoja", placeholder="Ej: Inquilinos, Gastos, etc.")
            
            with col2:
                plantilla = st.selectbox(
                    "Plantilla",
                    ["Personalizada", "Correspondencia", "Residentes", "Gastos", "Mantenimiento", "Reuniones"]
                )
            
            # Plantillas predefinidas
            plantillas = {
                "Correspondencia": ["ID", "Fecha_Recepcion", "Destinatario", "Apartamento", "Torre", "Tipo_Correspondencia", "Estado"],
                "Residentes": ["ID", "Nombre", "Apartamento", "Torre", "Telefono", "Email", "Fecha_Ingreso", "Estado"],
                "Gastos": ["ID", "Fecha", "Concepto", "Categoria", "Monto", "Responsable", "Estado", "Observaciones"],
                "Mantenimiento": ["ID", "Fecha_Solicitud", "Apartamento", "Tipo_Mantenimiento", "Descripcion", "Estado", "Fecha_Resolucion"],
                "Reuniones": ["ID", "Fecha", "Tipo_Reunion", "Participantes", "Temas", "Decisiones", "Compromisos"]
            }
            
            if plantilla != "Personalizada":
                st.info(f"📋 Columnas para {plantilla}: {', '.join(plantillas[plantilla])}")
            else:
                columnas_personalizadas = st.text_input(
                    "Columnas (separadas por coma)",
                    placeholder="Nombre, Apellido, Telefono, Email"
                )
            
            if st.button("➕ Crear Hoja", type="primary"):
                if nuevo_nombre:
                    headers = None
                    if plantilla != "Personalizada":
                        headers = plantillas[plantilla]
                    elif columnas_personalizadas:
                        headers = [col.strip() for col in columnas_personalizadas.split(',')]
                    
                    if create_new_worksheet(spreadsheet, nuevo_nombre, headers):
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("❌ Ingresa un nombre para la hoja")
        
        with tab2:
            st.subheader("🗑️ Eliminar Hoja")
            st.warning("⚠️ Esta acción es irreversible. Asegúrate de tener backups.")
            
            hoja_eliminar = st.selectbox(
                "Selecciona la hoja a eliminar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            confirmacion = st.text_input(
                f"Para confirmar, escribe: {hoja_eliminar}",
                placeholder="Escribe el nombre exacto de la hoja"
            )
            
            if st.button("🗑️ Eliminar Hoja", type="secondary"):
                if confirmacion == hoja_eliminar:
                    if delete_worksheet(spreadsheet, hoja_eliminar):
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("❌ El nombre no coincide")
        
        with tab3:
            st.subheader("📄 Duplicar Hoja")
            
            col1, col2 = st.columns(2)
            with col1:
                hoja_origen = st.selectbox(
                    "Hoja origen",
                    [ws['title'] for ws in spreadsheet_info['worksheets']]
                )
            
            with col2:
                nombre_duplicado = st.text_input(
                    "Nombre para la copia",
                    value=f"{hoja_origen}_copia" if hoja_origen else ""
                )
            
            if st.button("📄 Duplicar Hoja", type="primary"):
                if hoja_origen and nombre_duplicado:
                    if duplicate_worksheet(spreadsheet, hoja_origen, nombre_duplicado):
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("❌ Completa todos los campos")
        
        with tab4:
            st.subheader("✏️ Renombrar Hoja")
            
            col1, col2 = st.columns(2)
            with col1:
                hoja_renombrar = st.selectbox(
                    "Hoja a renombrar",
                    [ws['title'] for ws in spreadsheet_info['worksheets']]
                )
            
            with col2:
                nuevo_nombre_hoja = st.text_input("Nuevo nombre")
            
            if st.button("✏️ Renombrar Hoja", type="primary"):
                if hoja_renombrar and nuevo_nombre_hoja:
                    try:
                        worksheet = spreadsheet.worksheet(hoja_renombrar)
                        worksheet.update_title(nuevo_nombre_hoja)
                        st.success(f"✅ Hoja renombrada de '{hoja_renombrar}' a '{nuevo_nombre_hoja}'")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error renombrando hoja: {str(e)}")
                else:
                    st.error("❌ Completa todos los campos")
    
    elif opcion == "💾 Backups y Restauración":
        st.header("💾 Backups y Restauración")
        
        tab1, tab2, tab3 = st.tabs(["💾 Crear Backup", "📥 Restaurar Datos", "🗂️ Gestión de Backups"])
        
        with tab1:
            st.subheader("💾 Crear Backup")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📄 Backup Individual")
                hoja_backup = st.selectbox(
                    "Selecciona hoja para backup",
                    [ws['title'] for ws in spreadsheet_info['worksheets']]
                )
                
                if st.button("💾 Descargar CSV", key="backup_individual"):
                    if hoja_backup:
                        try:
                            worksheet = spreadsheet.worksheet(hoja_backup)
                            csv_data = backup_worksheet_to_csv(worksheet)
                            if csv_data:
                                st.download_button(
                                    label="📥 Descargar Backup",
                                    data=csv_data,
                                    file_name=f"{hoja_backup}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.warning("⚠️ La hoja está vacía")
                        except Exception as e:
                            st.error(f"❌ Error creando backup: {str(e)}")
            
            with col2:
                st.markdown("#### 📦 Backup Completo")
                st.info("Descarga todas las hojas en un archivo ZIP")
                
                if st.button("📦 Crear Backup Completo", key="backup_completo"):
                    with st.spinner("Creando backup completo..."):
                        zip_data = create_full_backup(spreadsheet)
                        if zip_data:
                            st.download_button(
                                label="📥 Descargar Backup Completo",
                                data=zip_data,
                                file_name=f"gestion_conjuntos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                                mime="application/zip"
                            )
        
        with tab2:
            st.subheader("📥 Restaurar Datos")
            st.warning("⚠️ La restauración reemplazará todos los datos existentes en la hoja seleccionada.")
            
            hoja_restaurar = st.selectbox(
                "Selecciona hoja a restaurar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            archivo_csv = st.file_uploader(
                "Sube archivo CSV para restaurar",
                type=['csv'],
                help="El archivo debe tener el mismo formato que el backup original"
            )
            
            if archivo_csv and hoja_restaurar:
                # Mostrar preview
                try:
                    csv_content = archivo_csv.getvalue().decode('utf-8')
                    df_preview = pd.read_csv(io.StringIO(csv_content))
                    
                    st.markdown("#### 👀 Preview de los datos a restaurar:")
                    st.dataframe(df_preview.head(), use_container_width=True)
                    st.info(f"📊 El archivo contiene {len(df_preview)} registros y {len(df_preview.columns)} columnas")
                    
                    if st.button("📥 Restaurar Datos", type="secondary"):
                        try:
                            worksheet = spreadsheet.worksheet(hoja_restaurar)
                            if restore_worksheet_from_csv(worksheet, csv_content):
                                st.success(f"✅ Datos restaurados exitosamente en '{hoja_restaurar}'")
                                st.cache_data.clear()
                            else:
                                st.error("❌ Error restaurando datos")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                
                except Exception as e:
                    st.error(f"❌ Error leyendo archivo CSV: {str(e)}")
        
        with tab3:
            st.subheader("🗂️ Gestión de Backups")
            
            # Programar backups automáticos (información)
            st.markdown("#### ⏰ Programación de Backups")
            st.info("""
            💡 **Recomendaciones para Backups:**
            - Realiza backups semanales de todas las hojas
            - Guarda backups antes de operaciones masivas
            - Mantén al menos 3 versiones de backup
            - Almacena backups en ubicaciones seguras
            """)
            
            # Verificación de integridad
            st.markdown("#### 🔍 Verificación de Integridad")
            if st.button("🔍 Verificar Integridad de Datos"):
                with st.spinner("Verificando integridad..."):
                    problemas = []
                    
                    for ws_info in spreadsheet_info['worksheets']:
                        try:
                            worksheet = spreadsheet.worksheet(ws_info['title'])
                            data = worksheet.get_all_values()
                            
                            # Verificaciones básicas
                            if not data:
                                problemas.append(f"⚠️ {ws_info['title']}: Hoja completamente vacía")
                            elif len(data) == 1:
                                problemas.append(f"ℹ️ {ws_info['title']}: Solo contiene encabezados")
                            
                        except Exception as e:
                            problemas.append(f"❌ {ws_info['title']}: Error accediendo - {str(e)}")
                    
                    if problemas:
                        st.warning("⚠️ Problemas encontrados:")
                        for problema in problemas:
                            st.write(f"- {problema}")
                    else:
                        st.success("✅ Todas las hojas están en buen estado")
    
    elif opcion == "🔧 Herramientas de Datos":
        st.header("🔧 Herramientas de Datos")
        
        tab1, tab2, tab3 = st.tabs(["🧹 Limpieza de Datos", "🔄 Transformaciones", "📊 Validaciones"])
        
        with tab1:
            st.subheader("🧹 Limpieza de Datos")
            
            hoja_limpiar = st.selectbox(
                "Selecciona hoja para limpiar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            if hoja_limpiar:
                try:
                    worksheet = spreadsheet.worksheet(hoja_limpiar)
                    data = worksheet.get_all_records()
                    
                    if data:
                        df = pd.DataFrame(data)
                        
                        st.markdown("#### 📊 Estadísticas actuales:")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total de filas", len(df))
                        with col2:
                            filas_vacias = df.isnull().all(axis=1).sum()
                            st.metric("Filas completamente vacías", filas_vacias)
                        with col3:
                            celdas_vacias = df.isnull().sum().sum()
                            st.metric("Celdas vacías", celdas_vacias)
                        
                        # Opciones de limpieza
                        st.markdown("#### 🛠️ Opciones de limpieza:")
                        limpiar_filas_vacias = st.checkbox("Eliminar filas completamente vacías")
                        limpiar_espacios = st.checkbox("Eliminar espacios extra")
                        limpiar_duplicados = st.checkbox("Eliminar filas duplicadas")
                        
                        if st.button("🧹 Aplicar Limpieza"):
                            df_limpio = df.copy()
                            
                            if limpiar_filas_vacias:
                                df_limpio = df_limpio.dropna(how='all')
                            
                            if limpiar_espacios:
                                for col in df_limpio.select_dtypes(include=['object']).columns:
                                    df_limpio[col] = df_limpio[col].astype(str).str.strip()
                            
                            if limpiar_duplicados:
                                df_limpio = df_limpio.drop_duplicates()
                            
                            # Actualizar la hoja
                            try:
                                worksheet.clear()
                                worksheet.append_row(df_limpio.columns.tolist())
                                for _, row in df_limpio.iterrows():
                                    worksheet.append_row(row.tolist())
                                
                                st.success(f"✅ Limpieza aplicada. Filas finales: {len(df_limpio)}")
                                st.cache_data.clear()
                            
                            except Exception as e:
                                st.error(f"❌ Error aplicando limpieza: {str(e)}")
                    else:
                        st.info("ℹ️ La hoja no contiene datos")
                
                except Exception as e:
                    st.error(f"❌ Error accediendo a la hoja: {str(e)}")
        
        with tab2:
            st.subheader("🔄 Transformaciones de Datos")
            
            hoja_transformar = st.selectbox(
                "Selecciona hoja para transformar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            if hoja_transformar:
                try:
                    worksheet = spreadsheet.worksheet(hoja_transformar)
                    data = worksheet.get_all_records()
                    
                    if data:
                        df = pd.DataFrame(data)
                        
                        st.markdown("#### 🔄 Opciones de transformación:")
                        
                        # Transformaciones disponibles
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Transformaciones de texto:**")
                            mayusculas = st.checkbox("Convertir texto a mayúsculas")
                            minusculas = st.checkbox("Convertir texto a minúsculas")
                            capitalizar = st.checkbox("Capitalizar primera letra")
                        
                        with col2:
                            st.markdown("**Transformaciones de datos:**")
                            rellenar_vacios = st.checkbox("Rellenar celdas vacías")
                            if rellenar_vacios:
                                valor_relleno = st.text_input("Valor para rellenar", value="N/A")
                        
                        # Selección de columnas
                        columnas_disponibles = df.columns.tolist()
                        columnas_seleccionadas = st.multiselect(
                            "Selecciona columnas a transformar (vacío = todas)",
                            columnas_disponibles
                        )
                        
                        if not columnas_seleccionadas:
                            columnas_seleccionadas = columnas_disponibles
                        
                        if st.button("🔄 Aplicar Transformaciones"):
                            df_transformado = df.copy()
                            
                            for col in columnas_seleccionadas:
                                if col in df_transformado.columns:
                                    if mayusculas and df_transformado[col].dtype == 'object':
                                        df_transformado[col] = df_transformado[col].astype(str).str.upper()
                                    elif minusculas and df_transformado[col].dtype == 'object':
                                        df_transformado[col] = df_transformado[col].astype(str).str.lower()
                                    elif capitalizar and df_transformado[col].dtype == 'object':
                                        df_transformado[col] = df_transformado[col].astype(str).str.title()
                                    
                                    if rellenar_vacios:
                                        df_transformado[col] = df_transformado[col].fillna(valor_relleno)
                            
                            # Actualizar la hoja
                            try:
                                worksheet.clear()
                                worksheet.append_row(df_transformado.columns.tolist())
                                for _, row in df_transformado.iterrows():
                                    worksheet.append_row(row.tolist())
                                
                                st.success("✅ Transformaciones aplicadas exitosamente")
                                st.cache_data.clear()
                            
                            except Exception as e:
                                st.error(f"❌ Error aplicando transformaciones: {str(e)}")
                    else:
                        st.info("ℹ️ La hoja no contiene datos")
                
                except Exception as e:
                    st.error(f"❌ Error accediendo a la hoja: {str(e)}")
        
        with tab3:
            st.subheader("📊 Validaciones de Datos")
            
            hoja_validar = st.selectbox(
                "Selecciona hoja para validar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            if hoja_validar:
                try:
                    worksheet = spreadsheet.worksheet(hoja_validar)
                    data = worksheet.get_all_records()
                    
                    if data:
                        df = pd.DataFrame(data)
                        
                        st.markdown("#### 🔍 Validaciones disponibles:")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            validar_vacios = st.checkbox("Detectar campos vacíos")
                            validar_duplicados = st.checkbox("Detectar duplicados")
                            validar_formato_email = st.checkbox("Validar formato de email")
                        
                        with col2:
                            validar_numeros = st.checkbox("Validar campos numéricos")
                            validar_fechas = st.checkbox("Validar formato de fechas")
                            validar_longitud = st.checkbox("Validar longitud de texto")
                        
                        if st.button("📊 Ejecutar Validaciones"):
                            problemas = []
                            
                            # Validar campos vacíos
                            if validar_vacios:
                                for col in df.columns:
                                    vacios = df[col].isnull().sum()
                                    if vacios > 0:
                                        problemas.append(f"⚠️ {col}: {vacios} campos vacíos")
                            
                            # Validar duplicados
                            if validar_duplicados:
                                duplicados = df.duplicated().sum()
                                if duplicados > 0:
                                    problemas.append(f"⚠️ {duplicados} filas duplicadas encontradas")
                            
                            # Validar emails
                            if validar_formato_email:
                                email_cols = [col for col in df.columns if 'email' in col.lower() or 'correo' in col.lower()]
                                for col in email_cols:
                                    if col in df.columns:
                                        emails_invalidos = df[~df[col].astype(str).str.contains(r'^[^@]+@[^@]+\.[^@]+$', na=False)]
                                        if len(emails_invalidos) > 0:
                                            problemas.append(f"⚠️ {col}: {len(emails_invalidos)} emails con formato inválido")
                            
                            # Validar números
                            if validar_numeros:
                                numeric_cols = df.select_dtypes(include=['object']).columns
                                for col in numeric_cols:
                                    try:
                                        pd.to_numeric(df[col], errors='raise')
                                    except:
                                        problemas.append(f"⚠️ {col}: Contiene valores no numéricos")
                            
                            # Mostrar resultados
                            if problemas:
                                st.warning("⚠️ Problemas de validación encontrados:")
                                for problema in problemas:
                                    st.write(f"- {problema}")
                            else:
                                st.success("✅ Todas las validaciones pasaron exitosamente")
                    else:
                        st.info("ℹ️ La hoja no contiene datos")
                
                except Exception as e:
                    st.error(f"❌ Error accediendo a la hoja: {str(e)}")
    
    elif opcion == "📈 Análisis y Reportes":
        st.header("📈 Análisis y Reportes")
        
        tab1, tab2, tab3 = st.tabs(["📊 Estadísticas", "📈 Gráficos", "📋 Reportes"])
        
        with tab1:
            st.subheader("📊 Análisis Estadístico")
            
            hoja_analizar = st.selectbox(
                "Selecciona hoja para analizar",
                [ws['title'] for ws in spreadsheet_info['worksheets']]
            )
            
            if hoja_analizar:
                try:
                    worksheet = spreadsheet.worksheet(hoja_analizar)
                    data = worksheet.get_all_records()
                    
                    if data:
                        df = pd.DataFrame(data)
                        
                        # Estadísticas generales
                        st.markdown("#### 📊 Estadísticas Generales")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total de Registros", len(df))
                        with col2:
                            st.metric("Total de Columnas", len(df.columns))
                        with col3:
                            st.metric("Registros Completos", len(df.dropna()))
                        with col4:
                            completitud = (1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
                            st.metric("Completitud", f"{completitud:.1f}%")
                        
                        # Análisis por columna
                        st.markdown("#### 📋 Análisis por Columna")
                        
                        columna_analizar = st.selectbox(
                            "Selecciona columna para análisis detallado",
                            df.columns.tolist()
                        )
                        
                        if columna_analizar:
                            col_data = df[columna_analizar]
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"**Estadísticas de: {columna_analizar}**")
                                st.write(f"- Valores únicos: {col_data.nunique()}")
                                st.write(f"- Valores nulos: {col_data.isnull().sum()}")
                                st.write(f"- Tipo de datos: {col_data.dtype}")
                                
                                if col_data.dtype in ['int64', 'float64']:
                                    st.write(f"- Media: {col_data.mean():.2f}")
                                    st.write(f"- Mediana: {col_data.median():.2f}")
                                    st.write(f"- Desviación estándar: {col_data.std():.2f}")
                            
                            with col2:
                                st.markdown("**Valores más frecuentes:**")
                                top_values = col_data.value_counts().head(10)
                                st.dataframe(top_values, use_container_width=True)
                    else:
                        st.info("ℹ️ La hoja no contiene datos")
                
                except Exception as e:
                    st.error(f"❌ Error analizando datos: {str(e)}")
        
        with tab2:
            st.subheader("📈 Visualizaciones")
            
            hoja_graficar = st.selectbox(
                "Selecciona hoja para graficar",
                [ws['title'] for ws in spreadsheet_info['worksheets']],
                key="hoja_graficar"
            )
            
            if hoja_graficar:
                try:
                    worksheet = spreadsheet.worksheet(hoja_graficar)
                    data = worksheet.get_all_records()
                    
                    if data:
                         df = pd.DataFrame(data)

                except Exception as e:
                    st.error(f"❌ Error analizando datos: {str(e)}")

        with tab3:
            pass

#if __name__ == "__main__":
#    mantenimiento_main()