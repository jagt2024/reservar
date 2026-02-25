"""
Plan de Negocio Estratégico — Versión Free (sin API Key)
========================================================= Ejemplo:
Espacios de descanso personales en cabinas o espacios individuales, que funcionara al interior de una terminal de trasportes, mientras esperas la salida de tu transporte, tendrá un servicio de 24 horas, se cobrará por hora y tendrás acceso a baño, conexión de internet y carga de tú celular, portátil o tableta
"""

import streamlit as st
import io
import re
import time
from datetime import datetime

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_JUSTIFY

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Plan Estratégico de Negocio",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
  .stApp { background: #0a0e1a; color: #e8eaf0; }

  .hero {
    background: linear-gradient(135deg, #0d1b2e 0%, #1a2a4a 50%, #0f2040 100%);
    border: 1px solid rgba(99,179,237,0.18);
    border-radius: 20px;
    padding: 3rem 3.5rem 2.5rem;
    margin-bottom: 2.5rem;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(99,179,237,0.08) 0%, transparent 70%);
    border-radius: 50%;
  }
  .hero-tag {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #63b3ed;
    background: rgba(99,179,237,0.1);
    border: 1px solid rgba(99,179,237,0.25);
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 20px;
    margin-bottom: 1rem;
  }
  .hero h1 {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 900;
    color: #f0f4ff;
    line-height: 1.15;
    margin: 0 0 0.8rem;
  }
  .hero p {
    font-size: 1.05rem;
    color: rgba(232,234,240,0.65);
    font-weight: 300;
    max-width: 520px;
    margin: 0;
    line-height: 1.7;
  }
  .free-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6ee7b7;
    background: rgba(16,185,129,0.12);
    border: 1px solid rgba(16,185,129,0.3);
    padding: 0.28rem 0.85rem;
    border-radius: 20px;
    margin-left: 0.7rem;
    vertical-align: middle;
  }
  .card {
    background: #111827;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.5rem;
  }
  .card-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #c9d6f5;
    margin-bottom: 0.3rem;
  }
  .card-sub { font-size: 0.82rem; color: rgba(200,210,230,0.45); margin-bottom: 1.2rem; }

  textarea, input[type="text"] {
    background: #1a2235 !important;
    border: 1.5px solid rgba(99,179,237,0.2) !important;
    border-radius: 10px !important;
    color: #e8eaf0 !important;
    font-family: 'DM Sans', sans-serif !important;
  }
  textarea:focus, input[type="text"]:focus {
    border-color: rgba(99,179,237,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,179,237,0.08) !important;
  }
  label { color: #a8b8d8 !important; font-size: 0.88rem !important; font-weight: 500 !important; }

  .stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border-radius: 10px !important;
    padding: 0.65rem 1.8rem !important;
    transition: all 0.22s ease !important;
    border: none !important;
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: white !important;
    box-shadow: 0 4px 18px rgba(37,99,235,0.35) !important;
  }
  .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 25px rgba(37,99,235,0.5) !important;
  }
  .stDownloadButton > button {
    background: linear-gradient(135deg, #065f46, #047857) !important;
    color: white !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 0.65rem 1.8rem !important;
    box-shadow: 0 4px 18px rgba(6,95,70,0.4) !important;
    transition: all 0.22s !important;
    border: none !important;
  }
  .stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 25px rgba(6,95,70,0.55) !important;
  }
  .result-wrapper {
    background: #0f1926;
    border: 1px solid rgba(99,179,237,0.12);
    border-radius: 16px;
    padding: 2.5rem;
    margin-top: 1.5rem;
  }
  .section-chip {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; padding: 0.28rem 0.85rem;
    border-radius: 20px; margin-bottom: 0.8rem;
  }
  .chip-blue   { background: rgba(59,130,246,0.15);  color: #93c5fd; border: 1px solid rgba(59,130,246,0.25); }
  .chip-purple { background: rgba(139,92,246,0.15);  color: #c4b5fd; border: 1px solid rgba(139,92,246,0.25); }
  .chip-green  { background: rgba(16,185,129,0.15);  color: #6ee7b7; border: 1px solid rgba(16,185,129,0.25); }
  .chip-amber  { background: rgba(245,158,11,0.15);  color: #fcd34d; border: 1px solid rgba(245,158,11,0.25); }
  .chip-rose   { background: rgba(244,63,94,0.15);   color: #fda4af; border: 1px solid rgba(244,63,94,0.25); }
  .section-heading {
    font-family: 'Playfair Display', serif; font-size: 1.45rem;
    font-weight: 700; color: #dde6ff; margin: 0 0 0.7rem; line-height: 1.3;
  }
  .section-body {
    font-size: 0.93rem; color: rgba(210,220,240,0.82);
    line-height: 1.82; white-space: pre-wrap;
  }
  .divider { border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 2rem 0; }
  .stSpinner > div { border-top-color: #3b82f6 !important; }
  .stAlert { border-radius: 10px !important; }
  .footer {
    text-align: center; font-size: 0.78rem;
    color: rgba(150,165,195,0.4); padding: 2rem 0 1rem;
    border-top: 1px solid rgba(255,255,255,0.05); margin-top: 3rem;
  }
  .prog-bar-wrap {
    background: #111827; border: 1px solid rgba(99,179,237,0.15);
    border-radius: 12px; padding: 1.2rem 1.5rem; margin: 0.5rem 0;
  }
  .prog-label {
    font-size: 0.78rem; color: #63b3ed; font-weight: 600;
    letter-spacing: 0.1em; margin-bottom: 0.7rem;
  }
  .prog-track {
    background: #1e293b; border-radius: 6px; height: 6px; overflow: hidden;
  }
  .prog-fill {
    height: 100%; border-radius: 6px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    transition: width 0.3s;
  }
  .prog-step { display: flex; align-items: center; gap: 0.7rem;
               padding: 0.5rem 0; font-size: 0.85rem; color: rgba(200,215,240,0.7); }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════
SECTIONS = [
    ("📋", "RESUMEN EJECUTIVO",              "chip-blue"),
    ("🎯", "MERCADOS OBJETIVO PRIORITARIOS", "chip-purple"),
    ("⚔️",  "ANÁLISIS COMPETITIVO",           "chip-green"),
    ("💡", "PROPUESTA DE VALOR ÚNICA",       "chip-amber"),
    ("🗺️", "PLAN DE ACCIÓN ESTRATÉGICO",     "chip-rose"),
]


# ═══════════════════════════════════════════════════════════════════════════
#  MOTOR DE GENERACIÓN LOCAL — sin dependencias externas ni API key
# ═══════════════════════════════════════════════════════════════════════════

def _detectar_sector(desc: str) -> str:
    desc_l = desc.lower()
    mapa = {
        "tecnología":                       ["software","app","tecnolog","saas","plataform","digital","ia ","inteligencia artificial","datos","desarrollo web","ecommerce","e-commerce"],
        "gastronomía":                      ["restaurant","comida","gastronom","aliment","bebida","café","catering","cocina","delivery","food"],
        "salud y bienestar":                ["salud","médic","clínic","farmac","bienestar","fitness","gym","deporte","terapia","nutrici"],
        "educación":                        ["educac","capacitac","curso","enseñanza","academia","formac","tutoría","aprendizaje","e-learning"],
        "comercio y retail":                ["retail","tienda","venta al detalle","comercio","producto físico","artesanía","moda","ropa","calzado"],
        "construcción e inmobiliaria":      ["construcc","inmobiliar","arquitect","propiedad","vivienda","edificio","obra","bienes raíces"],
        "logística y transporte":           ["logístic","transport","envío","distribuc","supply chain","mensajería","flete","almacenamiento"],
        "finanzas y servicios financieros": ["finanz","banco","crédit","invers","seguro","contabil","fintech","ahorro","préstamo"],
        "marketing y comunicaciones":       ["market","publicidad","agencia","branding","comunicac","redes sociales","contenido","seo","campaña"],
        "consultoría y servicios profesionales": ["consultor","asesor","servicio profesional","legal","jurídic","auditor","outsourc","rrhh","recursos humanos"],
        "turismo y hospitalidad":           ["turismo","hotel","hostal","viaje","tour","agencia de viaje","hospedaje"],
        "manufactura e industria":          ["manufactur","industria","fábrica","producción","planta","maquinaria","insumo"],
    }
    for sector, kws in mapa.items():
        if any(kw in desc_l for kw in kws):
            return sector
    return "servicios generales"


def _keywords(desc: str) -> list:
    stop = {"de","la","el","en","y","a","los","las","un","una","que","con","por","para",
            "su","se","es","al","del","le","lo","nos","pero","más","ya","como","este",
            "esta","esto","son","ser","está","fue","tiene","tenemos"}
    words = re.findall(r'\b[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]{4,}\b', desc)
    seen, result = set(), []
    for w in words:
        wl = w.lower()
        if wl not in stop and wl not in seen:
            seen.add(wl)
            result.append(w)
    return result[:10]


def _anio() -> int:
    return datetime.now().year


# ─── Sección 1: Resumen Ejecutivo ─────────────────────────────────────────
def _resumen_ejecutivo(nombre: str, desc: str, sector: str) -> str:
    anio = _anio()
    return f"""**Visión General del Negocio**

{nombre} es una organización enfocada en el sector de {sector}, cuya propuesta central se fundamenta en: {desc.strip()}.

En el contexto económico de {anio}, el sector de {sector} atraviesa una etapa de transformación acelerada impulsada por la digitalización, los cambios en los patrones de consumo y una mayor exigencia de personalización por parte de los clientes. {nombre} se posiciona estratégicamente para capturar valor en este entorno dinámico.

**Misión**

Proveer soluciones de alto impacto en el ámbito de {sector}, generando valor sostenible para clientes, colaboradores y la comunidad, a través de innovación continua y excelencia operativa.

**Visión a 5 Años**

Consolidarse como un referente reconocido a nivel regional en {sector}, con presencia en al menos tres mercados geográficos, una base de clientes fidelizada superior al 70% y márgenes operativos que permitan financiar la expansión orgánica.

**Objetivos Estratégicos Clave**

• Alcanzar rentabilidad operativa sostenida dentro de los primeros 18 meses.
• Expandir la oferta con al menos 2 nuevas líneas de producto/servicio en el primer año.
• Construir una marca reconocible con NPS (Net Promoter Score) superior a 50 puntos.
• Establecer alianzas estratégicas con al menos 3 actores clave del ecosistema de {sector}.
• Digitalizar el 80% de los procesos internos para mejorar eficiencia y trazabilidad.
• Alcanzar una tasa de retención de clientes igual o superior al 75% anual.

**Modelo de Negocio Resumido**

La propuesta de valor de {nombre} descansa sobre tres pilares fundamentales: (1) diferenciación por calidad y especialización en {sector}; (2) accesibilidad y facilidad de acceso para el cliente objetivo; (3) escalabilidad del modelo que permita crecer sin pérdida de estándares. Los ingresos se generarán a través de una combinación de ventas directas, contratos recurrentes y potenciales fuentes de ingresos pasivos conforme madure la operación.

**Indicadores de Éxito (KPIs Principales)**

Los siguientes indicadores serán utilizados para monitorear el desempeño estratégico de {nombre}:
• Tasa de crecimiento mensual de ingresos: objetivo ≥ 8%
• Costo de adquisición de cliente (CAC): reducir un 20% año sobre año
• Valor de vida del cliente (LTV): objetivo 5x el CAC
• Tasa de retención de clientes: ≥ 75% anual
• Satisfacción del cliente: puntuación ≥ 4.2 / 5.0
• Margen bruto operativo: ≥ 40% en el segundo año"""


# ─── Sección 2: Mercados Objetivo ─────────────────────────────────────────
def _mercados_objetivo(nombre: str, desc: str, sector: str) -> str:
    anio = _anio()
    mercados_por_sector = {
        "tecnología":                       ["Pymes en proceso de digitalización","Startups B2B y B2C con necesidades de escala","Corporaciones optimizando procesos con IA y automatización","Sector público en transformación digital"],
        "gastronomía":                      ["Consumidores urbanos millennials y Gen Z","Turistas nacionales e internacionales","Empresas para servicios de catering corporativo","Plataformas de delivery y operadores dark kitchen"],
        "salud y bienestar":                ["Adultos de 25-55 años con estilo de vida activo","Empresas con programas de bienestar corporativo","Adultos mayores con necesidades de atención preventiva","Instituciones educativas con programas de salud"],
        "educación":                        ["Profesionales buscando upskilling y certificaciones","Jóvenes de 18-30 años con orientación a empleo","Empresas con necesidades de capacitación corporativa","Instituciones educativas buscando alianzas y contenido"],
        "comercio y retail":                ["Consumidores finales B2C online y offline","Distribuidores y mayoristas regionales","Marketplaces y plataformas de ecommerce","Compradores corporativos B2B con compras recurrentes"],
        "construcción e inmobiliaria":      ["Familias de clase media buscando primera vivienda","Inversores inmobiliarios institucionales y privados","Empresas buscando oficinas, locales o bodegas","Desarrolladores que necesitan insumos o servicios especializados"],
        "logística y transporte":           ["Ecommerce y retailers con necesidades de última milla","Industria manufacturera con cadenas de suministro complejas","Sector agropecuario con distribución de productos perecederos","Empresas importadoras y exportadoras"],
        "finanzas y servicios financieros": ["Pymes sin acceso adecuado a financiamiento tradicional","Personas naturales no bancarizadas o sub-bancarizadas","Startups que necesitan servicios financieros ágiles y modernos","Inversores buscando alternativas de rentabilidad diversificada"],
        "marketing y comunicaciones":       ["Pymes con necesidad de posicionamiento digital","Marcas en proceso de rebranding o lanzamiento","Startups que ingresan al mercado y requieren visibilidad","Corporaciones con campañas estacionales y activaciones"],
        "consultoría y servicios profesionales": ["Empresas medianas en transformación organizacional","Startups buscando mentoring, estructura y aceleración","Organizaciones sin fines de lucro con necesidades de eficiencia","Organismos gubernamentales con proyectos de modernización"],
        "turismo y hospitalidad":           ["Turistas nacionales con tendencia a viajes internos","Viajeros internacionales de segmento medio-alto","Empresas con necesidades de turismo corporativo y eventos","Agencias de viaje buscando proveedores locales confiables"],
        "manufactura e industria":          ["Empresas industriales buscando eficiencia productiva","Distribuidores nacionales de insumos y materiales","Sector exportador con necesidades de calidad certificada","Grandes constructoras y contratistas con demanda sostenida"],
        "servicios generales":              ["Consumidores B2C en segmento socioeconómico medio-alto","Pymes que externalizan funciones no core","Corporaciones con necesidades específicas puntuales","Organismos públicos con licitaciones y compras regulares"],
    }
    segmentos = mercados_por_sector.get(sector, mercados_por_sector["servicios generales"])

    return f"""**Marco de Análisis de Mercado (TAM-SAM-SOM)**

La identificación de mercados objetivo para {nombre} se realizó aplicando el modelo TAM-SAM-SOM (Total Addressable Market, Serviceable Available Market, Serviceable Obtainable Market), combinado con criterios de atractividad: tamaño, tasa de crecimiento, accesibilidad, rentabilidad potencial y alineación estratégica con las capacidades actuales de la empresa.

**Mercado Total Disponible (TAM)**

El sector de {sector} en América Latina registró tasas de crecimiento promedio del 12-18% anual en el período {anio-3}-{anio}, con proyecciones de continuar expandiéndose impulsado por: mayor conectividad, expansión de la clase media, adopción tecnológica acelerada y cambios regulatorios favorables a nuevos actores.

**Segmentos Prioritarios Identificados para {nombre}**

**1. {segmentos[0]} — Prioridad ALTA ⭐⭐⭐**
Este segmento representa la base inmediata y natural de clientes de {nombre}. Sus características clave son: alta disposición a pagar por soluciones de calidad comprobada, ciclo de venta relativamente corto, potencial de referidos orgánicos elevado y baja saturación competitiva en nichos específicos. Estrategia de entrada recomendada: marketing directo, demostraciones de producto/servicio, programas de prueba piloto y casos de éxito documentados desde los primeros clientes.

Estimación de tamaño: representa aproximadamente el 35-45% del mercado objetivo total de {nombre}. Ticket promedio base: referencia del mercado sectorial.

**2. {segmentos[1]} — Prioridad ALTA ⭐⭐⭐**
Mercado con alto potencial de contratos recurrentes y LTV (Lifetime Value) considerablemente elevado respecto al segmento base. Requiere un proceso de venta consultivo, propuestas personalizadas y construcción de confianza previa. La penetración puede lograrse mediante alianzas con cámaras sectoriales, participación en eventos especializados y referidos de clientes satisfechos actuales. Ticket promedio estimado: 3-5x superior al segmento base.

**3. {segmentos[2]} — Prioridad MEDIA ⭐⭐**
Segmento de expansión a mediano plazo (6-18 meses). Presenta barreras de entrada moderadas pero ofrece notable estabilidad de ingresos y mayor predictibilidad de flujo de caja. {nombre} deberá desarrollar capacidades específicas (certificaciones, casos de éxito documentados, equipo especializado) antes de abordar activamente este segmento como foco principal.

**4. {segmentos[3]} — Prioridad MEDIA-BAJA ⭐**
Oportunidad de diversificación estratégica a largo plazo (18+ meses). Este segmento puede requerir adaptación de la oferta actual e inversión en desarrollo de producto/servicio. Se recomienda explorar mediante proyectos piloto de bajo riesgo antes de comprometer recursos significativos.

**Estrategia de Expansión Geográfica Recomendada**

• **Fase 1 (Meses 1-6):** Consolidar presencia en mercado local / ciudad principal. Objetivo: 80% o más de los ingresos iniciales provenientes de este ámbito.
• **Fase 2 (Meses 7-18):** Expansión regional a ciudades secundarias o países limítrofes con perfil socioeconómico similar y demanda validada.
• **Fase 3 (Mes 19+):** Evaluación de mercados internacionales con mayor poder adquisitivo o menor saturación competitiva en {sector}.

**Mercado Obtenible Realista (SOM)**

Considerando las capacidades actuales de {nombre} y un horizonte de 24 meses, el mercado obtenible representa entre el 0.5% y el 2.5% del SAM regional, equivalente a un potencial de ingresos proyectado de USD 150,000 - USD 850,000 anuales, dependiendo del segmento abordado, la estrategia de precios y la velocidad de ejecución."""


# ─── Sección 3: Análisis Competitivo ──────────────────────────────────────
def _analisis_competitivo(nombre: str, desc: str, sector: str) -> str:
    return f"""**Estructura del Panorama Competitivo en {sector.title()}**

El análisis competitivo de {nombre} en el sector de {sector} revela un mercado con múltiples niveles de competencia que la empresa debe comprender y navegar estratégicamente para construir y defender su posición diferenciada.

**Categorías de Competidores Identificados**

**Competidores Directos — misma oferta, mismo segmento objetivo**
Son los actores con quienes {nombre} compite directamente por el mismo perfil de cliente con propuestas similares. En {sector}, este grupo típicamente incluye:
• Empresas consolidadas con 5+ años en el mercado, marca reconocida y base de clientes establecida.
• Startups de rápido crecimiento con respaldo de inversión y foco en tecnología y escalabilidad.
• Operadores locales con relaciones establecidas, bajo costo estructural y conocimiento del territorio.

**Competidores Indirectos — necesidad similar, solución distinta**
Empresas que satisfacen la misma necesidad del cliente a través de aproximaciones diferentes:
• Soluciones in-house que los propios clientes desarrollan internamente para evitar dependencia de terceros.
• Productos sustitutos provenientes de sectores adyacentes que migran hacia {sector}.
• Plataformas generalistas que incluyen funcionalidades de {sector} como parte de una oferta más amplia.

**Competidores Potenciales — podrían ingresar en 12-24 meses**
• Grandes plataformas tecnológicas globales con posibilidad de expansión vertical hacia {sector}.
• Empresas de sectores adyacentes buscando diversificación o integración vertical.
• Startups internacionales con modelos validados que buscan expansión en América Latina.

**Análisis de las 5 Fuerzas Competitivas (Modelo de Porter)**

**Fuerza 1 — Amenaza de nuevos entrantes: Media-Alta**
Las barreras de entrada en {sector} son moderadas. El capital requerido es relativamente accesible y la tecnología ha democratizado muchas capacidades antes reservadas a grandes actores. Sin embargo, la reputación construida, las relaciones con clientes y la curva de aprendizaje actúan como barreras naturales de cierta efectividad. {nombre} debe moverse rápido para construir estos activos defensivos.

**Fuerza 2 — Poder de negociación de proveedores: Medio**
En {sector}, existe una disponibilidad razonable de proveedores alternativos, aunque los proveedores altamente especializados pueden ejercer presión en precios y condiciones. Recomendación: diversificar la base de proveedores clave y construir relaciones de largo plazo con los estratégicos.

**Fuerza 3 — Poder de negociación de clientes: Alto**
Los clientes en {sector} tienen acceso a múltiples alternativas y comparan activamente precio, calidad y servicio. La fidelización requiere esfuerzo continuo y una propuesta de valor que genere costos de cambio (switching costs) percibidos. Este es uno de los mayores desafíos para {nombre}.

**Fuerza 4 — Amenaza de productos sustitutos: Media**
La innovación tecnológica genera continuamente nuevas formas de satisfacer las necesidades del cliente en {sector}. {nombre} debe mantenerse en la frontera de innovación y monitorear activamente tendencias emergentes que podrían hacer obsoleta parte de su oferta actual.

**Fuerza 5 — Rivalidad entre competidores existentes: Alta**
El mercado de {sector} presenta competencia intensa en precio, servicio y diferenciación. La guerra de precios es un riesgo latente para jugadores sin una propuesta diferenciada sólida. {nombre} debe evitar competir principalmente en precio y construir en cambio su posición sobre valor percibido.

**Brechas y Oportunidades Identificadas**

Tras el análisis competitivo, se detectan las siguientes oportunidades no explotadas donde {nombre} puede construir ventaja competitiva sostenible:

1. **Brecha de personalización:** La mayoría de los competidores ofrecen soluciones estandarizadas. {nombre} puede diferenciarse con atención altamente personalizada y soluciones adaptadas a cada cliente.
2. **Brecha de transparencia:** Existe poca comunicación proactiva de valor e impacto en el sector. {nombre} puede liderar con contenido educativo, métricas de impacto claras y reportes de resultados.
3. **Brecha de agilidad:** Los actores consolidados son lentos para adaptarse. {nombre} puede capitalizar su velocidad de respuesta, flexibilidad operativa y toma de decisiones ágil.
4. **Brecha digital:** Segmentos desatendidos por canales digitales que {nombre} puede abordar con menores costos de adquisición que los competidores tradicionales.

**Posicionamiento Competitivo Recomendado**

{nombre} debe evitar la competencia directa en precio con operadores establecidos de mayor escala y construir su posición en el cuadrante de "alta calidad percibida + especialización en nicho", que presenta menor presión competitiva y mayor tolerancia de precio por parte del cliente objetivo."""


# ─── Sección 4: Propuesta de Valor ────────────────────────────────────────
def _propuesta_valor(nombre: str, desc: str, sector: str) -> str:
    kw = _keywords(desc)
    difs = kw[:3] if len(kw) >= 3 else ["calidad", "innovación", "servicio"]
    return f"""**Definición de la Propuesta de Valor Única (UVP)**

La Propuesta de Valor Única de {nombre} se construye sobre la comprensión profunda de los problemas reales del cliente en {sector} y la capacidad demostrada de resolverlos de manera superior a cualquier alternativa disponible actualmente en el mercado.

**Declaración de Valor Central**

"{nombre} ayuda a los clientes de {sector} a lograr sus resultados deseados mediante su enfoque único en {', '.join(difs)}, a diferencia de los competidores convencionales que ofrecen soluciones genéricas sin la especialización y personalización que el mercado exige."

Esta declaración debe refinarse continuamente con los aprendizajes de las interacciones reales con clientes, pero establece la dirección estratégica de posicionamiento desde el inicio.

**Los 3 Pilares de Diferenciación de {nombre}**

**Pilar 1 — Especialización Profunda en {sector.title()}**
{nombre} no es una solución genérica adaptada superficialmente. Cada aspecto de la oferta está diseñado específicamente para las necesidades, el lenguaje técnico y el contexto operativo del cliente en {sector}. Esta especialización se traduce en: menor tiempo de implementación o adopción, curva de aprendizaje reducida para el cliente, resultados más predecibles y equipo con conocimiento sectorial real. Los clientes en {sector} no quieren adaptar su negocio a una solución externa; quieren una solución que entienda profundamente su negocio.

**Pilar 2 — Experiencia del Cliente como Ventaja Competitiva Sostenida**
En mercados donde los productos y servicios se convierten progresivamente en commodities, la experiencia total del cliente diferencia a los ganadores. {nombre} invertirá en cada punto de contacto del cliente: desde el primer contacto comercial hasta el soporte post-venta y la renovación. Los procesos internos se diseñarán con el cliente como centro, no como periférico. Las métricas de experiencia (NPS, CSAT, tiempo de resolución de problemas) serán KPIs de primer nivel en la organización.

**Pilar 3 — Resultados Medibles y Comunicados con Transparencia**
El cliente en {sector} exige retorno claro sobre su inversión. {nombre} se compromete a definir junto a cada cliente los indicadores de éxito al inicio de cada relación comercial, y a reportar proactivamente el progreso contra esos indicadores. Esta transparencia genera confianza profunda, reduce la fricción en renovaciones y recompras, y convierte clientes satisfechos en promotores activos de la marca.

**Value Proposition Canvas — Estructura Analítica**

Trabajos del cliente que {nombre} ayuda a completar:
• Resolver el problema principal asociado a {sector} de manera rápida, confiable y con mínima fricción.
• Tomar decisiones informadas con acceso a datos, análisis y expertise de calidad.
• Liberar tiempo y recursos internos para que el cliente se enfoque en su actividad core y de mayor valor.

Dolores que {nombre} alivia activamente:
• Frustración por soluciones genéricas que no se adaptan al contexto específico del cliente.
• Pérdida de tiempo y dinero con proveedores que no cumplen plazos, estándares o promesas.
• Incertidumbre y falta de visibilidad sobre el retorno real de la inversión realizada.
• Sobrecarga operativa por tener que gestionar múltiples proveedores sin integración.

Ganancias que {nombre} crea para el cliente:
• Incremento medible en eficiencia operativa: objetivo 20-35% en los primeros 6 meses.
• Acceso a expertise especializado sin necesidad de contratación permanente de alto costo.
• Tranquilidad y confianza en la operación del área de {sector}.
• Ventaja competitiva derivada de mejores herramientas, procesos o conocimientos.

**Estrategia de Comunicación de la Propuesta de Valor**

• **Canales digitales (web, redes, SEO):** Mensaje conciso, orientado a resultados tangibles, con prueba social sólida: testimonios reales, casos de éxito con métricas, logos de clientes conocidos.
• **Venta consultiva directa:** Diagnóstico del problema específico del prospecto antes de presentar cualquier solución. La escucha activa precede siempre a la presentación de valor.
• **Aliados y canales de distribución:** Énfasis en complementariedad y en el beneficio mutuo generado para el cliente compartido. El mensaje debe resonar con los intereses del canal, no solo del cliente final.

**Protección y Evolución de la Propuesta de Valor**

La UVP de {nombre} debe defenderse y evolucionarse continuamente mediante: (1) inversión constante en conocimiento sectorial y tendencias de {sector}; (2) mecanismos de feedback rápido con clientes activos (encuestas trimestrales, entrevistas semestrales); (3) ciclos de mejora de producto/servicio no superiores a 90 días; (4) construcción de activos de marca como contenido de valor, comunidad activa y reputación en el sector, que son difíciles de replicar por los competidores."""


# ─── Sección 5: Plan de Acción ─────────────────────────────────────────────
def _plan_accion(nombre: str, desc: str, sector: str) -> str:
    anio = _anio()
    return f"""**Marco de Implementación Estratégica por Fases**

El Plan de Acción de {nombre} está estructurado en tres horizontes temporales que balancean la urgencia operativa inmediata con la construcción de capacidades de largo plazo. Cada fase tiene objetivos concretos, acciones priorizadas, recursos estimados y métricas de control definidas.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FASE 1 — Fundamentos y Validación (Meses 1-3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objetivo principal: Validar la propuesta de valor con clientes reales y establecer las bases operativas y comerciales de {nombre}.

Acciones Prioritarias:
• Completar el mapa detallado de clientes objetivo (ICP — Ideal Customer Profile) con criterios cuantitativos y cualitativos.
• Realizar 15-20 entrevistas de descubrimiento con prospectos calificados para validar o ajustar la propuesta de valor.
• Desarrollar o refinar el MVP (Minimum Viable Product/Service) basado directamente en el feedback obtenido.
• Establecer la infraestructura digital mínima viable: sitio web profesional, CRM básico, presencia en redes clave.
• Cerrar los primeros 3-5 clientes de referencia (pueden ser a precio reducido a cambio de testimonios documentados).
• Definir y documentar los procesos core: entrega, onboarding de cliente, gestión de cobros y soporte básico.
• Establecer alianzas con al menos 2 proveedores estratégicos para asegurar capacidad de entrega.

KPIs Fase 1:
• 3-5 clientes activos pagando al cierre del mes 3
• CAC (Costo de Adquisición de Cliente) inicial calculado y documentado
• NPS de primeros clientes ≥ 40 puntos
• Procesos core documentados al 60% o más

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FASE 2 — Crecimiento y Escalamiento (Meses 4-12)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objetivo principal: Escalar la adquisición de clientes manteniendo calidad operativa y construir sistemas de crecimiento repetibles y medibles.

Acciones Prioritarias:
• Implementar estrategia de contenido y marketing digital en {sector}: blog técnico, LinkedIn, SEO, casos de éxito en video o texto.
• Lanzar programa formal de referidos con incentivos tangibles para clientes actuales.
• Contratar o asociar al menos un perfil comercial dedicado a nuevos negocios (fulltime o por comisión).
• Desarrollar al menos 1 nueva línea de producto/servicio complementaria para aumentar el LTV por cliente.
• Formalizar los procesos de atención al cliente con tiempos de respuesta garantizados y SLAs claros.
• Iniciar exploración activa de mercados geográficos adyacentes con demanda validada del modelo.
• Participar en al menos 2 eventos, ferias o conferencias del sector de {sector} para construir visibilidad y red.

KPIs Fase 2:
• 20-40 clientes activos al cierre del mes 12
• MRR (Monthly Recurring Revenue) creciendo ≥ 10% mensual sostenido
• Tasa de retención de clientes ≥ 70%
• Margen bruto operativo ≥ 45%
• Equipo: 3-6 personas (incluyendo freelancers o socios)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FASE 3 — Consolidación y Expansión (Meses 13-24)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objetivo principal: Consolidar la posición de mercado de {nombre} y explorar vectores de crecimiento no lineal o de mayor palanca.

Acciones Prioritarias:
• Evaluar e implementar expansión geográfica regional basándose en datos y aprendizajes de la Fase 2.
• Construir un programa formal de partnerships con empresas complementarias en {sector}.
• Considerar acceso a financiamiento (rondas, crédito bancario, fondos de capital) si los fundamentos lo justifican.
• Invertir en tecnología y automatización para mejorar márgenes y reducir dependencia de procesos manuales.
• Desarrollar un programa de fidelización y comunidad de clientes (club, evento anual, grupo exclusivo).
• Explorar modelos de ingresos pasivos, licenciamiento o franquiciamiento si aplican al modelo de {nombre}.
• Evaluar la construcción de activos de datos o IP (propiedad intelectual) como ventaja defensiva a largo plazo.

KPIs Fase 3:
• Reconocimiento entre los top 3 referentes del nicho en el mercado local/regional
• EBITDA positivo sostenido durante al menos 3 meses consecutivos
• Equipo de 8-20 personas según necesidad y escala alcanzada
• Exploración activa de opciones de expansión internacional

**Recursos Estimados por Fase**

Fase 1 → Inversión: USD 5,000 - 20,000 | Equipo: 1-3 personas | Tecnología: básica
Fase 2 → Inversión: USD 20,000 - 80,000 | Equipo: 3-8 personas | Tecnología: intermedia
Fase 3 → Inversión: USD 80,000 - 300,000+ | Equipo: 8-20 personas | Tecnología: avanzada

**Matriz de Gestión de Riesgos**

1. Riesgo de validación — La propuesta de valor no resuena con el mercado.
   Mitigación: Ciclos de feedback ultra-cortos (sprint de 2 semanas), pivotar rápido con bajo costo comprometido.

2. Riesgo operativo — Capacidad insuficiente para atender la demanda generada.
   Mitigación: Crecer de forma controlada, priorizar calidad sobre velocidad de crecimiento en etapas tempranas.

3. Riesgo competitivo — Copia o imitación de la propuesta por competidores con más recursos.
   Mitigación: Construir activos intangibles (marca, comunidad, datos, cultura) que son difíciles de replicar incluso con capital.

4. Riesgo financiero — Flujo de caja negativo sostenido que agota el capital disponible.
   Mitigación: Estructurar el modelo con cobro anticipado o contratos recurrentes prepagados desde el inicio.

**Acciones Inmediatas — Próximos 30 Días**

✓ Definir el ICP (Ideal Customer Profile) con criterios cuantificables y verificables.
✓ Identificar y contactar 20 prospectos calificados para entrevistas de descubrimiento gratuitas.
✓ Establecer presencia digital mínima: web funcional + LinkedIn empresarial + Google Business (si aplica).
✓ Definir el pricing inicial y validarlo en al menos 5 conversaciones de venta reales con prospectos.
✓ Iniciar conversaciones con 2-3 potenciales aliados o socios estratégicos en {sector}.
✓ Configurar un CRM básico (HubSpot Free, Notion, o similar) para gestionar prospectos y clientes."""


# ═══════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL DE GENERACIÓN
# ═══════════════════════════════════════════════════════════════════════════

def generate_plan_local(business_name: str, business_desc: str) -> dict:
    """Genera el plan completo sin API ni internet."""
    sector = _detectar_sector(business_desc)
    return {
        "RESUMEN EJECUTIVO":              _resumen_ejecutivo(business_name, business_desc, sector),
        "MERCADOS OBJETIVO PRIORITARIOS": _mercados_objetivo(business_name, business_desc, sector),
        "ANÁLISIS COMPETITIVO":           _analisis_competitivo(business_name, business_desc, sector),
        "PROPUESTA DE VALOR ÚNICA":       _propuesta_valor(business_name, business_desc, sector),
        "PLAN DE ACCIÓN ESTRATÉGICO":     _plan_accion(business_name, business_desc, sector),
        "_sector":                        sector,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  GENERADOR DE PDF
# ═══════════════════════════════════════════════════════════════════════════

DARK_BG   = colors.HexColor("#0a0e1a")
ACCENT    = colors.HexColor("#3b82f6")
MUTED_TXT = colors.HexColor("#8899bb")
WHITE     = colors.white

CHIP_COLORS = {
    "RESUMEN EJECUTIVO":              colors.HexColor("#3b82f6"),
    "MERCADOS OBJETIVO PRIORITARIOS": colors.HexColor("#8b5cf6"),
    "ANÁLISIS COMPETITIVO":           colors.HexColor("#10b981"),
    "PROPUESTA DE VALOR ÚNICA":       colors.HexColor("#f59e0b"),
    "PLAN DE ACCIÓN ESTRATÉGICO":     colors.HexColor("#f43f5e"),
}


def _page_deco(canvas_obj, doc):
    w, h = A4
    canvas_obj.saveState()
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, w, h, stroke=0, fill=1)
    canvas_obj.setFillColor(ACCENT)
    canvas_obj.rect(0, h - 6*mm, w, 6*mm, stroke=0, fill=1)
    canvas_obj.setFillColor(colors.HexColor("#1e293b"))
    canvas_obj.rect(0, 0, w, 12*mm, stroke=0, fill=1)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(MUTED_TXT)
    canvas_obj.drawString(20*mm, 4*mm, "Plan de Negocio Estratégico — Version Free (sin API Key)")
    canvas_obj.drawRightString(w - 20*mm, 4*mm,
        f"Página {doc.page}  •  {datetime.now().strftime('%d/%m/%Y')}")
    canvas_obj.restoreState()


def build_pdf(business_name: str, sections: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=22*mm, rightMargin=22*mm,
                            topMargin=22*mm, bottomMargin=20*mm)

    title_s = ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=26,
                             textColor=WHITE, leading=32, spaceAfter=4)
    sub_s   = ParagraphStyle("S", fontName="Helvetica", fontSize=11,
                             textColor=MUTED_TXT, leading=16, spaceAfter=2)
    meta_s  = ParagraphStyle("M", fontName="Helvetica", fontSize=9,
                             textColor=MUTED_TXT, leading=14)
    chip_s  = ParagraphStyle("C", fontName="Helvetica-Bold", fontSize=7.5,
                             textColor=WHITE, leading=12)
    sec_s   = ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=14,
                             textColor=WHITE, leading=18, spaceBefore=6, spaceAfter=10)
    body_s  = ParagraphStyle("B", fontName="Helvetica", fontSize=9.5,
                             textColor=colors.HexColor("#c9d6f0"), leading=15,
                             spaceAfter=4, alignment=TA_JUSTIFY)

    story = []
    story.append(Spacer(1, 18*mm))

    # Portada
    lbl = Table([[Paragraph("PLAN DE NEGOCIO ESTRATÉGICO", meta_s)]], colWidths=[166*mm])
    lbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111827")),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),14),
    ]))
    story.append(lbl)
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(business_name, title_s))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Análisis estratégico integral: mercados, competencia y propuesta de valor", sub_s))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d de %B de %Y')}  •  Versión Free — Sin API Key",
        meta_s))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#1e3a5f"), spaceAfter=10*mm))

    # Índice
    idx_rows = [[Paragraph("CONTENIDO DEL DOCUMENTO",
                 ParagraphStyle("ih", fontName="Helvetica-Bold", fontSize=8,
                                textColor=ACCENT, leading=12))]]
    for i, (icon, title, _) in enumerate(SECTIONS, 1):
        idx_rows.append([Paragraph(f"{i}.  {icon}  {title}",
                          ParagraphStyle("ii", fontName="Helvetica", fontSize=9,
                                         textColor=colors.HexColor("#a0b4d0"), leading=16))])
    idx_t = Table(idx_rows, colWidths=[166*mm])
    idx_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#0d1829")),
        ("LINEBELOW",(0,0),(-1,0),0.5,colors.HexColor("#1e3a5f")),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",(0,0),(-1,-1),14),
    ]))
    story.append(idx_t)
    story.append(PageBreak())

    # Secciones de contenido
    for icon, title, _ in SECTIONS:
        content   = sections.get(title, "").strip()
        chip_color = CHIP_COLORS.get(title, ACCENT)

        chip_t = Table([[Paragraph(f"{icon}  {title}", chip_s)]], colWidths=[None])
        chip_t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),chip_color),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),
        ]))
        story.append(chip_t)
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(title, sec_s))
        story.append(HRFlowable(width="100%", thickness=1.5,
                                color=chip_color, spaceAfter=6*mm))

        for raw_line in content.split("\n"):
            line = raw_line.rstrip()
            if not line:
                story.append(Spacer(1, 2*mm))
                continue
            # Convertir **negrita**
            line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            # Escapar HTML (preservando tags ya insertados)
            line = (line.replace("&","&amp;")
                        .replace("<b>","<<B>>").replace("</b>","<</B>>")
                        .replace("<","&lt;")
                        .replace("<<B>>","<b>").replace("<</B>>","</b>"))
            if line.startswith(("• ","- ","* ")):
                txt = "    •  " + line[2:]
            elif re.match(r"^\d+\.", line):
                txt = "    " + line
            elif line.startswith("✓"):
                txt = "    ✓  " + line[1:].lstrip()
            elif line.startswith("━"):
                story.append(HRFlowable(width="100%", thickness=0.8,
                                        color=chip_color, spaceAfter=3*mm))
                continue
            else:
                txt = line
            story.append(Paragraph(txt, body_s))

        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#1e293b"), spaceAfter=8*mm))
        story.append(PageBreak())

    doc.build(story, onFirstPage=_page_deco, onLaterPages=_page_deco)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  UI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero">
  <div class="hero-tag">🧭 Consultoría estratégica con IA
    <span class="free-badge">✓ 100% Gratis</span>
  </div>
  <h1>Plan de Negocio<br>Estratégico</h1>
  <p>Genera en segundos un análisis completo: mercados objetivo,
     panorama competitivo y propuesta de valor única.<br>
     <strong style="color:#6ee7b7;">Sin API Key · Sin costo · Sin registro.</strong></p>
</div>
""", unsafe_allow_html=True)

col_l, col_r = st.columns([1, 1], gap="large")

with col_l:
    st.markdown("""
    <div class="card">
      <div class="card-title">🏢 Datos del negocio</div>
      <div class="card-sub">Completa los campos para personalizar tu análisis</div>
    </div>
    """, unsafe_allow_html=True)

    business_name = st.text_input(
        "Nombre de la empresa / negocio",
        placeholder="Ej: TechNova Solutions",
        key="biz_name",
    )
    business_desc = st.text_area(
        "Descripción del tipo de negocio",
        placeholder=(
            "Describe en detalle tu negocio: sector, productos o servicios, "
            "modelo de ingresos, etapa actual, geografía de operación, "
            "clientes actuales y cualquier diferenciador que ya tengas...\n\n"
            "Mientras más detalle incluyas, más personalizado será el análisis."
        ),
        height=240,
        key="biz_desc",
    )
    st.markdown("""
    <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);
                border-radius:10px;padding:0.9rem 1.1rem;margin-top:0.5rem;">
      <div style="font-size:0.78rem;color:#6ee7b7;font-weight:600;margin-bottom:0.3rem;">
        ✓ VERSIÓN 100% GRATUITA — SIN API KEY REQUERIDA
      </div>
      <div style="font-size:0.8rem;color:rgba(110,231,183,0.65);line-height:1.5;">
        Utiliza un motor de generación estratégica inteligente basado en plantillas
        sectoriales adaptadas automáticamente a tu negocio. Solo requiere
        <code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:3px;">streamlit</code>
        y
        <code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:3px;">reportlab</code>.
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_r:
    st.markdown("""
    <div class="card">
      <div class="card-title">🔍 ¿Qué incluye el plan?</div>
      <div class="card-sub">Cinco secciones estratégicas de alto impacto</div>
    </div>
    """, unsafe_allow_html=True)
    features = [
        ("📋", "chip-blue",   "Resumen Ejecutivo",          "Visión, misión, modelo de negocio y KPIs principales."),
        ("🎯", "chip-purple", "Mercados Objetivo",          "TAM/SAM/SOM y 4 segmentos priorizados con estrategia de entrada."),
        ("⚔️",  "chip-green",  "Análisis Competitivo",       "5 Fuerzas de Porter, tipos de competidores y brechas detectadas."),
        ("💡", "chip-amber",  "Propuesta de Valor Única",   "UVP, Value Proposition Canvas y estrategia de comunicación."),
        ("🗺️", "chip-rose",   "Plan de Acción Estratégico", "3 fases con acciones, KPIs, presupuesto y gestión de riesgos."),
    ]
    for icon, chip, title, desc in features:
        st.markdown(f"""
        <div style="display:flex;align-items:flex-start;gap:1rem;padding:0.85rem 0;
                    border-bottom:1px solid rgba(255,255,255,0.05);">
          <span class="section-chip {chip}">{icon}</span>
          <div>
            <div style="font-weight:600;font-size:0.9rem;color:#c9d6f5;margin-bottom:3px;">{title}</div>
            <div style="font-size:0.79rem;color:rgba(180,195,220,0.55);line-height:1.5;">{desc}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── Botón Generar ──────────────────────────────────────────────────────────
st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
btn_col, _ = st.columns([1, 3])
with btn_col:
    generate_btn = st.button("⚡  Generar Plan Estratégico", use_container_width=True)

# ── Inicializar estado ─────────────────────────────────────────────────────
for key, default in [("plan_sections",{}), ("pdf_bytes",None), ("last_name",""), ("last_sector","")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Lógica de generación ───────────────────────────────────────────────────
if generate_btn:
    if not business_name.strip():
        st.error("⚠️  Por favor ingresa el nombre de tu empresa o negocio.")
    elif not business_desc.strip():
        st.error("⚠️  Por favor describe el tipo de negocio para personalizar el análisis.")
    elif len(business_desc.strip()) < 25:
        st.warning("💡  Agrega más detalle en la descripción (mínimo 25 caracteres) para obtener un análisis más personalizado.")
    else:
        prog = st.empty()
        steps = [
            "Detectando sector y palabras clave del negocio...",
            "Elaborando Resumen Ejecutivo...",
            "Analizando Mercados Objetivo Prioritarios...",
            "Construyendo Análisis Competitivo (Porter)...",
            "Definiendo Propuesta de Valor Única...",
            "Diseñando Plan de Acción por Fases...",
            "Generando PDF profesional descargable...",
        ]
        for i, step in enumerate(steps):
            pct = int((i + 1) / len(steps) * 100)
            prog.markdown(f"""
            <div class="prog-bar-wrap">
              <div class="prog-label">GENERANDO PLAN ESTRATÉGICO... {pct}%</div>
              <div class="prog-track">
                <div class="prog-fill" style="width:{pct}%"></div>
              </div>
              <div class="prog-step">
                <div style="width:8px;height:8px;border-radius:50%;background:#3b82f6;
                            flex-shrink:0;"></div>
                <span>{step}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.15)

        try:
            data   = generate_plan_local(business_name.strip(), business_desc.strip())
            sector = data.pop("_sector", "servicios")
            pdf_b  = build_pdf(business_name.strip(), data)

            st.session_state.plan_sections = data
            st.session_state.pdf_bytes     = pdf_b
            st.session_state.last_name     = business_name.strip()
            st.session_state.last_sector   = sector

            prog.empty()
            st.success(
                f"✅  Plan estratégico generado para **{business_name.strip()}**"
                f" · Sector detectado: **{sector.title()}**"
            )
        except Exception as e:
            prog.empty()
            st.error(f"❌  Error al generar el plan: {e}")

# ── Mostrar resultados ─────────────────────────────────────────────────────
if st.session_state.plan_sections:
    secs      = st.session_state.plan_sections
    biz_name  = st.session_state.last_name
    sector    = st.session_state.last_sector
    pdf_bytes = st.session_state.pdf_bytes

    st.markdown(f"""
    <div class="result-wrapper">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;
                  flex-wrap:wrap;gap:1rem;margin-bottom:2.5rem;">
        <div>
          <div style="font-size:0.7rem;letter-spacing:0.2em;text-transform:uppercase;
                      color:#63b3ed;font-weight:700;margin-bottom:0.4rem;">Plan generado para</div>
          <div style="font-family:'Playfair Display',serif;font-size:2rem;
                      font-weight:900;color:#f0f4ff;">{biz_name}</div>
          <div style="font-size:0.82rem;color:rgba(180,200,230,0.5);margin-top:0.3rem;">
            Sector detectado: <strong style="color:#6ee7b7;">{sector.title()}</strong>
          </div>
        </div>
        <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);
                    border-radius:10px;padding:0.7rem 1.2rem;align-self:flex-start;">
          <div style="font-size:0.7rem;font-weight:700;color:#6ee7b7;letter-spacing:0.1em;">
            ✓ GENERADO SIN API KEY
          </div>
        </div>
      </div>
    """, unsafe_allow_html=True)

    for icon, title, chip in SECTIONS:
        content = secs.get(title, "Sin información generada.")
        st.markdown(f"""
        <span class="section-chip {chip}">{icon} {title}</span>
        <div class="section-heading">{title.title()}</div>
        <div class="section-body">{content}</div>
        <hr class="divider">
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Botón descarga PDF
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    dl_col, _ = st.columns([1, 3])
    with dl_col:
        fname = f"plan_estrategico_{biz_name.lower().replace(' ','_')}.pdf"
        st.download_button(
            label="📥  Descargar PDF",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
        )

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  🧭 Plan de Negocio Estratégico &nbsp;•&nbsp; Versión Free
  &nbsp;•&nbsp; Solo requiere
  <code>pip install streamlit reportlab</code>
</div>
""", unsafe_allow_html=True)
