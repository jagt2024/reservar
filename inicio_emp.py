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

    #text_column, animation_column = st.columns(2)
  
    #url= "https://lottiefiles.com/animations/japan-rocket-lottie-json-animation-R0uHPn4UFa?from=search"
    
        #"https://lottiefiles.com/animations/sparkles-loop-loader-mJIacMF4XW"
        #https://lottiefiles.com/animations/free-download-brochure-DuC22rU6lB
        #https://lottiefiles.com/animations/flowing-1970s-hair-nbyDq6g31z?from=search
       
    #def load_lottie(url):
    #  r = requests.get(url)
    #  r.raise_for_status()
    #  if r.status_code != 200:
    #    return None
    #  return r.json()
  
    #lottie = load_lottie(url) 
  
    #with animation_column:
    #  st_lottie(lottie, height=400)
  
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
