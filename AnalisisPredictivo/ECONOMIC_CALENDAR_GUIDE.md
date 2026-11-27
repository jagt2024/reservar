# 📅 Guía: Calendario Económico en Tiempo Real

## 🎯 Resumen

El sistema incluye un **calendario económico** que muestra eventos importantes que pueden afectar los mercados financieros. Por defecto, muestra eventos típicos, pero puedes conectarlo a APIs gratuitas para obtener datos en tiempo real.

---

## 📊 Tres Niveles de Funcionalidad

### 🟢 Nivel 1: Sin Configuración (Por Defecto)
**Qué obtienes:**
- Calendario con eventos económicos típicos de EE.UU.
- Fechas proyectadas basadas en calendario habitual
- Clasificación de impacto (Alto, Medio, Bajo)

**Ventajas:**
✅ Funciona inmediatamente sin configurar nada
✅ Muestra eventos comunes que se repiten regularmente
✅ Suficiente para aprendizaje y práctica

**Limitaciones:**
❌ Fechas aproximadas, no exactas
❌ Sin datos reales (actual, estimate, previous)
❌ No incluye eventos especiales

---

### 🟡 Nivel 2: Con Finnhub API (Recomendado)
**Qué obtienes:**
- ✅ Calendario económico en tiempo real
- ✅ Fechas exactas de publicación
- ✅ Datos reales: Actual, Estimate, Previous
- ✅ Eventos de earnings corporativos
- ✅ Actualizaciones diarias

**Configuración (5 minutos):**

#### Paso 1: Registrarse en Finnhub
1. Ve a: https://finnhub.io/register
2. Ingresa tu email y crea una contraseña
3. Verifica tu email
4. En tu dashboard, copia tu API Key

#### Paso 2: Agregar la Key al Sistema
Abre `trading_predictor.py` y busca esta sección (líneas ~25-35):

```python
# Finnhub (para noticias y análisis)
# FINNHUB_KEY = "TU_API_KEY_AQUI"
```

Descomenta y agrega tu key:

```python
# Finnhub (para noticias y análisis)
FINNHUB_KEY = "c5q2vkpr01qjfh3tb7u0c5q2vkpr01qjfh3tb7ug"  # Tu key real aquí
```

#### Paso 3: Reinicia la Aplicación
```bash
streamlit run trading_predictor.py
```

¡Listo! Ahora tendrás eventos económicos en tiempo real 🎉

**Límites del Plan Gratuito:**
- 60 llamadas por minuto
- Suficiente para uso personal
- Datos económicos básicos incluidos

---

### 🔵 Nivel 3: Con Alpha Vantage (Alternativa)
**Qué obtienes:**
- ✅ Indicadores económicos históricos
- ✅ Datos de CPI, desempleo, retail sales
- ✅ Valores reales publicados

**Configuración (30 segundos):**

#### Paso 1: Obtener API Key
1. Ve a: https://www.alphavantage.co/support/#api-key
2. Ingresa tu email
3. Recibirás tu key instantáneamente

#### Paso 2: Agregar al Sistema
```python
# Alpha Vantage (para datos más detallados)
ALPHA_VANTAGE_KEY = "ABC123XYZ456"  # Tu key aquí
```

**Límites del Plan Gratuito:**
- 500 llamadas por día
- 5 llamadas por minuto
- Indicadores económicos básicos

**Nota:** Alpha Vantage proporciona datos históricos de indicadores económicos, no un calendario de eventos futuros. Es complementario a Finnhub.

---

## 🔄 Comparativa de APIs para Calendario Económico

| Característica | Sin API | Finnhub | Alpha Vantage |
|----------------|---------|---------|---------------|
| **Costo** | Gratis | Gratis | Gratis |
| **Configuración** | Ninguna | 5 min | 30 seg |
| **Fechas exactas** | ❌ | ✅ | ❌ |
| **Eventos futuros** | ✅ (aprox.) | ✅ (reales) | ❌ |
| **Datos históricos** | ❌ | ✅ | ✅ |
| **Actual/Estimate** | ❌ | ✅ | ✅ |
| **Límite diario** | N/A | Sin límite | 500 |
| **Mejor para** | Práctica | Trading real | Análisis histórico |

---

## 📋 Eventos del Calendario Económico

### Eventos de Alto Impacto ⚠️

#### 1. **CPI (Índice de Precios al Consumidor)**
- **Frecuencia**: Mensual
- **Impacto**: MUY ALTO
- **Por qué importa**: Mide la inflación, afecta decisiones de la Fed
- **Trading**: Evita abrir posiciones 30 min antes/después

#### 2. **NFP (Nóminas No Agrícolas)**
- **Frecuencia**: Primer viernes de cada mes
- **Impacto**: MUY ALTO
- **Por qué importa**: Indicador clave del empleo en EE.UU.
- **Trading**: Alta volatilidad, spreads amplios

#### 3. **Minutas del FOMC (Fed)**
- **Frecuencia**: 8 veces al año
- **Impacto**: MUY ALTO
- **Por qué importa**: Política monetaria y tasas de interés
- **Trading**: Puede cambiar tendencia del mercado

#### 4. **Tasa de Desempleo**
- **Frecuencia**: Mensual
- **Impacto**: ALTO
- **Por qué importa**: Salud del mercado laboral
- **Trading**: Publicado junto con NFP

#### 5. **PPI (Índice de Precios al Productor)**
- **Frecuencia**: Mensual
- **Impacto**: ALTO
- **Por qué importa**: Indicador adelantado de inflación
- **Trading**: Precede al CPI

---

### Eventos de Medio Impacto 📊

#### 6. **Ventas Minoristas**
- **Frecuencia**: Mensual
- **Impacto**: MEDIO
- **Por qué importa**: Gasto del consumidor

#### 7. **PMI Manufacturero**
- **Frecuencia**: Mensual
- **Impacto**: MEDIO
- **Por qué importa**: Salud del sector industrial

#### 8. **Confianza del Consumidor**
- **Frecuencia**: Mensual
- **Impacto**: MEDIO
- **Por qué importa**: Sentimiento económico

#### 9. **Solicitudes de Desempleo**
- **Frecuencia**: Semanal (jueves)
- **Impacto**: MEDIO
- **Por qué importa**: Indicador semanal del empleo

---

### Eventos de Bajo Impacto 📉

#### 10. **Ventas de Viviendas**
- **Impacto**: BAJO
- **Por qué importa**: Sector inmobiliario

#### 11. **Inventarios de Petróleo**
- **Frecuencia**: Semanal
- **Impacto**: BAJO (excepto para energía)
- **Por qué importa**: Afecta precios del petróleo

---

## 💡 Cómo Usar el Calendario para Trading

### Antes del Evento (1-2 días)
1. **Revisa el calendario**: Identifica eventos de alto impacto
2. **Analiza expectativas**: Compara estimate vs previous
3. **Evalúa consenso**: ¿Qué esperan los analistas?
4. **Ajusta posiciones**: Reduce riesgo o cierra posiciones

### Durante el Evento (5 min antes - 30 min después)
1. **No operes**: Alta volatilidad, spreads amplios
2. **Observa reacción**: ¿Mercado reacciona al dato?
3. **Espera confirmación**: Falsos breakouts son comunes
4. **Protege capital**: Usa stops amplios si tienes posiciones

### Después del Evento (30 min - 2 horas)
1. **Analiza resultado**: Actual vs Estimate
2. **Identifica tendencia**: Dirección definida
3. **Busca oportunidades**: Entrada con mejor timing
4. **Gestiona riesgo**: Stops ajustados al nuevo contexto

---

## 📈 Interpretación de Datos

### Ejemplo Real:

```
Evento: CPI (Inflación)
Date: 2025-02-15
Estimate: 2.5%
Previous: 2.3%
Actual: 2.7%
```

**Interpretación:**
- **Actual > Estimate**: ✅ Inflación más alta de lo esperado
- **Impacto**: Dólar sube, acciones bajan (posible alza de tasas)
- **Trading**: Corto en acciones tech, largo en USD

---

## 🔧 Solución de Problemas

### Error: "Finnhub API no disponible"
**Causa:** Key no configurada o inválida
**Solución:**
1. Verifica que copiaste la key completa
2. No debe tener espacios antes/después
3. Reinicia Streamlit después de agregar la key

### Error: "Rate limit exceeded"
**Causa:** Demasiadas llamadas a la API
**Solución:**
1. Espera 1 minuto (Finnhub: 60 llamadas/min)
2. El sistema tiene cache de 1 hora
3. Cierra y vuelve a abrir la pestaña del calendario

### Calendario vacío o con errores
**Causa:** Problemas de conexión o API
**Solución:**
1. Verifica tu conexión a Internet
2. El sistema automáticamente usa calendario de respaldo
3. Revisa la consola de Streamlit para errores

---

## 🎯 Recomendaciones por Nivel de Experiencia

### 👶 Principiante
- Usa calendario sin API (aprende los conceptos)
- Estudia los eventos y su impacto
- No operes durante eventos de alto impacto
- **Recomendación**: Nivel 1 (sin API)

### 🧑 Intermedio
- Configura Finnhub API (5 minutos)
- Practica timing alrededor de eventos
- Aprende a leer Actual vs Estimate
- **Recomendación**: Nivel 2 (Finnhub)

### 👨‍💼 Avanzado
- Usa Finnhub + Alpha Vantage
- Analiza correlaciones históricas
- Desarrolla estrategias para eventos
- **Recomendación**: Nivel 3 (ambas APIs)

---

## 📚 Recursos Adicionales

### Calendarios Económicos Externos (para comparar):
- **Investing.com**: https://www.investing.com/economic-calendar/
- **ForexFactory**: https://www.forexfactory.com/calendar
- **TradingEconomics**: https://tradingeconomics.com/calendar

### Aprende más sobre indicadores:
- **CPI**: https://www.bls.gov/cpi/
- **NFP**: https://www.bls.gov/news.release/empsit.toc.htm
- **Fed**: https://www.federalreserve.gov/

---

## ✅ Checklist de Configuración

- [ ] Decidí qué nivel de calendario quiero
- [ ] (Nivel 2) Me registré en Finnhub
- [ ] (Nivel 2) Copié mi API key
- [ ] (Nivel 2) Agregué la key a trading_predictor.py
- [ ] Reinicié la aplicación
- [ ] Verifiqué que aparece "Finnhub API (datos en tiempo real)"
- [ ] El calendario muestra eventos reales
- [ ] Puedo ver columnas: Actual, Estimate, Previous

---

## 🎉 Resumen Rápido

**¿Quieres calendario en tiempo real?**

```bash
# Paso 1: Registrate (5 min)
https://finnhub.io/register

# Paso 2: Copia tu key
[En tu dashboard de Finnhub]

# Paso 3: Agrégala al código
FINNHUB_KEY = "tu_key_aqui"

# Paso 4: Reinicia
streamlit run trading_predictor.py
```

**¡Listo! Ahora tienes eventos económicos reales** 🚀

---

**El calendario funciona sin configurar APIs, pero con Finnhub obtienes datos reales y fechas exactas.**

---

**Versión**: 1.0  
**Última actualización**: Febrero 2025
