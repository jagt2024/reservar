import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
import os

class GenerarExcel:
  
  class Model:
    pageTitle ='***Genera archivo de datos de reservas***'
  
  def view(self,model):
    st.title(model.pageTitle)
  
    with st.form(key='myform',clear_on_submit=True):
      
      try:
      
        col1, col2 = st.columns(2)
        datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas.xlsx")
  
        generar = st.form_submit_button(" Generar ")
  
        if generar:
        
          df = pd.read_excel(datos)
  
          with st.spinner('Cargando...'): 
            try: 
                os.chdir("archivos")
                for x in df["SERVICIOS"].unique(): 
                  df_temp = df[df["SERVICIOS"] == x ]
                  df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
          
                  #data = os.listdir()
                  #for x in data:
                  #print(data)
                os.chdir("..")
                st.success('Archivos generados exitosamente')
                st.balloons()
                
            except HttpError as err:
              raise Exception(f'A ocurrido un error en generaExcel: {err}')
              #st.warning(f'se presento un  Errror {err} ')
      
      except HttpError as err:
           st.warning(f' Error No se encontro la ruta y el archivo fuente {err} ')
           raise Exception(f'A ocurrido un error en generaExcel: {err}')
