import streamlit as st
from PIL import Image
import requests
from streamlit_lottie import st_lottie
import psutil
import logging
import streamlit.components.v1 as components

def log_resource_usage():
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent
    logging.info(f"CPU: {cpu_percent}%, Memoria: {memory_percent}%")

#st.write(st.session_state["shared"])
   
class InicioEmp:
  
  class Model:
    
   pageTitle = ('***SERVILEVAS***') 
 
  def view(self,model):
    st.title(model.pageTitle)
    st.subheader(' DISTRIBUCION DE PRODUCTOS PARA PANADERIAS')

    #st_custom_icon("https://reservaremp.streamlit.app")
    #st.write("¡Icono clickeado!")
    
    try:
        st.image("./assets-dlv/image1.jpg")
    except Exception as e:
        st.error(f"Error al cargar el video: {str(e)}")

    #image = st.image("assets/CarService.mp4")
    st.write(
        """
          ***Realice sus solicitudes en Linea y Programe sus Pedidos***
        """)
