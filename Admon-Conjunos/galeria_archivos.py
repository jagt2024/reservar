import streamlit as st
import os
import json
from pathlib import Path
from PIL import Image, ExifTags
from datetime import datetime
import mimetypes
import pandas as pd

# Configuración de la página
#st.set_page_config(
#    page_title="Galería Multimedia",
#    page_icon="🎨",
#    layout="wide"
#)

# Directorios base
BASE_DIR = "../Admon-Conjunos/archivos_subidos"
DIRECTORIES = {
    "Imágenes": f"{BASE_DIR}/images",
    "Videos": f"{BASE_DIR}/videos", 
    "Audios": f"{BASE_DIR}/audios",
    "Documentos": f"{BASE_DIR}/documentos",
    "Otros": f"{BASE_DIR}/otros"
}

def get_file_metadata(file_path):
    """Extrae metadatos de un archivo"""
    try:
        file_stat = os.stat(file_path)
        metadata = {
            "nombre": os.path.basename(file_path),
            "tamaño": f"{file_stat.st_size / 1024:.1f} KB",
            "fecha_modificacion": datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": mimetypes.guess_type(file_path)[0] or "Desconocido"
        }
        
        # Metadatos específicos para imágenes
        if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            try:
                with Image.open(file_path) as img:
                    metadata["dimensiones"] = f"{img.width}x{img.height}"
                    
                    # Intentar extraer datos EXIF
                    exif = img._getexif()
                    if exif:
                        for tag, value in exif.items():
                            tag_name = ExifTags.TAGS.get(tag, tag)
                            if tag_name == "DateTime":
                                metadata["fecha_foto"] = value
                            elif tag_name == "Make":
                                metadata["camara_marca"] = value
                            elif tag_name == "Model":
                                metadata["camara_modelo"] = value
            except Exception:
                pass
                
        return metadata
    except Exception as e:
        return {"error": str(e)}

def load_custom_metadata(file_path):
    """Carga metadatos personalizados desde archivo JSON"""
    metadata_file = file_path.rsplit('.', 1)[0] + '_metadata.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_custom_metadata(file_path, metadata):
    """Guarda metadatos personalizados en archivo JSON"""
    metadata_file = file_path.rsplit('.', 1)[0] + '_metadata.json'
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def display_image_gallery(directory):
    """Muestra galería de imágenes"""
    if not os.path.exists(directory):
        st.warning(f"El directorio {directory} no existe")
        return
    
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    image_files = []
    
    for file in os.listdir(directory):
        if file.lower().endswith(image_extensions):
            image_files.append(os.path.join(directory, file))
    
    if not image_files:
        st.info("No se encontraron imágenes en este directorio")
        return
    
    # Mostrar imágenes en columnas
    cols = st.columns(3)
    
    for idx, image_path in enumerate(image_files):
        col = cols[idx % 3]
        
        with col:
            try:
                # Mostrar imagen
                image = Image.open(image_path)
                st.image(image, use_column_width=True)
                
                # Metadatos del archivo
                file_metadata = get_file_metadata(image_path)
                custom_metadata = load_custom_metadata(image_path)
                
                # Mostrar información
                st.write(f"**{file_metadata.get('nombre', 'N/A')}**")
                
                with st.expander("Ver metadatos"):
                    st.write(f"**Tamaño:** {file_metadata.get('tamaño', 'N/A')}")
                    st.write(f"**Dimensiones:** {file_metadata.get('dimensiones', 'N/A')}")
                    st.write(f"**Fecha:** {file_metadata.get('fecha_modificacion', 'N/A')}")
                    
                    # Metadatos personalizados
                    if custom_metadata:
                        st.write("**Metadatos personalizados:**")
                        if 'descripcion' in custom_metadata:
                            st.write(f"**Descripción:** {custom_metadata['descripcion']}")
                        if 'categoria' in custom_metadata:
                            st.write(f"**Categoría:** {custom_metadata['categoria']}")
                        if 'ubicacion' in custom_metadata:
                            st.write(f"**Ubicación:** {custom_metadata['ubicacion']}")
                
                # Editor de metadatos
                with st.expander("Editar metadatos"):
                    descripcion = st.text_area(
                        "Descripción", 
                        value=custom_metadata.get('descripcion', ''),
                        key=f"desc_{idx}"
                    )
                    categoria = st.text_input(
                        "Categoría",
                        value=custom_metadata.get('categoria', ''),
                        key=f"cat_{idx}"
                    )
                    ubicacion = st.text_input(
                        "Ubicación",
                        value=custom_metadata.get('ubicacion', ''),
                        key=f"ubi_{idx}"
                    )
                    
                    if st.button("Guardar metadatos", key=f"save_{idx}"):
                        new_metadata = {
                            'descripcion': descripcion,
                            'categoria': categoria,
                            'ubicacion': ubicacion,
                            'fecha_actualizacion': datetime.now().isoformat()
                        }
                        if save_custom_metadata(image_path, new_metadata):
                            st.success("Metadatos guardados")
                            st.rerun()
                        else:
                            st.error("Error al guardar metadatos")
                
            except Exception as e:
                st.error(f"Error al cargar imagen: {e}")

def display_video_gallery(directory):
    """Muestra galería de videos"""
    if not os.path.exists(directory):
        st.warning(f"El directorio {directory} no existe")
        return
    
    video_extensions = ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm')
    video_files = []
    
    for file in os.listdir(directory):
        if file.lower().endswith(video_extensions):
            video_files.append(os.path.join(directory, file))
    
    if not video_files:
        st.info("No se encontraron videos en este directorio")
        return
    
    for video_path in video_files:
        st.write("---")
        
        # Metadatos del archivo
        file_metadata = get_file_metadata(video_path)
        custom_metadata = load_custom_metadata(video_path)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**{file_metadata.get('nombre', 'N/A')}**")
            
            # Mostrar video
            try:
                st.video(video_path)
            except Exception as e:
                st.error(f"Error al cargar video: {e}")
        
        with col2:
            st.write("**Información del archivo:**")
            st.write(f"Tamaño: {file_metadata.get('tamaño', 'N/A')}")
            st.write(f"Fecha: {file_metadata.get('fecha_modificacion', 'N/A')}")
            
            # Metadatos personalizados
            if custom_metadata:
                st.write("**Metadatos personalizados:**")
                if 'descripcion' in custom_metadata:
                    st.write(f"**Descripción:** {custom_metadata['descripcion']}")
                if 'categoria' in custom_metadata:
                    st.write(f"**Categoría:** {custom_metadata['categoria']}")
                if 'ubicacion' in custom_metadata:
                    st.write(f"**Ubicación:** {custom_metadata['ubicacion']}")

def display_audio_gallery(directory):
    """Muestra galería de audios"""
    if not os.path.exists(directory):
        st.warning(f"El directorio {directory} no existe")
        return
    
    audio_extensions = ('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac')
    audio_files = []
    
    for file in os.listdir(directory):
        if file.lower().endswith(audio_extensions):
            audio_files.append(os.path.join(directory, file))
    
    if not audio_files:
        st.info("No se encontraron archivos de audio en este directorio")
        return
    
    for audio_path in audio_files:
        st.write("---")
        
        # Metadatos del archivo
        file_metadata = get_file_metadata(audio_path)
        custom_metadata = load_custom_metadata(audio_path)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**{file_metadata.get('nombre', 'N/A')}**")
            
            # Mostrar reproductor de audio
            try:
                st.audio(audio_path)
            except Exception as e:
                st.error(f"Error al cargar audio: {e}")
        
        with col2:
            st.write("**Información del archivo:**")
            st.write(f"Tamaño: {file_metadata.get('tamaño', 'N/A')}")
            st.write(f"Fecha: {file_metadata.get('fecha_modificacion', 'N/A')}")
            
            # Metadatos personalizados
            if custom_metadata:
                st.write("**Metadatos personalizados:**")
                if 'descripcion' in custom_metadata:
                    st.write(f"**Descripción:** {custom_metadata['descripcion']}")
                if 'categoria' in custom_metadata:
                    st.write(f"**Categoría:** {custom_metadata['categoria']}")
                if 'ubicacion' in custom_metadata:
                    st.write(f"**Ubicación:** {custom_metadata['ubicacion']}")

def display_other_files(directory):
    """Muestra otros tipos de archivos"""
    if not os.path.exists(directory):
        st.warning(f"El directorio {directory} no existe")
        return
    
    files = []
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if os.path.isfile(file_path):
            files.append(file_path)
    
    if not files:
        st.info("No se encontraron archivos en este directorio")
        return
    
    # Crear tabla con información de archivos
    file_data = []
    for file_path in files:
        file_metadata = get_file_metadata(file_path)
        custom_metadata = load_custom_metadata(file_path)
        
        file_data.append({
            'Nombre': file_metadata.get('nombre', 'N/A'),
            'Tipo': file_metadata.get('tipo', 'N/A'),
            'Tamaño': file_metadata.get('tamaño', 'N/A'),
            'Fecha': file_metadata.get('fecha_modificacion', 'N/A'),
            'Descripción': custom_metadata.get('descripcion', ''),
            'Categoría': custom_metadata.get('categoria', ''),
            'Ubicación': custom_metadata.get('ubicacion', '')
        })
    
    df = pd.DataFrame(file_data)
    st.dataframe(df, use_container_width=True)

# Interfaz principal
def galeria_main():
    st.title("🎨 Galería Multimedia")
    st.markdown("Explora tu colección de archivos multimedia organizados por categorías")
    
    # Crear pestañas
    tabs = st.tabs(list(DIRECTORIES.keys()))
    
    for idx, (tab_name, directory) in enumerate(DIRECTORIES.items()):
        with tabs[idx]:
            st.header(f"📁 {tab_name}")
            
            if tab_name == "Imágenes":
                display_image_gallery(directory)
            elif tab_name == "Videos":
                display_video_gallery(directory)
            elif tab_name == "Audios":
                display_audio_gallery(directory)
            else:
                display_other_files(directory)

if __name__ == "__main__":
    galeria_main()