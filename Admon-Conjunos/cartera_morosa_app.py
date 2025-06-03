import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import base64

# Configuración de la página
st.set_page_config(
    page_title="🏢 Gestión de Cartera Morosa",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Función para cargar credenciales
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
            st.success(f"✅ Conexión exitosa! Encontradas {len(sheets)} hojas de cálculo disponibles")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def get_or_create_sheet(client, sheet_name="gestion-conjuntos", worksheet_name="gestion_morosos"):
    """Obtener o crear la hoja de cálculo y worksheet"""
    try:
        # Intentar abrir la hoja existente
        sheet = client.open(sheet_name)
        st.info(f"📊 Hoja '{sheet_name}' encontrada")
    except gspread.SpreadsheetNotFound:
        # Crear nueva hoja si no existe
        sheet = client.create(sheet_name)
        st.success(f"📊 Nueva hoja '{sheet_name}' creada")
    
    try:
        # Intentar abrir el worksheet
        worksheet = sheet.worksheet(worksheet_name)
        st.info(f"📋 Worksheet '{worksheet_name}' encontrado")
    except gspread.WorksheetNotFound:
        # Crear nuevo worksheet si no existe
        worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        # Crear encabezados
        headers = [
            "ID", "Fecha_Registro", "Apartamento/Casa", "Propietario", "Cedula", 
            "Telefono", "Email", "Valor_Deuda", "Concepto_Deuda", "Fecha_Vencimiento",
            "Dias_Mora", "Estado_Gestion", "Tipo_Gestion", "Fecha_Ultimo_Contacto",
            "Observaciones", "Accion_Juridica", "Fecha_Accion_Juridica", "Valor_Pagado",
            "Fecha_Pago", "Saldo_Pendiente"
        ]
        worksheet.append_row(headers)
        st.success(f"📋 Nuevo worksheet '{worksheet_name}' creado con encabezados")
    
    return sheet, worksheet

def load_data(worksheet):
    """Cargar datos desde Google Sheets"""
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            # Convertir fechas
            date_columns = ['Fecha_Registro', 'Fecha_Vencimiento', 'Fecha_Ultimo_Contacto', 
                          'Fecha_Accion_Juridica', 'Fecha_Pago']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Convertir valores numéricos
            numeric_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente', 'Dias_Mora']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando datos: {str(e)}")
        return pd.DataFrame()

def save_data(worksheet, df):
    """Guardar datos en Google Sheets"""
    try:
        # Limpiar la hoja excepto los encabezados
        worksheet.clear()
        
        # Escribir encabezados
        headers = list(df.columns)
        worksheet.append_row(headers)
        
        # Escribir datos
        if not df.empty:
            # Convertir fechas a string para Google Sheets
            df_copy = df.copy()
            date_columns = ['Fecha_Registro', 'Fecha_Vencimiento', 'Fecha_Ultimo_Contacto', 
                          'Fecha_Accion_Juridica', 'Fecha_Pago']
            for col in date_columns:
                if col in df_copy.columns:
                    df_copy[col] = df_copy[col].astype(str)
            
            # Convertir DataFrame a lista de listas
            data_list = df_copy.values.tolist()
            worksheet.append_rows(data_list)
        
        st.success("✅ Datos guardados exitosamente en Google Sheets")
        return True
    except Exception as e:
        st.error(f"❌ Error guardando datos: {str(e)}")
        return False

def calculate_mora_days(fecha_vencimiento):
    """Calcular días de mora"""
    if pd.isna(fecha_vencimiento):
        return 0
    
    if isinstance(fecha_vencimiento, str):
        try:
            fecha_vencimiento = pd.to_datetime(fecha_vencimiento)
        except:
            return 0
    
    today = datetime.now()
    if fecha_vencimiento < today:
        return (today - fecha_vencimiento).days
    return 0

def get_estado_by_dias_mora(dias_mora):
    """Determinar estado según días de mora"""
    if dias_mora <= 30:
        return "Al Día"
    elif dias_mora <= 60:
        return "Mora Temprana"
    elif dias_mora <= 90:
        return "Mora Media"
    elif dias_mora <= 180:
        return "Mora Tardía"
    else:
        return "Cobro Jurídico"

def main():
    # Título principal
    st.title("🏢 Sistema de Gestión de Cartera Morosa")
    st.markdown("### 📋 Control y Manejo de Cobro Prejurídico - Condominios")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Obtener o crear hoja
    sheet, worksheet = get_or_create_sheet(client)
    
    # Cargar datos existentes
    df = load_data(worksheet)
    
    # Sidebar para navegación
    st.sidebar.title("🔧 Panel de Control")
    menu_option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["📊 Dashboard", "➕ Nuevo Registro", "📝 Gestionar Registros", 
         "📞 Gestión de Cobro", "📈 Reportes", "⚙️ Configuración"]
    )
    
    if menu_option == "📊 Dashboard":
        show_dashboard(df)
    elif menu_option == "➕ Nuevo Registro":
        show_new_record_form(df, worksheet)
    elif menu_option == "📝 Gestionar Registros":
        show_manage_records(df, worksheet)
    elif menu_option == "📞 Gestión de Cobro":
        show_collection_management(df, worksheet)
    elif menu_option == "📈 Reportes":
        show_reports(df)
    elif menu_option == "⚙️ Configuración":
        show_configuration()

def show_dashboard(df):
    """Mostrar dashboard principal"""
    st.header("📊 Dashboard de Cartera Morosa")
    
    if df.empty:
        st.warning("📋 No hay datos disponibles. Comienza agregando registros.")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_deudores = len(df)
        st.metric("👥 Total Deudores", total_deudores)
    
    with col2:
        total_deuda = df['Valor_Deuda'].sum()
        st.metric("💰 Deuda Total", f"${total_deuda:,.0f}")
    
    with col3:
        total_pagado = df['Valor_Pagado'].sum()
        st.metric("💚 Total Pagado", f"${total_pagado:,.0f}")
    
    with col4:
        saldo_pendiente = df['Saldo_Pendiente'].sum()
        st.metric("⚠️ Saldo Pendiente", f"${saldo_pendiente:,.0f}")
    
    # Actualizar días de mora y estados
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    df['Estado_Calculado'] = df['Dias_Mora'].apply(get_estado_by_dias_mora)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribución por Estado de Mora")
        estado_counts = df['Estado_Calculado'].value_counts()
        fig_pie = px.pie(
            values=estado_counts.values, 
            names=estado_counts.index,
            title="Estados de Mora"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📈 Evolución de Deudas")
        df_grouped = df.groupby('Estado_Calculado').agg({
            'Valor_Deuda': 'sum',
            'Saldo_Pendiente': 'sum'
        }).reset_index()
        
        fig_bar = px.bar(
            df_grouped, 
            x='Estado_Calculado', 
            y=['Valor_Deuda', 'Saldo_Pendiente'],
            title="Deuda vs Saldo Pendiente por Estado",
            barmode='group'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabla de casos críticos
    st.subheader("🚨 Casos Críticos (Más de 90 días)")
    casos_criticos = df[df['Dias_Mora'] > 90].sort_values('Dias_Mora', ascending=False)
    if not casos_criticos.empty:
        st.dataframe(
            casos_criticos[['Apartamento/Casa', 'Propietario', 'Valor_Deuda', 
                          'Dias_Mora', 'Estado_Calculado']],
            use_container_width=True
        )
    else:
        st.success("✅ No hay casos críticos actualmente")

def show_new_record_form(df, worksheet):
    """Formulario para nuevo registro"""
    st.header("➕ Nuevo Registro de Deuda")
    
    with st.form("nuevo_registro"):
        col1, col2 = st.columns(2)
        
        with col1:
            apartamento = st.text_input("🏠 Apartamento/Casa*", placeholder="Ej: Apto 101, Casa 15")
            propietario = st.text_input("👤 Nombre Propietario*", placeholder="Nombre completo")
            cedula = st.text_input("🆔 Cédula*", placeholder="Número de identificación")
            telefono = st.text_input("📱 Teléfono", placeholder="Número de contacto")
            email = st.text_input("📧 Email", placeholder="correo@ejemplo.com")
        
        with col2:
            valor_deuda = st.number_input("💰 Valor de la Deuda*", min_value=0.0, step=1000.0)
            concepto = st.selectbox("📋 Concepto de la Deuda*", [
                "Administración", "Parqueadero", "Cuota Extraordinaria", 
                "Multas", "Servicios", "Otros"
            ])
            fecha_vencimiento = st.date_input("📅 Fecha de Vencimiento*")
            observaciones = st.text_area("📝 Observaciones", placeholder="Detalles adicionales...")
        
        submitted = st.form_submit_button("💾 Guardar Registro", type="primary")
        
        if submitted:
            if apartamento and propietario and cedula and valor_deuda > 0:
                # Crear nuevo ID
                nuevo_id = len(df) + 1 if not df.empty else 1
                
                # Calcular días de mora
                dias_mora = calculate_mora_days(pd.to_datetime(fecha_vencimiento))
                estado_gestion = get_estado_by_dias_mora(dias_mora)
                
                # Crear nuevo registro
                nuevo_registro = {
                    'ID': nuevo_id,
                    'Fecha_Registro': datetime.now().strftime('%Y-%m-%d'),
                    'Apartamento/Casa': apartamento,
                    'Propietario': propietario,
                    'Cedula': cedula,
                    'Telefono': telefono,
                    'Email': email,
                    'Valor_Deuda': valor_deuda,
                    'Concepto_Deuda': concepto,
                    'Fecha_Vencimiento': fecha_vencimiento.strftime('%Y-%m-%d'),
                    'Dias_Mora': dias_mora,
                    'Estado_Gestion': estado_gestion,
                    'Tipo_Gestion': 'Pendiente',
                    'Fecha_Ultimo_Contacto': '',
                    'Observaciones': observaciones,
                    'Accion_Juridica': 'No',
                    'Fecha_Accion_Juridica': '',
                    'Valor_Pagado': 0,
                    'Fecha_Pago': '',
                    'Saldo_Pendiente': valor_deuda
                }
                
                # Agregar al DataFrame
                if df.empty:
                    df_nuevo = pd.DataFrame([nuevo_registro])
                else:
                    df_nuevo = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
                
                # Guardar en Google Sheets
                if save_data(worksheet, df_nuevo):
                    st.success("✅ Registro guardado exitosamente")
                    st.rerun()
            else:
                st.error("❌ Por favor complete todos los campos obligatorios (*)")

def show_manage_records(df, worksheet):
    """Gestionar registros existentes"""
    st.header("📝 Gestionar Registros")
    
    if df.empty:
        st.warning("📋 No hay registros para gestionar")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filtro_estado = st.selectbox("Filtrar por Estado:", 
                                   ["Todos"] + df['Estado_Gestion'].dropna().unique().tolist())
    
    with col2:
        filtro_apartamento = st.selectbox("Filtrar por Apartamento:", 
                                        ["Todos"] + df['Apartamento/Casa'].dropna().unique().tolist())
    
    with col3:
        dias_mora_min = st.number_input("Días de mora mínimos:", min_value=0, value=0)
    
    # Aplicar filtros
    df_filtrado = df.copy()
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Estado_Gestion'] == filtro_estado]
    if filtro_apartamento != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Apartamento/Casa'] == filtro_apartamento]
    
    df_filtrado['Dias_Mora'] = df_filtrado['Fecha_Vencimiento'].apply(calculate_mora_days)
    df_filtrado = df_filtrado[df_filtrado['Dias_Mora'] >= dias_mora_min]
    
    # Mostrar tabla editable
    st.subheader(f"📊 Registros Encontrados: {len(df_filtrado)}")
    
    if not df_filtrado.empty:
        # Selección de registro para editar
        registro_seleccionado = st.selectbox(
            "Seleccionar registro para editar:",
            options=df_filtrado['ID'].tolist(),
            format_func=lambda x: f"ID {x} - {df_filtrado[df_filtrado['ID']==x]['Propietario'].iloc[0]} - {df_filtrado[df_filtrado['ID']==x]['Apartamento/Casa'].iloc[0]}"
        )
        
        if registro_seleccionado:
            registro = df_filtrado[df_filtrado['ID'] == registro_seleccionado].iloc[0]
            
            with st.form("editar_registro"):
                st.subheader(f"✏️ Editando Registro ID: {registro_seleccionado}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    nuevo_estado = st.selectbox("Estado de Gestión:", 
                                              ["Al Día", "Mora Temprana", "Mora Media", 
                                               "Mora Tardía", "Cobro Jurídico", "Pagado"],
                                              index=0 if pd.isna(registro['Estado_Gestion']) else 
                                              ["Al Día", "Mora Temprana", "Mora Media", 
                                               "Mora Tardía", "Cobro Jurídico", "Pagado"].index(registro['Estado_Gestion']) 
                                              if registro['Estado_Gestion'] in ["Al Día", "Mora Temprana", "Mora Media", 
                                                                               "Mora Tardía", "Cobro Jurídico", "Pagado"] else 0)
                    
                    tipo_gestion = st.selectbox("Tipo de Gestión:", 
                                              ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"],
                                              index=0 if pd.isna(registro['Tipo_Gestion']) else 
                                              ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"].index(registro['Tipo_Gestion'])
                                              if registro['Tipo_Gestion'] in ["Pendiente", "Llamada", "Email", "Visita", "Carta", "Jurídico"] else 0)
                    
                    valor_pagado = st.number_input("Valor Pagado:", 
                                                 min_value=0.0, 
                                                 value=float(registro['Valor_Pagado']) if not pd.isna(registro['Valor_Pagado']) else 0.0)
                
                with col2:
                    fecha_contacto = st.date_input("Fecha Último Contacto:", 
                                                 value=datetime.now().date())
                    
                    accion_juridica = st.selectbox("Acción Jurídica:", ["No", "Sí"],
                                                 index=1 if registro['Accion_Juridica'] == 'Sí' else 0)
                    
                    observaciones_edit = st.text_area("Observaciones:", 
                                                    value=registro['Observaciones'] if not pd.isna(registro['Observaciones']) else "")
                
                actualizar = st.form_submit_button("💾 Actualizar Registro", type="primary")
                
                if actualizar:
                    # Actualizar el registro en el DataFrame
                    idx = df[df['ID'] == registro_seleccionado].index[0]
                    df.loc[idx, 'Estado_Gestion'] = nuevo_estado
                    df.loc[idx, 'Tipo_Gestion'] = tipo_gestion
                    df.loc[idx, 'Fecha_Ultimo_Contacto'] = fecha_contacto.strftime('%Y-%m-%d')
                    df.loc[idx, 'Valor_Pagado'] = valor_pagado
                    df.loc[idx, 'Saldo_Pendiente'] = float(registro['Valor_Deuda']) - valor_pagado
                    df.loc[idx, 'Accion_Juridica'] = accion_juridica
                    df.loc[idx, 'Observaciones'] = observaciones_edit
                    
                    if accion_juridica == 'Sí' and pd.isna(registro['Fecha_Accion_Juridica']):
                        df.loc[idx, 'Fecha_Accion_Juridica'] = datetime.now().strftime('%Y-%m-%d')
                    
                    # Guardar cambios
                    if save_data(worksheet, df):
                        st.success("✅ Registro actualizado exitosamente")
                        st.rerun()

def show_collection_management(df, worksheet):
    """Gestión de cobro"""
    st.header("📞 Gestión de Cobro Prejurídico")
    
    if df.empty:
        st.warning("📋 No hay registros para gestionar")
        return
    
    # Actualizar días de mora
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    
    # Casos por gestionar (con saldo pendiente > 0)
    casos_pendientes = df[(df['Saldo_Pendiente'] > 0) & (df['Estado_Gestion'] != 'Pagado')]
    
    if casos_pendientes.empty:
        st.success("✅ No hay casos pendientes de cobro")
        return
    
    st.subheader(f"📋 Casos Pendientes de Cobro: {len(casos_pendientes)}")
    
    # Priorizar casos por días de mora
    casos_priorizados = casos_pendientes.sort_values('Dias_Mora', ascending=False)
    
    # Mostrar casos críticos
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🚨 Casos Prioritarios")
        for idx, caso in casos_priorizados.head(10).iterrows():
            with st.expander(f"🏠 {caso['Apartamento/Casa']} - {caso['Propietario']} ({caso['Dias_Mora']} días)"):
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.write(f"**💰 Deuda:** ${caso['Valor_Deuda']:,.0f}")
                    st.write(f"**💸 Pagado:** ${caso['Valor_Pagado']:,.0f}")
                    st.write(f"**⚠️ Saldo:** ${caso['Saldo_Pendiente']:,.0f}")
                    st.write(f"**📱 Teléfono:** {caso['Telefono']}")
                
                with col_b:
                    st.write(f"**📅 Vencimiento:** {caso['Fecha_Vencimiento']}")
                    st.write(f"**📞 Último contacto:** {caso['Fecha_Ultimo_Contacto']}")
                    st.write(f"**📋 Estado:** {caso['Estado_Gestion']}")
                    st.write(f"**⚖️ Jurídico:** {caso['Accion_Juridica']}")
                
                # Acciones rápidas
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                
                with col_btn1:
                    if st.button(f"📞 Contactar", key=f"contact_{caso['ID']}"):
                        st.info("Registrando contacto...")
                
                with col_btn2:
                    if st.button(f"💰 Pago", key=f"payment_{caso['ID']}"):
                        st.info("Registrando pago...")
                
                with col_btn3:
                    if st.button(f"⚖️ Jurídico", key=f"legal_{caso['ID']}"):
                        st.info("Iniciando proceso jurídico...")
    
    with col2:
        st.subheader("📊 Resumen de Gestión")
        
        # Métricas de gestión
        total_casos = len(casos_pendientes)
        casos_criticos = len(casos_pendientes[casos_pendientes['Dias_Mora'] > 90])
        casos_juridicos = len(casos_pendientes[casos_pendientes['Accion_Juridica'] == 'Sí'])
        
        st.metric("📋 Total Casos", total_casos)
        st.metric("🚨 Casos Críticos", casos_criticos)
        st.metric("⚖️ En Proceso Jurídico", casos_juridicos)
        
        # Gráfico de distribución
        distribucion = casos_pendientes.copy()
        distribucion['Rango_Mora'] = distribucion['Dias_Mora'].apply(
            lambda x: '0-30 días' if x <= 30 else
                     '31-60 días' if x <= 60 else
                     '61-90 días' if x <= 90 else
                     '91-180 días' if x <= 180 else
                     '+180 días'
        )
        
        fig_dist = px.pie(
            distribucion['Rango_Mora'].value_counts().reset_index(),
            values='count',
            names='Rango_Mora',
            title="Distribución por Días de Mora"
        )
        st.plotly_chart(fig_dist, use_container_width=True)

def show_reports(df):
    """Mostrar reportes y análisis"""
    st.header("📈 Reportes y Análisis")
    
    if df.empty:
        st.warning("📋 No hay datos para generar reportes")
        return
    
    # Actualizar cálculos
    df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(calculate_mora_days)
    df['Estado_Calculado'] = df['Dias_Mora'].apply(get_estado_by_dias_mora)
    
    # Tabs para diferentes reportes
    tab1, tab2, tab3, tab4 = st.tabs(["📊 General", "💰 Financiero", "📅 Temporal", "📋 Detallado"])
    
    with tab1:
        st.subheader("📊 Reporte General")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribución por estado
            estado_dist = df['Estado_Calculado'].value_counts()
            fig_estado = px.bar(
                x=estado_dist.index,
                y=estado_dist.values,
                title="Distribución por Estado de Mora",
                labels={'x': 'Estado', 'y': 'Cantidad'}
            )
            st.plotly_chart(fig_estado, use_container_width=True)
        
        with col2:
            # Top deudores
            top_deudores = df.nlargest(10, 'Saldo_Pendiente')[['Propietario', 'Apartamento/Casa', 'Saldo_Pendiente']]
            st.subheader("🔝 Top 10 Deudores")
            st.dataframe(top_deudores, use_container_width=True)
    
    with tab2:
        st.subheader("💰 Reporte Financiero")
        
        # Métricas financieras
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Deuda Total", f"${df['Valor_Deuda'].sum():,.0f}")
        with col2:
            st.metric("💚 Total Recaudado", f"${df['Valor_Pagado'].sum():,.0f}")