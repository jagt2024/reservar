import streamlit as st

# Definir el estilo CSS para el botón de imagen
st.markdown("""
    <style>
    .image-button {
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        transition: transform 0.3s ease;
        display: inline-block;
    }
    
    .image-button img {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .image-button:hover {
        transform: scale(1.1);
    }
    
    .image-button:active {
        transform: scale(0.95);
    }
    </style>
""", unsafe_allow_html=True)

# Crear el botón de imagen
st.markdown(f"""
    <a href="https://reservar-dp.streamlit.app/" target="_blank" class="image-button">
        <img src="./assets-dp/dp-andres.png" alt="Abrir Aplicación">
    </a>
""", unsafe_allow_html=True)

# Alternativa usando componentes nativos de Streamlit
col1, col2, col3 = st.columns([2, 1, 2])

with col2:
    image = st.image("dp-andres.png", width=60)
    # Hacer la imagen clicable
    if st.button("", key="image_button", use_container_width=True):
        js = f"""
        <script>
            window.open("https://reservar-dp.streamlit.app/", "_blank");
        </script>
        """
        st.components.v1.html(js, height=0)