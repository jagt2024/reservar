import streamlit as st
import sqlite3

# Acceder a secretos
db_password = st.secrets["db_password"]
api_key = st.secrets["api_key"]

# Usar los secretos de forma segura
def connect_to_db():
    conn = sqlite3.connect('users.db')
    # Usa db_password aquí si es necesario
    return conn

def api_call():
    # Usa api_key aquí para autenticación
    pass

# No imprimas nunca los secretos en la aplicación
st.write("Conexión a la base de datos establecida")
st.write("API lista para usar")

# Resto de tu aplicación
   