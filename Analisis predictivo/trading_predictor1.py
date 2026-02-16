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
# FINNHUB_KEY = "d68ueq1r01qs7u9k27p0d68ueq1r01qs7u9k27pg"
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
    
    # Asegurarse de que tenemos las columnas necesarias
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Falta la columna requerida: {col}")
            return None
    
    try:
        # Media móvil simple
        df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        df['BB_middle'] = df['Close'].rolling(window=20, min_periods=1).mean()
        bb_std = df['Close'].rolling(window=20, min_periods=1).std()
        df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
        df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
        
        # Volatilidad
        returns = df['Close'].pct_change()
        df['Volatility'] = returns.rolling(window=20, min_periods=1).std() * np.sqrt(252)
        
        # Rellenar NaN con método forward fill
        df = df.ffill()
        
        return df
    except Exception as e:
        st.error(f"Error al calcular indicadores: {str(e)}")
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

# Función para obtener ganadoras y perdedoras
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

# Función para calendario económico (eventos simulados)
def get_economic_calendar():
    # En un caso real, esto vendría de una API de calendario económico
    events = [
        {"date": "2025-02-14", "event": "Índice de Precios al Consumidor (CPI)", "impact": "Alto"},
        {"date": "2025-02-15", "event": "Ventas Minoristas", "impact": "Medio"},
        {"date": "2025-02-18", "event": "Minutas de la Fed", "impact": "Alto"},
        {"date": "2025-02-20", "event": "Solicitudes de Desempleo", "impact": "Medio"},
        {"date": "2025-02-21", "event": "PMI Manufacturero", "impact": "Medio"},
    ]
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
tab1, tab2, tab3, tab4 = st.tabs(["📊 Análisis Principal", "🏆 Top Performers", "📅 Calendario Económico", "📈 Datos Detallados"])

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

with tab3:
    st.header("📅 Calendario Económico")
    st.write("Próximos eventos económicos importantes de Estados Unidos:")
    
    calendar_df = get_economic_calendar()
    
    # Aplicar colores según impacto
    def highlight_impact(row):
        if row['impact'] == 'Alto':
            return ['background-color: #ffcccc'] * len(row)
        elif row['impact'] == 'Medio':
            return ['background-color: #fff4cc'] * len(row)
        else:
            return ['background-color: #ccffcc'] * len(row)
    
    styled_df = calendar_df.style.apply(highlight_impact, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.info("🔴 Rojo = Alto impacto | 🟡 Amarillo = Medio impacto | 🟢 Verde = Bajo impacto")

with tab4:
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
