import subprocess
import sys
import os
from flask import Flask, jsonify

def run_npm_dev():
    try:
        # Cambia al directorio del proyecto si es necesario
        # os.chdir('/ruta/a/tu/proyecto')

        # Ejecuta 'npm run dev'
        process = subprocess.Popen(['npm', 'run', 'dev'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)

        # Captura la salida en tiempo real
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                sys.stdout.flush()

        # Captura cualquier error
        stderr = process.stderr.read()
        if stderr:
            print(f"Error: {stderr}")
            return False

        return True
    except Exception as e:
        print(f"Se produjo un error: {str(e)}")
        return False

# Crear una aplicación Flask para ejecutar la función desde la web
app = Flask(__name__)

@app.route('/api-whatsapp-ts/run-npm-dev', methods=['GET'])
def web_run_npm_dev():
    success = run_npm_dev()
    return jsonify({"success": success})

if __name__ == "__main__":
    # Si se ejecuta directamente, corre la función
    run_npm_dev()
    
    # Descomenta la siguiente línea para ejecutar el servidor Flask
    # app.run(debug=True)
