import streamlit as st
import pandas as pd
import base64
import io

def load_excel(file):
    return pd.read_excel(file, sheet_name=None)

def save_excel(dataframes, filename="datos_modificados.xlsx"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dataframes.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Descargar Excel modificado</a>'
    return href

def get_table_download_link(df, filename="datos_agenda_filtrados.csv"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar datos filtrados (CSV)</a>'
    return href

class ConsultarAgenda:
  
    class Model:
        pageTitle = "***Consulta y Edición Avanzada de la Agenda***"
  
    def view(self, model):
        st.title(model.pageTitle)
        
        # Cargar archivo
        uploaded_file = st.file_uploader("Escoge un archivo Excel", type=['xlsx', 'xls'])
        
        if uploaded_file is not None:
            excel_file = load_excel(uploaded_file)
            st.success("Archivo cargado exitosamente!")

            # Seleccionar modo: Consulta o Edición
            mode = st.radio("Selecciona el modo", ["Consulta", "Edición"])

            if mode == "Consulta":
                self.consulta_mode(excel_file)
            else:
                self.edicion_mode(excel_file)

    def consulta_mode(self, excel_file):
        # (El código de consulta permanece igual)
        ...

    def edicion_mode(self, excel_file):
        st.subheader("Modo de Edición")

        # Seleccionar hoja o crear nueva
        sheet_names = list(excel_file.keys())
        sheet_action = st.radio("¿Qué deseas hacer?", ["Editar hoja existente", "Crear nueva hoja"])

        if sheet_action == "Editar hoja existente":
            selected_sheet = st.selectbox("Selecciona la hoja a editar", sheet_names)
            df = excel_file[selected_sheet]
        else:
            new_sheet_name = st.text_input("Nombre de la nueva hoja")
            if new_sheet_name and new_sheet_name not in sheet_names:
                df = pd.DataFrame()
                excel_file[new_sheet_name] = df
                selected_sheet = new_sheet_name
            else:
                st.warning("Por favor, ingresa un nombre único para la nueva hoja.")
                return

        # Editar columnas
        st.subheader("Editar columnas")
        col_action = st.radio("¿Qué deseas hacer con las columnas?", ["Mantener", "Agregar", "Eliminar", "Renombrar"])

        if col_action == "Agregar":
            new_col_name = st.text_input("Nombre de la nueva columna")
            if new_col_name and new_col_name not in df.columns:
                df[new_col_name] = ""
        elif col_action == "Eliminar":
            col_to_delete = st.selectbox("Selecciona la columna a eliminar", df.columns)
            if st.button("Eliminar columna"):
                df = df.drop(columns=[col_to_delete])
        elif col_action == "Renombrar":
            col_to_rename = st.selectbox("Selecciona la columna a renombrar", df.columns)
            new_name = st.text_input("Nuevo nombre de la columna")
            if new_name and st.button("Renombrar columna"):
                df = df.rename(columns={col_to_rename: new_name})

        # Editar datos
        st.subheader("Editar datos")
        data_action = st.radio("¿Qué deseas hacer con los datos?", ["Editar existentes", "Agregar nueva fila"])

        if data_action == "Editar existentes":
            edited_df = st.data_editor(df)
        else:
            new_row = {}
            for col in df.columns:
                new_row[col] = st.text_input(f"Valor para {col}")
            
            if st.button("Agregar nueva fila"):
                new_df = pd.DataFrame([new_row])
                df = pd.concat([df, new_df], ignore_index=True)
                st.success("Nueva fila agregada exitosamente!")

        # Mostrar datos actualizados
        st.subheader("Datos actualizados")
        st.write(df)

        # Guardar cambios
        if st.button("Guardar cambios"):
            excel_file[selected_sheet] = df
            st.success("Cambios guardados exitosamente!")

        # Descargar Excel modificado
        st.markdown(save_excel(excel_file), unsafe_allow_html=True)

if __name__ == "__main__":
    ConsultarAgenda().view(ConsultarAgenda.Model())