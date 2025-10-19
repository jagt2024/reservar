import streamlit as st
import os
import base64
from pathlib import Path
import mimetypes
import shutil
from datetime import datetime, date

# Configuración de la página
st.set_page_config(
    page_title="Visor de Archivos Multimedia - Condominio Ceiba",
    page_icon="🏢",
    layout="wide"
)

# Configuración de rutas por tipo de archivo
DIRECTORIES = {
    'images': "../Admon-Conjunos/archivos_subidos/images",
    'audio': "../Admon-Conjunos/archivos_subidos/audios", 
    'video': "../Admon-Conjunos/archivos_subidos/videos",
    'other': "../Admon-Conjunos/archivos_subidos/otros"
}

# Ruta para archivos de metadatos
METADATA_DIR = "../Admon-Conjunos/archivos_subidos/metadata"

# Ruta para archivos anteriores
ANTERIORES_DIR = "../Admon-Conjunos/archivos_subidos/anteriores"

# Función para mover archivo a carpeta anteriores
def move_to_anteriores(filename, file_type):
    """Mueve un archivo a la carpeta anteriores"""
    try:
        # Crear directorio anteriores si no existe
        os.makedirs(ANTERIORES_DIR, exist_ok=True)
        
        source_path = os.path.join(DIRECTORIES[file_type], filename)
        dest_path = os.path.join(ANTERIORES_DIR, filename)
        
        # Si ya existe un archivo con el mismo nombre en anteriores, agregar timestamp
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{name}_{timestamp}{ext}"
            dest_path = os.path.join(ANTERIORES_DIR, new_filename)
        
        # Mover archivo
        shutil.move(source_path, dest_path)
        
        # También mover archivo de metadatos si existe
        metadata_file = os.path.join(METADATA_DIR, f"{filename}_{file_type}.json")
        if os.path.exists(metadata_file):
            metadata_dest = os.path.join(ANTERIORES_DIR, f"{os.path.basename(dest_path).split('.')[0]}_{file_type}_metadata.json")
            shutil.move(metadata_file, metadata_dest)
        
        return True, os.path.basename(dest_path)
    except Exception as e:
        return False, str(e)

# Función para convertir string a fecha
def string_to_date(date_string):
    """Convierte string a objeto date, retorna None si no es válido"""
    if not date_string:
        return None
    
    try:
        # Intentar diferentes formatos de fecha
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(str(date_string), fmt).date()
            except ValueError:
                continue
        return None
    except:
        return None

# Función para cargar metadatos de un archivo
def load_metadata(filename, file_type):
    """Carga los metadatos de un archivo específico"""
    metadata_file = os.path.join(METADATA_DIR, f"{filename}_{file_type}.json")
    default_metadata = {
        'titulo': '',
        'descripcion': '',
        'categoria': '',
        'fecha_evento': None,  # Cambiar a None por defecto
        'ubicacion': '',
        'tags': '',
        'observaciones': ''
    }
    
    try:
        if os.path.exists(metadata_file):
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                saved_metadata = json.load(f)
                # Combinar con valores por defecto para asegurar que existan todas las claves
                default_metadata.update(saved_metadata)
                
                # Convertir fecha string a objeto date si existe
                if default_metadata['fecha_evento']:
                    default_metadata['fecha_evento'] = string_to_date(default_metadata['fecha_evento'])
                
        return default_metadata
    except Exception as e:
        st.error(f"Error al cargar metadatos: {str(e)}")
        return default_metadata

# Función para guardar metadatos de un archivo
def save_metadata(filename, file_type, metadata):
    """Guarda los metadatos de un archivo específico"""
    try:
        # Crear directorio de metadatos si no existe
        os.makedirs(METADATA_DIR, exist_ok=True)
        
        metadata_file = os.path.join(METADATA_DIR, f"{filename}_{file_type}.json")
        import json
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Error al guardar metadatos: {str(e)}")
        return False

# Función para obtener archivos de cada directorio específico
@st.cache_data
def get_files_by_type():
    """Obtiene archivos de cada directorio específico por tipo"""
    files_dict = {
        'images': [],
        'audio': [],
        'video': [],
        'other': []
    }
    
    # Extensiones soportadas para validación
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'}
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'}
    
    for file_type, directory_path in DIRECTORIES.items():
        try:
            if os.path.exists(directory_path):
                for filename in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, filename)
                    if os.path.isfile(file_path):
                        file_ext = Path(filename).suffix.lower()
                        
                        # Validar que el archivo esté en el directorio correcto
                        if file_type == 'images' and file_ext in image_extensions:
                            files_dict['images'].append(filename)
                        elif file_type == 'audio' and file_ext in audio_extensions:
                            files_dict['audio'].append(filename)
                        elif file_type == 'video' and file_ext in video_extensions:
                            files_dict['video'].append(filename)
                        elif file_type == 'other':
                            # Para 'other' aceptamos cualquier archivo
                            files_dict['other'].append(filename)
                       #else:
                            # Archivo en directorio incorrecto, mostrar advertencia
                        #    st.warning(f"⚠️ Archivo '{filename}' encontrado en directorio '{file_type}' pero no coincide con el tipo esperado")
            else:
                st.warning(f"⚠️ El directorio {directory_path} no existe")
        except Exception as e:
            st.error(f"Error al acceder al directorio {directory_path}: {str(e)}")
    
    return files_dict

# Función para convertir archivo a base64
def get_base64_encoded_file(file_path):
    """Convierte un archivo a base64 para mostrar en Streamlit"""
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        st.error(f"Error al leer el archivo: {str(e)}")
        return None

# Función para mostrar imágenes
def display_images(image_files):
    """Muestra las imágenes en una galería"""
    if not image_files:
        st.info("No se encontraron archivos de imagen")
        return
    
    st.subheader("🖼️ Galería de Imágenes")
    
    # Selector de imagen
    selected_image = st.selectbox("Selecciona una imagen:", image_files)
    
    if selected_image:
        image_path = os.path.join(DIRECTORIES['images'], selected_image)
        
        # Crear dos columnas
        col1, col2 = st.columns([2, 1])
        
        with col1:
            try:
                st.image(image_path, caption=selected_image, use_column_width=True)
            except Exception as e:
                st.error(f"Error al mostrar la imagen: {str(e)}")
        
        with col2:
            # Cargar metadatos existentes
            metadata = load_metadata(selected_image, 'image')
            
            st.write("**📝 Información de la imagen:**")
            
            # Formulario para editar información
            with st.form(f"metadata_form_image_{selected_image}"):
                metadata['titulo'] = st.text_input("Título:", value=metadata['titulo'], key="titulo")
                metadata['descripcion'] = st.text_area("Descripción:", value=metadata['descripcion'], height=100, key="descripcion")
                metadata['categoria'] = st.selectbox(
                    "Categoría:", 
                    ["", "Evento", "Reunión", "Mantenimiento", "Área común", "Documento", "Otro"],
                    index=0 if not metadata['categoria'] else ["", "Evento", "Reunión", "Mantenimiento", "Área común", "Documento", "Otro"].index(metadata['categoria']) if metadata['categoria'] in ["", "Evento", "Reunión", "Mantenimiento", "Área común", "Documento", "Otro"] else 0
                )
                metadata['fecha_evento'] = st.date_input("Fecha del evento:", value=metadata['fecha_evento'])
                metadata['ubicacion'] = st.text_input("Ubicación:", value=metadata['ubicacion'], key="ubica")
                metadata['tags'] = st.text_input("Tags (separados por comas):", value=metadata['tags'], key="tags")
                metadata['observaciones'] = st.text_area("Observaciones:", value=metadata['observaciones'], key="observ")
                
                submitted = st.form_submit_button("💾 Guardar información")
                
                if submitted:
                    # Convertir fecha a string si existe
                    if metadata['fecha_evento']:
                        metadata['fecha_evento'] = str(metadata['fecha_evento'])
                    
                    if save_metadata(selected_image, 'image', metadata):
                        st.success("✅ Información guardada correctamente")
                        st.rerun()
            
            # Botones de acción
            st.markdown("---")
            col_download, col_remove = st.columns(2)
            
            with col_download:
                # Botón de descarga
                with open(image_path, "rb") as file:
                    st.download_button(
                        label="📥 Descargar",
                        data=file.read(),
                        file_name=selected_image,
                        mime=mimetypes.guess_type(image_path)[0],
                        use_container_width=True
                    )
            
            with col_remove:
                # Botón para mover a anteriores
                if st.button("🗑️ Quitar", key=f"remove_image_{selected_image}", 
                           help="Mover archivo a carpeta 'anteriores'", 
                           use_container_width=True):
                    success, message = move_to_anteriores(selected_image, 'images')
                    if success:
                        st.success(f"✅ Archivo movido a anteriores como: {message}")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Error al mover archivo: {message}")

# Función para mostrar archivos de audio
def display_audio(audio_files):
    """Muestra reproductores de audio"""
    if not audio_files:
        st.info("No se encontraron archivos de audio")
        return
    
    st.subheader("🎵 Reproductor de Audio")
    
    # Selector de audio
    selected_audio = st.selectbox("Selecciona un archivo de audio:", audio_files)
    
    if selected_audio:
        audio_path = os.path.join(DIRECTORIES['audio'], selected_audio)
        
        try:
            # Mostrar reproductor de audio
            st.audio(audio_path)
            
            # Crear columnas para información
            col1, col2 = st.columns(2)
            
            with col1:
                # Cargar metadatos existentes
                metadata = load_metadata(selected_audio, 'audio')
                
                st.write("**📝 Información del audio:**")
                
                # Formulario para editar información
                with st.form(f"metadata_form_audio_{selected_audio}"):
                    metadata['titulo'] = st.text_input("Título:", value=metadata['titulo'], key="titulo1")
                    metadata['descripcion'] = st.text_area("Descripción:", value=metadata['descripcion'], height=80, key="desccrip1")
                    metadata['categoria'] = st.selectbox(
                        "Categoría:", 
                        ["", "Grabación de reunión", "Mensaje", "Audio informativo", "Entrevista", "Otro"],
                        index=0 if not metadata['categoria'] else ["", "Grabación de reunión", "Mensaje", "Audio informativo", "Entrevista", "Otro"].index(metadata['categoria']) if metadata['categoria'] in ["", "Grabación de reunión", "Mensaje", "Audio informativo", "Entrevista", "Otro"] else 0
                    )
                    metadata['fecha_evento'] = st.date_input("Fecha de grabación:", value=metadata['fecha_evento'])
                    metadata['ubicacion'] = st.text_input("Lugar de grabación:", value=metadata['ubicacion'], key="ubica1")
                    metadata['tags'] = st.text_input("Tags (separados por comas):", value=metadata['tags'], key="tags1")
                    metadata['observaciones'] = st.text_area("Observaciones:", value=metadata['observaciones'], key="observ1")
                    
                    submitted = st.form_submit_button("💾 Guardar información")
                    
                    if submitted:
                        # Convertir fecha a string si existe
                        if metadata['fecha_evento']:
                            metadata['fecha_evento'] = str(metadata['fecha_evento'])
                        
                        if save_metadata(selected_audio, 'audio', metadata):
                            st.success("✅ Información guardada correctamente")
                            st.rerun()
            
            with col2:
                # Información técnica del archivo
                st.write("**🔧 Información técnica:**")
                try:
                    file_stats = os.stat(audio_path)
                    st.write(f"- **Archivo:** {selected_audio}")
                    st.write(f"- **Tamaño:** {file_stats.st_size / (1024*1024):.2f} MB")
                    st.write(f"- **Tipo:** {mimetypes.guess_type(audio_path)[0] or 'Desconocido'}")
                    
                    # Botones de acción
                    st.markdown("---")
                    col_download, col_remove = st.columns(2)
                    
                    with col_download:
                        # Botón de descarga
                        with open(audio_path, "rb") as file:
                            st.download_button(
                                label="📥 Descargar",
                                data=file.read(),
                                file_name=selected_audio,
                                mime=mimetypes.guess_type(audio_path)[0],
                                use_container_width=True
                            )
                    
                    with col_remove:
                        # Botón para mover a anteriores
                        if st.button("🗑️ Quitar", key=f"remove_audio_{selected_audio}", 
                                   help="Mover archivo a carpeta 'anteriores'", 
                                   use_container_width=True):
                            success, message = move_to_anteriores(selected_audio, 'audio')
                            if success:
                                st.success(f"✅ Archivo movido a anteriores como: {message}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ Error al mover archivo: {message}")
                                
                except Exception as e:
                    st.error(f"Error al obtener información técnica: {str(e)}")
                        
        except Exception as e:
            st.error(f"Error al reproducir el audio: {str(e)}")

# Función para mostrar archivos de video
def display_video(video_files):
    """Muestra reproductores de video"""
    if not video_files:
        st.info("No se encontraron archivos de video")
        return
    
    st.subheader("🎬 Reproductor de Video")
    
    # Selector de video
    selected_video = st.selectbox("Selecciona un archivo de video:", video_files)
    
    if selected_video:
        video_path = os.path.join(DIRECTORIES['video'], selected_video)
        
        try:
            # Mostrar reproductor de video
            st.video(video_path)
            
            # Crear columnas para información
            col1, col2 = st.columns(2)
            
            with col1:
                # Cargar metadatos existentes
                metadata = load_metadata(selected_video, 'video')
                
                st.write("**📝 Información del video:**")
                
                # Formulario para editar información
                with st.form(f"metadata_form_video_{selected_video}"):
                    metadata['titulo'] = st.text_input("Título:", value=metadata['titulo'], key="titulo2")
                    metadata['descripcion'] = st.text_area("Descripción:", value=metadata['descripcion'], height=80, key="descrip2")
                    metadata['categoria'] = st.selectbox(
                        "Categoría:", 
                        ["", "Reunión grabada", "Presentación", "Tutorial", "Evento", "Inspección", "Otro"],
                        index=0 if not metadata['categoria'] else ["", "Reunión grabada", "Presentación", "Tutorial", "Evento", "Inspección", "Otro"].index(metadata['categoria']) if metadata['categoria'] in ["", "Reunión grabada", "Presentación", "Tutorial", "Evento", "Inspección", "Otro"] else 0
                    )
                    metadata['fecha_evento'] = st.date_input("Fecha de grabación:", value=metadata['fecha_evento'])
                    metadata['ubicacion'] = st.text_input("Lugar de grabación:", value=metadata['ubicacion'], key="ubica2")
                    metadata['tags'] = st.text_input("Tags (separados por comas):", value=metadata['tags'], key="tags2")
                    metadata['observaciones'] = st.text_area("Observaciones:", value=metadata['observaciones'], key="observ2")
                    
                    submitted = st.form_submit_button("💾 Guardar información")
                    
                    if submitted:
                        # Convertir fecha a string si existe
                        if metadata['fecha_evento']:
                            metadata['fecha_evento'] = str(metadata['fecha_evento'])
                        
                        if save_metadata(selected_video, 'video', metadata):
                            st.success("✅ Información guardada correctamente")
                            st.rerun()
            
            with col2:
                # Información técnica del archivo
                st.write("**🔧 Información técnica:**")
                try:
                    file_stats = os.stat(video_path)
                    st.write(f"- **Archivo:** {selected_video}")
                    st.write(f"- **Tamaño:** {file_stats.st_size / (1024*1024):.2f} MB")
                    st.write(f"- **Tipo:** {mimetypes.guess_type(video_path)[0] or 'Desconocido'}")
                    
                    # Botones de acción
                    st.markdown("---")
                    col_download, col_remove = st.columns(2)
                    
                    with col_download:
                        # Botón de descarga
                        with open(video_path, "rb") as file:
                            st.download_button(
                                label="📥 Descargar",
                                data=file.read(),
                                file_name=selected_video,
                                mime=mimetypes.guess_type(video_path)[0],
                                use_container_width=True
                            )
                    
                    with col_remove:
                        # Botón para mover a anteriores
                        if st.button("🗑️ Quitar", key=f"remove_video_{selected_video}", 
                                   help="Mover archivo a carpeta 'anteriores'", 
                                   use_container_width=True):
                            success, message = move_to_anteriores(selected_video, 'video')
                            if success:
                                st.success(f"✅ Archivo movido a anteriores como: {message}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ Error al mover archivo: {message}")
                                
                except Exception as e:
                    st.error(f"Error al obtener información técnica: {str(e)}")
                        
        except Exception as e:
            st.error(f"Error al reproducir el video: {str(e)}")

# Función para mostrar otros archivos
def display_other_files(other_files):
    """Muestra otros tipos de archivos"""
    if not other_files:
        st.info("No se encontraron otros tipos de archivos")
        return
        
    st.subheader("📄 Otros Archivos")
    
    # Selector de archivo
    selected_file = st.selectbox("Selecciona un archivo:", other_files)
    
    if selected_file:
        file_path = os.path.join(DIRECTORIES['other'], selected_file)
        
        # Crear columnas
        col1, col2 = st.columns(2)
        
        with col1:
            # Cargar metadatos existentes
            metadata = load_metadata(selected_file, 'other')
            
            st.write("**📝 Información del archivo:**")
            
            # Formulario para editar información
            with st.form(f"metadata_form_other_{selected_file}"):
                metadata['titulo'] = st.text_input("Título:", value=metadata['titulo'], key="titulo")
                metadata['descripcion'] = st.text_area("Descripción:", value=metadata['descripcion'], height=100, key="deescrip")
                metadata['categoria'] = st.selectbox(
                    "Categoría:", 
                    ["", "Documento", "Reporte", "Contrato", "Acta", "Reglamento", "Otro"],
                    index=0 if not metadata['categoria'] else ["", "Documento", "Reporte", "Contrato", "Acta", "Reglamento", "Otro"].index(metadata['categoria']) if metadata['categoria'] in ["", "Documento", "Reporte", "Contrato", "Acta", "Reglamento", "Otro"] else 0
                )
                metadata['fecha_evento'] = st.date_input("Fecha del documento:", value=metadata['fecha_evento'])
                metadata['ubicacion'] = st.text_input("Departamento/Área:", value=metadata['ubicacion'], key="ubicacion")
                metadata['tags'] = st.text_input("Tags (separados por comas):", value=metadata['tags'], key="tags")
                metadata['observaciones'] = st.text_area("Observaciones:", value=metadata['observaciones'], key="observ")
                
                submitted = st.form_submit_button("💾 Guardar información")
                
                if submitted:
                    # Convertir fecha a string si existe
                    if metadata['fecha_evento']:
                        metadata['fecha_evento'] = str(metadata['fecha_evento'])
                    
                    if save_metadata(selected_file, 'other', metadata):
                        st.success("✅ Información guardada correctamente")
                        st.rerun()
        
        with col2:
            # Información técnica del archivo
            st.write("**🔧 Información técnica:**")
            try:
                # Botones de acción
                st.markdown("---")
                col_download, col_remove = st.columns(2)
                
                with col_download:
                    # Botón de descarga
                    with open(file_path, "rb") as f:
                        st.download_button(
                            label="📥 Descargar",
                            data=f.read(),
                            file_name=selected_file,
                            key=f"download_{selected_file}",
                            use_container_width=True
                        )
                
                with col_remove:
                    # Botón para mover a anteriores
                    if st.button("🗑️ Quitar", key=f"remove_other_{selected_file}", 
                               help="Mover archivo a carpeta 'anteriores'", 
                               use_container_width=True):
                        success, message = move_to_anteriores(selected_file, 'other')
                        if success:
                            st.success(f"✅ Archivo movido a anteriores como: {message}")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"❌ Error al mover archivo: {message}")
                            
            except Exception as e:
                st.error(f"Error con el archivo: {str(e)}")

# Función para buscar en metadatos
def search_metadata(search_term):
    """Busca archivos por términos en sus metadatos"""
    results = []
    search_term = search_term.lower()
    
    try:
        if os.path.exists(METADATA_DIR):
            import json
            for metadata_file in os.listdir(METADATA_DIR):
                if metadata_file.endswith('.json'):
                    try:
                        with open(os.path.join(METADATA_DIR, metadata_file), 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # Extraer nombre del archivo y tipo del nombre del archivo de metadatos
                        filename_parts = metadata_file.replace('.json', '').rsplit('_', 1)
                        if len(filename_parts) == 2:
                            filename, file_type = filename_parts
                            
                            # Buscar en todos los campos de metadatos
                            searchable_text = ' '.join([
                                metadata.get('titulo', ''),
                                metadata.get('descripcion', ''),
                                metadata.get('tags', ''),
                                metadata.get('categoria', ''),
                                metadata.get('observaciones', '')
                            ]).lower()
                            
                            if search_term in searchable_text:
                                results.append({
                                    'filename': filename,
                                    'type': file_type,
                                    'metadata': metadata
                                })
                    except Exception:
                        continue
    except Exception:
        pass
    
    return results

# Función principal
def main():
    # Título principal
    st.title("🏢 Condominio Ceiba - Visor de Archivos Multimedia")
    st.markdown("---")
    
    # Obtener archivos de cada directorio específico
    files_dict = get_files_by_type()
    
    # Verificar el estado de los directorios
    missing_dirs = []
    existing_dirs = []
    
    for file_type, directory_path in DIRECTORIES.items():
        if os.path.exists(directory_path):
            existing_dirs.append(f"✅ {file_type}: {directory_path}")
        else:
            missing_dirs.append(f"❌ {file_type}: {directory_path}")
    
    if missing_dirs:
        st.sidebar.error("**Directorios faltantes:**")
        for dir_info in missing_dirs:
            st.sidebar.write(dir_info)
    
    # Selector de tipo de archivo
    st.sidebar.header("📁 Filtros")
    file_type = st.sidebar.selectbox(
        "Selecciona el tipo de archivo:",
        [ "Imágenes", "Audio", "Video", "Todos", "Otros"]
    )
    
    # Mostrar contenido según la selección
    if file_type == "Imágenes" or file_type == "Todos":
        if files_dict['images']:
            display_images(files_dict['images'])
            st.markdown("---")
        elif file_type == "Imágenes":
            if not os.path.exists(DIRECTORIES['images']):
                st.error(f"❌ El directorio de imágenes no existe: {DIRECTORIES['images']}")
            else:
                st.info("No se encontraron archivos de imagen en el directorio")
    
    if file_type == "Audio" or file_type == "Todos":
        if files_dict['audio']:
            display_audio(files_dict['audio'])
            st.markdown("---")
        elif file_type == "Audio":
            if not os.path.exists(DIRECTORIES['audio']):
                st.error(f"❌ El directorio de audio no existe: {DIRECTORIES['audio']}")
            else:
                st.info("No se encontraron archivos de audio en el directorio")
    
    if file_type == "Video" or file_type == "Todos" :
        if files_dict['video']:
            display_video(files_dict['video'])
            st.markdown("---")
        elif file_type == "Video":
            if not os.path.exists(DIRECTORIES['video']):
                st.error(f"❌ El directorio de video no existe: {DIRECTORIES['video']}")
            else:
                st.info("No se encontraron archivos de video en el directorio")
    
    if file_type == "Otros":
        if files_dict['other']:
            display_other_files(files_dict['other'])
        else:
            if not os.path.exists(DIRECTORIES['other']):
                st.error(f"❌ El directorio de otros archivos no existe: {DIRECTORIES['other']}")
            else:
                st.info("No se encontraron otros tipos de archivos en el directorio")
    
    # Información adicional en el sidebar
    st.sidebar.markdown("---")
    st.sidebar.write("**Formatos soportados:**")
    st.sidebar.write("• **Imágenes:** JPG, PNG, GIF, BMP, WebP, SVG")
    st.sidebar.write("• **Audio:** MP3, WAV, OGG, M4A, AAC, FLAC")
    st.sidebar.write("• **Video:** MP4, AVI, MOV, WMV, FLV, WebM, MKV")
    
    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Función 'Quitar':** Los archivos se mueven a la carpeta 'anteriores' con sus metadatos, no se eliminan permanentemente.")
    
    # Herramientas adicionales
    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Herramientas")
    if st.sidebar.button("🔄 Actualizar archivos"):
        st.cache_data.clear()
        st.rerun()
    
    if st.sidebar.button("📋 Crear directorios faltantes"):
        created_dirs = []
        for file_type, directory_path in DIRECTORIES.items():
            if not os.path.exists(directory_path):
                try:
                    os.makedirs(directory_path, exist_ok=True)
                    created_dirs.append(directory_path)
                except Exception as e:
                    st.sidebar.error(f"Error creando {directory_path}: {str(e)}")
        
        # Crear directorio de metadatos también
        if not os.path.exists(METADATA_DIR):
            try:
                os.makedirs(METADATA_DIR, exist_ok=True)
                created_dirs.append(METADATA_DIR)
            except Exception as e:
                st.sidebar.error(f"Error creando directorio de metadatos: {str(e)}")
        
        # Crear directorio anteriores también
        if not os.path.exists(ANTERIORES_DIR):
            try:
                os.makedirs(ANTERIORES_DIR, exist_ok=True)
                created_dirs.append(ANTERIORES_DIR)
            except Exception as e:
                st.sidebar.error(f"Error creando directorio de anteriores: {str(e)}")
        
        if created_dirs:
            st.sidebar.success(f"Directorios creados: {len(created_dirs)}")
            for dir_path in created_dirs:
                st.sidebar.write(f"✅ {dir_path}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.info("Todos los directorios ya existen")
    
    # Función de búsqueda de metadatos
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Buscar en metadatos")
    search_term = st.sidebar.text_input("Buscar por título, descripción o tags:")
    
    if search_term:
        st.sidebar.write("**Resultados de búsqueda:**")
        search_results = search_metadata(search_term)
        if search_results:
            for result in search_results[:5]:  # Mostrar máximo 5 resultados
                st.sidebar.write(f"📄 **{result['filename']}** ({result['type']})")
                if result['metadata']['titulo']:
                    st.sidebar.write(f"   {result['metadata']['titulo']}")
        else:
            st.sidebar.write("No se encontraron resultados")

if __name__ == "__main__":
    main()