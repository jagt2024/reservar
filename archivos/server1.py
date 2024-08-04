import http.server
import socketserver
import os
import argparse

# Configurar el puerto en el que el servidor escuchará
PORT = 3001

# Ruta predefinida al directorio que contiene index.html
# Modifica esta línea con la ruta correcta a tu archivo index.html
DEFAULT_DIRECTORY = "templates"

# Parseador de argumentos para permitir sobrescribir el directorio por defecto
parser = argparse.ArgumentParser(description='Servidor HTTP simple para servir index.html')
parser.add_argument('--dir', type=str, default=DEFAULT_DIRECTORY,
                    help=f'Directorio donde se encuentra index.html (por defecto: {DEFAULT_DIRECTORY})')
args = parser.parse_args()

# Usar el directorio especificado o el predeterminado
DIRECTORY = os.path.abspath(args.dir)

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
    print(f"Sirviendo archivos desde: {DIRECTORY}")
    print("Visita http://localhost:3001 en tu navegador")
    
    # Iniciar el servidor
    httpd.serve_forever()