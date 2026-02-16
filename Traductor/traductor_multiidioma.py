"""
Módulo de Traductor Multiidioma
"""

import streamlit as st
from gtts import gTTS
from googletrans import Translator
import PyPDF2
from docx import Document
import tempfile
import os
from io import BytesIO
import base64

# Diccionario de idiomas
IDIOMAS = {
    "Español": "es",
    "Inglés": "en",
    "Francés": "fr",
    "Alemán": "de"
}

def extraer_texto_pdf(archivo_pdf):
    """Extrae texto de un archivo PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(archivo_pdf)
        texto = ""
        for pagina in pdf_reader.pages:
            texto += pagina.extract_text()
        return texto
    except Exception as e:
        st.error(f"Error al leer el PDF: {str(e)}")
        return None

def extraer_texto_docx(archivo_docx):
    """Extrae texto de un archivo DOCX"""
    try:
        doc = Document(archivo_docx)
        texto = ""
        for parrafo in doc.paragraphs:
            texto += parrafo.text + "\n"
        return texto
    except Exception as e:
        st.error(f"Error al leer el DOCX: {str(e)}")
        return None

def traducir_texto(texto, idioma_destino):
    """Traduce texto al idioma especificado"""
    try:
        translator = Translator()
        traduccion = translator.translate(texto, dest=idioma_destino)
        return traduccion.text
    except Exception as e:
        st.error(f"Error en la traducción: {str(e)}")
        return None

def generar_audio(texto, idioma, velocidad):
    """Genera audio a partir de texto"""
    try:
        slow = velocidad < 1.0
        tts = gTTS(text=texto, lang=idioma, slow=slow)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            tts.save(fp.name)
            return fp.name
    except Exception as e:
        st.error(f"Error al generar el audio: {str(e)}")
        return None

def get_audio_download_link(audio_file):
    """Crea enlace de descarga para el audio"""
    with open(audio_file, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()
    return f'<a href="data:audio/mp3;base64,{b64}" download="traduccion.mp3">📥 Descargar Audio</a>'


def mostrar_traductor():
    """
    Función principal del traductor que puede ser llamada desde un menú
    """
    
    # Título de la sección
    st.title("🌍 Traductor Multiidioma")
    st.markdown("---")

    # Crear dos columnas: sidebar simulado y contenido principal
    col_config, col_principal = st.columns([1, 3])
    
    # ========== COLUMNA DE CONFIGURACIÓN (SIDEBAR) ==========
    with col_config:
        st.header("⚙️ Configuración")
        
        # Selección de idioma destino
        st.subheader("🎯 Idioma")
        idioma_seleccionado = st.selectbox(
            "Idioma destino:",
            options=list(IDIOMAS.keys()),
            index=1,
            key="idioma_traductor"
        )
        
        # Control de velocidad
        st.subheader("🎚️ Velocidad")
        velocidad = st.slider(
            "Audio:",
            min_value=0.5,
            max_value=1.5,
            value=1.0,
            step=0.1,
            key="velocidad_traductor",
            help="1.0 = velocidad normal"
        )
        
        st.markdown("---")
        st.info("💡 **Pasos:**\n\n1. Selecciona idioma\n2. Ingresa texto o sube archivo\n3. Haz clic en 'Traducir'")
    
    # ========== COLUMNA PRINCIPAL ==========
    with col_principal:
        
        # Tabs para diferentes modos de entrada
        tab1, tab2 = st.tabs(["📝 Entrada de Texto", "📄 Subir Documento"])
        
        texto_a_traducir = ""
        
        # Tab 1: Entrada de texto manual
        with tab1:
            st.subheader("Escribe el texto a traducir:")
            texto_manual = st.text_area(
                "Texto:",
                height=200,
                placeholder="Escribe aquí el texto que deseas traducir...",
                label_visibility="collapsed",
                key="texto_manual_traductor"
            )
            if texto_manual:
                texto_a_traducir = texto_manual
        
        # Tab 2: Subir documento
        with tab2:
            st.subheader("Sube un documento PDF o DOCX:")
            archivo_subido = st.file_uploader(
                "Selecciona un archivo:",
                type=["pdf", "docx"],
                label_visibility="collapsed",
                key="archivo_traductor"
            )
            
            if archivo_subido is not None:
                st.info(f"📎 Archivo: {archivo_subido.name} ({archivo_subido.size} bytes)")
                
                # Extraer texto según el tipo de archivo
                if archivo_subido.name.endswith('.pdf'):
                    texto_extraido = extraer_texto_pdf(archivo_subido)
                elif archivo_subido.name.endswith('.docx'):
                    texto_extraido = extraer_texto_docx(archivo_subido)
                
                if texto_extraido:
                    texto_a_traducir = texto_extraido
                    with st.expander("👁️ Ver texto extraído"):
                        st.text_area("Contenido:", texto_extraido, height=200, disabled=True, key="texto_extraido_traductor")
        
        # ========== BOTÓN DE TRADUCCIÓN ==========
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            boton_traducir = st.button("🚀 Traducir", use_container_width=True, type="primary", key="boton_traducir")
        
        # ========== PROCESAMIENTO Y RESULTADOS ==========
        if boton_traducir:
            if not texto_a_traducir:
                st.warning("⚠️ Por favor, ingresa un texto o sube un documento para traducir.")
            else:
                # Obtener código del idioma seleccionado
                codigo_idioma = IDIOMAS[idioma_seleccionado]
                
                # Mostrar spinner mientras se traduce
                with st.spinner("Traduciendo..."):
                    texto_traducido = traducir_texto(texto_a_traducir, codigo_idioma)
                
                if texto_traducido:
                    st.success("✅ Traducción completada!")
                    st.markdown("---")
                    
                    # Mostrar resultado en dos columnas
                    col_izq, col_der = st.columns(2)
                    
                    with col_izq:
                        st.subheader("📄 Texto Original")
                        st.text_area(
                            "Original:",
                            texto_a_traducir,
                            height=250,
                            disabled=True,
                            label_visibility="collapsed",
                            key="resultado_original"
                        )
                    
                    with col_der:
                        st.subheader(f"📄 Traducción ({idioma_seleccionado})")
                        st.text_area(
                            "Traducción:",
                            texto_traducido,
                            height=250,
                            disabled=True,
                            label_visibility="collapsed",
                            key="resultado_traduccion"
                        )
                    
                    # Generar audio
                    st.markdown("---")
                    st.subheader("🔊 Audio de la Traducción")
                    
                    with st.spinner("Generando audio..."):
                        archivo_audio = generar_audio(texto_traducido, codigo_idioma, velocidad)
                    
                    if archivo_audio:
                        # Reproducir audio
                        st.audio(archivo_audio, format='audio/mp3')
                        
                        # Enlace de descarga
                        st.markdown(get_audio_download_link(archivo_audio), unsafe_allow_html=True)
                    
                    # Botón para descargar el texto traducido
                    st.download_button(
                        label="📥 Descargar Traducción (TXT)",
                        data=texto_traducido,
                        file_name=f"traduccion_{idioma_seleccionado.lower()}.txt",
                        mime="text/plain",
                        key="descargar_traduccion"
                    )


# Si se ejecuta directamente (no importado)
if __name__ == "__main__":
#    st.set_page_config(
##        page_title="Traductor Multiidioma",
#        page_icon="🌍",
#        layout="wide"
#    )
    mostrar_traductor()
