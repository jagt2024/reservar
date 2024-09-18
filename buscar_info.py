import streamlit as st
import webbrowser
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import json
from datetime import datetime
from typing import List, Dict
import traceback

class LocalWebSearch:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
       
    def search(self, query: str, engine: str = 'google', open_browser: bool = True) -> List[Dict[str, str]]:
        """Realiza una búsqueda web."""
        if not query:
            raise ValueError("La consulta de búsqueda no puede estar vacía")
        
        if engine == 'google':
            url = f"https://www.google.com/search?q={quote_plus(query)}"
        elif engine == 'bing':
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
        else:
            raise ValueError("Motor de búsqueda no soportado")
        
        if open_browser:
            webbrowser.open(url)
        
        return self.extract_results(url)

    def extract_results(self, url: str) -> List[Dict[str, str]]:
        """Extrae los resultados de la página de búsqueda."""
        response = self.session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        if 'google.com' in url:
            for g in soup.find_all('div', class_='g'):
                anchor = g.find('a')
                if anchor and anchor.get('href'):
                    title = anchor.find('h3')
                    snippet = g.find('div', class_='VwiC3b')
                    if title and snippet:
                        results.append({
                            'title': title.text,
                            'link': anchor['href'],
                            'snippet': snippet.text
                        })
        elif 'bing.com' in url:
            for li in soup.find_all('li', class_='b_algo'):
                anchor = li.find('a')
                if anchor:
                    title = anchor.text
                    snippet = li.find('p')
                    if title and snippet:
                        results.append({
                            'title': title,
                            'link': anchor['href'],
                            'snippet': snippet.text
                        })

        return results[:10]  # Limitamos a 10 resultados para simplicidad

    @staticmethod
    def perform_search(query: str, engine: str = 'google', open_browser: bool = False) -> List[Dict[str, str]]:
        """Método estático para realizar una búsqueda desde una aplicación externa."""
        if not query:
            raise ValueError("La consulta de búsqueda no puede estar vacía")
        searcher = LocalWebSearch()
        return searcher.search(query, engine, open_browser)

def streamlit_app():
    st.title("***Buscador Web***")

    # Selección del motor de búsqueda
    search_engines = ["Google", "Bing"]
    selected_engine = st.selectbox("Seleccione un motor de búsqueda", search_engines)

    # Campo de búsqueda
    query = st.text_input("Ingrese su búsqueda")

    if st.button("Realizar búsqueda"):
        if query:
            try:
                st.info(f"Realizando búsqueda: '{query}' en {selected_engine}")
                results = LocalWebSearch.perform_search(query, selected_engine.lower(), True)

                # Mostrar resultados
                for result in results:
                    st.subheader(result['title'])
                    st.write(result['snippet'])
                    st.write(result['link'])
                    st.write("---")

                # Botón de descarga
                st.download_button(
                    label="Descargar resultados como JSON",
                    data=json.dumps(results, indent=2),
                    file_name=f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

            except Exception as e:
                st.error(f"Error al realizar la búsqueda: {str(e)}")
                st.error(f"Traceback: {traceback.format_exc()}")
        else:
            st.warning("Por favor, ingrese una consulta de búsqueda.")

#if __name__ == "__main__":
#    streamlit_app()

# Ejemplo de uso como módulo importado
def example_usage():
    try:
        results = LocalWebSearch.perform_search("Python programming", engine="google", open_browser=False)
        for result in results:
            print(f"Título: {result['title']}")
            print(f"Enlace: {result['link']}")
            print(f"Descripción: {result['snippet']}")
            print("---")
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")

# Descomenta la siguiente línea para probar el uso como módulo
#example_usage()