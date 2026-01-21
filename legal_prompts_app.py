import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# Configuración de la página
st.set_page_config(
    page_title="Repositorio Prompts Jurídicos",
    page_icon="📚",
    layout="wide"
)

# Estilos CSS personalizados
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

# Inicializar base de datos
def init_db():
    conn = sqlite3.connect('prompts_juridicos.db')
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
        insert_initial_data(conn)
    
    conn.close()

# Insertar datos iniciales
def insert_initial_data(conn):
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
        
        ("Perplexity", "Investigación jurisprudencial", "Alta", "90%", "precedente, línea jurisprudencial, ratio decidendi",
         "Ley 1437/2011 Art. 10, CGP Art. 7", "Constitución > Sentencias Unificación > Jurisprudencia",
         "Construcción líneas jurisprudenciales y precedentes",
         "Como investigador jurídico, analiza precedentes: identifica sentencias hito, extrae ratio decidendi y construye línea."),
        
        ("ChatGPT", "Etapa de alegatos", "Alta", "80%", "alegatos, valoración probatoria, silogismo",
         "CGP Arts. 176-177, 372-380", "Constitución Art. 29 > CGP > Jurisprudencia",
         "Fase final proceso antes de sentencia",
         "Como litigante experto, elabora alegatos con síntesis fáctica, análisis probatorio y subsunción normativa."),
        
        ("Claude", "Recurso extraordinario", "Media", "45%", "casación, violación ley, error",
         "CGP Arts. 334-349", "Constitución Art. 235 > CGP > Reglamentos CSJ",
         "Procesos >500 SMLMV contra sentencias tribunales",
         "Como casacionista CSJ, estructura recurso: requisitos, cargo violación directa/indirecta y sustentación."),
        
        ("NotebookLM", "Due Diligence Legal", "Alta", "85%", "due diligence, M&A, auditoría legal",
         "C.Comercio, Ley 222/95, Ley 1581/2012", "Constitución > Leyes sectoriales > C.Comercio",
         "M&A, fusiones, inversiones, identificar riesgos",
         "Como abogado corporativo, realiza auditoría: corporativo, contratos, litigios, PI, laboral, tributario."),
        
        ("Gemini", "Derecho de Petición", "Alta", "95%", "petición, Art. 23, información",
         "CP Art. 23, Ley 1755/2015", "Constitución Art. 23 > Ley 1755/2015 > CPACA",
         "Ante autoridades públicas/privadas servicio público",
         "Como administrativista, redacta derecho petición Ley 1755/2015 con fundamentos y términos respuesta."),
        
        ("ChatGPT", "Proceso laboral", "Alta", "80%", "despido injusto, indemnización, prestaciones",
         "CST, Ley 789/2002", "Constitución Arts. 25,53 > Convenios OIT > CST",
         "Reclamaciones despido, salarios, prestaciones",
         "Como laboralista, elabora demanda: pretensiones indemnización Art. 64 CST, prestaciones y pruebas."),
        
        ("Claude", "Querella penal", "Media", "60%", "querella, delito querellable, injuria",
         "CPP Ley 906/2004 Arts. 74,107-108", "Constitución Arts. 250,29 > CPP > CP",
         "Delitos querellables. Término: 6 meses",
         "Como penalista, redacta querella sistema acusatorio con tipificación y constitución parte civil."),
        
        ("Perplexity", "Demanda alimentos", "Alta", "85%", "cuota alimentaria, obligación, capacidad",
         "CC Arts. 411-427, Ley 1098/2006", "Constitución Arts. 42,44 > Ley Infancia > CC",
         "Alimentos cónyuges, hijos menores. Verbal sumario",
         "Como abogado familia, elabora demanda alimentos con cuantificación y medida provisional."),
        
        ("Gemini", "Recurso DIAN", "Media-Alta", "55%", "reconsideración, liquidación oficial, sanción",
         "Estatuto Tributario Arts. 720-729", "Constitución Arts. 338,363 > ET > Procedimiento",
         "Contra liquidaciones/sanciones DIAN. 2 meses",
         "Como tributarista, estructura recurso con argumentos por concepto y suspensión."),
        
        ("NotebookLM", "Proceso ejecutivo", "Alta", "90%", "ejecutivo, título ejecutivo, obligación clara",
         "CGP Arts. 422-438, C.Co Arts. 619-849", "Constitución Art. 29 > CGP > C.Comercio",
         "Título ejecutivo con obligación clara, expresa, exigible",
         "Como especialista comercial, elabora ejecutiva con liquidación y medidas cautelares."),
        
        ("ChatGPT", "Nulidad acto administrativo", "Media", "50%", "nulidad, acto administrativo, ilegalidad",
         "CPACA Ley 1437/2011 Arts. 137-141", "Constitución Arts. 29,84,89 > CPACA",
         "Nulidad actos. Caducidad 4 meses/5 años",
         "Como administrativista, demanda nulidad con causales Art. 137 CPACA y restablecimiento."),
        
        ("Claude", "Cobro coactivo PH", "Alta", "95%", "propiedad horizontal, cuotas administración",
         "Ley 675/2001 Arts. 15,51,53-56", "Constitución Art. 58 > Ley 675/2001",
         "Cobro cuotas/multas. Jurisdicción coactiva propia",
         "Como especialista PH, estructura cobro coactivo con mandamiento pago y liquidación."),
        
        ("Perplexity", "Responsabilidad médica", "Media", "40%", "mala praxis, lex artis, consentimiento",
         "Ley 23/1981, Ley 1751/2015", "Constitución Art. 49 > Ley 1751/2015 > Ley 23/1981",
         "Negligencia médica. Probar daño, falla, nexo causal",
         "Como especialista médico-sanitario, demanda responsabilidad con análisis lex artis y perjuicios."),
        
        ("ChatGPT", "Divorcio contencioso", "Alta", "85%", "divorcio, causales, sociedad conyugal",
         "CC Arts. 140-154, Ley 25/1992", "Constitución Art. 42 > CC > Ley Infancia",
         "Matrimonio vigente con causal Art. 154 CC",
         "Como abogado familia, demanda divorcio con causal, liquidación sociedad conyugal y custodia."),
        
        ("Claude", "Protección datos personales IA", "Alta", "75%", "habeas data, protección datos, IA, tratamiento",
         "Ley 1581/2012, Decreto 1377/2013", "Constitución Art. 15 > Ley 1581/2012 > Decreto 1377",
         "Tratamiento datos personales con IA. Sanciones hasta 2000 SMMLV",
         "Como experto datos y Ley 1581/2012, analiza tratamiento con IA: principios, autorización, derechos titulares, IA automatizada."),
        
        ("Gemini", "Regulación financiera IA", "Alta", "85%", "IA sector financiero, gobierno IA, riesgos, modelo",
         "Circular Externa 02/2024 Superfinanciera", "Constitución > Ley 1581/2012 > CONPES 4144 > Circular 02/2024",
         "Obligatoria entidades vigiladas Superfinanciera con IA",
         "Como experto regulación financiera, analiza cumplimiento Circular 02/2024: gobierno IA, gestión riesgos, ciclo vida modelos, transparencia."),
        
        ("Perplexity", "Regulación judicial IA", "Alta", "80%", "Rama Judicial, IA sentencias, ética judicial",
         "Acuerdo PCSJA24-12243 CSJ", "Constitución Arts. 228-229 > Ley 270/1996 > Acuerdo CSJ",
         "Todos funcionarios Rama Judicial. Límites y buenas prácticas IA",
         "Como experto regulación judicial, analiza cumplimiento Acuerdo CSJ: principios, usos permitidos/prohibidos, garantías procesales, responsabilidad."),
        
        ("ChatGPT", "Criptoactivos y regulación", "Media-Alta", "65%", "criptoactivos, blockchain, bitcoin, lavado activos",
         "Ley 2502/2023, Decreto 1692/2020 UIAF", "Constitución > Ley 2502/2023 > Estatuto Financiero",
         "Exchanges cripto, proveedores servicios. Registro UIAF",
         "Como especialista fintech y cripto, analiza Ley 2502/2023: registro UIAF, LA/FT, KYC, ciberseguridad, IA en trading."),
        
        ("NotebookLM", "Derechos de autor y IA", "Media", "60%", "derechos autor, IA generativa, originalidad, DNDA",
         "Ley 23/1982, Ley 1915/2018, Resoluciones DNDA", "Constitución Art. 61 > Decisión Andina 351 > Ley 23/1982",
         "Creadores y usuarios IA generativa. Autoría y protección",
         "Como experto PI y tecnología, analiza derechos autor IA: autoría, originalidad, infracciones, registro DNDA, casos por tipo contenido."),
        
        ("Claude", "Política Nacional de IA", "Alta", "90%", "política pública IA, CONPES, gobernanza IA, ética",
         "CONPES 4144/2025, Ley 1955/2019 PND", "Constitución > PND Ley 1955/2019 > CONPES 4144/2025",
         "Vinculante sector público, orientador privado. Estrategia nacional IA",
         "Como consultor política pública IA, analiza CONPES 4144: principios éticos, 6 pilares, clasificación riesgo, gobernanza, plan acción.")
    ]
    
    c = conn.cursor()
    c.executemany('''
        INSERT INTO prompts (plataforma, fase_analisis, viabilidad_proceso, viabilidad_exito,
                           palabras_clave, marco_juridico, jerarquizacion, aplicabilidad, prompt_completo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', initial_prompts)
    conn.commit()

# Funciones CRUD
def get_all_prompts():
    conn = sqlite3.connect('prompts_juridicos.db')
    query = '''
        SELECT p.*, COUNT(a.id) as num_archivos
        FROM prompts p
        LEFT JOIN archivos a ON p.id = a.prompt_id
        GROUP BY p.id
        ORDER BY p.fecha_modificacion DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def insert_prompt(data, archivos=None):
    conn = sqlite3.connect('prompts_juridicos.db')
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO prompts (plataforma, fase_analisis, viabilidad_proceso, viabilidad_exito,
                           palabras_clave, marco_juridico, jerarquizacion, aplicabilidad, prompt_completo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)
    
    prompt_id = c.lastrowid
    
    # Guardar archivos adjuntos
    if archivos:
        for archivo in archivos:
            c.execute('''
                INSERT INTO archivos (prompt_id, nombre_archivo, tipo_archivo, tamanio, contenido)
                VALUES (?, ?, ?, ?, ?)
            ''', (prompt_id, archivo['nombre'], archivo['tipo'], archivo['tamanio'], archivo['contenido']))
    
    conn.commit()
    conn.close()
    return prompt_id

def update_prompt(prompt_id, data, archivos=None):
    conn = sqlite3.connect('prompts_juridicos.db')
    c = conn.cursor()
    
    c.execute('''
        UPDATE prompts
        SET plataforma=?, fase_analisis=?, viabilidad_proceso=?, viabilidad_exito=?,
            palabras_clave=?, marco_juridico=?, jerarquizacion=?, aplicabilidad=?,
            prompt_completo=?, fecha_modificacion=CURRENT_TIMESTAMP
        WHERE id=?
    ''', data + (prompt_id,))
    
    # Si hay nuevos archivos, eliminar los antiguos y agregar los nuevos
    if archivos is not None:
        c.execute('DELETE FROM archivos WHERE prompt_id=?', (prompt_id,))
        for archivo in archivos:
            c.execute('''
                INSERT INTO archivos (prompt_id, nombre_archivo, tipo_archivo, tamanio, contenido)
                VALUES (?, ?, ?, ?, ?)
            ''', (prompt_id, archivo['nombre'], archivo['tipo'], archivo['tamanio'], archivo['contenido']))
    
    conn.commit()
    conn.close()

def delete_prompt(prompt_id):
    conn = sqlite3.connect('prompts_juridicos.db')
    c = conn.cursor()
    c.execute('DELETE FROM prompts WHERE id=?', (prompt_id,))
    conn.commit()
    conn.close()

def get_archivos(prompt_id):
    conn = sqlite3.connect('prompts_juridicos.db')
    c = conn.cursor()
    c.execute('SELECT id, nombre_archivo, tipo_archivo, tamanio FROM archivos WHERE prompt_id=?', (prompt_id,))
    archivos = c.fetchall()
    conn.close()
    return archivos

def get_archivo_contenido(archivo_id):
    conn = sqlite3.connect('prompts_juridicos.db')
    c = conn.cursor()
    c.execute('SELECT nombre_archivo, tipo_archivo, contenido FROM archivos WHERE id=?', (archivo_id,))
    archivo = c.fetchone()
    conn.close()
    return archivo

def format_file_size(bytes_size):
    if bytes_size == 0:
        return "0 Bytes"
    k = 1024
    sizes = ['Bytes', 'KB', 'MB', 'GB']
    i = 0
    size = bytes_size
    while size >= k and i < len(sizes) - 1:
        size /= k
        i += 1
    return f"{size:.2f} {sizes[i]}"

# Inicializar base de datos
init_db()

# Inicializar estado de sesión
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None
if 'show_form' not in st.session_state:
    st.session_state.show_form = False

# Header
st.markdown("<h1>📚 Repositorio de Prompts Jurídicos</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: white; margin-top: -20px;'>Creado por Jose A. Garcia T.</p>", unsafe_allow_html=True)

# Estadísticas
df_prompts = get_all_prompts()
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Prompts", len(df_prompts))
with col2:
    plataformas = df_prompts['plataforma'].nunique() if len(df_prompts) > 0 else 0
    st.metric("Plataformas", plataformas)
with col3:
    con_archivos = len(df_prompts[df_prompts['num_archivos'] > 0]) if len(df_prompts) > 0 else 0
    st.metric("Con Archivos", con_archivos)

st.markdown("---")

# Botones de acción
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    if st.button("➕ Agregar Nuevo Prompt", use_container_width=True):
        st.session_state.show_form = not st.session_state.show_form
        st.session_state.editing_id = None

with col2:
    if st.button("📥 Descargar Excel", use_container_width=True):
        if len(df_prompts) > 0:
            # Preparar datos para exportar
            export_df = df_prompts[['id', 'plataforma', 'fase_analisis', 'viabilidad_proceso', 
                                   'viabilidad_exito', 'palabras_clave', 'marco_juridico', 
                                   'jerarquizacion', 'aplicabilidad', 'prompt_completo', 'num_archivos']]
            export_df.columns = ['No.', 'Plataforma IA', 'Fase de Análisis', 'Viabilidad por Proceso',
                               'Viabilidad de Éxito', 'Palabras Clave', 'Marco Jurídico',
                               'Jerarquización Normativa', 'Análisis de Aplicabilidad', 
                               'Prompt Completo', 'Cantidad Archivos']
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, sheet_name='Prompts Jurídicos', index=False)
            
            fecha = datetime.now().strftime("%Y-%m-%d")
            st.download_button(
                label="⬇️ Descargar",
                data=buffer.getvalue(),
                file_name=f"Repositorio_Prompts_Juridicos_{fecha}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

with col3:
    uploaded_file = st.file_uploader("📤 Importar Unicamente Prompts en Excel", type=['xlsx', 'xls'], accept_multiple_files=False,
            help="Solo archivos Excel (.xlsx, .xls)", key="import_excel")
    if uploaded_file is not None:
        try:
            import_df = pd.read_excel(uploaded_file)
            conn = sqlite3.connect('prompts_juridicos.db')
            
            for _, row in import_df.iterrows():
                data = (
                    row.get('Plataforma IA', ''),
                    row.get('Fase de Análisis', ''),
                    row.get('Viabilidad por Proceso', ''),
                    row.get('Viabilidad de Éxito', ''),
                    row.get('Palabras Clave', ''),
                    row.get('Marco Jurídico', ''),
                    row.get('Jerarquización Normativa', ''),
                    row.get('Análisis de Aplicabilidad', ''),
                    row.get('Prompt Completo', '')
                )
                insert_prompt(data)
            
            conn.close()
            st.success(f"✅ Se importaron {len(import_df)} prompts exitosamente")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al importar: {str(e)}")

# Formulario de nuevo/editar prompt
if st.session_state.show_form:
    st.markdown("### 📝 Nuevo Prompt Jurídico" if st.session_state.editing_id is None else "### ✏️ Editar Prompt")
    
    # Si estamos editando, cargar datos
    prompt_data = None
    if st.session_state.editing_id:
        filtered_df = df_prompts[df_prompts['id'] == st.session_state.editing_id]
        if not filtered_df.empty:
            prompt_data = filtered_df.iloc[0]
    
    with st.form("prompt_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Determinar índice de plataforma
            plataforma_options = ["", "ChatGPT", "Gemini", "Claude", "NotebookLM", "Perplexity"]
            plataforma_index = 0
            if prompt_data is not None:
                try:
                    plataforma_index = plataforma_options.index(prompt_data['plataforma'])
                except (ValueError, KeyError):
                    plataforma_index = 0
            
            plataforma = st.selectbox(
                "Plataforma IA *",
                plataforma_options,
                index=plataforma_index
            )
            fase = st.text_input("Fase de Análisis", value=str(prompt_data['fase_analisis']) if prompt_data is not None else "")
            viab_proceso = st.text_input("Viabilidad por Proceso", value=str(prompt_data['viabilidad_proceso']) if prompt_data is not None else "")
            viab_exito = st.text_input("Viabilidad de Éxito", value=str(prompt_data['viabilidad_exito']) if prompt_data is not None else "")
        
        with col2:
            palabras = st.text_input("Palabras Clave", value=str(prompt_data['palabras_clave']) if prompt_data is not None else "")
            marco = st.text_input("Marco Jurídico", value=str(prompt_data['marco_juridico']) if prompt_data is not None else "")
        
        jerarquizacion = st.text_area("Jerarquización Normativa", value=str(prompt_data['jerarquizacion']) if prompt_data is not None else "", height=100)
        aplicabilidad = st.text_area("Análisis de Aplicabilidad", value=str(prompt_data['aplicabilidad']) if prompt_data is not None else "", height=100)
        prompt_completo = st.text_area("Prompt Completo *", value=str(prompt_data['prompt_completo']) if prompt_data is not None else "", height=150)
        
        # Archivos adjuntos
        st.markdown("#### 📎 Archivos Adjuntos")
        
        # Mostrar información de archivos existentes si está editando
        if st.session_state.editing_id:
            archivos_existentes = get_archivos(st.session_state.editing_id)
            if archivos_existentes:
                st.info(f"📂 Archivos actuales: {len(archivos_existentes)}")
                cols = st.columns(len(archivos_existentes) if len(archivos_existentes) <= 3 else 3)
                for idx, archivo in enumerate(archivos_existentes):
                    with cols[idx % 3]:
                        file_icon = "📕" if archivo[1].endswith('.pdf') else "📘" if archivo[1].endswith(('.doc', '.docx')) else "📗" if archivo[1].endswith(('.xlsx', '.xls')) else "📄"
                        st.text(f"{file_icon} {archivo[1]}")
                        st.caption(f"{format_file_size(archivo[3])}")
                st.warning("⚠️ Si subes nuevos archivos, reemplazarán los existentes")
        
        uploaded_files = st.file_uploader(
            "Arrastra y suelta archivos aquí o haz clic para seleccionar (.pdf, .doc, .docx, .xlsx, .xls)",
            type=['pdf', 'doc', 'docx', 'xlsx', 'xls'],
            accept_multiple_files=True,
            key="file_uploader",
            help="Formatos soportados: PDF, DOC, DOCX, XLSX, XLS - Máximo tamaño recomendado: 10MB por archivo"
        )
        
        # Mostrar archivos seleccionados con diseño mejorado
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} archivo(s) seleccionado(s)")
            cols = st.columns(len(uploaded_files) if len(uploaded_files) <= 3 else 3)
            for idx, file in enumerate(uploaded_files):
                with cols[idx % 3]:
                    file_icon = "📕" if file.name.endswith('.pdf') else "📘" if file.name.endswith(('.doc', '.docx')) else "📗" if file.name.endswith(('.xlsx', '.xls')) else "📄"
                    st.markdown(f"**{file_icon} {file.name}**")
                    st.caption(f"Tamaño: {format_file_size(file.size)}")
                    st.caption(f"Tipo: {file.type if file.type else 'Desconocido'}")
        
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
                        # Leer contenido del archivo
                        file_content = file.read()
                        archivos_data.append({
                            'nombre': file.name,
                            'tipo': file.type if file.type else 'application/octet-stream',
                            'tamanio': file.size,
                            'contenido': file_content
                        })
                        # Resetear el puntero del archivo
                        file.seek(0)
                
                try:
                    if st.session_state.editing_id:
                        update_prompt(st.session_state.editing_id, data, archivos_data)
                        st.success("✅ Prompt actualizado exitosamente")
                    else:
                        insert_prompt(data, archivos_data)
                        st.success("✅ Prompt creado exitosamente")
                    
                    st.session_state.show_form = False
                    st.session_state.editing_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {str(e)}")

st.markdown("---")

# Tabla de prompts
st.markdown("### 📋 Prompts Registrados")

if len(df_prompts) == 0:
    st.info("No hay prompts registrados. ¡Agrega el primero!")
else:
    # Mostrar tabla
    display_df = df_prompts[['id', 'plataforma', 'fase_analisis', 'marco_juridico', 'aplicabilidad', 'palabras_clave', 'num_archivos']].copy()
    display_df.columns = ['ID', 'Plataforma', 'Fase', 'Marco_Juridico', 'Análisis de Aplicabilidad', 'Palabras Clave', 'Archivos']
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Seleccionar prompt para ver detalles
    st.markdown("### 🔍 Detalles del Prompt")
    selected_id = st.selectbox("Seleccionar prompt", df_prompts['id'].tolist(), 
                               format_func=lambda x: f"#{x} - {df_prompts[df_prompts['id']==x]['plataforma'].values[0]} - {df_prompts[df_prompts['id']==x]['fase_analisis'].values[0]}")
    
    if selected_id:
        prompt = df_prompts[df_prompts['id'] == selected_id].iloc[0]
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            if st.button("✏️ Editar", use_container_width=True):
                st.session_state.editing_id = selected_id
                st.session_state.show_form = True
                st.rerun()
        
        with col2:
            if st.button("🗑️ Eliminar", use_container_width=True):
                delete_prompt(selected_id)
                st.success("🗑️ Prompt eliminado")
                st.rerun()
        
        with col3:
            # Función para obtener URL según plataforma
            def get_platform_url(plataforma):
                urls = {
                    "ChatGPT": "https://chat.openai.com/",
                    "Claude": "https://claude.ai/new",
                    "Gemini": "https://gemini.google.com/",
                    "NotebookLM": "https://notebooklm.google.com/",
                    "Perplexity": "https://www.perplexity.ai/"
                }
                return urls.get(plataforma, "https://www.google.com/search?q=" + plataforma)
            
            platform_url = get_platform_url(prompt['plataforma'])
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
        archivos = get_archivos(selected_id)
        if archivos:
            st.markdown(f"**📎 Archivos Adjuntos ({len(archivos)}):**")
            for archivo in archivos:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    file_icon = "📕" if archivo[1].endswith('.pdf') else "📘" if archivo[1].endswith(('.doc', '.docx')) else "📗" if archivo[1].endswith(('.xlsx', '.xls')) else "📄"
                    st.text(f"{file_icon} {archivo[1]} ({format_file_size(archivo[3])})")
                with col2:
                    st.text(f"Tipo: {archivo[2].split('/')[-1]}")
                with col3:
                    archivo_data = get_archivo_contenido(archivo[0])
                    if archivo_data:
                        st.download_button(
                            label="⬇️ Descargar",
                            data=archivo_data[2],
                            file_name=archivo_data[0],
                            mime=archivo_data[1],
                            key=f"download_{archivo[0]}",
                            use_container_width=True
                        )