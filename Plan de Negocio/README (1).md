# 🧭 Plan de Negocio Estratégico — Powered by Claude AI

App Streamlit que genera planes de negocio completos usando la API de Claude.

## ✅ Instalación

```bash
pip install streamlit anthropic reportlab
```

## 🔑 Configurar API Key

Exporta tu clave de Anthropic antes de ejecutar:

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

> Obtén tu clave en: https://console.anthropic.com/settings/api-keys

## ▶️ Ejecutar

```bash
streamlit run plan_estrategico.py
```

La app se abrirá en: http://localhost:8501

## 📋 Funcionalidades

| Sección                      | Descripción                                     |
|------------------------------|-------------------------------------------------|
| 📋 Resumen Ejecutivo         | Visión, misión y objetivos clave del negocio    |
| 🎯 Mercados Objetivo         | Segmentos prioritarios para expansión           |
| ⚔️  Análisis Competitivo     | Rivales, brechas y oportunidades del sector     |
| 💡 Propuesta de Valor Única  | Diferenciadores y posicionamiento de marca      |
| 🗺️ Plan de Acción Estratégico | Hoja de ruta con hitos, KPIs y recursos         |

## 📥 Descarga PDF

Una vez generado el plan, el botón **Descargar PDF** genera un documento
profesional con diseño oscuro, numeración de páginas y secciones coloreadas.

## 🛠 Requisitos

- Python 3.9+
- streamlit >= 1.32
- anthropic >= 0.25
- reportlab >= 4.0
