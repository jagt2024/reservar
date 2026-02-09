import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

class LegalPromptsApp:
    """Clase para gestionar la aplicación de Prompts Jurídicos"""
    
    def __init__(self):
        self.db_name = 'prompts_juridicos.db'
        self.init_db()
    
    # ==================== BASE DE DATOS ====================
    
    def init_db(self):
        """Inicializar base de datos"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Crear tabla de prompts
        c.execute('''
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plataforma TEXT NOT NULL,
                fase_analisis TEXT,
                viabilidad_proceso TEXT,
                viabilidad_exito TEXT,
                palabras_clave TEXT,
                marco_juridico TEXT,
                jerarquizacion TEXT,
                aplicabilidad TEXT,
                prompt_completo TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Crear tabla de archivos adjuntos
        c.execute('''
            CREATE TABLE IF NOT EXISTS archivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER,
                nombre_archivo TEXT,
                tipo_archivo TEXT,
                tamanio INTEGER,
                contenido BLOB,
                FOREIGN KEY (prompt_id) REFERENCES prompts (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        
        # Verificar si hay datos iniciales
        c.execute('SELECT COUNT(*) FROM prompts')
        if c.fetchone()[0] == 0:
            self.insert_initial_data(conn)
        
        conn.close()
    
    def insert_initial_data(self, conn):
        """Insertar datos iniciales"""
        initial_prompts = [
            ("ChatGPT", "Etapa probatoria", "Alta", "85%", "tutela, derecho fundamental, salud",
             "CP Art. 86, Decreto 2591/1991", "Constitución > Bloque Constitucionalidad > Ley Estatutaria",
             "Protección inmediata derechos fundamentales vulnerados",
             "Actúa como abogado constitucionalista experto en tutelas. Elabora acción de tutela según Decreto 2591/1991."),
            
            ("Claude", "Fase de demanda", "Alta", "75%", "proceso ordinario, pretensiones, CGP",
             "CGP Ley 1564/2012 Arts. 82-90", "Constitución Art. 29 > CGP > Código Civil",
             "Demandas declarativas ordinarias sin trámite especial",
             "Como litigante especializado, elabora demanda ordinaria CGP con competencia, partes, pretensiones, hechos y pruebas."),
            
            ("Gemini", "Análisis de contratos", "Media-Alta", "70%", "contrato, cláusulas abusivas, consumidor",
             "CC Arts. 1602-1625, Ley 1480/2011", "Constitución > Estatuto Consumidor > CC",
             "Revisión contratos adhesión, consumo, comerciales",
             "Como especialista contractual, analiza contrato identificando cláusulas abusivas Art. 42 Ley 1480/2011."),
        ]
        
        c = conn.cursor()
        for prompt in initial_prompts:
            c.execute('''
                INSERT INTO prompts (plataforma, fase_analisis, viabilidad_proceso, 
                                   viabilidad_exito, palabras_clave, marco_juridico, 
                                   jerarquizacion, aplicabilidad, prompt_completo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', prompt)
        conn.commit()
    
    def get_all_prompts(self):
        """Obtener todos los prompts con conteo de archivos"""
        conn = sqlite3.connect(self.db_name)
        query = '''
            SELECT p.*, 
                   COUNT(a.id) as num_archivos
            FROM prompts p
            LEFT JOIN archivos a ON p.id = a.prompt_id
            GROUP BY p.id
            ORDER BY p.fecha_modificacion DESC
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def insert_prompt(self, data, archivos_data=None):
        """Insertar nuevo prompt"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO prompts (plataforma, fase_analisis, viabilidad_proceso, 
                               viabilidad_exito, palabras_clave, marco_juridico, 
                               jerarquizacion, aplicabilidad, prompt_completo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data)
        
        prompt_id = c.lastrowid
        
        # Insertar archivos si existen
        if archivos_data:
            for archivo in archivos_data:
                c.execute('''
                    INSERT INTO archivos (prompt_id, nombre_archivo, tipo_archivo, tamanio, contenido)
                    VALUES (?, ?, ?, ?, ?)
                ''', (prompt_id, archivo['nombre'], archivo['tipo'], archivo['tamanio'], archivo['contenido']))
        
        conn.commit()
        conn.close()
    
    def update_prompt(self, prompt_id, data, archivos_data=None):
        """Actualizar prompt existente"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute('''
            UPDATE prompts 
            SET plataforma=?, fase_analisis=?, viabilidad_proceso=?, 
                viabilidad_exito=?, palabras_clave=?, marco_juridico=?, 
                jerarquizacion=?, aplicabilidad=?, prompt_completo=?,
                fecha_modificacion=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (*data, prompt_id))
        
        # Actualizar archivos si se proporcionaron nuevos
        if archivos_data:
            # Eliminar archivos anteriores
            c.execute('DELETE FROM archivos WHERE prompt_id=?', (prompt_id,))
            
            # Insertar nuevos archivos
            for archivo in archivos_data:
                c.execute('''
                    INSERT INTO archivos (prompt_id, nombre_archivo, tipo_archivo, tamanio, contenido)
                    VALUES (?, ?, ?, ?, ?)
                ''', (prompt_id, archivo['nombre'], archivo['tipo'], archivo['tamanio'], archivo['contenido']))
        
        conn.commit()
        conn.close()
    
    def delete_prompt(self, prompt_id):
        """Eliminar prompt"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('DELETE FROM prompts WHERE id=?', (prompt_id,))
        conn.commit()
        conn.close()
    
    def get_archivos(self, prompt_id):
        """Obtener archivos de un prompt"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''
            SELECT id, nombre_archivo, tipo_archivo, tamanio 
            FROM archivos 
            WHERE prompt_id=?
        ''', (prompt_id,))
        archivos = c.fetchall()
        conn.close()
        return archivos
    
    def get_archivo_contenido(self, archivo_id):
        """Obtener contenido de un archivo"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''
            SELECT nombre_archivo, tipo_archivo, contenido 
            FROM archivos 
            WHERE id=?
        ''', (archivo_id,))
        resultado = c.fetchone()
        conn.close()
        return resultado
    
    def format_file_size(self, size_bytes):
        """Formatear tamaño de archivo"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def get_platform_url(self, plataforma):
        """Obtener URL según plataforma"""
        urls = {
            "ChatGPT": "https://chat.openai.com/",
            "Claude": "https://claude.ai/new",
            "Gemini": "https://gemini.google.com/",
            "NotebookLM": "https://notebooklm.google.com/",
            "Perplexity": "https://www.perplexity.ai/"
        }
        return urls.get(plataforma, "https://www.google.com/search?q=" + plataforma)
    
    # ==================== INTERFAZ ====================
    
    def apply_styles(self):
        """Aplicar estilos CSS personalizados"""
        st.markdown("""
            <style>
            .main {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .stApp {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            div[data-testid="stMetricValue"] {
                font-size: 28px;
                font-weight: 700;
                color: #2a5298;
            }
            div[data-testid="stMetricLabel"] {
                font-size: 14px;
                color: #6c757d;
            }
            .dataframe {
                font-size: 13px;
            }
            h1 {
                color: white;
                text-align: center;
                padding: 20px;
            }
            h3 {
                color: #2a5298;
            }
            </style>
        """, unsafe_allow_html=True)
    
    def show_header(self):
        """Mostrar encabezado"""
        st.markdown("<h1>📚 Repositorio de Prompts Jurídicos</h1>", unsafe_allow_html=True)
    
    def show_stats(self, df_prompts):
        """Mostrar estadísticas"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Prompts", len(df_prompts))
        
        with col2:
            if len(df_prompts) > 0:
                plataforma_mas_usada = df_prompts['plataforma'].mode()[0]
                count = len(df_prompts[df_prompts['plataforma'] == plataforma_mas_usada])
                st.metric("Plataforma más usada", f"{plataforma_mas_usada} ({count})")
            else:
                st.metric("Plataforma más usada", "N/A")
        
        with col3:
            if len(df_prompts) > 0:
                total_archivos = df_prompts['num_archivos'].sum()
                st.metric("Total Archivos", int(total_archivos))
            else:
                st.metric("Total Archivos", 0)
    
    def show_form(self, df_prompts):
        """Mostrar formulario de creación/edición"""
        # Inicializar variables de sesión
        if 'show_form' not in st.session_state:
            st.session_state.show_form = False
        if 'editing_id' not in st.session_state:
            st.session_state.editing_id = None
        
        # Botón para mostrar formulario
        if not st.session_state.show_form:
            if st.button("➕ Nuevo Prompt", use_container_width=True):
                st.session_state.show_form = True
                st.session_state.editing_id = None
                st.rerun()
            return
        
        # Determinar si estamos editando
        is_editing = st.session_state.editing_id is not None
        
        if is_editing:
            st.markdown("### ✏️ Editar Prompt")
            prompt_data = df_prompts[df_prompts['id'] == st.session_state.editing_id].iloc[0]
        else:
            st.markdown("### ➕ Nuevo Prompt")
            prompt_data = None
        
        with st.form("prompt_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                plataforma = st.selectbox(
                    "🤖 Plataforma IA *",
                    ["ChatGPT", "Claude", "Gemini", "NotebookLM", "Perplexity", "Copilot", "Otra"],
                    index=["ChatGPT", "Claude", "Gemini", "NotebookLM", "Perplexity", "Copilot", "Otra"].index(prompt_data['plataforma']) if is_editing else 0
                )
                
                fase = st.text_input(
                    "📚 Fase del Análisis Jurídico",
                    value=prompt_data['fase_analisis'] if is_editing else "",
                    placeholder="Ej: Etapa probatoria, Fase de demanda"
                )
                
                viab_proceso = st.selectbox(
                    "📊 Viabilidad del Proceso",
                    ["Alta", "Media-Alta", "Media", "Media-Baja", "Baja"],
                    index=["Alta", "Media-Alta", "Media", "Media-Baja", "Baja"].index(prompt_data['viabilidad_proceso']) if is_editing and prompt_data['viabilidad_proceso'] else 0
                )
            
            with col2:
                viab_exito = st.text_input(
                    "✅ % Viabilidad de Éxito",
                    value=prompt_data['viabilidad_exito'] if is_editing else "",
                    placeholder="Ej: 85%"
                )
                
                palabras = st.text_input(
                    "🏷️ Palabras Clave",
                    value=prompt_data['palabras_clave'] if is_editing else "",
                    placeholder="Separadas por comas"
                )
                
                marco = st.text_area(
                    "⚖️ Marco Jurídico Aplicable",
                    value=prompt_data['marco_juridico'] if is_editing else "",
                    height=70,
                    placeholder="Leyes, artículos, decretos..."
                )
            
            jerarquizacion = st.text_input(
                "📜 Jerarquización Normativa",
                value=prompt_data['jerarquizacion'] if is_editing else "",
                placeholder="Ej: Constitución > Ley > Decreto"
            )
            
            aplicabilidad = st.text_area(
                "🎯 Análisis de Aplicabilidad",
                value=prompt_data['aplicabilidad'] if is_editing else "",
                height=80,
                placeholder="Contexto de aplicación del prompt..."
            )
            
            prompt_completo = st.text_area(
                "💬 Prompt Completo *",
                value=prompt_data['prompt_completo'] if is_editing else "",
                height=200,
                placeholder="Escribe aquí el prompt completo..."
            )
            
            # Archivos adjuntos
            st.markdown("**📎 Archivos Adjuntos (opcional)**")
            uploaded_files = st.file_uploader(
                "Sube documentos relacionados",
                accept_multiple_files=True,
                type=['pdf', 'docx', 'xlsx', 'txt', 'doc', 'xls'],
                label_visibility="collapsed"
            )
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("💾 Guardar", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
            
            if cancel:
                st.session_state.show_form = False
                st.session_state.editing_id = None
                st.rerun()
            
            if submit:
                if not plataforma or not prompt_completo:
                    st.error("⚠️ Por favor completa al menos la plataforma y el prompt completo")
                else:
                    data = (plataforma, fase, viab_proceso, viab_exito, palabras, marco, 
                           jerarquizacion, aplicabilidad, prompt_completo)
                    
                    # Procesar archivos
                    archivos_data = None
                    if uploaded_files:
                        archivos_data = []
                        for file in uploaded_files:
                            file_content = file.read()
                            archivos_data.append({
                                'nombre': file.name,
                                'tipo': file.type if file.type else 'application/octet-stream',
                                'tamanio': file.size,
                                'contenido': file_content
                            })
                            file.seek(0)
                    
                    try:
                        if st.session_state.editing_id:
                            self.update_prompt(st.session_state.editing_id, data, archivos_data)
                            st.success("✅ Prompt actualizado exitosamente")
                        else:
                            self.insert_prompt(data, archivos_data)
                            st.success("✅ Prompt creado exitosamente")
                        
                        st.session_state.show_form = False
                        st.session_state.editing_id = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {str(e)}")
    
    def show_prompts_table(self, df_prompts):
        """Mostrar tabla de prompts"""
        st.markdown("---")
        st.markdown("### 📋 Prompts Registrados")
        
        if len(df_prompts) == 0:
            st.info("No hay prompts registrados. ¡Agrega el primero!")
            return
        
        # Mostrar tabla
        display_df = df_prompts[['id', 'plataforma', 'fase_analisis', 'marco_juridico', 'aplicabilidad', 'palabras_clave', 'num_archivos']].copy()
        display_df.columns = ['ID', 'Plataforma', 'Fase', 'Marco Jurídico', 'Análisis de Aplicabilidad', 'Palabras Clave', 'Archivos']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    def show_prompt_details(self, df_prompts):
        """Mostrar detalles de un prompt seleccionado"""
        if len(df_prompts) == 0:
            return
        
        st.markdown("### 🔍 Detalles del Prompt")
        selected_id = st.selectbox(
            "Seleccionar prompt", 
            df_prompts['id'].tolist(), 
            format_func=lambda x: f"#{x} - {df_prompts[df_prompts['id']==x]['plataforma'].values[0]} - {df_prompts[df_prompts['id']==x]['fase_analisis'].values[0]}"
        )
        
        if not selected_id:
            return
        
        prompt = df_prompts[df_prompts['id'] == selected_id].iloc[0]
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            if st.button("✏️ Editar", use_container_width=True):
                st.session_state.editing_id = selected_id
                st.session_state.show_form = True
                st.rerun()
        
        with col2:
            if st.button("🗑️ Eliminar", use_container_width=True):
                self.delete_prompt(selected_id)
                st.success("🗑️ Prompt eliminado")
                st.rerun()
        
        with col3:
            platform_url = self.get_platform_url(prompt['plataforma'])
            st.markdown(f"""
                <a href="{platform_url}" target="_blank">
                    <button style="
                        width: 100%;
                        padding: 8px 16px;
                        background: #28a745;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-weight: 600;
                        cursor: pointer;
                        font-size: 14px;
                    ">
                        🚀 Ejecutar
                    </button>
                </a>
            """, unsafe_allow_html=True)
        
        # Mostrar detalles
        st.markdown("---")
        st.markdown(f"### 📋 Información del Prompt")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**🤖 Plataforma:** {prompt['plataforma']}")
            st.markdown(f"**📊 Viabilidad Proceso:** {prompt['viabilidad_proceso']}")
            st.markdown(f"**✅ Viabilidad Éxito:** {prompt['viabilidad_exito']}")
        with col2:
            st.markdown(f"**📚 Fase:** {prompt['fase_analisis']}")
            st.markdown(f"**🏷️ Palabras Clave:** {prompt['palabras_clave']}")
        
        st.markdown(f"**⚖️ Marco Jurídico:** {prompt['marco_juridico']}")
        st.markdown(f"**📜 Jerarquización:** {prompt['jerarquizacion']}")
        st.markdown(f"**🎯 Aplicabilidad:** {prompt['aplicabilidad']}")
        
        st.markdown("---")
        st.markdown("### 💬 Prompt Completo")
        
        # Mostrar el prompt en un área de texto copiable
        prompt_text = prompt['prompt_completo']
        st.text_area("", prompt_text, height=150, disabled=False, label_visibility="collapsed", key=f"prompt_text_{selected_id}")
        
        # Botón para copiar al portapapeles
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("💡 **Instrucciones:** Copia el prompt, haz clic en '🚀 Ejecutar' para abrir la plataforma, y pega el prompt allí.")
        with col2:
            if st.button("📋 Copiar", use_container_width=True, key=f"copy_{selected_id}"):
                st.code(prompt_text, language=None)
                st.success("✅ Prompt listo para copiar")
        
        st.markdown("---")
        
        # Mostrar archivos
        archivos = self.get_archivos(selected_id)
        if archivos:
            st.markdown(f"**📎 Archivos Adjuntos ({len(archivos)}):**")
            for archivo in archivos:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    file_icon = "📕" if archivo[1].endswith('.pdf') else "📘" if archivo[1].endswith(('.doc', '.docx')) else "📗" if archivo[1].endswith(('.xlsx', '.xls')) else "📄"
                    st.text(f"{file_icon} {archivo[1]} ({self.format_file_size(archivo[3])})")
                with col2:
                    st.text(f"Tipo: {archivo[2].split('/')[-1]}")
                with col3:
                    archivo_data = self.get_archivo_contenido(archivo[0])
                    if archivo_data:
                        st.download_button(
                            label="⬇️ Descargar",
                            data=archivo_data[2],
                            file_name=archivo_data[0],
                            mime=archivo_data[1],
                            key=f"download_{archivo[0]}",
                            use_container_width=True
                        )
    
    def run(self):
        """Ejecutar la aplicación completa"""
        # Aplicar estilos
        self.apply_styles()
        
        # Mostrar encabezado
        self.show_header()
        
        # Obtener datos
        df_prompts = self.get_all_prompts()
        
        # Mostrar estadísticas
        self.show_stats(df_prompts)
        
        st.markdown("---")
        
        # Mostrar formulario
        self.show_form(df_prompts)
        
        # Mostrar tabla de prompts
        self.show_prompts_table(df_prompts)
        
        # Mostrar detalles del prompt
        self.show_prompt_details(df_prompts)


# ==================== FUNCIÓN PRINCIPAL ====================

def legal_prompts_main():
    """Función principal para ejecutar desde un menú"""
    app = LegalPromptsApp()
    app.run()


# ==================== EJECUCIÓN DIRECTA ====================

if __name__ == "__main__":
    legal_prompts_main()
