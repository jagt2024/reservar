import streamlit as st
import streamlit.components.v1 as components
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
       
    def browser_location_input(self, latitude, longitude, accuracy):
        """Add location from browser geolocation"""
        location = LocationData(
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=datetime.now().isoformat(),
            source='Browser'
        )
        return location
   
    def get_ip_location(self):
        """Obtener ubicación basada en dirección IP"""
        try:
            response = requests.get('https://ipapi.co/json/')
            data = response.json()
            return LocationData(
                latitude=data.get('latitude', 0),
                longitude=data.get('longitude', 0),
                accuracy=1000,  # IP-based location es menos preciso
                timestamp=datetime.now().isoformat(),
                source='IP'
            )
        except Exception as e:
            st.error(f"Error obteniendo ubicación por IP: {e}")
            return None
    
    def manual_location_input(self, latitude, longitude):
        """Agregar ubicación manualmente"""
        location = LocationData(
            latitude=latitude,
            longitude=longitude,
            accuracy=10,  # Precisión manual
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
                Precisión: {loc.accuracy}m
                """
            ).add_to(m)
        
        # Línea de seguimiento
        if len(locations) > 1:
            points = [[loc.latitude, loc.longitude] for loc in locations]
            folium.PolyLine(points, color='red').add_to(m)
        
        folium_static(m)
        return locations
    
    def delete_location(self, mobile_number, index):
        """Eliminar una ubicación específica"""
        if mobile_number in st.session_state.tracked_locations:
            if 0 <= index < len(st.session_state.tracked_locations[mobile_number]):
                del st.session_state.tracked_locations[mobile_number][index]
                st.success(f"Ubicación eliminada para {mobile_number}")
            else:
                st.error("Índice de ubicación no válido")
        else:
            st.error("Número móvil no encontrado")
    
    def delete_all_locations(self, mobile_number):
        """Eliminar todas las ubicaciones para un número móvil"""
        if mobile_number in st.session_state.tracked_locations:
            del st.session_state.tracked_locations[mobile_number]
            st.success(f"Todas las ubicaciones para {mobile_number} han sido eliminadas")
        else:
            st.error("Número móvil no encontrado")

def geolocation_script():
    """Returns JavaScript for browser geolocation"""
    return """
    <script>
    function getLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(showPosition, showError);
        } else {
            document.getElementById("location").innerHTML = "Geolocation is not supported by this browser.";
        }
    }

    function showPosition(position) {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;
        document.getElementById("location").innerHTML = 
            `Latitude: ${latitude}° <br>Longitude: ${longitude}° 
            <br><a href='https://www.openstreetmap.org/#map=18/${latitude}/${longitude}' target='_blank'>View on Map</a>`;
            
        doSomething(position.latitude, position.longitude);doSomething(position.latitude, position.longitude);    
    }

    function showError(error) {
        let errorMessage;
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMessage = "User denied the request for Geolocation.";
                break;
            case error.POSITION_UNAVAILABLE:
                errorMessage = "Location information is unavailable.";
                break;
            case error.TIMEOUT:
                errorMessage = "The request to get user location timed out.";
                break;
            case error.UNKNOWN_ERROR:
                errorMessage = "An unknown error occurred.";
                break;
        }
        window.parent.postMessage({
            type: 'streamlit:setComponentValue', 
            key: 'browser_location_error', 
            value: errorMessage
        }, '*');
    }

    getLocation();
    </script>
    """

def show_google_maps_guide():
    """Mostrar guía detallada para obtener coordenadas en Google Maps"""
    st.markdown("## 📍 Guía para Obtener Coordenadas en Google Maps (Windows)")
    
    st.markdown("### Paso a Paso:")
    st.markdown("""
    1. Abre Google Chrome
    2. Navega a [Google Maps](https://www.google.com/maps)
    3. Busca la ubicación que deseas
    4. ***Método 1: Clic Derecho***
        - Haz clic derecho en el punto exacto
        - Selecciona "¿Qué hay aquí?"
        - Las coordenadas aparecerán en la parte inferior
    
    5. ***Método 2: URL***
        - Mueve el mapa al punto deseado
        - La URL cambiará mostrando las coordenadas
        - Ejemplo: `https://www.google.com/maps/@19.4326,-99.1332,12z`
    
    ### Consejos:
    - Las coordenadas son: Latitud (primer número), Longitud (segundo número)
    - Latitud va de -90 a 90 (Norte/Sur)
    - Longitud va de -180 a 180 (Este/Oeste)
    
    ### Ejemplos de Coordenadas:
    - Ciudad de México: 19.4326, -99.1332
    - Bogotá: 4.7110, -74.0721
    - Buenos Aires: -34.6037, -58.3816
    """)

def main_geolocation():
    st.title("🗺️ Rastreador de Ubicación Multipropósito")
    
    # Inicializar tracker
    tracker = LocationTracker()

    # Selector de pestañas
    tab1, tab2, tab3, tab4 = st.tabs([
        "Rastrear Ubicación", 
        "Guía Google Maps", 
        "Ubicaciones Guardadas", 
        "Eliminar Ubicaciones"
    ])
    
    with tab1:
        st.header("Obtener y Rastrear Ubicación")
        
        mobile_number = st.text_input("Número de Móvil", 
                                      placeholder="Ej: +573001234567", 
                                      key="mobile_input")
        
        #st.markdown('''<iframe src="https://www.openstreetmap.org/#map=18/" width="600" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>''',unsafe_allow_html=True)
        
        # Nuevo botón para obtener ubicación del navegador
        if st.button("Obtener Ubicación del Navegador"):
            # Inyectar script de geolocalización
            components.html(geolocation_script(), height=0)
        
        # Manejar la ubicación del navegador
        browser_location = st.session_state.get('browser_location', None)
        browser_location_error = st.session_state.get('browser_location_error', None)
        
        if browser_location:
            #latitude = 4.283
            #longitude = -74.218
            try:
                location = tracker.browser_location_input(
                    latitude=browser_location['latitude'], 
                    longitude=browser_location['longitude'], 
                    accuracy=browser_location['accuracy']
                )
                tracker.add_location(location, mobile_number)
                # Limpiar la ubicación para evitar re-agregación
                del st.session_state.browser_location
            except Exception as e:
                st.error(f"Error procesando ubicación: {e}")
        
        if browser_location_error:
            st.error(f"Error de geolocalización: {browser_location_error}")
            del st.session_state.browser_location_error
        
        # Resto del código permanece igual
        metodo = st.selectbox("Método de Ubicación", [
            "Seleccionar Método",
            "Obtener por Dirección IP",
            "Ingreso Manual de Coordenadas"
        ])
        
        if metodo == "Obtener por Dirección IP":
            if st.button("Obtener Ubicación por IP"):
                location = tracker.get_ip_location()
                if location:
                    tracker.add_location(location, mobile_number)
        
        elif metodo == "Ingreso Manual de Coordenadas":
            col1, col2 = st.columns(2)
            with col1:
                latitud = st.number_input("Latitud", format="%.6f", 
                                          help="Entre -90 y 90. Ejemplo: 19.4326",key="number3")
            with col2:
                longitud = st.number_input("Longitud", format="%.6f", 
                                           help="Entre -180 y 180. Ejemplo: -99.1332",key="number4")
            
            if st.button("Agregar Ubicación"):
                location = tracker.manual_location_input(latitud, longitud)
                tracker.add_location(location, mobile_number)
    
    with tab2:
        show_google_maps_guide()
    
    with tab3:
        st.header("Ubicaciones Guardadas")
        # Visualización de ubicaciones
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
    
    with tab4:
        st.header("Eliminar Ubicaciones")
        
        # Selección de número móvil para eliminación
        mobile_numbers = list(st.session_state.tracked_locations.keys())
        
        if mobile_numbers:
            selected_number = st.selectbox("Seleccionar Número Móvil", mobile_numbers)
            
            # Opción de eliminar todas las ubicaciones
            if st.button(f"Eliminar Todas las Ubicaciones de {selected_number}"):
                tracker.delete_all_locations(selected_number)
            
            # Eliminar ubicación específica
            locations = st.session_state.tracked_locations.get(selected_number, [])
            if locations:
                st.subheader("Ubicaciones Guardadas")
                for i, loc in enumerate(locations):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"Ubicación {i+1}: {loc.timestamp}")
                    with col2:
                        if st.button(f"Eliminar #{i+1}", key=f"delete_{selected_number}_{i}"):
                            tracker.delete_location(selected_number, i)
                            st.rerun()
        else:
            st.info("No hay ubicaciones guardadas para eliminar")

if __name__ == "__main__":
    main_geolocation()