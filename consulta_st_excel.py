import streamlit as st
import pandas as pd
import base64
import io

def load_excel(file):
    return pd.read_excel(file, sheet_name=None)

def get_table_download_link(df, filename="datos_agenda_filtrados.csv"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar datos filtrados (CSV)</a>'
    return href

#def main():
#    st.title("Visor de Excel con Streamlit")

class ConsultarAgenda:
  
  class Model:
    pageTitle = "***Consulta de la Agenda***"
  
  def view(self,model):
    st.title(model.pageTitle)
    
    # Cargar archivo
    uploaded_file = st.file_uploader("Escoge un archivo Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        #df = load_excel(uploaded_file)
        excel_file = load_excel(uploaded_file)
        st.success("Archivo cargado exitosamente!")
        
        # Seleccionar hoja
        sheet_names = list(excel_file.keys())
        selected_sheet = st.selectbox("Selecciona la hoja a consultar", sheet_names)

        # Cargar la hoja seleccionada
        df = excel_file[selected_sheet]

        # Seleccionar columnas
        all_columns = df.columns.tolist()
        selected_columns = st.multiselect("Selecciona las columnas a mostrar", all_columns, default=all_columns)

        # Número de registros
        num_records = st.number_input("Número de registros a mostrar", min_value=1, max_value=len(df), value=2)

        # Ordenar por columna
        sort_column = st.selectbox("Ordenar por", ["Sin ordenar"] + all_columns)

        # Aplicar filtros y ordenamiento
        if selected_columns:
            df_view = df[selected_columns]
        else:
            df_view = df

        if sort_column != "Sin ordenar":
            df_view = df_view.sort_values(by=sort_column, ascending=False)  # Ordenar de forma descendente

        df_view = df_view.head(num_records)

        # Mostrar datos
        st.write(df_view)

        # Descargar datos filtrados
        st.markdown(get_table_download_link(df_view), unsafe_allow_html=True)

#if __name__ == "__main__":
#    main()