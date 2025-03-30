import streamlit as st
import pandas as pd
import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import base64
import io
import toml
import gspread
from google.oauth2.service_account import Credentials
#from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
import time

# Configuración de reintentos para manejo de errores de API
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5  # segundos

# Función para cargar credenciales desde .toml
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

# Función para conectar con Google Sheets
def connect_to_gsheets():
    for intento in range(MAX_RETRIES):
        try:
            # Cargar credenciales desde el archivo .toml
            creds = load_credentials_from_toml()
            if not creds:
                return None

            # Definir el alcance
            scope = [
                'https://spreadsheets.google.com/feeds', 
                'https://www.googleapis.com/auth/drive'
            ]

            # Crear credenciales
            credentials = Credentials.from_service_account_info(creds, scopes=scope)

            # Autorizar el cliente
            client = gspread.authorize(credentials)

            # Abrir la hoja existente
            spreadsheet = client.open('gestion-reservas-amo')

            # Obtener las hojas específicas
            try:
                historia_clinica_sheet = spreadsheet.worksheet('historia_clinica')
            except HttpError as error:
                if error.resp.status == 429:  # Error de cuota excedida
                    if intento < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** intento)
                        st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                        time.sleep(delay)
                        continue
                    else:
                        st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
                        return None
                else:
                    st.error(f"Error de la API: {str(error)}")
                    return None
            except Exception as e:
                st.error(f"Error al acceder a la hoja de historia clínica: {e}")
                return None

            try:
                evoluciones_sheet = spreadsheet.worksheet('evolucion_paciente')
            except HttpError as error:
                if error.resp.status == 429:  # Error de cuota excedida
                    if intento < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** intento)
                        st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                        time.sleep(delay)
                        continue
                    else:
                        st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
                        return None
                else:
                    st.error(f"Error de la API: {str(error)}")
                    return None
            except Exception as e:
                st.error(f"Error al acceder a la hoja de evoluciones: {e}")
                return None

            return {
                'historia_clinica': historia_clinica_sheet, 
                'evolucion_paciente': evoluciones_sheet
            }

        except Exception as e:
            st.error(f"Error al conectar con Google Sheets: {e}")
            return None

# Función para obtener lista de pacientes
def get_patient_list():
    sheets_connection = connect_to_gsheets()
    if not sheets_connection:
        return []
    
    historia_clinica_sheet = sheets_connection['historia_clinica']
    
    try:
        # Obtener todos los registros de la hoja de historia clínica
        pacientes = historia_clinica_sheet.get_all_records()
        
        # Extraer nombres de pacientes (ajustar según la estructura real de tu hoja)
        nombres_pacientes = [
            f"{paciente.get('Nombre', '')}" 
            for paciente in pacientes if paciente.get('Nombre')
        ]
        
        return nombres_pacientes
    except Exception as e:
        st.error(f"Error al obtener lista de pacientes: {e}")
        return []

# Función para obtener evoluciones de un paciente específico
def obtener_evoluciones_paciente(nombre_paciente):
    sheets_connection = connect_to_gsheets()
    if not sheets_connection:
        return None
    
    historia_clinica_sheet = sheets_connection['historia_clinica']
    evoluciones_sheet = sheets_connection['evolucion_paciente']
    
    try:
        # Primero, encontrar el ID del paciente en la hoja de historia clínica
        pacientes = historia_clinica_sheet.get_all_records()
        paciente_seleccionado = next(
            (paciente for paciente in pacientes 
             if f"{paciente.get('Nombre', '')}" == nombre_paciente), 
            None
        )
        
        if not paciente_seleccionado:
            st.warning(f"No se encontró el paciente {nombre_paciente}")
            return None
        
        # Buscar evoluciones para este paciente en la hoja de evoluciones
        id_paciente = paciente_seleccionado.get('ID')  # Asumir que hay una columna 'id'
        
        evoluciones = evoluciones_sheet.get_all_records()
        evoluciones_paciente = [
            evolucion for evolucion in evoluciones 
            if evolucion.get('ID') == id_paciente
        ]
        
        return evoluciones_paciente
    
    except Exception as e:
        st.error(f"Error al obtener evoluciones: {e}")
        return None


# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Parametrización de Terapias",
#    page_icon="🏥",
#    layout="wide"
#)

# Función para guardar configuraciones
def guardar_configuracion(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    st.success(f"Configuración guardada en {filename}")

# Función para cargar configuraciones
def cargar_configuracion(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Función para generar PDF
def generar_pdf(tipo_terapia, configuracion, formulario=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Crear estilo personalizado basado en la configuración
    color_texto = configuracion.get("colorTexto", "#000000").lstrip('#')
    color_rgb = tuple(int(color_texto[i:i+2], 16) for i in (0, 2, 4))
    color_rgb = [x/255 for x in color_rgb]  # Convertir a valores entre 0 y 1
    
    estilo_titulo = ParagraphStyle(
        'EstiloTitulo',
        parent=styles['Heading1'],
        textColor=colors.Color(color_rgb[0], color_rgb[1], color_rgb[2])
    )
    
    estilo_subtitulo = ParagraphStyle(
        'EstiloSubtitulo',
        parent=styles['Heading2'],
        textColor=colors.Color(color_rgb[0], color_rgb[1], color_rgb[2])
    )
    
    # Elementos del PDF
    elementos = []
    
    # Título
    elementos.append(Paragraph(f"Formato de Terapia: {tipo_terapia}", estilo_titulo))
    elementos.append(Spacer(1, 12))
    
    # Información de configuración
    elementos.append(Paragraph("Configuración del formato:", estilo_subtitulo))
    elementos.append(Spacer(1, 6))
    
    # Tabla de configuración
    datos_config = [
        ["Propiedad", "Valor"],
        ["Plantilla", configuracion.get("plantilla", "")],
        ["Logo", configuracion.get("logo", "")]
    ]
    
    tabla_config = Table(datos_config, colWidths=[200, 300])
    tabla_config.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (1, 0), 12),
        ('BACKGROUND', (0, 1), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elementos.append(tabla_config)
    elementos.append(Spacer(1, 12))
    
    # Si hay un formulario asociado, agregarlo
    if formulario:
        elementos.append(Paragraph(f"Formulario: {formulario['nombre']}", estilo_subtitulo))
        elementos.append(Paragraph(formulario['descripcion'], styles['Normal']))
        elementos.append(Spacer(1, 12))
        
        # Agregar secciones del formulario
        for seccion in formulario['secciones']:
            elementos.append(Paragraph(f"Sección: {seccion['nombre']}", estilo_subtitulo))
            elementos.append(Spacer(1, 6))
            
            # Campos de la sección
            datos_campos = [["Campo", "Tipo", "Obligatorio"]]
            
            for campo in seccion['campos']:
                datos_campos.append([
                    campo.get('nombre', campo.get('id', 'Sin nombre')),
                    campo.get('tipo', 'texto'),
                    "Sí" if campo.get('obligatorio', False) else "No"
                ])
            
            tabla_campos = Table(datos_campos, colWidths=[200, 150, 100])
            tabla_campos.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elementos.append(tabla_campos)
            elementos.append(Spacer(1, 12))
    
    # Construir PDF
    doc.build(elementos)
    buffer.seek(0)
    return buffer

# Función para crear un enlace de descarga para un archivo
def get_download_link(buffer, filename, text):
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Sidebar
st.sidebar.title("Menú de Parametrización")
menu = st.sidebar.radio(
    "Seleccione una opción:",
    ["Inicio", "Cargar Excel", "Configuración de Formatos", "Campos Obligatorios", "Formularios de Evaluación", "Generar PDF"]
)

# Página de inicio
if menu == "Inicio":
    st.title("Sistema de Parametrización de Terapias")
    st.markdown("""
    Esta aplicación permite configurar diferentes parámetros para su sistema de gestión de terapias.
    
    ### Funcionalidades:
    - Cargar parámetros desde archivos Excel
    - Configurar formatos específicos por tipo de terapia
    - Definir campos obligatorios según normativas
    - Personalizar formularios de evaluación
    
    Para comenzar, seleccione una opción del menú lateral.
    """)
    
    st.info("Nota: Todas las configuraciones se guardarán en archivos JSON para su fácil integración con otros sistemas.")

# Cargar Excel
elif menu == "Cargar Excel":
    st.title("Cargar Archivo de Parametrización")
    
    uploaded_file = st.file_uploader("Cargar archivo Excel", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            # Intentamos leer todas las hojas del Excel
            formatos_df = pd.read_excel(uploaded_file, sheet_name="Formatos", engine="openpyxl")
            campos_df = pd.read_excel(uploaded_file, sheet_name="CamposObligatorios", engine="openpyxl")
            formularios_df = pd.read_excel(uploaded_file, sheet_name="FormulariosEvaluacion", engine="openpyxl")
            
            st.success("¡Archivo cargado correctamente!")
            
            # Guardamos los DataFrames en la sesión
            st.session_state['formatos_df'] = formatos_df
            st.session_state['campos_df'] = campos_df
            st.session_state['formularios_df'] = formularios_df
            
            # Mostramos las pestañas con la información
            tabs = st.tabs(["Formatos", "Campos Obligatorios", "Formularios"])
            
            with tabs[0]:
                st.subheader("Formatos por Tipo de Terapia")
                st.dataframe(formatos_df)
            
            with tabs[1]:
                st.subheader("Campos Obligatorios según Normativa")
                st.dataframe(campos_df)
            
            with tabs[2]:
                st.subheader("Formularios de Evaluación")
                st.dataframe(formularios_df)
                
            # Opción para procesar todas las configuraciones a la vez
            if st.button("Procesar todas las configuraciones"):
                # Procesar formatos
                formatos_config = {}
                for _, row in formatos_df.iterrows():
                    tipo_terapia = row['TipoTerapia']
                    formatos_config[tipo_terapia] = {
                        "colorFondo": row['ColorFondo'],
                        "colorTexto": row['ColorTexto'],
                        "plantilla": row['Plantilla'],
                        "logo": row['Logo'],
                        "configuracionAdicional": json.loads(row['ConfiguracionAdicional']) if isinstance(row.get('ConfiguracionAdicional'), str) else {}
                    }
                guardar_configuracion(formatos_config, "formatos_config.json")
                
                # Procesar campos obligatorios
                campos_config = {}
                for _, row in campos_df.iterrows():
                    normativa = row['Normativa']
                    if normativa not in campos_config:
                        campos_config[normativa] = []
                    campos_config[normativa].append({
                        "campo": row['Campo'],
                        "descripcion": row['Descripcion'],
                        "tipo": row['Tipo'],
                        "validacion": row['Validacion']
                    })
                guardar_configuracion(campos_config, "campos_obligatorios_config.json")
                
                # Procesar formularios
                formularios_config = {}
                for _, row in formularios_df.iterrows():
                    id_formulario = row['IDFormulario']
                    if id_formulario not in formularios_config:
                        formularios_config[id_formulario] = {
                            "nombre": row['Nombre'],
                            "descripcion": row['Descripcion'],
                            "tipoTerapia": row['TipoTerapia'],
                            "secciones": []
                        }
                    
                    # Si existe la información de secciones
                    if 'Seccion' in row and 'CamposSeccion' in row:
                        seccion_existente = False
                        for seccion in formularios_config[id_formulario]["secciones"]:
                            if seccion["nombre"] == row['Seccion']:
                                seccion_existente = True
                                break
                        
                        if not seccion_existente:
                            formularios_config[id_formulario]["secciones"].append({
                                "nombre": row['Seccion'],
                                "campos": json.loads(row['CamposSeccion']) if isinstance(row.get('CamposSeccion'), str) else []
                            })
                
                guardar_configuracion(formularios_config, "formularios_config.json")
                
        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")
            st.warning("Asegúrese de que el archivo Excel contiene las hojas: 'Formatos', 'CamposObligatorios' y 'FormulariosEvaluacion'")
            
            # Mostrar estructura esperada
            st.subheader("Estructura esperada del archivo Excel:")
            
            st.markdown("""
            ### Hoja "Formatos":
            - TipoTerapia (texto): Identificador del tipo de terapia
            - ColorFondo (texto): Código hexadecimal del color de fondo
            - ColorTexto (texto): Código hexadecimal del color del texto
            - Plantilla (texto): Ruta o nombre de la plantilla
            - Logo (texto): Ruta o nombre del logo
            - ConfiguracionAdicional (texto/JSON): Configuración adicional en formato JSON
            
            ### Hoja "CamposObligatorios":
            - Normativa (texto): Identificador de la normativa
            - Campo (texto): Nombre del campo
            - Descripcion (texto): Descripción del campo
            - Tipo (texto): Tipo de dato del campo
            - Validacion (texto): Reglas de validación
            
            ### Hoja "FormulariosEvaluacion":
            - IDFormulario (texto): Identificador único del formulario
            - Nombre (texto): Nombre del formulario
            - Descripcion (texto): Descripción del formulario
            - TipoTerapia (texto): Tipo de terapia asociada
            - Seccion (texto): Nombre de la sección
            - CamposSeccion (texto/JSON): Lista de campos en formato JSON
            """)

# Configuración de Formatos
elif menu == "Configuración de Formatos":
    st.title("Configuración de Formatos por Tipo de Terapia")
    
    # Cargar configuración existente
    formatos_config = cargar_configuracion("formatos_config.json")
    
    # Verificar si hay datos cargados de Excel
    if 'formatos_df' in st.session_state:
        st.info("Se encontraron datos de formatos desde el archivo Excel cargado.")
        # Usar como base los datos del Excel
        formatos_df = st.session_state['formatos_df']
        tipos_terapia = formatos_df['TipoTerapia'].unique().tolist()
    else:
        # Permitir añadir tipos de terapia manualmente
        tipos_terapia = list(formatos_config.keys())
        nuevo_tipo = st.text_input("Añadir nuevo tipo de terapia")
        if nuevo_tipo and st.button("Añadir"):
            if nuevo_tipo not in tipos_terapia:
                tipos_terapia.append(nuevo_tipo)
                formatos_config[nuevo_tipo] = {"colorFondo": "#FFFFFF", "colorTexto": "#000000", "plantilla": "", "logo": "", "configuracionAdicional": {}}
    
    # Mostrar configuración por tipo de terapia
    if tipos_terapia:
        tipo_seleccionado = st.selectbox("Seleccione tipo de terapia para configurar", tipos_terapia)
        
        # Si es un tipo nuevo, inicializar
        if tipo_seleccionado not in formatos_config:
            formatos_config[tipo_seleccionado] = {"colorFondo": "#FFFFFF", "colorTexto": "#000000", "plantilla": "", "logo": "", "configuracionAdicional": {}}
        
        # Editar configuración
        with st.form(f"form_formato_{tipo_seleccionado}"):
            st.subheader(f"Configuración para {tipo_seleccionado}")
            
            color_fondo = st.color_picker("Color de fondo", formatos_config[tipo_seleccionado].get("colorFondo", "#FFFFFF"))
            color_texto = st.color_picker("Color de texto", formatos_config[tipo_seleccionado].get("colorTexto", "#000000"))
            plantilla = st.text_input("Plantilla", formatos_config[tipo_seleccionado].get("plantilla", ""))
            logo = st.text_input("Logo", formatos_config[tipo_seleccionado].get("logo", ""))
            
            # Configuración adicional como JSON
            st.subheader("Configuración adicional (formato JSON)")
            config_adicional = st.text_area("JSON", json.dumps(formatos_config[tipo_seleccionado].get("configuracionAdicional", {}), indent=2))
            
            submitted = st.form_submit_button("Guardar configuración")
            
            if submitted:
                try:
                    # Actualizar configuración
                    formatos_config[tipo_seleccionado]["colorFondo"] = color_fondo
                    formatos_config[tipo_seleccionado]["colorTexto"] = color_texto
                    formatos_config[tipo_seleccionado]["plantilla"] = plantilla
                    formatos_config[tipo_seleccionado]["logo"] = logo
                    formatos_config[tipo_seleccionado]["configuracionAdicional"] = json.loads(config_adicional)
                    
                    # Guardar configuración
                    guardar_configuracion(formatos_config, "formatos_config.json")
                    
                except json.JSONDecodeError:
                    st.error("Error en el formato JSON de la configuración adicional")
        
        # Previsualización
        st.subheader("Previsualización")
        preview_col1, preview_col2 = st.columns(2)
        
        with preview_col1:
            st.markdown("**Configuración actual:**")
            st.json(formatos_config[tipo_seleccionado])
        
        with preview_col2:
            st.markdown("**Muestra de estilo:**")
            style = f"""
            <div style="background-color: {formatos_config[tipo_seleccionado]['colorFondo']}; 
                        color: {formatos_config[tipo_seleccionado]['colorTexto']}; 
                        padding: 20px; 
                        border-radius: 5px;">
                <h3>Ejemplo de {tipo_seleccionado}</h3>
                <p>Este es un ejemplo de cómo se vería el texto con la configuración seleccionada.</p>
            </div>
            """
            st.markdown(style, unsafe_allow_html=True)
    else:
        st.warning("No hay tipos de terapia configurados. Cargue un archivo Excel o añada un nuevo tipo.")

# Campos Obligatorios
elif menu == "Campos Obligatorios":
    st.title("Definición de Campos Obligatorios según Normativa")
    
    # Cargar configuración existente
    campos_config = cargar_configuracion("campos_obligatorios_config.json")
    
    # Verificar si hay datos cargados de Excel
    if 'campos_df' in st.session_state:
        st.info("Se encontraron datos de campos obligatorios desde el archivo Excel cargado.")
        # Usar como base los datos del Excel
        campos_df = st.session_state['campos_df']
        normativas = campos_df['Normativa'].unique().tolist()
    else:
        # Permitir añadir normativas manualmente
        normativas = list(campos_config.keys())
        nueva_normativa = st.text_input("Añadir nueva normativa")
        if nueva_normativa and st.button("Añadir Normativa"):
            if nueva_normativa not in normativas:
                normativas.append(nueva_normativa)
                campos_config[nueva_normativa] = []
    
    # Mostrar y editar campos por normativa
    if normativas:
        normativa_seleccionada = st.selectbox("Seleccione normativa para configurar", normativas)
        
        # Si es una normativa nueva, inicializar
        if normativa_seleccionada not in campos_config:
            campos_config[normativa_seleccionada] = []
        
        # Mostrar campos existentes
        if campos_config[normativa_seleccionada]:
            st.subheader(f"Campos obligatorios para {normativa_seleccionada}")
            
            for i, campo in enumerate(campos_config[normativa_seleccionada]):
                with st.expander(f"{campo['campo']} ({campo['tipo']})"):
                    # Mostrar detalles y permitir editar
                    new_campo = st.text_input(f"Campo #{i+1}", campo['campo'], key=f"campo_{i}")
                    new_descripcion = st.text_area(f"Descripción #{i+1}", campo['descripcion'], key=f"desc_{i}")
                    new_tipo = st.selectbox(f"Tipo #{i+1}", ["texto", "numero", "fecha", "seleccion", "booleano"], 
                                          index=["texto", "numero", "fecha", "seleccion", "booleano"].index(campo['tipo']), key=f"tipo_{i}")
                    new_validacion = st.text_input(f"Validación #{i+1}", campo['validacion'], key=f"val_{i}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Actualizar", key=f"update_{i}"):
                            campos_config[normativa_seleccionada][i] = {
                                "campo": new_campo,
                                "descripcion": new_descripcion,
                                "tipo": new_tipo,
                                "validacion": new_validacion
                            }
                            guardar_configuracion(campos_config, "campos_obligatorios_config.json")
                            st.success("Campo actualizado")
                    
                    with col2:
                        if st.button("Eliminar", key=f"delete_{i}"):
                            campos_config[normativa_seleccionada].pop(i)
                            guardar_configuracion(campos_config, "campos_obligatorios_config.json")
                            st.success("Campo eliminado")
                            st.rerun()
        
        # Añadir nuevo campo
        st.subheader(f"Añadir nuevo campo para {normativa_seleccionada}")
        with st.form("nuevo_campo_form"):
            nuevo_campo = st.text_input("Nombre del campo")
            nueva_descripcion = st.text_area("Descripción")
            nuevo_tipo = st.selectbox("Tipo de dato", ["texto", "numero", "fecha", "seleccion", "booleano"])
            nueva_validacion = st.text_input("Reglas de validación (expresión regular, rango, etc.)")
            
            if st.form_submit_button("Añadir campo"):
                if nuevo_campo:
                    campos_config[normativa_seleccionada].append({
                        "campo": nuevo_campo,
                        "descripcion": nueva_descripcion,
                        "tipo": nuevo_tipo,
                        "validacion": nueva_validacion
                    })
                    guardar_configuracion(campos_config, "campos_obligatorios_config.json")
                    st.success("Campo añadido correctamente")
                    st.rerun()
                else:
                    st.error("El nombre del campo es obligatorio")
    else:
        st.warning("No hay normativas configuradas. Cargue un archivo Excel o añada una nueva normativa.")

# Formularios de Evaluación
elif menu == "Formularios de Evaluación":
    st.title("Personalización de Formularios de Evaluación")
    
    # Cargar configuración existente
    formularios_config = cargar_configuracion("formularios_config.json")
    
    # Pestañas para gestionar formularios
    tab1, tab2 = st.tabs(["Ver/Editar Formularios", "Crear Nuevo Formulario"])
    
    with tab1:
        # Verificar si hay formularios configurados
        if formularios_config:
            # Lista de formularios disponibles
            ids_formularios = list(formularios_config.keys())
            id_seleccionado = st.selectbox("Seleccione un formulario para editar", ids_formularios)
            
            if id_seleccionado:
                formulario = formularios_config[id_seleccionado]
                
                st.subheader(f"Editar formulario: {formulario['nombre']}")
                
                # Información básica del formulario
                with st.form("editar_formulario"):
                    nuevo_nombre = st.text_input("Nombre", formulario['nombre'])
                    nueva_descripcion = st.text_area("Descripción", formulario['descripcion'])
                    nuevo_tipo_terapia = st.text_input("Tipo de terapia", formulario['tipoTerapia'])
                    
                    st.subheader("Secciones del formulario")
                    
                    # Mostrar secciones existentes
                    secciones_actualizadas = []
                    for i, seccion in enumerate(formulario['secciones']):
                        st.markdown(f"**Sección {i+1}: {seccion['nombre']}**")
                        nuevo_nombre_seccion = st.text_input(f"Nombre de la sección #{i+1}", seccion['nombre'], key=f"seccion_nombre_{i}")
                        
                        # Convertir lista de campos a string para edición
                        campos_str = json.dumps(seccion['campos'], indent=2)
                        nuevos_campos = st.text_area(f"Campos (formato JSON) #{i+1}", campos_str, key=f"seccion_campos_{i}")
                        
                        try:
                            nuevos_campos_json = json.loads(nuevos_campos)
                            secciones_actualizadas.append({
                                "nombre": nuevo_nombre_seccion,
                                "campos": nuevos_campos_json
                            })
                        except json.JSONDecodeError:
                            st.error(f"Error en el formato JSON de los campos de la sección {i+1}")
                            secciones_actualizadas.append(seccion)  # Mantener la sección original
                    
                    # Opción para agregar nueva sección
                    agregar_seccion = st.checkbox("Agregar nueva sección")
                    if agregar_seccion:
                        nombre_nueva_seccion = st.text_input("Nombre de la nueva sección")
                        campos_nueva_seccion = st.text_area("Campos de la nueva sección (formato JSON)", "[]")
                        
                        try:
                            campos_nueva_seccion_json = json.loads(campos_nueva_seccion)
                            if nombre_nueva_seccion:
                                secciones_actualizadas.append({
                                    "nombre": nombre_nueva_seccion,
                                    "campos": campos_nueva_seccion_json
                                })
                        except json.JSONDecodeError:
                            st.error("Error en el formato JSON de los campos de la nueva sección")
                    
                    if st.form_submit_button("Guardar cambios"):
                        # Actualizar formulario
                        formularios_config[id_seleccionado] = {
                            "nombre": nuevo_nombre,
                            "descripcion": nueva_descripcion,
                            "tipoTerapia": nuevo_tipo_terapia,
                            "secciones": secciones_actualizadas
                        }
                        
                        guardar_configuracion(formularios_config, "formularios_config.json")
                        st.success("Formulario actualizado correctamente")
                
                # Vista previa del formulario
                st.subheader("Vista previa del formulario")
                st.json(formularios_config[id_seleccionado])
                
                # Eliminar formulario
                if st.button("Eliminar este formulario"):
                    del formularios_config[id_seleccionado]
                    guardar_configuracion(formularios_config, "formularios_config.json")
                    st.success("Formulario eliminado correctamente")
                    st.rerun()
        else:
            st.warning("No hay formularios configurados. Cree uno nuevo o cargue un archivo Excel.")
    
    with tab2:
        st.subheader("Crear nuevo formulario de evaluación")
        
        with st.form("nuevo_formulario"):
            # Información básica
            id_formulario = st.text_input("ID del formulario (único)")
            nombre_formulario = st.text_input("Nombre del formulario")
            descripcion_formulario = st.text_area("Descripción")
            tipo_terapia_formulario = st.text_input("Tipo de terapia asociada")
            
            # Primera sección (obligatoria)
            st.subheader("Primera sección")
            nombre_seccion = st.text_input("Nombre de la sección")
            campos_seccion = st.text_area("Campos (formato JSON)", """[
  {
    "id": "campo1",
    "nombre": "Nombre del campo",
    "tipo": "texto",
    "obligatorio": true,
    "placeholder": "Escribe aquí..."
  }
]""")
            
            if st.form_submit_button("Crear formulario"):
                if id_formulario and nombre_formulario and nombre_seccion:
                    try:
                        campos_json = json.loads(campos_seccion)
                        
                        # Crear nuevo formulario
                        nuevo_formulario = {
                            "nombre": nombre_formulario,
                            "descripcion": descripcion_formulario,
                            "tipoTerapia": tipo_terapia_formulario,
                            "secciones": [
                                {
                                    "nombre": nombre_seccion,
                                    "campos": campos_json
                                }
                            ]
                        }
                        
                        # Guardar formulario
                        formularios_config[id_formulario] = nuevo_formulario
                        guardar_configuracion(formularios_config, "formularios_config.json")
                        st.success("Formulario creado correctamente")
                        
                    except json.JSONDecodeError:
                        st.error("Error en el formato JSON de los campos")
                else:
                    st.error("ID del formulario, nombre y nombre de sección son obligatorios")

# Nueva sección para generar PDF

elif menu == "Generar PDF":
        st.title("Generar PDF para Impresión")
        
        # Cargar configuraciones
        formatos_config = cargar_configuracion("formatos_config.json")
        formularios_config = cargar_configuracion("formularios_config.json")
        
        if not formatos_config:
            st.warning("No hay formatos de terapia configurados. Configure formatos primero.")
        else:
            # Nueva sección de integración con Google Sheets
            st.header("Integración con Historias Clínicas")
            
            # Obtener lista de pacientes
            pacientes = get_patient_list()
            
            if pacientes:
                # Selector de paciente
                paciente_seleccionado = st.selectbox("Seleccione un paciente", pacientes)
                
                # Botón para cargar evoluciones
                if st.button("Cargar Evoluciones"):
                    evoluciones = obtener_evoluciones_paciente(paciente_seleccionado)
                    
                    if evoluciones:
                        st.subheader(f"Evoluciones de {paciente_seleccionado}")
                        df_evoluciones = pd.DataFrame(evoluciones)
                        st.dataframe(df_evoluciones)
                        
                        # Integrar con generación de PDF
                        tipos_terapia = list(formatos_config.keys())
                        tipo_seleccionado = st.selectbox("Seleccione tipo de terapia para el PDF", tipos_terapia)
        
                        configuracion = formatos_config[tipo_seleccionado]
        
                        # Buscar formularios asociados
                        formularios_asociados = {
                        id_form: form["nombre"] 
                        for id_form, form in formularios_config.items() 
                            if form.get("tipoTerapia") == tipo_seleccionado
                            }
        
                        if not formularios_asociados:
                            st.warning(f"No hay formularios para el tipo de terapia '{tipo_seleccionado}'")
                            #return
        
                        # Selección de formulario
                        id_formulario = st.selectbox(
                        "Seleccione un formulario", 
                        options=list(formularios_asociados.keys()),
                        format_func=lambda x: formularios_asociados[x]
                        )
                        formulario_seleccionado = formularios_config[id_formulario]
        
                        # Selección de campos de evolución
                        datos_evolucion = st.multiselect(
                        "Seleccione campos de evolución para incluir en el PDF", 
                        list(df_evoluciones.columns)
                        )
        
                        # Generar PDF
                        if st.button("Generar PDF con Datos de Evolución"):
                            # Modificar el formulario con los datos seleccionados
                            for seccion in formulario_seleccionado['secciones']:
                                for campo in seccion['campos']:
                                    if campo['nombre'] in datos_evolucion:
                                        campo['valor'] = df_evoluciones[campo['nombre']].iloc[0]
            
                            # Generar PDF
                            pdf_buffer = generar_pdf(
                            tipo_seleccionado, 
                            configuracion, 
                            formulario_seleccionado
                            )
            
                            # Botón de descarga
                            st.download_button(
                            label="Descargar PDF con Datos de Evolución",
                            data=pdf_buffer,
                            file_name=f"evolucion_{paciente_seleccionado.lower().replace(' ', '_')}.pdf",
                            mime="application/pdf"
                            )
                        #else:
                        #    st.warning(f"No hay formularios para el tipo de terapia '{tipo_seleccionado}'")
                    else:
                        st.warning("No se encontraron evoluciones para este paciente")
            else:
                st.warning("No se pudieron cargar los pacientes. Verifique la conexión con Google Sheets.")
    

# Añadir instrucciones sobre cómo integrar con otras aplicaciones
st.sidebar.markdown("---")
st.sidebar.subheader("Integración")
st.sidebar.info("""
Los archivos de configuración generados (formatos_config.json, campos_obligatorios_config.json y formularios_config.json) 
pueden ser utilizados fácilmente en sus aplicaciones.

Para integrar con otras aplicaciones, simplemente lea estos archivos JSON con cualquier biblioteca estándar.
""")

# Footer
#st.sidebar.markdown("---")
#st.sidebar.caption("Sistema de Parametrización v1.0")
