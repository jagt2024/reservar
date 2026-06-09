# modulo_seguridad.py — SolarCalc Pro · Módulo de Seguridad y Control de Acceso
# ═══════════════════════════════════════════════════════════════════════════════
"""
Gestión completa de usuarios, roles y permisos para SolarCalc Pro.

Roles disponibles:
  • superadmin  — acceso total + gestión de usuarios
  • admin       — acceso total a proyectos y módulos
  • ingeniero   — dimensionamiento, simulador y planos
  • visualizador— solo lectura (sin guardar ni exportar)

Tablas creadas:
  usuarios  — id, username, nombre_completo, email, password_hash, rol, activo, creado
  sesiones  — id, usuario_id, token, creado, expira
  auditoria — id, usuario_id, accion, detalle, ip, fecha
"""

import streamlit as st
import sqlite3
import hashlib
import secrets
import os
import pathlib
import tempfile
import re
import pandas as pd
from datetime import datetime, timedelta

# ─── Constantes de roles y permisos ──────────────────────────────────────────
ROLES = {
    "superadmin": {
        "label":   "Super Administrador",
        "color":   "#FF5252",
        "icon":    "👑",
        "permisos": [
            "ver_proyectos", "crear_proyectos", "editar_proyectos", "eliminar_proyectos",
            "dimensionamiento", "simulador", "planos", "presupuesto",
            "exportar_pdf", "exportar_excel",
            "ver_usuarios", "crear_usuarios", "editar_usuarios", "eliminar_usuarios",
            "ver_auditoria", "gestion_sistema",
        ],
    },
    "admin": {
        "label":   "Administrador",
        "color":   "#FF6B35",
        "icon":    "🔧",
        "permisos": [
            "ver_proyectos", "crear_proyectos", "editar_proyectos", "eliminar_proyectos",
            "dimensionamiento", "simulador", "planos", "presupuesto",
            "exportar_pdf", "exportar_excel",
            "ver_usuarios", "crear_usuarios", "editar_usuarios",
            "ver_auditoria",
        ],
    },
    "ingeniero": {
        "label":   "Ingeniero",
        "color":   "#00BCD4",
        "icon":    "⚡",
        "permisos": [
            "ver_proyectos", "crear_proyectos", "editar_proyectos",
            "dimensionamiento", "simulador", "planos", "presupuesto",
            "exportar_pdf", "exportar_excel",
        ],
    },
    "visualizador": {
        "label":   "Visualizador",
        "color":   "#8A9BBD",
        "icon":    "👁",
        "permisos": [
            "ver_proyectos", "dimensionamiento",
        ],
    },
}

PERMISOS_LABELS = {
    "ver_proyectos":      "Ver proyectos",
    "crear_proyectos":    "Crear proyectos",
    "editar_proyectos":   "Editar proyectos",
    "eliminar_proyectos": "Eliminar proyectos",
    "dimensionamiento":   "Dimensionamiento",
    "simulador":          "Simulador",
    "planos":             "Ver planos",
    "presupuesto":        "Presupuesto",
    "exportar_pdf":       "Exportar PDF",
    "exportar_excel":     "Exportar Excel",
    "ver_usuarios":       "Ver usuarios",
    "crear_usuarios":     "Crear usuarios",
    "editar_usuarios":    "Editar usuarios",
    "eliminar_usuarios":  "Eliminar usuarios",
    "ver_auditoria":      "Ver auditoría",
    "gestion_sistema":    "Gestión del sistema",
}

# ─── DB path ─────────────────────────────────────────────────────────────────
def _db_path() -> str:
    env = os.environ.get("SOLARCALC_DB_PATH")
    if env: return env
    script_dir = pathlib.Path(__file__).parent.resolve()
    try:
        t = script_dir / ".wt"; t.touch(); t.unlink()
        return str(script_dir / "solar_calc.db")
    except Exception:
        return str(pathlib.Path(tempfile.gettempdir()) / "solar_calc.db")

DB_PATH = _db_path()

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN DE TABLAS
# ═══════════════════════════════════════════════════════════════════════════════
def init_seguridad_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            username         TEXT    NOT NULL UNIQUE,
            nombre_completo  TEXT    NOT NULL,
            email            TEXT    NOT NULL UNIQUE,
            password_hash    TEXT    NOT NULL,
            rol              TEXT    NOT NULL DEFAULT 'visualizador',
            activo           INTEGER NOT NULL DEFAULT 1,
            creado           TEXT    DEFAULT (datetime('now')),
            ultimo_acceso    TEXT,
            creado_por       INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER NOT NULL,
            token       TEXT    NOT NULL UNIQUE,
            creado      TEXT    DEFAULT (datetime('now')),
            expira      TEXT    NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER,
            username    TEXT,
            accion      TEXT    NOT NULL,
            detalle     TEXT,
            modulo      TEXT,
            fecha       TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Crear superadmin por defecto si no existe ningún usuario
    existing = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if existing == 0:
        pwd_hash = _hash_password("Admin2024!")
        c.execute("""
            INSERT INTO usuarios (username, nombre_completo, email, password_hash, rol)
            VALUES (?, ?, ?, ?, ?)
        """, ("admin", "Administrador SolarCalc", "admin@solarcalc.com", pwd_hash, "superadmin"))

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════════════════════
def _hash_password(password: str) -> str:
    """SHA-256 con sal fija de la app."""
    salt = "SolarCalcPro_2024_#SEC"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def _generar_token() -> str:
    return secrets.token_hex(32)

def _validar_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email))

def _validar_password(pwd: str) -> tuple:
    if len(pwd) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", pwd):
        return False, "Debe tener al menos una mayúscula"
    if not re.search(r"[0-9]", pwd):
        return False, "Debe tener al menos un número"
    return True, "OK"

def registrar_auditoria(usuario_id: int, username: str, accion: str,
                         detalle: str = "", modulo: str = ""):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO auditoria(usuario_id,username,accion,detalle,modulo) VALUES(?,?,?,?,?)",
            (usuario_id, username, accion, detalle, modulo))
        conn.commit()
        conn.close()
    except Exception:
        pass

def tiene_permiso(permiso: str) -> bool:
    """Verifica si el usuario en sesión tiene un permiso específico."""
    usuario = st.session_state.get("usuario_sesion")
    if not usuario:
        return False
    rol = usuario.get("rol", "visualizador")
    return permiso in ROLES.get(rol, {}).get("permisos", [])

def usuario_activo() -> object:
    """Retorna el dict del usuario en sesión o None."""
    return st.session_state.get("usuario_sesion")

def es_superadmin() -> bool:
    u = usuario_activo()
    return u is not None and u.get("rol") == "superadmin"


# ═══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
def _login(username: str, password: str) -> tuple:
    """Intenta autenticar. Retorna (éxito, mensaje)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, nombre_completo, email, password_hash, rol, activo "
        "FROM usuarios WHERE username=? OR email=?",
        (username.strip(), username.strip())).fetchone()
    conn.close()

    if not row:
        return False, "Usuario no encontrado"
    if not row[6]:
        return False, "Cuenta desactivada. Contacta al administrador"
    if row[4] != _hash_password(password):
        return False, "Contraseña incorrecta"

    # Sesión exitosa
    token = _generar_token()
    expira = (datetime.now() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("INSERT INTO sesiones(usuario_id,token,expira) VALUES(?,?,?)",
                 (row[0], token, expira))
    conn.execute("UPDATE usuarios SET ultimo_acceso=? WHERE id=?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row[0]))
    conn.commit()
    conn.close()

    st.session_state["usuario_sesion"] = {
        "id": row[0], "username": row[1], "nombre": row[2],
        "email": row[3], "rol": row[5], "token": token,
    }
    registrar_auditoria(row[0], row[1], "LOGIN", "Inicio de sesión exitoso", "seguridad")
    return True, "OK"

def _logout():
    u = usuario_activo()
    if u:
        registrar_auditoria(u["id"], u["username"], "LOGOUT", "Cierre de sesión", "seguridad")
        conn = get_conn()
        conn.execute("DELETE FROM sesiones WHERE token=?", (u.get("token",""),))
        conn.commit()
        conn.close()
    for k in ["usuario_sesion", "tipo_sistema", "modulo_activo"]:
        st.session_state.pop(k, None)


# ═══════════════════════════════════════════════════════════════════════════════
# PANTALLA DE LOGIN
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_login():
    """Renderiza la pantalla de login. Llama st.stop() hasta que el usuario inicie sesión."""
    st.markdown("""
    <style>
    .login-wrap{display:flex;flex-direction:column;align-items:center;
     justify-content:center;min-height:80vh;padding:2rem;}
    .login-card{background:#0F1525;border:1px solid #2A3A55;border-radius:16px;
     padding:2.5rem 3rem;max-width:420px;width:100%;}
    .login-logo{text-align:center;margin-bottom:1.5rem;}
    .login-logo .brand{font-family:Rajdhani,sans-serif;font-size:2.6rem;
     font-weight:700;color:#FFB300;letter-spacing:3px;line-height:1;}
    .login-logo .sub{font-size:0.65rem;color:#8A9BBD;letter-spacing:4px;margin-top:0.3rem;}
    .login-divider{border:none;border-top:1px solid #2A3A55;margin:1.2rem 0;}
    </style>
    """, unsafe_allow_html=True)

    # Centrar con columnas
    _, col_c, _ = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("""
        <div class='login-logo'>
            <div class='brand'>☀ SOLAR<br>CALC</div>
            <div class='sub'>DIMENSIONAMIENTO FOTOVOLTAICO</div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("""
            <div style='background:#0F1525;border:1px solid #2A3A55;border-radius:16px;
             padding:2rem;margin-top:1rem;'>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style='text-align:center;margin-bottom:1.2rem;'>
                <span style='font-family:Rajdhani,sans-serif;font-size:1.1rem;
                 color:#FFB300;font-weight:600;letter-spacing:2px;'>
                    🔐 INICIAR SESIÓN
                </span>
            </div>
            """, unsafe_allow_html=True)

            username = st.text_input("Usuario o correo electrónico",
                                     placeholder="usuario@empresa.com",
                                     key="login_user")
            password = st.text_input("Contraseña", type="password",
                                     placeholder="••••••••",
                                     key="login_pass")

            if st.button("Ingresar →", use_container_width=True, type="primary",
                         key="login_btn"):
                if not username or not password:
                    st.error("Ingresa usuario y contraseña")
                else:
                    ok, msg = _login(username, password)
                    if ok:
                        st.success("✓ Acceso concedido")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

            st.markdown("""
            <div style='text-align:center;margin-top:1.2rem;font-size:0.75rem;
             color:#2A3A55;letter-spacing:1px;'>
                SolarCalc Pro · Acceso restringido<br>
                Contacta al administrador para obtener acceso
            </div>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — INFO DE USUARIO ACTIVO
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_usuario_sidebar():
    """Renderiza el bloque de usuario en el sidebar."""
    u = usuario_activo()
    if not u:
        return
    rol_info = ROLES.get(u["rol"], ROLES["visualizador"])
    st.markdown(f"""
    <div style='background:#1A2235;border:1px solid #2A3A55;border-radius:10px;
     padding:0.7rem 0.9rem;margin-bottom:0.5rem;'>
        <div style='font-family:Rajdhani,sans-serif;font-size:0.95rem;
         color:#E8EDF5;font-weight:600;'>{rol_info["icon"]} {u["nombre"]}</div>
        <div style='font-size:0.7rem;color:#8A9BBD;margin-top:0.2rem;'>
            @{u["username"]}
        </div>
        <div style='margin-top:0.4rem;'>
            <span style='background:{rol_info["color"]}22;color:{rol_info["color"]};
             font-family:Rajdhani,sans-serif;font-weight:700;font-size:0.65rem;
             padding:2px 8px;border-radius:12px;letter-spacing:1px;border:1px solid {rol_info["color"]}44;'>
                {rol_info["label"].upper()}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Cerrar sesión", use_container_width=True, key="btn_logout"):
        _logout()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE GESTIÓN DE USUARIOS (solo admin/superadmin)
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_gestion_usuarios():
    """Panel completo de administración de usuarios."""
    u = usuario_activo()
    if not tiene_permiso("ver_usuarios"):
        st.error("🔒 No tienes permiso para acceder a esta sección.")
        return

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>🔐 GESTIÓN DE USUARIOS</div>
        <div class='hero-sub'>ADMINISTRACIÓN DE ACCESO · ROLES · PERMISOS</div>
    </div>
    """, unsafe_allow_html=True)

    tab_lista, tab_nuevo, tab_auditoria = st.tabs([
        "👥 Usuarios", "➕ Nuevo usuario", "📋 Auditoría"
    ])

    # ── TAB: Lista de usuarios ────────────────────────────────────────────────
    with tab_lista:
        conn = get_conn()
        usuarios_df = pd.read_sql(
            "SELECT id, username, nombre_completo, email, rol, activo, creado, ultimo_acceso "
            "FROM usuarios ORDER BY creado DESC", conn)
        conn.close()

        st.markdown(f"""
        <div style='display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;'>
            <div style='background:#1A2235;border-radius:8px;padding:0.6rem 1.2rem;text-align:center;'>
                <div style='font-family:Share Tech Mono;font-size:1.4rem;color:#FFB300;'>{len(usuarios_df)}</div>
                <div style='font-size:0.72rem;color:#8A9BBD;'>Usuarios totales</div>
            </div>
            <div style='background:#1A2235;border-radius:8px;padding:0.6rem 1.2rem;text-align:center;'>
                <div style='font-family:Share Tech Mono;font-size:1.4rem;color:#00E676;'>{usuarios_df["activo"].sum()}</div>
                <div style='font-size:0.72rem;color:#8A9BBD;'>Activos</div>
            </div>
            <div style='background:#1A2235;border-radius:8px;padding:0.6rem 1.2rem;text-align:center;'>
                <div style='font-family:Share Tech Mono;font-size:1.4rem;color:#FF5252;'>{(~usuarios_df["activo"].astype(bool)).sum()}</div>
                <div style='font-size:0.72rem;color:#8A9BBD;'>Inactivos</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        for _, row in usuarios_df.iterrows():
            rol_i  = ROLES.get(row["rol"], ROLES["visualizador"])
            activo = bool(row["activo"])
            with st.expander(
                f"{rol_i['icon']} {row['nombre_completo']} — @{row['username']} "
                f"{'✅' if activo else '🔴'}",
                expanded=False):

                col1, col2, col3 = st.columns([1.5, 1.5, 1])
                with col1:
                    st.markdown(f"""
                    <table style='font-size:0.82rem;width:100%;border-collapse:collapse;'>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>ID</td>
                            <td style='font-family:Share Tech Mono;color:#FFD54F;'>#{row['id']}</td></tr>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>Usuario</td>
                            <td style='color:#E8EDF5;'>@{row['username']}</td></tr>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>Correo</td>
                            <td style='color:#E8EDF5;'>{row['email']}</td></tr>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>Rol</td>
                            <td style='color:{rol_i["color"]};font-weight:700;'>{rol_i["label"]}</td></tr>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>Creado</td>
                            <td style='font-family:Share Tech Mono;color:#8A9BBD;'>{row['creado'][:16]}</td></tr>
                        <tr><td style='color:#8A9BBD;padding:0.25rem 0;'>Último acceso</td>
                            <td style='font-family:Share Tech Mono;color:#8A9BBD;'>{str(row['ultimo_acceso'] or '—')[:16]}</td></tr>
                    </table>
                    """, unsafe_allow_html=True)

                with col2:
                    st.markdown("<div style='color:#8A9BBD;font-size:0.75rem;margin-bottom:0.4rem;'>PERMISOS DEL ROL</div>", unsafe_allow_html=True)
                    perms = ROLES.get(row["rol"], {}).get("permisos", [])
                    for p in PERMISOS_LABELS:
                        tiene = p in perms
                        st.markdown(
                            f"<div style='font-size:0.75rem;color:{'#00E676' if tiene else '#2A3A55'};'>"
                            f"{'✓' if tiene else '✗'} {PERMISOS_LABELS[p]}</div>",
                            unsafe_allow_html=True)

                with col3:
                    if tiene_permiso("editar_usuarios") and row["id"] != u["id"]:
                        st.markdown("<div style='color:#8A9BBD;font-size:0.75rem;margin-bottom:0.4rem;'>ACCIONES</div>", unsafe_allow_html=True)

                        nuevo_rol = st.selectbox(
                            "Cambiar rol",
                            options=list(ROLES.keys()),
                            format_func=lambda x: f"{ROLES[x]['icon']} {ROLES[x]['label']}",
                            index=list(ROLES.keys()).index(row["rol"]) if row["rol"] in ROLES else 0,
                            key=f"rol_sel_{row['id']}")

                        if st.button("💾 Guardar rol", key=f"save_rol_{row['id']}",
                                     use_container_width=True):
                            conn = get_conn()
                            conn.execute("UPDATE usuarios SET rol=? WHERE id=?",
                                         (nuevo_rol, row["id"]))
                            conn.commit(); conn.close()
                            registrar_auditoria(u["id"], u["username"], "CAMBIO_ROL",
                                                f"Usuario #{row['id']} → rol: {nuevo_rol}", "usuarios")
                            st.success("Rol actualizado ✓"); st.rerun()

                        btn_lbl  = "🔴 Desactivar" if activo else "✅ Activar"
                        btn_val  = 0 if activo else 1
                        if st.button(btn_lbl, key=f"toggle_{row['id']}",
                                     use_container_width=True):
                            conn = get_conn()
                            conn.execute("UPDATE usuarios SET activo=? WHERE id=?",
                                         (btn_val, row["id"]))
                            conn.commit(); conn.close()
                            registrar_auditoria(u["id"], u["username"],
                                                "ACTIVAR" if btn_val else "DESACTIVAR",
                                                f"Usuario #{row['id']} @{row['username']}", "usuarios")
                            st.rerun()

                        if tiene_permiso("eliminar_usuarios") and row["rol"] != "superadmin":
                            with st.expander("⚠ Eliminar"):
                                st.markdown("<div style='color:#FF5252;font-size:0.75rem;'>Esta acción es permanente.</div>", unsafe_allow_html=True)
                                if st.button("🗑 Confirmar eliminación",
                                             key=f"del_{row['id']}",
                                             use_container_width=True):
                                    conn = get_conn()
                                    conn.execute("DELETE FROM usuarios WHERE id=?", (row["id"],))
                                    conn.commit(); conn.close()
                                    registrar_auditoria(u["id"], u["username"], "ELIMINAR_USUARIO",
                                                        f"@{row['username']}", "usuarios")
                                    st.success("Usuario eliminado ✓"); st.rerun()

                        # Reset contraseña
                        with st.expander("🔑 Reset contraseña"):
                            nueva_pwd = st.text_input("Nueva contraseña",
                                                       type="password",
                                                       key=f"npwd_{row['id']}")
                            if st.button("Aplicar", key=f"rpwd_{row['id']}",
                                         use_container_width=True):
                                ok_p, msg_p = _validar_password(nueva_pwd)
                                if not ok_p:
                                    st.error(msg_p)
                                else:
                                    conn = get_conn()
                                    conn.execute(
                                        "UPDATE usuarios SET password_hash=? WHERE id=?",
                                        (_hash_password(nueva_pwd), row["id"]))
                                    conn.commit(); conn.close()
                                    registrar_auditoria(u["id"], u["username"], "RESET_PASSWORD",
                                                        f"@{row['username']}", "usuarios")
                                    st.success("Contraseña actualizada ✓")

    # ── TAB: Nuevo usuario ────────────────────────────────────────────────────
    with tab_nuevo:
        if not tiene_permiso("crear_usuarios"):
            st.error("🔒 No tienes permiso para crear usuarios.")
        else:
            st.markdown("""
            <div class='sol-card-title'><span class='step-badge'>+</span>
            REGISTRAR NUEVO USUARIO</div>
            """, unsafe_allow_html=True)

            col_n1, col_n2 = st.columns(2)
            with col_n1:
                n_nombre   = st.text_input("Nombre completo *", key="nu_nombre",
                                           placeholder="Ej: Juan Pérez González")
                n_username = st.text_input("Nombre de usuario *", key="nu_user",
                                           placeholder="Ej: jperez")
                n_email    = st.text_input("Correo electrónico *", key="nu_email",
                                           placeholder="jperez@empresa.com")
            with col_n2:
                n_rol    = st.selectbox("Rol *", options=list(ROLES.keys()),
                                        format_func=lambda x: f"{ROLES[x]['icon']} {ROLES[x]['label']}",
                                        key="nu_rol")
                n_pwd    = st.text_input("Contraseña *", type="password", key="nu_pwd",
                                         placeholder="Mín. 8 chars, 1 mayúscula, 1 número")
                n_pwd2   = st.text_input("Confirmar contraseña *", type="password",
                                          key="nu_pwd2")

            # Vista previa de permisos del rol seleccionado
            if n_rol:
                rol_sel = ROLES[n_rol]
                st.markdown(f"""
                <div class='sol-card' style='margin-top:0.8rem;'>
                    <div style='color:{rol_sel["color"]};font-family:Rajdhani,sans-serif;
                     font-weight:600;margin-bottom:0.6rem;'>
                        {rol_sel["icon"]} Permisos de {rol_sel["label"]}
                    </div>
                    <div style='display:flex;flex-wrap:wrap;gap:0.4rem;'>
                """, unsafe_allow_html=True)
                for p in rol_sel["permisos"]:
                    st.markdown(
                        f"<span style='background:{rol_sel['color']}22;color:{rol_sel['color']};"
                        f"font-size:0.72rem;padding:2px 8px;border-radius:10px;"
                        f"border:1px solid {rol_sel['color']}44;'>"
                        f"{PERMISOS_LABELS.get(p, p)}</span>",
                        unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Crear usuario", use_container_width=True,
                         type="primary", key="btn_crear_user"):
                errores = []
                if not n_nombre.strip():  errores.append("Nombre completo requerido")
                if not n_username.strip(): errores.append("Nombre de usuario requerido")
                if not _validar_email(n_email): errores.append("Correo electrónico inválido")
                ok_p, msg_p = _validar_password(n_pwd)
                if not ok_p: errores.append(f"Contraseña: {msg_p}")
                if n_pwd != n_pwd2: errores.append("Las contraseñas no coinciden")

                if errores:
                    for e in errores: st.error(e)
                else:
                    try:
                        conn = get_conn()
                        conn.execute("""
                            INSERT INTO usuarios
                            (username, nombre_completo, email, password_hash, rol, creado_por)
                            VALUES (?,?,?,?,?,?)
                        """, (n_username.strip().lower(), n_nombre.strip(),
                              n_email.strip().lower(), _hash_password(n_pwd),
                              n_rol, u["id"]))
                        conn.commit(); conn.close()
                        registrar_auditoria(u["id"], u["username"], "CREAR_USUARIO",
                                            f"@{n_username} rol:{n_rol}", "usuarios")
                        st.success(f"✓ Usuario @{n_username} creado exitosamente")
                        st.balloons()
                    except sqlite3.IntegrityError as e:
                        if "username" in str(e):
                            st.error("❌ El nombre de usuario ya existe")
                        elif "email" in str(e):
                            st.error("❌ El correo electrónico ya está registrado")
                        else:
                            st.error(f"❌ Error: {e}")

    # ── TAB: Auditoría ────────────────────────────────────────────────────────
    with tab_auditoria:
        if not tiene_permiso("ver_auditoria"):
            st.error("🔒 No tienes permiso para ver la auditoría.")
        else:
            conn = get_conn()
            aud_df = pd.read_sql("""
                SELECT fecha, username, accion, modulo, detalle
                FROM auditoria
                ORDER BY fecha DESC LIMIT 200
            """, conn)
            conn.close()

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_user = st.text_input("Filtrar por usuario", key="aud_user")
            with col_f2:
                filtro_acc  = st.text_input("Filtrar por acción", key="aud_acc")
            with col_f3:
                filtro_mod  = st.text_input("Filtrar por módulo", key="aud_mod")

            df_show = aud_df.copy()
            if filtro_user: df_show = df_show[df_show["username"].str.contains(filtro_user, case=False, na=False)]
            if filtro_acc:  df_show = df_show[df_show["accion"].str.contains(filtro_acc, case=False, na=False)]
            if filtro_mod:  df_show = df_show[df_show["modulo"].str.contains(filtro_mod, case=False, na=False)]

            st.markdown(f"<div style='color:#8A9BBD;font-size:0.8rem;margin-bottom:0.5rem;'>"
                        f"Mostrando {len(df_show)} de {len(aud_df)} registros</div>",
                        unsafe_allow_html=True)

            for _, row in df_show.head(100).iterrows():
                accion_col = {"LOGIN": "#00E676", "LOGOUT": "#8A9BBD",
                              "CREAR": "#00BCD4", "ELIMINAR": "#FF5252",
                              "CAMBIO": "#FFB300"}.get(row["accion"][:6], "#8A9BBD")
                st.markdown(f"""
                <div style='background:#0F1525;border-left:3px solid {accion_col};
                 border-radius:6px;padding:0.4rem 0.8rem;margin-bottom:0.3rem;
                 display:flex;gap:1rem;align-items:center;font-size:0.78rem;'>
                    <span style='color:#2A3A55;font-family:Share Tech Mono;min-width:130px;'>{str(row['fecha'])[:16]}</span>
                    <span style='color:#FFB300;font-weight:600;min-width:100px;'>@{row['username'] or '—'}</span>
                    <span style='color:{accion_col};font-family:Share Tech Mono;min-width:140px;'>{row['accion']}</span>
                    <span style='color:#8A9BBD;min-width:90px;'>{row['modulo'] or ''}</span>
                    <span style='color:#E8EDF5;'>{row['detalle'] or ''}</span>
                </div>
                """, unsafe_allow_html=True)

            if tiene_permiso("gestion_sistema"):
                st.markdown("<hr style='border-color:#2A3A55;margin:1rem 0;'>", unsafe_allow_html=True)
                if st.button("🗑 Limpiar auditoría (>30 días)", key="limpiar_aud"):
                    conn = get_conn()
                    conn.execute("DELETE FROM auditoria WHERE fecha < datetime('now','-30 days')")
                    conn.commit(); conn.close()
                    st.success("Auditoría limpiada ✓"); st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO DE CONTRASEÑA (perfil propio)
# ═══════════════════════════════════════════════════════════════════════════════
def mostrar_cambio_password():
    """Panel para que el usuario cambie su propia contraseña."""
    u = usuario_activo()
    if not u:
        return

    st.markdown("""
    <div class='sol-card-title'><span class='step-badge'>🔑</span>
    CAMBIAR CONTRASEÑA</div>
    """, unsafe_allow_html=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        pwd_actual = st.text_input("Contraseña actual", type="password", key="cp_actual")
        pwd_nueva  = st.text_input("Nueva contraseña", type="password", key="cp_nueva",
                                   help="Mín. 8 chars, 1 mayúscula, 1 número")
        pwd_conf   = st.text_input("Confirmar nueva contraseña", type="password",
                                   key="cp_conf")

        if st.button("💾 Actualizar contraseña", use_container_width=True,
                     type="primary", key="btn_cambiar_pwd"):
            conn = get_conn()
            row = conn.execute("SELECT password_hash FROM usuarios WHERE id=?",
                               (u["id"],)).fetchone()
            conn.close()

            if not row or row[0] != _hash_password(pwd_actual):
                st.error("❌ La contraseña actual es incorrecta")
            else:
                ok_p, msg_p = _validar_password(pwd_nueva)
                if not ok_p:
                    st.error(f"❌ {msg_p}")
                elif pwd_nueva != pwd_conf:
                    st.error("❌ Las contraseñas no coinciden")
                else:
                    conn = get_conn()
                    conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?",
                                 (_hash_password(pwd_nueva), u["id"]))
                    conn.commit(); conn.close()
                    registrar_auditoria(u["id"], u["username"], "CAMBIO_PASSWORD",
                                        "Contraseña actualizada por el usuario", "seguridad")
                    st.success("✓ Contraseña actualizada exitosamente")

    with col_p2:
        st.markdown(f"""
        <div class='sol-card'>
            <div style='color:#FFB300;font-family:Rajdhani,sans-serif;font-weight:600;
             margin-bottom:0.8rem;'>MI PERFIL</div>
            <table style='font-size:0.82rem;width:100%;border-collapse:collapse;'>
                <tr><td style='color:#8A9BBD;padding:0.3rem 0;'>ID</td>
                    <td style='font-family:Share Tech Mono;color:#FFD54F;'>#{u['id']}</td></tr>
                <tr><td style='color:#8A9BBD;padding:0.3rem 0;'>Nombre</td>
                    <td style='color:#E8EDF5;'>{u['nombre']}</td></tr>
                <tr><td style='color:#8A9BBD;padding:0.3rem 0;'>Usuario</td>
                    <td style='color:#E8EDF5;'>@{u['username']}</td></tr>
                <tr><td style='color:#8A9BBD;padding:0.3rem 0;'>Correo</td>
                    <td style='color:#E8EDF5;'>{u['email']}</td></tr>
                <tr><td style='color:#8A9BBD;padding:0.3rem 0;'>Rol</td>
                    <td style='color:{ROLES[u["rol"]]["color"]};font-weight:700;'>
                        {ROLES[u["rol"]]["icon"]} {ROLES[u["rol"]]["label"]}</td></tr>
            </table>
            <div style='margin-top:1rem;'>
                <div style='color:#8A9BBD;font-size:0.75rem;margin-bottom:0.4rem;'>MIS PERMISOS</div>
                {''.join(
                    f"<div style='font-size:0.73rem;color:#00E676;'>✓ {PERMISOS_LABELS.get(p,p)}</div>"
                    for p in ROLES[u['rol']]['permisos']
                )}
            </div>
        </div>
        """, unsafe_allow_html=True)
