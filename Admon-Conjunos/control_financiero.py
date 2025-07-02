import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, timedelta
import uuid
import hashlib

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión Financiera - Conjuntos",
#    page_icon="🏢",
#    layout="wide"
#)

import logging
logging.basicConfig(level=logging.DEBUG, filename='control_financiero.log', filemode='w', 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

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

def load_data_from_sheet(client, sheet_name, worksheet_name):
    """Cargar datos desde una hoja específica"""
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"⚠️ La hoja '{worksheet_name}' no existe. Se creará automáticamente.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando datos de {worksheet_name}: {str(e)}")
        return None

def generate_unique_key(unidad, concepto, fecha_vencimiento):
    """Generar una clave única para identificar registros duplicados"""
    try:
        # Normalizar datos para crear una clave consistente
        unidad_str = str(unidad).strip().upper() if unidad else ""
        concepto_str = str(concepto).strip().upper() if concepto else ""
        
        # Convertir fecha a string formato estándar
        if isinstance(fecha_vencimiento, str):
            fecha_str = fecha_vencimiento.strip()
        elif pd.isna(fecha_vencimiento) or fecha_vencimiento is None:
            fecha_str = ""
        else:
            try:
                if hasattr(fecha_vencimiento, 'strftime'):
                    fecha_str = fecha_vencimiento.strftime('%Y-%m-%d')
                else:
                    fecha_str = str(fecha_vencimiento).strip()
            except:
                fecha_str = str(fecha_vencimiento).strip()
        
        # Crear string único y generar hash
        unique_string = f"{unidad_str}|{concepto_str}|{fecha_str}"
        hash_key = hashlib.md5(unique_string.encode()).hexdigest()[:12]
        
        # Debug info (solo mostrar en desarrollo)
        if st.session_state.get('debug_mode', False):
            st.write(f"Debug - Clave generada: {unique_string} -> {hash_key}")
        
        return hash_key
    
    except Exception as e:
        st.warning(f"Error generando clave única: {str(e)}")
        return str(uuid.uuid4())[:12]

def get_existing_keys_from_sheet(client, sheet_name):
    """Obtener todas las claves únicas existentes en la hoja de morosos"""
    try:
        existing_morosos_df = load_data_from_sheet(client, sheet_name, "gestion_morosos")
        
        if existing_morosos_df is None or existing_morosos_df.empty:
            st.info("ℹ️ No existen registros previos en gestión de morosos")
            return set(), pd.DataFrame()
       
        # Si no existe la columna Clave_Unica, crearla
        if 'Clave_Unica' not in existing_morosos_df.columns:
            st.info("🔄 Creando claves únicas para registros existentes...")
            existing_morosos_df['Clave_Unica'] = existing_morosos_df.apply(
                lambda row: generate_unique_key(
                    row.get('Apartamento/Casa', ''), 
                    row.get('Concepto_Deuda', ''), 
                    row.get('Fecha_Vencimiento', '')
                ), axis=1
            )
            
            # Actualizar la hoja con las nuevas claves únicas
            success = update_sheet_data(client, sheet_name, "gestion_morosos", existing_morosos_df)
            if success:
                st.success("✅ Claves únicas agregadas a registros existentes")
            else:
                st.error("❌ Error actualizando claves únicas en la hoja")
        
        # Obtener todas las claves únicas existentes
        existing_keys = set()
        for key in existing_morosos_df['Clave_Unica'].tolist():
            if key and str(key).strip():  # Solo agregar claves válidas
                existing_keys.add(str(key).strip())
        
        return existing_keys, existing_morosos_df
        
    except Exception as e:
        st.error(f"Error obteniendo claves existentes: {str(e)}")
        return set(), pd.DataFrame()

def filter_new_records_only(nuevos_morosos_df, existing_keys):
    """Filtrar solo los registros completamente nuevos"""
    try:
        if nuevos_morosos_df.empty:
            return pd.DataFrame(), [], []
        
        # Generar claves únicas para los nuevos registros
        nuevos_morosos_df['Clave_Unica'] = nuevos_morosos_df.apply(
            lambda row: generate_unique_key(
                row['Apartamento/Casa'], 
                row['Concepto_Deuda'], 
                row['Fecha_Vencimiento']
            ), axis=1
        )
        
        # Identificar registros completamente nuevos
        nuevos_keys = set(nuevos_morosos_df['Clave_Unica'].tolist())
        
        # Registros que NO existen en la base de datos
        keys_verdaderamente_nuevas = nuevos_keys - existing_keys
        
        # Filtrar solo registros nuevos
        mask_nuevos = nuevos_morosos_df['Clave_Unica'].isin(keys_verdaderamente_nuevas)
        registros_completamente_nuevos = nuevos_morosos_df[mask_nuevos].copy()
        
        # Identificar duplicados exactos
        keys_duplicadas = nuevos_keys & existing_keys
        mask_duplicados = nuevos_morosos_df['Clave_Unica'].isin(keys_duplicadas)
        registros_duplicados = nuevos_morosos_df[mask_duplicados].copy()
        
        # Crear listas para reporte
        nuevos_para_reporte = registros_completamente_nuevos[['Apartamento/Casa', 'Propietario', 'Concepto_Deuda', 'Fecha_Vencimiento', 'Saldo_Pendiente']].to_dict('records')
        duplicados_para_reporte = registros_duplicados[['Apartamento/Casa', 'Propietario', 'Concepto_Deuda', 'Fecha_Vencimiento', 'Saldo_Pendiente']].to_dict('records')
        
        st.info(f"🔍 Análisis de registros:")
        st.info(f"  • Total candidatos: {len(nuevos_morosos_df)}")
        st.info(f"  • Completamente nuevos: {len(registros_completamente_nuevos)}")
        
        return registros_completamente_nuevos, nuevos_para_reporte, duplicados_para_reporte
        
    except Exception as e:
        st.error(f"Error filtrando registros nuevos: {str(e)}")
        return pd.DataFrame(), [], []

def safe_float_conversion(value):
    """Safely convert values to float, handling various input types"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove common formatting
        cleaned = value.strip().replace(',', '').replace('$', '')
        if cleaned == '' or cleaned.lower() == 'nan':
            return 0.0
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    return 0.0

def safe_date_conversion(date_value):
    """Safely convert date values"""
    if pd.isna(date_value):
        return pd.NaT
    if isinstance(date_value, str) and date_value.strip() == '':
        return pd.NaT
    try:
        return pd.to_datetime(date_value)
    except:
        return pd.NaT

def get_period_from_date(date_value):
    """Obtener período (YYYY-MM) de una fecha de manera segura"""
    try:
        dt = safe_date_conversion(date_value)
        if pd.isna(dt):
            return None
        return dt.strftime('%Y-%m')
    except:
        return None

def identify_morosos_to_remove(df_admin, existing_morosos_df):
    """Identificar registros de morosos que deben ser eliminados por pagos completos"""
    try:
        if existing_morosos_df is None or existing_morosos_df.empty:
            st.info("ℹ️ No hay registros de morosos para verificar eliminación")
            return pd.DataFrame(), []
        
        # Clean and convert Saldo_Pendiente columns to numeric at the start
        df_admin = df_admin.copy()
        existing_morosos_df = existing_morosos_df.copy()
        
        # Aggressive cleaning of Saldo_Pendiente columns
        df_admin['Saldo_Pendiente'] = df_admin['Saldo_Pendiente'].replace('', '0').fillna('0')
        existing_morosos_df['Saldo_Pendiente'] = existing_morosos_df['Saldo_Pendiente'].replace('', '0').fillna('0')
        
        # Convert to numeric, coercing errors to 0
        df_admin['Saldo_Pendiente'] = pd.to_numeric(df_admin['Saldo_Pendiente'], errors='coerce').fillna(0.0)
        existing_morosos_df['Saldo_Pendiente'] = pd.to_numeric(existing_morosos_df['Saldo_Pendiente'], errors='coerce').fillna(0.0)
        
        # Filtrar solo cuotas de mantenimiento pagadas con saldo <= 0
        cuotas_pagadas = df_admin[
            (df_admin['Tipo_Operacion'] == 'Cuota de Mantenimiento') &
            (df_admin['Estado'] == 'Aldia') &
            (df_admin['Saldo_Pendiente'] <= 0)
        ].copy()
        
        if cuotas_pagadas.empty:
            st.info("ℹ️ No se encontraron cuotas pagadas completamente")
            return existing_morosos_df, []
        
        # Convertir fechas y crear períodos para cuotas pagadas
        cuotas_pagadas['Fecha_dt'] = cuotas_pagadas['Fecha'].apply(safe_date_conversion)
        cuotas_pagadas = cuotas_pagadas[~pd.isna(cuotas_pagadas['Fecha_dt'])].copy()
        cuotas_pagadas['periodo'] = cuotas_pagadas['Fecha_dt'].apply(
            lambda x: x.strftime('%Y-%m') if not pd.isna(x) else None
        )
        cuotas_pagadas = cuotas_pagadas[~pd.isna(cuotas_pagadas['periodo'])].copy()
        
        # Preparar DataFrame de morosos para comparación
        existing_morosos_df['Fecha_Venc_dt'] = existing_morosos_df['Fecha_Vencimiento'].apply(safe_date_conversion)
        existing_morosos_df['periodo_moroso'] = existing_morosos_df['Fecha_Venc_dt'].apply(
            lambda x: x.strftime('%Y-%m') if not pd.isna(x) else None
        )
        
        # Identificar morosos que corresponden a cuotas ya pagadas
        morosos_a_eliminar = []
        indices_a_eliminar = []
        
        for idx, moroso in existing_morosos_df.iterrows():
            try:
                # Solo procesar cuotas de mantenimiento
                concepto_deuda = str(moroso.get('Concepto_Deuda', '')).strip().upper()
                if concepto_deuda != 'CUOTA DE MANTENIMIENTO':
                    #continue
                
                    # Buscar pagos correspondientes
                    unidad_moroso = str(moroso.get('Apartamento/Casa', '')).strip()
                    periodo_moroso = moroso.get('periodo_moroso')
                
                if not unidad_moroso or not periodo_moroso:
                    continue
                
                # Verificar si existe pago completo para esta unidad y período
                pagos_correspondientes = cuotas_pagadas[
                    (cuotas_pagadas['Unidad'].astype(str).str.strip() == unidad_moroso) &
                    (cuotas_pagadas['periodo'] == periodo_moroso)
                ]

                if not pagos_correspondientes.empty:
                    # Verificar que el saldo pendiente sea efectivamente <= 0
                    saldo_total_pagado = pagos_correspondientes['Saldo_Pendiente'].sum()
                    
                    if saldo_total_pagado <= 0:
                        morosos_a_eliminar.append({
                            'Apartamento/Casa': unidad_moroso,
                            'Propietario': str(moroso.get('Propietario', '')),
                            'Concepto_Deuda': str(moroso.get('Concepto_Deuda', '')),
                            'Fecha_Vencimiento': str(moroso.get('Fecha_Vencimiento', '')),
                            'Saldo_Pendiente': float(moroso.get('Saldo_Pendiente', 0)),
                            'Periodo': periodo_moroso,
                            'Motivo': f'Pago completo detectado - Saldo actual: ${saldo_total_pagado:,.2f}'
                        })
                        indices_a_eliminar.append(idx)
                        
            except Exception as e:
                st.warning(f"Error procesando moroso en índice {idx}: {str(e)}")
                continue
        
        # Crear DataFrame sin los registros a eliminar
        if indices_a_eliminar:
            morosos_actualizados = existing_morosos_df.drop(indices_a_eliminar).reset_index(drop=True)
            morosos_actualizados = clean_dataframe_for_arrow(morosos_actualizados)
            st.success(f"🗑️ Se identificaron {len(morosos_a_eliminar)} registros de morosos para eliminar")
        else:
            morosos_actualizados = existing_morosos_df
            morosos_actualizados = clean_dataframe_for_arrow(morosos_actualizados)
            st.info("ℹ️ No se encontraron registros de morosos para eliminar")
        
        return morosos_actualizados, morosos_a_eliminar
        
    except Exception as e:
        st.error(f"Error identificando morosos para eliminar: {str(e)}")
        fallback_df = existing_morosos_df if existing_morosos_df is not None else pd.DataFrame()
        if not fallback_df.empty:
            fallback_df = clean_dataframe_for_arrow(fallback_df)
        return fallback_df, []

def clean_dataframe_for_arrow(df):
    """Clean DataFrame to ensure Arrow compatibility"""
    if df.empty:
        return df
    
    df_clean = df.copy()
    
    # Fix ALL columns that might have mixed types
    for col in df_clean.columns:
        if col == 'Saldo_Pendiente':
            # Handle numeric columns
            df_clean[col] = df_clean[col].replace('', '0').fillna('0')
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0.0)
        else:
            # Handle string columns - convert everything to string and handle NaN
            df_clean[col] = df_clean[col].astype(str).replace('nan', '').replace('<NA>', '')
    
    # Ensure proper dtypes
    if 'Saldo_Pendiente' in df_clean.columns:
        df_clean['Saldo_Pendiente'] = df_clean['Saldo_Pendiente'].astype('float64')
    
    return df_clean

def remove_resolved_morosos(existing_morosos_df, morosos_eliminados):
    """Elimina los registros de morosos que ya están resueltos"""
    if not morosos_eliminados or existing_morosos_df is None:
        return existing_morosos_df
    
    # Crear una copia del DataFrame
    morosos_df_actualizado = existing_morosos_df.copy()
    
    # Crear índices para eliminar
    indices_to_remove = []
    
    for moroso_eliminado in morosos_eliminados:
        # Verificar si es un diccionario o una Serie de pandas
        if isinstance(moroso_eliminado, dict):
            apartamento = moroso_eliminado.get('Apartamento/Casa', '')
            propietario = moroso_eliminado.get('Propietario', '')
        elif hasattr(moroso_eliminado, 'get'):  # Serie de pandas
            apartamento = moroso_eliminado.get('Apartamento/Casa', '')
            propietario = moroso_eliminado.get('Propietario', '')
        else:
            # Si es otro tipo de objeto, intentar acceso por índice
            try:
                if hasattr(moroso_eliminado, '__getitem__'):
                    apartamento = moroso_eliminado['Apartamento/Casa'] if 'Apartamento/Casa' in moroso_eliminado else ''
                    propietario = moroso_eliminado['Propietario'] if 'Propietario' in moroso_eliminado else ''
                else:
                    continue
            except (KeyError, TypeError, IndexError):
                continue
        
        # Encontrar el índice del registro a eliminar
        try:
            match_index = morosos_df_actualizado[
                (morosos_df_actualizado['Apartamento/Casa'].astype(str).str.strip() == str(apartamento).strip()) &
                (morosos_df_actualizado['Propietario'].astype(str).str.strip() == str(propietario).strip())
            ].index
            
            if not match_index.empty:
                indices_to_remove.extend(match_index.tolist())
        except Exception as e:
            continue
    
    # Eliminar los registros
    if indices_to_remove:
        morosos_df_actualizado = morosos_df_actualizado.drop(indices_to_remove).reset_index(drop=True)
    
    return morosos_df_actualizado

def update_sheet_data(client, sheet_name, worksheet_name, df):
    """Actualizar datos en la hoja de Google Sheets"""
    try:
        if df.empty:
            st.warning(f"DataFrame vacío para {worksheet_name}")
            return True
            
        sheet = client.open(sheet_name)
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # Crear la hoja si no existe
            worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=26)
            st.success(f"✅ Hoja '{worksheet_name}' creada exitosamente")
        
        # Limpiar la hoja completamente
        worksheet.clear()
        
        # Agregar headers
        headers = df.columns.tolist()
        worksheet.append_row(headers)
        
        # Escribir datos
        if not df.empty:
            # Convertir DataFrame a lista de listas, manejando tipos de datos
            data_list = []
            for _, row in df.iterrows():
                row_data = []
                for value in row:
                    if pd.isna(value):
                        row_data.append("")
                    elif isinstance(value, (int, float)):
                        row_data.append(float(value) if not pd.isna(value) else 0)
                    else:
                        row_data.append(str(value))
                data_list.append(row_data)
            
            # Insertar datos por lotes para mayor eficiencia
            if data_list:
                worksheet.append_rows(data_list)
        
        return True
    except Exception as e:
        st.error(f"Error actualizando {worksheet_name}: {str(e)}")
        return False

def insert_new_records_only(client, sheet_name, worksheet_name, df_nuevos):
    """Insertar SOLO registros completamente nuevos"""
    try:
        if df_nuevos.empty:
            return True
        
        sheet = client.open(sheet_name)
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # Crear la hoja si no existe
            worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=26)
            st.success(f"✅ Hoja '{worksheet_name}' creada exitosamente")
        
        # Verificar si la hoja está vacía y agregar headers si es necesario
        existing_data = worksheet.get_all_records()
        if not existing_data:
            headers = df_nuevos.columns.tolist()
            worksheet.append_row(headers)
        
        # Insertar SOLO los nuevos datos
        data_list = []
        for _, row in df_nuevos.iterrows():
            row_data = []
            for value in row:
                if pd.isna(value):
                    row_data.append("")
                elif isinstance(value, (int, float)):
                    row_data.append(float(value) if not pd.isna(value) else 0)
                else:
                    row_data.append(str(value))
            data_list.append(row_data)
        
        if data_list:
            worksheet.append_rows(data_list)
            st.success(f"✅ Se insertaron {len(data_list)} registros COMPLETAMENTE NUEVOS")
        
        return True
    except Exception as e:
        st.error(f"Error insertando registros nuevos en {worksheet_name}: {str(e)}")
        return False

def process_maintenance_fees(df_admin, df_residents):
    """Procesar cuotas de mantenimiento y realizar cruces"""
    try:
        # Hacer una copia del DataFrame para evitar modificaciones no deseadas
        df_admin_copy = df_admin.copy()
        
        # Filtrar registros de cuotas de mantenimiento
        cuotas_df = df_admin_copy[df_admin_copy['Tipo_Operacion'] == 'Cuota de Mantenimiento'].copy()
        
        if cuotas_df.empty:
            st.warning("No se encontraron registros de Cuota de Mantenimiento")
            return df_admin_copy, pd.DataFrame(), []
        
        # Convertir fechas de manera segura y crear periodo
        cuotas_df['Fecha_dt'] = cuotas_df['Fecha'].apply(safe_date_conversion)
        
        # Eliminar registros sin fecha válida
        valid_dates_mask = ~pd.isna(cuotas_df['Fecha_dt'])
        cuotas_df = cuotas_df[valid_dates_mask].copy()
        
        if cuotas_df.empty:
            st.warning("No se encontraron registros con fechas válidas")
            return df_admin_copy, pd.DataFrame(), []
        
        # Crear período usando la función segura
        cuotas_df['periodo'] = cuotas_df['Fecha_dt'].apply(lambda x: x.strftime('%Y-%m') if not pd.isna(x) else None)
        
        # Eliminar registros sin período válido
        cuotas_df = cuotas_df[~pd.isna(cuotas_df['periodo'])].copy()
        
        if cuotas_df.empty:
            st.warning("No se pudieron generar períodos válidos")
            return df_admin_copy, pd.DataFrame(), []
        
        # Separar registros pagados y pendientes
        # Use bitwise & operator for multiple conditions on DataFrames
        pagados = cuotas_df[
            (cuotas_df['Estado'] == 'Pagado') & 
            (cuotas_df['Registrado'] == 'Principal')
        ].copy()
        
        pendientes = cuotas_df[cuotas_df['Estado'] == 'Pendiente'].copy()
        
        st.info(f"📊 Procesando: {len(pagados)} pagados, {len(pendientes)} pendientes")
        
        actualizados = []
        morosos_data = []
        
        for idx, pendiente in pendientes.iterrows():
            try:
                # Buscar pagos correspondientes
                pagos_relacionados = pagados[
                    (pagados['Unidad'] == pendiente['Unidad']) &
                    (pagados['periodo'] == pendiente['periodo'])
                ]
               
                # Convertir montos a float de manera segura
                monto_pendiente = safe_float_conversion(pendiente['Monto'])
                total_pagado = 0
                pagos_aplicados = []  # Para rastrear los pagos que se aplicaron
                
                if not pagos_relacionados.empty:
                    for _, pago in pagos_relacionados.iterrows():
                        monto_pago = safe_float_conversion(pago['Monto'])
                        total_pagado += monto_pago
                        pagos_aplicados.append(pago.name)  # Guardar índice del pago aplicado
                
                # Calcular saldo pendiente
                saldo_pendiente = monto_pendiente - total_pagado
                
                # Actualizar el registro pendiente en el DataFrame original
                df_admin_copy.loc[df_admin_copy.index == idx, 'Saldo_Pendiente'] = saldo_pendiente
                
                if saldo_pendiente <= 0:
                    df_admin_copy.loc[df_admin_copy.index == idx, 'Estado'] = 'Aldia'
                    actualizados.append(f"Unidad {pendiente['Unidad']} - Periodo {pendiente['periodo']}")
                    
                    # Actualizar los pagos aplicados a 'Aplicado'
                    for pago_idx in pagos_aplicados:
                        df_admin_copy.loc[df_admin_copy.index == pago_idx, 'Estado'] = 'Aplicado'
                        
                else:
                    # Si hay pagos parciales, también marcarlos como aplicados
                    if pagos_aplicados:
                        for pago_idx in pagos_aplicados:
                            df_admin_copy.loc[df_admin_copy.index == pago_idx, 'Estado'] = 'Aplicado'
                    
                    # Crear registro para morosos solo si tiene más de 30 días de mora
                    moroso_record = create_moroso_record(pendiente, df_residents, pagos_relacionados, saldo_pendiente, monto_pendiente)
                    if moroso_record and moroso_record['Dias_Mora'] > 30:
                        morosos_data.append(moroso_record)
                        
            except Exception as e:
                st.warning(f"Error procesando registro en índice {idx}: {str(e)}")
                continue
        
        morosos_df = pd.DataFrame(morosos_data) if morosos_data else pd.DataFrame()
        
        return df_admin_copy, morosos_df, actualizados
        
    except Exception as e:
        st.error(f"Error procesando cuotas de mantenimiento: {str(e)}")
        return df_admin, pd.DataFrame(), []

def create_moroso_record(pendiente, df_residents, pagos_relacionados, saldo_pendiente, monto_original):
    """Crear registro de moroso"""
    try:
        # Buscar información del residente - FIX: Usar & en lugar de and
        residente_info = df_residents[
            (df_residents['Tipo'] == 'Propietario') & 
            (df_residents['Unidad'] == pendiente['Unidad'])
        ]
        
        if residente_info.empty:
            # Crear registro con información mínima
            residente_data = {
                'Nombre': 'No especificado',
                'Apellido': '',
                'Identificacion': 'No especificado',
                'Telefono': 'No especificado',
                'Email': 'No especificado'
            }
        else:
            residente_data = residente_info.iloc[0].to_dict()
        
        # Calcular días de mora de manera segura
        try:
            fecha_vencimiento = safe_date_conversion(pendiente['Fecha'])
            if pd.isna(fecha_vencimiento):
                dias_mora = 0
            else:
                dias_mora = max(0, (datetime.now() - fecha_vencimiento).days)
        except:
            dias_mora = 0
        
        # Información de pago (si existe)
        valor_pagado = 0
        fecha_pago = ""
        
        if not pagos_relacionados.empty:
            try:
                # Convertir montos de pagos de manera segura
                for _, pago in pagos_relacionados.iterrows():
                    valor_pagado += safe_float_conversion(pago['Monto'])
                
                # Obtener fecha de pago más reciente
                fechas_pago = pagos_relacionados['Fecha'].apply(safe_date_conversion)
                fechas_validas = fechas_pago.dropna()
                if not fechas_validas.empty:
                    fecha_pago = fechas_validas.max().strftime('%Y-%m-%d')
            except:
                valor_pagado = 0
                fecha_pago = ""
        
        # Crear el registro de moroso
        moroso_record = {
            'ID': pendiente.get('ID', ''),
            'Fecha_Registro': datetime.now().strftime('%Y-%m-%d'),
            'Apartamento/Casa': str(pendiente['Unidad']) if pendiente['Unidad'] else '',
            'Propietario': f"{residente_data.get('Nombre', '')} {residente_data.get('Apellido', '')}".strip(),
            'Cedula': str(residente_data.get('Identificacion', '')) if residente_data.get('Identificacion') else '',
            'Telefono': str(residente_data.get('Telefono', '')) if residente_data.get('Telefono') else '',
            'Email': str(residente_data.get('Email', '')) if residente_data.get('Email') else '',
            'Valor_Deuda': float(monto_original) if monto_original else 0,
            'Concepto_Deuda': str(pendiente.get('Concepto', 'Cuota de Mantenimiento')),
            'Fecha_Vencimiento': fecha_vencimiento.strftime('%Y-%m-%d') if not pd.isna(fecha_vencimiento) else '',
            'Dias_Mora': int(dias_mora),
            'Estado_Gestion':'',
            'Tipo_Gestion':'',
            'Fecha_Ultimo_Contacto':'',
            'Observaciones': 'Proceso Control Financiero',
            'Accion_Juridica':'',
            'Fecha_Accion_Juridica':'',
            'Valor_Pagado': float(valor_pagado),
            'Fecha_Pago': fecha_pago,
            'Saldo_Pendiente': float(saldo_pendiente),
            'Iteres_Mora': 0,
            'Saldo_Total': float(saldo_pendiente),
            'Clave_Unica': '',  # Se generará después
            'Fecha_Venc_dt': fecha_vencimiento.strftime('%Y-%m-%d') if not pd.isna(fecha_vencimiento) else '',
            'periodo_moroso': get_period_from_date(fecha_vencimiento)
        }
        
        # Generar clave única
        moroso_record['Clave_Unica'] = generate_unique_key(
            moroso_record['Apartamento/Casa'],
            moroso_record['Concepto_Deuda'],
            moroso_record['Fecha_Vencimiento']
        )
        
        return moroso_record
        
    except Exception as e:
        st.error(f"Error creando registro de moroso para unidad {pendiente.get('Unidad', 'desconocida')}: {str(e)}")
        return None

def control_main():
  st.title("🏢 Proceso para la Gestión Financiera")
  st.markdown("---")
    
  import traceback
  try:
    
    # Inicializar session_state
    if 'datos_procesados' not in st.session_state:
        st.session_state.datos_procesados = False
    if 'df_admin_updated' not in st.session_state:
        st.session_state.df_admin_updated = None
    if 'morosos_df_nuevos' not in st.session_state:
        st.session_state.morosos_df_nuevos = None
    if 'actualizados' not in st.session_state:
        st.session_state.actualizados = []
    if 'processed_sheet_name' not in st.session_state:
        st.session_state.processed_sheet_name = None
    if 'duplicados_encontrados' not in st.session_state:
        st.session_state.duplicados_encontrados = []
    if 'nuevos_para_reporte' not in st.session_state:
        st.session_state.nuevos_para_reporte = []
    if 'morosos_eliminados' not in st.session_state:
        st.session_state.morosos_eliminados = []
    if 'morosos_df_actualizado' not in st.session_state:
        st.session_state.morosos_df_actualizado = None
    if 'existing_morosos_df' not in st.session_state:
        st.session_state.existing_morosos_df = None
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Configuración del archivo
    sheet_name = "gestion-conjuntos"   #st.text_input("Nombre del archivo de Google Sheets:",  value="gestion-conjuntos", key="sheet_name")
    
    # Botón para procesar datos
    if st.button("🔄 Procesar Datos Financieros", type="primary"):
        if not sheet_name:
            st.error("Por favor ingresa el nombre del archivo")
            return
        
        with st.spinner("Cargando datos..."):
            # Cargar datos
            df_admin = load_data_from_sheet(client, sheet_name, "Administracion_Financiera")
            df_residents = load_data_from_sheet(client, sheet_name, "Control_Residentes")
            
            if df_admin is None or df_residents is None:
                st.error("Error cargando los datos. Verifica el nombre del archivo y las hojas.")
                return
        
        st.success("✅ Datos cargados correctamente")
        
        # Mostrar información básica
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Registros Administración", len(df_admin))
        with col2:
            st.metric("Registros Residentes", len(df_residents))
        
        with st.spinner("Procesando cuotas de mantenimiento..."):
            # Procesar datos
            df_admin_updated, morosos_df_candidatos, actualizados = process_maintenance_fees(df_admin, df_residents)

        # Cargar morosos existentes para identificar los que deben eliminarse
        with st.spinner("Cargando registros de morosos existentes..."):
            existing_morosos_df = load_data_from_sheet(client, sheet_name, "gestion_morosos")
            #print(f'Cargando registros de morosos existentes...: {existing_morosos_df}')
            if existing_morosos_df is not None:
                st.session_state.existing_morosos_df = existing_morosos_df
        
        # NUEVO: Verificación exhaustiva de duplicados
        duplicados_encontrados = []
        nuevos_para_reporte = []
        morosos_eliminados = []
        morosos_df_nuevos = pd.DataFrame()
        
        if not morosos_df_candidatos.empty:
            with st.spinner("🔍 Verificación exhaustiva de duplicados..."):
                # Obtener todas las claves existentes
                existing_keys, existing_df = get_existing_keys_from_sheet(client, sheet_name)
                
                # Filtrar SOLO registros completamente nuevos
                morosos_df_nuevos, nuevos_para_reporte, duplicados_encontrados = filter_new_records_only(morosos_df_candidatos, existing_keys)


        # Identificar morosos que deben eliminarse (ya no están en mora)
        if st.session_state.existing_morosos_df is not None:
            with st.spinner("🔍 Identificando morosos a eliminar..."):
                morosos_df_actualizado, morosos_eliminados = identify_morosos_to_remove(df_admin_updated , st.session_state.existing_morosos_df)
                #print(f'Identificando morosos a eliminar...: {morosos_df_actualizado}, {morosos_eliminados}')
        # Guardar en session_state
        st.session_state.df_admin_updated = df_admin_updated
        st.session_state.morosos_df_nuevos = morosos_df_nuevos
        st.session_state.actualizados = actualizados
        st.session_state.duplicados_encontrados = duplicados_encontrados
        st.session_state.nuevos_para_reporte = nuevos_para_reporte
        st.session_state.morosos_eliminados = morosos_eliminados
        st.session_state.datos_procesados = True
        st.session_state.processed_sheet_name = sheet_name
    
    # Mostrar resultados si ya se procesaron los datos
    if st.session_state.datos_procesados:
        st.markdown("### 📊 Resultados del Procesamiento")
        
        if st.session_state.actualizados:
            st.success(f"✅ Se actualizaron {len(st.session_state.actualizados)} registros a estado 'Pagado'")
            with st.expander("Ver registros actualizados"):
                for item in st.session_state.actualizados:
                    st.write(f"• {item}")
        
        # Mostrar información sobre duplicados
        if st.session_state.duplicados_encontrados:
            st.error(f"🚫 Se encontraron {len(st.session_state.duplicados_encontrados)} registros DUPLICADOS (NO se insertarán)")
            with st.expander("Ver registros duplicados detectados"):
                for dup in st.session_state.duplicados_encontrados:
                    st.write(f"• Unidad: {dup.get('Apartamento/Casa', 'N/A')} - Propietario: {dup.get('Propietario', 'N/A')} - Saldo: ${dup.get('Saldo_Pendiente', 0):,.2f}")
        
        # Mostrar registros completamente nuevos
        if st.session_state.nuevos_para_reporte:
            st.success(f"✅ Se identificaron {len(st.session_state.nuevos_para_reporte)} registros COMPLETAMENTE NUEVOS para insertar")
            with st.expander("Vista previa de registros NUEVOS"):
                for nuevo in st.session_state.nuevos_para_reporte:
                    st.write(f"• Unidad: {nuevo.get('Apartamento/Casa', 'N/A')} - Propietario: {nuevo.get('Propietario', 'N/A')} - Saldo: ${nuevo.get('Saldo_Pendiente', 0):,.2f}")
        else:
            if not st.session_state.duplicados_encontrados:
                st.info("ℹ️ No se encontraron registros con más de 30 días de mora")
            else:
                st.info("ℹ️ Todos los registros candidatos ya existían en la base de datos")
        
        # Mostrar morosos a eliminar
        if st.session_state.morosos_eliminados:
            st.warning(f"⚠️ Se identificaron {len(st.session_state.morosos_eliminados)} registros de morosos que ya NO están en mora")
            #with st.expander("Ver registros de morosos a eliminar"):
            #    for moroso in st.session_state.morosos_eliminados:
            #        st.write(f"• Unidad: {moroso.get('Apartamento/Casa', 'N/A')} - Propietario: {moroso.get('Propietario', 'N/A')} - Estado actual: Pagado")

        # Botones de actualización
        st.markdown("### 💾 Actualizar Datos")
        #col1, col2, col3, col4 = st.columns(4)
        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        
        with col1:
            if st.button("💾 Actualizar Administración Financiera", key="update_admin"):
                if st.session_state.df_admin_updated is not None and st.session_state.processed_sheet_name:
                    with st.spinner("Actualizando administración financiera..."):
                        success = update_sheet_data(client, st.session_state.processed_sheet_name, "Administracion_Financiera", st.session_state.df_admin_updated)
                        if success:
                            st.success("✅ Administración Financiera actualizada correctamente")
                            st.balloons()
                        else:
                            st.error("❌ Error actualizando administración financiera")
                else:
                    st.error("No hay datos para actualizar")
        
        with col2:
            if st.session_state.morosos_df_nuevos is not None and not st.session_state.morosos_df_nuevos.empty:
                if st.button("📝 Insertar Registros NUEVOS de Morosos", key="insert_morosos"):
                    if st.session_state.processed_sheet_name:
                        with st.spinner("Insertando datos de morosos..."):
                            success = insert_new_records_only(client, st.session_state.processed_sheet_name, "gestion_morosos", st.session_state.morosos_df_nuevos)
                            #success = insert_data_to_sheet(client, st.session_state.processed_sheet_name, "gestion_morosos", st.session_state.morosos_df)
                            if success:
                                st.success(f"✅ Se insertaron {len(st.session_state.morosos_df_nuevos)} registros NUEVOS en Gestión Morosos")
                                if st.session_state.duplicados_encontrados:
                                    st.info(f"ℹ️ Se evitaron {len(st.session_state.duplicados_encontrados)} duplicados")
                                st.balloons()
                            else:
                                st.error("❌ Error insertando datos de morosos")
                    else:
                        st.error("No se puede determinar el nombre de la hoja")
            else:
                if st.session_state.duplicados_encontrados:
                    st.info("ℹ️ Solo se encontraron registros duplicados - No hay registros nuevos para insertar")
                else:
                    st.info("No hay registros de morosos para insertar")


        with col3:
            if st.session_state.morosos_eliminados:
                if st.button("🗑️ Eliminar Morosos Resueltos", key="remove_morosos"):
                    if st.session_state.processed_sheet_name and st.session_state.existing_morosos_df is not None:
                        with st.spinner("Eliminando registros de morosos resueltos..."):
                            # Crear DataFrame actualizado sin los morosos eliminados
                            morosos_df_actualizado = remove_resolved_morosos(
                                st.session_state.existing_morosos_df, 
                                st.session_state.morosos_eliminados
                            )
                            
                            # Actualizar la hoja con los datos filtrados
                            success = update_sheet_data(client, st.session_state.processed_sheet_name, "gestion_morosos", morosos_df_actualizado)
                            if success:
                                st.success(f"✅ Se eliminaron {len(st.session_state.morosos_eliminados)} registros de morosos resueltos")
                                # Actualizar el session_state
                                st.session_state.existing_morosos_df = morosos_df_actualizado
                                st.session_state.morosos_eliminados = []
                                st.balloons()
                            else:
                                st.error("❌ Error eliminando registros de morosos")
                    else:
                        st.error("No se puede proceder con la eliminación")
            else:
                st.info("No hay morosos resueltos para eliminar")
        
        with col4:
            if st.button("🔄 Limpiar y Reiniciar", key="reset"):
                # Limpiar session_state
                st.session_state.df_admin_updated = None
                st.session_state.morosos_df_nuevos = None
                st.session_state.actualizados = []
                st.session_state.duplicados_encontrados = []
                st.session_state.morosos_eliminados = []
                #st.session_state.nuevos_para_reporte = nuevos_para_reporte
                st.session_state.datos_procesados = False
                st.session_state.processed_sheet_name = None
                st.rerun()

    # Información adicional
    with st.expander("ℹ️ Información del Proceso"):
        st.markdown("""
        **Este script realiza las siguientes operaciones:**
        
        1. **Carga datos** de las hojas 'Administracion_Financiera' y 'Control_Residentes'
        2. **Filtra registros** de 'Cuota de Mantenimiento' con estados 'Pagado' y 'Pendiente'
        3. **Realiza cruces** por Unidad y periodo (mes/año) de la fecha
        4. **Calcula saldos** restando montos pagados de montos pendientes
        5. **Actualiza estados** a 'Pagado' cuando el saldo es ≤ 0
        6. **Genera registros** de morosos SOLO para saldos pendientes > 0 con MÁS de 30 días de mora
        7. **Verifica duplicados** usando claves únicas basadas en Unidad + Concepto + Fecha de Vencimiento
        8. **Actualiza** la hoja 'Administracion_Financiera' con los nuevos estados y saldos
        9. **Inserta** SOLO registros NUEVOS en 'gestion_morosos' (evita duplicados automáticamente)
        
        **Validaciones implementadas:**
        - ✅ **ANTI-DUPLICADOS**: Sistema de claves únicas para evitar registros duplicados
        - ✅ **Detección automática**: Identifica y reporta registros ya existentes
        - ✅ **Actualización inteligente**: Actualiza montos en registros existentes si es necesario
        - ✅ Solo morosos con más de 30 días de mora
        - ✅ Manejo seguro de tipos de datos y valores nulos
        - ✅ Conversión robusta de montos (elimina caracteres especiales)
        - ✅ Validación de fechas y cálculo correcto de días de mora
        - ✅ Creación automática de hojas si no existen
        
        **Sistema de Claves Únicas:**
        - Se genera un hash MD5 único basado en: `Unidad|Concepto|Fecha_Vencimiento`
        - Los registros existentes se actualizan automáticamente con claves únicas
        - Solo se insertan registros que NO existan previamente
     """)    

    #    **Campos requeridos en las hojas:**
    #    - **Administracion_Financiera:** Tipo_Operacion, Unidad, Fecha, Estado, Monto, Concepto, Saldo_Pendiente
    #    - **Control_Residentes:** Unidad, Nombre, Apellido, Identificacion, Telefono, Email
    #    - **gestion_morosos:** Se crea automáticamente con campo `Clave_Unica` para control de duplicados
       
  except ValueError as e:
        st.error(f"Error detectado: {str(e)}")
        st.error("Stack trace:")
        st.code(traceback.format_exc())
        logging.error(f"Error detectado: {str(e)}", exc_info=True)
        return

if __name__ == "__main__":
    control_main()