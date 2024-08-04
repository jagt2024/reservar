import http.server
import socketserver
import os

# Configurar el puerto en el que el servidor escuchará
PORT = 3001

# Directorio donde se encuentra el archivo index.html
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Clase personalizada para manejar las solicitudes
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

# Crear el servidor
with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print(f"Servidor corriendo en el puerto {PORT}")
    print(f"Directorio del servidor: {DIRECTORY}")
    print("Visita http://localhost:3001 en tu navegador")
    
    # Iniciar el servidor
    httpd.serve_forever()
