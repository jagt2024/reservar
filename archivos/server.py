import http.server
import socketserver
import os

# Configuración
PORT = 3001  # Cambia esto al puerto de tu aplicación principal
DIRECTORY = "templates"  # Cambia esto a la ruta donde está tu index.html

class IntegratedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        elif self.path.startswith('/api/'):
            # Aquí manejarías las rutas de tu API o aplicación principal
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"message": "This is your API"}')
        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

def run_server():
    with socketserver.TCPServer(("", PORT), IntegratedHandler) as httpd:
        print(f"Servidor corriendo en el puerto {PORT}")
        print(f"Sirviendo archivos desde: {DIRECTORY}")
        print(f"Visita http://localhost:{PORT} en tu navegador")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
else:
    # Esto permite importar este script como un módulo en tu aplicación principal
    handler = IntegratedHandler
