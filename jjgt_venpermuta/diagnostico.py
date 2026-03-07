# Script de diagnóstico — ejecutar en la misma carpeta que app.py
import os, sys
sys.path.insert(0, os.getcwd())

print("=== DIAGNÓSTICO JJGT MEDIA ===")
print(f"Directorio actual: {os.getcwd()}")
print(f"Directorio JJGT_Media: {os.path.abspath('JJGT_Media')}")
print(f"Existe JJGT_Media: {os.path.isdir('JJGT_Media')}")
print()

# Listar carpetas dentro de JJGT_Media
media_dir = "JJGT_Media"
if os.path.isdir(media_dir):
    carpetas = os.listdir(media_dir)
    print(f"Carpetas en JJGT_Media: {carpetas}")
    for c in carpetas:
        archivos = os.listdir(os.path.join(media_dir, c))
        print(f"  {c}/: {archivos}")
else:
    print("❌ JJGT_Media NO EXISTE en este directorio")
    print("   Buscando en otras ubicaciones...")
    for root, dirs, files in os.walk(os.path.expanduser("~\\Desktop"), topdown=True):
        if "JJGT_Media" in dirs:
            print(f"   Encontrado en: {root}")
        if root.count(os.sep) - os.path.expanduser("~\\Desktop").count(os.sep) > 4:
            break

print()
print("=== FIN DIAGNÓSTICO ===")
