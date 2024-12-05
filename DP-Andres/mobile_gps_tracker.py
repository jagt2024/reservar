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

     # Add a new component for browser geolocation
    st.header("Obtener Ubicación del Navegador")
    
    # Input for mobile number
    
    # Selector de pestañas
    tab1, tab2, tab3, tab4 = st.tabs([
        "Rastrear Ubicación", 
        "Guía Google Maps", 
        "Ubicaciones Guardadas", 
        "Eliminar Ubicaciones"
    ])
    
    with tab1:
        st.header("Obtener y Rastrear Ubicación")
        
        # Modificación para incluir método de ubicación por número móvil
        metodo = st.selectbox("Método de Ubicación", [
            "Seleccionar Método",
            "Obtener por Dirección IP",
            "Ingreso Manual de Coordenadas", 
            "Ubicación por Número Móvil"  # Nuevo método agregado
        ])
        
        mobile_number = st.text_input("Número de Móvil", 
                                      placeholder="Ej: +573001234567", 
                                      key="mobile_input")
        
        
        if metodo == "Ubicación por Número Móvil":
           # Button to trigger geolocation
            if st.button("Obtener Ubicación por Número Móvil"):
                # Check if geolocation is available
                if 'mobile_location' in st.session_state:
                    try:
                        mobile_location = st.session_state.mobile_location
                        location = LocationData(
                            latitude=mobile_location['latitude'],
                            longitude=mobile_location['longitude'],
                            accuracy=mobile_location['accuracy'],
                            timestamp=datetime.now().isoformat(),
                            source='Mobile Number Geolocation'
                        )
                        if location:
                           tracker.add_location(location, mobile_number)
                    
                        # Clear the location to prevent re-adding
                        #del st.session_state.mobile_location
                    except Exception as e:
                        st.error(f"Error procesando ubicación: {e}")
        
            # Error handling for geolocation
            if 'mobile_location_error' in st.session_state:
                st.error(f"Error de geolocalización: {st.session_state.mobile_location_error}")
                del st.session_state.mobile_location_error
    
            # JavaScript to get geolocation with mobile number context
            components.html(f"""
            <script>
            const mobileNumber = "{mobile_number}";
            const options = {{
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }};

            function sendLocationToStreamlit(latitude, longitude, accuracy) {{
                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue', 
                    key: 'mobile_location', 
                    value: {{
                        mobile_number: mobileNumber,
                        latitude: latitude, 
                        longitude: longitude, 
                        accuracy: accuracy
                    }}
                    }}, '*');
            }}

            function success(pos) {{
                const crd = pos.coords;
                sendLocationToStreamlit(crd.latitude, crd.longitude, crd.accuracy);
            }}

            function error(err) {{
                console.warn(`ERROR(${{err.code}}): ${{err.message}}`);
                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue', 
                    key: 'mobile_location_error', 
                    value: err.message
                }}, '*');
            }}

            navigator.geolocation.getCurrentPosition(success, error, options);
            </script>
            """, height=0)
       
            # Listen for browser location
            #browser_location = st.session_state.get('browser_location', None)
            #if browser_location:
            #  try:
            #    location = tracker.browser_location_input(
            #        latitude=browser_location['latitude'], 
            #        longitude=browser_location['longitude'], 
            #        accuracy=browser_location['accuracy']
            #    )
            #    tracker.add_location(location, mobile_number)
                # Clear the location to prevent re-adding
            #    st.session_state.browser_location = None
            #  except Exception as e:
            #    st.error(f"Error procesando ubicación: {e}")
        
        # Método de obtención de ubicación
        #metodo = st.selectbox("Método de Ubicación", [
        #    "Seleccionar Método",
        #    "Obtener por Dirección IP",
        #    "Ingreso Manual de Coordenadas"
        #])
        
        elif metodo == "Obtener por Dirección IP":
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