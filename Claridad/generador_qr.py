import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
import os
from datetime import datetime
import io

def load_excel_data():
    """Carga los datos del archivo Excel."""
    try:
        df = pd.read_excel("./archivos-cld/parametros_empresa.xlsx", sheet_name="encargado")
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo Excel: {str(e)}")
        return None

def generate_qr_code(data):
    """Genera un código QR basado en los datos proporcionados."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    return qr_image

def save_qr_code(qr_image, save_dir, filename):
    """Guarda el código QR generado en el directorio especificado."""
    # Crear directorio si no existe
    os.makedirs(save_dir, exist_ok=True)
    # Guardar imagen
    filepath = os.path.join(save_dir, filename)
    qr_image.save(filepath)
    return filepath

def codigoqr():
    st.title("Generador de Códigos QR")
    
    # Inicializar el directorio de guardado en session_state si no existe
    if 'save_dir' not in st.session_state:
        st.session_state['save_dir'] = "codigos_qr"

    # Cargar datos del Excel
    df = load_excel_data()
    
    if df is not None:
        # Configuración del directorio de guardado
        st.subheader("Configuración de guardado")
        save_dir = st.text_input(
            "Directorio para guardar los códigos QR",
            value=st.session_state['save_dir'],
            help="Introduce la ruta completa o relativa donde deseas guardar los códigos QR"
        )
        st.session_state['save_dir'] = save_dir
        
        # Mostrar los datos en una tabla
        st.subheader("Datos disponibles")
        st.dataframe(df)
        
        # Columnas disponibles
        columns = df.columns.tolist()
        
        # Permitir selección de columnas para incluir en el QR
        selected_columns = st.multiselect(
            "Seleccione los campos que desea incluir en el código QR",
            columns,
            default=columns  # Por defecto todas las columnas seleccionadas
        )
        
        # Permitir selección múltiple de registros
        selected_indices = st.multiselect(
            "Seleccione los registros para generar códigos QR",
            range(len(df)),
            format_func=lambda x: f"Registro {x+1}: {df.iloc[x][selected_columns].to_dict()}"
        )
        
        if st.button("Generar Códigos QR"):
            if selected_indices and selected_columns:
                for idx in selected_indices:
                    # Obtener datos del registro seleccionado (solo columnas seleccionadas)
                    record = df.iloc[idx][selected_columns]
                    
                    # Crear string con la información para el QR
                    qr_data = ", ".join([f"{col}: {val}" for col, val in record.items()])
                    
                    # Generar nombre único para el archivo
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"QR_registro_{idx+1}_{timestamp}.png"
                    
                    try:
                        # Generar el código QR
                        qr_image = generate_qr_code(qr_data)
                        
                        # Guardar el código QR en el directorio seleccionado
                        filepath = save_qr_code(qr_image, save_dir, filename)
                        
                        # Convertir la imagen PIL a bytes para mostrarla en Streamlit
                        img_byte_arr = io.BytesIO()
                        qr_image.save(img_byte_arr, format='PNG')
                        img_byte_arr = img_byte_arr.getvalue()
                        
                        # Mostrar el código QR generado
                        st.success(f"Código QR generado y guardado en: {filepath}")
                        st.image(img_byte_arr, caption=f"Código QR para registro {idx+1}")
                    except Exception as e:
                        st.error(f"Error al generar o guardar el código QR: {str(e)}")
            else:
                if not selected_columns:
                    st.warning("Por favor, seleccione al menos una columna para incluir en el QR.")
                if not selected_indices:
                    st.warning("Por favor, seleccione al menos un registro.")

#if __name__ == "__main__":
#    codioqr()