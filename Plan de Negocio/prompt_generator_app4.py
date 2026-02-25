"""
Generador de Prompts para Plan de Negocio — Streamlit App

"""

import streamlit as st
import sqlite3
import json
import os
from datetime import datetime

# ──────────────────────────────────────────────
# Configuración de página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Generador de Prompts · Plan de Negocio",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CSS personalizado
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0f172a 100%);
        color: #f1f5f9;
    }
    section[data-testid="stSidebar"] {
        background: rgba(10, 18, 40, 0.92);
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }
    .plan-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .prompt-box {
        background: rgba(2, 12, 30, 0.85);
        border: 1.5px solid rgba(96, 165, 250, 0.35);
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 16px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        color: #e2e8f0;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .section-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
        background: rgba(59,130,246,.18);
        border: 1px solid rgba(59,130,246,.35);
        color: #93c5fd;
    }
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all .25s;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(37, 99, 235, .35);
    }
    .stTextInput input, .stTextArea textarea {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1.5px solid rgba(148, 163, 184, 0.25) !important;
        color: white !important;
        border-radius: 8px !important;
    }
    h1, h2, h3 { color: #f1f5f9 !important; }
    .model-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        background: rgba(139,92,246,0.25);
        border: 1px solid rgba(139,92,246,0.4);
        color: #c4b5fd;
        font-size: 12px;
        font-weight: 700;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SQLite — Base de datos
# ──────────────────────────────────────────────
DB_PATH = "prompts_negocio.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            prompts_json TEXT NOT NULL,
            modelo TEXT,
            creado_en TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()

def save_prompts(negocio, descripcion, prompts_dict, modelo):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO prompts (negocio, descripcion, prompts_json, modelo, creado_en) VALUES (?,?,?,?,?)",
        (negocio, descripcion, json.dumps(prompts_dict, ensure_ascii=False),
         modelo, datetime.now().isoformat())
    )
    con.commit()
    last_id = cur.lastrowid
    con.close()
    return last_id

def load_all_prompts():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id, negocio, modelo, creado_en FROM prompts ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    con.close()
    return rows

def load_prompt_by_id(pid):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT * FROM prompts WHERE id=?", (pid,))
    row = cur.fetchone()
    con.close()
    return row

init_db()


# ──────────────────────────────────────────────
# Modelos de IA disponibles
# ──────────────────────────────────────────────
AI_MODELS = {
    "🤖 Claude (Anthropic)":        "https://claude.ai",
    "✨ ChatGPT (OpenAI)":           "https://chatgpt.com",
    "🔵 Gemini (Google)":           "https://gemini.google.com",
    "📓 NotebookLM (Google)":       "https://notebooklm.google.com",
    "🔍 Perplexity AI":             "https://www.perplexity.ai",
    "🌊 Grok (xAI)":               "https://grok.com",
    "🦙 Meta AI (Llama)":           "https://www.meta.ai",
    "🇪🇺 Mistral Le Chat":          "https://chat.mistral.ai",
    "💠 Copilot (Microsoft)":       "https://copilot.microsoft.com",
    "🟣 DeepSeek":                  "https://chat.deepseek.com",
}


# ──────────────────────────────────────────────
# Generadores de prompts
# ──────────────────────────────────────────────
def build_prompts(name: str, desc: str) -> dict:
    return {
        "1_resumen_ejecutivo": f"""Actúa como un consultor estratégico senior con más de 20 años de experiencia en startups y empresas consolidadas.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Genera un RESUMEN EJECUTIVO completo y profesional que incluya:

1. MISIÓN — Declaración clara, concisa y memorable de propósito (máximo 2 oraciones).
2. VISIÓN — Estado futuro aspiracional a 5 años, específico y medible.
3. VALORES CORPORATIVOS — 4-5 valores con descripción de cómo se aplican.
4. OBJETIVOS ESTRATÉGICOS — 5 objetivos SMART para los próximos 12-24 meses.
5. KPIs PRINCIPALES — 6-8 indicadores clave con metas numéricas y frecuencia de medición.
6. MODELO DE NEGOCIO — Cómo genera valor, para quién y cómo monetiza.
7. ESTADO ACTUAL Y PROYECCIÓN — Etapa actual del negocio y proyección a 1, 3 y 5 años.

Formato: usa headers claros, listas numeradas y tablas donde sea útil. Mínimo 600 palabras. Tono profesional y ejecutivo.""",

        "2_mercados_objetivo": f"""Actúa como analista de mercado experto con especialización en estrategia de entrada a mercados.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Desarrolla un análisis exhaustivo de MERCADOS OBJETIVO que incluya:

1. ANÁLISIS TAM-SAM-SOM
   - TAM (Total Addressable Market): tamaño total del mercado global con fuentes estimadas.
   - SAM (Serviceable Addressable Market): segmento alcanzable con el modelo actual.
   - SOM (Serviceable Obtainable Market): porción realista en los primeros 3 años.

2. SEGMENTOS PRIORITARIOS (mínimo 4 segmentos)
   Para cada segmento incluir:
   - Nombre y descripción detallada del segmento
   - Tamaño estimado y potencial de ingresos
   - Características demográficas, psicográficas y conductuales
   - Necesidad principal que satisface el negocio
   - Estrategia de entrada y canales de adquisición
   - Ticket promedio estimado y LTV

3. MAPA DE EMPATÍA DEL CLIENTE IDEAL — Para el segmento #1.

4. ESTRATEGIA DE EXPANSIÓN GEOGRÁFICA — Fases de expansión por regiones/países.

5. TENDENCIAS DE MERCADO — 5 tendencias relevantes que favorecen el negocio.

Mínimo 600 palabras. Sé específico con estimaciones y datos.""",

        "3_analisis_competitivo": f"""Actúa como estratega competitivo con expertise en análisis de mercados y posicionamiento.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Realiza un ANÁLISIS COMPETITIVO completo que incluya:

1. PANORAMA COMPETITIVO
   - Descripción del ecosistema competitivo actual
   - Mapa de actores: competidores directos, indirectos y sustitutos potenciales

2. 5 FUERZAS DE PORTER (análisis detallado aplicado a este negocio)
   - Rivalidad entre competidores existentes
   - Amenaza de nuevos entrantes
   - Poder de negociación de proveedores
   - Poder de negociación de clientes
   - Amenaza de productos/servicios sustitutos
   → Para cada fuerza: nivel (alto/medio/bajo), justificación e implicaciones estratégicas.

3. MATRIZ FODA
   - Fortalezas internas (mínimo 5)
   - Oportunidades externas (mínimo 5)
   - Debilidades internas (mínimo 4)
   - Amenazas externas (mínimo 4)

4. BRECHAS Y OPORTUNIDADES — 4-5 oportunidades concretas no explotadas por la competencia.

5. POSICIONAMIENTO RECOMENDADO — Declaración de posicionamiento y estrategia competitiva sugerida.

Mínimo 600 palabras. Sé analítico y basado en lógica de mercado.""",

        "4_propuesta_de_valor": f"""Actúa como experto en branding estratégico, diseño de propuesta de valor y marketing de posicionamiento.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Define la PROPUESTA DE VALOR ÚNICA con los siguientes componentes:

1. DECLARACIÓN DE VALOR CENTRAL
   - Propuesta de valor en una oración poderosa y memorable
   - Elevator pitch de 30 segundos

2. VALUE PROPOSITION CANVAS
   - PERFIL DEL CLIENTE:
     * Trabajos del cliente (Jobs to be done): funcionales, sociales, emocionales
     * Dolores (Pains): frustraciones, miedos, obstáculos
     * Ganancias (Gains): beneficios esperados, deseados y sorpresivos
   - MAPA DE VALOR:
     * Productos/servicios ofrecidos
     * Aliviadores de dolores (Pain relievers)
     * Creadores de ganancias (Gain creators)

3. 3 PILARES DE DIFERENCIACIÓN
   Para cada pilar: nombre, descripción, argumento concreto y cómo comunicarlo.

4. ESTRATEGIA DE COMUNICACIÓN POR CANAL
   - Mensaje para redes sociales
   - Mensaje para email/ventas B2B
   - Mensaje para publicidad digital
   - Mensaje para partnerships

5. EVOLUCIÓN DE LA PROPUESTA — Cómo proteger y escalar la propuesta de valor en el tiempo.

Mínimo 600 palabras. Tono creativo y estratégico.""",

        "5_plan_de_accion": f"""Actúa como consultor de implementación estratégica especializado en operaciones y crecimiento de empresas.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Desarrolla un PLAN DE ACCIÓN DETALLADO estructurado en 3 fases:

━━━ FASE 1: FUNDAMENTOS (Meses 1-3) ━━━
- Objetivo principal de la fase
- 7 acciones prioritarias con responsable sugerido y plazo
- KPIs de éxito de la fase con metas numéricas
- Recursos necesarios (humanos, tecnológicos, financieros)
- Inversión estimada

━━━ FASE 2: CRECIMIENTO (Meses 4-12) ━━━
- Objetivo principal de la fase
- 7 acciones prioritarias con responsable sugerido y plazo
- KPIs de éxito con metas numéricas
- Hitos clave del trimestre
- Recursos e inversión estimada

━━━ FASE 3: CONSOLIDACIÓN (Meses 13-24) ━━━
- Objetivo principal de la fase
- 7 acciones prioritarias con responsable sugerido y plazo
- KPIs de éxito con metas numéricas
- Escenarios de expansión
- Recursos e inversión estimada

GESTIÓN DE RIESGOS
- 5 riesgos principales con probabilidad, impacto y plan de mitigación

ACCIONES INMEDIATAS (próximos 30 días)
- Lista de las 10 primeras acciones a ejecutar hoy

Mínimo 700 palabras. Sé práctico, accionable y específico.""",

        "6_desarrollo_negocio": f"""Actúa como experto en desarrollo de negocios, modelos de monetización y estrategia de crecimiento.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Crea un plan completo de DESARROLLO DEL NEGOCIO que incluya:

1. MODELO DE INGRESOS Y MONETIZACIÓN
   - Fuentes de ingresos actuales y potenciales
   - Estructura de precios recomendada con justificación
   - Proyección de ingresos a 12, 24 y 36 meses (escenario conservador, realista y optimista)

2. ESTRATEGIA DE VENTAS Y CANALES
   - Proceso de ventas paso a paso
   - Canales de distribución primarios y secundarios
   - Estrategia de marketing digital y contenido
   - Funnel de conversión sugerido con métricas

3. ESTRATEGIA DE PARTNERSHIPS Y ALIANZAS
   - Tipos de alianzas estratégicas recomendadas
   - Perfil de socios ideales
   - Modelo de propuesta para alianzas

4. OPERACIONES Y TECNOLOGÍA
   - Stack tecnológico recomendado
   - Procesos clave a automatizar
   - Estructura organizacional sugerida por etapa

5. FINANCIAMIENTO Y CRECIMIENTO
   - Opciones de financiamiento adecuadas para cada etapa
   - Métricas de tracción que buscan los inversores
   - Roadmap de producto/servicio a 24 meses

6. MÉTRICAS NORTE (North Star Metrics)
   - 3-5 métricas fundamentales que definen el éxito del negocio

Mínimo 700 palabras. Orientado a resultados y crecimiento escalable.""",

        "7_prompt_imagen_logo": f"""Actúa como director creativo y diseñador de marca con experiencia en identidad visual para empresas tech y startups.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Genera los siguientes PROMPTS DE IMAGEN para herramientas de IA (Midjourney, DALL-E, Stable Diffusion, Firefly):

━━━ PROMPT #1 — LOGO PRINCIPAL ━━━
Genera un prompt detallado en español para crear el logo principal del negocio. Incluir:
- Estilo visual (minimalista, moderno, geométrico, etc.)
- Paleta de colores con justificación de psicología del color
- Tipografía sugerida
- Elementos icónicos o simbólicos relevantes al negocio
- Formato: "professional logo for [negocio], [descripción visual detallada], vector style, clean, scalable, white background, --ar 1:1 --style raw"

━━━ PROMPT #2 — VARIACIONES DEL LOGO ━━━
- Versión dark/dark mode
- Versión solo ícono (sin texto)
- Versión horizontal con tagline

━━━ PROMPT #3 — IDENTIDAD VISUAL DE MARCA ━━━
Prompt para crear un brandboard completo con paleta de colores, tipografías y elementos visuales.

━━━ PROMPT #4 — IMAGEN HERO / BANNER ━━━
Prompt para imagen principal de website o redes sociales representando la esencia del negocio.

━━━ PROMPT #5 — PERSONAJE O MASCOTA (opcional) ━━━
Si aplica, prompt para crear un personaje/mascota que represente la marca.

Para cada prompt: escribe el prompt completo en español listo para copiar en la herramienta IA, y explica brevemente en español el concepto detrás.""",

        "8_prompt_video": f"""Actúa como director creativo y productor de video con especialización en contenido para marcas digitales.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Genera PROMPTS COMPLETOS para crear videos con herramientas de IA (Sora, Runway, Pika, Kling, HeyGen):

━━━ PROMPT #1 — VIDEO PRESENTACIÓN DE MARCA (60 segundos) ━━━
Prompt detallado para video de presentación corporativa. Incluir:
- Escenas clave con descripción visual
- Estilo cinematográfico, paleta de colores, ambiente
- Música y tono emocional sugerido
- Texto/narración en off sugerida
- Formato: "cinematic brand video for [negocio], [descripción de escenas], [estilo], [mood], 4K, professional"

━━━ PROMPT #2 — REEL DE REDES SOCIALES (15-30 segundos) ━━━
Prompt para video viral de Instagram/TikTok mostrando el negocio en acción.

━━━ PROMPT #3 — VIDEO EXPLICATIVO / EXPLAINER (90 segundos) ━━━
Prompt para video animado explicando el problema que resuelve y la solución del negocio.

━━━ PROMPT #4 — VIDEO TESTIMONIAL / CASO DE ÉXITO ━━━
Prompt para video con estructura de storytelling de un cliente satisfecho.

━━━ PROMPT #5 — VIDEO ANUNCIO PUBLICITARIO (15 segundos) ━━━
Prompt para ad corto, impactante y con CTA claro para publicidad digital.

━━━ GUIÓN NARRATIVO COMPLETO ━━━
Para el video principal: guión completo con escenas, diálogos/narración, transiciones y CTA.

Para cada prompt: escribe el prompt en español (listo para la herramienta IA) y el concepto en español. Incluye sugerencias de plataforma ideal para cada video.""",

        "9_landing_page": f"""Actúa como un equipo experto combinando: Diseñador UI/UX Senior, Desarrollador Front-End Full-Stack, Copywriter especialista en conversión, Estratega de Marketing Digital y Experto en SEO.

NEGOCIO: {name}
DESCRIPCIÓN: {desc}

Tu misión es generar el CÓDIGO COMPLETO HTML/CSS/JavaScript de una landing page de alta conversión, visualmente extraordinaria y lista para publicar.

══════════════════════════════════════════════════════════
 INSTRUCCIONES DE DISEÑO Y ESTÉTICA
══════════════════════════════════════════════════════════

IDENTIDAD VISUAL:
- Diseña una paleta de colores premium basada en la esencia del negocio "{name}" (propón colores primario, secundario, acento y neutros con sus códigos HEX).
- Elige tipografías de Google Fonts que sean únicas, memorables y apropiadas para la marca (NO uses Inter, Roboto ni Arial). Una fuente display para títulos y una fuente legible para cuerpo.
- El logo del negocio debe integrarse en el header como un SVG inline elegante o como texto estilizado con la fuente display si no hay imagen disponible; diseña un isologotipo de texto que se vea como una marca real.
- Integra placeholders realistas para las imágenes generadas por IA usando elementos CSS/SVG creativos (no simples rectángulos grises), con descripciones del tipo de imagen que irá ahí (hero, equipo, producto, testimonios, etc.).

ESTÉTICA Y ATMÓSFERA:
- Elige una dirección estética clara y ejecútala con precisión: puede ser luxury/refinado, editorial/magazine, bold/minimalista, tech/futurista, orgánico/natural, art deco, etc. — lo que mejor represente al negocio.
- Usa fondos con profundidad: gradientes mesh, texturas sutiles, noise overlays, formas geométricas flotantes o patrones que creen atmósfera.
- Incluye animaciones CSS impactantes: entrada de elementos con scroll (Intersection Observer), efectos hover memorables, parallax sutil, contador animado de métricas.
- Diseño asimétrico, con elementos que rompan el grid de forma intencional, overlap de secciones, uso dramático del espacio negativo.

══════════════════════════════════════════════════════════
 ESTRUCTURA DE LA LANDING PAGE (TODAS LAS SECCIONES)
══════════════════════════════════════════════════════════

1. HEADER / NAVEGACIÓN FIJA
   - Logo del negocio (SVG inline o texto estilizado como marca real)
   - Menú de navegación con links suaves (smooth scroll) a cada sección
   - CTA principal en el header ("Empezar gratis", "Contactar", etc.)
   - Efecto glassmorphism o sólido según la estética elegida
   - Hamburger menu animado para móvil

2. HERO SECTION — PRIMERA IMPRESIÓN (Above the fold)
   - Headline principal: frase de máximo impacto que comunique la transformación del cliente (NO el nombre del producto, SÍ el beneficio)
   - Subheadline: complemento que clarifica la propuesta de valor en 1-2 líneas
   - 2 botones CTA: primario (acción principal) y secundario (ver demo/saber más)
   - Elemento visual hero: mockup del producto, ilustración SVG animada o imagen placeholder descriptiva
   - Social proof inicial: "Más de X clientes" o logos de empresas / métricas clave con animación de conteo
   - Efecto de fondo animado (partículas, gradiente en movimiento, formas geométricas)

3. BARRA DE LOGOS — CREDIBILIDAD SOCIAL
   - Sección "Confían en nosotros" con logos de empresas/medios/partners (usa nombres ficticios representativos)
   - Animación de scroll infinito horizontal (marquee/carousel)

4. PROBLEMA / SOLUCIÓN — STORYTELLING
   - Sección narrativa: primero agitar el dolor del cliente ("¿Cansado de...?")
   - Luego presentar la solución de forma clara y visual
   - Usar iconografía SVG inline animada, no emojis
   - Diseño de dos columnas con contraste visual fuerte

5. CARACTERÍSTICAS / BENEFICIOS — PROPUESTA DE VALOR
   - Grid de 3-6 features con icono SVG único, título y descripción
   - Cada tarjeta con efecto hover 3D o elevación
   - Highlight del diferenciador principal con diseño destacado
   - Tabs o acordeones si hay mucho contenido

6. CÓMO FUNCIONA — PROCESO EN 3 PASOS
   - Numeración visual grande y decorativa
   - Descripción clara de cada paso con icono
   - Línea conectora animada entre pasos
   - Screenshot o mockup placeholder por cada paso

7. MÉTRICAS / RESULTADOS — PRUEBA SOCIAL NUMÉRICA
   - 4-6 números impactantes con contador animado al hacer scroll
   - Ej: "97% de satisfacción", "10,000+ usuarios", "3x más rápido"
   - Fondo con imagen o gradiente dramático (sección oscura si el resto es claro)

8. TESTIMONIOS — PRUEBA SOCIAL CUALITATIVA
   - 3 testimonios con foto placeholder circular, nombre, cargo/empresa y texto
   - Calificación en estrellas SVG
   - Diseño en tarjetas con carousel o grid masonry
   - Cita destacada más grande para el testimonio principal

9. PRECIOS — TABLA DE PLANES (si aplica)
   - 3 planes (Básico, Pro, Enterprise) con toggle Mensual/Anual
   - Resaltar plan recomendado con badge "Más Popular"
   - Lista de features con checkmarks SVG coloridos
   - CTA por cada plan
   - Garantía (ej: "30 días de prueba gratuita sin tarjeta de crédito")

10. FAQ — PREGUNTAS FRECUENTES
    - 5-7 preguntas relevantes al negocio con acordeón animado
    - Diseño limpio con líneas separadoras sutiles

11. CTA FINAL — SECCIÓN DE CONVERSIÓN
    - Headline poderoso orientado a urgencia o transformación
    - Formulario de captura: nombre, email, (teléfono opcional), botón CTA grande
    - Elementos de confianza: candado SSL, sin spam, garantía
    - Fondo contrastante dramático con la identidad visual

12. FOOTER COMPLETO
    - Logo + tagline
    - 4 columnas: Producto, Empresa, Recursos, Legal
    - Redes sociales con iconos SVG animados
    - Newsletter signup inline
    - Copyright y links de privacidad/términos

══════════════════════════════════════════════════════════
 COPYWRITING Y MARKETING
══════════════════════════════════════════════════════════

- Escribe copy real y específico para "{name}", NO texto placeholder genérico
- Aplica fórmulas probadas: AIDA (Atención-Interés-Deseo-Acción), PAS (Problema-Agitación-Solución)
- Cada CTA debe ser específico y orientado a beneficio ("Empieza a crecer hoy", NO "Enviar")
- Integra palabras clave de SEO de forma natural en headings y párrafos
- Microcopy de confianza: "Sin tarjeta de crédito", "Cancela cuando quieras", "Soporte 24/7"

══════════════════════════════════════════════════════════
 ESPECIFICACIONES TÉCNICAS
══════════════════════════════════════════════════════════

CÓDIGO:
- HTML5 semántico completo (un solo archivo .html autocontenido)
- CSS3 moderno con variables CSS (--color-primary, etc.), Flexbox y Grid
- JavaScript vanilla ES6+ sin dependencias externas
- Google Fonts via @import en el CSS
- Todos los iconos como SVG inline (NO FontAwesome, NO imágenes externas)
- Intersection Observer para animaciones on-scroll
- Formulario con validación JS y feedback visual

RESPONSIVE DESIGN:
- Mobile-first con breakpoints: 480px, 768px, 1024px, 1440px
- Navegación hamburger en móvil completamente funcional
- Imágenes y tipografías fluidas con clamp()
- Touch-friendly en todos los elementos interactivos

SEO Y PERFORMANCE:
- Meta tags completos: title, description, og:tags, twitter:card
- Schema.org markup para LocalBusiness o SoftwareApplication
- Atributos alt descriptivos en todas las imágenes
- Lazy loading en imágenes
- Estructura de headings H1→H2→H3 correcta

ACCESIBILIDAD:
- Roles ARIA en elementos interactivos
- Focus styles visibles
- Contraste de colores WCAG AA mínimo
- Skip navigation link

══════════════════════════════════════════════════════════
 INSTRUCCIONES DE ENTREGA
══════════════════════════════════════════════════════════

Entrega:
1. Primero, un BRIEF DE DISEÑO (10-15 líneas): paleta de colores elegida con HEX, tipografías, dirección estética y concepto general de la marca.
2. Luego, el CÓDIGO HTML COMPLETO del archivo index.html (todo en un solo archivo, incluyendo <style> y <script>).
3. Al final, una GUÍA DE IMPLEMENTACIÓN: cómo reemplazar los placeholders de imágenes por las generadas con IA, y qué imágenes específicas se necesitan generadas (con sus prompts sugeridos para Midjourney/DALL-E).

El código debe estar listo para abrirse en el navegador sin configuración adicional y verse de forma extraordinaria. Prioriza calidad visual y conversión sobre simplicidad de código.""",

        "10_tienda_virtual": f"""Actúa como un equipo élite combinando: Arquitecto de E-Commerce Senior, Diseñador UI/UX especialista en tiendas online, Desarrollador Full-Stack con experiencia en comercio electrónico, Experto en UX de conversión (CRO), Copywriter de producto y Estratega de marketing digital para ventas online.

NEGOCIO: {{name}}
DESCRIPCIÓN: {{desc}}

Tu misión es generar el CÓDIGO COMPLETO HTML/CSS/JavaScript de una tienda virtual completamente funcional, visualmente extraordinaria, fácil de usar e intuitiva — todo en un único archivo autocontenido listo para abrir en el navegador.

══════════════════════════════════════════════════════════════
 IDENTIDAD VISUAL Y ESTÉTICA DE LA TIENDA
══════════════════════════════════════════════════════════════

DISEÑO DE MARCA:
- Crea una paleta de colores premium y coherente al negocio "{{name}}" (primario, secundario, acento, fondo, texto con códigos HEX).
- Tipografías exclusivas vía Google Fonts: una display para títulos y precios, una sans-serif legible para descripciones. NUNCA uses Inter, Roboto ni Arial.
- Logo integrado como SVG inline en el header con isologotipo de texto estilizado que luzca como una marca real de e-commerce.
- Iconografía SVG inline personalizada para carrito, wishlist, búsqueda, usuario, estrellas, filtros, categorías. NUNCA uses FontAwesome.
- Placeholders de imágenes de producto con CSS gradient art + descripción del tipo de foto (fondo blanco, lifestyle, detalle, etc.).
- Estética diferenciada: luxury/minimalista, bold/colorida, editorial/magazine, tech/moderna, boutique/artesanal — la que mejor represente al negocio.

ATMÓSFERA Y MOTION:
- Animaciones CSS fluidas: fade-in de productos al scroll (Intersection Observer), hover cards con zoom suave + sombra elevada, skeleton loading simulado.
- Micro-interacciones: botón "Agregar al carrito" con efecto bounce + cambio de estado, animación de corazón en wishlist, badge del carrito con pulso al agregar item.
- Fondo con profundidad: gradiente sutil, patrón geométrico fino o textura que no compita con los productos.

══════════════════════════════════════════════════════════════
 ARQUITECTURA Y PÁGINAS DE LA TIENDA (single-page app)
══════════════════════════════════════════════════════════════

Implementa las siguientes VISTAS navegables con JavaScript (router simple con hashchange):

━━━ VISTA 1 — HOME ━━━
- Hero banner rotativo (3 slides, autoplay, indicadores, flechas) con headline + CTA + countdown de oferta
- Barra de beneficios: envío gratis / devoluciones / pago seguro / soporte 24h (iconos SVG)
- Categorías destacadas: grid 4-6 con imagen placeholder y nombre
- Productos más vendidos: carrusel horizontal de 8 tarjetas
- Banner de oferta especial con urgencia y CTA
- Nuevos productos: grid 4 columnas
- ¿Por qué elegirnos?: 4 íconos SVG + título + descripción
- Testimonios: 3 cards con foto placeholder, nombre, ciudad, estrellas y texto
- Newsletter signup con validación JS y mensaje de confirmación

━━━ VISTA 2 — CATÁLOGO ━━━
- Breadcrumb + toolbar (resultados, ordenar, toggle grid/lista)
- Sidebar de filtros desktop / drawer animado móvil:
  * Categoría (checkboxes con conteo), precio (slider dual range), rating, disponibilidad
  * Botones "Aplicar" y "Limpiar"
- Grid productos (4/2/1 col por breakpoint): badge dinámico, wishlist toggle, rating, precio tachado/actual, botones "Ver" y "Agregar"
- Paginación con números
- Estado vacío con ilustración SVG y CTA
- Quick-view modal al pasar cursor sobre la tarjeta

━━━ VISTA 3 — DETALLE DE PRODUCTO ━━━
- Galería: imagen principal + 4 miniaturas clicables + zoom hover
- Badge disponibilidad y stock restante
- Selector de variantes (color/talla), selector de cantidad +-
- CTAs: "Agregar al carrito" (primario) + "Wishlist"
- Información de envío con campo de ciudad
- Badges de confianza: SSL / devolución 30 días / envío asegurado
- Tabs: Descripción / Especificaciones / Reseñas / FAQ
- Sección reseñas: 4 reviews + formulario para dejar reseña
- Productos relacionados: carrusel 4 items

━━━ VISTA 4 — CARRITO ━━━
- Lista de items: imagen, nombre, variante, cantidad (/+), subtotal, eliminar
- Campo de cupón con validación JS (código "PROMO20" = 20% off)
- Resumen: subtotal, descuento, envío, impuesto, TOTAL en tiempo real
- Barra de progreso "Faltan $X para envío gratis"
- CTAs: "Seguir comprando" + "Ir al pago"
- Estado vacío + sugerencias de productos

━━━ VISTA 5 — CHECKOUT ━━━
- Stepper: Información → Envío → Pago → Confirmación
- Paso 1: datos del comprador (nombre, email, teléfono)
- Paso 2: dirección + opciones de envío (estándar/express/recogida) con costos y días
- Paso 3: método de pago en tabs (tarjeta / PSE / transferencia / contra entrega)
  * Form de tarjeta con formateo automático y visualización 3D animada que voltea al ingresar CVV
- Paso 4: confirmación con número de orden, estimado de entrega y CTA volver a tienda

━━━ VISTA 6 — WISHLIST ━━━
- Grid de favoritos con botón "Agregar al carrito" y "Eliminar"
- Botón "Agregar todo al carrito"

━━━ MODAL MI CUENTA ━━━
- Tabs: Login / Registro (solo UI, sin backend)

══════════════════════════════════════════════════════════════
 COMPONENTES GLOBALES
══════════════════════════════════════════════════════════════

HEADER FIJO:
- Logo SVG + barra de búsqueda central con autocompletado JS + iconos cuenta/wishlist/carrito con contadores
- Mega-menú hover desktop con subcategorías + featured product
- Hamburger fullscreen en móvil

BANNER SUPERIOR DISMISSIBLE: oferta + código promocional + botón X (localStorage)

FOOTER: logo, 4 columnas de links, métodos de pago SVG, newsletter, redes, copyright

SISTEMAS GLOBALES:
- Toast notifications apilables (esquina sup der, auto-dismiss 3s)
- Botón "volver arriba" flotante (aparece > 300px scroll)
- Modal de búsqueda con overlay y resultados en tiempo real
- Skeleton loading: simular carga de productos 500ms

══════════════════════════════════════════════════════════════
 CATÁLOGO DE DATOS
══════════════════════════════════════════════════════════════

Genera en JavaScript un catálogo de MÍNIMO 20 PRODUCTOS coherentes con "{{name}}" y su descripción. Cada producto debe tener: id, nombre, categoría, precio original, precio oferta, descripción, rating (4.0-5.0), numReseñas, stock, variantes, tags, esNuevo, esOferta, imagenDesc (descripción del placeholder).
Organiza en 4-6 CATEGORÍAS lógicas con nombre, descripción e ícono SVG path.

══════════════════════════════════════════════════════════════
 FUNCIONALIDADES JAVASCRIPT REQUERIDAS
══════════════════════════════════════════════════════════════

- Router SPA (hashchange/history API)
- Estado global carrito: agregar, quitar, actualizar, vaciar, persistir localStorage
- Estado wishlist: toggle, persistir localStorage
- Contadores header en tiempo real
- Filtros catálogo: categoría, rango precio, rating — en tiempo real
- Ordenamiento: precio asc/desc, popularidad, novedad
- Toggle vista grid/lista
- Buscador: filtrado en tiempo real por nombre/categoría/tag + autocompletado
- Countdown de oferta con setInterval
- Contador animado de métricas (Intersection Observer)
- Carrusel hero: autoplay 4s + manual + indicadores
- Carrusel relacionados con drag/swipe en móvil
- Validación completa de checkout: email, teléfono, campos requeridos
- Cupón de descuento con validación y aplicación al total
- Animación tarjeta 3D en checkout (flip al ingresar CVV)
- Toast notifications apilables
- Skeleton loading (setTimeout 500ms)
- Quick-view modal de producto
- Acordeón FAQ con animación de altura
- Tabs de producto suaves
- Galería de producto con thumbnail click + zoom
- Persistir preferencia grid/lista en localStorage

══════════════════════════════════════════════════════════════
 RESPONSIVE Y ACCESIBILIDAD
══════════════════════════════════════════════════════════════

- Mobile-first, breakpoints: 480px / 768px / 1024px / 1280px / 1440px
- Grid productos: 1 col (móvil) / 2 col (tablet) / 3-4 col (desktop)
- Sidebar filtros → drawer en móvil
- Touch/swipe en carruseles
- Botones y áreas táctiles mínimo 44px
- Roles ARIA, labels en inputs, focus trap en modales, contraste WCAG AA

══════════════════════════════════════════════════════════════
 SEO Y META TAGS
══════════════════════════════════════════════════════════════

- Title y meta description actualizados por vista con JS
- Open Graph y Twitter Card
- Schema.org: Organization + WebSite + Product
- Breadcrumb structured data

══════════════════════════════════════════════════════════════
 INSTRUCCIONES DE ENTREGA
══════════════════════════════════════════════════════════════

Entrega en este orden:

1. BRIEF DE DISEÑO E-COMMERCE (15 líneas):
   Nombre tienda, slogan, paleta HEX completa, tipografías elegidas, estética, concepto visual.

2. JSON DEL CATÁLOGO:
   Array de 20+ productos con todos sus campos + array de categorías con ícono SVG path.

3. CÓDIGO HTML COMPLETO (un solo archivo index.html):
   HTML semántico + <style> CSS completo + <script> JS completo. Sin dependencias externas (solo Google Fonts por @import). Funcional al abrir directamente en navegador.

4. GUÍA DE IMÁGENES:
   Lista de todas las imágenes necesarias (20+ productos + 3 banners + 6 categorías).
   Para cada imagen: prompt en español listo para Midjourney/DALL-E 3/Firefly.
   Instrucciones de cómo reemplazar placeholders CSS.

5. GUÍA DE INTEGRACIÓN DE PAGO:
   Cómo conectar con MercadoPago, PayU, Wompi (Colombia) o Stripe.
   Snippet de código de ejemplo para cada pasarela.

La tienda debe ser FUNCIONAL, HERMOSA e INTUITIVA: cualquier persona puede navegar, filtrar, comprar y pagar sin necesitar instrucciones.""",
    }


SECTION_META = {
    "1_resumen_ejecutivo":    ("📋", "Resumen Ejecutivo",      "#3b82f6"),
    "2_mercados_objetivo":    ("🎯", "Mercados Objetivo",       "#8b5cf6"),
    "3_analisis_competitivo": ("⚔️",  "Análisis Competitivo",   "#10b981"),
    "4_propuesta_de_valor":   ("💡", "Propuesta de Valor",     "#f59e0b"),
    "5_plan_de_accion":       ("🗺️", "Plan de Acción",         "#f43f5e"),
    "6_desarrollo_negocio":   ("🚀", "Desarrollo del Negocio", "#06b6d4"),
    "7_prompt_imagen_logo":   ("🎨", "Imagen & Logo",          "#ec4899"),
    "8_prompt_video":         ("🎬", "Prompts de Video",       "#a855f7"),
    "9_landing_page":         ("🌐", "Landing Page / Web",     "#22c55e"),
    "10_tienda_virtual":      ("🛒", "Tienda Virtual",         "#f97316"),
}


# ──────────────────────────────────────────────
# Estado de sesión
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "prompts_generados": None,
        "negocio": "",
        "descripcion": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ──────────────────────────────────────────────
# Sidebar — modelo y historial
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 Seleccionar Modelo IA")
    st.markdown("*El prompt se copiará listo para pegar en la plataforma elegida.*")
    modelo_sel = st.selectbox(
        "Plataforma destino:",
        list(AI_MODELS.keys()),
        index=0,
    )
    url_modelo = AI_MODELS[modelo_sel]
    st.markdown(f'<div class="model-badge">{modelo_sel}</div>', unsafe_allow_html=True)
    st.markdown(f"[🔗 Abrir {modelo_sel.split(' ')[1]}]({url_modelo})", unsafe_allow_html=False)

    st.markdown("---")
    st.markdown("## 📚 Historial Guardado")
    historial = load_all_prompts()
    if historial:
        for row in historial[:10]:
            pid, neg, mod, fecha = row
            fecha_fmt = fecha[:16].replace("T", " ")
            if st.button(f"📄 #{pid} {neg[:20]}… ({fecha_fmt})", key=f"hist_{pid}", use_container_width=True):
                data = load_prompt_by_id(pid)
                if data:
                    st.session_state.prompts_generados = json.loads(data[3])
                    st.session_state.negocio = data[1]
                    st.session_state.descripcion = data[2]
                    st.rerun()
    else:
        st.caption("Aún no hay prompts guardados.")

    st.markdown("---")
    st.caption("Generador de Prompts · Plan de Negocio IA")


# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
_, col_h, _ = st.columns([1, 3, 1])
with col_h:
    st.markdown("""
    <div style='text-align:center; padding: 8px 0 28px;'>
        <div style='display:inline-block; padding:6px 18px;
                    background:rgba(37,99,235,0.18);
                    border:1px solid rgba(37,99,235,0.35);
                    border-radius:20px; font-size:13px;
                    font-weight:700; color:#93c5fd; margin-bottom:14px;'>
            🧠 Generador Inteligente de Prompts
        </div>
        <h1 style='font-size:clamp(24px,5vw,44px); font-weight:900; margin:10px 0;
                   background:linear-gradient(90deg,#93c5fd,#c4b5fd,#f9a8d4);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
            Plan de Negocio · Prompts Completos
        </h1>
        <p style='color:#94a3b8; font-size:16px; margin:0;'>
            Describe tu negocio y obtén 10 prompts listos para cualquier IA
        </p>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Formulario de entrada
# ──────────────────────────────────────────────
with st.container():
    st.markdown('<div class="plan-card">', unsafe_allow_html=True)
    st.markdown("### 🏢 Información del Negocio")
    st.caption("Estos datos se usarán para personalizar todos los prompts generados.")
    st.markdown("---")

    col1, col2 = st.columns([1, 2])
    with col1:
        negocio = st.text_input(
            "Nombre del Negocio *",
            placeholder="Ej: EduTech Colombia",
            value=st.session_state.negocio,
            key="input_negocio",
        )
    with col2:
        descripcion = st.text_area(
            "Descripción del Negocio *",
            placeholder=(
                "¿Qué hace tu negocio? ¿A quién va dirigido? ¿Cuál es tu propuesta de valor? "
                "¿En qué etapa está? ¿Cuál es el modelo de ingresos?..."
            ),
            value=st.session_state.descripcion,
            height=120,
            key="input_descripcion",
        )

    chars = len(descripcion.strip())
    color_ind = "🟢" if chars >= 50 else ("🟡" if chars >= 20 else "🔴")
    st.caption(f"{color_ind} {chars} / 50 caracteres mínimos recomendados")

    st.markdown('<br>', unsafe_allow_html=True)
    col_btn1, col_btn2, _ = st.columns([2, 2, 4])
    with col_btn1:
        generar = st.button("🚀 Generar Prompts", type="primary", use_container_width=True)
    with col_btn2:
        limpiar = st.button("🗑️ Limpiar", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

if limpiar:
    st.session_state.prompts_generados = None
    st.session_state.negocio = ""
    st.session_state.descripcion = ""
    st.rerun()

if generar:
    if not negocio.strip():
        st.error("❌ El nombre del negocio es obligatorio.")
    elif chars < 20:
        st.error("❌ La descripción debe tener al menos 20 caracteres.")
    else:
        with st.spinner("⚙️ Construyendo prompts personalizados..."):
            prompts = build_prompts(negocio.strip(), descripcion.strip())
            st.session_state.prompts_generados = prompts
            st.session_state.negocio = negocio.strip()
            st.session_state.descripcion = descripcion.strip()
        st.success("✅ ¡10 prompts generados exitosamente!")
        st.rerun()


# ──────────────────────────────────────────────
# Mostrar prompts generados
# ──────────────────────────────────────────────
if st.session_state.prompts_generados:
    prompts = st.session_state.prompts_generados
    nombre = st.session_state.negocio
    desc_neg = st.session_state.descripcion

    st.markdown("---")

    # ── Acciones globales ──
    col_tit, col_save, col_dl = st.columns([3, 1.5, 1.5])
    with col_tit:
        st.markdown(f"## 📦 Prompts para: **{nombre}**")
        st.caption(f"Modelo destino seleccionado: {modelo_sel}  ·  [Abrir plataforma]({url_modelo})")
    with col_save:
        if st.button("💾 Guardar en SQLite", type="primary", use_container_width=True):
            pid = save_prompts(nombre, desc_neg, prompts, modelo_sel)
            st.success(f"✅ Guardado con ID #{pid}")
    with col_dl:
        # Armar texto plano para descarga
        txt_lines = [
            f"PLAN DE NEGOCIO — PROMPTS GENERADOS POR IA",
            f"{'='*60}",
            f"Negocio: {nombre}",
            f"Descripción: {desc_neg}",
            f"Modelo destino: {modelo_sel}",
            f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"{'='*60}\n",
        ]
        for key, texto in prompts.items():
            _, label, _ = SECTION_META.get(key, ("", key, ""))
            txt_lines.append(f"\n{'─'*60}")
            txt_lines.append(f"  PROMPT: {label.upper()}")
            txt_lines.append(f"{'─'*60}\n")
            txt_lines.append(texto)
            txt_lines.append("\n")
        txt_content = "\n".join(txt_lines)

        st.download_button(
            label="⬇️ Descargar .txt",
            data=txt_content.encode("utf-8"),
            file_name=f"prompts_{nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.markdown("---")
    st.info(
        f"💡 **Cómo usar:** Copia cada prompt con el botón 📋, ábrelo en **{modelo_sel}** "
        f"([{url_modelo}]({url_modelo})) y pégalo directamente en el chat.",
        icon="ℹ️"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Sección por sección ──
    for key, texto in prompts.items():
        icono, label, color = SECTION_META.get(key, ("📄", key, "#2563eb"))

        with st.expander(f"{icono} {label}", expanded=(key == "1_resumen_ejecutivo")):
            col_lbl, col_copy = st.columns([5, 1])
            with col_lbl:
                st.markdown(
                    f'<span class="section-badge" style="border-color:{color}40; color:{color};">'
                    f'{icono} {label.upper()}</span>',
                    unsafe_allow_html=True,
                )
            with col_copy:
                # Streamlit no tiene copy-to-clipboard nativo; usamos JS via components
                st.markdown(
                    f"""
                    <button onclick="navigator.clipboard.writeText(`{texto.replace('`', "'")}`).then(()=>this.innerText='✅ Copiado!').catch(()=>this.innerText='❌ Error')"
                    style="padding:6px 14px; border-radius:8px; background:rgba(37,99,235,0.35);
                           border:1px solid rgba(37,99,235,0.5); color:#93c5fd; cursor:pointer;
                           font-size:13px; font-weight:600; width:100%;">
                        📋 Copiar
                    </button>
                    """,
                    unsafe_allow_html=True,
                )

            # Mostrar prompt en caja de código
            st.markdown(f'<div class="prompt-box">{texto.replace("<","&lt;").replace(">","&gt;")}</div>', unsafe_allow_html=True)

            # Botón de descarga individual
            st.download_button(
                label=f"⬇️ Descargar este prompt",
                data=texto.encode("utf-8"),
                file_name=f"prompt_{key}_{nombre.replace(' ', '_')}.txt",
                mime="text/plain",
                key=f"dl_{key}",
            )

    # ── Pie ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"""<div style='text-align:center; padding:20px 0; color:#64748b; font-size:13px;'>
            Generado con <strong>Generador de Prompts · Plan de Negocio IA</strong> ·
            Úsalos en {modelo_sel}
        </div>""",
        unsafe_allow_html=True,
    )
