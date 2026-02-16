# 🌍 Traductor Multiidioma con Streamlit

Aplicación web interactiva para traducir texto entre Español, Inglés, Francés y Alemán, con salida en texto y voz.

## 📋 Características

- ✅ Traducción entre 4 idiomas: Español, Inglés, Francés y Alemán
- ✅ Entrada de texto manual o mediante documentos PDF/DOCX
- ✅ Salida en texto y audio (voz)
- ✅ Control de velocidad de reproducción de audio
- ✅ Interfaz intuitiva y fácil de usar
- ✅ Descarga de traducción en formato TXT y MP3

## 🚀 Instalación

### Requisitos previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Pasos de instalación

1. **Clona o descarga los archivos del proyecto**

2. **Instala las dependencias:**
```bash
pip install -r requirements.txt
```

3. **Ejecuta la aplicación:**
```bash
streamlit run traductor_multiidioma.py
```

4. **Abre tu navegador** en la dirección que aparece en la terminal (generalmente `http://localhost:8501`)

## 📖 Modo de Uso

### Opción 1: Entrada de Texto Manual
1. Selecciona el idioma destino en la barra lateral
2. Ve a la pestaña "📝 Entrada de Texto"
3. Escribe o pega el texto que deseas traducir
4. Ajusta la velocidad del audio si lo deseas
5. Haz clic en "🚀 Traducir"

### Opción 2: Subir Documento
1. Selecciona el idioma destino en la barra lateral
2. Ve a la pestaña "📄 Subir Documento"
3. Sube un archivo PDF o DOCX
4. Ajusta la velocidad del audio si lo deseas
5. Haz clic en "🚀 Traducir"

### Configuración de Velocidad
- **0.5 - 0.9**: Velocidad lenta (ideal para aprendizaje)
- **1.0**: Velocidad normal
- **1.1 - 1.5**: Velocidad rápida

## 🎯 Funcionalidades

### Barra Lateral
- **Selección de idioma destino**: Elige entre Español, Inglés, Francés o Alemán
- **Control de velocidad**: Ajusta la velocidad de reproducción del audio (0.5x a 1.5x)

### Área Principal
- **Entrada de Texto**: Campo de texto para escritura manual
- **Subir Documento**: Carga archivos PDF o DOCX
- **Botón Traducir**: Inicia el proceso de traducción
- **Resultados**: Muestra texto original y traducción lado a lado
- **Audio**: Reproduce la traducción en voz
- **Descargas**: Descarga la traducción en TXT y el audio en MP3

## 🔧 Tecnologías Utilizadas

- **Streamlit**: Framework para la interfaz web
- **googletrans**: API de traducción de Google
- **gTTS**: Conversión de texto a voz (Google Text-to-Speech)
- **PyPDF2**: Extracción de texto de archivos PDF
- **python-docx**: Extracción de texto de archivos DOCX

## ⚠️ Notas Importantes

1. **Conexión a Internet**: La aplicación requiere conexión a internet para funcionar, ya que utiliza las APIs de Google Translate y Google Text-to-Speech.

2. **Límites de texto**: Aunque no hay un límite estricto, textos muy largos pueden tardar más en procesarse.

3. **Calidad de audio**: La calidad del audio depende del servicio gTTS de Google.

4. **Archivos PDF**: Algunos PDFs escaneados o con imágenes pueden no extraerse correctamente. Para mejores resultados, usa PDFs con texto seleccionable.

## 🐛 Solución de Problemas

### Error al instalar dependencias
Si tienes problemas instalando `googletrans`, intenta:
```bash
pip install googletrans==4.0.0rc1
```

### Error con PyPDF2
Asegúrate de tener la versión correcta:
```bash
pip install PyPDF2==3.0.1
```

### El audio no se reproduce
- Verifica que tu navegador permita la reproducción de audio
- Algunos navegadores requieren interacción del usuario antes de reproducir audio

## 📝 Licencia

Este proyecto es de código abierto y está disponible para uso personal y educativo.

## 👨‍💻 Contribuciones

Las contribuciones son bienvenidas. Si encuentras un error o tienes una sugerencia, no dudes en crear un issue o pull request.

---

**Desarrollado con ❤️ usando Streamlit**
