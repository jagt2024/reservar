import streamlit as st
from PIL import Image

class Servicios:
  
  class Model:
    pageTitle = "***Servicios***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    st.subheader("""Nuestra Mision : Tiene por objetivo dar respuestas integrales, eficaces y eficientes a las diversas necesidades de los clientes. Estamos en una constante búsqueda de la excelencia, nuestros abogados ejercen la profesión apegados al derecho, la justicia y la ética.""")    
    image_column, text_column = st.columns((1,1))

    with image_column:
      image = Image.open('assets/actividad-abogado.webp')
      st.image(image, use_column_width=True)

    with text_column:
      st.write(""" 
               
      - Derecho Civil, Mercantil y Corporativo : La firma presta asesoramiento en todas las áreas del día a día de una compañía, incluyendo negociaciones de todo tipo de contratos y su elaboración, la constitución de sociedades y elaboración de los documentos corporativos requeridos.
            
      - Derecho Laboral : La firma se especializa en todas las áreas relativas al derecho del trabajo, asesorando a sus clientes de manera efectiva y práctica en la aplicación de la normativa laboral, así como en negociación individual y colectiva, conflictos individuales y colectivos, su prevención y su resolución de ser el caso en la administración del trabajo y los tribunales laborales ante los cuales se tiene amplia experiencia y en todas sus instancias conforme la Ley Orgánica Procesal del Trabajo, bien sea en la fase de mediación y/o juicio de llegarse a ese última etapa y ante la Sala de Casación Social del Tribunal Supremo de Justicia, en ocasión de recursos de casación ante la misma y habiendo participado en casos que han tenido relevancia en el ámbito judicial."
      
      - Seguridad Social : La firma se especializa en las áreas relativas al derecho de la seguridad social, habiendo participado activamente en comisiones técnicas de formulación de la Ley marco del sistema de seguridad social y de los proyectos y leyes de los regímenes prestacionales de la seguridad social como las de pensiones y seguridad y salud laboral.
      """)
    
    with image_column:
      image = Image.open('assets/pexels-5.jpg')
      st.image(image, use_column_width=True)
    
    with image_column:
      image = Image.open('assets/imagen-abogado2.jpeg')
      st.image(image, use_column_width=True)
      
    with image_column:
      image = Image.open('assets/imagen-abogado3.jpeg')
      st.image(image, use_column_width=True)
    