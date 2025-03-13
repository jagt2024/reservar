import streamlit as st
import pandas as pd
from PIL import Image
import os

def create_upload_directory():
    if not os.path.exists("./assets-dlv"):
        os.makedirs("./assets-dlv")

def save_uploaded_image(uploaded_file, product_name):
    if uploaded_file is not None:
        create_upload_directory()
        file_path = f"./assets-dlv/{product_name.lower().replace(' ', '_')}.png"
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None

def catalogo():
    # st.set_page_config(
    #     page_title="Catálogo de Productos",
    #     page_icon="🧴",
    #      layout="wide"
    #)
    
    # Header
    st.title("🧴 Catálogo de Productos para Reposteria y Panaderia")
    st.markdown("*Productos Frescos y de Calidad*")
    
    # Admin mode toggle
    admin_mode = st.sidebar.checkbox("Modo Administrador")
    
    # Create product data
    products = {
        "Sprinkles - GrageaS": {
            "sizes": ["Paquete de 500" , "Paquete de 1000"],
            "prices": ["$10.000", "$25.000"],
            "...": "Grageas de diferentes colores tamanos y Texturas",
            "icon": "🧪",
            "image_path": "./assets-dlv/spimg1.png",
            "image_path": "./assets-dlv/spimg2.png"

        },
        "Moldes ": {
            "sizes": ["Paquete de 20" , "Caja de 10"],
            "prices": ["$30.000", "$25.000"],
            "...": "Moldes ",
            "icon": "🌺",
            "image_path": "./assets-dlv/moimg1.png"
                    },
        "Cortadores ": {
            "sizes": ["Paquete de 20" , "Paquete de 10"],
            "prices": ["$40.000", "$20.000"],
            "...": "Cortadores con diferentes Figuras",
            "icon": "✨",
            "image_path": "./assets-dlv/coimg1.png"
        },
        "Bailarinas ": {
            "sizes": ["Tipo 1", "Tipo 2", "Tipo 3"],
            "prices": ["$20.000", "$45.000", "$60.000"],
            "...": "Baialrinas con difeerentes tamanos ...",
            "icon": "🍽️",
            "image_path": "./assets-dlv/baimg1.png"
        },
        "Mini Licores": {
            "sizes": ["Botella 500 cc", "Botella 1000 cc", "Botella 2.000 cc"],
            "prices": ["$100.000", "$180.000", "$350.000"],
            "...": "Mini Licores, Gato Negro.....",
            "icon": "🍽️",
            "image_path": "./assets-dlv/lcimg1.png"
        },
        "Cajitas ": {
            "sizes": ["Tamano 1", "Tamano 2", "Tamano 3"],
            "prices": ["$5.000", "$6.000", "$7.000"],
            "...": "Vive una permanente y agradable sensación de un abrazo",
            "icon": "👕",
            "image_path": "./assets-dlv/image8.png"
        },
        "Otros ": {
            "sizes": ["Otro 1", "Otro 2", "Otro 3"],
            "prices": ["$0", "$0", "$0"],
            "...": "Llena tu entorno de PAZ con nuestros aromas especiales",
            "icon": "🏠",
            "image_path": "./assets-dlv/image3.png"
        }        
    }
    
    # Traperos (Mops) section
    st.header("🏠 Promocion Especial")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Poducto Ref.")
        st.markdown("""
        - Meterial XXXX
        - Copa plástica
        - Cabo 100% aluminio
        """)
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen Ref. 1", key="promo1")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "promo1")
        
        if os.path.exists("./assets-dlv/image6.png"):
            st.image("./assets-dlv/image6.png", width=300)
    
    with col2:
        st.subheader("Promocion 2 Ref. ")
        st.markdown("Ideal para uso industrial y comercial")
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen pomocion2", key="promo2")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "promo2")
        
        if os.path.exists("./assets-dlv/image6.png"):
            st.image("./assets-dlv/image6.png", width=300)
    
    # Products Display
    st.header("🛍️ Nuestros Productos")
    
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
                
                # Create a price table
                data = {
                    "Presentación": product_info["sizes"],
                    "Precio": product_info["prices"]
                }
                df = pd.DataFrame(data)
                st.table(df)
    
    # Loyalty Program
    st.header("♻️ Programa de Fidelización")
    st.info("""
    ¡TODOS nuestros PRODUCTOS son de Alta Calidad!
    - Grantizamos ...
    - Cumplimieento de Entregas ...
    """)
    
    # Contact Information
    st.header("📞 Contáctanos")
    st.markdown("""
    Para nosotros es un gusto atenderte y ser el proveedor de tus productos.
    
    **Línea de atención:** 320 
    """)

#if __name__ == "__main__":
#    catalogo()