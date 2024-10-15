import streamlit as st
import subprocess
import sys
import os
import hashlib
import sqlite3
import json
import requests
from github import Github

# Asumimos que actualizar_token.py está en el mismo directorio
SCRIPT_PATH = "actualizar_token.py"
DB_PATH = "users.db"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = "jagt2024/reservar"  # Reemplaza con tu nombre de usuario y repositorio
FILE_PATH = "token.json"  # Reemplaza con la ruta correcta en tu repositorio

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

def update_github_file(file_content):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    try:
        # Obtener el archivo actual
        file = repo.get_contents(FILE_PATH)
        
        # Actualizar el archivo
        repo.update_file(
            FILE_PATH,
            "Actualizar token.json",
            json.dumps(file_content, indent=2),
            file.sha
        )
        return True, "Archivo actualizado exitosamente en GitHub"
    except Exception as e:
        return False, f"Error al actualizar el archivo en GitHub: {str(e)}"

def run_actualizar_token():
    try:
        result = subprocess.run([sys.executable, SCRIPT_PATH], 
                                capture_output=True, 
                                text=True, 
                                check=True)
        output = result.stdout
        if result.stderr:
            st.warning(f"Advertencias del script:\n{result.stderr}")
        
        # Intentar leer el archivo token.json actualizado
        with open('token.json', 'r') as file:
            token_content = json.load(file)
        
        # Actualizar el archivo en GitHub
        success, message = update_github_file(token_content)
        if success:
            return True, f"{output}\n\n{message}"
        else:
            return False, message
    except subprocess.CalledProcessError as e:
        return False, f"Error al ejecutar el script: {e.output}"
    except FileNotFoundError:
        return False, "No se pudo encontrar el archivo token.json"
    except json.JSONDecodeError:
        return False, "El archivo token.json no es un JSON válido"

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

if __name__ == "__main__":
    newtoken()
