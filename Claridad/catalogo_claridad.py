import streamlit as st
import pandas as pd
from PIL import Image
import os

def create_upload_directory():
    if not os.path.exists("./assets-cld"):
        os.makedirs("./assets-cld")

def save_uploaded_image(uploaded_file, product_name):
    if uploaded_file is not None:
        create_upload_directory()
        file_path = f"./assets-cld/{product_name.lower().replace(' ', '_')}.jpg"
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
    st.title("🧴 Catálogo de Productos de Limpieza")
    st.markdown("*Válido del 15 Noviembre 2024 al 31 de diciembre 2025*")
    
    # Admin mode toggle
    admin_mode = st.sidebar.checkbox("Modo Administrador")
    
    # Create product data
    products = {
        "Hipoclorito": {
            "sizes": ["20.000 cc", "3.800 cc"],
            "prices": ["$50.000", "$14.000"],
            "...": "Es momento de hacer una desinfección profunda en tu hogar y remover las manchas en tu ropa blanca",
            "icon": "🧪",
            "image_path": "./assets-cld/image2.jpg"
        },
        "Eliminador de Olores": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc", "500 cc"],
            "prices": ["$100.000", "$25.000", "$15.000", "8.000"],
            "...": "Desaparecen los malos olores dejando un aroma suave y fresco",
            "icon": "🌺",
            "image_path": "./assets-cld/image3.jpg"
        },
        "Desengrasante Multiusos": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$100.000", "$25.000", "$15.000"],
            "...": "Elimina la grasa y la mugre en superficies percudidas",
            "icon": "✨",
            "image_path": "./assets-cld/image4.jpg"
        },
        "Jabón Lavaplatos": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$100.000", "$25.000", "$15.000"],
            "...": "Tu Vajilla, Cubiertos y Cristalería estarán RESPLANDECIENTES,Eriquecido co emolietes para proteger tus maos.",
            "icon": "🍽️",
            "image_path": "./assets-cld/image5.jpg"
        },
        "Jabón Liquido para Manos": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$95.000", "$25.000", "$15.000"],
            "...": "Con formula generadora de espuma que limpia, desifecta y humecta la piel.",
            "icon": "🍽️",
            "image_path": "./assets-cld/image5.jpg"
        },
        "Detergente Líquido para Lavadora": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$125.000", "$29.000", "$17.000"],
            "...": "Vive una permanente y agradable sensación de un abrazo",
            "icon": "👕",
            "image_path": "./assets-cld/image8.jpg"
        },
        "Detergente Líquido para Bebe": {
            "sizes": ["2.000 cc", "1.000 cc"],
            "prices": ["$17.000", "$9.000"],
            "...": "Creado especialmente para la ropita de Bebe",
            "icon": "👕",
            "image_path": "./assets-cld/image9.jpg"
        },
        "Jabón para Pisos": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$90.000", "$25.000", "$15.000"],
            "...": "Llena tu entorno de PAZ con nuestros aromas especiales",
            "icon": "🏠",
            "image_path": "./assets-cld/image10.jpg"
        },
        "Cera Autobrillante": {
            "sizes": ["20.000 cc", "3.800 cc", "2.000 cc"],
            "prices": ["$230.000", "$48.000", "$26.000"],
            "...": "Ilumina tus Pisos con nuestra cera especial",
            "icon": "🏠",
            "image_path": "./assets-cld/image11.jpg"
        }
    }
    
    # Traperos (Mops) section
    st.header("🧹 Traperos Especiales")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trapero Ref. 1000")
        st.markdown("""
        - Fibra 100% algodón
        - Copa plástica, uña metálica
        - Cabo 100% aluminio
        """)
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen Trapero Ref. 1000", key="trapero1000")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "trapero1000")
        
        if os.path.exists("./assets-cld/image12.jpg"):
            st.image("./assets-cld/image12.jpg", width=300)
    
    with col2:
        st.subheader("Trapero Ref. INDUSTRIAL")
        st.markdown("Ideal para uso industrial y comercial")
        if admin_mode:
            uploaded_file = st.file_uploader("Subir imagen Trapero Industrial", key="traperoind")
            if uploaded_file:
                save_uploaded_image(uploaded_file, "traperoind")
        
        if os.path.exists("./assets-cld/image13.jpg"):
            st.image("./assets-cld/image13.jpg", width=300)
    
    # Products Display
    st.header("🛍️ Nuestros Productos")
    
    for product_name, product_info in products.items():
        with st.expander(f"{product_info['icon']} {product_name}"):
            col1, col2 = st.columns([1, 2])
            
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
    ¡Los envases de TODOS nuestros PRODUCTOS son RETORNABLES!
    - Por cada envase que RETORNES, recibes 1 punto
    - Con 10 puntos recibes 250cc de jabón gratis
    """)
    
    # Contact Information
    st.header("📞 Contáctanos")
    st.markdown("""
    Para nosotros es un gusto atenderte y ser el proveedor de tus productos de aseo.
    
    **Línea de atención:** 320 4402014
    """)

#if __name__ == "__main__":
#    catalogo()