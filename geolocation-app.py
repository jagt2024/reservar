import streamlit as st
#import streamlit.components.v1 as components
from streamlit_folium import folium_static
import folium

def geolocation_script():
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
        switch(error.code) {
            case error.PERMISSION_DENIED:
                document.getElementById("location").innerHTML = "User denied the request for Geolocation.";
                break;
            case error.POSITION_UNAVAILABLE:
                document.getElementById("location").innerHTML = "Location information is unavailable.";
                break;
            case error.TIMEOUT:
                document.getElementById("location").innerHTML = "The request to get user location timed out.";
                break;
            case error.UNKNOWN_ERROR:
                document.getElementById("location").innerHTML = "An unknown error occurred.";
                break;
        }
    }
    </script>
    <div id="location">Click 'Get Location' to find your position</div>
    <button onclick="getLocation()">Get Location</button>
    """
    

def create_map(latitude, longitude):
    m = folium.Map(location=[latitude, longitude], zoom_start=15)
    
    folium.Marker(
        [latitude, longitude], 
        popup='Your Location', 
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    return m

def main():
    st.title("Geolocation and Map App")
    
    # Inject geolocation JavaScript
    st.components.v1.html(geolocation_script(), height=100)
    
    # Check for saved location in localStorage via JavaScript
    latitude = None
    longitude = None
    
    try:
        latitude = st.session_state.get('latitude')
        longitude = st.session_state.get('longitude')
    except:
        """
        <script>
        function getLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(showPosition, showError);
                navigator.geolocation.getCurrentPosition(position => {
                console.log(position);
                }, e => {
                console.log(e);
            });
        </script>"""
    
    if latitude and longitude:
        st.success(f"Location Captured: {latitude}°, {longitude}°")
        
        # Create and display map
        map_obj = create_map(float(latitude), float(longitude))
        folium_static(map_obj)
        
        # Option to clear location
        if st.button('Clear Location'):
            del st.session_state['latitude']
            del st.session_state['longitude']
            st.rerun()
            
            
#def main():
#    st.title("Native Geolocation App")
    
    # Inject the JavaScript
#    st.components.v1.html(geolocation_script(), height=300)

if __name__ == "__main__":
    main()