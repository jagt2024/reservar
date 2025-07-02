import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de la página
#st.set_page_config(
#    page_title="Estado Financiero - Gestión Conjuntos",
#    page_icon="💰",
#    layout="wide",
#    initial_sidebar_state="expanded"
#)

def load_credentials_from_toml():
    """Cargar credenciales desde el archivo secrets.toml"""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except FileNotFoundError:
        st.error("📁 Archivo secrets.toml no encontrado en .streamlit/")
        st.info("Crea el archivo `.streamlit/secrets.toml` con tus credenciales")
        return None, None
    except KeyError as e:
        st.error(f"🔑 Clave faltante en secrets.toml: {str(e)}")
        st.info("Verifica la estructura del archivo secrets.toml")
        return None, None
    except json.JSONDecodeError as e:
        st.error(f"📄 Error al parsear JSON en secrets.toml: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"❌ Error cargando credenciales: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(_creds):
    """Establecer conexión con Google Sheets"""
    try:
        scope = [
            'https://spreadsheets.google.com/feeds', 
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_info(_creds, scopes=scope)
        client = gspread.authorize(credentials)
    
        # Verificar la conexión intentando listar las hojas
        try:
            sheets = client.openall()
            st.success(f"✅ Conexión exitosa y disponible!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=300)
def load_data_from_sheets(_client, sheet_name, worksheet_name):
    """Cargar datos desde Google Sheets"""
    try:
        sheet = _client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Limpiar datos vacías
        df = df.dropna(how='all').reset_index(drop=True)
        
        # Verificar y limpiar columnas duplicadas
        if df.columns.duplicated().any():
            st.warning("⚠️ Se encontraron columnas duplicadas. Limpiando...")
            df = df.loc[:, ~df.columns.duplicated()]
        
        return df
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return None

def process_financial_data(df):
    """Procesar y limpiar datos financieros"""
    if df is None or df.empty:
        return None
    
    # Verificar columnas requeridas
    required_columns = ['Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha', 'Estado', 'Saldo_Pendiente']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"❌ Columnas faltantes en los datos: {', '.join(missing_columns)}")
        st.info("Columnas disponibles: " + ', '.join(df.columns.tolist()))
        return None
    
    # Convertir fecha si existe
    if 'Fecha' in df.columns:
        try:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            df['Año'] = df['Fecha'].dt.year
            df['Mes'] = df['Fecha'].dt.month
            df['Mes_Nombre'] = df['Fecha'].dt.strftime('%B')
            df['Periodo'] = df['Fecha'].dt.strftime('%Y-%m')
        except Exception as e:
            st.warning(f"⚠️ Error procesando fechas: {str(e)}")
    
    # Convertir columnas numéricas específicas
    numeric_columns = ['Monto', 'Saldo_Pendiente']
    for col in numeric_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            except Exception as e:
                st.warning(f"⚠️ Error procesando columna numérica {col}: {str(e)}")
    
    # Limpiar datos de texto
    text_columns = ['Tipo_Operacion', 'Unidad', 'Concepto', 'Estado']
    for col in text_columns:
        if col in df.columns:
            try:
                df[col] = df[col].astype(str).str.strip()
            except Exception as e:
                st.warning(f"⚠️ Error procesando columna de texto {col}: {str(e)}")
    
    return df

def create_financial_summary(df, filtros):
    """Crear resumen financiero"""
    if df is None or df.empty:
        return None
    
    # Aplicar filtros
    df_filtered = df.copy()
    
    if filtros['tipo_operacion'] != 'Todos':
        df_filtered = df_filtered[df_filtered['Tipo_Operacion'] == filtros['tipo_operacion']]
    
    if filtros['unidad'] != 'Todas':
        df_filtered = df_filtered[df_filtered['Unidad'] == filtros['unidad']]
    
    if filtros['periodo']:
        año, mes = filtros['periodo'].split('-')
        df_filtered = df_filtered[
            (df_filtered['Año'] == int(año)) & 
            (df_filtered['Mes'] == int(mes))
        ]
    
    if filtros['estado'] != 'Todos':
        df_filtered = df_filtered[df_filtered['Estado'] == filtros['estado']]
    
    # Calcular métricas financieras usando la columna Monto
    ingresos = df_filtered[df_filtered['Tipo_Operacion'] == 'Ingreso']['Monto'].sum()
    egresos = df_filtered[df_filtered['Tipo_Operacion'] == 'Egreso']['Monto'].sum()
    saldo_neto = ingresos - egresos
    
    # Calcular saldos pendientes
    saldo_pendiente_total = df_filtered['Saldo_Pendiente'].sum()
    
    # Crear resumen por concepto
    resumen_concepto = df_filtered.groupby(['Concepto', 'Tipo_Operacion']).agg({
        'Monto': 'sum',
        'Saldo_Pendiente': 'sum'
    }).reset_index()
    
    # Contar transacciones por separado
    conteo_transacciones = df_filtered.groupby(['Concepto', 'Tipo_Operacion']).size().reset_index(name='Num_Transacciones')
    
    # Combinar los resultados
    resumen_concepto = resumen_concepto.merge(conteo_transacciones, on=['Concepto', 'Tipo_Operacion'])
    resumen_concepto.rename(columns={
        'Monto': 'Monto_Total', 
        'Saldo_Pendiente': 'Saldo_Pendiente_Total'
    }, inplace=True)
    
    # Resumen por unidad
    resumen_unidad = df_filtered.groupby(['Unidad', 'Tipo_Operacion']).agg({
        'Monto': 'sum',
        'Saldo_Pendiente': 'sum'
    }).reset_index()
    
    # Resumen por estado
    resumen_estado = df_filtered.groupby(['Estado']).agg({
        'Monto': 'sum',
        'Saldo_Pendiente': 'sum'
    }).reset_index()
    
    return {
        'data_filtered': df_filtered,
        'total_ingresos': ingresos,
        'total_egresos': egresos,
        'saldo_neto': saldo_neto,
        'saldo_pendiente_total': saldo_pendiente_total,
        'resumen_concepto': resumen_concepto,
        'resumen_unidad': resumen_unidad,
        'resumen_estado': resumen_estado,
        'num_transacciones': len(df_filtered)
    }

def create_charts(summary):
    """Crear gráficos financieros"""
    charts = {}
    
    if summary:
        # Gráfico de barras por concepto
        if not summary['resumen_concepto'].empty:
            fig_bar = px.bar(
                summary['resumen_concepto'], 
                x='Concepto', 
                y='Monto_Total', 
                color='Tipo_Operacion',
                title='Ingresos y Egresos por Concepto',
                color_discrete_map={'Ingreso': 'green', 'Egreso': 'red'},
                text='Monto_Total'
            )
            fig_bar.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            fig_bar.update_layout(height=500, xaxis_tickangle=-45)
            charts['bar_concepto'] = fig_bar
        
        # Gráfico de barras por unidad
        if not summary['resumen_unidad'].empty:
            fig_bar_unidad = px.bar(
                summary['resumen_unidad'], 
                x='Unidad', 
                y='Monto', 
                color='Tipo_Operacion',
                title='Ingresos y Egresos por Unidad',
                color_discrete_map={'Ingreso': 'green', 'Egreso': 'red'}
            )
            fig_bar_unidad.update_layout(height=400)
            charts['bar_unidad'] = fig_bar_unidad
        
        # Gráfico de pastel para ingresos por concepto
        ingresos_concepto = summary['resumen_concepto'][
            summary['resumen_concepto']['Tipo_Operacion'] == 'Ingreso'
        ]
        if not ingresos_concepto.empty:
            fig_pie_ingresos = px.pie(
                ingresos_concepto, 
                values='Monto_Total', 
                names='Concepto',
                title='Distribución de Ingresos por Concepto',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie_ingresos.update_traces(textinfo='percent+label', textposition='outside')
            charts['pie_ingresos'] = fig_pie_ingresos
        
        # Gráfico de pastel para egresos por concepto
        egresos_concepto = summary['resumen_concepto'][
            summary['resumen_concepto']['Tipo_Operacion'] == 'Egreso'
        ]
        if not egresos_concepto.empty:
            fig_pie_egresos = px.pie(
                egresos_concepto, 
                values='Monto_Total', 
                names='Concepto',
                title='Distribución de Egresos por Concepto',
                color_discrete_sequence=px.colors.qualitative.Set1
            )
            fig_pie_egresos.update_traces(textinfo='percent+label', textposition='outside')
            charts['pie_egresos'] = fig_pie_egresos
        
        # Gráfico de estado de pagos
        if not summary['resumen_estado'].empty:
            fig_estado = px.bar(
                summary['resumen_estado'], 
                x='Estado', 
                y='Monto',
                title='Montos por Estado de Pago',
                color='Estado',
                color_discrete_sequence=px.colors.qualitative.Pastel1
            )
            fig_estado.update_layout(height=350)
            charts['bar_estado'] = fig_estado
        
        # Gráfico de saldos pendientes
        if not summary['resumen_estado'].empty and 'Saldo_Pendiente' in summary['resumen_estado'].columns:
            fig_pendiente = px.bar(
                summary['resumen_estado'], 
                x='Estado', 
                y='Saldo_Pendiente',
                title='Saldos Pendientes por Estado',
                color='Estado',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pendiente.update_layout(height=350)
            charts['bar_pendiente'] = fig_pendiente
    
    return charts

def informe_estado_main():
    st.title("💰 Estado Financiero - Gestión Conjuntos")
    st.markdown("---")
    
    # Sidebar para filtros
    st.sidebar.header("🔍 Filtros")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Conectar a Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Cargar datos
    with st.spinner("📊 Cargando datos financieros..."):
        df = load_data_from_sheets(client, "gestion-conjuntos", "Administracion_Financiera")
    
    if df is None:
        st.error("❌ No se pudieron cargar los datos")
        st.stop()
    
    # Procesar datos
    df = process_financial_data(df)
    
    if df is None or df.empty:
        st.error("❌ No hay datos disponibles para procesar")
        st.stop()
    
    # Mostrar información básica
    st.sidebar.info(f"📋 Total de registros: {len(df)}")
    
    # Filtros en sidebar
    tipos_operacion = ['Todos'] + sorted(list(df['Tipo_Operacion'].unique())) if 'Tipo_Operacion' in df.columns else ['Todos']
    tipo_operacion = st.sidebar.selectbox("🔄 Tipo de Operación", tipos_operacion)
    
    unidades = ['Todas'] + sorted(list(df['Unidad'].unique())) if 'Unidad' in df.columns else ['Todas']
    unidad = st.sidebar.selectbox("🏠 Unidad", unidades)
    
    # Filtro de estado
    estados = ['Todos'] + sorted(list(df['Estado'].unique())) if 'Estado' in df.columns else ['Todos']
    estado = st.sidebar.selectbox("📋 Estado", estados)
    
    # Filtro de periodo
    if 'Periodo' in df.columns:
        periodos = sorted(df['Periodo'].dropna().unique(), reverse=True)
        periodo = st.sidebar.selectbox("📅 Período (Año-Mes)", [''] + periodos)
    else:
        periodo = ''
    
    # Botón para actualizar
    if st.sidebar.button("🔄 Actualizar Datos", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    # Crear filtros
    filtros = {
        'tipo_operacion': tipo_operacion,
        'unidad': unidad,
        'periodo': periodo,
        'estado': estado
    }
    
    # Generar resumen financiero
    with st.spinner("📈 Generando estado financiero..."):
        summary = create_financial_summary(df, filtros)
    
    if not summary:
        st.warning("⚠️ No hay datos para mostrar con los filtros seleccionados")
        return
    
    # Mostrar métricas principales
    st.subheader("📊 Resumen Financiero")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "💚 Total Ingresos", 
            f"${summary['total_ingresos']:,.2f}",
            delta=None
        )
    
    with col2:
        st.metric(
            "💸 Total Egresos", 
            f"${summary['total_egresos']:,.2f}",
            delta=None
        )
    
    with col3:
        st.metric(
            "💰 Saldo Neto", 
            f"${summary['saldo_neto']:,.2f}",
            delta=None,
            delta_color="normal" if summary['saldo_neto'] >= 0 else "inverse"
        )
    
    with col4:
        st.metric(
            "⏳ Saldo Pendiente", 
            f"${summary['saldo_pendiente_total']:,.2f}",
            delta=None
        )
    
    with col5:
        st.metric(
            "📝 Transacciones", 
            summary['num_transacciones'],
            delta=None
        )
    
    # Mostrar gráficos
    st.subheader("📈 Análisis Gráfico")
    
    charts = create_charts(summary)
    
    if charts:
        # Gráfico principal por concepto
        if 'bar_concepto' in charts:
            st.plotly_chart(charts['bar_concepto'], use_container_width=True)
        
        # Fila de gráficos de pastel
        col1, col2 = st.columns(2)
        
        with col1:
            if 'pie_ingresos' in charts:
                st.plotly_chart(charts['pie_ingresos'], use_container_width=True)
        
        with col2:
            if 'pie_egresos' in charts:
                st.plotly_chart(charts['pie_egresos'], use_container_width=True)
        
        # Gráficos por unidad y estado
        col3, col4 = st.columns(2)
        
        with col3:
            if 'bar_unidad' in charts:
                st.plotly_chart(charts['bar_unidad'], use_container_width=True)
        
        with col4:
            if 'bar_estado' in charts:
                st.plotly_chart(charts['bar_estado'], use_container_width=True)
        
        # Gráfico de saldos pendientes
        if 'bar_pendiente' in charts:
            st.plotly_chart(charts['bar_pendiente'], use_container_width=True)
    
    # Tabla detallada
    st.subheader("📋 Detalle de Transacciones")
    
    # Mostrar datos filtrados
    if not summary['data_filtered'].empty:
        # Seleccionar columnas importantes para mostrar
        columns_to_show = ['Fecha', 'Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Estado', 'Saldo_Pendiente']
        # Verificar que las columnas existan en el DataFrame
        columns_to_show = [col for col in columns_to_show if col in summary['data_filtered'].columns]
        
        if columns_to_show:
            st.dataframe(
                summary['data_filtered'][columns_to_show].sort_values(
                    'Fecha' if 'Fecha' in columns_to_show else columns_to_show[0], 
                    ascending=False
                ),
                use_container_width=True,
                height=400
            )
        else:
            st.dataframe(summary['data_filtered'], use_container_width=True, height=400)
        
        # Opción para descargar
        csv = summary['data_filtered'].to_csv(index=False)
        st.download_button(
            label="📥 Descargar datos como CSV",
            data=csv,
            file_name=f"estado_financiero_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("ℹ️ No hay transacciones para mostrar con los filtros seleccionados")
    
    # Resumen por concepto y análisis adicional
    if not summary['resumen_concepto'].empty:
        st.subheader("📊 Análisis Detallado")
        
        # Tabs para diferentes análisis
        tab1, tab2, tab3 = st.tabs(["💡 Por Concepto", "🏠 Por Unidad", "📋 Por Estado"])
        
        with tab1:
            st.markdown("### Resumen por Concepto")
            # Crear tabla pivot para conceptos
            pivot_concepto = summary['resumen_concepto'].pivot(
                index='Concepto', 
                columns='Tipo_Operacion', 
                values='Monto_Total'
            ).fillna(0)
            
            if not pivot_concepto.empty:
                # Agregar columnas calculadas
                if 'Ingreso' in pivot_concepto.columns and 'Egreso' in pivot_concepto.columns:
                    pivot_concepto['Saldo'] = pivot_concepto['Ingreso'] - pivot_concepto['Egreso']
                elif 'Ingreso' in pivot_concepto.columns:
                    pivot_concepto['Saldo'] = pivot_concepto['Ingreso']
                elif 'Egreso' in pivot_concepto.columns:
                    pivot_concepto['Saldo'] = -pivot_concepto['Egreso']
                
                st.dataframe(pivot_concepto.style.format("${:,.2f}"), use_container_width=True)
        
        with tab2:
            st.markdown("### Resumen por Unidad")
            if not summary['resumen_unidad'].empty:
                pivot_unidad = summary['resumen_unidad'].pivot(
                    index='Unidad', 
                    columns='Tipo_Operacion', 
                    values='Monto'
                ).fillna(0)
                
                if not pivot_unidad.empty:
                    if 'Ingreso' in pivot_unidad.columns and 'Egreso' in pivot_unidad.columns:
                        pivot_unidad['Saldo'] = pivot_unidad['Ingreso'] - pivot_unidad['Egreso']
                    
                    st.dataframe(pivot_unidad.style.format("${:,.2f}"), use_container_width=True)
                    
                    # Mostrar saldos pendientes por unidad si existe
                    saldo_unidad = summary['resumen_unidad'].groupby('Unidad')['Saldo_Pendiente'].sum().reset_index()
                    if not saldo_unidad.empty and saldo_unidad['Saldo_Pendiente'].sum() > 0:
                        st.markdown("#### Saldos Pendientes por Unidad")
                        st.dataframe(saldo_unidad.style.format({"Saldo_Pendiente": "${:,.2f}"}), use_container_width=True)
        
        with tab3:
            st.markdown("### Resumen por Estado")
            if not summary['resumen_estado'].empty:
                st.dataframe(
                    summary['resumen_estado'].style.format({
                        "Monto": "${:,.2f}",
                        "Saldo_Pendiente": "${:,.2f}"
                    }), 
                    use_container_width=True
                )

#if __name__ == "__main__":
#    main()