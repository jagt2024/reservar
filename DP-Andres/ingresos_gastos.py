import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_sheets_emp import GoogleSheet
import toml
import json

def load_data_from_sheets(gs):
    """Cargar datos desde Google Sheets"""
    try:
        data = gs.read_data("A1:E")
        if data and len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
            df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce')
            return df
        return pd.DataFrame(columns=['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Monto'])
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame(columns=['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Monto'])

def save_transaction_to_sheets(gs, transaction_data):
    """Guardar nueva transacción en Google Sheets"""
    try:
        rango = gs.get_last_row_range()
        values = [[
            transaction_data['Fecha'].strftime('%Y-%m-%d'),
            transaction_data['Tipo'],
            transaction_data['Categoría'],
            transaction_data['Descripción'],
            str(transaction_data['Monto'])
        ]]
        gs.write_data(rango, values)
        return True
    except Exception as e:
        st.error(f"Error al guardar transacción: {str(e)}")
        return False

def initialize_sheet_if_empty(gs):
    """Inicializar la hoja con encabezados si está vacía"""
    try:
        data = gs.read_data("A1:E1")
        if not data:
            headers = [['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Monto']]
            gs.write_data("A1:E1", headers)
    except Exception as e:
        st.error(f"Error al inicializar hoja: {str(e)}")

def get_date_range():
    """Obtener rango de fechas para el filtro"""
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input(
            "Fecha Inicial",
            datetime.now().date().replace(day=1)
        )
    with col2:
        fecha_fin = st.date_input(
            "Fecha Final",
            datetime.now().date()
        )
    return fecha_inicio, fecha_fin

def control():
    st.title("Sistema de Control de Ingresos y Gastos")

    # Configuración de Google Sheets
    document = 'gestion-reservas-dp'
    sheet = 'ingresos_gastos'
    credentials = st.secrets['sheetsemp']['credentials_sheet']
    
    try:
        gs = GoogleSheet(credentials, document, sheet)
        initialize_sheet_if_empty(gs)
        if 'transactions' not in st.session_state:
            st.session_state.transactions = load_data_from_sheets(gs)
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {str(e)}")
        return

    # Selector de rango de fechas
    st.subheader("Seleccione el Rango de Fechas para el Análisis")
    fecha_inicio, fecha_fin = get_date_range()

    # Crear dos columnas: una para el formulario y otra para el resumen
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Crear una Nueva Transacción")
        
        # Campos fuera del formulario para que sean reactivos
        fecha = st.date_input("Fecha", datetime.now())
        tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"], key="tipo_selector")
        
        # Categorías según el tipo seleccionado
        categorias_ingresos = ["Ventas", "Servicios", "Otros Ingresos"]
        categorias_gastos = ["Compras", "Servicios", "Salarios", "Alquiler", "Otros Gastos"]
        categorias = categorias_ingresos if tipo == "Ingreso" else categorias_gastos
        categoria = st.selectbox("Categoría", categorias)
        
        descripcion = st.text_input("Descripción")
        monto = st.number_input("Monto", min_value=0.0, value=0.0)
        
        # Botón de envío fuera del formulario
        if st.button("Registrar Transacción"):
            if monto > 0:
                nueva_transaccion = {
                    'Fecha': fecha,
                    'Tipo': tipo,
                    'Categoría': categoria,
                    'Descripción': descripcion,
                    'Monto': monto
                }
                
                if save_transaction_to_sheets(gs, nueva_transaccion):
                    nueva_transaccion_df = pd.DataFrame([nueva_transaccion])
                    st.session_state.transactions = pd.concat(
                        [st.session_state.transactions, nueva_transaccion_df],
                        ignore_index=True
                    )
                    st.success("Transacción registrada con éxito!")
                    st.session_state.transactions = load_data_from_sheets(gs)
                else:
                    st.error("Error al registrar la transacción")
            else:
                st.warning("El monto debe ser mayor a 0")

    with col2:
        if not st.session_state.transactions.empty:
            # Filtrar transacciones por rango de fechas
            df_filtered = st.session_state.transactions[
                (st.session_state.transactions['Fecha'] >= fecha_inicio) &
                (st.session_state.transactions['Fecha'] <= fecha_fin)
            ]

            # Cálculos financieros con datos filtrados
            total_ingresos = df_filtered[
                df_filtered['Tipo'] == 'Ingreso'
            ]['Monto'].sum()
            
            total_gastos = df_filtered[
                df_filtered['Tipo'] == 'Gasto'
            ]['Monto'].sum()
            
            balance = total_ingresos - total_gastos
            
            # Mostrar métricas principales
            st.subheader(f"Resumen Financiero ({fecha_inicio} al {fecha_fin})")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Ingresos", f"${total_ingresos:.2f}", "+")
            with col_b:
                st.metric("Total Gastos", f"${total_gastos:.2f}", "-")
            with col_c:
                st.metric(
                    "Balance",
                    f"${balance:.2f}",
                    f"{'↑' if balance > 0 else '↓'}"
                )
            
            # Análisis por categoría con datos filtrados
            st.subheader("Análisis por Categoría")
            tab1, tab2 = st.tabs(["Ingresos", "Gastos"])
            
            with tab1:
                ingresos_por_categoria = df_filtered[
                    df_filtered['Tipo'] == 'Ingreso'
                ].groupby('Categoría')['Monto'].sum()
                st.bar_chart(ingresos_por_categoria)
                
            with tab2:
                gastos_por_categoria = df_filtered[
                    df_filtered['Tipo'] == 'Gasto'
                ].groupby('Categoría')['Monto'].sum()
                st.bar_chart(gastos_por_categoria)
    
    # Mostrar transacciones filtradas
    if not st.session_state.transactions.empty:
        st.subheader(f"Registro de Transacciones ({fecha_inicio} al {fecha_fin})")
        st.dataframe(
            df_filtered.sort_values('Fecha', ascending=False),
            hide_index=True
        )
        
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            "Descargar Datos Filtrados",
            csv,
            "transacciones_filtradas.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No hay transacciones registradas. Utiliza el formulario para comenzar.")

#if __name__ == "__main__":
#    control()