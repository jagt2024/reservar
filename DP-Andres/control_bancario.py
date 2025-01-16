import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
import toml
import base64
import io

# Configuración de la página
#st.set_page_config(
#    page_title="Control de Movimientos Bancarios",
#    page_icon="💰",
#    layout="wide"
#)

# Definir nombres de columnas esperados
COLUMN_NAMES = ['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Monto', 'Banco', 'Referencia']

# Función para cargar credenciales desde archivo TOML
def load_credentials_from_toml(file_path):
    with open(file_path, 'r') as toml_file:
        config = toml.load(toml_file)
        credentials = config['sheetsemp']['credentials_sheet']
    return credentials

# Función para obtener datos de Google Sheets
def get_google_sheet_data(creds, sheet_name='bancos'):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds, scopes=scope)
        client = gspread.authorize(credentials)
        sheet = client.open('gestion-reservas-dp')
        worksheet = sheet.worksheet(sheet_name)
        data = worksheet.get_all_values()
        
        if not data:
            st.error("No se encontraron datos en la hoja de cálculo.")
            return None, None
        
        # Si no hay datos previos, crear DataFrame con las columnas predefinidas
        if len(data) <= 1:
            df = pd.DataFrame(columns=COLUMN_NAMES)
        else:
            # Crear DataFrame y asegurarse de que use los nombres de columnas correctos
            df = pd.DataFrame(data[1:], columns=COLUMN_NAMES)
            
        return worksheet, df
    except Exception as e:
        st.error(f"Error al acceder a Google Sheets: {str(e)}")
        return None, None

# Función para guardar nuevos datos
def save_transaction(worksheet, transaction_data):
    try:
        # Si la hoja está vacía, primero agregar los encabezados
        if worksheet.row_count <= 1:
            worksheet.append_row(COLUMN_NAMES)
        worksheet.append_row(transaction_data)
        return True
    except Exception as e:
        st.error(f"Error al guardar la transacción: {str(e)}")
        return False

def download_data(df, file_format='csv'):
    """
    Prepara el archivo para descarga en el formato especificado
    """
    if file_format == 'csv':
        output = df.to_csv(index=False)
        b64 = base64.b64encode(output.encode()).decode()
        filename = f"movimientos_bancarios_{datetime.now().strftime('%Y%m%d')}.csv"
        mime_type = 'text/csv'
    elif file_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Movimientos', index=False)
        b64 = base64.b64encode(output.getvalue()).decode()
        filename = f"movimientos_bancarios_{datetime.now().strftime('%Y%m%d')}.xlsx"
        mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">Descargar archivo {file_format.upper()}</a>'
    return href

def bancos():
    st.title("📊 Control de Movimientos Bancarios")
    
    try:
        # Cargar credenciales desde el archivo TOML
        credentials = load_credentials_from_toml('./.streamlit/secrets.toml')
        
        # Obtener hoja de cálculo y datos
        worksheet, df = get_google_sheet_data(credentials)
        
        if worksheet is None:
            st.error("No se pudo establecer conexión con Google Sheets")
            return

        # Crear columnas para la interfaz
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Crear Nuevo Movimiento")
            
            # Formulario para nuevos movimientos
            with st.form("transaction_form"):
                fecha = st.date_input("Fecha", datetime.now())
                tipo = st.selectbox("Tipo de Movimiento", ["Ingreso", "Egreso"])
                categoria = st.selectbox("Categoría", [
                    "Ventas", "Servicios", "Salarios",
                    "Proveedores", "Gastos Operativos", "Otros"
                ])
                descripcion = st.text_area("Descripción")
                monto = st.number_input("Monto", min_value=0.0, format="%f")
                banco = st.selectbox("Banco", ["Banco de Colombia", "Banco Davivienda", "Banco de Bogota", "Banco de Occidente", "Banco Popular", "Banco Colpatria", "Banco BBVA", "Nequi"])
                num_referencia = st.text_input("Número de Referencia")
                
                submitted = st.form_submit_button("Registrar Movimiento")
                
                if submitted:
                    transaction_data = [
                        fecha.strftime("%Y-%m-%d"),
                        tipo,
                        categoria,
                        descripcion,
                        str(monto),  # Convertir a string para consistencia
                        banco,
                        num_referencia
                    ]
                    
                    if save_transaction(worksheet, transaction_data):
                        st.success("Movimiento creado exitosamente")
                        st.balloons()
                        # Recargar datos después de guardar
                        worksheet, df = get_google_sheet_data(credentials)

        with col2:
            st.subheader("Movimientos Registrados")
            
            if df is not None and not df.empty:

                # Convertir la columna Fecha a datetime
                df['Fecha'] = pd.to_datetime(df['Fecha'], format='%Y-%m-%d', errors='coerce')
                
                # Obtener el rango de fechas disponible
                fecha_min = df['Fecha'].min()
                fecha_max = df['Fecha'].max()
                
                # Agregar filtros en tres columnas
                col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
                
                # Filtro de fechas
                with col_filtro1:
                    st.write("Rango de Fechas")
                    fecha_inicio = st.date_input(
                        "Desde",
                        value=fecha_min.date() if not pd.isna(fecha_min) else datetime.now().date(),
                        min_value=fecha_min.date() if not pd.isna(fecha_min) else None,
                        max_value=fecha_max.date() if not pd.isna(fecha_max) else None
                    )
                    fecha_fin = st.date_input(
                        "Hasta",
                        value=fecha_max.date() if not pd.isna(fecha_max) else datetime.now().date(),
                        min_value=fecha_min.date() if not pd.isna(fecha_min) else None,
                        max_value=fecha_max.date() if not pd.isna(fecha_max) else None
                    )

                # Agregar filtros
                #col_filtro1, col_filtro2 = st.columns(2)
                with col_filtro2:
                    bancos_disponibles = df['Banco'].unique() if 'Banco' in df.columns else []
                    banco_filter = st.multiselect(
                        "Filtrar por Banco",
                        options=bancos_disponibles
                    )
                with col_filtro3:
                    tipos_disponibles = df['Tipo'].unique() if 'Tipo' in df.columns else []
                    tipo_filter = st.multiselect(
                        "Filtrar por Tipo",
                        options=tipos_disponibles
                    )

                # Aplicar filtros
                df_filtered = df.copy()
                if banco_filter and 'Banco' in df.columns:
                    df_filtered = df_filtered[df_filtered['Banco'].isin(banco_filter)]
                if tipo_filter and 'Tipo' in df.columns:
                    df_filtered = df_filtered[df_filtered['Tipo'].isin(tipo_filter)]

                # Mostrar resumen
                st.subheader("Resumen")
                col_resumen1, col_resumen2, col_resumen3 = st.columns(3)
                
                with col_resumen1:
                    try:
                        total_ingresos = df_filtered[df_filtered['Tipo'] == 'Ingreso']['Monto'].astype(float).sum()
                        st.metric("Total Ingresos", f"${total_ingresos:,.2f}")
                    except:
                        st.metric("Total Ingresos", "$0.00")
                
                with col_resumen2:
                    try:
                        total_egresos = df_filtered[df_filtered['Tipo'] == 'Egreso']['Monto'].astype(float).sum()
                        st.metric("Total Egresos", f"${total_egresos:,.2f}")
                    except:
                        st.metric("Total Egresos", "$0.00")
                
                with col_resumen3:
                    try:
                        balance = total_ingresos - total_egresos
                        st.metric("Balance", f"${balance:,.2f}")
                    except:
                        st.metric("Balance", "$0.00")

                # Mostrar tabla de movimientos
                try:
                    df_filtered['Monto'] = df_filtered['Monto'].astype(float)
                    st.dataframe(
                        df_filtered.style.format({'Monto': '${:,.2f}'}),
                        use_container_width=True
                    )

                    st.divider()
                    st.subheader("Descargar Movimientos")
                    
                    col_download1, col_download2 = st.columns(2)
                    
                    with col_download1:
                        if st.button("📥 Descargar CSV"):
                            csv_href = download_data(df_filtered, 'csv')
                            st.markdown(csv_href, unsafe_allow_html=True)
                    
                    with col_download2:
                        if st.button("📊 Descargar Excel"):
                            excel_href = download_data(df_filtered, 'xlsx')
                            st.markdown(excel_href, unsafe_allow_html=True)
                            
                except:
                    st.dataframe(df_filtered, use_container_width=True)
            else:
                st.info("No hay movimientos registrados")

    except Exception as e:
        st.error(f"Error en la aplicación: {str(e)}")

#if __name__ == "__main__":
#    bancos()