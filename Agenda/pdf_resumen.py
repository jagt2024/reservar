import streamlit as st
import PyPDF2
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.probability import FreqDist
from heapq import nlargest
import re
import string
from fpdf import FPDF
import io
import base64
import datetime
import unicodedata

def normalize_unicode_text(text):
    """Normaliza el texto Unicode para evitar problemas de codificación."""
    # Reemplazar caracteres Unicode problemáticos por sus equivalentes ASCII
    replacements = {
        '\u2013': '-',  # guión largo
        '\u2014': '-',  # guión más largo
        '\u2018': "'",  # comilla simple izquierda
        '\u2019': "'",  # comilla simple derecha
        '\u201c': '"',  # comilla doble izquierda
        '\u201d': '"',  # comilla doble derecha
        '\u2026': '...',  # puntos suspensivos
        '\u00a0': ' ',  # espacio sin ruptura
        '\u00ad': '-',  # guión opcional
        # Añadir más reemplazos según sea necesario
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # Eliminar caracteres no ASCII que no se pueden mapear fácilmente
    text = ''.join(c if ord(c) < 128 else ' ' for c in text)
    
    return text

def create_download_pdf(filename, pages_text, full_summary, top_keywords, page_summaries):
    """Crea un PDF con los resúmenes generados y devuelve un enlace de descarga."""
    try:
        # Crear PDF con manejo de caracteres Unicode
        pdf = FPDF()
        pdf.add_page()
        
        # Configurar la fuente
        pdf.set_font("Arial", "B", 16)
        
        # Normalizar textos para evitar problemas de codificación
        safe_filename = normalize_unicode_text(filename)
        safe_full_summary = normalize_unicode_text(full_summary)
        safe_top_keywords = [normalize_unicode_text(k) for k in top_keywords]
            
        # Título
        pdf.cell(0, 10, "Resumen del documento", ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 10, f"Archivo original: {safe_filename}", ln=True)
        pdf.cell(0, 5, f"Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True)
        pdf.ln(5)
        
        # Resumen general
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Resumen general", ln=True)
        pdf.set_font("Arial", "", 11)
        
        # Dividir el texto para evitar desbordamiento
        pdf.multi_cell(0, 5, safe_full_summary)
        pdf.ln(5)
        
        # Palabras clave
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Palabras clave", ln=True)
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 5, ", ".join(safe_top_keywords), ln=True)
        pdf.ln(10)
        
        # Resúmenes por página
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Resumenes por pagina", ln=True)
        
        for idx, ((page_num, text), (summary, keywords)) in enumerate(zip(pages_text, page_summaries)):
            # Comprobar si hay suficiente espacio en la página actual, si no, añadir una nueva
            if pdf.get_y() > 240:  # Si estamos cerca del final de la página
                pdf.add_page()
            
            # Normalizar el texto para esta página
            safe_text = normalize_unicode_text(text)
            safe_summary = normalize_unicode_text(summary) if isinstance(summary, str) else "No disponible"
            safe_keywords = [normalize_unicode_text(k) for k in keywords]
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"Pagina {page_num}", ln=True)
            
            sentences = sent_tokenize(safe_text)
            if len(sentences) <= 1 or summary == "Texto insuficiente":
                pdf.set_font("Arial", "", 11)
                pdf.multi_cell(0, 5, "Texto insuficiente para generar un resumen en esta pagina.")
                # Limitar el texto si es muy largo
                short_text = safe_text[:500] + "..." if len(safe_text) > 500 else safe_text
                pdf.multi_cell(0, 5, short_text)
            else:
                pdf.set_font("Arial", "", 11)
                pdf.multi_cell(0, 5, safe_summary)
                
                if keywords:
                    pdf.set_font("Arial", "I", 10)
                    pdf.cell(0, 5, "Palabras clave: " + ", ".join(safe_keywords), ln=True)
            
            pdf.ln(5)
        
        # Generar el PDF en memoria - CORREGIDO PARA EVITAR EL ERROR
        pdf_output = io.BytesIO()
        # En lugar de usar directamente pdf.output(pdf_output), usamos este método alternativo
        pdf_data = pdf.output(dest='S').encode('latin-1')
        pdf_output.write(pdf_data)
        pdf_output.seek(0)
        
        # Crear un enlace de descarga
        b64_pdf = base64.b64encode(pdf_output.read()).decode()
        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="resumen_{safe_filename}.pdf" class="btn btn-primary">📥 Descargar resumen como PDF</a>'
        
        return href
    except Exception as e:
        st.error(f"Error al generar el PDF: {str(e)}")
        # Ofrecer alternativa en texto plano
        text_output = io.StringIO()
        text_output.write(f"RESUMEN DEL DOCUMENTO\n")
        text_output.write(f"Archivo original: {filename}\n")
        text_output.write(f"Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        text_output.write(f"RESUMEN GENERAL\n{full_summary}\n\n")
        text_output.write(f"PALABRAS CLAVE\n{', '.join(top_keywords)}\n\n")
        text_output.write(f"RESÚMENES POR PÁGINA\n")
        
        for idx, ((page_num, text), (summary, keywords)) in enumerate(zip(pages_text, page_summaries)):
            text_output.write(f"Página {page_num}\n")
            if summary == "Texto insuficiente":
                text_output.write("Texto insuficiente para generar un resumen en esta página.\n")
            else:
                text_output.write(f"{summary}\n")
                if keywords:
                    text_output.write(f"Palabras clave: {', '.join(keywords)}\n")
            text_output.write("\n")
        
        b64_text = base64.b64encode(text_output.getvalue().encode()).decode()
        return f'<a href="data:text/plain;base64,{b64_text}" download="resumen_{filename}.txt">📄 Descargar resumen como texto plano</a>'

# Clase personalizada de FPDF para manejar caracteres Unicode
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        # Establecer la fuente predeterminada que soporte caracteres especiales
        self.add_font('DejaVu', '', './DejaVuSansCondensed.ttf', uni=True)
        self.set_font('DejaVu', '', 10)
    
    def header(self):
        # No usar encabezado personalizado
        pass
    
    def footer(self):
        # No usar pie de página personalizado
        pass

# Descargar recursos necesarios de NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def extract_text_from_pdf(pdf_file):
    """Extrae el texto de un archivo PDF, página por página."""
    reader = PyPDF2.PdfReader(pdf_file)
    pages_text = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text.strip():  # Solo agregar páginas que tengan texto
            pages_text.append((i+1, text))  # Guardar número de página (empezando en 1) y texto
    
    return pages_text

def preprocess_text(text):
    """Limpia y preprocesa el texto para el análisis de frecuencia de palabras.
    Ahora esta función solo se usa para crear el diccionario de frecuencias,
    no para modificar el texto original que se usará en el resumen."""
    # Convertir a minúsculas
    text = text.lower()
    # Eliminar números y puntuación
    text = re.sub(r'\d+', '', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Eliminar saltos de línea múltiples y espacios extras
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_word_frequencies(text, language='spanish'):
    """Obtiene la frecuencia de palabras importantes del texto."""
    # Preprocesar el texto para el análisis
    processed_text = preprocess_text(text)
    
    # Detectar el idioma para usar las stopwords adecuadas
    if len(re.findall(r'\b(the|is|at|on|in|and|or)\b', processed_text)) > len(re.findall(r'\b(el|la|los|las|es|en|y|o)\b', processed_text)):
        language = 'english'
    
    stop_words = set(stopwords.words(language))
    
    # Tokenizar palabras
    words = word_tokenize(processed_text)
    
    # Filtrar stopwords
    filtered_words = [word for word in words if word.lower() not in stop_words]
    
    # Calcular frecuencia de palabras
    word_freq = FreqDist(filtered_words)
    
    return word_freq, language

def summarize_text(text, num_sentences=5):
    """Genera un resumen del texto usando el algoritmo de frecuencia de palabras,
    pero preservando el formato original de las oraciones seleccionadas."""
    # Si el texto está vacío o es muy corto
    if not text or len(text.strip()) < 50:
        return "Texto insuficiente para generar un resumen.", []
    
    # Tokenizar oraciones manteniendo el formato original
    original_sentences = sent_tokenize(text)
    
    # Si no hay suficientes oraciones
    if len(original_sentences) <= 1:
        return "Texto insuficiente para generar un resumen.", []
    
    # Obtener frecuencias de palabras
    word_freq, language = get_word_frequencies(text)
    
    # Asignar puntuación a cada oración basada en la frecuencia de palabras
    sent_scores = {}
    for i, sentence in enumerate(original_sentences):
        # Preprocesar la oración solo para la puntuación
        processed_sentence = preprocess_text(sentence)
        words = word_tokenize(processed_sentence)
        
        for word in words:
            if word in word_freq:
                if i not in sent_scores:
                    sent_scores[i] = word_freq[word]
                else:
                    sent_scores[i] += word_freq[word]
    
    # Obtener las oraciones con mayor puntuación
    summary_sentences_indices = nlargest(min(num_sentences, len(original_sentences)), 
                                        sent_scores, key=sent_scores.get)
    summary_sentences_indices = sorted(summary_sentences_indices)
    
    # Formar el resumen final MANTENIENDO las oraciones originales intactas
    summary = ' '.join([original_sentences[i] for i in summary_sentences_indices])
    
    # Extraer palabras clave (top 10 palabras más frecuentes)
    keywords = [word for word, _ in word_freq.most_common(10)]
    
    return summary, keywords

def resumen_pdf():
    #st.set_page_config(page_title="Resumidor de PDFs", page_icon="📄")
    
    #st.title("📄 Resumidor de Documentos PDF")
    #st.write("Esta aplicación extrae y resume la información más relevante de documentos PDF, página por página.")
    
    # Sección para cargar el archivo
    uploaded_file = st.file_uploader("Carga un archivo PDF", type="pdf")
    
    if uploaded_file is not None:
        with st.spinner('Procesando el documento...'):
            # Obtener el nombre del archivo
            filename = uploaded_file.name
            
            # Extraer texto del PDF
            pages_text = extract_text_from_pdf(uploaded_file)
            
            # Mostrar opciones avanzadas
            with st.expander("Opciones avanzadas"):
                num_sentences = st.slider(
                    "Número de oraciones para el resumen por página",
                    min_value=2,
                    max_value=10,
                    value=3
                )
            
            # Opciones adicionales
            show_full_summary = st.checkbox("Generar también un resumen general del documento completo", value=True)
            
            # Lista para almacenar todos los resúmenes de página
            page_summaries = []
            
            # Variables para el resumen general
            full_summary = ""
            top_keywords = []
            
            if show_full_summary:
                st.header("Resumen General del Documento")
                # Combinar todo el texto para un resumen general
                all_text = " ".join([text for _, text in pages_text])
                
                # Determinar un número apropiado de oraciones para el resumen general
                total_sentences = len(sent_tokenize(all_text))
                general_num_sentences = min(10, max(5, total_sentences // 10))
                
                # Generar resumen general
                full_summary, top_keywords = summarize_text(all_text, num_sentences=general_num_sentences)
                
                st.subheader("Principales ideas del documento")
                st.write(full_summary)
                
                st.subheader("Palabras clave generales")
                st.write(", ".join(top_keywords))
            
            st.header("Resumen por Páginas")
            
            # Procesar cada página
            for page_num, text in pages_text:
                st.subheader(f"Página {page_num}")
                if len(text.strip()) > 0:
                    # Verificar si hay suficiente texto para resumir
                    sentences = sent_tokenize(text)
                    if len(sentences) <= 1:
                        st.write("Texto insuficiente para generar un resumen en esta página.")
                        st.write("**Contenido completo:**")
                        st.write(text)
                        # Agregar a la lista de resúmenes de página
                        page_summaries.append(("Texto insuficiente", []))
                    else:
                        # Ajustar el número de oraciones según el contenido disponible
                        page_num_sentences = min(num_sentences, len(sentences))
                        summary, keywords = summarize_text(text, num_sentences=page_num_sentences)
                        
                        # Mostrar resultados
                        st.write("**Resumen:**")
                        st.write(summary)
                        
                        st.write("**Palabras clave:**")
                        st.write(", ".join(keywords))
                        
                        # Agregar a la lista de resúmenes de página
                        page_summaries.append((summary, keywords))
                        
                        # Mostrar texto completo
                        texto_completo = st.checkbox(f"Ver texto completo de la página {page_num}")
                        if texto_completo:
                            st.text_area(f"Texto extraído de la página {page_num}", text, height=200)
                
                # Agregar un divisor entre páginas para mejor visualización
                st.markdown("---")
            
            # Opción para descargar el resumen como PDF
            if len(pages_text) > 0:
                st.header("Descargar resumen")
                download_link = create_download_pdf(filename, pages_text, full_summary, top_keywords, page_summaries)
                st.markdown(download_link, unsafe_allow_html=True)

if __name__ == "__main__":
    resumen_pdf()