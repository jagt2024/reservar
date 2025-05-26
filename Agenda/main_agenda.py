import streamlit as st
from streamlit_option_menu import option_menu
from inicio_agenda import InicioAgenda
from email_sender import mostrar_correo_masivo
from agenda import agenda_main
from carga_resumen_cv import carga_cv
from consulta_resume import consulta_cv
from crear_vacantes import vacante
from cv_candidatos import candidatos
from consulta_candidatos import consulta_candidato
from inscripcion import inscripcion_main
from user_management import user_management_system
from PIL import Image
from datetime import date
import datetime
import time
import pytz
import toml
import logging
import sys

# Configurar la página y ocultar la opción "Manage app" del menú
st.set_page_config(
    page_title="Personal Information Form",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Ocultar elementos de la interfaz de Streamlit usando CSS personalizado
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            .css-1rs6os {visibility: hidden;}
            .css-14xtw13 {visibility: hidden;}
            .css-1avcm0n {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, filename='main_agenda.log', filemode='w', 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# Cargar configuraciones desde config.toml
with open("./.streamlit/config.toml", "r") as f:
    config = toml.load(f)

sys.excepthook = global_exception_handler

logo = Image.open("./assets-agenda/logoJAGT.ico") 

# Diccionario de traducciones
translations = {
    "en": {
        "language_selector": "🌐 Language / Idioma",
        "app_title": "Personal Information Form",
        "option0": "Home",
        "option1": "Schedule",
        "option3": "Upload Resume",
        "option4": "Consult Resume",
        "option2": "Send Emails",
        "option5": "Create Vacancy",
        "option6": "Create and Manage Candidates",
        "option7": "Consult Candidates",
        "version": "Version: 0.0.1",
        "year": "Year: 2025",
        "error_message": "An error occurred: {}",
        "system_error": "A system error occurred: {}"
    },
    "es": {
        "language_selector": "🌐 Language / Idioma",
        "app_title": "Formulario de Información Personal",
        "option0": "Inicio",
        "option1": "Agenda",
        "option3": "Cargar Curriculum",
        "option4": "Consultar Curriculum",
        "option2": "Enviar Correos",
        "option5": "Crear Vacante",
        "option6": "Crear y Gestionar Candidatos",
        "option7": "Consulta Candidatos",
        "version": "Versión: 0.0.1",
        "year": "Año: 2025",
        "error_message": "Ocurrió un error: {}",
        "system_error": "Ha ocurrido un error en main_emp.py: {}"
    }
}

# Inicializar el estado de sesión si no existe
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'InicioAgenda'
    
if 'language' not in st.session_state:
    st.session_state.language = 'en'

class Model:
    
    def __init__(self, language="en"):
        self.language = language
        self.update_translations()
        
    def update_translations(self):
        lang = translations[self.language]
        self.menuTitle = lang["app_title"]
        self.option0 = lang["option0"]
        self.option1 = lang["option1"]
        self.option3 = lang["option3"]
        self.option4 = lang["option4"]
        self.option2 = lang["option2"]
        self.option5 = lang["option5"]
        self.option6 = lang["option6"]
        self.option7 = lang["option7"]

# Función para cambiar entre páginas
def cambiar_pagina(page_name):
    st.session_state.current_page = page_name
    # No es necesario llamar a st.rerun() aquí porque se ejecutará automáticamente

def view(model):
    try:
        def update_clock_and_calendar():
            while True:
                        now = datetime.datetime.now(pytz.timezone('America/Bogota'))
                        clock_placeholder.markdown(f'<p class="clock">Hora: {now.strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)

                        today = date.today()
                        meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                        mes_es = meses_es[today.month - 1]
                        dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                        dia_es = dias_es[today.weekday()]
        
                        calendar_placeholder.markdown(f'<p class="calendar">Día: {dia_es.capitalize()} {today.day} de {mes_es} de {today.year}<br></p>', unsafe_allow_html=True)
        
                        time.sleep(1)

        # SIDEBAR PRINCIPAL - Solo se muestra cuando estamos en la página principal
        if st.session_state.current_page in ['InicioAgenda', None]:
            with st.sidebar:
                # Selector de idioma en la parte superior del sidebar
                languages = {"English": "en", "Español": "es"}
                selected_language_name = st.selectbox(
                    translations[model.language]["language_selector"],
                    options=list(languages.keys())
                )
                selected_language = languages[selected_language_name]
                
                # Actualizar idioma si cambia
                if selected_language != model.language:
                  model.language = selected_language
                  st.session_state.language = selected_language
                  model.update_translations()

              
            
                # Menú principal
                app = option_menu(model.menuTitle,
                            [model.option0, model.option1, model.option3, model.option4, 
                            model.option2, model.option5, model.option6, model.option7],
                            icons=['house', 'calendar2-date', 'cloud-upload', 'search',
                                  'envelope', 'briefcase', 'person-plus', 'people'],
                            default_index=0,
                            styles= {
                               "container":{ "padding": "5!important",
                               "background-color":'#acbee9'},
                               "icon":{"color":"white","font-size":"23px"},
                               "nav-link":{"color":"white","font-size":"20px","text-align":"left", "margin":"0px"},
                               "nav-link-selected":{"background-color":"#02ab21"},
                            })

            st.header('Empresa de Servicios - Inscripcion, Agenda y Seleccion')

            st.markdown(f"""
            <style>
                    @import url('https://fonts.googleapis.com/css2?family={config['fonts']['clock_font']}:wght@400;500&display=swap');
                    .clock {{
                    font-family: '{config['fonts']['clock_font']}', sans-serif;
                    font-size: {config['font_sizes']['clock_font_size']};
                    color: {config['colors']['clock_color']};
                    text-shadow: 0 0 10px rgba(255,255,0,0.7);
                    margin-top: {config['layout']['top_margin']};
                    margin-bottom: {config['layout']['bottom_margin']};
                    }}
                    .calendar {{
                    font-family: '{config['fonts']['calendar_font']}', sans-serif;
                    font-size: {config['font_sizes']['calendar_font_size']};
                    color: {config['colors']['calendar_color']};
                    margin-top: {config['layout']['top_margin']};
                    margin-bottom: {config['layout']['bottom_margin']};
                    }}
            </style>
            """, unsafe_allow_html=True)

            # Crear los tabs con los estilos personalizados

            # Crear columnas para el diseño
            col1, col2, col3, col4 = st.columns(4)

            # Columna 1: Reloj Digital
            with col1:
                #st.header("Reloj Digital")
                clock_placeholder = st.empty()
                             
            with col2:
                st.image(logo, width=250)  # Ajusta el ancho según sea necesario
        
            # Columna 2: Calendario
            with col3:
                #st.header("Calendario")
                #calendar_placeholder = st.empty()
                pass
            with col4:
                calendar_placeholder = st.empty()
                with st.form(key='myform4',clear_on_submit=True):
                    limpiar = st.form_submit_button("Limpiar Pantalla")
                    if limpiar:
                        #st.submit_button("Limpiar Opcion")
                        clear_session_state()
                        st.rerun()

                           
            tabs = st.tabs(["Inicio", "Inscripcion", "En construccion","En construccion", "Catalogo Productos", "Soporte - PQRS"
            #, "Registrar Pago", "Soporte - PQRS"])
            ])
            
            #with tabs[0]:
            #  InicioEmp()
            #InicioEmp().view(InicioEmp.Model())
              
            with tabs[1]:
               inscripcion_main()
    
            with tabs[2]:
                pass
    
            with tabs[3]:
                pass
        
            with tabs[4]:
                pass
        
            with tabs[5]:
                pass

            # Actualizar la página según la selección del menú
            if app == model.option0:
                st.session_state.current_page = 'InicioAgenda'
            elif app == model.option1:
                st.session_state.current_page = 'agenda_main'
            elif app == model.option3:
                st.session_state.current_page = 'carga_cv'
            elif app == model.option4:
                st.session_state.current_page = 'consulta_cv'
            elif app == model.option2:
                st.session_state.current_page = 'mostrar_correo_masivo'
            elif app == model.option5:
                st.session_state.current_page = 'vacante'
            elif app == model.option6:
                st.session_state.current_page = 'candidatos'
            elif app == model.option7:
                st.session_state.current_page = 'consulta_candidato'

        #with st.sidebar:
        #    st.markdown("---")
        #    st.text(translations[model.language]["version"])
        #    st.text(translations[model.language]["year"])
        #    st.markdown("---")

        # SIDEBARS ESPECÍFICOS PARA CADA PÁGINA
        # Se mostrará un sidebar específico según la página actual
        if user_management_system():

          current_page = st.session_state.current_page
        


          # Renderizar la página actual según session_state
          if current_page == 'InicioAgenda':
             InicioAgenda()

        
          elif current_page == 'agenda_main':
            # Sidebar específico para agenda
            with st.sidebar:
                st.header("Menú de Agenda")
                st.button("Volver al Inicio", key="btn_back_agenda", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Aquí puedes agregar controles específicos para la agenda
                st.divider()
                #st.subheader("Opciones de Agenda")
                #st.date_input("Fecha de búsqueda", key="agenda_date")
                #st.checkbox("Mostrar solo citas confirmadas", key="show_confirmed")
            
            # Mostrar el contenido de la agenda
            if current_page == 'agenda_main':
                agenda_main()
            else:
                st.button("Volver al Inicio", key="btn_back_agenda", on_click=cambiar_pagina, args=('InicioAgenda',))
            
        
          elif current_page == 'carga_cv':
            # Sidebar específico para carga de CV
            with st.sidebar:
                st.header("Cargar Curriculum")
                st.button("Volver al Inicio", key="btn_back_cv", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para carga de CV
                
                st.divider()
                #st.subheader("Opciones de Carga")
                #st.selectbox("Formato preferido", ["PDF", "DOCX", "TXT"], key="cv_format")
            
            # Mostrar el contenido de carga CV
            if current_page == 'carga_cv':
                carga_cv()
            else:
                st.button("Volver al Inicio", key="btn_back_cv", on_click=cambiar_pagina, args=('InicioAgenda',))
            
        
          elif current_page == 'consulta_cv':
            # Sidebar específico para consulta de CV
            with st.sidebar:
                st.header("Consulta de CV")
                st.button("Volver al Inicio", key="btn_back_consulta", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para consulta
                st.divider()
                #st.subheader("Filtros de Búsqueda")
                #st.text_input("Buscar por nombre", key="search_name")
                #st.selectbox("Ordenar por", ["Fecha", "Nombre", "Relevancia"], key="sort_by")
            
            # Mostrar el contenido de consulta CV
            if current_page == 'consulta_cv':
                 consulta_cv()
            else:
                st.button("Volver al Inicio", key="btn_back_consulta", on_click=cambiar_pagina, args=('InicioAgenda',))
            
        
          elif current_page == 'mostrar_correo_masivo':
            # Sidebar específico para emails
            with st.sidebar:
                st.header("Envío de Correos")
                st.button("Volver al Inicio", key="btn_back_email", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para emails
                st.divider()
                #st.subheader("Opciones de Envío")
                #st.checkbox("Incluir adjuntos", key="include_attachments")
                #st.checkbox("Correo prioritario", key="priority_email")
            
            # Mostrar el contenido de correo masivo
            if current_page == 'mostrar_correo_masivo':
                 mostrar_correo_masivo()
            else:
                st.button("Volver al Inicio", key="btn_back_email", on_click=cambiar_pagina, args=('InicioAgenda',))
           
        
          elif current_page == 'vacante':
            # Sidebar específico para vacantes
            with st.sidebar:
                st.header("Gestión de Vacantes")
                st.button("Volver al Inicio", key="btn_back_vacante", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para vacantes
                st.divider()
                #st.subheader("Opciones de Vacante")
                #st.selectbox("Departamento", ["Dirección General",
                #"Administración y Finanzas",
                #"Recursos Humanos",
                #"Comercial y Ventas",
                #"Marketing y Comunicaciones",
                #"Atención al Cliente",
                #"Operaciones",
                #"Tecnología de la Información",
                #"Logística y Distribución",
                #"Servicios Profesionales",
                #"Consultoría",
                #"Legal y Compliance",
                #"Calidad",
                #"Investigación y Desarrollo",
                #"Proyectos",
                #"Otro (Personalizado)"], key="depto_vacante")
            
            # Mostrar el contenido de vacantes
            if current_page == 'vacante':
                vacante()
            else:
                st.button("Volver al Inicio", key="btn_back_vacante", on_click=cambiar_pagina, args=('InicioAgenda',))
       
          elif current_page == 'candidatos':
            # Sidebar específico para candidatos
            with st.sidebar:
                st.header("Gestión de Candidatos")
                st.button("Volver al Inicio", key="btn_back_candidatos", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para candidatos
                st.divider()
                #st.subheader("Opciones de Candidatos")
                #st.selectbox("Estado", ["Todos", "En proceso", "Finalistas", "Contratados", "Rechazados"], key="estado_candidato")
            
            # Mostrar el contenido de candidatos
            if current_page == 'candidatos':
                candidatos()
            else:
                st.button("Volver al Inicio", key="btn_back_candidatos", on_click=cambiar_pagina, args=('InicioAgenda',))
        
          elif current_page == 'consulta_candidato':
            # Sidebar específico para consulta de candidatos
            with st.sidebar:
                st.header("Consulta de Candidatos")
                st.button("Volver al Inicio", key="btn_back_consulta_cand", on_click=cambiar_pagina, args=('InicioAgenda',))
                
                # Opciones específicas para consulta de candidatos
                st.divider()
                #st.subheader("Filtros de Candidatos")
                #st.multiselect("Habilidades", ["Python", "Java", "SQL", "Marketing", "Ventas"], key="skills_filter")
            
            if current_page == 'consulta_candidato':
                consulta_candidato()
            else:
                st.button("Volver al Inicio", key="btn_back_consulta_cand", on_click=cambiar_pagina, args=('InicioAgenda',))
        
          with st.sidebar:
            st.markdown("---")
            st.text(translations[model.language]["version"])
            st.text(translations[model.language]["year"])
            st.markdown("---")

          #update_clock_and_calendar()
        
    except Exception as e:
        error_msg = translations[model.language]["error_message"].format(e)
        st.error(error_msg)
        logging.error(f"Error en la vista: {e}", exc_info=True)

# Inicializar modelo con el idioma almacenado en session_state o el valor predeterminado
model = Model(language=st.session_state.language)
view(model)

# No es necesario incluir el footer aquí ya que está oculto con CSS
