import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, date
import time

# Configuración de la página
#st.set_page_config(
#    page_title="Sistema de Cobro Jurídico",
#    page_icon="⚖️",
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
            st.success(f"✅ Conexión exitosa! y disponible")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def safe_numeric_conversion(value, default=0):
    """Convertir un valor a numérico de forma segura"""
    try:
        if pd.isna(value) or value == '' or value is None:
            return default
        # Limpiar el valor si es string (remover separadores de miles, espacios, etc.)
        if isinstance(value, str):
            # Remover caracteres comunes en números formateados
            cleaned = value.replace(',', '').replace('.', '').replace(' ', '').replace('$', '')
            return float(cleaned) if cleaned else default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_format_currency(value):
    """Formatear valor como moneda de forma segura"""
    try:
        numeric_value = safe_numeric_conversion(value)
        return f"${numeric_value:,.0f}"
    except:
        return f"${value}" if value else "$0"

def get_cartera_morosa_data(client):
    """Obtener datos de cartera morosa existente"""
    try:
        # Abrir el archivo de Google Sheets
        sheet = client.open("gestion-conjuntos")
        
        # Intentar obtener datos de cartera morosa (ajusta el nombre de la hoja según corresponda)
        try:
            cartera_ws = sheet.worksheet("gestion_morosos")  # Ajusta el nombre
            cartera_data = cartera_ws.get_all_records()
            df = pd.DataFrame(cartera_data)
            
            # Convertir columnas numéricas de forma segura
            if 'Valor_Deuda' in df.columns:
                df['Valor_Deuda'] = df['Valor_Deuda'].apply(safe_numeric_conversion)
            if 'Dias_Mora' in df.columns:
                df['Dias_Mora'] = df['Dias_Mora'].apply(safe_numeric_conversion)
            if 'valor_deuda' in df.columns:
                df['valor_deuda'] = df['valor_deuda'].apply(safe_numeric_conversion)
            if 'dias_mora' in df.columns:
                df['dias_mora'] = df['dias_mora'].apply(safe_numeric_conversion)
                
            return df
        except:
            # Si no existe la hoja, crear datos de ejemplo
            st.warning("⚠️ No se encontró la hoja de cartera morosa. Mostrando datos de ejemplo.")
            return pd.DataFrame({
                'Propietario': ['Juan Pérez', 'María García', 'Carlos López'],
                'Cedula': ['12345678', '87654321', '11223344'],
                'Apartamento/Casa': ['101', '205', '304'],
                'Valor_Deuda': [1500000, 2300000, 890000],
                'Dias_Mora': [120, 180, 95],
                'Estado_Gestion': ['Moroso', 'Moroso', 'Moroso']
            })
    except Exception as e:
        st.error(f"Error obteniendo datos de cartera: {str(e)}")
        return pd.DataFrame()

def save_cobro_juridico_data(client, data):
    """Guardar datos en la hoja cobro_juridico"""
    try:
        sheet = client.open("gestion-conjuntos")
        
        # Intentar abrir la hoja cobro_juridico
        try:
            ws = sheet.worksheet("cobro_juridico")
        except:
            # Si no existe, crearla con los headers
            headers = [
                'fecha_registro', 'deudor', 'documento', 'apartamento', 
                'valor_deuda', 'dias_mora', 'abogado_asignado', 'estado_proceso',
                'tipo_proceso', 'fecha_inicio_proceso', 'radicado', 'juzgado',
                'observaciones', 'fecha_actualizacion', 'usuario_registro'
            ]
            ws = sheet.add_worksheet(title="cobro_juridico", rows=1000, cols=len(headers))
            ws.append_row(headers)
            st.success("✅ Hoja 'cobro_juridico' creada exitosamente")
        
        # Agregar los datos
        ws.append_row(data)
        return True
        
    except Exception as e:
        st.error(f"❌ Error guardando datos: {str(e)}")
        return False

def get_cobro_juridico_data(client):
    """Obtener datos existentes de cobro jurídico"""
    try:
        sheet = client.open("gestion-conjuntos")
        ws = sheet.worksheet("cobro_juridico")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Convertir columnas numéricas de forma segura
        if 'valor_deuda' in df.columns:
            df['valor_deuda'] = df['valor_deuda'].apply(safe_numeric_conversion)
        if 'dias_mora' in df.columns:
            df['dias_mora'] = df['dias_mora'].apply(safe_numeric_conversion)
            
        return df
    except:
        return pd.DataFrame()

def format_deudor_option(idx, cartera_df):
    """Formatear opción de deudor de forma segura"""
    try:
        row = cartera_df.iloc[idx]
        propietario = row.get('Propietario', 'N/A')
        apartamento = row.get('Apartamento/Casa', 'N/A')
        valor_deuda = safe_format_currency(row.get('Valor_Deuda', 0))
        return f"{propietario} - Apt. {apartamento} - {valor_deuda}"
    except Exception as e:
        return f"Error en fila {idx}: {str(e)}"

def juridico_main():
    st.title("⚖️ Sistema de Cobro Jurídico")
    st.markdown("---")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Conectar a Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.error("No se pudo establecer conexión con Google Sheets")
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("📋 Menú de Opciones")
    opcion = st.sidebar.selectbox(
        "Seleccione una opción:",
        ["Consultar Cartera Morosa", "Registrar Proceso Jurídico", "Gestionar Procesos", "Dashboard"]
    )
    
    if opcion == "Consultar Cartera Morosa":
        st.subheader("📊 Cartera Morosa Actual")
        
        # Obtener datos de cartera morosa
        cartera_df = get_cartera_morosa_data(client)
        
        if not cartera_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                min_deuda = st.number_input("Deuda mínima", value=0, step=100000)
            with col2:
                min_dias = st.number_input("Días mínimos de mora", value=0, step=10)
            with col3:
                estados_disponibles = cartera_df['Estado_Gestion'].unique() if 'Estado_Gestion' in cartera_df.columns else []
                estado_filtro = st.selectbox("Estado", ["Todos"] + list(estados_disponibles))
            
            # Aplicar filtros
            df_filtrado = cartera_df.copy()
            
            # Filtro por valor de deuda
            valor_deuda_col = 'Valor_Deuda' if 'Valor_Deuda' in df_filtrado.columns else 'valor_deuda'
            if valor_deuda_col in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado[valor_deuda_col] >= min_deuda]
            
            # Filtro por días de mora
            dias_mora_col = 'Dias_Mora' if 'Dias_Mora' in df_filtrado.columns else 'dias_mora'
            if dias_mora_col in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado[dias_mora_col] >= min_dias]
            
            # Filtro por estado
            if estado_filtro != "Todos" and 'Estado_Gestion' in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado['Estado_Gestion'] == estado_filtro]
            
            st.dataframe(df_filtrado, use_container_width=True)
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Deudores", len(df_filtrado))
            with col2:
                if valor_deuda_col in df_filtrado.columns:
                    total_deuda = df_filtrado[valor_deuda_col].sum()
                    st.metric("Deuda Total", safe_format_currency(total_deuda))
            with col3:
                if dias_mora_col in df_filtrado.columns:
                    promedio_mora = df_filtrado[dias_mora_col].mean()
                    st.metric("Promedio Días Mora", f"{promedio_mora:.0f}")
            with col4:
                if valor_deuda_col in df_filtrado.columns:
                    elegibles = len(df_filtrado[df_filtrado[valor_deuda_col] > 1000000])
                    st.metric("Elegibles Cobro Jurídico", elegibles)
        else:
            st.warning("No se encontraron datos de cartera morosa")
    
    elif opcion == "Registrar Proceso Jurídico":
        st.subheader("📝 Registro de Nuevo Proceso Jurídico")
        
        # Obtener cartera morosa para selección
        cartera_df = get_cartera_morosa_data(client)
        
        with st.form("registro_proceso"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Información del Deudor**")
                
                if not cartera_df.empty:
                    # Selección desde cartera morosa
                    deudor_seleccionado = st.selectbox(
                        "Seleccionar deudor de cartera morosa:",
                        options=range(len(cartera_df)),
                        format_func=lambda x: format_deudor_option(x, cartera_df)
                    )
                    
                    if deudor_seleccionado is not None:
                        deudor_info = cartera_df.iloc[deudor_seleccionado]
                        deudor = deudor_info.get('Propietario', '')
                        documento = str(deudor_info.get('Cedula', ''))
                        apartamento = str(deudor_info.get('Apartamento/Casa', ''))
                        valor_deuda = safe_numeric_conversion(deudor_info.get('Valor_Deuda', 0))
                        dias_mora = safe_numeric_conversion(deudor_info.get('Dias_Mora', 0))
                        
                        st.info(f"**Deudor:** {deudor}\n**Documento:** {documento}\n**Apartamento:** {apartamento}\n**Deuda:** {safe_format_currency(valor_deuda)}\n**Días mora:** {dias_mora}")
                else:
                    # Entrada manual si no hay cartera
                    deudor = st.text_input("Nombre del deudor")
                    documento = st.text_input("Documento")
                    apartamento = st.text_input("Apartamento")
                    valor_deuda = st.number_input("Valor de la deuda", min_value=0, step=10000)
                    dias_mora = st.number_input("Días de mora", min_value=0, step=1)
                
                abogado_asignado = st.selectbox(
                    "Abogado asignado:",
                    ["Dr. López & Asociados", "Dra. Martínez", "Dr. Rodríguez", "Bufete García"]
                )
            
            with col2:
                st.markdown("**Información del Proceso**")
                
                estado_proceso = st.selectbox(
                    "Estado del proceso:",
                    ["Evaluación", "Pre-jurídico", "Demanda", "Proceso ejecutivo", 
                     "Embargo", "Remate", "Acuerdo de pago", "Cerrado"]
                )
                
                tipo_proceso = st.selectbox(
                    "Tipo de proceso:",
                    ["Ejecutivo", "Declarativo", "Monitorio", "Verbal sumario"]
                )
                
                fecha_inicio = st.date_input("Fecha inicio proceso", value=date.today())
                
                radicado = st.text_input("Número de radicado")
                
                juzgado = st.text_input("Juzgado")
                
                observaciones = st.text_area("Observaciones", height=100)
                
                usuario_registro = st.text_input("Usuario que registra", value="Admin")
            
            submitted = st.form_submit_button("💾 Registrar Proceso Jurídico")
            
            if submitted:
                if deudor and documento and apartamento:
                    # Preparar datos para guardar
                    data_to_save = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # fecha_registro
                        deudor,
                        documento,
                        apartamento,
                        valor_deuda,
                        dias_mora,
                        abogado_asignado,
                        estado_proceso,
                        tipo_proceso,
                        fecha_inicio.strftime("%Y-%m-%d"),
                        radicado,
                        juzgado,
                        observaciones,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # fecha_actualizacion
                        usuario_registro
                    ]
                    
                    if save_cobro_juridico_data(client, data_to_save):
                        st.success("✅ Proceso jurídico registrado exitosamente")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar el proceso jurídico")
                else:
                    st.error("⚠️ Por favor complete todos los campos obligatorios")
    
    elif opcion == "Gestionar Procesos":
        st.subheader("📋 Gestión de Procesos Jurídicos")
        
        # Obtener datos de procesos jurídicos
        procesos_df = get_cobro_juridico_data(client)
        
        if not procesos_df.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                estados_disponibles = list(procesos_df['estado_proceso'].unique()) if 'estado_proceso' in procesos_df.columns else []
                estado_filtro = st.selectbox("Filtrar por estado:", ["Todos"] + estados_disponibles)
            
            with col2:
                abogados_disponibles = list(procesos_df['abogado_asignado'].unique()) if 'abogado_asignado' in procesos_df.columns else []
                abogado_filtro = st.selectbox("Filtrar por abogado:", ["Todos"] + abogados_disponibles)
            
            with col3:
                tipos_disponibles = list(procesos_df['tipo_proceso'].unique()) if 'tipo_proceso' in procesos_df.columns else []
                tipo_filtro = st.selectbox("Filtrar por tipo:", ["Todos"] + tipos_disponibles)
            
            # Aplicar filtros
            df_filtrado = procesos_df.copy()
            if estado_filtro != "Todos" and 'estado_proceso' in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado['estado_proceso'] == estado_filtro]
            if abogado_filtro != "Todos" and 'abogado_asignado' in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado['abogado_asignado'] == abogado_filtro]
            if tipo_filtro != "Todos" and 'tipo_proceso' in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado['tipo_proceso'] == tipo_filtro]
            
            st.dataframe(df_filtrado, use_container_width=True)
            
            # Métricas de procesos
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Procesos", len(df_filtrado))
            with col2:
                if 'valor_deuda' in df_filtrado.columns:
                    total_valor = df_filtrado['valor_deuda'].sum()
                    st.metric("Valor Total en Proceso", safe_format_currency(total_valor))
            with col3:
                activos = len(df_filtrado[df_filtrado['estado_proceso'] != 'Cerrado']) if 'estado_proceso' in df_filtrado.columns else 0
                st.metric("Procesos Activos", activos)
            with col4:
                if 'tipo_proceso' in df_filtrado.columns:
                    ejecutivos = len(df_filtrado[df_filtrado['tipo_proceso'] == 'Ejecutivo'])
                    st.metric("Procesos Ejecutivos", ejecutivos)
        else:
            st.info("📝 No hay procesos jurídicos registrados aún")
            st.markdown("Utiliza la opción 'Registrar Proceso Jurídico' para agregar el primer proceso.")
    
    elif opcion == "Dashboard":
        st.subheader("📊 Dashboard de Cobro Jurídico")
        
        # Obtener datos
        cartera_df = get_cartera_morosa_data(client)
        procesos_df = get_cobro_juridico_data(client)
        
        # Métricas generales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_morosos = len(cartera_df) if not cartera_df.empty else 0
            st.metric("Total Morosos", total_morosos)
        
        with col2:
            total_procesos = len(procesos_df) if not procesos_df.empty else 0
            st.metric("Procesos Jurídicos", total_procesos)
        
        with col3:
            if not cartera_df.empty:
                valor_deuda_col = 'Valor_Deuda' if 'Valor_Deuda' in cartera_df.columns else 'valor_deuda'
                if valor_deuda_col in cartera_df.columns:
                    cartera_total = cartera_df[valor_deuda_col].sum()
                    st.metric("Cartera Total", safe_format_currency(cartera_total))
                else:
                    st.metric("Cartera Total", "$0")
            else:
                st.metric("Cartera Total", "$0")
        
        with col4:
            if not procesos_df.empty and 'valor_deuda' in procesos_df.columns:
                en_proceso = procesos_df['valor_deuda'].sum()
                st.metric("En Proceso Jurídico", safe_format_currency(en_proceso))
            else:
                st.metric("En Proceso Jurídico", "$0")
        
        # Gráficos (si hay datos)
        if not procesos_df.empty:
            st.markdown("### 📈 Distribución de Procesos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'estado_proceso' in procesos_df.columns:
                    estado_counts = procesos_df['estado_proceso'].value_counts()
                    st.bar_chart(estado_counts)
                    st.caption("Procesos por Estado")
            
            with col2:
                if 'tipo_proceso' in procesos_df.columns:
                    tipo_counts = procesos_df['tipo_proceso'].value_counts()
                    st.bar_chart(tipo_counts)
                    st.caption("Procesos por Tipo")

#if __name__ == "__main__":
#    juridico_main()