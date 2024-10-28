import sqlite3
import hashlib
import os
from functools import wraps
from datetime import datetime

class DBSecurityManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.setup_security_db()
    
    def setup_security_db(self):
        """Configura la tabla de usuarios autorizados y registro de accesos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de usuarios autorizados
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS authorized_users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Tabla de registro de accesos
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_support_user(self, username, password):
        """Agrega un usuario de soporte autorizado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            cursor.execute('''
            INSERT INTO authorized_users (username, password_hash, role)
            VALUES (?, ?, ?)
            ''', (username, password_hash, 'support'))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def verify_user(self, username, password):
        """Verifica las credenciales del usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('''
        SELECT * FROM authorized_users 
        WHERE username = ? AND password_hash = ? AND role = 'support'
        ''', (username, password_hash))
        
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def log_access(self, username, action):
        """Registra los accesos a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO access_log (username, action)
        VALUES (?, ?)
        ''', (username, action))
        
        conn.commit()
        conn.close()

class SecureDatabase:
    def __init__(self, db_path, security_manager):
        self.db_path = db_path
        self.security_manager = security_manager
        self.current_user = None
    
    def requires_auth(func):
        """Decorador para verificar autenticación"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.current_user:
                raise Exception("No autorizado: Debe iniciar sesión primero")
            return func(self, *args, **kwargs)
        return wrapper
    
    def login(self, username, password):
        """Inicia sesión del usuario"""
        if self.security_manager.verify_user(username, password):
            self.current_user = username
            self.security_manager.log_access(username, "login")
            return True
        return False
    
    @requires_auth
    def execute_query(self, query, params=()):
        """Ejecuta una consulta SQL con autenticación"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            self.security_manager.log_access(self.current_user, f"execute_query: {query}")
            result = cursor.fetchall()
            conn.commit()
            return result
        finally:
            conn.close()
