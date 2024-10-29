import streamlit as st
import subprocess
import sys
import os
import hashlib
import sqlite3
import json
import toml
import requests
import base64

def cargar_configuracion():
    try:
        config = toml.load("./.streamlit/config.toml")
        return config["token"]["github"]
    except FileNotFoundError:
        st.error("Archivo de configuración no encontrado.")
        return None
    except KeyError:
        st.error("Clave no encontrada en el archivo de configuración.")
        return None


SCRIPT_PATH = "actualizar_token.py"
DB_PATH = "users.db"
GITHUB_TOKEN = cargar_configuracion()
REPO_NAME = "jagt2024/reservar"   
FILE_PATH = "token.json"

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
    try:
        # Configurar headers para la API de GitHub
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # URL de la API de GitHub para el archivo
        api_url = f'https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}'
        
        # Primero obtener el SHA del archivo actual
        response = requests.get(api_url, headers=headers)
        if response.status_code == 401:
            return False, "Error de autenticación: Token de GitHub inválido o expirado 1"
        elif response.status_code != 200:
            return False, f"Error al obtener el archivo: {response.json().get('message', '')}"
        
        current_file = response.json()
        
        # Preparar la actualización
        update_data = {
            'message': 'Actualizar token.json',
            'content': base64.b64encode(json.dumps(file_content, indent=2).encode()).decode(),
            'sha': current_file['sha']
        }
        
        # Realizar la actualización
        response = requests.put(api_url, headers=headers, json=update_data)
        
        if response.status_code == 200:
            return True, "Archivo actualizado exitosamente en GitHub"
        elif response.status_code == 401:
            return False, "Error de autenticación: Token de GitHub inválido o expirado 2"
        else:
            return False, f"Error al actualizar el archivo: {response.json().get('message', '')}"
            
    except Exception as e:
        return False, f"Error al conectar con GitHub: {str(e)}"

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
