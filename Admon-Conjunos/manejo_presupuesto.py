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
import re

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión de Presupuesto - Conjuntos",
#    page_icon="🏢",
#    layout="wide",
#    initial_sidebar_state="expanded"
#)

def clean_currency_value(value):
    """Limpiar y convertir valores de moneda a float"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    # Convertir a string si no lo es
    str_value = str(value).strip()
    
    # Eliminar símbolos de moneda, espacios y caracteres especiales
    # Mantener solo números, puntos y comas
    cleaned = re.sub(r'[^\d.,\-]', '', str_value)
    
    # Si está vacío después de limpiar, retornar 0
    if not cleaned:
        return 0.0
    
    try:
        # Casos específicos de formato
        if ',' in cleaned and '.' in cleaned:
            # Formato mixto: determinar cuál es el separador decimal
            last_comma = cleaned.rfind(',')
            last_dot = cleaned.rfind('.')
            
            if last_comma > last_dot:
                # La coma es el separador decimal: 1.234.567,89
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # El punto es el separador decimal: 1,234,567.89
                cleaned = cleaned.replace(',', '')
        
        elif ',' in cleaned:
            # Solo comas
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probablemente separador decimal: 1234,50
                cleaned = cleaned.replace(',', '.')
            else:
                # Separador de miles: 1,234,567
                cleaned = cleaned.replace(',', '')
        
        elif '.' in cleaned:
            # Solo puntos - formato colombiano típico
            parts = cleaned.split('.')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Solo un punto con 1-2 decimales: 1234.50
                pass  # Ya está en formato correcto
            else:
                # Múltiples puntos como separadores de miles: 30.000.000
                # Eliminar todos los puntos excepto si el último tiene 1-2 dígitos
                if len(parts[-1]) <= 2 and len(parts) > 1:
                    # Último segmento parece decimal
                    cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
                else:
                    # Todos son separadores de miles
                    cleaned = cleaned.replace('.', '')
        
        return float(cleaned)
        
    except ValueError:
        # Debug: mostrar qué valor causó el error
        st.warning(f"⚠️ No se pudo convertir el valor: '{value}' -> '{cleaned}'")
        return 0.0

def format_currency(value):
    """Formatear número como moneda colombiana"""
    try:
        return f"${value:,.0f}".replace(',', '.')
    except:
        return "$0"
    
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
            st.success(f"✅ Conexión exitosa! y disponible")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=300)
def load_existing_data(_client):
    """Cargar datos existentes para obtener información de referencia"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Presupuesto")
        data = worksheet.get_all_records()
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Limpiar y convertir valores numéricos
        numeric_columns = ['Valor_Presupuestado', 'Valor_Ejecutado', 'Saldo']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].apply(clean_currency_value)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return pd.DataFrame()

def create_budget_sheet(_client):
    """Crear la hoja de presupuesto si no existe"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        
        # Intentar acceder a la hoja Presupuesto
        try:
            worksheet = spreadsheet.worksheet("Presupuesto")
            st.info("ℹ️ La hoja 'Presupuesto' ya existe")
        except gspread.WorksheetNotFound:
            # Crear la hoja si no existe
            worksheet = spreadsheet.add_worksheet(title="Presupuesto", rows="1000", cols="20")
            
            # Definir las columnas del presupuesto
            headers = [
                'ID', 'Fecha_Creacion', 'Nombre_Conjunto', 'Periodo', 'Categoria',
                'Subcategoria', 'Concepto', 'Descripcion', 'Valor_Presupuestado',
                'Valor_Ejecutado', 'Saldo', 'Estado', 'Responsable', 'Fecha_Ejecucion',
                'Observaciones', 'Torre_Bloque', 'Unidad_Apartamento', 'Tipo_Gasto',
                'Prioridad', 'Fecha_Actualizacion'
            ]
            
            # Insertar encabezados
            worksheet.insert_row(headers, 1)
            
            # Formatear encabezados
            worksheet.format('A1:T1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.8},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            st.success("✅ Hoja 'Presupuesto' creada exitosamente")
        
        return worksheet
        
    except Exception as e:
        st.error(f"❌ Error creando/accediendo a la hoja: {str(e)}")
        return None

def save_budget_item(_client, budget_data):
    """Guardar un ítem de presupuesto en Google Sheets"""
    try:
        worksheet = create_budget_sheet(_client)
        if not worksheet:
            return False
        
        # Generar ID único
        existing_data = worksheet.get_all_records()
        new_id = len(existing_data) + 1
        
        # Preparar los datos
        row_data = [
            new_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            budget_data['nombre_conjunto'],
            budget_data['periodo'],
            budget_data['categoria'],
            budget_data['subcategoria'],
            budget_data['concepto'],
            budget_data['descripcion'],
            budget_data['valor_presupuestado'],
            budget_data.get('valor_ejecutado', 0),
            budget_data['valor_presupuestado'] - budget_data.get('valor_ejecutado', 0),
            budget_data.get('estado', 'Pendiente'),
            budget_data['responsable'],
            budget_data.get('fecha_ejecucion', ''),
            budget_data.get('observaciones', ''),
            budget_data.get('torre_bloque', ''),
            budget_data.get('unidad_apartamento', ''),
            budget_data['tipo_gasto'],
            budget_data['prioridad'],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        # Insertar la fila
        worksheet.append_row(row_data)
        
        st.success(f"✅ Ítem de presupuesto guardado exitosamente (ID: {new_id})")
        return True
        
    except Exception as e:
        st.error(f"❌ Error guardando el ítem: {str(e)}")
        return False

def update_budget_item(_client, item_id, updated_data):
    """Actualizar un ítem de presupuesto existente"""
    try:
        worksheet = create_budget_sheet(_client)
        if not worksheet:
            return False
        
        # Buscar la fila por ID
        try:
            # Obtener todos los datos para encontrar la fila correcta
            all_data = worksheet.get_all_records()
            row_num = None
            
            for i, row in enumerate(all_data, start=2):  # start=2 porque la fila 1 son headers
                if str(row.get('ID', '')) == str(item_id):
                    row_num = i
                    break
            
            if row_num is None:
                st.error(f"❌ No se encontró el ítem con ID: {item_id}")
                return False
                
        except Exception as e:
            st.error(f"❌ Error buscando el ítem: {str(e)}")
            return False
        
        # Preparar todas las actualizaciones en un batch
        # Definir el rango y los valores
        update_range = f'E{row_num}:T{row_num}'  # Desde columna E hasta T
        
        # Preparar los valores en el orden correcto según las columnas
        values = [
            updated_data['categoria'],                    # E - Categoria
            updated_data['subcategoria'],                 # F - Subcategoria  
            updated_data['concepto'],                     # G - Concepto
            updated_data['descripcion'],                  # H - Descripcion
            updated_data['valor_presupuestado'],          # I - Valor_Presupuestado
            updated_data.get('valor_ejecutado', 0),       # J - Valor_Ejecutado
            updated_data['valor_presupuestado'] - updated_data.get('valor_ejecutado', 0),  # K - Saldo
            updated_data.get('estado', 'Pendiente'),      # L - Estado
            updated_data['responsable'],                  # M - Responsable
            updated_data.get('fecha_ejecucion', ''),      # N - Fecha_Ejecucion
            updated_data.get('observaciones', ''),        # O - Observaciones
            '',  # P - Torre_Bloque (no actualizable en este form)
            '',  # Q - Unidad_Apartamento (no actualizable en este form)
            '',  # R - Tipo_Gasto (no actualizable en este form)
            updated_data['prioridad'],                    # S - Prioridad
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # T - Fecha_Actualizacion
        ]
        
        # Actualizar todo el rango de una vez
        worksheet.update(update_range, [values])
        
        st.success(f"✅ Ítem {item_id} actualizado exitosamente")
        return True
        
    except Exception as e:
        st.error(f"❌ Error actualizando el ítem: {str(e)}")
        return False

def presupuesto_main():
    st.title("🏢 Sistema de Gestión de Presupuesto")
    st.markdown("### Administración de Presupuestos para Conjuntos de Apartamentos y Condominios")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("📋 Menú de Navegación")
    option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["🏠 Dashboard", "➕ Crear Presupuesto", "📝 Editar Presupuesto", "📊 Reportes", "⚙️ Configuración"]
    )
    
    if option == "🏠 Dashboard":
        show_dashboard(client)
    elif option == "➕ Crear Presupuesto":
        create_budget_form(client)
    elif option == "📝 Editar Presupuesto":
        edit_budget_form(client)
    elif option == "📊 Reportes":
        show_reports(client)
    elif option == "⚙️ Configuración":
        show_configuration(client)

def show_dashboard(client):
    """Mostrar el dashboard principal"""
    st.header("📊 Dashboard de Presupuesto")
    
    # Cargar datos existentes
    df = load_existing_data(client)
    
    if df.empty:
        st.info("📋 No hay datos de presupuesto disponibles. Crea tu primer ítem de presupuesto.")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_presupuestado = df['Valor_Presupuestado'].sum()
        st.metric("💰 Total Presupuestado", format_currency(total_presupuestado))
    
    with col2:
        total_ejecutado = df['Valor_Ejecutado'].sum()
        st.metric("💸 Total Ejecutado", format_currency(total_ejecutado))
    
    with col3:
        saldo_total = total_presupuestado - total_ejecutado
        st.metric("💵 Saldo Disponible", format_currency(saldo_total))
    
    with col4:
        porcentaje_ejecucion = (total_ejecutado / total_presupuestado * 100) if total_presupuestado > 0 else 0
        st.metric("📈 % Ejecución", f"{porcentaje_ejecucion:.1f}%")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Presupuesto por Categoría")
        categoria_data = df.groupby('Categoria')['Valor_Presupuestado'].sum().reset_index()
        fig = px.pie(categoria_data, values='Valor_Presupuestado', names='Categoria', 
                    title="Distribución del Presupuesto")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📈 Estado de Ejecución")
        estado_data = df.groupby('Estado').size().reset_index(name='Cantidad')
        fig = px.bar(estado_data, x='Estado', y='Cantidad', 
                    title="Ítems por Estado")
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabla resumen
    st.subheader("📋 Resumen de Presupuesto")
    # Formatear valores para mostrar
    display_df = df.copy()
    display_df['Valor_Presupuestado'] = display_df['Valor_Presupuestado'].apply(format_currency)
    display_df['Valor_Ejecutado'] = display_df['Valor_Ejecutado'].apply(format_currency)
    display_df['Saldo'] = display_df['Saldo'].apply(format_currency)
    
    st.dataframe(display_df[['Concepto', 'Categoria', 'Valor_Presupuestado', 'Valor_Ejecutado', 'Saldo', 'Estado', 'Responsable']], 
                use_container_width=True)

def create_budget_form(client):
    """Formulario para crear nuevo ítem de presupuesto"""
    st.header("➕ Crear Nuevo Ítem de Presupuesto")
    
    with st.form("budget_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_conjunto = st.text_input("🏢 Nombre del Conjunto*", placeholder="Ej: Conjunto Los Robles")
            periodo = st.selectbox("📅 Período*", [
                f"{datetime.now().year}",
                f"{datetime.now().year - 1}",
                f"{datetime.now().year + 1}"
            ])
            categoria = st.selectbox("📂 Categoría*", [
                "Mantenimiento", "Servicios Públicos", "Seguridad", "Aseo", 
                "Administración", "Reparaciones", "Mejoras", "Otros"
            ])
            subcategoria = st.text_input("📋 Subcategoría", placeholder="Ej: Mantenimiento Ascensores")
            concepto = st.text_input("📝 Concepto*", placeholder="Ej: Mantenimiento mensual ascensores")
        
        with col2:
            descripcion = st.text_area("📄 Descripción detallada")
            valor_presupuestado = st.number_input("💰 Valor Presupuestado*", min_value=0.0, step=1000.0)
            tipo_gasto = st.selectbox("🏷️ Tipo de Gasto*", ["Fijo", "Variable", "Extraordinario"])
            prioridad = st.selectbox("⚡ Prioridad*", ["Alta", "Media", "Baja"])
            responsable = st.text_input("👤 Responsable*", placeholder="Nombre del responsable")
        
        # Campos adicionales
        st.subheader("📍 Información Adicional (Opcional)")
        col3, col4 = st.columns(2)
        
        with col3:
            torre_bloque = st.text_input("🏗️ Torre/Bloque", placeholder="Ej: Torre A")
            unidad_apartamento = st.text_input("🏠 Unidad/Apartamento", placeholder="Ej: Apto 101")
        
        with col4:
            observaciones = st.text_area("📝 Observaciones")
        
        submitted = st.form_submit_button("💾 Guardar Ítem de Presupuesto", type="primary")
        
        if submitted:
            # Validaciones
            if not all([nombre_conjunto, categoria, concepto, valor_presupuestado > 0, tipo_gasto, prioridad, responsable]):
                st.error("⚠️ Por favor completa todos los campos obligatorios (*)")
            else:
                budget_data = {
                    'nombre_conjunto': nombre_conjunto,
                    'periodo': periodo,
                    'categoria': categoria,
                    'subcategoria': subcategoria,
                    'concepto': concepto,
                    'descripcion': descripcion,
                    'valor_presupuestado': valor_presupuestado,
                    'tipo_gasto': tipo_gasto,
                    'prioridad': prioridad,
                    'responsable': responsable,
                    'torre_bloque': torre_bloque,
                    'unidad_apartamento': unidad_apartamento,
                    'observaciones': observaciones
                }
                
                if save_budget_item(client, budget_data):
                    st.balloons()
                    st.rerun()

def edit_budget_form(client):
    """Formulario para editar ítem de presupuesto existente"""
    st.header("📝 Editar Ítem de Presupuesto")
    
    # Cargar datos existentes
    df = load_existing_data(client)
    
    if df.empty:
        st.info("📋 No hay ítems de presupuesto para editar.")
        return
    
    # Selector de ítem
    items_options = [f"ID {row['ID']} - {row['Concepto']}" for _, row in df.iterrows()]
    selected_item = st.selectbox("Selecciona el ítem a editar:", items_options)
    
    if selected_item:
        item_id = int(selected_item.split(' ')[1])
        item_data = df[df['ID'] == item_id].iloc[0]
        
        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                categoria = st.selectbox("📂 Categoría*", [
                    "Mantenimiento", "Servicios Públicos", "Seguridad", "Aseo", 
                    "Administración", "Reparaciones", "Mejoras", "Otros"
                ], index=["Mantenimiento", "Servicios Públicos", "Seguridad", "Aseo", 
                         "Administración", "Reparaciones", "Mejoras", "Otros"].index(item_data['Categoria']) if item_data['Categoria'] in ["Mantenimiento", "Servicios Públicos", "Seguridad", "Aseo", "Administración", "Reparaciones", "Mejoras", "Otros"] else 0)
                
                subcategoria = st.text_input("📋 Subcategoría", value=item_data.get('Subcategoria', ''))
                concepto = st.text_input("📝 Concepto*", value=item_data['Concepto'])
                descripcion = st.text_area("📄 Descripción", value=item_data.get('Descripcion', ''))
                
            with col2:
                valor_presupuestado = st.number_input("💰 Valor Presupuestado*", 
                                                    value=clean_currency_value(item_data['Valor_Presupuestado']), 
                                                    min_value=0.0, step=1000.0)
                valor_ejecutado = st.number_input("💸 Valor Ejecutado", 
                                                value=clean_currency_value(item_data.get('Valor_Ejecutado', 0)), 
                                                min_value=0.0, step=1000.0)
                estado = st.selectbox("📊 Estado", ["Pendiente", "En Proceso", "Ejecutado", "Cancelado"],
                                    index=["Pendiente", "En Proceso", "Ejecutado", "Cancelado"].index(item_data.get('Estado', 'Pendiente')) if item_data.get('Estado', 'Pendiente') in ["Pendiente", "En Proceso", "Ejecutado", "Cancelado"] else 0)
                prioridad = st.selectbox("⚡ Prioridad*", ["Alta", "Media", "Baja"],
                                       index=["Alta", "Media", "Baja"].index(item_data['Prioridad']) if item_data['Prioridad'] in ["Alta", "Media", "Baja"] else 0)
                responsable = st.text_input("👤 Responsable*", value=item_data['Responsable'])
            
            fecha_ejecucion = st.date_input("📅 Fecha de Ejecución", value=None)
            observaciones = st.text_area("📝 Observaciones", value=item_data.get('Observaciones', ''))
            
            submitted = st.form_submit_button("💾 Actualizar Ítem", type="primary")
            
            if submitted:
                updated_data = {
                    'categoria': categoria,
                    'subcategoria': subcategoria,
                    'concepto': concepto,
                    'descripcion': descripcion,
                    'valor_presupuestado': valor_presupuestado,
                    'valor_ejecutado': valor_ejecutado,
                    'estado': estado,
                    'prioridad': prioridad,
                    'responsable': responsable,
                    'fecha_ejecucion': fecha_ejecucion.strftime('%Y-%m-%d') if fecha_ejecucion else '',
                    'observaciones': observaciones
                }
                
                if update_budget_item(client, item_id, updated_data):
                    st.success("✅ Ítem actualizado exitosamente")
                    st.rerun()

def show_reports(client):
    """Mostrar reportes y análisis"""
    st.header("📊 Reportes y Análisis")
    
    df = load_existing_data(client)
    
    if df.empty:
        st.info("📋 No hay datos para generar reportes.")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        conjuntos = df['Nombre_Conjunto'].unique()
        selected_conjunto = st.selectbox("🏢 Filtrar por Conjunto:", ["Todos"] + list(conjuntos))
    
    with col2:
        categorias = df['Categoria'].unique()
        selected_categoria = st.selectbox("📂 Filtrar por Categoría:", ["Todas"] + list(categorias))
    
    with col3:
        estados = df['Estado'].unique()
        selected_estado = st.selectbox("📊 Filtrar por Estado:", ["Todos"] + list(estados))
    
    # Aplicar filtros
    filtered_df = df.copy()
    if selected_conjunto != "Todos":
        filtered_df = filtered_df[filtered_df['Nombre_Conjunto'] == selected_conjunto]
    if selected_categoria != "Todas":
        filtered_df = filtered_df[filtered_df['Categoria'] == selected_categoria]
    if selected_estado != "Todos":
        filtered_df = filtered_df[filtered_df['Estado'] == selected_estado]
    
    if filtered_df.empty:
        st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
        return
    
    # Gráficos de análisis
    tab1, tab2, tab3 = st.tabs(["💰 Análisis Financiero", "📈 Tendencias", "📋 Detalles"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de barras: Presupuestado vs Ejecutado por categoría
            fig = go.Figure()
            categories = filtered_df.groupby('Categoria').agg({
                'Valor_Presupuestado': 'sum',
                'Valor_Ejecutado': 'sum'
            }).reset_index()
        
            fig.add_trace(go.Bar(name='Presupuestado', x=categories['Categoria'], y=categories['Valor_Presupuestado']))
            fig.add_trace(go.Bar(name='Ejecutado', x=categories['Categoria'], y=categories['Valor_Ejecutado']))
        
            fig.update_layout(title='Presupuestado vs Ejecutado por Categoría', barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Gráfico de gauge para porcentaje de ejecución
            total_pres = filtered_df['Valor_Presupuestado'].sum()
            total_ejec = filtered_df['Valor_Ejecutado'].sum()
            porcentaje = (total_ejec / total_pres * 100) if total_pres > 0 else 0
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=porcentaje,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "% Ejecución Total"},
                delta={'reference': 80},
                gauge={'axis': {'range': [None, 100]},
                       'bar': {'color': "darkblue"},
                       'steps': [
                           {'range': [0, 50], 'color': "lightgray"},
                           {'range': [50, 80], 'color': "gray"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75, 'value': 90}}))
            
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("📈 Distribución por Prioridad")
        prioridad_data = filtered_df.groupby('Prioridad').agg({
            'Valor_Presupuestado': 'sum',
            'ID': 'count'
        }).reset_index()
        prioridad_data.columns = ['Prioridad', 'Valor_Total', 'Cantidad_Items']
        
        fig = px.scatter(prioridad_data, x='Cantidad_Items', y='Valor_Total', 
                        size='Valor_Total', color='Prioridad',
                        title='Relación entre Cantidad de Ítems y Valor por Prioridad')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("📋 Tabla Detallada")
        
        # Formatear valores para mostrar
        display_df = filtered_df.copy()
        display_df['Valor_Presupuestado'] = display_df['Valor_Presupuestado'].apply(format_currency)
        display_df['Valor_Ejecutado'] = display_df['Valor_Ejecutado'].apply(format_currency)
        display_df['Saldo'] = display_df['Saldo'].apply(format_currency)
        
        st.dataframe(display_df, use_container_width=True)
        
        # Descargar reporte
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Reporte CSV",
            data=csv,
            file_name=f"reporte_presupuesto_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

def show_configuration(client):
    """Mostrar configuración del sistema"""
    st.header("⚙️ Configuración del Sistema")
    
    # Información de conexión
    st.subheader("🔗 Estado de Conexión")
    if client:
        st.success("✅ Conectado a Google Sheets")
        
        # Información de la hoja
        try:
            spreadsheet = client.open("gestion-conjuntos")
            st.info(f"📊 Hoja de cálculo: {spreadsheet.title}")
            st.info(f"🔗 URL: {spreadsheet.url}")
        except Exception as e:
            st.error(f"❌ Error accediendo a la hoja: {str(e)}")
    else:
        st.error("❌ No conectado")
    
    # Crear hoja de presupuesto si no existe
    st.subheader("🛠️ Herramientas de Administración")
    if st.button("🔄 Crear/Verificar Hoja de Presupuesto"):
        create_budget_sheet(client)
    
    # Estadísticas generales
    st.subheader("📊 Estadísticas del Sistema")
    df = load_existing_data(client)
    
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📋 Total de Ítems", len(df))
        
        with col2:
            conjuntos_unicos = df['Nombre_Conjunto'].nunique()
            st.metric("🏢 Conjuntos Registrados", conjuntos_unicos)
        
        with col3:
            ultimo_update = df['Fecha_Actualizacion'].max() if 'Fecha_Actualizacion' in df.columns else "N/A"
            st.metric("🕒 Última Actualización", ultimo_update)

#if __name__ == "__main__":
#    presupuesto_main