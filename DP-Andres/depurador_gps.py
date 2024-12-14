import streamlit as st
import streamlit.components.v1 as components

def main_geolocation():
    st.title("🗺️ Rastreador de Ubicación Multipropósito")
    
    st.header("Depuración de Geolocalización")
    
    # Botón simple para obtener ubicación
    if st.button("Obtener Ubicación"):
        # Inyectar script de geolocalización directamente
        components.html("""
        <script>
        // Log de depuración
        console.log("Geolocation script started");

        // Verificar si el navegador soporta geolocalización
        if ('geolocation' in navigator) {
            console.log("Geolocation is supported");
            
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    // Éxito
                    console.log("Latitude: " + position.coords.latitude);
                    console.log("Longitude: " + position.coords.longitude);
                    console.log("Accuracy: " + position.coords.accuracy + " meters");

                    // Enviar datos a Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue', 
                        key: 'location_data',
                        value: {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy
                        }
                    }, '*');
                },
                function(error) {
                    // Error
                    console.error("Error Code: " + error.code);
                    console.error("Error Message: " + error.message);
                    
                    // Enviar error a Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue', 
                        key: 'location_error',
                        value: error.message
                    }, '*');
                },
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        } else {
            console.error("Geolocation is not supported by this browser.");
        }
        </script>
        """, height=0)
    
    # Mostrar resultado de la ubicación
    location_data = st.session_state.get('location_data')
    location_error = st.session_state.get('location_error')
    
    if location_data:
        st.success("Ubicación obtenida:")
        st.write(f"Latitud: {location_data['latitude']}")
        st.write(f"Longitud: {location_data['longitude']}")
        st.write(f"Precisión: {location_data['accuracy']} metros")
        
        # Limpiar datos para evitar repetición
        st.session_state.location_data = None
    
    if location_error:
        st.error(f"Error de geolocalización: {location_error}")
        # Limpiar error
        st.session_state.location_error = None

if __name__ == "__main__":
    main_geolocation()