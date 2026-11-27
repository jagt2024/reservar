# 🚀 Guía de Inicio Rápido - APIs

## ¿Necesito API Keys para usar el sistema?

### ❌ NO - El sistema funciona sin configurar nada

El **Trading Predictor Pro** usa **Yahoo Finance** que NO requiere API keys ni registro.

**Puedes empezar a usar el sistema inmediatamente:**

```bash
pip install -r requirements.txt
streamlit run trading_predictor.py
```

¡Eso es todo! 🎉

---

## 🌟 ¿Por qué agregar APIs opcionales?

Las APIs adicionales te dan:

| Beneficio | Con Yahoo Finance | Con APIs Premium |
|-----------|-------------------|------------------|
| **Datos históricos** | ✅ Últimos 10+ años | ✅ Más detallados |
| **Delay de datos** | ⏰ 15-20 minutos | ⚡ Tiempo real* |
| **Noticias** | ❌ No incluidas | ✅ En tiempo real |
| **Indicadores** | ✅ Calculados localmente | ✅ Precalculados |
| **Costo** | 🆓 Gratis | 🆓 Gratis (con límites) |

*Tiempo real disponible solo en planes pagos de algunas APIs

---

## 📝 Configuración en 3 Pasos (Opcional)

### Opción A: Para Principiantes (Recomendado)

**Simplemente usa el sistema como está** - Ya funciona con Yahoo Finance incluido.

### Opción B: Agregar Alpha Vantage (5 minutos)

Si quieres datos más detallados:

#### Paso 1: Obtén tu API Key
1. Ve a: https://www.alphavantage.co/support/#api-key
2. Ingresa tu email
3. Recibirás tu key inmediatamente (ejemplo: `ABC123XYZ456`)

#### Paso 2: Agrégala al script
Abre `trading_predictor.py` y busca esta sección (líneas 20-30):

```python
# Alpha Vantage (para datos más detallados)
# ALPHA_VANTAGE_KEY = "TU_API_KEY_AQUI"
```

Descomenta y agrega tu key:

```python
# Alpha Vantage (para datos más detallados)
ALPHA_VANTAGE_KEY = "ABC123XYZ456"  # Tu key real aquí
```

#### Paso 3: Instala el paquete (opcional)
```bash
pip install requests alpha-vantage
```

¡Listo! Ahora tienes acceso a 500 llamadas gratuitas por día.

---

### Opción C: Configuración Profesional con .env

Para mayor seguridad (recomendado si compartes tu código):

#### Paso 1: Instala python-dotenv
```bash
pip install python-dotenv
```

#### Paso 2: Crea archivo .env
Copia el archivo `.env.example` y renómbralo a `.env`:

```bash
cp .env.example .env
```

#### Paso 3: Edita .env con tus keys
Abre `.env` y agrega tus keys reales:

```bash
ALPHA_VANTAGE_KEY=ABC123XYZ456
FINNHUB_KEY=tu_finnhub_key_aqui
```

#### Paso 4: Modifica trading_predictor.py
Al inicio del archivo, agrega:

```python
from dotenv import load_dotenv
import os

load_dotenv()

# Cargar keys desde .env
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
FINNHUB_KEY = os.getenv('FINNHUB_KEY')
```

---

## 🎯 Casos de Uso Recomendados

### Para Aprender/Practicar:
```
✅ Yahoo Finance (incluido)
❌ No necesitas nada más
```

### Para Trading Serio:
```
✅ Yahoo Finance (datos históricos)
✅ Alpha Vantage (indicadores detallados)
✅ Finnhub (noticias y sentimiento)
```

### Para Desarrollo Profesional:
```
✅ Yahoo Finance (backup)
✅ Polygon.io (datos profesionales)
✅ Finnhub (noticias)
✅ Alpha Vantage (alternativa)
```

---

## 🔑 Obtener API Keys Rápido

### 1️⃣ Alpha Vantage (30 segundos)
- URL: https://www.alphavantage.co/support/#api-key
- Solo email, key instantánea
- Límite: 500 llamadas/día

### 2️⃣ Finnhub (2 minutos)
- URL: https://finnhub.io/register
- Email + contraseña
- Verificar email
- Límite: 60 llamadas/minuto

### 3️⃣ NewsAPI (2 minutos)
- URL: https://newsapi.org/register
- Email + datos básicos
- Key por email
- Límite: 100 requests/día

---

## ⚡ Tabla de Decisión Rápida

| Pregunta | Respuesta | Acción |
|----------|-----------|--------|
| ¿Solo quiero probar el sistema? | Sí | ✅ Usa Yahoo Finance (ya incluido) |
| ¿Quiero análisis más detallado? | Sí | 📝 Agrega Alpha Vantage |
| ¿Necesito noticias en tiempo real? | Sí | 📰 Agrega Finnhub |
| ¿Voy a compartir mi código? | Sí | 🔒 Usa .env para keys |
| ¿Es un proyecto comercial? | Sí | 💼 Considera planes pagos |

---

## 🛡️ Seguridad de API Keys

### ✅ HACER:
- ✅ Usar archivo .env
- ✅ Agregar .env al .gitignore
- ✅ Usar variables de entorno
- ✅ Rotar keys periódicamente

### ❌ NO HACER:
- ❌ Subir keys a GitHub
- ❌ Compartir keys en chat/email
- ❌ Hardcodear keys en el código
- ❌ Usar la misma key en múltiples proyectos

---

## 📊 Límites de APIs Gratuitas

| API | Llamadas/Día | Llamadas/Minuto | Restricciones |
|-----|--------------|-----------------|---------------|
| **Yahoo Finance** | Sin límite oficial | Moderado | Uso razonable |
| **Alpha Vantage** | 500 | 5 | Solo 1 key por email |
| **Finnhub** | Sin límite | 60 | Plan free limitado |
| **NewsAPI** | 100 | No especificado | Solo desarrollo |
| **Polygon.io** | Sin límite | 5 | Datos con delay |

---

## 🆘 Problemas Comunes

### "Invalid API Key"
- Verifica que copiaste la key completa
- Asegúrate de no tener espacios extra
- La key es case-sensitive

### "Rate limit exceeded"
- Espera unos minutos
- Reduce frecuencia de llamadas
- Considera upgrading al plan pago

### "API Key not working"
- Verifica que el servicio esté activo
- Algunos servicios requieren verificar email
- La key puede tardar unos minutos en activarse

---

## 📞 Soporte

### Para el Trading Predictor Pro:
- Revisa `TROUBLESHOOTING.md`
- Revisa `API_CONFIGURATION.md` (detalle completo)

### Para APIs específicas:
- **Alpha Vantage**: support@alphavantage.co
- **Finnhub**: support@finnhub.io
- **NewsAPI**: support@newsapi.org
- **Polygon.io**: support@polygon.io

---

## 🎓 Siguientes Pasos

1. **Prueba el sistema sin APIs adicionales** ✅
2. Si te gusta, registra Alpha Vantage (5 min) 📝
3. Experimenta con los datos 🧪
4. Considera agregar Finnhub para noticias 📰
5. Lee la documentación completa en `API_CONFIGURATION.md` 📚

---

## ✨ Resumen

**Para empezar AHORA:**
```bash
pip install -r requirements.txt
streamlit run trading_predictor.py
```

**Para mejorar DESPUÉS (opcional):**
1. Registra Alpha Vantage (5 min)
2. Copia tu key
3. Agrégala al script
4. ¡Disfruta de más datos!

**El sistema funciona perfectamente SIN configurar APIs adicionales.** 🚀

---

**Versión**: 1.0  
**Última actualización**: Febrero 2025
