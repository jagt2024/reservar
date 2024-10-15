import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import json
from datetime import datetime
#from user_management import logout 

# Función para conectar a la base de datos
def get_db_connection():
    conn = sqlite3.connect('facturas.db')
    conn.row_factory = sqlite3.Row
    return conn

# Función para cargar los datos de las facturas
def load_invoice_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM facturas", conn)
    conn.close()
    
    # Convertir la columna de servicios de JSON a lista de diccionarios
    df['servicios'] = df['servicios'].apply(json.loads)
    
    # Convertir fecha_factura a datetime
    df['fecha_factura'] = pd.to_datetime(df['fecha_factura'])
    
    return df

# Función para extraer servicios individuales
def extract_services(df):
    services = []
    for _, row in df.iterrows():
        for service in row['servicios']:
            service['fecha_factura'] = row['fecha_factura']
            services.append(service)
    return pd.DataFrame(services)

# Aplicación Streamlit
def main_factura():
    st.title("Estadísticas de Servicios")

    # Cargar datos
    df = load_invoice_data()

    # Añadir filtro de rango de fechas en el área principal
    st.header("Filtrar por Rango de Fechas")
    min_date = df['fecha_factura'].min().date()
    max_date = df['fecha_factura'].max().date()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Fecha de inicio", min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("Fecha de fin", max_date, min_value=min_date, max_value=max_date)

    # Filtrar el DataFrame por el rango de fechas seleccionado
    mask = (df['fecha_factura'].dt.date >= start_date) & (df['fecha_factura'].dt.date <= end_date)
    filtered_df = df.loc[mask]

    services_df = extract_services(filtered_df)

    # Botón para aplicar el filtro
    if st.button("Aplicar Filtro"):
        st.success(f"Mostrando datos desde {start_date} hasta {end_date}")

        # Métricas generales
        st.header("Métricas Generales")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Facturas", len(filtered_df))
        col2.metric("Total Servicios Vendidos", services_df['cantidad'].sum())
        col3.metric("Ingresos Totales", f"${filtered_df['total'].sum():,.2f}")

        # Gráfico de barras: Servicios más vendidos
        st.header("Servicios Más Vendidos")
        top_services = services_df.groupby('descripcion')['cantidad'].sum().sort_values(ascending=False).head(10)
        fig = px.bar(top_services, x=top_services.index, y='cantidad')
        st.plotly_chart(fig)

        # Gráfico de líneas: Ingresos por mes
        st.header("Ingresos por Mes")
        filtered_df['mes'] = filtered_df['fecha_factura'].dt.to_period('M')
        monthly_revenue = filtered_df.groupby('mes')['total'].sum().reset_index()
        monthly_revenue['mes'] = monthly_revenue['mes'].astype(str)
        fig = px.line(monthly_revenue, x='mes', y='total', title='Ingresos Mensuales')
        st.plotly_chart(fig)

        # Gráfico circular: Distribución de ingresos por servicio
        st.header("Distribución de Ingresos por Servicio")
        service_revenue = services_df.groupby('descripcion')['subtotal'].sum().sort_values(ascending=False)
        fig = px.pie(service_revenue, values='subtotal', names=service_revenue.index, title='Distribución de Ingresos por Servicio')
        st.plotly_chart(fig)

        # Tabla de resumen de servicios
        st.header("Resumen de Servicios")
        service_summary = services_df.groupby('descripcion').agg({
            'cantidad': 'sum',
            'subtotal': 'sum'
        }).sort_values('subtotal', ascending=False).reset_index()
        service_summary['precio_promedio'] = service_summary['subtotal'] / service_summary['cantidad']
        service_summary = service_summary.rename(columns={
            'descripcion': 'Servicio',
            'cantidad': 'Cantidad Vendida',
            'subtotal': 'Ingresos Totales',
            'precio_promedio': 'Precio Promedio'
        })
        service_summary['Ingresos Totales'] = service_summary['Ingresos Totales'].apply(lambda x: f"${x:,.2f}")
        service_summary['Precio Promedio'] = service_summary['Precio Promedio'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(service_summary)
    

#if __name__ == "__main__":
#    main()
