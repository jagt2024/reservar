import os
import sys
import subprocess

#Archivo para generar o crear un Ejecutable dela aplicacion
#forma de ejecutr en la ruta del script de este archivo
#python build_exe.py ruta/a/tu/script.py [nombre_del_ejecutable]
#Donde ruta/a/tu/script.py es la ruta a tu aplicación Python, y [nombre_del_ejecutable] es opcional.

def install_pyinstaller():
    print("Instalando PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def create_executable(script_path, output_name=None):
    if not os.path.exists(script_path):
        print(f"Error: El archivo '{script_path}' no existe.")
        return

    if output_name is None:
        output_name = os.path.splitext(os.path.basename(script_path))[0]

    print(f"Generando ejecutable para: {script_path}")
    
    try:
        subprocess.check_call([
            "pyinstaller",
            "--onefile",
            "--windowed",
            f"--name={output_name}",
            script_path
        ])
        print(f"Ejecutable generado exitosamente: {output_name}")
        print(f"Puedes encontrar el ejecutable en la carpeta 'dist'.")
    except subprocess.CalledProcessError as e:
        print(f"Error al generar el ejecutable: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python build_exe.py <ruta_del_script> [nombre_de_salida]")
        sys.exit(1)

    script_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        import pyinstaller
    except ImportError:
        print("PyInstaller no está instalado. Intentando instalar...")
        install_pyinstaller()

    create_executable(script_path, output_name)
