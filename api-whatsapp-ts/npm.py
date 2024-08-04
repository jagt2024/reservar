import subprocess
import os
import time

def run_npm_command(command, directory, timeout=60):
    """
    Ejecuta un comando npm en el directorio especificado con un timeout.
    
    :param command: El comando npm a ejecutar (sin 'npm' al principio)
    :param directory: La ruta del directorio donde se ejecutará el comando
    :param timeout: Tiempo máximo de espera en segundos (por defecto 60)
    :return: El resultado de la ejecución del comando o un mensaje de error
    """
    original_dir = os.getcwd()
    try:
        # Cambia al directorio especificado
        os.chdir(directory)
        print(f"Cambiando al directorio: {directory}")
        
        # Construye el comando completo
        full_command = f"npm {command}"
        print(f"Ejecutando comando: {full_command}")
        
        # Ejecuta el comando con un timeout
        start_time = time.time()
        process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        while process.poll() is None:
            if time.time() - start_time > timeout:
                process.kill()
                return f"Error: El comando excedió el tiempo límite de {timeout} segundos."
            time.sleep(0.1)
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            return f"Error al ejecutar el comando. Código de salida: {process.returncode}\nError: {stderr}"
        
        return f"Comando ejecutado exitosamente.\nSalida:\n{stdout}"
    
    except Exception as e:
        return f"Error inesperado: {str(e)}"
    
    finally:
        # Vuelve al directorio original
        os.chdir(original_dir)

# Ejemplo de uso
if __name__ == "__main__":
    # Directorio donde se ejecutará el comando npm
    npm_directory = "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas/api-whatsapp-ts"
    
    # Comando npm a ejecutar (por ejemplo, 'install')
    npm_command = "run dev"
    
    # Ejecuta el comando y muestra el resultado
    print("Iniciando la ejecución del comando npm...")
    output = run_npm_command(npm_command, npm_directory, timeout=1500)
    print("\nResultado de la ejecución:")
    print(output)
