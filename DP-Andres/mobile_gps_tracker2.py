import streamlit as st
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
    
    def add_location(self, latitude, longitude, accuracy, mobile_number):
        """Añadir ubicación para un número móvil"""
        location = LocationData(
            latitude=latitude,
            longitude=longitude,
            accurate=accuracy,
            timestamp=datetime.now().isoformat(),
            source='Browser'
        )
        
        if not mobile_number:
            mobile_number = "Sin Número"
        
        if mobile_number not in st.session_state.tracked_locations:
            st.session_state.tracked_locations[mobile_number] = []
        
        st.session_state.tracked_locations[mobile_number].append(location)
        st.success(f"Ubicación agregada para {mobile_number}")
        return location
    
    def visualize_location(self, latitude, longitude, accuracy):
        """Visualizar ubicación única en un mapa"""
        # Crear mapa centrado en la ubicación
        m = folium.Map(
            location=[latitude, longitude],
            zoom_start=15
        )
        
        # Agregar marcador
        folium.Marker(
            [latitude, longitude],
            popup=f"""
            Precisión: {accuracy}m<br>
            Tiempo: {datetime.now().isoformat()}
            """
        ).add_to(m)
        
        # Mostrar mapa en Streamlit
        folium_static(m)

def main_geolocation():
    st.title("🗺️ Rastreador de Ubicación Multipropósito")
    
    # Inicializar rastreador
    tracker = LocationTracker()
    
    st.header("Obtener Ubicación")
    
    st.info("""
    Instrucciones para obtener ubicación:
    1. Haga clic en "Obtener Ubicación Actual"
    2. Permita el acceso a la ubicación cuando se lo solicite
    3. Asegúrese de tener conexión a internet
    4. Verifique que la ubicación de GPS esté habilitada
    """)
    
    # Entrada para número de móvil
    mobile_number = st.text_input("Número de Móvil (Opcional)", placeholder="Puedes dejarlo en blanco")
    
    # Botón para obtener ubicación
    if st.button("Obtener Ubicación Actual"):
        st.components.v1.html("""
        <div id="location-info" style="margin-bottom: 10px;"></div>
        <div id="debug-info" style="color: gray; font-size: 0.8em;"></div>
        <script>
        function getLocation() {
            var locationDiv = document.getElementById('location-info');
            var debugDiv = document.getElementById('debug-info');
            
            debugDiv.innerHTML = "Iniciando solicitud de ubicación...";
            
            if (!navigator.geolocation) {
                locationDiv.innerHTML = "Geolocalización no soportada";
                debugDiv.innerHTML = "El navegador no soporta geolocalización";
                return;
            }
            
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var latitude = position.coords.latitude;
                    var longitude = position.coords.longitude;
                    var accuracy = position.coords.accuracy;
                    
                    locationDiv.innerHTML = 
                        'Latitud: ' + latitude.toFixed(6) + '° ' +
                        'Longitud: ' + longitude.toFixed(6) + '° ' +
                        'Precisión: ' + accuracy.toFixed(2) + 'm';
                    
                    debugDiv.innerHTML = 
                        'Método de ubicación: ' + 
                        (position.coords.accuracyError ? 'Aproximado' : 'Preciso');
                    
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        key: 'browser_location',
                        value: {
                            latitude: latitude,
                            longitude: longitude,
                            accuracy: accuracy
                        }
                    }, '*');
                },
                function(error) {
                    var errorMessage = "";
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = "Permiso de ubicación denegado.";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = "Información de ubicación no disponible.";
                            break;
                        case error.TIMEOUT:
                            errorMessage = "La solicitud de ubicación expiró.";
                            break;
                        case error.UNKNOWN_ERROR:
                            errorMessage = "Error desconocido.";
                            break;
                    }
                    
                    locationDiv.innerHTML = errorMessage;
                    debugDiv.innerHTML = "Código de error: " + error.code;
                },
                {
                    enableHighAccuracy: true,
                    timeout: 30000,
                    maximumAge: 0
                }
            );
        }
        
        getLocation();
        </script>
        """, height=250)
    
    # Procesar ubicación capturada
    browser_location = st.session_state.get('browser_location', None)
    
    if browser_location:
        try:
            # Añadir ubicación
            location = tracker.add_location(
                latitude=browser_location['latitude'],
                longitude=browser_location['longitude'],
                accuracy=browser_location['accuracy'],
                mobile_number=mobile_number
            )
            
            # Mostrar información de ubicación
            st.write("Detalles de ubicación:")
            st.json({
                "Latitud": location.latitude,
                "Longitud": location.longitude,
                "Precisión": f"{location.accurate}m",
                "Timestamp": location.timestamp
            })
            
            # Mostrar mapa
            st.header("Mapa de Ubicación")
            tracker.visualize_location(
                latitude=location.latitude, 
                longitude=location.longitude, 
                accuracy=location.accurate
            )
            
            # Mostrar enlace de OpenStreetMap
            st.markdown(f"[Ver en OpenStreetMap](https://www.openstreetmap.org/#map=18/{location.latitude}/{location.longitude})")
            
        except Exception as e:
            st.error(f"Error procesando ubicación: {e}")

if __name__ == "__main__":
    main_geolocation()