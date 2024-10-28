import streamlit as st
from PIL import Image
import requests
from streamlit_lottie import st_lottie
import psutil
import logging
import streamlit.components.v1 as components

def st_custom_icon(url, key=None):
    component_value = components.declare_component(
        "custom_icon",
        path="frontend"  # Directorio donde estará tu componente React
    )
    return component_value(url=url, key=key, default=None)


def log_resource_usage():
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent
    logging.info(f"CPU: {cpu_percent}%, Memoria: {memory_percent}%")

#st.write(st.session_state["shared"])
   
class InicioEmp:
  
  class Model:
    
   pageTitle = ('***DISTRITO PRIVADO***') 
 
  def view(self,model):
    st.title(model.pageTitle)
    st.subheader(' ASOCIACION USUARIOS-CONDUCTORES')

    #st_custom_icon("https://reservaremp.streamlit.app")
    #st.write("¡Icono clickeado!")
    
    try:
        st.video("assets/CarService.mp4")
    except Exception as e:
        st.error(f"Error al cargar el video: {str(e)}")

    #image = st.image("assets/CarService.mp4")
    st.write(
        """
          ***Genere sus Reservas en Linea y Programe su Agenda***
          Direcion:            
          Ciudad:              
          Celular:             
          Email:            
        """)
