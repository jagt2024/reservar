import streamlit as st
from streamlit_option_menu import option_menu

def main():
    # Configuración de la página
    st.set_page_config(page_title="MiApp", layout="wide")

    # Estilos CSS personalizados
    st.markdown("""
        <style>
        .stApp {
            background-color: #f9fafb;
        }
        .main-header {
            background-color: white;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            margin: -1rem -1rem 1rem -1rem;
        }
        .search-container {
            background-color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        .card {
            background-color: white;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Barra de navegación superior
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,4,1])
    with col1:
        st.markdown("🔍")
    with col2:
        st.markdown("<h1 style='text-align: center; color: #2563eb; font-size: 1.5rem;'>MiApp</h1>", unsafe_allow_html=True)
    with col3:
        st.markdown("👤")
    st.markdown('</div>', unsafe_allow_html=True)

    # Menú lateral
    with st.sidebar:
        selected = option_menu(
            "Menú Principal",
            ["Dashboard", "Proyectos", "Tareas", "Configuración"],
            icons=['house', 'list-task', 'check2-square', 'gear'],
            menu_icon="cast",
            default_index=0,
        )

    # Contenido principal
    # Barra de búsqueda
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    st.text_input("", placeholder="Buscar...", key="search")
    st.markdown('</div>', unsafe_allow_html=True)

    # Formulario de nuevo proyecto
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Nuevo Proyecto")
    with st.form("nuevo_proyecto"):
        nombre_proyecto = st.text_input("Nombre del Proyecto")
        descripcion = st.text_area("Descripción")
        submitted = st.form_submit_button("Crear Proyecto", 
            type="primary",
            use_container_width=True)
        if submitted:
            st.success("Proyecto creado exitosamente!")
    st.markdown('</div>', unsafe_allow_html=True)

    # Lista de proyectos recientes
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Proyectos Recientes")
    for i in range(1, 4):
        col1, col2 = st.columns([3,1])
        with col1:
            st.markdown(f"### Proyecto {i}")
            st.caption("Última actualización: hace 2 días")
        with col2:
            st.button("Ver detalles", key=f"ver_detalles_{i}", 
                     use_container_width=True)
        st.divider()
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
