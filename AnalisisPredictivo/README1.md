# 📈 Trading Predictor Pro - Sistema de Análisis Predictivo

Sistema completo de análisis predictivo para trading de acciones, criptomonedas y metales preciosos con datos en tiempo real.

## 🚀 Características Principales

### 1. **Análisis en Tiempo Real**
- Datos actualizados de Yahoo Finance
- Actualización automática cada 5 minutos
- Múltiples categorías de activos:
  - ✅ Acciones (AAPL, MSFT, TSLA, NVDA, etc.)
  - ₿ Criptomonedas (BTC, ETH, SOL, ADA, etc.)
  - 🥇 Metales Preciosos (Oro, Plata, Platino, etc.)

### 2. **Indicadores Técnicos Avanzados**
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bandas de Bollinger
- Medias Móviles (SMA 20 y 50)
- Análisis de Volatilidad

### 3. **Predicción con Machine Learning**
- Modelo Random Forest para predicciones
- Predicción personalizable (días o meses)
- Análisis de importancia de features
- Visualización de tendencias futuras

### 4. **Top Performers**
- Ranking de ganadoras y perdedoras del día
- Análisis por categoría (Acciones, Criptos, Metales)
- Métricas de cambio porcentual

### 5. **Calendario Económico**
- Eventos económicos importantes de USA
- Clasificación por nivel de impacto
- Fechas y descripciones detalladas

### 6. **Visualizaciones Interactivas**
- Gráficos de velas (candlestick)
- Múltiples paneles con indicadores
- Zoom y exploración interactiva
- Exportación de datos a CSV

## 📋 Requisitos Previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Conexión a Internet

## 🔑 APIs Utilizadas

### API Principal (Ya Incluida - Sin Configuración)
- **Yahoo Finance (yfinance)**: GRATIS, sin API key necesaria ✅
  - Proporciona todos los datos necesarios para el funcionamiento básico
  - Datos de acciones, criptomonedas y metales
  - Sin límites estrictos para uso personal

### APIs Opcionales (Para Funcionalidad Avanzada)
Si deseas mejorar el sistema con datos más detallados o noticias en tiempo real:

1. **Alpha Vantage** (OPCIONAL) - Datos financieros detallados
   - Registro: https://www.alphavantage.co/support/#api-key
   - Límite gratuito: 500 llamadas/día
   - Tiempo de registro: 30 segundos

2. **Finnhub** (OPCIONAL) - Noticias financieras
   - Registro: https://finnhub.io/register
   - Límite gratuito: 60 llamadas/minuto
   - Tiempo de registro: 2 minutos

3. **NewsAPI** (OPCIONAL) - Noticias generales
   - Registro: https://newsapi.org/register
   - Límite gratuito: 100 requests/día
   - Tiempo de registro: 2 minutos

**📖 Para guía completa de APIs, consulta:** `API_CONFIGURATION.md`
**🚀 Para inicio rápido con APIs, consulta:** `QUICK_START_API.md`

**⚠️ IMPORTANTE**: El sistema funciona completamente SIN configurar APIs adicionales. Solo necesitas instalarlas si quieres funcionalidad premium.

## 🔧 Instalación

### Paso 1: Clonar o descargar los archivos
```bash
# Si tienes los archivos en una carpeta, navega a ella
cd ruta/a/tu/carpeta
```

### Paso 2: Crear un entorno virtual (recomendado)
```bash
# En Windows
python -m venv venv
venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar dependencias
```bash
pip install -r requirements.txt
```

## ▶️ Cómo Ejecutar

### Ejecutar la aplicación
```bash
streamlit run trading_predictor.py
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

## 📖 Guía de Uso

### Barra Lateral (Configuración)

1. **Categoría de Activo**: Selecciona entre Acciones, Criptomonedas o Metales
2. **Seleccionar Activo**: Elige el activo específico que deseas analizar
3. **Rango de Fechas**: 
   - Fecha Inicio: Define desde cuándo quieres los datos históricos
   - Fecha Final: Define hasta cuándo (por defecto, hoy)
4. **Configuración de Predicción**:
   - Tipo: Selecciona Días o Meses
   - Período: Define cuántos días/meses predecir (1-90 días o 1-12 meses)
5. **Botón Actualizar**: Refresca los datos en tiempo real

### Pestañas Principales

#### 📊 Análisis Principal
- **Métricas Superiores**: Precio actual, máximo/mínimo 52 semanas, volumen
- **Gráfico Principal**: Incluye:
  - Precio histórico y predicción
  - Bandas de Bollinger
  - Medias móviles (SMA 20 y 50)
  - RSI con zonas de sobrecompra/sobreventa
  - MACD con línea de señal
  - Volumen con colores (rojo=bajista, verde=alcista)
- **Resumen de Predicción**: Análisis del cambio esperado
- **Importancia de Features**: Qué indicadores influyen más en la predicción

#### 🏆 Top Performers
- Ganadoras y perdedoras del día
- Tres columnas: Acciones, Criptomonedas, Metales
- Cambio porcentual y precio actual

#### 📅 Calendario Económico
- Próximos eventos económicos importantes
- Clasificación por impacto (Alto, Medio, Bajo)
- Fechas y descripciones

#### 📈 Datos Detallados
- Estadísticas descriptivas
- Indicadores técnicos actuales
- Tabla completa de datos históricos (últimos 100 registros)
- Opción de descarga en formato CSV

## 🎨 Personalización

### Agregar Nuevos Activos

Edita el archivo `trading_predictor.py` y agrega símbolos a los diccionarios:

```python
STOCKS = {
    "Nombre de la Empresa": "SÍMBOLO",
    # Por ejemplo:
    "Disney": "DIS",
}

CRYPTOS = {
    "Nombre Cripto": "SÍMBOLO-USD",
    # Por ejemplo:
    "Litecoin": "LTC-USD",
}

METALS = {
    "Nombre Metal": "SÍMBOLO",
    # Por ejemplo:
    "Aluminio": "AL=F",
}
```

### Modificar Período de Cache

En la función `get_real_time_data`, cambia el parámetro `ttl`:

```python
@st.cache_data(ttl=300)  # 300 segundos = 5 minutos
```

## 📊 Indicadores Técnicos Explicados

### RSI (Índice de Fuerza Relativa)
- **Rango**: 0-100
- **Sobrecompra**: >70 (posible corrección bajista)
- **Sobreventa**: <30 (posible rebote alcista)

### MACD
- **Señal de Compra**: MACD cruza por encima de la línea de señal
- **Señal de Venta**: MACD cruza por debajo de la línea de señal

### Bandas de Bollinger
- **Precio cerca de banda superior**: Posible sobrecompra
- **Precio cerca de banda inferior**: Posible sobreventa
- **Estrechamiento de bandas**: Baja volatilidad (posible ruptura)

### Medias Móviles
- **SMA 20**: Tendencia de corto plazo
- **SMA 50**: Tendencia de mediano plazo
- **Cruce Dorado**: SMA 20 cruza por encima de SMA 50 (alcista)
- **Cruce de Muerte**: SMA 20 cruza por debajo de SMA 50 (bajista)

## ⚠️ Limitaciones y Advertencias

1. **Datos de Yahoo Finance**: 
   - Puede haber retrasos de 15-20 minutos en datos de mercado
   - Algunos activos pueden no estar disponibles

2. **Predicciones**:
   - Las predicciones son estimaciones basadas en datos históricos
   - No garantizan resultados futuros
   - Usar solo como herramienta de apoyo, no como única base de decisión

3. **Calendario Económico**:
   - Los eventos mostrados son ejemplos
   - Para uso en producción, integrar con API de calendario económico real

4. **No es Asesoramiento Financiero**:
   - Este sistema es solo para fines educativos
   - Siempre consulte con un asesor financiero profesional
   - Las inversiones conllevan riesgos

## 🐛 Solución de Problemas

### Error: "No se pudieron obtener datos"
- Verifica tu conexión a Internet
- Confirma que el símbolo del activo sea correcto
- Algunos activos pueden no tener datos históricos suficientes

### Error de instalación de paquetes
```bash
# Actualiza pip
pip install --upgrade pip

# Instala paquetes individualmente si hay errores
pip install streamlit
pip install yfinance
pip install pandas
pip install plotly
pip install scikit-learn
```

### La aplicación no se abre en el navegador
```bash
# Especifica el puerto manualmente
streamlit run trading_predictor.py --server.port 8501
```

## 🔄 Actualizaciones Futuras Planeadas

- [ ] Integración con API de noticias financieras
- [ ] Alertas de precio personalizables
- [ ] Análisis de sentimiento de redes sociales
- [ ] Backtesting de estrategias
- [ ] Integración con calendarios económicos reales
- [ ] Soporte para más mercados internacionales
- [ ] Análisis de correlaciones entre activos
- [ ] Dashboard de portfolio completo

## 📞 Soporte

Para preguntas o problemas:
1. Revisa esta documentación
2. Verifica los mensajes de error en la consola
3. Asegúrate de tener las últimas versiones de los paquetes

## 📄 Licencia

Este proyecto es de código abierto y está disponible para uso educativo.

## 🙏 Agradecimientos

- **Yahoo Finance** por proporcionar datos de mercado
- **Streamlit** por el framework de visualización
- **Plotly** por gráficos interactivos
- **scikit-learn** por algoritmos de machine learning

---

**¡Importante!** Este sistema es una herramienta educativa. Las decisiones de inversión deben tomarse consultando con profesionales financieros y realizando su propia investigación exhaustiva.

**Versión**: 1.0  
**Última actualización**: Febrero 2025
