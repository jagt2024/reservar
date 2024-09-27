import os
from git import Repo
from git.exc import GitCommandError
import subprocess

def run_git_command(command):
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True, shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando comando Git: {e}")
        print(f"Salida de error: {e.stderr}")
        return None

def update_github_repo(repo_path, commit_message):
    try:
        print(f"Intentando actualizar el repositorio en: {repo_path}")
        
        # Verifica si el directorio existe
        if not os.path.exists(repo_path):
            print(f"Error: El directorio {repo_path} no existe.")
            return

        # Cambia al directorio del repositorio
        os.chdir(repo_path)
        
        # Verifica los remotos configurados usando subprocess
        remotes = run_git_command("git remote -v")
        if remotes:
            print(f"Remotos configurados:\n{remotes}")
        else:
            print("No se pudieron obtener los remotos configurados.")
            return

        # Inicializa el repositorio
        repo = Repo(repo_path)
        
        # Verifica si hay cambios
        if not repo.is_dirty(untracked_files=True):
            print("No hay cambios para commitear.")
            return
        
        # Agrega todos los archivos modificados y nuevos
        repo.git.add(A=True)
        
        # Hace el commit
        repo.index.commit(commit_message)
        
        # Obtiene la referencia al branch actual
        current_branch = repo.active_branch
        
        # Intenta hacer el push al remoto usando subprocess
        push_result = run_git_command(f"git push origin {current_branch}")
        if push_result:
            print(f"Repositorio actualizado exitosamente en el branch {current_branch}.")
        else:
            print("No se pudo hacer push. Puede que necesites autenticarte en el navegador.")
            print("Intenta ejecutar 'git push' manualmente para completar la autenticación.")
    
    except Exception as e:
        print(f"Ocurrió un error: {str(e)}")

# Uso del script
if __name__ == "__main__":
    repo_path = "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas"
    commit_message = "Actualización automática de archivos locales"
    
    update_github_repo(repo_path, "update 18")
