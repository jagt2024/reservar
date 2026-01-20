import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import toml
from datetime import datetime, date
import numpy as np
import re
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
    """Formatear valores monetarios con separador de miles (punto)"""
    # Manejar valores None, NaN o vacíos
    if value is None or pd.isna(value):
        return 0
    
    # Convertir a float si es necesario
    try:
        value = value
    except (ValueError, TypeError):
        return 0
    
    # Si es cero, retornar 0
    if value == 0:
        return 0
    
    # Formatear con separador de miles (punto) sin decimales
    return f"{value:,.2f}"
    
    # Formatear con separador de miles (coma)
    # Luego reemplazar coma por punto para formato colombiano
    formatted = f"${value:,.2f}".replace(' ', '')
    return formatted

def format_currency_cop(value):
    """Formatear valor como moneda colombiana"""
    if pd.isna(value) or value == 0:
        return 0
    
    try:
        # Convertir a float si es necesario
        if isinstance(value, str):
            # Remover caracteres no numéricos excepto punto y coma
            clean_value = ''.join(c for c in value if c.isdigit() or c in '.,')
            if clean_value:
                value = clean_value.replace(',', '')
            else:
                return 0
        
        value = value
        
        # Formatear con separadores de miles
        formatted = "{:,.2f}".format(value)
        # Reemplazar comas por puntos para formato colombiano
        #formatted = formatted.replace(',', '.')
        
        return f"{formatted}"
    except (ValueError, TypeError):
        return 0

def parse_currency_cop(currency_str):
    """Convertir string de moneda colombiana a número"""
    if not currency_str or currency_str == "$0":
        return 0
    
    try:
        # Remover símbolo de peso y espacios
        clean_str = currency_str.replace('$', '').replace(' ', '')
        # Reemplazar puntos por nada (separadores de miles)
        #clean_str = clean_str.replace('.', '')
        # Si hay coma, es separador decimal
        if ',' in clean_str:
            clean_str = clean_str.replace(',', '.')
        
        return clean_str if clean_str else 0
    except (ValueError, TypeError):
        return 0

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
                return 0.0
    
    if isinstance(fecha_actual, str):
        try:
            fecha_actual = datetime.strptime(fecha_actual, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_actual = datetime.strptime(fecha_actual, '%d/%m/%Y').date()
            except ValueError:
                return 0.0
    
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
    """
    Limpia valores de moneda y los convierte a float.
    
    Args:
        value: Puede ser str, int o float
               Ejemplos: "$210.000", "210,000.50", "210000", 210000
    
    Returns:
        float: Valor numérico limpio
    """
    if value is None or value == '':
        return 0
    
    # Si ya es numérico, convertir directamente
    if isinstance(value, (int, float)):
        return int(value)
    
    # Si es string, limpiar
    if isinstance(value, str):
        # Eliminar espacios
        value = value.strip()
        
        # Eliminar símbolos de moneda
        value = re.sub(r'[$€£¥₹₩]', '', value)
        
        # Eliminar separadores de miles (puntos o comas según formato)
        # Detectar formato: si hay punto antes que coma, es formato europeo
        if '.' in value and ',' in value:
            if value.rindex('.') < value.rindex(','):
                # Formato europeo: 1.234,56
                value = value.replace('.', '').replace(',', '.')
            else:
                # Formato americano: 1,234.56
                value = value.replace(',', '')
        elif ',' in value and value.count(',') > 1:
            # Múltiples comas = separadores de miles: 1,234,567
            value = value.replace(',', '')
        elif '.' in value and value.count('.') > 1:
            # Múltiples puntos = separadores de miles: 1.234.567
            value = value.replace('.', '')
        elif ',' in value:
            # Una sola coma, verificar si es decimal o separador
            parts = value.split(',')
            if len(parts[-1]) <= 2:
                # Probablemente decimal: 1234,56
                value = value.replace(',', '.')
            else:
                # Probablemente separador: 1,234
                value = value.replace(',', '')
        
        # Convertir a float
        try:
            return value
        except ValueError:
            return 0
    
    return 0


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

def update_sheet_data(worksheet, df, periodo_desde=None, periodo_hasta=None):
    """
    Actualizar datos en Google Sheets con formato colombiano - Solo actualiza registros del período
    
    Args:
        worksheet: Hoja de Google Sheets
        df: DataFrame con los datos calculados
        periodo_desde: Fecha inicial del período (date)
        periodo_hasta: Fecha final del período (date)
    """
    try:
        # Columnas clave para identificar registros
        key_columns = ['Apartamento/Casa', 'Cedula', 'Fecha_Venc_dt', 'periodo_moroso']
        
        # Verificar que las columnas clave existan en el DataFrame
        missing_cols = [col for col in key_columns if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Faltan columnas clave en el DataFrame: {missing_cols}")
            return False
        
        # Verificar que exista la columna de fecha para filtrar
        if 'Fecha_Vencimiento' not in df.columns:
            st.error("❌ Falta la columna 'Fecha_Vencimiento' para filtrar por período")
            return False
        
        # Crear una copia para trabajar
        df_filtered = df.copy()
        
        # CRÍTICO: Convertir TODAS las columnas de fecha a string ANTES de filtrar
        date_columns = df_filtered.select_dtypes(include=['datetime64[ns]', 'datetime64', 'datetime']).columns
        for col in date_columns:
            df_filtered[col] = pd.to_datetime(df_filtered[col]).dt.strftime('%Y-%m-%d')
        
        # También convertir cualquier Timestamp oculto en columnas object
        for col in df_filtered.columns:
            if df_filtered[col].dtype == 'object':
                # Intentar detectar si hay Timestamps
                if df_filtered[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
                    df_filtered[col] = pd.to_datetime(df_filtered[col]).dt.strftime('%Y-%m-%d')
        
        # Filtrar por período si se proporcionan las fechas
        if periodo_desde is not None and periodo_hasta is not None:
            # Convertir temporalmente la columna de fecha para filtrar
            fecha_temp = pd.to_datetime(df['Fecha_Vencimiento'])
            
            # Aplicar filtro de período
            fecha_mask = (
                (fecha_temp.dt.date >= periodo_desde) & 
                (fecha_temp.dt.date <= periodo_hasta)
            )
            df_filtered = df_filtered[fecha_mask].copy()
            
            if len(df_filtered) == 0:
                st.warning(f"⚠️ No hay registros en el período {periodo_desde} a {periodo_hasta}")
                return False
            
            st.info(f"📅 Actualizando {len(df_filtered)} registros del período {periodo_desde} a {periodo_hasta}")
        
        # Obtener datos actuales de la hoja
        existing_data = worksheet.get_all_records()
        
        if not existing_data:
            st.warning("⚠️ La hoja está vacía. Se insertarán todos los registros del período.")
            return _insert_all_data(worksheet, df_filtered)
        
        # Convertir datos existentes a DataFrame
        df_existing = pd.DataFrame(existing_data)
        
        # Crear una copia del DataFrame filtrado para enviar a Google Sheets
        df_to_send = df_filtered.copy()
        
        # Formatear columnas monetarias para Google Sheets
        money_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente', 'Interes_Mora', 'Saldo_Total']
        for col in money_columns:
            if col in df_to_send.columns:
                df_to_send[col] = df_to_send[col].apply(
                        lambda x: f"${x:,.2f}" if pd.notna(x) and x != '' else "0"
                    )
        # Convertir todo a strings para evitar problemas de serialización
        #df_to_send = df_to_send.astype(str)
        
        # Crear clave única para comparar registros
        def create_key(row):
            """Crear clave única concatenando las columnas clave"""
            return '|'.join([str(row.get(col, '')) for col in key_columns])
        
        # Crear diccionario de registros existentes con su índice (fila en sheets)
        existing_keys = {}
        for idx, row in df_existing.iterrows():
            key = create_key(row)
            existing_keys[key] = idx + 2  # +2 porque sheets empieza en 1 y tiene header
        
        # Contadores para reporte
        updated_count = 0
        new_count = 0
        
        # Procesar cada registro del DataFrame filtrado
        for idx, row in df_to_send.iterrows():
            key = create_key(row)
            
            # Convertir la fila a lista de valores simples (strings)
            row_values = [val if val != 'nan' and val != 'NaT' else '' for val in row.tolist()]
            
            if key in existing_keys:
                # Actualizar registro existente
                sheet_row = existing_keys[key]
                
                # Actualizar la fila completa
                range_to_update = f'A{sheet_row}'
                worksheet.update(range_to_update, [row_values])
                updated_count += 1
            else:
                # Agregar nuevo registro
                worksheet.append_row(row_values)
                new_count += 1
        
        # Mensaje de resumen
        if periodo_desde and periodo_hasta:
            st.success(
                f"✅ Actualización completada para período {periodo_desde} a {periodo_hasta}:\n"
                f"- {updated_count} registros actualizados\n"
                f"- {new_count} registros nuevos agregados"
            )
        else:
            st.success(
                f"✅ Actualización completada:\n"
                f"- {updated_count} registros actualizados\n"
                f"- {new_count} registros nuevos"
            )
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error actualizando hoja: {str(e)}")
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
        return False


def _insert_all_data(worksheet, df):
    """Función auxiliar para insertar todos los datos cuando la hoja está vacía"""
    try:
        # Crear una copia del DataFrame para enviar a Google Sheets
        df_to_send = df.copy()
        
        # Convertir TODAS las fechas a string
        date_columns = df_to_send.select_dtypes(include=['datetime64[ns]', 'datetime64', 'datetime']).columns
        for col in date_columns:
            df_to_send[col] = pd.to_datetime(df_to_send[col]).dt.strftime('%Y-%m-%d')
        
        # Formatear columnas monetarias
        money_columns = ['Valor_Deuda', 'Valor_Pagado', 'Saldo_Pendiente', 'Interes_Mora', 'Saldo_Total']
        for col in money_columns:
            if col in df_to_send.columns:
                df_to_send[col] = df_to_send[col].apply(
                        lambda x: f"${x:,.2f}" if pd.notna(x) and x != '' else "0"
                    )
        
        # Convertir todo a strings
        #df_to_send = df_to_send.astype(str)
        
        # Limpiar la hoja y escribir los nuevos datos
        worksheet.clear()
        
        # Escribir headers
        headers = df_to_send.columns.tolist()
        worksheet.append_row(headers)
        
        # Escribir datos
        for index, row in df_to_send.iterrows():
            row_values = [val if val != 'nan' and val != 'NaT' else '' for val in row.tolist()]
            worksheet.append_row(row_values)
        
        st.success(f"✅ {len(df_to_send)} registros insertados")
        return True
        
    except Exception as e:
        st.error(f"❌ Error insertando datos: {str(e)}")
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
        return False


def calculate_interes_mora(saldo_pendiente, dias_mora, tasa_mensual):
    """
    Calcular interés de mora según fórmula bancaria colombiana.
    
    Args:
        saldo_pendiente: Capital adeudado (monto de la cuota) - str o float
                        Ejemplo: "210.000" o "210000" o 210000
        dias_mora: Número de días de retraso - int, float o str
                  Ejemplo: 30 o "30"
        tasa_mensual: Tasa bancaria corriente mensual en PORCENTAJE
                     Ejemplo: 24.36 (para 24.36%) o 0.2436 (decimal)
    
    Returns:
        float: Intereses de mora redondeados a 2 decimales
    
    Nota: Si usas con pandas DataFrame, asegúrate de convertir la columna:
          df['interes_mora'] = df['interes_mora'].astype('float64')
    """
    
    try:
        # Paso 1: Validar y convertir saldo pendiente
        saldo_limpio = clean_currency_value(saldo_pendiente)
        
        # Paso 2: Validar y convertir días de mora
        dias_mora_limpio = clean_currency_value(dias_mora)
        dias_mora_limpio = int(dias_mora_limpio)
        
        # Paso 3: Validar y convertir tasa mensual
        if isinstance(tasa_mensual, str):
            tasa_mensual = tasa_mensual.replace('%', '').strip()
            tasa_mensual = clean_currency_value(tasa_mensual)
        else:
            tasa_mensual = tasa_mensual
        
        # Si la tasa es mayor a 1, asumir que es porcentaje (ej: 24.36)
        if tasa_mensual > 1:
            tasa_mensual = tasa_mensual / 100
        
        # Validar rangos
        if saldo_limpio <= 0:
            return 0.0
        
        if dias_mora_limpio < 0:
            return 0.0
        
        if dias_mora_limpio == 0:
            return 0.0
        
        if tasa_mensual <= 0 or tasa_mensual > 1:
            print(f"⚠️ Tasa mensual debe estar entre 0 y 100%: {tasa_mensual*100:.2f}%")
            return 0.0
        
        # Paso 4: Calcular tasa de mora efectiva anual
        # Multiplica la tasa bancaria corriente por 1.5
        tasa_mora_anual = tasa_mensual * 1.5
        
        # Paso 5: Convertir tasa efectiva anual a tasa diaria
        # Fórmula: Tasa Diaria = (1 + TEA)^(1/365) - 1
        tasa_diaria = ((1 + tasa_mora_anual) ** (1/365)) - 1
        
        # Paso 6: Calcular intereses de mora total
        # Fórmula: Intereses de mora = Capital adeudado × Tasa Diaria × Días de retraso
        interes_mora = saldo_limpio * tasa_diaria * dias_mora_limpio
        
        return round(interes_mora, 2)
    
    except Exception as e:
        print(f"❌ Error en cálculo de mora: {str(e)}")
        return 0.0

    
    except Exception as e:
        print(f"❌ Error en cálculo de mora: {str(e)}")
        return 0.0

def calcular_main():
    #st.set_page_config(
    #    page_title="Calculadora de Mora",
    #    page_icon="💰",
    #    layout="wide"
    #)
    
    st.title("💰 Calcula Dias de Mora e Intereses")
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
    #sheet_name = st.sidebar.text_input("Nombre del archivo", value="gestion-conjuntos")
    #worksheet_name = st.sidebar.text_input("Nombre de la hoja", value="gestion_morosos")
    #st.date_input("Desde:", date(2025, 7, 1)
    periodo_desde = st.sidebar.date_input('Aplicar tasa de Fecha Desde', value= date.today())
    periodo_hasta = st.sidebar.date_input('Aplicar tasa de Fecha Hasta', value= date.today())
    tasa_mensual = st.sidebar.number_input("Tasa de Interés Moratorio (% anual)", value=12.0, min_value=0.0, max_value=100.0, format="%.2f")
    
    # Botón para cargar datos
    if st.button("📊 Cargar Datos", type="primary"):
        with st.spinner("Cargando datos..."):
            df, worksheet = load_data_from_sheet(client, sheet_name ="gestion-conjuntos", worksheet_name ="gestion_morosos")
            
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

                # ✅ IMPORTANTE: Limpiar TODAS las columnas monetarias de una vez
                # Y asegurarse que sean float64
                df['Valor_Deuda'] = df['Valor_Deuda'].apply(clean_currency_value).astype('float64')
                df['Valor_Pagado'] = df['Valor_Pagado'].apply(clean_currency_value).astype('float64')
        
                # Calcular saldo pendiente (ahora ambos son float64)
                df['Saldo_Pendiente'] = (df['Valor_Deuda'] - df['Valor_Pagado']).astype('float64')

                # Convertir fecha
                df['Fecha_Vencimiento'] = pd.to_datetime(df['Fecha_Vencimiento'])

                # Crear máscara para filtrar filas
                fecha_mask = (df['Fecha_Vencimiento'].dt.date >= periodo_desde) & (df['Fecha_Vencimiento'].dt.date <= periodo_hasta)
        
                # Calcular interés de mora
                tasa_decimal = (tasa_mensual / 100)
        
                # Inicializar columnas como float64
                df['Interes_Mora'] = df['Interes_Mora'].apply(clean_currency_value).astype('float64') 
                df['tasa_aplicada'] = df['tasa_aplicada'].apply(clean_currency_value).astype('float64')
        
                # Aplicar interés solo a las filas dentro del período
                df.loc[fecha_mask, 'Interes_Mora'] = df.loc[fecha_mask].apply(
                    lambda row: calculate_interes_mora(
                        row['Saldo_Pendiente'],  # Ya es float64
                        row['Dias_Mora'],
                        tasa_decimal
                    ), axis=1
                )
        
                # Aplicar tasa
                df.loc[fecha_mask, 'tasa_aplicada'] = tasa_mensual
        
                # ✅ Calcular saldo total (ahora ambos son float64 garantizado)
                df['Saldo_Total'] = (df['Saldo_Pendiente'] + df['Interes_Mora']).astype('float64')
        
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
                    # Ya NO necesitas convertir fechas aquí, la función lo hace internamente
                    success = update_sheet_data(
                        st.session_state.worksheet, 
                        df_calc,  # Pasar el DataFrame original
                        periodo_desde=periodo_desde,
                        periodo_hasta=periodo_hasta
                    )
        
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
    - Tasa de interés: % mensual por defecto
    - Solo se calculan intereses para saldos vencidos
    - Los cálculos se basan en la fecha actual
    - Formato de moneda: Pesos colombianos ($1.000.000)
    """)

if __name__ == "__main__":
    calcular_main()