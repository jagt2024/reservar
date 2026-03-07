# python leer_sheets2.py
import os, sys, toml
sys.path.insert(0, os.getcwd())

s = toml.load(".streamlit/secrets.toml")
print("Claves en secrets.toml:", list(s.keys()))
print()

# Buscar la clave que tiene type = service_account
creds_key = None
for k, v in s.items():
    if isinstance(v, dict) and v.get("type") == "service_account":
        creds_key = k
        print(f"Credenciales encontradas en clave: [{creds_key}]")
        print(f"client_email: {v.get('client_email','?')}")
        break

if not creds_key:
    print("No se encontro clave con type=service_account")
    print("Contenido completo de secrets.toml:")
    for k, v in s.items():
        if isinstance(v, dict):
            print(f"  [{k}] -> keys: {list(v.keys())}")
        else:
            print(f"  {k} = {str(v)[:60]}")
    sys.exit(1)

# Conectar con la clave correcta
import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(
    s[creds_key],
    scopes=[
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ])
gc = gspread.authorize(creds)
print("Conectado OK")

sh  = gc.open("jjgt_gestion")
ws  = sh.worksheet("📋 PUBLICACIONES")
rows = ws.get_all_records()
print(f"Publicaciones: {len(rows)}")

for row in rows:
    pid  = row.get("ID Publicacion", row.get("ID Pub", row.get("ID","")))
    furl = row.get("Fotos URLs","")
    vurl = row.get("Video URL","")
    print(f"\nID: {pid}")
    print(f"Fotos URLs: [{furl}]")
    print(f"Video URL:  [{vurl}]")

print(f"\nColumnas: {list(rows[0].keys()) if rows else []}")
