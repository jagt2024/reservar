import streamlit as st
import pandas as pd
import numpy as np
import toml
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import tempfile
import os

# Configurar página
#st.set_page_config(page_title="Carga de Clientes", layout="wide")
#st.title("Carga de Datos de Clientes")

# Definir columnas requeridas en orden específico
REQUIRED_COLUMNS = ['NOMBRE', 'EMAIL', 'DIRECCION', 'TELEFONO', 'ZONA', 'PRODUCTO']

def load_credentials_from_toml():
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales: {str(e)}")
        return None

def get_existing_data(client):
    """Obtiene los datos existentes de la hoja de cálculo"""
    sheet = client.open('gestion-reservas-cld')
    worksheet = sheet.worksheet('clientes')
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def check_duplicates(existing_df, new_df):
    """Verifica duplicados basados en coincidencia exacta de NOMBRE, EMAIL y DIRECCION"""
    existing_df_lower = existing_df.copy()
    new_df_lower = new_df.copy()
    
    for col in ['NOMBRE', 'EMAIL', 'DIRECCION']:
        if col in existing_df_lower.columns:
            existing_df_lower[col] = existing_df_lower[col].str.lower().str.strip()
        if col in new_df_lower.columns:
            new_df_lower[col] = new_df_lower[col].str.lower().str.strip()
    
    duplicates = []
    unique_records = []
    
    for idx, row in new_df.iterrows():
        matches = existing_df_lower[
            (existing_df_lower['NOMBRE'] == str(row['NOMBRE']).lower().strip()) &
            (existing_df_lower['EMAIL'] == str(row['EMAIL']).lower().strip()) &
            (existing_df_lower['DIRECCION'] == str(row['DIRECCION']).lower().strip())
        ]
        
        if not matches.empty:
            duplicates.append({
                'row': idx + 2,
                'NOMBRE': row['NOMBRE'],
                'EMAIL': row['EMAIL'],
                'DIRECCION': row['DIRECCION']
            })
        else:
            unique_records.append(row)
    
    return pd.DataFrame(unique_records), duplicates

def validate_data(df):
    """Valida que estén todas las columnas requeridas"""
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    
    if missing_columns:
        return False, f"Faltan las siguientes columnas: {', '.join(missing_columns)}"
    return True, ""

def clean_data_for_json(df):
    """Limpia los datos para asegurar compatibilidad con JSON"""
    df_clean = df.copy()
    
    for column in df_clean.columns:
        # Convertir valores NaN a None
        df_clean[column] = df_clean[column].replace({np.nan: None, np.inf: None, -np.inf: None})
        
        # Convertir números a string si son muy grandes
        df_clean[column] = df_clean[column].apply(lambda x: 
            str(x) if isinstance(x, (np.int64, np.float64)) and (abs(x) > 1e9 or pd.isna(x)) 
            else x)
        
        # Convertir tipos numpy a tipos Python básicos
        df_clean[column] = df_clean[column].apply(lambda x: 
            x.item() if isinstance(x, (np.int64, np.float64)) 
            else x)
    
    return df_clean

def prepare_data_for_upload(df):
    """Prepara los datos para la carga, organizando las columnas y añadiendo la fecha"""
    # Seleccionar solo las columnas requeridas en el orden especificado
    df_prepared = df[REQUIRED_COLUMNS].copy()
    
    # Añadir la fecha actual
    df_prepared['FECHA'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return df_prepared

def read_file(uploaded_file, file_type):
    """Lee el archivo según su tipo"""
    try:
        if file_type == 'csv':
            st.subheader("Configuración de archivo CSV")
            encoding = st.selectbox("Selecciona la codificación del archivo:", 
                                  ['utf-8', 'latin-1', 'iso-8859-1'], 
                                  index=0)
            separator = st.selectbox("Selecciona el separador:", 
                                   [',', ';', '|', '\t'], 
                                   index=0)
            
            df = pd.read_csv(uploaded_file, encoding=encoding, sep=separator)
        else:  # xlsx
            df = pd.read_excel(uploaded_file)
        
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo: {str(e)}")
        return None

def upload_to_sheets(creds, df):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        
        # Preparar datos con el orden correcto y fecha
        df = prepare_data_for_upload(df)
        
        # Obtener datos existentes y verificar duplicados
        existing_df = get_existing_data(client)
        unique_df, duplicates = check_duplicates(existing_df, df)
        
        if len(duplicates) > 0:
            st.warning("Se encontraron los siguientes registros duplicados:")
            for dup in duplicates:
                st.write(f"""Fila {dup['row']}:
                         \n- NOMBRE: {dup['NOMBRE']}
                         \n- EMAIL: {dup['EMAIL']}
                         \n- DIRECCION: {dup['DIRECCION']}""")
            
            if unique_df.empty:
                return False, "No hay registros únicos para cargar."
            
            st.info(f"Se cargarán solo los {len(unique_df)} registros únicos.")
        
        if not unique_df.empty:
            # Limpiar datos para compatibilidad con JSON
            unique_df = clean_data_for_json(unique_df)
            
            # Abrir la hoja y cargar los registros únicos
            sheet = client.open('gestion-reservas-cld')
            worksheet = sheet.worksheet('clientes')
            
            # Convertir DataFrame a lista de listas
            data = unique_df.values.tolist()
            
            # Obtener el último ID
            last_row = len(worksheet.get_all_values())
            
            # Añadir ID a cada fila
            rows_to_add = []
            for i, row in enumerate(data):
                new_id = last_row + i
                rows_to_add.append([new_id] + row)
            
            # Añadir todas las filas de una vez
            worksheet.append_rows(rows_to_add)
            
            return True, f"Se agregaron {len(unique_df)} registros exitosamente."
        else:
            return False, "No hay registros nuevos para cargar."
            
    except Exception as e:
        return False, f"Error al subir datos: {str(e)}"

def carga():
    creds = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales. Verifica el archivo secrets.toml")
        return
    
    # Mostrar las columnas requeridas y su orden
    st.info(f"El archivo debe contener las siguientes columnas en este orden:\n{', '.join(REQUIRED_COLUMNS + ['FECHA'])}")
    
    uploaded_file = st.file_uploader("Selecciona el archivo", type=['xlsx', 'csv'])
    
    if uploaded_file:
        try:
            file_type = uploaded_file.name.split('.')[-1].lower()
            df = read_file(uploaded_file, file_type)
            
            if df is not None:
                # Mostrar preview de datos
                st.subheader("Vista previa de datos")
                st.dataframe(df[REQUIRED_COLUMNS].head() if all(col in df.columns for col in REQUIRED_COLUMNS) else df.head())
                
                # Validar estructura
                is_valid, message = validate_data(df)
                
                if is_valid:
                    if st.button("Cargar datos"):
                        success, message = upload_to_sheets(creds, df)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                else:
                    st.error(message)
                
        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")

#if __name__ == "__main__":
##    carga()