import streamlit as st
from PIL import Image

class Servicios:
  
  class Model:
    pageTitle = "***Servicios***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    image_column, image_column2 = st.columns((1,1))

    with image_column:
      image = Image.open('assets/pexels-1.jpg')
      st.image(image, use_column_width=True)
    
    with image_column2:
      image = Image.open('assets/pexels-2.jpg')
      st.image(image, use_column_width=True)
   
    with image_column:
      image = Image.open('assets/pexels-3.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-4.jpg')
      st.image(image, use_column_width=True)
   
    with image_column:
      image = Image.open('assets/pexels-5.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-6.jpg')
      st.image(image, use_column_width=True)

    with image_column:
      image = Image.open('assets/pexels-7.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-8.jpg')
      st.image(image, use_column_width=True)

    with image_column:
      image = Image.open('assets/pexels-9.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-10.jpg')
      st.image(image, use_column_width=True)
import streamlit as st
from PIL import Image

class Servicios:
  
  class Model:
    pageTitle = "***Servicios***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    image_column, image_column2 = st.columns((1,1))

    with image_column:
      image = Image.open('assets/pexels-1.jpg')
      st.image(image, use_column_width=True)
    
    with image_column2:
      image = Image.open('assets/pexels-2.jpg')
      st.image(image, use_column_width=True)
   
    with image_column:
      image = Image.open('assets/pexels-3.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-4.jpg')
      st.image(image, use_column_width=True)
   
    with image_column:
      image = Image.open('assets/pexels-5.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-6.jpg')
      st.image(image, use_column_width=True)

    with image_column:
      image = Image.open('assets/pexels-7.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-8.jpg')
      st.image(image, use_column_width=True)

    with image_column:
      image = Image.open('assets/pexels-9.jpg')
      st.image(image, use_column_width=True)   
          
    with image_column2:  
      image = Image.open('assets/pexels-10.jpg')
      st.image(image, use_column_width=True)
