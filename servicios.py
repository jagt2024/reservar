import streamlit as st
from PIL import Image

class Servicios:
  
  class Model:
    pageTitle = "***Servicios***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    image_column, text_column = st.columns((2,1))

    with image_column:
      image = Image.open('assets/corte-hombre1.jpg')
      st.image(image, use_column_width=True)
    with text_column:
      st.subheader(""" 
                   Servicio de Corte Caballero
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                   
                   """)

    with image_column:
      image = Image.open('assets/cabello-dama1.jpg')
      st.image(image, use_column_width=True)
    with text_column:
      st.subheader(""" 
                   Servicio de Corte y Peinado Damas
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                         
                   """)

    with image_column:
      image = Image.open('assets/corte-barba.jpg')
      st.image(image, use_column_width=True)   
    with text_column:
      st.subheader(""" 
                   Servicio de Corte Barba           
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                   -      

                   """)
       
    with image_column:  
      image = Image.open('assets/afeitar1.jpg')
      st.image(image, use_column_width=True)
    with text_column:
      st.subheader(""" 
                   Servicio de Afeitar Caballero           
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                   -
                   """)
  