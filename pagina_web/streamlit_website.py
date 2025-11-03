import streamlit as st
from PIL import Image

# Configuración de la página
st.set_page_config(
    page_title="Un Futuro más Seguro",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado
st.markdown("""
<style>
    /* Estilos generales */
    .stApp {
        background-color: #013220;
    }
    
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Navbar */
    .navbar {
        background-color: #013220;
        padding: 1rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #ff6b35;
        margin-bottom: 2rem;
    }
    
    .brand {
        color: white;
        font-size: 1.8rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .nav-links {
        display: flex;
        gap: 2rem;
    }
    
    .nav-link {
        color: white;
        text-decoration: none;
        font-size: 1.1rem;
        font-weight: 500;
        transition: color 0.3s;
        cursor: pointer;
    }
    
    .nav-link:hover {
        color: #ff6b35;
    }
    
    /* Hero Section */
    .hero {
        text-align: center;
        padding: 4rem 2rem;
        background: linear-gradient(135deg, #013220 0%, #025230 100%);
        border-radius: 15px;
        margin: 2rem 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    
    .hero h1 {
        color: white;
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1.5rem;
        line-height: 1.2;
    }
    
    .hero p {
        color: #e0e0e0;
        font-size: 1.3rem;
        margin-bottom: 2rem;
        max-width: 700px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .cta-button {
        background-color: #ff6b35;
        color: white;
        padding: 1rem 2.5rem;
        border-radius: 30px;
        font-size: 1.2rem;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        transition: all 0.3s;
        border: none;
        cursor: pointer;
    }
    
    .cta-button:hover {
        background-color: #ff8555;
        transform: translateY(-3px);
        box-shadow: 0 5px 15px rgba(255,107,53,0.4);
    }
    
    /* Servicios Section */
    .section {
        padding: 3rem 2rem;
        margin: 2rem 0;
    }
    
    .section-title {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 3rem;
        position: relative;
    }
    
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -10px;
        left: 50%;
        transform: translateX(-50%);
        width: 100px;
        height: 4px;
        background-color: #ff6b35;
    }
    
    .service-card {
        background-color: #025230;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        transition: all 0.3s;
        height: 100%;
        border: 2px solid transparent;
    }
    
    .service-card:hover {
        transform: translateY(-10px);
        border-color: #ff6b35;
        box-shadow: 0 10px 25px rgba(255,107,53,0.2);
    }
    
    .service-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    .service-title {
        color: white;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .service-description {
        color: #e0e0e0;
        font-size: 1rem;
        line-height: 1.6;
    }
    
    /* Contacto Section */
    .contact-section {
        background-color: #025230;
        padding: 3rem 2rem;
        border-radius: 15px;
        margin: 2rem 0;
    }
    
    .contact-info {
        color: white;
        font-size: 1.1rem;
        line-height: 2;
        text-align: center;
    }
    
    .contact-info strong {
        color: #ff6b35;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem;
        color: #e0e0e0;
        border-top: 2px solid #ff6b35;
        margin-top: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar session state para navegación
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'

# Función para cambiar de página
def set_page(page_name):
    st.session_state.page = page_name

# Navbar
col1, col2 = st.columns([2, 3])

with col1:
    # Opción para cargar logo
    logo_file = st.file_uploader("", type=['png', 'jpg', 'jpeg'], key="logo", label_visibility="collapsed")
    
    if logo_file:
        logo = Image.open(logo_file)
        st.image(logo, width=50)
    
    st.markdown('<div class="brand">Un Futuro más Seguro</div>', unsafe_allow_html=True)

with col2:
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 2])
    
    with nav_col1:
        if st.button("Inicio", key="nav_inicio", use_container_width=True):
            set_page('inicio')
    
    with nav_col2:
        if st.button("Servicios", key="nav_servicios", use_container_width=True):
            set_page('servicios')
    
    with nav_col3:
        if st.button("Contacto", key="nav_contacto", use_container_width=True):
            set_page('contacto')

st.markdown("<hr style='border: 1px solid #ff6b35; margin: 1rem 0;'>", unsafe_allow_html=True)

# Contenido según la página seleccionada
if st.session_state.page == 'inicio':
    # Hero Section
    st.markdown("""
    <div class="hero">
        <h1>Protegiendo tu futuro con confianza</h1>
        <p>Soluciones integrales de seguridad diseñadas para empresas y hogares que valoran la tranquilidad</p>
        <button class="cta-button" onclick="window.scrollTo(0, document.body.scrollHeight);">Conoce nuestros servicios</button>
    </div>
    """, unsafe_allow_html=True)
    
    # Características destacadas
    st.markdown('<h2 class="section-title">¿Por qué elegirnos?</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🛡️</div>
            <div class="service-title">Confiabilidad</div>
            <div class="service-description">
                Tecnología de última generación respaldada por años de experiencia en el sector
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">⚡</div>
            <div class="service-title">Respuesta Rápida</div>
            <div class="service-description">
                Monitoreo 24/7 con tiempos de respuesta inmediatos ante cualquier incidente
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">👥</div>
            <div class="service-title">Atención Personalizada</div>
            <div class="service-description">
                Soluciones adaptadas a las necesidades específicas de cada cliente
            </div>
        </div>
        """, unsafe_allow_html=True)

elif st.session_state.page == 'servicios':
    st.markdown('<h2 class="section-title">Nuestros Servicios</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">📹</div>
            <div class="service-title">Videovigilancia Inteligente</div>
            <div class="service-description">
                Sistemas de cámaras de alta definición con análisis de video en tiempo real y almacenamiento en la nube
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🔐</div>
            <div class="service-title">Control de Acceso</div>
            <div class="service-description">
                Sistemas biométricos y de tarjetas para gestión inteligente de accesos a instalaciones
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🚨</div>
            <div class="service-title">Alarmas Inteligentes</div>
            <div class="service-description">
                Sistemas de alarma conectados con monitoreo remoto y notificaciones instantáneas
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="service-card">
            <div class="service-icon">🏢</div>
            <div class="service-title">Seguridad Corporativa</div>
            <div class="service-description">
                Soluciones integrales para empresas con protocolos personalizados y personal capacitado
            </div>
        </div>
        """, unsafe_allow_html=True)

elif st.session_state.page == 'contacto':
    st.markdown('<h2 class="section-title">Contáctanos</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="contact-section">
            <h3 style="color: white; margin-bottom: 2rem;">Información de Contacto</h3>
            <div class="contact-info">
                <p><strong>📧 Email:</strong> info@unfuturomaseguro.com</p>
                <p><strong>📱 Teléfono:</strong> +57 (2) 123-4567</p>
                <p><strong>📍 Dirección:</strong> Cali, Valle del Cauca, Colombia</p>
                <p><strong>🕐 Horario:</strong> Lunes a Viernes, 8:00 AM - 6:00 PM</p>
                <p style="margin-top: 2rem; color: #ff6b35; font-size: 1.2rem;">
                    <strong>Emergencias 24/7:</strong> +57 300 000-0000
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="contact-section">', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white; margin-bottom: 2rem;">Envíanos un mensaje</h3>', unsafe_allow_html=True)
        
        with st.form("contact_form"):
            nombre = st.text_input("Nombre completo", placeholder="Tu nombre")
            email = st.text_input("Email", placeholder="tucorreo@ejemplo.com")
            telefono = st.text_input("Teléfono", placeholder="+57 300 000-0000")
            mensaje = st.text_area("Mensaje", placeholder="¿En qué podemos ayudarte?", height=150)
            
            submitted = st.form_submit_button("Enviar mensaje", use_container_width=True)
            
            if submitted:
                if nombre and email and mensaje:
                    st.success("✅ Mensaje enviado exitosamente. Nos pondremos en contacto contigo pronto.")
                else:
                    st.error("❌ Por favor completa todos los campos obligatorios.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="footer">
    <p><strong>Un Futuro más Seguro</strong> © 2025 - Todos los derechos reservados</p>
    <p>Protegiendo lo que más valoras</p>
</div>
""", unsafe_allow_html=True)
