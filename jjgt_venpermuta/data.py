"""
JJGT — data.py  v3.0
Carga datos desde Google Sheets (jjgt_gestion).
Fallback automático a datos estáticos si no hay conexión.
"""
import os, json, time, random, gspread, pandas as pd, streamlit as st
from google.oauth2.service_account import Credentials

# ════════════════════════════════════════════════════════════════════════════
# RETRY CON BACKOFF EXPONENCIAL — manejo del error 429 (Quota exceeded)
# ════════════════════════════════════════════════════════════════════════════
_MAX_RETRIES = 6
_BASE_DELAY  = 2.0
_MAX_DELAY   = 64.0

def _is_quota_err(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ["429","quota","rate limit","exhausted","too many"])

def _api_call(fn, *args, **kwargs):
    """
    Envuelve cualquier llamada a la API de Google Sheets con reintentos
    automáticos ante errores 429 (Quota exceeded) o 5xx.

    Backoff exponencial con jitter:
      intento 1 → ~2s · 2 → ~4s · 3 → ~8s · 4 → ~16s · 5 → ~32s · 6 → error
    """
    delay = _BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            recoverable = _is_quota_err(e) or any(
                c in str(e) for c in ["500","502","503","504"])
            if recoverable:
                jitter = random.uniform(0, delay * 0.25)
                time.sleep(min(delay + jitter, _MAX_DELAY))
                delay  = min(delay * 2, _MAX_DELAY)
            else:
                raise

# ── Nombres de hojas ──────────────────────────────────────────────────────────
SHEET_FILE = "jjgt_gestion"
WS_VEH     = "🚗 VEHÍCULOS"
WS_USR     = "👥 USUARIOS"
WS_PERM    = "🔄 PERMUTAS"
WS_PUB     = "📋 PUBLICACIONES"
WS_RES     = "⭐ RESEÑAS"
WS_HIST    = "📦 HISTORIAL"
WS_NOTIF   = "🔔 NOTIFICACIONES"

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _int(v, d=0):
    try:    return int(float(str(v).replace(",","").replace("$","").strip() or d))
    except: return d

def _float(v, d=0.0):
    try:    return float(str(v).replace(",",".").strip() or d)
    except: return d

def _tipo(s):
    t = str(s).lower()
    return "ambos" if ("venta" in t and "permuta" in t) else ("permuta" if "permuta" in t else "venta")

def _cat(nombre, modelo):
    txt = f"{nombre} {modelo}".lower()
    if any(x in txt for x in ["hilux","ranger","oroch","frontier","l200"]): return "pickup"
    if any(x in txt for x in ["tracker","tucson","cx-5","cx5","sportage","explorer",
                                "wrangler","tiguan","ecosport","sorento","duster suv"]): return "suv"
    if any(x in txt for x in ["golf","sandero","stepway","swift","polo",
                                "mazda 2","mazda2","spark","picanto","hb20"]): return "hatchback"
    return "sedan"

GRAD_N = 15

# ════════════════════════════════════════════════════════════════════════════
# CREDENCIALES — lee st.secrets primero, luego secrets.toml como fallback
# ════════════════════════════════════════════════════════════════════════════
def load_credentials_from_toml():
    """
    Obtiene las credenciales de servicio de Google.
    Orden de búsqueda:
      1. st.secrets["sheetsemp"]["credentials_sheet"]  (Streamlit Cloud / local con secrets.toml)
      2. Archivo .streamlit/secrets.toml leído manualmente con toml
      3. None si no se encuentra nada
    Devuelve (dict_credenciales, None)
    """
    # ── Intento 1: st.secrets (funciona tanto en Cloud como en local) ─────────
    try:
        raw = st.secrets["sheetsemp"]["credentials_sheet"]
        if isinstance(raw, str):
            creds = json.loads(raw)
        else:
            # st.secrets devuelve AttrDict → convertir a dict plano
            creds = dict(raw)
        # Validar que tenga las claves mínimas de una service account
        if "private_key" in creds and "client_email" in creds:
            return creds, None
    except Exception:
        pass   # st.secrets no disponible o clave no existe → probar con toml

    # ── Intento 2: leer secrets.toml directamente ─────────────────────────────
    # Buscar el archivo en varias ubicaciones posibles
    toml_candidates = [
        ".streamlit/secrets.toml",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"),
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    for toml_path in toml_candidates:
        if not os.path.isfile(toml_path):
            continue
        try:
            import toml as toml_lib
            config = toml_lib.load(toml_path)
            raw = config.get("sheetsemp", {}).get("credentials_sheet")
            if raw is None:
                continue
            if isinstance(raw, str):
                creds = json.loads(raw)
            else:
                creds = dict(raw)
            if "private_key" in creds and "client_email" in creds:
                return creds, None
        except Exception:
            continue

    return None, None


# ════════════════════════════════════════════════════════════════════════════
# CONEXIÓN — sin @st.cache_resource para evitar problemas de hasheo con dicts
# ════════════════════════════════════════════════════════════════════════════
def get_google_sheets_connection(creds: dict):
    """
    Crea y devuelve un cliente gspread autenticado.
    No usa @st.cache_resource porque los dicts/AttrDicts no son hasheables.
    El cliente se guarda manualmente en st.session_state._gs_client.
    """
    try:
        # Si ya hay un cliente vivo en session_state, reutilizarlo
        existing = st.session_state.get("_gs_client")
        if existing is not None:
            return existing

        credentials = Credentials.from_service_account_info(creds, scopes=_SCOPES)
        client = gspread.authorize(credentials)
        st.session_state._gs_client = client   # guardar para futuras escrituras
        return client
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# CARGA DE UNA HOJA — robusto, sin get_all_records
# ════════════════════════════════════════════════════════════════════════════
def _parse_sheet_values(all_values: list) -> pd.DataFrame:
    """Convierte lista de listas (get_all_values) en DataFrame limpio."""
    if not all_values or len(all_values) < 2:
        return pd.DataFrame()
    raw_headers = all_values[0]
    headers, seen = [], {}
    for h in raw_headers:
        h = str(h).strip()
        if not h:
            h = f"_col{len(headers)}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        headers.append(h)
    data_rows = []
    for row in all_values[1:]:
        padded = (row + [""] * len(headers))[:len(headers)]
        if any(str(v).strip() for v in padded):
            data_rows.append(padded)
    return pd.DataFrame(data_rows, columns=headers)


def load_data_from_sheet(client, sheet_name: str, worksheet_name: str) -> pd.DataFrame:
    """
    Carga una hoja usando get_all_values() con reintentos automáticos ante 429.
    """
    try:
        sheet     = _api_call(client.open, sheet_name)
        worksheet = _api_call(sheet.worksheet, worksheet_name)
        all_values = _api_call(worksheet.get_all_values)
        return _parse_sheet_values(all_values)

    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"⚠️ Hoja '{worksheet_name}' no existe en '{sheet_name}'.")
        return pd.DataFrame()
    except Exception as e:
        if _is_quota_err(e):
            st.warning(
                f"⚠️ Límite de solicitudes alcanzado al cargar '{worksheet_name}'. "
                f"La API de Google Sheets permite 60 lecturas/minuto. "
                f"Espera un momento y recarga la página.")
        else:
            st.warning(f"⚠️ Error cargando '{worksheet_name}': {e}")
        return pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# TRANSFORMADORES  DataFrame → listas internas
# ════════════════════════════════════════════════════════════════════════════
def _df_to_vehicles(df: pd.DataFrame) -> list:
    """Lee hoja de vehículos — acepta nombres de columna con o sin tilde."""
    def g(row, *keys, default=""):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                return v
        return default

    out = []
    for i, row in df.iterrows():
        n = str(g(row, "Nombre", default="")).strip()
        if not n or n.upper().startswith("TOTAL"):
            continue
        m = str(g(row, "Modelo", default="")).strip()
        out.append({
            "id":           _int(g(row, "ID", default=i + 1)),
            "name":         n,
            "model":        m,
            "year":         _int(g(row, "Año", "Ano", default=2022)),
            "price":        _int(g(row, "Precio (COP)", "Precio", default=0)),
            "km":           _int(g(row, "Km", default=0)),
            "fuel":         str(g(row, "Combustible", default="Gasolina")),
            "trans":        str(g(row, "Transmisión", "Transmision", default="Automático")),
            "city":         str(g(row, "Ciudad", default="Bogotá")),
            "color":        str(g(row, "Color", default="—")),
            "type":         _tipo(g(row, "Tipo Aviso", default="Venta")),
            "cat":          _cat(n, m),
            "rating":       _float(g(row, "Calificación", "Calificacion", default=4.5)),
            "reviews":      _int(g(row, "Reseñas", "Resenas", default=0)),
            "estado":       str(g(row, "Estado", default="Activo")),
            "desc":         str(g(row, "Descripción", "Descripcion", default="")),
            "seller":       str(g(row, "Vendedor", default="—")),
            "phone":        str(g(row, "Celular Vendedor", "Celular", default="")),
            "seller_phone": str(g(row, "Celular Vendedor", "Celular", default="")),
            "seller_email": str(g(row, "Correo Vendedor", "Correo", default="")),
            "grad":         i % GRAD_N,
            "fotos_urls":   str(g(row, "Fotos URLs", default="")),
            "video_url":    str(g(row, "Video URL",  default="")),
            "fotos":        [],     # se reconstruye lazy en page_vehicle_detail
            "video":        None,   # idem
            "isUserPub":    False,
        })
    return out


def _df_to_history(df: pd.DataFrame) -> list:
    STATUS_MAP = {
        "activo": "activo", "pendiente": "pendiente",
        "completado": "completado", "cancelado": "cancelled", "cerrado": "completado",
    }
    out = []
    for _, row in df.iterrows():
        hid = str(row.get("ID", "")).strip()
        if not hid or hid.upper() in ("ID", "TOTALES"):
            continue
        raw_est = str(row.get("Estado", "activo")).strip().lower()
        out.append({
            "id":     hid,
            "name":   str(row.get("Vehículo", row.get("Vehiculo", ""))),
            "price":  _int(row.get("Precio Final", row.get("Precio", 0))),
            "date":   str(row.get("Fecha", "—")),
            "status": STATUS_MAP.get(raw_est, "activo"),
            "type":   str(row.get("Tipo", "Publicación")),
            "km":     0,
            "seller": str(row.get("Vendedor", "—")),
            "buyer":  str(row.get("Comprador / Permutante", row.get("Comprador", "—"))),
            "city":   str(row.get("Ciudad", "Bogotá")),
            "notes":  str(row.get("Notas", "—")),
            "points": _int(row.get("Puntos Generados", 0)),
        })
    return out


def _df_to_notifications(df: pd.DataFrame) -> list:
    ICON_MAP = {
        "mensaje": "💬", "visita": "👁️", "permuta": "🔄", "reseña": "⭐",
        "sistema": "✅", "alerta": "🔔", "puntos": "🏆", "favorito": "❤️",
    }
    out = []
    for _, row in df.iterrows():
        nid = str(row.get("ID", "")).strip()
        if not nid or nid.upper() == "ID":
            continue
        tipo  = str(row.get("Tipo", "Sistema")).strip()
        leida = str(row.get("Leída", row.get("Leida", "Sí"))).strip().lower()
        fecha = str(row.get("Fecha", "—"))
        grupo = ("Hoy" if "26/02/2024" in fecha else "Ayer" if "25/02/2024" in fecha else "Esta semana")
        out.append({
            "id":     nid,
            "group":  grupo,
            "icon":   ICON_MAP.get(tipo.lower(), "🔔"),
            "tipo":   tipo,
            "title":  str(row.get("Título", row.get("Titulo", "Notificación"))),
            "desc":   str(row.get("Descripción", row.get("Descripcion", ""))),
            "user":   str(row.get("Usuario Destino", "—")),
            "date":   fecha,
            "time":   str(row.get("Hora", "—")),
            "unread": leida in ("no", "false", "0"),
            "action": str(row.get("Acción", row.get("Accion", "—"))),
        })
    return out


def _df_to_permutas(df: pd.DataFrame) -> list:
    """Lee hoja de permutas — acepta nombres con/sin punto abreviado."""
    out = []
    for _, row in df.iterrows():
        pid = str(row.get("ID", "")).strip()
        if not pid or pid.upper() == "ID":
            continue
        out.append({
            "id":              pid,
            "veh_oferta":      str(row.get("Veh. Ofertado", row.get("Veh Ofertado", ""))),
            "vendedor_oferta": str(row.get("Vendedor Oferta", "")),
            "veh_destino":     str(row.get("Veh. Solicitado", row.get("Veh Solicitado", ""))),
            "propietario":     str(row.get("Propietario Destino", row.get("Propietario", ""))),
            "ciudad":          str(row.get("Ciudad", "Bogotá")),
            "valor_oferta":    _int(row.get("Valor Estimado", 0)),
            "diferencia":      _int(row.get("Diferencia", 0)),
            "fecha":           str(row.get("Fecha", "—")),
            "estado":          str(row.get("Estado", "Activa")),
            "mensaje":         str(row.get("Mensaje", "")),
            "resultado":       str(row.get("Resultado", "Pendiente")),
        })
    return out


def _df_to_usuarios(df: pd.DataFrame) -> list:
    """Lee hoja de usuarios — acepta 'Nombre Completo' o 'Nombre'."""
    out = []
    for _, row in df.iterrows():
        # El xlsx exportado usa "Nombre", el original usa "Nombre Completo"
        n = str(row.get("Nombre Completo", row.get("Nombre", ""))).strip()
        if not n or n.upper() in ("TOTALES", "NOMBRE COMPLETO", "NOMBRE"):
            continue
        out.append({
            "id":             _int(row.get("ID", 0)),
            "nombre":         n,
            "correo":         str(row.get("Correo", "")),
            "celular":        str(row.get("Celular", "")),
            "documento":      str(row.get("Documento", "")),
            "ciudad":         str(row.get("Ciudad", "Bogotá")),
            "rol":            str(row.get("Rol", "Usuario")),
            "publicaciones":  _int(row.get("Publicaciones", 0)),
            "ventas":         _int(row.get("Ventas", 0)),
            "puntos":         _int(row.get("Puntos", 0)),
            "nivel":          str(row.get("Nivel", "Bronze")),
            "fecha_registro": str(row.get("Fecha Registro", "—")),
            "password_hash":  str(row.get("Password Hash", "")),
        })
    return out


# ════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN ÚNICA POR SESIÓN
# ════════════════════════════════════════════════════════════════════════════
def load_from_xlsx(file_bytes: bytes) -> bool:
    """
    Carga datos desde un archivo .xlsx con la misma estructura que jjgt_gestion.
    Hojas esperadas (por nombre exacto o contenido de columnas):
      🚗 VEHÍCULOS, 👥 USUARIOS, 🔄 PERMUTAS, 📦 HISTORIAL, 🔔 NOTIFICACIONES
    Devuelve True si al menos la hoja de vehículos se cargó con datos.
    """
    import io as _io
    try:
        xls = pd.ExcelFile(_io.BytesIO(file_bytes))
    except Exception as e:
        st.error(f"❌ No se pudo leer el archivo Excel: {e}")
        return False

    # Mapeo de nombres alternativos de hoja → clave interna
    SHEET_MAP = {
        WS_VEH:    "veh",   "VEHICULOS": "veh",   "VEHÍCULOS": "veh",
        WS_USR:    "usr",   "USUARIOS":  "usr",
        WS_PERM:   "perm",  "PERMUTAS":  "perm",
        WS_PUB:    "pub",   "PUBLICACIONES": "pub",
        WS_HIST:   "hist",  "HISTORIAL": "hist",
        WS_NOTIF:  "notif", "NOTIFICACIONES": "notif",
    }

    dfs = {"veh": pd.DataFrame(), "usr": pd.DataFrame(),
           "perm": pd.DataFrame(), "pub": pd.DataFrame(),
           "hist": pd.DataFrame(), "notif": pd.DataFrame()}

    for sheet in xls.sheet_names:
        key = SHEET_MAP.get(sheet) or SHEET_MAP.get(sheet.upper().strip())
        if key:
            try:
                dfs[key] = xls.parse(sheet)
            except Exception:
                pass

    vehs = _df_to_vehicles(dfs["veh"])
    if not vehs:
        st.error("❌ El archivo no contiene vehículos válidos. "
                 "Verifica que la hoja se llame '🚗 VEHÍCULOS'.")
        return False

    pubs_xlsx = _reconstruir_media_local(_df_to_publicaciones(dfs.get("pub", pd.DataFrame())))
    st.session_state._vehicles      = _reconstruir_media_local(vehs)
    st.session_state._publicaciones = pubs_xlsx
    st.session_state._usuarios      = _df_to_usuarios(dfs["usr"])
    st.session_state._permutas_base = _df_to_permutas(dfs["perm"])
    st.session_state._history_base  = _df_to_history(dfs["hist"])
    st.session_state._notifs_base   = _df_to_notifications(dfs["notif"])
    # Cargar publicaciones en user_publications
    if pubs_xlsx:
        existing = {p.get("id") for p in st.session_state.get("user_publications", [])}
        nuevas = [p for p in pubs_xlsx if p.get("id") not in existing]
        st.session_state.setdefault("user_publications", [])
        st.session_state["user_publications"] = nuevas + st.session_state["user_publications"]
    st.session_state._data_source   = "📂 Archivo Excel"
    st.session_state._xlsx_loaded   = True
    st.session_state._data_loaded   = False   # permitir que init_data detecte xlsx
    return True


def _df_to_resenas(df: pd.DataFrame) -> list:
    """Convierte hoja RESEÑAS en lista de dicts."""
    if df is None or df.empty:
        return []
    out = []
    def g(row, *keys, default=""):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip() not in ("","nan","None"):
                return v
        return default
    for i, row in df.iterrows():
        rid = str(g(row, "ID", default="")).strip()
        if not rid:
            continue
        out.append({
            "id":          rid,
            "pub_id":      str(g(row, "Pub ID",       default="")),
            "vehiculo":    str(g(row, "Vehiculo",      default="")),
            "vendedor":    str(g(row, "Vendedor",      default="")),
            "autor":       str(g(row, "Autor",         default="")),
            "rating":      int(float(str(g(row, "Calificacion", default=0)) or 0)),
            "comentario":  str(g(row, "Comentario",   default="")),
            "fecha":       str(g(row, "Fecha",         default="")),
            "verificada":  str(g(row, "Verificada",   default="No")).lower() == "si",
        })
    return out


def _df_to_publicaciones(df: pd.DataFrame) -> list:
    """
    Convierte la hoja PUBLICACIONES en lista de vehículos con isUserPub=True.
    Columnas: ID Pub, Vehiculo, Año, Precio, Tipo Aviso, Estado Pub,
              Vendedor, Correo Vendedor, Celular Vendedor, Ciudad,
              Fotos URLs, Video URL
    """
    if df is None or df.empty:
        return []

    def g(row, *keys, default=""):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                return v
        return default

    out = []
    for i, row in df.iterrows():
        pid = str(g(row, "ID Pub", "ID", default="")).strip()
        if not pid:
            continue
        vehiculo = str(g(row, "Vehiculo", "Vehículo", "Nombre", default="")).strip()
        if not vehiculo:
            continue

        # Separar marca y modelo del campo Vehiculo (ej: "ford explorer")
        partes = vehiculo.split(" ", 1)
        marca  = partes[0].capitalize() if partes else vehiculo
        modelo = partes[1] if len(partes) > 1 else ""

        fotos_urls = str(g(row, "Fotos URLs", "fotos_urls", default="")).strip()
        video_url  = str(g(row, "Video URL",  "video_url",  default="")).strip()

        out.append({
            "id":           pid,
            "name":         marca,
            "model":        modelo,
            "year":         _int(g(row, "Año", "Ano", default=2022)),
            "price":        _int(g(row, "Precio", "Precio (COP)", default=0)),
            "km":           _int(g(row, "Km", default=0)),
            "fuel":         str(g(row, "Combustible", default="Gasolina")),
            "trans":        str(g(row, "Transmisión", "Transmision", default="Automático")),
            "city":         str(g(row, "Ciudad", default="Bogotá")),
            "color":        str(g(row, "Color", default="—")),
            "type":         _tipo(g(row, "Tipo Aviso", default="Venta")),
            "cat":          "sedan",
            "rating":       0,
            "reviews":      0,
            "estado":       str(g(row, "Estado Pub", "Estado", default="Activo")),
            "desc":         str(g(row, "Descripción", "Descripcion", default="")),
            "seller":       str(g(row, "Vendedor", default="—")),
            "phone":        str(g(row, "Celular Vendedor", "Celular", default="")),
            "seller_phone": str(g(row, "Celular Vendedor", "Celular", default="")),
            "seller_email": str(g(row, "Correo Vendedor",  "Correo",  default="")),
            "grad":         i % GRAD_N,
            "fotos_urls":   fotos_urls,
            "video_url":    video_url,
            "fotos":        [],
            "video":        None,
            "isUserPub":    True,
            "fecha":        str(g(row, "Fecha Pub", "Fecha", default="")),
        })
    return out


def _reconstruir_media_local(vehicles: list) -> list:
    """
    Para cada vehículo con fotos_urls o video_url, lee los archivos
    desde JJGT_Media/ (relativo al directorio del script) y carga
    los bytes en memoria como data_uri para mostrar en la galería.
    """
    from media_sync import _leer_local, _a_data_uri
    import os
    for v in vehicles:
        fotos_csv = (v.get("fotos_urls") or "").strip()
        video_url = (v.get("video_url")  or "").strip()
        if not fotos_csv and not video_url:
            continue

        # ── Fotos ──────────────────────────────────────────────────────────
        fotos = []
        for ref in [r.strip() for r in fotos_csv.split(",") if r.strip()]:
            raw = _leer_local(ref)
            if raw:
                fotos.append({
                    "name":     os.path.basename(ref),
                    "bytes":    raw,
                    "path":     ref,
                    "data_uri": _a_data_uri(raw, 800),
                })
        if fotos:
            v["fotos"] = fotos

        # ── Video ───────────────────────────────────────────────────────────
        if video_url:
            raw = _leer_local(video_url)
            if raw:
                v["video"] = {
                    "name":  os.path.basename(video_url),
                    "bytes": raw,
                    "path":  video_url,
                }

    return vehicles


def init_data():
    """
    Prioridad de carga:
      1. Google Sheets  → SIEMPRE se usa si hay credenciales, sin fallback a estáticos.
         Si una hoja está vacía en Sheets, esa lista queda vacía (no se mezcla con estáticos).
      2. Excel subido   → si el usuario cargó un .xlsx se usa en lugar de Sheets.
      3. Sin conexión   → lista vacía (no datos estáticos inventados).
    Solo se ejecuta UNA VEZ por sesión (_data_loaded).
    """
    if st.session_state.get("_data_loaded"):
        return

    # ── Prioridad 1: Google Sheets ───────────────────────────────────────────
    creds, _ = load_credentials_from_toml()
    client    = None

    if creds:
        client = get_google_sheets_connection(creds)

    if client:
        st.session_state._gs_client   = client
        st.session_state._data_source = "☁️ Google Sheets"
        try:
            _hojas = [
                (WS_VEH,  "🚗 Vehículos",      "_vehicles",      _df_to_vehicles),
                (WS_PUB,  "📋 Publicaciones",   "_publicaciones", _df_to_publicaciones),
                (WS_RES,  "⭐ Reseñas",         "_resenas",        _df_to_resenas),
                (WS_USR,  "👥 Usuarios",        "_usuarios",      _df_to_usuarios),
                (WS_PERM, "🔄 Permutas",        "_permutas_base", _df_to_permutas),
                (WS_HIST, "📦 Historial",       "_history_base",  _df_to_history),
                (WS_NOTIF,"🔔 Notificaciones",  "_notifs_base",   _df_to_notifications),
            ]
            errores = []
            with st.status("📊 Cargando jjgt_gestion…", expanded=True) as status:
                for ws_name, label, ss_key, transformer in _hojas:
                    st.write(f"Leyendo {label}…")
                    try:
                        df = load_data_from_sheet(client, SHEET_FILE, ws_name)
                        datos = transformer(df)
                        # Reconstruir media local desde JJGT_Media
                        if ss_key in ("_vehicles", "_publicaciones"):
                            datos = _reconstruir_media_local(datos)
                        st.session_state[ss_key] = datos
                        # Cargar publicaciones en user_publications para que aparezcan en la app
                        if ss_key == "_publicaciones" and datos:
                            existing = {p.get("id") for p in st.session_state.get("user_publications", [])}
                            nuevas = [p for p in datos if p.get("id") not in existing]
                            st.session_state.setdefault("user_publications", [])
                            st.session_state["user_publications"] = nuevas + st.session_state["user_publications"]
                        if ss_key == "_resenas" and datos:
                            st.session_state["resenas"] = datos
                        n_rows = len(st.session_state[ss_key])
                        st.write(f"✅ {label}: {n_rows} registros")
                        time.sleep(0.6)   # pausa entre lecturas para no saturar cuota
                    except Exception as e_hoja:
                        st.session_state[ss_key] = []
                        msg = str(e_hoja)
                        if _is_quota_err(e_hoja):
                            msg = (f"⚠️ Cuota excedida ({label}). "
                                   f"Espera ~1 minuto y recarga la página. "
                                   f"(Error 429 – Quota exceeded)")
                        else:
                            msg = f"⚠️ Error en {label}: {e_hoja}"
                        st.write(msg)
                        errores.append(label)

                if errores:
                    status.update(
                        label=f"⚠️ Cargado con errores en: {', '.join(errores)}",
                        state="error", expanded=True)
                else:
                    n = len(st.session_state.get("_vehicles", []))
                    status.update(
                        label=f"☁️ jjgt_gestion cargado · {n} vehículos",
                        state="complete", expanded=False)

        except Exception as e:
            msg = str(e)
            if _is_quota_err(e):
                st.warning(
                    "⚠️ **Límite de lectura de Google Sheets alcanzado (Error 429)**\n\n"
                    "La API permite 60 solicitudes/minuto por usuario. "
                    "Espera ~1 minuto y recarga la página.\n\n"
                    "Mientras tanto puedes cargar un archivo Excel con los mismos datos "
                    "usando el panel '📂 Cargar Excel' del menú lateral.")
            else:
                st.warning(f"⚠️ Error cargando hojas: {msg}")
            st.session_state._vehicles      = []
            st.session_state._usuarios      = []
            st.session_state._permutas_base = []
            st.session_state._history_base  = []
            st.session_state._notifs_base   = []

        # Eliminar de _vehicles cualquier ID que ya esté en publicaciones
        # Normalizar IDs: strip, upper para comparación robusta
        pub_ids = {
            str(p.get("id","")).strip().upper()
            for p in st.session_state.get("user_publications", [])
        }
        # También indexar por nombre+año como fallback
        pub_names = {
            f"{str(p.get('name','')).strip().upper()}_{str(p.get('year',''))}".strip("_")
            for p in st.session_state.get("user_publications", [])
        }
        if pub_ids:
            st.session_state._vehicles = [
                v for v in st.session_state.get("_vehicles", [])
                if str(v.get("id","")).strip().upper() not in pub_ids
                and f"{str(v.get('name','')).strip().upper()}_{str(v.get('year',''))}".strip("_") not in pub_names
            ]

        # Reconstruir media de publicaciones del usuario si las hay
        pubs = st.session_state.get("user_publications", [])
        if pubs:
            st.session_state["user_publications"] = _reconstruir_media_local(pubs)

        st.session_state._data_loaded = True
        return

    # ── Prioridad 2: Excel subido por el usuario ─────────────────────────────
    if st.session_state.get("_xlsx_loaded"):
        # Reconstruir media de publicaciones del usuario si las hay
        pubs = st.session_state.get("user_publications", [])
        if pubs:
            st.session_state["user_publications"] = _reconstruir_media_local(pubs)
        st.session_state._data_source = "📂 Archivo Excel"
        st.session_state._data_loaded = True
        return

    # ── Sin ninguna fuente disponible ────────────────────────────────────────
    st.session_state._vehicles      = []
    st.session_state._usuarios      = []
    st.session_state._permutas_base = []
    st.session_state._history_base  = []
    st.session_state._notifs_base   = []
    st.session_state._data_source   = "⚠️ Sin fuente de datos"
    st.session_state._gs_client     = None
    st.session_state._data_loaded   = True


# ════════════════════════════════════════════════════════════════════════════
# RECONSTRUCCIÓN LAZY DE MEDIA (fotos/video desde Drive)
# ════════════════════════════════════════════════════════════════════════════
def reconstruct_media(v: dict) -> dict:
    """
    Reconstruye fotos/video desde URLs de Drive.

    FIX v2.3: La lógica anterior bloqueaba la reconstrucción si fotos[]
    estaba vacío (vehículos de Sheets siempre llegan con fotos:[]).
    Ahora la condición correcta es:
      - ¿Ya tiene preview_url? → ya fue reconstruido, no tocar.
      - ¿Tiene fotos_urls en Drive? → reconstruir siempre.
    """
    fotos_list = v.get("fotos") or []
    video_dict = v.get("video")
    fotos_urls = (v.get("fotos_urls") or "").strip()
    video_url  = (v.get("video_url")  or "").strip()

    # ¿Ya tiene preview_url? → ya fue reconstruido con el nuevo sistema
    fotos_ya_reconstruidas = any(
        isinstance(f, dict) and f.get("preview_url")
        for f in fotos_list
    )
    # ¿Ya hay bytes en memoria (publicación recién subida)?
    fotos_tienen_bytes = any(
        isinstance(f, dict) and f.get("bytes")
        for f in fotos_list
    )
    # ¿Video ya tiene embed_url?
    video_ok = isinstance(video_dict, dict) and (
        video_dict.get("embed_url") or video_dict.get("bytes"))

    # Si ya está todo listo, no hacer nada
    if fotos_ya_reconstruidas and (video_ok or not video_url):
        return v
    # Si tiene bytes propios (publicación nueva), no pisar
    if fotos_tienen_bytes and (video_ok or not video_url):
        return v
    # Sin URLs de Drive → nada que hacer
    if not fotos_urls and not video_url:
        return v

    try:
        from media_sync import load_media_from_urls
        fotos_nuevas, video_nuevo = load_media_from_urls(fotos_urls, video_url)

        # Fotos: reconstruir si llegaron datos Y no había bytes propios
        if fotos_nuevas and not fotos_tienen_bytes:
            v["fotos"] = fotos_nuevas

        # Video: reconstruir si llegó embed_url Y no había bytes propios
        if video_nuevo and not video_ok:
            v["video"] = video_nuevo

        # Sincronizar referencia en session_state
        sv = st.session_state.get("selected_vehicle")
        if sv is not None and sv.get("id") == v.get("id"):
            st.session_state.selected_vehicle = v

    except Exception:
        pass   # silencioso — galería mostrará placeholder

    return v


# ── Getters públicos — devuelven lista vacía si no hay datos cargados ─────────
def get_vehicles():      return st.session_state.get("_vehicles",      [])
def get_usuarios():      return st.session_state.get("_usuarios",      [])
def get_permutas_base(): return st.session_state.get("_permutas_base", [])
def get_history_base():  return st.session_state.get("_history_base",  [])
def get_notifs_base():   return st.session_state.get("_notifs_base",   [])


# ════════════════════════════════════════════════════════════════════════════

CHATBOT_REPLIES = {
    "publicar": "Para publicar ve a 'Publicar' en el menú. Necesitarás fotos/video y datos del vehículo. ¿Tienes alguna duda?",
    "permuta":  "La permuta es muy sencilla. Busca el vehículo y toca 'Proponer permuta'. ¡Sin intermediarios! 🔄",
    "precio":   "Para verificar precios compara vehículos similares en la plataforma. ¿Qué marca te interesa?",
    "soat":     "El SOAT y tecnomecánica son responsabilidad del vendedor. Revisa en persona antes de cerrar.",
    "pago":     "Usa consignación bancaria o transferencia. Nunca envíes dinero sin ver el vehículo.",
    "seguro":   "Verificamos identidad de usuarios. Siempre revisa el vehículo en persona.",
    "gratis":   "¡Publicar es completamente gratis! Hasta 3 avisos activos.",
    "puntos":   "Ganas puntos por publicar, completar ventas e invitar amigos.",
    "default":  "Nuestro equipo está disponible Lun–Sáb 8am–6pm. ¿Te contactamos por WhatsApp? 😊",
}
