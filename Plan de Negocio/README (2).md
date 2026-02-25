# 🧭 Plan de Negocio Estratégico — Versión Free

Genera planes de negocio estratégicos completos **sin API Key, sin internet y sin costo**.

## ✅ Instalación (solo 2 paquetes)

```bash
pip install streamlit reportlab
```

## ▶️ Ejecutar

```bash
streamlit run plan_estrategico.py
```

Abre automáticamente en: **http://localhost:8501**

---

## 🚫 ¿Por qué no necesita API Key?

Esta versión utiliza un **motor de generación estratégica local** integrado directamente en
el script. Detecta automáticamente el sector del negocio a partir de la descripción y adapta
todo el contenido (mercados, competidores, propuesta de valor, plan de acción) a ese sector.

**Sectores reconocidos automáticamente:**
- Tecnología / Software / SaaS / IA
- Gastronomía / Restaurantes / Delivery
- Salud y Bienestar / Fitness / Clínicas
- Educación / Capacitación / E-learning
- Comercio y Retail / E-commerce
- Construcción e Inmobiliaria
- Logística y Transporte
- Finanzas y Servicios Financieros
- Marketing y Comunicaciones
- Consultoría y Servicios Profesionales
- Turismo y Hospitalidad
- Manufactura e Industria
- Servicios Generales (fallback)

---

## 📋 Contenido generado

| Sección                        | Contenido                                                   |
|-------------------------------|-------------------------------------------------------------|
| 📋 Resumen Ejecutivo           | Visión, misión, modelo de negocio, KPIs                     |
| 🎯 Mercados Objetivo           | TAM/SAM/SOM, 4 segmentos priorizados + estrategia de entrada|
| ⚔️  Análisis Competitivo        | 5 Fuerzas de Porter, tipos de competidores, brechas         |
| 💡 Propuesta de Valor Única    | UVP, Value Proposition Canvas, comunicación                 |
| 🗺️ Plan de Acción Estratégico  | 3 fases, acciones, KPIs, presupuesto, riesgos               |

## 📥 Descarga PDF

Al generar el plan, el botón **Descargar PDF** produce un documento profesional con:
- Portada con nombre del negocio
- Índice de contenidos
- Secciones coloreadas por tema
- Encabezado y pie de página con fecha y numeración

## 🛠 Requisitos mínimos

- Python 3.9+
- streamlit
- reportlab
