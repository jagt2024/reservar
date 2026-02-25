# 🚀 Plan Estratégico de Negocio — Streamlit App

Generador de planes estratégicos profesionales con IA (Claude de Anthropic).

## Requisitos

- Python 3.9+
- Una API Key de Anthropic → https://console.anthropic.com

## Instalación

```bash
# 1. Clona o descarga los archivos
# 2. Instala dependencias
pip install -r requirements.txt
```

## Ejecución

### Opción A — Variable de entorno (recomendado)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run plan_estrategico_app.py
```

### Opción B — Ingresar la key en la app
```bash
streamlit run plan_estrategico_app.py
# Luego ingresa tu API Key en la barra lateral izquierda
```

## Funcionalidades

| Feature | Descripción |
|---|---|
| 🔐 Autenticación | Login simulado por email con código de 6 dígitos |
| 🧠 Generación IA | 5 secciones estratégicas generadas por Claude |
| ✏️ Edición | Edita cualquier sección manualmente |
| 🔄 Regeneración | Regenera una sección específica con IA |
| ⬇️ Descarga | Exporta el plan completo como HTML |

## Secciones generadas

1. **Resumen Ejecutivo** — Misión, visión, objetivos y KPIs
2. **Mercados Objetivo** — TAM-SAM-SOM y segmentos prioritarios
3. **Análisis Competitivo** — 5 Fuerzas de Porter y oportunidades
4. **Propuesta de Valor** — Diferenciación y Value Proposition Canvas
5. **Plan de Acción** — 3 fases con acciones, KPIs y mitigación de riesgos

## Notas

- El código de verificación es **simulado** (aparece como toast/alerta).
- Para producción, integra un servicio de envío de emails (SendGrid, AWS SES, etc.).
- Modelo por defecto: `claude-opus-4-6` (puedes cambiarlo en el código).
