# 🔧 Guía de Solución de Problemas

## Problemas Comunes y Soluciones

### 1. Error: "ValueError: Cannot set a DataFrame with multiple columns..."

**Causa**: Este error ocurría cuando yfinance devolvía DataFrames con MultiIndex en las columnas.

**Solución**: ✅ YA CORREGIDO en la versión actual del script. El código ahora maneja automáticamente los MultiIndex.

**Qué hace la corrección**:
```python
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)
```

---

### 2. Error: "No se pudieron obtener datos para [símbolo]"

**Posibles causas y soluciones**:

#### A. Problema de conexión a Internet
```bash
# Verifica tu conexión
ping yahoo.com
```

#### B. Símbolo incorrecto o no disponible
- Verifica el símbolo en Yahoo Finance: https://finance.yahoo.com
- Algunos activos pueden tener símbolos diferentes

#### C. Límite de tasa de Yahoo Finance
- Espera 1-2 minutos y vuelve a intentar
- Reduce la frecuencia de actualización

**Solución temporal**: Cambia el período de datos
```python
# En lugar de fechas personalizadas, usa períodos predefinidos:
data = yf.download(symbol, period="1y")  # 1 año
data = yf.download(symbol, period="6mo") # 6 meses
data = yf.download(symbol, period="1mo") # 1 mes
```

---

### 3. Error: "AttributeError: 'NoneType' object has no attribute..."

**Causa**: Los datos no se descargaron correctamente.

**Solución**:
1. Verifica que el símbolo sea correcto
2. Cambia el rango de fechas (más reciente)
3. Reinicia la aplicación

---

### 4. Advertencias de pandas (FutureWarning)

**Mensaje típico**: 
```
FutureWarning: DataFrame.fillna with 'method' is deprecated
```

**Solución**: ✅ YA CORREGIDO. El código ahora usa `.ffill()` en lugar de `.fillna(method='ffill')`

---

### 5. La predicción no funciona o da error

**Posibles causas**:

#### A. Datos insuficientes
```
Error: No hay suficientes datos para generar predicciones
```
**Solución**: Aumenta el rango de fechas (mínimo 3 meses de datos históricos)

#### B. Valores NaN o infinitos
**Solución**: El código ahora limpia automáticamente estos valores:
```python
df_ml = df_ml.replace([np.inf, -np.inf], np.nan)
df_ml = df_ml.dropna()
```

---

### 6. Gráficos no se muestran correctamente

**Causa**: Problema con Plotly o navegador

**Soluciones**:
1. Limpia la caché del navegador
2. Actualiza Plotly:
```bash
pip install --upgrade plotly
```
3. Prueba en otro navegador (Chrome, Firefox, Edge)

---

### 7. Streamlit no se ejecuta

**Error típico**:
```
streamlit: command not found
```

**Solución**:
```bash
# Verifica instalación
pip show streamlit

# Si no está instalado
pip install streamlit

# Si está instalado pero no se encuentra
python -m streamlit run trading_predictor.py
```

---

### 8. Error al instalar paquetes

**Error típico**:
```
ERROR: Could not build wheels for [paquete]
```

**Soluciones**:

#### Para Windows:
```bash
# Actualiza pip
python -m pip install --upgrade pip

# Instala Visual C++ Build Tools si es necesario
# Descarga desde: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

#### Para macOS:
```bash
# Instala Command Line Tools
xcode-select --install

# Actualiza pip
pip3 install --upgrade pip
```

#### Para Linux:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-dev python3-pip

# Actualiza pip
pip3 install --upgrade pip
```

---

### 9. Los datos no se actualizan en tiempo real

**Causa**: Cache de Streamlit o Yahoo Finance

**Soluciones**:

#### A. Forzar actualización en la app
- Haz clic en el botón "🔄 Actualizar Datos"
- Esto ignora la caché y descarga datos frescos

#### B. Modificar tiempo de caché
En `trading_predictor.py`, línea ~30:
```python
@st.cache_data(ttl=300)  # Cambiar de 300 a 60 para actualizar cada minuto
```

#### C. Limpiar caché de Streamlit
```bash
streamlit cache clear
```

---

### 10. Error: "ModuleNotFoundError"

**Error típico**:
```
ModuleNotFoundError: No module named 'yfinance'
```

**Solución**:
```bash
# Verifica que estés en el entorno correcto
# Si usas entorno virtual:
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Instala las dependencias
pip install -r requirements.txt
```

---

### 11. Rendimiento lento

**Síntomas**: La app tarda mucho en cargar o actualizar

**Soluciones**:

1. **Reduce el rango de fechas**: Usa menos meses de datos históricos
2. **Reduce días de predicción**: Predice menos días (ej: 30 en lugar de 90)
3. **Ajusta el modelo**:
```python
# En la función predict_prices, reduce estimadores:
model = RandomForestRegressor(n_estimators=50, ...)  # en lugar de 100
```

---

### 12. Top Performers muestra datos vacíos

**Causa**: Problemas descargando múltiples símbolos simultáneamente

**Solución**:
1. Espera unos segundos y recarga la pestaña
2. El código tiene manejo de errores que omite símbolos problemáticos
3. Si persiste, verifica tu conexión

---

### 13. Error en Windows con rutas de archivo

**Error típico**:
```
FileNotFoundError: [WinError 3]
```

**Solución**:
```python
# Usa rutas raw strings o barras diagonales
path = r"C:\Users\tu_usuario\trading_predictor.py"
# o
path = "C:/Users/tu_usuario/trading_predictor.py"
```

---

## 🧪 Script de Diagnóstico

Si tienes problemas, ejecuta primero el script de prueba:

```bash
python test_setup.py
```

Este script verificará:
- ✅ Descarga de datos de acciones
- ✅ Descarga de datos de criptos
- ✅ Descarga de datos de metales
- ✅ Paquetes instalados correctamente

---

## 📞 Pasos de Diagnóstico General

Cuando tengas un error:

### Paso 1: Lee el mensaje de error completo
Copia el error completo, no solo la última línea

### Paso 2: Verifica instalaciones
```bash
pip list | grep -E "streamlit|yfinance|pandas|plotly|scikit"
```

### Paso 3: Prueba con un símbolo simple
En lugar de usar la app completa, prueba:
```python
import yfinance as yf
data = yf.download("AAPL", period="1mo")
print(data.head())
```

### Paso 4: Verifica versiones de Python
```bash
python --version
# Debe ser Python 3.8 o superior
```

### Paso 5: Reinstala en entorno limpio
```bash
# Crea nuevo entorno virtual
python -m venv venv_nuevo
source venv_nuevo/bin/activate  # o venv_nuevo\Scripts\activate en Windows
pip install -r requirements.txt
streamlit run trading_predictor.py
```

---

## 🔄 Actualizaciones de Paquetes

Para mantener todo actualizado:

```bash
pip install --upgrade streamlit yfinance pandas plotly scikit-learn numpy
```

---

## ⚡ Optimizaciones Recomendadas

### Para mejor rendimiento:

1. **Usa períodos fijos en lugar de rangos de fecha personalizados**:
```python
data = yf.download(symbol, period="1y")  # Más rápido que start/end
```

2. **Reduce datos en Top Performers**:
```python
# Cambia de analizar todos los activos a solo unos pocos
```

3. **Aumenta tiempo de caché**:
```python
@st.cache_data(ttl=600)  # 10 minutos en lugar de 5
```

---

## 📧 Registro de Errores

Si encuentras un error persistente, guarda esta información:

1. **Mensaje de error completo**
2. **Versión de Python**: `python --version`
3. **Versiones de paquetes**: `pip list`
4. **Sistema operativo**: Windows/macOS/Linux
5. **Comando ejecutado**: `streamlit run ...`
6. **Símbolo que causó el problema**

---

## ✅ Verificación de Instalación Exitosa

Deberías ver:

1. ✅ Sin errores al ejecutar `pip install -r requirements.txt`
2. ✅ Streamlit se abre en el navegador automáticamente
3. ✅ Los datos se cargan en menos de 10 segundos
4. ✅ Los gráficos se muestran correctamente
5. ✅ Las predicciones se generan sin errores

---

**¿Todo funciona?** ¡Excelente! Ahora puedes disfrutar del Trading Predictor Pro 🎉

**¿Aún tienes problemas?** Revisa los pasos de diagnóstico o verifica los logs de la consola donde ejecutaste Streamlit.
