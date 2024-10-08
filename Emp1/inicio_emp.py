import streamlit as st
from PIL import Image
import requests
from streamlit_lottie import st_lottie
import psutil
import logging

def log_resource_usage():
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent
    logging.info(f"CPU: {cpu_percent}%, Memoria: {memory_percent}%")

#st.write(st.session_state["shared"])
   
class InicioEmp:
  
  class Model:
    
    pageTitle = ('***BARBERIA STYLOS***')
 
  def view(self,model):
    st.title(model.pageTitle)
    image = st.image("assets/barberia1.webp")
    st.write(
        """
          ***Genere sus Reservas en Linea y Programe su Agenda***
          Direcion:            
          Ciudad:              
          Celular:             
          Email:            
        """)
