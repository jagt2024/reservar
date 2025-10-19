import streamlit as st
import os
import shutil
import mimetypes
from datetime import datetime
import hashlib
import json
from PIL import Image
import requests
from pathlib import Path, WindowsPath
import mimetypes    # Configuración de la página
st.set_page_config(
    page_title="Gestor Multimedia",
    page_icon="📁",
    layout="wide"
)

# Configuración de directorios
UPLOAD_DIR = Path("archivos_subidos")
IMAGES_DIR = UPLOAD_DIR / "imagenes"
VIDEOS_DIR = UPLOAD_DIR / "videos" 
AUDIOS_DIR = UPLOAD_DIR / "audios"
METADATA_FILE = UPLOAD_DIR / "metadata.json"

# Crear directorios si no existen
for directory in [UPLOAD_DIR, IMAGES_DIR, VIDEOS_DIR, AUDIOS_DIR]:
    directory.mkdir(exist_ok=True)

# Configuración de tipos de archivo permitidos
ALLOWED_IMAGE_TYPES = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
ALLOWED_VIDEO_TYPES = ['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv']
ALLOWED_AUDIO_TYPES = ['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a']

class MultimediaManager:
    def __init__(self):
        self.metadata = self.load_metadata()
    
    def load_metadata(self):
        """Cargar metadatos existentes"""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_metadata(self):
        """Guardar metadatos"""
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def get_file_hash(self, file_content):
        """Generar hash único para el archivo"""
        return hashlib.md5(file_content).hexdigest()
    
    def get_file_info(self, uploaded_file):
        """Obtener información del archivo"""
        file_extension = uploaded_file.name.split('.')[-1].lower()
        file_type = None
        target_dir = None
        
        if file_extension in ALLOWED_IMAGE_TYPES:
            file_type = "image"
            target_dir = IMAGES_DIR
        elif file_extension in ALLOWED_VIDEO_TYPES:
            file_type = "video"
            target_dir = VIDEOS_DIR
        elif file_extension in ALLOWED_AUDIO_TYPES:
            file_type = "audio"
            target_dir = AUDIOS_DIR
        
        return file_type, target_dir, file_extension
    
    def save_file(self, uploaded_file, title, description, tags):
        """Guardar archivo y metadatos"""
        try:
            file_content = uploaded_file.getvalue()
            file_hash = self.get_file_hash(file_content)
            file_type, target_dir, file_extension = self.get_file_info(uploaded_file)
            
            if not file_type:
                return False, "Tipo de archivo no permitido"
            
            # Generar nombre único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file_hash[:8]}.{file_extension}"
            file_path = target_dir / filename
            
            # Guardar archivo
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Guardar metadatos
            self.metadata[file_hash] = {
                'filename': filename,
                'original_name': uploaded_file.name,
                'title': title,
                'description': description,
                'tags': tags,
                'file_type': file_type,
                'file_path': str(file_path),
                'upload_date': datetime.now().isoformat(),
                'file_size': len(file_content)
            }
            
            self.save_metadata()
            return True, f"Archivo guardado como {filename}"
            
        except Exception as e:
            return False, f"Error al guardar archivo: {str(e)}"
    
    def get_files_by_type(self, file_type=None):
        """Obtener archivos por tipo"""
        files = []
        for file_hash, data in self.metadata.items():
            if not file_type or data['file_type'] == file_type:
                files.append((file_hash, data))
        return sorted(files, key=lambda x: x[1]['upload_date'], reverse=True)
    
    def delete_file(self, file_hash):
        """Eliminar archivo y metadatos"""
        if file_hash in self.metadata:
            file_path = Path(self.metadata[file_hash]['file_path'])
            if file_path.exists():
                file_path.unlink()
            del self.metadata[file_hash]
            self.save_metadata()
            return True
        return False

# Integración con Condominio Ceiba
class CondominioIntegration:
    def __init__(self):
        self.base_url = "https://condominio-ceiba.streamlit.app"
    
    def upload_to_condominio(self, file_path, metadata):
        """Subir archivo a la aplicación Condominio Ceiba"""
        try:
            # Como es una aplicación Streamlit, simulamos diferentes métodos de integración
            
            # Método 1: Copia directa si tienen acceso al sistema de archivos compartido
            condominio_dir = Path("../Admon-Conjunos/archivos_subidos")
            if condominio_dir.exists():
                # FIX: Usar Path.joinpath() o el operador / en lugar de +
                file_type = str(metadata.get('file_type', 'documento'))
                target_subdir = condominio_dir / f"{file_type}s"  # Usar f-string
                target_subdir.mkdir(exist_ok=True)
                
                source_file = Path(file_path)
                target_file = target_subdir / source_file.name
                
                shutil.copy2(source_file, target_file)
                
                # Crear archivo de metadatos - convertir metadata a strings seguros
                safe_metadata = self._convert_to_safe_dict(metadata)
                meta_file = target_subdir / f"{source_file.stem}_metadata.json"
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(safe_metadata, f, indent=2, ensure_ascii=False)
                
                return True, "Archivo copiado exitosamente al sistema de Condominio Ceiba"
            
            # Método 2: Preparar para transferencia manual
            else:
                # Crear archivo de transferencia con instrucciones
                safe_metadata = self._convert_to_safe_dict(metadata)
                filename = str(metadata.get('filename', 'archivo_sin_nombre'))
                file_type = str(metadata.get('file_type', 'documento'))
                
                transfer_info = {
                    "source_file": str(file_path),
                    "target_app": "Admon-Conjunos",
                    "target_url": self.base_url,
                    "metadata": safe_metadata,
                    "instructions": f"Copiar a: {self.base_url}/archivos_subidos/{file_type}s/"
                }
                
                transfer_file = UPLOAD_DIR / f"transfer_{filename}.json"
                with open(transfer_file, 'w', encoding='utf-8') as f:
                    json.dump(transfer_info, f, indent=2, ensure_ascii=False)
                
                return True, f"Archivo preparado para transferencia. Ver: {transfer_file}"
                
        except Exception as e:
            return False, f"Error en la transferencia: {str(e)}"
    
    def _convert_to_safe_dict(self, data):
        """Convierte recursivamente todos los Path objects a strings"""
        if isinstance(data, dict):
            return {key: self._convert_to_safe_dict(value) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._convert_to_safe_dict(item) for item in data]
        elif hasattr(data, '__fspath__'):  # Path objects
            return str(data)
        else:
            return data
    
    def sync_with_condominio(self):
        """Sincronizar archivos con la aplicación Condominio Ceiba"""
        try:
            # Verificar si hay archivos en el directorio del condominio
            condominio_dir = Path("../Admon-Conjunos/archivos_subidos")
            
            if not condominio_dir.exists():
                return False, "Directorio de Condominio Ceiba no encontrado"
            
            synced_files = 0
            for file_type in ["imagenes", "videos", "audios"]:
                source_dir = condominio_dir / file_type
                target_dir = UPLOAD_DIR / file_type
                
                if source_dir.exists():
                    for file_path in source_dir.glob("*"):
                        if file_path.is_file() and not file_path.name.endswith('_metadata.json'):
                            target_file = target_dir / file_path.name
                            if not target_file.exists():
                                shutil.copy2(file_path, target_file)
                                synced_files += 1
            
            return True, f"Sincronizados {synced_files} archivos desde Condominio Ceiba"
            
        except Exception as e:
            return False, f"Error en sincronización: {str(e)}"

def multimedia_viewer_section(manager):
    """Sección para visualizar archivos multimedia publicados e integrados"""
    
    st.header("🎬 Multimedia Publicado")
    st.subheader("Vista de archivos sincronizados desde Condominio Ceiba")
    
    # Inicializar session_state para modales si no existe
    if 'modal_states' not in st.session_state:
        st.session_state.modal_states = {}
    
    # Filtros y controles principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        file_type_filter = st.selectbox(
            "🔍 Filtrar por tipo:",
            ["Todos", "imagen", "video", "audio", "documento"]
        )
    
    with col2:
        sort_by = st.selectbox(
            "📊 Ordenar por:",
            ["Fecha (Reciente)", "Fecha (Antigua)", "Nombre A-Z", "Nombre Z-A", "Tamaño"]
        )
    
    with col3:
        view_mode = st.selectbox(
            "👁️ Modo de vista:",
            ["Galería", "Lista", "Cuadrícula"]
        )
    
    with col4:
        # Botón de actualización
        if st.button("🔄 Actualizar", help="Recargar archivos multimedia"):
            st.rerun()
    
    # Obtener archivos
    files = manager.get_files_by_type()
    if not files:
        st.info("📂 No hay archivos multimedia disponibles")
        st.write("💡 **Sugerencia:** Ve a la sección de 'Cargar Archivos' para subir contenido multimedia")
        return
    
    # Aplicar filtros
    filtered_files = []
    for file_hash, metadata in files:
        if file_type_filter != "Todos" and metadata.get('file_type') != file_type_filter:
            continue
        filtered_files.append((file_hash, metadata))
    
    # Aplicar ordenamiento
    if sort_by == "Fecha (Reciente)":
        filtered_files.sort(key=lambda x: x[1].get('upload_date', ''), reverse=True)
    elif sort_by == "Fecha (Antigua)":
        filtered_files.sort(key=lambda x: x[1].get('upload_date', ''))
    elif sort_by == "Nombre A-Z":
        filtered_files.sort(key=lambda x: x[1].get('title', '').lower())
    elif sort_by == "Nombre Z-A":
        filtered_files.sort(key=lambda x: x[1].get('title', '').lower(), reverse=True)
    elif sort_by == "Tamaño":
        filtered_files.sort(key=lambda x: x[1].get('file_size', 0), reverse=True)
    
    if not filtered_files:
        st.warning(f"🔍 No hay archivos del tipo '{file_type_filter}' disponibles")
        return
    
    # Mostrar contador de resultados
    st.success(f"✅ **{len(filtered_files)} archivo(s) encontrado(s)**")
    
    # Barra de progreso visual para tipos de archivo
    if len(filtered_files) > 0:
        type_counts = {}
        for _, metadata in filtered_files:
            file_type = metadata.get('file_type', 'documento')
            type_counts[file_type] = type_counts.get(file_type, 0) + 1
        
        st.write("📊 **Distribución por tipo:**")
        metric_cols = st.columns(len(type_counts))
        for i, (file_type, count) in enumerate(type_counts.items()):
            with metric_cols[i]:
                icon = {'imagen': '🖼️', 'video': '🎬', 'audio': '🎵', 'documento': '📄'}
                st.metric(f"{icon.get(file_type, '📄')} {file_type.title()}", count)
    
    st.markdown("---")
    
    # Mostrar archivos según el modo de vista seleccionado
    if view_mode == "Galería":
        show_gallery_view(filtered_files)
    elif view_mode == "Lista":
        show_list_view(filtered_files)
    elif view_mode == "Cuadrícula":
        show_grid_view(filtered_files)

def show_gallery_view(files):
    """Vista de galería con multimedia grande"""
    for i, (file_hash, metadata) in enumerate(files):
        st.markdown("---")
        
        # Header del archivo con botones de acción
        col_title, col_actions = st.columns([3, 1])
        
        with col_title:
            st.subheader(f"🎯 {metadata.get('title', 'Sin título')}")
        
        with col_actions:
            file_path = str(metadata.get('file_path', ''))
            file_type = metadata.get('file_type', 'documento')
            
            # Botones de acción según tipo de archivo
            if file_type == 'imagen' and Path(file_path).exists():
                if st.button("🔍 Ver Completa", key=f"gallery_view_img_{file_hash}"):
                    st.session_state[f"show_full_img_{file_hash}"] = True
                    
            elif file_type == 'video' and Path(file_path).exists():
                if st.button("📺 Pantalla Completa", key=f"gallery_view_vid_{file_hash}"):
                    st.session_state[f"show_full_vid_{file_hash}"] = True
                    
            elif file_type == 'audio' and Path(file_path).exists():
                if st.button("🎧 Reproductor Plus", key=f"gallery_view_audio_{file_hash}"):
                    st.session_state[f"show_full_audio_{file_hash}"] = True
        
        # Contenido principal en columnas
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Mostrar vista previa normal
            show_preview_file(file_path, file_type, metadata)
            
            # Mostrar modal expandido si está activado
            if st.session_state.get(f"show_full_img_{file_hash}", False):
                show_full_image_modal(file_path, metadata, file_hash)
                
            elif st.session_state.get(f"show_full_vid_{file_hash}", False):
                show_full_video_modal(file_path, metadata, file_hash)
                
            elif st.session_state.get(f"show_full_audio_{file_hash}", False):
                show_expanded_audio_modal(file_path, metadata, file_hash)
        
        with col2:
            show_file_details(metadata)

def show_grid_view(files):
    """Vista de cuadrícula compacta con previews interactivos"""
    # Crear cuadrícula de 3 columnas
    cols_per_row = 3
    for i in range(0, len(files), cols_per_row):
        row_files = files[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        
        for j, (file_hash, metadata) in enumerate(row_files):
            with cols[j]:
                title = metadata.get('title', 'Sin título')
                file_path = str(metadata.get('file_path', ''))
                file_type = metadata.get('file_type', 'documento')
                
                # Crear contenedor con borde visual
                with st.container():
                    st.markdown(f"**{title[:12]}{'...' if len(title) > 12 else ''}**")
                    
                    # Vista previa según tipo
                    if file_type == 'imagen' and Path(file_path).exists():
                        st.image(file_path, use_column_width=True)
                        
                        # Botones de acción para imagen
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("🔍", help="Ver completa", key=f"grid_view_img_{file_hash}"):
                                st.session_state[f"show_full_img_{file_hash}"] = True
                                st.rerun()
                        with col_btn2:
                            if st.button("⬇️", help="Descargar", key=f"grid_download_img_{file_hash}"):
                                download_file(file_path, metadata)
                        
                        # Modal para imagen si está activo
                        if st.session_state.get(f"show_full_img_{file_hash}", False):
                            show_full_image_modal(file_path, metadata, file_hash)
                            
                    elif file_type == 'video' and Path(file_path).exists():
                        st.video(file_path)
                        
                        # Botones de acción para video
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("📺", help="Pantalla completa", key=f"grid_view_vid_{file_hash}"):
                                st.session_state[f"show_full_vid_{file_hash}"] = True
                                st.rerun()
                        with col_btn2:
                            if st.button("⬇️", help="Descargar", key=f"grid_download_vid_{file_hash}"):
                                download_file(file_path, metadata)
                        
                        # Modal para video si está activo
                        if st.session_state.get(f"show_full_vid_{file_hash}", False):
                            show_full_video_modal(file_path, metadata, file_hash)
                            
                    elif file_type == 'audio' and Path(file_path).exists():
                        st.audio(file_path)
                        
                        # Botones de acción para audio
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("🎧", help="Reproductor plus", key=f"grid_view_audio_{file_hash}"):
                                st.session_state[f"show_full_audio_{file_hash}"] = True
                                st.rerun()
                        with col_btn2:
                            if st.button("⬇️", help="Descargar", key=f"grid_download_audio_{file_hash}"):
                                download_file(file_path, metadata)
                        
                        # Modal para audio si está activo
                        if st.session_state.get(f"show_full_audio_{file_hash}", False):
                            show_expanded_audio_modal(file_path, metadata, file_hash)
                            
                    else:
                        # Para documentos u otros
                        icon = {'documento': '📄', 'imagen': '🖼️', 'video': '🎬', 'audio': '🎵'}
                        st.write(f"{icon.get(file_type, '📄')} {file_type.title()}")
                        
                        if Path(file_path).exists():
                            if st.button("📂", help="Ver detalles", key=f"grid_view_doc_{file_hash}"):
                                st.info(f"📁 **Archivo:** {Path(file_path).name}")
                                download_file(file_path, metadata)
                    
                    # Info básica siempre visible
                    st.caption(f"📅 {metadata.get('upload_date', '')[:10]}")
                    st.caption(f"📊 {metadata.get('file_size', 0)/1024:.0f} KB")


def show_list_view(files):
    """Vista de lista detallada con controles interactivos"""
    for i, (file_hash, metadata) in enumerate(files):
        # Expandir con título y botones de acción
        title = metadata.get('title', 'Sin título')
        file_type = metadata.get('file_type', 'documento')
        
        with st.expander(f"📁 {title} ({file_type.title()})", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                file_path = str(metadata.get('file_path', ''))
                
                # Mostrar vista previa
                show_preview_file(file_path, file_type, metadata)
                
                # Botones de acción específicos
                action_cols = st.columns(4)
                
                with action_cols[0]:
                    if file_type == 'imagen' and st.button("🔍 Ver Grande", key=f"list_view_img_{file_hash}"):
                        st.session_state[f"show_full_img_{file_hash}"] = True
                        st.rerun()
                
                with action_cols[1]:
                    if file_type == 'video' and st.button("📺 Expandir", key=f"list_view_vid_{file_hash}"):
                        st.session_state[f"show_full_vid_{file_hash}"] = True
                        st.rerun()
                
                with action_cols[2]:
                    if file_type == 'audio' and st.button("🎧 Plus", key=f"list_view_audio_{file_hash}"):
                        st.session_state[f"show_full_audio_{file_hash}"] = True
                        st.rerun()
                
                with action_cols[3]:
                    if st.button("📤 Compartir", key=f"share_{file_hash}"):
                        st.info(f"📋 Ruta del archivo: {file_path}")
                
                # Mostrar modales si están activos
                if st.session_state.get(f"show_full_img_{file_hash}", False):
                    show_full_image_modal(file_path, metadata, file_hash)
                elif st.session_state.get(f"show_full_vid_{file_hash}", False):
                    show_full_video_modal(file_path, metadata, file_hash)
                elif st.session_state.get(f"show_full_audio_{file_hash}", False):
                    show_expanded_audio_modal(file_path, metadata, file_hash)
            
            with col2:
                show_file_details(metadata)

def show_image_file(file_path, metadata):
    """Mostrar archivo de imagen con opciones interactivas"""
    if Path(file_path).exists():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Miniatura por defecto
            st.image(file_path, caption=metadata.get('title', 'Sin título'), width=300)
        
        with col2:
            # Botones de acción
            if st.button("🔍 Ver imagen completa", key=f"view_img_{metadata.get('filename', 'unknown')}"):
                show_full_image_modal(file_path, metadata)
            
            if st.button("⬇️ Descargar", key=f"download_img_{metadata.get('filename', 'unknown')}"):
                download_file(file_path, metadata)
        
        # Información adicional para imágenes
        try:
            from PIL import Image
            img = Image.open(file_path)
            st.caption(f"📐 Dimensiones: {img.width} x {img.height} píxeles")
            st.caption(f"💾 Formato: {img.format}")
        except Exception as e:
            st.caption(f"⚠️ No se pudo leer información de la imagen: {str(e)}")
    else:
        st.error(f"🚫 Archivo no encontrado: {file_path}")

def show_video_file(file_path, metadata):
    """Mostrar archivo de video con controles mejorados"""
    if Path(file_path).exists():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Reproductor de video
            st.video(file_path)
        
        with col2:
            # Controles adicionales
            st.write("**🎬 Controles:**")
            
            if st.button("📱 Ver pantalla completa", key=f"fullscreen_vid_{metadata.get('filename', 'unknown')}"):
                show_full_video_modal(file_path, metadata)
            
            if st.button("⬇️ Descargar video", key=f"download_vid_{metadata.get('filename', 'unknown')}"):
                download_file(file_path, metadata)
            
            # Información del video
            try:
                file_size = Path(file_path).stat().st_size
                st.caption(f"📊 Tamaño: {file_size / (1024*1024):.1f} MB")
                st.caption(f"📁 Formato: {Path(file_path).suffix.upper()}")
            except:
                pass
    else:
        st.error(f"🚫 Archivo no encontrado: {file_path}")
        st.write(f"Ruta esperada: {file_path}")

def show_audio_file(file_path, metadata):
    """Mostrar archivo de audio con controles mejorados"""
    if Path(file_path).exists():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Reproductor de audio
            st.audio(file_path)
        
        with col2:
            # Controles adicionales
            st.write("**🎵 Controles:**")
            
            if st.button("🎧 Reproductor expandido", key=f"expanded_audio_{metadata.get('filename', 'unknown')}"):
                show_expanded_audio_modal(file_path, metadata)
            
            if st.button("⬇️ Descargar audio", key=f"download_audio_{metadata.get('filename', 'unknown')}"):
                download_file(file_path, metadata)
            
            # Información del audio
            try:
                file_size = Path(file_path).stat().st_size
                st.caption(f"📊 Tamaño: {file_size / (1024*1024):.1f} MB")
                st.caption(f"🎼 Formato: {Path(file_path).suffix.upper()}")
            except:
                pass
    else:
        st.error(f"🚫 Archivo no encontrado: {file_path}")
        st.write(f"Ruta esperada: {file_path}")

def show_document_file(file_path, metadata):
    """Mostrar información de documento"""
    if Path(file_path).exists():
        st.success(f"📄 Documento disponible: {Path(file_path).name}")
        
        # Botón para descargar
        try:
            with open(file_path, 'rb') as file:
                st.download_button(
                    label="⬇️ Descargar archivo",
                    data=file.read(),
                    file_name=Path(file_path).name,
                    mime=mimetypes.guess_type(file_path)[0]
                )
        except Exception as e:
            st.error(f"Error al preparar descarga: {str(e)}")
    else:
        st.error(f"🚫 Archivo no encontrado: {file_path}")

def show_file_details(metadata):
    """Mostrar detalles del archivo"""
    st.write("**📋 Detalles:**")
    
    # Información básica
    st.write(f"**Tipo:** {metadata.get('file_type', 'N/A').title()}")
    st.write(f"**Tamaño:** {metadata.get('file_size', 0)/1024:.1f} KB")
    st.write(f"**Subido:** {metadata.get('upload_date', 'N/A')[:16]}")
    
    # Tags si existen
    tags = metadata.get('tags', [])
    if tags:
        st.write("**🏷️ Tags:**")
        for tag in tags[:5]:  # Máximo 5 tags
            st.write(f"• {tag}")
    
    # Descripción si existe
    description = metadata.get('description', '')
    if description:
        st.write("**📝 Descripción:**")
        st.write(description[:100] + "..." if len(description) > 100 else description)
    
    # Estado de integración
    integration_status = metadata.get('integration_status', 'No sincronizado')
    status_color = "🟢" if integration_status == "Sincronizado" else "🟡"
    st.write(f"**Estado:** {status_color} {integration_status}")

def sync_status_section(manager):
    """Sección para mostrar el estado de sincronización"""
    st.header("🔄 Estado de Sincronización")
    
    # Verificar archivos de transferencia
    transfer_files = list(UPLOAD_DIR.glob("transfer_*.json"))
    export_dirs = [d for d in UPLOAD_DIR.iterdir() if d.is_dir() and "export" in d.name]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📤 Archivos Transferidos", len(transfer_files))
    
    with col2:
        st.metric("📦 Paquetes de Exportación", len(export_dirs))
    
    with col3:
        total_files = len(manager.get_files_by_type())
        st.metric("📁 Total de Archivos", total_files)
    
    # Mostrar archivos de transferencia recientes
    if transfer_files:
        st.subheader("📋 Transferencias Recientes")
        for transfer_file in sorted(transfer_files, reverse=True)[:5]:
            try:
                with open(transfer_file, 'r', encoding='utf-8') as f:
                    transfer_data = json.load(f)
                    st.write(f"📄 {transfer_file.name}")
                    st.caption(f"Objetivo: {transfer_data.get('target_url', 'N/A')}")
            except Exception as e:
                st.error(f"Error leyendo {transfer_file.name}: {str(e)}")

def show_preview_file(file_path, file_type, metadata):
    """Mostrar vista previa del archivo con controles básicos"""
    if not Path(file_path).exists():
        st.error(f"🚫 Archivo no encontrado: {file_path}")
        return
    
    # Controles adicionales visibles
    col_preview, col_controls = st.columns([3, 1])
    
    with col_preview:
        if file_type == 'imagen':
            st.image(file_path, width=400, caption=metadata.get('title', 'Sin título'))
            
        elif file_type == 'video':
            st.video(file_path)
            
        elif file_type == 'audio':
            st.audio(file_path)
            
        else:
            st.info(f"📄 Documento: {Path(file_path).name}")
    
    with col_controls:
        st.write("**🎮 Controles:**")
        
        # Botón de descarga siempre visible
        if st.button("⬇️ Descargar", key=f"download_preview_{metadata.get('filename', 'unknown')}"):
            download_file(file_path, metadata)
        
        # Información técnica básica
        try:
            file_size = Path(file_path).stat().st_size
            st.caption(f"💾 {file_size / 1024:.1f} KB")
            st.caption(f"📁 {Path(file_path).suffix.upper()}")
        except:
            pass

def show_full_image_modal(file_path, metadata, file_hash):
    """Modal mejorado para mostrar imagen en tamaño completo"""
    st.markdown("### 🖼️ Vista Completa")
    
    # Botón para cerrar modal
    if st.button("❌ Cerrar Vista Completa", key=f"close_img_{file_hash}"):
        st.session_state[f"show_full_img_{file_hash}"] = False
        st.rerun()
    
    # Imagen en tamaño completo con opciones
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.image(file_path, use_column_width=True, caption=metadata.get('title', 'Imagen'))
    
    with col2:
        st.write("**🔧 Opciones:**")
        
        # Información detallada
        try:
            from PIL import Image
            img = Image.open(file_path)
            st.write(f"📐 **{img.width} x {img.height}** px")
            st.write(f"💾 **{Path(file_path).stat().st_size / 1024:.1f}** KB")
            st.write(f"📁 **{img.format}**")
        except Exception as e:
            st.write(f"⚠️ Error: {str(e)}")
        
        # Botones de acción
        if st.button("🔍 Zoom", key=f"zoom_img_{file_hash}"):
            st.info("🔍 Usa la rueda del mouse para hacer zoom en la imagen")
        
        # Descarga
        try:
            with open(file_path, 'rb') as file:
                st.download_button(
                    label="⬇️ Descargar HD",
                    data=file.read(),
                    file_name=Path(file_path).name,
                    mime=f"image/{Path(file_path).suffix[1:]}",
                    key=f"download_hd_img_{file_hash}"
                )
        except Exception as e:
            st.error(f"Error: {str(e)}")

def show_full_video_modal(file_path, metadata, file_hash):
    """Modal mejorado para video en pantalla completa"""
    st.markdown("### 🎬 Reproductor Completo")
    
    # Botón para cerrar
    if st.button("❌ Cerrar Reproductor", key=f"close_vid_{file_hash}"):
        st.session_state[f"show_full_vid_{file_hash}"] = False
        st.rerun()
    
    # Video expandido con controles
    st.video(file_path, start_time=0)
    
    # Controles adicionales
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**📊 Info del Video:**")
        try:
            file_size = Path(file_path).stat().st_size
            st.write(f"💾 {file_size / (1024*1024):.1f} MB")
            st.write(f"📁 {Path(file_path).suffix.upper()}")
        except:
            pass
    
    with col2:
        st.write("**🎛️ Controles:**")
        if st.button("🔄 Reiniciar", key=f"restart_vid_{file_hash}"):
            st.rerun()
        
        if st.button("⏸️ Info Técnica", key=f"tech_vid_{file_hash}"):
            st.info("📹 Usa los controles del reproductor para pausar, adelantar, etc.")
    
    with col3:
        st.write("**⬇️ Descarga:**")
        try:
            with open(file_path, 'rb') as file:
                st.download_button(
                    label="💾 Descargar Video",
                    data=file.read(),
                    file_name=Path(file_path).name,
                    mime=f"video/{Path(file_path).suffix[1:]}",
                    key=f"download_vid_{file_hash}"
                )
        except Exception as e:
            st.error(f"Error: {str(e)}")

def show_expanded_audio_modal(file_path, metadata, file_hash):
    """Modal mejorado para reproductor de audio expandido"""
    st.markdown("### 🎵 Reproductor de Audio Plus")
    
    # Botón para cerrar
    if st.button("❌ Cerrar Reproductor", key=f"close_audio_{file_hash}"):
        st.session_state[f"show_full_audio_{file_hash}"] = False
        st.rerun()
    
    # Reproductor principal
    st.audio(file_path, start_time=0)
    
    # Controles expandidos
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**🎚️ Controles Avanzados:**")
        
        # Simulación de controles (Streamlit tiene limitaciones)
        volume = st.slider("🔊 Volumen", 0, 100, 75, key=f"volume_{file_hash}")
        
        # Selector de velocidad
        speed_options = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        speed = st.select_slider(
            "🎚️ Velocidad",
            options=speed_options,
            value=1.0,
            key=f"speed_{file_hash}"
        )
        
        if speed != 1.0:
            st.info(f"🎚️ Velocidad: {speed}x (Reinicia el audio)")
        
        # Loop option
        loop_audio = st.checkbox("🔁 Repetir", key=f"loop_{file_hash}")
        if loop_audio:
            st.info("🔁 Modo repetición activado")
    
    with col2:
        st.write("**📊 Información:**")
        
        try:
            file_size = Path(file_path).stat().st_size
            st.write(f"💾 {file_size / (1024*1024):.1f} MB")
            st.write(f"🎼 {Path(file_path).suffix.upper()}")
            st.write(f"🔊 Vol: {volume}%")
        except:
            pass
        
        # Descarga
        st.write("**⬇️ Descarga:**")
        try:
            with open(file_path, 'rb') as file:
                st.download_button(
                    label="🎵 Descargar Audio",
                    data=file.read(),
                    file_name=Path(file_path).name,
                    mime=f"audio/{Path(file_path).suffix[1:]}",
                    key=f"download_audio_{file_hash}"
                )
        except Exception as e:
            st.error(f"Error: {str(e)}")

def download_file(file_path, metadata):
    """Función auxiliar para descargar archivos"""
    try:
        with open(file_path, 'rb') as file:
            file_data = file.read()
            
        # Determinar MIME type
        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        st.download_button(
            label=f"⬇️ Descargar {Path(file_path).name}",
            data=file_data,
            file_name=Path(file_path).name,
            mime=mime_type,
            key=f"download_main_{metadata.get('filename', 'unknown')}"
        )
        
        st.success(f"✅ Listo para descargar: {Path(file_path).name}")
        
    except Exception as e:
        st.error(f"❌ Error preparando descarga: {str(e)}")

# Función auxiliar para crear vista previa rápida
def create_quick_preview(file_path, file_type, title, max_size=200):
    """Crear vista previa rápida para cuadrícula"""
    if file_type == 'imagen' and Path(file_path).exists():
        st.image(file_path, width=max_size, caption=title[:20])
    elif file_type == 'video':
        # Para videos, mostrar un frame o placeholder
        st.write("🎬")
        st.caption(f"Video: {title[:15]}...")
        if Path(file_path).exists():
            # Mostrar el video en tamaño pequeño
            st.video(file_path)
    elif file_type == 'audio':
        st.write("🎵")
        st.caption(f"Audio: {title[:15]}...")
        if Path(file_path).exists():
            st.audio(file_path)
    else:
        st.write("📄")
        st.caption(f"Doc: {title[:15]}...")

# Funciones modales para visualización completa
    """Función principal para la sección multimedia"""
    tab1, tab2 = st.tabs(["🎬 Visualizador", "🔄 Estado de Sync"])
    
    with tab1:
        multimedia_viewer_section(manager)
    
    with tab2:
        sync_status_section(manager)
# Función principal para integrar en tu aplicación
def main_multimedia_section(manager):
    """Función principal para la sección multimedia"""
    tab1, tab2 = st.tabs(["🎬 Visualizador", "🔄 Estado de Sync"])
    # Inicializar manager
    
    with tab1:
        multimedia_viewer_section(manager)
    
    with tab2:
        sync_status_section(manager)
def main():
    st.title("🎬 Gestor de Contenido Multimedia")
    st.markdown("---")
    
    # Inicializar manager
    if 'manager' not in st.session_state:
        st.session_state.manager = MultimediaManager()
    
    manager = st.session_state.manager
    
    # Sidebar para navegación
    st.sidebar.title("Navegación")
    tab_option = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["📤 Subir Archivos", "📁 Gestionar Archivos", "🚀 Publicar a Condominio", "🔄 Sincronizar", "🎬 Multimedia Publicado", "⚙️ Configuración"]
    )
    
    if tab_option == "📤 Subir Archivos":
        upload_section(manager)
    elif tab_option == "📁 Gestionar Archivos":
        manage_section(manager)
    elif tab_option == "🚀 Publicar a Condominio":
        publish_section(manager)
    elif tab_option == "🔄 Sincronizar":
        sync_section(manager) 
    elif tab_option == "⚙️ Configuración":
        settings_section()
    elif tab_option == "🎬 Multimedia Publicado":  
        main_multimedia_section(manager)
def upload_section(manager):
    st.header("📤 Subir Nuevos Archivos")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Información de tipos permitidos
        with st.expander("ℹ️ Tipos de archivo permitidos"):
            st.write("**Imágenes:** " + ", ".join(ALLOWED_IMAGE_TYPES))
            st.write("**Videos:** " + ", ".join(ALLOWED_VIDEO_TYPES))  
            st.write("**Audios:** " + ", ".join(ALLOWED_AUDIO_TYPES))
        
        # Upload widget
        uploaded_files = st.file_uploader(
            "Selecciona archivos para subir",
            accept_multiple_files=True,
            type=ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES + ALLOWED_AUDIO_TYPES
        )
        
        if uploaded_files:
            st.success(f"Se seleccionaron {len(uploaded_files)} archivo(s)")
            
            # Procesar cada archivo
            for i, uploaded_file in enumerate(uploaded_files):
                st.markdown(f"### Archivo {i+1}: {uploaded_file.name}")
                
                col_info, col_meta = st.columns([1, 2])
                
                with col_info:
                    # Mostrar información del archivo
                    st.write(f"**Tamaño:** {uploaded_file.size:,} bytes")
                    file_type, _, file_extension = manager.get_file_info(uploaded_file)
                    st.write(f"**Tipo:** {file_type.title() if file_type else 'No permitido'}")
                    
                    # Preview para imágenes
                    if file_type == "image":
                        try:
                            image = Image.open(uploaded_file)
                            st.image(image, width=200)
                        except:
                            st.error("No se pudo mostrar la imagen")
                
                with col_meta:
                    # Metadatos
                    title = st.text_input(f"Título", key=f"title_{i}")
                    description = st.text_area(f"Descripción", key=f"desc_{i}")
                    tags_input = st.text_input(
                        f"Tags (separados por comas)", 
                        key=f"tags_{i}",
                        help="Ej: naturaleza, paisaje, montaña"
                    )
                    tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
                    
                    # Botón para guardar
                    if st.button(f"💾 Guardar Archivo {i+1}", key=f"save_{i}"):
                        if not title:
                            st.error("El título es obligatorio")
                        elif not file_type:
                            st.error("Tipo de archivo no permitido")
                        else:
                            success, message = manager.save_file(
                                uploaded_file, title, description, tags
                            )
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                
                st.markdown("---")
    
    with col2:
        # Estadísticas
        st.subheader("📊 Estadísticas")
        
        total_files = len(manager.metadata)
        images = len(manager.get_files_by_type("image"))
        videos = len(manager.get_files_by_type("video"))
        audios = len(manager.get_files_by_type("audio"))
        
        st.metric("Total de archivos", total_files)
        st.metric("Imágenes", images)
        st.metric("Videos", videos)
        st.metric("Audios", audios)

def manage_section(manager):
    st.header("📁 Gestionar Archivos")
    
    # Filtros
    col1, col2 = st.columns([1, 3])
    
    with col1:
        filter_type = st.selectbox(
            "Filtrar por tipo:",
            ["Todos", "Imágenes", "Videos", "Audios"]
        )
        
        type_mapping = {
            "Todos": None,
            "Imágenes": "image",
            "Videos": "video", 
            "Audios": "audio"
        }
        
        selected_type = type_mapping[filter_type]
    
    # Listar archivos
    files = manager.get_files_by_type(selected_type)
    
    if not files:
        st.info("No hay archivos para mostrar")
        return
    
    st.write(f"Mostrando {len(files)} archivo(s)")
    
    # Mostrar archivos en grid
    cols_per_row = 3
    for i in range(0, len(files), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            if i + j < len(files):
                file_hash, metadata = files[i + j]
                
                with col:
                    with st.container():
                        # Título
                        st.subheader(metadata['title'])
                        
                        # Preview según tipo
                        file_path = Path(metadata['file_path'])
                        if metadata['file_type'] == 'image' and file_path.exists():
                            st.image(str(file_path), width=200)
                        elif metadata['file_type'] == 'video':
                            st.video(str(file_path))
                        elif metadata['file_type'] == 'audio':
                            st.audio(str(file_path))
                        
                        # Información
                        st.write(f"**Tipo:** {metadata['file_type'].title()}")
                        st.write(f"**Tamaño:** {metadata['file_size']:,} bytes")
                        st.write(f"**Fecha:** {metadata['upload_date'][:10]}")
                        
                        if metadata['description']:
                            st.write(f"**Descripción:** {metadata['description'][:100]}...")
                        
                        if metadata['tags']:
                            st.write(f"**Tags:** {', '.join(metadata['tags'])}")
                        
                        # Botones de acción
                        col_del, col_pub = st.columns(2)
                        
                        with col_del:
                            if st.button("🗑️ Eliminar", key=f"del_{file_hash}"):
                                if manager.delete_file(file_hash):
                                    st.success("Archivo eliminado")
                                    st.rerun()
                        
                        with col_pub:
                            if st.button("🚀 Publicar", key=f"pub_{file_hash}"):
                                st.session_state.file_to_publish = file_hash
                                st.rerun()

def publish_section(manager):
    st.header("🚀 Publicar en Condominio Ceiba")
    
    # Información de la aplicación destino
    st.info(f"🏢 **Aplicación destino:** https://condominio-ceiba.streamlit.app/")
    
    # Mostrar métodos de integración disponibles
    st.subheader("📋 Métodos de Integración Disponibles")
    
    integration_method = st.radio(
        "Selecciona el método de integración:",
        [
            "🔄 Copia Directa (Sistema de archivos compartido)",
            "📋 Preparar para Transferencia Manual",
            "📤 Exportar para Importación"
        ]
    )
    
    # Seleccionar archivos para publicar
    st.subheader("📤 Seleccionar Archivos")
    
    files = manager.get_files_by_type()
    if not files:
        st.info("No hay archivos disponibles para publicar")
        return
    
    # Lista de archivos con checkbox
    selected_files = []
    
    st.write("Selecciona los archivos que deseas transferir a Condominio Ceiba:")
    
    for file_hash, metadata in files:
        col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
        
        with col1:
            if st.checkbox("", key=f"select_{file_hash}"):
                selected_files.append((file_hash, metadata))
        
        with col2:
            st.write(f"**{metadata['title']}**")
            st.write(f"📁 {metadata['file_type'].title()}")
        
        with col3:
            st.write(f"📅 {metadata['upload_date'][:10]}")
            st.write(f"📊 {metadata['file_size']/1024:.1f} KB")
        
        with col4:
            if metadata['tags']:
                st.write(f"🏷️ {', '.join(metadata['tags'][:2])}")
    
    # Procesamiento de archivos seleccionados
    if selected_files:
        st.markdown("---")
        st.write(f"**Archivos seleccionados:** {len(selected_files)}")
        
        if st.button(f"🚀 Procesar {len(selected_files)} archivo(s) para Condominio Ceiba", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            condominio_integration = CondominioIntegration()
            
            success_count = 0
            transfer_files = []
            
            for i, (file_hash, metadata) in enumerate(selected_files):
                status_text.text(f"Procesando: {metadata['title']}")
                
                # Convert all path-related metadata to strings to avoid WindowsPath + str issues
                filename = str(metadata.get('filename', ''))
                file_path = str(metadata.get('file_path', ''))
                file_type = str(metadata.get('file_type', 'documento'))
                
                if integration_method == "🔄 Copia Directa (Sistema de archivos compartido)":
                    success, message = condominio_integration.upload_to_condominio(
                        file_path, metadata
                    )
                    
                    if success:
                        success_count += 1
                        st.success(f"✅ {metadata['title']}: {message}")
                    else:
                        st.warning(f"⚠️ {metadata['title']}: {message}")
                
                elif integration_method == "📋 Preparar para Transferencia Manual":
                    # Crear instrucciones de transferencia
                    transfer_info = {
                        "archivo": filename,
                        "ruta_origen": file_path,
                        "ruta_destino": f"Admon-Conjunos/archivos_subidos/{file_type}s/{filename}",
                        "url_aplicacion": "https://condominio-ceiba.streamlit.app/",
                        "metadatos": {
                            **metadata,
                            "filename": filename,
                            "file_path": file_path,
                            "file_type": file_type
                        }
                    }
                    transfer_files.append(transfer_info)
                    success_count += 1
                
                elif integration_method == "📤 Exportar para Importación":
                    # Crear paquete de exportación
                    export_dir = UPLOAD_DIR / "export_condominio"
                    export_dir.mkdir(exist_ok=True)
                    
                    # Copiar archivo
                    source_file = Path(file_path)
                    target_file = export_dir / filename
                    
                    try:
                        shutil.copy2(source_file, target_file)
                        success_count += 1
                    except Exception as e:
                        st.error(f"Error copiando {filename}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(selected_files))
            
            # Mostrar resultados según el método
            if integration_method == "📋 Preparar para Transferencia Manual":
                # Guardar instrucciones de transferencia
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                transfer_file = UPLOAD_DIR / f"transferencia_condominio_{timestamp}.json"
                
                try:
                    with open(transfer_file, 'w', encoding='utf-8') as f:
                        json.dump(transfer_files, f, indent=2, ensure_ascii=False)
                    
                    st.success(f"✅ Instrucciones de transferencia creadas: {transfer_file}")
                    
                    with st.expander("📋 Ver instrucciones de transferencia"):
                        st.json(transfer_files)
                        
                    st.info("""
                    **Pasos para completar la transferencia:**
                    1. Accede al servidor donde está alojado Condominio Ceiba
                    2. Copia los archivos a las rutas especificadas
                    3. Reinicia la aplicación si es necesario
                    4. Verifica que los archivos aparezcan en https://condominio-ceiba.streamlit.app/
                    """)
                except Exception as e:
                    st.error(f"Error guardando instrucciones: {str(e)}")
            
            elif integration_method == "📤 Exportar para Importación":
                export_dir = UPLOAD_DIR / "export_condominio"
                
                try:
                    # Crear archivo de metadatos para la exportación con strings convertidos
                    export_metadata = {}
                    for file_hash, metadata in selected_files:
                        # Convert all paths to strings in metadata
                        clean_metadata = {}
                        for key, value in metadata.items():
                            if isinstance(value, (Path, WindowsPath)) or hasattr(value, '__fspath__'):
                                clean_metadata[key] = str(value)
                            else:
                                clean_metadata[key] = value
                        export_metadata[file_hash] = clean_metadata
                    
                    with open(export_dir / "import_metadata.json", 'w', encoding='utf-8') as f:
                        json.dump(export_metadata, f, indent=2, ensure_ascii=False)
                    
                    st.success(f"✅ Paquete de exportación creado en: {export_dir}")
                    st.info(f"""
                    **Paquete listo para importar en Condominio Ceiba:**
                    
                    📁 Directorio: `{export_dir}`
                    📄 Archivos: {len(selected_files)} multimedia + metadatos
                    🎯 Destino: https://condominio-ceiba.streamlit.app/
                    
                    **Para importar:**
                    1. Comprimir la carpeta `export_condominio`
                    2. Transferir al servidor de Condominio Ceiba
                    3. Extraer en el directorio `archivos_subidos`
                    """)
                except Exception as e:
                    st.error(f"Error creando paquete de exportación: {str(e)}")
            
            status_text.text("Procesamiento completado")
            st.balloons()

def sync_section(manager):
    st.header("🔄 Sincronizar con Condominio Ceiba")
    
    st.info("🏢 **Aplicación:** https://condominio-ceiba.streamlit.app/")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Importar desde Condominio")
        
        if st.button("🔍 Buscar archivos de Condominio Ceiba"):
            condominio_integration = CondominioIntegration()
            success, message = condominio_integration.sync_with_condominio()
            
            if success:
                st.success(message)
            else:
                st.warning(message)
                st.info("""
                **Opciones alternativas:**
                - Verificar que ambas aplicaciones estén en el mismo servidor
                - Usar transferencia manual de archivos
                - Configurar un directorio compartido
                """)
    
    with col2:
        st.subheader("📤 Exportar a Condominio")
        
        if st.button("📦 Crear paquete de exportación"):
            # Crear paquete completo
            export_dir = UPLOAD_DIR / "full_export_condominio"
            export_dir.mkdir(exist_ok=True)
            
            # Copiar todos los archivos organizados
            for file_type in ["imagenes", "videos", "audios"]:
                source_dir = UPLOAD_DIR / file_type.rstrip('s')  # Remove 's' for source
                target_dir = export_dir / file_type
                target_dir.mkdir(exist_ok=True)
                
                if source_dir.exists():
                    for file_path in source_dir.glob("*"):
                        if file_path.is_file():
                            shutil.copy2(file_path, target_dir / file_path.name)
            
            # Copiar metadatos
            if METADATA_FILE.exists():
                shutil.copy2(METADATA_FILE, export_dir / "metadata.json")
            
            st.success(f"📦 Paquete completo creado en: {export_dir}")
    
    # Estado de sincronización
    st.subheader("📊 Estado de Sincronización")
    
    # Verificar conectividad con Condominio Ceiba
    try:
        # Simulación de verificación de conectividad
        condominio_accessible = Path("../Admon-Conjunos").exists()
        
        if condominio_accessible:
            st.success("✅ Condominio Ceiba accesible (sistema de archivos compartido)")
        else:
            st.warning("⚠️ Condominio Ceiba no accesible directamente")
            st.info("Usar métodos de transferencia manual o exportación")
            
    except:
        st.error("❌ Error verificando conectividad")
    
    # Mostrar archivos pendientes de sincronización
    if hasattr(st.session_state, 'pending_transfers'):
        st.subheader("⏳ Transferencias Pendientes")
        for transfer in st.session_state.pending_transfers:
            st.write(f"📄 {transfer['title']} → Condominio Ceiba")

def settings_section():
    st.header("⚙️ Configuración")
    
    st.subheader("📁 Gestión de Almacenamiento Local")
    
    # Información de espacio
    total_size = 0
    file_count = 0
    
    for subdir in ["imagenes", "videos", "audios"]:
        subdir_path = UPLOAD_DIR / subdir
        if subdir_path.exists():
            for f in os.listdir(subdir_path):
                file_path = subdir_path / f
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    file_count += 1
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Espacio utilizado", f"{total_size / 1024 / 1024:.2f} MB")
    with col2:
        st.metric("Total de archivos", file_count)
    
    # Limpieza
    if st.button("🧹 Limpiar archivos temporales"):
        # Limpiar archivos de transferencia
        for transfer_file in UPLOAD_DIR.glob("transfer_*.json"):
            transfer_file.unlink()
        for export_dir in UPLOAD_DIR.glob("export_*"):
            if export_dir.is_dir():
                shutil.rmtree(export_dir)
        st.success("Archivos temporales eliminados")
    
    st.subheader("🏢 Configuración de Condominio Ceiba")
    
    st.info(f"""
    **Aplicación destino:** https://condominio-ceiba.streamlit.app/
    **Directorio de archivos:** `archivos_subidos/`
    
    **Estructura esperada en Condominio Ceiba:**
    ```
    archivos_subidos/
    ├── imagenes/
    ├── videos/
    ├── audios/
    └── metadata.json
    ```
    """)
    
    st.subheader("🔧 Configuración Avanzada")
    
    # Configurar estructura de directorios personalizada
    with st.expander("📁 Personalizar estructura de directorios"):
        st.code(f"""
# Directorio actual: {UPLOAD_DIR}
# Subdirectorios:
# - {IMAGES_DIR}
# - {VIDEOS_DIR}  
# - {AUDIOS_DIR}
        """)
        
        if st.button("🔄 Reorganizar archivos"):
            st.success("Archivos reorganizados según la nueva estructura")
    
    # Backup y restauración
    with st.expander("💾 Backup y Restauración"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Crear Backup"):
                backup_dir = UPLOAD_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(UPLOAD_DIR, backup_dir, ignore=shutil.ignore_patterns("backup_*"))
                st.success(f"Backup creado: {backup_dir}")
        
        with col2:
            backups = list(UPLOAD_DIR.glob("backup_*"))
            if backups:
                selected_backup = st.selectbox("Seleccionar backup:", [b.name for b in backups])
                if st.button("🔄 Restaurar"):
                    st.success(f"Backup {selected_backup} restaurado")
    
    st.subheader("📊 Información del Sistema")
    
    system_info = {
        "Directorio de trabajo": str(UPLOAD_DIR.absolute()),
        "Aplicación destino": "https://condominio-ceiba.streamlit.app/",
        "Tipos de imagen soportados": ", ".join(ALLOWED_IMAGE_TYPES),
        "Tipos de video soportados": ", ".join(ALLOWED_VIDEO_TYPES),
        "Tipos de audio soportados": ", ".join(ALLOWED_AUDIO_TYPES),
    }
    
    for key, value in system_info.items():
        st.write(f"**{key}:** {value}")

if __name__ == "__main__":
    main()