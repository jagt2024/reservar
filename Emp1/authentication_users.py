import streamlit as st
import sqlite3
import hashlib

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    # Create admin user if not exists
    c.execute("SELECT * FROM users WHERE username=? AND role=?", ('admin', 'admin'))
    if not c.fetchone():
        hashed_password = hashlib.sha256('admin'.encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?)", ('admin', hashed_password, 'admin'))
    
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

def creds_entered():
    if "user" not in st.session_state:
        st.session_state["user"] = ""
    if "passwd" not in st.session_state:
        st.session_state["passwd"] = ""
    
    if st.session_state["user"].strip() and st.session_state["passwd"].strip():
        role = check_credentials(st.session_state["user"].strip(), st.session_state["passwd"].strip())
        if role:
            st.session_state["authenticated"] = True
            st.session_state["role"] = role
        else:
            st.session_state["authenticated"] = False
            st.error("Usuario/Contraseña inválidos :face_with_raised_eyebrow:")
    else:
        st.session_state["authenticated"] = False
        if not st.session_state["passwd"]:
            st.warning("Por favor ingrese la contraseña.")
        elif not st.session_state["user"]:
            st.warning("Por favor ingrese el usuario.")

def authenticate_user():
    init_db()  # Ensure the database is initialized
    
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    if not st.session_state["authenticated"]:
        login_container = st.empty()
        
        with login_container.container():
            
            st.write("Por favor, inicie sesión para acceder a la aplicación")
            st.warning('***AUTENTICACION***')
            
            with st.form("login_form"):
                st.text_input(label="Usuario:", value="", key="user")
                st.text_input(label="Contraseña:", value="", key="passwd", type="password")
                submit_button = st.form_submit_button("Iniciar Sesión")
        
            if submit_button:
                creds_entered()
                if st.session_state["authenticated"]:
                    st.success(f"Inicio de sesión exitoso. Bienvenido, {st.session_state['user']}!")
                    
                    #for key in ['authenticated', 'user', 'passwd', 'role']:
                    #    del st.session_state[key]
                    #login_container.empty()
    #else:
    #    if st.sidebar.button("Cerrar Sesión"):
    #        for key in ['authenticated', 'user', 'passwd', 'role']:
    #            if key in st.session_state:
    #                del st.session_state[key]
    #        st.rerun()
    
    return st.session_state.get("authenticated", False)

def create_user(username, password, role):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hashed_password, role))
        conn.commit()
        st.success(f"Usuario '{username}' creado exitosamente con rol '{role}'.")
    except sqlite3.IntegrityError:
        st.error(f"El usuario '{username}' ya existe.")
    finally:
        conn.close()

# Ejemplo de uso para crear un nuevo usuario (solo accesible para administradores)
def admin_panel():
    if st.session_state.get("authenticated", False) and st.session_state.get("role") == "admin":
        st.subheader("Crear Nuevo Usuario")
        with st.form("create_user_form"):
            new_username = st.text_input("Nuevo usuario:")
            new_password = st.text_input("Nueva contraseña:", type="password")
            new_role = st.selectbox("Rol:", ["user", "admin"])
            submit_button = st.form_submit_button("Crear Usuario")
        
        if submit_button:
            if new_username and new_password:
                create_user(new_username, new_password, new_role)
            else:
                st.error("Por favor, ingrese un nombre de usuario y una contraseña.")

#if __name__ == "__main__":
#    if authenticate_user():
#        admin_panel()