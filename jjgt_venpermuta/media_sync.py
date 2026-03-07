"""
JJGT — media_sync.py  v5.0
Almacenamiento local en JJGT_Media/. Simple y directo.
"""
from __future__ import annotations
import io, os, time, random, mimetypes, base64
import streamlit as st

MEDIA_DIR      = "JJGT_Media"
DRIVE_FOLDER_ID = "10CRIboHnD1-_v6kEN2BlBrJWFrqivJ8r"
_MAX_RETRIES   = 3
_BASE_DELAY    = 2.0
_MAX_DELAY     = 16.0


# ─── rutas ────────────────────────────────────────────────────────────────────
def _pub_dir(pub_id):
    # Usar siempre el directorio de trabajo actual (donde está app.py)
    path = os.path.join(os.getcwd(), MEDIA_DIR, str(pub_id))
    os.makedirs(path, exist_ok=True)
    return path


def _leer(ruta):
    """Lee bytes de una ruta local. Soporta rutas absolutas y relativas."""
    if not ruta:
        return None
    ruta = ruta.strip()

    def _abrir(p):
        try:
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    return f.read()
        except Exception:
            pass
        return None

    # 1. Ruta tal cual (funciona si es absoluta y válida)
    r = _abrir(ruta)
    if r:
        return r

    # 2. Normalizar separadores Windows/Unix
    ruta_norm = os.path.normpath(ruta.replace("/", os.sep))
    r = _abrir(ruta_norm)
    if r:
        return r

    # 3. Extraer segmento JJGT_Media/... y buscar desde cwd
    ruta_unix = ruta.replace("\\", "/")
    if "JJGT_Media" in ruta_unix:
        idx = ruta_unix.find("JJGT_Media")
        segmento = ruta_unix[idx:].replace("/", os.sep)
        for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
            r = _abrir(os.path.join(base, segmento))
            if r:
                return r

    return None


def _guardar(pub_id, nombre, data):
    """Guarda bytes y retorna ruta relativa JJGT_Media/pub_id/nombre."""
    carpeta  = _pub_dir(pub_id)
    filepath = os.path.join(carpeta, nombre)
    with open(filepath, "wb") as f:
        f.write(data)
    # Retornar SIEMPRE ruta relativa desde JJGT_Media — portable entre PCs
    return f"JJGT_Media/{pub_id}/{nombre}"


def _a_data_uri(raw, max_w=600):
    """Convierte bytes de imagen a data URI base64."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        img.thumbnail((max_w, max_w))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        b64 = base64.b64encode(raw).decode()
    return f"data:image/jpeg;base64,{b64}"


# ─── Drive (backup opcional) ──────────────────────────────────────────────────
def _is_quota_err(e):
    return any(x in str(e).lower() for x in ["429","quota","rate limit","exhausted","too many"])

def _retry(fn, *args, **kwargs):
    delay = _BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            if _is_quota_err(e) or any(c in str(e) for c in ["500","502","503","504"]):
                time.sleep(min(delay + random.uniform(0, delay*0.25), _MAX_DELAY))
                delay = min(delay*2, _MAX_DELAY)
            else:
                raise

def _get_drive_service():
    svc = st.session_state.get("_drive_service")
    if svc:
        return svc
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        from data import load_credentials_from_toml
        creds_dict, _ = load_credentials_from_toml()
        if not creds_dict:
            return None
        creds = Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/drive"])
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        st.session_state._drive_service = svc
        return svc
    except Exception:
        return None

def _subir_drive_bg(ruta_local, nombre):
    """Sube a Drive como backup sin bloquear."""
    try:
        from googleapiclient.http import MediaIoBaseUpload
        svc = _get_drive_service()
        if not svc or not DRIVE_FOLDER_ID.strip():
            return
        raw  = _leer(ruta_local)
        if not raw:
            return
        mime = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
        media = MediaIoBaseUpload(io.BytesIO(raw), mimetype=mime, resumable=False)
        meta  = {"name": nombre, "parents": [DRIVE_FOLDER_ID.strip()]}
        _retry(svc.files().create(body=meta, media_body=media, fields="id").execute)
    except Exception:
        pass


# ─── API pública ──────────────────────────────────────────────────────────────
def upload_media(pub_id, fotos, video):
    """Guarda fotos/video en JJGT_Media/<pub_id>/. Retorna (fotos_csv, video_path)."""
    os.makedirs(MEDIA_DIR, exist_ok=True)
    foto_paths = []
    for i, f in enumerate(fotos or []):
        nombre = f"foto_{i:02d}_{f.get('name','foto.jpg')}"
        ruta   = _guardar(pub_id, nombre, f["bytes"])
        foto_paths.append(ruta)
        _subir_drive_bg(ruta, f"{pub_id}_{nombre}")
        time.sleep(0.1)

    video_path = ""
    if video:
        nombre     = f"video_{video.get('name','video.mp4')}"
        video_path = _guardar(pub_id, nombre, video["bytes"])
        _subir_drive_bg(video_path, f"{pub_id}_{nombre}")

    return ",".join(foto_paths), video_path


def load_media_from_urls(fotos_csv, video_url):
    """Lee fotos/video desde rutas locales. Retorna (lista_fotos, video_dict)."""
    fotos = []
    for ruta in [r.strip() for r in (fotos_csv or "").split(",") if r.strip()]:
        raw = _leer(ruta)
        if raw:
            fotos.append({
                "name":     os.path.basename(ruta),
                "bytes":    raw,
                "path":     ruta,
                "data_uri": _a_data_uri(raw, 800),
            })

    video = None
    vpath = (video_url or "").strip()
    if vpath:
        raw = _leer(vpath)
        if raw:
            video = {"name": os.path.basename(vpath), "bytes": raw, "path": vpath}

    return fotos, video


def get_portada_data_uri(v, max_w=400):
    """
    Retorna data URI de la portada del vehículo.
    Orden: data_uri cacheado → bytes en fotos → leer desde fotos_urls
    """
    import base64 as _b64

    def _bytes_a_uri(raw):
        """Convierte bytes a data URI, con o sin PIL."""
        if not raw:
            return ""
        try:
            from PIL import Image as _PIL
            img = _PIL.open(io.BytesIO(raw))
            img.thumbnail((max_w, max_w))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            data = buf.getvalue()
        except Exception:
            data = raw
        return "data:image/jpeg;base64," + _b64.b64encode(data).decode()

    # 1. Buscar en fotos en memoria
    for f in (v.get("fotos") or []):
        if not isinstance(f, dict):
            continue
        if f.get("data_uri"):
            return f["data_uri"]
        raw = f.get("bytes")
        if raw:
            uri = _bytes_a_uri(raw)
            if uri:
                f["data_uri"] = uri  # cachear
                return uri

    # 2. Leer desde ruta en fotos_urls
    fotos_csv = (v.get("fotos_urls") or "").strip()
    if not fotos_csv:
        return ""

    for ruta in [r.strip() for r in fotos_csv.split(",") if r.strip()]:
        raw = _leer(ruta)
        if raw:
            uri = _bytes_a_uri(raw)
            if uri:
                # Cachear en fotos para no releer
                if not isinstance(v.get("fotos"), list):
                    v["fotos"] = []
                v["fotos"].insert(0, {
                    "name":     os.path.basename(ruta),
                    "bytes":    raw,
                    "path":     ruta,
                    "data_uri": uri,
                })
                return uri

    return ""


def _extract_file_id(url):
    import re
    for pat in [r"[?&]id=([a-zA-Z0-9_-]+)", r"/file/d/([a-zA-Z0-9_-]+)"]:
        m = re.search(pat, url or "")
        if m:
            return m.group(1)
    return None

# alias para compatibilidad
_read_local = _leer


def show_fotos(fotos, cols=3):
    if not fotos:
        return
    columnas = st.columns(min(len(fotos), cols))
    for i, foto in enumerate(fotos):
        with columnas[i % cols]:
            uri = foto.get("data_uri") or ""
            if not uri and foto.get("bytes"):
                uri = _a_data_uri(foto["bytes"])
            if uri:
                st.markdown(f'<img src="{uri}" style="width:100%;border-radius:8px;">',
                            unsafe_allow_html=True)


def show_video(video=None):
    if not video:
        return
    raw = video.get("bytes")
    if raw:
        try:
            st.video(io.BytesIO(raw))
        except Exception:
            st.caption("⚠️ No se pudo reproducir el video.")


def send_permuta_email(destinatarios, propuesta, vehiculo_ofrecido, vehiculo_deseado):
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text      import MIMEText

        # Leer credenciales desde st.secrets["emails"]
        smtp_user = st.secrets["emails"]["smtp_user"]
        smtp_pass = st.secrets["emails"]["smtp_password"]
        smtp_host = "smtp.gmail.com"
        smtp_port = 465
        from_name = "JJGT Vehículos"

        if not smtp_user or not smtp_pass:
            st.warning("Configura [emails] en secrets.toml para enviar correos.")
            return False

        diferencia = float(propuesta.get("diferencia", 0) or 0)
        if diferencia > 0:
            dif_html = f"<b style='color:#c0392b;'>Diferencia a pagar: ${diferencia:,.0f}</b>"
        elif diferencia < 0:
            dif_html = f"<b style='color:#27ae60;'>Diferencia a favor: ${abs(diferencia):,.0f}</b>"
        else:
            dif_html = "<b>Permuta directa</b>"

        html = f"""<html><body style="font-family:Arial,sans-serif;">
<div style="background:#1a3a5c;color:#fff;padding:20px;">
  <h2>Propuesta de Permuta - {from_name}</h2>
  <p>ID: <b>{propuesta.get('id','')}</b> | Fecha: <b>{propuesta.get('fecha','')}</b></p>
</div>
<div style="padding:20px;border:1px solid #ddd;">
  <table style="width:100%"><tr>
    <td style="width:50%;padding:10px;border-right:1px solid #eee;vertical-align:top;">
      <b>Vehiculo Ofrecido</b><br>
      {vehiculo_ofrecido.get('marca','')} {vehiculo_ofrecido.get('modelo','')}<br>
      Valor: ${float(vehiculo_ofrecido.get('precio',0) or 0):,.0f}
    </td>
    <td style="width:50%;padding:10px;vertical-align:top;">
      <b>Vehiculo Deseado</b><br>
      {vehiculo_deseado.get('marca','')} {vehiculo_deseado.get('modelo','')}<br>
      Valor: ${float(vehiculo_deseado.get('precio',0) or 0):,.0f}
    </td>
  </tr></table>
  <div style="margin-top:16px;padding:14px;background:#f0f6ff;text-align:center;">
    {dif_html}
  </div>
  {"<p><b>Notas:</b> " + str(propuesta.get('notas','')) + "</p>" if propuesta.get('notas') else ""}
</div>
</body></html>"""

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            for dest in destinatarios:
                dest = dest.strip()
                if not dest:
                    continue
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Propuesta de Permuta {propuesta.get('id','')}"
                msg["From"]    = f"{from_name} <{smtp_user}>"
                msg["To"]      = dest
                msg.attach(MIMEText(html, "html"))
                server.sendmail(smtp_user, dest, msg.as_string())
        return True
    except Exception as e:
        st.warning(f"Error enviando correo: {e}")
        return False
