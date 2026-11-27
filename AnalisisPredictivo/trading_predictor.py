"""
Trading Predictor Pro - Sistema de Análisis Predictivo

APIs UTILIZADAS:
1. Yahoo Finance (yfinance) - GRATUITA, sin API key necesaria
   - Datos de acciones, criptos y metales
   - Datos históricos y en tiempo real (con ligero delay)
   
2. APIs OPCIONALES para mejorar funcionalidad (requieren registro):
   - Alpha Vantage: https://www.alphavantage.co/support/#api-key (GRATIS: 500 llamadas/día)
   - Finnhub: https://finnhub.io/ (GRATIS: 60 llamadas/minuto)
   - Polygon.io: https://polygon.io/ (GRATIS: nivel básico disponible)
   - NewsAPI: https://newsapi.org/ (GRATIS: 100 requests/día)

CONFIGURACIÓN:
- Por defecto usa Yahoo Finance (sin API key)
- Para habilitar APIs premium, descomentar secciones correspondientes
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# ============================================
# CONFIGURACIÓN DE API KEYS (OPCIONAL)
# ============================================
# Descomenta y completa para usar APIs premium:

# Alpha Vantage (para datos más detallados)
# ALPHA_VANTAGE_KEY = "TU_API_KEY_AQUI"
# Obtén tu key gratis en: https://www.alphavantage.co/support/#api-key

# Finnhub (para noticias y análisis)
FINNHUB_KEY = "d68ueq1r01qs7u9k27p0d68ueq1r01qs7u9k27pg"
# Obtén tu key gratis en: https://finnhub.io/register

# NewsAPI (para noticias financieras)
# NEWS_API_KEY = "TU_API_KEY_AQUI"
# Obtén tu key gratis en: https://newsapi.org/register

# ============================================

# Configuración de la página
st.set_page_config(
    page_title="Trading Predictor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# Título principal
st.title("📈 Trading Predictor Pro - Análisis Predictivo en Tiempo Real")

# Diccionarios de activos
STOCKS = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "Tesla": "TSLA",
    "Meta": "META",
    "NVIDIA": "NVDA",
    "Netflix": "NFLX",
    "JPMorgan": "JPM",
    "Visa": "V",
    "Walmart": "WMT",
    "Coca-Cola": "KO"
}

CRYPTOS = {
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Binance Coin": "BNB-USD",
    "Cardano": "ADA-USD",
    "Solana": "SOL-USD",
    "Ripple": "XRP-USD",
    "Polkadot": "DOT-USD",
    "Dogecoin": "DOGE-USD"
}

METALS = {
    "Oro": "GC=F",
    "Plata": "SI=F",
    "Cobre": "HG=F",
    "Platino": "PL=F",
    "Paladio": "PA=F"
}

# Función para obtener datos en tiempo real
@st.cache_data(ttl=300)  # Cache de 5 minutos
def get_real_time_data(symbol, start_date, end_date):
    try:
        data = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if data.empty:
            return None
        
        # Si el DataFrame tiene múltiples niveles de columnas, aplanarlos
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        # Asegurarse de que las columnas estén en el formato correcto
        if 'Adj Close' in data.columns and 'Close' not in data.columns:
            data['Close'] = data['Adj Close']
        
        return data
    except Exception as e:
        st.error(f"Error al obtener datos para {symbol}: {str(e)}")
        return None

# Función para calcular indicadores técnicos
def calculate_indicators(df):
    # Crear una copia para evitar modificar el original
    df = df.copy()
    
    # Primero, asegurarse de que no hay MultiIndex en columnas
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Asegurarse de que tenemos las columnas necesarias
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Falta la columna requerida: {col}")
            return None
    
    try:
        # Extraer solo la serie Close para cálculos
        close_series = df['Close'].copy()
        
        # Si Close es un DataFrame (MultiIndex), convertir a Series
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]
        
        # Media móvil simple
        df['SMA_20'] = close_series.rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = close_series.rolling(window=50, min_periods=1).mean()
        
        # RSI
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        
        # Evitar división por cero
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        df['RSI'] = rsi.fillna(50)  # RSI neutro por defecto
        
        # MACD
        exp1 = close_series.ewm(span=12, adjust=False).mean()
        exp2 = close_series.ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        bb_middle = close_series.rolling(window=20, min_periods=1).mean()
        bb_std = close_series.rolling(window=20, min_periods=1).std()
        df['BB_middle'] = bb_middle
        df['BB_upper'] = bb_middle + (bb_std * 2)
        df['BB_lower'] = bb_middle - (bb_std * 2)
        
        # Volatilidad
        returns = close_series.pct_change()
        volatility = returns.rolling(window=20, min_periods=1).std() * np.sqrt(252)
        df['Volatility'] = volatility.fillna(0)
        
        # Rellenar NaN con método forward fill
        df = df.ffill()
        
        # Rellenar los restantes con backward fill
        df = df.bfill()
        
        return df
        
    except Exception as e:
        st.error(f"Error al calcular indicadores: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")
        return None

# Función de predicción con Machine Learning
def predict_prices(df, days_ahead):
    try:
        df = df.copy()
        df = df.dropna()
        
        if len(df) < 50:
            return None, None
        
        # Preparar features
        df['Returns'] = df['Close'].pct_change()
        df['Volume_Change'] = df['Volume'].pct_change()
        
        # Features para el modelo
        feature_columns = ['Returns', 'Volume_Change', 'RSI', 'MACD', 'Volatility']
        
        # Verificar que todas las columnas existan
        for col in feature_columns:
            if col not in df.columns:
                st.warning(f"Columna {col} no encontrada. No se puede predecir.")
                return None, None
        
        df_ml = df[feature_columns].copy()
        df_ml = df_ml.replace([np.inf, -np.inf], np.nan)
        df_ml = df_ml.dropna()
        
        if len(df_ml) < 50:
            return None, None
        
        # Preparar datos
        X = df_ml.values[:-1]
        y = df['Close'].values[len(df) - len(df_ml) + 1:]
        
        if len(X) != len(y):
            # Ajustar longitudes
            min_len = min(len(X), len(y))
            X = X[:min_len]
            y = y[:min_len]
        
        # Escalar
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Entrenar modelo
        model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10, n_jobs=-1)
        model.fit(X_scaled, y)
        
        # Predicción
        predictions = []
        last_price = df['Close'].iloc[-1]
        
        # Usar la última fila de features para predecir
        last_features = X_scaled[-1].reshape(1, -1)
        
        for i in range(days_ahead):
            pred_price = model.predict(last_features)[0]
            predictions.append(pred_price)
            
            # Para simplificar, mantenemos las mismas features
            # En un modelo más avanzado, actualizaríamos las features
        
        return predictions, model.feature_importances_
        
    except Exception as e:
        st.error(f"Error en predicción: {str(e)}")
        return None, None

# Función para análisis de mejores oportunidades de inversión
@st.cache_data(ttl=300)
def analyze_best_investment_opportunities(timeframe='3d'):
    """
    Analiza todos los activos disponibles y determina las mejores oportunidades
    basándose en múltiples factores: momentum, volatilidad, RSI, y predicción.
    
    Args:
        timeframe: '3d' para 3 días, '3h' para 3 horas (aproximado)
    
    Returns:
        DataFrame con análisis completo y rankings
    """
    all_assets = {**STOCKS, **CRYPTOS, **METALS}
    results = []
    
    # Determinar período de descarga
    if timeframe == '3h':
        period = '1d'  # Yahoo Finance no tiene datos de 3h, usar 1 día con intervalos
        interval = '1h'
    else:
        period = '5d'  # Usar 5 días para tener suficientes datos
        interval = '1d'
    
    for name, symbol in all_assets.items():
        try:
            # Descargar datos
            data = yf.download(symbol, period=period, interval=interval, progress=False)
            
            if data.empty or len(data) < 3:
                continue
            
            # Manejar MultiIndex - CRÍTICO
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # Eliminar duplicados de columnas si existen
            data = data.loc[:, ~data.columns.duplicated()]
            
            # Extraer series como objetos Series simples para evitar MultiIndex
            close_series = pd.Series(data['Close'].values, index=data.index)
            volume_series = pd.Series(data['Volume'].values, index=data.index) if 'Volume' in data.columns else pd.Series(0, index=data.index)
            
            # Calcular métricas
            current_price = float(close_series.iloc[-1])
            
            # Momentum (últimos 3 períodos)
            if len(close_series) >= 3:
                price_3_periods_ago = float(close_series.iloc[-3])
                momentum = ((current_price - price_3_periods_ago) / price_3_periods_ago) * 100
            else:
                momentum = 0
            
            # Volatilidad (últimos 3 períodos)
            returns = close_series.pct_change().dropna()
            volatility = float(returns.std() * 100) if len(returns) > 0 else 0
            
            # RSI simplificado
            delta = close_series.diff()
            gain = delta.where(delta > 0, 0).rolling(window=min(14, len(data)), min_periods=1).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=min(14, len(data)), min_periods=1).mean()
            
            # Evitar división por cero
            loss = loss.replace(0, np.nan)
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            current_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1]) else 50
            
            # Tendencia (regresión lineal simple)
            if len(close_series) >= 3:
                x = np.arange(len(close_series))
                y = close_series.values
                z = np.polyfit(x, y, 1)
                trend_slope = z[0]
                trend = "Alcista" if trend_slope > 0 else "Bajista"
            else:
                trend = "Neutral"
                trend_slope = 0
            
            # Volumen comparado con promedio
            avg_volume = float(volume_series.mean())
            current_volume = float(volume_series.iloc[-1])
            volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1
            
            # Determinar categoría
            if symbol in STOCKS.values():
                category = "Acción"
            elif symbol in CRYPTOS.values():
                category = "Cripto"
            else:
                category = "Metal"
            
            # Puntuación compuesta (0-100)
            # Factores: momentum (30%), RSI (20%), volatilidad (20%), tendencia (20%), volumen (10%)
            
            # Normalizar momentum (-10 a +10 → 0 a 100)
            momentum_score = min(100, max(0, (momentum + 10) * 5))
            
            # RSI score (30-70 es óptimo)
            if 30 <= current_rsi <= 70:
                rsi_score = 100
            elif current_rsi < 30:
                rsi_score = current_rsi * 2  # Sobreventa puede ser oportunidad
            else:
                rsi_score = 100 - (current_rsi - 70) * 2  # Penalizar sobrecompra
            
            # Volatilidad score (moderada es mejor)
            volatility_score = max(0, 100 - (volatility * 10))
            
            # Tendencia score
            trend_score = 100 if trend == "Alcista" else 30
            
            # Volumen score
            volume_score = min(100, volume_ratio * 50)
            
            # Score total
            total_score = (
                momentum_score * 0.30 +
                rsi_score * 0.20 +
                volatility_score * 0.20 +
                trend_score * 0.20 +
                volume_score * 0.10
            )
            
            # Recomendación
            if total_score >= 75:
                recommendation = "Compra Fuerte"
                emoji = "🟢"
            elif total_score >= 60:
                recommendation = "Compra"
                emoji = "🟡"
            elif total_score >= 40:
                recommendation = "Mantener"
                emoji = "⚪"
            elif total_score >= 25:
                recommendation = "Vender"
                emoji = "🟠"
            else:
                recommendation = "Vender Fuerte"
                emoji = "🔴"
            
            results.append({
                'Nombre': name,
                'Símbolo': symbol,
                'Categoría': category,
                'Precio': current_price,
                'Momentum 3P (%)': momentum,
                'Volatilidad (%)': volatility,
                'RSI': current_rsi,
                'Tendencia': trend,
                'Vol. Ratio': volume_ratio,
                'Score': total_score,
                'Recomendación': recommendation,
                'Emoji': emoji
            })
            
        except Exception as e:
            continue
    
    if not results:
        return None
    
    # Crear DataFrame y ordenar por score
    df = pd.DataFrame(results)
    df = df.sort_values('Score', ascending=False)
    
    return df

# Función para análisis detallado de un activo específico
def detailed_asset_analysis(symbol, name, period='5d'):
    """
    Análisis profundo de un activo específico
    """
    try:
        data = yf.download(symbol, period=period, interval='1h' if period == '1d' else '1d', progress=False)
        
        if data.empty:
            return None
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        # Calcular indicadores
        data = calculate_indicators(data)
        
        if data is None or data.empty:
            return None
        
        # Métricas avanzadas
        current_price = data['Close'].iloc[-1]
        max_price = data['High'].max()
        min_price = data['Low'].min()
        
        # Distancia de máximo y mínimo
        distance_from_high = ((max_price - current_price) / max_price) * 100
        distance_from_low = ((current_price - min_price) / min_price) * 100
        
        # Soporte y resistencia (simplificado)
        recent_highs = data['High'].nlargest(3).mean()
        recent_lows = data['Low'].nsmallest(3).mean()
        
        # Análisis de volumen
        volume_trend = "Creciente" if data['Volume'].iloc[-3:].mean() > data['Volume'].mean() else "Decreciente"
        
        return {
            'data': data,
            'current_price': current_price,
            'distance_from_high': distance_from_high,
            'distance_from_low': distance_from_low,
            'support': recent_lows,
            'resistance': recent_highs,
            'volume_trend': volume_trend
        }
        
    except Exception as e:
        return None
def get_top_performers(symbols_dict, days=1):
    performance = {}
    
    for name, symbol in symbols_dict.items():
        try:
            data = yf.download(symbol, period=f"{days}d", progress=False)
            
            if data.empty:
                continue
                
            # Manejar MultiIndex si existe
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # Verificar que tenemos suficientes datos
            if len(data) > 1:
                close_values = data['Close'].dropna()
                volume_values = data['Volume'].dropna() if 'Volume' in data.columns else pd.Series([0])
                
                if len(close_values) > 1:
                    change = ((close_values.iloc[-1] - close_values.iloc[0]) / close_values.iloc[0]) * 100
                    performance[name] = {
                        'symbol': symbol,
                        'change': change,
                        'price': close_values.iloc[-1],
                        'volume': volume_values.iloc[-1] if len(volume_values) > 0 else 0
                    }
        except Exception as e:
            continue
    
    return performance

# Función para calendario económico (eventos en tiempo real)
@st.cache_data(ttl=3600)  # Cache de 1 hora para calendario
def get_economic_calendar():
    """
    Obtiene eventos económicos reales usando múltiples fuentes gratuitas.
    Prioridad: 1) Finnhub, 2) Trading Economics (si configurado), 3) Datos de respaldo
    """
    events = []
    
    # Intentar con Finnhub (si está configurado)
    try:
        # Verificar si FINNHUB_KEY está definido en el código
        if 'FINNHUB_KEY' in globals() and FINNHUB_KEY and FINNHUB_KEY != "TU_API_KEY_AQUI":
            import requests
            from datetime import datetime, timedelta
            
            # Obtener calendario de earnings (eventos corporativos)
            today = datetime.now()
            end_date = today + timedelta(days=30)
            
            url = f"https://finnhub.io/api/v1/calendar/economic?token={FINNHUB_KEY}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'economicCalendar' in data:
                    for item in data['economicCalendar'][:20]:  # Primeros 20 eventos
                        # Clasificar impacto basado en importancia
                        impact = "Medio"
                        event_name = item.get('event', 'Evento Económico')
                        
                        if any(keyword in event_name.lower() for keyword in ['cpi', 'nfp', 'gdp', 'fomc', 'fed', 'unemployment']):
                            impact = "Alto"
                        elif any(keyword in event_name.lower() for keyword in ['housing', 'retail', 'pmi', 'ism']):
                            impact = "Medio"
                        else:
                            impact = "Bajo"
                        
                        events.append({
                            'date': item.get('time', today.strftime('%Y-%m-%d')).split('T')[0],
                            'event': event_name,
                            'impact': impact,
                            'actual': item.get('actual', '-'),
                            'estimate': item.get('estimate', '-'),
                            'previous': item.get('prev', '-')
                        })
                
                if events:
                    return pd.DataFrame(events)
    except Exception as e:
        st.info("Finnhub API no disponible, usando calendario de respaldo")
    
    # Intentar con Alpha Vantage Economic Indicators (si está configurado)
    try:
        if 'ALPHA_VANTAGE_KEY' in globals() and ALPHA_VANTAGE_KEY and ALPHA_VANTAGE_KEY != "TU_API_KEY_AQUI":
            import requests
            
            # Alpha Vantage tiene indicadores económicos históricos
            indicators = ['CPI', 'RETAIL_SALES', 'UNEMPLOYMENT', 'NONFARM_PAYROLL']
            
            for indicator in indicators[:3]:  # Primeros 3 para no exceder límite
                try:
                    url = f"https://www.alphavantage.co/query?function={indicator}&apikey={ALPHA_VANTAGE_KEY}"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data and len(data['data']) > 0:
                            latest = data['data'][0]
                            events.append({
                                'date': latest.get('date', 'Próximo'),
                                'event': f"Publicación de {indicator.replace('_', ' ').title()}",
                                'impact': "Alto" if indicator in ['CPI', 'NONFARM_PAYROLL'] else "Medio",
                                'actual': latest.get('value', '-'),
                                'estimate': '-',
                                'previous': data['data'][1].get('value', '-') if len(data['data']) > 1 else '-'
                            })
                except:
                    continue
            
            if events:
                return pd.DataFrame(events)
    except Exception as e:
        pass
    
    # Si no hay APIs configuradas, usar calendario de respaldo con datos reales típicos
    # Estos son eventos económicos comunes de Estados Unidos
    from datetime import datetime, timedelta
    
    today = datetime.now()
    base_date = today
    
    # Calendario de eventos económicos típicos de EE.UU.
    typical_events = [
        {"days_offset": 1, "event": "Índice de Precios al Consumidor (CPI)", "impact": "Alto"},
        {"days_offset": 3, "event": "Ventas Minoristas", "impact": "Medio"},
        {"days_offset": 5, "event": "Solicitudes de Desempleo Semanales", "impact": "Medio"},
        {"days_offset": 7, "event": "Índice de Producción Industrial", "impact": "Medio"},
        {"days_offset": 10, "event": "Minutas del FOMC (Fed)", "impact": "Alto"},
        {"days_offset": 12, "event": "Índice de Confianza del Consumidor", "impact": "Medio"},
        {"days_offset": 14, "event": "Nóminas No Agrícolas (NFP)", "impact": "Alto"},
        {"days_offset": 17, "event": "PMI Manufacturero", "impact": "Medio"},
        {"days_offset": 19, "event": "PMI de Servicios", "impact": "Medio"},
        {"days_offset": 21, "event": "Ventas de Viviendas Nuevas", "impact": "Bajo"},
        {"days_offset": 24, "event": "Índice de Precios al Productor (PPI)", "impact": "Alto"},
        {"days_offset": 26, "event": "Inventarios de Petróleo", "impact": "Bajo"},
        {"days_offset": 28, "event": "Discurso del Presidente de la Fed", "impact": "Alto"},
        {"days_offset": 30, "event": "Pedidos de Bienes Duraderos", "impact": "Medio"},
    ]
    
    events = []
    for event_info in typical_events:
        event_date = base_date + timedelta(days=event_info['days_offset'])
        events.append({
            'date': event_date.strftime('%Y-%m-%d'),
            'event': event_info['event'],
            'impact': event_info['impact'],
            'actual': '-',
            'estimate': '-',
            'previous': '-'
        })
    
    return pd.DataFrame(events)

# Sidebar - Configuración
st.sidebar.header("⚙️ Configuración")

# Selección de categoría
category = st.sidebar.selectbox(
    "Categoría de Activo",
    ["Acciones", "Criptomonedas", "Metales"]
)

# Selección de activo según categoría
if category == "Acciones":
    asset_dict = STOCKS
    asset_name = st.sidebar.selectbox("Seleccionar Acción", list(STOCKS.keys()))
elif category == "Criptomonedas":
    asset_dict = CRYPTOS
    asset_name = st.sidebar.selectbox("Seleccionar Cripto", list(CRYPTOS.keys()))
else:
    asset_dict = METALS
    asset_name = st.sidebar.selectbox("Seleccionar Metal", list(METALS.keys()))

selected_symbol = asset_dict[asset_name]

# Fechas
st.sidebar.subheader("📅 Rango de Fechas")
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input(
        "Fecha Inicio",
        value=datetime.now() - timedelta(days=365)
    )
with col2:
    end_date = st.date_input(
        "Fecha Final",
        value=datetime.now()
    )

# Predicción
st.sidebar.subheader("🔮 Configuración de Predicción")
prediction_type = st.sidebar.radio("Tipo de Predicción", ["Días", "Meses"])

if prediction_type == "Días":
    prediction_period = st.sidebar.slider("Días a Predecir", 1, 90, 30)
else:
    prediction_months = st.sidebar.slider("Meses a Predecir", 1, 12, 3)
    prediction_period = prediction_months * 30

# Botón de actualización
refresh = st.sidebar.button("🔄 Actualizar Datos", type="primary")

# Main content
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Análisis Principal", 
    "🎯 Mejores Oportunidades", 
    "🏆 Top Performers", 
    "📅 Calendario Económico", 
    "📈 Datos Detallados"
])

with tab1:
    # Obtener datos
    with st.spinner(f'Obteniendo datos en tiempo real para {asset_name}...'):
        df = get_real_time_data(selected_symbol, start_date, end_date)
    
    if df is not None and not df.empty:
        # Calcular indicadores
        df = calculate_indicators(df)
        
        if df is None:
            st.error("Error al calcular indicadores técnicos.")
        else:
            # Métricas principales
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - prev_price
            price_change_pct = (price_change / prev_price) * 100 if prev_price != 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Precio Actual",
                f"${current_price:.2f}",
                f"{price_change_pct:.2f}%"
            )
        
        with col2:
            st.metric(
                "Máximo 52 Semanas",
                f"${df['High'].tail(252).max():.2f}"
            )
        
        with col3:
            st.metric(
                "Mínimo 52 Semanas",
                f"${df['Low'].tail(252).min():.2f}"
            )
        
        with col4:
            st.metric(
                "Volumen Promedio",
                f"{df['Volume'].tail(20).mean()/1e6:.2f}M"
            )
        
        # Predicción
        st.subheader("🔮 Predicción de Precios")
        
        with st.spinner('Generando predicciones con Machine Learning...'):
            predictions, feature_importance = predict_prices(df, prediction_period)
        
        if predictions is not None:
            # Crear fechas futuras
            last_date = df.index[-1]
            future_dates = pd.date_range(
                start=last_date + timedelta(days=1),
                periods=prediction_period,
                freq='D'
            )
            
            # Gráfico principal con predicción
            fig = make_subplots(
                rows=4, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=(
                    'Precio y Predicción',
                    'RSI',
                    'MACD',
                    'Volumen'
                ),
                row_heights=[0.4, 0.2, 0.2, 0.2]
            )
            
            # Precio histórico
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Close'],
                    name='Precio Real',
                    line=dict(color='#2E86AB', width=2)
                ),
                row=1, col=1
            )
            
            # Bollinger Bands
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['BB_upper'],
                    name='BB Superior',
                    line=dict(color='rgba(250, 128, 114, 0.3)', dash='dash'),
                    showlegend=False
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['BB_lower'],
                    name='BB Inferior',
                    line=dict(color='rgba(250, 128, 114, 0.3)', dash='dash'),
                    fill='tonexty',
                    showlegend=False
                ),
                row=1, col=1
            )
            
            # Medias móviles
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['SMA_20'],
                    name='SMA 20',
                    line=dict(color='orange', width=1, dash='dot')
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['SMA_50'],
                    name='SMA 50',
                    line=dict(color='purple', width=1, dash='dot')
                ),
                row=1, col=1
            )
            
            # Predicción
            fig.add_trace(
                go.Scatter(
                    x=future_dates,
                    y=predictions,
                    name='Predicción',
                    line=dict(color='#FF6B35', width=2, dash='dash'),
                    marker=dict(size=4)
                ),
                row=1, col=1
            )
            
            # RSI
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['RSI'],
                    name='RSI',
                    line=dict(color='purple', width=1.5)
                ),
                row=2, col=1
            )
            
            # Líneas de sobrecompra/sobreventa
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
            
            # MACD
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['MACD'],
                    name='MACD',
                    line=dict(color='blue', width=1.5)
                ),
                row=3, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Signal'],
                    name='Signal',
                    line=dict(color='red', width=1.5)
                ),
                row=3, col=1
            )
            
            # Volumen
            colors = ['red' if row['Close'] < row['Open'] else 'green' 
                     for _, row in df.iterrows()]
            
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df['Volume'],
                    name='Volumen',
                    marker_color=colors,
                    showlegend=False
                ),
                row=4, col=1
            )
            
            # Actualizar layout
            fig.update_layout(
                height=1000,
                title_text=f"{asset_name} ({selected_symbol}) - Análisis Técnico y Predicción",
                showlegend=True,
                hovermode='x unified',
                template='plotly_white'
            )
            
            fig.update_xaxes(title_text="Fecha", row=4, col=1)
            fig.update_yaxes(title_text="Precio ($)", row=1, col=1)
            fig.update_yaxes(title_text="RSI", row=2, col=1)
            fig.update_yaxes(title_text="MACD", row=3, col=1)
            fig.update_yaxes(title_text="Volumen", row=4, col=1)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Análisis de predicción
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Resumen de Predicción")
                pred_change = ((predictions[-1] - current_price) / current_price) * 100
                
                st.write(f"**Precio Actual:** ${current_price:.2f}")
                st.write(f"**Precio Predicho ({prediction_period} días):** ${predictions[-1]:.2f}")
                st.write(f"**Cambio Esperado:** {pred_change:.2f}%")
                
                if pred_change > 5:
                    st.success("🚀 Tendencia alcista fuerte")
                elif pred_change > 0:
                    st.info("📈 Tendencia alcista moderada")
                elif pred_change > -5:
                    st.warning("📉 Tendencia bajista moderada")
                else:
                    st.error("⚠️ Tendencia bajista fuerte")
            
            with col2:
                st.subheader("🎯 Importancia de Features")
                if feature_importance is not None:
                    feature_names = ['Returns', 'Volume_Change', 'RSI', 'MACD', 'Volatility']
                    importance_df = pd.DataFrame({
                        'Feature': feature_names,
                        'Importancia': feature_importance
                    }).sort_values('Importancia', ascending=False)
                    
                    fig_importance = go.Figure(go.Bar(
                        x=importance_df['Importancia'],
                        y=importance_df['Feature'],
                        orientation='h',
                        marker_color='#2E86AB'
                    ))
                    
                    fig_importance.update_layout(
                        title="Importancia de Indicadores en la Predicción",
                        xaxis_title="Importancia",
                        height=300
                    )
                    
                    st.plotly_chart(fig_importance, use_container_width=True)
        else:
            st.warning("No hay suficientes datos para generar predicciones confiables.")
    else:
        st.error("No se pudieron obtener datos para el activo seleccionado.")

with tab2:
    st.header("🎯 Análisis de Mejores Oportunidades de Inversión")
    
    st.write("""
    Este análisis evalúa **todos los activos disponibles** (acciones, criptomonedas y metales) 
    para identificar las mejores oportunidades de inversión basándose en:
    - 📈 Momentum reciente (cambio de precio)
    - 📊 RSI (identificar sobrecompra/sobreventa)
    - 📉 Volatilidad (riesgo)
    - 🎯 Tendencia (dirección del precio)
    - 📦 Volumen (confirmación de movimientos)
    """)
    
    # Selector de timeframe
    col1, col2 = st.columns([1, 3])
    with col1:
        analysis_timeframe = st.selectbox(
            "Período de Análisis",
            ["3 Días", "Última Sesión"],
            help="3 Días: Análisis de tendencia de corto plazo\nÚltima Sesión: Análisis intradiario (aproximado)"
        )
    
    timeframe = '3d' if analysis_timeframe == "3 Días" else '3h'
    
    with col2:
        st.info(f"📊 Analizando **{len(STOCKS) + len(CRYPTOS) + len(METALS)}** activos en busca de las mejores oportunidades...")
    
    # Realizar análisis
    with st.spinner('🔍 Analizando todos los activos... Esto puede tomar unos segundos...'):
        analysis_df = analyze_best_investment_opportunities(timeframe)
    
    if analysis_df is not None and not analysis_df.empty:
        
        # Resumen ejecutivo
        st.subheader("📋 Resumen Ejecutivo")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Mejor de cada categoría
        best_stock = analysis_df[analysis_df['Categoría'] == 'Acción'].iloc[0] if len(analysis_df[analysis_df['Categoría'] == 'Acción']) > 0 else None
        best_crypto = analysis_df[analysis_df['Categoría'] == 'Cripto'].iloc[0] if len(analysis_df[analysis_df['Categoría'] == 'Cripto']) > 0 else None
        best_metal = analysis_df[analysis_df['Categoría'] == 'Metal'].iloc[0] if len(analysis_df[analysis_df['Categoría'] == 'Metal']) > 0 else None
        best_overall = analysis_df.iloc[0]
        
        with col1:
            st.metric(
                "🏆 Mejor General",
                best_overall['Nombre'],
                f"Score: {best_overall['Score']:.1f}/100"
            )
            st.caption(f"{best_overall['Emoji']} {best_overall['Recomendación']}")
        
        with col2:
            if best_stock is not None:
                st.metric(
                    "📈 Mejor Acción",
                    best_stock['Nombre'],
                    f"Score: {best_stock['Score']:.1f}/100"
                )
                st.caption(f"{best_stock['Emoji']} {best_stock['Recomendación']}")
            else:
                st.info("No hay datos de acciones")
        
        with col3:
            if best_crypto is not None:
                st.metric(
                    "₿ Mejor Cripto",
                    best_crypto['Nombre'],
                    f"Score: {best_crypto['Score']:.1f}/100"
                )
                st.caption(f"{best_crypto['Emoji']} {best_crypto['Recomendación']}")
            else:
                st.info("No hay datos de criptos")
        
        with col4:
            if best_metal is not None:
                st.metric(
                    "🥇 Mejor Metal",
                    best_metal['Nombre'],
                    f"Score: {best_metal['Score']:.1f}/100"
                )
                st.caption(f"{best_metal['Emoji']} {best_metal['Recomendación']}")
            else:
                st.info("No hay datos de metales")
        
        # Distribución de recomendaciones
        st.subheader("📊 Distribución de Recomendaciones")
        
        rec_counts = analysis_df['Recomendación'].value_counts()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig_rec = go.Figure(data=[
                go.Bar(
                    x=rec_counts.index,
                    y=rec_counts.values,
                    marker_color=['#00cc66', '#99cc00', '#cccccc', '#ff9933', '#ff3333'],
                    text=rec_counts.values,
                    textposition='auto'
                )
            ])
            
            fig_rec.update_layout(
                title="Distribución de Recomendaciones",
                xaxis_title="Recomendación",
                yaxis_title="Cantidad de Activos",
                height=300
            )
            
            st.plotly_chart(fig_rec, use_container_width=True)
        
        with col2:
            st.write("**Leyenda:**")
            st.write("🟢 **Compra Fuerte**: Score ≥ 75")
            st.write("🟡 **Compra**: Score 60-74")
            st.write("⚪ **Mantener**: Score 40-59")
            st.write("🟠 **Vender**: Score 25-39")
            st.write("🔴 **Vender Fuerte**: Score < 25")
        
        # Top 10 mejores oportunidades
        st.subheader("🏅 Top 10 Mejores Oportunidades")
        
        top_10 = analysis_df.head(10).copy()
        
        # Formatear para visualización
        display_df = top_10[[
            'Emoji', 'Nombre', 'Categoría', 'Precio', 'Momentum 3P (%)', 
            'RSI', 'Volatilidad (%)', 'Tendencia', 'Score', 'Recomendación'
        ]].copy()
        
        display_df['Precio'] = display_df['Precio'].apply(lambda x: f"${x:.2f}")
        display_df['Momentum 3P (%)'] = display_df['Momentum 3P (%)'].apply(lambda x: f"{x:+.2f}%")
        display_df['RSI'] = display_df['RSI'].apply(lambda x: f"{x:.1f}")
        display_df['Volatilidad (%)'] = display_df['Volatilidad (%)'].apply(lambda x: f"{x:.2f}%")
        display_df['Score'] = display_df['Score'].apply(lambda x: f"{x:.1f}")
        
        # Aplicar colores por score
        def highlight_score(row):
            score = float(row['Score'])
            if score >= 75:
                return ['background-color: #d4edda'] * len(row)
            elif score >= 60:
                return ['background-color: #fff3cd'] * len(row)
            elif score >= 40:
                return ['background-color: #f8f9fa'] * len(row)
            elif score >= 25:
                return ['background-color: #ffe5d4'] * len(row)
            else:
                return ['background-color: #f8d7da'] * len(row)
        
        styled_top_10 = display_df.style.apply(highlight_score, axis=1)
        st.dataframe(styled_top_10, use_container_width=True, hide_index=True)
        
        # Análisis detallado del mejor activo
        st.subheader(f"🔍 Análisis Detallado: {best_overall['Nombre']}")
        
        detailed = detailed_asset_analysis(
            best_overall['Símbolo'], 
            best_overall['Nombre'],
            period='5d'
        )
        
        if detailed:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Precio Actual", f"${detailed['current_price']:.2f}")
                st.metric("Soporte Estimado", f"${detailed['support']:.2f}")
            
            with col2:
                st.metric("Distancia del Máximo", f"{detailed['distance_from_high']:.2f}%")
                st.metric("Resistencia Estimada", f"${detailed['resistance']:.2f}")
            
            with col3:
                st.metric("Distancia del Mínimo", f"+{detailed['distance_from_low']:.2f}%")
                st.metric("Tendencia de Volumen", detailed['volume_trend'])
            
            # Razones de la recomendación
            st.write("**¿Por qué es una buena oportunidad?**")
            
            reasons = []
            
            if best_overall['Momentum 3P (%)'] > 5:
                reasons.append(f"✅ Momentum positivo fuerte: {best_overall['Momentum 3P (%)']:.2f}%")
            elif best_overall['Momentum 3P (%)'] > 0:
                reasons.append(f"✅ Momentum positivo: {best_overall['Momentum 3P (%)']:.2f}%")
            
            if 30 <= best_overall['RSI'] <= 40:
                reasons.append(f"✅ RSI en zona de posible rebote: {best_overall['RSI']:.1f}")
            elif 40 < best_overall['RSI'] <= 60:
                reasons.append(f"✅ RSI en zona neutral: {best_overall['RSI']:.1f}")
            
            if best_overall['Tendencia'] == "Alcista":
                reasons.append("✅ Tendencia alcista confirmada")
            
            if best_overall['Vol. Ratio'] > 1.5:
                reasons.append(f"✅ Volumen alto (confirma movimiento): {best_overall['Vol. Ratio']:.2f}x promedio")
            
            if best_overall['Volatilidad (%)'] < 3:
                reasons.append(f"✅ Baja volatilidad (menor riesgo): {best_overall['Volatilidad (%)']:.2f}%")
            
            for reason in reasons:
                st.write(reason)
            
            # Advertencias
            if best_overall['RSI'] > 70:
                st.warning(f"⚠️ RSI alto ({best_overall['RSI']:.1f}): Posible sobrecompra, considerar esperar corrección")
            
            if best_overall['Volatilidad (%)'] > 5:
                st.warning(f"⚠️ Alta volatilidad ({best_overall['Volatilidad (%)']:.2f}%): Mayor riesgo")
            
            # Gráfico del mejor activo
            st.write("**Gráfico de Precio Reciente:**")
            
            fig_best = go.Figure()
            
            fig_best.add_trace(go.Candlestick(
                x=detailed['data'].index,
                open=detailed['data']['Open'],
                high=detailed['data']['High'],
                low=detailed['data']['Low'],
                close=detailed['data']['Close'],
                name=best_overall['Nombre']
            ))
            
            # Agregar niveles de soporte y resistencia
            fig_best.add_hline(
                y=detailed['support'], 
                line_dash="dash", 
                line_color="green",
                annotation_text="Soporte"
            )
            
            fig_best.add_hline(
                y=detailed['resistance'], 
                line_dash="dash", 
                line_color="red",
                annotation_text="Resistencia"
            )
            
            fig_best.update_layout(
                title=f"{best_overall['Nombre']} ({best_overall['Símbolo']}) - Últimos Días",
                yaxis_title="Precio ($)",
                height=400,
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig_best, use_container_width=True)
        
        # Tabla completa (expandible)
        with st.expander("📋 Ver Análisis Completo de Todos los Activos"):
            # Preparar tabla completa
            full_display = analysis_df.copy()
            full_display['Precio'] = full_display['Precio'].apply(lambda x: f"${x:.2f}")
            full_display['Momentum 3P (%)'] = full_display['Momentum 3P (%)'].apply(lambda x: f"{x:+.2f}%")
            full_display['RSI'] = full_display['RSI'].apply(lambda x: f"{x:.1f}")
            full_display['Volatilidad (%)'] = full_display['Volatilidad (%)'].apply(lambda x: f"{x:.2f}%")
            full_display['Vol. Ratio'] = full_display['Vol. Ratio'].apply(lambda x: f"{x:.2f}x")
            full_display['Score'] = full_display['Score'].apply(lambda x: f"{x:.1f}")
            
            # Seleccionar columnas para mostrar
            full_display = full_display[[
                'Emoji', 'Nombre', 'Símbolo', 'Categoría', 'Precio', 
                'Momentum 3P (%)', 'RSI', 'Volatilidad (%)', 'Tendencia', 
                'Vol. Ratio', 'Score', 'Recomendación'
            ]]
            
            st.dataframe(full_display, use_container_width=True, hide_index=True)
        
        # Análisis por categoría
        st.subheader("📊 Análisis por Categoría")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**📈 Acciones**")
            stocks_df = analysis_df[analysis_df['Categoría'] == 'Acción'].head(5)
            if not stocks_df.empty:
                for _, row in stocks_df.iterrows():
                    st.write(f"{row['Emoji']} **{row['Nombre']}**: {row['Score']:.1f} - {row['Recomendación']}")
            else:
                st.info("No hay datos disponibles")
        
        with col2:
            st.write("**₿ Criptomonedas**")
            crypto_df = analysis_df[analysis_df['Categoría'] == 'Cripto'].head(5)
            if not crypto_df.empty:
                for _, row in crypto_df.iterrows():
                    st.write(f"{row['Emoji']} **{row['Nombre']}**: {row['Score']:.1f} - {row['Recomendación']}")
            else:
                st.info("No hay datos disponibles")
        
        with col3:
            st.write("**🥇 Metales**")
            metals_df = analysis_df[analysis_df['Categoría'] == 'Metal'].head(5)
            if not metals_df.empty:
                for _, row in metals_df.iterrows():
                    st.write(f"{row['Emoji']} **{row['Nombre']}**: {row['Score']:.1f} - {row['Recomendación']}")
            else:
                st.info("No hay datos disponibles")
        
        # Descarga de resultados
        st.subheader("💾 Exportar Análisis")
        
        csv = analysis_df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Análisis Completo (CSV)",
            data=csv,
            file_name=f"analisis_oportunidades_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # Información adicional
        with st.expander("ℹ️ Cómo se calcula el Score"):
            st.write("""
            ### Metodología de Puntuación (0-100)
            
            El **Score de Oportunidad** se calcula combinando 5 factores clave:
            
            #### 1. Momentum (30% del score)
            - Cambio porcentual de precio en el período seleccionado
            - Mayor momentum = mayor puntuación
            - Rango: -10% a +10% normalizado a 0-100
            
            #### 2. RSI - Relative Strength Index (20% del score)
            - Identifica condiciones de sobrecompra/sobreventa
            - Óptimo: 30-70 (score máximo)
            - <30: Sobreventa (posible rebote)
            - >70: Sobrecompra (posible corrección)
            
            #### 3. Volatilidad (20% del score)
            - Desviación estándar de los retornos
            - Menor volatilidad = menor riesgo = mayor score
            - Alta volatilidad penaliza el score
            
            #### 4. Tendencia (20% del score)
            - Dirección del precio (regresión lineal)
            - Alcista: 100 puntos
            - Bajista: 30 puntos
            
            #### 5. Volumen (10% del score)
            - Ratio del volumen actual vs promedio
            - Alto volumen confirma el movimiento
            - Máximo: 2x el volumen promedio = 100 puntos
            
            ### Interpretación del Score:
            
            - **75-100**: 🟢 Compra Fuerte (alta probabilidad de éxito)
            - **60-74**: 🟡 Compra (buena oportunidad)
            - **40-59**: ⚪ Mantener (neutral)
            - **25-39**: 🟠 Vender (débil)
            - **0-24**: 🔴 Vender Fuerte (alto riesgo)
            
            ### Limitaciones:
            
            ⚠️ **Este análisis es una herramienta de apoyo, NO un consejo de inversión**
            
            - Basado en datos históricos (no garantiza rendimiento futuro)
            - No considera noticias o eventos fundamentales
            - No incluye análisis de estados financieros
            - Diseñado para trading de corto plazo
            
            **Siempre realiza tu propio análisis y consulta con un asesor financiero profesional.**
            """)
        
    else:
        st.error("No se pudieron obtener suficientes datos para realizar el análisis. Verifica tu conexión a Internet.")

with tab3:
    st.header("🏆 Top Performers del Día")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📈 Acciones")
        with st.spinner('Analizando acciones...'):
            stock_perf = get_top_performers(STOCKS, days=1)
            if stock_perf:
                sorted_stocks = sorted(stock_perf.items(), key=lambda x: x[1]['change'], reverse=True)
                
                st.write("**Ganadoras:**")
                for i, (name, data) in enumerate(sorted_stocks[:5]):
                    st.metric(
                        name,
                        f"${data['price']:.2f}",
                        f"{data['change']:.2f}%"
                    )
                
                st.write("**Perdedoras:**")
                for i, (name, data) in enumerate(sorted_stocks[-5:]):
                    st.metric(
                        name,
                        f"${data['price']:.2f}",
                        f"{data['change']:.2f}%"
                    )
    
    with col2:
        st.subheader("₿ Criptomonedas")
        with st.spinner('Analizando criptos...'):
            crypto_perf = get_top_performers(CRYPTOS, days=1)
            if crypto_perf:
                sorted_cryptos = sorted(crypto_perf.items(), key=lambda x: x[1]['change'], reverse=True)
                
                st.write("**Ganadoras:**")
                for i, (name, data) in enumerate(sorted_cryptos[:4]):
                    st.metric(
                        name,
                        f"${data['price']:.2f}",
                        f"{data['change']:.2f}%"
                    )
                
                st.write("**Perdedoras:**")
                for i, (name, data) in enumerate(sorted_cryptos[-4:]):
                    st.metric(
                        name,
                        f"${data['price']:.2f}",
                        f"{data['change']:.2f}%"
                    )
    
    with col3:
        st.subheader("🥇 Metales")
        with st.spinner('Analizando metales...'):
            metal_perf = get_top_performers(METALS, days=1)
            if metal_perf:
                sorted_metals = sorted(metal_perf.items(), key=lambda x: x[1]['change'], reverse=True)
                
                for name, data in sorted_metals:
                    st.metric(
                        name,
                        f"${data['price']:.2f}",
                        f"{data['change']:.2f}%"
                    )

with tab4:
    st.header("📅 Calendario Económico")
    
    # Verificar si hay APIs configuradas
    has_api = False
    api_source = "Calendario de respaldo (eventos típicos)"
    
    if 'FINNHUB_KEY' in globals() and FINNHUB_KEY and FINNHUB_KEY != "TU_API_KEY_AQUI":
        has_api = True
        api_source = "Finnhub API (datos en tiempo real)"
    elif 'ALPHA_VANTAGE_KEY' in globals() and ALPHA_VANTAGE_KEY and ALPHA_VANTAGE_KEY != "TU_API_KEY_AQUI":
        has_api = True
        api_source = "Alpha Vantage API"
    
    st.info(f"📡 Fuente de datos: {api_source}")
    
    if not has_api:
        st.warning("⚠️ Para obtener eventos económicos en tiempo real, configura tu API key de Finnhub o Alpha Vantage. Ver: API_CONFIGURATION.md")
    
    st.write("Próximos eventos económicos importantes de Estados Unidos:")
    
    with st.spinner('Obteniendo calendario económico...'):
        calendar_df = get_economic_calendar()
    
    if calendar_df is not None and not calendar_df.empty:
        # Ordenar por fecha
        calendar_df['date'] = pd.to_datetime(calendar_df['date'])
        calendar_df = calendar_df.sort_values('date')
        calendar_df['date'] = calendar_df['date'].dt.strftime('%Y-%m-%d')
        
        # Aplicar colores según impacto
        def highlight_impact(row):
            if row['impact'] == 'Alto':
                return ['background-color: #ffcccc'] * len(row)
            elif row['impact'] == 'Medio':
                return ['background-color: #fff4cc'] * len(row)
            else:
                return ['background-color: #ccffcc'] * len(row)
        
        styled_df = calendar_df.style.apply(highlight_impact, axis=1)
        
        # Mostrar tabla
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Leyenda
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("🔴 **Alto impacto**: Puede causar volatilidad significativa")
        with col2:
            st.markdown("🟡 **Medio impacto**: Movimientos moderados esperados")
        with col3:
            st.markdown("🟢 **Bajo impacto**: Efecto limitado en mercados")
        
        # Mostrar detalles si hay columnas adicionales
        if 'actual' in calendar_df.columns:
            st.subheader("📊 Interpretación de Datos")
            st.write("""
            - **Actual**: Valor real publicado del indicador
            - **Estimate**: Valor esperado por analistas
            - **Previous**: Valor de la publicación anterior
            
            **Cómo interpretar:**
            - Si Actual > Estimate: Generalmente positivo para la economía
            - Si Actual < Estimate: Puede indicar debilidad económica
            """)
        
        # Estadísticas del calendario
        st.subheader("📈 Resumen del Calendario")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            high_impact = len(calendar_df[calendar_df['impact'] == 'Alto'])
            st.metric("Eventos de Alto Impacto", high_impact)
        
        with col2:
            medium_impact = len(calendar_df[calendar_df['impact'] == 'Medio'])
            st.metric("Eventos de Medio Impacto", medium_impact)
        
        with col3:
            low_impact = len(calendar_df[calendar_df['impact'] == 'Bajo'])
            st.metric("Eventos de Bajo Impacto", low_impact)
        
        # Descargar calendario
        csv = calendar_df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Calendario CSV",
            data=csv,
            file_name=f"calendario_economico_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # Información adicional
        with st.expander("ℹ️ Cómo usar el Calendario Económico"):
            st.write("""
            ### Eventos de Alto Impacto:
            - **CPI (Índice de Precios al Consumidor)**: Mide la inflación
            - **NFP (Nóminas No Agrícolas)**: Indicador clave del empleo
            - **Minutas de la Fed**: Insights sobre política monetaria
            - **Tasa de Desempleo**: Salud del mercado laboral
            
            ### Eventos de Medio Impacto:
            - **Ventas Minoristas**: Gasto del consumidor
            - **PMI Manufacturero**: Salud del sector industrial
            - **Confianza del Consumidor**: Sentimiento económico
            
            ### Trading durante eventos:
            1. **Antes del evento**: Volatilidad baja, posiciones cautelosas
            2. **Durante la publicación**: Alta volatilidad, spreads amplios
            3. **Después del evento**: Dirección definida, oportunidades
            
            ### Recomendaciones:
            - ⚠️ Evita operar justo antes/durante eventos de alto impacto
            - ✅ Espera 15-30 minutos después de la publicación
            - 📊 Compara el dato actual vs expectativas del mercado
            - 🎯 Usa stops más amplios en días de eventos importantes
            """)
    else:
        st.error("No se pudo obtener el calendario económico. Verifica tu conexión a Internet.")

with tab5:
    st.header("📈 Datos Detallados")
    
    if df is not None and not df.empty:
        st.subheader(f"Datos históricos de {asset_name}")
        
        # Mostrar estadísticas
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Estadísticas Descriptivas:**")
            stats_df = df[['Open', 'High', 'Low', 'Close', 'Volume']].describe()
            st.dataframe(stats_df, use_container_width=True)
        
        with col2:
            st.write("**Indicadores Técnicos Actuales:**")
            current_indicators = pd.DataFrame({
                'Indicador': ['RSI', 'MACD', 'Signal', 'Volatilidad (Anual)'],
                'Valor': [
                    f"{df['RSI'].iloc[-1]:.2f}",
                    f"{df['MACD'].iloc[-1]:.4f}",
                    f"{df['Signal'].iloc[-1]:.4f}",
                    f"{df['Volatility'].iloc[-1]*100:.2f}%"
                ]
            })
            st.dataframe(current_indicators, use_container_width=True, hide_index=True)
        
        # Tabla de datos completa
        st.subheader("Tabla de Datos Completa")
        display_df = df[['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD']].tail(100)
        st.dataframe(display_df, use_container_width=True)
        
        # Opción de descarga
        csv = df.to_csv()
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv,
            file_name=f"{selected_symbol}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

# Footer
st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Trading Predictor Pro v1.0**
    
    Datos en tiempo real proporcionados por Yahoo Finance.
    
    ⚠️ Advertencia: Este análisis es solo con fines educativos. 
    No constituye asesoramiento financiero.
    """
)

# Auto-refresh cada 5 minutos
st.sidebar.markdown(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
