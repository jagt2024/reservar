import streamlit as st

def main():
    st.title("Mi Aplicación Principal")

    # Crear el menú principal en la barra lateral
    menu = st.sidebar.selectbox(
        "Menú Principal",
        ["Inicio", "Datos", "Análisis", "Configuración"]
    )

    # Crear submenú para la opción "Datos"
    if menu == "Datos":
        with st.sidebar.expander("Submenú de Datos"):
            submenu = st.radio(
                "Opciones",
                ["Cargar Datos", "Ver Datos", "Exportar Datos"]
            )
        
        if submenu == "Cargar Datos":
            st.write("Aquí puedes implementar la funcionalidad para cargar datos")
        elif submenu == "Ver Datos":
            st.write("Aquí puedes mostrar los datos cargados")
        elif submenu == "Exportar Datos":
            st.write("Aquí puedes implementar la funcionalidad para exportar datos")

    # Implementar otras opciones del menú principal
    elif menu == "Inicio":
        st.write("Bienvenido a la página de inicio")
    elif menu == "Análisis":
        st.write("Aquí puedes realizar análisis de datos")
    elif menu == "Configuración":
        st.write("Configura tu aplicación aquí")

if __name__ == "__main__":
    main()