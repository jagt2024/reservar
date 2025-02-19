import streamlit as st
import pandas as pd
from PIL import Image
import os

def create_upload_directory():
    if not os.path.exists("./assets-amo"):
        os.makedirs("./assets-amo")

def save_uploaded_image(uploaded_file, product_name):
    if uploaded_file is not None:
        create_upload_directory()
        file_path = f"./assets-amo/{product_name.lower().replace(' ', '_')}.jpg"
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None

def catalogo():
    # Header
    st.title("Catálogo de Servicios Especializados")
    st.markdown("*Maxima confidencialid, Te Esperamos*")
    
    # Admin mode toggle
    admin_mode = st.sidebar.checkbox("Modo Administrador")
    
    # Create product data with matched array lengths
    products = {
        "Psicologia": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Ansiedad - Depresion",
            "icon": "🧪",
            "image_path": "./assets-amo/psico2.jpg"
        },
        "Duelo por Separacion": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Por Engano, Sin Amor, Falta de Confianza, Adicciones etc.",
            "icon": "🌺",
            "image_path": "./assets-amo/psico3.jpg"
        },
        "Dependencia en Adicciones": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Alcohol, Tabaco, Juegos, Drogas etc. ",
            "icon": "✨",
            "image_path": "./assets-amo/imagen6.jpg"
        },
        "Dependencia Emocionnal": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Inseguridad, Vacios, Amor Propio etc. ",
            "icon": "🍽️",
            "image_path": "./assets-amo/psico7.jpg"
        },
        "Problemas de Aprendizaje Infantil ": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Trastornos del Sueno, Vision, TDAH , etc.",
            "icon": "🍽️",
            "image_path": "./assets-amo/psico8.jpg"
        },
        "Conflictos de Relacion de Pareja ": {
            "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Comunicacion, Confianza, Dinero etc.",
            "icon": "🍽️",
            "image_path": "./assets-amo/psico5.jpg"
        },
        "Manejo de Celos": {
           "Numero Sesiones": ["2", "3", "4"],
            "Tiempo": ["8:30", "9:45", "10:30"],
            "...": "Inseguridades, Dominio, Confianza etc.",
            "icon": "🍽️",
            "image_path": "./assets-amo/psico4.jpg"
        }
    }
    
    # Courses section
    st.header("Cursos")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Diplomado")
        st.markdown("""
        - Diplomado de Primeros Auxilios Psicologicos 
        - Basado en el libro El Juego Perfecto 
        - Certificados de asistencias y materiales, sin costo
        - Dias Sabados de 3 pm. a 5 pm.
        """)
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen", key="image1")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "image1")
    
        if os.path.exists("./assets-amo/lugar.png"):
            st.image("./assets-amo/lugar.png", width=300)
    
    with col2:
        st.subheader("Tecnicas Psicologicas")
        st.markdown("""
        - En Terapias
        - Conciencias 
        - Sanacion de Adicciones
        """)
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen 2", key="image3")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "image3")
        
        if os.path.exists("./assets-amo/lugar.png"):
            st.image("./assets-amo/lugar.png", width=300)
    
    # Products Display
    st.header("🛍️ Nuestros Servicios")
    
    for product_name, product_info in products.items():
        with st.expander(f"{product_info['icon']} {product_name}"):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Image upload in admin mode
                if admin_mode:
                    uploaded_file = st.file_uploader(
                        f"Subir imagen para {product_name}",
                        key=product_name
                    )
                    if uploaded_file:
                        product_info["image_path"] = save_uploaded_image(
                            uploaded_file,
                            product_name.lower().replace(" ", "_")
                        )
                
                # Display image if exists
                if "image_path" in product_info and os.path.exists(product_info["image_path"]):
                    st.image(product_info["image_path"], width=300)
                else:
                    st.info("Imagen no disponible")
            
            with col2:
                st.markdown(f"**... :** {product_info['...']}")
                
                # Create a price table with matched lengths
                data = {
                    "No. Sesiones": product_info["Numero Sesiones"],
                    "Horario": product_info["Tiempo"]
                }
                df = pd.DataFrame(data)
                st.table(df)
    
    # Loyalty Program
    st.header("♻️ Programa de Fidelización")
    st.info("""
    ¡CUANDO HAY TERAPIA HAY ESPERANZA!
    """)
    
    # Contact Information
    st.header("📞 Contáctanos")
    st.markdown("""
    Para nosotros es un gusto atenderte en SANTA ISABEL, GIRARDOT.
    
    **Línea de atención:** 311 2852770
    """)
    