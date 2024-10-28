# Archivo .gitignore
*.db
*.sqlite
*.sqlite3
database/*
!database/.gitkeep

# Script de encriptación para la base de datos
import sqlite3
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

class DatabaseEncryption:
    def __init__(self, key_path='secure_key.key'):
        self.key_path = key_path
        
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
        
        # Guardar la sal junto con la clave
        with open(self.key_path, 'wb') as key_file:
            key_file.write(salt + key)
        
    def encrypt_database(self, db_path, password):
        """Encripta la base de datos"""
        # Leer la base de datos original
        with open(db_path, 'rb') as file:
            data = file.read()
            
        # Generar clave y encriptar
        self.generate_key(password)
        with open(self.key_path, 'rb') as key_file:
            key_data = key_file.read()
            salt = key_data[:16]
            key = key_data[16:]
            
        f = Fernet(key)
        encrypted_data = f.encrypt(data)
        
        # Guardar la base de datos encriptada
        encrypted_path = db_path + '.encrypted'
        with open(encrypted_path, 'wb') as file:
            file.write(encrypted_data)
            
        return encrypted_path
        
    def decrypt_database(self, encrypted_db_path, password):
        """Desencripta la base de datos"""
        # Leer la clave y la sal
        with open(self.key_path, 'rb') as key_file:
            key_data = key_file.read()
            salt = key_data[:16]
            key = key_data[16:]
            
        # Leer la base de datos encriptada
        with open(encrypted_db_path, 'rb') as file:
            encrypted_data = file.read()
            
        # Desencriptar
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data)
        
        # Guardar la base de datos desencriptada
        decrypted_path = encrypted_db_path.replace('.encrypted', '.decrypted')
        with open(decrypted_path, 'wb') as file:
            file.write(decrypted_data)
            
        return decrypted_path

# Ejemplo de uso
if __name__ == "__main__":
    encryptor = DatabaseEncryption()
    
    # Encriptar la base de datos antes de subir a GitHub
    encrypted_file = encryptor.encrypt_database('mi_base_datos.db', 'contraseña_segura')
    
    # Para usar la base de datos localmente
    decrypted_file = encryptor.decrypt_database(encrypted_file, 'contraseña_segura')
