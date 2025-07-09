import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime
import numpy as np
import io
import hashlib

# Configuración de la página
#st.set_page_config(
#    page_title="Carga de Pagos Bancarios",
#    page_icon="🏦",
#    layout="wide"
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

def validate_csv_structure(df):
    """Validar que el CSV tenga las columnas necesarias para pagos bancarios"""
    required_columns = ['Monto', 'Fecha']  # Columnas mínimas requeridas
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        return False, f"Faltan columnas requeridas: {', '.join(missing_columns)}"
    
    return True, "Estructura válida"

def process_csv_data(df):
    """Procesar y normalizar datos del CSV para Google Sheets"""
    # Columnas esperadas en Google Sheets
    target_columns = [
        'ID', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha',
        'Banco', 'Estado', 'Metodo_Pago', 'Soporte_Pago', 'Ruta_Archivo',
        'Numero_Recibo', 'Ruta_Recibo', 'Observaciones', 'Saldo_Pendiente', 'Registrado'
    ]
    
    # Crear DataFrame con las columnas objetivo
    processed_df = pd.DataFrame(columns=target_columns)
    
    # Mapear columnas del CSV a las columnas objetivo
    for col in target_columns:
        if col in df.columns:
            processed_df[col] = df[col]
        else:
            # Valores por defecto para columnas faltantes
            if col == 'ID':
                processed_df[col] = range(1, len(df) + 1)
            elif col == 'Tipo_Operacion':
                processed_df[col] = 'Cuota de Mantenimiento'
            elif col == 'Estado':
                processed_df[col] = 'Pendiente'
            elif col == 'Registrado':
                processed_df[col] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                processed_df[col] = ''
    
    # Limpiar y validar datos
    if 'Monto' in processed_df.columns:
        processed_df['Monto'] = pd.to_numeric(processed_df['Monto'], errors='coerce')
    
    if 'Fecha' in processed_df.columns:
        # Convertir fechas y manejar errores
        try:
            processed_df['Fecha'] = pd.to_datetime(processed_df['Fecha'], errors='coerce')
            # Convertir a datetime objects para el editor
            processed_df['Fecha'] = processed_df['Fecha'].dt.date
        except Exception as e:
            st.warning(f"⚠️ Error procesando fechas: {str(e)}")
            # Si hay error, mantener como string
            processed_df['Fecha'] = processed_df['Fecha'].astype(str)
    
    # Convertir Saldo_Pendiente a numérico si existe
    if 'Saldo_Pendiente' in processed_df.columns:
        processed_df['Saldo_Pendiente'] = pd.to_numeric(processed_df['Saldo_Pendiente'], errors='coerce').fillna(0)
    
    # Eliminar filas con valores críticos faltantes
    processed_df = processed_df.dropna(subset=['Monto'])
    
    return processed_df

def generate_unique_id():
    """Generar ID único para el registro"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"PAG_{timestamp}"

def edit_dataframe(df):
    """Función para editar el DataFrame con funcionalidades avanzadas"""
    if 'edited_df' not in st.session_state:
        st.session_state.edited_df = df.copy()
    
    # Ensure DataFrame has a clean index
    st.session_state.edited_df = st.session_state.edited_df.reset_index(drop=True)
    
    st.subheader("✏️ Editor de Datos")
    
    # Tabs para diferentes funcionalidades
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Vista y Edición", "➕ Agregar Fila", "🗑️ Eliminar Filas", "📋 Acciones"])
    
    with tab1:
        st.markdown("**Edita los datos directamente en la tabla:**")
        
        # Preparar configuración de columnas dinámicamente
        column_config = {
            "Monto": st.column_config.NumberColumn(
                "Monto",
                help="Cantidad del pago",
                min_value=0,
                step=0.01,
                format="$%.2f"
            ),
            "Estado": st.column_config.SelectboxColumn(
                "Estado",
                help="Estado del pago",
                options=["Pendiente", "Pagado", "Cancelado"],
                required=True
            ),
            "Tipo_Operacion": st.column_config.SelectboxColumn(
                "Tipo Operación",
                help="Tipo de operación",
                options=["Cuota de Mantenimiento", "Ingreso", "Egreso", "Multa", "Extraordinaria"],
                required=True
            ),
            "Saldo_Pendiente": st.column_config.NumberColumn(
                "Saldo Pendiente",
                help="Saldo pendiente",
                min_value=0,
                step=0.01,
                format="$%.2f"
            )
        }
        
        # Configurar columna Fecha según el tipo de datos
        if 'Fecha' in st.session_state.edited_df.columns:
            fecha_sample = st.session_state.edited_df['Fecha'].dropna().iloc[0] if not st.session_state.edited_df['Fecha'].dropna().empty else None
            
            if fecha_sample is not None:
                # Verificar si es un objeto date
                if hasattr(fecha_sample, 'year'):
                    column_config["Fecha"] = st.column_config.DateColumn(
                        "Fecha",
                        help="Fecha del pago",
                        format="YYYY-MM-DD"
                    )
                else:
                    # Si es string, usar TextColumn
                    column_config["Fecha"] = st.column_config.TextColumn(
                        "Fecha",
                        help="Fecha del pago (formato: YYYY-MM-DD)",
                        max_chars=10
                    )
        
        # Editor de datos con st.data_editor
        edited_df = st.data_editor(
            st.session_state.edited_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config=column_config,
            hide_index=True,
            key="data_editor"
        )
        
        # Actualizar session state
        st.session_state.edited_df = edited_df
        
        # Mostrar estadísticas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Registros", len(edited_df))
        with col2:
            total_monto = edited_df['Monto'].sum() if 'Monto' in edited_df.columns else 0
            st.metric("Total Monto", f"${total_monto:,.2f}")
        with col3:
            pendientes = len(edited_df[edited_df['Estado'] == 'Pendiente']) if 'Estado' in edited_df.columns else 0
            st.metric("Pendientes", pendientes)
        with col4:
            pagados = len(edited_df[edited_df['Estado'] == 'Pagado']) if 'Estado' in edited_df.columns else 0
            st.metric("Pagados", pagados)
    
    with tab2:
        st.markdown("**Agregar nueva fila:**")
        
        with st.form("add_row_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_tipo = st.selectbox("Tipo Operación", ["Cuota de Mantenimiento", "Ingreso", "Egreso", "Multa", "Extraordinaria"])
                new_unidad = st.text_input("Unidad")
                new_concepto = st.text_input("Concepto")
                new_monto = st.number_input("Monto", min_value=0.0, step=0.01)
                new_fecha = st.date_input("Fecha")
                new_banco = st.text_input("Banco")
                new_estado = st.selectbox("Estado", ["Pendiente", "Pagado", "Cancelado"])
                new_metodo = st.text_input("Método Pago")
            
            with col2:
                new_soporte = st.text_input("Soporte Pago")
                new_ruta_archivo = st.text_input("Ruta Archivo")
                new_numero_recibo = st.text_input("Número Recibo")
                new_ruta_recibo = st.text_input("Ruta Recibo")
                new_observaciones = st.text_area("Observaciones")
                new_saldo = st.number_input("Saldo Pendiente", min_value=0.0, step=0.01)
            
            if st.form_submit_button("➕ Agregar Fila"):
                new_row = {
                    'ID': generate_unique_id() + f"_{len(st.session_state.edited_df)+1:03d}",
                    'Tipo_Operacion': new_tipo,
                    'Unidad': new_unidad,
                    'Concepto': new_concepto,
                    'Monto': new_monto,
                    'Fecha': new_fecha,  # Mantener como objeto date
                    'Banco': new_banco,
                    'Estado': new_estado,
                    'Metodo_Pago': new_metodo,
                    'Soporte_Pago': new_soporte,
                    'Ruta_Archivo': new_ruta_archivo,
                    'Numero_Recibo': new_numero_recibo,
                    'Ruta_Recibo': new_ruta_recibo,
                    'Observaciones': new_observaciones,
                    'Saldo_Pendiente': new_saldo,
                    'Registrado': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Agregar la nueva fila
                st.session_state.edited_df = pd.concat([st.session_state.edited_df, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Fila agregada exitosamente")
                st.rerun()
    
    with tab3:
        st.markdown("**Eliminar filas:**")
        
        if not st.session_state.edited_df.empty:
            # Mostrar tabla para seleccionar filas a eliminar
            st.markdown("Selecciona las filas que deseas eliminar:")
            
            # Initialize session state for row selection if not exists
            if 'rows_to_delete' not in st.session_state:
                st.session_state.rows_to_delete = []
            
            # Reset the selection when DataFrame changes
            current_df_size = len(st.session_state.edited_df)
            if 'last_df_size' not in st.session_state:
                st.session_state.last_df_size = current_df_size
            elif st.session_state.last_df_size != current_df_size:
                st.session_state.rows_to_delete = []
                st.session_state.last_df_size = current_df_size
            
            # Crear checkboxes para cada fila con keys únicos
            rows_to_delete = []
            for position, (idx, row) in enumerate(st.session_state.edited_df.iterrows()):
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    # Use position instead of index to ensure unique keys
                    unique_key = f"delete_row_{position}_{hash(str(row.get('ID', '')))}_{current_df_size}"
                    # FIXED: Add proper label with label_visibility="collapsed"
                    delete_row = st.checkbox(
                        f"Eliminar fila {position + 1}",
                        key=unique_key,
                        label_visibility="collapsed"
                    )
                with col2:
                    unidad = row.get('Unidad', 'N/A')
                    concepto = row.get('Concepto', 'N/A')
                    monto = row.get('Monto', 0)
                    fecha = row.get('Fecha', 'N/A')
                    st.write(f"**{concepto}** - ${monto:,.2f} - {fecha}")
                
                if delete_row:
                    rows_to_delete.append(idx)
            
            if rows_to_delete:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Eliminar Filas Seleccionadas", type="primary"):
                        st.session_state.edited_df = st.session_state.edited_df.drop(rows_to_delete).reset_index(drop=True)
                        st.success(f"✅ {len(rows_to_delete)} filas eliminadas")
                        st.rerun()
                with col2:
                    st.info(f"Se eliminarán {len(rows_to_delete)} filas")
        else:
            st.info("No hay datos para eliminar")
    
    with tab4:
        st.markdown("**Acciones sobre los datos:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Restaurar Original"):
                st.session_state.edited_df = df.copy()
                st.success("✅ Datos restaurados al original")
                st.rerun()
        
        with col2:
            if st.button("🧹 Limpiar Todo"):
                st.session_state.edited_df = pd.DataFrame(columns=df.columns)
                st.success("✅ Datos limpiados")
                st.rerun()
        
        with col3:
            # Exportar datos editados
            if not st.session_state.edited_df.empty:
                csv_buffer = io.StringIO()
                st.session_state.edited_df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label="📥 Descargar CSV Editado",
                    data=csv_data,
                    file_name=f"datos_editados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Validaciones
        st.markdown("---")
        st.subheader("🔍 Validaciones")
        
        if not st.session_state.edited_df.empty:
            # Validar datos faltantes
            missing_data = st.session_state.edited_df.isnull().sum()
            critical_missing = missing_data[['Monto', 'Fecha']].sum()
            
            if critical_missing > 0:
                st.error(f"❌ Hay {critical_missing} valores faltantes en campos críticos (Monto, Fecha)")
            else:
                st.success("✅ Todos los campos críticos están completos")
            
            # Validar montos negativos
            negative_amounts = (st.session_state.edited_df['Monto'] < 0).sum()
            if negative_amounts > 0:
                st.warning(f"⚠️ Hay {negative_amounts} montos negativos")

            # Validar duplicados internos
            internal_duplicates, _ = detect_duplicates_in_dataframe(st.session_state.edited_df)
            
            if not internal_duplicates.empty:
                st.error(f"❌ Se encontraron {len(internal_duplicates)} registros duplicados en los datos actuales")
                with st.expander("🔍 Ver registros duplicados"):
                    # Mostrar duplicados con índices para facilitar identificación
                    duplicates_display = internal_duplicates.copy()
                    duplicates_display['Índice_Original'] = internal_duplicates.index
                    st.dataframe(duplicates_display[['Índice_Original', 'Monto', 'Fecha', 'Unidad', 'Concepto']])
                    
                    # Botón para eliminar duplicados automáticamente
                    if st.button("🗑️ Eliminar Duplicados Automáticamente"):
                        st.session_state.edited_df = st.session_state.edited_df.drop_duplicates(
                            subset=['Monto', 'Fecha', 'Unidad', 'Concepto'], 
                            keep='first'
                        ).reset_index(drop=True)
                        st.success("✅ Duplicados eliminados automáticamente")
                        st.rerun()
            else:
                st.success("✅ No hay registros duplicados")
            
            # Validar fechas futuras
            try:
                # Convertir fechas a datetime para comparación
                fecha_column = st.session_state.edited_df['Fecha']
                if hasattr(fecha_column.iloc[0], 'year'):
                    # Si son objetos date, convertir a datetime
                    fecha_datetime = pd.to_datetime(fecha_column)
                else:
                    # Si son strings, convertir a datetime
                    fecha_datetime = pd.to_datetime(fecha_column, errors='coerce')
                
                future_dates = (fecha_datetime > datetime.now()).sum()
                if future_dates > 0:
                    st.info(f"ℹ️ Hay {future_dates} fechas futuras")
            except:
                st.info("ℹ️ No se pudieron validar las fechas")
    
    return st.session_state.edited_df

def analyze_existing_data(client, sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera"):
    """
    Analiza los datos existentes en Google Sheets para entender la estructura
    """
    print("🔍 === ANÁLISIS DE DATOS EXISTENTES ===")
    
    try:
        # Obtener datos existentes
        sheet = client.open("gestion-conjuntos")
        worksheet = sheet.worksheet("Administracion_Financiera")
        existing_data = worksheet.get_all_records()
        existing_df = pd.DataFrame(existing_data)
        
        print(f"📊 Total registros existentes: {len(existing_df)}")
        
        if existing_df.empty:
            print("⚠️ No hay datos existentes en la hoja")
            return existing_df
        
        # Mostrar información de columnas
        print(f"📋 Columnas disponibles: {list(existing_df.columns)}")
        
        # Analizar cada columna relevante
        key_columns = ['Unidad', 'Concepto', 'Monto', 'Fecha']
        for col in key_columns:
            if col in existing_df.columns:
                print(f"\n🔍 Análisis de columna '{col}':")
                print(f"   - Tipo de datos: {existing_df[col].dtype}")
                print(f"   - Valores únicos: {existing_df[col].nunique()}")
                print(f"   - Valores nulos: {existing_df[col].isnull().sum()}")
                print(f"   - Ejemplos: {existing_df[col].head(3).tolist()}")
                
                # Verificar si hay valores vacíos o problemáticos
                empty_values = existing_df[col].isin(['', ' ', 'nan', 'None', None]).sum()
                if empty_values > 0:
                    print(f"   - Valores vacíos: {empty_values}")
        
        # Mostrar algunos registros completos
        print(f"\n📋 Primeros 3 registros completos:")
        display_cols = [col for col in key_columns if col in existing_df.columns]
        if display_cols:
            for i, row in existing_df[display_cols].head(3).iterrows():
                print(f"   Registro {i}: {dict(row)}")
        
        return existing_df
        
    except Exception as e:
        print(f"❌ Error analizando datos existentes: {str(e)}")
        return pd.DataFrame()


def create_comparison_key(df, columns, mode='exact'):
    """
    Crea una clave única para comparación basada en las columnas especificadas
    """
    df_copy = df.copy()
    
    # Normalizar cada columna
    for col in columns:
        if col in df_copy.columns:
            # Convertir a string
            df_copy[col] = df_copy[col].astype(str)
            
            if mode == 'fuzzy':
                # Normalización fuzzy: quitar espacios, minúsculas, caracteres especiales
                df_copy[col] = df_copy[col].str.strip().str.lower()
                df_copy[col] = df_copy[col].str.replace(r'[^\w\s]', '', regex=True)
                df_copy[col] = df_copy[col].str.replace(r'\s+', ' ', regex=True)
            
            # Manejar valores vacíos
            df_copy[col] = df_copy[col].replace(['nan', 'None', ''], 'NULL')
    
    # Crear clave de comparación
    comparison_key = df_copy[columns].apply(
        lambda x: hashlib.md5('|'.join(x.astype(str)).encode()).hexdigest(), 
        axis=1
    )
    
    return comparison_key


def validate_duplicates_enhanced(new_df, existing_df, duplicate_columns, comparison_mode='exact'):
    """
    Validación de duplicados mejorada con debugging detallado
    """
    print("🔍 === VALIDACIÓN DE DUPLICADOS MEJORADA ===")
    print(f"Columnas para validar: {duplicate_columns}")
    print(f"Modo de comparación: {comparison_mode}")
    
    # Verificar que existan las columnas
    missing_new = [col for col in duplicate_columns if col not in new_df.columns]
    missing_existing = [col for col in duplicate_columns if col not in existing_df.columns]
    
    if missing_new:
        print(f"❌ Columnas faltantes en datos nuevos: {missing_new}")
        return new_df, pd.DataFrame(), None
    
    if missing_existing:
        print(f"❌ Columnas faltantes en datos existentes: {missing_existing}")
        return new_df, pd.DataFrame(), None
    
    if existing_df.empty:
        print("✅ No hay datos existentes - todos los registros son nuevos")
        return new_df, pd.DataFrame(), None
    
    print(f"📊 Registros nuevos: {len(new_df)}")
    print(f"📊 Registros existentes: {len(existing_df)}")
    
    # Crear claves de comparación
    print("🔧 Creando claves de comparación...")
    new_keys = create_comparison_key(new_df, duplicate_columns, comparison_mode)
    existing_keys = create_comparison_key(existing_df, duplicate_columns, comparison_mode)
    
    print(f"🔍 Ejemplo de claves nuevas: {new_keys.head(3).tolist()}")
    print(f"🔍 Ejemplo de claves existentes: {existing_keys.head(3).tolist()}")
    
    # Encontrar duplicados
    existing_keys_set = set(existing_keys.values)
    duplicate_mask = new_keys.isin(existing_keys_set)
    
    duplicates = new_df[duplicate_mask].copy()
    unique_records = new_df[~duplicate_mask].copy()
    
    print(f"📊 Duplicados encontrados: {len(duplicates)}")
    print(f"📊 Registros únicos: {len(unique_records)}")
    
    # Mostrar ejemplos de duplicados
    if len(duplicates) > 0:
        print("🔍 Ejemplos de registros duplicados:")
        display_cols = [col for col in duplicate_columns if col in duplicates.columns]
        for i, (_, row) in enumerate(duplicates[display_cols].head(3).iterrows()):
            print(f"   Duplicado {i+1}: {dict(row)}")
            
            # Encontrar el registro existente correspondiente
            row_key = create_comparison_key(pd.DataFrame([row]), duplicate_columns, comparison_mode).iloc[0]
            existing_match = existing_df[existing_keys == row_key]
            if not existing_match.empty:
                existing_row = existing_match.iloc[0]
                print(f"   Coincide con: {dict(existing_row[display_cols])}")
    
    return unique_records, duplicates, {
        'total_nuevos': len(new_df),
        'duplicados': len(duplicates),
        'unicos': len(unique_records)
    }


def upload_with_strict_validation(client, df, sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera", duplicate_columns=['Unidad', 'Concepto', 'Monto', 'Fecha'], comparison_mode='exact'):
    """
    Función de carga con validación estricta de duplicados
    """
    print("🚀 === CARGA CON VALIDACIÓN ESTRICTA ===")
    
    if df.empty:
        return False, "❌ No hay datos para subir"
    
    try:
        # Paso 1: Analizar datos existentes
        print("📥 Paso 1: Analizando datos existentes...")
        existing_df = analyze_existing_data(client,  sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera")
        
        # Paso 2: Limpiar datos nuevos
        print("🔧 Paso 2: Limpiando datos nuevos...")
        clean_df = df.copy()
        
        # Normalizar columnas de fecha si existen
        if 'Fecha' in clean_df.columns:
            clean_df['Fecha'] = pd.to_datetime(clean_df['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Normalizar columnas numéricas
        if 'Monto' in clean_df.columns:
            clean_df['Monto'] = pd.to_numeric(clean_df['Monto'], errors='coerce')
        
        # Quitar registros internos duplicados
        print("🔍 Paso 3: Eliminando duplicados internos...")
        valid_dup_cols = [col for col in duplicate_columns if col in clean_df.columns]
        internal_duplicates = clean_df.duplicated(subset=valid_dup_cols, keep='first')
        clean_df = clean_df[~internal_duplicates]
        
        print(f"📊 Duplicados internos eliminados: {internal_duplicates.sum()}")
        print(f"📊 Registros después de limpieza interna: {len(clean_df)}")
        
        # Paso 4: Validar contra datos existentes
        print("🔍 Paso 4: Validando contra datos existentes...")
        unique_records, duplicates, report = validate_duplicates_enhanced(
            clean_df, existing_df, valid_dup_cols, comparison_mode
        )
        
        if len(unique_records) == 0:
            message = "❌ No hay registros únicos para subir. Todos los registros ya existen."
            print(message)
            return False, message
        
        # Paso 5: Subir solo registros únicos
        print(f"📤 Paso 5: Subiendo {len(unique_records)} registros únicos...")
        
        # Conectar a Google Sheets
        sheet = client.open("gestion-conjuntos")
        worksheet = sheet.worksheet("Administracion_Financiera")
        
        # Preparar datos para subir
        upload_df = unique_records.copy()
        
        # Generar IDs únicos si no existen
        if 'ID' not in upload_df.columns:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            upload_df['ID'] = [f"ID_{timestamp}_{i:04d}" for i in range(len(upload_df))]
        
        # Limpiar valores problemáticos
        upload_df = upload_df.replace([np.inf, -np.inf], '')
        upload_df = upload_df.fillna('')
        
        # Convertir a lista de listas
        values = upload_df.values.tolist()
        
        # Subir a Google Sheets
        if existing_df.empty:
            # Primera carga: incluir headers
            headers = upload_df.columns.tolist()
            worksheet.append_row(headers)
        
        worksheet.append_rows(values)
        
        # Mensaje de éxito
        success_message = f"✅ {len(unique_records)} registros subidos exitosamente"
        if len(duplicates) > 0:
            success_message += f"\n⚠️ {len(duplicates)} duplicados omitidos"
        
        print(success_message)
        return True, success_message
        
    except Exception as e:
        error_msg = f"❌ Error en la carga: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        return False, error_msg


def test_duplicate_detection(client, test_data, sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera"):
    """
    Función para probar la detección de duplicados con datos específicos
    """
    print("🧪 === PRUEBA DE DETECCIÓN DE DUPLICADOS ===")
    
    # Crear DataFrame de prueba
    test_df = pd.DataFrame(test_data)
    print(f"📊 Datos de prueba: {len(test_df)} registros")
    
    # Mostrar datos de prueba
    print("📋 Datos de prueba:")
    for i, row in test_df.iterrows():
        print(f"   {i+1}: {dict(row)}")
    
    # Obtener datos existentes
    existing_df = analyze_existing_data(client,  sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera")
    
    # Probar detección
    duplicate_columns = ['Unidad', 'Concepto', 'Monto', 'Fecha']
    unique_records, duplicates, report = validate_duplicates_enhanced(
        test_df, existing_df, duplicate_columns, 'exact'
    )
    
    print(f"\n📊 Resultado de la prueba:")
    print(f"   - Registros únicos: {len(unique_records)}")
    print(f"   - Duplicados detectados: {len(duplicates)}")
    
    return unique_records, duplicates


def detect_duplicates_in_dataframe(df, key_columns=None):
    """Detectar registros duplicados dentro del mismo DataFrame"""
    if key_columns is None:
        key_columns = ['Monto', 'Fecha', 'Unidad', 'Concepto']
    
    # Filtrar solo las columnas que existen en el DataFrame
    available_columns = [col for col in key_columns if col in df.columns]
    
    if not available_columns:
        return pd.DataFrame(), pd.DataFrame()
    
    # Encontrar duplicados
    duplicates_mask = df.duplicated(subset=available_columns, keep=False)
    duplicates_df = df[duplicates_mask].copy()
    unique_df = df[~duplicates_mask].copy()
    
    return duplicates_df, unique_df

def normalize_data_for_comparison(df, columns_to_normalize):
    """
    Normaliza los datos para una comparación más robusta
    """
    df_normalized = df.copy()
    
    for col in columns_to_normalize:
        if col not in df_normalized.columns:
            continue
            
        if col == 'Fecha':
            # Normalizar fechas - convertir a formato estándar
            df_normalized[col] = pd.to_datetime(df_normalized[col], errors='coerce')
            # Convertir a string con formato consistente
            df_normalized[col] = df_normalized[col].dt.strftime('%Y-%m-%d')
            # Reemplazar NaT con string vacío
            df_normalized[col] = df_normalized[col].fillna('')
            
        elif col == 'Monto':
            # Normalizar montos - convertir a numérico y redondear
            df_normalized[col] = pd.to_numeric(df_normalized[col], errors='coerce')
            df_normalized[col] = df_normalized[col].round(2)
            # Convertir a string para comparación consistente
            df_normalized[col] = df_normalized[col].astype(str).replace('nan', '0')
            
        elif df_normalized[col].dtype == 'object':
            # Normalizar texto - quitar espacios, convertir a minúsculas
            df_normalized[col] = df_normalized[col].astype(str).str.strip().str.lower()
            # Remover caracteres especiales y espacios múltiples
            df_normalized[col] = df_normalized[col].str.replace(r'\s+', ' ', regex=True)
            # Reemplazar valores nulos
            df_normalized[col] = df_normalized[col].fillna('').replace('nan', '')
        
        # Asegurar que todos los valores sean strings para concatenación
        df_normalized[col] = df_normalized[col].astype(str).str.strip()
    
    return df_normalized

def create_comparison_key(df, key_columns):
    """
    Crea una clave única para comparación basada en las columnas especificadas
    """
    df_copy = df.copy()
    
    # Asegurar que todas las columnas sean strings limpios para concatenación
    for col in key_columns:
        if col in df_copy.columns:
            # Convertir todo a string y limpiar
            df_copy[col] = df_copy[col].astype(str).str.strip()
            # Reemplazar valores problemáticos
            df_copy[col] = df_copy[col].replace(['nan', 'NaT', 'None', 'null'], '')
    
    # Crear clave única concatenando valores con separador único
    comparison_key = df_copy[key_columns].apply(
        lambda row: '||'.join([str(val) for val in row.values]), axis=1
    )
    
    return comparison_key

def detect_duplicates_with_existing_data(new_df, existing_df, key_columns=None):
    """
    Detectar registros que ya existen en Google Sheets con validación mejorada
    """
    if key_columns is None:
        key_columns = ['Monto', 'Fecha', 'Unidad', 'Concepto']
    
    # Si no hay datos existentes, todos los registros son únicos
    if existing_df.empty:
        return pd.DataFrame(), new_df.copy()
    
    # Verificar que las columnas existen en ambos DataFrames
    available_columns = [col for col in key_columns 
                        if col in new_df.columns and col in existing_df.columns]
    
    if not available_columns:
        print("⚠️ No hay columnas comunes para comparar")
        return pd.DataFrame(), new_df.copy()
    
    print(f"🔍 Comparando usando columnas: {available_columns}")
    
    # Normalizar ambos DataFrames
    new_df_normalized = normalize_data_for_comparison(new_df, available_columns)
    existing_df_normalized = normalize_data_for_comparison(existing_df, available_columns)
    
    # Debug: Mostrar algunos valores antes de crear claves
    print("🔍 DEBUG - Valores en datos nuevos:")
    for i, row in new_df_normalized.head(3).iterrows():
        values = [f"{col}='{row[col]}'" for col in available_columns if col in row.index]
        print(f"   Fila {i}: {' | '.join(values)}")
    
    print("🔍 DEBUG - Valores en datos existentes:")
    for i, row in existing_df_normalized.head(3).iterrows():
        values = [f"{col}='{row[col]}'" for col in available_columns if col in row.index]
        print(f"   Fila {i}: {' | '.join(values)}")
    
    # Crear claves de comparación
    new_keys = create_comparison_key(new_df_normalized, available_columns)
    existing_keys = create_comparison_key(existing_df_normalized, available_columns)
    
    # Debug: Mostrar claves generadas
    print("🔍 DEBUG - Claves de comparación nuevas:")
    for i, key in enumerate(new_keys.head(3)):
        print(f"   {i}: '{key}'")
    
    print("🔍 DEBUG - Claves de comparación existentes:")
    for i, key in enumerate(existing_keys.head(3)):
        print(f"   {i}: '{key}'")
    
    # Encontrar duplicados
    existing_keys_set = set(existing_keys.tolist())
    duplicate_mask = new_keys.isin(existing_keys_set)
    
    # Separar duplicados y únicos
    duplicates_df = new_df[duplicate_mask].copy()
    unique_df = new_df[~duplicate_mask].copy()
    
    # Debug: mostrar algunos ejemplos
    if len(duplicates_df) > 0:
        print(f"🔍 Encontrados {len(duplicates_df)} duplicados:")
        for i, (idx, row) in enumerate(duplicates_df.head(5).iterrows()):
            values = [str(row[col]) for col in available_columns if col in row.index]
            key = new_keys.iloc[idx] if idx < len(new_keys) else "N/A"
            print(f"   {i+1}. {' | '.join(values)} (clave: {key})")
    else:
        print("🔍 No se encontraron duplicados")
        # Mostrar por qué no hay duplicados
        print("🔍 Comparando claves individuales:")
        for i, new_key in enumerate(new_keys.head(3)):
            match_found = new_key in existing_keys_set
            print(f"   Nueva clave {i}: '{new_key}' -> {'DUPLICADO' if match_found else 'ÚNICO'}")
    
    return duplicates_df, unique_df

def detect_internal_duplicates(df, key_columns):
    """
    Detecta duplicados internos dentro del mismo DataFrame
    """
    # Verificar que las columnas existen
    available_columns = [col for col in key_columns if col in df.columns]
    
    if not available_columns:
        return pd.DataFrame(), df.copy()
    
    # Normalizar datos
    df_normalized = normalize_data_for_comparison(df, available_columns)
    
    # Detectar duplicados usando las columnas normalizadas
    duplicate_mask = df_normalized.duplicated(subset=available_columns, keep='first')
    
    duplicates = df[duplicate_mask].copy()
    unique_records = df[~duplicate_mask].copy()
    
    return duplicates, unique_records

def validate_existing_records(new_df, existing_df, duplicate_columns, comparison_mode='exact'):
    """
    Valida registros nuevos contra registros existentes para detectar duplicados
    con validación mejorada y más estricta
    """
    
    if existing_df.empty:
        print("📊 No hay registros existentes - todos los registros son únicos")
        return new_df, pd.DataFrame(), {
            'total_nuevos': len(new_df),
            'registros_duplicados': 0,
            'registros_unicos': len(new_df),
            'porcentaje_duplicados': 0.0,
            'modo_comparacion': comparison_mode,
            'columnas_comparacion': duplicate_columns,
            'detalles_duplicados': []
        }
    
    # Verificar columnas disponibles
    valid_columns = [col for col in duplicate_columns 
                    if col in new_df.columns and col in existing_df.columns]
    
    if not valid_columns:
        print("⚠️ No hay columnas válidas para comparar")
        return new_df, pd.DataFrame(), {
            'total_nuevos': len(new_df),
            'registros_duplicados': 0,
            'registros_unicos': len(new_df),
            'porcentaje_duplicados': 0.0,
            'modo_comparacion': comparison_mode,
            'columnas_comparacion': duplicate_columns,
            'detalles_duplicados': []
        }
    
    print(f"🔍 Validando con columnas: {valid_columns}")
    
    # Usar la función mejorada de detección de duplicados
    duplicate_records, unique_records = detect_duplicates_with_existing_data(
        new_df, existing_df, valid_columns
    )
    
    # Crear detalles de duplicados
    duplicate_details = []
    if len(duplicate_records) > 0:
        for idx, row in duplicate_records.head(10).iterrows():
            duplicate_details.append({
                'new_index': idx,
                'values': {col: str(row[col]) for col in valid_columns if col in row.index},
                'full_record': row.to_dict()
            })
    
    # Crear reporte de validación
    validation_report = {
        'total_nuevos': len(new_df),
        'registros_duplicados': len(duplicate_records),
        'registros_unicos': len(unique_records),
        'porcentaje_duplicados': (len(duplicate_records) / len(new_df)) * 100 if len(new_df) > 0 else 0,
        'modo_comparacion': comparison_mode,
        'columnas_comparacion': valid_columns,
        'detalles_duplicados': duplicate_details
    }
    
    print(f"📊 Validación completada:")
    print(f"   - Total nuevos: {validation_report['total_nuevos']}")
    print(f"   - Duplicados: {validation_report['registros_duplicados']}")
    print(f"   - Únicos: {validation_report['registros_unicos']}")
    print(f"   - % Duplicados: {validation_report['porcentaje_duplicados']:.1f}%")
    
    return unique_records, duplicate_records, validation_report

def upload_to_google_sheets_with_validation(client, df, sheet_name="gestion-conjuntos", 
                                           worksheet_name="Administracion_Financiera", 
                                           validate_duplicates=True, duplicate_columns=None, 
                                           comparison_mode='exact'):
    """
    Subir datos a Google Sheets con validación robusta de duplicados
    """
    
    try:
        # Validaciones iniciales
        if df.empty:
            return False, "❌ No hay datos para subir"
        
        print(f"🚀 Iniciando carga de {len(df)} registros")
        print(f"🔍 Validación de duplicados: {'Activada' if validate_duplicates else 'Desactivada'}")
        
        # Configurar columnas por defecto si no se especifican
        if duplicate_columns is None:
            duplicate_columns = ['Monto', 'Fecha', 'Unidad', 'Concepto']
        
        if validate_duplicates:
            print(f"🔍 Columnas para validar: {duplicate_columns}")
            print(f"🔍 Modo de comparación: {comparison_mode}")
        
        # Crear copia del DataFrame para procesamiento
        upload_df = df.copy()
        
        # Conectar a Google Sheets
        print("📥 Conectando a Google Sheets...")
        sheet = client.open("gestion-conjuntos")
        worksheet = sheet.worksheet("Administracion_Financiera")
        
        # Obtener datos existentes
        print("📥 Obteniendo datos existentes de Google Sheets...")
        existing_data = worksheet.get_all_records()
        existing_df = pd.DataFrame(existing_data)
        
        print(f"📊 Datos existentes en Google Sheets: {len(existing_df)} registros")
        
        # Variables para tracking
        total_original = len(df)
        total_internal_duplicates = 0
        total_external_duplicates = 0
        
        if validate_duplicates:
            # Verificar que las columnas existen
            valid_dup_columns = [col for col in duplicate_columns if col in upload_df.columns]
            
            if not valid_dup_columns:
                error_msg = f"❌ Error: Ninguna de las columnas especificadas existe en los datos: {duplicate_columns}"
                print(error_msg)
                return False, error_msg
            
            if len(valid_dup_columns) != len(duplicate_columns):
                missing_cols = [col for col in duplicate_columns if col not in upload_df.columns]
                print(f"⚠️ Columnas faltantes: {missing_cols}")
                print(f"⚠️ Usando columnas válidas: {valid_dup_columns}")
            
            # Paso 1: Detectar duplicados internos
            print("🔍 Paso 1: Detectando duplicados internos...")
            internal_duplicates, upload_df_clean = detect_internal_duplicates(
                upload_df, valid_dup_columns
            )
            total_internal_duplicates = len(internal_duplicates)
            
            print(f"📊 Duplicados internos encontrados: {total_internal_duplicates}")
            
            # Paso 2: Validar contra registros existentes
            print("🔍 Paso 2: Validando contra registros existentes...")
            
            unique_records, external_duplicates, validation_report = validate_existing_records(
                upload_df_clean, 
                existing_df, 
                valid_dup_columns,
                comparison_mode
            )
            
            total_external_duplicates = len(external_duplicates)
            final_upload_df = unique_records
            
            print(f"📊 Duplicados externos encontrados: {total_external_duplicates}")
            print(f"📊 Registros únicos para subir: {len(final_upload_df)}")
            
            # Verificación adicional - comparar directamente con datos existentes
            if len(final_upload_df) > 0 and len(existing_df) > 0:
                print("🔍 Verificación adicional de duplicados...")
                
                # Última verificación con normalización estricta
                additional_duplicates, verified_unique = detect_duplicates_with_existing_data(
                    final_upload_df, existing_df, valid_dup_columns
                )
                
                if len(additional_duplicates) > 0:
                    print(f"⚠️ ENCONTRADOS {len(additional_duplicates)} duplicados adicionales en verificación final")
                    print("🔍 Registros que se intentaban subir pero ya existen:")
                    for i, (idx, row) in enumerate(additional_duplicates.head(5).iterrows()):
                        values = [f"{col}='{row[col]}'" for col in valid_dup_columns if col in row.index]
                        print(f"   {i+1}. {' | '.join(values)}")
                    
                    final_upload_df = verified_unique
                    total_external_duplicates += len(additional_duplicates)
                
                # Verificación manual adicional con comparación directa
                print("🔍 Verificación manual adicional...")
                manual_duplicates = []
                
                for idx, new_row in final_upload_df.iterrows():
                    # Crear valores normalizados para comparación
                    new_values = {}
                    for col in valid_dup_columns:
                        if col in new_row.index:
                            val = str(new_row[col]).strip().lower()
                            if col == 'Fecha':
                                try:
                                    val = pd.to_datetime(val).strftime('%Y-%m-%d')
                                except:
                                    pass
                            elif col == 'Monto':
                                try:
                                    val = str(round(float(val), 2))
                                except:
                                    pass
                            new_values[col] = val
                    
                    # Comparar con cada registro existente
                    for _, existing_row in existing_df.iterrows():
                        existing_values = {}
                        for col in valid_dup_columns:
                            if col in existing_row.index:
                                val = str(existing_row[col]).strip().lower()
                                if col == 'Fecha':
                                    try:
                                        val = pd.to_datetime(val).strftime('%Y-%m-%d')
                                    except:
                                        pass
                                elif col == 'Monto':
                                    try:
                                        val = str(round(float(val), 2))
                                    except:
                                        pass
                                existing_values[col] = val
                        
                        # Comparar todos los valores
                        if all(new_values.get(col) == existing_values.get(col) for col in valid_dup_columns):
                            manual_duplicates.append(idx)
                            print(f"🔍 DUPLICADO MANUAL ENCONTRADO: {new_values}")
                            break
                
                if manual_duplicates:
                    print(f"⚠️ ENCONTRADOS {len(manual_duplicates)} duplicados en verificación manual")
                    final_upload_df = final_upload_df.drop(manual_duplicates)
                    total_external_duplicates += len(manual_duplicates)
            
            # Mostrar ejemplos de duplicados
            if total_external_duplicates > 0:
                print("🔍 Ejemplos de duplicados encontrados:")
                for i, detail in enumerate(validation_report['detalles_duplicados'][:3]):
                    print(f"   {i+1}. {detail['values']}")
            
            # Mostrar reporte en Streamlit si está disponible
            if 'st' in globals():
                validation_message = f"""
                📊 **Reporte de Validación de Duplicados:**
                - Registros originales: {total_original}
                - Duplicados internos: {total_internal_duplicates}
                - Duplicados con datos existentes: {total_external_duplicates}
                - Registros únicos para subir: {len(final_upload_df)}
                - Porcentaje de duplicados: {((total_internal_duplicates + total_external_duplicates) / total_original) * 100:.1f}%
                - Modo de comparación: {comparison_mode}
                - Columnas de comparación: {', '.join(valid_dup_columns)}
                """
                
                st.info(validation_message)
                
                # Mostrar duplicados internos
                if total_internal_duplicates > 0:
                    st.warning(f"⚠️ Se encontraron {total_internal_duplicates} registros duplicados dentro del archivo:")
                    with st.expander("Ver duplicados internos"):
                        display_columns = [col for col in valid_dup_columns if col in internal_duplicates.columns]
                        st.dataframe(internal_duplicates[display_columns])
                
                # Mostrar duplicados externos
                if total_external_duplicates > 0:
                    st.warning(f"⚠️ Se encontraron {total_external_duplicates} registros que ya existen en la base de datos")
                    with st.expander("Ver duplicados existentes"):
                        display_columns = [col for col in valid_dup_columns if col in external_duplicates.columns]
                        st.dataframe(external_duplicates[display_columns])
        
        else:
            # Sin validación de duplicados
            print("⚠️ Validación de duplicados deshabilitada")
            final_upload_df = upload_df
        
        # Verificar si hay datos para subir
        if final_upload_df.empty:
            message = "❌ No hay registros únicos para subir. Todos los registros ya existen o están duplicados."
            print(message)
            return False, message
        
        # Procesamiento final de datos
        print(f"🔧 Procesando {len(final_upload_df)} registros para subir...")
        
        # Convertir fechas a strings para Google Sheets
        if 'Fecha' in final_upload_df.columns and len(final_upload_df) > 0:
            final_upload_df['Fecha'] = pd.to_datetime(final_upload_df['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Generar IDs únicos si es necesario
        if 'ID' not in final_upload_df.columns or final_upload_df['ID'].isna().any():
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            final_upload_df['ID'] = [f"ID_{timestamp}_{i:04d}" for i in range(len(final_upload_df))]
        
        # Limpiar datos problemáticos
        final_upload_df = final_upload_df.replace([np.inf, -np.inf], '')
        final_upload_df = final_upload_df.fillna('')
        
        # Convertir a lista para Google Sheets
        values = final_upload_df.values.tolist()
        
        # Subir datos
        print("📤 Subiendo datos a Google Sheets...")
        if existing_data:
            worksheet.append_rows(values)
        else:
            headers = final_upload_df.columns.tolist()
            worksheet.append_row(headers)
            worksheet.append_rows(values)
        
        print("✅ Datos subidos exitosamente")
        
        # Mensaje de éxito
        success_message = f"✅ {len(final_upload_df)} registros subidos exitosamente"
        if validate_duplicates and (total_internal_duplicates > 0 or total_external_duplicates > 0):
            success_message += f"\n📊 {total_internal_duplicates + total_external_duplicates} duplicados omitidos"
            success_message += f"\n🔍 Validación: {comparison_mode}"
        
        return True, success_message
        
    except Exception as e:
        error_msg = f"❌ Error subiendo datos: {str(e)}"
        print(error_msg)
        
        # Mostrar traceback completo para debugging
        import traceback
        print("🔍 Traceback completo:")
        print(traceback.format_exc())
        
        if 'st' in globals():
            st.error(error_msg)
        
        return False, error_msg

# Función auxiliar para debugging
def debug_comparison(new_df, existing_df, duplicate_columns, comparison_mode='exact'):
    """
    Función de debugging para entender por qué no se detectan duplicados
    """
    print("🔍 === DEBUG DE COMPARACIÓN ===")
    print(f"Columnas para comparar: {duplicate_columns}")
    print(f"Modo de comparación: {comparison_mode}")
    
    # Verificar estructura
    print(f"Registros nuevos: {len(new_df)}")
    print(f"Registros existentes: {len(existing_df)}")
    
    if existing_df.empty:
        print("⚠️ No hay datos existentes para comparar")
        return
    
    # Verificar columnas
    for col in duplicate_columns:
        if col in new_df.columns and col in existing_df.columns:
            print(f"✅ Columna '{col}' existe en ambos DataFrames")
            print(f"   Nuevos - Tipo: {new_df[col].dtype}, Ejemplos: {new_df[col].head(2).tolist()}")
            print(f"   Existentes - Tipo: {existing_df[col].dtype}, Ejemplos: {existing_df[col].head(2).tolist()}")
        else:
            print(f"❌ Columna '{col}' falta en algún DataFrame")
            print(f"   En nuevos: {col in new_df.columns}")
            print(f"   En existentes: {col in existing_df.columns}")
    
    # Crear ejemplo de comparación
    if len(new_df) > 0 and len(existing_df) > 0:
        valid_cols = [col for col in duplicate_columns if col in new_df.columns and col in existing_df.columns]
        if valid_cols:
            print("🔍 Ejemplo de comparación:")
            new_example = new_df[valid_cols].iloc[0]
            existing_example = existing_df[valid_cols].iloc[0]
            print(f"   Nuevo: {dict(new_example)}")
            print(f"   Existente: {dict(existing_example)}")
            
            # Comparar valores
            for col in valid_cols:
                new_val = str(new_example[col]).strip().lower() if comparison_mode == 'fuzzy' else str(new_example[col])
                existing_val = str(existing_example[col]).strip().lower() if comparison_mode == 'fuzzy' else str(existing_example[col])
                match = new_val == existing_val
                print(f"   {col}: '{new_val}' == '{existing_val}' -> {match}")
    
    print("🔍 === FIN DEBUG ===")

def csv_main():
    st.title("🏦 Carga de Pagos Bancarios")
    st.markdown("---")
    
    # Cargar credenciales
    with st.spinner("🔑 Cargando credenciales..."):
        creds, config = load_credentials_from_toml()
    
    if not creds:
        st.stop()
    
    # Establecer conexión
    with st.spinner("🔗 Conectando a Google Sheets..."):
        client = get_google_sheets_connection(creds)
    
    if not client:
        st.stop()
    
    st.markdown("---")
    
    # Interfaz de carga de archivo
    st.header("📄 Cargar Archivo CSV")
    
    uploaded_file = st.file_uploader(
        "Selecciona un archivo CSV con los pagos bancarios",
        type=['csv'],
        help="El archivo debe contener al menos las columnas: Monto, Fecha"
    )
    
    if uploaded_file is not None:
        try:
            # Leer CSV
            df = pd.read_csv(uploaded_file)
            
            # Mostrar información básica del archivo
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Filas", len(df))
            with col2:
                st.metric("Columnas", len(df.columns))
            with col3:
                st.metric("Tamaño", f"{uploaded_file.size / 1024:.1f} KB")
            
            # Validar estructura
            is_valid, message = validate_csv_structure(df)
            
            if is_valid:
                st.success(f"✅ {message}")
                
                # Procesar datos
                with st.spinner("🔄 Procesando datos..."):
                    processed_df = process_csv_data(df)
                
                if not processed_df.empty:
                    st.markdown("---")
                    
                    # Editor de datos interactivo
                    final_df = edit_dataframe(processed_df)
                    
                    st.markdown("---")
                    
                    # Configuración de carga
                    st.subheader("⚙️ Configuración de carga")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        sheet_name = "gestion-conjuntos"
                        worksheet_name = "Administracion_Financiera"
                        
                        # Configuración de modo de comparación
                        st.markdown("**Modo de comparación:**")
                        comparison_mode = st.selectbox(
                            "Tipo de validación de duplicados",
                            options=['exact', 'fuzzy'],
                            index=0,
                            help="Exact: comparación exacta de caracteres. Fuzzy: comparación normalizada (ignora mayúsculas, espacios extra)"
                        )
                        
                        if comparison_mode == 'exact':
                            st.info("🔍 **Modo Exacto**: Los registros deben coincidir exactamente en las columnas seleccionadas")
                        else:
                            st.info("🔍 **Modo Flexible**: Se normalizan mayúsculas, espacios y caracteres especiales")
                    
                    with col2:
                        st.markdown("**Configuración de validación de duplicados:**")
                        
                        # Mostrar columnas disponibles en el DataFrame
                        available_columns = list(final_df.columns)
                        st.info(f"Columnas disponibles: {', '.join(available_columns)}")
                        
                        duplicate_columns = st.multiselect(
                            "Columnas para detectar duplicados",
                            options=available_columns,
                            default=[col for col in ['Monto', 'Fecha', 'Unidad', 'Concepto'] if col in available_columns],
                            help="Selecciona las columnas que se usarán para identificar registros duplicados"
                        )
                        
                        validate_duplicates = st.checkbox(
                            "Validar duplicados antes de subir",
                            value=True,
                            help="Desactiva esta opción para permitir registros duplicados"
                        )
                        
                        # Botón para pre-validar registros
                        #if st.button("🔍 Pre-validar duplicados", help="Ejecutar validación sin subir datos"):

                            ###########################

                            #if validate_duplicates and duplicate_columns:
                            #    with st.spinner("🔍 Ejecutando pre-validación..."):
                            #        try:
                                        # Obtener datos existentes para validación
                            #            sheet = client.open(sheet_name)
                            #            worksheet = sheet.worksheet(worksheet_name)
                            #            existing_data = worksheet.get_all_records()
                            #            existing_df = pd.DataFrame(existing_data)
                                        
                                        # Ejecutar validación
                            #            unique_records, duplicate_records, validation_report = validate_existing_records(
                            #                final_df,
                            #                existing_df,
                            #                duplicate_columns,
                            #                comparison_mode
                            #            )
                                      
                                        
                                        # Mostrar resultados
                            #            col_a, col_b, col_c = st.columns(3)
                            #            with col_a:
                            #                st.metric("Registros únicos", len(unique_records), delta=f"{len(unique_records) - len(final_df)}")
                            #            with col_b:
                            #                st.metric("Duplicados encontrados", len(duplicate_records))
                            #            with col_c:
                            #                pass
                                            #st.metric("% Duplicados", f"{validation_report['porcentaje_duplicados']:.1f}%")
                                        
                            #            if len(duplicate_records) > 0:
                            #                st.warning(f"⚠️ Se encontraron {len(duplicate_records)} registros duplicados")
                            #                with st.expander("Ver registros duplicados"):
                            #                    display_cols = [col for col in duplicate_columns if col in duplicate_records.columns]
                            #                    st.dataframe(duplicate_records[display_cols])
                            #            else:
                            #                st.success("✅ No se encontraron registros duplicados")
                                            
                            #        except Exception as e:
                            #            st.error(f"Error en pre-validación: {str(e)}")
                            #else:
                            #    st.warning("⚠️ Selecciona columnas para validar duplicados")
                    
                    # Validar selección de columnas para duplicados
                    if validate_duplicates and not duplicate_columns:
                        st.warning("⚠️ Si quieres validar duplicados, debes seleccionar al menos una columna")
                    
                    # Mostrar resumen antes de subir
                    if not final_df.empty:
                        st.subheader("📋 Resumen de datos a subir")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Registros", len(final_df))
                        with col2:
                            total_monto = final_df['Monto'].sum() if 'Monto' in final_df.columns else 0
                            st.metric("Total Monto", f"${total_monto:,.2f}")
                        with col3:
                            pendientes = len(final_df[final_df['Estado'] == 'Pendiente']) if 'Estado' in final_df.columns else 0
                            st.metric("Pendientes", pendientes)
                        with col4:
                            pagados = len(final_df[final_df['Estado'] == 'Pagado']) if 'Estado' in final_df.columns else 0
                            st.metric("Pagados", pagados)
                        
                        # Mostrar configuración de validación
                        if validate_duplicates and duplicate_columns:
                            st.info(f"🔍 **Validación de duplicados activada** usando las columnas: {', '.join(duplicate_columns)} (modo: {comparison_mode})")
                        elif validate_duplicates:
                            st.warning("⚠️ **Validación de duplicados desactivada** - No se seleccionaron columnas")
                        else:
                            st.warning("⚠️ **Validación de duplicados desactivada** - Se permitirán registros duplicados")
                        
                        # Botón de carga principal
                        if st.button("🚀 Subir a Google Sheets", type="primary", help="Subir datos con validación de duplicados"):
                            # Validar que si se quiere validar duplicados, se hayan seleccionado columnas
                            if validate_duplicates and not duplicate_columns:
                                st.error("❌ Para validar duplicados, debes seleccionar al menos una columna")
                            else:
                                with st.spinner("📤 Subiendo datos con validación completa..."):
                                    # Usar la nueva función integrada de validación
                                    success, message = upload_to_google_sheets_with_validation(
                                        client=client,
                                        df=final_df,
                                        sheet_name="gestion-conjuntos",  #sheet_name,
                                        worksheet_name= "Administracion_Financiera", #worksheet_name,
                                        validate_duplicates=validate_duplicates,
                                        duplicate_columns=duplicate_columns if validate_duplicates else None,
                                        comparison_mode=comparison_mode
                                    )
                                
                                if success:
                                    st.success(message)
                                    st.balloons()
                                    
                                    # Mostrar resumen final
                                    with st.expander("📊 Resumen detallado de la carga"):
                                        st.write("**Configuración utilizada:**")
                                        st.write(f"- Hoja: {sheet_name}")
                                        st.write(f"- Pestaña: {worksheet_name}")
                                        st.write(f"- Validación de duplicados: {'Activada' if validate_duplicates else 'Desactivada'}")
                                        if validate_duplicates:
                                            st.write(f"- Columnas de validación: {', '.join(duplicate_columns)}")
                                            st.write(f"- Modo de comparación: {comparison_mode}")
                                        st.write(f"- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                    
                                    # Limpiar cache para refrescar datos
                                    if hasattr(st, 'cache_data'):
                                        st.cache_data.clear()
                                else:
                                    st.error(message)
                                    
                                    # Mostrar sugerencias para resolver problemas
                                    with st.expander("💡 Sugerencias para resolver problemas"):
                                        st.write("**Si continúas teniendo problemas:**")
                                        st.write("1. Verifica que las columnas seleccionadas existen en ambos lugares")
                                        st.write("2. Prueba cambiando el modo de comparación (exact/fuzzy)")
                                        st.write("3. Usa la función 'Pre-validar duplicados' para diagnosticar")
                                        st.write("4. Verifica los permisos de acceso a Google Sheets")
                    else:
                        st.warning("⚠️ No hay datos para subir")
                else:
                    st.error("❌ No se pudieron procesar los datos del CSV")
            else:
                st.error(f"❌ {message}")
                st.info("Por favor, asegúrate de que el CSV contenga las columnas requeridas")
        
        except Exception as e:
            st.error(f"❌ Error leyendo el archivo CSV: {str(e)}")
            st.exception(e)
            
            # Mostrar información de debugging
            with st.expander("🔧 Información de debugging"):
                st.write("**Detalles del error:**")
                st.code(str(e))
                if hasattr(e, '__traceback__'):
                    import traceback
                    st.code(traceback.format_exc())

    
    # Información adicional
    st.markdown("---")
    st.subheader("ℹ️ Información")
    
    with st.expander("📋 Estructura esperada del CSV"):
        st.markdown("""
        **Columnas requeridas:**
        - `Monto`: Cantidad del pago (numérico)
        - `Fecha`: Fecha del pago (formato: YYYY-MM-DD o similar)
        
        **Columnas opcionales:**
        - `Tipo_Operacion`: Tipo de operación (por defecto: "Cuota de Mantenimiento")
        - `Unidad`: Unidad o apartamento
        - `Concepto`: Descripción del pago
        - `Banco`: Entidad bancaria
        - `Estado`: Estado del pago (por defecto: "Pendiente")
        - `Metodo_Pago`: Método utilizado para el pago
        - `Soporte_Pago`: Referencia del soporte
        - `Numero_Recibo`: Número de recibo
        - `Observaciones`: Comentarios adicionales
        """)
    
    with st.expander("✏️ Funcionalidades del Editor"):
        st.markdown("""
        **Vista y Edición:**
        - Edita directamente los valores en la tabla
        - Validación automática de tipos de datos
        - Estadísticas en tiempo real
        
        **Agregar Filas:**
        - Formulario para agregar nuevos registros
        - Validación de campos obligatorios
        - Generación automática de IDs
        
        **Eliminar Filas:**
        - Selección múltiple de filas
        - Vista previa antes de eliminar
        - Confirmación de eliminación
        
        **Acciones:**
        - Restaurar datos originales
        - Limpiar todos los datos
        - Exportar datos editados
        - Validaciones automáticas
        """)

if __name__ == "__main__":
    csv_main()