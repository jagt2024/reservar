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
#    page_title="Control de Mascotas y Vehículos",
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
            st.success(f"✅ Conexión exitosa a Google Sheets!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
    
        return client

    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def get_worksheet(client, sheet_name="gestion-conjuntos", worksheet_name="mascotas_vehiculos"):
    """Obtener la hoja de trabajo específica"""
    try:
        spreadsheet = client.open(sheet_name)
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            return worksheet
        except gspread.WorksheetNotFound:
            # Crear la hoja si no existe
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            # Agregar encabezados
            headers = [
                'ID', 'Tipo', 'Torre/Bloque', 'Apartamento', 'Propietario/Residente',
                'Telefono', 'Email', 'Nombre_Mascota_Vehiculo', 'Raza_Marca', 
                'Color', 'Edad_Modelo', 'Placa_Chip', 'Observaciones', 
                'Estado', 'Fecha_Registro', 'Fecha_Actualizacion'
            ]
            worksheet.append_row(headers)
            st.success(f"✅ Hoja '{worksheet_name}' creada exitosamente")
            return worksheet
    except Exception as e:
        st.error(f"❌ Error accediendo a la hoja: {str(e)}")
        return None

def get_data_from_sheet(worksheet):
    """Obtener todos los datos de la hoja"""
    try:
        records = worksheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            return df
        else:
            # Retornar DataFrame vacío con las columnas correctas
            columns = [
                'ID', 'Tipo', 'Torre/Bloque', 'Apartamento', 'Propietario/Residente',
                'Telefono', 'Email', 'Nombre_Mascota_Vehiculo', 'Raza_Marca', 
                'Color', 'Edad_Modelo', 'Placa_Chip', 'Observaciones', 
                'Estado', 'Fecha_Registro', 'Fecha_Actualizacion'
            ]
            return pd.DataFrame(columns=columns)
    except Exception as e:
        st.error(f"❌ Error obteniendo datos: {str(e)}")
        return None

def generate_id(df, tipo):
    """Generar ID único para el registro"""
    if df.empty:
        return f"{tipo}001"
    
    # Filtrar por tipo para obtener el último ID del mismo tipo
    tipo_df = df[df['Tipo'] == tipo]
    if tipo_df.empty:
        return f"{tipo}001"
    
    # Extraer números de los IDs existentes del mismo tipo
    ids = tipo_df['ID'].astype(str).tolist()
    numbers = []
    for id_str in ids:
        if id_str.startswith(tipo):
            try:
                num = int(id_str.replace(tipo, ''))
                numbers.append(num)
            except ValueError:
                continue
    
    if numbers:
        next_num = max(numbers) + 1
        return f"{tipo}{next_num:03d}"
    else:
        return f"{tipo}001"

def add_record(worksheet, data):
    """Agregar nuevo registro a la hoja"""
    try:
        worksheet.append_row(data)
        return True
    except Exception as e:
        st.error(f"❌ Error agregando registro: {str(e)}")
        return False

def update_record(worksheet, row_index, data):
    """Actualizar registro existente"""
    try:
        # row_index + 2 porque la primera fila son headers y gspread usa 1-indexing
        for i, value in enumerate(data, start=1):
            worksheet.update_cell(row_index + 2, i, value)
        return True
    except Exception as e:
        st.error(f"❌ Error actualizando registro: {str(e)}")
        return False

def delete_record(worksheet, row_index):
    """Eliminar registro"""
    try:
        # row_index + 2 porque la primera fila son headers y gspread usa 1-indexing
        worksheet.delete_rows(row_index + 2)
        return True
    except Exception as e:
        st.error(f"❌ Error eliminando registro: {str(e)}")
        return False

def mascove_main():
    st.title("🏠 Control de Mascotas y Vehículos")
    st.markdown("Sistema de gestión para conjuntos residenciales")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Conectar a Google Sheets
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Obtener worksheet
    worksheet = get_worksheet(client)
    if not worksheet:
        st.stop()
    
    # Sidebar para navegación
    st.sidebar.title("📋 Menú de Opciones")
    option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["🏠 Dashboard", "➕ Registrar Nuevo", "👀 Consultar Registros", 
         "✏️ Editar Registro", "🗑️ Eliminar Registro", "📊 Reportes"]
    )
    
    # Obtener datos actuales
    df = get_data_from_sheet(worksheet)
    if df is None:
        st.error("No se pudieron cargar los datos")
        st.stop()
    
    # Dashboard
    if option == "🏠 Dashboard":
        st.header("📊 Dashboard General")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_registros = len(df)
        mascotas = len(df[df['Tipo'] == 'Mascota']) if not df.empty else 0
        vehiculos = len(df[df['Tipo'] == 'Vehiculo']) if not df.empty else 0
        activos = len(df[df['Estado'] == 'Activo']) if not df.empty else 0
        
        col1.metric("Total Registros", total_registros)
        col2.metric("🐕 Mascotas", mascotas)
        col3.metric("🚗 Vehículos", vehiculos)
        col4.metric("✅ Activos", activos)
        
        if not df.empty:
            st.subheader("📋 Registros Recientes")
            st.dataframe(df.tail(10), use_container_width=True)
    
    # Registrar Nuevo
    elif option == "➕ Registrar Nuevo":
        st.header("➕ Registrar Nueva Mascota o Vehículo")
        
        with st.form("registro_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                tipo = st.selectbox("Tipo *", ["Mascota", "Vehiculo"])
                torre_bloque = st.text_input("Torre/Bloque *")
                apartamento = st.text_input("Apartamento *")
                propietario = st.text_input("Propietario/Residente *")
                telefono = st.text_input("Teléfono")
                email = st.text_input("Email")
            
            with col2:
                if tipo == "Mascota":
                    nombre = st.text_input("Nombre de la Mascota *")
                    raza_marca = st.text_input("Raza *")
                    edad_modelo = st.text_input("Edad")
                    placa_chip = st.text_input("Número de Chip")
                else:
                    nombre = st.text_input("Descripción del Vehículo *")
                    raza_marca = st.text_input("Marca *")
                    edad_modelo = st.text_input("Modelo/Año")
                    placa_chip = st.text_input("Placa *")
                
                color = st.text_input("Color")
                observaciones = st.text_area("Observaciones")
                estado = st.selectbox("Estado", ["Activo", "Inactivo"])
            
            submitted = st.form_submit_button("💾 Registrar", type="primary")
            
            if submitted:
                if not all([tipo, torre_bloque, apartamento, propietario, nombre, raza_marca]):
                    st.error("❌ Por favor completa todos los campos obligatorios (*)")
                else:
                    # Generar ID único
                    new_id = generate_id(df, tipo[:1].upper())  # M para Mascota, V para Vehiculo
                    
                    # Preparar datos
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    data = [
                        new_id, tipo, torre_bloque, apartamento, propietario,
                        telefono, email, nombre, raza_marca, color,
                        edad_modelo, placa_chip, observaciones, estado,
                        fecha_actual, fecha_actual
                    ]
                    
                    # Agregar registro
                    if add_record(worksheet, data):
                        st.success(f"✅ {tipo} registrado exitosamente con ID: {new_id}")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar")
    
    # Consultar Registros
    elif option == "👀 Consultar Registros":
        st.header("👀 Consultar Registros")
        
        if df.empty:
            st.info("📋 No hay registros disponibles")
        else:
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                tipo_filter = st.selectbox("Filtrar por Tipo", ["Todos", "Mascota", "Vehiculo"])
            with col2:
                torre_filter = st.selectbox("Filtrar por Torre/Bloque", 
                                          ["Todos"] + sorted(df['Torre/Bloque'].unique().tolist()))
            with col3:
                estado_filter = st.selectbox("Filtrar por Estado", 
                                           ["Todos", "Activo", "Inactivo"])
            
            # Aplicar filtros
            filtered_df = df.copy()
            
            if tipo_filter != "Todos":
                filtered_df = filtered_df[filtered_df['Tipo'] == tipo_filter]
            
            if torre_filter != "Todos":
                filtered_df = filtered_df[filtered_df['Torre/Bloque'] == torre_filter]
            
            if estado_filter != "Todos":
                filtered_df = filtered_df[filtered_df['Estado'] == estado_filter]
            
            # Búsqueda por texto
            search_term = st.text_input("🔍 Buscar por nombre, propietario o placa:")
            if search_term:
                mask = (
                    filtered_df['Nombre_Mascota_Vehiculo'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Propietario/Residente'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Placa_Chip'].str.contains(search_term, case=False, na=False)
                )
                filtered_df = filtered_df[mask]
            
            st.write(f"📊 Mostrando {len(filtered_df)} de {len(df)} registros")
            
            if not filtered_df.empty:
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.info("🔍 No se encontraron registros con los filtros aplicados")
    
    # Editar Registro
    elif option == "✏️ Editar Registro":
        st.header("✏️ Editar Registro")
        
        if df.empty:
            st.info("📋 No hay registros disponibles para editar")
        else:
            # Seleccionar registro a editar
            registro_options = []
            for idx, row in df.iterrows():
                registro_options.append(f"{row['ID']} - {row['Tipo']} - {row['Nombre_Mascota_Vehiculo']} ({row['Torre/Bloque']}-{row['Apartamento']})")
            
            selected_registro = st.selectbox("Selecciona el registro a editar:", registro_options)
            
            if selected_registro:
                # Obtener índice del registro seleccionado
                selected_idx = registro_options.index(selected_registro)
                registro = df.iloc[selected_idx]
                
                st.subheader(f"Editando: {registro['ID']}")
                
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        tipo = st.selectbox("Tipo *", ["Mascota", "Vehiculo"], 
                                          index=0 if registro['Tipo'] == 'Mascota' else 1)
                        torre_bloque = st.text_input("Torre/Bloque *", value=registro['Torre/Bloque'])
                        apartamento = st.text_input("Apartamento *", value=registro['Apartamento'])
                        propietario = st.text_input("Propietario/Residente *", value=registro['Propietario/Residente'])
                        telefono = st.text_input("Teléfono", value=registro['Telefono'])
                        email = st.text_input("Email", value=registro['Email'])
                    
                    with col2:
                        nombre = st.text_input("Nombre/Descripción *", value=registro['Nombre_Mascota_Vehiculo'])
                        raza_marca = st.text_input("Raza/Marca *", value=registro['Raza_Marca'])
                        color = st.text_input("Color", value=registro['Color'])
                        edad_modelo = st.text_input("Edad/Modelo", value=registro['Edad_Modelo'])
                        placa_chip = st.text_input("Placa/Chip", value=registro['Placa_Chip'])
                        observaciones = st.text_area("Observaciones", value=registro['Observaciones'])
                        estado = st.selectbox("Estado", ["Activo", "Inactivo"], 
                                            index=0 if registro['Estado'] == 'Activo' else 1)
                    
                    updated = st.form_submit_button("💾 Actualizar", type="primary")
                    
                    if updated:
                        if not all([tipo, torre_bloque, apartamento, propietario, nombre, raza_marca]):
                            st.error("❌ Por favor completa todos los campos obligatorios (*)")
                        else:
                            # Preparar datos actualizados
                            fecha_actualizacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            data = [
                                registro['ID'], tipo, torre_bloque, apartamento, propietario,
                                telefono, email, nombre, raza_marca, color,
                                edad_modelo, placa_chip, observaciones, estado,
                                registro['Fecha_Registro'], fecha_actualizacion
                            ]
                            
                            # Actualizar registro
                            if update_record(worksheet, selected_idx, data):
                                st.success("✅ Registro actualizado exitosamente")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar registro")
    
    # Eliminar Registro
    elif option == "🗑️ Eliminar Registro":
        st.header("🗑️ Eliminar Registro")
        
        if df.empty:
            st.info("📋 No hay registros disponibles para eliminar")
        else:
            # Seleccionar registro a eliminar
            registro_options = []
            for idx, row in df.iterrows():
                registro_options.append(f"{row['ID']} - {row['Tipo']} - {row['Nombre_Mascota_Vehiculo']} ({row['Torre/Bloque']}-{row['Apartamento']})")
            
            selected_registro = st.selectbox("Selecciona el registro a eliminar:", registro_options)
            
            if selected_registro:
                # Obtener índice del registro seleccionado
                selected_idx = registro_options.index(selected_registro)
                registro = df.iloc[selected_idx]
                
                st.subheader("⚠️ Confirmar Eliminación")
                st.warning(f"Estás a punto de eliminar el registro: **{registro['ID']} - {registro['Nombre_Mascota_Vehiculo']}**")
                
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    if st.button("🗑️ Confirmar Eliminación", type="primary"):
                        if delete_record(worksheet, selected_idx):
                            st.success("✅ Registro eliminado exitosamente")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Error al eliminar registro")
                
                with col2:
                    st.info("Esta acción no se puede deshacer")
    
    # Reportes
    elif option == "📊 Reportes":
        st.header("📊 Reportes y Estadísticas")
        
        if df.empty:
            st.info("📋 No hay datos disponibles para generar reportes")
        else:
            # Estadísticas generales
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📈 Estadísticas por Tipo")
                tipo_counts = df['Tipo'].value_counts()
                st.bar_chart(tipo_counts)
            
            with col2:
                st.subheader("🏢 Distribución por Torre/Bloque")
                torre_counts = df['Torre/Bloque'].value_counts()
                st.bar_chart(torre_counts)
            
            # Tabla resumen
            st.subheader("📋 Resumen por Torre/Bloque")
            resumen = df.groupby(['Torre/Bloque', 'Tipo']).size().unstack(fill_value=0)
            st.dataframe(resumen, use_container_width=True)
            
            # Opción para descargar datos
            st.subheader("💾 Exportar Datos")
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"mascotas_vehiculos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

#if __name__ == "__main__":
#    mascove_main()