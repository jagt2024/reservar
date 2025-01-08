import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
from datetime import datetime
import json
from streamlit.components.v1 import html
import requests
import ipaddress

def show_gps_tracker():
    """Función principal que maneja la página del localizador GPS"""
    
    # Título de la sección
    st.title("🗺️ Visualizador de Ubicación en Tiempo Real")

    # Inicializar el historial de ubicaciones en session state si no existe
    if 'locations_history' not in st.session_state:
        st.session_state.locations_history = []

    # Crear dos columnas
    col1, col2 = st.columns([2, 1])

    with col1:
        # Tabs para diferentes métodos de localización
        tab1, tab2, tab3 = st.tabs(["📍 GPS del Navegador", "🌐 Localización por IP", "📝 Entrada Manual"])
        
        with tab1:
            # Botón de geolocalización del navegador
            get_geolocation()
        
        with tab2:
            # Formulario para localización por IP
            with st.form("ip_form"):
                st.subheader("Búsqueda por IP")
                ip_address = st.text_input("Dirección IP", placeholder="Ej: 8.8.8.8")
                submit_ip = st.form_submit_button("Buscar ubicación")
                
                if submit_ip and ip_address:
                    location_data = get_location_by_ip(ip_address)
                    if location_data:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        add_location(
                            location_data['latitude'],
                            location_data['longitude'],
                            timestamp,
                            "IP",
                            {
                                'ip': ip_address,
                                'city': location_data['city'],
                                'country': location_data['country'],
                                'isp': location_data['isp']
                            }
                        )
                        st.success(f"Ubicación encontrada: {location_data['city']}, {location_data['country']}")
        
        with tab3:
            # Formulario para ingresar coordenadas manualmente
            with st.form("location_form"):
                st.subheader("Ingrese las coordenadas")
                latitude = st.number_input("Latitud", value=0.0, format="%.6f")
                longitude = st.number_input("Longitud", value=0.0, format="%.6f")
                submitted = st.form_submit_button("Actualizar ubicación")
                
                if submitted:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    add_location(latitude, longitude, timestamp, "Manual")
                    st.success("¡Ubicación actualizada!")

        # Mostrar el mapa
        display_map()

    with col2:
        display_history()

    # Botón para limpiar historial
    if st.button("Limpiar Historial"):
        st.session_state.locations_history = []
        st.rerun()

    # Instrucciones de uso
    display_instructions()

def get_location_by_ip(ip_address):
    """Obtiene la localización usando la API de ip-api.com"""
    try:
        ipaddress.ip_address(ip_address)
        response = requests.get(f'http://ip-api.com/json/{ip_address}')
        data = response.json()
        
        if data['status'] == 'success':
            return {
                'latitude': data['lat'],
                'longitude': data['lon'],
                'city': data.get('city', 'Desconocida'),
                'country': data.get('country', 'Desconocido'),
                'isp': data.get('isp', 'Desconocido')
            }
        return None
    except ValueError:
        st.error("IP inválida. Por favor, ingrese una dirección IP válida.")
        return None
    except Exception as e:
        st.error(f"Error al obtener la localización: {str(e)}")
        return None

def get_geolocation():
    """Componente HTML/JavaScript para geolocalización del navegador"""
    components_html = """
        <div style='margin-bottom: 20px'>
            <button id="getLocation" style="
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 15px 32px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 4px 2px;
                cursor: pointer;
                border-radius: 4px;">
                Obtener Mi Ubicación
            </button>
            <p id="status" style="color: gray;"></p>
        </div>
        
        <script>
        const button = document.getElementById('getLocation');
        const status = document.getElementById('status');
        
        button.addEventListener('click', () => {
            status.textContent = 'Solicitando permiso de ubicación...';
            
            if (!navigator.geolocation) {
                status.textContent = 'La geolocalización no está soportada en tu navegador';
                return;
            }
            
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    status.textContent = `Ubicación obtenida: ${lat}, ${lon}`;
                    
                    window.parent.postMessage({
                        type: 'streamlit:set_location',
                        latitude: lat,
                        longitude: lon
                    }, '*');
                },
                (error) => {
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            status.textContent = 'Usuario denegó el permiso de geolocalización';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            status.textContent = 'Información de ubicación no disponible';
                            break;
                        case error.TIMEOUT:
                            status.textContent = 'Tiempo de espera agotado al obtener la ubicación';
                            break;
                        default:
                            status.textContent = 'Error desconocido al obtener la ubicación';
                            break;
                    }
                },
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        });
        </script>
    """
    html(components_html, height=100)

def add_location(lat, lon, timestamp, source="Manual", details=None):
    """Agrega una nueva ubicación al historial"""
    new_location = {
        'timestamp': timestamp,
        'latitude': lat,
        'longitude': lon,
        'source': source,
        'details': details or {}
    }
    st.session_state.locations_history.append(new_location)

def display_map():
    """Muestra el mapa con las ubicaciones marcadas"""
    if st.session_state.locations_history:
        last_location = st.session_state.locations_history[-1]
        
        m = folium.Map(
            location=[last_location['latitude'], last_location['longitude']],
            zoom_start=15
        )
        
        for location in st.session_state.locations_history:
            popup_content = f"""
                <b>Tiempo:</b> {location['timestamp']}<br>
                <b>Fuente:</b> {location['source']}<br>
            """
            if location['details']:
                for key, value in location['details'].items():
                    popup_content += f"<b>{key.title()}:</b> {value}<br>"
            
            color = {
                'GPS': 'red',
                'IP': 'blue',
                'Manual': 'green'
            }.get(location['source'], 'gray')
            
            folium.Marker(
                [location['latitude'], location['longitude']],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
        
        if len(st.session_state.locations_history) > 1:
            points = [[loc['latitude'], loc['longitude']] 
                     for loc in st.session_state.locations_history]
            folium.PolyLine(
                points,
                weight=2,
                color='purple',
                opacity=0.8
            ).add_to(m)
        
        folium_static(m)
    else:
        st.info("Usa cualquiera de los métodos disponibles para obtener una ubicación.")

def display_history():
    """Muestra el historial de ubicaciones"""
    st.subheader("Historial de Ubicaciones")
    if st.session_state.locations_history:
        df = pd.DataFrame(st.session_state.locations_history)
        df['city'] = df['details'].apply(lambda x: x.get('city', '') if x else '')
        df['country'] = df['details'].apply(lambda x: x.get('country', '') if x else '')
        display_df = df[['timestamp', 'latitude', 'longitude', 'source', 'city', 'country']]
        st.dataframe(display_df, hide_index=True)
        
        if st.button("Descargar Historial"):
            json_string = json.dumps(st.session_state.locations_history, indent=2)
            st.download_button(
                label="Descargar como JSON",
                file_name="historial_ubicaciones.json",
                mime="application/json",
                data=json_string
            )
    else:
        st.info("No hay ubicaciones registradas aún.")

def display_instructions():
    """Muestra las instrucciones de uso"""
    with st.expander("📖 Instrucciones de Uso"):
        st.markdown("""
        ### Métodos de localización disponibles:
        
        1. **GPS del Navegador**
           - Haz clic en el botón 'Obtener Mi Ubicación'
           - Acepta el permiso de geolocalización cuando el navegador lo solicite
        
        2. **Localización por IP**
           - Ingresa una dirección IP válida
           - Haz clic en 'Buscar ubicación'
           - Se mostrará la ubicación aproximada del servidor
        
        3. **Entrada Manual**
           - Ingresa las coordenadas de latitud y longitud
           - Haz clic en 'Actualizar ubicación'
        
        ### Características adicionales:
        - El historial muestra todas las ubicaciones registradas
        - Puedes descargar el historial en formato JSON
        - Usa el botón 'Limpiar Historial' para reiniciar los datos
        - Los marcadores en el mapa tienen diferentes colores según el método usado:
          - 🔴 Rojo: GPS
          - 🔵 Azul: IP
          - 🟢 Verde: Manual
        """)