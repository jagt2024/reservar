"""
JJGT — app.py  v2.3
Plataforma de Venta y Permuta de Vehículos · Colombia

Fixes v2.3:
  1. Imágenes en detalle: usa preview_url de Drive (thumbnail) en lugar de bytes
  2. Video en detalle: usa iframe embed de Drive en lugar de st.video()
  3. Tarjeta de vehículo: solo muestra foto de portada (no todas las fotos)
  4. Correo automático al enviar propuesta de permuta
  5. Guardado bidireccional: Excel descargable + Google Sheets en tiempo real
"""
import io
import re
import streamlit as st
from datetime import datetime
from PIL import Image
from media_sync import load_media_from_urls, show_fotos, show_video, get_portada_data_uri

# Ocultar elementos de la interfaz de Streamlit usando CSS personalizado
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stDeployButton {display:none;}
            .css-1rs6os {visibility: hidden;}
            .css-14xtw13 {visibility: hidden;}
            .css-1avcm0n {visibility: hidden;}
            /* Ocultar header pero mantener botón del sidebar visible */
            header[data-testid="stHeader"] {visibility: hidden; height: 0; min-height: 0;}
            /* Botón abrir/cerrar sidebar — siempre visible */
            [data-testid="collapsedControl"],
            button[data-testid="baseButton-header"] {
                visibility: visible !important;
                display: flex !important;
                opacity: 1 !important;
                z-index: 999999 !important;
                position: fixed !important;
                top: 0.4rem !important;
                left: 0.4rem !important;
                background: rgba(196,30,58,0.85) !important;
                border-radius: 8px !important;
                color: white !important;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

def _dedup_vehicles():
    """Une user_publications + vehicles sin duplicados por ID."""
    seen, result = set(), []
    for v in st.session_state.user_publications + get_vehicles():
        # Normalizar ID: quitar espacios, convertir a string uppercase
        vid = str(v.get("id", "")).strip().upper()
        if vid not in seen:
            seen.add(vid)
            result.append(v)
    return result



from data import (
    init_data, get_vehicles, get_usuarios, get_permutas_base,
    get_history_base, get_notifs_base, CHATBOT_REPLIES, load_from_xlsx,
    reconstruct_media,
)
from components import GRAD_COLORS, fmt_price, permuta_card_html

ADMIN_EMAIL = "josegarjagt@gmail.com"
from styles import get_css
from excel_sync import (
    download_button_excel, save_and_notify, save_section_silent,
)

from media_sync import send_permuta_email

# ── Helper: escribir password_hash directo en Sheets (sin depender de excel_sync externo) ──
def _save_pw_hash(correo: str, pw_hash: str) -> tuple:
    """Escribe pw_hash en la celda exacta de la hoja USUARIOS buscando por correo."""
    try:
        import time as _time, string as _string
        from data import load_credentials_from_toml, get_google_sheets_connection
        from excel_sync import SHEET_FILE
        creds, _ = load_credentials_from_toml()
        if not creds:
            return False, "Sin credenciales Google"
        client = get_google_sheets_connection(creds)
        sh = client.open(SHEET_FILE)
        ws = sh.worksheet("👥 USUARIOS")
        all_vals = ws.get_all_values()
        if not all_vals:
            return False, "Hoja USUARIOS vacía"
        headers = list(all_vals[0])
        # Buscar o crear columna Password Hash
        PH = "Password Hash"
        if PH in headers:
            ph_idx = headers.index(PH)
        else:
            ph_idx = len(headers)
            headers.append(PH)
            ws.update("A1", [headers])
            _time.sleep(0.4)
        # Buscar columna Correo
        correo_idx = next((headers.index(c) for c in ("Correo","correo","Email","email")
                           if c in headers), None)
        if correo_idx is None:
            return False, "No se encontró columna Correo"
        # Buscar fila del usuario
        correo_norm = correo.strip().lower()
        target_row  = None
        for i, row in enumerate(all_vals[1:], start=2):
            if correo_idx < len(row) and row[correo_idx].strip().lower() == correo_norm:
                target_row = i
                break
        if target_row is None:
            return False, f"Correo '{correo}' no encontrado en USUARIOS"
        # Letra de columna
        def _col(idx):
            r = ""
            idx += 1
            while idx:
                idx, rem = divmod(idx - 1, 26)
                r = _string.ascii_uppercase[rem] + r
            return r
        ws.update(f"{_col(ph_idx)}{target_row}", [[pw_hash]])
        return True, "OK"
    except Exception as e:
        return False, str(e)


def _upsert_vehiculo_in_sheets(pub: dict) -> tuple:
    """Inserta o actualiza SOLO la fila de una publicación en la hoja de Vehículos."""
    try:
        import time as _time
        from data import load_credentials_from_toml, get_google_sheets_connection
        from excel_sync import SHEET_FILE, WS, _row_veh, _safe
        creds, _ = load_credentials_from_toml()
        if not creds:
            return False, "Sin credenciales Google"
        client  = get_google_sheets_connection(creds)
        sh      = client.open(SHEET_FILE)
        ws      = sh.worksheet(WS["vehiculos"])   # 🚗 VEHÍCULOS
        all_v   = ws.get_all_values()
        row_d   = _row_veh(pub)
        headers = list(row_d.keys())
        values  = [_safe(v) for v in row_d.values()]
        pid_str = str(pub.get("id","")).strip()

        if not all_v:
            ws.append_row(headers)
            _time.sleep(0.3)
            ws.append_row(values)
            return True, "Fila creada en Vehículos"

        # Verificar/actualizar encabezados
        if all_v[0] != headers:
            ws.update("A1", [headers])
            _time.sleep(0.3)
            all_v = ws.get_all_values()

        # Buscar fila por ID
        pk_idx  = headers.index("ID")
        target  = None
        for i, row in enumerate(all_v[1:], start=2):
            if pk_idx < len(row) and str(row[pk_idx]).strip() == pid_str:
                target = i
                break

        import string as _s
        def _col(n):
            r, n = "", n+1
            while n:
                n, rem = divmod(n-1, 26)
                r = _s.ascii_uppercase[rem] + r
            return r

        if target:
            ws.update(f"A{target}:{_col(len(values)-1)}{target}", [values])
            return True, f"Vehículo actualizado en fila {target}"
        else:
            ws.append_row(values)
            return True, "Vehículo agregado a Vehículos"
    except Exception as e:
        return False, str(e)


def _delete_pub_from_sheets(pub_id: str) -> tuple:
    """Elimina la fila con pub_id de Vehículos y Publicaciones en Sheets. No toca Historial."""
    try:
        import time as _time
        from data import load_credentials_from_toml, get_google_sheets_connection
        from excel_sync import SHEET_FILE, WS
        creds, _ = load_credentials_from_toml()
        if not creds:
            return False, "Sin credenciales Google"
        client = get_google_sheets_connection(creds)
        sh      = client.open(SHEET_FILE)
        pid_str = str(pub_id).strip()
        msgs    = []

        # Cada hoja usa un PK diferente — definirlo explícitamente
        hojas = [
            ("vehiculos",     WS["vehiculos"],     "ID"),        # 🚗 VEHÍCULOS  → col "ID"
            ("publicaciones", WS["publicaciones"], "ID Pub"),    # 📋 PUBLICACIONES → col "ID Pub"
        ]

        for ws_key, ws_name, pk_col in hojas:
            try:
                ws = sh.worksheet(ws_name)
            except Exception as _we:
                msgs.append(f"{ws_name}: no encontrada ({_we})")
                continue

            all_vals = ws.get_all_values()
            if not all_vals:
                msgs.append(f"{ws_name}: vacía")
                continue

            headers = all_vals[0]

            # Buscar columna PK — puede tener espacios o codificación diferente
            pk_idx = None
            for i, h in enumerate(headers):
                if h.strip() == pk_col.strip():
                    pk_idx = i
                    break

            if pk_idx is None:
                msgs.append(f"{ws_name}: columna '{pk_col}' no encontrada (headers: {headers[:5]})")
                continue

            to_del = [
                i + 2  # +2 porque all_vals[1:] empieza en fila 2 de Sheets
                for i, row in enumerate(all_vals[1:])
                if pk_idx < len(row) and str(row[pk_idx]).strip() == pid_str
            ]

            if not to_del:
                msgs.append(f"{ws_name}: ID '{pid_str}' no encontrado")
                continue

            for row_num in sorted(to_del, reverse=True):
                ws.delete_rows(row_num)
                _time.sleep(0.2)

            msgs.append(f"{ws_name}: ✅ {len(to_del)} fila(s) eliminada(s)")

        return True, " · ".join(msgs)
    except Exception as e:
        return False, str(e)


# ── Configuración de página ────────────────────────────────────────────────────
#st.set_page_config(
#    page_title="JJGT — Vehículos Colombia",
#    page_icon="🚗", layout="wide",
#    initial_sidebar_state="collapsed",
#)
#st.markdown(get_css(), unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
_DEFAULTS = {
    "logged_in": False, "user_name": "", "user_email": "",
    "user_phone": "", "user_city": "Bogotá",
    "page": "home", "selected_vehicle": None,
    "user_publications": [],
    "resenas": [],
    "history_items": None,
    "notifications": None,
    "permutas": None,
    "notif_count": 3,
    "active_cities": ["Bogotá", "Medellín", "Cali"],
    "dark_mode": False,
    "loyalty_points": 200, "loyalty_level": "Silver",
    "chat_messages": [],
    "notif_prefs": {"mensajes": True, "permutas": True, "visitas": True,
                    "nuevos": False, "resenas": True, "push": True},
    "det_action":      None,
    "det_edit_mode":   False,
    "det_confirm_del": False,
    "_confirm_del_usr": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Carga de datos ─────────────────────────────────────────────────────────────
init_data()

# ── DIAGNÓSTICO TEMPORAL DE MEDIA (borrar después) ────────────────────────────
#with st.sidebar.expander("🔍 Debug Media", expanded=False):
#    import os as _os
#    st.caption(f"cwd: {_os.getcwd()}")
#    pubs = st.session_state.get("user_publications", [])
#    vehs = st.session_state.get("_vehicles", [])
#    st.caption(f"user_publications: {len(pubs)}")
#    st.caption(f"_vehicles con fotos_urls: {sum(1 for v in vehs if v.get('fotos_urls'))}")
#    todos = pubs + vehs
#    for v in todos[:5]:
#        fcsv = (v.get("fotos_urls") or "").strip()
#        if not fcsv:
#            continue
#        primera = fcsv.split(",")[0].strip()
#        fotos_mem = v.get("fotos", [])
#        tiene_bytes = any(f.get("bytes") for f in fotos_mem if isinstance(f, dict))
#        from media_sync import _leer
#        raw = _leer(primera)
#        from media_sync import get_portada_data_uri as _gpd
#        uri = _gpd(v, 100)
#        st.caption(
#            f"ID: {v.get('id','?')} | "
#            f"ruta: {primera[:60]} | "
#            f"_leer: {'OK' if raw is not None else 'FAIL'} | "
#            f"fotos: {len(fotos_mem)} bytes:{tiene_bytes} | "
#            f"uri: {'OK' if uri else 'VACIO'}"
#        )
#        if uri:
#            st.markdown(f'<img src="{uri}" style="width:80px;height:60px;object-fit:cover;">',
#                        unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.history_items is None:
    st.session_state.history_items = list(get_history_base())
if st.session_state.notifications is None:
    st.session_state.notifications = list(get_notifs_base())
if st.session_state.permutas is None:
    st.session_state.permutas = list(get_permutas_base())


# ── Utilidades ─────────────────────────────────────────────────────────────────
def go(page: str):
    if page != "vehicle_detail":
        st.session_state.det_action      = None
        st.session_state.det_edit_mode   = False
        st.session_state.det_confirm_del = False
    st.session_state.page = page
    st.rerun()


def _cambiar_cuenta():
    """Limpia todos los datos del usuario actual y redirige al login."""
    _USER_KEYS = [
        "logged_in", "user_name", "user_email", "user_phone", "user_city",
        "user_password_hash", "active_cities", "loyalty_points", "loyalty_level",
        "history_items", "notifications", "user_publications", "permutas",
        "chat_messages", "resenas", "_del_pending_id", "_del_pending_name",
        "_pw_change_data", "_pw_change_result", "_login_attempt",
        "_hist_email_no_existe", "_hist_login_attempt", "_hist_reg_data",
    ]
    for k in _USER_KEYS:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_email = ""
    go("login")


def _btn_inicio(key_suffix=""):
    """Botón de regreso al inicio dentro del contenido principal."""
    st.markdown(
        """<div style="margin-bottom:8px;">""",
        unsafe_allow_html=True)
    if st.button("← Volver al inicio", key=f"btn_inicio_{key_suffix}",
                 type="secondary"):
        go("home")
    st.markdown("</div>", unsafe_allow_html=True)



def _guardar_sheets(sections: list, key: str, label: str = "☁️ Guardar en Google Sheets"):
    if st.button(label, key=key, use_container_width=True, type="primary"):
        save_and_notify(
            sections=sections,
            success_msg="✅ Guardado en Google Sheets",
        )


def _grad(index: int):
    return GRAD_COLORS[index % len(GRAD_COLORS)]


# ══════════════════════════════════════════════════════════════════════════════
# TARJETA DE VEHÍCULO
# FIX 3: solo muestra la foto de portada (primera foto), no todas.
# ══════════════════════════════════════════════════════════════════════════════
def _get_portada_url(v: dict):
    """Obtiene data URI de portada usando almacenamiento local JJGT_Media."""
    from media_sync import get_portada_data_uri
    return get_portada_data_uri(v, max_w=400)


def vehicle_card(v: dict, btn_key: str):
    c1, c2 = _grad(v.get("grad", 0))
    name    = v.get("name", "")
    model   = v.get("model", "")
    year    = v.get("year", "")
    price   = v.get("price", 0)
    city    = v.get("city", "")
    km      = v.get("km", 0)
    fuel    = v.get("fuel", "")
    rating  = v.get("rating", 0)
    tipo    = v.get("type", "venta")
    is_user = v.get("isUserPub", False)

    TIPO_LABEL = {"venta": "🏷️ Venta", "permuta": "🔄 Permuta", "ambos": "🔄 Venta+Permuta"}
    TIPO_COLOR = {"venta": "#C41E3A",   "permuta": "#00C9A7",    "ambos": "#F5A623"}
    tc = TIPO_COLOR.get(tipo, "#C41E3A")

    portada_url = _get_portada_url(v)

    with st.container(border=True):
        if portada_url:
            st.markdown(
                f'<img src="{portada_url}" style="width:100%;height:160px;'
                f'object-fit:cover;border-radius:10px;margin-bottom:4px;">',
                unsafe_allow_html=True)
        else:
            # Debug: mostrar qué tiene el vehículo para diagnosticar
            fotos_csv = (v.get("fotos_urls") or "").strip()
            fotos_mem = v.get("fotos", [])
            if fotos_csv or fotos_mem:
                import os as _os
                primera = fotos_csv.split(",")[0].strip() if fotos_csv else ""
                existe  = _os.path.isfile(primera) if primera else False
                st.caption(
                    f"📂 {primera[:60] if primera else 'sin ruta'} "
                    f"{'✅ existe' if existe else '❌ no encontrado'} "
                    f"| fotos mem: {len(fotos_mem)}")
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{c1},{c2});height:130px;'
                f'border-radius:12px;display:flex;align-items:center;'
                f'justify-content:center;font-size:40px;">🚗</div>',
                unsafe_allow_html=True)

        col_badge, col_year = st.columns([3, 1])
        with col_badge:
            st.markdown(
                f'<span style="background:{tc}22;color:{tc};font-size:10px;font-weight:700;'
                f'padding:2px 9px;border-radius:8px;">{TIPO_LABEL.get(tipo, tipo)}</span>',
                unsafe_allow_html=True)
        with col_year:
            st.markdown(
                f'<div style="text-align:right;font-size:11px;color:#9999BB;">{year}</div>',
                unsafe_allow_html=True)

        tag = " 🔴" if is_user else ""
        st.markdown(f"**{name} {model}**{tag}")
        st.caption(f"📍 {city}  ·  {km:,} km  ·  ⛽ {fuel}")

        pc, rc = st.columns([3, 2])
        with pc:
            st.markdown(
                f'<div style="font-size:20px;font-weight:800;color:#C41E3A;">'
                f'{fmt_price(price)}</div>', unsafe_allow_html=True)
        with rc:
            stars = "⭐" * int(rating) if rating else ""
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:#F5A623;padding-top:4px;">'
                f'{stars}</div>', unsafe_allow_html=True)

        if st.button("Ver detalle →", key=btn_key, use_container_width=True):
            st.session_state.selected_vehicle = v
            go("vehicle_detail")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar():
    src = st.session_state.get("_data_source", "💾 Datos locales")
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:18px 0 8px;">
            <div style="font-size:42px;font-weight:900;letter-spacing:4px;
                background:linear-gradient(135deg,#C41E3A,#F5A623);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">JJGT</div>
            <div style="font-size:10px;color:#9999BB;letter-spacing:2px;">VEHÍCULOS · COLOMBIA</div>
            <div style="font-size:10px;color:#7B9B7B;margin-top:3px;">{src}</div>
        </div>""", unsafe_allow_html=True)
        st.divider()

        if st.session_state.logged_in:
            ini = "".join(w[0].upper() for w in st.session_state.user_name.split()[:2])
            st.markdown(f"""
            <div style="text-align:center;padding:6px 0 12px;">
                <div style="width:50px;height:50px;border-radius:25px;margin:0 auto 8px;
                    background:linear-gradient(135deg,#C41E3A,#9B1729);
                    display:flex;align-items:center;justify-content:center;
                    font-size:20px;font-weight:700;color:#fff;">{ini}</div>
                <div style="font-weight:700;font-size:14px;">{st.session_state.user_name}</div>
                <div style="font-size:11px;color:#9999BB;">{st.session_state.user_email}</div>
                <span style="background:rgba(245,166,35,.15);color:#C47D00;font-size:10px;
                    font-weight:700;padding:2px 8px;border-radius:10px;margin-top:4px;display:inline-block;">
                    ⭐ {st.session_state.loyalty_level}</span>
            </div>""", unsafe_allow_html=True)
            st.divider()

        cur = st.session_state.page
        NAV = [
            ("🏠", "Inicio",         "home"),
            ("🔍", "Explorar",       "explore"),
            ("➕", "Publicar",       "publish"),
            ("📋", "Mis avisos",     "history"),
            ("🔔", "Notificaciones", "notifications"),
            ("🔄", "Permutas",       "permutas"),
            ("💬", "Soporte",        "support"),
            ("👤", "Mi perfil",      "profile"),
        ]
        for icon, label, pid in NAV:
            badge = " 🔴" if pid == "notifications" and st.session_state.notif_count > 0 else ""
            btype = "primary" if cur == pid else "secondary"
            if st.button(f"{icon} {label}{badge}", key=f"sb_{pid}",
                         use_container_width=True, type=btype):
                go(pid)

        st.divider()
        if st.session_state.logged_in:
            if st.session_state.get("user_email","").lower() == ADMIN_EMAIL.lower():
                if st.button("⚙️ Administrador", key="sb_admin", use_container_width=True, type="primary"):
                    go("admin")
            if st.button("🔄 Cambiar cuenta", key="sb_switch", use_container_width=True):
                _cambiar_cuenta()
            if st.button("🚪 Cerrar sesión", key="sb_logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_name = ""
                go("home")
        else:
            a, b = st.columns(2)
            with a:
                if st.button("Ingresar",  key="sb_login",    use_container_width=True, type="primary"):
                    go("login")
            with b:
                if st.button("Registro",  key="sb_register", use_container_width=True):
                    go("register")

        st.divider()
        src = st.session_state.get("_data_source", "⚠️ Sin fuente")
        src_color = ("#00C9A7" if "Sheets" in src
                     else "#F5A623" if "Excel" in src
                     else "#E53935")
        st.markdown(
            f'<div style="font-size:11px;font-weight:700;color:{src_color};'
            f'text-align:center;padding:4px 0 8px;">{src}</div>',
            unsafe_allow_html=True)

        # ── Sección de configuración solo para admins ──────────────────
        _es_admin = st.session_state.get("user_email","").lower() == ADMIN_EMAIL.lower()
        if _es_admin:
            with st.expander("📂 Cargar Excel (jjgt_gestion.xlsx)", expanded=False):
                st.caption("Sube un archivo .xlsx con la misma estructura del archivo jjgt_gestion.")
                uploaded = st.file_uploader(
                    "Selecciona el archivo",
                    type=["xlsx"],
                    key="sb_xlsx_upload",
                    label_visibility="collapsed",
                )
                if uploaded is not None:
                    with st.spinner("📊 Cargando datos del Excel…"):
                        ok = load_from_xlsx(uploaded.read())
                    if ok:
                        st.session_state._data_loaded = False
                        n = len(st.session_state.get("_vehicles", []))
                        st.success(f"✅ {n} vehículos cargados del Excel")
                        st.rerun()

            if st.session_state.get("_gs_client") is not None:
                if st.button("🔄 Recargar desde Sheets", key="sb_reload_sheets",
                             use_container_width=True):
                    for k in ["_data_loaded","_vehicles","_usuarios","_permutas_base",
                               "_history_base","_notifs_base","history_items",
                               "notifications","permutas"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            st.divider()
            st.markdown(
                '<div style="font-size:11px;color:#9999BB;font-weight:700;'
                'letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">'
                '💾 Guardar</div>', unsafe_allow_html=True)
            download_button_excel(
                label    = "⬇️ Exportar Excel",
                sections = None,
                key      = "sb_dl_excel",
            )
            _guardar_sheets(
                sections = None,
                key      = "sb_save_sheets",
                label    = "☁️ Guardar todo en Sheets",
            )
        else:
            if st.session_state.logged_in:
                st.caption("⚙️ Configuración disponible para administradores.")

        st.markdown(
            '<div style="text-align:center;font-size:10px;color:#9999BB;padding-top:8px;">'
            'JJGT v4.0 · Colombia 🇨🇴</div>', unsafe_allow_html=True)

        # ── Panel de diagnóstico de media (admin) ──────────────────────────
        if _es_admin:
            with st.expander("🔍 Diagnóstico de fotos", expanded=False):
                try:
                    from media_sync import _get_drive_service
                    svc = _get_drive_service()
                    if svc:
                        st.success("✅ Google Drive: conectado")
                    else:
                        st.error("❌ Google Drive: sin conexión")
                except Exception as _de:
                    st.error(f"❌ Drive error: {_de}")
                drive_errs = st.session_state.get("_drive_upload_errors", [])
                if drive_errs:
                    st.warning("⚠️ Errores subida Drive:")
                    for e in drive_errs[-3:]:
                        st.caption(e)
                pubs = st.session_state.get("user_publications", [])
                if pubs:
                    st.markdown("**Fotos en publicaciones:**")
                    for p in pubs[:5]:
                        fb = p.get("fotos_b64") or []
                        fo = p.get("fotos") or []
                        pid = p.get("id","?")
                        tipos = []
                        for r in fb:
                            if isinstance(r, str):
                                if r.startswith("gdrive:"):
                                    tipos.append("drive")
                                else:
                                    tipos.append(f"b64({len(r)}c)")
                        st.caption(f"ID:{pid} refs:{len(fb)} [{', '.join(tipos[:3])}] mem:{len(fo)}")
                else:
                    st.caption("Sin publicaciones cargadas")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ══════════════════════════════════════════════════════════════════════════════
def page_home():
    vehicles = _dedup_vehicles()

    # Mensaje de bienvenida tras login exitoso
    _wm = st.session_state.pop("_welcome_msg", None)
    if _wm:
        st.success(_wm)

    if not st.session_state.logged_in:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);border-radius:20px;
                    padding:28px;margin-bottom:18px;color:#fff;position:relative;overflow:hidden;">
            <div style="position:absolute;right:-20px;top:-20px;width:120px;height:120px;
                border-radius:60px;background:rgba(196,30,58,.2);"></div>
            <div style="font-size:11px;letter-spacing:2px;color:rgba(255,255,255,.5);
                text-transform:uppercase;margin-bottom:8px;">JJGT · VEHÍCULOS COLOMBIA</div>
            <div style="font-size:32px;font-weight:900;line-height:1.1;margin-bottom:8px;">
                🚗 Compra y vende<br>sin intermediarios</div>
            <div style="font-size:13px;color:rgba(255,255,255,.65);margin-bottom:18px;">
                Miles de vehículos · Publica gratis · Permuta sin complicaciones</div>
            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#F5A623;">15K+</div><div style="font-size:11px;opacity:.6;">Vehículos</div></div>
                <div style="width:1px;background:rgba(255,255,255,.15);"></div>
                <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#00C9A7;">8.2K</div><div style="font-size:11px;opacity:.6;">Vendedores</div></div>
                <div style="width:1px;background:rgba(255,255,255,.15);"></div>
                <div style="text-align:center;"><div style="font-size:26px;font-weight:900;color:#C41E3A;">4.8★</div><div style="font-size:11px;opacity:.6;">Rating</div></div>
                <div style="width:1px;background:rgba(255,255,255,.15);"></div>
                <div style="text-align:center;"><div style="font-size:26px;font-weight:900;">100%</div><div style="font-size:11px;opacity:.6;">Gratis</div></div>
            </div>
        </div>""", unsafe_allow_html=True)
        hc1, hc2 = st.columns(2)
        with hc1:
            if st.button("🔐 Ingresar",     key="home_login",    type="primary", use_container_width=True): go("login")
        with hc2:
            if st.button("📝 Crear cuenta", key="home_register", use_container_width=True): go("register")
    else:
        h = datetime.now().hour
        greet = "Buenos días" if h < 12 else ("Buenas tardes" if h < 18 else "Buenas noches")
        first = st.session_state.user_name.split()[0]
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:18px;
                    padding:22px 28px;margin-bottom:18px;color:#fff;">
            <div style="font-size:13px;opacity:.7;">{greet},</div>
            <div style="font-size:28px;font-weight:800;margin-top:2px;">{first} 👋</div>
            <div style="font-size:12px;opacity:.6;margin-top:4px;">
                🌟 {st.session_state.loyalty_level} · {st.session_state.loyalty_points} pts</div>
        </div>""", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    kpis = [("15,234","🚗 Vehículos","#C41E3A"),("8,241","👥 Usuarios","#00C9A7"),
            ("2,847","🔄 Permutas","#F5A623"),("4.8 ⭐","Rating","#2979FF")]
    for col, (val, lbl, col_) in zip([k1,k2,k3,k4], kpis):
        with col:
            st.markdown(f"""
            <div style="background:#fff;border-radius:14px;padding:16px;text-align:center;
                box-shadow:0 4px 20px rgba(26,26,46,.07);border:1px solid #E0E0EC;">
                <div style="font-size:26px;font-weight:800;color:{col_};">{val}</div>
                <div style="font-size:11px;color:#6B6B8A;margin-top:2px;">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("### ⚡ Acciones rápidas")
    qa = [("➕ Publicar","publish"),("🔄 Permuta","permutas"),
          ("📋 Mis avisos","history"),("💬 Soporte","support"),
          ("📝 Registro","register"),("🔍 Explorar","explore"),
          ("🔔 Alertas","notifications"),("❓ Ayuda","support")]
    for row_start in range(0, len(qa), 4):
        cols = st.columns(4)
        for i, (label, dest) in enumerate(qa[row_start:row_start+4]):
            with cols[i]:
                if st.button(label, key=f"home_qa_{row_start}_{i}", use_container_width=True):
                    go(dest)

    st.divider()
    st.markdown("### 🌟 Vehículos destacados")
    featured = vehicles[:6]
    cols = st.columns(3)
    for i, v in enumerate(featured):
        with cols[i % 3]:
            vehicle_card(v, btn_key=f"home_feat_{v.get('id', i)}_{i}")

    st.divider()
    perm_vehs = [v for v in vehicles if v.get("type") in ("permuta", "ambos")]
    if perm_vehs:
        st.markdown("### 🔄 Permutas activas")
        cols2 = st.columns(min(len(perm_vehs[:4]), 2))
        for i, v in enumerate(perm_vehs[:4]):
            with cols2[i % 2]:
                vehicle_card(v, btn_key=f"home_perm_{v.get('id', i)}_{i}")


# ── Explorar ───────────────────────────────────────────────────────────────────
def page_explore():
    _btn_inicio("explore")
    st.markdown("## 🔍 Explorar vehículos")
    vehicles = _dedup_vehicles()

    with st.expander("🎛️ Filtros avanzados", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1: cat  = st.selectbox("Categoría", ["Todos","Sedán","SUV","Pickup","Hatchback"], key="exp_cat")
        with f2: tipo = st.selectbox("Tipo",       ["Todos","Venta","Permuta","Ambos"],         key="exp_tipo")
        with f3: city = st.selectbox("Ciudad",
                     ["Todas","Bogotá","Medellín","Cali","Barranquilla","Bucaramanga","Pereira"], key="exp_city")
        p1, p2 = st.columns(2)
        with p1: pmin = st.number_input("Precio mín (M COP)", 0, 400, 0,   key="exp_pmin")
        with p2: pmax = st.number_input("Precio máx (M COP)", 0, 400, 400, key="exp_pmax")

    q = st.text_input("🔎 Buscar...", placeholder="Marca, modelo, ciudad...", key="exp_q")

    CAT_MAP  = {"Todos":"all","Sedán":"sedan","SUV":"suv","Pickup":"pickup","Hatchback":"hatchback"}
    TIPO_MAP = {"Todos":None,"Venta":"venta","Permuta":"permuta","Ambos":"ambos"}

    filtered = list(vehicles)
    if q:
        ql = q.lower()
        filtered = [v for v in filtered if ql in
            f"{v.get('name','')} {v.get('model','')} {v.get('year','')} {v.get('city','')}".lower()]
    c = CAT_MAP.get(cat, "all")
    if c != "all":
        filtered = [v for v in filtered if v.get("cat") == c]
    t = TIPO_MAP.get(tipo)
    if t:
        filtered = [v for v in filtered if v.get("type") == t]
    if city != "Todas":
        filtered = [v for v in filtered if v.get("city") == city]
    filtered = [v for v in filtered
                if pmin * 1_000_000 <= v.get("price", 0) <= pmax * 1_000_000]

    st.caption(f"{len(filtered)} vehículo(s) encontrado(s)")

    if not filtered:
        st.info("No se encontraron vehículos con esos filtros.")
        return

    cols = st.columns(3)
    for i, v in enumerate(filtered):
        with cols[i % 3]:
            vehicle_card(v, btn_key=f"exp_{v.get('id', i)}_{i}")


# ── Helper: crear notificación ─────────────────────────────────────────────────
def _add_notif(tipo: str, icon: str, title: str, desc: str,
               user: str = "", action: str = "") -> None:
    from datetime import datetime as _dt
    now = _dt.now()
    notif = {
        "id":     f"N-{int(now.timestamp()*1000)}",
        "group":  "Hoy",
        "icon":   icon,
        "tipo":   tipo,
        "title":  title,
        "desc":   desc,
        "user":   user,
        "date":   now.strftime("%d/%m/%Y"),
        "time":   now.strftime("%H:%M"),
        "unread": True,
        "action": action,
    }
    if not isinstance(st.session_state.get("notifications"), list):
        st.session_state.notifications = []
    st.session_state.notifications.insert(0, notif)
    st.session_state.notif_count = sum(
        1 for n in st.session_state.notifications if n.get("unread"))


# ── Helper: métrica HTML ────────────────────────────────────────────────────────
def _metric_card(label: str, value, color: str = "#2979FF") -> str:
    return (
        f'<div style="background:#fff;border-radius:14px;padding:16px;text-align:center;'
        f'box-shadow:0 2px 10px rgba(26,26,46,.07);border-top:3px solid {color};">'
        f'<div style="font-size:28px;font-weight:800;color:{color};">{value}</div>'
        f'<div style="font-size:12px;color:#6B6B8A;margin-top:2px;">{label}</div>'
        f'</div>'
    )


# ── Detalle de vehículo ────────────────────────────────────────────────────────
def page_vehicle_detail():
    _btn_inicio("detail")
    v = st.session_state.selected_vehicle
    if not v:
        go("explore")
        return

    v = reconstruct_media(v)

    pub_id  = v.get("id", "")
    name    = v.get("name",  "")
    model   = v.get("model", "")
    year    = v.get("year",  "")
    price   = v.get("price", 0)
    city    = v.get("city",  "")
    km      = v.get("km",    0)
    fuel    = v.get("fuel",  "")
    trans   = v.get("trans", "")
    color   = v.get("color", "")
    tipo    = v.get("type",  "venta")
    rating  = v.get("rating", 0)
    reviews = v.get("reviews", 0)
    desc    = v.get("desc",  "")
    fotos   = v.get("fotos", [])
    video   = v.get("video")
    is_user = v.get("isUserPub", False)
    seller  = v.get("seller", "—")
    s_phone = str(v.get("seller_phone", v.get("phone", ""))).strip()
    s_email = str(v.get("seller_email", "")).strip()
    c1g, c2g = _grad(v.get("grad", 0))

    if st.button("← Volver", key="det_back"):
        go("explore")

    # ═══════════════════════════════════════════════════════════════════════════
    # GALERÍA + INFO
    # ═══════════════════════════════════════════════════════════════════════════
    col_m, col_i = st.columns([1.2, 1])

    with col_m:
        # ══════════════════════════════════════════════════════════════════════
        # GALERÍA CON SLIDER (3 s auto-avance)
        # Fuente de verdad: fotos[] en RAM (cargados por _reconstruir_media_local)
        # Fallback: fotos_b64 list y session_state cache
        # ══════════════════════════════════════════════════════════════════════
        from media_sync import _b64_to_data_uri, _is_drive_ref, _file_id_from_ref, _leer_de_drive, _a_data_uri

        img_items = []

        def _ref_to_src(ref: str) -> str:
            """Convierte un ref (gdrive: o b64 puro) en data URI."""
            if not ref:
                return ""
            if _is_drive_ref(ref):
                raw = _leer_de_drive(_file_id_from_ref(ref))
                return _a_data_uri(raw, 800) if raw else ""
            return _b64_to_data_uri(ref)

        # 1. data_uri ya en memoria (fotos[] cargados por _reconstruir)
        for fi in (fotos or []):
            if not isinstance(fi, dict):
                continue
            src = fi.get("data_uri") or ""
            if not src and fi.get("bytes"):
                try:
                    from PIL import Image as _PIL
                    buf = io.BytesIO()
                    _PIL.open(io.BytesIO(fi["bytes"])).save(
                        buf, format="JPEG", quality=82)
                    import base64 as _b64m
                    src = ("data:image/jpeg;base64,"
                           + _b64m.b64encode(buf.getvalue()).decode())
                except Exception:
                    pass
            if src:
                img_items.append(src)

        # 2. fotos_b64 del dict (puede contener gdrive: refs o b64 puro)
        if not img_items:
            fotos_b64 = v.get("fotos_b64") or []
            img_items = [s for s in (_ref_to_src(r) for r in fotos_b64 if r) if s]

        # 3. session_state cache (subida reciente en esta sesion)
        if not img_items:
            for ck in ("_fotos_refs", "_fotos_b64"):
                cache = st.session_state.get(ck, {})
                refs  = cache.get(str(pub_id), [])
                if refs:
                    img_items = [s for s in (_ref_to_src(r) for r in refs if r) if s]
                    break

        if img_items:
            n_fotos = len(img_items)
            _sk = f"_slider_{pub_id}"
            if _sk not in st.session_state:
                st.session_state[_sk] = 0
            idx = st.session_state[_sk] % n_fotos

            st.markdown(
                f'<img src="{img_items[idx]}" '
                f'style="width:100%;max-height:400px;object-fit:cover;'
                f'border-radius:12px;display:block;">',
                unsafe_allow_html=True)

            if n_fotos > 1:
                sc1, sc2, sc3 = st.columns([1, 2, 1])
                with sc1:
                    if st.button("◀", key=f"sl_prev_{pub_id}",
                                 use_container_width=True):
                        st.session_state[_sk] = (idx - 1) % n_fotos
                        st.rerun()
                with sc2:
                    st.markdown(
                        f'<div style="text-align:center;font-size:12px;'
                        f'color:#9999BB;padding-top:6px;">'
                        f'📸 {idx+1} / {n_fotos}</div>',
                        unsafe_allow_html=True)
                with sc3:
                    if st.button("▶", key=f"sl_next_{pub_id}",
                                 use_container_width=True):
                        st.session_state[_sk] = (idx + 1) % n_fotos
                        st.rerun()

                th_cols = st.columns(min(n_fotos, 5))
                for ti, src in enumerate(img_items[:5]):
                    with th_cols[ti]:
                        border = ("3px solid #C41E3A" if ti == idx
                                  else "2px solid transparent")
                        st.markdown(
                            f'<img src="{src}" style="width:100%;height:60px;'
                            f'object-fit:cover;border-radius:6px;'
                            f'border:{border};">',
                            unsafe_allow_html=True)
                        if st.button("", key=f"sl_th_{pub_id}_{ti}",
                                     use_container_width=True,
                                     help=f"Foto {ti+1}"):
                            st.session_state[_sk] = ti
                            st.rerun()
        else:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{c1g},{c2g});'
                f'height:240px;border-radius:16px;display:flex;'
                f'align-items:center;justify-content:center;">'
                f'<div style="text-align:center;color:rgba(255,255,255,.7);">'
                f'<div style="font-size:56px;">🚗</div>'
                f'<div style="font-size:13px;margin-top:8px;">{name} {model}</div>'
                f'</div></div>', unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # VIDEO — bytes RAM → SQLite
        # ══════════════════════════════════════════════════════════════════════
        video_mostrado = False
        video_bytes    = video.get("bytes") if isinstance(video, dict) else None

        if not video_bytes:
            from media_sync import _is_sqlite_ref, _pub_id_from_sqlite_ref, \
                                   _leer_video_sqlite, _leer_local
            vref = (v.get("video_url") or "").strip()
            if not vref and isinstance(video, dict):
                vref = video.get("path", "")
            if vref:
                if _is_sqlite_ref(vref):
                    video_bytes, _ = _leer_video_sqlite(
                        _pub_id_from_sqlite_ref(vref))
                else:
                    video_bytes = _leer_local(vref)

        if video_bytes:
            try:
                st.video(io.BytesIO(video_bytes))
                video_mostrado = True
            except Exception:
                st.caption("⚠️ No se pudo reproducir el video.")
                video_mostrado = True

    with col_i:
        TIPO_L = {"venta": "🏷️ Venta", "permuta": "🔄 Permuta", "ambos": "🔄 Venta + Permuta"}
        TIPO_C = {"venta": "#C41E3A",  "permuta": "#00C9A7",    "ambos": "#F5A623"}
        tc = TIPO_C.get(tipo, "#C41E3A")
        st.markdown(
            f'<span style="background:{tc}22;color:{tc};font-size:12px;font-weight:700;'
            f'padding:4px 14px;border-radius:20px;">{TIPO_L.get(tipo,"")}</span>',
            unsafe_allow_html=True)
        st.markdown(f"## {name} {model}")
        st.caption(f"{year} · {city} · {km:,} km")
        st.markdown(
            f'<div style="font-size:34px;font-weight:900;color:#C41E3A;margin:8px 0;">'
            f'{fmt_price(price)}</div>', unsafe_allow_html=True)
        if rating:
            st.markdown(f"{'⭐'*int(rating)} **{rating}/5** ({reviews} reseñas)")

        st.markdown("**Especificaciones**")
        s1, s2 = st.columns(2)
        specs = [("📅 Año", year), ("📏 Km", f"{km:,}"), ("⛽ Comb.", fuel),
                 ("⚙️ Trans.", trans), ("🎨 Color", color), ("📍 Ciudad", city)]
        for idx, (lbl, val) in enumerate(specs):
            with (s1 if idx % 2 == 0 else s2):
                st.markdown(
                    f'<div style="background:#F4F5F7;border-radius:10px;padding:10px 14px;'
                    f'margin-bottom:8px;">'
                    f'<div style="font-size:11px;color:#6B6B8A;">{lbl}</div>'
                    f'<div style="font-weight:700;font-size:14px;">{val}</div></div>',
                    unsafe_allow_html=True)

    if desc:
        st.markdown("**📝 Descripción**")
        st.markdown(
            f'<div style="background:#F4F5F7;border-radius:12px;padding:16px;line-height:1.7;">'
            f'{desc}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # VENDEDOR
    # ═══════════════════════════════════════════════════════════════════════════
    st.divider()
    ini = "".join(w[0].upper() for w in seller.split()[:2]) if seller not in ("—", "") else "VD"
    st.markdown("**👤 Vendedor**")
    st.markdown(f"""
    <div style="background:#fff;border-radius:16px;padding:16px;
                box-shadow:0 4px 20px rgba(26,26,46,.08);margin-bottom:14px;">
        <div style="display:flex;gap:14px;align-items:center;">
            <div style="width:50px;height:50px;border-radius:25px;flex-shrink:0;
                background:linear-gradient(135deg,#C41E3A,#9B1729);
                display:flex;align-items:center;justify-content:center;
                font-size:18px;font-weight:700;color:#fff;">{ini}</div>
            <div style="flex:1;">
                <div style="font-weight:700;font-size:15px;">{seller}</div>
                <div style="font-size:12px;color:#6B6B8A;">📍 {city} · 📱 {s_phone}</div>
            </div>
            <span style="background:rgba(0,201,167,.12);color:#00C9A7;font-size:11px;
                font-weight:700;padding:4px 10px;border-radius:8px;">✓ Verificado</span>
        </div>
    </div>""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # BOTONES DE ACCIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    phone_clean = "".join(c for c in s_phone if c.isdigit())

    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        if st.button("💬 WhatsApp", key="det_wa", use_container_width=True, type="primary"):
            st.session_state.det_action = (None if st.session_state.det_action == "whatsapp"
                                           else "whatsapp")
            st.rerun()
    with bc2:
        if st.button("📞 Llamar", key="det_call", use_container_width=True):
            st.session_state.det_action = (None if st.session_state.det_action == "llamar"
                                           else "llamar")
            st.rerun()
    with bc3:
        tipo_label = {"permuta": "🔄 Permuta", "ambos": "🔄 Venta+Permuta"}.get(tipo, "🔄 Proponer permuta")
        if st.button(tipo_label, key="det_perm", use_container_width=True):
            if not st.session_state.logged_in:
                st.session_state.det_action = "perm_login"
            else:
                st.session_state.det_action = (None if st.session_state.det_action == "permuta"
                                               else "permuta")
            st.rerun()
    with bc4:
        if st.button("📤 Compartir", key="det_share", use_container_width=True):
            st.session_state.det_action = (None if st.session_state.det_action == "compartir"
                                           else "compartir")
            st.rerun()

    # ═══════════════════════════════════════════════════════════════════════════
    # PANELES DE ACCIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    _ok_msg = st.session_state.pop("_perm_ok", None)
    if _ok_msg:
        st.success(_ok_msg)

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    if st.session_state.det_action == "whatsapp":
        with st.container(border=True):
            st.markdown("### 💬 Contactar por WhatsApp")
            wa_default = (f"Hola {seller}, vi tu {name} {model} {year} en JJGT "
                          f"por {fmt_price(price)} y me interesa. ¿Está disponible?")
            wa_msg = st.text_area("Mensaje (editable)", value=wa_default,
                                  height=90, key="det_wa_msg")
            wa_url = (f"https://wa.me/57{phone_clean}"
                      f"?text={wa_msg.replace(' ','%20').replace(chr(10),'%0A')}")
            col_wa1, col_wa2 = st.columns(2)
            with col_wa1:
                st.link_button("💬 Abrir WhatsApp", wa_url,
                               use_container_width=True, type="primary")
            with col_wa2:
                if st.button("✖ Cerrar", key="det_wa_cancel", use_container_width=True):
                    st.session_state.det_action = None
                    st.rerun()
            st.caption("Se abrirá WhatsApp Web o la app en tu dispositivo.")

    # ── Llamar ────────────────────────────────────────────────────────────────
    elif st.session_state.det_action == "llamar":
        with st.container(border=True):
            st.markdown("### 📞 Contactar por llamada")
            st.markdown(f"""
            <div style="background:#F4F5F7;border-radius:14px;padding:22px;text-align:center;">
                <div style="font-size:44px;margin-bottom:10px;">📱</div>
                <div style="font-size:24px;font-weight:800;color:#1A1A2E;letter-spacing:3px;">
                    {s_phone}</div>
                <div style="font-size:13px;color:#6B6B8A;margin-top:6px;">{seller}</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("")
            cll1, cll2 = st.columns(2)
            with cll1:
                if s_phone:
                    st.link_button(f"📞 Llamar ahora", f"tel:+57{phone_clean}",
                                   use_container_width=True, type="primary")
            with cll2:
                if st.button("✖ Cerrar", key="det_call_cancel", use_container_width=True):
                    st.session_state.det_action = None
                    st.rerun()
            if s_email:
                st.caption(f"✉️ Correo: {s_email}")

    # ── Permuta — sin sesión ──────────────────────────────────────────────────
    elif st.session_state.det_action == "perm_login":
        with st.container(border=True):
            st.warning("🔐 Debes iniciar sesión para proponer o gestionar permutas.")
            pl1, pl2 = st.columns(2)
            with pl1:
                if st.button("🔐 Iniciar sesión", key="det_perm_login",
                             use_container_width=True, type="primary"):
                    go("login")
            with pl2:
                if st.button("✖ Cerrar", key="det_perm_login_cancel",
                             use_container_width=True):
                    st.session_state.det_action = None
                    st.rerun()

    # ── Permuta — con sesión ──────────────────────────────────────────────────
    elif st.session_state.det_action == "permuta":
        with st.container(border=True):
            st.markdown("### 🔄 Proponer Permuta")

            propuestas_recibidas = [
                p for p in (st.session_state.permutas or [])
                if f"{name} {model}" in p.get("veh_destino", "")
                and p.get("propietario", "") == seller
            ]

            if is_user and propuestas_recibidas:
                EC = {"Activa":"#00C9A7","Contraoferta":"#F5A623",
                      "Aceptada":"#2979FF","Rechazada":"#E53935","Pendiente":"#9999BB"}
                with st.expander(f"📥 Propuestas recibidas ({len(propuestas_recibidas)})", expanded=True):
                    for pi, p in enumerate(propuestas_recibidas):
                        ec     = EC.get(p.get("estado","Activa"), "#6B6B8A")
                        pid_p  = str(p.get("id","")).replace("-","_").replace(".","_")
                        estado = p.get("estado","Activa")
                        with st.container(border=True):
                            pr1, pr2 = st.columns([4,1])
                            with pr1:
                                st.markdown(
                                    f"**🚗 {p.get('veh_oferta','')}** · "
                                    f"{p.get('km_oferta',0):,} km · "
                                    f"{p.get('color_oferta','')} · "
                                    f"{p.get('estado_oferta','')}")
                                st.caption(
                                    f"👤 {p.get('vendedor_oferta','—')} · "
                                    f"📱 {p.get('phone_oferta','')} · "
                                    f"📍 {p.get('ciudad','')} · 📅 {p.get('fecha','')}")
                                st.markdown(
                                    f'💰 Ofrece **{fmt_price(p.get("valor_oferta",0))}** '
                                    f'· Diferencia: **{fmt_price(p.get("diferencia",0))}**')
                                if p.get("mensaje"):
                                    st.caption(f'💬 "{p["mensaje"]}"')
                            with pr2:
                                st.markdown(
                                    f'<div style="background:{ec}22;color:{ec};'
                                    f'font-size:11px;font-weight:700;padding:4px 10px;'
                                    f'border-radius:8px;text-align:center;">{estado}</div>',
                                    unsafe_allow_html=True)
                            if estado == "Activa":
                                ba1, ba2, ba3 = st.columns(3)
                                with ba1:
                                    if st.button("✅ Aceptar", key=f"pacp_{pi}_{pid_p}",
                                                 use_container_width=True, type="primary"):
                                        p["estado"] = "Aceptada"; p["resultado"] = "Aceptada"
                                        _add_notif("Permuta","✅",
                                            f"Permuta aceptada: {p.get('veh_oferta','')}",
                                            f"{seller} aceptó tu propuesta. Tel: {s_phone}",
                                            user=p.get("vendedor_oferta",""), action="Ver permutas")
                                        save_section_silent(["permutas","notificaciones"])
                                        st.success("✅ Aceptada · Proponente notificado")
                                        st.rerun()
                                with ba2:
                                    if st.button("❌ Rechazar", key=f"prch_{pi}_{pid_p}",
                                                 use_container_width=True):
                                        p["estado"] = "Rechazada"; p["resultado"] = "Rechazada"
                                        _add_notif("Permuta","❌",
                                            f"Permuta rechazada: {p.get('veh_oferta','')}",
                                            f"{seller} no aceptó la propuesta.",
                                            user=p.get("vendedor_oferta",""), action="Ver permutas")
                                        save_section_silent(["permutas","notificaciones"])
                                        st.rerun()
                                with ba3:
                                    if st.button("↩️ Contraofertar", key=f"pco_{pi}_{pid_p}",
                                                 use_container_width=True):
                                        st.session_state[f"co_open_{pid_p}"] = True
                                        st.rerun()
                                if st.session_state.get(f"co_open_{pid_p}"):
                                    with st.form(f"fco_{pid_p}"):
                                        co_dif = st.number_input("Nueva diferencia (COP)",
                                            min_value=0, step=500_000, format="%d")
                                        co_msg = st.text_area("Mensaje", height=60)
                                        if st.form_submit_button("📤 Enviar", use_container_width=True, type="primary"):
                                            p["estado"]="Contraoferta"; p["diferencia"]=int(co_dif)
                                            p["mensaje"]=co_msg.strip() or p.get("mensaje","")
                                            _add_notif("Permuta","↩️",
                                                f"Contraoferta: {p.get('veh_oferta','')}",
                                                f"{seller} propone diferencia {fmt_price(int(co_dif))}.",
                                                user=p.get("vendedor_oferta",""), action="Ver permutas")
                                            save_section_silent(["permutas","notificaciones"])
                                            st.session_state.pop(f"co_open_{pid_p}", None)
                                            st.success("↩️ Contraoferta enviada"); st.rerun()

                st.divider()

            st.markdown(
                f'<div style="background:rgba(0,201,167,.08);border-radius:10px;'
                f'padding:12px 16px;margin-bottom:14px;font-size:13px;">'
                f'Propones cambiar tu vehículo por: '
                f'<strong>{name} {model} {year}</strong>'
                f' &nbsp;·&nbsp; {fmt_price(price)}</div>',
                unsafe_allow_html=True)

            with st.form("form_permuta_det"):
                fp1, fp2 = st.columns(2)
                with fp1:
                    mi_veh = st.text_input(
                        "Mi vehículo (marca · modelo · año) *",
                        placeholder="Ej: Chevrolet Onix 2021")
                    mi_valor = st.number_input(
                        "Valor estimado (COP) *",
                        min_value=0, step=1_000_000, format="%d")
                    mi_km = st.number_input(
                        "Kilómetros", min_value=0, step=1000)
                with fp2:
                    mi_ciudad = st.selectbox(
                        "Ciudad",
                        ["Bogotá","Medellín","Cali","Barranquilla",
                         "Bucaramanga","Pereira","Cartagena"])
                    mi_color = st.text_input("Color", placeholder="Blanco, Gris…")
                    mi_estado_veh = st.selectbox(
                        "Estado",
                        ["Excelente","Bueno","Regular","Necesita revisión"])
                mi_phone = st.text_input(
                    "Tu celular *",
                    value=st.session_state.get("user_phone",""))
                mi_mensaje = st.text_area(
                    "Mensaje al vendedor",
                    placeholder="Describe extras, historial, motivo del cambio…",
                    height=80)

                sub_perm = st.form_submit_button(
                    "📤 Enviar propuesta de permuta",
                    use_container_width=True, type="primary")

                if sub_perm:
                    err = []
                    if not mi_veh.strip():   err.append("vehículo")
                    if mi_valor <= 0:        err.append("valor estimado")
                    if not mi_phone.strip(): err.append("celular")
                    if err:
                        st.error(f"❌ Completa: {', '.join(err)}")
                    else:
                        dif_final  = price - mi_valor
                        nueva_perm = {
                            "id":              f"P-{int(datetime.now().timestamp())}",
                            "veh_oferta":      mi_veh.strip(),
                            "vendedor_oferta": st.session_state.user_name,
                            "veh_destino":     f"{name} {model} {year}",
                            "propietario":     seller,
                            "ciudad":          mi_ciudad,
                            "valor_oferta":    int(mi_valor),
                            "diferencia":      abs(int(dif_final)),
                            "fecha":           datetime.now().strftime("%d/%m/%Y"),
                            "estado":          "Activa",
                            "resultado":       "Pendiente",
                            "mensaje":         mi_mensaje.strip() or "Sin mensaje.",
                            "km_oferta":       int(mi_km),
                            "color_oferta":    mi_color.strip(),
                            "estado_oferta":   mi_estado_veh,
                            "phone_oferta":    mi_phone.strip(),
                        }
                        st.session_state.permutas.insert(0, nueva_perm)
                        _add_notif("Permuta","🔄",
                            f"Permuta enviada — {name} {model}",
                            f"Propuesta enviada a {seller}. Recibirás respuesta pronto.",
                            user=st.session_state.user_name, action="Ver permutas")
                        _add_notif("Permuta","📥",
                            f"Nueva propuesta para {name} {model}",
                            f"{st.session_state.user_name} ofrece {mi_veh} "
                            f"por {fmt_price(int(mi_valor))}.",
                            user=seller, action="Ver permuta")
                        save_section_silent(["permutas","notificaciones"])

                        # ── FIX 4: Correo automático ───────────────────────
                        try:
                            emails_destino = []
                            if s_email:
                                emails_destino.append(s_email)
                            if st.session_state.get("user_email"):
                                emails_destino.append(st.session_state.user_email)

                            if emails_destino:
                                send_permuta_email(
                                    destinatarios=emails_destino,
                                    propuesta={
                                        "id":         nueva_perm["id"],
                                        "fecha":      nueva_perm["fecha"],
                                        "diferencia": nueva_perm["diferencia"],
                                        "notas":      mi_mensaje.strip(),
                                    },
                                    vehiculo_ofrecido={
                                        "marca":      mi_veh.strip(),
                                        "modelo":     "",
                                        "año":        "",
                                        "placa":      "—",
                                        "precio":     int(mi_valor),
                                        "fotos_urls": "",
                                    },
                                    vehiculo_deseado={
                                        "marca":      name,
                                        "modelo":     model,
                                        "año":        str(year),
                                        "placa":      "—",
                                        "precio":     price,
                                        "fotos_urls": v.get("fotos_urls", ""),
                                    },
                                )
                        except Exception:
                            pass  # El correo no debe bloquear la propuesta
                        # ──────────────────────────────────────────────────

                        st.session_state._perm_ok = (
                            f"✅ Propuesta enviada a {seller}. "
                            f"Diferencia: {fmt_price(abs(int(dif_final)))}.")
                        st.session_state.det_action = None
                        st.rerun()

            if st.button("✖ Cerrar", key="det_perm_cancel", use_container_width=True):
                st.session_state.det_action = None
                st.rerun()

    # ── Compartir ─────────────────────────────────────────────────────────────
    elif st.session_state.det_action == "compartir":
        import urllib.parse as _up
        with st.container(border=True):
            st.markdown("### 📤 Compartir vehículo")

            share_title = f"{name} {model} {year} — JJGT Vehículos Colombia"
            share_body  = (f"{name} {model} {year} · {fmt_price(price)} · "
                           f"{km:,} km · {city} · {fuel}\n"
                           f"Publica y vende sin intermediarios en JJGT 🚗🇨🇴")
            share_url   = "https://jjgt-autos.streamlit.app/"

            t_enc  = _up.quote(share_body + "\n" + share_url)
            ti_enc = _up.quote(share_title)
            u_enc  = _up.quote(share_url)

            st.markdown("**📋 Texto del aviso**")
            st.code(share_body, language=None)

            st.markdown("**🌐 Compartir en:**")
            REDES = [
                ("💬 WhatsApp",  f"https://wa.me/?text={t_enc}", "#25D366"),
                ("📘 Facebook",  f"https://www.facebook.com/sharer/sharer.php?u={u_enc}&quote={ti_enc}", "#1877F2"),
                ("🐦 X / Twitter", f"https://twitter.com/intent/tweet?text={t_enc}", "#1DA1F2"),
                ("✈️ Telegram",  f"https://t.me/share/url?url={u_enc}&text={t_enc}", "#2AABEE"),
                ("💼 LinkedIn",  f"https://www.linkedin.com/sharing/share-offsite/?url={u_enc}", "#0A66C2"),
                ("✉️ Email",     f"mailto:?subject={ti_enc}&body={t_enc}", "#C41E3A"),
            ]

            sh1, sh2, sh3 = st.columns(3)
            for col, (lbl, url_r, _c) in zip([sh1, sh2, sh3], REDES[:3]):
                with col:
                    st.link_button(lbl, url_r, use_container_width=True)

            sh4, sh5, sh6 = st.columns(3)
            for col, (lbl, url_r, _c) in zip([sh4, sh5, sh6], REDES[3:]):
                with col:
                    st.link_button(lbl, url_r, use_container_width=True)

            st.divider()

            with st.expander("📹 ¿Cómo compartir en YouTube?"):
                yt_desc = (
                    f"{share_title}\n"
                    f"Precio: {fmt_price(price)} · {km:,} km · {city}\n"
                    f"Contacto: {s_phone}\n"
                    f"Publicado en: {share_url}")
                st.markdown(
                    "YouTube no tiene enlace directo de compartir. Para publicar:\n\n"
                    "1. Descarga el video del vehículo desde el aviso.\n"
                    "2. Súbelo a tu canal de YouTube.\n"
                    "3. Copia esta descripción:")
                st.code(yt_desc, language=None)

            with st.expander("📱 Código QR para compartir en persona"):
                qr_url = (f"https://api.qrserver.com/v1/create-qr-code/"
                          f"?size=220x220&data={u_enc}&color=1A1A2E")
                qc1, qc2 = st.columns([1, 2])
                with qc1:
                    st.image(qr_url, width=200, caption="Escanea para ver el aviso")
                with qc2:
                    st.markdown(
                        "**Úsalo para:**\n"
                        "- Imprimir en volantes o tarjetas\n"
                        "- Mostrar en ferias de autos\n"
                        "- Compartir en reuniones\n\n"
                        "Apunta la cámara del celular al QR para abrir el aviso.")

            if st.button("✖ Cerrar", key="det_share_close", use_container_width=True):
                st.session_state.det_action = None
                st.rerun()

    # ═══════════════════════════════════════════════════════════════════════════
    # GESTIÓN DEL DUEÑO
    # ═══════════════════════════════════════════════════════════════════════════
    if is_user and st.session_state.logged_in:
        st.divider()
        st.markdown("**🔧 Gestionar mi publicación**")
        mc1, mc2, mc3 = st.columns(3)

        with mc1:
            if st.button("✏️ Editar", key="det_edit",
                         use_container_width=True, type="primary"):
                st.session_state.det_edit_mode   = not st.session_state.det_edit_mode
                st.session_state.det_confirm_del = False
                st.rerun()

        with mc2:
            if not st.session_state.det_confirm_del:
                if st.button("🗑️ Eliminar", key="det_del", use_container_width=True):
                    st.session_state.det_confirm_del = True
                    st.session_state.det_edit_mode   = False
                    st.rerun()
            else:
                st.error("¿Confirmas eliminar esta publicación?")
                cd1, cd2 = st.columns(2)
                with cd1:
                    if st.button("✅ Sí, eliminar", key="det_del_confirm",
                                 use_container_width=True, type="primary"):
                        st.session_state.user_publications = [
                            p for p in st.session_state.user_publications
                            if p.get("id") != pub_id]
                        st.session_state.history_items = [
                            h for h in st.session_state.history_items
                            if h.get("id") != pub_id]
                        ok = save_section_silent(["publicaciones","historial","vehiculos"])
                        st.success("✅ Eliminada" + (" · ☁️ Sheets" if ok else ""))
                        st.session_state.det_confirm_del = False
                        st.session_state.selected_vehicle = None
                        go("history")
                with cd2:
                    if st.button("❌ No, cancelar", key="det_del_cancel",
                                 use_container_width=True):
                        st.session_state.det_confirm_del = False
                        st.rerun()

        with mc3:
            estado_actual = v.get("estado", "Activo")
            estado_opts   = ["Activo","Pendiente","Completado","Cancelado"]
            nuevo_estado  = st.selectbox(
                "Estado", estado_opts,
                index=estado_opts.index(estado_actual)
                      if estado_actual in estado_opts else 0,
                key="det_estado_sel")
            if nuevo_estado != estado_actual:
                for p in st.session_state.user_publications:
                    if p.get("id") == pub_id:
                        p["estado"] = nuevo_estado
                for h in st.session_state.history_items:
                    if h.get("id") == pub_id:
                        h["status"] = nuevo_estado.lower()
                save_section_silent(["publicaciones","historial"])
                st.toast(f"✅ Estado: {nuevo_estado}")
                st.rerun()

        if st.session_state.det_edit_mode:
            st.markdown("---")
            st.markdown("#### ✏️ Editar publicación")

            from media_sync import (
                _b64_to_data_uri, _foto_a_b64,
                _is_sqlite_ref, _pub_id_from_sqlite_ref,
                _leer_video_sqlite, _guardar_video_sqlite,
            )

            ANIOS = ["2025","2024","2023","2022","2021","2020","2019","2018","2017",
                     "2015","2014","2013","2012","2011","2010","2009","2008","2007",
                     "2006","2005","2004","2003","2002","2001","2000","1999","1998",
                     "1997","1996","1995","1994","1993","1992","1991","1990","1989",
                     "1988","1987","1986","1985","1984","1983","1982","1981","1980"]
            MARCAS   = ["Toyota","Chevrolet","Renault","Mazda","Hyundai","Kia","Ford",
                        "Hummer","Audi","Volkswagen","BMW","Mercedes-Benz","Nissan",
                        "Honda","Suzuki","Jeep"]
            FUELS    = ["Gasolina","Diesel","Híbrido","Eléctrico","Gas"]
            CIUDADES = ["Bogotá","Medellín","Cali","Barranquilla",
                        "Bucaramanga","Pereira","Cartagena"]

            def _idx(lst, val, default=0):
                return lst.index(str(val)) if str(val) in lst else default

            def _sync_fotos_b64(nueva_lista: list):
                """Actualiza fotos_b64 en todos los dicts y Sheets."""
                uris = [_b64_to_data_uri(b) for b in nueva_lista if b]
                fotos_mem = [{"name": f"foto_{i+1}.jpg", "bytes": None,
                              "path": f"b64_col_{i+1}", "data_uri": uri}
                             for i, uri in enumerate(uris)]
                v["fotos_b64"] = nueva_lista
                v["fotos"]     = fotos_mem
                for p in st.session_state.user_publications:
                    if str(p.get("id","")) == str(pub_id):
                        p["fotos_b64"] = nueva_lista
                        p["fotos"]     = fotos_mem
                for h in st.session_state.history_items:
                    if str(h.get("id","")) == str(pub_id) and h.get("pubRef"):
                        h["pubRef"]["fotos_b64"] = nueva_lista
                        h["pubRef"]["fotos"]     = fotos_mem
                # Actualizar cache de sesión
                st.session_state.setdefault("_fotos_b64", {})[str(pub_id)] = nueva_lista
                st.session_state.selected_vehicle = v
                save_section_silent(["publicaciones", "vehiculos"])

            def _sync_video(nuevo_ref: str, nuevo_bytes=None):
                """Actualiza video_url en todos los dicts y Sheets."""
                video_dict = ({"name": "video.mp4", "bytes": nuevo_bytes,
                               "path": nuevo_ref} if nuevo_bytes else None)
                v["video_url"] = nuevo_ref
                v["video"]     = video_dict
                for p in st.session_state.user_publications:
                    if str(p.get("id","")) == str(pub_id):
                        p["video_url"] = nuevo_ref
                        p["video"]     = video_dict
                for h in st.session_state.history_items:
                    if str(h.get("id","")) == str(pub_id) and h.get("pubRef"):
                        h["pubRef"]["video_url"] = nuevo_ref
                        h["pubRef"]["video"]     = video_dict
                st.session_state.selected_vehicle = v
                save_section_silent(["publicaciones", "vehiculos"])

            # ── FOTOS ACTUALES ────────────────────────────────────────────────
            st.markdown("##### 📸 Fotos actuales")
            fotos_b64_cur = list(v.get("fotos_b64") or [])

            if fotos_b64_cur:
                cols_f = st.columns(min(len(fotos_b64_cur), 5))
                for fi, b64 in enumerate(fotos_b64_cur):
                    with cols_f[fi % 5]:
                        uri = _b64_to_data_uri(b64)
                        border = "3px solid #F5A623" if fi == 0 else "2px solid #333"
                        if uri:
                            st.markdown(
                                f'<img src="{uri}" style="width:100%;height:75px;'
                                f'object-fit:cover;border-radius:8px;'
                                f'border:{border};margin-bottom:3px;">',
                                unsafe_allow_html=True)
                        else:
                            st.markdown("🖼️")
                        st.caption("📌 Portada" if fi == 0 else f"Foto {fi+1}")
                        if fi > 0:
                            if st.button("⭐", key=f"portada_{pub_id}_{fi}",
                                         use_container_width=True,
                                         help="Hacer portada"):
                                nuevo = ([fotos_b64_cur[fi]]
                                         + fotos_b64_cur[:fi]
                                         + fotos_b64_cur[fi+1:])
                                _sync_fotos_b64(nuevo)
                                st.rerun()
                        mc1, mc2 = st.columns(2)
                        with mc1:
                            if fi > 0:
                                if st.button("◀", key=f"izq_{pub_id}_{fi}",
                                             use_container_width=True):
                                    nuevo = list(fotos_b64_cur)
                                    nuevo[fi-1], nuevo[fi] = nuevo[fi], nuevo[fi-1]
                                    _sync_fotos_b64(nuevo)
                                    st.rerun()
                            else:
                                st.write("")
                        with mc2:
                            if fi < len(fotos_b64_cur) - 1:
                                if st.button("▶", key=f"der_{pub_id}_{fi}",
                                             use_container_width=True):
                                    nuevo = list(fotos_b64_cur)
                                    nuevo[fi], nuevo[fi+1] = nuevo[fi+1], nuevo[fi]
                                    _sync_fotos_b64(nuevo)
                                    st.rerun()
                            else:
                                st.write("")
                        if st.button("❌", key=f"del_foto_{pub_id}_{fi}",
                                     use_container_width=True, help="Eliminar"):
                            nuevo = [b for j, b in enumerate(fotos_b64_cur) if j != fi]
                            _sync_fotos_b64(nuevo)
                            st.rerun()
            else:
                st.caption("Sin fotos cargadas.")

            nuevas_fotos = st.file_uploader(
                "➕ Agregar fotos (jpg, png, webp)",
                type=["jpg","jpeg","png","webp"],
                accept_multiple_files=True,
                key=f"edit_fotos_{pub_id}",
            )
            if nuevas_fotos:
                if st.button("📤 Guardar fotos", key=f"btn_fotos_{pub_id}",
                             type="primary"):
                    with st.spinner("Procesando fotos…"):
                        nuevas_b64 = []
                        for ff in nuevas_fotos[:10]:
                            ff.seek(0)
                            b64 = _foto_a_b64(ff.read(), max_w=700)
                            if b64:
                                nuevas_b64.append(b64)
                        if nuevas_b64:
                            merged = fotos_b64_cur + nuevas_b64
                            _sync_fotos_b64(merged[:10])
                            st.success(f"✅ {len(nuevas_b64)} foto(s) agregada(s)")
                            st.rerun()
                        else:
                            st.warning("⚠️ No se pudieron procesar las fotos")

            st.divider()

            # ── VIDEO ─────────────────────────────────────────────────────────
            st.markdown("##### 🎥 Video actual")
            video_ref_cur = (v.get("video_url") or "").strip()

            if video_ref_cur:
                # Intentar mostrar el video
                vbytes = None
                if _is_sqlite_ref(video_ref_cur):
                    vbytes, _ = _leer_video_sqlite(
                        _pub_id_from_sqlite_ref(video_ref_cur))
                if vbytes:
                    try:
                        st.video(io.BytesIO(vbytes))
                    except Exception:
                        st.caption(f"📁 Video guardado ({video_ref_cur})")
                else:
                    st.caption(f"📁 {video_ref_cur} (sesión anterior — re-subir para ver)")

                if st.button("❌ Eliminar video", key=f"del_video_{pub_id}",
                             type="secondary"):
                    _sync_video("")
                    st.success("✅ Video eliminado")
                    st.rerun()
            else:
                st.caption("Sin video cargado.")

            nuevo_video = st.file_uploader(
                "➕ Subir video (mp4, mov, avi, webm)",
                type=["mp4","mov","avi","webm"],
                key=f"edit_video_{pub_id}",
            )
            if nuevo_video:
                if st.button("📤 Guardar video", key=f"btn_video_{pub_id}",
                             type="primary"):
                    with st.spinner("Guardando video en SQLite…"):
                        try:
                            nuevo_video.seek(0)
                            vdata   = nuevo_video.read()
                            vnombre = f"video_{nuevo_video.name}"
                            nueva_ref = _guardar_video_sqlite(str(pub_id), vnombre, vdata)
                            if nueva_ref:
                                _sync_video(nueva_ref, vdata)
                                st.success("✅ Video guardado")
                                st.rerun()
                            else:
                                st.warning("⚠️ No se pudo guardar el video")
                        except Exception as _ev:
                            st.error(f"Error: {_ev}")

            st.divider()

            # ── DATOS DEL VEHÍCULO ────────────────────────────────────────────
            st.markdown("##### 📋 Datos del vehículo")
            with st.form("form_edit_pub"):
                ee1, ee2 = st.columns(2)
                with ee1:
                    e_marca  = st.selectbox("Marca", MARCAS,
                                            index=_idx(MARCAS, name), key="de_marca")
                    e_modelo = st.text_input("Modelo", value=model, key="de_modelo")
                    e_anio   = st.selectbox("Año", ANIOS,
                                            index=_idx(ANIOS, str(year)), key="de_anio")
                    e_km     = st.number_input("Km", value=int(km),
                                               min_value=0, step=1000, key="de_km")
                    e_precio = st.number_input("Precio (COP)", value=int(price),
                                               min_value=0, step=1_000_000,
                                               format="%d", key="de_precio")
                with ee2:
                    e_comb   = st.selectbox("Combustible", FUELS,
                                            index=_idx(FUELS, fuel), key="de_comb")
                    e_trans  = st.selectbox("Transmisión", ["Automático","Manual"],
                                            index=0 if trans == "Automático" else 1,
                                            key="de_trans")
                    e_color  = st.text_input("Color", value=color, key="de_color")
                    e_ciudad = st.selectbox("Ciudad", CIUDADES,
                                            index=_idx(CIUDADES, city), key="de_ciudad")
                e_tipo  = st.selectbox("Tipo aviso",
                                       ["Venta","Permuta","Venta y Permuta"],
                                       index={"venta":0,"permuta":1,"ambos":2}.get(tipo,0),
                                       key="de_tipo")
                e_desc  = st.text_area("Descripción", value=desc,
                                       height=90, key="de_desc")
                e_phone = st.text_input("Celular", value=s_phone, key="de_phone")

                if st.form_submit_button("💾 Guardar cambios",
                                         use_container_width=True, type="primary"):
                    TIPO2 = {"Venta":"venta","Permuta":"permuta","Venta y Permuta":"ambos"}
                    cambios = {
                        "name":         e_marca,
                        "model":        e_modelo.strip(),
                        "year":         int(e_anio),
                        "km":           int(e_km),
                        "price":        int(e_precio),
                        "fuel":         e_comb,
                        "trans":        e_trans,
                        "color":        e_color.strip() or "—",
                        "city":         e_ciudad,
                        "type":         TIPO2.get(e_tipo, "venta"),
                        "desc":         e_desc.strip(),
                        "phone":        e_phone.strip(),
                        "seller_phone": e_phone.strip(),
                    }
                    for p in st.session_state.user_publications:
                        if str(p.get("id","")) == str(pub_id):
                            p.update(cambios)
                    for h in st.session_state.history_items:
                        if str(h.get("id","")) == str(pub_id) and h.get("pubRef"):
                            h["pubRef"].update(cambios)
                    v.update(cambios)
                    st.session_state.selected_vehicle = v
                    ok = save_section_silent(["publicaciones","historial","vehiculos"])
                    st.success("✅ Cambios guardados" + (" · ☁️" if ok else ""))
                    st.session_state.det_edit_mode = False
                    st.rerun()

            if st.button("Cancelar edición", key="det_edit_cancel",
                         use_container_width=True):
                st.session_state.det_edit_mode = False
                st.rerun()

    # ═══════════════════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════════════════
    # RESEÑAS REALES
    # ═══════════════════════════════════════════════════════════════════════════
    st.divider()
    pub_id   = str(v.get("id",""))
    vendedor = v.get("seller","")
    resenas  = [r for r in st.session_state.get("resenas",[])
                if str(r.get("pub_id","")) == pub_id]

    ra, rb = st.columns([3,2])
    with ra:
        st.markdown("**⭐ Reseñas del vendedor**")
    with rb:
        if st.session_state.logged_in:
            if st.button("✍️ Escribir reseña", key=f"btn_resena_{pub_id}", use_container_width=True):
                st.session_state["_writing_resena"] = pub_id

    if not resenas:
        st.caption("Sin reseñas aún. ¡Sé el primero en calificar!")
    else:
        avg = sum(r.get("rating",0) for r in resenas) / len(resenas)
        st.caption(f"{'⭐'*round(avg)}  {avg:.1f}/5 · {len(resenas)} reseña{'s' if len(resenas)!=1 else ''}")
        for r in resenas:
            ri = "".join(w[0].upper() for w in str(r.get("autor","?")).split()[:2])
            st.markdown(f"""
            <div style="display:flex;gap:12px;margin-bottom:10px;padding:14px;
                        background:#F4F5F7;border-radius:12px;">
                <div style="width:36px;height:36px;border-radius:18px;flex-shrink:0;
                    background:linear-gradient(135deg,#C41E3A,#1A1A2E);
                    display:flex;align-items:center;justify-content:center;
                    font-size:13px;font-weight:700;color:#fff;">{ri}</div>
                <div style="flex:1;">
                    <div style="font-weight:700;font-size:13px;">{r.get("autor","")}</div>
                    <div>{"⭐"*int(r.get("rating",0))}</div>
                    <div style="font-size:13px;color:#6B6B8A;">{r.get("comentario","")}</div>
                    <div style="font-size:11px;color:#ADADCA;margin-top:4px;">
                        {r.get("fecha","")}</div>
                </div>
            </div>""", unsafe_allow_html=True)

    # Formulario nueva reseña
    if st.session_state.get("_writing_resena") == pub_id:
        with st.form(key=f"form_resena_{pub_id}"):
            st.markdown("#### ✍️ Tu reseña")
            rat_str = st.select_slider("Calificación",
                options=["⭐ (1)","⭐⭐ (2)","⭐⭐⭐ (3)","⭐⭐⭐⭐ (4)","⭐⭐⭐⭐⭐ (5)"],
                value="⭐⭐⭐⭐⭐ (5)", key=f"rat_slider_{pub_id}")
            rat_val = int(rat_str.count("⭐"))
            comentario = st.text_area("Comentario", placeholder="Describe tu experiencia con este vendedor...", height=80, key=f"res_coment_{pub_id}")
            r1, r2 = st.columns(2)
            with r1: enviar  = st.form_submit_button("📤 Publicar reseña", type="primary", use_container_width=True)
            with r2: cancelar= st.form_submit_button("❌ Cancelar", use_container_width=True)
            if enviar:
                if not comentario.strip():
                    st.error("Escribe un comentario")
                else:
                    nueva = {
                        "id":          f"RES-{int(datetime.now().timestamp())}",
                        "pub_id":      pub_id,
                        "vehiculo":    f"{v.get('name','')} {v.get('model','')} {v.get('year','')}".strip(),
                        "vendedor":    vendedor,
                        "autor":       st.session_state.user_name,
                        "rating":      rat_val,
                        "comentario":  comentario.strip(),
                        "fecha":       datetime.now().strftime("%d/%m/%Y"),
                        "verificada":  True,
                    }
                    if "resenas" not in st.session_state:
                        st.session_state.resenas = []
                    st.session_state.resenas.append(nueva)
                    # Actualizar rating promedio del vehículo
                    todas = [r for r in st.session_state.resenas if str(r.get("pub_id","")) == pub_id]
                    nuevo_avg = round(sum(r.get("rating",0) for r in todas) / len(todas), 1)
                    v["rating"]  = nuevo_avg
                    v["reviews"] = len(todas)
                    save_section_silent(["resenas","vehiculos","publicaciones"])
                    st.session_state["_writing_resena"] = None
                    st.success("✅ Reseña publicada")
                    st.rerun()
            if cancelar:
                st.session_state["_writing_resena"] = None
                st.rerun()


# ── Publicar ───────────────────────────────────────────────────────────────────
def page_publish():
    _btn_inicio("publish")
    st.markdown("## ➕ Publicar vehículo")
    if not st.session_state.logged_in:
        st.warning("⚠️ Debes iniciar sesión para publicar.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔐 Ingresar",     key="pub_login",    type="primary", use_container_width=True): go("login")
        with c2:
            if st.button("📝 Registrarme",  key="pub_register", use_container_width=True): go("register")
        return

    _pending = st.session_state.pop("_pub_pending", None)
    if _pending:
        new_id     = _pending["new_id"]
        fotos_data = st.session_state.pop("_pub_fotos_data", [])
        video_data = st.session_state.pop("_pub_video_data", None)
        TIPO_MAP   = {"Venta":"venta","Permuta":"permuta","Venta y Permuta":"ambos"}

        fotos_b64_list = []
        video_ref      = ""
        with st.spinner("💾 Guardando fotos y video…"):
            try:
                from media_sync import upload_media
                fotos_b64_list, video_ref = upload_media(new_id, fotos_data, video_data)
            except Exception as e_media:
                st.warning(f"⚠️ No se pudieron guardar las fotos: {e_media}")

        new_pub = {
            "id":           new_id,
            "name":         _pending["pub_marca"],
            "model":        _pending["pub_modelo"],
            "year":         int(_pending["pub_anio"]),
            "price":        _pending.get("pub_precio", 0),
            "km":           _pending["pub_km"],
            "fuel":         _pending["pub_comb"],
            "trans":        _pending["pub_trans"],
            "city":         _pending["pub_city"],
            "color":        _pending["pub_color"],
            "type":         TIPO_MAP.get(_pending["pub_tipo"], "venta"),
            "cat":          "sedan",
            "rating":       0,
            "reviews":      0,
            "desc":         _pending["pub_desc"],
            "seller":       _pending["pub_sname"],
            "phone":        _pending["pub_sphone"],
            "seller_phone": _pending["pub_sphone"],
            "seller_email": _pending["pub_semail"],
            "fotos":        fotos_data,      # bytes RAM para mostrar de inmediato
            "video":        video_data,
            "fotos_b64":    fotos_b64_list,  # b64 para Sheets y portada
            "fotos_urls":   "",              # legacy vacío
            "video_url":    video_ref,       # "sqlite:<pub_id>"
            "grad":         0,
            "estado":       "Activo",
            "isUserPub":    True,
            "fecha":        datetime.now().strftime("%d/%m/%Y"),
        }

        existing_ids = {p.get("id") for p in st.session_state.user_publications}
        if new_id not in existing_ids:
            st.session_state.user_publications.insert(0, new_pub)
            st.session_state.history_items.insert(0, {
                "id":     new_id,
                "name":   f"{_pending['pub_marca']} {_pending['pub_modelo']} {_pending['pub_anio']}",
                "price":  new_pub["price"],
                "date":   new_pub["fecha"],
                "status": "activo",
                "type":   _pending["pub_tipo"],
                "km":     _pending["pub_km"],
                "seller": _pending["pub_sname"],
                "buyer":  "—",
                "city":   _pending["pub_city"],
                "notes":  "Publicación recién creada",
                "points": 50,
                "pubRef": new_pub,
            })
            st.session_state.loyalty_points += 50

        st.session_state.selected_vehicle = new_pub
        ok = save_section_silent(["publicaciones", "historial"])
        media_msg = f" · 📸 {len(fotos_b64_list)} foto(s) guardada(s)" if fotos_b64_list else ""

        _veh_ok, _veh_msg = _upsert_vehiculo_in_sheets(new_pub)
        if not _veh_ok:
            st.warning(f"⚠️ No se guardó en hoja Vehículos: {_veh_msg}")

        _email_msg = ""
        try:
            from media_sync import send_nueva_publicacion_email, get_portada_data_uri
            _portada_uri = get_portada_data_uri(new_pub, max_w=400) if fotos_b64_list else ""
            _email_ok = send_nueva_publicacion_email(ADMIN_EMAIL, new_pub, _portada_uri)
            _email_msg = " · ✉️ Correo enviado" if _email_ok else " · ⚠️ Correo no enviado"
        except Exception as _em:
            _email_msg = f" · ⚠️ Error correo: {str(_em)[:60]}"

        if ok:
            st.success(f"🎉 ¡Publicado con éxito! +50 pts · ☁️ Guardado{media_msg}{_email_msg}")
        else:
            st.success(f"🎉 ¡Publicado con éxito! +50 pts{media_msg}{_email_msg}")
        go("vehicle_detail")
        return

    ini = "".join(w[0].upper() for w in st.session_state.user_name.split()[:2])
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);border-radius:16px;
                padding:18px;margin-bottom:20px;display:flex;gap:14px;align-items:center;">
        <div style="width:48px;height:48px;border-radius:24px;flex-shrink:0;
            background:linear-gradient(135deg,#C41E3A,#9B1729);
            display:flex;align-items:center;justify-content:center;
            font-size:18px;font-weight:700;color:#fff;">{ini}</div>
        <div style="flex:1;">
            <div style="font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;
                letter-spacing:1px;font-weight:700;">Publicado por</div>
            <div style="font-size:16px;font-weight:700;color:#fff;">{st.session_state.user_name}</div>
            <div style="font-size:11px;color:rgba(255,255,255,.55);">
                📍 {st.session_state.user_city}</div>
        </div>
        <div style="background:rgba(0,201,167,.2);border:1px solid rgba(0,201,167,.4);
            border-radius:8px;padding:4px 10px;font-size:11px;font-weight:700;color:#00C9A7;">
            ✓ Verificado</div>
    </div>""", unsafe_allow_html=True)

    with st.form("publish_form", clear_on_submit=True):
        st.markdown("#### 📸 Fotos y video")
        mc1, mc2 = st.columns(2)
        with mc1:
            fotos_files = st.file_uploader("📷 Fotos (máx. 10)",
                type=["jpg","jpeg","png","webp"], accept_multiple_files=True, key="pub_fotos")
        with mc2:
            video_file = st.file_uploader("🎥 Video", type=["mp4","mov","avi","webm"], key="pub_video")

        if fotos_files:
            th = st.columns(min(len(fotos_files), 5))
            for pi, pf in enumerate(fotos_files[:5]):
                with th[pi]:
                    st.caption("📌 Portada" if pi == 0 else f"Foto {pi+1}")
                    st.caption(f"✅ {pf.name}")
        if video_file:
            st.caption(f"🎥 Video listo: {video_file.name}")

        st.divider()
        st.markdown("#### 📋 Información del vehículo")
        vc1, vc2 = st.columns(2)
        with vc1:
            pub_tipo  = st.selectbox("Tipo", ["Venta","Permuta","Venta y Permuta"], key="pf_tipo")
            pub_marca = st.selectbox("Marca",
                ["Toyota","Chevrolet","Renault","Mazda","Hyundai","Kia","Ford", "Hummer", "Audi",
                 "Volkswagen","BMW","Mercedes-Benz","Nissan","Honda","Suzuki","Jeep"], key="pf_marca")
            pub_modelo = st.text_input("Modelo *", placeholder="Ej: Corolla XEI", key="pf_modelo")
            pub_anio   = st.selectbox("Año",
                ["2025","2024","2023","2022","2021","2020","2019","2018","2017","2015","2014","2013","2012","2011","2010","2009","2008","2007","2006","2005","2004","2003","2002","2001","2000","1999","1998","1997","1996","1995","1994","1993","1992","1991","1990","1989","1988","1987","1986","1985","1984","1983","1982","1981","1980"], key="pf_anio")
            pub_km     = st.number_input("Km *", 0, 500_000, step=1_000, key="pf_km")
        with vc2:
            pub_comb  = st.selectbox("Combustible", ["Gasolina","Diesel","Híbrido","Eléctrico","Gas"], key="pf_comb")
            pub_trans = st.selectbox("Transmisión", ["Automático","Manual"], key="pf_trans")
            pub_city  = st.selectbox("Ciudad",
                ["Bogotá","Medellín","Cali","Barranquilla","Bucaramanga","Pereira","Cartagena"], key="pf_city")
            pub_color = st.text_input("Color", placeholder="Blanco, Gris…", key="pf_color")
            pub_precio = st.number_input("Precio (COP) *", 0, 2_000_000_000,
                                         step=1_000_000, format="%d", key="pf_precio")
            if pub_precio > 0:
                st.markdown(f'<div style="color:#C41E3A;font-weight:700;font-size:13px;">'
                            f'$ {pub_precio/1_000_000:.1f} M</div>', unsafe_allow_html=True)
        pub_desc = st.text_area("Descripción", height=90, key="pf_desc",
                                placeholder="Describe el estado, extras, historial…")

        st.divider()
        st.markdown("#### 👤 Datos de contacto")
        cc1, cc2, cc3 = st.columns(3)
        with cc1: pub_sname  = st.text_input("Nombre",  value=st.session_state.user_name,  key="pf_sname")
        with cc2: pub_sphone = st.text_input("Celular", value=st.session_state.user_phone or "", key="pf_sphone")
        with cc3: pub_semail = st.text_input("Correo",  value=st.session_state.user_email, key="pf_semail")
        st.checkbox("✅ Contacto por WhatsApp", value=True, key="pf_wa")

        st.divider()
        submitted = st.form_submit_button("🚀 Publicar vehículo", use_container_width=True, type="primary")
        if submitted:
            errs = []
            if not pub_modelo.strip(): errs.append("Modelo")
            if pub_precio <= 0:        errs.append("Precio")
            if not fotos_files and not video_file: errs.append("Al menos una foto o video")
            if errs:
                st.error(f"❌ Campos requeridos: {', '.join(errs)}")
            else:
                fotos_data = []
                for ff in (fotos_files or [])[:10]:
                    ff.seek(0)
                    fotos_data.append({"name": ff.name, "bytes": ff.read()})
                video_data = None
                if video_file:
                    video_file.seek(0)
                    video_data = {"name": video_file.name, "bytes": video_file.read()}

                new_id = f"PUB-{int(datetime.now().timestamp())}"
                st.session_state._pub_fotos_data = fotos_data
                st.session_state._pub_video_data = video_data
                st.session_state._pub_pending = {
                    "new_id":     new_id,
                    "pub_marca":  pub_marca,
                    "pub_modelo": pub_modelo,
                    "pub_anio":   pub_anio,
                    "pub_km":     pub_km,
                    "pub_precio": pub_precio,
                    "pub_comb":   pub_comb,
                    "pub_trans":  pub_trans,
                    "pub_city":   pub_city,
                    "pub_color":  pub_color or "—",
                    "pub_tipo":   pub_tipo,
                    "pub_desc":   pub_desc,
                    "pub_sname":  pub_sname,
                    "pub_sphone": pub_sphone,
                    "pub_semail": pub_semail,
                }
                st.rerun()


# ── Mis avisos ─────────────────────────────────────────────────────────────────
def page_history():
    _btn_inicio("history")
    st.markdown("## 📋 Mis avisos")
    if not st.session_state.logged_in:
        # ── Selector de modo: Registrarse / Ingresar ─────────────────────────
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.markdown("""
            <div style="text-align:center;padding:12px 0 8px;">
              <div style="font-size:38px;font-weight:900;letter-spacing:4px;
                  background:linear-gradient(135deg,#C41E3A,#F5A623);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;">JJGT</div>
              <div style="font-size:13px;color:#6B6B8A;margin-top:4px;">
                  Para ver o crear avisos necesitas una cuenta</div>
            </div>""", unsafe_allow_html=True)

            # ── Correo no encontrado: forzar registro antes de continuar ─────
            _email_no_existe = st.session_state.get("_hist_email_no_existe", "")
            if _email_no_existe:
                st.error(
                    f"❌ El correo **{_email_no_existe}** no está registrado. "
                    f"Para continuar debes crear una cuenta primero."
                )
                with st.form("hist_force_register_form"):
                    st.markdown("#### 👤 Crear tu cuenta")
                    name  = st.text_input("Nombre *", key="hfr_name")
                    phone = st.text_input("Celular *", placeholder="300 000 0000", key="hfr_phone")
                    st.text_input("Correo", value=_email_no_existe, key="hfr_email_show",
                                  disabled=True)
                    city  = st.selectbox("Ciudad",
                        ["Bogotá","Medellín","Cali","Barranquilla",
                         "Bucaramanga","Pereira","Cartagena"], key="hfr_city")
                    pw1   = st.text_input("Contraseña *", type="password", key="hfr_pw1")
                    pw2   = st.text_input("Confirmar contraseña *", type="password", key="hfr_pw2")
                    terms = st.checkbox("✅ Acepto Términos y condiciones", key="hfr_terms")
                    sub   = st.form_submit_button("🎉 Crear cuenta y continuar",
                                                  use_container_width=True, type="primary")
                    if sub:
                        errs = []
                        if not name.strip():  errs.append("Nombre")
                        if not phone.strip(): errs.append("Celular")
                        if not pw1:           errs.append("Contraseña")
                        if pw1 != pw2:        errs.append("Las contraseñas no coinciden")
                        if not terms:         errs.append("Acepta los términos")
                        if errs:
                            st.error("❌ " + " · ".join(errs))
                        else:
                            # Guardar datos para procesar FUERA del form
                            st.session_state["_hist_reg_data"] = {
                                "name": name, "phone": phone, "city": city,
                                "pw1": pw1, "email": _email_no_existe,
                            }

                # ── Procesar registro FUERA del form ─────────────────────────
                _rdata = st.session_state.pop("_hist_reg_data", None)
                if _rdata:
                    import hashlib as _hl
                    pw_hash  = _hl.sha256(_rdata["pw1"].encode()).hexdigest()
                    new_user = {
                        "id": int(datetime.now().timestamp()),
                        "nombre": _rdata["name"], "correo": _rdata["email"],
                        "celular": _rdata["phone"], "documento": "",
                        "ciudad": _rdata["city"], "rol": "Usuario",
                        "publicaciones": 0, "ventas": 0, "puntos": 50,
                        "nivel": "Bronze",
                        "fecha_registro": datetime.now().strftime("%d/%m/%Y"),
                        "password_hash": pw_hash,
                    }
                    st.session_state.logged_in          = True
                    st.session_state.user_name          = _rdata["name"]
                    st.session_state.user_email         = _rdata["email"]
                    st.session_state.user_phone         = _rdata["phone"]
                    st.session_state.user_city          = _rdata["city"]
                    st.session_state.active_cities      = [_rdata["city"]]
                    st.session_state.user_password_hash = pw_hash
                    st.session_state.history_items      = []
                    st.session_state.notifications      = list(get_notifs_base())
                    usuarios_list = list(st.session_state.get("_usuarios", []))
                    usuarios_list.append(new_user)
                    st.session_state._usuarios = usuarios_list
                    st.session_state.pop("_hist_email_no_existe", None)
                    save_section_silent(["usuarios"])
                    st.rerun()

                if st.button("← Usar otro correo", key="hist_back_login"):
                    st.session_state.pop("_hist_email_no_existe", None)
                    st.rerun()
                return  # No mostrar nada más hasta que se registre

            # ── Selector normal: Registrarse / Ingresar ──────────────────────
            modo = st.radio("", ["📝 Crear cuenta nueva", "🔐 Ya tengo cuenta"],
                            horizontal=True, key="hist_auth_modo",
                            label_visibility="collapsed")

            if modo == "📝 Crear cuenta nueva":
                _prefill_email = st.session_state.pop("_hist_prefill_email", "")
                with st.form("hist_register_form"):
                    st.markdown("#### 👤 Crear cuenta")
                    name  = st.text_input("Nombre *",   key="hrg_name")
                    phone = st.text_input("Celular *",  placeholder="300 000 0000", key="hrg_phone")
                    email = st.text_input("Correo *",   value=_prefill_email, key="hrg_email")
                    city  = st.selectbox("Ciudad",
                        ["Bogotá","Medellín","Cali","Barranquilla",
                         "Bucaramanga","Pereira","Cartagena"], key="hrg_city")
                    pw1   = st.text_input("Contraseña *",         type="password", key="hrg_pw1")
                    pw2   = st.text_input("Confirmar contraseña *", type="password", key="hrg_pw2")
                    terms = st.checkbox("✅ Acepto Términos y condiciones", key="hrg_terms")
                    sub   = st.form_submit_button("🎉 Crear cuenta y ver mis avisos",
                                                  use_container_width=True, type="primary")
                    if sub:
                        errs = []
                        if not name.strip():  errs.append("Nombre")
                        if not email.strip(): errs.append("Correo")
                        if not phone.strip(): errs.append("Celular")
                        if not pw1:           errs.append("Contraseña")
                        if pw1 != pw2:        errs.append("Las contraseñas no coinciden")
                        if not terms:         errs.append("Acepta los términos")
                        if errs:
                            st.error("❌ " + " · ".join(errs))
                        else:
                            st.session_state["_hist_reg_data"] = {
                                "name": name, "phone": phone, "city": city,
                                "pw1": pw1, "email": email.strip(),
                            }

                # ── Procesar registro FUERA del form ─────────────────────────
                _rdata2 = st.session_state.pop("_hist_reg_data", None)
                if _rdata2:
                    import hashlib as _hl
                    pw_hash = _hl.sha256(_rdata2["pw1"].encode()).hexdigest()
                    new_user = {
                        "id": int(datetime.now().timestamp()),
                        "nombre": _rdata2["name"], "correo": _rdata2["email"],
                        "celular": _rdata2["phone"], "documento": "",
                        "ciudad": _rdata2["city"], "rol": "Usuario",
                        "publicaciones": 0, "ventas": 0, "puntos": 50,
                        "nivel": "Bronze",
                        "fecha_registro": datetime.now().strftime("%d/%m/%Y"),
                        "password_hash": pw_hash,
                    }
                    st.session_state.logged_in          = True
                    st.session_state.user_name          = _rdata2["name"]
                    st.session_state.user_email         = _rdata2["email"]
                    st.session_state.user_phone         = _rdata2["phone"]
                    st.session_state.user_city          = _rdata2["city"]
                    st.session_state.active_cities      = [_rdata2["city"]]
                    st.session_state.user_password_hash = pw_hash
                    st.session_state.history_items      = []
                    st.session_state.notifications      = list(get_notifs_base())
                    usuarios_list = list(st.session_state.get("_usuarios", []))
                    usuarios_list.append(new_user)
                    st.session_state._usuarios = usuarios_list
                    save_section_silent(["usuarios"])
                    st.rerun()

            else:  # Ya tengo cuenta
                with st.form("hist_login_form"):
                    st.markdown("#### 🔐 Ingresar")
                    lg_email = st.text_input("Correo", key="hlg_email")
                    lg_pw    = st.text_input("Contraseña", type="password", key="hlg_pw")
                    lg_sub   = st.form_submit_button("Ingresar",
                                                     use_container_width=True, type="primary")
                    if lg_sub:
                        # Guardar datos del intento — la validación se hace FUERA del form
                        st.session_state["_hist_login_attempt"] = {
                            "email": lg_email.strip(),
                            "pw":    lg_pw,
                        }

                # ── Validación FUERA del form (st.rerun() funciona aquí) ──────
                _attempt = st.session_state.pop("_hist_login_attempt", None)
                if _attempt:
                    import hashlib as _hl
                    _lemail    = _attempt["email"]
                    _pw_hash   = _hl.sha256(_attempt["pw"].encode()).hexdigest()
                    _usuarios  = st.session_state.get("_usuarios", [])
                    _enorm     = _lemail.lower()

                    _u = next((u for u in _usuarios
                                if u.get("correo","").strip().lower() == _enorm), None)

                    if _u is None:
                        # Correo no existe → bloquear con formulario de registro
                        st.session_state["_hist_email_no_existe"] = _lemail
                        st.rerun()
                    elif _u.get("password_hash","") != _pw_hash:
                        st.error("❌ Contraseña incorrecta. Verifica e intenta de nuevo.")
                    else:
                        st.session_state.logged_in          = True
                        st.session_state.user_name          = _u.get("nombre","")
                        st.session_state.user_email         = _u.get("correo","")
                        st.session_state.user_phone         = _u.get("celular","")
                        st.session_state.user_city          = _u.get("ciudad","")
                        st.session_state.active_cities      = [_u.get("ciudad","")]
                        st.session_state.user_password_hash = _pw_hash
                        st.session_state.loyalty_points     = int(_u.get("puntos", 0) or 0)
                        st.session_state.notifications      = list(get_notifs_base())
                        st.rerun()

        return

    top1, top2 = st.columns([3, 1])
    with top1:
        tab_f = st.radio("Filtrar:", ["Todos","Activos","Pendientes","Cerrados"],
                         horizontal=True, key="hist_tab")
    with top2:
        if st.button("➕ Nueva publicación", key="hist_new", type="primary", use_container_width=True):
            go("publish")

    FMAP = {"Todos":None,"Activos":"activo","Pendientes":"pendiente","Cerrados":"completado"}
    sel  = FMAP[tab_f]

    # ── Solo publicaciones del usuario logueado ─────────────────────────
    user_email = (st.session_state.get("user_email") or "").strip().lower()
    user_name  = (st.session_state.get("user_name")  or "").strip()

    def _es_mia(p):
        se = (p.get("seller_email") or "").strip().lower()
        sn = (p.get("seller")       or "").strip()
        return (user_email and se == user_email) or (user_name and sn == user_name)

    mis_pubs = [p for p in st.session_state.user_publications if _es_mia(p)]
    mis_ids  = {str(p.get("id","")) for p in mis_pubs}

    items_hist = [h for h in st.session_state.history_items
                  if str(h.get("id","")) in mis_ids or
                  (user_name and h.get("seller","") == user_name)]

    if items_hist:
        items = items_hist
    else:
        items = [{
            "id":     p.get("id",""),
            "name":   f"{p.get('name','')} {p.get('model','')} {p.get('year','')}".strip(),
            "price":  p.get("price",0),
            "date":   p.get("fecha",""),
            "status": "activo" if str(p.get("estado","Activo")).lower() == "activo" else "pendiente",
            "type":   p.get("type","venta"),
            "city":   p.get("city",""),
            "seller": p.get("seller",""),
            "pubRef": p,
        } for p in mis_pubs]

    if sel:
        items = [h for h in items if h.get("status") == sel]

    if not items:
        st.markdown('<div style="text-align:center;padding:50px;color:#6B6B8A;">'
                    '<div style="font-size:40px;margin-bottom:10px;">📋</div>'
                    'Sin avisos en esta categoría</div>', unsafe_allow_html=True)
        return

    SS = {
        "activo":    ("#00C9A7","#E0FAF6","ACTIVO"),
        "pendiente": ("#F5A623","#FEF6E4","PENDIENTE"),
        "completado":("#2979FF","#E3EDFF","CERRADO"),
        "cancelled": ("#E53935","#FDEAED","CANCELADO"),
    }

    for idx, h in enumerate(items):
        sc = h.get("status","activo")
        sfg, sbg, slbl = SS.get(sc, ("#6B6B8A","#F4F5F7","ESTADO"))
        hkey = str(h.get("id","x")).replace("#","").replace("-","_")

        can_edit = sc in ("activo","pendiente")

        with st.container(border=True):
            r1, r2 = st.columns([4, 1])
            with r1:
                st.markdown(f"**{h.get('name','')}**")
                st.caption(f"{h.get('date','')} · {h.get('type','')} · {h.get('city','')}")
                st.markdown(f'<div style="font-size:20px;font-weight:800;color:#C41E3A;">'
                            f'{fmt_price(h.get("price",0))}</div>', unsafe_allow_html=True)
            with r2:
                st.markdown(f'<div style="background:{sbg};color:{sfg};font-size:10px;'
                            f'font-weight:700;padding:4px 10px;border-radius:8px;'
                            f'text-align:center;margin-top:6px;">{slbl}</div>',
                            unsafe_allow_html=True)

            if can_edit:
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    if st.button("👁️ Ver", key=f"hist_view_{hkey}_{idx}",
                                 use_container_width=True):
                        # Buscar referencia: 1) pubRef directo, 2) user_publications por id,
                        # 3) get_vehicles() por id, 4) get_vehicles() por nombre exacto
                        ref = h.get("pubRef")
                        hid = str(h.get("id","")).strip()
                        if not ref and hid:
                            ref = next((p for p in st.session_state.user_publications
                                        if str(p.get("id","")).strip() == hid), None)
                        if not ref and hid:
                            ref = next((v for v in get_vehicles()
                                        if str(v.get("id","")).strip() == hid), None)
                        if not ref:
                            hname = h.get("name","").strip().lower()
                            ref = next((v for v in get_vehicles()
                                        if v.get("name","").strip().lower() == hname), None)
                        if not ref:
                            hname = h.get("name","").strip().lower()
                            ref = next((p for p in st.session_state.user_publications
                                        if p.get("name","").strip().lower() == hname), None)
                        if ref:
                            st.session_state.selected_vehicle = ref
                            go("vehicle_detail")
                        else:
                            st.warning("⚠️ No se encontró el detalle del vehículo.")
                with bc2:
                    if st.button("✏️ Editar", key=f"hist_edit_{hkey}_{idx}",
                                 use_container_width=True):
                        st.session_state["_editing_pub_id"] = h.get("id")
                with bc3:
                    if st.button("🗑️ Eliminar", key=f"hist_del_{hkey}_{idx}",
                                 use_container_width=True):
                        st.session_state["_del_pending_id"]   = h.get("id")
                        st.session_state["_del_pending_name"] = h.get("name", "")
                        st.rerun()

            # ── Confirmación de eliminación ──────────────────────────────────
            if str(st.session_state.get("_del_pending_id","")) == str(h.get("id","")):
                st.warning(f"⚠️ ¿Eliminar **{h.get('name','')}**? Se borrará de Vehículos y Publicaciones en Sheets.")
                _cd1, _cd2 = st.columns(2)
                with _cd1:
                    if st.button("✅ Sí, eliminar", key=f"hist_del_yes_{hkey}_{idx}",
                                 type="primary", use_container_width=True):
                        hid = st.session_state.pop("_del_pending_id", None)
                        st.session_state.pop("_del_pending_name", None)
                        # Quitar de session_state — historial queda con status completado
                        st.session_state.user_publications = [
                            p for p in st.session_state.user_publications
                            if str(p.get("id","")) != str(hid)]
                        for _hi in st.session_state.history_items:
                            if str(_hi.get("id","")) == str(hid):
                                _hi["status"] = "completado"
                                _hi["notes"]  = "Eliminado por el usuario"
                        # Borrar filas en Sheets
                        with st.spinner("🗑️ Eliminando de Google Sheets…"):
                            _ok, _msg = _delete_pub_from_sheets(str(hid))
                        # Guardar historial actualizado
                        save_section_silent(["historial"])
                        if _ok:
                            st.success(f"✅ {_msg}")
                        else:
                            st.warning(f"⚠️ Eliminado de sesión. Error en Sheets: {_msg}")
                        st.rerun()
                with _cd2:
                    if st.button("❌ Cancelar", key=f"hist_del_no_{hkey}_{idx}",
                                 use_container_width=True):
                        st.session_state.pop("_del_pending_id", None)
                        st.session_state.pop("_del_pending_name", None)
                        st.rerun()
            else:
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("👁️ Ver", key=f"hist_view2_{hkey}_{idx}",
                                 use_container_width=True):
                        ref = h.get("pubRef")
                        hid = str(h.get("id","")).strip()
                        if not ref and hid:
                            ref = next((p for p in st.session_state.user_publications
                                        if str(p.get("id","")).strip() == hid), None)
                        if not ref and hid:
                            ref = next((v for v in get_vehicles()
                                        if str(v.get("id","")).strip() == hid), None)
                        if not ref:
                            hname = h.get("name","").strip().lower()
                            ref = next((v for v in get_vehicles()
                                        if v.get("name","").strip().lower() == hname), None)
                        if not ref:
                            hname = h.get("name","").strip().lower()
                            ref = next((p for p in st.session_state.user_publications
                                        if p.get("name","").strip().lower() == hname), None)
                        if ref:
                            st.session_state.selected_vehicle = ref
                            go("vehicle_detail")
                        else:
                            st.warning("⚠️ No se encontró el detalle del vehículo.")
                with bc2:
                    st.button("🔁 Republicar", key=f"hist_rep_{hkey}_{idx}",
                              use_container_width=True)

        # Formulario de edición inline (fuera del container, después de él)
        if st.session_state.get("_editing_pub_id") == h.get("id"):
            pub_ref = next((p for p in st.session_state.user_publications
                            if str(p.get("id","")) == str(h.get("id",""))), None)
            if pub_ref:
                with st.form(key=f"edit_form_{hkey}_{idx}"):
                    st.markdown("#### ✏️ Editar publicación")
                    e1, e2 = st.columns(2)
                    with e1:
                        new_price = st.number_input("Precio",
                            value=int(pub_ref.get("price",0) or 0), step=1000000)
                        new_city  = st.text_input("Ciudad",
                            value=str(pub_ref.get("city","")))
                    with e2:
                        new_km    = st.number_input("Km",
                            value=int(pub_ref.get("km",0) or 0), step=1000)
                        tipo_opts = ["Venta","Permuta","Venta y Permuta"]
                        tipo_vals = ["venta","permuta","ambos"]
                        cur_tipo  = pub_ref.get("type","venta")
                        tipo_idx  = tipo_vals.index(cur_tipo) if cur_tipo in tipo_vals else 0
                        new_tipo  = st.selectbox("Tipo aviso", tipo_opts, index=tipo_idx)
                    new_desc  = st.text_area("Descripción",
                        value=str(pub_ref.get("desc","")), height=80)
                    est_opts  = ["Activo","Pausado","Cerrado"]
                    cur_est   = pub_ref.get("estado","Activo")
                    est_idx   = est_opts.index(cur_est) if cur_est in est_opts else 0
                    new_estado = st.selectbox("Estado", est_opts, index=est_idx)
                    es1, es2  = st.columns(2)
                    with es1:
                        guardar  = st.form_submit_button("💾 Guardar",
                            type="primary", use_container_width=True)
                    with es2:
                        cancelar = st.form_submit_button("❌ Cancelar",
                            use_container_width=True)
                    if guardar:
                        TIPO_MAP = {"Venta":"venta","Permuta":"permuta","Venta y Permuta":"ambos"}
                        pub_ref["price"]  = new_price
                        pub_ref["city"]   = new_city
                        pub_ref["km"]     = new_km
                        pub_ref["type"]   = TIPO_MAP.get(new_tipo,"venta")
                        pub_ref["desc"]   = new_desc
                        pub_ref["estado"] = new_estado
                        h["price"]  = new_price
                        h["status"] = "activo" if new_estado == "Activo" else "pendiente"
                        save_section_silent(["publicaciones","vehiculos","historial"])
                        st.session_state["_editing_pub_id"] = None
                        st.success("✅ Publicación actualizada")
                        st.rerun()
                    if cancelar:
                        st.session_state["_editing_pub_id"] = None
                        st.rerun()

    st.divider()
    st.markdown("**💾 Guardar cambios**")
    hg1, hg2 = st.columns(2)
    with hg1:
        _guardar_sheets(
            sections=["historial", "publicaciones", "vehiculos"],
            key="hist_save_sheets",
            label="☁️ Guardar avisos en Google Sheets",
        )
    with hg2:
        download_button_excel(
            label    = "⬇️ Exportar avisos a Excel",
            sections = ["historial", "publicaciones"],
            key      = "hist_dl_excel",
        )


# ── Notificaciones ─────────────────────────────────────────────────────────────
def page_notifications():
    _btn_inicio("notif")
    st.markdown("## 🔔 Notificaciones")

    notifs = st.session_state.notifications or []
    unread = [n for n in notifs if n.get("unread")]
    tipos_disponibles = sorted({n.get("tipo", "General") for n in notifs if n.get("tipo")})

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(_metric_card("Total", len(notifs), "#2979FF"), unsafe_allow_html=True)
    with m2:
        st.markdown(_metric_card("Sin leer 🔴", len(unread), "#C41E3A"), unsafe_allow_html=True)
    with m3:
        st.markdown(_metric_card("Permutas 🔄",
            sum(1 for n in notifs if n.get("tipo") == "Permuta"), "#00C9A7"),
            unsafe_allow_html=True)
    with m4:
        st.markdown(_metric_card("Sistema ⚙️",
            sum(1 for n in notifs if n.get("tipo") == "Sistema"), "#F5A623"),
            unsafe_allow_html=True)

    st.markdown("")
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        filtro_tipo = st.selectbox(
            "Tipo", ["Todas"] + tipos_disponibles,
            key="notif_filtro_tipo", label_visibility="collapsed")
    with c2:
        filtro_lect = st.selectbox(
            "Estado", ["Todas", "Sin leer", "Leídas"],
            key="notif_filtro_lect", label_visibility="collapsed")
    with c3:
        if st.button("✓ Marcar todas leídas", key="notif_all", use_container_width=True):
            for n in notifs:
                n["unread"] = False
            st.session_state.notif_count = 0
            save_section_silent(["notificaciones"])
            st.rerun()
    with c4:
        if st.button("🗑️ Borrar leídas", key="notif_del_read", use_container_width=True):
            st.session_state.notifications = [n for n in notifs if n.get("unread")]
            st.session_state.notif_count = len(st.session_state.notifications)
            save_section_silent(["notificaciones"])
            st.rerun()

    visibles = list(notifs)
    if filtro_tipo != "Todas":
        visibles = [n for n in visibles if n.get("tipo") == filtro_tipo]
    if filtro_lect == "Sin leer":
        visibles = [n for n in visibles if n.get("unread")]
    elif filtro_lect == "Leídas":
        visibles = [n for n in visibles if not n.get("unread")]

    if not visibles:
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#9999BB;">'
            '<div style="font-size:52px;margin-bottom:12px;">🔔</div>'
            '<div style="font-size:16px;font-weight:600;">Sin notificaciones</div>'
            '<div style="font-size:13px;margin-top:4px;">Aquí aparecerán tus permutas,'
            ' mensajes y actividad de tus avisos.</div>'
            '</div>', unsafe_allow_html=True)
    else:
        ORDEN_G = ["Hoy", "Esta semana", "Anteriores"]
        groups: dict[str, list] = {}
        for n in visibles:
            groups.setdefault(n.get("group", "Anteriores"), []).append(n)

        grupos_sorted = sorted(
            groups.items(),
            key=lambda x: ORDEN_G.index(x[0]) if x[0] in ORDEN_G else 99)

        TIPO_C = {
            "Permuta":     "#00C9A7",
            "Publicación": "#2979FF",
            "Sistema":     "#F5A623",
            "Venta":       "#C41E3A",
            "Mensaje":     "#9C27B0",
            "General":     "#6B6B8A",
        }

        for grp, items in grupos_sorted:
            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:#9999BB;'
                f'text-transform:uppercase;letter-spacing:1.5px;'
                f'padding:16px 0 6px;">{grp} · {len(items)}</div>',
                unsafe_allow_html=True)

            for ni, n in enumerate(items):
                nid      = str(n.get("id", f"n{ni}")).replace("-","_").replace(".","_")
                unread_n = n.get("unread", False)
                tipo_n   = n.get("tipo", "General")
                tc       = TIPO_C.get(tipo_n, "#6B6B8A")
                bg       = "rgba(196,30,58,.03)" if unread_n else "#fff"
                border_l = f"border-left:4px solid {tc};"
                fw       = "700" if unread_n else "500"

                st.markdown(f"""
                <div style="background:{bg};border-radius:12px;padding:14px 16px 10px;
                            margin-bottom:8px;{border_l}
                            box-shadow:0 2px 8px rgba(26,26,46,.06);">
                    <div style="display:flex;gap:12px;align-items:flex-start;">
                        <div style="font-size:24px;flex-shrink:0;padding-top:1px;">
                            {n.get("icon","🔔")}</div>
                        <div style="flex:1;min-width:0;">
                            <div style="display:flex;align-items:center;gap:8px;
                                        flex-wrap:wrap;margin-bottom:3px;">
                                <span style="font-weight:{fw};font-size:14px;color:#1A1A2E;">
                                    {re.sub(r'<[^>]+>', ' ', str(n.get("title",""))).strip()}</span>
                                <span style="background:{tc}22;color:{tc};font-size:10px;
                                    font-weight:700;padding:1px 8px;border-radius:20px;">
                                    {tipo_n}</span>
                                {"<span style='width:7px;height:7px;border-radius:50%;" +
                                 "background:#C41E3A;display:inline-block;'></span>" if unread_n else ""}
                            </div>
                            <div style="font-size:13px;color:#6B6B8A;line-height:1.5;">
                                {re.sub(r'<[^>]+>', ' ', str(n.get("desc",""))).strip()}</div>
                            <div style="font-size:11px;color:#ADADCA;margin-top:5px;">
                                🕐 {n.get("date","")} {n.get("time","")}
                                {"&nbsp;·&nbsp;<b>Sin leer</b>" if unread_n else ""}
                            </div>
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)

                btn_a, btn_b, btn_c = st.columns([3, 3, 1])
                accion = n.get("action", "")
                with btn_a:
                    if accion in ("Ver permuta", "Ver permutas", "Ir a permutas"):
                        if st.button("🔄 Ver en Permutas", key=f"nact_{nid}_{ni}", use_container_width=True):
                            n["unread"] = False
                            st.session_state.notif_count = max(0, st.session_state.notif_count - 1)
                            save_section_silent(["notificaciones"])
                            go("permutas")
                    elif accion in ("Ver aviso", "Mis avisos"):
                        if st.button("📋 Ver mis avisos", key=f"nact_{nid}_{ni}", use_container_width=True):
                            n["unread"] = False
                            go("history")
                    elif accion:
                        st.caption(f"→ {accion}")
                with btn_b:
                    if unread_n:
                        if st.button("✓ Marcar leída", key=f"nread_{nid}_{ni}", use_container_width=True):
                            n["unread"] = False
                            st.session_state.notif_count = max(0, st.session_state.notif_count - 1)
                            save_section_silent(["notificaciones"])
                            st.rerun()
                with btn_c:
                    if st.button("🗑", key=f"ndel_{nid}_{ni}", use_container_width=True,
                                 help="Eliminar esta notificación"):
                        st.session_state.notifications = [
                            x for x in st.session_state.notifications
                            if x.get("id") != n.get("id")]
                        st.session_state.notif_count = sum(
                            1 for x in st.session_state.notifications if x.get("unread"))
                        save_section_silent(["notificaciones"])
                        st.rerun()

    st.divider()
    with st.expander("⚙️ Preferencias de notificación"):
        prefs = st.session_state.notif_prefs
        p1, p2, p3 = st.columns(3)
        with p1:
            prefs["permutas"] = st.toggle("🔄 Permutas",       value=prefs.get("permutas", True),  key="np_permutas")
            prefs["mensajes"] = st.toggle("💬 Mensajes",        value=prefs.get("mensajes", True),  key="np_mensajes")
        with p2:
            prefs["visitas"]  = st.toggle("👁️ Visitas al aviso", value=prefs.get("visitas", True),  key="np_visitas")
            prefs["nuevos"]   = st.toggle("🚗 Nuevos avisos",   value=prefs.get("nuevos", False),   key="np_nuevos")
        with p3:
            prefs["resenas"]  = st.toggle("⭐ Reseñas",         value=prefs.get("resenas", True),   key="np_resenas")
            prefs["push"]     = st.toggle("📲 Notif. push",     value=prefs.get("push", True),      key="np_push")
        if st.button("💾 Guardar preferencias", key="np_save", use_container_width=True):
            st.toast("✅ Preferencias guardadas")

    ng1, ng2 = st.columns(2)
    with ng1:
        _guardar_sheets(sections=["notificaciones"], key="notif_save_sheets",
                        label="☁️ Guardar en Google Sheets")
    with ng2:
        download_button_excel(label="⬇️ Exportar Excel",
                              sections=["notificaciones"], key="notif_dl_excel")


# ── Soporte ────────────────────────────────────────────────────────────────────
def page_support():
    _btn_inicio("support")
    st.markdown("## 💬 Soporte JJGT")
    st.markdown("""
    <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:16px;
                padding:20px;margin-bottom:20px;text-align:center;color:#fff;">
        <div style="font-size:20px;font-weight:800;">¿Necesitas ayuda?</div>
        <div style="font-size:12px;opacity:.7;">Lun–Sáb 8:00am – 6:00pm</div>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.chat_messages:
        st.session_state.chat_messages = [{
            "role": "bot",
            "text": "¡Hola! Soy el asistente de JJGT 🚗. ¿En qué puedo ayudarte?"
        }]

    for msg in st.session_state.chat_messages:
        if msg["role"] == "bot":
            st.markdown(f"""
            <div style="display:flex;gap:10px;margin-bottom:10px;">
                <div style="width:30px;height:30px;border-radius:15px;flex-shrink:0;
                    background:linear-gradient(135deg,#C41E3A,#1A1A2E);
                    display:flex;align-items:center;justify-content:center;">🚗</div>
                <div style="background:#F4F5F7;border-radius:0 12px 12px 12px;
                    padding:12px 16px;max-width:80%;font-size:14px;">{msg['text']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="display:flex;justify-content:flex-end;margin-bottom:10px;">
                <div style="background:linear-gradient(135deg,#C41E3A,#9B1729);color:#fff;
                    border-radius:12px 0 12px 12px;padding:12px 16px;
                    max-width:80%;font-size:14px;">{msg['text']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("**Preguntas frecuentes:**")
    QRS = [("¿Cómo publico?","publicar"),("¿Cómo hago permuta?","permuta"),
           ("Verificar precio","precio"),("Documentos","soat"),
           ("Pagos seguros","pago"),("Hablar con agente","default")]
    qr_cols = st.columns(3)
    for i, (label, key) in enumerate(QRS):
        with qr_cols[i % 3]:
            if st.button(label, key=f"chat_qr_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role":"user","text":label})
                st.session_state.chat_messages.append(
                    {"role":"bot","text":CHATBOT_REPLIES.get(key, CHATBOT_REPLIES["default"])})
                st.rerun()

    with st.form("chat_form", clear_on_submit=True):
        ci1, ci2 = st.columns([4, 1])
        with ci1: user_msg = st.text_input("Escribe…", label_visibility="collapsed", key="chat_in")
        with ci2: send = st.form_submit_button("→", use_container_width=True)
        if send and user_msg.strip():
            st.session_state.chat_messages.append({"role":"user","text":user_msg.strip()})
            found = next((k for k in CHATBOT_REPLIES if k in user_msg.lower()), "default")
            st.session_state.chat_messages.append(
                {"role":"bot","text":CHATBOT_REPLIES[found]})
            st.rerun()

    st.divider()
    st.markdown("**📚 FAQ**")
    for q, a in [
        ("¿Cómo publico un vehículo?",
         "Ve a 'Publicar' en el menú, completa los datos, agrega fotos/video y establece el precio."),
        ("¿Qué es una permuta?",
         "Es el intercambio de tu vehículo por otro, con o sin diferencia de precio."),
        ("¿Es seguro negociar en JJGT?",
         "Verificamos identidad de usuarios. Revisa en persona antes de cerrar cualquier trato."),
        ("¿Cuánto cuesta publicar?",
         "¡Completamente gratis! Hasta 3 avisos activos simultáneamente."),
        ("¿Cómo funcionan los puntos?",
         "Ganas puntos por publicar, vender e invitar amigos. Canjéalos por avisos destacados."),
    ]:
        with st.expander(q):
            st.write(a)

    # ═══════════════════════════════════════════════════════════════════════════
    # CONSULTA RUNT — SOAT Y TECNOMECÁNICA
    # ═══════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(135deg,#003366,#0055A5);border-radius:16px;
                padding:20px;margin-bottom:16px;color:#fff;">
        <div style="font-size:20px;font-weight:800;">🚗 Consulta RUNT</div>
        <div style="font-size:12px;opacity:.75;margin-top:4px;">
            Verifica SOAT vigente y Revisión Técnico-Mecánica de cualquier vehículo en Colombia</div>
    </div>""", unsafe_allow_html=True)

    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs(["🔍 Consultar vehículo","💰 Tarifas SOAT 2026","ℹ️ ¿Qué es el RUNT?","📋 Guía de documentos"])

    with r_tab1:
        st.markdown("#### Ingresa la placa del vehículo")
        st.caption("La placa debe tener el formato: 3 letras + 3 números (ej. ABC123) o el nuevo formato (ej. ABC12D)")

        rc1, rc2 = st.columns([3,1])
        with rc1:
            placa_raw = st.text_input("Placa", placeholder="ABC123",
                                       max_chars=7, key="runt_placa",
                                       label_visibility="collapsed")
        with rc2:
            buscar = st.button("🔍 Consultar", key="runt_buscar",
                               type="primary", use_container_width=True)

        placa = placa_raw.strip().upper().replace(" ","").replace("-","")

        if buscar and placa:
            if len(placa) < 5:
                st.error("Placa inválida. Ejemplo válido: ABC123")
            else:
                # URLs oficiales RUNT
                url_runt_soat      = f"https://portalpublico.runt.gov.co/#/consulta-vehiculo/consulta/info-vehiculo/"
                url_runt_rtm       = f"https://portalpublico.runt.gov.co/#/consulta-vehiculo/consulta/info-vehiculo/"
                url_simit          = "https://www.fcm.org.co/simit/#/home-public"
                url_mintransporte  = "https://mintransporte.gov.co/publicaciones/4671/runt/"

                st.markdown(f"""
                <div style="background:#F0F7FF;border:2px solid #0055A5;border-radius:14px;
                            padding:20px;margin:12px 0;">
                    <div style="font-size:16px;font-weight:800;color:#003366;margin-bottom:12px;">
                        📋 Placa: <span style="color:#C41E3A;font-size:20px;letter-spacing:3px;">{placa}</span>
                    </div>
                    <div style="font-size:12px;color:#555;margin-bottom:16px;">
                        El RUNT es el sistema oficial del Ministerio de Transporte de Colombia.
                        La consulta se realiza directamente en el portal oficial.
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                        <a href="{url_runt_soat}" target="_blank" style="
                            background:linear-gradient(135deg,#1B5E20,#2E7D32);
                            color:#fff;text-decoration:none;border-radius:10px;
                            padding:14px;display:block;text-align:center;">
                            <div style="font-size:22px;">🛡️</div>
                            <div style="font-weight:800;font-size:14px;margin-top:4px;">Consultar SOAT</div>
                            <div style="font-size:11px;opacity:.8;">Seguro Obligatorio</div>
                        </a>
                        <a href="{url_runt_rtm}" target="_blank" style="
                            background:linear-gradient(135deg,#0D47A1,#1565C0);
                            color:#fff;text-decoration:none;border-radius:10px;
                            padding:14px;display:block;text-align:center;">
                            <div style="font-size:22px;">🔧</div>
                            <div style="font-weight:800;font-size:14px;margin-top:4px;">Tecnomecánica</div>
                            <div style="font-size:11px;opacity:.8;">Rev. Técnico-Mecánica</div>
                        </a>
                    </div>
                </div>""", unsafe_allow_html=True)

                st.markdown("##### 📌 Pasos para consultar:")
                st.markdown("""
                1. Haz clic en **Consultar SOAT** o **Tecnomecánica** arriba
                2. El portal oficial RUNT abrirá con la placa pre-cargada
                3. Completa el CAPTCHA de seguridad si aparece
                4. Verifica la vigencia del SOAT y el estado de la revisión técnico-mecánica
                """)

                st.info("💡 **Tip JJGT:** Siempre verifica SOAT y tecnomecánica antes de comprar o aceptar una permuta. Documentos al día = negocio seguro.")

                with st.expander("🔗 Otros portales oficiales útiles"):
                    st.markdown(f"""
                    | Portal | Descripción | Enlace |
                    |--------|-------------|--------|
                    | 🏛️ RUNT oficial | Registro Único Nacional de Tránsito | [runt.com.co](https://www.runt.com.co) |
                    | ⚖️ SIMIT | Multas y comparendos | [fcm.org.co/simit](https://www.fcm.org.co/simit/#/home-public) |
                    | 🚌 Mintransporte | Información oficial | [mintransporte.gov.co](https://mintransporte.gov.co) |
                    | 📄 Imp. vehículos | Impuesto vehicular por ciudad | Consulta en la secretaría de tu ciudad |
                    """)

        elif buscar and not placa:
            st.warning("⚠️ Ingresa una placa para consultar")

        if not buscar:
            st.markdown("""
            <div style="background:#FFFBF0;border:1px solid #F5A623;border-radius:10px;
                        padding:14px;margin-top:8px;">
                <div style="font-weight:700;color:#8B5E00;font-size:13px;">⚠️ Información importante</div>
                <ul style="font-size:12px;color:#666;margin:8px 0 0;padding-left:18px;">
                    <li>La consulta se realiza en el portal oficial del RUNT — no almacenamos datos del vehículo</li>
                    <li>El SOAT vencido implica una multa de <b>30 SMLDV</b> (~$1.4M COP)</li>
                    <li>La tecnomecánica vencida implica inmovilización del vehículo</li>
                    <li>Los resultados dependen de la disponibilidad del portal RUNT</li>
                </ul>
            </div>""", unsafe_allow_html=True)

    with r_tab2:
        st.markdown("#### 💰 Tarifas máximas SOAT 2026 — Superintendencia Financiera de Colombia")
        st.caption("Fuente: Circular 022 de 2025 · Vigentes desde el 1 de enero de 2026 · Valores en pesos colombianos (COP)")

        st.info("💡 Selecciona el tipo y características de tu vehículo para conocer la tarifa exacta.")

        tipo_veh = st.selectbox("Tipo de vehículo", [
            "🏍️ Motocicleta",
            "🛵 Ciclomotor / Mototriciclo",
            "🚗 Auto familiar / Particular",
            "🚙 Campero / Camioneta",
            "🚐 Vehículo 6+ pasajeros",
            "🚖 Auto de negocio / Taxi",
            "🚛 Vehículo de carga / Mixto",
            "🚌 Servicio público urbano",
        ], key="soat_tipo")

        tarifa_final = None
        descripcion  = ""

        if tipo_veh == "🛵 Ciclomotor / Mototriciclo":
            tarifa_final = 124_100
            descripcion  = "Ciclomotor / Mototriciclo / Motocarro (tarifa única)"

        elif tipo_veh == "🏍️ Motocicleta":
            cc = st.radio("Cilindraje", ["Menos de 100 c.c.","Entre 100 y 200 c.c.","Más de 200 c.c."],
                          horizontal=True, key="soat_moto_cc")
            tarifas_moto = {
                "Menos de 100 c.c.":       256_200,
                "Entre 100 y 200 c.c.":    343_300,
                "Más de 200 c.c.":         761_400,
            }
            tarifa_final = tarifas_moto[cc]
            descripcion  = f"Motocicleta · {cc}"

        elif tipo_veh == "🚗 Auto familiar / Particular":
            cc2 = st.radio("Cilindraje", ["Menos de 1.500 c.c.","Entre 1.500 y 2.500 c.c.","Más de 2.500 c.c."],
                           horizontal=True, key="soat_auto_cc")
            ant2 = st.radio("Antigüedad", ["Menos de 10 años","10 años o más"],
                            horizontal=True, key="soat_auto_ant")
            tarifas_auto = {
                ("Menos de 1.500 c.c.",       "Menos de 10 años"): 447_300,
                ("Menos de 1.500 c.c.",       "10 años o más"):    592_900,
                ("Entre 1.500 y 2.500 c.c.", "Menos de 10 años"): 544_700,
                ("Entre 1.500 y 2.500 c.c.", "10 años o más"):    677_400,
                ("Más de 2.500 c.c.",         "Menos de 10 años"): 636_000,
                ("Más de 2.500 c.c.",         "10 años o más"):    754_300,
            }
            tarifa_final = tarifas_auto[(cc2, ant2)]
            descripcion  = f"Auto familiar · {cc2} · {ant2}"

        elif tipo_veh == "🚙 Campero / Camioneta":
            cc3 = st.radio("Cilindraje", ["Menos de 1.500 c.c.","Entre 1.500 y 2.500 c.c.","Más de 2.500 c.c."],
                           horizontal=True, key="soat_camp_cc")
            ant3 = st.radio("Antigüedad", ["Menos de 10 años","10 años o más"],
                            horizontal=True, key="soat_camp_ant")
            tarifas_camp = {
                ("Menos de 1.500 c.c.",       "Menos de 10 años"):   792_800,
                ("Menos de 1.500 c.c.",       "10 años o más"):      953_000,
                ("Entre 1.500 y 2.500 c.c.", "Menos de 10 años"):   946_600,
                ("Entre 1.500 y 2.500 c.c.", "10 años o más"):    1_121_400,
                ("Más de 2.500 c.c.",         "Menos de 10 años"): 1_110_300,
                ("Más de 2.500 c.c.",         "10 años o más"):    1_274_000,
            }
            tarifa_final = tarifas_camp[(cc3, ant3)]
            descripcion  = f"Campero/Camioneta · {cc3} · {ant3}"

        elif tipo_veh == "🚐 Vehículo 6+ pasajeros":
            cc4 = st.radio("Cilindraje", ["Menos de 2.500 c.c.","2.500 c.c. o más"],
                           horizontal=True, key="soat_6p_cc")
            ant4 = st.radio("Antigüedad", ["Menos de 10 años","10 años o más"],
                            horizontal=True, key="soat_6p_ant")
            tarifas_6p = {
                ("Menos de 2.500 c.c.", "Menos de 10 años"):   797_300,
                ("Menos de 2.500 c.c.", "10 años o más"):    1_017_700,
                ("2.500 c.c. o más",    "Menos de 10 años"): 1_067_300,
                ("2.500 c.c. o más",    "10 años o más"):    1_281_600,
            }
            tarifa_final = tarifas_6p[(cc4, ant4)]
            descripcion  = f"Vehículo 6+ pasajeros · {cc4} · {ant4}"

        elif tipo_veh == "🚖 Auto de negocio / Taxi":
            cc5 = st.radio("Cilindraje", ["Menos de 1.500 c.c.","Entre 1.500 y 2.500 c.c.","Más de 2.500 c.c."],
                           horizontal=True, key="soat_taxi_cc")
            ant5 = st.radio("Antigüedad", ["Menos de 10 años","10 años o más"],
                            horizontal=True, key="soat_taxi_ant")
            tarifas_taxi = {
                ("Menos de 1.500 c.c.",       "Menos de 10 años"): 281_600,
                ("Menos de 1.500 c.c.",       "10 años o más"):    352_000,
                ("Entre 1.500 y 2.500 c.c.", "Menos de 10 años"): 350_000,
                ("Entre 1.500 y 2.500 c.c.", "10 años o más"):    432_400,
                ("Más de 2.500 c.c.",         "Menos de 10 años"): 451_400,
                ("Más de 2.500 c.c.",         "10 años o más"):    451_400,
            }
            tarifa_final = tarifas_taxi.get((cc5, ant5), 281_600)
            descripcion  = f"Auto de negocio/Taxi · {cc5} · {ant5}"

        elif tipo_veh == "🚛 Vehículo de carga / Mixto":
            peso = st.radio("Peso / Tonelaje", ["Menos de 5 toneladas","Entre 5 y 15 toneladas","Más de 15 toneladas"],
                            horizontal=True, key="soat_carga_peso")
            tarifas_carga = {
                "Menos de 5 toneladas":      888_400,
                "Entre 5 y 15 toneladas":  1_282_800,
                "Más de 15 toneladas":     1_621_900,
            }
            tarifa_final = tarifas_carga[peso]
            descripcion  = f"Carga/Mixto · {peso}"

        elif tipo_veh == "🚌 Servicio público urbano":
            cap = st.radio("Capacidad", ["Menos de 10 pasajeros","10 o más pasajeros / Bus-buseta"],
                           horizontal=True, key="soat_bus_cap")
            tarifas_bus = {
                "Menos de 10 pasajeros":          436_300,
                "10 o más pasajeros / Bus-buseta": 633_500,
            }
            tarifa_final = tarifas_bus[cap]
            descripcion  = f"Servicio público urbano · {cap}"

        if tarifa_final:
            anio_veh = st.number_input("Año del vehículo (para referencia)",
                                        min_value=1980, max_value=2026, value=2018,
                                        key="soat_anio", step=1)
            from datetime import datetime as _dt
            antiguedad_real = _dt.now().year - anio_veh
            nota_ant = f"Tu vehículo tiene **{antiguedad_real} años** — aplica tarifa de " +                        ("**menos de 10 años**" if antiguedad_real < 10 else "**10 años o más**")

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#003366,#0055A5);border-radius:16px;
                        padding:24px;margin:16px 0;color:#fff;text-align:center;">
                <div style="font-size:13px;opacity:.75;text-transform:uppercase;letter-spacing:1px;">
                    Tarifa máxima SOAT 2026</div>
                <div style="font-size:13px;opacity:.6;margin-bottom:8px;">{descripcion}</div>
                <div style="font-size:44px;font-weight:900;letter-spacing:1px;">
                    ${tarifa_final:,.0f}
                </div>
                <div style="font-size:12px;opacity:.7;margin-top:8px;">COP · Vigente desde 1 ene 2026</div>
            </div>""".replace(",", "."), unsafe_allow_html=True)

            st.caption(nota_ant)

            with st.expander("📊 Desglose del valor"):
                prime   = round(tarifa_final * 0.48)
                adres   = round(tarifa_final * 0.52)
                runt_v  = 2_400
                st.markdown(f"""
                | Concepto | Valor aproximado |
                |----------|-----------------|
                | Prima neta (aseguradora) | ${prime:,.0f} COP |
                | Contribución ADRES (52%) | ${adres:,.0f} COP |
                | Aporte RUNT | $2.400 COP |
                | **Total estimado** | **${tarifa_final:,.0f} COP** |
                """.replace(",","."))
                st.caption("El 52% va a la ADRES para cubrir atención médica de víctimas de accidentes de tránsito.")

            st.markdown("##### 🏦 ¿Dónde comprar el SOAT?")
            aseguradoras = [
                ("Sura",    "https://www.sura.com/soluciones-personas/soat.aspx"),
                ("Mapfre",  "https://www.mapfre.com.co/seguros-para-ti/soat/"),
                ("Bolívar", "https://www.segurosbolivar.com/personas/soat"),
                ("AXA Colpatria","https://www.axacolpatria.co/soat"),
                ("Liberty", "https://www.liberty.com.co/personas/soat"),
                ("Previsora","https://www.previsora.gov.co"),
                ("HDI",     "https://www.hdi.com.co"),
            ]
            cols_a = st.columns(4)
            for i, (nombre, url) in enumerate(aseguradoras):
                with cols_a[i % 4]:
                    st.markdown(f"[🏦 {nombre}]({url})", unsafe_allow_html=False)

            st.warning("⚠️ Son tarifas **máximas** oficiales. El valor final puede ser igual o menor según la aseguradora. Compra solo en canales autorizados.")

            st.markdown("""
            <div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);border-radius:14px;
                        padding:18px;margin-top:16px;display:flex;gap:14px;align-items:center;">
                <div style="width:50px;height:50px;border-radius:25px;flex-shrink:0;
                    background:linear-gradient(135deg,#C41E3A,#9B1729);
                    display:flex;align-items:center;justify-content:center;
                    font-size:22px;font-weight:700;color:#fff;">JG</div>
                <div style="flex:1;">
                    <div style="font-size:11px;color:rgba(255,255,255,.5);text-transform:uppercase;
                        letter-spacing:1px;font-weight:700;">Tu Asesor de Seguros</div>
                    <div style="font-size:16px;font-weight:800;color:#fff;margin-top:2px;">
                        Jose A. Garcia</div>
                    <div style="font-size:12px;color:rgba(255,255,255,.65);margin-top:4px;">
                        📱 <a href="https://wa.me/573205511091" target="_blank"
                            style="color:#25D366;text-decoration:none;font-weight:700;">
                            320 551 1091</a>
                        &nbsp;·&nbsp;
                        ✉️ <a href="mailto:josegarjagt@gmail.com"
                            style="color:#F5A623;text-decoration:none;">
                            josegarjagt@gmail.com</a>
                    </div>
                    <div style="margin-top:8px;font-size:11px;
                        background:rgba(0,201,167,.15);border:1px solid rgba(0,201,167,.3);
                        color:#00C9A7;border-radius:6px;padding:4px 10px;display:inline-block;">
                        🔒 No dude en contactarme · Absoluta reserva</div>
                </div>
            </div>""", unsafe_allow_html=True)

    with r_tab3:
        st.markdown("""
        ### ¿Qué es el RUNT?
        El **Registro Único Nacional de Tránsito (RUNT)** es la base de datos oficial del
        Ministerio de Transporte de Colombia que centraliza toda la información de:

        **🛡️ SOAT — Seguro Obligatorio de Accidentes de Tránsito**
        - Seguro obligatorio para todo vehículo automotor en Colombia
        - Cubre atención médica de víctimas en accidentes de tránsito
        - Debe renovarse **anualmente** antes del vencimiento
        - Multa por no tenerlo: **30 SMLDV** (~$1.4M COP en 2025)
        - Se puede adquirir en aseguradoras: Sura, Mapfre, Bolívar, AXA, Liberty, etc.

        **🔧 Revisión Técnico-Mecánica (RTM)**
        - Verificación obligatoria del estado mecánico y de emisiones del vehículo
        - Vehículos nuevos: exentos los **primeros 3 años**
        - Vehículos de 3–6 años: revisión **cada 2 años**
        - Vehículos mayores de 6 años: revisión **anual**
        - Se realiza en Centros de Diagnóstico Automotor (CDA) habilitados
        - Vigencia: 1 año a partir de la fecha de la revisión
        """)

    with r_tab4:
        st.markdown("#### 📋 Documentos para vender o permutar un vehículo en Colombia")
        docs = [
            ("🪪", "Tarjeta de propiedad", "Obligatorio", "Documento que acredita quién es el propietario del vehículo."),
            ("🛡️", "SOAT vigente",        "Obligatorio", "Debe estar activo al momento de la venta. El comprador puede renovarlo."),
            ("🔧", "Tecnomecánica",        "Obligatorio", "Revisión técnico-mecánica vigente según la antigüedad del vehículo."),
            ("📄", "Impuesto al día",      "Obligatorio", "Impuesto vehicular pagado hasta el año vigente. Consulta en la secretaría de tu ciudad."),
            ("🔍", "Certificado RUNT",     "Recomendado", "Verifica que el vehículo no esté reportado como robado o con limitaciones."),
            ("🧾", "Paz y salvo SIMIT",    "Recomendado", "Certifica que el vehículo no tiene multas de tránsito pendientes."),
        ]
        for ico, nombre, tipo, desc in docs:
            color = "#1B5E20" if tipo == "Obligatorio" else "#0D47A1"
            bg    = "#F1F8F1" if tipo == "Obligatorio" else "#F0F4FF"
            st.markdown(f"""
            <div style="display:flex;gap:12px;padding:12px;background:{bg};
                        border-radius:10px;margin-bottom:8px;border-left:4px solid {color};">
                <div style="font-size:24px;flex-shrink:0;">{ico}</div>
                <div>
                    <div style="font-weight:700;font-size:14px;">{nombre}
                        <span style="background:{color};color:#fff;font-size:10px;font-weight:700;
                            padding:1px 8px;border-radius:10px;margin-left:6px;">{tipo}</span>
                    </div>
                    <div style="font-size:12px;color:#666;margin-top:3px;">{desc}</div>
                </div>
            </div>""", unsafe_allow_html=True)


# ── Permutas ───────────────────────────────────────────────────────────────────
def page_permutas():
    _btn_inicio("permutas")
    st.markdown("## 🔄 Permutas activas")
    st.caption("Intercambios de vehículos sin intermediarios en toda Colombia.")
    vehicles = _dedup_vehicles()
    perm_vehs = [v for v in vehicles if v.get("type") in ("permuta", "ambos")]
    permutas_list = st.session_state.permutas

    k1, k2, k3 = st.columns(3)
    with k1: st.metric("🔄 Activas",     sum(1 for p in permutas_list if p.get("estado")=="Activa"))
    with k2: st.metric("✅ Completadas", sum(1 for p in permutas_list if p.get("resultado")=="Completada"))
    with k3: st.metric("🚗 Disponibles", len(perm_vehs))

    st.divider()
    t1, t2 = st.tabs(["🚗 Vehículos disponibles", "📋 Propuestas"])

    with t1:
        todos_activos = [v for v in vehicles if str(v.get("estado","Activo")).strip() in ("Activo","activo","")]
        if not todos_activos:
            st.info("No hay vehículos disponibles.")
        else:
            cols = st.columns(2)
            for i, v in enumerate(todos_activos):
                with cols[i % 2]:
                    vehicle_card(v, btn_key=f"perm_veh_{v.get('id',i)}_{i}")
                    if v.get("type") in ("permuta","ambos"):
                        if st.button("🔄 Proponer permuta",
                                     key=f"perm_prop_{v.get('id',i)}_{i}",
                                     type="primary", use_container_width=True):
                            if not st.session_state.logged_in:
                                st.error("Inicia sesión primero")
                            else:
                                nueva_perm = {
                                    "id":              f"P-{int(datetime.now().timestamp())}",
                                    "veh_oferta":      f"{v.get('name','')} {v.get('model','')}",
                                    "vendedor_oferta": st.session_state.user_name,
                                    "veh_destino":     f"{v.get('name','')} {v.get('model','')}",
                                    "propietario":     v.get("seller","—"),
                                    "ciudad":          v.get("city","Bogotá"),
                                    "valor_oferta":    v.get("price",0),
                                    "diferencia":      0,
                                    "fecha":           datetime.now().strftime("%d/%m/%Y"),
                                    "estado":          "Activa",
                                    "mensaje":         "Propuesta enviada desde la app",
                                    "resultado":       "Pendiente",
                                }
                                st.session_state.permutas.insert(0, nueva_perm)
                                save_section_silent(["permutas"])
                                # Enviar correo al vendedor y al proponente
                                try:
                                    from media_sync import send_permuta_email as _spe
                                    emails_dst = []
                                    if v.get("seller_email"): emails_dst.append(v["seller_email"])
                                    if st.session_state.get("user_email"): emails_dst.append(st.session_state.user_email)
                                    if emails_dst:
                                        _spe(
                                            destinatarios=emails_dst,
                                            propuesta={
                                                "id":         nueva_perm["id"],
                                                "fecha":      nueva_perm["fecha"],
                                                "diferencia": nueva_perm["diferencia"],
                                                "notas":      "",
                                            },
                                            vehiculo_ofrecido={
                                                "marca":  st.session_state.user_name,
                                                "modelo": "(Vehículo del usuario)",
                                                "precio": nueva_perm["valor_oferta"],
                                            },
                                            vehiculo_deseado={
                                                "marca":  v.get("name",""),
                                                "modelo": v.get("model",""),
                                                "precio": v.get("price",0),
                                            },
                                        )
                                except Exception:
                                    pass
                                st.success(f"✅ Propuesta enviada para {v.get('name','')} {v.get('model','')}")

    with t2:
        EC = {"Activa":"#00C9A7","Contraoferta":"#F5A623","Cerrada":"#2979FF","Cancelada":"#E53935"}
        for p in permutas_list:
            ec = EC.get(p.get("estado","Activa"),"#6B6B8A")
            with st.container(border=True):
                ra, rb = st.columns([4, 1])
                with ra:
                    st.markdown(f"**{p.get('veh_oferta','')}**  ⇄  **{p.get('veh_destino','')}**")
                    st.caption(f"🏙️ {p.get('ciudad','')} · 📅 {p.get('fecha','')} · {p.get('vendedor_oferta','')}")
                    if p.get("mensaje"):
                        st.markdown(f'*"{p["mensaje"]}"*')
                with rb:
                    st.markdown(
                        f'<div style="background:{ec}22;color:{ec};font-size:11px;'
                        f'font-weight:700;padding:4px 10px;border-radius:8px;'
                        f'text-align:center;margin-top:4px;">{p.get("estado","")}</div>',
                        unsafe_allow_html=True)
                    st.caption(fmt_price(p.get("diferencia",0)) + " dif.")

    st.divider()
    st.markdown("**💾 Guardar cambios**")
    pg1, pg2 = st.columns(2)
    with pg1:
        _guardar_sheets(sections=["permutas"], key="perm_save_sheets",
                        label="☁️ Guardar permutas en Google Sheets")
    with pg2:
        download_button_excel(label="⬇️ Exportar permutas a Excel",
                              sections=["permutas"], key="perm_dl_excel")


# ── Perfil ─────────────────────────────────────────────────────────────────────
def page_profile():
    _btn_inicio("profile")
    if not st.session_state.logged_in:
        st.markdown("## 👤 Mi Perfil")
        st.info("🔐 Inicia sesión para ver tu perfil.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Ingresar",     key="prof_login",    type="primary", use_container_width=True): go("login")
        with c2:
            if st.button("Crear cuenta", key="prof_register", use_container_width=True): go("register")
        return

    ini = "".join(w[0].upper() for w in st.session_state.user_name.split()[:2])
    n_av  = len(st.session_state.history_items)
    n_vt  = sum(1 for h in st.session_state.history_items if h.get("status")=="completado")
    pts   = st.session_state.loyalty_points

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:20px;
                padding:28px;margin-bottom:20px;text-align:center;color:#fff;">
        <div style="width:68px;height:68px;border-radius:34px;margin:0 auto 12px;
            background:linear-gradient(135deg,#E8384F,#9B1729);
            display:flex;align-items:center;justify-content:center;
            font-size:26px;font-weight:700;">{ini}</div>
        <div style="font-size:22px;font-weight:800;">{st.session_state.user_name}</div>
        <div style="font-size:12px;opacity:.7;margin-top:2px;">{st.session_state.user_email}</div>
        <div style="display:flex;justify-content:center;gap:28px;margin-top:18px;">
            <div><div style="font-size:26px;font-weight:800;">{n_av}</div>
                 <div style="font-size:11px;opacity:.6;">Avisos</div></div>
            <div style="width:1px;background:rgba(255,255,255,.2);"></div>
            <div><div style="font-size:26px;font-weight:800;">{n_vt}</div>
                 <div style="font-size:11px;opacity:.6;">Ventas</div></div>
            <div style="width:1px;background:rgba(255,255,255,.2);"></div>
            <div><div style="font-size:26px;font-weight:800;">{pts}</div>
                 <div style="font-size:11px;opacity:.6;">Puntos</div></div>
        </div>
    </div>""", unsafe_allow_html=True)

    prog = min(pts / 500, 1.0)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);border-radius:18px;
                padding:22px;margin-bottom:20px;color:#fff;">
        <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#F5A623;">
            ⭐ MIEMBRO {st.session_state.loyalty_level.upper()}</div>
        <div style="font-size:44px;font-weight:900;margin:6px 0;">{pts} pts</div>
        <div style="display:flex;justify-content:space-between;font-size:11px;opacity:.5;margin-bottom:5px;">
            <span>Silver ({pts})</span><span>Gold (500)</span></div>
        <div style="height:8px;background:rgba(255,255,255,.1);border-radius:4px;">
            <div style="height:100%;width:{prog*100:.0f}%;border-radius:4px;
                background:linear-gradient(90deg,#F5A623,#C41E3A);"></div>
        </div>
    </div>""", unsafe_allow_html=True)

    for icon, label, pid in [
        ("👤","Mis datos","profile_mydata"),
        ("📍","Mis ciudades","profile_cities"),
        ("🔔","Notificaciones","profile_notifconfig"),
        ("🔒","Privacidad","profile_privacy"),
        ("❓","Ayuda","support"),
    ]:
        if st.button(f"{icon} {label}", key=f"prof_{pid}", use_container_width=True):
            go(pid)

    st.divider()
    st.markdown("**💾 Guardar y exportar datos**")
    src = st.session_state.get("_data_source","💾 Datos locales")
    color_src = "#00C9A7" if "Sheets" in src else "#F5A623"
    st.markdown(
        f'<div style="background:rgba(0,0,0,.04);border-radius:10px;'
        f'padding:10px 14px;margin-bottom:14px;font-size:12px;">'
        f'📡 Fuente: <strong style="color:{color_src}">{src}</strong></div>',
        unsafe_allow_html=True)

    _guardar_sheets(sections=None, key="prof_save_all", label="☁️ Guardar TODO en Google Sheets")

    vg1, vg2 = st.columns(2)
    with vg1:
        _guardar_sheets(sections=["vehiculos","publicaciones"], key="prof_save_veh", label="🚗 Guardar Vehículos")
    with vg2:
        _guardar_sheets(sections=["usuarios"], key="prof_save_usr", label="👥 Guardar Usuarios")

    ug1, ug2 = st.columns(2)
    with ug1:
        _guardar_sheets(sections=["historial","publicaciones"], key="prof_save_hist", label="📋 Guardar Historial")
    with ug2:
        _guardar_sheets(sections=["permutas"], key="prof_save_perm", label="🔄 Guardar Permutas")

    eg1, eg2 = st.columns(2)
    with eg1:
        _guardar_sheets(sections=["notificaciones"], key="prof_save_notif", label="🔔 Guardar Notificaciones")
    with eg2:
        download_button_excel(label="⬇️ Exportar TODO a Excel", sections=None, key="prof_dl_all")

    st.divider()
    dark = st.toggle("🌙 Modo oscuro", value=st.session_state.dark_mode, key="prof_dark")
    st.session_state.dark_mode = dark
    st.divider()
    if st.button("🔄 Cambiar cuenta", key="prof_switch", use_container_width=True):
        _cambiar_cuenta()
    if st.button("🚪 Cerrar sesión", key="prof_logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        go("home")


def page_profile_mydata():
    _btn_inicio("profile_mydata")
    if st.button("← Volver", key="myd_back"): go("profile")
    st.markdown("## 👤 Mis datos")
    with st.form("myd_form"):
        c1, c2 = st.columns(2)
        with c1:
            nm = st.text_input("Nombre",  value=st.session_state.user_name,  key="myd_name")
            em = st.text_input("Correo",  value=st.session_state.user_email, key="myd_email")
            ph = st.text_input("Celular", value=st.session_state.user_phone or "", key="myd_phone")
        with c2:
            st.text_input("Documento", value="10.234.567", key="myd_doc")
            st.selectbox("Ciudad",
                ["Bogotá","Medellín","Cali","Barranquilla","Bucaramanga","Pereira"], key="myd_city")
        if st.form_submit_button("💾 Guardar datos en Google Sheets", type="primary", use_container_width=True):
            st.session_state.user_name  = nm
            st.session_state.user_email = em
            st.session_state.user_phone = ph
            for u in st.session_state.get("_usuarios", []):
                if u.get("correo","").lower() == st.session_state.user_email.lower():
                    u["nombre"]  = nm
                    u["correo"]  = em
                    u["celular"] = ph
                    break
            save_and_notify(
                sections=["usuarios"],
                success_msg="✅ Datos del usuario actualizados y guardados en Google Sheets",
            )


def page_profile_cities():
    _btn_inicio("profile_cities")
    if st.button("← Volver", key="cit_back"): go("profile")
    st.markdown("## 📍 Mis ciudades")
    ALL_CITIES = ["Bogotá","Medellín","Cali","Barranquilla","Bucaramanga",
                  "Pereira","Cartagena","Manizales","Ibagué","Pasto"]
    remove = []
    for city in st.session_state.active_cities:
        cc1, cc2 = st.columns([5, 1])
        with cc1:
            is_main = city == st.session_state.active_cities[0]
            st.markdown("""
                f'<div style="background:#fff;border-radius:12px;padding:12px 16px;'
                f'margin-bottom:8px;border:1px solid #E0E0EC;">📍 <strong>{city}</strong>'
                f'{"  <small style=\'color:#C41E3A;\'>(Principal)</small>" if is_main else ""}'
                f'</div>'""", unsafe_allow_html=True)
        if not is_main:
            with cc2:
                if st.button("✕", key=f"cit_rem_{city}", use_container_width=True):
                    remove.append(city)
    for c in remove:
        st.session_state.active_cities.remove(c)
        st.rerun()

    avail = [c for c in ALL_CITIES if c not in st.session_state.active_cities]
    if avail:
        new_c = st.selectbox("Agregar ciudad", avail, key="cit_add_sel")
        if st.button("➕ Agregar", key="cit_add_btn", type="primary"):
            st.session_state.active_cities.append(new_c)
            st.rerun()


def page_profile_notifconfig():
    _btn_inicio("profile_notifconfig")
    if st.button("← Volver", key="nc_back"): go("profile")
    st.markdown("## 🔔 Notificaciones")
    prefs = st.session_state.notif_prefs
    for k, label, desc in [
        ("mensajes","💬 Mensajes nuevos","Cuando alguien te escriba"),
        ("permutas","🔄 Propuestas de permuta","Ofertas de intercambio"),
        ("visitas", "👁️ Visitas a mis avisos","Cuántas personas ven tus publicaciones"),
        ("nuevos",  "🚗 Nuevos vehículos","En tus ciudades de interés"),
        ("resenas", "⭐ Reseñas","Cuando alguien califique tu perfil"),
        ("push",    "📱 Push","Alertas en tu dispositivo"),
    ]:
        nc1, nc2 = st.columns([5, 1])
        with nc1:  st.markdown(f"**{label}**  \n{desc}")
        with nc2:  prefs[k] = st.toggle("", value=prefs.get(k,True), key=f"nc_{k}")
    st.session_state.notif_prefs = prefs
    st.divider()
    page_notifications()


def page_profile_privacy():
    _btn_inicio("profile_privacy")
    if st.button("← Volver al perfil", key="priv_back"): go("profile")
    st.markdown("## 🔒 Privacidad y seguridad")

    if not st.session_state.get("logged_in"):
        st.warning("🔐 Debes iniciar sesión para acceder a esta sección.")
        if st.button("Ingresar", key="priv_login", type="primary"): go("login")
        return

    st.info("🛡️ Tu información es tuya. Solo compartimos lo necesario.")
    for label, default in [
        ("Mostrar mi número de celular", True),
        ("Mostrar correo electrónico",   False),
        ("Perfil público",               True),
        ("Mostrar ciudad exacta",        True),
    ]:
        st.toggle(label, value=default, key=f"priv_{label[:18].replace(' ','_')}")

    st.divider()
    st.markdown("#### 🔑 Cambiar contraseña")
    st.caption(f"Cuenta: **{st.session_state.get('user_email', '')}**")

    # Mostrar mensaje de resultado si viene de submit anterior
    _pw_result = st.session_state.pop("_pw_change_result", None)
    if _pw_result:
        if _pw_result["ok"]:
            st.success(_pw_result["msg"])
        else:
            st.error(_pw_result["msg"])

    with st.form("priv_pw_form"):
        _email_usr    = (st.session_state.get("user_email") or "").strip().lower()
        _u_list       = st.session_state.get("_usuarios", [])
        _u_match      = next((u for u in _u_list
                              if u.get("correo","").strip().lower() == _email_usr), None)
        _tiene_hash   = _u_match and (_u_match.get("password_hash","") or "").strip() \
                        not in ("", "nan", "None")

        if not _tiene_hash:
            st.info("ℹ️ Aún no tienes contraseña configurada. Escribe directamente la nueva.")
            pw_actual = st.text_input("Contraseña actual", type="password",
                                      key="priv_pw_actual", placeholder="(déjala vacía si no tienes)",
                                      value="")
        else:
            pw_actual = st.text_input("Contraseña actual *", type="password", key="priv_pw_actual")

        pw_nueva    = st.text_input("Nueva contraseña *",        type="password", key="priv_pw_nueva")
        pw_confirma = st.text_input("Confirmar nueva contraseña *", type="password", key="priv_pw_conf")

        sub_pw = st.form_submit_button("💾 Guardar nueva contraseña",
                                       use_container_width=True, type="primary")
        if sub_pw:
            errs = []
            if not pw_nueva:              errs.append("Escribe la nueva contraseña")
            if len(pw_nueva) < 6:         errs.append("Mínimo 6 caracteres")
            if pw_nueva != pw_confirma:   errs.append("Las contraseñas no coinciden")
            if errs:
                st.error("❌ " + " · ".join(errs))
            else:
                st.session_state["_pw_change_data"] = {
                    "actual": pw_actual, "nueva": pw_nueva
                }

    # ── Procesar cambio FUERA del form ───────────────────────────────────────
    _pcd = st.session_state.pop("_pw_change_data", None)
    if _pcd:
        import hashlib as _hl
        _hash_actual   = _hl.sha256(_pcd["actual"].encode()).hexdigest() if _pcd["actual"] else ""
        _hash_nueva    = _hl.sha256(_pcd["nueva"].encode()).hexdigest()
        _email_usr     = (st.session_state.get("user_email") or "").strip().lower()
        _u_list        = st.session_state.get("_usuarios", [])
        _u_match       = next((u for u in _u_list
                               if u.get("correo","").strip().lower() == _email_usr), None)

        if not _u_match:
            st.session_state["_pw_change_result"] = {
                "ok": False, "msg": "❌ No se encontró tu usuario. Vuelve a iniciar sesión."}
            st.rerun()
        else:
            _hash_guardado = (_u_match.get("password_hash","") or "").strip()
            _sin_hash      = _hash_guardado in ("", "nan", "None")

            if not _sin_hash and _hash_guardado != _hash_actual:
                st.session_state["_pw_change_result"] = {
                    "ok": False, "msg": "❌ La contraseña actual es incorrecta."}
                st.rerun()
            else:
                _u_match["password_hash"]           = _hash_nueva
                st.session_state.user_password_hash = _hash_nueva
                try:
                    _ok, _msg = _save_pw_hash(_email_usr, _hash_nueva)
                    if _ok:
                        st.session_state["_pw_change_result"] = {
                            "ok": True,
                            "msg": "✅ Contraseña actualizada y guardada en Google Sheets."}
                    else:
                        st.session_state["_pw_change_result"] = {
                            "ok": False,
                            "msg": f"✅ Contraseña cambiada en sesión, pero no se guardó en Sheets.\n\n"
                                   f"🔍 Error: `{_msg}`"}
                except Exception as _e:
                    st.session_state["_pw_change_result"] = {
                        "ok": False,
                        "msg": f"✅ Contraseña cambiada en sesión.\n\n"
                               f"🔍 Excepción: `{str(_e)[:200]}`"}
                st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📱 Auth 2 pasos",  key="priv_2fa", use_container_width=True):
            st.info("Próximamente")
    with c2:
        if st.button("⬇️ Mis datos",     key="priv_dl",  use_container_width=True):
            st.info("📧 Recibirás info en 24h")
    if st.button("🗑️ Eliminar cuenta", key="priv_del",
                 use_container_width=True, type="secondary"):
        st.warning("⚠️ Para eliminar tu cuenta contacta a soporte.")


# ── Login ──────────────────────────────────────────────────────────────────────
def page_login():
    _btn_inicio("login")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:24px 0 16px;">
            <div style="font-size:56px;font-weight:900;letter-spacing:5px;
                background:linear-gradient(135deg,#C41E3A,#F5A623);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">JJGT</div>
            <div style="font-size:11px;color:#6B6B8A;letter-spacing:2px;">VEHÍCULOS COLOMBIA</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("### Ingresar a tu cuenta")

        with st.form("login_form"):
            email = st.text_input("✉️ Correo", placeholder="correo@ejemplo.com", key="lg_email")
            pw    = st.text_input("🔑 Contraseña", type="password", key="lg_pw")
            st.checkbox("Recordarme", key="lg_rem")
            sub = st.form_submit_button("🚀 Ingresar", use_container_width=True, type="primary")
            if sub:
                if not email or not pw:
                    st.error("❌ Completa todos los campos")
                else:
                    # Guardar intento para procesar FUERA del form
                    st.session_state["_login_attempt"] = {"email": email.strip(), "pw": pw}

        # ── Validación FUERA del form (st.rerun() funciona aquí) ─────────────
        _attempt = st.session_state.pop("_login_attempt", None)
        if _attempt:
            import hashlib as _hl
            _lemail   = _attempt["email"]
            _pw_hash  = _hl.sha256(_attempt["pw"].encode()).hexdigest()
            _usuarios = get_usuarios()
            _enorm    = _lemail.lower()

            # 1. ¿Existe el correo?
            _u = next((u for u in _usuarios
                       if u.get("correo","").strip().lower() == _enorm), None)

            if _u is None:
                # Correo no registrado
                st.error(
                    f"❌ El correo **{_lemail}** no está registrado. "
                    f"Verifica que sea correcto o crea una cuenta nueva."
                )
                _a1, _a2 = st.columns(2)
                with _a1:
                    if st.button("📝 Crear cuenta nueva", key="lg_goto_register",
                                 type="primary", use_container_width=True):
                        go("register")
                with _a2:
                    if st.button("🏠 Volver al inicio", key="lg_goto_home",
                                 use_container_width=True):
                        go("home")

            elif _u.get("password_hash","") not in ("", "nan", "None") \
                    and _u.get("password_hash","") != _pw_hash:
                # Correo existe, contraseña incorrecta
                st.error("❌ Contraseña incorrecta. Verifica e intenta de nuevo.")
                if st.button("🔓 Recuperar contraseña", key="lg_forgot_btn"):
                    go("forgot")

            else:
                # Login exitoso
                # Si no tenía hash aún (usuario pre-existente), guardarlo en background
                _hash_vacio = not _u.get("password_hash","").strip() or \
                              _u.get("password_hash","").strip() in ("nan","None","")
                if _hash_vacio:
                    _u["password_hash"] = _pw_hash
                    try:
                        _save_pw_hash(_lemail, _pw_hash)
                    except Exception:
                        pass  # No bloquear el login si falla el guardado

                st.session_state.logged_in          = True
                st.session_state.user_name          = _u.get("nombre", _lemail.split("@")[0].title())
                st.session_state.user_email         = _u.get("correo", _lemail)
                st.session_state.user_phone         = _u.get("celular", "")
                st.session_state.user_city          = _u.get("ciudad", "Bogotá")
                st.session_state.active_cities      = [_u.get("ciudad", "Bogotá")]
                st.session_state.user_password_hash = _pw_hash
                st.session_state.loyalty_points     = int(_u.get("puntos", 0) or 0)
                st.session_state.loyalty_level      = _u.get("nivel", "Bronze")
                st.session_state.history_items      = list(get_history_base())
                st.session_state.notifications      = list(get_notifs_base())
                _nombre_corto = _u.get("nombre", "").split()[0] or "usuario"
                st.session_state["_welcome_msg"] = f"✅ ¡Bienvenido {_nombre_corto}! Sesión iniciada."
                st.session_state.page = "home"
                st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📝 Crear cuenta",        key="lg_register", use_container_width=True): go("register")
        with c2:
            if st.button("🔓 Recuperar contraseña", key="lg_forgot",   use_container_width=True): go("forgot")
        if st.button("🏠 Inicio", key="lg_home", use_container_width=True): go("home")


# ── Registro ───────────────────────────────────────────────────────────────────
def page_register():
    _btn_inicio("register")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:16px 0 12px;">
            <div style="font-size:44px;font-weight:900;letter-spacing:4px;
                background:linear-gradient(135deg,#C41E3A,#F5A623);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">JJGT</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("### Crear cuenta")
        with st.form("register_form"):
            name  = st.text_input("👤 Nombre *",   key="rg_name")
            phone = st.text_input("📱 Celular *",  placeholder="300 000 0000", key="rg_phone")
            email = st.text_input("✉️ Correo *",   key="rg_email")
            city  = st.selectbox("📍 Ciudad",
                ["Bogotá","Medellín","Cali","Barranquilla","Bucaramanga","Pereira","Cartagena"], key="rg_city")
            pw1   = st.text_input("🔑 Contraseña *",        type="password", key="rg_pw1")
            pw2   = st.text_input("🔑 Confirmar contraseña *", type="password", key="rg_pw2")
            terms = st.checkbox("✅ Acepto Términos y condiciones", key="rg_terms")
            sub   = st.form_submit_button("🎉 Crear cuenta", use_container_width=True, type="primary")
            if sub:
                errs = []
                if not name.strip():  errs.append("Nombre")
                if not email.strip(): errs.append("Correo")
                if not phone.strip(): errs.append("Celular")
                if not pw1:           errs.append("Contraseña")
                if pw1 != pw2:        errs.append("Las contraseñas no coinciden")
                if not terms:         errs.append("Acepta los términos")
                if errs:
                    st.error("❌ " + " · ".join(errs))
                else:
                    st.session_state.logged_in     = True
                    st.session_state.user_name     = name
                    st.session_state.user_email    = email
                    st.session_state.user_phone    = phone
                    st.session_state.user_city     = city
                    st.session_state.active_cities = [city]
                    st.session_state.history_items = []
                    st.session_state.notifications = list(get_notifs_base())
                    import hashlib as _hl
                    pw_hash = _hl.sha256(pw1.encode()).hexdigest()
                    new_user = {
                        "id": int(datetime.now().timestamp()),
                        "nombre": name, "correo": email, "celular": phone,
                        "documento": "", "ciudad": city, "rol": "Usuario",
                        "publicaciones": 0, "ventas": 0, "puntos": 50,
                        "nivel": "Bronze",
                        "fecha_registro": datetime.now().strftime("%d/%m/%Y"),
                        "password_hash": pw_hash,
                    }
                    st.session_state.user_password_hash = pw_hash
                    usuarios_list = list(st.session_state.get("_usuarios", []))
                    usuarios_list.append(new_user)
                    st.session_state._usuarios = usuarios_list
                    save_section_silent(["usuarios"])
                    st.success(f"🎉 ¡Bienvenido {name.split()[0]}!")
                    go("home")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔐 Ya tengo cuenta", key="rg_login", type="primary", use_container_width=True): go("login")
        with c2:
            if st.button("🏠 Inicio",           key="rg_home",                  use_container_width=True): go("home")


# ── Recuperar contraseña ───────────────────────────────────────────────────────
def page_forgot():
    _btn_inicio("forgot")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:20px 0 12px;">
          <div style="font-size:44px;font-weight:900;letter-spacing:4px;
              background:linear-gradient(135deg,#C41E3A,#F5A623);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;">JJGT</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("### 🔑 Recuperar contraseña")
        st.caption("Te enviaremos una contraseña temporal a tu correo registrado.")

        with st.form("forgot_form"):
            email = st.text_input("✉️ Correo electrónico registrado", key="fg_email")
            sub   = st.form_submit_button("📧 Enviar contraseña temporal",
                                          use_container_width=True, type="primary")
            if sub:
                if not email.strip():
                    st.error("❌ Escribe tu correo.")
                else:
                    st.session_state["_forgot_attempt"] = email.strip()

        # ── Procesar FUERA del form ───────────────────────────────────────────
        _fg_email = st.session_state.pop("_forgot_attempt", None)
        if _fg_email:
            _usuarios = get_usuarios()
            _u = next((u for u in _usuarios
                       if u.get("correo","").strip().lower() == _fg_email.lower()), None)
            if _u is None:
                st.error(
                    f"❌ El correo **{_fg_email}** no está registrado. "
                    f"Verifica o crea una cuenta nueva."
                )
                if st.button("📝 Crear cuenta nueva", key="fg_register",
                             type="primary", use_container_width=True):
                    go("register")
            else:
                from media_sync import send_recuperacion_email
                _ok, _err = send_recuperacion_email(_u)
                if _ok:
                    # Aplicar el nuevo hash al usuario en session_state y Sheets
                    _reset = st.session_state.pop("_pw_reset_pending", None)
                    if _reset:
                        for u in st.session_state.get("_usuarios", []):
                            if u.get("correo","").strip().lower() == _reset["correo"].lower():
                                u["password_hash"] = _reset["hash"]
                                break
                        try:
                            _save_pw_hash(_reset["correo"], _reset["hash"])
                        except Exception:
                            pass
                    st.success(
                        f"✅ Contraseña temporal enviada a **{_fg_email}**. "
                        f"Revisa tu bandeja de entrada (y carpeta de spam)."
                    )
                    st.info("Usa esa contraseña para ingresar y cámbiala desde tu perfil.")
                else:
                    st.error(f"❌ No se pudo enviar el correo: {_err[:150]}")

        st.divider()
        if st.button("← Volver al login", key="fg_back", use_container_width=True):
            go("login")


# ══════════════════════════════════════════════════════════════════════════════
# HEADER + ROUTER
# ══════════════════════════════════════════════════════════════════════════════
sidebar()

src = st.session_state.get("_data_source", "💾 Datos locales")
user_tag = f"👤 {st.session_state.user_name}" if st.session_state.logged_in else "🔐 Sin sesión"
st.markdown(f"""
<div style="background:linear-gradient(135deg,#C41E3A,#9B1729);color:#fff;
            padding:11px 20px;border-radius:14px;margin-bottom:18px;
            display:flex;align-items:center;justify-content:space-between;">
    <div>
        <span style="font-size:18px;font-weight:900;letter-spacing:3px;">🚗 JJGT</span>
        <span style="font-size:10px;opacity:.7;margin-left:10px;">VEHÍCULOS COLOMBIA</span>
    </div>
    <div style="font-size:11px;opacity:.8;text-align:right;">
        {user_tag}<br>{src}
    </div>
</div>""", unsafe_allow_html=True)

def _actualizar_hoja_acceso(email, nombre, notas=""):
    """Actualiza la hoja 🔐 ACCESO en Sheets con los datos del admin."""
    try:
        from excel_sync import _get_client, _api_call, SHEET_FILE
        client = _get_client()
        if not client:
            return False
        sh  = client.open(SHEET_FILE)
        ws  = sh.worksheet("🔐 ACCESO")
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        filas = [
            ["", "", ""],
            ["", "JJGT — SISTEMA DE GESTIÓN", ""],
            ["", "Venta y Permuta de Vehículos · Colombia", ""],
            ["", "", ""],
            ["", "🔐  ACCESO RESTRINGIDO", ""],
            ["", "Este archivo es de uso exclusivo de la cuenta JJGT", ""],
            ["", "", ""],
            ["", "CUENTA AUTORIZADA", ""],
            ["", email, ""],
            ["", f"Nombre: {nombre}  ·  Nivel: ADMINISTRADOR · JJGT", ""],
            ["", notas or "", ""],
            ["", "", ""],
            ["", "HOJAS DISPONIBLES", ""],
            ["", "🚗 VEHÍCULOS",      "Catálogo completo de vehículos publicados"],
            ["", "👥 USUARIOS",       "Registro de vendedores y compradores"],
            ["", "🔄 PERMUTAS",       "Propuestas de permuta activas e historial"],
            ["", "📋 PUBLICACIONES",  "Avisos publicados con datos del vendedor"],
            ["", "📦 HISTORIAL",      "Transacciones y cierres de negocios"],
            ["", "🔔 NOTIFICACIONES", "Alertas y comunicaciones del sistema"],
            ["", "📊 DASHBOARD",      "Métricas y estadísticas de la plataforma"],
            ["", "⭐ RESEÑAS",        "Calificaciones de vendedores"],
            ["", "", ""],
            ["", f"Actualizado: {now}  |  Versión 2.1", ""],
        ]
        _api_call(ws.clear)
        _api_call(ws.update, "A1", filas)
        return True
    except Exception:
        return False



# ── Administrador ──────────────────────────────────────────────────────────────
def page_admin():
    _btn_inicio("admin")
    is_admin = st.session_state.get("user_email","").strip().lower() == ADMIN_EMAIL.lower()
    if not st.session_state.logged_in or not is_admin:
        st.error("🔐 Acceso restringido — solo administradores.")
        return

    st.markdown("## ⚙️ Panel de Administrador")
    st.caption(f"Sesión: {st.session_state.user_email}")

    tabs = st.tabs(["👥 Usuarios", "🔐 Acceso", "📊 Dashboard"])

    # ══ Tab Usuarios ══════════════════════════════════════════════════════
    with tabs[0]:
        st.markdown("### Gestión de usuarios")
        usuarios = list(st.session_state.get("_usuarios", []))
        if not usuarios:
            st.info("No hay usuarios registrados.")
        else:
            for idx, u in enumerate(usuarios):
                ukey = str(u.get("id","")).replace("-","_")
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    with c1:
                        st.markdown(f"**{u.get('nombre','')}**  ·  {u.get('correo','')}")
                        st.caption(f"📱 {u.get('celular','')}  ·  📍 {u.get('ciudad','')}  ·  Rol: {u.get('rol','')}")
                    with c2:
                        nuevo_rol = st.selectbox("Rol", ["Usuario","Vendedor","Administrador"],
                            index=["Usuario","Vendedor","Administrador"].index(u.get("rol","Usuario"))
                                  if u.get("rol","Usuario") in ["Usuario","Vendedor","Administrador"] else 0,
                            key=f"adm_rol_{ukey}_{idx}", label_visibility="collapsed")
                        if nuevo_rol != u.get("rol"):
                            if st.button("Actualizar rol", key=f"adm_upd_{ukey}_{idx}", use_container_width=True):
                                u["rol"] = nuevo_rol
                                st.session_state._usuarios = usuarios
                                save_section_silent(["usuarios"])
                                st.success(f"Rol actualizado → {nuevo_rol}")
                                st.rerun()
                    with c3:
                        if st.button("🔑", key=f"adm_pw_{ukey}_{idx}",
                                     help="Cambiar contraseña", use_container_width=True):
                            cur = st.session_state.get("_adm_pw_uid")
                            st.session_state["_adm_pw_uid"] = None if cur == u.get("id") else u.get("id")
                            st.rerun()
                    with c4:
                        if u.get("correo","") != ADMIN_EMAIL:
                            if st.button("🗑️", key=f"adm_del_{ukey}_{idx}", help="Eliminar usuario"):
                                st.session_state["_confirm_del_usr"] = u.get("id")
                    if st.session_state.get("_confirm_del_usr") == u.get("id"):
                        st.warning(f"¿Eliminar a **{u.get('nombre','')}**?")
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            if st.button("✅ Confirmar", key=f"adm_delok_{ukey}_{idx}", type="primary", use_container_width=True):
                                st.session_state._usuarios = [x for x in usuarios if x.get("id") != u.get("id")]
                                st.session_state["_confirm_del_usr"] = None
                                save_section_silent(["usuarios"])
                                st.success("Usuario eliminado")
                                st.rerun()
                        with dc2:
                            if st.button("❌ Cancelar", key=f"adm_delno_{ukey}_{idx}", use_container_width=True):
                                st.session_state["_confirm_del_usr"] = None
                                st.rerun()

                # ── Formulario cambio de contraseña inline ───────────────────
                if st.session_state.get("_adm_pw_uid") == u.get("id"):
                    with st.container(border=True):
                        st.markdown(f"#### 🔑 Nueva contraseña para **{u.get('nombre','')}**")
                        st.caption(f"✉️ {u.get('correo','')}")
                        with st.form(key=f"adm_pw_form_{ukey}_{idx}"):
                            pw1 = st.text_input("Nueva contraseña *",        type="password", key=f"adm_pw1_{ukey}_{idx}")
                            pw2 = st.text_input("Confirmar contraseña *",    type="password", key=f"adm_pw2_{ukey}_{idx}")
                            _s1, _s2 = st.columns(2)
                            with _s1:
                                guardar  = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
                            with _s2:
                                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
                            if guardar:
                                if not pw1:
                                    st.error("❌ Escribe la nueva contraseña.")
                                elif len(pw1) < 6:
                                    st.error("❌ Mínimo 6 caracteres.")
                                elif pw1 != pw2:
                                    st.error("❌ Las contraseñas no coinciden.")
                                else:
                                    st.session_state["_adm_pw_save"] = {
                                        "uid": u.get("id"), "correo": u.get("correo",""), "pw": pw1
                                    }
                            if cancelar:
                                st.session_state["_adm_pw_uid"] = None
                                st.rerun()

                # ── Procesar guardado FUERA del form ─────────────────────────
                _psave = st.session_state.get("_adm_pw_save")
                if _psave and str(_psave.get("uid")) == str(u.get("id")):
                    st.session_state.pop("_adm_pw_save")
                    import hashlib as _hl
                    _new_hash = _hl.sha256(_psave["pw"].encode()).hexdigest()
                    # Actualizar en session_state
                    for _u2 in st.session_state.get("_usuarios", []):
                        if str(_u2.get("id")) == str(_psave["uid"]):
                            _u2["password_hash"] = _new_hash
                            break
                    # Guardar directo en Sheets
                    _ok, _msg = _save_pw_hash(_psave["correo"], _new_hash)
                    if _ok:
                        st.success(f"✅ Contraseña actualizada para **{u.get('nombre','')}**")
                        st.session_state["_adm_pw_uid"] = None
                    else:
                        st.warning(f"⚠️ Actualizado en sesión. Error en Sheets: {_msg}")
                    st.rerun()

    # ══ Tab Acceso / Cuenta Admin ══════════════════════════════════════════
    with tabs[1]:
        st.markdown("### 🔐 Configuración de acceso y cuenta administrador")
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);border-radius:12px;
                    padding:16px;margin-bottom:16px;color:#fff;">
            <div style="font-size:11px;opacity:.6;text-transform:uppercase;letter-spacing:1px;">
                Cuenta activa</div>
            <div style="font-size:18px;font-weight:700;margin-top:4px;">
                {name}</div>
            <div style="font-size:13px;opacity:.7;">{email}</div>
            <div style="margin-top:8px;background:rgba(196,30,58,.3);border-radius:6px;
                        padding:3px 10px;display:inline-block;font-size:11px;font-weight:700;">
                ⚙️ ADMINISTRADOR</div>
        </div>""".format(
            name=st.session_state.user_name,
            email=st.session_state.user_email), unsafe_allow_html=True)

        accion = st.radio("Acción", ["✏️ Actualizar cuenta","🔑 Cambiar contraseña","➕ Agregar admin","📋 Ver hoja ACCESO"],
                          horizontal=True, key="adm_accion_radio")

        if accion == "✏️ Actualizar cuenta":
            with st.form("adm_update_form"):
                st.markdown("#### Datos de la cuenta")
                c1, c2 = st.columns(2)
                with c1:
                    adm_nombre = st.text_input("Nombre", value=st.session_state.user_name)
                    adm_tel    = st.text_input("Teléfono", value=st.session_state.get("user_phone",""))
                with c2:
                    adm_email  = st.text_input("Correo", value=st.session_state.user_email)
                    adm_ciudad = st.text_input("Ciudad", value=st.session_state.get("user_city","Bogotá"))
                adm_notas = st.text_area("Notas internas", placeholder="Notas para la hoja ACCESO...", height=60)
                if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                    st.session_state.user_name  = adm_nombre
                    st.session_state.user_email = adm_email
                    st.session_state.user_phone = adm_tel
                    st.session_state.user_city  = adm_ciudad
                    for u in st.session_state.get("_usuarios", []):
                        if u.get("correo","").lower() == ADMIN_EMAIL.lower():
                            u["nombre"] = adm_nombre
                            u["correo"] = adm_email
                            u["celular"] = adm_tel
                            u["ciudad"]  = adm_ciudad
                    _actualizar_hoja_acceso(adm_email, adm_nombre, adm_notas)
                    save_section_silent(["usuarios"], update_dash=False)
                    st.success("✅ Cuenta actualizada en sesión y en Sheets")

        elif accion == "🔑 Cambiar contraseña":
            with st.form("adm_pw_form"):
                st.markdown("#### Nueva contraseña")
                pw1 = st.text_input("Nueva contraseña", type="password", placeholder="••••••••")
                pw2 = st.text_input("Confirmar",        type="password", placeholder="••••••••")
                if st.form_submit_button("🔑 Actualizar contraseña", type="primary", use_container_width=True):
                    if not pw1:
                        st.error("Escribe la nueva contraseña")
                    elif pw1 != pw2:
                        st.error("Las contraseñas no coinciden")
                    else:
                        import hashlib
                        pw_hash = hashlib.sha256(pw1.encode()).hexdigest()
                        for u in st.session_state.get("_usuarios", []):
                            if u.get("correo","").lower() == ADMIN_EMAIL.lower():
                                u["password_hash"] = pw_hash
                        save_section_silent(["usuarios"], update_dash=False)
                        st.success("✅ Contraseña actualizada")

        elif accion == "➕ Agregar admin":
            with st.form("adm_add_form"):
                st.markdown("#### Nuevo administrador")
                st.caption("Agrega un correo adicional con permisos de administrador.")
                new_adm_nombre = st.text_input("Nombre")
                new_adm_email  = st.text_input("Correo electrónico")
                new_adm_pw     = st.text_input("Contraseña inicial", type="password")
                if st.form_submit_button("➕ Agregar administrador", type="primary", use_container_width=True):
                    if not new_adm_email or not new_adm_nombre or not new_adm_pw:
                        st.error("Completa todos los campos")
                    else:
                        import hashlib
                        nuevo_adm = {
                            "id":              int(datetime.now().timestamp()),
                            "nombre":          new_adm_nombre,
                            "correo":          new_adm_email,
                            "celular":         "",
                            "documento":       "",
                            "ciudad":          "Bogotá",
                            "rol":             "Administrador",
                            "publicaciones":   0,
                            "ventas":          0,
                            "puntos":          9999,
                            "nivel":           "Admin",
                            "fecha_registro":  datetime.now().strftime("%d/%m/%Y"),
                            "password_hash":   hashlib.sha256(new_adm_pw.encode()).hexdigest(),
                        }
                        usuarios = list(st.session_state.get("_usuarios", []))
                        usuarios.append(nuevo_adm)
                        st.session_state._usuarios = usuarios
                        save_section_silent(["usuarios"], update_dash=False)
                        st.success(f"✅ Administrador {new_adm_nombre} agregado")

        elif accion == "📋 Ver hoja ACCESO":
            st.markdown("#### Contenido actual de la hoja 🔐 ACCESO")
            try:
                from excel_sync import _get_client, _api_call, SHEET_FILE
                client = _get_client()
                if client:
                    sh   = client.open(SHEET_FILE)
                    ws   = sh.worksheet("🔐 ACCESO")
                    rows = ws.get_all_values()
                    for r in rows:
                        if any(c.strip() for c in r):
                            st.markdown(f"`{'  |  '.join(c for c in r if c.strip())}`")
                    if st.button("🔄 Actualizar hoja ACCESO ahora", key="adm_upd_acceso", type="primary"):
                        _actualizar_hoja_acceso(
                            st.session_state.user_email,
                            st.session_state.user_name, "")
                        st.success("✅ Hoja ACCESO actualizada")
                        st.rerun()
                else:
                    st.warning("Sin conexión a Google Sheets")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        if st.button("📊 Forzar actualizar Dashboard en Sheets", key="adm_dash_btn", use_container_width=True):
            try:
                from excel_sync import _get_client, SHEET_FILE, update_dashboard
                client = _get_client()
                if client:
                    sh = client.open(SHEET_FILE)
                    update_dashboard(sh)
                    st.success("✅ Dashboard sincronizado con Google Sheets")
            except Exception as e:
                st.error(f"Error: {e}")

    # ══ Tab Dashboard en pantalla ═════════════════════════════════════════
    with tabs[2]:
        st.markdown("### 📊 Métricas actuales")
        vehs  = st.session_state.get("_vehicles",[]) + st.session_state.get("user_publications",[])
        users = st.session_state.get("_usuarios",[])
        perms = st.session_state.get("permutas",[])
        hists = st.session_state.get("history_items",[])
        resenas = st.session_state.get("resenas",[])

        m1,m2,m3,m4 = st.columns(4)
        with m1: st.metric("🚗 Vehículos",  len(vehs))
        with m2: st.metric("👥 Usuarios",   len(users))
        with m3: st.metric("🔄 Permutas",   len(perms))
        with m4: st.metric("⭐ Reseñas",    len(resenas))

        st.markdown("#### Por estado")
        e1,e2,e3 = st.columns(3)
        with e1: st.metric("✅ Activos",  sum(1 for v in vehs if str(v.get("estado","Activo")).lower()=="activo"))
        with e2: st.metric("⏸️ Pausados", sum(1 for v in vehs if str(v.get("estado","")).lower()=="pausado"))
        with e3: st.metric("🔒 Cerrados", sum(1 for v in vehs if str(v.get("estado","")).lower()=="cerrado"))

        st.markdown("#### Transacciones")
        t1,t2,t3 = st.columns(3)
        with t1: st.metric("💰 Ventas OK",    sum(1 for h in hists if h.get("status")=="completado"))
        with t2: st.metric("🔄 Permutas OK",  sum(1 for p in perms if p.get("resultado")=="Completada"))
        with t3: st.metric("⭐ Rating prom",  round(sum(r.get("rating",0) for r in resenas)/max(len(resenas),1),1))

        st.markdown("#### Por ciudad")
        ciudad_data = {}
        for v in vehs:
            c = v.get("city","Sin ciudad") or "Sin ciudad"
            ciudad_data[c] = ciudad_data.get(c, 0) + 1
        if ciudad_data:
            import pandas as _pd
            df_c = _pd.DataFrame(
                sorted(ciudad_data.items(), key=lambda x: -x[1]),
                columns=["Ciudad","Vehículos"])
            st.dataframe(df_c, use_container_width=True, hide_index=True)

        if st.button("🔄 Actualizar Dashboard en Sheets", key="adm_dash_update", type="primary"):
            try:
                from excel_sync import _get_client, SHEET_FILE, update_dashboard
                client = _get_client()
                if client:
                    sh = client.open(SHEET_FILE)
                    update_dashboard(sh)
                    st.success("✅ Dashboard sincronizado con Google Sheets")
            except Exception as e:
                st.error(f"Error: {e}")


ROUTES = {
    "home":                page_home,
    "explore":             page_explore,
    "vehicle_detail":      page_vehicle_detail,
    "publish":             page_publish,
    "history":             page_history,
    "notifications":       page_notifications,
    "support":             page_support,
    "profile":             page_profile,
    "profile_mydata":      page_profile_mydata,
    "profile_cities":      page_profile_cities,
    "profile_notifconfig": page_profile_notifconfig,
    "profile_privacy":     page_profile_privacy,
    "permutas":            page_permutas,
    "login":               page_login,
    "register":            page_register,
    "forgot":              page_forgot,
    "help":                page_support,
    "admin":               page_admin,
}
ROUTES.get(st.session_state.page, page_home)()
