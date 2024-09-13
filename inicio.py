import streamlit as st
from PIL import Image
import requests
from streamlit_lottie import st_lottie
import time
import os

def image_carousel(image_directory, width=None, height=None, position="center"):

      """
      Carga y presenta diferentes imágenes de forma consecutiva con un intervalo de 4 segundos.

      Parameters:
      image_directory (str): La ruta del directorio que contiene las imágenes a mostrar.
      width (int): Ancho deseado para las imágenes (opcional).
      height (int): Altura deseada para las imágenes (opcional).
      position (str): Posición de la imagen en la pantalla ("left", "center", "right").
      """
    
      image_files = [f for f in os.listdir(image_directory) if f.endswith((".png", ".jpg", ".jpeg", ".gif"))]
    
      # Verificar si hay al menos una imagen
      if not image_files:
        st.warning("No se encontraron imágenes en el directorio especificado.")
        return None
    
      # Mostrar las imágenes una a una, reemplazando la imagen anterior
      image_files = image_files[:4]
      
      # Configurar el layout según la posición
      if position == "left":
        _, col, _ = st.columns([1, 2, 1])
      elif position == "right":
        _, _, col = st.columns([1, 1, 2])
      else:  # center
        _, col, _ = st.columns([1, 3, 1])
    
      image_placeholder = col.empty()
      for image_file in image_files:
        image_path = os.path.join(image_directory, image_file)
        image = Image.open(image_path)
        
        if width and height:
            image = image.resize((width, height))
        elif width:
            wpercent = (width / float(image.size[0]))
            hsize = int((float(image.size[1]) * float(wpercent)))
            image = image.resize((width, hsize))
        elif height:
            hpercent = (height / float(image.size[1]))
            wsize = int((float(image.size[0]) * float(hpercent)))
            image = image.resize((wsize, height))
        
        image_placeholder.image(image, use_column_width=True)
        time.sleep(3)
        image_placeholder.empty()
   
class Inicio:
  
  class Model:
    
    pageTitle =('***AGENDA PERSONAL***')
    
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
    
        # Configuración de la presentación de imágenes
        #width = st.sidebar.slider("Ancho de la imagen", 100, 800, 600)
        #height = st.sidebar.slider("Altura de la imagen", 100, 600, 500)
        #position = st.sidebar.radio("Posición de la imagen", ["left", "center", "right"])
        
        image_carousel('./album_personal', 700, 600, 'center')
        
        st.title(model.pageTitle)
        st.write('***Programe su Agenda Ahora (Diariamente, Semanalmente o por más tiempo)***')
        
        # Imagen final
        final_image = Image.open("./album_personal/pexels-moments.jpg")
        final_width = 650  #st.sidebar.slider("Ancho de la imagen final", 100, 800, 600)
        final_image = final_image.resize((final_width, int(final_width * final_image.size[1] / final_image.size[0])))
        st.image(final_image)
