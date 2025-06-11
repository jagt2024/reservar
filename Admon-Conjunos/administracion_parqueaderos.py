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
#    page_title="🚗 Administración de Parqueaderos",
#    page_icon="🚗",
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

def get_spreadsheet_data(client, spreadsheet_name, worksheet_name):
    """Obtener datos de la hoja de cálculo"""
    try:
        spreadsheet = client.open(spreadsheet_name)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except gspread.WorksheetNotFound:
        try:
            # Crear la hoja si no existe
            spreadsheet = client.open(spreadsheet_name)
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=15)
            # Agregar encabezados
            headers = [
                "ID_Parqueadero", "Numero_Parqueadero", "Tipo_Parqueadero", 
                "Estado", "Apartamento_Asignado", "Propietario", "Placa_Vehiculo",
                "Tipo_Vehiculo", "Fecha_Asignacion", "Fecha_Liberacion", 
                "Observaciones", "Telefono_Contacto", "Email_Contacto",
                "Fecha_Creacion", "Ultima_Actualizacion"
            ]
            worksheet.append_row(headers)
            st.success(f"✅ Hoja '{worksheet_name}' creada exitosamente")
            # Return empty DataFrame with headers and the worksheet
            return pd.DataFrame(columns=headers), worksheet
        except Exception as e:
            st.error(f"❌ Error creando la hoja: {str(e)}")
            return None, None
    except gspread.SpreadsheetNotFound:
        st.error(f"📄 No se encontró la hoja de cálculo: {spreadsheet_name}")
        return None, None
    except Exception as e:
        st.error(f"❌ Error obteniendo datos: {str(e)}")
        return None, None

def initialize_worksheet(worksheet):
    """Inicializar la hoja con las columnas necesarias si está vacía"""
    try:
        headers = [
            "ID_Parqueadero", "Numero_Parqueadero", "Tipo_Parqueadero", 
            "Estado", "Apartamento_Asignado", "Propietario", "Placa_Vehiculo",
            "Tipo_Vehiculo", "Fecha_Asignacion", "Fecha_Liberacion", 
            "Observaciones", "Telefono_Contacto", "Email_Contacto",
            "Fecha_Creacion", "Ultima_Actualizacion"
        ]
        
        # Verificar si la hoja está vacía
        if not worksheet.get_all_values():
            worksheet.insert_row(headers, 1)
            st.success("✅ Hoja inicializada con columnas necesarias")
        
        return headers
    except Exception as e:
        st.error(f"❌ Error inicializando hoja: {str(e)}")
        return None

def add_parking_space(worksheet, data):
    """Agregar un nuevo espacio de parqueadero"""
    try:
        # Agregar timestamps
        data['Fecha_Creacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['Ultima_Actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convertir datos a lista en el orden correcto
        row_data = [
            data.get('ID_Parqueadero', ''),
            data.get('Numero_Parqueadero', ''),
            data.get('Tipo_Parqueadero', ''),
            data.get('Estado', ''),
            data.get('Apartamento_Asignado', ''),
            data.get('Propietario', ''),
            data.get('Placa_Vehiculo', ''),
            data.get('Tipo_Vehiculo', ''),
            data.get('Fecha_Asignacion', ''),
            data.get('Fecha_Liberacion', ''),
            data.get('Observaciones', ''),
            data.get('Telefono_Contacto', ''),
            data.get('Email_Contacto', ''),
            data.get('Fecha_Creacion', ''),
            data.get('Ultima_Actualizacion', '')
        ]
        
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"❌ Error agregando parqueadero: {str(e)}")
        return False

def update_parking_space(worksheet, df, row_index, updated_data):
    """Actualizar un espacio de parqueadero existente"""
    try:
        # Agregar timestamp de actualización
        updated_data['Ultima_Actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Actualizar cada celda individualmente
        headers = df.columns.tolist()
        for col_index, header in enumerate(headers):
            if header in updated_data:
                worksheet.update_cell(row_index + 2, col_index + 1, updated_data[header])
        
        return True
    except Exception as e:
        st.error(f"❌ Error actualizando parqueadero: {str(e)}")
        return False

def parqueadero_main():
    st.title("🚗 Sistema de Administración de Parqueaderos")
    st.markdown("### Conjunto Residencial - Gestión de Espacios de Parqueadero")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Configuración de la hoja de cálculo
    spreadsheet_name = "gestion-conjuntos"
    worksheet_name = "parqueaderos"
    
    # Obtener datos
    df, worksheet = get_spreadsheet_data(client, spreadsheet_name, worksheet_name)
    if worksheet is None:
        st.stop()
    
    # Inicializar hoja si es necesario
    if df is None or df.empty:
        headers = initialize_worksheet(worksheet)
        df = pd.DataFrame(columns=headers if headers else [])
    
    # Sidebar para navegación
    st.sidebar.title("🎯 Menú de Opciones")
    option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["📊 Dashboard", "➕ Agregar Parqueadero", "✏️ Editar Parqueadero", "🔍 Buscar/Filtrar", "📈 Reportes"]
    )
    
    if option == "📊 Dashboard":
        st.header("📊 Dashboard General")
        
        col1, col2, col3, col4 = st.columns(4)
        
        if not df.empty:
            total_spaces = len(df)
            occupied = len(df[df['Estado'] == 'Ocupado']) if 'Estado' in df.columns else 0
            available = len(df[df['Estado'] == 'Disponible']) if 'Estado' in df.columns else 0
            maintenance = len(df[df['Estado'] == 'Mantenimiento']) if 'Estado' in df.columns else 0
            
            with col1:
                st.metric("Total Parqueaderos", total_spaces)
            with col2:
                st.metric("Ocupados", occupied)
            with col3:
                st.metric("Disponibles", available)
            with col4:
                st.metric("En Mantenimiento", maintenance)
            
            # Mostrar datos en tabla
            st.subheader("📋 Lista de Parqueaderos")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("📝 No hay parqueaderos registrados. Comienza agregando uno nuevo.")
    
    elif option == "➕ Agregar Parqueadero":
        st.header("➕ Agregar Nuevo Parqueadero")
        
        with st.form("add_parking_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                id_parqueadero = st.text_input("🆔 ID Parqueadero*", placeholder="P001")
                numero_parqueadero = st.text_input("🔢 Número de Parqueadero*", placeholder="101")
                tipo_parqueadero = st.selectbox("🚗 Tipo de Parqueadero*", 
                    ["Carro", "Moto", "Visitante", "Discapacitado"])
                estado = st.selectbox("📊 Estado*", 
                    ["Disponible", "Ocupado", "Mantenimiento", "Reservado"])
                apartamento_asignado = st.text_input("🏠 Apartamento Asignado", placeholder="Apt 101")
                propietario = st.text_input("👤 Propietario", placeholder="Nombre completo")
                placa_vehiculo = st.text_input("🚙 Placa del Vehículo", placeholder="ABC123")
            
            with col2:
                tipo_vehiculo = st.selectbox("🚗 Tipo de Vehículo", 
                    ["", "Automóvil", "Motocicleta", "Camioneta", "SUV", "Otro"])
                fecha_asignacion = st.date_input("📅 Fecha de Asignación", value=None)
                fecha_liberacion = st.date_input("📅 Fecha de Liberación", value=None)
                telefono_contacto = st.text_input("📞 Teléfono de Contacto", placeholder="+57 300 123 4567")
                email_contacto = st.text_input("📧 Email de Contacto", placeholder="ejemplo@email.com")
                observaciones = st.text_area("📝 Observaciones", placeholder="Comentarios adicionales...")
            
            submitted = st.form_submit_button("💾 Guardar Parqueadero", type="primary")
            
            if submitted:
                if not id_parqueadero or not numero_parqueadero or not tipo_parqueadero or not estado:
                    st.error("❌ Por favor completa todos los campos obligatorios (*)")
                else:
                    # Verificar si el ID ya existe
                    if not df.empty and id_parqueadero in df['ID_Parqueadero'].values:
                        st.error("❌ Ya existe un parqueadero con este ID")
                    else:
                        new_data = {
                            'ID_Parqueadero': id_parqueadero,
                            'Numero_Parqueadero': numero_parqueadero,
                            'Tipo_Parqueadero': tipo_parqueadero,
                            'Estado': estado,
                            'Apartamento_Asignado': apartamento_asignado,
                            'Propietario': propietario,
                            'Placa_Vehiculo': placa_vehiculo,
                            'Tipo_Vehiculo': tipo_vehiculo,
                            'Fecha_Asignacion': str(fecha_asignacion) if fecha_asignacion else '',
                            'Fecha_Liberacion': str(fecha_liberacion) if fecha_liberacion else '',
                            'Observaciones': observaciones,
                            'Telefono_Contacto': telefono_contacto,
                            'Email_Contacto': email_contacto
                        }
                        
                        if add_parking_space(worksheet, new_data):
                            st.success("✅ Parqueadero agregado exitosamente!")
                            time.sleep(2)
                            st.rerun()
    
    elif option == "✏️ Editar Parqueadero":
        st.header("✏️ Editar Parqueadero")
        
        if df.empty:
            st.info("📝 No hay parqueaderos para editar.")
        else:
            # Seleccionar parqueadero a editar
            parking_options = [f"{row['ID_Parqueadero']} - {row['Numero_Parqueadero']}" 
                             for _, row in df.iterrows()]
            selected_parking = st.selectbox("Selecciona el parqueadero a editar:", parking_options)
            
            if selected_parking:
                selected_id = selected_parking.split(" - ")[0]
                selected_row = df[df['ID_Parqueadero'] == selected_id].iloc[0]
                row_index = df[df['ID_Parqueadero'] == selected_id].index[0]
                
                with st.form("edit_parking_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        numero_parqueadero = st.text_input("🔢 Número de Parqueadero", 
                            value=selected_row.get('Numero_Parqueadero', ''))
                        tipo_parqueadero = st.selectbox("🚗 Tipo de Parqueadero", 
                            ["Carro", "Moto", "Visitante", "Discapacitado"],
                            index=["Carro", "Moto", "Visitante", "Discapacitado"].index(
                                selected_row.get('Tipo_Parqueadero', 'Carro')))
                        estado = st.selectbox("📊 Estado", 
                            ["Disponible", "Ocupado", "Mantenimiento", "Reservado"],
                            index=["Disponible", "Ocupado", "Mantenimiento", "Reservado"].index(
                                selected_row.get('Estado', 'Disponible')))
                        apartamento_asignado = st.text_input("🏠 Apartamento Asignado", 
                            value=selected_row.get('Apartamento_Asignado', ''))
                        propietario = st.text_input("👤 Propietario", 
                            value=selected_row.get('Propietario', ''))
                        placa_vehiculo = st.text_input("🚙 Placa del Vehículo", 
                            value=selected_row.get('Placa_Vehiculo', ''))
                    
                    with col2:
                        tipo_vehiculo = st.selectbox("🚗 Tipo de Vehículo", 
                            ["", "Automóvil", "Motocicleta", "Camioneta", "SUV", "Otro"],
                            index=0 if not selected_row.get('Tipo_Vehiculo') else 
                            ["", "Automóvil", "Motocicleta", "Camioneta", "SUV", "Otro"].index(
                                selected_row.get('Tipo_Vehiculo', '')))
                        telefono_contacto = st.text_input("📞 Teléfono de Contacto", 
                            value=selected_row.get('Telefono_Contacto', ''))
                        email_contacto = st.text_input("📧 Email de Contacto", 
                            value=selected_row.get('Email_Contacto', ''))
                        observaciones = st.text_area("📝 Observaciones", 
                            value=selected_row.get('Observaciones', ''))
                    
                    submitted = st.form_submit_button("💾 Actualizar Parqueadero", type="primary")
                    
                    if submitted:
                        updated_data = {
                            'Numero_Parqueadero': numero_parqueadero,
                            'Tipo_Parqueadero': tipo_parqueadero,
                            'Estado': estado,
                            'Apartamento_Asignado': apartamento_asignado,
                            'Propietario': propietario,
                            'Placa_Vehiculo': placa_vehiculo,
                            'Tipo_Vehiculo': tipo_vehiculo,
                            'Observaciones': observaciones,
                            'Telefono_Contacto': telefono_contacto,
                            'Email_Contacto': email_contacto
                        }
                        
                        if update_parking_space(worksheet, df, row_index, updated_data):
                            st.success("✅ Parqueadero actualizado exitosamente!")
                            time.sleep(2)
                            st.rerun()
    
    elif option == "🔍 Buscar/Filtrar":
        st.header("🔍 Buscar y Filtrar Parqueaderos")
        
        if df.empty:
            st.info("📝 No hay parqueaderos para filtrar.")
        else:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                filter_type = st.selectbox("🏷️ Filtrar por Tipo:", 
                    ["Todos"] + df['Tipo_Parqueadero'].unique().tolist() if 'Tipo_Parqueadero' in df.columns else ["Todos"])
            
            with col2:
                filter_status = st.selectbox("📊 Filtrar por Estado:", 
                    ["Todos"] + df['Estado'].unique().tolist() if 'Estado' in df.columns else ["Todos"])
            
            with col3:
                search_text = st.text_input("🔍 Buscar por texto:", placeholder="ID, número, propietario...")
            
            # Aplicar filtros
            filtered_df = df.copy()
            
            if filter_type != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo_Parqueadero'] == filter_type]
            
            if filter_status != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == filter_status]
            
            if search_text:
                mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_text, case=False, na=False)).any(axis=1)
                filtered_df = filtered_df[mask]
            
            st.subheader(f"📋 Resultados ({len(filtered_df)} parqueaderos encontrados)")
            st.dataframe(filtered_df, use_container_width=True)
    
    elif option == "📈 Reportes":
        st.header("📈 Reportes y Estadísticas")
        
        if df.empty:
            st.info("📝 No hay datos para generar reportes.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Distribución por Estado")
                if 'Estado' in df.columns:
                    estado_counts = df['Estado'].value_counts()
                    st.bar_chart(estado_counts)
            
            with col2:
                st.subheader("🚗 Distribución por Tipo")
                if 'Tipo_Parqueadero' in df.columns:
                    tipo_counts = df['Tipo_Parqueadero'].value_counts()
                    st.bar_chart(tipo_counts)
            
            # Resumen estadístico
            st.subheader("📋 Resumen Estadístico")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Parqueaderos", len(df))
            with col2:
                ocupados = len(df[df['Estado'] == 'Ocupado']) if 'Estado' in df.columns else 0
                st.metric("Ocupados", ocupados)
            with col3:
                disponibles = len(df[df['Estado'] == 'Disponible']) if 'Estado' in df.columns else 0
                st.metric("Disponibles", disponibles)
            with col4:
                ocupacion = (ocupados / len(df) * 100) if len(df) > 0 else 0
                st.metric("% Ocupación", f"{ocupacion:.1f}%")

#if __name__ == "__main__":
#    parqueadero_main()