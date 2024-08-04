from flask import Flask, send_from_directory
import os

app = Flask(__name__)

# Ruta al directorio que contiene tu index.html
# Modifica esta línea con la ruta correcta a tu archivo index.html
STATIC_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

@app.route('/')
def serve_index():
    return send_from_directory(STATIC_FILE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_FILE_DIR, path)

# Tus otras rutas y lógica de la aplicación irían aquí

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3001))
    app.run(host='192.168.139.160', port=port, debug=True)
