import streamlit as st
import pandas as pd
import gspread
import json
import toml
import time
import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from google.oauth2.service_account import Credentials
from datetime import datetime

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(page_title="Gestión de Vacantes", layout="wide")
#st.title("Sistema de Gestión de Vacantes")

def crear_pdf_vacante(datos_vacante):
    """Crear un PDF con los datos de una vacante"""
    buffer = io.BytesIO()
    
    # Configurar el documento PDF
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    titulo_style = styles['Heading1']
    subtitulo_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Estilo personalizado para campos
    campo_style = ParagraphStyle(
        'Campo',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        spaceAfter=3
    )
    
    # Título principal
    elements.append(Paragraph(f"VACANTE: {datos_vacante['cargo']}", titulo_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Información general
    elements.append(Paragraph("INFORMACIÓN GENERAL", subtitulo_style))
    
    # Tabla de información general
    data = [
        ["Cargo:", datos_vacante['cargo']],
        ["Área:", datos_vacante['area']],
        ["Estado:", datos_vacante['estado']],
        ["Jefe Inmediato:", datos_vacante['jefe']],
        ["Tipo de Contrato:", datos_vacante['tipo_contrato']],
        ["Tiempo:", datos_vacante['tiempo']],
        ["Salario:", datos_vacante['salario']],
        ["Fecha de Creación:", datos_vacante.get('fecha', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))]
    ]
    
    t = Table(data, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 0.25*inch))
    
    # Requisitos y detalles
    elements.append(Paragraph("REQUISITOS Y DETALLES", subtitulo_style))
    
    # Funciones principales
    elements.append(Paragraph("Funciones Principales:", campo_style))
    elements.append(Paragraph(datos_vacante['funciones'], normal_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Estudios requeridos
    elements.append(Paragraph("Estudios Requeridos:", campo_style))
    elements.append(Paragraph(datos_vacante['estudios'], normal_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Experiencia requerida
    elements.append(Paragraph("Experiencia Requerida:", campo_style))
    elements.append(Paragraph(datos_vacante['experiencia'], normal_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Habilidades y competencias
    elements.append(Paragraph("Habilidades y Competencias:", campo_style))
    elements.append(Paragraph(datos_vacante['habilidades'], normal_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Justificación de la vacante
    elements.append(Paragraph("Justificación de la Vacante:", campo_style))
    elements.append(Paragraph(datos_vacante['justificacion'], normal_style))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el PDF del buffer
    buffer.seek(0)
    return buffer

def crear_pdf_todas_vacantes(vacantes):
    """Crear un PDF con un resumen de todas las vacantes"""
    buffer = io.BytesIO()
    
    # Configurar el documento PDF
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    titulo_style = styles['Heading1']
    subtitulo_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Título principal
    elements.append(Paragraph("REPORTE DE VACANTES", titulo_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Fecha del reporte
    elements.append(Paragraph(f"Fecha del reporte: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Tabla de resumen de vacantes
    elementos_tabla = [
        ["#", "Cargo", "Área", "Estado", "Jefe", "Salario", "Fecha"]
    ]
    
    for i, vacante in enumerate(vacantes):
        elementos_tabla.append([
            str(i+1),
            vacante['cargo'],
            vacante['area'],
            vacante['estado'],
            vacante['jefe'],
            vacante['salario'],
            vacante.get('fecha', '')
        ])
    
    # Crear tabla
    t = Table(elementos_tabla, repeatRows=1)
    
    # Estilo de la tabla
    estilo_tabla = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    # Aplicar estilo a filas alternas para mejorar la legibilidad
    for i in range(1, len(elementos_tabla)):
        if i % 2 == 0:
            estilo_tabla.add('BACKGROUND', (0, i), (-1, i), colors.white)
    
    t.setStyle(estilo_tabla)
    elements.append(t)
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el PDF del buffer
    buffer.seek(0)
    return buffer

def get_download_link_pdf(buffer, filename):
    """Generar un enlace de descarga para un archivo PDF"""
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Descargar archivo PDF</a>'

def load_credentials_from_toml():
    """Cargar credenciales desde el archivo secrets.toml"""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except Exception as e:
        st.error(f"Error cargando credenciales: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    """Establecer conexión con Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {str(e)}")
        return None

def guardar_vacante(client, datos_vacante):
    """Guardar los datos de la vacante en Google Sheets"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Guardando información... (Intento {intento + 1}/{MAX_RETRIES})'):
                # Abrir la hoja de cálculo y seleccionar la hoja "vacantes"
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('vacantes')
                
                # Obtener los valores actuales para añadir la nueva fila
                valores_actuales = worksheet.get_all_values()
                
                # Si la hoja está vacía, añadir encabezados
                if not valores_actuales:
                    encabezados = ["estado", "cargo", "area", "funciones", "estudios", 
                                  "experiencia", "habilidades", "salario", "jefe", 
                                  "tipo_contrato", "tiempo", "justificacion","fecha"]
                    worksheet.append_row(encabezados)
                
                # Añadir la nueva fila con los datos de la vacante
                nueva_fila = [
                    datos_vacante["estado"],
                    datos_vacante["cargo"],
                    datos_vacante["area"],
                    datos_vacante["funciones"],
                    datos_vacante["estudios"],
                    datos_vacante["experiencia"],
                    datos_vacante["habilidades"],
                    datos_vacante["salario"],
                    datos_vacante["jefe"],
                    datos_vacante["tipo_contrato"],
                    datos_vacante["tiempo"],
                    datos_vacante["justificacion"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
                
                worksheet.append_row(nueva_fila)
                return True, "Información guardada exitosamente."
                
        except Exception as e:
            # Si es el último intento, mostrar error
            if intento == MAX_RETRIES - 1:
                return False, f"Error al guardar los datos: {str(e)}"
            # Esperar antes de reintentar
            delay = INITIAL_RETRY_DELAY * (2 ** intento)
            time.sleep(delay)
    
    return False, "Error al guardar los datos después de varios intentos."

def obtener_vacantes(client):
    """Obtener todas las vacantes del Google Sheet"""
    try:
        # Abrir la hoja de cálculo y seleccionar la hoja "vacantes"
        sheet = client.open('gestion-agenda')
        worksheet = sheet.worksheet('vacantes')
        
        # Obtener todos los datos
        datos = worksheet.get_all_records()
        return True, datos
    except Exception as e:
        return False, f"Error al obtener las vacantes: {str(e)}"

def eliminar_vacante(client, indice_fila):
    """Eliminar una vacante específica en Google Sheets"""
    for intento in range(MAX_RETRIES):
        try:
            with st.spinner(f'Eliminando vacante... (Intento {intento + 1}/{MAX_RETRIES})'):
                # Abrir la hoja de cálculo y seleccionar la hoja "vacantes"
                sheet = client.open('gestion-agenda')
                worksheet = sheet.worksheet('vacantes')
                
                # Sumar 2 al índice porque la fila 1 es el encabezado y los índices en Google Sheets comienzan desde 1
                fila_real = indice_fila + 2
                
                # Eliminar la fila
                worksheet.delete_rows(fila_real)
                return True, "Vacante eliminada exitosamente."
                
        except Exception as e:
            # Si es el último intento, mostrar error
            if intento == MAX_RETRIES - 1:
                return False, f"Error al eliminar la vacante: {str(e)}"
            # Esperar antes de reintentar
            delay = INITIAL_RETRY_DELAY * (2 ** intento)
            time.sleep(delay)
    
    return False, "Error al eliminar la vacante después de varios intentos."

def vacante():
    st.title("Sistema de Gestión de Vacantes")

    """Función principal que maneja la interfaz y la lógica del formulario"""
    # Cargar credenciales
    creds, _ = load_credentials_from_toml()
    if not creds:
        st.error("No se pudieron cargar las credenciales.")
        return
    
    # Establecer conexión con Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets.")
        return
    
    # Crear pestañas para las diferentes funcionalidades
    tab1, tab2, tab3 = st.tabs(["Crear Vacante", "Eliminar Vacante", "Generar PDF"])
    
    with tab1:
        # Formulario para crear vacante (código existente)
        with st.form("formulario_vacante"):
            st.subheader("Información de la Vacante")
            
            # Primera fila: Cargo, Área y Jefe
            col1, col2, col3 = st.columns(3)
            with col1:
                lista_estado = ["Activo", "Inactivo"]
                # Lista predefinida de cargos para empresa de servicios
                lista_cargos = [
                    "Seleccione...",
                    # Dirección y Gerencia
                    "Director General", "Gerente General", "Director Ejecutivo",
                    "Director Administrativo", "Director Comercial", "Director de Operaciones",
                    "Director Financiero", "Director de Recursos Humanos", "Director de Marketing",
                    "Director de TI", "Gerente de Sucursal", "Gerente de Proyecto",
                    # Área Comercial y Atención al Cliente
                    "Ejecutivo de Ventas", "Asesor Comercial", "Consultor de Servicios",
                    "Supervisor de Ventas", "Coordinador de Ventas", "Representante de Servicio al Cliente",
                    "Supervisor de Atención al Cliente", "Asesor de Servicio", "Ejecutivo de Cuentas",
                    "Ejecutivo de Desarrollo de Negocios", "Gestor de Cuentas Clave",
                    # Área Administrativa y Financiera
                    "Asistente Administrativo", "Auxiliar Administrativo", "Secretaria Ejecutiva",
                    "Recepcionista", "Contador", "Auxiliar Contable", "Analista Financiero",
                    "Tesorero", "Auditor Interno", "Analista de Costos", "Asistente de Facturación",
                    # Área de Recursos Humanos
                    "Analista de Recursos Humanos", "Asistente de Recursos Humanos", 
                    "Reclutador", "Especialista en Selección", "Coordinador de Capacitación",
                    "Especialista en Compensación y Beneficios", "Analista de Nómina",
                    # Área de Tecnología
                    "Desarrollador de Software", "Analista de Sistemas", "Ingeniero de Software",
                    "Administrador de Base de Datos", "Técnico de Soporte TI", "Analista de Seguridad Informática",
                    "Especialista en Redes", "Diseñador Web", "Analista Programador", "Administrador de Sistemas",
                    # Área de Marketing y Comunicaciones
                    "Especialista en Marketing Digital", "Community Manager", "Diseñador Gráfico", "Especialista en SEO/SEM", "Analista de Marketing", "Coordinador de Eventos", "Gestor de Contenidos", "Especialista en Comunicaciones", "Analista de Mercado",
                    # Área de Logística y Operaciones
                    "Coordinador de Operaciones", "Supervisor de Operaciones", "Analista de Logística", "Salvavidas", "Piscinero", "Vigilancia","Supervisora de Bodega","Supervisor de Bodega", "Jefe de Bodega", "Coordinador de Distribución", "Inspector de Calidad", "Despachador",
                    # Área de Servicios Profesionales
                    "Consultor Senior", "Consultor Junior", "Analista de Procesos", "Asesor Legal", "Especialista en Compliance", "Especialista en Servicios", "Coordinador de Proyectos",
                    # Personalizado
                    "Otro (Personalizado)"
                ]
                
                estado = st.selectbox("Estado Cargo*", lista_estado )

                cargo_seleccionado = st.selectbox("Cargo *", lista_cargos)
                
                # Si selecciona "Otro", mostrar campo para ingresar cargo personalizado
                if cargo_seleccionado == "Otro (Personalizado)":
                    cargo = st.text_input("Especifique el cargo")
                else:
                    cargo = cargo_seleccionado
            with col2:
                # Lista predefinida de áreas para empresa de servicios
                lista_areas = [
                    "Seleccione...",
                    "Dirección General",
                    "Administración y Finanzas",
                    "Recursos Humanos",
                    "Comercial y Ventas",
                    "Marketing y Comunicaciones",
                    "Atención al Cliente",
                    "Operaciones",
                    "Tecnología de la Información",
                    "Logística y Distribución",
                    "Servicios Profesionales",
                    "Consultoría",
                    "Legal y Compliance",
                    "Calidad",
                    "Investigación y Desarrollo",
                    "Proyectos",
                    "Otro (Personalizado)"
                ]
                
                area_seleccionada = st.selectbox("Área *", lista_areas)
                
                # Si selecciona "Otro", mostrar campo para ingresar área personalizada
                if area_seleccionada == "Otro (Personalizado)":
                    area = st.text_input("Especifique el área")
                else:
                    area = area_seleccionada
            with col3:
                jefe = st.text_input("Jefe Inmediato *")
            
            # Segunda fila: Tipo de contrato, Tiempo y Salario
            col1, col2, col3 = st.columns(3)
            with col1:
                tipo_contrato = st.selectbox("Tipo de Contrato *", 
                                            ["Seleccione...", "Indefinido", "Fijo", "Obra o labor", 
                                             "Aprendizaje", "Prestación de servicios", "Otro"])
            with col2:
                tiempo = st.selectbox("Tiempo *", 
                                     ["Seleccione...", "Completo", "Medio tiempo", "Por horas"])
            with col3:
                # Rangos salariales comunes en empresas de servicios
                rangos_salariales = [
                    "Seleccione...",
                    "Menos de $1.000.000",
                    "$1.000.000 - $1.500.000",
                    "$1.500.001 - $2.000.000",
                    "$2.000.001 - $2.500.000",
                    "$2.500.001 - $3.000.000",
                    "$3.000.001 - $4.000.000",
                    "$4.000.001 - $5.000.000",
                    "$5.000.001 - $6.000.000",
                    "$6.000.001 - $8.000.000",
                    "$8.000.001 - $10.000.000",
                    "$10.000.001 - $15.000.000",
                    "Más de $15.000.000",
                    "A convenir",
                    "Otro (Personalizado)"
                ]
            
                salario_seleccionado = st.selectbox("Salario *", rangos_salariales)
            
                # Si selecciona "Otro", mostrar campo para ingresar salario personalizado
                if salario_seleccionado == "Otro (Personalizado)":
                    salario = st.text_input("Especifique el salario")
                else:
                    salario = salario_seleccionado
            
            # Tercera fila: Campos de texto más grandes
            st.subheader("Requisitos y Detalles")
            
            # Funciones
            funciones = st.text_area("Funciones Principales *", height=100)
            
            # Estudios y Experiencia
            col1, col2 = st.columns(2)
            with col1:
                estudios = st.text_area("Estudios Requeridos *", height=100)
            with col2:
                experiencia = st.text_area("Experiencia Requerida *", height=100)
            
            # Habilidades y Justificación
            col1, col2 = st.columns(2)
            with col1:
                habilidades = st.text_area("Habilidades y Competencias *", height=100)
            with col2:
                justificacion = st.text_area("Justificación de la Vacante *", height=100)
            
            # Botón de envío
            submitted = st.form_submit_button("Guardar Vacante")
            
            if submitted:
                # Validar campos obligatorios
                campos_requeridos = {
                    "estado": estado,
                    "cargo": cargo,
                    "area": area,
                    "funciones": funciones,
                    "estudios": estudios,
                    "experiencia": experiencia,
                    "habilidades": habilidades,
                    "salario": salario,
                    "jefe": jefe,
                    "tipo_contrato": tipo_contrato,
                    "tiempo": tiempo,
                    "justificacion": justificacion
                }
                
                # Verificar si hay campos vacíos o con valores por defecto
                campos_invalidos = []
                for campo, valor in campos_requeridos.items():
                    if campo in ["cargo", "area"] and valor in ["Seleccione...", "Otro (Personalizado)"]:
                        campos_invalidos.append(campo)
                    elif not valor or valor == "Seleccione...":
                        campos_invalidos.append(campo)
                
                if campos_invalidos:
                    st.error(f"Por favor complete todos los campos obligatorios: {', '.join(campos_invalidos)}")
                else:
                    # Guardar datos en Google Sheets
                    exito, mensaje = guardar_vacante(client, campos_requeridos)
                    if exito:
                        st.success(mensaje)
                        # Limpiar formulario o mostrar un mensaje de éxito
                        st.balloons()
                    else:
                        st.error(mensaje)

        # Mostrar información sobre el proceso
        with st.expander("Información sobre el proceso de creación de vacantes"):
            st.write("""
            Este formulario permite registrar nuevas vacantes en la empresa. 
            La información se almacena de forma segura en Google Drive y puede ser consultada 
            por el departamento de Recursos Humanos para iniciar el proceso de selección.
            
            Todos los campos marcados con * son obligatorios.
            """)
    
    with tab2:
        st.subheader("Eliminar Vacante")
        
        # Obtener las vacantes existentes
        exito, datos_vacantes = obtener_vacantes(client)
        
        if not exito:
            st.error(datos_vacantes)
        elif not datos_vacantes:
            st.warning("No hay vacantes registradas en el sistema.")
        else:
            # Crear un DataFrame con las vacantes para mostrarlas
            df_vacantes = pd.DataFrame(datos_vacantes)
            
            # Crear una columna con información relevante para identificar cada vacante
            df_vacantes['identificacion'] = df_vacantes.apply(
                lambda row: f"{row['cargo']} - {row['area']} ({row['fecha']})", axis=1
            )
            
            # Mostrar tabla con las vacantes
            st.write("Vacantes registradas:")
            st.dataframe(
                df_vacantes[['cargo', 'area', 'jefe', 'salario', 'estado', 'fecha']],
                use_container_width=True
            )
            
            # Seleccionar vacante para eliminar
            vacante_seleccionada = st.selectbox(
                "Seleccione la vacante que desea eliminar:",
                options=list(range(len(df_vacantes))),
                format_func=lambda x: df_vacantes['identificacion'].iloc[x]
            )
            
            # Mostrar detalles de la vacante seleccionada
            vacante_a_eliminar = df_vacantes.iloc[vacante_seleccionada]
            
            with st.expander("Ver detalles de la vacante seleccionada"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Cargo:** {vacante_a_eliminar['cargo']}")
                    st.write(f"**Área:** {vacante_a_eliminar['area']}")
                    st.write(f"**Jefe:** {vacante_a_eliminar['jefe']}")
                    st.write(f"**Estado:** {vacante_a_eliminar['estado']}")
                    st.write(f"**Tipo de contrato:** {vacante_a_eliminar['tipo_contrato']}")
                    st.write(f"**Tiempo:** {vacante_a_eliminar['tiempo']}")
                    st.write(f"**Salario:** {vacante_a_eliminar['salario']}")
                with col2:
                    st.write("**Funciones:**")
                    st.write(vacante_a_eliminar['funciones'])
                    st.write("**Estudios requeridos:**")
                    st.write(vacante_a_eliminar['estudios'])
                    st.write("**Experiencia requerida:**")
                    st.write(vacante_a_eliminar['experiencia'])
            
            # Confirmación de eliminación
            if st.button(f"Eliminar vacante: {vacante_a_eliminar['cargo']}"):
                confirmacion = st.checkbox("Confirmo que deseo eliminar esta vacante")
                
                if confirmacion:
                    # Eliminar la vacante
                    exito, mensaje = eliminar_vacante(client, vacante_seleccionada)
                    
                    if exito:
                        st.success(mensaje)
                        # Recargar la página para actualizar la lista de vacantes
                        st.rerun()
                    else:
                        st.error(mensaje)
                else:
                    st.warning("Por favor confirme que desea eliminar la vacante.")
    
    with tab3:
        st.subheader("Generar PDF de Vacantes")
        
        # Obtener las vacantes existentes
        exito, datos_vacantes = obtener_vacantes(client)
        
        if not exito:
            st.error(datos_vacantes)
        elif not datos_vacantes:
            st.warning("No hay vacantes registradas en el sistema.")
        else:
            # Crear un DataFrame con las vacantes para mostrarlas
            df_vacantes = pd.DataFrame(datos_vacantes)
            
            # Crear una columna con información relevante para identificar cada vacante
            df_vacantes['identificacion'] = df_vacantes.apply(
                lambda row: f"{row['cargo']} - {row['area']} ({row['fecha'] if 'fecha' in row else 'Sin fecha'})", axis=1
            )
            
            # Mostrar tabla resumida con las vacantes
            st.write("Vacantes registradas para generar PDF:")
            st.dataframe(
                df_vacantes[['cargo', 'area', 'jefe', 'salario', 'estado', 'fecha'] if 'fecha' in df_vacantes.columns else ['cargo', 'area', 'jefe', 'salario', 'estado']],
                use_container_width=True
            )
            
            # Opciones para generar PDF
            opcion_pdf = st.radio(
                "Seleccione qué tipo de PDF desea generar:",
                ["PDF de vacante individual", "PDF con resumen de todas las vacantes"]
            )
            
            if opcion_pdf == "PDF de vacante individual":
                # Seleccionar vacante para el PDF
                vacante_seleccionada = st.selectbox(
                    "Seleccione la vacante para generar el PDF:",
                    options=list(range(len(df_vacantes))),
                    format_func=lambda x: df_vacantes['identificacion'].iloc[x]
                )
                
                # Mostrar vista previa de la vacante seleccionada
                vacante_para_pdf = df_vacantes.iloc[vacante_seleccionada].to_dict()
                
                with st.expander("Vista previa de la vacante seleccionada"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Cargo:** {vacante_para_pdf['cargo']}")
                        st.write(f"**Área:** {vacante_para_pdf['area']}")
                        st.write(f"**Jefe:** {vacante_para_pdf['jefe']}")
                        st.write(f"**Estado:** {vacante_para_pdf['estado']}")
                        st.write(f"**Tipo de contrato:** {vacante_para_pdf['tipo_contrato']}")
                        st.write(f"**Tiempo:** {vacante_para_pdf['tiempo']}")
                        st.write(f"**Salario:** {vacante_para_pdf['salario']}")
                    with col2:
                        st.write("**Funciones:**")
                        st.write(vacante_para_pdf['funciones'])
                        st.write("**Estudios requeridos:**")
                        st.write(vacante_para_pdf['estudios'])
                        st.write("**Experiencia requerida:**")
                        st.write(vacante_para_pdf['experiencia'])
                
                # Botón para generar PDF de vacante individual
                if st.button("Generar PDF de vacante individual"):
                    with st.spinner("Generando PDF..."):
                        try:
                            # Crear el PDF
                            pdf_buffer = crear_pdf_vacante(vacante_para_pdf)
                            
                            # Generar nombre de archivo
                            nombre_archivo = f"vacante_{vacante_para_pdf['cargo'].replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.pdf"
                            
                            # Crear enlace de descarga
                            st.markdown(get_download_link_pdf(pdf_buffer, nombre_archivo), unsafe_allow_html=True)
                            st.success("PDF generado correctamente. Haga clic en el enlace para descargar.")
                        except Exception as e:
                            st.error(f"Error al generar el PDF: {str(e)}")
            
            else:  # PDF con resumen de todas las vacantes
                # Botón para generar PDF con todas las vacantes
                if st.button("Generar PDF con resumen de todas las vacantes"):
                    with st.spinner("Generando PDF con todas las vacantes..."):
                        try:
                            # Crear el PDF
                            pdf_buffer = crear_pdf_todas_vacantes(datos_vacantes)
                            
                            # Generar nombre de archivo
                            nombre_archivo = f"resumen_vacantes_{datetime.now().strftime('%Y%m%d')}.pdf"
                            
                            # Crear enlace de descarga
                            st.markdown(get_download_link_pdf(pdf_buffer, nombre_archivo), unsafe_allow_html=True)
                            st.success("PDF generado correctamente. Haga clic en el enlace para descargar.")
                        except Exception as e:
                            st.error(f"Error al generar el PDF: {str(e)}")
            
            # Información sobre la generación de PDF
            with st.expander("Información sobre la generación de PDF"):
                st.write("""
                Esta funcionalidad le permite generar documentos PDF de las vacantes registradas en el sistema.
                
                Puede elegir entre dos opciones:
                - **PDF de vacante individual**: Genera un documento detallado de una vacante específica, ideal para compartir con candidatos o para revisión interna.
                - **PDF con resumen de todas las vacantes**: Crea un informe que incluye todas las vacantes activas, útil para presentaciones o reuniones de planificación.
                
                Los PDF generados pueden ser descargados y compartidos con otros miembros del equipo o candidatos.
                """)

#if __name__ == "__main__":
#    vacante()