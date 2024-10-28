# init_database.py
import sqlite3
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name='reservas_dp.db'):
        self.db_name = db_name
        
    def init_database(self):
        """Inicializa la base de datos con las tablas necesarias"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Crear tablas necesarias
        # Tabla de usuarios de soporte
        c.execute('''
        CREATE TABLE IF NOT EXISTS support_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Tabla de registro de accesos
        c.execute('''
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Aquí puedes agregar más tablas según tus necesidades
        # Por ejemplo, una tabla para tus datos principales:
        c.execute('''
        CREATE TABLE IF NOT EXISTS your_main_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field1 TEXT,
            field2 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        print(f"Base de datos {self.db_name} inicializada correctamente")
    
    def add_initial_data(self):
        """Agrega datos iniciales a la base de datos"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Agregar usuario de soporte inicial
        from hashlib import sha256
        admin_password = "admin_soporte"  # Cambiar esto
        password_hash = sha256(admin_password.encode()).hexdigest()
        
        try:
            c.execute('''
            INSERT INTO support_users (username, password_hash, role)
            VALUES (?, ?, ?)
            ''', ('admin', password_hash, 'admin'))
        except sqlite3.IntegrityError:
            print("El usuario admin ya existe")
        
        # Agregar algunos datos de ejemplo
        c.execute('''
        INSERT INTO your_main_table (field1, field2)
        VALUES (?, ?)
        ''', ('ejemplo1', 'valor1'))
        
        conn.commit()
        conn.close()
        print("Datos iniciales agregados correctamente")

class DatabaseEncryption:
    def __init__(self):
        self.key_file = 'encryption_key.key'
    
    def generate_key(self, password):
        """Genera una clave de encriptación basada en contraseña"""
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        # Guardar la sal y la clave
        with open(self.key_file, 'wb') as f:
            f.write(salt + key)
        return key
    
    def encrypt_database(self, db_path, password):
        """Encripta la base de datos"""
        # Generar clave
        key = self.generate_key(password)
        fernet = Fernet(key)
        
        # Leer la base de datos
        with open(db_path, 'rb') as file:
            db_data = file.read()
        
        # Encriptar datos
        encrypted_data = fernet.encrypt(db_data)
        
        # Guardar base de datos encriptada
        encrypted_db_path = f"{db_path}.encrypted"
        with open(encrypted_db_path, 'wb') as file:
            file.write(encrypted_data)
        
        return encrypted_db_path
    
    def decrypt_database(self, encrypted_db_path, password):
        """Desencripta la base de datos"""
        # Leer la sal y la clave
        with open(self.key_file, 'rb') as f:
            key_data = f.read()
            salt = key_data[:16]
            key = key_data[16:]
        
        fernet = Fernet(key)
        
        # Leer la base de datos encriptada
        with open(encrypted_db_path, 'rb') as file:
            encrypted_data = file.read()
        
        # Desencriptar datos
        decrypted_data = fernet.decrypt(encrypted_data)
        
        # Guardar base de datos desencriptada
        decrypted_db_path = encrypted_db_path.replace('.encrypted', '')
        with open(decrypted_db_path, 'wb') as file:
            file.write(decrypted_data)
        
        return decrypted_db_path

def main():
    # Inicializar la base de datos
    db_manager = DatabaseManager()
    db_manager.init_database()
    db_manager.add_initial_data()
    
    # Encriptar la base de datos para producción
    encryptor = DatabaseEncryption()
    password = input("Ingrese la contraseña para encriptar la base de datos: ")
    encrypted_path = encryptor.encrypt_database('database.db', password)
    
    print(f"\nBase de datos encriptada guardada en: {encrypted_path}")
    print("Guarda la contraseña de forma segura, la necesitarás en producción")
    print("\nArchivos generados:")
    print(f"1. {encrypted_path} - Subir a GitHub")
    print(f"2. {encryptor.key_file} - Mantener seguro, NO subir a GitHub")
    
    # Crear archivo .gitignore si no existe
    gitignore_content = """
# Base de datos
database.db
*.db-journal

# Archivos de encriptación
encryption_key.key

# Archivos de Python
__pycache__/
*.py[cod]
*$py.class

# Entorno virtual
venv/
env/

# Archivos de sistema
.DS_Store
Thumbs.db

# Archivos de Streamlit
.streamlit/secrets.toml
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("\n.gitignore creado/actualizado")

if __name__ == "__main__":
    main()
