import streamlit as st
import pandas as pd
import gspread
import toml
import json
from google.oauth2.service_account import Credentials
from datetime import datetime
import io

# Configuración de la página
st.set_page_config(
    page_title="Gestor de Residentes",
    page_icon="🏠",
    layout="wide"
)

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

def validate_dataframe(df):
    """Validar que el DataFrame tenga las columnas obligatorias"""
    required_columns = [
        'Identificacion', 'Nombre', 'Apellido', 'Tipo_Unidad', 'Unidad', 'Tipo'
    ]
    
    # Verificar columnas faltantes
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        return False, missing_columns
    
    return True, []

def generate_next_id(existing_data):
    """Generar el próximo ID disponible"""
    if not existing_data:
        return 1
    
    existing_ids = []
    for row in existing_data:
        try:
            if row.get('ID'):
                existing_ids.append(int(row['ID']))
        except (ValueError, TypeError):
            continue
    
    return max(existing_ids) + 1 if existing_ids else 1

def prepare_dataframe_for_sheets(df, existing_data):
    """Preparar DataFrame con IDs automáticos y columnas completas"""
    # Crear una copia para no modificar el original
    prepared_df = df.copy()
    
    # Definir todas las columnas en el orden correcto
    all_columns = [
        'ID', 'Identificacion', 'Nombre', 'Apellido', 'Tipo_Unidad', 
        'Unidad', 'Tipo', 'Telefono', 'Email', 'Fecha_Ingreso', 
        'Estado', 'Observaciones'
    ]
    
    # Agregar columnas faltantes con valores por defecto
    for col in all_columns:
        if col not in prepared_df.columns:
            if col == 'ID':
                continue  # Se agregará después
            elif col == 'Fecha_Ingreso':
                prepared_df[col] = datetime.now().strftime('%Y-%m-%d')
            elif col == 'Estado':
                prepared_df[col] = 'Activo'
            else:
                prepared_df[col] = ''
    
    # Reemplazar NaN con cadenas vacías
    prepared_df = prepared_df.fillna('')
    
    # Generar IDs automáticos
    next_id = generate_next_id(existing_data)
    prepared_df['ID'] = range(next_id, next_id + len(prepared_df))
    
    # Reordenar columnas
    prepared_df = prepared_df[all_columns]
    
    # Convertir fechas al formato correcto
    if 'Fecha_Ingreso' in prepared_df.columns:
        prepared_df['Fecha_Ingreso'] = pd.to_datetime(
            prepared_df['Fecha_Ingreso'], 
            errors='coerce'
        ).dt.strftime('%Y-%m-%d')
        prepared_df['Fecha_Ingreso'] = prepared_df['Fecha_Ingreso'].fillna(datetime.now().strftime('%Y-%m-%d'))
    
    # Asegurar que todas las columnas sean strings para Google Sheets
    for col in prepared_df.columns:
        prepared_df[col] = prepared_df[col].astype(str)
    
    return prepared_df

def get_existing_data(client, sheet_name, worksheet_name):
    """Obtener datos existentes de Google Sheets"""
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        existing_data = worksheet.get_all_records()
        return existing_data, worksheet
    except gspread.SpreadsheetNotFound:
        st.error(f"❌ No se encontró la hoja '{sheet_name}'. Verifica el nombre.")
        return None, None
    except gspread.WorksheetNotFound:
        st.error(f"❌ No se encontró la hoja de trabajo '{worksheet_name}' en '{sheet_name}'")
        return None, None
    except Exception as e:
        st.error(f"❌ Error obteniendo datos existentes: {str(e)}")
        return None, None

def insert_new_records(worksheet, df, existing_data):
    """Insertar nuevos registros (basado en Identificacion + Unidad)"""
    try:
        # Crear conjunto de combinaciones existentes (Identificacion + Unidad)
        existing_combinations = set()
        for row in existing_data:
            if row.get('Identificacion') and row.get('Unidad'):
                combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                existing_combinations.add(combination)
        
        new_records = []
        duplicate_count = 0
        
        for _, row in df.iterrows():
            combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
            if combination not in existing_combinations:
                new_records.append(row.tolist())
            else:
                duplicate_count += 1
        
        if new_records:
            for record in new_records:
                worksheet.append_row(record)
            
            return len(new_records), duplicate_count
        else:
            return 0, duplicate_count
            
    except Exception as e:
        st.error(f"❌ Error insertando registros: {str(e)}")
        return 0, 0

def update_existing_records(worksheet, df, existing_data):
    """Actualizar registros existentes basado en Identificacion + Unidad"""
    try:
        # Crear un mapa de combinaciones existentes (Identificacion + Unidad) con sus filas
        combination_to_row = {}
        for i, row in enumerate(existing_data):
            if row.get('Identificacion') and row.get('Unidad'):
                combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                combination_to_row[combination] = i + 2  # +2 porque las filas empiezan en 1 y hay encabezado
        
        updated_count = 0
        
        for _, row in df.iterrows():
            combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
            if combination in combination_to_row:
                row_number = combination_to_row[combination]
                
                # Actualizar cada celda de la fila
                for col_index, value in enumerate(row.tolist()):
                    worksheet.update_cell(row_number, col_index + 1, value)
                
                updated_count += 1
        
        return updated_count
        
    except Exception as e:
        st.error(f"❌ Error actualizando registros: {str(e)}")
        return 0

def delete_records(worksheet, combinations_to_delete, existing_data):
    """Eliminar registros basado en combinaciones Identificacion + Unidad"""
    try:
        # Encontrar las filas a eliminar (en orden descendente para no afectar los índices)
        rows_to_delete = []
        for i, row in enumerate(existing_data):
            if row.get('Identificacion') and row.get('Unidad'):
                combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                if combination in combinations_to_delete:
                    rows_to_delete.append(i + 2)  # +2 porque las filas empiezan en 1 y hay encabezado
        
        # Eliminar en orden descendente
        rows_to_delete.sort(reverse=True)
        
        for row_number in rows_to_delete:
            worksheet.delete_rows(row_number)
        
        return len(rows_to_delete)
        
    except Exception as e:
        st.error(f"❌ Error eliminando registros: {str(e)}")
        return 0

def load_file(uploaded_file):
    """Cargar archivo CSV o Excel y convertir a DataFrame"""
    try:
        if uploaded_file.name.endswith('.csv'):
            # Intentar diferentes encodings para CSV
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)  # Volver al inicio del archivo
                df = pd.read_csv(uploaded_file, encoding='latin-1')
        
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        
        else:
            st.error("❌ Formato de archivo no soportado. Use CSV o Excel.")
            return None
        
        return df
    
    except Exception as e:
        st.error(f"❌ Error cargando el archivo: {str(e)}")
        return None

def show_data_management_section(client, sheet_name, worksheet_name):
    """Mostrar sección de gestión de datos existentes"""
    st.markdown("### 🗂️ Gestión de Datos Existentes")
    
    if st.button("🔄 Cargar datos existentes", type="secondary"):
        with st.spinner("📊 Cargando datos existentes..."):
            existing_data, worksheet = get_existing_data(client, sheet_name, worksheet_name)
            
            if existing_data and worksheet:
                df_existing = pd.DataFrame(existing_data)
                
                st.success(f"✅ {len(existing_data)} registros cargados")
                st.dataframe(df_existing, use_container_width=True)
                
                # Mostrar opciones de eliminación
                st.markdown("#### ❌ Eliminar Registros")
                
                if len(existing_data) > 0:
                    # Crear opciones con formato "Identificacion - Unidad (Nombre Apellido)"
                    deletion_options = []
                    combination_map = {}
                    
                    for row in existing_data:
                        if row.get('Identificacion') and row.get('Unidad'):
                            combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                            display_name = f"{row.get('Identificacion', '')} - {row.get('Unidad', '')} ({row.get('Nombre', '')} {row.get('Apellido', '')})"
                            deletion_options.append(display_name)
                            combination_map[display_name] = combination
                    
                    if deletion_options:
                        selected_options = st.multiselect(
                            "Selecciona los registros a eliminar:",
                            deletion_options,
                            help="Formato: Identificación - Unidad (Nombre Apellido)"
                        )
                        
                        if selected_options:
                            selected_combinations = [combination_map[option] for option in selected_options]
                            st.warning(f"⚠️ Se eliminarán {len(selected_combinations)} registros")
                            
                            # Mostrar detalles de los registros a eliminar
                            st.markdown("**Registros a eliminar:**")
                            for option in selected_options:
                                st.write(f"• {option}")
                            
                            if st.button("🗑️ Confirmar Eliminación", type="primary"):
                                with st.spinner("🗑️ Eliminando registros..."):
                                    deleted_count = delete_records(worksheet, selected_combinations, existing_data)
                                    
                                if deleted_count > 0:
                                    st.success(f"✅ {deleted_count} registros eliminados exitosamente")
                                    st.rerun()
                                else:
                                    st.error("❌ No se pudieron eliminar los registros")
                    else:
                        st.info("ℹ️ No hay registros válidos para eliminar (faltan Identificación o Unidad)")
                else:
                    st.info("ℹ️ No hay registros existentes")

def main():
    st.title("🏠 Gestor de Residentes - Conjunto")
    st.markdown("---")
    
    # Cargar credenciales
    with st.spinner("🔐 Cargando credenciales..."):
        creds, config = load_credentials_from_toml()
    
    if not creds:
        st.stop()
    
    # Establecer conexión
    with st.spinner("🔗 Conectando a Google Sheets..."):
        client = get_google_sheets_connection(creds)
    
    if not client:
        st.stop()
    
    # Configuración de hojas
    st.sidebar.markdown("### ⚙️ Configuración")
    sheet_name = st.sidebar.text_input("Nombre de la hoja de cálculo:", value="gestion-conjuntos")
    worksheet_name = st.sidebar.text_input("Nombre de la hoja de trabajo:", value="Control_Residentes")
    
    # Tabs para diferentes operaciones
    tab1, tab2, tab3 = st.tabs(["📤 Cargar Datos", "🔄 Actualizar Datos", "🗂️ Gestionar Datos"])
    
    with tab1:
        st.markdown("### 📤 Cargar Nuevos Residentes")
        
        # Upload de archivo
        uploaded_file = st.file_uploader(
            "Selecciona un archivo CSV o Excel",
            type=['csv', 'xlsx', 'xls'],
            help="Columnas obligatorias: Identificacion, Nombre, Apellido, Tipo_Unidad, Unidad, Tipo",
            key="upload_new"
        )
        
        if uploaded_file is not None:
            # Mostrar información del archivo
            st.info(f"📄 Archivo seleccionado: {uploaded_file.name} ({uploaded_file.size} bytes)")
            
            # Cargar archivo
            with st.spinner("📖 Cargando archivo..."):
                df = load_file(uploaded_file)
            
            if df is not None:
                st.success(f"✅ Archivo cargado: {len(df)} filas, {len(df.columns)} columnas")
                
                # Mostrar las primeras filas
                st.markdown("#### 👀 Vista previa de los datos:")
                st.dataframe(df.head(), use_container_width=True)
                
                # Validar estructura
                st.markdown("#### 🔍 Validación de estructura:")
                is_valid, missing_cols = validate_dataframe(df)
                
                if is_valid:
                    st.success("✅ Estructura del archivo correcta")
                    
                    # Obtener datos existentes y preparar DataFrame
                    with st.spinner("📊 Preparando datos..."):
                        existing_data, worksheet = get_existing_data(client, sheet_name, worksheet_name)
                        
                        if existing_data is not None and worksheet is not None:
                            prepared_df = prepare_dataframe_for_sheets(df, existing_data)
                            
                            # Mostrar estadísticas
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Registros a procesar", len(prepared_df))
                            with col2:
                                st.metric("Próximo ID", prepared_df['ID'].iloc[0] if len(prepared_df) > 0 else "N/A")
                            with col3:
                                st.metric("Registros existentes", len(existing_data))
                            
                            # Botón para insertar
                            if st.button("🚀 Insertar nuevos registros", type="primary", use_container_width=True):
                                with st.spinner("⬆️ Insertando datos..."):
                                    inserted_count, duplicate_count = insert_new_records(worksheet, prepared_df, existing_data)
                                
                                if inserted_count > 0:
                                    st.balloons()
                                    st.success(f"🎉 {inserted_count} registros insertados exitosamente!")
                                    if duplicate_count > 0:
                                        st.warning(f"⚠️ {duplicate_count} registros duplicados fueron omitidos")
                                else:
                                    st.warning("⚠️ No hay registros nuevos para insertar")
                
                else:
                    st.error("❌ Estructura del archivo incorrecta")
                    st.error(f"Columnas obligatorias faltantes: {', '.join(missing_cols)}")
    
    with tab2:
        st.markdown("### 🔄 Actualizar Residentes Existentes")
        
        uploaded_file_update = st.file_uploader(
            "Selecciona un archivo CSV o Excel para actualizar",
            type=['csv', 'xlsx', 'xls'],
            help="Los registros se actualizarán basándose en la combinación de Identificación + Unidad",
            key="upload_update"
        )
        
        if uploaded_file_update is not None:
            st.info(f"📄 Archivo seleccionado: {uploaded_file_update.name}")
            
            with st.spinner("📖 Cargando archivo..."):
                df_update = load_file(uploaded_file_update)
            
            if df_update is not None:
                st.success(f"✅ Archivo cargado: {len(df_update)} filas")
                st.dataframe(df_update.head(), use_container_width=True)
                
                is_valid, missing_cols = validate_dataframe(df_update)
                
                if is_valid:
                    st.success("✅ Estructura del archivo correcta")
                    
                    with st.spinner("📊 Preparando actualización..."):
                        existing_data, worksheet = get_existing_data(client, sheet_name, worksheet_name)
                        
                        if existing_data is not None and worksheet is not None:
                            prepared_df_update = prepare_dataframe_for_sheets(df_update, existing_data)
                            
                            # Verificar cuántos registros se pueden actualizar
                            existing_combinations = set()
                            for row in existing_data:
                                if row.get('Identificacion') and row.get('Unidad'):
                                    combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                                    existing_combinations.add(combination)
                            
                            update_combinations = set()
                            for _, row in df_update.iterrows():
                                combination = f"{str(row['Identificacion'])}_{str(row['Unidad'])}"
                                update_combinations.add(combination)
                            
                            updatable = len(update_combinations.intersection(existing_combinations))
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Registros actualizables", updatable)
                            with col2:
                                st.metric("Registros en archivo", len(df_update))
                            
                            if updatable > 0:
                                if st.button("🔄 Actualizar registros existentes", type="primary", use_container_width=True):
                                    with st.spinner("🔄 Actualizando datos..."):
                                        updated_count = update_existing_records(worksheet, prepared_df_update, existing_data)
                                    
                                    if updated_count > 0:
                                        st.success(f"✅ {updated_count} registros actualizados exitosamente!")
                                    else:
                                        st.warning("⚠️ No se pudieron actualizar registros")
                            else:
                                st.warning("⚠️ No hay registros para actualizar (identificaciones no coinciden)")
                
                else:
                    st.error(f"❌ Columnas obligatorias faltantes: {', '.join(missing_cols)}")
    
    with tab3:
        show_data_management_section(client, sheet_name, worksheet_name)
    
    # Información adicional
    st.markdown("---")
    st.markdown("### 📋 Información del sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""
        **Columnas obligatorias:**
        - Identificacion: Número de identificación único
        - Nombre: Nombre del residente
        - Apellido: Apellido del residente
        - Tipo_Unidad: Tipo de unidad (Apartamento, Casa, etc.)
        - Unidad: Número o identificador de la unidad
        - Tipo: Tipo de residente (Propietario, Arrendatario, etc.)
        
        **Nota:** Los duplicados se detectan por la combinación de Identificación + Unidad
        """)
    
    with col2:
        st.info("""
        **Columnas opcionales:**
        - Telefono: Número de teléfono
        - Email: Correo electrónico
        - Fecha_Ingreso: Se asigna automáticamente si no se proporciona
        - Estado: Se asigna como 'Activo' si no se proporciona
        - Observaciones: Notas adicionales
        - ID: Se genera automáticamente
        """)

if __name__ == "__main__":
    main()