"""
JJGT — media_sync.py  v6.0
═══════════════════════════════════════════════════════════════════════════════
ESTRATEGIA v6.0 — GOOGLE DRIVE COMO FUENTE PRIMARIA
────────────────────────────────────────────────────
En entornos web (Streamlit Cloud) el sistema de archivos local es efímero:
cualquier archivo en JJGT_Media/ se pierde al reiniciar el servidor.

Solución: Google Drive es la única fuente de persistencia real.

• upload_media()      → sube bytes directamente a Drive; devuelve file_ids CSV
• load_media_from_urls() → descarga bytes desde Drive usando los file_ids
• get_portada_data_uri() → obtiene miniatura desde Drive o memoria RAM
• JJGT_Media/         → solo se usa como caché local temporal (best-effort)

Compatibilidad: si no hay conexión a Drive (sin credenciales) se guarda en
JJGT_Media/ como fallback, igual que en v5.0, para no romper entornos locales.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import io, os, time, random, mimetypes, base64
import streamlit as st

MEDIA_DIR       = "JJGT_Media"
DRIVE_FOLDER_ID = "10CRIboHnD1-_v6kEN2BlBrJWFrqivJ8r"
_MAX_RETRIES    = 3
_BASE_DELAY     = 2.0
_MAX_DELAY      = 16.0

# ─── prefijo que identifica IDs de Drive dentro de fotos_urls ────────────────
_DRIVE_PREFIX = "gdrive:"   # "gdrive:<file_id>"


# ════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ════════════════════════════════════════════════════════════════════════════

def _is_quota_err(e):
    return any(x in str(e).lower() for x in
               ["429", "quota", "rate limit", "exhausted", "too many"])


def _retry(fn, *args, **kwargs):
    delay = _BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            if _is_quota_err(e) or any(c in str(e) for c in ["500","502","503","504"]):
                time.sleep(min(delay + random.uniform(0, delay * 0.25), _MAX_DELAY))
                delay = min(delay * 2, _MAX_DELAY)
            else:
                raise


def _get_drive_service():
    """Devuelve cliente Drive autenticado (cachea en session_state)."""
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


def _a_data_uri(raw: bytes, max_w: int = 600) -> str:
    """Convierte bytes de imagen a data URI base64 (con redimensionado si hay PIL)."""
    if not raw:
        return ""
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


# ─── Rutas locales (caché / fallback sin Drive) ───────────────────────────────

def _pub_dir(pub_id: str) -> str:
    path = os.path.join(os.getcwd(), MEDIA_DIR, str(pub_id))
    os.makedirs(path, exist_ok=True)
    return path


def _guardar_local(pub_id: str, nombre: str, data: bytes) -> str:
    """Guarda bytes localmente y retorna ruta relativa JJGT_Media/pub_id/nombre."""
    carpeta  = _pub_dir(pub_id)
    filepath = os.path.join(carpeta, nombre)
    with open(filepath, "wb") as f:
        f.write(data)
    return f"JJGT_Media/{pub_id}/{nombre}"


def _leer_local(ruta: str) -> bytes | None:
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

    r = _abrir(ruta)
    if r:
        return r

    ruta_norm = os.path.normpath(ruta.replace("/", os.sep))
    r = _abrir(ruta_norm)
    if r:
        return r

    ruta_unix = ruta.replace("\\", "/")
    if "JJGT_Media" in ruta_unix:
        idx      = ruta_unix.find("JJGT_Media")
        segmento = ruta_unix[idx:].replace("/", os.sep)
        for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
            r = _abrir(os.path.join(base, segmento))
            if r:
                return r
    return None


# alias de compatibilidad con código anterior
_leer      = _leer_local
_read_local = _leer_local


# ════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE — subida y descarga
# ════════════════════════════════════════════════════════════════════════════

def _subir_a_drive(nombre: str, data: bytes) -> str | None:
    """
    Sube bytes a Drive y retorna el file_id, o None si falla.
    El archivo queda con permiso público de lectura.
    """
    try:
        from googleapiclient.http import MediaIoBaseUpload
        svc = _get_drive_service()
        if not svc:
            return None
        if not DRIVE_FOLDER_ID.strip():
            return None
        mime  = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
        meta  = {"name": nombre, "parents": [DRIVE_FOLDER_ID.strip()]}
        file_ = _retry(
            svc.files().create(body=meta, media_body=media, fields="id").execute)
        file_id = file_.get("id")
        if not file_id:
            return None
        # Hacer público (lector anónimo)
        _retry(
            svc.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
            ).execute)
        return file_id
    except Exception as e:
        # Guardar el error para diagnóstico en sidebar
        errs = st.session_state.setdefault("_drive_upload_errors", [])
        errs.append(str(e)[:200])
        return None


def _leer_de_drive(file_id: str) -> bytes | None:
    """Descarga bytes de un archivo en Drive por su file_id."""
    if not file_id:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload
        svc = _get_drive_service()
        if not svc:
            return None
        request  = svc.files().get_media(fileId=file_id)
        buf      = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
    except Exception:
        return None


def _thumbnail_url_drive(file_id: str, size: int = 400) -> str:
    """URL pública de miniatura de Drive (no requiere autenticación)."""
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{size}"


def _is_drive_ref(s: str) -> bool:
    return isinstance(s, str) and s.startswith(_DRIVE_PREFIX)


def _file_id_from_ref(s: str) -> str:
    return s[len(_DRIVE_PREFIX):]


# ════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ════════════════════════════════════════════════════════════════════════════

def upload_media(pub_id: str, fotos: list, video: dict | None):
    """
    Guarda fotos/video. Flujo por prioridad:
      1. Drive → "gdrive:<file_id>"  (persiste entre reinicios del servidor)
      2. base64 embebido en la referencia → "b64:<base64_jpeg>"  (garantizado)
         Solo para la portada (primera foto) para no exceder el límite de Sheets.
      3. Local JJGT_Media/ → ruta relativa (solo útil en desarrollo local)

    Retorna (fotos_csv, video_path).
    """
    os.makedirs(MEDIA_DIR, exist_ok=True)
    # Limpiar errores anteriores
    st.session_state.pop("_drive_upload_errors", None)

    svc_ok = _get_drive_service() is not None
    foto_paths = []

    for i, f in enumerate(fotos or []):
        nombre = f"foto_{i:02d}_{f.get('name', 'foto.jpg')}"
        data   = f.get("bytes", b"")
        if not data:
            continue

        ref = None

        # 1. Intentar Drive
        if svc_ok:
            fid = _subir_a_drive(f"{pub_id}_{nombre}", data)
            if fid:
                ref = f"{_DRIVE_PREFIX}{fid}"
                time.sleep(0.1)

        # 2. Fallback: base64 para la portada (primera foto), local para las demás
        if ref is None:
            if i == 0:
                # Portada: comprimir y guardar como base64 inline
                ref = _foto_a_b64_ref(data, max_w=600)
            else:
                # Fotos adicionales: intentar local (solo persiste en dev)
                ref = _guardar_local(pub_id, nombre, data)

        if ref:
            foto_paths.append(ref)

    video_path = ""
    if video:
        nombre = f"video_{video.get('name', 'video.mp4')}"
        data   = video.get("bytes", b"")
        if data:
            ref = None
            if svc_ok:
                fid = _subir_a_drive(f"{pub_id}_{nombre}", data)
                if fid:
                    ref = f"{_DRIVE_PREFIX}{fid}"
            if not ref:
                ref = _guardar_local(pub_id, nombre, data)
            video_path = ref or ""

    return ",".join(foto_paths), video_path


def _foto_a_b64_ref(data: bytes, max_w: int = 400) -> str:
    """
    Comprime la imagen y retorna referencia 'b64:<base64>'.
    Objetivo: < 40KB base64 para caber en una celda de Google Sheets (límite ~50K chars).
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        # Reducir a tamaño pequeño
        img.thumbnail((max_w, max_w))
        # Intentar con calidad decreciente hasta que quepa
        for quality in [60, 45, 30, 20]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            raw = buf.getvalue()
            b64 = base64.b64encode(raw).decode()
            if len(b64) < 40_000:   # margen seguro bajo el límite de Sheets
                return f"b64:{b64}"
        # Último recurso: escalar más pequeño
        img.thumbnail((200, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=20)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"b64:{b64}"
    except Exception:
        # Sin PIL: comprimir bruto si es pequeño, o vacío si es muy grande
        b64 = base64.b64encode(data).decode()
        if len(b64) < 40_000:
            return f"b64:{b64}"
        return ""


_B64_PREFIX = "b64:"

def _is_b64_ref(s: str) -> bool:
    return isinstance(s, str) and s.startswith(_B64_PREFIX)

def _bytes_from_b64_ref(s: str) -> bytes:
    return base64.b64decode(s[len(_B64_PREFIX):])


def load_media_from_urls(fotos_csv: str, video_url: str):
    """
    Lee fotos/video desde sus referencias.
    Soporta: "gdrive:<id>", "b64:<base64>", rutas locales.
    Retorna (lista_fotos, video_dict).
    """
    fotos = []
    for ref in [r.strip() for r in (fotos_csv or "").split(",") if r.strip()]:
        raw  = None
        name = ""
        if _is_drive_ref(ref):
            fid  = _file_id_from_ref(ref)
            raw  = _leer_de_drive(fid)
            name = fid
        elif _is_b64_ref(ref):
            raw  = _bytes_from_b64_ref(ref)
            name = "portada.jpg"
        else:
            raw  = _leer_local(ref)
            name = os.path.basename(ref)

        if raw:
            fotos.append({
                "name":     name,
                "bytes":    raw,
                "path":     ref,
                "data_uri": _a_data_uri(raw, 800),
            })

    video = None
    vref  = (video_url or "").strip()
    if vref:
        raw  = None
        name = ""
        if _is_drive_ref(vref):
            fid  = _file_id_from_ref(vref)
            raw  = _leer_de_drive(fid)
            name = fid
        elif _is_b64_ref(vref):
            raw  = _bytes_from_b64_ref(vref)
            name = "video.mp4"
        else:
            raw  = _leer_local(vref)
            name = os.path.basename(vref)
        if raw:
            video = {"name": name, "bytes": raw, "path": vref}

    return fotos, video


def get_portada_data_uri(v: dict, max_w: int = 400) -> str:
    """
    Retorna data URI de la portada del vehículo.
    Orden de prioridad:
      1. data_uri ya cacheado en fotos[]
      2. bytes en fotos[] RAM (publicación reciente)
      3. thumbnail de Drive (rápido, sin descargar el archivo)
      4. Descarga completa desde Drive
      5. Leer desde archivo local JJGT_Media/
    """
    def _bytes_a_uri(raw: bytes) -> str:
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
        return "data:image/jpeg;base64," + base64.b64encode(data).decode()

    # 1 & 2 — fotos en memoria (RAM)
    for f in (v.get("fotos") or []):
        if not isinstance(f, dict):
            continue
        if f.get("data_uri"):
            return f["data_uri"]
        raw = f.get("bytes")
        if raw:
            uri = _bytes_a_uri(raw)
            if uri:
                f["data_uri"] = uri
                return uri

    fotos_csv = (v.get("fotos_urls") or "").strip()
    if not fotos_csv:
        return ""

    primera = fotos_csv.split(",")[0].strip()
    if not primera:
        return ""

    # 3 — según tipo de referencia
    if _is_drive_ref(primera):
        # Miniatura Drive (URL directa, sin descargar)
        fid = _file_id_from_ref(primera)
        return _thumbnail_url_drive(fid, max_w)

    if _is_b64_ref(primera):
        # Base64 embebido → data URI directa
        raw = _bytes_from_b64_ref(primera)
        uri = _bytes_a_uri(raw)
        if uri:
            if not isinstance(v.get("fotos"), list):
                v["fotos"] = []
            if not v["fotos"]:
                v["fotos"].insert(0, {"name": "portada.jpg", "bytes": raw,
                                      "path": primera, "data_uri": uri})
            return uri

    # 4 — local (fallback sin Drive)
    raw = _leer_local(primera)
    if raw:
        uri = _bytes_a_uri(raw)
        if uri:
            if not isinstance(v.get("fotos"), list):
                v["fotos"] = []
            v["fotos"].insert(0, {
                "name":     os.path.basename(primera),
                "bytes":    raw,
                "path":     primera,
                "data_uri": uri,
            })
            return uri

    return ""


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE VISUALIZACIÓN
# ════════════════════════════════════════════════════════════════════════════

def show_fotos(fotos: list, cols: int = 3):
    if not fotos:
        return
    columnas = st.columns(min(len(fotos), cols))
    for i, foto in enumerate(fotos):
        with columnas[i % cols]:
            uri = foto.get("data_uri") or ""
            if not uri and foto.get("bytes"):
                uri = _a_data_uri(foto["bytes"])
            if uri:
                st.markdown(
                    f'<img src="{uri}" style="width:100%;border-radius:8px;">',
                    unsafe_allow_html=True)


def show_video(video: dict | None = None):
    if not video:
        return
    raw = video.get("bytes")
    if raw:
        try:
            st.video(io.BytesIO(raw))
        except Exception:
            st.caption("⚠️ No se pudo reproducir el video.")


# ════════════════════════════════════════════════════════════════════════════
# CORREO DE PERMUTA
# ════════════════════════════════════════════════════════════════════════════

def send_permuta_email(destinatarios, propuesta, vehiculo_ofrecido, vehiculo_deseado):
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text      import MIMEText

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


def send_recuperacion_email(usuario: dict) -> tuple[bool, str]:
    """
    Envía correo de recuperación de contraseña con la contraseña actual hasheada.
    Como no guardamos la contraseña en texto plano, genera una nueva temporal
    y la guarda en session_state para que el admin pueda resetearla.
    Retorna (ok, mensaje_error).
    """
    try:
        import smtplib, secrets, string
        from email.mime.multipart import MIMEMultipart
        from email.mime.text      import MIMEText

        smtp_user = st.secrets["emails"]["smtp_user"]
        smtp_pass = st.secrets["emails"]["smtp_password"]
        smtp_host = "smtp.gmail.com"
        smtp_port = 465
        from_name = "JJGT Vehículos"

        if not smtp_user or not smtp_pass:
            return False, "Credenciales SMTP no configuradas"

        nombre     = usuario.get("nombre", "Usuario")
        dest_email = (usuario.get("correo") or "").strip()
        if not dest_email:
            return False, "El usuario no tiene correo registrado"

        # Generar contraseña temporal legible
        alfabeto  = string.ascii_letters + string.digits
        nueva_pw  = "".join(secrets.choice(alfabeto) for _ in range(10))

        # Guardar nueva contraseña temporal en session_state para aplicarla
        import hashlib as _hl
        nuevo_hash = _hl.sha256(nueva_pw.encode()).hexdigest()
        st.session_state["_pw_reset_pending"] = {
            "correo": dest_email,
            "hash":   nuevo_hash,
        }

        html = f"""
<html><body style="font-family:Arial,sans-serif;background:#F4F5F7;padding:20px;">
<div style="max-width:480px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);
              border-radius:16px 16px 0 0;padding:24px;color:#fff;text-align:center;">
    <div style="font-size:32px;font-weight:900;letter-spacing:4px;">JJGT</div>
    <div style="font-size:12px;opacity:.7;">VEHÍCULOS · COLOMBIA</div>
    <div style="font-size:16px;font-weight:700;margin-top:10px;">🔑 Recuperación de contraseña</div>
  </div>

  <div style="background:#fff;border-radius:0 0 16px 16px;padding:28px;
              box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;">Hola <b>{nombre.split()[0]}</b>,</p>
    <p>Recibimos una solicitud para recuperar tu contraseña en <b>JJGT Vehículos</b>.</p>
    <p>Tu nueva contraseña temporal es:</p>

    <div style="background:#F0F4FF;border:2px dashed #C41E3A;border-radius:12px;
                padding:20px;text-align:center;margin:20px 0;">
      <div style="font-size:28px;font-weight:900;letter-spacing:6px;
                  color:#C41E3A;font-family:monospace;">{nueva_pw}</div>
    </div>

    <p style="font-size:13px;color:#555;">
      Ingresa con esta contraseña y cámbiala desde tu perfil una vez que hayas iniciado sesión.
    </p>

    <div style="background:#FFF3E0;border-radius:10px;padding:14px;
                font-size:12px;color:#E65100;margin-top:16px;">
      ⚠️ Si no solicitaste este cambio, ignora este correo. Tu contraseña anterior
      seguirá siendo válida hasta que uses esta nueva.
    </div>

    <div style="margin-top:20px;font-size:12px;color:#9999BB;text-align:center;">
      ¿Necesitas ayuda? <a href="mailto:{smtp_user}" style="color:#C41E3A;">{smtp_user}</a>
    </div>
  </div>
</div>
</body></html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🔑 Tu nueva contraseña temporal — JJGT Vehículos"
        msg["From"]    = f"{from_name} <{smtp_user}>"
        msg["To"]      = dest_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, dest_email, msg.as_string())

        return True, ""
    except Exception as e:
        return False, str(e)



    """
    Envía correo al administrador cada vez que se crea una nueva publicación.
    También envía confirmación al vendedor si tiene correo.
    """
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text      import MIMEText

        smtp_user = st.secrets["emails"]["smtp_user"]
        smtp_pass = st.secrets["emails"]["smtp_password"]
        smtp_host = "smtp.gmail.com"
        smtp_port = 465
        from_name = "JJGT Vehículos"

        if not smtp_user or not smtp_pass:
            return False

        precio   = float(pub.get("price", 0) or 0)
        nombre   = f"{pub.get('name','')} {pub.get('model','')} {pub.get('year','')}".strip()
        tipo_map = {"venta": "🏷️ Venta", "permuta": "🔄 Permuta", "ambos": "🔄 Venta + Permuta"}
        tipo_lbl = tipo_map.get(pub.get("type", "venta"), "Venta")

        # Imagen de portada (solo si es data URI pequeño, no b64 largo)
        img_html = ""
        if portada_uri and portada_uri.startswith("https://"):
            img_html = (f'<img src="{portada_uri}" '
                        f'style="width:100%;max-height:220px;object-fit:cover;'
                        f'border-radius:10px;margin-bottom:16px;">')

        # ── Correo al ADMINISTRADOR ───────────────────────────────────────────
        html_admin = f"""
<html><body style="font-family:Arial,sans-serif;background:#F4F5F7;padding:20px;">
<div style="max-width:560px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:16px 16px 0 0;
              padding:24px;color:#fff;text-align:center;">
    <div style="font-size:32px;font-weight:900;letter-spacing:4px;">JJGT</div>
    <div style="font-size:12px;opacity:.7;margin-top:2px;">VEHÍCULOS · COLOMBIA</div>
    <div style="font-size:16px;font-weight:700;margin-top:12px;">🚗 Nueva publicación recibida</div>
  </div>

  <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px;
              box-shadow:0 4px 20px rgba(0,0,0,.08);">
    {img_html}

    <div style="background:#F0F4FF;border-radius:10px;padding:16px;margin-bottom:16px;">
      <div style="font-size:20px;font-weight:800;color:#1A1A2E;">{nombre}</div>
      <div style="margin-top:6px;">
        <span style="background:#C41E3A22;color:#C41E3A;font-size:11px;font-weight:700;
                     padding:2px 10px;border-radius:20px;">{tipo_lbl}</span>
      </div>
    </div>

    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#F9F9FB;">
        <td style="padding:8px 12px;color:#6B6B8A;width:40%;">💰 Precio</td>
        <td style="padding:8px 12px;font-weight:700;color:#C41E3A;font-size:16px;">
            ${precio:,.0f} COP</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6B6B8A;">📅 Año</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('year','')}</td>
      </tr>
      <tr style="background:#F9F9FB;">
        <td style="padding:8px 12px;color:#6B6B8A;">📏 Kilómetros</td>
        <td style="padding:8px 12px;font-weight:600;">{int(pub.get('km',0) or 0):,} km</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6B6B8A;">⛽ Combustible</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('fuel','')}</td>
      </tr>
      <tr style="background:#F9F9FB;">
        <td style="padding:8px 12px;color:#6B6B8A;">⚙️ Transmisión</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('trans','')}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6B6B8A;">🎨 Color</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('color','')}</td>
      </tr>
      <tr style="background:#F9F9FB;">
        <td style="padding:8px 12px;color:#6B6B8A;">📍 Ciudad</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('city','')}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6B6B8A;">📋 ID Publicación</td>
        <td style="padding:8px 12px;font-weight:600;font-family:monospace;">{pub.get('id','')}</td>
      </tr>
      <tr style="background:#F9F9FB;">
        <td style="padding:8px 12px;color:#6B6B8A;">📅 Fecha</td>
        <td style="padding:8px 12px;font-weight:600;">{pub.get('fecha','')}</td>
      </tr>
    </table>

    <div style="background:#E8F5E9;border-radius:10px;padding:14px;margin-top:16px;">
      <div style="font-size:12px;font-weight:700;color:#2E7D32;margin-bottom:6px;">👤 VENDEDOR</div>
      <div style="font-size:14px;font-weight:700;">{pub.get('seller','')}</div>
      <div style="font-size:13px;color:#555;margin-top:4px;">
        📱 {pub.get('seller_phone', pub.get('phone',''))} &nbsp;·&nbsp;
        ✉️ {pub.get('seller_email','')}
      </div>
    </div>

    {"<div style='background:#F9F9FB;border-radius:10px;padding:14px;margin-top:14px;font-size:13px;color:#555;line-height:1.6;'><b>📝 Descripción:</b><br>" + str(pub.get('desc','')).replace('<','&lt;') + "</div>" if pub.get('desc') else ""}

    <div style="margin-top:20px;padding:14px;background:#FFF3E0;border-radius:10px;
                font-size:12px;color:#E65100;text-align:center;">
      ⚡ Publicación en vivo en <b>JJGT Vehículos Colombia</b>
    </div>
  </div>

  <div style="text-align:center;font-size:11px;color:#9999BB;margin-top:16px;">
    JJGT · Sistema de Gestión · Colombia 🇨🇴
  </div>
</div>
</body></html>"""

        # ── Correo de CONFIRMACIÓN al vendedor ────────────────────────────────
        html_vendedor = f"""
<html><body style="font-family:Arial,sans-serif;background:#F4F5F7;padding:20px;">
<div style="max-width:540px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:16px 16px 0 0;
              padding:24px;color:#fff;text-align:center;">
    <div style="font-size:30px;font-weight:900;letter-spacing:4px;">JJGT</div>
    <div style="font-size:14px;margin-top:10px;">🎉 ¡Tu vehículo ya está publicado!</div>
  </div>

  <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px;
              box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;">Hola <b>{pub.get('seller','')}</b>,</p>
    <p>Tu publicación ha sido creada exitosamente en <b>JJGT Vehículos Colombia</b>.</p>

    <div style="background:linear-gradient(135deg,#C41E3A22,#1A1A2E11);
                border-radius:12px;padding:18px;margin:16px 0;text-align:center;">
      <div style="font-size:18px;font-weight:800;">{nombre}</div>
      <div style="font-size:28px;font-weight:900;color:#C41E3A;margin-top:8px;">
          ${precio:,.0f} COP</div>
      <div style="font-size:12px;color:#6B6B8A;margin-top:4px;">
          {pub.get('city','')} · {int(pub.get('km',0) or 0):,} km · {pub.get('fuel','')}</div>
    </div>

    <div style="font-size:13px;color:#555;line-height:1.8;">
      <b>📋 ID de tu publicación:</b>
      <span style="font-family:monospace;background:#F0F0F0;padding:2px 8px;
                   border-radius:4px;">{pub.get('id','')}</span><br>
      <b>📅 Fecha:</b> {pub.get('fecha','')}<br>
      <b>📞 Contacto visible:</b> {pub.get('seller_phone', pub.get('phone',''))}
    </div>

    <div style="margin-top:20px;padding:14px;background:#E3F2FD;border-radius:10px;
                font-size:13px;color:#1565C0;">
      💡 Los interesados te contactarán directamente por WhatsApp o teléfono.
      Mantén tu celular activo para no perder oportunidades.
    </div>

    <div style="margin-top:16px;font-size:12px;color:#9999BB;text-align:center;">
      ¿Necesitas ayuda? Escríbenos a
      <a href="mailto:{smtp_user}" style="color:#C41E3A;">{smtp_user}</a>
    </div>
  </div>
</div>
</body></html>"""

        destinatarios = [admin_email]
        seller_email  = (pub.get("seller_email") or "").strip()
        if seller_email and seller_email.lower() != admin_email.lower():
            destinatarios.append(seller_email)

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.ehlo()
            server.login(smtp_user, smtp_pass)

            # Correo al admin
            msg_admin = MIMEMultipart("alternative")
            msg_admin["Subject"] = f"🚗 Nueva publicación: {nombre} — ${precio:,.0f}"
            msg_admin["From"]    = f"{from_name} <{smtp_user}>"
            msg_admin["To"]      = admin_email
            msg_admin.attach(MIMEText(html_admin, "html"))
            server.sendmail(smtp_user, admin_email, msg_admin.as_string())

            # Correo al vendedor (si tiene correo distinto al admin)
            if seller_email and seller_email.lower() != admin_email.lower():
                msg_vend = MIMEMultipart("alternative")
                msg_vend["Subject"] = f"🎉 Tu vehículo ya está publicado en JJGT — {nombre}"
                msg_vend["From"]    = f"{from_name} <{smtp_user}>"
                msg_vend["To"]      = seller_email
                msg_vend.attach(MIMEText(html_vendedor, "html"))
                server.sendmail(smtp_user, seller_email, msg_vend.as_string())

        return True
    except Exception as e:
        # No bloquear la publicación si el correo falla
        st.session_state["_email_pub_error"] = str(e)
        return False


def _extract_file_id(url: str) -> str | None:
    import re
    for pat in [r"[?&]id=([a-zA-Z0-9_-]+)", r"/file/d/([a-zA-Z0-9_-]+)"]:
        m = re.search(pat, url or "")
        if m:
            return m.group(1)
    return None


def send_nueva_publicacion_email(admin_email: str, pub: dict, portada_uri: str = "") -> bool:
    """
    Envía correo HTML al administrador cuando se crea una nueva publicación.
    Retorna True si se envió correctamente.
    """
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        smtp_user = st.secrets["emails"]["smtp_user"]
        smtp_pass = st.secrets["emails"]["smtp_password"]
        if not smtp_user or not smtp_pass:
            return False

        nombre_vendedor = pub.get("seller", pub.get("name", "—"))
        telefono        = pub.get("phone", pub.get("seller_phone", "—"))
        correo_vendedor = pub.get("seller_email", "—")
        nombre_vehiculo = f"{pub.get('name','')} {pub.get('model','')} {pub.get('year','')}".strip()
        precio          = pub.get("price", 0)
        ciudad          = pub.get("city", "—")
        tipo            = pub.get("type", "venta").capitalize()
        km              = pub.get("km", 0)
        color           = pub.get("color", "—")
        desc            = pub.get("desc", "")[:300]
        fecha           = pub.get("fecha", "—")
        pub_id          = pub.get("id", "—")

        def _fmt(n):
            try: return f"$ {int(n):,}".replace(",",".")
            except: return str(n)

        portada_html = ""
        if portada_uri and portada_uri.startswith("data:"):
            portada_html = f'<img src="{portada_uri}" style="width:100%;max-height:220px;object-fit:cover;border-radius:10px;margin-bottom:16px;" />'

        html = f"""
<html><body style="font-family:Arial,sans-serif;background:#F4F5F7;padding:20px;margin:0;">
<div style="max-width:500px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#C41E3A,#1A1A2E);border-radius:16px 16px 0 0;
              padding:22px 24px;color:#fff;text-align:center;">
    <div style="font-size:30px;font-weight:900;letter-spacing:4px;">JJGT</div>
    <div style="font-size:11px;opacity:.7;letter-spacing:2px;">VEHÍCULOS · COLOMBIA</div>
    <div style="font-size:15px;font-weight:700;margin-top:10px;">🚗 Nueva publicación recibida</div>
  </div>

  <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px;
              box-shadow:0 4px 20px rgba(0,0,0,.08);">
    {portada_html}

    <h2 style="margin:0 0 4px;font-size:18px;color:#1A1A2E;">{nombre_vehiculo}</h2>
    <div style="font-size:22px;font-weight:900;color:#C41E3A;margin-bottom:16px;">{_fmt(precio)}</div>

    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#F8F9FA;"><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">📅 Fecha</td><td style="padding:8px 10px;">{fecha}</td></tr>
      <tr><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">🆔 ID Pub</td><td style="padding:8px 10px;">{pub_id}</td></tr>
      <tr style="background:#F8F9FA;"><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">📍 Ciudad</td><td style="padding:8px 10px;">{ciudad}</td></tr>
      <tr><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">🔁 Tipo</td><td style="padding:8px 10px;">{tipo}</td></tr>
      <tr style="background:#F8F9FA;"><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">🛣️ Km</td><td style="padding:8px 10px;">{km:,}</td></tr>
      <tr><td style="padding:8px 10px;color:#6B6B8A;font-weight:600;">🎨 Color</td><td style="padding:8px 10px;">{color}</td></tr>
    </table>

    <div style="background:#F0F4FF;border-radius:10px;padding:14px;margin:16px 0;">
      <div style="font-size:12px;font-weight:700;color:#6B6B8A;margin-bottom:6px;">👤 VENDEDOR</div>
      <div style="font-size:14px;font-weight:700;color:#1A1A2E;">{nombre_vendedor}</div>
      <div style="font-size:13px;color:#555;">📱 {telefono}</div>
      <div style="font-size:13px;color:#555;">✉️ {correo_vendedor}</div>
    </div>

    {"<div style='background:#FAFAFA;border-radius:8px;padding:12px;font-size:13px;color:#444;'>" + desc + "</div>" if desc else ""}

    <div style="margin-top:20px;font-size:11px;color:#9999BB;text-align:center;">
      JJGT Vehículos · Notificación automática
    </div>
  </div>
</div>
</body></html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚗 Nueva publicación: {nombre_vehiculo} — JJGT"
        msg["From"]    = f"JJGT Vehículos <{smtp_user}>"
        msg["To"]      = admin_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, admin_email, msg.as_string())
        return True
    except Exception:
        return False
