import http.server
import socketserver
import os
import argparse
import socket

def find_free_port(start_port=8000, max_port=65535):
    for port in range(start_port, max_port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', port))
            s.close()
            return port
        except OSError:
            pass
    return None

# Ruta predefinida al directorio que contiene index.html
# Modifica esta línea con la ruta correcta a tu archivo index.html
DEFAULT_DIRECTORY = r"C:\ruta\a\tu\directorio"

# Parseador de argumentos
parser = argparse.ArgumentParser(description='Servidor HTTP simple para servir index.html')
parser.add_argument('--dir', type=str, default=DEFAULT_DIRECTORY,
                    help=f'Directorio donde se encuentra index.html (por defecto: {DEFAULT_DIRECTORY})')
parser.add_argument('--port', type=int, default=8000,
                    help='Puerto para el servidor (por defecto: 8000)')
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

# Intentar iniciar el servidor
try:
    PORT = args.port
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"Servidor corriendo en el puerto {PORT}")
        print(f"Sirviendo archivos desde: {DIRECTORY}")
        print(f"Visita http://localhost:{PORT} en tu navegador")
        httpd.serve_forever()
except PermissionError:
    print(f"Error: No se pudo usar el puerto {PORT}. Intentando encontrar un puerto disponible...")
    free_port = find_free_port(PORT + 1)
    if free_port:
        print(f"Intentando con el puerto {free_port}")
        try:
            with socketserver.TCPServer(("", free_port), MyHandler) as httpd:
                print(f"Servidor corriendo en el puerto {free_port}")
                print(f"Sirviendo archivos desde: {DIRECTORY}")
                print(f"Visita http://localhost:{free_port} en tu navegador")
                httpd.serve_forever()
        except Exception as e:
            print(f"Error al iniciar el servidor en el puerto {free_port}: {e}")
    else:
        print("No se pudo encontrar un puerto disponible. Por favor, cierra algunas aplicaciones e intenta de nuevo.")
except Exception as e:
    print(f"Error inesperado: {e}")
