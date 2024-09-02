import streamlit as st
import requests
import time

# Configura la URL de tu servidor Node.js
SERVER_URL = "node ./dist/app.js"

def get_qr():
    response = requests.get(f"{SERVER_URL}/qr")
    if response.status_code == 200:
        return response.content
    return None

def get_status():
    response = requests.get(f"{SERVER_URL}/status")
    if response.status_code == 200:
        return response.json()['status']
    return False

def send_message(phone, message):
    response = requests.post(f"{SERVER_URL}/send", json={"phone": phone, "message": message})
    return response.json()

def main():
    st.title("WhatsApp Web Interface")

    if 'status' not in st.session_state:
        st.session_state['status'] = False

    status = get_status()
    st.session_state['status'] = status

    if not st.session_state['status']:
        st.write("Esperando conexión con WhatsApp...")
        qr = get_qr()
        if qr:
            st.image(qr, caption="Escanea este código QR con WhatsApp")
        
        # Comprobamos el estado cada 5 segundos
        time.sleep(5)
        st.experimental_rerun()
    else:
        st.success("¡Conectado a WhatsApp!")
        
        phone = st.text_input("Número de teléfono (con código de país)")
        message = st.text_area("Mensaje")
        
        if st.button("Enviar mensaje"):
            if phone and message:
                result = send_message(phone, message)
                if 'id' in result:
                    st.success(f"Mensaje enviado. ID: {result['id']}")
                else:
                    st.error(f"Error al enviar el mensaje: {result.get('error', 'Unknown error')}")
            else:
                st.warning("Por favor, introduce un número de teléfono y un mensaje.")

if __name__ == "__main__":
    main()
