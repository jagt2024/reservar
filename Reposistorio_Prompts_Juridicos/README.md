# 🎯 Generador de Prompts Profesional con Streamlit

Aplicación interactiva para crear, validar y optimizar prompts usando frameworks establecidos y técnicas avanzadas de prompting.

## 🚀 Características

### Frameworks Disponibles
- **CTF** (Context-Task-Format): Simple y efectivo
- **RISEN** (Role-Instructions-Steps-End goal-Narrowing): Completo y estructurado
- **RACE** (Role-Action-Context-Expectation): Enfocado en resultados
- **CRAFT** (Context-Role-Action-Format-Target): Balanceado y profesional
- **SMART** (Specific-Measurable-Achievable-Relevant-Time-bound): Para objetivos claros
- **APE** (Action-Purpose-Expectation): Directo y conciso
- **STAR** (Situation-Task-Action-Result): Narrativo y orientado a resultados
- **CREATE** (Character-Request-Examples-Adjustments-Type-Extras): Para contenido creativo

### Técnicas de Prompting
- **Chain of Thought**: Razonamiento paso a paso
- **Few-Shot Learning**: Aprendizaje por ejemplos
- **Self-Consistency**: Múltiples enfoques
- **Meta-Prompting**: Auto-optimización del prompt
- **Zero-Shot CoT**: Pensamiento estructurado sin ejemplos

### Funcionalidades
1. **Crear Prompts**: Construye prompts estructurados usando cualquier framework
2. **Validar Prompts**: Analiza la calidad de prompts existentes
3. **Ver Plantillas**: Explora las plantillas de cada framework
4. **Aplicar Técnicas**: Mejora tus prompts con técnicas avanzadas
5. **Exportar**: Descarga tus prompts y plantillas

## 📦 Instalación

### Requisitos Previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Pasos de Instalación

1. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

2. **Ejecutar la aplicación**
```bash
streamlit run prompt_generator_app.py
```

3. **Acceder a la aplicación**
La aplicación se abrirá automáticamente en tu navegador en:
```
http://localhost:8501
```

## 🎮 Uso

### Crear un Prompt Nuevo

1. Selecciona un **framework** en la barra lateral
2. Completa los **componentes** del framework en el área principal
3. (Opcional) Selecciona **técnicas** de prompting para mejorar tu prompt
4. Haz clic en **"Generar Prompt"**
5. Revisa el **score de calidad** y las validaciones
6. Descarga tu prompt usando el botón de descarga

### Validar un Prompt Existente

1. Ve a la pestaña **"Validar Prompt"**
2. Pega tu prompt en el área de texto
3. Haz clic en **"Validar"**
4. Revisa el análisis detallado y las recomendaciones

### Explorar Plantillas

1. Ve a la pestaña **"Plantilla"**
2. Selecciona un framework en la barra lateral
3. Revisa los componentes y la descripción
4. Descarga la plantilla si lo deseas

## 📊 Sistema de Validación

La aplicación evalúa cada prompt basándose en 6 criterios:

| Criterio | Descripción |
|----------|-------------|
| ✅ Objetivo Claro | Más de 50 caracteres |
| ✅ Estructura | Contiene saltos de línea organizados |
| ✅ Formato Específico | Define el formato de salida esperado |
| ✅ Contexto | Incluye contexto o situación |
| ✅ Rol Definido | Especifica un rol o personaje |
| ✅ Longitud Apropiada | Entre 100 y 5000 caracteres |

**Score de Calidad:**
- 80-100%: Excelente
- 60-79%: Bueno
- 0-59%: Mejorable

## 💡 Ejemplos de Uso

### Ejemplo 1: Marketing con RISEN
```
ROLE: Actúa como un experto en marketing digital con 10 años de experiencia
INSTRUCTIONS: Crea una estrategia de contenido para redes sociales
STEPS: 1. Analiza el público objetivo, 2. Define pilares de contenido, 3. Crea calendario
END GOAL: Un plan de contenido de 30 días listo para implementar
NARROWING: Enfócate en Instagram y TikTok, audiencia 18-35 años
```

### Ejemplo 2: Análisis con CTF
```
CONTEXT: Empresa de tecnología B2B con 500 clientes actuales
TASK: Analiza los datos de churn del último trimestre e identifica patrones
FORMAT: Informe ejecutivo con gráficos, tabla de hallazgos y 3 recomendaciones
```

### Ejemplo 3: Creativo con CREATE
```
CHARACTER: Escritor de ciencia ficción especializado en distopías
REQUEST: Escribe un cuento corto sobre IA en el año 2150
EXAMPLES: Estilo similar a "Black Mirror" pero más esperanzador
ADJUSTMENTS: Tono serio pero con momentos de humor
TYPE: Narrativa en primera persona, 1500 palabras
EXTRAS: Incluye un giro final sorprendente
```

## 🔧 Personalización

Puedes modificar el archivo `prompt_generator_app.py` para:
- Añadir nuevos frameworks
- Crear técnicas personalizadas
- Ajustar criterios de validación
- Cambiar el diseño de la interfaz

## 📝 Notas

- Los prompts se generan en tiempo real
- Todas las validaciones se ejecutan localmente
- Los archivos descargados son texto plano (.txt)
- La aplicación no almacena datos entre sesiones

## 🆘 Solución de Problemas

**La aplicación no inicia:**
```bash
# Verifica que Streamlit esté instalado
pip install --upgrade streamlit
```

**Error de módulos:**
```bash
# Reinstala las dependencias
pip install -r requirements.txt --force-reinstall
```

**Puerto ya en uso:**
```bash
# Usa un puerto diferente
streamlit run prompt_generator_app.py --server.port 8502
```

## 📚 Recursos Adicionales

- [Documentación de Streamlit](https://docs.streamlit.io)
- [Guía de Prompt Engineering](https://www.promptingguide.ai)
- [Anthropic Prompting Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)

## 🤝 Contribuciones

Si deseas mejorar esta aplicación:
1. Añade nuevos frameworks al diccionario `FRAMEWORKS`
2. Crea técnicas adicionales en el método `add_techniques`
3. Mejora los criterios de validación en `validate_prompt`

## 📄 Licencia

Este proyecto es de código abierto y está disponible para uso personal y comercial.

---

**Desarrollado con ❤️ usando Streamlit y Python**
