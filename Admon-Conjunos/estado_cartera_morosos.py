import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime
import calendar
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de la página
#st.set_page_config(
#    page_title="Estado de Cartera - Morosos",
#    page_icon="🏠",
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

#@st.cache_data(ttl=300)
def load_morosos_data(client):
    """Cargar datos de morosos desde Google Sheets"""
    try:
        # Abrir el archivo "gestion-conjuntos"
        spreadsheet = client.open("gestion-conjuntos")
        
        # Acceder a la hoja "gestion-morosos"
        worksheet = spreadsheet.worksheet("gestion_morosos")
        
        # Obtener todos los datos
        data = worksheet.get_all_records()
        
        if not data:
            st.warning("⚠️ No se encontraron datos en la hoja 'gestion-morosos'")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Limpiar datos vacíos
        df = df.dropna(how='all')
        
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ No se encontró el archivo 'gestion-conjuntos'")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error("❌ No se encontró la hoja 'gestion-morosos'")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return pd.DataFrame()

def process_morosos_data(df, selected_month, selected_year):
    """Procesar datos de morosos y filtrar por criterios"""
    if df.empty:
        return pd.DataFrame()
    
    try:
        # Convertir columnas numéricas con formato de peso colombiano
        numeric_columns = ['Dias_Mora', 'Saldo_Pendiente', 'Interes_Mora', 'Saldo_Total']
        for col in numeric_columns:
            if col in df.columns:
                if col == 'Dias_Mora':
                    # Días de mora probablemente ya sea numérico
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                else:
                    # Para columnas monetarias, usar la función de conversión
                    df[col] = df[col].apply(convert_currency_to_numeric)
        
        # Convertir fechas si existe columna de fecha
        date_columns = ['Fecha_Registro']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Filtrar por días de mora > 30
        if 'Dias_Mora' in df.columns:
            df_filtered = df[df['Dias_Mora'] > 30].copy()
        else:
            st.warning("⚠️ No se encontró la columna 'Dias_Mora'")
            df_filtered = df.copy()
        
        # Filtrar por mes y año si existe columna de fecha
        date_col = None
        for col in date_columns:
            if col in df_filtered.columns and not df_filtered[col].isna().all():
                date_col = col
                break
        
        if date_col:
            df_filtered = df_filtered[
                (df_filtered[date_col].dt.month <= selected_month) &
                (df_filtered[date_col].dt.year == selected_year)
            ]
        
        return df_filtered
        
    except Exception as e:
        st.error(f"❌ Error procesando datos: {str(e)}")
        return pd.DataFrame()

def convert_currency_to_numeric(value):
    """Convertir formato de peso colombiano a número"""
    if pd.isna(value) or value == '' or value is None:
        return 0
    
    # Si ya es un número, retornarlo
    if isinstance(value, (int, float)):
        return float(value)
    
    # Si es string, limpiar formato de peso colombiano
    if isinstance(value, str):
        # Remover símbolo de peso, espacios, puntos de miles
        cleaned = value.replace('$', '').replace(' ', '').replace('.', '').replace(',', '')
        try:
            return float(cleaned)
        except ValueError:
            return 0
    
    return 0
        
def has_valid_numeric_data(df, column):
    """Verificar si una columna tiene datos numéricos válidos (> 0)"""
    if column not in df.columns:
        return False
    
    # Convertir a numérico si es necesario
    if df[column].dtype == 'object':
        numeric_values = df[column].apply(convert_currency_to_numeric)
    else:
        numeric_values = pd.to_numeric(df[column], errors='coerce')
    
    # Verificar si hay valores válidos > 0
    return (numeric_values > 0).any()

def create_summary_cards(df):
    """Crear tarjetas de resumen mejoradas"""
    if df.empty:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_morosos = len(df)
        st.metric(
            label="🏠 Total Unidades Morosas", 
            value=total_morosos
        )
    
    with col2:
        # Priorizar Saldo_Total si está disponible y tiene datos válidos
        if has_valid_numeric_data(df, 'Saldo_Total'):
            total_saldo = df['Saldo_Total'].sum()
            st.metric(
                label="💰 Saldo Total", 
                value=f"${total_saldo:,.0f}"
            )
        elif has_valid_numeric_data(df, 'Saldo_Pendiente'):
            total_pendiente = df['Saldo_Pendiente'].sum()
            st.metric(
                label="💳 Saldo Pendiente", 
                value=f"${total_pendiente:,.0f}"
            )
        else:
            st.metric(label="💰 Saldo Total", value="N/A")
    
    with col3:
        if has_valid_numeric_data(df, 'Dias_Mora'):
            promedio_mora = df['Dias_Mora'].mean()
            st.metric(
                label="📅 Promedio Días Mora", 
                value=f"{promedio_mora:.0f} días"
            )
        else:
            st.metric(label="📅 Promedio Días Mora", value="N/A")
    
    with col4:
        if has_valid_numeric_data(df, 'Interes_Mora'):
            total_interes = df['Interes_Mora'].sum()
            st.metric(
                label="📈 Total Interés Mora", 
                value=f"${total_interes:,.0f}"
            )
        elif has_valid_numeric_data(df, 'Dias_Mora'):
            max_mora = df['Dias_Mora'].max()
            st.metric(
                label="⚠️ Máximos Días Mora", 
                value=f"{max_mora:.0f} días"
            )
        else:
            st.metric(label="📈 Total Interés Mora", value="N/A")

def create_charts(df):
    """Crear gráficos de análisis"""
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribución por Días de Mora")
        if has_valid_numeric_data(df, 'Dias_Mora') and 'Apartamento/Casa' in df.columns:
            # Crear rangos de mora
            df['rango_mora'] = pd.cut(
                df['Dias_Mora'], 
                bins=[30, 60, 90, 180, 365, float('inf')], 
                labels=['31-60 días', '61-90 días', '91-180 días', '181-365 días', '+365 días']
            )
            
            mora_counts = df['rango_mora'].value_counts()
            
            fig = px.bar(
                x=mora_counts.index, 
                y=mora_counts.values,
                labels={'x': 'Rango de Mora', 'y': 'Cantidad de Unidades'},
                color=mora_counts.values,
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("💰 Top 10 - Mayor Saldo")
        if has_valid_numeric_data(df, 'Saldo_Total') and 'Apartamento/Casa' in df.columns:
            top_deuda = df.nlargest(10, 'Saldo_Total')[['Apartamento/Casa', 'Saldo_Total']]
            
            fig = px.bar(
                top_deuda, 
                x='Apartamento/Casa', 
                y='Saldo_Total',
                labels={'Apartamento/Casa': 'Apartamento/Casa', 'Saldo_Total': 'Saldo Total'},
                color='Saldo_Total',
                color_continuous_scale='Oranges'
            )
            fig.update_layout(height=400)
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        elif has_valid_numeric_data(df, 'Saldo_Pendiente') and 'Apartamento/Casa' in df.columns:
            top_deuda = df.nlargest(10, 'Saldo_Pendiente')[['Apartamento/Casa', 'Saldo_Pendiente']]
            
            fig = px.bar(
                top_deuda, 
                x='Apartamento/Casa', 
                y='Saldo_Pendiente',
                labels={'Apartamento/Casa': 'Apartamento/Casa', 'Saldo_Pendiente': 'Saldo Pendiente'},
                color='Saldo_Pendiente',
                color_continuous_scale='Oranges'
            )
            fig.update_layout(height=400)
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

def display_detailed_table(df):
    """Mostrar tabla detallada de morosos con columnas mejoradas"""
    if df.empty:
        st.warning("⚠️ No hay datos para mostrar")
        return
    
    st.subheader("📋 Detalle de Cartera Morosa")
    
    # Configurar columnas a mostrar (orden de prioridad actualizado)
    priority_columns = [
        'Apartamento/Casa',
        'Propietario', 
        'Dias_Mora',
        'Saldo_Pendiente',
        'Interes_Mora',  # Agregado explícitamente
        'Saldo_Total'    # Agregado explícitamente
    ]
    
    # Inicializar lista de columnas a mostrar
    display_columns = []
    
    # Agregar columnas prioritarias si existen
    for col in priority_columns:
        if col in df.columns:
            display_columns.append(col)
    
    # Agregar columnas de conceptos de deuda si existen (evitando duplicados)
    concepto_columns = [col for col in df.columns 
                       if ('concepto' in col.lower() in col.lower()) 
                       and col not in display_columns]
    display_columns.extend(concepto_columns)
    
    # Eliminar duplicados manteniendo el orden
    display_columns = list(dict.fromkeys(display_columns))
    
    # Filtrar solo columnas que existen y no están completamente vacías
    display_columns = [col for col in display_columns 
                      if col in df.columns and not df[col].isna().all()]
    
    if display_columns:
        # Verificar si hay columnas duplicadas y mostrar información de debug
        if len(display_columns) != len(set(display_columns)):
            st.warning("⚠️ Se detectaron columnas duplicadas. Se eliminarán automáticamente.")
            with st.expander("🔍 Debug - Columnas detectadas"):
                st.write("**Columnas antes de limpiar:**", display_columns)
                st.write("**Columnas disponibles en datos:**", list(df.columns))
        
        # Asegurar que no hay duplicados
        display_columns = list(dict.fromkeys(display_columns))
        
        # Verificar que todas las columnas existen
        valid_columns = [col for col in display_columns if col in df.columns]
        
        if not valid_columns:
            st.error("❌ No se encontraron columnas válidas para mostrar")
            return
        
        df_display = df[valid_columns].copy()
        
        # Formatear columnas numéricas - Iterar sobre cada columna individualmente
        money_columns = ['saldo', 'interes', 'valor', 'deuda', 'total']
        for col in df_display.columns:
            # Verificar si la columna tiene datos numéricos
            if pd.api.types.is_numeric_dtype(df_display[col]):
                # Verificar si es una columna monetaria
                if any(keyword in col.lower() for keyword in money_columns):
                    df_display[col] = df_display[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
        
        # Ordenar por días de mora descendente
        if 'Dias_Mora' in df_display.columns:
            # Crear una copia temporal para ordenar por valores numéricos antes del formateo
            df_temp = df[valid_columns].copy()
            df_temp = df_temp.sort_values('Dias_Mora', ascending=False)
            
            # Aplicar formateo después del ordenamiento
            for col in df_temp.columns:
                if pd.api.types.is_numeric_dtype(df_temp[col]):
                    if any(keyword in col.lower() for keyword in money_columns):
                        df_temp[col] = df_temp[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
            
            df_display = df_temp
        
        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )
        
        # Botón de descarga - usar datos originales sin formatear
        df_download = df[valid_columns].copy()
        if 'Dias_Mora' in df_download.columns:
            df_download = df_download.sort_values('Dias_Mora', ascending=False)
        
        csv = df_download.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Reporte CSV",
            data=csv,
            file_name=f"cartera_morosos_{selected_month}_{selected_year}.csv",
            mime="text/csv"
        )
    else:
        st.error("❌ No se pudieron identificar las columnas necesarias")

def create_additional_analysis(df):
    """Crear análisis financiero detallado mejorado"""
    if df.empty:
        return
    
    st.markdown("---")
    st.subheader("📈 Análisis Financiero Detallado")
    
    # Crear métricas adicionales en fila superior
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if has_valid_numeric_data(df, 'Saldo_Pendiente'):
            total_pendiente = df['Saldo_Pendiente'].sum()
            st.metric(
                label="💳 Saldo Pendiente Total", 
                value=f"${total_pendiente:,.0f}"
            )
        else:
            st.metric(label="💳 Saldo Pendiente Total", value="N/A")
    
    with col2:
        if has_valid_numeric_data(df, 'Interes_Mora'):
            promedio_interes = df['Interes_Mora'].mean()
            st.metric(
                label="📊 Promedio Interés Mora", 
                value=f"${promedio_interes:,.0f}"
            )
        else:
            st.metric(label="📊 Promedio Interés Mora", value="N/A")
    
    with col3:
        if has_valid_numeric_data(df, 'Saldo_Total') and has_valid_numeric_data(df, 'Saldo_Pendiente'):
            total_saldo = df['Saldo_Total'].sum()
            total_pendiente = df['Saldo_Pendiente'].sum()
            if total_saldo > 0:
                porcentaje_pendiente = (total_pendiente / total_saldo) * 100
                st.metric(
                    label="📉 % Pendiente vs Total", 
                    value=f"{porcentaje_pendiente:.1f}%"
                )
            else:
                st.metric(label="📉 % Pendiente vs Total", value="N/A")
        else:
            st.metric(label="📉 % Pendiente vs Total", value="N/A")
    
    with col4:
        if has_valid_numeric_data(df, 'Interes_Mora') and has_valid_numeric_data(df, 'Saldo_Total'):
            total_interes = df['Interes_Mora'].sum()
            total_saldo = df['Saldo_Total'].sum()
            if total_saldo > 0:
                porcentaje_interes = (total_interes / total_saldo) * 100
                st.metric(
                    label="📈 % Interés vs Total", 
                    value=f"{porcentaje_interes:.1f}%"
                )
            else:
                st.metric(label="📈 % Interés vs Total", value="N/A")
        else:
            st.metric(label="📈 % Interés vs Total", value="N/A")
    
    # Gráfico de composición de deuda
    if has_valid_numeric_data(df, 'Saldo_Pendiente') and has_valid_numeric_data(df, 'Interes_Mora'):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🥧 Composición de la Deuda")
            total_pendiente = df['Saldo_Pendiente'].sum()
            total_interes = df['Interes_Mora'].sum()
            
            if total_pendiente + total_interes > 0:
                fig = px.pie(
                    values=[total_pendiente, total_interes],
                    names=['Saldo Pendiente', 'Intereses de Mora'],
                    title="Distribución de la Deuda Total"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos suficientes para mostrar la composición de deuda")
        
        with col2:
            st.subheader("📊 Saldo vs Interés por Unidad")
            if 'Apartamento/Casa' in df.columns and has_valid_numeric_data(df, 'Saldo_Total'):
                # Tomar los top 10 por saldo total
                top_units = df.nlargest(10, 'Saldo_Total')
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Saldo Pendiente',
                    x=top_units['Apartamento/Casa'],
                    y=top_units['Saldo_Pendiente'],
                    marker_color='lightblue'
                ))
                fig.add_trace(go.Bar(
                    name='Interés Mora',
                    x=top_units['Apartamento/Casa'],
                    y=top_units['Interes_Mora'],
                    marker_color='salmon'
                ))
                
                fig.update_layout(
                    barmode='stack',
                    title="Top 10 - Composición de Deuda por Unidad",
                    xaxis_title="Apartamento/Casa",
                    yaxis_title="Valor ($)",
                    height=400
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos suficientes para mostrar el gráfico por unidad")
    else:
        st.info("No hay datos suficientes para mostrar el análisis de composición de deuda")

# ==================== INTERFAZ PRINCIPAL ====================

st.title("🏠 Estado de Cartera de Morosos")
st.markdown("---")

# Sidebar para filtros
with st.sidebar:
    st.header("🔧 Filtros de Consulta")
    
    # Selección de mes y año
    current_year = datetime.now().year
    selected_year = st.selectbox(
        "📅 Seleccionar Año",
        options=list(range(current_year - 2, current_year + 1)),
        index=len(list(range(current_year - 2, current_year + 1))) - 1
    )
    
    selected_month = st.selectbox(
        "📅 Seleccionar Mes",
        options=list(range(1, 13)),
        format_func=lambda x: calendar.month_name[x],
        index=datetime.now().month - 1
    )
    
    st.markdown("---")
    st.info("📋 **Criterios de Filtro:**\n- Días de mora > 30\n- Mes y año seleccionados")

# Cargar credenciales y establecer conexión
with st.spinner("🔄 Conectando a Google Sheets..."):
    creds, config = load_credentials_from_toml()
    
    if creds:
        client = get_google_sheets_connection(creds)
        
        if client:
            # Cargar datos
            with st.spinner("📊 Cargando datos de morosos..."):
                df_morosos = load_morosos_data(client)
                
                if not df_morosos.empty:
                    # Mostrar información de las columnas disponibles
                    with st.expander("ℹ️ Información de Datos"):
                        st.write("**Columnas disponibles:**")
                        st.write(list(df_morosos.columns))
                        st.write(f"**Total de registros:** {len(df_morosos)}")
                    
                    # Procesar datos
                    df_filtered = process_morosos_data(df_morosos, selected_month, selected_year)
                    
                    if not df_filtered.empty:
                        st.success(f"✅ Se encontraron {len(df_filtered)} unidades morosas para {calendar.month_name[selected_month]} {selected_year}")
                        
                        # Mostrar tarjetas de resumen
                        create_summary_cards(df_filtered)
                        
                        st.markdown("---")
                        
                        # Mostrar gráficos
                        create_charts(df_filtered)
                        
                        # Mostrar análisis adicional
                        create_additional_analysis(df_filtered)
                        
                        st.markdown("---")
                        
                        # Mostrar tabla detallada
                        display_detailed_table(df_filtered)
                        
                    else:
                        st.warning(f"⚠️ No se encontraron morosos con más de 30 días para {calendar.month_name[selected_month]} {selected_year}")
                        
                        # Mostrar datos sin filtrar para debug
                        if not df_morosos.empty:
                            with st.expander("🔍 Ver todos los datos (sin filtros)"):
                                st.dataframe(df_morosos.head(10))
                else:
                    st.error("❌ No se pudieron cargar los datos de morosos")
        else:
            st.error("❌ No se pudo establecer conexión con Google Sheets")
    else:
        st.error("❌ No se pudieron cargar las credenciales")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        📊 Estado de Cartera de Morosos - Análisis Financiero Completo
    </div>
    """, 
    unsafe_allow_html=True
)

