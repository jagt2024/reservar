import streamlit as st
import pandas as pd
import base64
import io

def load_excel(file):
    """Carga un archivo Excel y retorna todas las hojas"""
    return pd.read_excel(file, sheet_name=None)

def get_table_download_link(df, filename="datos_agenda_filtrados.csv"):
    """Genera un enlace de descarga para el DataFrame filtrado"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar datos filtrados (CSV)</a>'
    return href

class ConsultarAgenda:
    """Clase para consultar y visualizar agendas desde archivos Excel"""
  
    class Model:
        pageTitle = "***Consulta de la Agenda***"
  
    def view(self, model):
        """Método principal que muestra la interfaz de consulta"""
        st.title(model.pageTitle)
        
        # Cargar archivo
        uploaded_file = st.file_uploader(
            "📂 Escoge un archivo Excel", 
            type=['xlsx', 'xls'],
            help="Sube un archivo Excel (.xlsx o .xls) para consultar la agenda"
        )
        
        if uploaded_file is not None:
            try:
                # Cargar el archivo Excel
                excel_file = load_excel(uploaded_file)
                st.success("✅ Archivo cargado exitosamente!")
                
                # Seleccionar hoja
                sheet_names = list(excel_file.keys())
                selected_sheet = st.selectbox(
                    "📋 Selecciona la hoja a consultar", 
                    sheet_names,
                    help="Selecciona qué hoja del archivo Excel deseas visualizar"
                )

                # Cargar la hoja seleccionada
                df = excel_file[selected_sheet]
                
                # Mostrar información básica del DataFrame
                st.info(f"📊 Total de registros en la hoja '{selected_sheet}': **{len(df)}**")

                # Crear columnas para los controles
                col1, col2 = st.columns(2)
                
                with col1:
                    # Seleccionar columnas
                    all_columns = df.columns.tolist()
                    selected_columns = st.multiselect(
                        "🔍 Selecciona las columnas a mostrar", 
                        all_columns, 
                        default=all_columns,
                        help="Selecciona una o más columnas para filtrar la vista"
                    )

                with col2:
                    # Número de registros
                    num_records = st.number_input(
                        "📝 Número de registros a mostrar", 
                        min_value=1, 
                        max_value=len(df), 
                        value=min(10, len(df)),
                        help="Cuántos registros deseas visualizar"
                    )

                # Ordenar por columna
                sort_column = st.selectbox(
                    "⬆️ Ordenar por", 
                    ["Sin ordenar"] + all_columns,
                    help="Selecciona una columna para ordenar los resultados"
                )
                
                # Opción de orden ascendente o descendente
                if sort_column != "Sin ordenar":
                    ascending = st.radio(
                        "Orden", 
                        ["Descendente", "Ascendente"],
                        horizontal=True
                    )

                # Aplicar filtros y ordenamiento
                if selected_columns:
                    df_view = df[selected_columns].copy()
                else:
                    df_view = df.copy()

                if sort_column != "Sin ordenar":
                    df_view = df_view.sort_values(
                        by=sort_column, 
                        ascending=(ascending == "Ascendente")
                    )

                df_view = df_view.head(num_records)

                # Mostrar datos
                st.subheader("📄 Datos Filtrados")
                st.dataframe(
                    df_view,
                    use_container_width=True,
                    height=400
                )

                # Estadísticas básicas si hay columnas numéricas
                numeric_cols = df_view.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    with st.expander("📊 Estadísticas básicas"):
                        st.write(df_view[numeric_cols].describe())

                # Descargar datos filtrados
                st.markdown("---")
                st.markdown(
                    get_table_download_link(df_view), 
                    unsafe_allow_html=True
                )
                
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {str(e)}")
                st.info("Asegúrate de que el archivo sea un Excel válido (.xlsx o .xls)")
        else:
            # Mostrar instrucciones cuando no hay archivo cargado
            st.info("👆 Por favor, carga un archivo Excel para comenzar la consulta")
            
            with st.expander("ℹ️ Instrucciones de uso"):
                st.markdown("""
                ### Cómo usar esta herramienta:
                
                1. **Cargar archivo**: Haz clic en "Browse files" y selecciona tu archivo Excel
                2. **Seleccionar hoja**: Elige la hoja que deseas consultar
                3. **Filtrar columnas**: Selecciona qué columnas deseas visualizar
                4. **Ajustar registros**: Define cuántos registros mostrar
                5. **Ordenar datos**: Opcional - ordena por cualquier columna
                6. **Descargar**: Descarga los datos filtrados en formato CSV
                
                #### Formatos soportados:
                - `.xlsx` (Excel 2007 y posteriores)
                - `.xls` (Excel 97-2003)
                """)


def ConsultarAgenda_standalone():
    """
    Función independiente para ejecutar ConsultarAgenda sin necesidad de la clase
    Útil cuando se llama directamente desde el menú principal
    """
    consulta = ConsultarAgenda()
    consulta.view(ConsultarAgenda.Model())


if __name__ == "__main__":
    # Si se ejecuta directamente, mostrar la interfaz
    ConsultarAgenda_standalone()
