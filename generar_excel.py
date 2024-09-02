import pandas as pd
import streamlit as st
import base64
from googleapiclient.errors import HttpError
import os

class GenerarExcel:
  
  class Model:
    pageTitle ='***Genera archivo de datos de reservas***'
  
  def view(self,model):
    st.title(model.pageTitle)
  
    def get_table_download_link(df, filename):
      csv = df.to_csv(index=False)
      b64 = base64.b64encode(csv.encode()).decode()
      href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar datos filtrados (CSV)</a>'
      return href
  
    with st.form(key='myform',clear_on_submit=True):
      opciones = ["Encargado", "Servicio", "Fecha"]
      try:
        col1, col2 = st.columns(2)
        opcion = col1.selectbox('Tipo Generacion de Archivo*:', opciones)
        
        if opcion == "Encargado":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-emp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
            
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["ESTILISTA"].unique(): 
                  df_temp = df[df["ESTILISTA"] == x ]
                  
                  # Descargar datos filtrados
                  #df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
                  datafile = (f"agenda-{x}.csv")
                
                  st.info(f"agenda-{x}.csv")
                  st.markdown(get_table_download_link(df_temp, datafile), unsafe_allow_html=True)
                            
                  #data = os.listdir()
                  #for x in data:
                  #print(data)
                  
                os.chdir("..")
                #os.chdir('C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas')
                st.success('Archivos generados exitosamente')
                st.balloons()
            
              except HttpError as err:
                st.warning(f'se presento un  Errror {err} ')
                raise Exception(f'A ocurrido un error en generaExcel: {err}')    
                
        elif opcion == "Servicio":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-emp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["SERVICIOS"].unique(): 
                  df_temp = df[df["SERVICIOS"] == x ]
                  #df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
                  
                  datafile = (f"agenda-{x}.csv")
                
                  st.info(f"agenda-{x}.csv")
                  st.markdown(get_table_download_link(df_temp, datafile), unsafe_allow_html=True)

                os.chdir("..")
                st.success('Archivos generados exitosamente')
                st.balloons()
             
              except HttpError as err:
                st.warning(f'se presento un  Errror {err} ')
                raise Exception(f'A ocurrido un error en generaExcel: {err}')
                
        elif opcion == "Fecha":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-emp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["FECHA"].unique(): 
                  df_temp = df[df["FECHA"] == x ]
                  #df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
                  
                  datafile = (f"agenda-{x}.csv")
                
                  st.info(f"agenda-{x}.csv")
                  st.markdown(get_table_download_link(df_temp, datafile), unsafe_allow_html=True)

                os.chdir("..")
                st.success('Archivos generados exitosamente')
                st.balloons()
             
              except HttpError as err:
                st.warning(f'se presento un  Errror {err} ')
                raise Exception(f'A ocurrido un error en generaExcel: {err}')
            
      except HttpError as err:
        st.warning(f' Error No se encontro la ruta o el archivo fuente {err} ')
        raise Exception(f'A ocurrido un error en generaExcel: {err}')
