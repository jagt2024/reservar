import streamlit as st

def info_dp():
    st.set_page_config(page_title="Distrito Privado", page_icon="🚚", layout="wide")
    
    # Title and Introduction
    st.title("Distrito Privado: Servicio Exclusivo de Transporte de Usuarios Asociados")
    st.markdown("---")
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Descripción General", 
        "Características del Servicio", 
        "Beneficios para el Negocio", 
        "Ventajas Estratégicas", 
        "Soluciones a Desafíos"
    ])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.header("¿Qué es Distrito Privado?")
            st.write("""
            Distrito Privado es la Asociacion de Usuarios y Conductores que usan la plataforma privada GCR, diseñada para reseervar, informar y controlar el servicio de transporte especifico desde y hacia el Aeropuerto. permitiendo a usuarios y conductores tener la informacion de Horarios, Precios, Responsables y Zonas para el servicio solicitado a la mano.
            """)
            #st.write("""
            #La plataforma proporciona soluciones web y móviles personalizadas para 
            #automatizar el servicio empresarial según las necesidades específicas de cada #organización.
            #""")
        with col2:
            st.image("assets-dp/oficina1.jpg", caption="Distrito Privado", use_column_width=True)
    
    with tab2:
        st.header("Características del Servicio")
        caracteristicas = {
            "Accesibilidad": {
                "desc": "Servicio disponible en cualquier momento, ideal para usuarios con horarios no convencionales.",
                "img": "assets-dp/OIP.jpg"
            },
            
            #"Rastreo en Tiempo Real": "Control y visibilidad completa sobre la logística de transporte.",
            "Reservas Programadas": {
                "desc" : "Planificación anticipada del servicio de transporte solicitado.",
                 "img": "assets-dp/OIP2.jpg"
            },
            "Envio en linea al correo suministrado ": { 
                "desc": "Se notificara e informara de la reserva con la iformacion relevante, tanto al usuario que solicita el servicio como al encargado que presta el servicio, asegurando la reserva.",
                 "img": "assets-dp/oficina1.jpg"
            },
            "Facturacion del Servicio": { 
                "desc":"Se enviara la Facttura que identifica el servicio prestado y su costo, al correo suministrado.",
                 "img": "assets-dp/oficina1.jpg"
            },
            "Calificaciones y Reseñas": {
                "desc": "Retroalimentación directa para mejorar la calidad del servicio.",
                "img": "assets-dp/oficina1.jpg"
            }
        }
        for key, value in caracteristicas.items():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{key}**")
                st.write(value["desc"])
            with col2:
                st.image(value["img"], caption=key, use_column_width=True)
    
    with tab3:
        st.header("Beneficios para el Negocio")
        beneficios = {
            "Aumento de la Eficiencia": {
                "desc":"Optimización de rutas y reducción de tiempos de respuesta.",
                  "img": "assets-dp/rutas.jpg"
            },
            "Ampliación de Base de Clientes": {
                "desc":"Atracción y retención de clientes mediante un servicio conveniente.",
                 "img": "assets-dp/OIP3.jpg"
            },
            "Reducción de Costos": {
                "desc": "Automatización de procesos y optimización de recursos.",
                 "img": "assets-dp/oficina1.jpg"
            },
            "Mejora la Experiencia del Cliente": {
                "desc": "Mejor satisfacción y fidelidad.",
                "img": "assets-dp/OIP1.jpg"
            },
            "Competitividad y Automatizacion": {
                "desc": "Adopción de herramientas para el servicio de transporte.",
                 "img": "assets-dp/rutas2.jpg"
            }
        }
        
        for key, value in beneficios.items():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{key}**")
                st.write(value["desc"])
            with col2:
                st.image(value["img"], caption=key, use_column_width=True)
    
    with tab4:
        st.header("Ventajas Estratégicas")
        ventajas = {
            "Datos y Analítica": {
                "desc": "Recopilación de información para decisiones estratégicas.",
                 "img": "assets-dp/oficina1.jpg"
            },
            "Flexibilidad": {
                "desc": "Adaptación de soluciones a necesidades específicas.",
                "img": "assets-dp/ruta1.jpg"
            },
            "Mejora de Imagen de Marca": {
                "desc": "Posicionamiento, innovación y comodidad.",
                "img": "assets-dp/transporte1.jpg"
            },
            "Expansión": {
                "desc": "Nuevas rutas y servicios de Transporte.",
                 "img": "assets-dp/transporte2.jpg"
            }
                
        }
        for key, value in ventajas.items():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{key}**")
                st.write(value["desc"])
            with col2:
                st.image(value["img"], caption=key, use_column_width=True)
    with tab5:
        st.header("Soluciones a Desafíos Comunes")
        soluciones = {
            "Tráfico y Congestión": {
                "desc": "Algoritmos de optimización de rutas para minimizar retrasos.",
                 "img": "assets-dp/oficina1.jpg"
            },
            "Gestión de Conductores": {
                "desc": "Asignación programada de conductores a cargodlservicio por zonas.",
                "img": "assets-dp/oficina1.jpg"
            },
            "Seguridad": {
                "desc": "Verificación de identidad de conductores y compartir detalles de la ruta.",
                 "img": "assets-dp/mapa1.jpg"
            }
        }
        for key, value in soluciones.items():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{key}**")
                st.write(value["desc"])
            with col2:
                st.image(value["img"], caption=key, use_column_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown("**Distrito Privado y el uso de la Pltaforma: Aportan a la Seguridad y Confianza de Usuarios y Conductores**")

#if __name__ == "__main__":
#    main()
