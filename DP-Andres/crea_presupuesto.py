import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# Configuración de la página
st.set_page_config(page_title="Gestor de Presupuestos", layout="wide")

# Función para crear archivo Excel con estructura inicial si no existe
def crear_excel_inicial(nombre_archivo):
    if not os.path.exists(nombre_archivo):
        # Crear DataFrame para presupuesto
        df_presupuesto = pd.DataFrame(columns=[
            'fecha', 'tipo', 'categoria', 'concepto', 'monto', 'notas'
        ])
        
        # Crear DataFrame para categorías
        categorias_default = {
            'categoria': [
                'Recursos Humanos - Salarios',
                'Recursos Humanos - Consultores',
                'Recursos Humanos - Capacitación',
                'Equipamiento - Hardware',
                'Equipamiento - Software',
                'Equipamiento - Mantenimiento',
                'Infraestructura - Alquiler',
                'Infraestructura - Servicios',
                'Materiales - Directos',
                'Materiales - Oficina',
                'Servicios Profesionales - Legal',
                'Servicios Profesionales - Contable',
                'Marketing - Publicidad',
                'Marketing - Eventos',
                'Gastos Operativos - Transporte',
                'Gastos Operativos - Viáticos',
                'Administrativos - Bancarios',
                'Administrativos - Permisos',
                'Contingencias',
                'I+D - Investigación'
            ],
            'presupuesto_asignado': [0] * 20  # Inicialmente en 0
        }
        df_categorias = pd.DataFrame(categorias_default)
        
        # Guardar ambos DataFrames en diferentes hojas del mismo archivo Excel
        with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
            df_presupuesto.to_excel(writer, sheet_name='Presupuesto', index=False)
            df_categorias.to_excel(writer, sheet_name='Categorias', index=False)

# Función para cargar datos desde Excel
def cargar_datos_excel(nombre_archivo):
    if os.path.exists(nombre_archivo):
        df_presupuesto = pd.read_excel(nombre_archivo, sheet_name='Presupuesto')
        df_categorias = pd.read_excel(nombre_archivo, sheet_name='Categorias')
        # Convertir la columna fecha a datetime
        if not df_presupuesto.empty:
            df_presupuesto['fecha'] = pd.to_datetime(df_presupuesto['fecha']).dt.date
        return df_presupuesto, df_categorias
    return None, None

# Función para guardar datos en Excel
def guardar_datos_excel(df_presupuesto, df_categorias, nombre_archivo):
    with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
        # Convertir la columna fecha a datetime antes de guardar
        df_presupuesto_save = df_presupuesto.copy()
        if not df_presupuesto_save.empty:
            df_presupuesto_save['fecha'] = pd.to_datetime(df_presupuesto_save['fecha'])
        df_presupuesto_save.to_excel(writer, sheet_name='Presupuesto', index=False)
        df_categorias.to_excel(writer, sheet_name='Categorias', index=False)

# Nombre del archivo Excel
NOMBRE_ARCHIVO = 'presupuesto_proyecto.xlsx'

# Crear archivo Excel si no existe
crear_excel_inicial(NOMBRE_ARCHIVO)

# Cargar datos existentes
df_presupuesto, df_categorias = cargar_datos_excel(NOMBRE_ARCHIVO)

# Título principal
st.title("📊 Gestor de Presupuestos para Proyectos")

# Sidebar para configuración de categorías
with st.sidebar:
    st.header("Gestión de Categorías")
    
    # Mostrar y editar presupuestos asignados
    st.subheader("Presupuestos por Categoría")
    df_categorias_temp = df_categorias.copy()
    
    for index, row in df_categorias.iterrows():
        nuevo_presupuesto = st.number_input(
            f"{row['categoria']}",
            value=float(row['presupuesto_asignado']),
            key=f"cat_{index}"
        )
        df_categorias_temp.at[index, 'presupuesto_asignado'] = nuevo_presupuesto
    
    if st.button("Actualizar Presupuestos"):
        df_categorias = df_categorias_temp.copy()
        guardar_datos_excel(df_presupuesto, df_categorias, NOMBRE_ARCHIVO)
        st.success("Presupuestos actualizados!")

# Contenido principal
tab1, tab2, tab3 = st.tabs(["Registro de Movimientos", "Análisis", "Reportes"])

# Tab de Registro de Movimientos
with tab1:
    st.header("Registro de Ingresos y Gastos")
    
    with st.form("nuevo_movimento"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
            fecha = st.date_input("Fecha")
        
        with col2:
            categoria = st.selectbox(
                "Categoría",
                options=df_categorias['categoria'].tolist()
            )
            concepto = st.text_input("Concepto")
        
        with col3:
            monto = st.number_input("Monto", min_value=0.0)
            notas = st.text_input("Notas")
        
        if st.form_submit_button("Registrar Movimiento"):
            nuevo_movimiento = pd.DataFrame([{
                'fecha': fecha,
                'tipo': tipo,
                'categoria': categoria,
                'concepto': concepto,
                'monto': monto if tipo == "Ingreso" else -monto,
                'notas': notas
            }])
            
            if df_presupuesto is None:
                df_presupuesto = nuevo_movimiento
            else:
                df_presupuesto = pd.concat([df_presupuesto, nuevo_movimiento], ignore_index=True)
            guardar_datos_excel(df_presupuesto, df_categorias, NOMBRE_ARCHIVO)
            st.success("Movimiento registrado exitosamente!")

    # Mostrar movimientos
    if df_presupuesto is not None and not df_presupuesto.empty:
        st.subheader("Últimos Movimientos")
        df_display = df_presupuesto.copy()
        df_display['fecha'] = pd.to_datetime(df_display['fecha']).dt.strftime('%Y-%m-%d')
        st.dataframe(df_display.sort_values('fecha', ascending=False))

# Tab de Análisis
with tab2:
    st.header("Análisis de Presupuesto")
    
    if df_presupuesto is not None and not df_presupuesto.empty:
        # Métricas principales
        total_ingresos = df_presupuesto[df_presupuesto['tipo'] == 'Ingreso']['monto'].sum()
        total_gastos = -df_presupuesto[df_presupuesto['tipo'] == 'Gasto']['monto'].sum()
        saldo = total_ingresos - total_gastos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ingresos", f"${total_ingresos:,.2f}")
        col2.metric("Total Gastos", f"${total_gastos:,.2f}")
        col3.metric("Saldo", f"${saldo:,.2f}")
        
        # Gráficos
        st.subheader("Distribución de Gastos por Categoría")
        gastos_categoria = df_presupuesto[df_presupuesto['tipo'] == 'Gasto'].groupby('categoria')['monto'].sum().abs()
        fig_pie = px.pie(
            values=gastos_categoria.values,
            names=gastos_categoria.index,
            title="Distribución de Gastos"
        )
        st.plotly_chart(fig_pie)
        
        # Evolución temporal
        st.subheader("Evolución Temporal")
        df_temp = df_presupuesto.copy()
        df_temp['fecha'] = pd.to_datetime(df_temp['fecha'])
        fig_line = px.line(
            df_temp.groupby(['fecha', 'tipo'])['monto'].sum().reset_index(),
            x='fecha',
            y='monto',
            color='tipo',
            title="Evolución de Ingresos y Gastos"
        )
        st.plotly_chart(fig_line)

# Tab de Reportes
with tab3:
    st.header("Reportes")
    
    if df_presupuesto is not None and not df_presupuesto.empty:
        # Comparación Presupuesto vs Realidad
        st.subheader("Comparación Presupuesto vs Realidad")
        
        df_comparacion = pd.DataFrame({
            'Categoría': df_categorias['categoria'],
            'Presupuesto Asignado': df_categorias['presupuesto_asignado'],
            'Gasto Real': [
                -df_presupuesto[
                    (df_presupuesto['categoria'] == cat) & 
                    (df_presupuesto['tipo'] == 'Gasto')
                ]['monto'].sum()
                for cat in df_categorias['categoria']
            ]
        })
        
        df_comparacion['Diferencia'] = df_comparacion['Presupuesto Asignado'] - df_comparacion['Gasto Real']
        df_comparacion['% Utilizado'] = (df_comparacion['Gasto Real'] / df_comparacion['Presupuesto Asignado'] * 100).fillna(0)
        
        st.dataframe(df_comparacion)
        
        # Gráfico de barras comparativo
        fig_comp = px.bar(
            df_comparacion,
            x='Categoría',
            y=['Presupuesto Asignado', 'Gasto Real'],
            title="Presupuesto vs Gasto Real por Categoría",
            barmode='group'
        )
        st.plotly_chart(fig_comp)