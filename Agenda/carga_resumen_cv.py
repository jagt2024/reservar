import gspread
import streamlit as st
import toml
import json
import time
import PyPDF2
import re
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
import pandas as pd
from dateutil import parser
import re
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

#st.set_page_config(page_title="Extractor de Hojas de Vida", layout="wide")
#st.title("Extractor de Información de CV")

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
    import streamlit as st
    import time
    from googleapiclient.errors import HttpError
    
    # Constantes para reintentos
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2
    
    try:
        for intento in range(MAX_RETRIES):
            try:
                with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                    sheet = client.open('gestion-agenda')
                    worksheet = sheet.worksheet('resumen-cv')
                    
                    # Lista de encabezados esperados - ajustar según los encabezados reales de tu hoja
                    # Esta es la clave para resolver el problema "expected_headers"
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
    import streamlit as st
    import pandas as pd
    import time
    
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
        
        # Eliminar registros
        st.subheader("Eliminar Registro")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            row_to_delete = st.number_input("Ingrese el número de fila a eliminar:", min_value=2, value=2, step=1)
        
        with col2:
            confirm = st.checkbox("Confirmar eliminación")
        
        if st.button("Eliminar Registro"):
            if confirm:
                success, message = delete_record(client, int(row_to_delete))
                if success:
                    st.success(message)
                    # Esperar un momento antes de recargar para que el usuario vea el mensaje
                    time.sleep(1)
                    st.rerun()  # Recargar la página para actualizar la tabla
                else:
                    st.error(message)
            else:
                st.warning("Debe confirmar la eliminación marcando la casilla antes de eliminar.")
    
    except Exception as e:
        st.error(f"Error al cargar o gestionar registros: {str(e)}")
        import traceback
        st.error(traceback.format_exc())  # Mostrar traza completa del error para depuración

def delete_record(client, row_num):
    """Eliminar un registro específico del Google Sheet"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Eliminando registro... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('resumen-cv')
                # Eliminar la fila específica
                worksheet.delete_rows(row_num)
                # Verificar que se haya eliminado correctamente
                total_rows_after = len(worksheet.get_all_values())
                if total_rows_after >= row_num:  # Si aún existe una fila con ese número o superior
                    return True, f"Registro #{row_num} eliminado con éxito."
                else:
                    return True, f"Registro eliminado. La hoja ahora tiene {total_rows_after} registros."

        except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                    time.sleep(delay)
                    continue
                else:
                    return False, "Se excedió el límite de intentos. Por favor, intenta más tarde."
            else:
                return False, f"Error de la API: {str(error)}"

        except Exception as e:
            return False, f"Error al eliminar el registro: {str(e)}"
    
    return False, "Error al eliminar el registro después de varios intentos."

def clear_form_state():
    """Limpiar el estado del formulario"""
    if 'cv_data' in st.session_state:
        st.session_state.cv_data = None
    if 'pdf_text' in st.session_state:
        st.session_state.pdf_text = None
    if 'pages_text' in st.session_state:
        st.session_state.pages_text = None

def extract_text_from_pdf(pdf_file):
    """Extraer texto de un archivo PDF con separación por páginas y mejor manejo de errores"""
    try:
        # Volver al inicio del archivo para asegurarnos de que se lee correctamente
        pdf_file.seek(0)
        
        # Intentar leer el PDF
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
        except Exception as e:
            st.error(f"Error al leer el PDF: {str(e)}")
            return None, {"pagina1": f"Error al leer el PDF: {str(e)}"}
        
        # Verificar si el PDF está encriptado
        if pdf_reader.is_encrypted:
            st.warning("El PDF está encriptado. Intentando desencriptar...")
            try:
                # Intentar desencriptar con contraseña vacía (funcionará si es encriptación básica)
                pdf_reader.decrypt('')
            except:
                return None, {"pagina1": "El PDF está encriptado y no se puede desencriptar automáticamente."}
        
        # Inicializar variables
        pages_text = {}
        full_text = ""
        
        # Procesar cada página del PDF
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                # Extraer texto de la página actual
                page_text = page.extract_text()
                
                # Verificar si se obtuvo texto
                if page_text and page_text.strip():
                    # Guardar el texto de cada página por separado
                    pages_text[f"pagina{page_num + 1}"] = page_text
                    
                    # Agregar al texto completo con separador de página
                    full_text += f"\n--- PÁGINA {page_num + 1} ---\n{page_text}\n"
                else:
                    # Página sin texto
                    pages_text[f"pagina{page_num + 1}"] = f"[Página {page_num + 1} sin texto extraíble]"
            except Exception as e:
                st.warning(f"Error al extraer texto de la página {page_num + 1}: {str(e)}")
                pages_text[f"pagina{page_num + 1}"] = f"[Error al procesar página {page_num + 1}]"
        
        # Verificar si se extrajo algún texto
        if not full_text.strip():
            # Mostrar advertencia pero seguir adelante con páginas vacías marcadas adecuadamente
            st.warning("El PDF no contiene texto extraíble. Podría ser un documento escaneado que requiere OCR.")
            pages_text["pagina1"] = "El PDF no contiene texto extraíble. Podría ser un documento escaneado que requiere OCR."
            return "", pages_text
            
        return full_text, pages_text
    
    except Exception as e:
        st.error(f"Error al extraer texto del PDF: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")
        return None, {"pagina1": f"Error al procesar el PDF: {str(e)}"}

def extract_name_from_first_line(text):
    """Extraer el nombre de la primera línea de la página 1"""
    if not text:
        return ""
    
    # Obtener la primera línea del texto
    lines = text.strip().split('\n')
    if lines:
        return lines[0].strip()
    return ""

def extract_identification(text):
    """Extraer número de identificación/cédula del texto con patrones más específicos
    Incluye búsqueda en la línea siguiente al nombre encontrado
    Maneja números con formato de puntos como separadores (ej. 80.493.576)"""
    import re
    
    if not text:
        return ""
    
    # Patrones más específicos para identificar cédulas en Colombia
    # y evitar confusiones con números telefónicos
    # Ahora incluye soporte para números con puntos como separadores
    patterns = [
        # Buscar patrones explícitos de cédula/identificación seguidos de número
        r'(?:C\.?C\.?|Cédula|Cedula|Documento de identidad)[^\d]*(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})',
        r'(?:Identificación|Identificacion)[^\d]*(?:No\.?|número|numero|Nº)[^\d]*(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})',
        r'(?:DNI|NIT|ID)[^\d]*(?:No\.?|número|numero|Nº)[^\d]*(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})',
        # Patrón con contexto explícito
        r'(?:Número|Numero|No\.|Nº) de (?:identificación|identificacion|cédula|cedula|documento)[^\d]*(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})',
        # Buscar texto donde explícitamente mencione cédula/identificación en proximidad del número
        r'(?:Cédula|Cedula|Identificación|Identificacion|Nº)(?:[^\d]{0,30})(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})',
        # Buscar en contexto de datos personales
        r'(?:Datos personales|Información personal)(?:.{0,100})(?:C\.?C\.?|Cédula|Cedula|ID)[^\d]*(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})'
    ]
    
    # Primero intentamos con los patrones específicos en todo el texto
    for pattern in patterns:
        matches = re.search(pattern, text, re.IGNORECASE)
        if matches:
            # Verificar que no sea un teléfono (los teléfonos en Colombia suelen tener 10 dígitos)
            id_number = matches.group(1)
            
            # Si encontramos "Teléfono" o "Celular" cerca del número, probablemente sea un teléfono
            context_before = text[max(0, text.find(id_number) - 30):text.find(id_number)]
            if re.search(r'(?:Teléfono|Telefono|Tel|Celular|Móvil|Movil)', context_before, re.IGNORECASE):
                continue
            
            # Limpiar los puntos del número antes de devolverlo
            return id_number.replace('.', '')
    
    # NUEVA FUNCIONALIDAD: Buscar patrones de nombre y revisar la línea siguiente
    nombre_patterns = [
        r'(?:Nombre|Nombre completo|Sr\.|Sra\.|Dr\.|Dra\.)[^\n]*?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,2})',
        r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,2})',
    ]
    
    for pattern in nombre_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            nombre = match.group(1)
            nombre_end_pos = match.end()
            
            # Buscar final de la línea actual
            next_line_start = text.find('\n', nombre_end_pos)
            if next_line_start != -1:
                # Buscar final de la siguiente línea
                next_line_end = text.find('\n', next_line_start + 1)
                if next_line_end == -1:  # Si no hay más líneas, tomar hasta el final
                    next_line_end = len(text)
                
                # Extraer la línea siguiente al nombre
                next_line = text[next_line_start+1:next_line_end].strip()
                
                # Buscar número de identificación en esta línea
                for pattern in patterns:
                    id_match = re.search(pattern, next_line, re.IGNORECASE)
                    if id_match:
                        return id_match.group(1).replace('.', '')
                
                # Si no encontramos con patrones específicos, buscar cualquier número de 7-12 dígitos
                # o números con formato de puntos en la línea siguiente
                digit_match = re.search(r'(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})', next_line)
                if digit_match:
                    num = digit_match.group(1)
                    # Verificar que no sea un teléfono
                    if not re.search(r'(?:Teléfono|Telefono|Tel|Celular|Móvil|Movil)', next_line, re.IGNORECASE):
                        return num.replace('.', '')
    
    # Si no encontramos con los patrones específicos ni en la línea siguiente a un nombre,
    # intentamos con búsqueda más general en todo el texto
    general_pattern = r'(\d{1,3}(?:\.\d{3}){1,3}|\d{7,12})'
    matches = re.finditer(general_pattern, text)
    for match in matches:
        num = match.group(1)
        
        # Verificar el contexto (30 caracteres antes y después)
        start_pos = max(0, match.start() - 30)
        end_pos = min(len(text), match.end() + 30)
        context = text[start_pos:end_pos]
        
        # Si el contexto sugiere que es un documento de identidad
        if re.search(r'(?:C\.?C\.?|Cédula|Cedula|Identificación|Identificacion|Documento|no\.|C\.C\.|No\.|c\.c\.|Nº)', context, re.IGNORECASE):
            # Y no parece ser un teléfono
            if not re.search(r'(?:Teléfono|Telefono|Tel|Celular|Móvil|Movil)', context, re.IGNORECASE):
                return num.replace('.', '')
    
    return ""

def save_to_google_sheet(client, data):
    """Guardar datos en la hoja 'resumen-cv' de Google Sheets con validación mejorada para evitar duplicados"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Guardando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('resumen-cv')
                
                # Obtener todas las columnas para saber dónde buscar los datos
                encabezados = worksheet.row_values(1)
                if not encabezados:
                    st.error("No se pueden leer los encabezados de la hoja. Verifique la estructura.")
                    return False, "Error al leer la estructura de la hoja"
                
                # Encontrar las columnas de identificación y nombre
                try:
                    id_col_idx = encabezados.index("identificacion") + 1  # +1 porque gspread usa índices desde 1
                    nombre_col_idx = encabezados.index("nombre") + 1
                except ValueError:
                    st.warning("No se encontraron las columnas 'identificacion' o 'nombre' en la hoja. Utilizando columnas predeterminadas.")
                    # Si no se encuentran los encabezados, asumimos que están en las primeras posiciones
                    id_col_idx = 2  # Asumiendo que identificación está en la columna B
                    nombre_col_idx = 1  # Asumiendo que nombre está en la columna A
                
                # Verificar si la identificación ya existe
                identificacion = data.get("identificacion", "")
                nombre = data.get("nombre", "")
                
                fila_existente = None
                mensaje_duplicado = ""
                
                # Si tenemos identificación, buscar por ella primero (más preciso)
                if identificacion and identificacion not in ["[Identificación no detectada]", "[No detectada]"]:
                    try:
                        # Buscar la identificación exacta en la columna de identificación
                        celdas_id = worksheet.findall(identificacion)
                        if celdas_id:
                            for celda in celdas_id:
                                # Verificar que sea la columna correcta (puede haber coincidencias en otras columnas)
                                if celda.col == id_col_idx:
                                    fila_existente = celda.row
                                    mensaje_duplicado = f"Se encontró un registro existente con la identificación '{identificacion}'."
                                    break
                    except Exception as e:
                        st.warning(f"Error al buscar por identificación: {str(e)}")
                
                # Si no se encontró por identificación y tenemos nombre, buscar por nombre
                if not fila_existente and nombre and nombre not in ["[Nombre no detectado]", "[No detectado]"]:
                    try:
                        # Buscar coincidencias exactas de nombre
                        celdas_nombre = worksheet.findall(nombre)
                        if celdas_nombre:
                            for celda in celdas_nombre:
                                # Verificar que sea la columna correcta
                                if celda.col == nombre_col_idx:
                                    fila_existente = celda.row
                                    mensaje_duplicado = f"Se encontró un registro existente con el mismo nombre '{nombre}'."
                                    break
                    except Exception as e:
                        st.warning(f"Error al buscar por nombre: {str(e)}")
                
                # Si se encontró un registro existente
                if fila_existente:
                    # Mostrar mensaje y opciones al usuario
                    st.warning(mensaje_duplicado)
                    
                    # Obtener la fila actual para mostrarla
                    try:
                        fila_actual = worksheet.row_values(fila_existente)
                        if len(fila_actual) >= 2:  # Asegurarse de que hay suficientes datos
                            st.info(f"Registro existente: Nombre: '{fila_actual[nombre_col_idx-1]}', Identificación: '{fila_actual[id_col_idx-1]}'")
                    except:
                        st.info("No se pudo recuperar la información del registro existente.")
                    
                    # Preguntar si actualizar o cancelar (usando un checkbox por limitaciones de Streamlit)
                    if st.checkbox("Marque esta casilla para actualizar el registro existente"):
                        # Actualizar la fila existente - convertir el diccionario a lista de valores
                        valores = list(data.values())
                        try:
                            # Actualizar la fila completa manteniendo el orden original de las columnas
                            worksheet.update(f'A{fila_existente}:Z{fila_existente}', [valores])
                            return True, f"Información actualizada para el registro existente. (Fila {fila_existente})"
                        except Exception as e:
                            return False, f"Error al actualizar: {str(e)}"
                    else:
                        return False, "Operación cancelada para evitar duplicados."
                
                # Si no existe un registro similar, añadir nueva fila
                valores = list(data.values())
                worksheet.append_row(valores)
                return True, f"Información guardada con éxito como nuevo registro."

        except HttpError as error:
            if error.resp.status == 429:  # Error de cuota excedida
                if intento < MAX_RETRIES - 1:
                    delay = INITIAL_RETRY_DELAY * (2 ** intento)
                    st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                    time.sleep(delay)
                    continue
                else:
                    return False, "Se excedió el límite de intentos. Por favor, intenta más tarde."
            else:
                return False, f"Error de la API: {str(error)}"

        except Exception as e:
            return False, f"Error al guardar datos: {str(e)}"
    
    return False, "Error al guardar los datos después de varios intentos."

def upload_tab():
    """Pestaña para subir archivo y extraer datos con mejor manejo de errores"""
    st.header("Cargar Hoja de Vida")
    st.write("Cargue un archivo PDF de hoja de vida para extraer la información.")
    
    # Limpiar formulario
    if st.button("Limpiar formulario"):
        clear_form_state()
        st.rerun()
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales. Verifique el archivo secrets.toml")
        return None, None
    
    # Conectar a Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets")
        return None, None
    
    # Subir archivo PDF
    uploaded_file = st.file_uploader("Selecciona un archivo PDF de hoja de vida", type="pdf")
    
    if uploaded_file is not None:
        # Verificar que el archivo tenga contenido
        if uploaded_file.size == 0:
            st.error("El archivo está vacío. Por favor, seleccione un archivo válido.")
            return client, None
            
        # Si hay un nuevo archivo subido, limpiar cualquier estado anterior
        if 'last_file_name' not in st.session_state or st.session_state.last_file_name != uploaded_file.name:
            st.session_state.last_file_name = uploaded_file.name
            clear_form_state()
        
        # Extraer texto del PDF con mejor manejo de errores
        with st.spinner("Extrayendo texto del PDF..."):
            # Asegurarse de que el archivo esté en su posición inicial
            uploaded_file.seek(0)
            
            # Mostrar información del archivo para depuración
            st.info(f"Información del archivo: Nombre={uploaded_file.name}, Tipo={uploaded_file.type}, Tamaño={uploaded_file.size} bytes")
            
            # Extraer texto
            st.session_state.pdf_text, st.session_state.pages_text = extract_text_from_pdf(uploaded_file)
        
        full_text = st.session_state.pdf_text
        pages_text = st.session_state.pages_text
        
        # Verificar si se pudo extraer algo (aunque sea páginas vacías)
        if full_text is not None and pages_text:
            with st.expander("Ver texto extraído del PDF"):
                if full_text:
                    st.text(full_text[:1500] + "..." if len(full_text) > 1500 else full_text)
                else:
                    st.warning("No se pudo extraer texto legible del PDF.")
            
            # Extraer nombre de la primera línea de la página 1
            nombre = extract_name_from_first_line(pages_text.get("pagina1", ""))
            
            # Extraer identificación/cédula
            identificacion = extract_identification(full_text if full_text else "")
            
            # Preparar datos para guardar
            data = {
                "nombre": nombre if nombre else "[Nombre no detectado]",
                "identificacion": identificacion if identificacion else "[Identificación no detectada]"
            }
            
            # Agregar el texto de cada página
            data.update(pages_text)
            
            # Sección para reemplazar en upload_tab() 
            # Mostrar los datos extraídos
            st.subheader("Datos Extraídos:")
            st.write(f"Nombre: {nombre if nombre else '[No detectado]'}")
            st.write(f"Identificación: {identificacion if identificacion else '[No detectada]'}")

            # Sección para ajustar manualmente los datos
            st.subheader("Ajuste manual de datos")
            manual_nombre = st.text_input("Nombre (editar si es necesario):", nombre)
            manual_identificacion = st.text_input("Identificación (editar si es necesario):", identificacion)

            # Actualizar los datos con los valores manuales
            data["nombre"] = manual_nombre
            data["identificacion"] = manual_identificacion

            # Validaciones básicas antes de guardar
            validaciones_ok = True
            mensajes_validacion = []

            if not manual_nombre.strip():
                mensajes_validacion.append("⚠️ El campo Nombre está vacío")
                validaciones_ok = False

            if not manual_identificacion.strip():
                mensajes_validacion.append("⚠️ El campo Identificación está vacío")
                validaciones_ok = False

            # Mostrar advertencias de validación si las hay
            if mensajes_validacion:
                for msg in mensajes_validacion:
                    st.warning(msg)
                if not validaciones_ok:
                    st.warning("Se recomienda completar los campos antes de guardar")

            # Botón para guardar
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Guardar en Google Sheets"):
                    if validaciones_ok:
                        success, message = save_to_google_sheet(client, data)
                        if success:
                            st.success(message)
                            # Guardar los datos en el estado de la sesión
                            st.session_state.cv_data = data
                            # Opcionalmente, limpiar el formulario después de guardar exitosamente
                            if st.checkbox("Limpiar formulario después de guardar",value=True) :
                                clear_form_state()
                                st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Por favor, complete los campos requeridos antes de guardar.")

            with col2:
                    if st.button("Cancelar"):
                        clear_form_state()
                        st.rerun()
            
            return client, data
        else:
            st.error("No se pudo extraer texto del PDF. Esto puede deberse a que el archivo es un PDF escaneado sin OCR o está dañado.")
            st.info("Sugerencia: Puede intentar utilizar herramientas de OCR online para convertir su PDF a texto antes de cargarlo.")
    
    return client, None

def summary_tab(cv_data):
    """Pestaña de resumen de datos"""
    st.header("Resumen de Datos Extraídos")
    
    if cv_data:
        # Mostrar nombre e identificación
        st.subheader("Información Personal")
        st.write(f"Nombre: {cv_data.get('nombre', 'No disponible')}")
        st.write(f"Identificación: {cv_data.get('identificacion', 'No disponible')}")
        
        # Mostrar contenido de cada página
        st.subheader("Contenido por Páginas")
        for key, value in cv_data.items():
            if key.startswith("pagina"):
                with st.expander(f"Contenido de {key}"):
                    st.text(value[:500] + "..." if len(value) > 500 else value)
    else:
        st.info("Primero cargue un archivo PDF en la pestaña 'Cargar CV'.")

def carga_cv():
    # Crear pestañas
    tab1, tab2, tab3 = st.tabs(["Cargar CV", "Resumen", "Gestionar Registros"])
    
    # Variables para almacenar los datos entre pestañas
    if 'cv_data' not in st.session_state:
        st.session_state.cv_data = None
    if 'client' not in st.session_state:
        st.session_state.client = None
    if 'pdf_text' not in st.session_state:
        st.session_state.pdf_text = None
    if 'pages_text' not in st.session_state:
        st.session_state.pages_text = None
    if 'last_file_name' not in st.session_state:
        st.session_state.last_file_name = None
    
    # Pestaña de carga de archivo
    with tab1:
        client, cv_data = upload_tab()
        if cv_data:
            st.session_state.cv_data = cv_data
        if client:
            st.session_state.client = client
    
    # Pestaña de resumen
    with tab2:
        summary_tab(st.session_state.cv_data)
    
    # Pestaña de gestión de registros
    with tab3:
        manage_records_tab(st.session_state.client)

#if __name__ == "__main__":
#    carga_cv()