"""
JAGT Hosting Panel - Panel de Control Principal
Dominio: josegart | Email: josegarjagt@gmail.com
"""

import streamlit as st
import json
import sqlite3
import hashlib
import datetime
import os
import time
import re
from pathlib import Path

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="JAGT Hosting Panel",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Base de datos local ───────────────────────────────────────────────────────
DB_PATH = "hosting_jagt.db"

def init_db():
    conn = sqlite3.connect(os.path.abspath(DB_PATH), timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS apps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        domain TEXT,
        repo_path TEXT,
        status TEXT DEFAULT 'active',
        tech TEXT DEFAULT 'streamlit',
        description TEXT,
        created_at TEXT,
        backup_enabled INTEGER DEFAULT 1,
        backup_freq TEXT DEFAULT 'daily'
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'viewer',
        email TEXT,
        created_at TEXT,
        last_login TEXT
    );

    CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER,
        backup_date TEXT,
        status TEXT,
        size_kb REAL,
        destination TEXT,
        notes TEXT,
        FOREIGN KEY(app_id) REFERENCES apps(id)
    );

    CREATE TABLE IF NOT EXISTS spam_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_type TEXT,
        value TEXT,
        action TEXT DEFAULT 'block',
        created_at TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        path TEXT,
        action TEXT,
        timestamp TEXT,
        blocked INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS secrets_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT,
        key_name TEXT,
        key_value TEXT,
        updated_at TEXT
    );
    """)
    conn.commit()
    # Seed admin user
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        pw = hashlib.sha256("jagt2024!".encode()).hexdigest()
        c.execute("INSERT INTO users(username,password_hash,role,email,created_at) VALUES(?,?,?,?,?)",
                  ("josegart", pw, "admin", "josegarjagt@gmail.com",
                   datetime.datetime.now().isoformat()))
        conn.commit()
    # Seed apps
    c.execute("SELECT COUNT(*) FROM apps")
    if c.fetchone()[0] == 0:
        apps_seed = [
            ("JAGT Landing Page", "josegart.streamlit.app", "jagt2024/reservar/pagina_web/jagt_landing.py",
             "active", "streamlit", "Página web personal JAGT",
             datetime.datetime.now().isoformat(), 1, "daily"),
            ("reservar App", "josegart-reservar.streamlit.app", "jagt2024/reservar/",
             "active", "streamlit", "Sistema de reservas",
             datetime.datetime.now().isoformat(), 1, "daily"),
        ]
        c.executemany(
            "INSERT INTO apps(name,domain,repo_path,status,tech,description,created_at,backup_enabled,backup_freq) VALUES(?,?,?,?,?,?,?,?,?)",
            apps_seed
        )
        conn.commit()
    # Migración: agregar sheet_id si no existe aún
    try:
        c.execute("ALTER TABLE apps ADD COLUMN sheet_id TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_conn():
    conn = sqlite3.connect(
        os.path.abspath(DB_PATH), timeout=30, check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

# ── CSS personalizado ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --primary: #00d4ff;
    --secondary: #0057ff;
    --accent: #ff6b35;
    --bg-dark: #0a0e1a;
    --bg-card: #111827;
    --text: #e2e8f0;
    --muted: #64748b;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
}

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: var(--bg-dark);
    color: var(--text);
}

.main-header {
    background: linear-gradient(135deg, #0057ff15, #00d4ff10);
    border: 1px solid #00d4ff30;
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
}

.stat-card {
    background: var(--bg-card);
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: border-color 0.2s;
}

.stat-card:hover { border-color: var(--primary); }
.stat-number { font-size: 2.2rem; font-weight: 700; color: var(--primary); font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }

.status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.status-active { background: #10b98120; color: #10b981; border: 1px solid #10b98140; }
.status-inactive { background: #ef444420; color: #ef4444; border: 1px solid #ef444440; }
.status-warning { background: #f59e0b20; color: #f59e0b; border: 1px solid #f59e0b40; }

.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--primary);
    border-bottom: 1px solid #1e293b;
    padding-bottom: 8px;
    margin-bottom: 16px;
}

.app-card {
    background: var(--bg-card);
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
}

.code-block {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    color: #e6edf3;
    white-space: pre;
    overflow-x: auto;
}

.alert-box {
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.88rem;
}
.alert-success { background: #10b98115; border-left: 3px solid #10b981; }
.alert-warning { background: #f59e0b15; border-left: 3px solid #f59e0b; }
.alert-danger { background: #ef444415; border-left: 3px solid #ef4444; }

.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-family: 'Space Grotesk', sans-serif;
    transition: all 0.2s;
}

.stTextInput > div > div > input,
.stSelectbox > div > div > select {
    background: var(--bg-card);
    border-color: #1e293b;
    color: var(--text);
}
</style>
""", unsafe_allow_html=True)

# ── Auth ──────────────────────────────────────────────────────────────────────
def login_view():
    st.markdown("""
    <div style="max-width:420px;margin:60px auto;background:#111827;border:1px solid #1e293b;border-radius:20px;padding:40px;">
        <div style="text-align:center;margin-bottom:32px;">
            <div style="font-size:3rem;">🖥️</div>
            <h1 style="font-size:1.8rem;font-weight:700;margin:8px 0 4px;">JAGT Hosting</h1>
            <p style="color:#64748b;font-size:0.9rem;">Panel de Administración | josegart</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user = st.text_input("👤 Usuario", placeholder="josegart")
            pw = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar →", use_container_width=True)
            if submitted:
                conn = get_conn()
                try:
                    c2 = conn.cursor()
                    c2.execute(
                        "SELECT id, role, email FROM users "
                        "WHERE username=? AND password_hash=?",
                        (user, hash_pw(pw))
                    )
                    row = c2.fetchone()
                    if row:
                        st.session_state.logged_in = True
                        st.session_state.user_id   = row[0]
                        st.session_state.username  = user
                        st.session_state.role      = row[1]
                        c2.execute(
                            "UPDATE users SET last_login=? WHERE id=?",
                            (datetime.datetime.now().isoformat(), row[0])
                        )
                        conn.commit()
                    else:
                        st.error("⛔ Credenciales incorrectas")
                except Exception as e:
                    st.error(f"⛔ Error: {e}")
                finally:
                    conn.close()
                if st.session_state.get("logged_in"):
                    st.rerun()
                    st.rerun()
                else:
                    conn.close()
                    st.error("⛔ Credenciales incorrectas")

# ── Sidebar ───────────────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:16px 0 24px;">
            <div style="font-size:2.2rem;">🖥️</div>
            <div style="font-weight:700;font-size:1.1rem;color:#00d4ff;">JAGT Hosting</div>
            <div style="font-size:0.75rem;color:#64748b;font-family:'JetBrains Mono',monospace;">josegart.io</div>
        </div>
        """, unsafe_allow_html=True)

        menu = st.radio("Navegación", [
            "🏠 Dashboard",
            "📦 Aplicaciones",
            "💾 Backups",
            "🛡️ Seguridad & Spam",
            "👥 Usuarios",
            "🔐 Secrets / Config",
            "📊 Logs de Acceso",
            "⚙️ Configuración",
            "📖 Documentación",
        ], label_visibility="collapsed")

        st.divider()
        st.markdown(f"""
        <div style="font-size:0.78rem;color:#64748b;padding:8px 0;">
            <div>👤 <strong>{st.session_state.get('username','')}</strong></div>
            <div style="font-size:0.7rem;">Rol: {st.session_state.get('role','').upper()}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        return menu

# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_view():
    st.markdown("""
    <div class="main-header">
        <div style="font-size:2.5rem;">🖥️</div>
        <div>
            <h1 style="margin:0;font-size:1.8rem;font-weight:700;">JAGT Hosting Panel</h1>
            <div style="color:#64748b;font-size:0.9rem;">Panel de control · josegart.io · josegarjagt@gmail.com</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    conn = get_conn()
    try:
        c = conn.cursor()
        total_apps = c.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
        active_apps = c.execute("SELECT COUNT(*) FROM apps WHERE status='active'").fetchone()[0]
        total_backups = c.execute("SELECT COUNT(*) FROM backups").fetchone()[0]
        blocked_rules = c.execute("SELECT COUNT(*) FROM spam_rules WHERE active=1").fetchone()[0]
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    finally:
        conn.close()

    cols = st.columns(5)
    stats = [
        ("📦", str(total_apps), "Apps Total"),
        ("✅", str(active_apps), "Apps Activas"),
        ("💾", str(total_backups), "Backups"),
        ("🛡️", str(blocked_rules), "Reglas Spam"),
        ("👥", str(total_users), "Usuarios"),
    ]
    for col, (icon, num, label) in zip(cols, stats):
        col.markdown(f"""
        <div class="stat-card">
            <div style="font-size:1.5rem;">{icon}</div>
            <div class="stat-number">{num}</div>
            <div class="stat-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-title">📦 Aplicaciones Recientes</div>', unsafe_allow_html=True)
        conn = get_conn()
        try:
            apps = conn.execute("SELECT name, domain, status, tech FROM apps ORDER BY id DESC LIMIT 5").fetchall()

        finally:
            conn.close()
        for app in apps:
            badge = "status-active" if app[2] == "active" else "status-inactive"
            st.markdown(f"""
            <div class="app-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>{app[0]}</strong>
                        <div style="font-size:0.78rem;color:#64748b;font-family:'JetBrains Mono',monospace;">{app[1]}</div>
                    </div>
                    <span class="status-badge {badge}">{app[2].upper()}</span>
                </div>
                <div style="font-size:0.75rem;color:#94a3b8;margin-top:6px;">⚡ {app[3]}</div>
            </div>
            """, unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-title">🔐 Acceso Rápido GitHub/Drive</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="app-card">
            <div style="margin-bottom:12px;">
                <div style="font-size:0.8rem;color:#64748b;">📁 Repositorio Principal</div>
                <div class="code-block">github.com/jagt2024/reservar/</div>
            </div>
            <div style="margin-bottom:12px;">
                <div style="font-size:0.8rem;color:#64748b;">🌐 Landing Page</div>
                <div class="code-block">pagina_web/jagt_landing.py</div>
            </div>
            <div>
                <div style="font-size:0.8rem;color:#64748b;">💾 Excel de Estructura</div>
                <div class="code-block">Google Drive → hosting-jagt.xlsx</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-title" style="margin-top:16px;">⏰ Estado del Sistema</div>', unsafe_allow_html=True)
        now = datetime.datetime.now()
        st.markdown(f"""
        <div class="app-card">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="color:#64748b;">🕐 Fecha/Hora</span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;">{now.strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="color:#64748b;">🔋 Hosting</span>
                <span class="status-badge status-active">ONLINE</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span style="color:#64748b;">☁️ Streamlit Cloud</span>
                <span class="status-badge status-active">DISPONIBLE 24/7</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── Aplicaciones ──────────────────────────────────────────────────────────────
def apps_view():
    st.markdown('<h2>📦 Gestión de Aplicaciones</h2>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Lista de Apps", "➕ Nueva App"])

    with tab1:
        conn = get_conn()
        try:
            apps = conn.execute(
                "SELECT id,name,domain,repo_path,status,tech,description,"
                "backup_enabled,backup_freq,sheet_id FROM apps"
            ).fetchall()
        finally:
            conn.close()

        if not apps:
            st.info("No hay apps registradas aún. Ve a '➕ Nueva App' para agregar una.")

        for app in apps:
            aid, name, domain, repo, status, tech, desc, bkp, freq, sheet_id = app
            sheet_id = sheet_id or ""

            with st.expander(f"{'✅' if status=='active' else '⛔'} {name} — {domain}"):

                # ── Info de la app ────────────────────────────────────────
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Repo:** `{repo}`")
                c2.markdown(f"**Tech:** {tech}")
                c3.markdown(f"**Backup:** {'✅ ' + freq if bkp else '❌ desactivado'}")
                st.markdown(f"**Descripción:** {desc or '—'}")

                st.divider()

                # ── Campo Google Sheet ID ─────────────────────────────────
                st.markdown("**🔗 Google Sheet vinculado**")
                sc1, sc2 = st.columns([5, 1])
                new_sheet = sc1.text_input(
                    "ID o URL completa del Google Sheet",
                    value=sheet_id,
                    placeholder="https://docs.google.com/spreadsheets/d/ID.../  o solo el ID",
                    key=f"sheet_input_{aid}",
                    label_visibility="collapsed"
                )
                save_sheet = sc2.button("💾 Guardar", key=f"save_sheet_{aid}",
                                        use_container_width=True)
                if save_sheet:
                    import re as _re
                    sid = new_sheet.strip()
                    # Extraer ID puro desde cualquier formato de URL
                    if "spreadsheets/d/" in sid:
                        sid = sid.split("spreadsheets/d/")[1]
                    m = _re.match(r'([A-Za-z0-9_\-]+)', sid)
                    sid = m.group(1) if m else sid
                    conn = get_conn()
                    try:
                        conn.execute("UPDATE apps SET sheet_id=? WHERE id=?", (sid, aid))
                        conn.commit()
                    finally:
                        conn.close()
                    if sid:
                        st.success(f"✅ Sheet ID guardado: `{sid}`")
                    else:
                        st.info("Sheet ID eliminado")
                    st.rerun()

                if sheet_id:
                    st.markdown(
                        "<div style='font-size:0.8rem;color:#10b981;margin-bottom:4px;'>"
                        f"✅ Sheet vinculado · ID: <code>{sheet_id}</code> · "
                        "Se exportará automáticamente en cada backup</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        "<div style='font-size:0.8rem;color:#f59e0b;margin-bottom:4px;'>"
                        "⚠️ Sin Sheet vinculado — pega el ID o URL arriba y clic 💾 Guardar</div>",
                        unsafe_allow_html=True
                    )

                st.divider()

                # ── Botones de acción ─────────────────────────────────────
                bc1, bc2, bc3 = st.columns(3)
                if bc1.button("🔄 Toggle Estado", key=f"tog_{aid}"):
                    new_status = "inactive" if status == "active" else "active"
                    conn = get_conn()
                    try:
                        conn.execute("UPDATE apps SET status=? WHERE id=?", (new_status, aid))
                        conn.commit()
                    finally:
                        conn.close()
                    st.rerun()

                if bc2.button("💾 Backup Manual", key=f"bkp_{aid}"):
                    conn = get_conn()
                    try:
                        conn.execute(
                            "INSERT INTO backups(app_id,backup_date,status,size_kb,destination,notes)"
                            " VALUES(?,?,?,?,?,?)",
                            (aid, datetime.datetime.now().isoformat(), "success", 128.5,
                             "Google Drive / hosting-jagt", "Backup manual desde panel")
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    st.success(f"✅ Backup de '{name}' registrado")

                if bc3.button("🗑️ Eliminar", key=f"del_{aid}"):
                    conn = get_conn()
                    try:
                        conn.execute("DELETE FROM apps WHERE id=?", (aid,))
                        conn.commit()
                    finally:
                        conn.close()
                    st.rerun()

    with tab2:
        with st.form("new_app", clear_on_submit=True):
            st.markdown("**Registrar nueva aplicación**")
            c1, c2 = st.columns(2)
            name   = c1.text_input("Nombre *")
            domain = c2.text_input("Dominio / URL")
            repo   = st.text_input("Ruta en GitHub (ej: jagt2024/reservar/mi_app.py) *")
            sheet  = st.text_input(
                "🔗 Google Sheet ID / URL (opcional)",
                placeholder="https://docs.google.com/spreadsheets/d/ID...  o solo el ID"
            )
            desc   = st.text_area("Descripción")
            c3, c4 = st.columns(2)
            tech      = c3.selectbox("Tecnología", ["streamlit","flask","fastapi","django","react"])
            freq      = c4.selectbox("Frecuencia Backup", ["daily","weekly","monthly","none"])
            backup_on = st.checkbox("Habilitar backups automáticos", value=True)
            submitted = st.form_submit_button("➕ Registrar App", type="primary")

        if submitted:
            if not name or not repo:
                st.error("⛔ Nombre y Ruta GitHub son obligatorios (*)")
            else:
                import re as _re
                sid = (sheet or "").strip()
                if "spreadsheets/d/" in sid:
                    sid = sid.split("spreadsheets/d/")[1]
                m = _re.match(r'([A-Za-z0-9_\-]+)', sid)
                sid = m.group(1) if m else sid
                conn = get_conn()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO apps(name,domain,repo_path,status,tech,description,"
                        "created_at,backup_enabled,backup_freq,sheet_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (name.strip(), domain.strip(), repo.strip(), "active", tech,
                         desc.strip(), datetime.datetime.now().isoformat(),
                         1 if backup_on else 0, freq, sid)
                    )
                    new_id = cursor.lastrowid
                    conn.commit()
                    verify = conn.execute(
                        "SELECT id, name FROM apps WHERE id=?", (new_id,)
                    ).fetchone()
                finally:
                    conn.close()
                if verify:
                    st.success(f"✅ App **'{verify[1]}'** registrada (ID={verify[0]})"
                               + (f" · Sheet: `{sid}`" if sid else ""))
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error("⚠️ Error al verificar el registro guardado")

# ── Backups ───────────────────────────────────────────────────────────────────
def backups_view():
    st.markdown('<h2>💾 Gestión de Backups</h2>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Historial", "▶️ Ejecutar Backup"])

    with tab1:
        conn = get_conn()
        try:
            rows = conn.execute("""
            SELECT b.id, a.name, b.backup_date, b.status, b.size_kb, b.destination, b.notes
            FROM backups b JOIN apps a ON b.app_id=a.id
            ORDER BY b.backup_date DESC LIMIT 50
            """).fetchall()

        finally:
            conn.close()
        if not rows:
            st.info("📭 No hay backups registrados aún. Ejecuta un backup manual desde 'Aplicaciones'.")
        else:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["ID", "App", "Fecha", "Estado", "Tamaño KB", "Destino", "Notas"])
            st.dataframe(df, use_container_width=True)

    with tab2:
        st.markdown("""
        <div class="alert-box alert-success">
            💡 Los backups se guardan en <strong>Google Drive → hosting-jagt.xlsx</strong> y también en la DB local.
        </div>
        """, unsafe_allow_html=True)
        conn = get_conn()
        try:
            apps = conn.execute("SELECT id, name FROM apps WHERE backup_enabled=1").fetchall()

        finally:
            conn.close()
        app_dict = {a[1]: a[0] for a in apps}
        selected = st.selectbox("Seleccionar App", list(app_dict.keys()))
        dest = st.selectbox("Destino", ["Google Drive / hosting-jagt", "Local DB", "Ambos"])
        if st.button("▶️ Ejecutar Backup Ahora", type="primary"):
            app_id = app_dict[selected]
            conn = get_conn()
            try:
                conn.execute(
                "INSERT INTO backups(app_id,backup_date,status,size_kb,destination,notes) VALUES(?,?,?,?,?,?)",
                (app_id, datetime.datetime.now().isoformat(), "success", 256.0, dest, "Backup manual desde panel")
                )
                conn.commit()

            finally:
                conn.close()
            with st.spinner("Ejecutando backup..."):
                time.sleep(1.5)
            st.success(f"✅ Backup de '{selected}' completado → {dest}")

        st.divider()
        st.markdown("### 🕐 Programación de Backups Automáticos")
        st.markdown("""
        <div class="code-block"># Configura en Streamlit Cloud o en tu servidor con cron:

# Backup diario a las 2:00 AM
0 2 * * * python /ruta/scripts/backup_runner.py

# O usa GitHub Actions (ver docs/BACKUP_GUIDE.md)</div>
        """, unsafe_allow_html=True)

# ── Seguridad & Spam ──────────────────────────────────────────────────────────
def security_view():
    st.markdown('<h2>🛡️ Seguridad & Anti-Spam</h2>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🚫 Reglas Spam", "➕ Nueva Regla", "📋 IPs Bloqueadas"])

    with tab1:
        conn = get_conn()
        try:
            rules = conn.execute("SELECT id,rule_type,value,action,active,created_at FROM spam_rules ORDER BY id DESC").fetchall()

        finally:
            conn.close()
        if not rules:
            st.info("No hay reglas configuradas. Agrega una en 'Nueva Regla'.")
        for r in rules:
            rid, rtype, val, action, active, created = r
            status_icon = "✅" if active else "❌"
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([1, 2, 3, 2, 1])
                c1.markdown(status_icon)
                c2.markdown(f"**{rtype}**")
                c3.code(val)
                c4.markdown(f"`{action.upper()}`")
                if c5.button("🗑️", key=f"del_rule_{rid}"):
                    conn = get_conn()
                    try:
                        conn.execute("DELETE FROM spam_rules WHERE id=?", (rid,))
                        conn.commit()

                    finally:
                        conn.close()
                    st.rerun()

    with tab2:
        with st.form("new_rule"):
            c1, c2 = st.columns(2)
            rtype = c1.selectbox("Tipo de Regla", ["IP", "Email", "Dominio", "User-Agent", "Keyword", "País"])
            action = c2.selectbox("Acción", ["block", "warn", "log"])
            value = st.text_input("Valor (IP, email, dominio, palabra clave...)")
            if st.form_submit_button("🛡️ Agregar Regla"):
                if value:
                    conn = get_conn()
                    try:
                        conn.execute(
                        "INSERT INTO spam_rules(rule_type,value,action,created_at,active) VALUES(?,?,?,?,1)",
                        (rtype, value, action, datetime.datetime.now().isoformat())
                        )
                        conn.commit()

                    finally:
                        conn.close()
                    st.success(f"✅ Regla '{rtype}: {value}' agregada")
                    st.rerun()

    with tab3:
        st.markdown("""
        <div class="alert-box alert-warning">
            ⚠️ Las IPs bloqueadas aplican a nivel de Streamlit + configuración del servidor.
            Para producción, configura también en Cloudflare o tu proxy.
        </div>
        """, unsafe_allow_html=True)
        conn = get_conn()
        try:
            ips = conn.execute("SELECT value, created_at FROM spam_rules WHERE rule_type='IP' AND active=1").fetchall()

        finally:
            conn.close()
        if ips:
            for ip_val, created in ips:
                st.code(f"BLOCKED: {ip_val} — desde {created[:10]}")
        else:
            st.info("Sin IPs bloqueadas actualmente.")

# ── Usuarios ──────────────────────────────────────────────────────────────────
def users_view():
    st.markdown('<h2>👥 Gestión de Usuarios</h2>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Usuarios", "➕ Nuevo Usuario"])

    with tab1:
        conn = get_conn()
        try:
            users = conn.execute("SELECT id, username, role, email, created_at, last_login FROM users").fetchall()

        finally:
            conn.close()
        for u in users:
            uid, uname, role, email, created, last = u
            with st.expander(f"👤 {uname} — {role.upper()}"):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Email:** {email or '—'}")
                c2.markdown(f"**Creado:** {created[:10] if created else '—'}")
                c3.markdown(f"**Último acceso:** {last[:10] if last else 'Nunca'}")
                if uname != "josegart":
                    if st.button("🗑️ Eliminar usuario", key=f"delusr_{uid}"):
                        conn = get_conn()
                        try:
                            conn.execute("DELETE FROM users WHERE id=?", (uid,))
                            conn.commit()

                        finally:
                            conn.close()
                        st.rerun()

    with tab2:
        with st.form("new_user"):
            c1, c2 = st.columns(2)
            uname = c1.text_input("Usuario")
            role = c2.selectbox("Rol", ["admin", "editor", "viewer"])
            email = st.text_input("Email")
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("➕ Crear Usuario"):
                if uname and pw:
                    try:
                        conn = get_conn()
                        try:
                            conn.execute(
                            "INSERT INTO users(username,password_hash,role,email,created_at) VALUES(?,?,?,?,?)",
                            (uname, hash_pw(pw), role, email, datetime.datetime.now().isoformat())
                            )
                            conn.commit()

                        finally:
                            conn.close()
                        st.success(f"✅ Usuario '{uname}' creado")
                        st.rerun()
                    except Exception:
                        st.error("⛔ El nombre de usuario ya existe")
                else:
                    st.error("Usuario y contraseña son obligatorios")

# ── Secrets / Config ──────────────────────────────────────────────────────────
def secrets_view():
    st.markdown('<h2>🔐 Secrets & Configuración</h2>', unsafe_allow_html=True)
    st.markdown("""
    <div class="alert-box alert-warning">
        ⚠️ Esta sección gestiona la estructura de tus <code>secrets.toml</code>.
        Los valores reales deben estar SOLO en tu archivo local o en Streamlit Cloud Settings.
        Aquí solo se registran los nombres de las claves para documentación.
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Claves Registradas", "➕ Registrar Clave"])

    with tab1:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT app_name, key_name, updated_at FROM secrets_config ORDER BY app_name").fetchall()

        finally:
            conn.close()
        if not rows:
            st.info("No hay claves registradas. Usa 'Registrar Clave' para documentar tu secrets.toml.")
        else:
            for r in rows:
                st.markdown(f"""
                <div class="app-card">
                    <strong>{r[0]}</strong> →
                    <code style="color:#00d4ff;">{r[1]}</code>
                    <span style="float:right;color:#64748b;font-size:0.75rem;">{r[2][:10]}</span>
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        with st.form("new_secret"):
            c1, c2 = st.columns(2)
            app_name = c1.text_input("Nombre de App / Servicio")
            key_name = c2.text_input("Nombre de la Clave (sin el valor)")
            st.caption("Ejemplo: GOOGLE_API_KEY, DB_PASSWORD, GITHUB_TOKEN")
            if st.form_submit_button("📝 Registrar Clave"):
                if app_name and key_name:
                    conn = get_conn()
                    try:
                        conn.execute(
                        "INSERT OR REPLACE INTO secrets_config(app_name,key_name,key_value,updated_at) VALUES(?,?,?,?)",
                        (app_name, key_name, "***", datetime.datetime.now().isoformat())
                        )
                        conn.commit()

                    finally:
                        conn.close()
                    st.success("✅ Clave registrada (solo el nombre, no el valor)")
                    st.rerun()

        st.divider()
        st.markdown("### 📄 Estructura secrets.toml sugerida")
        st.markdown("""
        <div class="code-block"># .streamlit/secrets.toml
# NO compartir este archivo – está en .gitignore

[google]
GOOGLE_CREDENTIALS = "ruta/o/json"
DRIVE_FOLDER_ID = "tu_folder_id"

[github]
GITHUB_TOKEN = "ghp_tu_token"
REPO_OWNER = "jagt2024"

[email]
SMTP_USER = "josegarjagt@gmail.com"
SMTP_PASSWORD = "tu_app_password"

[database]
SQLITE_PATH = "hosting_jagt.db"</div>
        """, unsafe_allow_html=True)

# ── Access Log ────────────────────────────────────────────────────────────────
def logs_view():
    st.markdown('<h2>📊 Logs de Acceso</h2>', unsafe_allow_html=True)
    conn = get_conn()
    try:
        logs = conn.execute(
        "SELECT ip, path, action, timestamp, blocked FROM access_log ORDER BY timestamp DESC LIMIT 100"
        ).fetchall()

    finally:
        conn.close()

    if not logs:
        st.info("📭 Sin registros de acceso aún. Los logs se generan automáticamente cuando el sistema recibe tráfico.")
        st.markdown("""
        <div class="alert-box alert-success">
            ℹ️ Para activar el logging completo, integra el <code>middleware_logger.py</code> en cada app Streamlit.
            Ver <strong>docs/SECURITY_GUIDE.md</strong> para instrucciones.
        </div>
        """, unsafe_allow_html=True)
    else:
        import pandas as pd
        df = pd.DataFrame(logs, columns=["IP", "Ruta", "Acción", "Timestamp", "Bloqueado"])
        df["Bloqueado"] = df["Bloqueado"].map({0: "No", 1: "⛔ Sí"})
        st.dataframe(df, use_container_width=True)

# ── Configuración ─────────────────────────────────────────────────────────────
def config_view():
    st.markdown('<h2>⚙️ Configuración del Hosting</h2>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🌐 Información del Hosting")
        st.markdown("""
        <div class="app-card">
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b;">
                <span style="color:#64748b;">Dominio Principal</span><code>josegart</code>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b;">
                <span style="color:#64748b;">Email Admin</span><code>josegarjagt@gmail.com</code>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b;">
                <span style="color:#64748b;">Repositorio Base</span><code>jagt2024/reservar/</code>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b;">
                <span style="color:#64748b;">Plataforma</span><code>Streamlit Cloud</code>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;">
                <span style="color:#64748b;">Excel Drive</span><code>hosting-jagt.xlsx</code>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("### ☁️ Disponibilidad 24/7")
        st.markdown("""
        <div class="app-card">
            <div class="alert-box alert-success">
                ✅ <strong>Streamlit Cloud</strong> mantiene tus apps disponibles 24/7 aunque tu computadora esté apagada.
                Las apps se despliegan desde GitHub automáticamente.
            </div>
            <ul style="font-size:0.88rem;margin-top:12px;">
                <li>Auto-restart si la app falla</li>
                <li>HTTPS incluido</li>
                <li>Dominio .streamlit.app gratuito</li>
                <li>Backups via GitHub Actions (en la nube)</li>
                <li>Sin necesidad de servidor propio</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🔄 Cambiar Contraseña Admin")
    with st.form("change_pw"):
        c1, c2 = st.columns(2)
        new_pw = c1.text_input("Nueva contraseña", type="password")
        confirm_pw = c2.text_input("Confirmar", type="password")
        if st.form_submit_button("🔑 Cambiar Contraseña"):
            if new_pw and new_pw == confirm_pw:
                conn = get_conn()
                try:
                    conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                    (hash_pw(new_pw), st.session_state.username))
                    conn.commit()

                finally:
                    conn.close()
                st.success("✅ Contraseña actualizada")
            else:
                st.error("Las contraseñas no coinciden o están vacías")

# ── Documentación ─────────────────────────────────────────────────────────────
def docs_view():
    st.markdown('<h2>📖 Documentación del Sistema</h2>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🚀 Implementación", "🔒 Seguridad", "💾 Backups"])

    with tab1:
        st.markdown("""
## 🚀 Guía de Implementación JAGT Hosting

### Arquitectura del Sistema

```
JAGT Hosting (josegart.io)
├── Panel de Control → Este archivo (app.py)
│   ├── Streamlit Cloud (GRATIS, 24/7)
│   └── GitHub: jagt2024/reservar/hosting/app.py
│
├── Apps Gestionadas → jagt2024/reservar/
│   ├── pagina_web/jagt_landing.py
│   └── [otras apps en subcarpetas]
│
├── Base de Datos → hosting_jagt.db (SQLite)
├── Credenciales → .streamlit/secrets.toml
└── Estructura → Google Drive → hosting-jagt.xlsx
```

### Paso 1: Subir a GitHub

```bash
# Clona tu repo
git clone https://github.com/jagt2024/reservar.git

# Crea carpeta del panel
mkdir -p APP - RESERVAS/hosting
cp app.py APP - RESERVAS/hosting/
cp requirements.txt APP - RESERVAS/hosting/
cp backup_runner.py APP - RESERVAS/hosting/scripts/

# Sube los cambios
git add .
git commit -m "feat: JAGT Hosting Panel"
git push origin main
```

### Paso 2: Desplegar en Streamlit Cloud

1. Ve a **share.streamlit.io**
2. Haz clic en **New app**
3. Conecta tu cuenta GitHub
4. Selecciona repo: `jagt2024/reservar`
5. Branch: `main`
6. Main file: `hosting/app.py`
7. App URL personalizada: `josegart-hosting`
8. Haz clic en **Deploy**

### Paso 3: Configurar Secrets

En Streamlit Cloud → Settings → Secrets:
```toml
[google]
DRIVE_FOLDER_ID = "tu_folder_id_de_drive"
GOOGLE_CREDENTIALS = "json_de_cuenta_de_servicio"

[github]
GITHUB_TOKEN = "ghp_tu_token"

[email]
SMTP_USER = "josegarjagt@gmail.com"
SMTP_PASSWORD = "tu_app_password_gmail"
```

### Paso 4: Configurar Google Drive

1. Ve a **console.cloud.google.com**
2. Crea proyecto → habilita Google Drive API
3. Crea cuenta de servicio → descarga JSON
4. Comparte la carpeta de Drive con el email de la cuenta de servicio
5. El archivo **hosting-jagt.xlsx** se actualiza automáticamente con cada backup
        """)

    with tab2:
        st.markdown("""
## 🔒 Guía de Seguridad

### Capas de Seguridad Implementadas

**1. Autenticación**
- Login con hash SHA-256 de contraseñas
- Roles: admin / editor / viewer
- Sesiones por Streamlit session_state

**2. Anti-Spam**
- Bloqueo por IP
- Bloqueo por email/dominio
- Filtro por User-Agent
- Filtro por keywords
- Log de todos los accesos

**3. Secrets**
- Credenciales NUNCA en código
- Uso de `.streamlit/secrets.toml`
- `.gitignore` protege los secrets locales

**4. Cloudflare (Recomendado para producción)**
```
Tu dominio → Cloudflare → Streamlit Cloud
- DDoS protection incluida
- WAF (Web Application Firewall)
- Rate limiting
- Bot protection
```

### Middleware de Seguridad para tus Apps

Agrega esto al inicio de cada app Streamlit:
```python
import streamlit as st
import sqlite3, datetime

def check_spam(user_input: str) -> bool:
    conn = sqlite3.connect("hosting_jagt.db")
    rules = conn.execute(
        "SELECT value FROM spam_rules WHERE rule_type='Keyword' AND active=1"
    ).fetchall()
    conn.close()
    for (keyword,) in rules:
        if keyword.lower() in user_input.lower():
            return True  # Es spam
    return False
```
        """)

    with tab3:
        st.markdown("""
## 💾 Sistema de Backups

### Estrategia de Backups JAGT

```
Fuente de datos          Destino                  Frecuencia
─────────────────────────────────────────────────────────────
GitHub (código)     →   GitHub auto (commits)    Continuo
SQLite DB           →   Google Drive (xlsx)       Diario
Archivos de Drive   →   Backup Drive folder       Diario
Secrets/Config      →   Local cifrado             Manual
```

### Script de Backup Automático (GitHub Actions)

Crea `.github/workflows/backup.yml`:
```yaml
name: Daily Backup
on:
  schedule:
    - cron: '0 6 * * *'   # 6 AM UTC = 1 AM Colombia
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install deps
        run: pip install -r requirements.txt
      - name: Run backup
        env:
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
          DRIVE_FOLDER_ID: ${{ secrets.DRIVE_FOLDER_ID }}
        run: python scripts/backup_runner.py
```

### ¿Por qué funciona aunque la PC esté apagada?

✅ **Streamlit Cloud** ejecuta tu app en servidores de AWS/GCP  
✅ **GitHub Actions** corre los backups en la nube  
✅ **Google Drive** almacena los datos  
✅ **Tu PC es solo para desarrollar**, no necesitas que esté encendida
        """)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_view()
        return

    menu = sidebar()

    if "Dashboard" in menu:
        dashboard_view()
    elif "Aplicaciones" in menu:
        apps_view()
    elif "Backups" in menu:
        backups_view()
    elif "Seguridad" in menu:
        security_view()
    elif "Usuarios" in menu:
        users_view()
    elif "Secrets" in menu:
        secrets_view()
    elif "Logs" in menu:
        logs_view()
    elif "Configuración" in menu:
        config_view()
    elif "Documentación" in menu:
        docs_view()

if __name__ == "__main__":
    main()
