import streamlit as st
import subprocess
import sys
import os

# Asumimos que actualizar_token.py está en el mismo directorio
SCRIPT_PATH = "actualizar_token.py"

def run_actualizar_token():
    try:
        # Ejecutar el script como un subproceso
        result = subprocess.run([sys.executable, SCRIPT_PATH], 
                                capture_output=True, 
                                text=True, 
                                check=True)
        
        # Capturar la salida del script
        output = result.stdout
        
        # Si el script imprime algo a stderr, lo consideramos como advertencias
        if result.stderr:
            st.warning(f"Advertencias del script:\n{result.stderr}")
        
        return True, output
    except subprocess.CalledProcessError as e:
        # Si el script falla, capturamos el error
        return False, f"Error al ejecutar el script: {e.output}"

st.title("Actualizar token.json en GitHub")

if st.button("Actualizar token.json"):
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

# Opcionalmente, puedes agregar un área para mostrar el contenido actual de token.json
if st.checkbox("Mostrar contenido actual de token.json"):
    try:
        with open("token.json", "r") as file:
            content = file.read()
        st.text("Contenido actual de token.json:")
        st.code(content, language="json")
    except FileNotFoundError:
        st.warning("No se pudo encontrar el archivo token.json localmente.")
