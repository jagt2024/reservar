"""
Script de prueba para verificar funcionalidad básica
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

print("🧪 Probando funcionalidad básica del sistema...")
print("-" * 50)

# Test 1: Descargar datos de una acción
print("\n✅ Test 1: Descargando datos de AAPL...")
try:
    data = yf.download("AAPL", period="1mo", progress=False)
    
    # Manejar MultiIndex si existe
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    print(f"   Datos descargados: {len(data)} registros")
    print(f"   Columnas: {list(data.columns)}")
    print(f"   Precio actual: ${data['Close'].iloc[-1]:.2f}")
    print("   ✓ Test 1 PASADO")
except Exception as e:
    print(f"   ✗ Test 1 FALLIDO: {e}")

# Test 2: Descargar datos de cripto
print("\n✅ Test 2: Descargando datos de BTC-USD...")
try:
    data = yf.download("BTC-USD", period="1mo", progress=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    print(f"   Datos descargados: {len(data)} registros")
    print(f"   Precio actual: ${data['Close'].iloc[-1]:.2f}")
    print("   ✓ Test 2 PASADO")
except Exception as e:
    print(f"   ✗ Test 2 FALLIDO: {e}")

# Test 3: Descargar datos de metal
print("\n✅ Test 3: Descargando datos de Oro (GC=F)...")
try:
    data = yf.download("GC=F", period="1mo", progress=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    print(f"   Datos descargados: {len(data)} registros")
    print(f"   Precio actual: ${data['Close'].iloc[-1]:.2f}")
    print("   ✓ Test 3 PASADO")
except Exception as e:
    print(f"   ✗ Test 3 FALLIDO: {e}")

# Test 4: Verificar paquetes instalados
print("\n✅ Test 4: Verificando paquetes instalados...")
try:
    import streamlit
    import plotly
    import sklearn
    import numpy
    print(f"   Streamlit: {streamlit.__version__}")
    print(f"   Plotly: {plotly.__version__}")
    print(f"   Scikit-learn: {sklearn.__version__}")
    print(f"   NumPy: {numpy.__version__}")
    print("   ✓ Test 4 PASADO")
except Exception as e:
    print(f"   ✗ Test 4 FALLIDO: {e}")

print("\n" + "=" * 50)
print("🎉 Pruebas completadas!")
print("\nSi todos los tests pasaron, el sistema está listo.")
print("Ejecuta: streamlit run trading_predictor.py")
print("=" * 50)
