import streamlit as st
import pandas as pd
import gspread
import json
import toml
import time
from google.oauth2.service_account import Credentials
from datetime import datetime

# Constantes
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2

# Configuración de la página
#st.set_page_config(page_title="Gestión de Vacantes", layout="wide")
#st.title("Sistema de Gestión de Vacantes")

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
                    encabezados = ["fecha_registro", "cargo", "area", "funciones", "estudios", 
                                  "experiencia", "habilidades", "salario", "jefe", 
                                  "tipo_contrato", "tiempo", "justificacion"]
                    worksheet.append_row(encabezados)
                
                # Añadir la nueva fila con los datos de la vacante
                nueva_fila = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                    datos_vacante["justificacion"]
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

def vacante():
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
    
    # Crear formulario para ingresar datos de la vacante
    with st.form("formulario_vacante"):
        st.subheader("Información de la Vacante")
        
        # Primera fila: Cargo, Área y Jefe
        col1, col2, col3 = st.columns(3)
        with col1:
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
                "Especialista en Marketing Digital", "Community Manager", "Diseñador Gráfico",
                "Especialista en SEO/SEM", "Analista de Marketing", "Coordinador de Eventos",
                "Gestor de Contenidos", "Especialista en Comunicaciones", "Analista de Mercado",
                # Área de Logística y Operaciones
                "Coordinador de Operaciones", "Supervisor de Operaciones", "Analista de Logística",
                "Jefe de Bodega", "Coordinador de Distribución", "Inspector de Calidad", "Despachador",
                # Área de Servicios Profesionales
                "Consultor Senior", "Consultor Junior", "Analista de Procesos", "Asesor Legal",
                "Especialista en Compliance", "Especialista en Servicios", "Coordinador de Proyectos",
                # Personalizado
                "Otro (Personalizado)"
            ]
            
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

if __name__ == "__main__":
    vacante()
