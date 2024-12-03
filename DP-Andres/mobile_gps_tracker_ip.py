import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import folium_static
from dataclasses import dataclass
from typing import List

GEOLOCATION_HTML = """
<div id="location-status"></div>
<div id="location-data" style="display:none;"></div>
<script>
const statusElement = document.getElementById("location-status");
const locationDataElement = document.getElementById("location-data");

function updateStatus(message, isError = false) {
    statusElement.style.color = isError ? 'red' : 'green';
    statusElement.innerText = message;
}

function requestLocationPermission() {
    if ("geolocation" in navigator) {
        updateStatus("Solicitando permiso de ubicación...");
        navigator.permissions.query({ name: 'geolocation' })
            .then(function(permissionStatus) {
                if (permissionStatus.state === 'granted') {
                    getCurrentLocation();
                } else if (permissionStatus.state === 'prompt') {
                    getCurrentLocation();
                } else {
                    updateStatus("Permiso de ubicación denegado", true);
                }

                permissionStatus.onchange = function() {
                    if (this.state === 'granted') {
                        getCurrentLocation();
                    }
                };
            });
    } else {
        updateStatus("Geolocalización no soportada", true);
    }
}

function getCurrentLocation() {
    const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
    };

    navigator.geolocation.getCurrentPosition(
        function(pos) {
            const crd = pos.coords;
            const locationData = {
                latitude: crd.latitude,
                longitude: crd.longitude,
                accuracy: crd.accuracy,
                timestamp: new Date(pos.timestamp).toISOString(),
                mobile_number: window.tracked_mobile_number || ''
            };
            
            updateStatus(`Ubicación encontrada: ${crd.latitude}, ${crd.longitude}`);
            locationDataElement.innerText = JSON.stringify(locationData);
            
            // Notify Streamlit about the location
            window.parent.postMessage({
                type: "locationUpdate", 
                locationData: locationData
            }, "*");
        },
        function(err) {
            updateStatus(`Error: ${err.message}`, true);
            console.warn(`ERROR(${err.code}): ${err.message}`);
        },
        options
    );
}

function startTracking(mobileNumber) {
    window.tracked_mobile_number = mobileNumber;
    requestLocationPermission();
}

window.addEventListener("message", function(event) {
    if (event.data.type === "startTracking") {
        startTracking(event.data.mobileNumber);
    }
});
</script>
"""

@dataclass
class LocationData:
    latitude: float
    longitude: float
    accuracy: float
    timestamp: str
    mobile_number: str

class MobileGPSTracker:
    def __init__(self):
        if 'tracked_locations' not in st.session_state:
            st.session_state.tracked_locations = {}
        
        # Location component with explicit height
        self.location_component = components.html(
            GEOLOCATION_HTML,
            height=100  # Visible height for status messages
        )
    
    def start_tracking(self, mobile_number: str):
        if not mobile_number or len(mobile_number) < 8:
            st.error("Por favor, ingrese un número de móvil válido")
            return False
        
        # Send tracking start message to JavaScript
        components.html(
            f'''
            <script>
            window.parent.postMessage({{
                type: "startTracking", 
                mobileNumber: "{mobile_number}"
            }}, "*");
            </script>
            ''',
            height=0
        )
        
        # Initialize location list for mobile number
        if mobile_number not in st.session_state.tracked_locations:
            st.session_state.tracked_locations[mobile_number] = []
        
        st.success(f"Preparado para rastrear el número {mobile_number}")
        return True
    
    def add_location(self, location_data: dict):
        """Add a new location for a mobile number"""
        mobile_number = location_data.get('mobile_number')
        if mobile_number:
            new_location = LocationData(
                latitude=location_data['latitude'],
                longitude=location_data['longitude'],
                accuracy=location_data['accuracy'],
                timestamp=location_data['timestamp'],
                mobile_number=mobile_number
            )
            
            # Add to tracked locations
            st.session_state.tracked_locations[mobile_number].append(new_location)
    
    def visualize_locations(self, mobile_number: str):
        locations = st.session_state.tracked_locations.get(mobile_number, [])
        
        if not locations:
            st.warning(f"No se encontraron ubicaciones para el número {mobile_number}")
            return None
        
        # Create map centered on last location
        last_location = locations[-1]
        m = folium.Map(
            location=[last_location.latitude, last_location.longitude],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add markers for all locations
        for loc in locations:
            folium.Marker(
                [loc.latitude, loc.longitude],
                popup=f"""
                Número: {loc.mobile_number}<br>
                Tiempo: {loc.timestamp}<br>
                Precisión: {loc.accuracy:.1f}m
                """
            ).add_to(m)
        
        # Add tracking line if multiple locations
        if len(locations) > 1:
            points = [[loc.latitude, loc.longitude] for loc in locations]
            folium.PolyLine(
                points,
                weight=2,
                color='red',
                opacity=0.8
            ).add_to(m)
        
        folium_static(m)
        return locations

def handle_location_message(tracker):
    """Handle location messages from JavaScript"""
    for msg in st.session_state.get('location_messages', []):
        if msg.get('type') == 'locationUpdate':
            tracker.add_location(msg['locationData'])
    st.session_state.location_messages = []

def main_geolocation():
    st.title("Rastreador GPS de Móviles")
    
    # Initialize tracker
    tracker = MobileGPSTracker()
    
    # Store and process any incoming location messages
    if 'location_messages' not in st.session_state:
        st.session_state.location_messages = []
    
    # Handle incoming location messages
    handle_location_message(tracker)
    
    # Track incoming JavaScript messages
    components.html("""
    <script>
    window.addEventListener("message", function(event) {
        if (event.data.type === "locationUpdate") {
            window.parent.postMessage({
                action: "storeMessage", 
                message: event.data
            }, "*");
        }
    });
    </script>
    """, height=0)
    
    # Mobile number input
    mobile_number = st.text_input("Número de Móvil a Rastrear")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Iniciar Seguimiento"):
            tracker.start_tracking(mobile_number)
    
    with col2:
        if st.button("Mostrar Ubicaciones"):
            locations = tracker.visualize_locations(mobile_number)
            if locations:
                location_data = [
                    {
                        "Número": loc.mobile_number,
                        "Timestamp": loc.timestamp,
                        "Latitud": loc.latitude,
                        "Longitud": loc.longitude,
                        "Precisión": f"{loc.accuracy:.1f}m"
                    }
                    for loc in locations
                ]
                st.dataframe(location_data)
    
    # List tracked mobile numbers
    if st.session_state.tracked_locations:
        st.subheader("Números Rastreados")
        for number in st.session_state.tracked_locations.keys():
            st.write(number)

#if __name__ == "__main__":
#    main()