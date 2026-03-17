import streamlit as st
import streamlit.components.v1 as components
import toml
import json
import smtplib
import gspread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials
from datetime import datetime

# ── CONFIGURACIÓN GLOBAL ──
# URL del video animado de proyectos (reemplaza con tu dominio cuando despliegues)
VIDEO_URL = "https://39561638-5f7a-4a60-98a8-ae51503be229-00-n7z16tvqo31f.riker.streamlit.app/josegart-proyectos/"
#VIDEO_URL = "https://Code-Fixer-Mar-17-10-12-56.mp4

# Contraseña para acceder a los enlaces de proyectos (cámbiala por la tuya)
PROJECT_PASSWORD = "josegart2025"

# ── FUNCIONES DE AUTENTICACIÓN Y CONTACTO ──

def load_credentials_from_toml():
    """
    Cargar credenciales de Google Sheets.
    Primero intenta leer desde st.secrets (Streamlit Cloud),
    luego hace fallback al archivo .streamlit/secrets.toml (local).
    """
    # ── Intento 1: st.secrets (Streamlit Cloud y local con secrets.toml) ──
    try:
        creds = st.secrets['sheetsemp']['credentials_sheet']
        if isinstance(creds, str):
            creds = json.loads(creds)
        return creds, st.secrets
    except (KeyError, AttributeError):
        pass

    # ── Intento 2: archivo físico (desarrollo local sin secrets.toml cargado) ──
    try:
        with open('./.streamlit/secrets.toml', 'r') as toml_file:
            config = toml.load(toml_file)
            creds = config['sheetsemp']['credentials_sheet']
            if isinstance(creds, str):
                creds = json.loads(creds)
            return creds, config
    except FileNotFoundError:
        st.error("🔒 Archivo secrets.toml no encontrado en .streamlit/")
        return None, None
    except KeyError as e:
        st.error(f"🔑 Clave faltante en secrets.toml: {str(e)}")
        return None, None
    except json.JSONDecodeError as e:
        st.error(f"📄 Error al parsear JSON en secrets.toml: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"❌ Error cargando credenciales: {str(e)}")
        return None, None


@st.cache_resource(ttl=300)
def get_google_sheets_connection(_creds):
    """Establecer conexión con Google Sheets"""
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_info(_creds, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {str(e)}")
        return None


def _build_html_body(nombre, email, telefono, mensaje):
    """Construye el cuerpo HTML del email de notificación."""
    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;background:#f9f9f9;">
          <div style="background:#0A0E1A;padding:20px;text-align:center;border-radius:10px 10px 0 0;">
            <h2 style="color:#00D4FF;margin:0;">Nueva Solicitud de Consulta</h2>
          </div>
          <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
            <h3 style="color:#0A0E1A;border-bottom:2px solid #00D4FF;padding-bottom:10px;">
              Información del Contacto
            </h3>
            <table style="width:100%;margin:20px 0;">
              <tr>
                <td style="padding:10px;background:#f5f5f5;font-weight:bold;width:150px;">👤 Nombre:</td>
                <td style="padding:10px;">{nombre}</td>
              </tr>
              <tr>
                <td style="padding:10px;background:#f5f5f5;font-weight:bold;">📧 Email:</td>
                <td style="padding:10px;">
                  <a href="mailto:{email}" style="color:#00D4FF;text-decoration:none;">{email}</a>
                </td>
              </tr>
              <tr>
                <td style="padding:10px;background:#f5f5f5;font-weight:bold;">📱 Teléfono:</td>
                <td style="padding:10px;">{telefono if telefono else 'No proporcionado'}</td>
              </tr>
              <tr>
                <td style="padding:10px;background:#f5f5f5;font-weight:bold;">🕐 Fecha:</td>
                <td style="padding:10px;">{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</td>
              </tr>
            </table>
            <h3 style="color:#0A0E1A;border-bottom:2px solid #00D4FF;padding-bottom:10px;margin-top:30px;">
              💬 Proyecto / Mensaje:
            </h3>
            <div style="background:#f9f9f9;padding:20px;border-left:4px solid #00D4FF;margin:20px 0;">
              <p style="margin:0;white-space:pre-wrap;">{mensaje if mensaje else 'Sin descripción adicional.'}</p>
            </div>
            <div style="margin-top:30px;padding-top:20px;border-top:1px solid #e0e0e0;text-align:center;color:#666;">
              <p style="margin:5px 0;"><strong>JOSEGART</strong> – Desarrollo de Aplicaciones Seguras</p>
              <p style="margin:5px 0;font-size:12px;">
                Mensaje enviado desde el formulario de contacto de josegart.com
              </p>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def send_email_gmail(nombre, email, telefono, mensaje):
    """
    Envía notificación por Gmail SMTP SSL.

    Requiere en secrets.toml:
        [emails]
        smtp_user     = "tu_cuenta@gmail.com"
        smtp_password = "xxxx xxxx xxxx xxxx"   ← contraseña de aplicación de Google
    """
    try:
        user        = st.secrets['emails']['smtp_user']
        password    = st.secrets['emails']['smtp_password']
        smtp_server = 'smtp.gmail.com'
        smtp_port   = 465

        msg = MIMEMultipart('alternative')
        msg['From']    = user
        msg['To']      = "josegarjagt@gmail.com"
        msg['Subject'] = f"Nueva solicitud de consulta – {nombre}"
        msg.attach(MIMEText(_build_html_body(nombre, email, telefono, mensaje), 'html'))

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(user, password)
            server.send_message(msg)

        return True, "✅ ¡Mensaje enviado exitosamente!"

    except KeyError as e:
        return False, f"❌ Credencial faltante en secrets.toml: {e}. Verifica [emails] smtp_user y smtp_password."
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Error de autenticación Gmail. Asegúrate de usar una contraseña de aplicación (no tu contraseña normal)."
    except smtplib.SMTPException as e:
        return False, f"❌ Error SMTP: {e}"
    except Exception as e:
        return False, f"❌ Error al enviar email: {e}"


def save_contact_to_sheets(client, nombre, email, telefono, mensaje):
    """
    Guardar solicitud de contacto en Google Sheets.
    Busca el spreadsheet 'autenticacion' y guarda en la hoja 'mensajes_contacto'.
    Columnas: Fecha | Nombre | Email | Teléfono | Mensaje
    """
    try:
        # Abrir o crear el spreadsheet
        try:
            sheet = client.open("autenticacion")
        except gspread.SpreadsheetNotFound:
            sheet = client.create("autenticacion")

        # Buscar o crear la hoja 'mensajes_contacto'
        try:
            worksheet = sheet.worksheet("mensajes_contacto")
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="mensajes_contacto", rows="1000", cols="5")
            # Encabezados sólo al crear la hoja por primera vez
            worksheet.update(range_name='A1:E1',
                             values=[['Fecha', 'Nombre', 'Email', 'Teléfono', 'Mensaje']])

        # Agregar fila con los datos del formulario
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row(
            [fecha, nombre, email,
             telefono if telefono else '',
             mensaje  if mensaje  else ''],
            value_input_option='USER_ENTERED'
        )

        return True, "✅ ¡Solicitud registrada exitosamente!"

    except Exception as e:
        return False, f"❌ Error al guardar en Google Sheets: {str(e)}"


st.set_page_config(
    page_title="JOSEGART - Un Futuro Mejor | Apps Seguras & IA",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── SESSION STATE PARA CONTRASEÑAS ──
if 'proj_unlocked' not in st.session_state:
    st.session_state.proj_unlocked = {}
if 'proj_asking' not in st.session_state:
    st.session_state.proj_asking = {}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --bg-deep:     #0A0E1A;
  --bg-card:     #0F1629;
  --primary:     #00D4FF;
  --secondary:   #7C3AED;
  --accent:      #F59E0B;
  --text-white:  #FFFFFF;
  --text-muted:  #94A3B8;
  --border:      rgba(0,212,255,0.15);
}

html, body, [data-testid="stAppViewContainer"] {
  background-color: var(--bg-deep) !important;
  color: var(--text-white) !important;
  font-family: 'DM Sans', sans-serif !important;
}

[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
footer { display: none !important; }

/* ── SKIP NAV ── */
.skip-nav {
  position: absolute; top: -40px; left: 0;
  background: var(--primary); color: #000;
  padding: 8px 16px; border-radius: 0 0 8px 0;
  text-decoration: none; font-weight: 600;
  transition: top .3s;
}
.skip-nav:focus { top: 0; }

/* ── HEADER ── */
.navbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
  background: rgba(10,14,26,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 1rem 2rem;
  display: flex; align-items: center; justify-content: space-between;
}
.logo-text {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.5rem; font-weight: 700;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: -0.02em;
}
.logo-badge {
  display: inline-block;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff; border-radius: 8px;
  padding: 4px 10px; font-size: .85rem; font-weight: 700;
  margin-right: 8px;
}
.nav-links { display: flex; gap: 2rem; align-items: center; }
.nav-links a {
  color: var(--text-muted); text-decoration: none;
  font-size: .95rem; font-weight: 500;
  transition: color .2s;
}
.nav-links a:hover { color: var(--primary); }
.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff !important; border: none; border-radius: 50px;
  padding: .6rem 1.5rem; font-weight: 600; cursor: pointer;
  text-decoration: none; font-size: .9rem;
  transition: opacity .2s, transform .2s;
  display: inline-block;
}
.btn-primary:hover { opacity: .9; transform: translateY(-1px); }

/* ── HERO ── */
.hero-section {
  min-height: 100vh;
  background: radial-gradient(ellipse 80% 60% at 50% -10%, rgba(124,58,237,.35) 0%, transparent 60%),
              radial-gradient(ellipse 60% 50% at 80% 50%, rgba(0,212,255,.18) 0%, transparent 50%),
              var(--bg-deep);
  display: flex; align-items: center;
  padding: 8rem 2rem 4rem;
  position: relative; overflow: hidden;
}
.hero-grid {
  max-width: 1200px; margin: 0 auto;
  display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: .5rem;
  background: rgba(0,212,255,.1); border: 1px solid var(--border);
  border-radius: 50px; padding: .35rem .9rem;
  font-size: .8rem; color: var(--primary); font-weight: 500;
  margin-bottom: 1.5rem;
}
.hero-badge::before { content: "●"; font-size: .6rem; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(2.5rem, 5vw, 4rem);
  font-weight: 700; line-height: 1.1;
  margin: 0 0 1.5rem;
}
.gradient-text {
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub {
  font-size: 1.1rem; color: var(--text-muted);
  line-height: 1.7; margin-bottom: 2rem; max-width: 500px;
}
.cta-group { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2.5rem; }
.btn-secondary {
  background: transparent; color: var(--text-white) !important;
  border: 1px solid var(--border); border-radius: 50px;
  padding: .6rem 1.5rem; font-weight: 500; cursor: pointer;
  text-decoration: none; font-size: .9rem;
  transition: border-color .2s, color .2s;
  display: inline-block;
}
.btn-secondary:hover { border-color: var(--primary); color: var(--primary) !important; }
.social-proof {
  display: flex; gap: 2rem; align-items: center;
}
.stat-item { text-align: left; }
.stat-num {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.8rem; font-weight: 700; color: var(--primary);
}
.stat-label { font-size: .8rem; color: var(--text-muted); }
.hero-visual {
  position: relative; display: flex; justify-content: center;
}
.hero-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 24px; padding: 2rem;
  box-shadow: 0 0 60px rgba(0,212,255,.12), 0 30px 60px rgba(0,0,0,.4);
  position: relative; overflow: hidden;
}
.hero-card::before {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(0,212,255,.05), rgba(124,58,237,.05));
}

/* ── MARQUEE ── */
.marquee-section {
  padding: 3rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  overflow: hidden; background: rgba(15,22,41,.5);
}
.marquee-label {
  text-align: center; color: var(--text-muted);
  font-size: .85rem; text-transform: uppercase; letter-spacing: .1em;
  margin-bottom: 1.5rem;
}
.marquee-track {
  display: flex; gap: 4rem; animation: marquee 20s linear infinite;
  width: max-content;
}
@keyframes marquee { from{transform:translateX(0)} to{transform:translateX(-50%)} }
.logo-item {
  color: var(--text-muted); font-family: 'Space Grotesk', sans-serif;
  font-weight: 600; font-size: 1.1rem; white-space: nowrap;
  opacity: .6; transition: opacity .2s;
}

/* ── SECTION BASE ── */
.section {
  padding: 6rem 2rem;
  max-width: 1200px; margin: 0 auto;
}
.section-label {
  font-size: .8rem; text-transform: uppercase; letter-spacing: .15em;
  color: var(--primary); font-weight: 600; margin-bottom: .75rem;
}
.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.8rem, 3.5vw, 2.8rem);
  font-weight: 700; line-height: 1.2; margin-bottom: 1rem;
  color: var(--text-white);
}
.section-subtitle {
  color: var(--text-muted); font-size: 1.05rem;
  line-height: 1.7; max-width: 600px;
}

/* ── PROBLEMA/SOLUCIÓN ── */
.problem-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center;
}
.pain-list { list-style: none; padding: 0; margin: 1.5rem 0; }
.pain-list li {
  display: flex; align-items: flex-start; gap: 1rem;
  padding: .75rem 0; border-bottom: 1px solid rgba(255,255,255,.05);
  color: var(--text-muted); font-size: .95rem;
}
.pain-icon { color: #EF4444; font-size: 1.1rem; margin-top: 2px; flex-shrink: 0; }
.solution-box {
  background: linear-gradient(135deg, rgba(0,212,255,.08), rgba(124,58,237,.08));
  border: 1px solid var(--border); border-radius: 20px; padding: 2rem;
}
.solution-item {
  display: flex; align-items: center; gap: 1rem;
  margin-bottom: 1.25rem;
}
.check-icon { color: var(--primary); font-size: 1.2rem; flex-shrink: 0; }

/* ── FEATURES ── */
.features-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;
}
.feature-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.75rem;
  transition: border-color .3s, transform .3s, box-shadow .3s;
}
.feature-card:hover {
  border-color: var(--primary);
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(0,212,255,.1);
}
.feature-icon {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(0,212,255,.15), rgba(124,58,237,.15));
  display: flex; align-items: center; justify-content: center;
  font-size: 1.4rem; margin-bottom: 1rem;
}
.feature-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.05rem; font-weight: 600; margin-bottom: .5rem;
  color: var(--text-white);
}
.feature-desc { color: var(--text-muted); font-size: .9rem; line-height: 1.6; }

/* ── HOW IT WORKS ── */
.steps-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem;
  position: relative;
}
.step-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 20px; padding: 2rem; text-align: center; position: relative;
}
.step-num {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 4rem; font-weight: 700; line-height: 1;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin-bottom: .5rem;
}
.step-title { font-family:'Space Grotesk',sans-serif; font-size:1.1rem; font-weight:600; margin-bottom:.5rem; color: var(--text-white); }
.step-desc { color: var(--text-muted); font-size: .9rem; line-height: 1.6; }

/* ── METRICS ── */
.metrics-section {
  background: linear-gradient(135deg, rgba(124,58,237,.25), rgba(0,212,255,.15)),
              var(--bg-card);
  border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  padding: 5rem 2rem;
}
.metrics-grid {
  max-width: 1000px; margin: 0 auto;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 2rem; text-align: center;
}
.metric-num {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 3rem; font-weight: 700;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.metric-label { color: var(--text-muted); font-size: .9rem; margin-top: .25rem; }

/* ── TESTIMONIOS ── */
.testimonials-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.testimonial-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 20px; padding: 2rem;
}
.stars { color: var(--accent); font-size: 1rem; margin-bottom: 1rem; }
.testimonial-text {
  color: var(--text-muted); font-size: .95rem; line-height: 1.7;
  font-style: italic; margin-bottom: 1.5rem;
}
.testimonial-author { display: flex; align-items: center; gap: .75rem; }
.avatar {
  width: 44px; height: 44px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 1rem; flex-shrink: 0;
}
.author-name { font-weight: 600; font-size: .9rem; color: var(--text-white); }
.author-role { color: var(--text-muted); font-size: .8rem; }

/* ── PRECIOS ── */
.pricing-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; align-items: start; }
.pricing-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 20px; padding: 2rem; position: relative;
}
.pricing-card.featured {
  border-color: var(--primary);
  box-shadow: 0 0 40px rgba(0,212,255,.15);
  transform: scale(1.03);
}
.popular-badge {
  position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff; border-radius: 50px; padding: .3rem 1rem;
  font-size: .75rem; font-weight: 700;
}
.plan-name { font-family:'Space Grotesk',sans-serif; font-weight:600; margin-bottom:.5rem; color: var(--text-white); }
.plan-price {
  font-family:'Space Grotesk',sans-serif; font-size:2.5rem; font-weight:700;
  margin: .5rem 0;
}
.plan-price span { font-size:1rem; color:var(--text-muted); }
.plan-desc { color:var(--text-muted); font-size:.9rem; margin-bottom:1.5rem; }
.plan-features { list-style:none; padding:0; margin:0 0 1.5rem; }
.plan-features li {
  display:flex; align-items:center; gap:.5rem;
  padding:.4rem 0; font-size:.9rem; color:var(--text-muted);
  border-bottom: 1px solid rgba(255,255,255,.04);
}
.plan-features li::before { content:"✓"; color:var(--primary); font-weight:700; }

/* ── FAQ ── */
.faq-list { max-width: 800px; margin: 0 auto; }
.faq-item {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; margin-bottom: 1rem; overflow: hidden;
}
.faq-q {
  padding: 1.25rem 1.5rem; font-weight: 600; cursor: pointer;
  display: flex; justify-content: space-between; align-items: center;
}
.faq-a {
  padding: 0 1.5rem 1.25rem; color: var(--text-muted);
  font-size: .95rem; line-height: 1.7;
}

/* ── CTA FINAL ── */
.cta-section {
  background: linear-gradient(135deg, rgba(124,58,237,.3), rgba(0,212,255,.2)), var(--bg-card);
  border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  padding: 6rem 2rem; text-align: center;
}
.cta-inner { max-width: 700px; margin: 0 auto; }
.trust-badges {
  display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;
  margin-top: 1.5rem;
}
.trust-item { display: flex; align-items: center; gap: .4rem; color: var(--text-muted); font-size: .85rem; }

/* ── FORM (Streamlit widget overrides) ── */
.form-group { margin-bottom: 1rem; }

/* Labels de los inputs */
[data-testid="stForm"] label,
[data-testid="stForm"] .stTextInput label,
[data-testid="stForm"] .stTextArea label {
  color: #E2E8F0 !important;
  font-weight: 500 !important;
  font-size: .95rem !important;
}

/* Campos de texto — fondo claro, texto negro para máxima legibilidad */
[data-testid="stForm"] input,
[data-testid="stForm"] textarea,
[data-testid="stForm"] .stTextInput input,
[data-testid="stForm"] .stTextArea textarea,
[data-testid="stForm"] input[type="text"],
[data-testid="stForm"] input[type="email"] {
  background-color: #FFFFFF !important;
  color: #111111 !important;
  border: 1px solid rgba(0,212,255,0.4) !important;
  border-radius: 10px !important;
  font-size: 1rem !important;
  caret-color: #111111 !important;
}

/* Placeholder */
[data-testid="stForm"] input::placeholder,
[data-testid="stForm"] textarea::placeholder {
  color: #9CA3AF !important;
  opacity: 1 !important;
}

/* Focus */
[data-testid="stForm"] input:focus,
[data-testid="stForm"] textarea:focus {
  border-color: #00D4FF !important;
  box-shadow: 0 0 0 2px rgba(0,212,255,0.2) !important;
  outline: none !important;
}

/* Botón submit */
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
  background: linear-gradient(135deg, #00D4FF, #7C3AED) !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: 50px !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  padding: .75rem 2rem !important;
  transition: opacity .2s, transform .2s !important;
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
  opacity: .9 !important;
  transform: translateY(-1px) !important;
}

/* Contenedor del form */
[data-testid="stForm"] {
  background: rgba(15,22,41,0.85) !important;
  border: 1px solid rgba(0,212,255,0.15) !important;
  border-radius: 20px !important;
  padding: 2rem !important;
}

/* ── PROYECTOS ── */
.projects-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;
}
.project-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 20px; overflow: hidden;
  transition: border-color .3s, transform .3s, box-shadow .3s;
  display: flex; flex-direction: column;
}
.project-card:hover {
  border-color: var(--primary);
  transform: translateY(-5px);
  box-shadow: 0 24px 48px rgba(0,212,255,.12);
}
.project-thumb {
  width: 100%; height: 160px;
  display: flex; align-items: center; justify-content: center;
  font-size: 3rem; position: relative; overflow: hidden;
}
.project-body { padding: 1.5rem; flex: 1; display: flex; flex-direction: column; }
.project-tag {
  display: inline-block;
  background: rgba(0,212,255,.1); border: 1px solid rgba(0,212,255,.25);
  color: var(--primary); border-radius: 50px;
  padding: .2rem .75rem; font-size: .75rem; font-weight: 600;
  margin-bottom: .75rem; text-transform: uppercase; letter-spacing: .05em;
}
.project-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.05rem; font-weight: 700;
  color: var(--text-white); margin-bottom: .5rem;
}
.project-desc {
  color: var(--text-muted); font-size: .88rem;
  line-height: 1.6; flex: 1; margin-bottom: 1.25rem;
}
.project-link {
  display: inline-flex; align-items: center; gap: .4rem;
  color: var(--primary); font-size: .88rem; font-weight: 600;
  text-decoration: none; transition: gap .2s;
}
.project-link:hover { gap: .7rem; }
.project-link::after { content: "→"; }

/* ── FOOTER ── */
.footer {
  background: #060910; border-top: 1px solid var(--border);
  padding: 4rem 2rem 2rem;
}
.footer-grid {
  max-width: 1200px; margin: 0 auto;
  display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr; gap: 3rem;
  margin-bottom: 3rem;
}
.footer-tagline { color: var(--text-muted); font-size: .9rem; margin-top: .5rem; line-height: 1.6; }
.footer-col-title { font-family:'Space Grotesk',sans-serif; font-weight:600; margin-bottom:1rem; font-size:.95rem; color: var(--text-white); }
.footer-links { list-style:none; padding:0; }
.footer-links li { margin-bottom: .5rem; }
.footer-links a { color: var(--text-muted); text-decoration: none; font-size: .9rem; transition: color .2s; }
.footer-links a:hover { color: var(--primary); }
.footer-bottom {
  max-width: 1200px; margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 2rem; border-top: 1px solid var(--border);
  color: var(--text-muted); font-size: .85rem; flex-wrap: wrap; gap: 1rem;
}
.social-links { display: flex; gap: 1rem; }
.social-link {
  width: 36px; height: 36px; border-radius: 8px;
  background: var(--bg-card); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-size: 1rem;
  text-decoration: none; transition: border-color .2s, color .2s;
}
.social-link:hover { border-color: var(--primary); color: var(--primary); }

/* ── RESPONSIVE ── */
@media (max-width: 768px) {
  .hero-grid, .problem-grid, .features-grid, .steps-grid,
  .metrics-grid, .testimonials-grid, .pricing-grid, .footer-grid {
    grid-template-columns: 1fr !important;
  }
  .hero-section { padding-top: 7rem !important; }
  .pricing-card.featured { transform: scale(1) !important; }
  .nav-links { display: none !important; }
}
</style>

<a href="#contacto" class="skip-nav">Ir al contenido principal</a>

<!-- ── NAVBAR ── -->
<nav class="navbar" role="navigation" aria-label="Navegación principal">
  <div>
    <span class="logo-badge">JG</span>
    <span class="logo-text">JOSE<span style="color:#7C3AED">GART</span></span>
  </div>
  <div class="nav-links">
    <a href="#servicios">Servicios</a>
    <a href="#proceso">Proceso</a>
    <a href="#proyectos">Proyectos</a>
    <a href="#testimonios">Testimonios</a>
    <a href="#planes">Planes</a>
    <a href="#faq">FAQ</a>
  </div>
  <a href="#contacto" class="btn-primary" aria-label="Solicitar consulta gratuita">Consulta Gratis</a>
</nav>

<!-- ── HERO ── -->
<section class="hero-section" id="inicio" aria-label="Sección principal">
  <div class="hero-grid">
    <div>
      <div class="hero-badge">Innovación Tecnológica 2025</div>
      <h1 class="hero-title">
        Transforma tu Negocio con<br>
        <span class="gradient-text">Tecnología que Trabaja por Ti</span>
      </h1>
      <p class="hero-sub">
        Desarrollamos aplicaciones seguras a medida, automatizamos procesos con IA
        y potenciamos tu presencia digital para que crezcas sin límites.
      </p>
      <div class="cta-group">
        <a href="#contacto" class="btn-primary">Empieza tu Proyecto →</a>
        <a href="#proceso" class="btn-secondary">Ver Cómo Funciona ↓</a>
      </div>
      <div class="social-proof">
        <div class="stat-item">
          <div class="stat-num">50+</div>
          <div class="stat-label">Proyectos entregados</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">97%</div>
          <div class="stat-label">Clientes satisfechos</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">5★</div>
          <div class="stat-label">Valoración media</div>
        </div>
      </div>
    </div>
    <div class="hero-visual">
      <div class="hero-card">
        <svg width="420" height="320" viewBox="0 0 420 320" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#00D4FF" stop-opacity="0.8"/>
              <stop offset="100%" stop-color="#7C3AED" stop-opacity="0.8"/>
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <circle cx="210" cy="160" r="100" stroke="url(#grad1)" stroke-width="1" stroke-dasharray="4 4" opacity="0.4"/>
          <circle cx="210" cy="160" r="60" stroke="url(#grad1)" stroke-width="1.5" opacity="0.6"/>
          <circle cx="210" cy="160" r="20" fill="url(#grad1)" filter="url(#glow)"/>
          <line x1="210" y1="60" x2="210" y2="260" stroke="#00D4FF" stroke-width="1" opacity="0.3"/>
          <line x1="110" y1="160" x2="310" y2="160" stroke="#00D4FF" stroke-width="1" opacity="0.3"/>
          <circle cx="210" cy="60" r="6" fill="#00D4FF" filter="url(#glow)"/>
          <circle cx="210" cy="260" r="6" fill="#7C3AED" filter="url(#glow)"/>
          <circle cx="110" cy="160" r="6" fill="#F59E0B" filter="url(#glow)"/>
          <circle cx="310" cy="160" r="6" fill="#00D4FF" filter="url(#glow)"/>
          <text x="75" y="140" fill="#94A3B8" font-size="11" font-family="monospace">APP</text>
          <text x="315" y="140" fill="#94A3B8" font-size="11" font-family="monospace">API</text>
          <text x="190" y="44" fill="#94A3B8" font-size="11" font-family="monospace">IA</text>
          <text x="180" y="285" fill="#94A3B8" font-size="11" font-family="monospace">DATA</text>
          <rect x="30" y="20" width="120" height="55" rx="10" fill="rgba(0,212,255,0.07)" stroke="rgba(0,212,255,0.2)" stroke-width="1"/>
          <text x="45" y="45" fill="#00D4FF" font-size="10" font-family="monospace" font-weight="bold">def josegart():</text>
          <text x="55" y="62" fill="#94A3B8" font-size="9" font-family="monospace">build(secure=True)</text>
          <rect x="270" y="240" width="120" height="55" rx="10" fill="rgba(124,58,237,0.07)" stroke="rgba(124,58,237,0.2)" stroke-width="1"/>
          <text x="285" y="265" fill="#7C3AED" font-size="10" font-family="monospace" font-weight="bold">status: 200 OK</text>
          <text x="285" y="282" fill="#94A3B8" font-size="9" font-family="monospace">deployed ✓</text>
          <rect x="270" y="20" width="110" height="45" rx="10" fill="rgba(245,158,11,0.07)" stroke="rgba(245,158,11,0.2)" stroke-width="1"/>
          <text x="285" y="40" fill="#F59E0B" font-size="10" font-family="monospace" font-weight="bold">AI.process(</text>
          <text x="285" y="55" fill="#94A3B8" font-size="9" font-family="monospace">data=True)</text>
        </svg>
      </div>
    </div>
  </div>
</section>

<!-- ── MARQUEE ── -->
<div class="marquee-section" aria-label="Empresas que confían en nosotros">
  <p class="marquee-label">Confían en nosotros</p>
  <div style="overflow:hidden">
    <div class="marquee-track">
      <span class="logo-item">◆ TechVentures</span>
      <span class="logo-item">◆ DigitalCorp</span>
      <span class="logo-item">◆ InnovaStart</span>
      <span class="logo-item">◆ ProBusiness</span>
      <span class="logo-item">◆ FutureScale</span>
      <span class="logo-item">◆ SmartFlow</span>
      <span class="logo-item">◆ NexaTech</span>
      <span class="logo-item">◆ TechVentures</span>
      <span class="logo-item">◆ DigitalCorp</span>
      <span class="logo-item">◆ InnovaStart</span>
      <span class="logo-item">◆ ProBusiness</span>
      <span class="logo-item">◆ FutureScale</span>
      <span class="logo-item">◆ SmartFlow</span>
      <span class="logo-item">◆ NexaTech</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── PROBLEMA / SOLUCIÓN ──
st.markdown("""
<div style="padding:6rem 2rem; max-width:1200px; margin:0 auto;" id="servicios">
  <div class="problem-grid">
    <div>
      <p class="section-label">El Problema</p>
      <h2 class="section-title">¿Tu negocio sigue perdiendo tiempo y dinero con tecnología obsoleta?</h2>
      <ul class="pain-list">
        <li><span class="pain-icon">✗</span>Procesos manuales lentos que consumen horas de trabajo cada día</li>
        <li><span class="pain-icon">✗</span>Datos e información del negocio expuestos a ciberataques</li>
        <li><span class="pain-icon">✗</span>Sin presencia digital sólida: pierdes clientes frente a la competencia</li>
        <li><span class="pain-icon">✗</span>No aprovechas la IA cuando tus competidores ya lo hacen</li>
        <li><span class="pain-icon">✗</span>Software genérico que no se adapta a tu flujo de trabajo real</li>
      </ul>
    </div>
    <div class="solution-box">
      <p class="section-label">La Solución</p>
      <h3 style="font-family:'Space Grotesk',sans-serif; font-size:1.6rem; font-weight:700; margin-bottom:1.5rem;">
        JOSEGART es tu socio tecnológico integral
      </h3>
      <div class="solution-item"><span class="check-icon">✓</span><span>Apps a medida que automatizan tus procesos únicos</span></div>
      <div class="solution-item"><span class="check-icon">✓</span><span>Seguridad enterprise con cifrado y backups automáticos</span></div>
      <div class="solution-item"><span class="check-icon">✓</span><span>Integración de IA para multiplicar tu productividad</span></div>
      <div class="solution-item"><span class="check-icon">✓</span><span>Estrategia digital completa para crecer online</span></div>
      <div class="solution-item"><span class="check-icon">✓</span><span>Acompañamiento desde la idea hasta el lanzamiento</span></div>
      <a href="#contacto" class="btn-primary" style="margin-top:1rem; display:inline-block;">Quiero una Consulta Gratis</a>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── CARACTERÍSTICAS ──
st.markdown("""
<div style="padding:2rem 2rem 6rem; max-width:1200px; margin:0 auto;">
  <div style="text-align:center; margin-bottom:3rem;">
    <p class="section-label">Características</p>
    <h2 class="section-title">Todo lo que tu negocio necesita en un solo lugar</h2>
  </div>
  <div class="features-grid">
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00D4FF" stroke-width="2" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
      </div>
      <p class="feature-title">Apps a Medida</p>
      <p class="feature-desc">Aplicaciones web y móviles 100% personalizadas para tu flujo de trabajo único, sin código genérico.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <p class="feature-title">Seguridad Avanzada</p>
      <p class="feature-desc">Cifrado end-to-end, backups automáticos y protocolos de seguridad nivel enterprise para proteger tu negocio.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
      </div>
      <p class="feature-title">IA & Automatización</p>
      <p class="feature-desc">Integra inteligencia artificial en tus procesos para multiplicar resultados y reducir costos operativos.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00D4FF" stroke-width="2" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      </div>
      <p class="feature-title">Negocios Digitales</p>
      <p class="feature-desc">Estrategia y herramientas completas para vender, escalar y posicionarte online ante tu competencia.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2" aria-hidden="true"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
      </div>
      <p class="feature-title">Asesoría Personalizada</p>
      <p class="feature-desc">Acompañamiento uno a uno desde la idea hasta el lanzamiento, con expertos en tu sector.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
      </div>
      <p class="feature-title">Soporte 24/7</p>
      <p class="feature-desc">Siempre disponibles para mantener tu negocio funcionando. Respuesta garantizada en menos de 2 horas.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── CÓMO FUNCIONA ──
st.markdown("""
<div style="padding:2rem 2rem 6rem; max-width:1200px; margin:0 auto; background:rgba(15,22,41,.3); border-radius:24px;" id="proceso">
  <div style="text-align:center; margin-bottom:3rem;">
    <p class="section-label">Proceso</p>
    <h2 class="section-title">Así transformamos tu negocio en 3 pasos</h2>
  </div>
  <div class="steps-grid">
    <div class="step-card">
      <div class="step-num">01</div>
      <p class="step-title">Conversamos</p>
      <p class="step-desc">Agenda una llamada gratuita de 30 minutos. Escuchamos tus necesidades, retos y objetivos de negocio sin compromisos.</p>
    </div>
    <div class="step-card">
      <div class="step-num">02</div>
      <p class="step-title">Diseñamos</p>
      <p class="step-desc">Creamos el plan técnico ideal para tu caso: arquitectura, tecnologías, cronograma y presupuesto transparente.</p>
    </div>
    <div class="step-card">
      <div class="step-num">03</div>
      <p class="step-title">Entregamos</p>
      <p class="step-desc">Desarrollo ágil con entregas semanales. Ves el progreso en tiempo real hasta el lanzamiento de tu solución.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── MÉTRICAS ──
st.markdown("""
<div class="metrics-section">
  <div style="text-align:center; margin-bottom:3rem;">
    <p class="section-label">Resultados Reales</p>
    <h2 class="section-title">Números que hablan por sí solos</h2>
  </div>
  <div class="metrics-grid">
    <div>
      <div class="metric-num">50+</div>
      <div class="metric-label">Proyectos Entregados</div>
    </div>
    <div>
      <div class="metric-num">97%</div>
      <div class="metric-label">Satisfacción de Clientes</div>
    </div>
    <div>
      <div class="metric-num">3x</div>
      <div class="metric-label">Más Productividad</div>
    </div>
    <div>
      <div class="metric-num">5★</div>
      <div class="metric-label">Años de Experiencia</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── TESTIMONIOS ──
st.markdown("""
<div style="padding:6rem 2rem; max-width:1200px; margin:0 auto;" id="testimonios">
  <div style="text-align:center; margin-bottom:3rem;">
    <p class="section-label">Testimonios</p>
    <h2 class="section-title">Lo que dicen nuestros clientes</h2>
  </div>
  <div class="testimonials-grid">
    <div class="testimonial-card">
      <div class="stars">★★★★★</div>
      <p class="testimonial-text">"JOSEGART transformó completamente nuestra operación. La app que desarrollaron redujo nuestro tiempo de gestión en un 70%. Increíble equipo."</p>
      <div class="testimonial-author">
        <div class="avatar">CM</div>
        <div>
          <div class="author-name">Carlos M.</div>
          <div class="author-role">CEO · TechVentures</div>
        </div>
      </div>
    </div>
    <div class="testimonial-card">
      <div class="stars">★★★★★</div>
      <p class="testimonial-text">"La asesoría en IA fue reveladora. Ahora automatizamos procesos que antes tardaban días enteros y lo hacemos en minutos. El ROI fue inmediato."</p>
      <div class="testimonial-author">
        <div class="avatar">ML</div>
        <div>
          <div class="author-name">María L.</div>
          <div class="author-role">Fundadora · InnovaStart</div>
        </div>
      </div>
    </div>
    <div class="testimonial-card">
      <div class="stars">★★★★★</div>
      <p class="testimonial-text">"Profesionalismo total desde el primer día. Entregaron antes del plazo y la seguridad de la aplicación es completamente impecable. 100% recomendados."</p>
      <div class="testimonial-author">
        <div class="avatar">RK</div>
        <div>
          <div class="author-name">Roberto K.</div>
          <div class="author-role">Director · DigitalCorp</div>
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── PROYECTOS DESARROLLADOS ──
st.markdown(
    '<div style="padding:6rem 2rem 3rem; background: rgba(15,22,41,.6); border-top:1px solid rgba(0,212,255,.08); border-bottom:1px solid rgba(0,212,255,.08);" id="proyectos">'
    '<div style="max-width:1200px; margin:0 auto;">'
    '<div style="text-align:center; margin-bottom:3rem;">'
    '<p class="section-label">Portafolio</p>'
    '<h2 class="section-title">Proyectos Desarrollados</h2>'
    '<p class="section-subtitle" style="margin:0 auto;">Aplicaciones reales, funcionando hoy, construidas para distintos sectores e industrias.</p>'
    '</div>',
    unsafe_allow_html=True
)

# ── VIDEO ANIMADO DE PROYECTOS ──
st.markdown(
    '<div style="border-radius:20px; overflow:hidden; border:1px solid rgba(0,212,255,0.25); '
    'box-shadow:0 0 60px rgba(0,212,255,0.15), 0 30px 60px rgba(0,0,0,0.5); margin-bottom:3rem;">',
    unsafe_allow_html=True
)
components.iframe(VIDEO_URL, height=520, scrolling=False)
st.markdown('</div>', unsafe_allow_html=True)

# ── GRID DE PROYECTOS CON CONTRASEÑA ──
_projects = [
    {
        "thumb_bg": "linear-gradient(135deg,#0f4c2a,#1a7a45)",
        "emoji": "🏢",
        "tag": "Inmobiliario",
        "title": "Administración de Conjuntos y Condominios",
        "desc": "Plataforma integral para la gestión de conjuntos residenciales y condominios: control de residentes, cuotas de administración, reservas de zonas comunes, comunicados y seguimiento de PQR.",
        "url": "https://condominio-ceiba.streamlit.app/",
    },
    {
        "thumb_bg": "linear-gradient(135deg,#1a1a2e,#e94560)",
        "emoji": "🚗",
        "tag": "Automotriz",
        "title": "Venta y Permuta de Vehículos",
        "desc": "Sistema para concesionarios y particulares: inventario de vehículos, publicación de fichas técnicas, gestión de permutas, seguimiento de clientes interesados y panel administrativo completo.",
        "url": "https://jjgt-autos.streamlit.app/",
    },
    {
        "thumb_bg": "linear-gradient(135deg,#003366,#0099cc)",
        "emoji": "🧴",
        "tag": "Retail",
        "title": "Empresa de Venta de Productos de Aseo",
        "desc": "Tienda y sistema de gestión para empresa de productos de limpieza e higiene: catálogo de productos, control de inventario, pedidos, facturación y seguimiento de clientes.",
        "url": "https://brillol.streamlit.app/",
    },
    {
        "thumb_bg": "linear-gradient(135deg,#2d1b69,#7c3aed)",
        "emoji": "🧠",
        "tag": "Salud",
        "title": "Clínica de Psicología",
        "desc": "Plataforma para clínica de salud mental: agendamiento de citas, gestión de pacientes e historias clínicas, recordatorios automáticos, facturación de sesiones y dashboard para psicólogos.",
        "url": "https://clinicadelamor.streamlit.app/",
    },
    {
        "thumb_bg": "linear-gradient(135deg,#1a3a1a,#f59e0b)",
        "emoji": "👷",
        "tag": "RRHH / Empleo",
        "title": "Empresa de Servicios de Empleo Temporal",
        "desc": "Sistema para empresa de empleo temporal: registro de candidatos, gestión de vacantes, asignación de personal, contratos, nómina básica y reporte de horas trabajadas.",
        "url": "https://agendar.streamlit.app/",
    },
    {
        "thumb_bg": "linear-gradient(135deg,#0a1628,#00d4ff)",
        "emoji": "🚐",
        "tag": "Transporte",
        "title": "Servicios de Transporte Particular",
        "desc": "Aplicación para empresa de transporte privado: reservas de viajes, asignación de conductores y vehículos, seguimiento de servicios, historial de clientes y liquidación de conductores.",
        "url": "https://reservar-dp.streamlit.app/",
    },
]

# Estilos adicionales para el widget de contraseña dentro de las tarjetas
st.markdown("""
<style>
.pwd-container {
  padding: .75rem 1.5rem 1.25rem;
  background: rgba(0,212,255,.04);
  border-top: 1px solid rgba(0,212,255,.12);
}
.pwd-success {
  display: inline-flex; align-items: center; gap: .5rem;
  background: rgba(0,212,255,.1); border: 1px solid rgba(0,212,255,.3);
  border-radius: 50px; padding: .4rem 1.1rem;
  color: #00D4FF; font-weight: 600; font-size: .88rem;
  text-decoration: none; margin: .5rem 1.5rem 1.25rem; display: block; width: fit-content;
}
/* Botón "Ver proyecto" nativo de Streamlit, estilizado */
[data-testid="stButton"] > button[kind="secondary"] {
  background: transparent !important;
  color: #00D4FF !important;
  border: 1px solid rgba(0,212,255,.4) !important;
  border-radius: 50px !important;
  font-size: .85rem !important;
  font-weight: 600 !important;
  padding: .35rem 1.1rem !important;
  transition: all .2s !important;
}
[data-testid="stButton"] > button[kind="secondary"]:hover {
  background: rgba(0,212,255,.1) !important;
  border-color: #00D4FF !important;
}
/* Input de contraseña dentro de tarjetas */
.stTextInput input[type="password"] {
  background: rgba(15,22,41,.95) !important;
  color: #E2E8F0 !important;
  border: 1px solid rgba(0,212,255,.35) !important;
  border-radius: 8px !important;
  font-size: .9rem !important;
}
.stTextInput input[type="password"]::placeholder { color: #64748B !important; }
</style>
""", unsafe_allow_html=True)

# Renderizar proyectos en filas de 3
_proj_rows = [_projects[i:i+3] for i in range(0, len(_projects), 3)]
for _row in _proj_rows:
    _cols = st.columns(3)
    for _col, _p in zip(_cols, _row):
        _key = ''.join(c for c in _p['title'] if c.isalnum())[:18]
        with _col:
            # Tarjeta sin enlace (lo gestiona Streamlit)
            st.markdown(
                f'<div class="project-card" style="margin-bottom:.25rem;">'
                f'<div class="project-thumb" style="background:{_p["thumb_bg"]};">{_p["emoji"]}</div>'
                f'<div class="project-body" style="padding-bottom:.75rem;">'
                f'<span class="project-tag">{_p["tag"]}</span>'
                f'<p class="project-title">{_p["title"]}</p>'
                f'<p class="project-desc">{_p["desc"]}</p>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            # Estado: desbloqueado → mostrar enlace
            if st.session_state.proj_unlocked.get(_key):
                st.markdown(
                    f'<a href="{_p["url"]}" target="_blank" class="pwd-success">'
                    f'✅ Acceso concedido &nbsp;·&nbsp; Abrir proyecto →</a>',
                    unsafe_allow_html=True
                )
                if st.button("🔒 Cerrar acceso", key=f"lock_{_key}"):
                    st.session_state.proj_unlocked[_key] = False
                    st.session_state.proj_asking[_key] = False
                    st.rerun()
            # Estado: pidiendo contraseña
            elif st.session_state.proj_asking.get(_key):
                _pwd = st.text_input(
                    "Contraseña de acceso:",
                    type="password",
                    key=f"pwd_{_key}",
                    placeholder="Ingresa la contraseña...",
                )
                if _pwd == PROJECT_PASSWORD:
                    st.session_state.proj_unlocked[_key] = True
                    st.session_state.proj_asking[_key] = False
                    st.rerun()
                elif _pwd:
                    st.error("Contraseña incorrecta. Intenta de nuevo.")
            # Estado: sin acceso → mostrar botón
            else:
                if st.button(f"🔒 Ver proyecto", key=f"btn_{_key}"):
                    st.session_state.proj_asking[_key] = True
                    st.rerun()

st.markdown('</div></div>', unsafe_allow_html=True)

# ── PLANES (sin precios) ──
st.markdown("""
<div style="padding:2rem 2rem 6rem; max-width:1200px; margin:0 auto;" id="planes">
  <div style="text-align:center; margin-bottom:3rem;">
    <p class="section-label">Planes</p>
    <h2 class="section-title">Una solución para cada etapa de tu negocio</h2>
    <p class="section-subtitle" style="margin:0 auto;">Cada proyecto es único. Contáctanos y diseñamos juntos la propuesta ideal para ti.</p>
  </div>
  <div class="pricing-grid">
    <div class="pricing-card">
      <p class="plan-name">Básico</p>
      <p class="plan-desc">Ideal para freelancers y pequeños negocios que quieren dar el primer paso digital.</p>
      <ul class="plan-features">
        <li>Consultoría digital mensual</li>
        <li>1 aplicación básica</li>
        <li>Soporte por email</li>
        <li>Dashboard de seguimiento</li>
        <li>Actualizaciones de seguridad</li>
      </ul>
      <a href="#contacto" class="btn-secondary" style="display:block; text-align:center; padding:.75rem;">Solicitar Información</a>
    </div>
    <div class="pricing-card featured">
      <div class="popular-badge">⭐ Más Popular</div>
      <p class="plan-name">Pro</p>
      <p class="plan-desc">Para negocios en crecimiento que necesitan tecnología avanzada e IA.</p>
      <ul class="plan-features">
        <li>Apps avanzadas ilimitadas</li>
        <li>Integración de IA y automatización</li>
        <li>Soporte prioritario 24/7</li>
        <li>Estrategia de negocios digitales</li>
        <li>Informes mensuales de rendimiento</li>
        <li>Capacitación del equipo</li>
      </ul>
      <a href="#contacto" class="btn-primary" style="display:block; text-align:center; padding:.75rem;">Solicitar Información</a>
    </div>
    <div class="pricing-card">
      <p class="plan-name">Enterprise</p>
      <p class="plan-desc">Soluciones completas para empresas que requieren escala y dedicación total.</p>
      <ul class="plan-features">
        <li>Equipo dedicado completo</li>
        <li>SLA garantizado 99.9%</li>
        <li>Arquitectura cloud personalizada</li>
        <li>Integraciones enterprise</li>
        <li>Soporte on-site disponible</li>
        <li>Contrato de confidencialidad NDA</li>
      </ul>
      <a href="#contacto" class="btn-secondary" style="display:block; text-align:center; padding:.75rem;">Contactar Ventas</a>
    </div>
  </div>
  <p style="text-align:center; color:#94A3B8; margin-top:2rem; font-size:.9rem;">
    🛡️ 30 días de garantía de satisfacción · Sin compromisos iniciales · Propuesta personalizada sin costo
  </p>
</div>
""", unsafe_allow_html=True)

# ── FAQ ──
st.markdown("""
<div style="padding:2rem 2rem 6rem;" id="faq">
  <div style="max-width:1200px; margin:0 auto; text-align:center; margin-bottom:3rem;">
    <p class="section-label">FAQ</p>
    <h2 class="section-title">Preguntas Frecuentes</h2>
  </div>
  <div class="faq-list">
""", unsafe_allow_html=True)

faq_items = [
    ("¿Cuánto tiempo tarda desarrollar mi aplicación?",
     "Depende de la complejidad. Un proyecto básico puede estar listo en 2-4 semanas. Las soluciones avanzadas con IA toman entre 6-12 semanas. Siempre recibirás un cronograma claro desde el primer día con hitos semanales."),
    ("¿Las aplicaciones son seguras?",
     "Absolutamente. Implementamos cifrado AES-256, autenticación de dos factores, backups automáticos diarios, auditorías de seguridad periódicas y cumplimos con los estándares OWASP y GDPR/RGPD."),
    ("¿Puedo integrar IA en mi negocio actual?",
     "Sí. Trabajamos con OpenAI, Anthropic, Google AI y modelos open-source para integrar IA en tus sistemas existentes sin necesidad de reconstruir desde cero."),
    ("¿Qué pasa si no estoy satisfecho con el resultado?",
     "Ofrecemos 30 días de garantía de satisfacción. Si el entregable no cumple las especificaciones acordadas, lo corregimos sin costo adicional hasta que quedes completamente satisfecho."),
    ("¿Trabajan con negocios pequeños?",
     "¡Por supuesto! Muchos de nuestros clientes son emprendedores y PyMEs. Tenemos planes adaptados a todos los presupuestos y crecemos junto contigo."),
    ("¿Qué incluye la consulta inicial gratuita?",
     "La consulta de 30 minutos incluye: análisis de tu situación actual, identificación de oportunidades de mejora con tecnología e IA, propuesta preliminar de solución, y presupuesto orientativo sin compromiso."),
]

for q, a in faq_items:
    with st.expander(q):
        st.markdown(f'<p style="color:#94A3B8; line-height:1.7;">{a}</p>', unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# ── CTA FINAL + FORMULARIO ──
st.markdown("""
<div class="cta-section" id="contacto">
  <div class="cta-inner">
    <p class="section-label" style="text-align:center;">Empieza Hoy</p>
    <h2 class="section-title" style="text-align:center;">¿Listo para Llevar tu Negocio al Siguiente Nivel?</h2>
    <p style="color:#94A3B8; text-align:center; margin-bottom:2.5rem;">
      Agenda tu consulta gratuita ahora. Sin compromisos, sin tarjeta de crédito. Solo resultados.
    </p>
  </div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    with st.form("contact_form", clear_on_submit=True):
        nombre = st.text_input("Nombre completo *", placeholder="Tu nombre")
        email = st.text_input("Email *", placeholder="tu@email.com")
        telefono = st.text_input("Teléfono (opcional)", placeholder="+1 234 567 8900")
        mensaje = st.text_area("¿Cuéntanos sobre tu proyecto?", placeholder="Describe brevemente qué necesitas...", height=100)
        submit = st.form_submit_button("🚀 Solicitar Consulta Gratuita Ahora", use_container_width=True)

        if submit:
            if not nombre or not email:
                st.error("Por favor completa los campos obligatorios (Nombre y Email).")
            elif "@" not in email:
                st.error("Por favor ingresa un email válido.")
            else:
                with st.spinner("Enviando tu solicitud..."):
                    # 1. Enviar email de notificación
                    email_ok, email_msg = send_email_gmail(nombre, email, telefono, mensaje)

                    # 2. Guardar en Google Sheets (si las credenciales están disponibles)
                    sheets_ok = False
                    creds, _ = load_credentials_from_toml()
                    if creds:
                        client = get_google_sheets_connection(creds)
                        if client:
                            sheets_ok, sheets_msg = save_contact_to_sheets(client, nombre, email, telefono, mensaje)

                if email_ok:
                    st.success(f"✅ ¡Gracias {nombre}! Hemos recibido tu solicitud. Te contactaremos en menos de 24 horas.")
                    st.balloons()
                else:
                    # Mostrar el error de email pero continuar si Sheets funcionó
                    st.warning(email_msg)
                    if sheets_ok:
                        st.success(f"✅ ¡Gracias {nombre}! Tu solicitud fue registrada. Te contactaremos pronto.")
                        st.balloons()
                    else:
                        st.error("No se pudo procesar tu solicitud en este momento. Por favor intenta de nuevo o escríbenos directamente a josegarjagt@gmail.com.")

    st.markdown("""
    <div class="trust-badges" style="margin-top:1rem;">
      <div class="trust-item">🔒 Conexión SSL segura</div>
      <div class="trust-item">✉️ Sin spam, prometido</div>
      <div class="trust-item">⏱️ Respuesta en 24h</div>
    </div>
    """, unsafe_allow_html=True)

# ── FOOTER ──
st.markdown("""
<div class="footer">
  <div class="footer-grid">
    <div>
      <div>
        <span class="logo-badge">JG</span>
        <span class="logo-text">JOSE<span style="color:#7C3AED">GART</span></span>
      </div>
      <p class="footer-tagline">Tecnología que construye tu futuro.<br>Desarrollamos apps seguras, implementamos IA y potenciamos negocios digitales.</p>
      <div class="social-links" style="margin-top:1rem;">
        <a href="#" class="social-link" aria-label="LinkedIn">in</a>
        <a href="#" class="social-link" aria-label="GitHub">GH</a>
        <a href="#" class="social-link" aria-label="Twitter/X">𝕏</a>
        <a href="#" class="social-link" aria-label="WhatsApp">WA</a>
      </div>
    </div>
    <div>
      <p class="footer-col-title">Servicios</p>
      <ul class="footer-links">
        <li><a href="#servicios">Apps a Medida</a></li>
        <li><a href="#servicios">Seguridad Digital</a></li>
        <li><a href="#servicios">IA & Automatización</a></li>
        <li><a href="#servicios">Negocios Digitales</a></li>
        <li><a href="#servicios">Asesoría en IA</a></li>
      </ul>
    </div>
    <div>
      <p class="footer-col-title">Empresa</p>
      <ul class="footer-links">
        <li><a href="#">Sobre Nosotros</a></li>
        <li><a href="#">Nuestro Equipo</a></li>
        <li><a href="#">Portfolio</a></li>
        <li><a href="#">Blog</a></li>
        <li><a href="#contacto">Contacto</a></li>
      </ul>
    </div>
    <div>
      <p class="footer-col-title">Recursos</p>
      <ul class="footer-links">
        <li><a href="#">Guía de IA 2025</a></li>
        <li><a href="#">Casos de Éxito</a></li>
        <li><a href="#">Webinars Gratis</a></li>
        <li><a href="#">Newsletter</a></li>
        <li><a href="#">Documentación</a></li>
      </ul>
    </div>
    <div>
      <p class="footer-col-title">Legal</p>
      <ul class="footer-links">
        <li><a href="#">Privacidad</a></li>
        <li><a href="#">Términos de Uso</a></li>
        <li><a href="#">Cookies</a></li>
        <li><a href="#">GDPR / RGPD</a></li>
        <li><a href="#">Seguridad</a></li>
      </ul>
    </div>
  </div>
  <div class="footer-bottom">
    <span>© 2025 JOSEGART - Un Futuro Mejor. Todos los derechos reservados.</span>
    <span>Hecho con ❤️ para impulsar tu negocio</span>
  </div>
</div>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "JOSEGART",
  "description": "Desarrollo de aplicaciones seguras a medida, asesoramiento en IA y herramientas digitales para negocios",
  "url": "https://josegart.com",
  "applicationCategory": "BusinessApplication",
  "offers": {
    "@type": "Offer",
    "price": "299",
    "priceCurrency": "COP"
  }
}
</script>
""", unsafe_allow_html=True)
