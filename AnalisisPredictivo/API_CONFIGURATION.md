# 🔑 Configuración de APIs - Trading Predictor Pro

## 📋 Resumen de APIs

### API Principal (INCLUIDA - Sin registro necesario)

#### ✅ Yahoo Finance (yfinance)
- **Costo**: GRATIS
- **Registro**: NO requerido
- **Límites**: Razonables para uso personal
- **Datos**: Acciones, ETFs, Criptos, Metales, Índices
- **Delay**: 15-20 minutos para datos de mercado
- **Documentación**: https://pypi.org/project/yfinance/

**ESTA ES LA API QUE USA EL SISTEMA POR DEFECTO** ✅

---

## 🚀 APIs Opcionales (Para Mejorar Funcionalidad)

### 1. Alpha Vantage
**Para qué sirve**: Datos financieros más detallados, indicadores técnicos avanzados

- **Costo**: GRATIS (con límites)
- **Límite gratuito**: 500 llamadas por día, 5 por minuto
- **Datos**: 
  - Datos intraday (1min, 5min, 15min, 30min, 60min)
  - Indicadores técnicos precalculados
  - Datos fundamentales de empresas
  - Forex, Criptos, Commodities

#### Cómo obtener tu API Key:
1. Ve a: https://www.alphavantage.co/support/#api-key
2. Ingresa tu email
3. Recibirás tu API key inmediatamente
4. Copia la key

#### Cómo usar en el sistema:
```python
# En trading_predictor.py, descomenta y agrega tu key:
ALPHA_VANTAGE_KEY = "TU_API_KEY_AQUI"
```

#### Ejemplo de uso:
```python
import requests

def get_alpha_vantage_data(symbol, apikey):
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={apikey}'
    response = requests.get(url)
    return response.json()
```

---

### 2. Finnhub
**Para qué sirve**: Noticias financieras en tiempo real, análisis de sentimiento, **calendario económico**

- **Costo**: GRATIS (plan básico)
- **Límite gratuito**: 60 llamadas por minuto
- **Datos**:
  - Noticias de mercado en tiempo real
  - Sentimiento de noticias
  - Recomendaciones de analistas
  - **Calendario económico (eventos en tiempo real)** ⭐
  - Earnings calendar
  - IPOs

#### Cómo obtener tu API Key:
1. Registrate en: https://finnhub.io/register
2. Verifica tu email
3. En el dashboard, copia tu API Key
4. La key aparece como: `xxxxxxxxxxxxxxxxxxxxx`

#### Cómo usar en el sistema:
```python
# En trading_predictor.py:
FINNHUB_KEY = "TU_API_KEY_AQUI"
```

#### Ejemplo de uso:
```python
import requests

def get_company_news(symbol, finnhub_key):
    url = f'https://finnhub.io/api/v1/company-news?symbol={symbol}&from=2025-01-01&to=2025-02-15&token={finnhub_key}'
    response = requests.get(url)
    return response.json()

def get_economic_calendar(finnhub_key):
    url = f'https://finnhub.io/api/v1/calendar/economic?token={finnhub_key}'
    response = requests.get(url)
    return response.json()
```

**💡 Uso en Trading Predictor Pro:**
- Si configuras FINNHUB_KEY, el calendario económico mostrará eventos REALES
- Fechas exactas de publicación de indicadores
- Datos: Actual, Estimate, Previous
- Actualizaciones automáticas

**Ver guía completa:** `ECONOMIC_CALENDAR_GUIDE.md`

---

### 3. Polygon.io
**Para qué sirve**: Datos de mercado de alta calidad, historial completo

- **Costo**: Plan gratuito disponible
- **Límite gratuito**: 5 llamadas por minuto
- **Datos**:
  - Datos históricos completos
  - Trades y quotes
  - Agregados (OHLC)
  - Splits y dividendos

#### Cómo obtener tu API Key:
1. Registrate en: https://polygon.io/
2. Selecciona el plan "Free" (o "Starter" para más features)
3. En tu dashboard, copia la API Key

#### Ejemplo de uso:
```python
import requests

def get_polygon_data(symbol, polygon_key):
    url = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/2024-01-01/2025-02-15?apiKey={polygon_key}'
    response = requests.get(url)
    return response.json()
```

---

### 4. NewsAPI
**Para qué sirve**: Noticias generales y financieras

- **Costo**: GRATIS (plan developer)
- **Límite gratuito**: 100 requests por día
- **Datos**:
  - Noticias de todo el mundo
  - Búsqueda por keywords
  - Filtros por fuente, fecha, idioma

#### Cómo obtener tu API Key:
1. Registrate en: https://newsapi.org/register
2. Recibirás tu API Key por email
3. También la verás en tu dashboard

#### Ejemplo de uso:
```python
import requests

def get_financial_news(query, news_api_key):
    url = f'https://newsapi.org/v2/everything?q={query}&apiKey={news_api_key}&language=es&sortBy=publishedAt'
    response = requests.get(url)
    return response.json()
```

---

### 5. Twelve Data (Alternativa a Alpha Vantage)
**Para qué sirve**: Datos de mercado completos

- **Costo**: GRATIS (800 llamadas/día)
- **Documentación**: https://twelvedata.com/
- **Datos**: Similar a Alpha Vantage pero con mejor límite gratuito

#### Cómo obtener tu API Key:
1. Registrate en: https://twelvedata.com/register
2. Copia tu API Key del dashboard

---

## 📝 Archivo de Configuración (.env)

Para mayor seguridad, crea un archivo `.env` en el mismo directorio:

```bash
# .env
ALPHA_VANTAGE_KEY=tu_key_aqui
FINNHUB_KEY=tu_key_aqui
POLYGON_KEY=tu_key_aqui
NEWS_API_KEY=tu_key_aqui
```

Luego instala python-dotenv:
```bash
pip install python-dotenv
```

Y carga las keys en tu script:
```python
from dotenv import load_dotenv
import os

load_dotenv()

ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
FINNHUB_KEY = os.getenv('FINNHUB_KEY')
```

---

## 🎯 ¿Qué API Usar para Qué?

### Datos de Precios Históricos:
1. **Yahoo Finance** (Incluida) - Suficiente para la mayoría
2. **Alpha Vantage** - Más detallado, indicadores precalculados
3. **Polygon.io** - Alta calidad, ideal para backtesting

### Datos en Tiempo Real:
1. **Yahoo Finance** (15-20 min delay) - Gratis
2. **Polygon.io** - Tiempo real con plan pago
3. **Twelve Data** - Mejor balance gratis/pago

### Noticias:
1. **Finnhub** - Específico para finanzas
2. **NewsAPI** - General, más fuentes

### Análisis Fundamental:
1. **Alpha Vantage** - Ratios financieros
2. **Finnhub** - Recomendaciones de analistas
3. **Yahoo Finance** - Datos básicos incluidos

---

## ⚡ Comparativa Rápida

| API | Gratis | Límite/Día | Mejor Para | Registro |
|-----|--------|------------|------------|----------|
| **Yahoo Finance** | ✅ | Razonable | Todo uso general | ❌ No |
| **Alpha Vantage** | ✅ | 500 | Indicadores técnicos | ✅ Sí |
| **Finnhub** | ✅ | 60/min | Noticias | ✅ Sí |
| **Polygon.io** | ✅/💰 | 5/min (free) | Datos profesionales | ✅ Sí |
| **NewsAPI** | ✅ | 100 | Noticias generales | ✅ Sí |
| **Twelve Data** | ✅ | 800 | Balance gratis/pro | ✅ Sí |

---

## 🛡️ Buenas Prácticas

### 1. **Nunca subas tus API Keys a GitHub**
```bash
# Crea un .gitignore
echo ".env" >> .gitignore
echo "config_local.py" >> .gitignore
```

### 2. **Usa variables de entorno**
```python
import os
API_KEY = os.getenv('MI_API_KEY', 'default_key_if_not_found')
```

### 3. **Maneja errores de API**
```python
try:
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    print(f"Error de API: {e}")
    # Usa datos de respaldo o caché
```

### 4. **Implementa cache para ahorrar llamadas**
```python
import streamlit as st

@st.cache_data(ttl=3600)  # Cache por 1 hora
def get_api_data(symbol):
    # Tu llamada a la API aquí
    pass
```

### 5. **Respeta los límites de tasa**
```python
import time

def rate_limited_call(func, delay=1.0):
    result = func()
    time.sleep(delay)
    return result
```

---

## 🆓 Recomendación para Empezar

**Para uso personal/educativo:**
```
✅ Yahoo Finance (ya incluido) - NO necesitas ninguna API key
```

**Para análisis más avanzado:**
```
1. Registrate en Alpha Vantage (5 minutos)
2. Obtén 500 llamadas gratis por día
3. Agrega la key al script
```

**Para noticias y sentimiento:**
```
1. Registrate en Finnhub (2 minutos)
2. Obtén acceso a noticias en tiempo real
3. Mejora tus análisis con sentimiento de mercado
```

---

## 🔧 Instalación de Paquetes Adicionales

Si decides usar APIs adicionales:

```bash
pip install requests python-dotenv
```

Para agregar al requirements.txt:
```
requests==2.31.0
python-dotenv==1.0.0
```

---

## 📞 Soporte de APIs

- **Yahoo Finance**: No tiene soporte oficial, pero comunidad activa en GitHub
- **Alpha Vantage**: support@alphavantage.co
- **Finnhub**: support@finnhub.io
- **Polygon.io**: support@polygon.io
- **NewsAPI**: support@newsapi.org

---

## ⚠️ Nota Importante

El sistema **funciona completamente SIN configurar ninguna API adicional**. Yahoo Finance (yfinance) está incluido y no requiere registro ni API keys. 

Las APIs opcionales solo mejoran la funcionalidad con:
- Más datos históricos
- Noticias en tiempo real
- Indicadores adicionales
- Menor latencia

**Para empezar, simplemente ejecuta el sistema tal cual está.** ✅

---

## 📚 Recursos Adicionales

- **Yahoo Finance Documentación**: https://finance.yahoo.com/
- **Alpha Vantage Docs**: https://www.alphavantage.co/documentation/
- **Finnhub API Docs**: https://finnhub.io/docs/api
- **Polygon.io Docs**: https://polygon.io/docs/stocks
- **NewsAPI Docs**: https://newsapi.org/docs

---

**Versión**: 1.0  
**Última actualización**: Febrero 2025
