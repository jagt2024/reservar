import streamlit as st
import pandas as pd
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

def generate_whatsapp_link(phone_number, message):
    encoded_message = message.replace(' ', '%20')
    return f"https://wa.me/{phone_number}?text={encoded_message}"

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

def whatsapp_sender():
    st.title("Generador de Enlaces para Mensajes de WhatsApp")

    uploaded_file = st.file_uploader("Cargar archivo Excel", type=["xlsx"])

    if uploaded_file is not None:
        df = load_excel_data(uploaded_file)
        if df is not None:
            df['FECHA'] = pd.to_datetime(df['FECHA'])
            
            days_to_filter = st.number_input("Ingrese el número de días para filtrar los datos:", min_value=1, value=15, step=1)
            
            filter_date = datetime.now() - timedelta(days=days_to_filter)
            df_filtered = df[(df['WHATSAPP'] == True) & (df['FECHA'] > filter_date)].copy()
            
            if df_filtered.empty:
                st.warning(f"No hay datos con WHATSAPP marcado como TRUE en los últimos {days_to_filter} días.")
            else:
                st.write("Selecciona los mensajes para generar enlaces:")
                
                df_filtered['enviar'] = False
                selected_indices = []
                
                for index, row in df_filtered.iterrows():
                    if st.checkbox(f"{row['NOMBRE']} - {row['TELEFONO']} - {str(row['NOTAS'])[:50]}... - Fecha: {row['FECHA'].strftime('%Y-%m-%d')}", key=f"checkbox_{index}"):
                        selected_indices.append(index)
                
                df_filtered.loc[selected_indices, 'enviar'] = True
                
                if st.button("Generar Enlaces de WhatsApp"):
                    df_to_send = df_filtered[df_filtered['enviar']]
                    
                    if not df_to_send.empty:
                        st.subheader("Enlaces generados:")
                        for _, row in df_to_send.iterrows():
                            phone_number = format_phone_number(row['TELEFONO'])
                            message = str(row['NOTAS'])
                            whatsapp_link = generate_whatsapp_link(phone_number, message)
                            st.markdown(f"[Enviar mensaje a {row['NOMBRE']}]({whatsapp_link})")
                        
                        # Preparar DataFrame para descargar
                        df_to_send['ENLACE_WHATSAPP'] = df_to_send.apply(lambda row: generate_whatsapp_link(format_phone_number(row['TELEFONO']), str(row['NOTAS'])), axis=1)
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_to_send.to_excel(writer, index=False)
                        excel_data = output.getvalue()
                        
                        st.download_button(
                            label="Descargar Excel con Enlaces",
                            data=excel_data,
                            file_name="enlaces_whatsapp.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("No se ha seleccionado ningún mensaje para generar enlaces.")
    else:
        st.info("Por favor, carga un archivo Excel para comenzar.")

#if __name__ == "__main__":
#    whatsapp_sender()
