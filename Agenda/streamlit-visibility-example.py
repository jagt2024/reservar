import streamlit as st
import pandas as pd
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Ejemplo de visibilidad en Streamlit", layout="wide")

# Inicializar variables en session_state si no existen
if 'mostrar_datos' not in st.session_state:
    st.session_state.mostrar_datos = False
if 'usuario_autenticado' not in st.session_state:
    st.session_state.usuario_autenticado = False
if 'nivel_acceso' not in st.session_state:
    st.session_state.nivel_acceso = "invitado"

# Autenticación básica
def autenticar():
    usuario = st.sidebar.text_input("Usuario")
    contraseña = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Iniciar sesión"):
        if usuario == "admin" and contraseña == "admin123":
            st.session_state.usuario_autenticado = True
            st.session_state.nivel_acceso = "admin"
            return True
        elif usuario == "usuario" and contraseña == "user123":
            st.session_state.usuario_autenticado = True
            st.session_state.nivel_acceso = "usuario"
            return True
        else:
            st.sidebar.error("Credenciales incorrectas")
            return False
    return st.session_state.usuario_autenticado

# Título principal
st.title("Ejemplo de visibilidad en Streamlit")

# Barra lateral para autenticación y controles
with st.sidebar:
    st.header("Panel de control")
    autenticado = autenticar()
    
    if autenticado:
        st.success(f"Conectado como: {st.session_state.nivel_acceso}")
        
        # Controles para mostrar/ocultar información
        st.subheader("Controles de visibilidad")
        mostrar_datos = st.checkbox("Mostrar datos sensibles", value=st.session_state.mostrar_datos)
        st.session_state.mostrar_datos = mostrar_datos
        
        if st.button("Cerrar sesión"):
            st.session_state.usuario_autenticado = False
            st.session_state.nivel_acceso = "invitado"
            st.session_state.mostrar_datos = False
            st.rerun()

# Contenido principal
if not st.session_state.usuario_autenticado:
    st.info("Por favor, inicia sesión para ver el contenido")
else:
    # Contenedor que podemos llenar o vaciar
    contenedor_datos = st.empty()
    
    # Datos ejemplo
    datos = pd.DataFrame({
        'fecha': pd.date_range(start='2023-01-01', periods=10),
        'ventas': np.random.randint(100, 1000, size=10),
        'gastos': np.random.randint(50, 500, size=10)
    })
    
    # Información básica visible para todos los usuarios
    st.subheader("Información general")
    st.write("Esta información es visible para todos los usuarios autenticados.")
    
    # Gráfico básico
    st.line_chart(datos[['ventas', 'gastos']])
    
    # Información que puede mostrarse u ocultarse
    if st.session_state.mostrar_datos:
        with contenedor_datos.container():
            st.subheader("Datos sensibles")
            st.dataframe(datos)
            
            # Información adicional en un expander
            with st.expander("Ver detalles adicionales"):
                st.write("Estos son detalles adicionales que normalmente estarían ocultos.")
                st.bar_chart(datos['ventas'])
    else:
        contenedor_datos.info("Activa 'Mostrar datos sensibles' en el panel de control para ver información adicional.")
    
    # Información exclusiva para administradores
    if st.session_state.nivel_acceso == "admin":
        st.subheader("Panel de administración")
        
        tabs = st.tabs(["Configuración", "Usuarios", "Sistema"])
        
        with tabs[0]:
            st.write("Configuración del sistema")
            mostrar_debug = st.checkbox("Mostrar información de depuración")
            
            if mostrar_debug:
                st.code("""
                # Variables del sistema
                usuario_actual = st.session_state.nivel_acceso
                datos_cargados = True
                version = "1.0.0"
                """)
                
        with tabs[1]:
            st.write("Gestión de usuarios")
            st.dataframe({
                'usuario': ['admin', 'usuario', 'invitado'],
                'nivel': ['Administrador', 'Usuario estándar', 'Visitante'],
                'último_acceso': ['2023-08-15', '2023-08-10', 'Nunca']
            })
            
        with tabs[2]:
            st.write("Información del sistema")
            st.json({
                "estado": "Activo",
                "memoria": "45% utilizada",
                "tiempo_activo": "5 días, 3 horas"
            })
