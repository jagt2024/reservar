import streamlit as st
import folium
from streamlit_folium import folium_static
from dataclasses import dataclass
import requests
from datetime import datetime

@dataclass
class LocationData:
    latitude: float
    longitude: float
    accuracy: float
    timestamp: str
    source: str

class LocationTracker:
    def __init__(self):
        if 'tracked_locations' not in st.session_state:
            st.session_state.tracked_locations = {}
    
    def get_ip_location(self):
        """Get location based on IP address"""
        try:
            services = [
                'https://ipapi.co/json/',
                'https://ip-api.com/json/'
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    data = response.json()
                    
                    if 'latitude' in data:  # ipapi.co format
                        return LocationData(
                            latitude=data.get('latitude', 0),
                            longitude=data.get('longitude', 0),
                            accuracy=1000,
                            timestamp=datetime.now().isoformat(),
                            source='IP-API'
                        )
                    elif 'lat' in data:  # ip-api.com format
                        return LocationData(
                            latitude=data.get('lat', 0),
                            longitude=data.get('lon', 0),
                            accuracy=1000,
                            timestamp=datetime.now().isoformat(),
                            source='IP-API'
                        )
                except Exception as e:
                    st.warning(f"Error with {service}: {e}")
            
            st.error("Could not retrieve location from any IP service")
            return None
        
        except Exception as e:
            st.error(f"Unexpected error getting IP location: {e}")
            return None
    
    def manual_location_input(self, latitude, longitude):
        """Add location manually"""
        location = LocationData(
            latitude=latitude,
            longitude=longitude,
            accuracy=10,
            timestamp=datetime.now().isoformat(),
            source='Manual'
        )
        return location
    
    def add_location(self, location, mobile_number):
        """Add location for a mobile number"""
        if not mobile_number:
            mobile_number = "Sin Número"
        
        if mobile_number not in st.session_state.tracked_locations:
            st.session_state.tracked_locations[mobile_number] = []
        
        st.session_state.tracked_locations[mobile_number].append(location)
        st.success(f"Ubicación agregada para {mobile_number}")
    
    def visualize_locations(self, mobile_number):
        """Visualize locations on a map"""
        locations = st.session_state.tracked_locations.get(mobile_number, [])
        
        if not locations:
            st.warning(f"No hay ubicaciones para {mobile_number}")
            return None
        
        last_location = locations[-1]
        m = folium.Map(
            location=[last_location.latitude, last_location.longitude],
            zoom_start=10
        )
        
        for loc in locations:
            folium.Marker(
                [loc.latitude, loc.longitude],
                popup=f"""
                Fuente: {loc.source}<br>
                Tiempo: {loc.timestamp}<br>
                Precisión: {loc.accuracy}m
                """
            ).add_to(m)
        
        if len(locations) > 1:
            points = [[loc.latitude, loc.longitude] for loc in locations]
            folium.PolyLine(points, color='red').add_to(m)
        
        folium_static(m)
        return locations

def run_gps_tracker():
    st.title("🗺️ Rastreador de Ubicación por IP")
    
    # Initialize tracker
    tracker = LocationTracker()
    
    # Input for mobile number
    mobile_number = st.text_input("Número de Móvil (Opcional)", 
                                  placeholder="Puedes dejarlo en blanco")
    
    # Get IP Location
    if st.button("Obtener Ubicación por IP"):
        location = tracker.get_ip_location()
        if location:
            tracker.add_location(location, mobile_number)
    
    # Manual Location Input
    st.header("Ingreso Manual de Coordenadas")
    col1, col2 = st.columns(2)
    with col1:
        latitud = st.number_input("Latitud", format="%.6f", 
                                  help="Entre -90 y 90. Ejemplo: 19.4326")
    with col2:
        longitud = st.number_input("Longitud", format="%.6f", 
                                   help="Entre -180 y 180. Ejemplo: -99.1332")
    
    if st.button("Agregar Ubicación Manual"):
        location = tracker.manual_location_input(latitud, longitud)
        tracker.add_location(location, mobile_number)
    
    # View Saved Locations
    st.header("Ubicaciones Guardadas")
    if st.session_state.tracked_locations:
        for number, locs in st.session_state.tracked_locations.items():
            st.subheader(f"Número: {number}")
            
            if st.button(f"Mostrar Mapa - {number}"):
                locations = tracker.visualize_locations(number)
                if locations:
                    location_data = [
                        {
                            "Fuente": loc.source,
                            "Timestamp": loc.timestamp,
                            "Latitud": loc.latitude,
                            "Longitud": loc.longitude,
                            "Precisión": f"{loc.accuracy}m"
                        }
                        for loc in locations
                    ]
                    st.dataframe(location_data)
    else:
        st.info("No se han guardado ubicaciones aún")