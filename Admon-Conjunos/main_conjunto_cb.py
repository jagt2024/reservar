import streamlit as st
from streamlit_option_menu import option_menu
from inicio_conjuntos import InicioConjunto
#from email_sender import mostrar_correo_masivo
from condominio_system import condominio_main
from cartera_morosa_conjunto import cartera_morosa_main
from pagos_conjunto import pago_main
from consulta_financiera import consulta_main
from consulta_financiera_residente import consulta_res_main
from generador_cuentas_cobro import generador_main
from pqrs_conjunto import pqrs_main
from manejo_presupuesto import presupuesto_main
from correspondencia_conjunto import correspondencia_main
from mantenimiento_conjunto import mantenimiento_main
from control_mascotas_vehiculos import mascove_main
from control_censo_poblacional import censo_main
from administracion_parqueaderos import parqueadero_main
#from user_management import user_management_system
from PIL import Image
from datetime import date
import datetime
import time
import pytz
import toml
import logging
import sys

# Configurar la página y ocultar la opción "Manage app" del menú
st.set_page_config(
    page_title="SADCO",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Ocultar elementos de la interfaz de Streamlit usando CSS personalizado
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            .css-1rs6os {visibility: hidden;}
            .css-14xtw13 {visibility: hidden;}
            .css-1avcm0n {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, filename='main_conjunto.log', filemode='w', 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def global_exception_handler(exc_type, exc_value, exc_traceback):
    st.error(f"Error no manejado: {exc_type.__name__}: {exc_value}")
    logging.error("Error no manejado", exc_info=(exc_type, exc_value, exc_traceback))

def clear_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# Cargar configuraciones desde config.toml con manejo de errores
try:
    with open("./.streamlit/config.toml", "r") as f:
        config = toml.load(f)
except FileNotFoundError:
    # Configuración por defecto si no existe el archivo
    config = {
        'fonts': {
            'clock_font': 'Arial',
            'calendar_font': 'Arial'
        },
        'font_sizes': {
            'clock_font_size': '24px',
            'calendar_font_size': '18px'
        },
        'colors': {
            'clock_color': '#000000',
            'calendar_color': '#000000'
        },
        'layout': {
            'top_margin': '10px',
            'bottom_margin': '10px'
        }
    }
    st.warning("Archivo config.toml no encontrado. Usando configuración por defecto.")

sys.excepthook = global_exception_handler

# Cargar logo con manejo de errores
try:
    logo = Image.open("./assets-conjuntos/logoCeiba.png")
except FileNotFoundError:
    logo = None
    st.warning("Logo no encontrado en ./assets-conjuntos/logoCeiba.png")

# Diccionario de traducciones
translations = {
    "en": {
        "language_selector": "🌐 Language / Idioma",
        "app_title": "Administracion Conjuntos",
        "option0": "Inicio",
        "option1": "Sistema de Administracion",
        "option2": "Gestion Cartera Morosa",
        "option3": "Consulta Financiera",
        "option4": "Generador Cuentas Cobro",
        "option5": "Registro de Pagos",
        "option6": "Manejo Presupueso ",
        "option7": "Peticiones, Quejas, Reclamos(pqrs)",
        "option8": "Gestion Correspondencia",
        "option9": "Generar Mantenimiento",
        "version": "Version: 0.0.1",
        "year": "A#o 2025",
        "sistema":"SADCO",
        "error_message": "An error occurred: {}",
        "system_error": "A system error occurred: {}"
    },
    "es": {
        "language_selector": "🌐 Language / Idioma",
        "app_title": "Administracion Conjuntos",
        "option0": "Inicio",
        "option1": "Sistema de Administracion",
        "option2": "Gestion Cartera Morosos",
        "option3": "Consulta Financiera",
        "option4": "Generador Cuentas Cobro",
        "option5": "Registro de Pagos",
        "option6": "Manejo Presupueso ",
        "option7": "Peticiones, Quejas, Reclamos(pqrs)",
        "option8": "Gestion Correspondencia",
        "option9": "Generar Mantenimiento",
        "version": "Versión: 0.0.1",
        "year": "A#o 2025",
        "sistema":"SADCO",
        "error_message": "Ocurrió un error: {}",
        "system_error": "Ha ocurrido un error en main_emp.py: {}"
    }
}

# Inicializar el estado de sesión si no existe
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'InicioConjunto'
    
if 'language' not in st.session_state:
    st.session_state.language = 'en'

class Model:
    
    def __init__(self, language="en"):
        self.language = language
        self.update_translations()
        
    def update_translations(self):
        lang = translations[self.language]
        self.menuTitle = lang["app_title"]
        self.option0 = lang["option0"]
        self.option1 = lang["option1"]
        self.option2 = lang["option2"]
        self.option3 = lang["option3"]
        self.option4 = lang["option4"]
        self.option5 = lang["option5"]
        self.option6 = lang["option6"]
        self.option7 = lang["option7"]
        self.option8 = lang["option8"]
        self.option9 = lang["option9"]

# Función para cambiar entre páginas
def cambiar_pagina(page_name):
    st.session_state.current_page = page_name
    st.rerun()

def view(model):
    try:
        current_page = st.session_state.current_page
        
        # SIDEBAR PRINCIPAL - Solo se muestra en la página de inicio
        if current_page == 'InicioConjunto':
            with st.sidebar:
                # Selector de idioma en la parte superior del sidebar
                languages = {"English": "en", "Español": "es"}
                selected_language_name = st.selectbox(
                    translations[model.language]["language_selector"],
                    options=list(languages.keys())
                )
                selected_language = languages[selected_language_name]
                
                # Actualizar idioma si cambia
                if selected_language != model.language:
                    model.language = selected_language
                    st.session_state.language = selected_language
                    model.update_translations()

                # Menú principal
                app = option_menu(model.menuTitle,
                            [model.option0, model.option1, model.option2, model.option3, model.option4, model.option5, model.option8, model.option6, model.option7,model.option9],
                            icons=['house', 'gear', 'credit-card', 'search', 'file-earmark-text'],
                            default_index=0,
                            styles={
                               "container": {"padding": "5!important",
                               "background-color": '#acbee9'},
                               "icon": {"color": "white", "font-size": "23px"},
                               "nav-link": {"color": "white", "font-size": "20px", "text-align": "left", "margin": "0px"},
                               "nav-link-selected": {"background-color": "#02ab21"},
                            })

                # Footer del sidebar
                st.markdown("---")
                st.text(translations[model.language]["version"])
                st.text(translations[model.language]["year"])
                st.text(translations[model.language]["sistema"])
                st.markdown("---")

                # Actualizar la página según la selección del menú
                if app == model.option1:
                    cambiar_pagina('condominio_main')
                elif app == model.option2:
                    cambiar_pagina('cartera_morosa_main')
                elif app == model.option3:
                    cambiar_pagina('consulta_main')
                elif app == model.option4:
                    cambiar_pagina('generador_main')
                elif app == model.option5:
                    cambiar_pagina('pago_main')
                elif app == model.option8:
                    cambiar_pagina('correspondencia_main') 
                elif app == model.option6:
                    cambiar_pagina('presupuesto_main')
                elif app == model.option7:
                    cambiar_pagina('pqrs_main')
                elif app == model.option9:
                    cambiar_pagina('mantenimiento_main')

        # SIDEBARS ESPECÍFICOS PARA CADA PÁGINA
        elif current_page == 'condominio_main':
            with st.sidebar:
                st.header("🏢 Administración")
                if st.button("🏠 Volver al Inicio", key="btn_back_conjunto"):
                    cambiar_pagina('InicioConjunto')
                st.divider()
                
                # Aquí puedes agregar opciones específicas de administración
                #st.subheader("Opciones:")
                #st.write("• Gestión de propietarios")
                #st.write("• Configuración del sistema")
                #st.write("• Reportes administrativos")
                               
        elif current_page == 'cartera_morosa_main':
            with st.sidebar:
                #st.header("💳 Cartera Morosa")
                if st.button("🏠 Volver al Inicio", key="btn_back_cm"):
                    cambiar_pagina('InicioConjunto')
                st.divider()
                
                # Opciones específicas de cartera morosa
                #st.subheader("Opciones:")
                #st.write("• Consultar morosos")
                #st.write("• Generar reportes")
                #st.write("• Enviar notificaciones")
                
        elif current_page == 'consulta_main':
            with st.sidebar:
                #st.header("🔍 Consulta Financiera")
                if st.button("🏠 Volver al Inicio", key="btn_back_cf"):
                    cambiar_pagina('InicioConjunto')
                st.divider()
                
                # Opciones específicas de consulta financiera
                #st.subheader("Opciones:")
                #st.write("• Estados de cuenta")
                #st.write("• Historial de pagos")
                #st.write("• Balances generales")
                
        elif current_page == 'generador_main':
            with st.sidebar:
                #st.header("📄 Generador Cuentas")
                if st.button("🏠 Volver al Inicio", key="btn_back_ca"):
                    cambiar_pagina('InicioConjunto')
                st.divider()
                
                # Opciones específicas del generador
                #st.subheader("Opciones:")
                #st.write("• Crear cuentas de cobro")
                #st.write("• Personalizar formatos")
                #st.write("• Envío masivo")

        elif current_page == 'pago_main':
            with st.sidebar:
                
                if st.button("🏠 Volver al Inicio", key="btn_back_pa"):
                    cambiar_pagina('InicioConjunto')
                st.divider()

        elif current_page == 'correspondencia_main':
            with st.sidebar:
                
                if st.button("🏠 Volver al Inicio", key="btn_back_pa"):
                    cambiar_pagina('InicioConjunto')
                st.divider()

        elif current_page == 'presupuesto_main':
            with st.sidebar:
                
                if st.button("🏠 Volver al Inicio", key="btn_back_pa"):
                    cambiar_pagina('InicioConjunto')
                st.divider()

        elif current_page == 'pqrs_main':
            with st.sidebar:
                
                if st.button("🏠 Volver al Inicio", key="btn_back_pa"):
                    cambiar_pagina('InicioConjunto')
                st.divider()

        elif current_page == 'mantenimiento_main':
            with st.sidebar:
                
                if st.button("🏠 Volver al Inicio", key="btn_back_pa"):
                    cambiar_pagina('InicioConjunto')
                st.divider()
        
        # CONTENIDO PRINCIPAL
        # Renderizar la página actual según session_state
        if current_page == 'InicioConjunto':
        # Encabezado principal
                
            st.markdown("""
                <div style='text-align: center;'>
                    <h1 style='color: #2E86AB; margin: 20px 0;'>
                        *** CONDOMINIO   L A   C E I B A ***
                    </h1>
                    <h3 style='color: #666; margin: 10px 0; line-height: 1.4;'>
                        Propiedad Horizontal P.J. No. 900002935-5<br>
                        Ricaurte – Cundinamarca Vereda Limoncitos
                    </h3>
                </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <style>
                    @import url('https://fonts.googleapis.com/css2?family={config['fonts']['clock_font']}:wght@400;500&display=swap');
                    .clock {{
                    font-family: '{config['fonts']['clock_font']}', sans-serif;
                    font-size: {config['font_sizes']['clock_font_size']};
                    color: {config['colors']['clock_color']};
                    text-shadow: 0 0 10px rgba(255,255,0,0.7);
                    margin-top: {config['layout']['top_margin']};
                    margin-bottom: {config['layout']['bottom_margin']};
                    }}
                    .calendar {{
                    font-family: '{config['fonts']['calendar_font']}', sans-serif;
                    font-size: {config['font_sizes']['calendar_font_size']};
                    color: {config['colors']['calendar_color']};
                    margin-top: {config['layout']['top_margin']};
                    margin-bottom: {config['layout']['bottom_margin']};
                    }}
            </style>
            """, unsafe_allow_html=True)

            # Crear columnas para el diseño
            col1, col2, col3 = st.columns(3)

            # Columna 1: Reloj Digital
            with col1:
                pass
                #clock_placeholder = st.empty()
                # Actualizar reloj
                #now = datetime.datetime.now(pytz.timezone('America/Bogota'))
                #clock_placeholder.markdown(f'<p class="clock">Hora: {now.strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)
                             
            with col2:
                if logo:
                    st.image(logo, width=200)
        
            # Columna 3: Calendario y botón limpiar
            with col3:
                calendar_placeholder = st.empty()
                # Actualizar calendario
                today = date.today()
                meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                mes_es = meses_es[today.month - 1]
                dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                dia_es = dias_es[today.weekday()]
                calendar_placeholder.markdown(f'<p class="calendar">Día: {dia_es.capitalize()} {today.day} de {mes_es} de {today.year}<br></p>', unsafe_allow_html=True)
                
                with st.form(key='myform4', clear_on_submit=True):
                    limpiar = st.form_submit_button("Limpiar Pantalla")
                    if limpiar:
                        clear_session_state()
                        st.rerun()

            st.markdown("""
            <style>
                .stTabs [data-baseweb="tab-list"] {
                    gap: 24px;
                }   
    
                .stTabs [data-baseweb="tab"] {
                    height: 50px;
                    padding-left: 20px;
                    padding-right: 20px;
                    background-color: #f0f2f6;
                    border-radius: 4px 4px 0px 0px;
                    color: #262730;
                    font-size: 20px;
                    font-weight: 500;
                }
    
                .stTabs [aria-selected="true"] {
                    background-color: #ff6b6b;
                    color: white;
                }
            </style>
            """, unsafe_allow_html=True)


            # Tabs principales con control de estado
            tab1, tab2 = st.tabs(["🏠 Inicio", "💰 Consulta Financiera"])#, "💳 Registrar Pago", "📞 Soporte - PQRS"])

            with tab1:
                st.subheader("🏠 Bienvenido al Sistema *SADCO* ")
    
                st.write("""
                ### Sistema de Administración de Conjuntos - Condominios
    
                Bienvenido al sistema de administración del Condominio La Ceiba.
    
                **Funcionalidades disponibles:**
                - Consulta financiera de propietarios
                - Registro de pagos
                - Gestión administrativa
                - Soporte y PQRS
    
                Utilice las opciones de la barra izquierda o superiores para navegar por las diferentes secciones.
                """)

            with tab2:
                #st.subheader("💰 Consulta Financiera - Residentes")
                try:
                    # Verificar si la función existe antes de llamarla
                    if 'consulta_res_main' in globals():
                        consulta_res_main()
                    else:
                        st.error("La función consulta_res_main no está disponible")
                        st.info("Verifique que el módulo consulta_financiera_residente esté correctamente importado")
                except Exception as e:
                        st.error(f"Error al cargar consulta financiera: {e}")
                        st.info("Por favor, contacte al administrador del sistema.")

            #with tab3:
                
                #st.subheader("💳 Registro de Pagos")
                #try:
                    # Verificar si la función existe
                #    if 'pago_main' in globals():
                #        st.write("✅ Función pago_main encontrada, ejecutando...")
                #        pago_main()
                #    else:
                #        st.warning("⚠️ La función pago_main no está disponible")
                #        st.info("Verifique que el módulo pagos_conjunto esté correctamente importado")
                #except Exception as e:
                #    st.error(f"Error al cargar sistema de pagos: {e}")
                #    st.info("El sistema de pagos no está disponible temporalmente.")
        
            #with tab4:
                #st.subheader("📞 Soporte - PQRS")
                #st.write("### Sistema de Peticiones, Quejas, Reclamos y Sugerencias")
            
        elif current_page == 'condominio_main':
            #st.header("🏢 Sistema de Administración")
            try:
                condominio_main()
            except Exception as e:
                st.error(f"Error al cargar condominio_main: {e}")
            
        elif current_page == 'cartera_morosa_main':
            st.header("💳 Gestión Cartera Morosa")
            try:
                cartera_morosa_main()
            except Exception as e:
                st.error(f"Error al cargar cartera_morosa_main: {e}")
                
        elif current_page == 'consulta_main':
            #st.header("🔍 Consulta Financiera")
            try:
                consulta_main()
            except Exception as e:
                st.error(f"Error al cargar consulta_main: {e}")

        elif current_page == 'generador_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                generador_main()
            except Exception as e:
                st.error(f"Error al cargar generador_main: {e}")

        elif current_page == 'pago_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                pago_main()
            except Exception as e:
                st.error(f"Error al cargar pago_main: {e}")

        elif current_page == 'correspondencia_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                correspondencia_main()
            except Exception as e:
                st.error(f"Error al cargar pago_main: {e}")

        elif current_page == 'presupuesto_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                presupuesto_main()
            except Exception as e:
                st.error(f"Error al cargar generador_main: {e}")

        elif current_page == 'pqrs_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                pqrs_main()
            except Exception as e:
                st.error(f"Error al cargar generador_main: {e}")

        elif current_page == 'mantenimiento_main':
            #st.header("📄 Generador Cuentas de Cobro")
            try:
                mantenimiento_main()
            except Exception as e:
                st.error(f"Error al cargar pago_main: {e}")
        
        #st.markdown("---")
        #st.text(translations[model.language]["version"])
        #st.text(translations[model.language]["year"])
        #st.text(translations[model.language]["sistema"])

    except Exception as e:
        error_msg = translations[model.language]["error_message"].format(e)
        st.error(error_msg)
        logging.error(f"Error en la vista: {e}", exc_info=True)

# Inicializar modelo con el idioma almacenado en session_state o el valor predeterminado
model = Model(language=st.session_state.language)
view(model)