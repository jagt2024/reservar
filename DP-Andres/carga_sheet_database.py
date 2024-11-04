import streamlit as st
import pandas as pd
import sqlite3
import toml
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import os
import json

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
        
        st.info("Conectado a Google Sheets exitosamente")
        
        try:
            spreadsheet = gc.open('gestion-reservas-dp')
            st.info("Documento encontrado")
            
            worksheet = spreadsheet.worksheet('reservas')
            st.info("Hoja de cálculo 'reservas' encontrada")
            
            data = worksheet.get_all_records()
            
            if not data:
                st.warning("No se encontraron datos en la hoja de cálculo")
                return None
                
            df = pd.DataFrame(data)
            
            if df.empty:
                st.warning("El DataFrame está vacío")
                return None
                
            return df
            
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("No se encontró el documento 'gestion-reservas-dp'")
            return None
        except gspread.exceptions.WorksheetNotFound:
            st.error("No se encontró la hoja 'reservas'")
            return None
            
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {str(e)}")
        return None

def create_database():
    try:
        conn = sqlite3.connect('reservas_dp.db')
        c = conn.cursor()
        
        c.execute('''
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
        
        # Crear índice único para evitar duplicados
        c.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reserva_unique 
            ON reservas(nombre, fecha, hora)
        ''')
        
        conn.commit()
        st.success("Base de datos creada/conectada exitosamente")
        return True
        
    except sqlite3.Error as e:
        st.error(f"Error al crear la base de datos: {str(e)}")
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

def get_existing_records():
    try:
        conn = sqlite3.connect('reservas_dp.db')
        query = "SELECT nombre, fecha, hora FROM reservas"
        existing_records = pd.read_sql_query(query, conn)
        return existing_records
    except sqlite3.Error as e:
        st.error(f"Error al obtener registros existentes: {str(e)}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals():
            conn.close()

def generate_unique_uid(conn, base_uid):
    """
    Genera un UID único añadiendo un sufijo numérico si es necesario
    """
    cursor = conn.cursor()
    counter = 0
    new_uid = base_uid
    while True:
        # Verificar si el UID existe
        cursor.execute("SELECT 1 FROM reservas WHERE uid = ?", (new_uid,))
        if not cursor.fetchone():
            return new_uid
        counter += 1
        new_uid = f"{base_uid}_{counter}"

def save_to_database(df):
    try:
        # Validación inicial del DataFrame
        if df.empty:
            st.error("No hay datos para guardar")
            return

        st.write("Columnas disponibles:", df.columns.tolist())

        # Verificar y limpiar valores nulos en la columna 'nombre'
        if 'nombre' not in df.columns or 'NOMBRE'  not in df.columns:
            st.error("La columna 'nombre' no existe en los datos")
            return

        df['nombre'] = df['nombre'].astype(str).str.strip()
        df.loc[df['nombre'].isin(['nan', '', 'None', 'NaN']), 'nombre'] = None
        
        # Eliminar registros sin nombre
        null_names = df['nombre'].isnull().sum()
        if null_names > 0:
            st.warning(f"Se encontraron {null_names} registros con nombres nulos")
            df = df.dropna(subset=['nombre'])

        if df.empty:
            st.error("No quedan registros válidos después de la limpieza")
            return

        # Conectar a la base de datos
        conn = sqlite3.connect('reservas_dp.db')
        
        try:
            # Lista de columnas requeridas con sus valores por defecto
            required_columns = {
                'nombre': '',
                'email': '',
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'hora': datetime.now().strftime('%H:%M'),
                'servicios': 'No especificado',
                'precio': '0',
                'encargado': 'No asignado',
                'correo_encargado': '',
                'zona': '',
                'direccion': '',
                'notas': '',
                'uid': '',
                'whatsapp': False,
                'telefono': '',
                'url_web': '',
                'boton': ''
            }

            # Renombrar columnas si existen con nombres diferentes
            column_mapping = {
                'email encargado': 'correo_encargado',
                'correo encargado': 'correo_encargado',
                'whatsapp_web': 'url_web'
            }
            df = df.rename(columns=column_mapping)

            # Asegurar que todas las columnas requeridas existan
            for col, default_value in required_columns.items():
                if col not in df.columns:
                    df[col] = default_value

            # Generar o validar UIDs únicos
            for idx, row in df.iterrows():
                base_uid = row.get('uid', '')
                if not base_uid:
                    # Si no hay UID, crear uno basado en el nombre y la fecha
                    base_uid = f"{row['nombre']}_{row['fecha']}_{row['hora']}".replace(' ', '_')
                df.at[idx, 'uid'] = generate_unique_uid(conn, base_uid)

            # Agregar timestamp de creación
            df['fecha_creacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Preparar datos para guardar
            columns_to_save = list(required_columns.keys()) + ['fecha_creacion']
            df_to_save = df[columns_to_save].copy()

            # Verificar duplicados basados en nombre, fecha y hora
            existing_records = pd.read_sql_query(
                "SELECT nombre, fecha, hora FROM reservas", 
                conn
            )

            if not existing_records.empty:
                duplicates = pd.merge(
                    df_to_save,
                    existing_records,
                    on=['nombre', 'fecha', 'hora'],
                    how='inner'
                )
                
                if not duplicates.empty:
                    st.warning(f"Se encontraron {len(duplicates)} registros duplicados que serán ignorados")
                    st.write("Registros duplicados:")
                    st.write(duplicates[['nombre', 'fecha', 'hora']])
                    
                    # Filtrar duplicados
                    df_to_save = pd.merge(
                        df_to_save,
                        existing_records,
                        on=['nombre', 'fecha', 'hora'],
                        how='left',
                        indicator=True
                    )
                    df_to_save = df_to_save[df_to_save['_merge'] == 'left_only']
                    df_to_save = df_to_save.drop('_merge', axis=1)

            if df_to_save.empty:
                st.warning("No hay nuevos registros para guardar después de filtrar duplicados")
                return

            # Mostrar resumen antes de guardar
            st.write("Resumen de datos a guardar:")
            st.write(df_to_save[['nombre', 'fecha', 'hora', 'uid']].head())
            st.info(f"Total de registros a guardar: {len(df_to_save)}")

            # Guardar en la base de datos
            df_to_save.to_sql('reservas', conn, if_exists='append', index=False)
            st.success(f"Se guardaron {len(df_to_save)} nuevos registros en la base de datos")

        finally:
            conn.close()

    except Exception as e:
        st.error(f"Error al guardar en la base de datos: {str(e)}")
        st.exception(e)

def data():
    st.title('Sistema de Gestión de Reservas')
    
    if not create_database():
        st.error("No se pudo crear/conectar a la base de datos")
        return
    
    # Mostrar estadísticas actuales
    existing_records = get_existing_records()
    if not existing_records.empty:
        st.info(f"Registros actuales en la base de datos: {len(existing_records)}")
    
    # Botón para cargar datos
    if st.button('Cargar datos de Google Sheets'):
        with st.spinner('Cargando datos...'):
            try:
                credentials = load_credentials_from_toml()
                if not credentials:
                    st.error("No se pudieron cargar las credenciales")
                    return
                
                df = get_google_sheet_data(credentials)
                
                if df is not None and not df.empty:
                    st.success('Datos cargados exitosamente de Google Sheets')
                    st.write("Vista previa de los datos nuevos:")
                    st.dataframe(df.head())
                    
                    # Mostrar las columnas actuales del DataFrame
                    st.write("Columnas disponibles en los datos:")
                    st.write(df.columns.tolist())
                    
                    # Guardar solo registros nuevos
                    save_to_database(df)
                    
                    # Actualizar y mostrar estadísticas
                    updated_records = get_existing_records()
                    if not updated_records.empty:
                        st.subheader('Estadísticas Actualizadas')
                        st.write(f"Total de registros en la base de datos: {len(updated_records)}")
                        
                        # Mostrar estadísticas de servicios
                        conn = sqlite3.connect('reservas_dp.db')
                        df_stats = pd.read_sql_query("SELECT servicios, COUNT(*) as cantidad FROM reservas GROUP BY servicios", conn)
                        conn.close()
                        
                        st.subheader('Servicios más solicitados')
                        st.bar_chart(df_stats.set_index('servicios'))
                    
                else:
                    st.error("No se pudieron cargar los datos de Google Sheets")
                    
            except Exception as e:
                st.error(f"Error en el proceso: {str(e)}")
                st.error("Por favor, verifica las credenciales y la conexión")

if __name__ == '__main__':
    data()