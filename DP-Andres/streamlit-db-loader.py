# db_loader.py
import streamlit as st
from cryptography.fernet import Fernet
import base64
import os

def load_encrypted_database():
    """Carga y desencripta la base de datos en Streamlit"""
    # Obtener la contraseña desde los secretos de Streamlit
    db_password = st.secrets["DB_PASSWORD"]
    
    # Ruta a la base de datos encriptada
    encrypted_db_path = "database.db.encrypted"
    
    # Leer la clave de encriptación
    with open("encryption_key.key", "rb") as key_file:
        key_data = key_file.read()
        salt = key_data[:16]
        key = key_data[16:]
    
    try:
        # Crear instancia de Fernet con la clave
        fernet = Fernet(key)
        
        # Leer y desencriptar la base de datos
        with open(encrypted_db_path, "rb") as enc_file:
            encrypted_data = enc_file.read()
            decrypted_data = fernet.decrypt(encrypted_data)
        
        # Guardar la base de datos desencriptada temporalmente
        with open("database.db", "wb") as db_file:
            db_file.write(decrypted_data)
        
        return True
    except Exception as e:
        st.error(f"Error al cargar la base de datos: {str(e)}")
        return False

# Modificar tu app.py para incluir esto al inicio
def initialize_app():
    if not os.path.exists("database.db"):
        if not load_encrypted_database():
            st.error("No se pudo cargar la base de datos")
            st.stop()
