import streamlit as st
from streamlit_option_menu import option_menu
from inicio_agenda import InicioAgenda
from agenda import agenda_main
import logging
import sys

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

logging.basicConfig(level=logging.DEBUG, filename='main_agenda.log', filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

page_title = 'Personal Information Form' 
page_icon= "./assets-agenda/logoJAGT.ico" 
title="Schedule"
layout = 'centered'

st.set_page_config(page_title=page_title, page_icon=page_icon,layout=layout)

class Model:
  
  menuTitle = "Personal Information Form"
  option1 = 'Schedule'

  def add_app(self,title, function):
      self.apps.append({
         "title":title,
         "function":function
       })

def view(model):
      try:
  
        with st.sidebar:
    
          app = option_menu(model.menuTitle,
                         [model.option1],
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


