# user_management.py

import streamlit as st
import sqlite3
import hashlib
import os

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username=? AND role=?", ('admin', 'admin'))
    if not c.fetchone():
        hashed_password = hashlib.sha256('admin'.encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?)", ('admin', hashed_password, 'admin'))
    
    conn.commit()
    conn.close()

def add_user(username, password, role):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (username, hashed_password, role))
    conn.commit()
    conn.close()

def check_credentials(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, hashed_password))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def login():
    st.subheader("Inicio de Sesión")
    with st.form("login_form"):
        username = st.text_input("Nombre de usuario")
        password = st.text_input("Contraseña", type="password")
        submit_button = st.form_submit_button("Iniciar Sesión")

    if submit_button:
        role = check_credentials(username, password)
        if role:
            st.success("Inicio de sesión exitoso")
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['role'] = role
            return True
        
        else:
            st.error("Nombre de usuario o contraseña incorrectos")
    return False

def signup():
    st.subheader("Registro de Usuario")
    if st.session_state.get('role') == 'admin':
        with st.form("signup_form"):
            new_username = st.text_input("Nuevo nombre de usuario")
            new_password = st.text_input("Nueva contraseña", type="password")
            new_role = st.selectbox("Rol", ["user", "admin"])
            submit_button = st.form_submit_button("Registrarse")

        if submit_button:
            if new_username and new_password:
                add_user(new_username, new_password, new_role)
                st.success("Usuario registrado con éxito.")                
                
            else:
                st.error("Por favor, introduzca un nombre de usuario y una contraseña.")
    else:
        st.error("Solo los administradores pueden registrar nuevos usuarios.")

def logout():
    st.session_state['logged_in'] = False
    st.session_state.pop('username', None)
    st.session_state.pop('role', None)

def user_management_system():
    init_db()
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        return login()
    else:
    #    st.write(f"Bienvenido, {st.session_state['username']}!")
    #    if st.button("Cerrar Sesión", key="logout"):
    #        logout()
    #        st.experimental_rerun()
    #    
        if st.session_state.get('role') == 'admin':
            st.markdown("---")
            signup()
        
        return True

# Ejemplo de uso en la aplicación principal:
#if __name__ == "__main__":
#    if user_management_system():
#        st.write("Acceso concedido a la aplicación principal")
        # Aquí iría el código de tu aplicación principal
#    else:
#        st.write("Por favor, inicie sesión para acceder a la aplicación")