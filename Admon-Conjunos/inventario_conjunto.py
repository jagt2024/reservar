import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
import io

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión de Inventarios - Conjunto Residencial",
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
            st.success(f"✅ Conexión exitosa - {len(sheets)} hojas disponibles")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero con acceso limitado: {str(e)}")
        
        return client
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

def get_or_create_inventory_sheet(client, spreadsheet_name):
    """Obtener o crear la hoja de inventarios"""
    try:
        # Intentar abrir la hoja existente
        spreadsheet = client.open(spreadsheet_name)
        st.success(f"📊 Hoja '{spreadsheet_name}' encontrada")
        
        # Verificar si existe la pestaña 'inventarios'
        try:
            worksheet = spreadsheet.worksheet('inventarios')
            st.info("📋 Pestaña 'inventarios' existente encontrada")
        except gspread.WorksheetNotFound:
            # Crear la pestaña 'inventarios'
            worksheet = spreadsheet.add_worksheet(title='inventarios', rows=1000, cols=20)
            
            # Definir las columnas del inventario
            headers = [
                'ID_Registro',
                'Fecha_Registro',
                'Apartamento_Unidad',
                'Torre_Bloque',
                'Propietario_Inquilino',
                'Tipo_Persona',
                'Contacto_Telefono',
                'Contacto_Email',
                'Categoria_Elemento',
                'Elemento_Descripcion',
                'Marca',
                'Modelo',
                'Serial_Codigo',
                'Estado_Conservacion',
                'Valor_Estimado',
                'Ubicacion_Especifica',
                'Observaciones',
                'Fecha_Ingreso_Propiedad',
                'Responsable_Registro',
                'Estado_Inventario'
            ]
            
            # Insertar encabezados
            worksheet.insert_row(headers, 1)
            st.success("✅ Pestaña 'inventarios' creada con las columnas requeridas")
        
        return spreadsheet, worksheet
    
    except gspread.SpreadsheetNotFound:
        st.error(f"❌ No se encontró la hoja '{spreadsheet_name}'")
        st.info("Verifica que el nombre de la hoja sea correcto y que tengas permisos de acceso")
        return None, None
    except Exception as e:
        st.error(f"❌ Error accediendo a la hoja: {str(e)}")
        return None, None

def load_existing_inventory(worksheet):
    """Cargar inventario existente desde Google Sheets"""
    try:
        records = worksheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando inventario existente: {str(e)}")
        return pd.DataFrame()

def save_inventory_record(worksheet, record_data):
    """Guardar un registro de inventario"""
    try:
        # Generar ID único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        record_data['ID_Registro'] = f"INV_{timestamp}"
        record_data['Fecha_Registro'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convertir a lista en el orden de las columnas
        row_data = [
            record_data['ID_Registro'],
            record_data['Fecha_Registro'],
            record_data['Apartamento_Unidad'],
            record_data['Torre_Bloque'],
            record_data['Propietario_Inquilino'],
            record_data['Tipo_Persona'],
            record_data['Contacto_Telefono'],
            record_data['Contacto_Email'],
            record_data['Categoria_Elemento'],
            record_data['Elemento_Descripcion'],
            record_data['Marca'],
            record_data['Modelo'],
            record_data['Serial_Codigo'],
            record_data['Estado_Conservacion'],
            record_data['Valor_Estimado'],
            record_data['Ubicacion_Especifica'],
            record_data['Observaciones'],
            record_data['Fecha_Ingreso_Propiedad'],
            record_data['Responsable_Registro'],
            record_data['Estado_Inventario']
        ]
        
        worksheet.append_row(row_data)
        return True, record_data['ID_Registro']
    except Exception as e:
        st.error(f"Error guardando registro: {str(e)}")
        return False, None

def create_download_excel(df):
    """Crear archivo Excel para descarga"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Inventarios', index=False)
        
        # Ajustar ancho de columnas
        worksheet = writer.sheets['Inventarios']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return output.getvalue()

def inventario_main():
    st.title("🏠 Sistema de Gestión de Inventarios")
    st.markdown("### Conjunto Residencial - Control de Elementos y Propiedades")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    if not creds:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    if not client:
        st.stop()
    
    # Sidebar para configuración
    st.sidebar.header("⚙️ Configuración")
    spreadsheet_name = st.sidebar.text_input(
        "Nombre de la hoja de Google Sheets:", 
        value="gestion-conjuntos",
        help="Nombre exacto de tu hoja de Google Sheets"
    )
    
    if not spreadsheet_name:
        st.warning("⚠️ Por favor ingresa el nombre de la hoja de Google Sheets")
        st.stop()
    
    # Obtener o crear hoja de inventarios
    spreadsheet, worksheet = get_or_create_inventory_sheet(client, spreadsheet_name)
    if not worksheet:
        st.stop()
    
    # Pestañas principales
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Nuevo Registro", "📊 Ver Inventario", "📈 Estadísticas", "⬇️ Descargar"])
    
    with tab1:
        st.header("📝 Registrar Nuevo Elemento")
        
        with st.form("inventory_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏠 Información de la Unidad")
                apartamento = st.text_input("Apartamento/Unidad*", placeholder="Ej: 101, 202A")
                torre = st.text_input("Torre/Bloque", placeholder="Ej: Torre A, Bloque 1")
                
                st.subheader("👤 Información del Responsable")
                propietario = st.text_input("Propietario/Inquilino*", placeholder="Nombre completo")
                tipo_persona = st.selectbox("Tipo de Persona", ["Propietario", "Inquilino", "Administrador"])
                telefono = st.text_input("Teléfono", placeholder="Ej: +57 300 123 4567")
                email = st.text_input("Email", placeholder="ejemplo@correo.com")
            
            with col2:
                st.subheader("📦 Información del Elemento")
                categoria = st.selectbox(
                    "Categoría del Elemento*",
                    ["Electrodomésticos", "Muebles", "Electrónicos", "Decoración", 
                     "Iluminación", "Herramientas", "Ropa de Hogar", "Otros"]
                )
                descripcion = st.text_area("Descripción del Elemento*", placeholder="Descripción detallada del elemento")
                marca = st.text_input("Marca", placeholder="Ej: Samsung, LG, Ikea")
                modelo = st.text_input("Modelo", placeholder="Modelo específico")
                serial = st.text_input("Serial/Código", placeholder="Número de serie o código")
                
                estado = st.selectbox(
                    "Estado de Conservación*",
                    ["Excelente", "Bueno", "Regular", "Malo", "Requiere Reparación"]
                )
                valor = st.number_input("Valor Estimado ($)", min_value=0, step=1000)
            
            col3, col4 = st.columns(2)
            with col3:
                ubicacion = st.text_input("Ubicación Específica", placeholder="Ej: Sala, Cocina, Dormitorio principal")
                fecha_ingreso = st.date_input("Fecha de Ingreso a la Propiedad", value=date.today())
            
            with col4:
                responsable = st.text_input("Responsable del Registro*", placeholder="Quien registra este elemento")
                estado_inventario = st.selectbox("Estado del Inventario", ["Activo", "Inactivo", "En Revisión"])
                observaciones = st.text_area("Observaciones", placeholder="Comentarios adicionales...")
            
            submitted = st.form_submit_button("💾 Guardar Registro", type="primary")
            
            if submitted:
                # Validar campos obligatorios
                if not all([apartamento, propietario, categoria, descripcion, estado, responsable]):
                    st.error("❌ Por favor completa todos los campos obligatorios marcados con *")
                else:
                    # Preparar datos del registro
                    record_data = {
                        'Apartamento_Unidad': apartamento,
                        'Torre_Bloque': torre,
                        'Propietario_Inquilino': propietario,
                        'Tipo_Persona': tipo_persona,
                        'Contacto_Telefono': telefono,
                        'Contacto_Email': email,
                        'Categoria_Elemento': categoria,
                        'Elemento_Descripcion': descripcion,
                        'Marca': marca,
                        'Modelo': modelo,
                        'Serial_Codigo': serial,
                        'Estado_Conservacion': estado,
                        'Valor_Estimado': valor,
                        'Ubicacion_Especifica': ubicacion,
                        'Observaciones': observaciones,
                        'Fecha_Ingreso_Propiedad': fecha_ingreso.strftime("%Y-%m-%d"),
                        'Responsable_Registro': responsable,
                        'Estado_Inventario': estado_inventario
                    }
                    
                    # Guardar registro
                    success, record_id = save_inventory_record(worksheet, record_data)
                    if success:
                        st.success(f"✅ Registro guardado exitosamente! ID: {record_id}")
                        st.balloons()
                    else:
                        st.error("❌ Error al guardar el registro")
    
    with tab2:
        st.header("📊 Inventario Actual")
        
        # Cargar datos existentes
        df_inventory = load_existing_inventory(worksheet)
        
        if not df_inventory.empty:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_apartamento = st.selectbox(
                    "Filtrar por Apartamento", 
                    ["Todos"] + sorted(df_inventory['Apartamento_Unidad'].unique().tolist())
                )
            with col2:
                filter_categoria = st.selectbox(
                    "Filtrar por Categoría", 
                    ["Todas"] + sorted(df_inventory['Categoria_Elemento'].unique().tolist())
                )
            with col3:
                filter_estado = st.selectbox(
                    "Filtrar por Estado", 
                    ["Todos"] + sorted(df_inventory['Estado_Conservacion'].unique().tolist())
                )
            
            # Aplicar filtros
            filtered_df = df_inventory.copy()
            if filter_apartamento != "Todos":
                filtered_df = filtered_df[filtered_df['Apartamento_Unidad'] == filter_apartamento]
            if filter_categoria != "Todas":
                filtered_df = filtered_df[filtered_df['Categoria_Elemento'] == filter_categoria]
            if filter_estado != "Todos":
                filtered_df = filtered_df[filtered_df['Estado_Conservacion'] == filter_estado]
            
            # Mostrar tabla
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )
            
            st.info(f"📊 Mostrando {len(filtered_df)} de {len(df_inventory)} registros")
        else:
            st.info("📝 No hay registros de inventario aún. Comienza agregando elementos en la pestaña 'Nuevo Registro'")
    
    with tab3:
        st.header("📈 Estadísticas del Inventario")
        
        df_inventory = load_existing_inventory(worksheet)
        
        if not df_inventory.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_elementos = len(df_inventory)
                st.metric("Total Elementos", total_elementos)
            
            with col2:
                total_apartamentos = df_inventory['Apartamento_Unidad'].nunique()
                st.metric("Apartamentos con Inventario", total_apartamentos)
            
            with col3:
                if 'Valor_Estimado' in df_inventory.columns:
                    valor_total = df_inventory['Valor_Estimado'].sum()
                    st.metric("Valor Total Estimado", f"${valor_total:,.0f}")
                else:
                    st.metric("Valor Total Estimado", "N/A")
            
            with col4:
                categorias_count = df_inventory['Categoria_Elemento'].nunique()
                st.metric("Categorías Diferentes", categorias_count)
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Elementos por Categoría")
                categoria_counts = df_inventory['Categoria_Elemento'].value_counts()
                st.bar_chart(categoria_counts)
            
            with col2:
                st.subheader("🏠 Elementos por Apartamento")
                apartamento_counts = df_inventory['Apartamento_Unidad'].value_counts().head(10)
                st.bar_chart(apartamento_counts)
            
            # Estado de conservación
            st.subheader("⚡ Estado de Conservación")
            estado_counts = df_inventory['Estado_Conservacion'].value_counts()
            st.bar_chart(estado_counts)
        else:
            st.info("📊 No hay datos suficientes para mostrar estadísticas")
    
    with tab4:
        st.header("⬇️ Descargar Inventario")
        
        df_inventory = load_existing_inventory(worksheet)
        
        if not df_inventory.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Resumen de Descarga")
                st.write(f"📝 Total de registros: {len(df_inventory)}")
                st.write(f"🏠 Apartamentos: {df_inventory['Apartamento_Unidad'].nunique()}")
                st.write(f"📦 Categorías: {df_inventory['Categoria_Elemento'].nunique()}")
            
            with col2:
                st.subheader("📁 Opciones de Descarga")
                
                # Descarga CSV
                csv_data = df_inventory.to_csv(index=False)
                st.download_button(
                    label="📄 Descargar CSV",
                    data=csv_data,
                    file_name=f"inventario_conjunto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
                # Descarga Excel
                excel_data = create_download_excel(df_inventory)
                st.download_button(
                    label="📊 Descargar Excel",
                    data=excel_data,
                    file_name=f"inventario_conjunto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            # Vista previa de datos
            st.subheader("👀 Vista Previa")
            st.dataframe(df_inventory.head(), use_container_width=True)
        else:
            st.info("📝 No hay registros para descargar")
    
    # Footer
    st.markdown("---")
    st.markdown("🏠 **Sistema de Gestión de Inventarios** - Desarrollado para control de elementos en conjuntos residenciales")

#if __name__ == "__main__":
#    inventario_main()