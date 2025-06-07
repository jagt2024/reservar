import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import toml
import json
from datetime import datetime, date
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import tempfile
from io import BytesIO

# Configuración de la página
#st.set_page_config(
#    page_title="Generador de Cuentas de Cobro",
#    page_icon="📋",
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
def load_financial_data(_client):
    """Cargar datos financieros pendientes"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Administracion_Financiera")
        data = worksheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            # Filtrar solo registros pendientes
            df_pending = df[df['Estado'].str.lower() == 'pendiente'].copy()
            return df_pending, worksheet
        else:
            return pd.DataFrame(), worksheet
            
    except gspread.WorksheetNotFound:
        st.error("❌ La hoja 'Administracion_Financiera' no existe")
        return pd.DataFrame(), None
    except Exception as e:
        st.error(f"❌ Error cargando datos financieros: {str(e)}")
        return pd.DataFrame(), None

@st.cache_data(ttl=300)
def load_residents_data(_client):
    """Cargar datos de residentes propietarios"""
    try:
        spreadsheet = _client.open("gestion-conjuntos")
        worksheet = spreadsheet.worksheet("Control_Residentes")
        data = worksheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            # Filtrar solo propietarios
            df_owners = df[df['Tipo'].str.lower() == 'propietario'].copy()
            return df_owners
        else:
            return pd.DataFrame()
            
    except gspread.WorksheetNotFound:
        st.error("❌ La hoja 'Control_Residentes' no existe")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando datos de residentes: {str(e)}")
        return pd.DataFrame()

def update_observation_in_sheet(worksheet, row, observation_msg):
    """
    Función mejorada para actualizar observaciones con manejo de errores
    """
    try:
        # Buscar la fila por ID único o combinación de campos
        unit_name = row['Unidad']
        concept = row['Concepto']
        amount = row['Monto']
        
        # Obtener todos los registros
        all_records = worksheet.get_all_records()
        
        # Buscar la fila específica
        for idx, record in enumerate(all_records):
            if (record.get('Unidad') == unit_name and 
                record.get('Concepto') == concept and 
                float(record.get('Monto', 0)) == float(amount)):
                
                # Actualizar la observación (fila idx + 2 porque las filas empiezan en 1 y hay header)
                row_number = idx + 2
                
                # Buscar la columna de observaciones
                headers = worksheet.row_values(1)
                obs_col = None
                for col_idx, header in enumerate(headers):
                    if 'observacion' in header.lower() or 'observación' in header.lower():
                        obs_col = col_idx + 1  # Las columnas empiezan en 1
                        break
                
                if obs_col:
                    # Actualizar usando batch_update para mejor rendimiento
                    worksheet.update_cell(row_number, obs_col, observation_msg)
                    return True
                else:
                    print("❌ No se encontró columna de observaciones")
                    return False
        
        print(f"❌ No se encontró la fila para {unit_name} - {concept}")
        return False
        
    except Exception as e:
        print(f"❌ Error actualizando observaciones: {str(e)}")
        # Intentar reconectar
        try:
            # Re-autorizar la conexión
            creds, _ = load_credentials_from_toml()
            if creds:
                new_client = get_google_sheets_connection(creds)
                if new_client:
                    # Intentar de nuevo con nueva conexión
                    new_worksheet = new_client.open_by_key(worksheet.spreadsheet.id).worksheet(worksheet.title)
                    return update_observation_in_sheet_retry(new_worksheet, row, observation_msg)
        except Exception as retry_error:
            print(f"❌ Error en reintento: {str(retry_error)}")
        
        return False

def update_observation_in_sheet_retry(worksheet, row, observation_msg):
    """
    Función de reintento simplificada
    """
    try:
        unit_name = row['Unidad']
        concept = row['Concepto']
        amount = row['Monto']
        
        all_records = worksheet.get_all_records()
        
        for idx, record in enumerate(all_records):
            if (record.get('Unidad') == unit_name and 
                record.get('Concepto') == concept and 
                float(record.get('Monto', 0)) == float(amount)):
                
                row_number = idx + 2
                headers = worksheet.row_values(1)
                
                for col_idx, header in enumerate(headers):
                    if 'observacion' in header.lower() or 'observación' in header.lower():
                        worksheet.update_cell(row_number, col_idx + 1, observation_msg)
                        return True
        return False
    except:
        return False

def filter_current_period_debts(df_financial, selected_date):
    """Filtrar deudas del período actual"""
    if df_financial.empty:
        return pd.DataFrame()
    
    try:
        # Convertir fechas si es necesario
        if 'Fecha' in df_financial.columns:
            df_financial['Fecha'] = pd.to_datetime(df_financial['Fecha'], errors='coerce')
        
        # Filtrar por período (mes y año)
        current_month = selected_date.month
        current_year = selected_date.year
        
        mask = (
            (df_financial['Fecha'].dt.month == current_month) &
            (df_financial['Fecha'].dt.year == current_year)
        ) | (
            # También incluir registros sin fecha válida si el concepto incluye el mes actual
            df_financial['Fecha'].isna() & 
            df_financial['Concepto'].str.contains(selected_date.strftime('%B'), case=False, na=False)
        )
        
        return df_financial[mask].copy()
        
    except Exception as e:
        st.error(f"❌ Error filtrando período: {str(e)}")
        return df_financial

def merge_financial_and_resident_data(df_financial, df_residents):
    """Combinar datos financieros con datos de residentes"""
    if df_financial.empty or df_residents.empty:
        return pd.DataFrame()
    
    try:
        # Hacer merge por Unidad
        df_merged = df_financial.merge(
            df_residents[['Unidad', 'Nombre', 'Email', 'Telefono']],
            on='Unidad',
            how='left'
        )
        
        # Filtrar solo registros que tienen email
        df_with_email = df_merged[df_merged['Email'].notna() & (df_merged['Email'] != '')].copy()
        
        return df_with_email
        
    except Exception as e:
        st.error(f"❌ Error combinando datos: {str(e)}")
        return pd.DataFrame()

def generate_invoice_pdf(unit_data, unit_name, invoice_date):
    """Generar PDF de cuenta de cobro para una unidad"""
    try:
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_filename = temp_file.name
        temp_file.close()
        
        # Crear documento PDF
        doc = SimpleDocTemplate(temp_filename, pagesize=A4)
        story = []
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12
        )
        
        # Encabezado
        story.append(Paragraph("CONDOMINIO LA CEIBA", title_style))
        story.append(Paragraph("CUENTA DE COBRO", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Información de la unidad
        info_data = [
            ['UNIDAD:', unit_name],
            ['PROPIETARIO:', unit_data.iloc[0]['Nombre'] if 'Nombre' in unit_data.columns else 'N/A'],
            ['FECHA DE EMISIÓN:', invoice_date.strftime('%d/%m/%Y')],
            ['PERÍODO:', invoice_date.strftime('%B %Y').upper()]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 30))
        
        # Detalle de conceptos
        story.append(Paragraph("DETALLE DE CONCEPTOS PENDIENTES:", subtitle_style))
        story.append(Spacer(1, 10))
        
        # Crear tabla de conceptos
        concepts_data = [['CONCEPTO', 'FECHA', 'VALOR']]
        total_amount = 0
        
        for index, row in unit_data.iterrows():
            concept = row['Concepto'] if 'Concepto' in row else 'N/A'
            fecha = row['Fecha'].strftime('%d/%m/%Y') if pd.notna(row['Fecha']) else 'N/A'
            monto = float(row['Monto']) if pd.notna(row['Monto']) else 0.0
            
            concepts_data.append([
                concept,
                fecha,
                f"${monto:,.2f}"
            ])
            total_amount += monto
        
        # Agregar fila de total
        concepts_data.append(['', 'TOTAL A PAGAR:', f"${total_amount:,.2f}"])
        
        concepts_table = Table(concepts_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        concepts_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ]))
        
        story.append(concepts_table)
        story.append(Spacer(1, 30))
        
        # Información de pago
        payment_info = """
        <b>INFORMACIÓN PARA PAGO:</b><br/>
        • Banco: Bancolombia<br/>
        • Cuenta Corriente: 123-456789-01<br/>
        • A nombre de: Condominio la Ceiba<br/>
        • Referencia: """ + unit_name + """<br/><br/>
        
        <b>IMPORTANTE:</b><br/>
        • Cargar el Pago y comprobante en la aplicacion del Condominio o Enviar comprobante de pago al correo: laceibacondominio@gmail.com<br/>
        • Fecha límite de pago: """ + (invoice_date.replace(day=28) if invoice_date.day < 28 else invoice_date).strftime('%d/%m/%Y') + """<br/>
        • Después de la fecha límite se aplicarán intereses moratorios
        """
        
        story.append(Paragraph(payment_info, normal_style))
        
        # Construir PDF
        doc.build(story)
        
        return temp_filename
        
    except Exception as e:
        st.error(f"❌ Error generando PDF para {unit_name}: {str(e)}")
        return None

def send_email_with_invoice(recipient_email, recipient_name, unit_name, pdf_path, smtp_config):
    """Enviar email con la cuenta de cobro adjunta"""
    try:
        # Configurar servidor SMTP
        server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
        server.starttls()
        server.login(smtp_config['email'], smtp_config['password'])
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = smtp_config['email']
        msg['To'] = recipient_email
        msg['Subject'] = f"Cuenta de Cobro - {unit_name} - {datetime.now().strftime('%B %Y')}"
        
        # Cuerpo del mensaje
        body = f"""
        Estimado(a) {recipient_name},
        
        Nos permitimos enviarle la cuenta de cobro correspondiente a la unidad {unit_name} 
        para el período de {datetime.now().strftime('%B %Y')}.
        
        Por favor revise el documento adjunto y proceda con el pago antes de la fecha límite.
        
        Si ya realizó el pago, por favor envíe el comprobante a este mismo correo.
        
        Gracias por su atención.
        
        Cordialmente,
        Administración del Conjunto
        Codominio La Ceiba
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Adjuntar PDF
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= "Cuenta_Cobro_{unit_name}_{datetime.now().strftime("%Y%m")}.pdf"'
        )
        
        msg.attach(part)
        
        # Enviar email
        text = msg.as_string()
        server.sendmail(smtp_config['email'], recipient_email, text)
        server.quit()
        
        return True, "Cuenta de cobro enviada exitosamente"
        
    except Exception as e:
        error_msg = f"Error al enviar correo: {str(e)}"
        return False, error_msg

def generador_main():
    st.title("📋 Generador de Cuentas de Cobro")
    st.subheader("Sistema Automático de Facturación")
    st.markdown("---")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    
    if creds is None:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    
    if client is None:
        st.stop()
    
    # Configuración de correo
    st.sidebar.header("⚙️ Configuración de Correo")
    with st.sidebar.expander("Configurar SMTP"):
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = st.secrets['emails']['smtp_user']
        sender_password = st.secrets['emails']['smtp_password']
        
        smtp_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'email': sender_email,
            'password': sender_password
        }
    
    # Selección de período
    st.header("📅 Selección de Período")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_date = st.date_input(
            "Período para generar cuentas de cobro",
            value=date.today(),
            help="Seleccione el mes y año para el cual generar las cuentas de cobro"
        )
    
    with col2:
        st.info(f"📊 Generando cuentas para: **{selected_date.strftime('%B %Y')}**")
    
    # Cargar datos
    with st.spinner("Cargando datos..."):
        df_financial, financial_worksheet = load_financial_data(client)
        df_residents = load_residents_data(client)
    
    if df_financial.empty:
        st.warning("⚠️ No se encontraron datos financieros")
        st.stop()
    
    if df_residents.empty:
        st.warning("⚠️ No se encontraron datos de residentes")
        st.stop()
    
    # Filtrar por período actual
    df_current_period = filter_current_period_debts(df_financial, selected_date)
    
    if df_current_period.empty:
        st.warning(f"⚠️ No se encontraron deudas pendientes para {selected_date.strftime('%B %Y')}")
        st.stop()
    
    # Combinar datos
    df_merged = merge_financial_and_resident_data(df_current_period, df_residents)
    
    if df_merged.empty:
        st.warning("⚠️ No se encontraron propietarios con email para las deudas pendientes")
        st.stop()
    
    # Mostrar resumen
    st.header("📊 Resumen de Cuentas a Generar")
    
    units_summary = df_merged.groupby('Unidad').agg({
        'Monto': 'sum',
        'Concepto': 'count',
        'Nombre': 'first',
        'Email': 'first'
    }).reset_index()
    
    units_summary.columns = ['Unidad', 'Total_Deuda', 'Num_Conceptos', 'Propietario', 'Email']
    
    st.dataframe(
        units_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total_Deuda": st.column_config.NumberColumn(
                "Total Deuda",
                format="$%.2f"
            )
        }
    )
    
    st.info(f"📋 **Total unidades con deudas:** {len(units_summary)}")
    st.info(f"💰 **Total a cobrar:** ${units_summary['Total_Deuda'].sum():,.2f}")
    
    # Botones de acción
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🚀 Generar y Enviar Cuentas de Cobro", type="primary", use_container_width=True):
            if not all([sender_email, sender_password]):
                st.error("❌ Por favor configure el correo electrónico en el panel lateral")
                st.stop()
            
            # Procesar cada unidad
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            total_units = len(units_summary)
            
            for index, unit_row in units_summary.iterrows():
                unit_name = unit_row['Unidad']
                unit_email = unit_row['Email']
                unit_owner = unit_row['Propietario']
                
                status_text.text(f"Procesando {unit_name}... ({index + 1}/{total_units})")
                
                # Obtener datos de la unidad
                unit_data = df_merged[df_merged['Unidad'] == unit_name]
                
                # Generar PDF
                pdf_path = generate_invoice_pdf(unit_data, unit_name, selected_date)
                
                if pdf_path:
                    # Enviar email
                    email_sent, message = send_email_with_invoice(
                        unit_email, unit_owner, unit_name, pdf_path, smtp_config
                    )
                    
                    # Actualizar observaciones para cada registro de la unidad
                    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
                    if email_sent:
                        observation_msg = f"Cuenta de cobro enviada por correo el {timestamp}"
                        status = 'Exitoso'
                    else:
                        observation_msg = f"Error al enviar cuenta de cobro el {timestamp}: {message}"
                        status = 'Error en envío'
                    
                    # Actualizar cada fila de la unidad en Google Sheets
                    updates_successful = 0
                    for _, row in unit_data.iterrows():
                        if update_observation_in_sheet(financial_worksheet, row, observation_msg):
                            updates_successful += 1
                    
                    results.append({
                        'Unidad': unit_name,
                        'Email': unit_email,
                        'PDF_Generado': 'Sí',
                        'Email_Enviado': 'Sí' if email_sent else 'No',
                        'Observaciones_Actualizadas': f'{updates_successful}/{len(unit_data)}',
                        'Estado': status,
                        'Mensaje': message
                    })
                    
                    # Limpiar archivo temporal
                    try:
                        os.unlink(pdf_path)
                    except:
                        pass
                else:
                    # Actualizar observaciones indicando error en PDF
                    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
                    observation_msg = f"Error al generar PDF el {timestamp}"
                    
                    updates_successful = 0
                    for _, row in unit_data.iterrows():
                        if update_observation_in_sheet(financial_worksheet, row, observation_msg):
                            updates_successful += 1
                    
                    results.append({
                        'Unidad': unit_name,
                        'Email': unit_email,
                        'PDF_Generado': 'No',
                        'Email_Enviado': 'No',
                        'Observaciones_Actualizadas': f'{updates_successful}/{len(unit_data)}',
                        'Estado': 'Error en PDF',
                        'Mensaje': 'No se pudo generar el PDF'
                    })
                
                progress_bar.progress((index + 1) / total_units)
            
            status_text.text("¡Proceso completado!")
            
            # Mostrar resultados
            st.success("✅ Proceso de generación y envío completado")
            
            results_df = pd.DataFrame(results)
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            
            # Resumen final
            successful = len(results_df[results_df['Estado'] == 'Exitoso'])
            failed = len(results_df[results_df['Estado'] != 'Exitoso'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ Enviados", successful)
            with col2:
                st.metric("❌ Fallidos", failed)
            with col3:
                st.metric("📊 Total", len(results_df))
            
            # Mostrar detalles de errores si los hay
            if failed > 0:
                st.warning("⚠️ Detalles de errores:")
                error_details = results_df[results_df['Estado'] != 'Exitoso'][['Unidad', 'Estado', 'Mensaje']]
                st.dataframe(error_details, use_container_width=True, hide_index=True)

#if __name__ == "__main__":
#    generador_main()