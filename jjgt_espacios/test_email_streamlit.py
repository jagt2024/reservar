"""
test_email_streamlit.py
Prueba de envío de correo con adjunto PDF opcional.
Ejecutar:  streamlit run test_email_streamlit.py
"""

import streamlit as st
import tempfile
import os

# ── Configuración de página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Prueba de Envío de Correo",
    page_icon="✉️",
    layout="centered",
)

# ── Estilos ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'IBM Plex Mono', monospace !important;
        }
        .stButton > button {
            background: #0f172a;
            color: #f8fafc;
            border: none;
            border-radius: 6px;
            font-family: 'IBM Plex Mono', monospace;
            font-weight: 600;
            letter-spacing: 0.05em;
            padding: 0.6rem 1.4rem;
            transition: background 0.2s;
        }
        .stButton > button:hover {
            background: #1e40af;
        }
        .result-ok {
            background: #dcfce7;
            border-left: 4px solid #16a34a;
            padding: 1rem;
            border-radius: 4px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.9rem;
        }
        .result-err {
            background: #fee2e2;
            border-left: 4px solid #dc2626;
            padding: 1rem;
            border-radius: 4px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Función de envío (igual a la del módulo principal) ─────────────────────────
def enviar_factura_email(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    pdf_bytes: bytes,
    nombre_pdf: str,
    email_from: str,
    nombre_from: str,
) -> bool:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", prefix="fac_"
        ) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        import yagmail

        yag = yagmail.SMTP(
            user=st.secrets["emails"]["smtp_user"],
            password=st.secrets["emails"]["smtp_password"],
            smtp_starttls=True,
            smtp_ssl=False,
        )
        remitente = f"{nombre_from} <{email_from}>" if nombre_from else email_from

        attachments = [tmp_path] if pdf_bytes else []

        yag.send(
            to=destinatario,
            subject=asunto,
            contents=cuerpo,
            attachments=attachments or None,
            headers={"From": remitente},
        )
        return True
    except Exception as e:
        st.session_state["last_error"] = str(e)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("✉️ Prueba de envío de correo")
st.caption("Verifica la configuración SMTP antes de ejecutar la facturación masiva.")

st.divider()

# Mostrar remitente configurado (solo lectura)
try:
    sender_display = st.secrets["emails"]["smtp_user"]
except Exception:
    sender_display = "⚠️ No configurado en secrets.toml"

st.info(f"**Remitente SMTP configurado:** `{sender_display}`")

st.divider()

# ── Formulario ─────────────────────────────────────────────────────────────────
with st.form("form_email"):
    st.subheader("Datos del mensaje de prueba")

    col1, col2 = st.columns(2)
    with col1:
        destinatario = st.text_input(
            "Destinatario *",
            placeholder="cliente@empresa.com",
        )
    with col2:
        nombre_from = st.text_input(
            "Nombre remitente visible",
            value="Suite Salitre",
            placeholder="Mi Empresa S.A.S.",
        )

    email_from = st.text_input(
        "Email remitente visible (campo From)",
        value=sender_display if "@" in sender_display else "",
        placeholder="notificaciones@miempresa.com",
    )

    asunto = st.text_input(
        "Asunto *",
        value="[PRUEBA] Verificación de envío de factura",
    )

    cuerpo = st.text_area(
        "Cuerpo del mensaje *",
        value=(
            "Hola,\n\n"
            "Este es un correo de prueba para verificar que el sistema de "
            "envío de facturas por email funciona correctamente.\n\n"
            "Si recibe este mensaje, la configuración es exitosa.\n\n"
            "Atentamente,\nSuite Salitre"
        ),
        height=160,
    )

    st.markdown("**Adjunto (opcional)**")
    archivo = st.file_uploader(
        "Sube un PDF para adjuntar (si no subes nada, se envía sin adjunto)",
        type=["pdf"],
    )

    enviado = st.form_submit_button("📤 Enviar correo de prueba", use_container_width=True)

# ── Acción ─────────────────────────────────────────────────────────────────────
if enviado:
    # Validaciones básicas
    errores_validacion = []
    if not destinatario or "@" not in destinatario:
        errores_validacion.append("El destinatario no parece un email válido.")
    if not asunto.strip():
        errores_validacion.append("El asunto no puede estar vacío.")
    if not cuerpo.strip():
        errores_validacion.append("El cuerpo del mensaje no puede estar vacío.")

    if errores_validacion:
        for err in errores_validacion:
            st.warning(err)
    else:
        pdf_bytes = b""
        nombre_pdf = "prueba.pdf"
        if archivo is not None:
            pdf_bytes = archivo.read()
            nombre_pdf = archivo.name

        with st.spinner("Enviando correo…"):
            ok = enviar_factura_email(
                destinatario=destinatario.strip(),
                asunto=asunto.strip(),
                cuerpo=cuerpo.strip(),
                pdf_bytes=pdf_bytes,
                nombre_pdf=nombre_pdf,
                email_from=email_from.strip() or sender_display,
                nombre_from=nombre_from.strip(),
            )

        if ok:
            st.markdown(
                f'<div class="result-ok">✅ Correo enviado correctamente a <strong>{destinatario}</strong>.</div>',
                unsafe_allow_html=True,
            )
            st.balloons()
        else:
            error_msg = st.session_state.get("last_error", "Error desconocido.")
            st.markdown(
                f'<div class="result-err">❌ Error al enviar el correo.<br><br>'
                f'<strong>Detalle:</strong> {error_msg}</div>',
                unsafe_allow_html=True,
            )

# ── Ayuda ──────────────────────────────────────────────────────────────────────
with st.expander("ℹ️ ¿Cómo configurar secrets.toml?"):
    st.code(
        """
# .streamlit/secrets.toml

smtp_user     = st.secrets['emails']['smtp_user']
smtp_password = st.secrets['emails']['smtp_password']
        """,
        language="toml",
    )
    st.markdown(
        "Para Gmail debes generar una **contraseña de aplicación** en "
        "[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) "
        "(requiere verificación en dos pasos activada)."
    )
