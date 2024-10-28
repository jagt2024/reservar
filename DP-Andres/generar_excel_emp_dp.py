import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
import os

class GenerarExcelEmp:
  
  class Model:
    pageTitle ='***Genera archivo de datos de reservas***'
  
  def view(self,model):
    st.title(model.pageTitle)
  
    with st.form(key='myform',clear_on_submit=True):
      opciones = ["Encargado", "Servicio", "Fecha", "Zona"]
      try:
        col1, col2 = st.columns(2)
        opcion = col1.selectbox('Tipo Generacion de Archivo*:', opciones)
        
        if opcion == "Encargado":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-dp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["ENCARGADO"].unique(): 
                  df_temp = df[df["ENCARGADO"] == x ]
                  df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
          
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
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-dp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["SERVICIOS"].unique(): 
                  df_temp = df[df["SERVICIOS"] == x ]
                  df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")

                os.chdir("..")
                st.success('Archivos generados exitosamente')
                st.balloons()
             
              except HttpError as err:
                st.warning(f'se presento un  Errror {err} ')
                raise Exception(f'A ocurrido un error en generaExcel: {err}')
                
        elif opcion == "Fecha":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-dp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["FECHA"].unique(): 
                  df_temp = df[df["FECHA"] == x ]
                  df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")

                os.chdir("..")
                st.success('Archivos generados exitosamente')
                st.balloons()
             
              except HttpError as err:
                st.warning(f'se presento un  Errror {err} ')
                raise Exception(f'A ocurrido un error en generaExcel: {err}')
        
        elif opcion == "Zona":
        
          datos =col2.file_uploader("Ruta para el archivo de datos: gestion-reservas-dp.xlsx")
          generar = st.form_submit_button(" Generar ")
  
          if generar:   
            df = pd.read_excel(datos)
  
            with st.spinner('Cargando...'): 
              try: 
                os.chdir("archivos")
                for x in df["ZONA"].unique(): 
                  df_temp = df[df["ZONA"] == x ]
                  df_temp.to_excel(f"reservas-{x}.xlsx", index = False, engine="openpyxl")
          
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
            
      except HttpError as err:
        st.warning(f' Error No se encontro la ruta o el archivo fuente {err} ')
        raise Exception(f'A ocurrido un error en generaExcel: {err}')
