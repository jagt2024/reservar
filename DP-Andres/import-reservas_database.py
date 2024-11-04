import streamlit as st
import pandas as pd
import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime
import uuid

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

def get_google_sheet_data(creds):
    try:
        if not creds:
            st.error("No se pudieron cargar las credenciales")
            return None

        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        gc = gspread.authorize(credentials)
        
        # Abre el archivo específico
        sheet = gc.open('gestion-reservas-dp').sheet1
        
        # Obtiene todos los datos
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Error al obtener datos de Google Sheets: {str(e)}")
        return None

def create_database():
    try:
        conn = sqlite3.connect('reservas_dp.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                email TEXT,
                fecha DATE NOT NULL,
                hora TEXT NOT NULL,
                servicio TEXT NOT NULL,
                precio TEXT,
                encargado TEXT NOT NULL,
                email_encargado TEXT,
                zona TEXT,
                direccion TEXT,
                notas TEXT,
                uid TEXT UNIQUE,
                whatsapp BOOLEAN,
                telefono TEXT,
                whatsapp_web TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Error al crear la base de datos: {str(e)}")
        return None

def process_data(df):
    # Mapeo de nombres de columnas del Excel a la base de datos
    column_mapping = {
        'NOMBRE': 'nombre',
        'EMAIL': 'email',
        'FECHA': 'fecha',
        'HORA': 'hora',
        'SERVICIOS': 'servicio',
        'PRECIO': 'precio',
        'ENCARGADO': 'encargado',
        'CORREO ENCARGADO': 'email_encargado',
        'ZONA': 'zona',
        'DIRECCION': 'direccion',
        'NOTAS': 'notas',
        'UID': 'uid',
        'WHATSAPP': 'whatsapp',
        'TELEFONO': 'telefono',
        'URL WEB': 'whatsapp_web'
    }
    
    # Verificar columnas requeridas
    required_columns = ['NOMBRE', 'FECHA', 'HORA', 'SERVICIOS', 'ENCARGADO']
    for col in required_columns:
        if col not in df.columns:
            st.error(f"Columna requerida '{col}' no encontrada en el archivo")
            return None
    
    # Convertir fecha al formato correcto
    df['FECHA'] = pd.to_datetime(df['FECHA']).dt.date
    
    # Renombrar columnas según el mapeo
    df_mapped = df.rename(columns=column_mapping)
    
    # Generar UID para registros que no lo tengan
    if 'uid' not in df_mapped.columns:
        df_mapped['uid'] = [str(uuid.uuid4()) for _ in range(len(df_mapped))]
    
    return df_mapped

def import_to_database(conn, df):
    cursor = conn.cursor()
    records_processed = 0
    records_skipped = 0
    
    # Definir las columnas de la base de datos que vamos a usar
    db_columns = [
        'nombre', 'email', 'fecha', 'hora', 'servicio', 'precio',
        'encargado', 'email_encargado', 'zona', 'direccion', 'notas',
        'uid', 'whatsapp', 'telefono', 'whatsapp_web'
    ]
    
    for _, row in df.iterrows():
        try:
            # Verificar si el registro ya existe
            cursor.execute('''
                SELECT COUNT(*) FROM reservas 
                WHERE nombre = ? AND fecha = ? AND hora = ?
            ''', (row['nombre'], row['fecha'], row['hora']))
            
            if cursor.fetchone()[0] == 0:
                # Preparar los valores solo para las columnas que existen en la base de datos
                values = [row[col] if col in row else None for col in db_columns]
                placeholders = ','.join(['?' for _ in db_columns])
                
                # Construir la consulta de inserción con los nombres de columnas correctos
                query = f'''
                    INSERT INTO reservas ({','.join(db_columns)})
                    VALUES ({placeholders})
                '''
                
                cursor.execute(query, values)
                records_processed += 1
            else:
                records_skipped += 1
                
        except Exception as e:
            st.warning(f"Error al procesar registro: {str(e)}\nRegistro: {row.to_dict()}")
            continue
    
    conn.commit()
    return records_processed, records_skipped

def data():
    st.title("Importador de Reservas")
    
    # Cargar credenciales
    creds = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales")
        return
    
    # Crear o conectar a la base de datos
    conn = create_database()
    if not conn:
        return
    
    if st.button("Iniciar Importación"):
        with st.spinner("Descargando datos de Google Sheets..."):
            df = get_google_sheet_data(creds)
            
        if df is not None:
            st.success(f"Datos descargados exitosamente. {len(df)} registros encontrados.")
            
            # Procesar datos
            with st.spinner("Procesando datos..."):
                df = process_data(df)
                
            if df is not None:
                # Importar a la base de datos
                with st.spinner("Importando datos a la base de datos..."):
                    records_processed, records_skipped = import_to_database(conn, df)
                    
                st.success(f"""
                    Importación completada:
                    - Registros procesados: {records_processed}
                    - Registros omitidos (duplicados): {records_skipped}
                """)
        
        conn.close()

if __name__ == "__main__":
    data()