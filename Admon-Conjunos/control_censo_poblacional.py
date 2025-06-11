import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, date
import re

# Configuración de la página
#st.set_page_config(
#    page_title="Control de Censo Poblacional",
#    page_icon="🏢",
#    layout="wide",
#    initial_sidebar_state="expanded"
#)

# Funciones de conexión (usando las que proporcionaste)
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

# Funciones para manejo de datos
def get_worksheet(client, spreadsheet_name="gestion-conjuntos", worksheet_name="censo_poblacional"):
    """Obtener la hoja de trabajo específica"""
    try:
        spreadsheet = client.open(spreadsheet_name)
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            # Crear la hoja si no existe
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            # Agregar encabezados
            headers = [
                "ID", "Fecha_Registro", "Torre_Bloque", "Apartamento", "Tipo_Vivienda",
                "Propietario_Nombre", "Propietario_Documento", "Propietario_Telefono", 
                "Propietario_Email", "Es_Arrendado", "Arrendatario_Nombre", 
                "Arrendatario_Documento", "Arrendatario_Telefono", "Arrendatario_Email",
                "Num_Residentes", "Residentes_Detalles", "Vehiculos", "Mascotas",
                "Observaciones", "Estado", "Ultima_Actualizacion"
            ]
            worksheet.append_row(headers)
        return worksheet
    except Exception as e:
        st.error(f"❌ Error accediendo a la hoja: {str(e)}")
        return None

def load_data(worksheet):
    """Cargar datos desde Google Sheets"""
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            return df
        else:
            # Retornar DataFrame vacío con columnas esperadas
            columns = [
                "ID", "Fecha_Registro", "Torre_Bloque", "Apartamento", "Tipo_Vivienda",
                "Propietario_Nombre", "Propietario_Documento", "Propietario_Telefono", 
                "Propietario_Email", "Es_Arrendado", "Arrendatario_Nombre", 
                "Arrendatario_Documento", "Arrendatario_Telefono", "Arrendatario_Email",
                "Num_Residentes", "Residentes_Detalles", "Vehiculos", "Mascotas",
                "Observaciones", "Estado", "Ultima_Actualizacion"
            ]
            return pd.DataFrame(columns=columns)
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return pd.DataFrame()

def save_data(worksheet, data_dict):
    """Guardar nueva fila de datos en Google Sheets"""
    try:
        # Generar ID único
        existing_data = worksheet.get_all_records()
        new_id = len(existing_data) + 1
        
        # Preparar los datos para insertar
        row_data = [
            new_id,
            data_dict.get('fecha_registro', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            data_dict.get('torre_bloque', ''),
            data_dict.get('apartamento', ''),
            data_dict.get('tipo_vivienda', ''),
            data_dict.get('propietario_nombre', ''),
            data_dict.get('propietario_documento', ''),
            data_dict.get('propietario_telefono', ''),
            data_dict.get('propietario_email', ''),
            data_dict.get('es_arrendado', 'No'),
            data_dict.get('arrendatario_nombre', ''),
            data_dict.get('arrendatario_documento', ''),
            data_dict.get('arrendatario_telefono', ''),
            data_dict.get('arrendatario_email', ''),
            data_dict.get('num_residentes', 0),
            data_dict.get('residentes_detalles', ''),
            data_dict.get('vehiculos', ''),
            data_dict.get('mascotas', ''),
            data_dict.get('observaciones', ''),
            data_dict.get('estado', 'Activo'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        
        worksheet.append_row(row_data)
        return True, new_id
    except Exception as e:
        st.error(f"❌ Error guardando datos: {str(e)}")
        return False, None

def update_data(worksheet, row_id, data_dict):
    """Actualizar fila existente en Google Sheets"""
    try:
        # Encontrar la fila por ID
        all_records = worksheet.get_all_records()
        row_index = None
        for i, record in enumerate(all_records, start=2):  # start=2 porque la primera fila son headers
            if str(record.get('ID', '')) == str(row_id):
                row_index = i
                break
        
        if row_index:
            # Actualizar solo las celdas modificadas
            data_dict['Ultima_Actualizacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Mapear campos del formulario a columnas
            field_mapping = {
                'torre_bloque': 'C', 'apartamento': 'D', 'tipo_vivienda': 'E',
                'propietario_nombre': 'F', 'propietario_documento': 'G', 
                'propietario_telefono': 'H', 'propietario_email': 'I',
                'es_arrendado': 'J', 'arrendatario_nombre': 'K',
                'arrendatario_documento': 'L', 'arrendatario_telefono': 'M',
                'arrendatario_email': 'N', 'num_residentes': 'O',
                'residentes_detalles': 'P', 'vehiculos': 'Q', 'mascotas': 'R',
                'observaciones': 'S', 'estado': 'T'
            }
            
            for field, column in field_mapping.items():
                if field in data_dict:
                    worksheet.update(f"{column}{row_index}", data_dict[field])
            
            # Actualizar fecha de modificación
            worksheet.update(f"U{row_index}", data_dict['Ultima_Actualizacion'])
            return True
        else:
            return False
    except Exception as e:
        st.error(f"❌ Error actualizando datos: {str(e)}")
        return False

# Funciones de validación
def validate_email(email):
    """Validar formato de email"""
    if not email:
        return True  # Email vacío es válido
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validar formato de teléfono"""
    if not phone:
        return True  # Teléfono vacío es válido
    # Permitir números con o sin formato
    cleaned = re.sub(r'[^\d]', '', phone)
    return len(cleaned) >= 7

# Interfaz principal
def censo_main():
    st.title("🏢 Control de Censo Poblacional")
    st.markdown("Sistema de gestión para apartamentos y condominios")
    
    # Cargar credenciales y establecer conexión
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    worksheet = get_worksheet(client)
    if not worksheet:
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("📋 Navegación")
    menu_option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["🏠 Registrar Nuevo Residente", "📊 Consultar Censo", "✏️ Editar Registro", "📈 Dashboard"]
    )
    
    if menu_option == "🏠 Registrar Nuevo Residente":
        register_resident(worksheet)
    elif menu_option == "📊 Consultar Censo":
        view_census(worksheet)
    elif menu_option == "✏️ Editar Registro":
        edit_record(worksheet)
    elif menu_option == "📈 Dashboard":
        show_dashboard(worksheet)

def register_resident(worksheet):
    """Formulario para registrar nuevo residente"""
    st.header("🏠 Registro de Nuevo Residente")
    
    with st.form("registro_residente"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📍 Información de la Vivienda")
            torre_bloque = st.text_input("Torre/Bloque", placeholder="Ej: Torre A, Bloque 1")
            apartamento = st.text_input("Número de Apartamento*", placeholder="Ej: 101, 2A")
            tipo_vivienda = st.selectbox("Tipo de Vivienda", 
                                       ["Apartamento", "Casa", "Penthouse", "Estudio"])
            
            st.subheader("👤 Información del Propietario")
            propietario_nombre = st.text_input("Nombre Completo del Propietario*")
            propietario_documento = st.text_input("Documento de Identidad*")
            propietario_telefono = st.text_input("Teléfono", placeholder="Ej: +57 300 123 4567")
            propietario_email = st.text_input("Email", placeholder="ejemplo@correo.com")
        
        with col2:
            st.subheader("🏠 Información de Arrendamiento")
            es_arrendado = st.selectbox("¿La vivienda está arrendada?", ["No", "Sí"])
            
            arrendatario_nombre = ""
            arrendatario_documento = ""
            arrendatario_telefono = ""
            arrendatario_email = ""
            
            if es_arrendado == "Sí":
                st.write("**Información del Arrendatario:**")
                arrendatario_nombre = st.text_input("Nombre Completo del Arrendatario*")
                arrendatario_documento = st.text_input("Documento del Arrendatario*")
                arrendatario_telefono = st.text_input("Teléfono Arrendatario")
                arrendatario_email = st.text_input("Email Arrendatario")
            
            st.subheader("👥 Información de Residentes")
            num_residentes = st.number_input("Número Total de Residentes", min_value=1, value=1)
            residentes_detalles = st.text_area("Detalles de Residentes", 
                                             placeholder="Nombres, edades, relación familiar...")
            
            vehiculos = st.text_area("Vehículos", placeholder="Tipo, placa, color...")
            mascotas = st.text_area("Mascotas", placeholder="Tipo, nombre, raza...")
            observaciones = st.text_area("Observaciones Adicionales")
        
        submitted = st.form_submit_button("💾 Registrar Residente", use_container_width=True)
        
        if submitted:
            # Validaciones
            errors = []
            if not apartamento:
                errors.append("El número de apartamento es obligatorio")
            if not propietario_nombre:
                errors.append("El nombre del propietario es obligatorio")
            if not propietario_documento:
                errors.append("El documento del propietario es obligatorio")
            if es_arrendado == "Sí" and not arrendatario_nombre:
                errors.append("El nombre del arrendatario es obligatorio")
            if es_arrendado == "Sí" and not arrendatario_documento:
                errors.append("El documento del arrendatario es obligatorio")
            if propietario_email and not validate_email(propietario_email):
                errors.append("El email del propietario no es válido")
            if arrendatario_email and not validate_email(arrendatario_email):
                errors.append("El email del arrendatario no es válido")
            if propietario_telefono and not validate_phone(propietario_telefono):
                errors.append("El teléfono del propietario no es válido")
            if arrendatario_telefono and not validate_phone(arrendatario_telefono):
                errors.append("El teléfono del arrendatario no es válido")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Preparar datos
                data_dict = {
                    'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'torre_bloque': torre_bloque,
                    'apartamento': apartamento,
                    'tipo_vivienda': tipo_vivienda,
                    'propietario_nombre': propietario_nombre,
                    'propietario_documento': propietario_documento,
                    'propietario_telefono': propietario_telefono,
                    'propietario_email': propietario_email,
                    'es_arrendado': es_arrendado,
                    'arrendatario_nombre': arrendatario_nombre,
                    'arrendatario_documento': arrendatario_documento,
                    'arrendatario_telefono': arrendatario_telefono,
                    'arrendatario_email': arrendatario_email,
                    'num_residentes': num_residentes,
                    'residentes_detalles': residentes_detalles,
                    'vehiculos': vehiculos,
                    'mascotas': mascotas,
                    'observaciones': observaciones,
                    'estado': 'Activo'
                }
                
                # Guardar datos
                success, new_id = save_data(worksheet, data_dict)
                if success:
                    st.success(f"✅ Residente registrado exitosamente con ID: {new_id}")
                    st.balloons()
                else:
                    st.error("❌ Error al registrar el residente")

def view_census(worksheet):
    """Consultar y filtrar el censo poblacional"""
    st.header("📊 Consulta del Censo Poblacional")
    
    # Cargar datos
    df = load_data(worksheet)
    
    if df.empty:
        st.info("📋 No hay registros en el censo poblacional")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        torre_filter = st.selectbox("Filtrar por Torre/Bloque", 
                                  ["Todos"] + list(df['Torre_Bloque'].unique()))
    
    with col2:
        tipo_filter = st.selectbox("Filtrar por Tipo de Vivienda", 
                                 ["Todos"] + list(df['Tipo_Vivienda'].unique()))
    
    with col3:
        estado_filter = st.selectbox("Filtrar por Estado", 
                                   ["Todos"] + list(df['Estado'].unique()))
    
    # Aplicar filtros
    filtered_df = df.copy()
    
    if torre_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Torre_Bloque'] == torre_filter]
    
    if tipo_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Tipo_Vivienda'] == tipo_filter]
    
    if estado_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Estado'] == estado_filter]
    
    # Mostrar resultados
    st.subheader(f"📋 Resultados ({len(filtered_df)} registros)")
    
    if not filtered_df.empty:
        # Columnas a mostrar
        display_columns = [
            'ID', 'Torre_Bloque', 'Apartamento', 'Tipo_Vivienda',
            'Propietario_Nombre', 'Es_Arrendado', 'Arrendatario_Nombre',
            'Num_Residentes', 'Estado'
        ]
        
        st.dataframe(
            filtered_df[display_columns],
            use_container_width=True,
            hide_index=True
        )
        
        # Opción de descarga
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar datos como CSV",
            data=csv,
            file_name=f"censo_poblacional_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("🔍 No se encontraron registros con los filtros aplicados")

def edit_record(worksheet):
    """Editar registro existente"""
    st.header("✏️ Editar Registro")
    
    # Cargar datos
    df = load_data(worksheet)
    
    if df.empty:
        st.info("📋 No hay registros para editar")
        return
    
    # Selector de registro
    record_options = []
    for _, row in df.iterrows():
        label = f"ID {row['ID']} - {row['Torre_Bloque']} Apt {row['Apartamento']} - {row['Propietario_Nombre']}"
        record_options.append((label, row['ID']))
    
    selected_record = st.selectbox(
        "Selecciona el registro a editar:",
        options=record_options,
        format_func=lambda x: x[0]
    )
    
    if selected_record:
        record_id = selected_record[1]
        record_data = df[df['ID'] == record_id].iloc[0]
        
        # Formulario de edición
        with st.form("editar_registro"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📍 Información de la Vivienda")
                torre_bloque = st.text_input("Torre/Bloque", value=record_data['Torre_Bloque'])
                apartamento = st.text_input("Número de Apartamento*", value=record_data['Apartamento'])
                tipo_vivienda = st.selectbox("Tipo de Vivienda", 
                                           ["Apartamento", "Casa", "Penthouse", "Estudio"],
                                           index=["Apartamento", "Casa", "Penthouse", "Estudio"].index(record_data['Tipo_Vivienda']) if record_data['Tipo_Vivienda'] in ["Apartamento", "Casa", "Penthouse", "Estudio"] else 0)
                
                st.subheader("👤 Información del Propietario")
                propietario_nombre = st.text_input("Nombre Completo del Propietario*", value=record_data['Propietario_Nombre'])
                propietario_documento = st.text_input("Documento de Identidad*", value=record_data['Propietario_Documento'])
                propietario_telefono = st.text_input("Teléfono", value=record_data['Propietario_Telefono'])
                propietario_email = st.text_input("Email", value=record_data['Propietario_Email'])
            
            with col2:
                st.subheader("🏠 Información de Arrendamiento")
                es_arrendado = st.selectbox("¿La vivienda está arrendada?", 
                                          ["No", "Sí"],
                                          index=0 if record_data['Es_Arrendado'] == 'No' else 1)
                
                arrendatario_nombre = st.text_input("Nombre Completo del Arrendatario", value=record_data['Arrendatario_Nombre'])
                arrendatario_documento = st.text_input("Documento del Arrendatario", value=record_data['Arrendatario_Documento'])
                arrendatario_telefono = st.text_input("Teléfono Arrendatario", value=record_data['Arrendatario_Telefono'])
                arrendatario_email = st.text_input("Email Arrendatario", value=record_data['Arrendatario_Email'])
                
                st.subheader("👥 Información de Residentes")
                num_residentes = st.number_input("Número Total de Residentes", 
                                               min_value=1, 
                                               value=int(record_data['Num_Residentes']) if record_data['Num_Residentes'] else 1)
                residentes_detalles = st.text_area("Detalles de Residentes", value=record_data['Residentes_Detalles'])
                
                vehiculos = st.text_area("Vehículos", value=record_data['Vehiculos'])
                mascotas = st.text_area("Mascotas", value=record_data['Mascotas'])
                observaciones = st.text_area("Observaciones Adicionales", value=record_data['Observaciones'])
                
                estado = st.selectbox("Estado", ["Activo", "Inactivo"], 
                                    index=0 if record_data['Estado'] == 'Activo' else 1)
            
            submitted = st.form_submit_button("💾 Actualizar Registro", use_container_width=True)
            
            if submitted:
                # Validaciones
                errors = []
                if not apartamento:
                    errors.append("El número de apartamento es obligatorio")
                if not propietario_nombre:
                    errors.append("El nombre del propietario es obligatorio")
                if not propietario_documento:
                    errors.append("El documento del propietario es obligatorio")
                
                if errors:
                    for error in errors:
                        st.error(f"❌ {error}")
                else:
                    # Preparar datos actualizados
                    updated_data = {
                        'torre_bloque': torre_bloque,
                        'apartamento': apartamento,
                        'tipo_vivienda': tipo_vivienda,
                        'propietario_nombre': propietario_nombre,
                        'propietario_documento': propietario_documento,
                        'propietario_telefono': propietario_telefono,
                        'propietario_email': propietario_email,
                        'es_arrendado': es_arrendado,
                        'arrendatario_nombre': arrendatario_nombre,
                        'arrendatario_documento': arrendatario_documento,
                        'arrendatario_telefono': arrendatario_telefono,
                        'arrendatario_email': arrendatario_email,
                        'num_residentes': num_residentes,
                        'residentes_detalles': residentes_detalles,
                        'vehiculos': vehiculos,
                        'mascotas': mascotas,
                        'observaciones': observaciones,
                        'estado': estado
                    }
                    
                    # Actualizar datos
                    success = update_data(worksheet, record_id, updated_data)
                    if success:
                        st.success("✅ Registro actualizado exitosamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar el registro")

def show_dashboard(worksheet):
    """Dashboard con estadísticas del censo"""
    st.header("📈 Dashboard del Censo Poblacional")
    
    # Cargar datos
    df = load_data(worksheet)
    
    if df.empty:
        st.info("📋 No hay datos para mostrar estadísticas")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_viviendas = len(df)
        st.metric("🏠 Total Viviendas", total_viviendas)
    
    with col2:
        total_residentes = df['Num_Residentes'].sum() if 'Num_Residentes' in df.columns else 0
        st.metric("👥 Total Residentes", int(total_residentes))
    
    with col3:
        viviendas_arrendadas = len(df[df['Es_Arrendado'] == 'Sí']) if 'Es_Arrendado' in df.columns else 0
        st.metric("🏠 Viviendas Arrendadas", viviendas_arrendadas)
    
    with col4:
        viviendas_activas = len(df[df['Estado'] == 'Activo']) if 'Estado' in df.columns else 0
        st.metric("✅ Viviendas Activas", viviendas_activas)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribución por Tipo de Vivienda")
        if 'Tipo_Vivienda' in df.columns:
            tipo_counts = df['Tipo_Vivienda'].value_counts()
            st.bar_chart(tipo_counts)
        else:
            st.info("No hay datos de tipo de vivienda")
    
    with col2:
        st.subheader("🏢 Distribución por Torre/Bloque")
        if 'Torre_Bloque' in df.columns:
            torre_counts = df['Torre_Bloque'].value_counts()
            st.bar_chart(torre_counts)
        else:
            st.info("No hay datos de torre/bloque")
    
    # Tabla resumen
    st.subheader("📋 Resumen por Torre/Bloque")
    if 'Torre_Bloque' in df.columns and 'Num_Residentes' in df.columns:
        summary = df.groupby('Torre_Bloque').agg({
            'Apartamento': 'count',
            'Num_Residentes': 'sum',
            'Es_Arrendado': lambda x: (x == 'Sí').sum()
        }).rename(columns={
            'Apartamento': 'Total_Apartamentos',
            'Num_Residentes': 'Total_Residentes',
            'Es_Arrendado': 'Apartamentos_Arrendados'
        })
        st.dataframe(summary, use_container_width=True)

#if __name__ == "__main__":
#    censo_main()