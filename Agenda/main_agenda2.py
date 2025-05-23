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
import logging
import sys

# Configurar la página y ocultar la opción "Manage app" del menú
st.set_page_config(
    page_title="Personal Information Form",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,  #'https://www.ejemplo.com/ayuda',
        'Report a bug': None,  #'https://www.ejemplo.com/reportar-bug',
        'About': None  #'# Esta es mi increíble aplicación Streamlit!'
        # La opción 'Manage app' no está incluida, por lo que no aparecerá
    }
)

# Ocultar elementos de la interfaz de Streamlit usando CSS personalizado
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}  /* Oculta el menú hamburguesa */
            footer {visibility: hidden;}  /* Oculta el footer "Made with Streamlit" */
            header {visibility: hidden;}  /* Oculta la cabecera */
            .stDeployButton {display:none;}  /* Oculta el botón de deploy */
            .css-1rs6os {visibility: hidden;}  /* Oculta el menú de configuración */
            .css-14xtw13 {visibility: hidden;}  /* Para algunas versiones de Streamlit */
            .css-1avcm0n {visibility: hidden;}  /* Para algunas versiones de Streamlit (menú hamburguesa) */
            
            /* En algunas versiones más recientes se usan diferentes clases CSS */
            /* Puedes identificar las clases específicas usando inspeccionar elemento en tu navegador */
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='main_agenda.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

title="Schedule"
layout = 'centered'

# Diccionario de traducciones
translations = {
    "en": {
        "language_selector": "🌐 Language / Idioma",
        "app_title": "Personal Information Form",
        "option0": "Inicio",
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
        
        
    def add_app(self, title, function):
        self.apps.append({
            "title": title,
            "function": function
        })

def view(model):
    try:
        # Language selector at the top of the sidebar
        with st.sidebar:
            languages = {"English": "en", "Español": "es"}
            selected_language_name = st.selectbox(
                translations[model.language]["language_selector"],
                options=list(languages.keys())
            )
            selected_language = languages[selected_language_name]
            
            # Update language if changed
            if selected_language != model.language:
                model.language = selected_language
                model.update_translations()
                #st.rerun()
        
        # Main sidebar menu
        with st.sidebar:
            app = option_menu(model.menuTitle,
                         [model.option0(key="btn_back_home", on_click=cambiar_pagina, args=('InicioAgenda',)),
                          model.option1(key="btn_back_home1", on_click=cambiar_pagina, args=('agenda_main',)),
                          model.option3, 
                          model.option4, 
                          model.option2, 
                          model.option5(key="btn_back_home5", on_click=cambiar_pagina, args=('vacante',)), 
                          model.option6(key="btn_back_home6", on_click=cambiar_pagina, args=('candidatos',)),
                          model.option7(key="btn_back_home7", on_click=cambiar_pagina, args=('consulta_candidato',))
                          ],
                          icons=['bi bi-calendar2-date'
                         ],
                         default_index=0,
                         styles= {
                           "container":{ "schedule": "5!important",
                           "background-color":'#acbee9'},
                           "icon":{"color":"white","font-size":"23px"},
                           "nav-lik":{"color":"white","font-size":"20px","text-aling":"left", "margin":"0px"},
                           "nav-lik-selected":{"backgroud-color":"#02ab21"},})

        with st.sidebar:
            st.markdown("---")
            st.text(translations[model.language]["version"])
            st.text(translations[model.language]["year"])
            st.markdown("---")
    
        # Store the language in session state to access it from other modules
        if "language" not in st.session_state:
            st.session_state.language = model.language
        else:
            st.session_state.language = model.language

        # Navigate to the selected page
        if app == model.option0:
            InicioAgenda()

        if app == model.option1:
            agenda_main()
        
        elif app == model.option3:
            carga_cv()

        elif app == model.option4:
            consulta_cv() 

        elif app == model.option2:
            mostrar_correo_masivo()

        elif app == model.option5:
            vacante()

        elif app == model.option6:
            candidatos()

        elif app == model.option7:
            consulta_candidato()        

    except Exception as e:
        error_msg = translations[model.language]["error_message"].format(e)
        st.error(error_msg)
                                      
    except SystemError as err:
        error_msg = translations[model.language]["system_error"].format(err)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = translations[model.language]["error_message"].format(e)
        st.error(error_msg)

sys.excepthook = global_exception_handler

# Función para cambiar entre páginas
def cambiar_pagina(page_name):
    # Actualizar la página actual en session_state
    st.session_state.page = page_name
    # Nota: Streamlit re-ejecutará todo el script, lo que creará un nuevo sidebar

# Initialize model with default language (English)
model = Model(language="en")
view(model)

# Footer
#st.markdown("---")
#st.markdown("© 2025 Clínica de Psicología del Amor- Sistema de Gestión de Historias Clínicas")


