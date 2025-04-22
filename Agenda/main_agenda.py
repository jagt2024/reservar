import streamlit as st
from streamlit_option_menu import option_menu
from inicio_agenda import InicioAgenda
from email_sender import mostrar_correo_masivo
from agenda import agenda_main
import logging
import sys

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

# Configuración de la página sin ícono de GitHub ni otras opciones
#st.set_page_config(
#    page_title="Mi Aplicación",
#    page_icon="🧊",
#    layout="wide",
#    initial_sidebar_state="expanded",
#    menu_items={
#        "Get Help": None,
#        "Report a bug": None,
#        "About": None
#    }
#)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='main_agenda.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

page_title = 'Personal Information Form' 
page_icon= "./assets-agenda/logoJAGT.ico" 
title="Schedule"
layout = 'centered'

#st.set_page_config(page_title=page_title, page_icon=page_icon,layout=layout)

class Model:
  
  menuTitle = "Personal Information Form"
  option1 = 'Schedule'
  option2 = "Sender Emails"

  def add_app(self,title, function):
      self.apps.append({
         "title":title,
         "function":function
       })

def view(model):
      try:
  
        with st.sidebar:
    
          app = option_menu(model.menuTitle,
                         [model.option1, model.option2],
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
          st.text("Version: 0.0.1")
          st.text("Ano: 2025")
          #st.text("Autor: JAGT")
          st.markdown("---")
    
          #if sw_empresa == ['VERDADERO'] or sw_empresa == ['True']:
          #  try:
                   
          #    clave_correcta = cargar_configuracion()
          #    if clave_correcta is None:
          #      st.error("No se pudo cargar la configuración. La opción protegida no estará disponible.")
          #      return 
      
        if app == model.option1:
           agenda_main()
        if app == model.option2:
          mostrar_correo_masivo()

      except Exception as e:
            st.error(f"Ocurrió un error: {e}")
                                      
      except SystemError as err:
        raise Exception(f'A ocurrido un error en main_emp.py: {err}')
      except Exception as e:
        st.error(f"Ocurrió un error en main_emp.py: {e}")
        
      #update_clock_and_calendar()
     
sys.excepthook = global_exception_handler

view(Model())

# Footer
#st.markdown("---")
#st.markdown("© 2025 Clínica de Psicología del Amor- Sistema de Gestión de Historias Clínicas")


