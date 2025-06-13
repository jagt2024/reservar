import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import toml
from datetime import datetime
import time
import re

# Configuración de la página
st.set_page_config(
    page_title="Pasarela de Pagos - Gestión Conjuntos",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        
        # Verificar la conexión
        try:
            sheets = client.openall()
            st.success(f"✅ Conexión exitosa a Google Sheets!")
        except Exception as e:
            st.warning(f"⚠️ Conexión establecida pero sin acceso completo: {str(e)}")
        
        return client
    
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=60)
def load_sheet_data(sheet_name="gestion-conjuntos", worksheet_name="Administracion_Financiera"):
    """Cargar datos de la hoja de Google Sheets"""
    try:
        creds, config = load_credentials_from_toml()
        if not creds:
            return None
        
        client = get_google_sheets_connection(creds)
        if not client:
            return None
        
        # Abrir la hoja
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        
        # Obtener todos los datos
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        return df, worksheet
    
    except Exception as e:
        st.error(f"❌ Error cargando datos de la hoja: {str(e)}")
        return None, None

def validate_payment_data(concepto, monto, cliente_unidad):
    """Validar datos del pago"""
    errors = []
    
    if not concepto or concepto.strip() == "":
        errors.append("El concepto es obligatorio")
    
    if not monto or monto <= 0:
        errors.append("El monto debe ser mayor a 0")
    
    if not cliente_unidad or cliente_unidad.strip() == "":
        errors.append("El cliente/unidad es obligatorio")
    
    return errors

def simulate_payment_gateway(concepto, monto, cliente_unidad, metodo_pago):
    """Simular procesamiento de pago"""
    with st.spinner("Procesando pago..."):
        # Simular tiempo de procesamiento
        time.sleep(2)
        
        # Simular respuesta exitosa (en producción aquí iría la lógica real)
        success = True  # Puedes cambiar esto para simular fallos
        
        if success:
            transaction_id = f"TXN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(cliente_unidad) % 10000}"
            return {
                "success": True,
                "transaction_id": transaction_id,
                "status": "APROBADO",
                "message": "Pago procesado exitosamente"
            }
        else:
            return {
                "success": False,
                "transaction_id": None,
                "status": "RECHAZADO",
                "message": "Pago rechazado por el banco"
            }

def save_payment_to_sheet(worksheet, concepto, monto, cliente_unidad, metodo_pago, transaction_result):
    """Guardar el pago en la hoja de Google Sheets"""
    try:
        current_time = datetime.now()
        
        # Preparar datos para insertar
        new_row = [
            current_time.strftime("%Y-%m-%d"),  # Fecha
            current_time.strftime("%H:%M:%S"),  # Hora
            concepto,                           # Concepto
            cliente_unidad,                     # Cliente/Unidad
            f"${monto:,.2f}",                  # Monto
            metodo_pago,                        # Método de pago
            transaction_result["status"],        # Estado
            transaction_result["transaction_id"], # ID Transacción
            transaction_result["message"]        # Mensaje
        ]
        
        # Insertar nueva fila
        worksheet.append_row(new_row)
        
        return True
    
    except Exception as e:
        st.error(f"❌ Error guardando en la hoja: {str(e)}")
        return False

def main():
    st.title("💳 Pasarela de Pagos")
    st.markdown("### Gestión de Pagos - Conjuntos Residenciales")
    
    # Sidebar para información
    with st.sidebar:
        st.header("ℹ️ Información")
        st.info("Esta aplicación procesa pagos y los registra automáticamente en Google Sheets")
        
        # Botón para recargar datos
        if st.button("🔄 Recargar Datos"):
            st.cache_data.clear()
            st.rerun()
    
    # Cargar datos de la hoja
    result = load_sheet_data()
    if result is None:
        st.error("❌ No se pudo establecer conexión con Google Sheets")
        st.stop()
    
    df, worksheet = result
    
    # Mostrar información de conexión
    st.success(f"✅ Conectado a Google Sheets - {len(df)} registros encontrados")
    
    # Formulario de pago
    st.header("💰 Formulario de Pago")
    
    with st.form("payment_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            concepto = st.text_input(
                "Concepto del Pago *",
                placeholder="Ej: Administración Enero 2024",
                help="Describe el concepto del pago"
            )
            
            monto = st.number_input(
                "Monto ($) *",
                min_value=0.01,
                step=0.01,
                format="%.2f",
                help="Ingresa el monto a pagar"
            )
        
        with col2:
            cliente_unidad = st.text_input(
                "Cliente/Unidad *",
                placeholder="Ej: Apto 101 - Juan Pérez",
                help="Ingresa el cliente o unidad"
            )
            
            metodo_pago = st.selectbox(
                "Método de Pago",
                ["Tarjeta de Crédito", "Tarjeta de Débito", "PSE", "Efectivo", "Transferencia"]
            )
        
        # Botón de envío
        submit_button = st.form_submit_button("🚀 Procesar Pago", use_container_width=True)
        
        if submit_button:
            # Validar datos
            errors = validate_payment_data(concepto, monto, cliente_unidad)
            
            if errors:
                st.error("❌ Errores en el formulario:")
                for error in errors:
                    st.error(f"• {error}")
            else:
                # Mostrar resumen del pago
                st.subheader("📋 Resumen del Pago")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Concepto", concepto)
                with col2:
                    st.metric("Monto", f"${monto:,.2f}")
                with col3:
                    st.metric("Cliente/Unidad", cliente_unidad)
                
                # Procesar pago
                transaction_result = simulate_payment_gateway(concepto, monto, cliente_unidad, metodo_pago)
                
                if transaction_result["success"]:
                    st.success("✅ ¡Pago procesado exitosamente!")
                    
                    # Mostrar detalles de la transacción
                    st.info(f"**ID Transacción:** {transaction_result['transaction_id']}")
                    st.info(f"**Estado:** {transaction_result['status']}")
                    
                    # Guardar en Google Sheets
                    if save_payment_to_sheet(worksheet, concepto, monto, cliente_unidad, metodo_pago, transaction_result):
                        st.success("✅ Pago registrado exitosamente en Google Sheets")
                        
                        # Limpiar caché para mostrar datos actualizados
                        st.cache_data.clear()
                        
                        # Mostrar botón para ver registro
                        if st.button("📊 Ver Registros Actualizados"):
                            st.rerun()
                    else:
                        st.error("❌ Error al guardar el pago en Google Sheets")
                else:
                    st.error(f"❌ Error en el pago: {transaction_result['message']}")
    
    # Mostrar historial de pagos
    st.header("📊 Historial de Pagos")
    
    if not df.empty:
        # Filtros
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Cliente/Unidad' in df.columns:
                clientes = df['Cliente/Unidad'].unique()
                selected_cliente = st.selectbox("Filtrar por Cliente/Unidad", ["Todos"] + list(clientes))
            else:
                selected_cliente = "Todos"
        
        with col2:
            if 'Fecha' in df.columns:
                fechas = df['Fecha'].unique()
                selected_fecha = st.selectbox("Filtrar por Fecha", ["Todas"] + list(fechas))
            else:
                selected_fecha = "Todas"
        
        # Aplicar filtros
        filtered_df = df.copy()
        
        if selected_cliente != "Todos" and 'Cliente/Unidad' in df.columns:
            filtered_df = filtered_df[filtered_df['Cliente/Unidad'] == selected_cliente]
        
        if selected_fecha != "Todas" and 'Fecha' in df.columns:
            filtered_df = filtered_df[filtered_df['Fecha'] == selected_fecha]
        
        # Mostrar tabla
        if not filtered_df.empty:
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Estadísticas
            if 'Monto' in filtered_df.columns:
                # Limpiar y convertir montos
                montos_clean = filtered_df['Monto'].astype(str).str.replace('$', '').str.replace(',', '').astype(float)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Pagos", len(filtered_df))
                with col2:
                    st.metric("Monto Total", f"${montos_clean.sum():,.2f}")
                with col3:
                    st.metric("Promedio", f"${montos_clean.mean():,.2f}")
        else:
            st.info("No hay registros que coincidan con los filtros seleccionados")
    else:
        st.info("No hay registros de pagos disponibles")

if __name__ == "__main__":
    main()