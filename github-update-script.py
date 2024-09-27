import os
from git import Repo

def update_github_repo(repo_path, commit_message):
    try:
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
        
        # Hace el push al remoto
        origin = repo.remote(name='https://github.com/jagt2024/reservar.git')
        origin.push(current_branch)
        
        print(f"Repositorio actualizado exitosamente en el branch {current_branch}.")
    
    except Exception as e:
        print(f"Ocurrió un error: {str(e)}")

# Uso del script
if __name__ == "__main__":
    repo_path = "C:/Users/hp  pc/Desktop/Programas practica Python/App - Reservas"
    commit_message = "Actualización automática de archivos locales"
    
    update_github_repo(repo_path, "update 18")
