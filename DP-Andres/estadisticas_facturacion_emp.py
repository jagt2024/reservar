import streamlit as st
import sqlite3
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
import toml

#from user_management import logout 

def load_credentials():
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales: {str(e)}")
        return None

def get_google_sheet_data(creds):
  try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(creds, scopes=scope)
    client = gspread.authorize(credentials)

    sheet = client.open('gestion-reservas-dp')
    worksheet = sheet.worksheet('facturacion')
    data = worksheet.get_all_values()
    
    if not data:
       st.error("No se encontraron datos en la hoja de cálculo.")
       return None
    
    df = pd.DataFrame(data[1:], columns=data[0])
    
    if df.empty:
       st.error("El DataFrame está vacío después de cargar los datos.")
       return None

    df = df.dropna(subset=['FECHA_FACTURA', 'TOTAL'])
    df['FECHA_FACTURA'] = df['FECHA_FACTURA'].astype('datetime64[ns]')
    
    df['SERVICIOS'] = df['SERVICIOS'].apply(json.loads)

    #df['FECHA_FACTURA'] = pd.to_datetime(df['FECHA_FACTURA'], errors='coerce')
    
    # Informar sobre filas con fechas inválidas
    invalid_dates = df[df['FECHA_FACTURA'].isna()]
    if not invalid_dates.empty:
        st.warning(f"Se encontraron {len(invalid_dates)} filas con fechas inválidas. Estas filas serán excluidas del análisis.")
        st.write("Primeras 5 filas con fechas inválidas:")
        st.write(invalid_dates.head())
    
    if df.empty:
        st.error("El DataFrame está vacío después de eliminar las fechas inválidas.")
        return None
    # Eliminar filas con fechas inválidas
    
    df = df.dropna(subset=['FECHA_FACTURA'])
    
    return df

  except Exception as e:
     st.error(f"Error al obtener datos de Google Sheets: {str(e)}")
     return None

@st.cache_data
def load_data():
    creds = load_credentials()
    df = get_google_sheet_data(creds)
    
    # Intentar diferentes formatos de fecha
    date_formats = ['%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    
    for date_format in date_formats:
        try:
            df['FECHA_FACTURA'] = pd.to_datetime(df['FECHA_FACTURA'], format=date_format)
            break
        except ValueError:
            continue
    
    if not pd.api.types.is_datetime64_any_dtype(df['FECHA_FACTURA']):
        # Si ningún formato funciona, intentar con parse_dates
        df['FECHA_FACTURA'] = pd.to_datetime(df['FECHA_FACTURA'], infer_datetime_format=True, errors='coerce')
    
    # Eliminar filas con fechas inválidas
    df = df.dropna(subset=['FECHA_FACTURA'])
    
    return df

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
    df['SERVICIOS'] = df['SERVICIOS'].apply(json.loads)
    
    # Convertir fecha_factura a datetime
    df['FECHA_FACTURA'] = pd.to_datetime(df['FECHA_FACTURA'])
    
    return df

# Función para extraer servicios individuales
def extract_services(df):
    services = []
    for _, row in df.iterrows():
        for service in row['SERVICIOS']:
            service_copy = service.copy()
            service_copy['FECHA_FACTURA'] = row['FECHA_FACTURA']
            services.append(service_copy)
    return pd.DataFrame(services)

def create_top_services_chart(services_df):
    top_services = services_df.groupby('descripcion')['cantidad'].sum().sort_values(ascending=False).head(10)
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(top_services.index),
            y=list(top_services.values),
            text=list(top_services.values),
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title='Top 10 Servicios Más Vendidos',
        xaxis_title='Servicio',
        yaxis_title='Cantidad Vendida',
        showlegend=False
    )
    
    return fig

# Aplicación Streamlit
def factura():
    st.title("Estadísticas Servicios de Facturacion")

    # Cargar datos
    #df = load_invoice_data()
    df = load_data()

    if df is None:
        st.error("No se pudieron cargar los datos. Por favor, verifique la conexión con Google Sheets.")
        return
    
    #df['FECHA_FACTURA'] = pd.to_datetime(df['FECHA_FACTURA'])
    
    try:
        # Añadir filtro de rango de fechas en el área principal
        st.header("Filtrar por Rango de Fechas")
        min_date = df['FECHA_FACTURA'].min().date()
        max_date = df['FECHA_FACTURA'].max().date()
    
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Fecha de inicio", min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("Fecha de fin", max_date, min_value=min_date, max_value=max_date)

        # Filtrar el DataFrame por el rango de fechas seleccionado
        mask = (df['FECHA_FACTURA'].dt.date >= start_date) & (df['FECHA_FACTURA'].dt.date <= end_date)
        filtered_df = df.loc[mask]

        services_df = extract_services(filtered_df)
    
        services_df['subtotal'] = pd.to_numeric(services_df['subtotal'], errors='coerce')
        services_df['cantidad'] = pd.to_numeric(services_df['cantidad'], errors='coerce')

        # Botón para aplicar el filtro
        if st.button("Aplicar Filtro"):
            st.success(f"Mostrando datos desde {start_date} hasta {end_date}")

            # Métricas generales
            st.header("Métricas Generales")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Facturas", len(filtered_df))
            col2.metric("Total Servicios Vendidos", int(services_df['cantidad'].sum()))
            col3.metric("Ingresos Totales", int(services_df['total'].sum()))
            
            # Gráfico de servicios más vendidos
            st.header("Servicios Más Vendidos")
            fig_services = create_top_services_chart(services_df)
            st.plotly_chart(fig_services)

            # Gráfico de ingresos mensuales
            st.header("Ingresos por Mes")
            filtered_df['mes'] = filtered_df['FECHA_FACTURA'].dt.strftime('%Y-%m')
            monthly_revenue = filtered_df.groupby('mes')['TOTAL'].sum().reset_index()
            fig = px.line(monthly_revenue, x='mes', y='TOTAL',
                         title='Ingresos Mensuales',
                         labels={'mes': 'Mes', 'TOTAL': 'Ingresos ($)'})
            st.plotly_chart(fig)

            # Gráfico de distribución de ingresos
            st.header("Distribución de Ingresos por Servicio")
            service_revenue = services_df.groupby('descripcion')['subtotal'].sum()
            fig = px.pie(values=service_revenue.values, 
                        names=service_revenue.index,
                        title='Distribución de Ingresos por Servicio')
            st.plotly_chart(fig)

            # Tabla de resumen
            st.header("Resumen de Servicios")
            service_summary = services_df.groupby('descripcion').agg({
                'cantidad': 'sum',
                'total': 'sum'
            }).sort_values('total', ascending=False).reset_index()
            
            service_summary['precio_promedio'] = service_summary['total'] / service_summary['cantidad']
            service_summary = service_summary.rename(columns={
                'descripcion': 'Servicio',
                'cantidad': 'Cantidad Vendida',
                'total': 'Ingresos Totales',
                'precio_promedio': 'Precio Promedio'
            })
            
            service_summary['Ingresos Totales'] = service_summary['Ingresos Totales'].apply(lambda x: f"${x:,.2f}")
            service_summary['Precio Promedio'] = service_summary['Precio Promedio'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(service_summary)
            
    except Exception as e:
        st.error(f"Error al procesar las fechas: {str(e)}")
        st.error("Por favor, verifique el formato de las fechas en la hoja de cálculo.")

#if __name__ == "__main__":
#    main()
