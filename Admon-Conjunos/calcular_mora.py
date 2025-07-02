import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, date
import numpy as np

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

def format_currency(value):
    """Formatear valores monetarios con separador de miles"""
    if pd.isna(value) or value == 0:
        return "$0"
    return f"${value:,.0f}".replace(',', '.')

def format_currency_cop(value):
    """Formatear valor como moneda colombiana"""
    if pd.isna(value) or value == 0:
        return "$0"
    
    try:
        # Convertir a float si es necesario
        if isinstance(value, str):
            # Remover caracteres no numéricos excepto punto y coma
            clean_value = ''.join(c for c in value if c.isdigit() or c in '.,')
            if clean_value:
                value = float(clean_value.replace(',', ''))
            else:
                return "$0"
        
        value = float(value)
        
        # Formatear con separadores de miles
        formatted = "{:,.0f}".format(value)
        # Reemplazar comas por puntos para formato colombiano
        formatted = formatted.replace(',', '.')
        
        return f"${formatted}"
    except (ValueError, TypeError):
        return "$0"

def parse_currency_cop(currency_str):
    """Convertir string de moneda colombiana a número"""
    if not currency_str or currency_str == "$0":
        return 0.0
    
    try:
        # Remover símbolo de peso y espacios
        clean_str = currency_str.replace('$', '').replace(' ', '')
        # Reemplazar puntos por nada (separadores de miles)
        clean_str = clean_str.replace('.', '')
        # Si hay coma, es separador decimal
        if ',' in clean_str:
            clean_str = clean_str.replace(',', '.')
        
        return float(clean_str) if clean_str else 0.0
    except (ValueError, TypeError):
        return 0.0

def calculate_mora_days(fecha_vencimiento, fecha_actual=None):
    """Calcular días de mora"""
    if fecha_actual is None:
        fecha_actual = date.today()
    
    # Convertir fechas si son strings
    if isinstance(fecha_vencimiento, str):
        try:
            fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%d/%m/%Y').date()
            except ValueError:
                return 0
    
    if isinstance(fecha_actual, str):
        try:
            fecha_actual = datetime.strptime(fecha_actual, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_actual = datetime.strptime(fecha_actual, '%d/%m/%Y').date()
            except ValueError:
                return 0
    
    # Calcular días de mora (solo si está vencido)
    dias_mora = (fecha_actual - fecha_vencimiento).days
    return max(0, dias_mora)

def format_dataframe_for_display(df):
    """Formatear DataFrame para mejor visualización usando formato colombiano"""
    df_display = df.copy()
    
    # Formatear columnas monetarias con formato colombiano
    money_columns = ['Valor_Deuda', 'Valor_Pagado' , 'Saldo_Pendiente', 'Interes_Mora', 'Saldo_Total']
    for col in money_columns:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(format_currency_cop)
    
    return df_display

def clean_currency_value(value):
    """Limpiar valores de moneda y convertir a float usando formato colombiano"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    # Si ya es un string con formato de moneda, usar parse_currency_cop
    if isinstance(value, str) and ('$' in value or '.' in value):
        return parse_currency_cop(value)
    
    # Convertir a string si no lo es
    value_str = str(value).strip()
    
    # Remover símbolos de moneda y espacios
    value_str = value_str.replace('$', '').replace(',', '').replace('€', '').replace('£', '')
    value_str = value_str.replace(' ', '').replace('\xa0', '')  # Espacios normales y no-breaking
    
    # Manejar separadores de miles y decimales
    # Si tiene puntos y comas, determinar cuál es el separador decimal
    if ',' in value_str and '.' in value_str:
        # Si el último separador es coma, es decimal (formato europeo)
        if value_str.rfind(',') > value_str.rfind('.'):
            value_str = value_str.replace('.', '').replace(',', '.')
        else:
            # Si el último separador es punto, es decimal (formato americano)
            value_str = value_str.replace(',', '')
    elif ',' in value_str:
        # Solo comas: podría ser separador de miles o decimal
        # Si hay más de una coma o si está en posición de miles, es separador de miles
        comma_count = value_str.count(',')
        comma_pos = value_str.rfind(',')
        if comma_count > 1 or (len(value_str) - comma_pos - 1) > 3:
            value_str = value_str.replace(',', '')
        else:
            # Probablemente es separador decimal
            value_str = value_str.replace(',', '.')
    elif '.' in value_str:
        # Solo puntos: podría ser separador de miles o decimal
        dot_count = value_str.count('.')
        dot_pos = value_str.rfind('.')
        if dot_count > 1 or (len(value_str) - dot_pos - 1) > 3:
            value_str = value_str.replace('.', '')
        # Si solo hay un punto y está en posición decimal, se mantiene
    
    try:
        return float(value_str)
    except ValueError:
        st.warning(f"⚠️ No se pudo convertir el valor: '{value}' - se asignará 0")
        return 0.0

def load_data_from_sheet(client, sheet_name="gestion-conjuntos", worksheet_name="gestion_morosos"):
    """Cargar datos desde Google Sheets"""
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, worksheet
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return None, None

def update_sheet_data(worksheet, df):
    """Actualizar datos en Google Sheets con formato colombiano"""
    try:
        # Crear una copia del DataFrame para enviar a Google Sheets
        df_to_send = df.copy()
        
        # Formatear columnas monetarias para Google Sheets
        money_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente', 'Interes_Mora', 'Saldo_Total']
        for col in money_columns:
            if col in df_to_send.columns:
                df_to_send[col] = df_to_send[col].apply(
                    lambda x: format_currency_cop(x) if pd.notna(x) else "$0"
                )
        
        # Limpiar la hoja y escribir los nuevos datos
        worksheet.clear()
        
        # Escribir headers
        headers = df_to_send.columns.tolist()
        worksheet.append_row(headers)
        
        # Escribir datos
        for index, row in df_to_send.iterrows():
            worksheet.append_row(row.tolist())
        
        return True
    except Exception as e:
        st.error(f"❌ Error actualizando hoja: {str(e)}")
        return False

def calculate_interes_mora(saldo_pendiente, dias_mora, tasa_mensual=0.03):
    """Calcular interés de mora al 3% mensual"""
    # Limpiar y convertir saldo pendiente
    saldo_limpio = clean_currency_value(saldo_pendiente)
    
    if dias_mora <= 0 or saldo_limpio <= 0:
        return 0
    
    # Convertir tasa mensual a diaria
    tasa_diaria = tasa_mensual / 30
    
    # Calcular interés compuesto diario
    interes_mora = saldo_limpio * (((1 + tasa_diaria) ** dias_mora) - 1)
    
    return round(interes_mora, 2)

def calcular_main():
    #st.set_page_config(
    #    page_title="Calculadora de Mora",
    #    page_icon="💰",
    #    layout="wide"
    #)
    
    st.title("💰 Calculadora de Mora e Intereses")
    st.markdown("---")
    
    # Cargar credenciales
    creds, config = load_credentials_from_toml()
    
    if creds is None:
        st.stop()
    
    # Establecer conexión
    client = get_google_sheets_connection(creds)
    
    if client is None:
        st.stop()
    
    # Sidebar para configuración
    st.sidebar.header("⚙️ Configuración")
    sheet_name = st.sidebar.text_input("Nombre del archivo", value="gestion-conjuntos")
    worksheet_name = st.sidebar.text_input("Nombre de la hoja", value="gestion_morosos")
    tasa_mensual = st.sidebar.number_input("Tasa de interés mensual (%)", value=3.0, min_value=0.0, max_value=100.0) / 100
    
    # Botón para cargar datos
    if st.button("📊 Cargar Datos", type="primary"):
        with st.spinner("Cargando datos..."):
            df, worksheet = load_data_from_sheet(client, sheet_name, worksheet_name)
            
            if df is not None:
                st.session_state.df = df
                st.session_state.worksheet = worksheet
                st.success("✅ Datos cargados exitosamente")
    
    # Mostrar datos si están cargados
    if 'df' in st.session_state:
        df = st.session_state.df.copy()
        
        st.subheader("📋 Datos Actuales")
        # Mostrar datos con formato colombiano
        df_display = format_dataframe_for_display(df)
        st.dataframe(df_display, use_container_width=True)
        
        # Verificar columnas requeridas
        required_columns = ['Fecha_Vencimiento', 'Valor_Deuda', 'Valor_Pagado','Saldo_Pendiente']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"❌ Faltan las siguientes columnas: {', '.join(missing_columns)}")
            st.stop()
        
        # Botón para calcular mora
        if st.button("🧮 Calcular Mora e Intereses", type="secondary"):
            with st.spinner("Calculando..."):
                fecha_actual = date.today()
                
                # Calcular días de mora
                df['Dias_Mora'] = df['Fecha_Vencimiento'].apply(
                    lambda x: calculate_mora_days(x, fecha_actual)
                )

                df['Valor_Deuda'] = df.apply(
                    lambda row: clean_currency_value(row['Valor_Deuda']), axis=1
                )

                df['Valor_Pagado'] = df.apply(
                    lambda row: clean_currency_value(row['Valor_Pagado']), axis=1
                )
                
                # FIX: Calcular saldo pendiente limpiando AMBOS valores
                df['Saldo_Pendiente'] = df.apply(
                    lambda row: clean_currency_value(row['Valor_Deuda']) - clean_currency_value(row['Valor_Pagado']), axis=1
                )

                # Calcular interés de mora
                df['Interes_Mora'] = df.apply(
                    lambda row: calculate_interes_mora(
                        row['Saldo_Pendiente'],
                        row['Dias_Mora'],
                        tasa_mensual
                    ), axis=1
                )
                
                # Calcular saldo total
                df['Saldo_Total'] = df.apply(
                    lambda row: clean_currency_value(row['Saldo_Pendiente']) + row['Interes_Mora'], axis=1
                )
                
                st.session_state.df_calculated = df
                st.success("✅ Cálculos completados")
        
        # Mostrar resultados calculados
        if 'df_calculated' in st.session_state:
            df_calc = st.session_state.df_calculated
            
            st.subheader("📊 Resultados Calculados")
            
            # Métricas resumidas con formato colombiano
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_morosos = len(df_calc[df_calc['Dias_Mora'] > 0])
                st.metric("👥 Total Morosos", total_morosos)
            
            with col2:
                total_saldo_pendiente = df_calc['Saldo_Pendiente'].apply(clean_currency_value).sum()
                st.metric("💰 Saldo Pendiente", format_currency_cop(total_saldo_pendiente))
            
            with col3:
                total_interes = df_calc['Interes_Mora'].sum()
                st.metric("📈 Interés Total", format_currency_cop(total_interes))
            
            with col4:
                total_general = df_calc['Saldo_Total'].sum()
                st.metric("🎯 Total General", format_currency_cop(total_general))
            
            # Mostrar tabla con resultados formateados
            df_calc_display = format_dataframe_for_display(df_calc)
            st.dataframe(df_calc_display, use_container_width=True)
            
            # Filtros para análisis
            st.subheader("🔍 Análisis por Filtros")
            
            col1, col2 = st.columns(2)
            
            with col1:
                min_dias = st.number_input("Días mínimos de mora", min_value=0, value=0)
                filtered_df = df_calc[df_calc['Dias_Mora'] >= min_dias]
                st.write(f"Registros con {min_dias}+ días de mora: {len(filtered_df)}")
                
            with col2:
                min_saldo = st.number_input("Saldo mínimo", min_value=0.0, value=0.0)
                filtered_df2 = df_calc[df_calc['Saldo_Total'] >= min_saldo]
                st.write(f"Registros con saldo ≥ {format_currency_cop(min_saldo)}: {len(filtered_df2)}")
            
            # Botón para actualizar Google Sheets
            st.markdown("---")
            st.subheader("📤 Actualizar Google Sheets")
            
            if st.button("🔄 Actualizar Hoja de Cálculo", type="primary"):
                with st.spinner("Actualizando Google Sheets..."):
                    success = update_sheet_data(st.session_state.worksheet, df_calc)
                    
                    if success:
                        st.success("✅ Hoja actualizada exitosamente en Google Sheets")
                        st.balloons()
                    else:
                        st.error("❌ Error al actualizar la hoja")
            
            # Opción para descargar CSV con formato colombiano
            df_csv = format_dataframe_for_display(df_calc)
            csv = df_csv.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"gestion_morosos_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # Información adicional
    st.sidebar.markdown("---")
    st.sidebar.info("""
    **📋 Instrucciones:**
     
    **💡 Notas:**
    - Tasa de interés: 3% mensual por defecto
    - Solo se calculan intereses para saldos vencidos
    - Los cálculos se basan en la fecha actual
    - Formato de moneda: Pesos colombianos ($1.000.000)
    """)

#if __name__ == "__main__":
#    main()