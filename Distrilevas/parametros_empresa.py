import streamlit as st
import pandas as pd
import os
from openpyxl import load_workbook
import numpy as np

def load_excel_file(file_path):
    """Cargar el archivo Excel y retornar el diccionario de DataFrames por hoja."""
    try:
        if not os.path.exists(file_path):
            return {"Hoja1": pd.DataFrame()}
            
        excel_file = pd.ExcelFile(file_path)
        sheets_dict = {sheet_name: pd.read_excel(file_path, sheet_name=sheet_name)
                      for sheet_name in excel_file.sheet_names}
        return sheets_dict
    except Exception as e:
        st.error(f"Error al cargar el archivo: {str(e)}")
        return {"Hoja1": pd.DataFrame()}

def save_excel_file(file_path, sheets_dict):
    """Guardar el diccionario de DataFrames en el archivo Excel."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for sheet_name, df in sheets_dict.items():
                if df.empty and len(df.columns) == 0:
                    df = pd.DataFrame(columns=['Columna1'])
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        st.success("Cambios guardados exitosamente")
    except Exception as e:
        st.error(f"Error al guardar el archivo: {str(e)}")

def get_column_config(df, column_name):
    """Determinar la configuración apropiada para cada columna basado en su tipo de datos."""
    try:
        # Si el nombre de la columna contiene indicadores de tipo
        col_lower = column_name.lower()
        
        if 'nit' in col_lower:
            return st.column_config.NumberColumn(
                column_name,
                default=0,
                format="%d",
                step=1
            )
        elif any(keyword in col_lower for keyword in ['telefono','licencia','cedula','modelo']):
            return st.column_config.NumberColumn(
                column_name,
                default=0,
                format="%d",
                step=1
            )    
        elif any(keyword in col_lower for keyword in ['precio', 'valor', 'monto', 'costo']):
            return st.column_config.NumberColumn(
                column_name,
                default=0.0,
                format="%.2f"
            )
        elif any(keyword in col_lower for keyword in ['fecha', 'date']):
            return st.column_config.DateColumn(column_name)
        elif any(keyword in col_lower for keyword in ['time']):
            return st.column_config.TimeColumn(column_name)
        elif any(keyword in col_lower for keyword in ['correo', 'email']):
            return st.column_config.TextColumn(column_name, validate="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        else:
            # Determinar por el tipo de datos
            dtype = str(df[column_name].dtype)
            if 'int' in dtype:
                return st.column_config.NumberColumn(column_name, format="%d", step=1)
            elif 'float' in dtype:
                return st.column_config.NumberColumn(column_name, format="%.2f")
            elif 'datetime' in dtype:
                return st.column_config.DatetimeColumn(column_name)
            elif 'bool' in dtype:
                return st.column_config.CheckboxColumn(column_name)
            else:
                return st.column_config.TextColumn(column_name)
    except:
        return st.column_config.TextColumn(column_name)

def parametros():
    st.title("Gestor de Parametros de Archivos")
    
    file_path = os.path.join("./archivos-dlv", "parametros_empresa.xlsx")
    
    if 'sheets_dict' not in st.session_state:
        st.session_state.sheets_dict = load_excel_file(file_path)
    
    with st.sidebar:
        st.header("Gestión de Hojas")
        
        new_sheet_name = st.text_input("Nombre de nueva hoja")
        if st.button("Crear nueva hoja"):
            if new_sheet_name and new_sheet_name not in st.session_state.sheets_dict:
                st.session_state.sheets_dict[new_sheet_name] = pd.DataFrame(columns=['Columna1'])
                st.success(f"Hoja '{new_sheet_name}' creada")
            else:
                st.error("Nombre inválido o la hoja ya existe")
        
        current_sheet = st.selectbox("Seleccionar hoja", 
                                   list(st.session_state.sheets_dict.keys()))
        
        #if len(st.session_state.sheets_dict) > 1 and st.button("Eliminar hoja actual"):
        #    if current_sheet:
        #        del st.session_state.sheets_dict[current_sheet]
        #        st.success(f"Hoja '{current_sheet}' eliminada")
        #        st.rerun()
    
    if current_sheet:
        st.header(f"Editando hoja: {current_sheet}")
        
        col1, col2 = st.columns(2)
        with col1:
            new_col_name = st.text_input("Nombre de nueva columna")
            if st.button("Añadir columna"):
                if new_col_name and new_col_name not in st.session_state.sheets_dict[current_sheet].columns:
                    st.session_state.sheets_dict[current_sheet][new_col_name] = ""
                    st.success(f"Columna '{new_col_name}' añadida")
                    st.rerun()
        
        with col2:
            columns = list(st.session_state.sheets_dict[current_sheet].columns)
            if columns:
                col_to_delete = st.selectbox("Seleccionar columna a eliminar", columns)
                if st.button("Eliminar columna") and len(columns) > 1:
                    st.session_state.sheets_dict[current_sheet] = st.session_state.sheets_dict[current_sheet].drop(columns=[col_to_delete])
                    st.success(f"Columna '{col_to_delete}' eliminada")
                    st.rerun()
        
        if st.session_state.sheets_dict[current_sheet].empty and len(st.session_state.sheets_dict[current_sheet].columns) == 0:
            st.session_state.sheets_dict[current_sheet] = pd.DataFrame(columns=['Columna1'])
        
        st.subheader("Editor de datos")
        
        # Configurar el tipo de columna basado en el nombre y los datos
        column_config = {
            col: get_column_config(st.session_state.sheets_dict[current_sheet], col)
            for col in st.session_state.sheets_dict[current_sheet].columns
        }
        
        edited_df = st.data_editor(
            st.session_state.sheets_dict[current_sheet],
            num_rows="dynamic",
            use_container_width=True,
            column_config=column_config
        )
        st.session_state.sheets_dict[current_sheet] = edited_df
        
        if st.button("Guardar todos los cambios"):
            save_excel_file(file_path, st.session_state.sheets_dict)

if __name__ == "__main__":
    parametros()