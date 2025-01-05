import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
import os
import zipfile
import io

class GenerarExcelEmp:
  
  class Model:
    pageTitle = '***Genera archivo de datos de reservas***'
  
  def view(self, model):
    st.title(model.pageTitle)
    
    # Create directory for files if it doesn't exist
    if not os.path.exists("./archivos-dp"):
        os.makedirs("./archivos-dp")
    
    # State management for generated files
    if 'generated_files' not in st.session_state:
        st.session_state.generated_files = []
    
    # Form for file generation
    with st.form(key='myform', clear_on_submit=True):
      opciones = ["Encargado", "Servicio", "Fecha", "Zona"]
      try:
        col1, col2 = st.columns(2)
        opcion = col1.selectbox('Tipo Generacion de Archivo*:', opciones)
        datos = col2.file_uploader("Ruta para el archivo de datos: temp_gestion_reservas-dp.xlsx")
        generar = st.form_submit_button(" Generar ")
        
        if generar and datos is not None:
          df = pd.read_excel(datos)
          st.session_state.generated_files = []  # Reset generated files list
          
          with st.spinner('Generando archivos...'):
            try:
              # Dictionary to map options to their corresponding column names
              option_columns = {
                "Encargado": "ENCARGADO",
                "Servicio": "SERVICIOS",
                "Fecha": "FECHA",
                "Zona": "ZONA"
              }
              
              column = option_columns[opcion]
              
              # Generate individual Excel files
              for x in df[column].unique():
                df_temp = df[df[column] == x]
                file_name = f"reservas-{x}.xlsx"
                file_path = os.path.join("archivos-dp", file_name)
                df_temp.to_excel(file_path, index=False, engine="openpyxl")
                st.session_state.generated_files.append(file_path)
              
              st.write(f"Se han procesado {len(df)} registros válidos.")
              st.success('Archivos generados exitosamente')
              st.balloons()
            
            except HttpError as err:
              st.warning(f'Se presentó un Error: {err}')
              raise Exception(f'Ha ocurrido un error en generaExcel: {err}')
            
      except HttpError as err:
        st.warning(f'Error: No se encontró la ruta o el archivo fuente {err}')
        raise Exception(f'Ha ocurrido un error en generaExcel: {err}')
    
    # Download section (outside the form)
    if st.session_state.generated_files:
        st.write("### Descargar archivos")
        
        # Download individual files
        for file_path in st.session_state.generated_files:
            with open(file_path, 'rb') as f:
                file_data = f.read()
                st.download_button(
                    label=f"Descargar {os.path.basename(file_path)}",
                    data=file_data,
                    file_name=os.path.basename(file_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{os.path.basename(file_path)}"  # Unique key for each button
                )
        
        # Create and offer ZIP download
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in st.session_state.generated_files:
                zip_file.write(file_path, os.path.basename(file_path))
        
        zip_buffer.seek(0)
        st.download_button(
            label="Descargar todos los archivos (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="reservas.zip",
            mime="application/zip",
            key="download_zip"
        )