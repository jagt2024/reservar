import streamlit as st
import pywhatkit
import pandas as pd
import time
from datetime import datetime, timedelta
from io import BytesIO

def format_phone_number(phone):
    phone_str = str(phone).split('.')[0]
    phone_str = phone_str.replace(' ', '').replace('-', '')
    if not phone_str.startswith('+'):
        if not phone_str.startswith('57'):
            phone_str = '+57' + phone_str
        else:
            phone_str = '+' + phone_str
    return phone_str

def send_whatsapp_message(phone_number, message):
    try:
        now = datetime.now()
        # Añadir 2 minutos al tiempo actual para dar tiempo a que WhatsApp Web se cargue
        send_time = now + timedelta(minutes=3)
        pywhatkit.sendwhatmsg(phone_number, message, send_time.hour, send_time.minute)
        return True
    except Exception as e:
        st.error(f"Error al enviar mensaje a {phone_number}: {str(e)}")
        return False

def load_excel_data(file):
    try:
        df = pd.read_excel(file)
        required_columns = ['TELEFONO', 'NOTAS', 'WHATSAPP', 'NOMBRE', 'FECHA']
        if not all(col in df.columns for col in required_columns):
            st.error("El archivo Excel debe contener las columnas 'TELEFONO', 'NOTAS', 'WHATSAPP', 'NOMBRE' y 'FECHA'")
            return None
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo Excel: {str(e)}")
        return None

def send_personal_message():
    st.subheader("Envío de Mensaje Personal")
    phone_number = st.text_input("Número de teléfono (formato internacional, ej. +34612345678):")
    message = st.text_area("Mensaje:")
    
    if st.button("Enviar Mensaje Personal"):
        if phone_number and message:
            with st.spinner("Preparando para enviar mensaje... Por favor, espere."):
                success = send_whatsapp_message(phone_number, message)
                if success:
                    st.success(f"Mensaje enviado a {phone_number}")
                else:
                    st.error(f"No se pudo enviar el mensaje a {phone_number}")
        else:
            st.warning("Por favor, ingresa un número de teléfono y un mensaje.")

def send_bulk_messages(df):
    total_messages = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    df['BOTON'] = ''  # Añadir columna de estado

    for index, row in df.iterrows():
        if row['WHATSAPP']:  # Solo enviar si está marcado para envío
            phone_number = format_phone_number(row['TELEFONO'])
            message = str(row['NOTAS'])

            status_text.text(f"Preparando para enviar mensaje a {row['NOMBRE']} ({phone_number})...")
            success = send_whatsapp_message(phone_number, message)

            if success:
                st.success(f"Mensaje enviado a {row['NOMBRE']} ({phone_number})")
                df.at[index, 'BOTON'] = 'Enviado OK'
            else:
                st.warning(f"No se pudo enviar el mensaje a {row['NOMBRE']} ({phone_number})")
                df.at[index, 'BOTON'] = 'Error al enviar'

        # Actualizar la barra de progreso
        progress = min((index + 1) / total_messages, 1.0)  # Asegurarse de que el valor esté entre 0 y 1
        progress_bar.progress(progress)
        
        time.sleep(60)  # Esperar 60 segundos entre mensajes

    status_text.text("¡Todos los mensajes han sido procesados!")
    return df

def whatsapp_sender():
    st.title("Envío de Mensajes de WhatsApp")

    message_type = st.radio("Selecciona el tipo de envío:", ("Personal", "Masivo"))

    if message_type == "Personal":
        send_personal_message()
    else:
        st.subheader("Envío de Mensajes Masivos")
        uploaded_file = st.file_uploader("Cargar archivo Excel", type=["xlsx"])

        if uploaded_file is not None:
            df = load_excel_data(uploaded_file)
            if df is not None:
                # Convertir la columna 'FECHA' a datetime si no lo está ya
                df['FECHA'] = pd.to_datetime(df['FECHA'])
                
                # Filtrar registros de los últimos 5 días
                five_days_ago = datetime.now() - timedelta(days=5)
                df_filtered = df[(df['WHATSAPP'] == True) & (df['FECHA'] > five_days_ago)].copy()
                
                if df_filtered.empty:
                    st.warning("No hay datos con WHATSAPP marcado como TRUE en los últimos 5 días.")
                else:
                    st.write("Selecciona los mensajes a enviar:")
                    
                    df_filtered['enviar'] = False
                    selected_indices = []
                    
                    for index, row in df_filtered.iterrows():
                        if st.checkbox(f"{row['NOMBRE']} - {row['TELEFONO']} - {str(row['NOTAS'])[:50]}... - Fecha: {row['FECHA'].strftime('%Y-%m-%d')}", key=f"checkbox_{index}"):
                            selected_indices.append(index)
                    
                    df_filtered.loc[selected_indices, 'enviar'] = True
                    
                    if st.button("Enviar Mensajes Seleccionados"):
                        df_to_send = df_filtered[df_filtered['enviar']]
                        
                        if not df_to_send.empty:
                            updated_df = send_bulk_messages(df_to_send)
                            
                            df.update(updated_df)
                            
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False)
                            excel_data = output.getvalue()
                            
                            st.download_button(
                                label="Descargar Excel Actualizado",
                                data=excel_data,
                                file_name="mensajes_whatsapp_actualizados.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.warning("No se ha seleccionado ningún mensaje para enviar.")
        else:
            st.info("Por favor, carga un archivo Excel para comenzar el envío masivo.")

if __name__ == "__main__":
    whatsapp_sender()
