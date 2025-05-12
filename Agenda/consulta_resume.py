import streamlit as st
import pandas as pd
import json
import toml
import gspread
from google.oauth2.service_account import Credentials
import time
from googleapiclient.errors import HttpError

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

#st.set_page_config(page_title="Consulta de Hojas de Vida", layout="wide")
#st.title("Sistema de Consulta de CV")

def load_credentials_from_toml():
    #Load credentials from secrets.toml file
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    #Establish connection with Google Sheets
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def get_all_data(client):
    """Get all data saved in the sheet using expected_headers para evitar problemas con encabezados duplicados"""
    try:
        for intento in range(MAX_RETRIES):
            try:
                with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                    sheet = client.open('gestion-agenda')
                    worksheet = sheet.worksheet('resumen-cv')
                    
                    # Lista de encabezados esperados - ajustar según los encabezados reales de tu hoja
                    expected_headers = ['nombre', 'identificacion']  #, 'telefono', 'email', 'fecha'
                    
                    # Usar expected_headers para evitar problemas con encabezados duplicados
                    try:
                        records = worksheet.get_all_records(expected_headers=expected_headers)
                    except Exception as header_error:
                        st.warning(f"No se pudieron usar los encabezados esperados: {str(header_error)}")
                        
                        # Plan B: Obtener valores y crear diccionarios manualmente
                        all_values = worksheet.get_all_values()
                        headers = all_values[0] if all_values else []
                        
                        # Crear headers únicos
                        unique_headers = []
                        header_count = {}
                        
                        for header in headers:
                            if header in header_count:
                                header_count[header] += 1
                                unique_header = f"{header}_{header_count[header]}"
                            else:
                                header_count[header] = 0
                                unique_header = header
                            
                            unique_headers.append(unique_header)
                        
                        # Crear registros con headers únicos
                        records = []
                        for i in range(1, len(all_values)):
                            row = all_values[i]
                            record = {}
                            for j in range(min(len(unique_headers), len(row))):
                                record[unique_headers[j]] = row[j]
                            records.append(record)
                    
                    return records, worksheet

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
                return [], None
                
        return [], None  # Si se agotaron los intentos

    except Exception as e:
        st.error(f"Error retrieving data: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")
        return [], None

def manage_records_tab(client):
    """Pestaña para gestionar los registros en Google Sheets"""
    st.header("Gestionar Registros")
    
    if not client:
        st.error("No hay conexión con Google Sheets. Por favor, cargue un archivo primero.")
        return
    
    try:
        # Obtener todos los registros usando la función mejorada
        with st.spinner("Cargando registros..."):
            records, worksheet = get_all_data(client)
        
        if not records:
            st.info("No hay registros para mostrar.")
            return
        
        # Convertir a DataFrame para mejor visualización
        df = pd.DataFrame(records)
        
        # Verificar y renombrar columnas para mantener consistencia
        # Posibles variaciones de nombres para columnas importantes
        nombre_variants = ["nombre", "nombres", "Nombre", "Nombres", "NOMBRE", "NOMBRES"]
        id_variants = ["identificacion", "identificación", "cedula", "cédula", "Identificacion", 
                      "Identificación", "Cedula", "Cédula", "ID", "id", "IDENTIFICACION", "CEDULA"]
        
        # Normalizar nombres de columnas (primera que coincida)
        for variants, standard_name in [(nombre_variants, "nombre"), (id_variants, "identificacion")]:
            found = False
            for variant in variants:
                if variant in df.columns:
                    df = df.rename(columns={variant: standard_name})
                    found = True
                    break
        
        # Asegurar que la columna 'identificacion' sea de tipo string
        # y limpiar espacios y puntos si existen
        if 'identificacion' in df.columns:
            df['identificacion'] = df['identificacion'].astype(str).str.strip().str.replace('.', '')
        
        # Filtrar columnas para mostrar solo información relevante en la vista previa
        preview_columns = ["nombre", "identificacion"]
        preview_df = df[preview_columns] if all(col in df.columns for col in preview_columns) else df.iloc[:, :2]
        
        # Mostrar todas las columnas disponibles en una casilla desplegable
        st.subheader("Seleccionar columnas para mostrar")
        selected_columns = st.multiselect("Seleccione las columnas que desea ver:", 
                                         options=df.columns.tolist(),
                                         default=preview_columns if all(col in df.columns for col in preview_columns) 
                                                else df.columns.tolist()[:2])
        
        if selected_columns:
            preview_df = df[selected_columns]
        
        # Agregar un índice comenzando en 1 para referencia de filas
        preview_df = preview_df.reset_index()
        preview_df = preview_df.rename(columns={"index": "Nº"})
        preview_df["Nº"] = preview_df["Nº"] + 2  # +2 porque la fila 1 suele ser encabezados
        
        st.subheader("Registros Existentes")
        st.dataframe(preview_df)
    except Exception as e:
        st.error(f"Error al gestionar registros: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")

def query_records_tab(client):
    """Pestaña para consultar y filtrar registros en Google Sheets"""
    st.header("Consulta de Registros")
    
    if not client:
        st.error("No hay conexión con Google Sheets. Por favor, verifique las credenciales.")
        return
    
    try:
        # Obtener todos los registros
        with st.spinner("Cargando registros para consulta..."):
            records, worksheet = get_all_data(client)
        
        if not records:
            st.info("No hay registros para consultar.")
            return
        
        # Convertir a DataFrame
        df = pd.DataFrame(records)
        
        # Normalizar nombres de columnas importantes
        nombre_variants = ["nombre", "nombres", "Nombre", "Nombres", "NOMBRE", "NOMBRES"]
        id_variants = ["identificacion", "identificación", "cedula", "cédula", "Identificacion", 
                      "Identificación", "Cedula", "Cédula", "ID", "id", "IDENTIFICACION", "CEDULA"]
        
        for variants, standard_name in [(nombre_variants, "nombre"), (id_variants, "identificacion")]:
            for variant in variants:
                if variant in df.columns:
                    df = df.rename(columns={variant: standard_name})
                    break
        
        # Normalizar datos
        if 'identificacion' in df.columns:
            df['identificacion'] = df['identificacion'].astype(str).str.strip().str.replace('.', '')
        
        # Crear búsqueda en pestañas
        tab1, tab2, tab3 = st.tabs(["Búsqueda por nombre", "Búsqueda por ID", "Búsqueda avanzada"])
        
        with tab1:
            st.subheader("Buscar por nombre")
            name_search = st.text_input("Ingrese el nombre o parte del nombre:", key="name_search")
            
            if name_search:
                # Filtrar por nombre (case insensitive)
                if 'nombre' in df.columns:
                    filtered_df = df[df['nombre'].str.lower().str.contains(name_search.lower())]
                    
                    if not filtered_df.empty:
                        st.success(f"Se encontraron {len(filtered_df)} registros que coinciden con '{name_search}'")
                        
                        # Mostrar resultados
                        st.dataframe(filtered_df)
                        
                        # Opción para ver detalles
                        if len(filtered_df) > 0:
                            selected_index = st.selectbox(
                                "Seleccione un registro para ver detalles:",
                                options=range(len(filtered_df)),
                                format_func=lambda i: f"{filtered_df.iloc[i].get('nombre', 'Sin nombre')} - {filtered_df.iloc[i].get('identificacion', 'Sin ID')}"
                            )
                            
                            if st.button("Ver detalles", key="ver_detalles_nombre"):
                                st.subheader("Detalles del registro")
                                record_details = filtered_df.iloc[selected_index].to_dict()
                                
                                # Mostrar en formato vertical para mejor visualización
                                for key, value in record_details.items():
                                    st.text(f"{key}: {value}")
                    else:
                        st.warning(f"No se encontraron registros con nombre que contenga '{name_search}'")
                else:
                    st.error("No se encontró una columna de nombre en los datos.")
        
        with tab2:
            st.subheader("Buscar por identificación")
            id_search = st.text_input("Ingrese el número de identificación:", key="id_search")
            
            if id_search:
                # Filtrar por ID
                if 'identificacion' in df.columns:
                    # Limpiar el input también
                    id_search_clean = id_search.strip().replace('.', '')
                    filtered_df = df[df['identificacion'].str.contains(id_search_clean)]
                    
                    if not filtered_df.empty:
                        st.success(f"Se encontraron {len(filtered_df)} registros con ID que contiene '{id_search}'")
                        
                        # Mostrar resultados
                        st.dataframe(filtered_df)
                        
                        # Opción para ver detalles
                        if len(filtered_df) > 0:
                            selected_index = st.selectbox(
                                "Seleccione un registro para ver detalles:",
                                options=range(len(filtered_df)),
                                format_func=lambda i: f"{filtered_df.iloc[i].get('nombre', 'Sin nombre')} - {filtered_df.iloc[i].get('identificacion', 'Sin ID')}",
                                key="select_id_detail"
                            )
                            
                            if st.button("Ver detalles", key="ver_detalles_id"):
                                st.subheader("Detalles del registro")
                                record_details = filtered_df.iloc[selected_index].to_dict()
                                
                                # Mostrar en formato vertical para mejor visualización
                                for key, value in record_details.items():
                                    st.text(f"{key}: {value}")
                    else:
                        st.warning(f"No se encontraron registros con identificación que contenga '{id_search}'")
                else:
                    st.error("No se encontró una columna de identificación en los datos.")
        
        with tab3:
            st.subheader("Búsqueda avanzada")
            
            # Permitir al usuario seleccionar columnas para buscar
            search_columns = st.multiselect(
                "Seleccione columnas para buscar:",
                options=df.columns.tolist(),
                default=["nombre", "identificacion"] if all(col in df.columns for col in ["nombre", "identificacion"]) else df.columns.tolist()[:2]
            )
            
            # Campo de búsqueda general
            general_search = st.text_input("Término de búsqueda:", key="general_search")
            
            if general_search and search_columns:
                st.write("Resultados de búsqueda:")
                
                # Crear una máscara de filtro combinando todas las columnas seleccionadas
                mask = pd.Series(False, index=df.index)
                
                for col in search_columns:
                    if df[col].dtype == 'object':  # Solo buscar en columnas de texto
                        column_mask = df[col].astype(str).str.lower().str.contains(general_search.lower())
                        mask = mask | column_mask.fillna(False)
                
                filtered_df = df[mask]
                
                if not filtered_df.empty:
                    st.success(f"Se encontraron {len(filtered_df)} registros")
                    
                    # Mostrar resultados
                    st.dataframe(filtered_df)
                    
                    # Exportar resultados
                    if st.button("Exportar resultados a CSV"):
                        csv = filtered_df.to_csv(index=False)
                        st.download_button(
                            label="Descargar CSV",
                            data=csv,
                            file_name="resultados_busqueda.csv",
                            mime="text/csv"
                        )
                else:
                    st.warning(f"No se encontraron registros que coincidan con '{general_search}'")
            
            # Filtros adicionales
            st.subheader("Filtros adicionales")
            
            if len(df) > 0:
                # Mostrar estadísticas básicas
                st.subheader("Estadísticas")
                st.write(f"Total de registros: {len(df)}")
                
                # Si hay columnas numéricas, mostrar algunas estadísticas
                numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
                if numeric_cols:
                    st.write("Seleccione una columna numérica para ver estadísticas:")
                    selected_numeric = st.selectbox("Columna:", options=numeric_cols)
                    
                    st.write(f"Estadísticas para {selected_numeric}:")
                    st.write(f"Promedio: {df[selected_numeric].mean():.2f}")
                    st.write(f"Mínimo: {df[selected_numeric].min()}")
                    st.write(f"Máximo: {df[selected_numeric].max()}")
                    
                    # Histograma simple
                    st.subheader(f"Distribución de {selected_numeric}")
                    hist_values = df[selected_numeric].dropna()
                    st.bar_chart(hist_values.value_counts())
    
    except Exception as e:
        st.error(f"Error al consultar registros: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")

def consulta_cv():
    st.sidebar.title("Navegación")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    
    if not creds:
        st.error("No se pudieron cargar las credenciales. Verifique el archivo secrets.toml")
        return
    
    # Establecer conexión con Google Sheets
    client = get_google_sheets_connection(creds)
    
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets.")
        return
    
    # Opciones de navegación
    app_mode = st.sidebar.radio(
        "Seleccione una opción:",
        options=["Consulta de Registros", "Gestión de Registros"]
    )
    
    # Mostrar la pestaña seleccionada
    if app_mode == "Consulta de Registros":
        query_records_tab(client)
    elif app_mode == "Gestión de Registros":
        manage_records_tab(client)
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info("Sistema de Consulta de CV v1.0")
    
    # Estado de la conexión
    if client:
        st.sidebar.success("✅ Conectado a Google Sheets")
    else:
        st.sidebar.error("❌ Sin conexión a Google Sheets")

#if __name__ == "__main__":
#    consulta_cv()