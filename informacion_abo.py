import streamlit as st

class Informacion:
  
  class Model:
    pageTitle = "***Informacion***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    st.subheader('Ubicacion')
     
    st.markdown('''<iframe src="https://www.google.com/maps/embed?pb=!1m10!1m8!1m3!1d31828.22712981875!2d-74.7930811!3d4.3113089!3m2!1i1024!2i768!4f13.1!5e0!3m2!1ses!2sco!4v1715792084638!5m2!1ses!2sco" width="600" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>''',unsafe_allow_html=True)

    with st.container():
        st.write("---")
        
        st.subheader('Horarios')
        dia, hora = st.columns(2)
       
        dia.text('Lunes')
        hora.text('10:00 am - 08:00 pm')
        dia.text('Martes')
        hora.text('10:00 am - 08:00 pm')
        dia.text('Miercoles')
        hora.text('10:00 am - 08:00 pm')
        dia.text('Jueves')
        hora.text('10:00 am - 08:00 pm')
        dia.text('Viernes')
        hora.text('10:00 am - 08:00 pm')
        dia.text('Sabado')
        hora.text('10:00 am - 06:00 pm')
  
    st.write("---")
    st.subheader('Contacto')
    st.image('assets/telephone-fill.svg')
    st.text('Cel. 320551091')
  
    st.write("---")
    st.subheader('Instagram')
    st.markdown('siguenos [aqui](https://www.instagram.com) en instagram')