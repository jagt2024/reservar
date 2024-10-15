import streamlit as st
import subprocess
import sys
import os
import hashlib
import sqlite3

#import bcrypt
#pip install bcrypt
#Para utilizar este nuevo sistema, necesitarás modificar la estructura de tu base de datos y la forma en que almacenas las contraseñas. Aquí te dejo un script SQL actualizado para crear la tabla y un ejemplo de cómo insertar un usuario:
#sqlCopyCREATE TABLE users (
#    id INTEGER PRIMARY KEY AUTOINCREMENT,
#    username TEXT UNIQUE NOT NULL,
#    password BLOB NOT NULL,
#    role TEXT NOT NULL
#);

#-- No insertes usuarios directamente en SQL. 
#-- En su lugar, usa Python para hashear la contraseña y luego insertarla.

#def insert_user(username, password, role):
#    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
#    conn = sqlite3.connect('users.db')
#    cursor = conn.cursor()
#    cursor.execute("""
#        INSERT INTO users (username, password, role) 
#        VALUES (?, ?, ?)
#    """, (username, hashed, role))
#    conn.commit()
#    conn.close()

# Ejemplo de uso
#insert_user('support_user', 'password123', 'soporte')

# Asumimos que actualizar_token.py está en el mismo directorio
SCRIPT_PATH = "actualizar_token.py"
DB_PATH = "users.db"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_support_credentials(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT password FROM users 
            WHERE username = ? AND role = 'soporte'
        """, (username,))
        result = cursor.fetchone()
        
        if result:
            stored_password = result[0]
            return stored_password == hash_password(password)
        else:
            return False
    finally:
        conn.close()

def run_actualizar_token():
    try:
        result = subprocess.run([sys.executable, SCRIPT_PATH], 
                                capture_output=True, 
                                text=True, 
                                check=True)
        output = result.stdout
        if result.stderr:
            st.warning(f"Advertencias del script:\n{result.stderr}")
        return True, output
    except subprocess.CalledProcessError as e:
        return False, f"Error al ejecutar el script: {e.output}"

def init_session_state():
    if 'is_support' not in st.session_state:
        st.session_state.is_support = False
    if 'login_message' not in st.session_state:
        st.session_state.login_message = ""

def newtoken():
    init_session_state()
    st.title("Panel de Administración")

    # Sección de login para el área de soporte
    st.sidebar.header("Área de Soporte")
    username = st.sidebar.text_input("Usuario", key="username_input")
    password = st.sidebar.text_input("Contraseña", type="password", key="password_input")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("Iniciar Sesión", key="login_button"):
            if verify_support_credentials(username, password):
                st.session_state.is_support = True
                st.session_state.login_message = "Acceso de soporte concedido"
            else:
                st.session_state.login_message = "Credenciales inválidas"
    
    with col2:
        if st.button("Cerrar Sesión", key="logout_button"):
            st.session_state.is_support = False
            st.session_state.login_message = "Sesión cerrada"

    if st.session_state.login_message:
        st.sidebar.info(st.session_state.login_message)
        # Limpiar el mensaje después de mostrarlo
        st.session_state.login_message = ""

    if st.session_state.is_support:
        if st.sidebar.button("Actualizar token.json", key="update_token_button"):
            with st.spinner("Actualizando token.json..."):
                success, message = run_actualizar_token()
            
            if success:
                st.success("token.json actualizado exitosamente en GitHub!")
                st.text("Salida del script:")
                st.code(message)
            else:
                st.error("Falló la actualización de token.json")
                st.text("Mensaje de error:")
                st.code(message)

    # Contenido principal de la aplicación
    st.header("Bienvenido a la Aplicación")
    st.write("Esta es la página de actualización del token.")
    
    # Aquí puedes agregar más funcionalidades para todos los usuarios

#if __name__ == "__main__":
#    newtoken()