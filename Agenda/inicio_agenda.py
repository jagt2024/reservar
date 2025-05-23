import streamlit as st
from PIL import Image
import requests
from streamlit_lottie import st_lottie
import psutil
import logging
import streamlit.components.v1 as components

st.cache_data.clear()
st.cache_resource.clear()

def log_resource_usage():
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent
    logging.info(f"CPU: {cpu_percent}%, Memoria: {memory_percent}%")

#st.write(st.session_state["shared"])
   
class InicioAgenda:
  
  class Model:
    
   pageTitle = ('***Schedule Personal Information App***') 
 
  def view(self,model):
    st.title(model.pageTitle)
    st.subheader(' Work Orders')

    #st_custom_icon("https://reservaremp.streamlit.app")
    #st.write("¡Icono clickeado!")
    
    try:
        st.image("./assets-agenda/logoJAGT.ico")
    except Exception as e:
        st.error(f"Error al cargar el logo: {str(e)}")

    #image = st.image("assets/CarService.mp4")
    st.write(
        """
          ***Online Scheduling***
        """)
# Footer
#st.markdown("---")
#st.markdown("© 2025 Clínica de Psicología del Amor- Sistema de Gestión de Historias Clínicas")