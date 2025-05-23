import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import json
import toml
import time
import traceback

# Configuración de la página
#st.set_page_config(
#    page_title="Gestión Agenda - Consulta Candidatos",
#    page_icon="📅",
#    layout="wide"
##)

# Funciones de credenciales
def load_credentials_from_toml():
    """Load credentials from secrets.toml file"""
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return None, None

@st.cache_resource(ttl=300)
def get_google_sheets_connection(creds):
    """Establish connection with Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_google_sheet_data(sheet_name='gestion-agenda', worksheet_name="candidatos"):
    """
    Carga datos desde Google Sheets con manejo robusto de errores y reintentos
    """
    from googleapiclient.errors import HttpError
    import time
    import traceback
    
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2
    
    try:
        # Cargar credenciales
        creds, config = load_credentials_from_toml()
        if not creds:
            return None
            
        # Establecer conexión
        client = get_google_sheets_connection(creds)
        if not client:
            return None
        
        # Reintentos para manejo de cuota excedida
        for intento in range(MAX_RETRIES):
            try:
                with st.spinner(f'Cargando datos... (Intento {intento + 1}/{MAX_RETRIES})'):
                    sheet = client.open(sheet_name)
                    worksheet = sheet.worksheet(worksheet_name)
                    
                    # Lista de encabezados esperados para candidatos
                    expected_headers = ['nombre', 'cargo', 'fecha', 'identificacion', 'telefono', 'email']
                    
                    # Intentar usar expected_headers para evitar problemas con encabezados duplicados
                    try:
                        records = worksheet.get_all_records(expected_headers=expected_headers)
                        df = pd.DataFrame(records)
                        return df
                        
                    except Exception as header_error:
                        st.warning(f"No se pudieron usar los encabezados esperados: {str(header_error)}")
                        
                        # Plan B: Obtener valores y crear diccionarios manualmente
                        all_values = worksheet.get_all_values()
                        headers = all_values[0] if all_values else []
                        
                        # Crear headers únicos
                        unique_headers = []
                        header_count = {}
                        
                        for header in headers:
                            if header in header_count:
                                header_count[header] += 1
                                unique_header = f"{header}_{header_count[header]}"
                            else:
                                header_count[header] = 0
                                unique_header = header
                            
                            unique_headers.append(unique_header)
                        
                        # Crear registros con headers únicos
                        records = []
                        for i in range(1, len(all_values)):
                            row = all_values[i]
                            record = {}
                            for j in range(min(len(unique_headers), len(row))):
                                record[unique_headers[j]] = row[j]
                            records.append(record)
                        
                        df = pd.DataFrame(records)
                        return df

            except HttpError as error:
                if error.resp.status == 429:  # Error de cuota excedida
                    if intento < MAX_RETRIES - 1:
                        delay = INITIAL_RETRY_DELAY * (2 ** intento)
                        st.warning(f"Límite de cuota excedida. Esperando {delay} segundos...")
                        time.sleep(delay)
                        continue
                    else:
                        st.error("Se excedió el límite de intentos. Por favor, intenta más tarde.")
                        return None
                else:
                    st.error(f"Error de la API: {str(error)}")
                    return None
                    
        return None  # Si se agotaron los intentos

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        st.error(f"Detalles: {traceback.format_exc()}")
        return None

def filter_data(df, cargo_filter=None, fecha_inicio=None, fecha_fin=None):
    """
    Filtra los datos según los criterios especificados
    """
    filtered_df = df.copy()
    
    # Filtrar por cargo
    if cargo_filter and cargo_filter != "Todos":
        if 'cargo' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['cargo'].str.contains(cargo_filter, case=False, na=False)]
        elif 'Cargo' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Cargo'].str.contains(cargo_filter, case=False, na=False)]
    
    # Filtrar por fecha
    if fecha_inicio or fecha_fin:
        # Buscar columna de fecha (pueden tener diferentes nombres)
        fecha_col = None
        for col in ['fecha', 'Fecha', 'fecha_candidatura', 'Fecha_Candidatura']:
            if col in filtered_df.columns:
                fecha_col = col
                break
        
        if fecha_col:
            try:
                # Convertir la columna de fecha
                filtered_df[fecha_col] = pd.to_datetime(filtered_df[fecha_col], errors='coerce')
                
                if fecha_inicio:
                    filtered_df = filtered_df[filtered_df[fecha_col] >= pd.to_datetime(fecha_inicio)]
                if fecha_fin:
                    filtered_df = filtered_df[filtered_df[fecha_col] <= pd.to_datetime(fecha_fin)]
            except:
                st.warning("No se pudo filtrar por fecha. Verifique el formato de las fechas en la hoja.")
    
    return filtered_df

def create_pdf_report(df, title="Consulta de Candidatos"):
    """
    Crea un reporte en PDF con los datos filtrados con mejor formato y manejo de contenido
    """
    buffer = io.BytesIO()
    
    # Configuración de página con márgenes más pequeños
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=1,  # Centrado
        textColor=colors.darkblue
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=15,
        alignment=1,  # Centrado
        textColor=colors.grey
    )
    
    # Contenido del PDF
    story = []
    
    # Título
    story.append(Paragraph(title, title_style))
    
    # Información del reporte
    info_text = f"Fecha del reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Total de registros: {len(df)}"
    story.append(Paragraph(info_text, subtitle_style))
    story.append(Spacer(1, 12))
    
    if not df.empty:
        # Preparar datos para la tabla
        # Convertir todos los valores a string y manejar valores largos
        df_display = df.copy()
        
        # Función para truncar texto largo
        def truncate_text(text, max_length=50):
            text = str(text) if text is not None else ''
            return text[:max_length] + '...' if len(text) > max_length else text
        
        # Aplicar truncamiento a todas las columnas
        for col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: truncate_text(x))
        
        # Preparar encabezados
        headers = [truncate_text(col, 25) for col in df_display.columns]
        
        # Preparar datos de la tabla
        table_data = [headers]
        for idx, row in df_display.iterrows():
            table_data.append(row.tolist())
        
        # Calcular ancho de columnas basado en el número de columnas
        num_cols = len(headers)
        available_width = 7.5 * inch  # Ancho disponible después de márgenes
        
        if num_cols <= 3:
            col_widths = [available_width / num_cols] * num_cols
        elif num_cols <= 6:
            col_widths = [available_width / num_cols] * num_cols
        else:
            # Para muchas columnas, hacer algunas más pequeñas
            col_widths = []
            for i, header in enumerate(headers):
                if any(keyword in header.lower() for keyword in ['id', 'codigo', 'num']):
                    col_widths.append(0.8 * inch)
                elif any(keyword in header.lower() for keyword in ['fecha', 'telefono']):
                    col_widths.append(1.0 * inch)
                else:
                    remaining_width = available_width - sum(col_widths)
                    remaining_cols = num_cols - len(col_widths)
                    col_widths.append(max(remaining_width / remaining_cols, 0.5 * inch))
        
        # Crear tabla con anchos específicos
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilo de la tabla mejorado
        table_style = [
            # Encabezados
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            
            # Contenido
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.darkblue),
            
            # Colores alternados para filas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            
            # Ajuste de texto
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]
        
        table.setStyle(TableStyle(table_style))
        
        # Dividir tabla si es muy larga para múltiples páginas
        story.append(table)
        
        # Agregar nota sobre truncamiento si hay datos largos
        truncation_note = Paragraph(
            "<i>Nota: El texto largo ha sido truncado para optimizar la visualización. "
            "Para ver el contenido completo, consulte la aplicación web.</i>",
            ParagraphStyle('Note', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
        )
        story.append(Spacer(1, 10))
        story.append(truncation_note)
        
    else:
        # Mensaje cuando no hay datos
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1,
            textColor=colors.red
        )
        story.append(Paragraph("No se encontraron registros con los criterios especificados.", no_data_style))
    
    # Agregar pie de página con información adicional
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=1,
        textColor=colors.grey,
        spaceAfter=0
    )
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("---", footer_style))
    story.append(Paragraph(f"Generado por Sistema de Gestión de Agenda", footer_style))
    
    # Construir PDF
    try:
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"Error al generar PDF: {str(e)}")
        return None

# Interfaz principal
def consulta_candidato():
    st.title("📅 Gestión Agenda - Consulta de Candidatos")
    st.markdown("---")
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Nombre de la hoja
        worksheet_name = st.text_input(
            "Nombre de la hoja:",
            value="candidatos",
            help="Nombre exacto de la hoja en 'gestion-agenda' (ej: candidatos, resumen-cv)"
        )
        
        # Información sobre las hojas disponibles
        st.info("📋 **Hojas principales:**\n"
                "- candidatos\n"
                "- resumen-cv\n"
                "- (otras hojas según tu configuración)")
        
        if st.button("🔄 Recargar datos"):
            st.cache_data.clear()
            st.rerun()
    
    # Verificar que el nombre de la hoja esté configurado
    if not worksheet_name:
        st.warning("⚠️ Por favor, configura el nombre de la hoja en el panel lateral.")
        st.info("💡 **Instrucciones:**\n"
                "1. Ve al panel lateral\n"
                "2. Introduce el nombre exacto de la hoja (ej: 'candidatos', 'resumen-cv')\n"
                "3. Asegúrate de que la hoja existe en el archivo 'gestion-agenda'")
        return
    
    # Cargar datos
    with st.spinner("Cargando datos..."):
        df = load_google_sheet_data('gestion-agenda', worksheet_name)
    
    if df is None:
        st.error("❌ No se pudieron cargar los datos. Verifica la configuración y permisos.")
        return
    
    if df.empty:
        st.warning("⚠️ La hoja está vacía o no se encontraron datos.")
        return
    
    # Mostrar información básica
    st.success(f"✅ Datos cargados exitosamente: {len(df)} registros encontrados")
    
    # Panel de filtros
    st.header("🔍 Filtros de Búsqueda")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtro por cargo
        cargo_options = ["Todos"]
        if 'cargo' in df.columns:
            cargo_options.extend(df['cargo'].dropna().unique().tolist())
        elif 'Cargo' in df.columns:
            cargo_options.extend(df['Cargo'].dropna().unique().tolist())
        
        cargo_filter = st.selectbox("Filtrar por cargo:", cargo_options)
    
    with col2:
        # Filtro por fecha de inicio
        fecha_inicio = st.date_input(
            "Fecha inicio:",
            value=None,
            help="Filtrar registros desde esta fecha"
        )
    
    with col3:
        # Filtro por fecha fin
        fecha_fin = st.date_input(
            "Fecha fin:",
            value=None,
            help="Filtrar registros hasta esta fecha"
        )
    
    # Aplicar filtros
    filtered_df = filter_data(df, cargo_filter, fecha_inicio, fecha_fin)
    
    # Mostrar resultados
    st.header("📊 Resultados")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"Se encontraron {len(filtered_df)} registros que coinciden con los filtros")
    
    with col2:
        # Botón de descarga PDF mejorado
        if st.button("📄 Descargar PDF", type="primary", use_container_width=True):
            if not filtered_df.empty:
                with st.spinner("Generando PDF optimizado..."):
                    pdf_buffer = create_pdf_report(
                        filtered_df, 
                        f"Consulta de Candidatos - {datetime.now().strftime('%d/%m/%Y')}"
                    )
                    
                    if pdf_buffer:
                        st.download_button(
                            label="💾 Descargar PDF Generado",
                            data=pdf_buffer.getvalue(),
                            file_name=f"candidatos_consulta_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        st.success("✅ PDF generado correctamente")
                    else:
                        st.error("❌ Error al generar el PDF")
            else:
                st.warning("⚠️ No hay datos para descargar")
    
    # Mostrar tabla de datos
    if not filtered_df.empty:
        st.dataframe(
            filtered_df,
            use_container_width=True,
            height=400
        )
        
        # Estadísticas básicas
        with st.expander("📈 Estadísticas"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total registros", len(filtered_df))
            
            with col2:
                if 'cargo' in filtered_df.columns:
                    unique_cargos = filtered_df['cargo'].nunique()
                elif 'Cargo' in filtered_df.columns:
                    unique_cargos = filtered_df['Cargo'].nunique()
                else:
                    unique_cargos = "N/A"
                st.metric("Cargos únicos", unique_cargos)
            
            with col3:
                # Buscar columna de fecha para mostrar rango
                fecha_col = None
                for col in ['fecha', 'Fecha', 'fecha_candidatura']:
                    if col in filtered_df.columns:
                        fecha_col = col
                        break
                
                if fecha_col:
                    try:
                        fecha_range = filtered_df[fecha_col].nunique()
                        st.metric("Fechas únicas", fecha_range)
                    except:
                        st.metric("Fechas únicas", "N/A")
                else:
                    st.metric("Fechas únicas", "N/A")
    else:
        st.warning("No se encontraron registros con los filtros aplicados.")

#if __name__ == "__main__":
#    consulta_candidato()