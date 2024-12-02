import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import numpy as np

# Definir zonas de Bogotá
ZONAS = {
    'Norte': ['Usaquén', 'Suba', 'Chapinero'],
    'Sur': ['Ciudad Bolívar', 'Tunjuelito', 'Rafael Uribe Uribe'],
    'Oriente': ['Santafé', 'Candelaria', 'Chapinero (parte oriental)'],
    'Occidente': ['Fontibón', 'Kennedy', 'Engativá']
}

# Coordenadas del Aeropuerto El Dorado
AEROPUERTO_COORDS = (4.7022, -74.1469)

# Función para generar rutas simuladas
def generar_rutas(zona):
    # Coordenadas base para cada zona (centros aproximados)
    zonas_coords = {
        'Norte': (4.7508, -74.0472),
        'Sur': (4.5964, -74.1500),
        'Oriente': (4.6544, -74.0629),
        'Occidente': (4.6542, -74.1254)
    }
    
    # Generar rutas simuladas
    rutas = []
    for _ in range(np.random.randint(3, 7)):
        # Generar distancia y tiempo aleatorios
        distancia = np.random.uniform(10, 50)
        tiempo = np.random.uniform(20, 90)
        
        ruta = {
            'Localidades': ', '.join(np.random.choice(ZONAS[zona], 2)),
            'Distancia (km)': round(distancia, 2),
            'Tiempo Estimado (min)': round(tiempo, 2)
        }
        rutas.append(ruta)
    
    return pd.DataFrame(rutas)

# Función para crear mapa
def crear_mapa(zona):
    # Coordenadas base para cada zona
    zonas_coords = {
        'Norte': (4.7508, -74.0472),
        'Sur': (4.5964, -74.1500),
        'Oriente': (4.6544, -74.0629),
        'Occidente': (4.6542, -74.1254)
    }
    
    # Crear mapa centrado en la zona seleccionada
    m = folium.Map(location=zonas_coords[zona], zoom_start=11)
    
    # Marcar Aeropuerto El Dorado
    folium.Marker(
        location=AEROPUERTO_COORDS, 
        popup='Aeropuerto El Dorado',
        icon=folium.Icon(color='red', icon='plane')
    ).add_to(m)
    
    # Añadir marcadores para algunas localidades de la zona
    for localidad in ZONAS[zona]:
        # Coordenadas aproximadas (esto sería más preciso con un servicio de geocodificación)
        lat = zonas_coords[zona][0] + np.random.uniform(-0.1, 0.1)
        lon = zonas_coords[zona][1] + np.random.uniform(-0.1, 0.1)
        
        folium.Marker(
            location=(lat, lon),
            popup=localidad,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)
    
    return m

# Aplicación Streamlit
def main():
    st.title('Gestión de Rutas - Aeropuerto El Dorado, Bogotá')
    
    # Selector de zona
    zona_seleccionada = st.selectbox(
        'Seleccione una Zona', 
        list(ZONAS.keys())
    )
    
    # Columnas para organizar contenido
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f'Rutas en Zona {zona_seleccionada}')
        # Mostrar tabla de rutas
        rutas_df = generar_rutas(zona_seleccionada)
        st.dataframe(rutas_df)
    
    with col2:
        st.subheader('Mapa de Rutas')
        # Mostrar mapa
        mapa = crear_mapa(zona_seleccionada)
        folium_static(mapa)
    
    # Información adicional
    st.sidebar.header('Detalles de Zonificación')
    st.sidebar.write(f"Localidades en Zona {zona_seleccionada}:")
    for loc in ZONAS[zona_seleccionada]:
        st.sidebar.text(f"• {loc}")

# Ejecutar la aplicación
if __name__ == '__main__':
    main()
