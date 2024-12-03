import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import folium_static
from dataclasses import dataclass
from datetime import datetime

@dataclass
class LocationData:
    latitude: float
    longitude: float
    accurate: float
    timestamp: str
    source: str

class LocationTracker:
    def __init__(self):
        if 'tracked_locations' not in st.session_state:
            st.session_state.tracked_locations = {}
    
    def browser_location_input(self, latitude, longitude, accurate):
        """Añadir ubicación desde la geolocalización del navegador"""
        location = LocationData(
            latitude=latitude,
            longitude=longitude,
            accurate=accurate,
            timestamp=datetime.now().isoformat(),
            source='Browser'
        )
        return location
    
    def add_location(self, location, mobile_number):
        """Añadir ubicación para un número móvil"""
        if not mobile_number:
            mobile_number = "Sin Número"
        
        if mobile_number not in st.session_state.tracked_locations:
            st.session_state.tracked_locations[mobile_number] = []
        
        st.session_state.tracked_locations[mobile_number].append(location)
        st.success(f"Ubicación agregada para {mobile_number}")
    
    def visualize_locations(self, mobile_number):
        """Visualizar ubicaciones en un mapa"""
        locations = st.session_state.tracked_locations.get(mobile_number, [])
        
        if not locations:
            st.warning(f"No hay ubicaciones para {mobile_number}")
            return None
        
        # Crear mapa con la última ubicación
        last_location = locations[-1]
        m = folium.Map(
            location=[last_location.latitude, last_location.longitude],
            zoom_start=10
        )
        
        # Agregar marcadores
        for loc in locations:
            folium.Marker(
                [loc.latitude, loc.longitude],
                popup=f"""
                Fuente: {loc.source}<br>
                Tiempo: {loc.timestamp}<br>
                Precisión: {loc.accurate}m
                """
            ).add_to(m)
        
        # Línea de seguimiento
        if len(locations) > 1:
            points = [[loc.latitude, loc.longitude] for loc in locations]
            folium.PolyLine(points, color='red').add_to(m)
        
        folium_static(m)
        return locations

def main_geolocation():
    st.title("🗺️ Rastreador de Ubicación Multipropósito")
    
    # Inicializar rastreador
    tracker = LocationTracker()
    
    # Agregar un nuevo componente para geolocalización del navegador
    st.header("Obtener Ubicación del Navegador")
    
    # Entrada para número de móvil
    mobile_number = st.text_input("Número de Móvil (Opcional)", placeholder="Puedes dejarlo en blanco")
    
    # Agregar un botón para activar la geolocalización
    if st.button("Obtener Ubicación Actual"):
        # JavaScript para obtener la geolocalización
        components.html("""
        <script>
        const options = {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        };

        function sendLocationToStreamlit(latitude, longitude, precision) {
            // Usar el evento personalizado de Streamlit para pasar datos de ubicación
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                key: 'browser_location',
                value: {
                    latitude: latitude,
                    longitude: longitude,
                    precision: precision
                }
            }, '*');
        }

        function success(pos) {
            const crd = pos.coords;
            sendLocationToStreamlit(crd.latitude, crd.longitude, crd.accuracy);
        }

        function error(err) {
            console.warn(`ERROR(${err.code}): ${err.message}`);
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                key: 'browser_location_error',
                value: err.message
            }, '*');
        }

        navigator.geolocation.getCurrentPosition(success, error, options);
        </script>
        """, height=0)
    
    # Escuchar la ubicación del navegador
    browser_location = st.session_state.get('browser_location', None)
    if browser_location:
        try:
            location = tracker.browser_location_input(
                latitude=browser_location['latitude'], 
                longitude=browser_location['longitude'], 
                accurate=browser_location.get('precision', 0)
            )
            tracker.add_location(location, mobile_number)
            # Borra la ubicación para evitar volver a agregarla
            st.session_state.browser_location = None
        except Exception as e:
            st.error(f"Error procesando ubicación: {e}")
    
    # Sección de ubicaciones guardadas
    st.header("Ubicaciones Guardadas")
    if st.session_state.tracked_locations:
        for number, locations in st.session_state.tracked_locations.items():
            st.subheader(f"Número: {number}")
            
            if st.button(f"Mostrar Mapa - {number}"):
                tracked_locations = tracker.visualize_locations(number)
                if tracked_locations:
                    location_details = [
                        {
                            "Fuente": loc.source,
                            "Timestamp": loc.timestamp,
                            "Latitud": loc.latitude,
                            "Longitud": loc.longitude,
                            "Precisión": f"{loc.accurate}m"
                        }
                        for loc in tracked_locations
                    ]
                    st.dataframe(location_details)
    else:
        st.info("No se han guardado ubicaciones aún")

#if __name__ == "__main__":
#    main_geolocation()
