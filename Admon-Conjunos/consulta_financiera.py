import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import base64

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión Financiera - Consultas",
#    page_icon="💰",
#    layout="wide"
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

@st.cache_data(ttl=300)
def load_data_from_sheets(_client):
    """Cargar datos desde Google Sheets"""
    try:
        # Abrir el archivo de Google Sheets
        spreadsheet = _client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Administracion_Financiera")
        
        # Obtener todos los datos
        data = worksheet.get_all_records()
        
        if not data:
            st.warning("⚠️ No se encontraron datos en la hoja")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Convertir columna de fecha si existe
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        
        return df
        
    except gspread.SpreadsheetNotFound:
        st.error("❌ No se encontró el archivo 'gestion-conjuntos'")
        return pd.DataFrame()
    except gspread.WorksheetNotFound:
        st.error("❌ No se encontró la hoja 'gestion_financiera'")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return pd.DataFrame()

def create_pdf_report(df, filters_info):
    """Crear reporte PDF con los datos filtrados"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkblue,
        alignment=1,  # Centrado
        spaceAfter=20
    )
    
    # Título
    title = Paragraph("Reporte de Gestión Financiera", title_style)
    elements.append(title)
    
    # Información de filtros aplicados
    filter_text = f"<b>Filtros aplicados:</b><br/>"
    for key, value in filters_info.items():
        if value and value != "Todos":
            filter_text += f"• {key}: {value}<br/>"
    
    if filter_text != "<b>Filtros aplicados:</b><br/>":
        filter_para = Paragraph(filter_text, styles['Normal'])
        elements.append(filter_para)
        elements.append(Spacer(1, 12))
    
    # Información del reporte
    fecha_generacion = datetime.now().strftime("%d/%m/%Y %H:%M")
    info_text = f"<b>Fecha de generación:</b> {fecha_generacion}<br/><b>Total de registros:</b> {len(df)}"
    info_para = Paragraph(info_text, styles['Normal'])
    elements.append(info_para)
    elements.append(Spacer(1, 20))
    
    if len(df) > 0:
        # Preparar datos para la tabla
        # Seleccionar solo las columnas requeridas
        required_columns = ['Tipo_Operacion', 'Unidad', 'Concepto', 'Monto', 'Fecha', 'Banco', 'Estado', 'Metodo_Pago']
        
        # Verificar qué columnas existen en el DataFrame
        available_columns = [col for col in required_columns if col in df.columns]
        
        if not available_columns:
            elements.append(Paragraph("❌ No se encontraron las columnas requeridas en los datos", styles['Normal']))
        else:
            # Crear datos para la tabla
            df_report = df[available_columns].copy()
            
            # Formatear fecha si existe
            if 'Fecha' in df_report.columns:
                df_report['Fecha'] = df_report['Fecha'].dt.strftime('%d/%m/%Y')
            
            # Encabezados
            headers = available_columns
            
            # Datos de la tabla
            table_data = [headers]
            
            for _, row in df_report.iterrows():
                table_data.append([str(row[col]) if pd.notna(row[col]) else '' for col in available_columns])
            
            # Crear tabla
            table = Table(table_data)
            
            # Estilo de la tabla
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
    else:
        elements.append(Paragraph("No hay datos para mostrar con los filtros aplicados", styles['Normal']))
    
    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def consulta_main():
    st.title("💰 Gestión Financiera - Sistema de Consultas")
    st.markdown("---")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    
    if creds is None:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    
    if client is None:
        st.stop()
    
    # Cargar datos
    with st.spinner("Cargando datos desde Google Sheets..."):
        df = load_data_from_sheets(client)
    
    if df.empty:
        st.warning("No hay datos disponibles para mostrar")
        st.stop()
    
    st.success(f"✅ Datos cargados exitosamente: {len(df)} registros")
    
    # Mostrar información de las columnas disponibles
    with st.expander("📊 Información de los datos"):
        st.write(f"**Columnas disponibles:** {', '.join(df.columns.tolist())}")
        st.write(f"**Total de registros:** {len(df)}")
        if 'Fecha' in df.columns and not df['Fecha'].isna().all():
            fecha_min = df['Fecha'].min()
            fecha_max = df['Fecha'].max()
            st.write(f"**Rango de fechas:** {fecha_min.strftime('%d/%m/%Y')} - {fecha_max.strftime('%d/%m/%Y')}")
    
    # Sidebar para filtros
    st.sidebar.header("🔍 Filtros de Búsqueda")
    
    # Filtros
    filters = {}
    
    # Filtro por Unidad
    if 'Unidad' in df.columns:
        unidades = ['Todos'] + sorted(df['Unidad'].dropna().unique().tolist())
        filtro_unidad = st.sidebar.selectbox("Filtrar por Unidad:", unidades)
        filters['Unidad'] = filtro_unidad
    
    # Filtro por Estado
    if 'Estado' in df.columns:
        estados = ['Todos'] + sorted(df['Estado'].dropna().unique().tolist())
        filtro_estado = st.sidebar.selectbox("Filtrar por Estado:", estados)
        filters['Estado'] = filtro_estado
    
    # Filtro por Fecha
    if 'Fecha' in df.columns and not df['Fecha'].isna().all():
        st.sidebar.subheader("📅 Rango de Fechas")
        fecha_min = df['Fecha'].min().date()
        fecha_max = df['Fecha'].max().date()
        
        fecha_inicio = st.sidebar.date_input(
            "Fecha inicio:",
            value=fecha_min,
            min_value=fecha_min,
            max_value=fecha_max
        )
        
        fecha_fin = st.sidebar.date_input(
            "Fecha fin:",
            value=fecha_max,
            min_value=fecha_min,
            max_value=fecha_max
        )
        
        filters['Fecha Inicio'] = fecha_inicio.strftime('%d/%m/%Y')
        filters['Fecha Fin'] = fecha_fin.strftime('%d/%m/%Y')
    
    # Aplicar filtros
    df_filtered = df.copy()
    
    # Filtrar por Unidad
    if 'Unidad' in filters and filters['Unidad'] != 'Todos':
        df_filtered = df_filtered[df_filtered['Unidad'] == filters['Unidad']]
    
    # Filtrar por Estado
    if 'Estado' in filters and filters['Estado'] != 'Todos':
        df_filtered = df_filtered[df_filtered['Estado'] == filters['Estado']]
    
    # Filtrar por Fecha
    if 'Fecha' in df.columns and 'Fecha Inicio' in filters:
        fecha_inicio_dt = pd.to_datetime(fecha_inicio)
        fecha_fin_dt = pd.to_datetime(fecha_fin)
        df_filtered = df_filtered[
            (df_filtered['Fecha'] >= fecha_inicio_dt) & 
            (df_filtered['Fecha'] <= fecha_fin_dt)
        ]
    
    # Mostrar resultados
    st.header("📊 Resultados de la Consulta")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Registros", len(df))
    with col2:
        st.metric("Registros Filtrados", len(df_filtered))
    with col3:
        if len(df) > 0:
            porcentaje = (len(df_filtered) / len(df)) * 100
            st.metric("Porcentaje Mostrado", f"{porcentaje:.1f}%")
    
    # Mostrar datos filtrados
    if len(df_filtered) > 0:
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True
        )
        
        # Botón para generar PDF
        st.header("📄 Generar Reporte PDF")
        
        if st.button("🔽 Descargar Reporte PDF", type="primary"):
            with st.spinner("Generando reporte PDF..."):
                try:
                    pdf_buffer = create_pdf_report(df_filtered, filters)
                    
                    # Crear nombre del archivo
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"reporte_gestion_financiera_{timestamp}.pdf"
                    
                    st.download_button(
                        label="📁 Descargar PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=filename,
                        mime="application/pdf"
                    )
                    
                    st.success("✅ Reporte PDF generado exitosamente!")
                    
                except Exception as e:
                    st.error(f"❌ Error generando PDF: {str(e)}")
    
    else:
        st.warning("⚠️ No se encontraron registros con los filtros aplicados")
        st.info("💡 Intenta ajustar los filtros para obtener resultados")
    
    # Información adicional
    st.markdown("---")
    with st.expander("ℹ️ Información del Sistema"):
        st.markdown("""
        **Funcionalidades disponibles:**
        - ✅ Filtrado por Unidad
        - ✅ Filtrado por Estado  
        - ✅ Filtrado por rango de fechas
        - ✅ Visualización de datos en tiempo real
        - ✅ Generación de reportes PDF
        - ✅ Descarga de reportes con filtros aplicados
        
        **Columnas incluidas en el PDF:**
        - Tipo_Operacion
        - Unidad
        - Concepto
        - Monto
        - Fecha
        - Banco
        - Estado
        - Metodo_Pago
        """)

#if __name__ == "__main__":
#    consulta_main()