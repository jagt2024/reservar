import streamlit as st

# Definir el estilo CSS para el ícono de aplicación
st.markdown("""
<style>
.app-icon-container {
    position: relative;
    display: inline-block;
    width: 72px;
    height: 72px;
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    cursor: pointer;
    transition: transform 0.3s ease;
}

.app-icon {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 16px;
}

.app-link {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(0, 0, 0, 0.4);
    color: white;
    font-weight: 600;
    text-decoration: none;
    transition: opacity 0.3s ease;
    opacity: 0;
}

.app-icon-container:hover .app-link {
    opacity: 1;
}

.app-icon-container:hover {
    transform: scale(1.05);
}
</style>
""", unsafe_allow_html=True)

# Crear el ícono de aplicación con superposición
st.markdown(f"""
<div class="app-icon-container">
    <img src="assets-dp/coche-electrico.png" alt="App Icon" class="app-icon">
    <a href="https://reservar-dp.streamlit.app/" target="_blank" class="app-link">
        Abrir Aplicación
    </a>
</div>
""", unsafe_allow_html=True)