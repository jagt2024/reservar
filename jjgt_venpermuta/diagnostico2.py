# Pega este script en tu carpeta jjgt_venpermuta y ejecuta: python diagnostico2.py
import os, sys
sys.path.insert(0, os.getcwd())

# Simular lo que hace _read_local con rutas típicas de Windows
rutas_prueba = [
    "JJGT_Media/PUB-1772579998/foto_00_carro2.jpg",
    "JJGT_Media\\PUB-1772579998\\foto_00_carro2.jpg",
    r"JJGT_Media\PUB-1772579998\foto_00_carro2.jpg",
    os.path.abspath("JJGT_Media/PUB-1772579998/foto_00_carro2.jpg"),
]

print("=== TEST DE RUTAS ===")
for r in rutas_prueba:
    existe = os.path.isfile(r)
    norm   = os.path.normpath(r)
    print(f"Ruta:    {r}")
    print(f"Normpath:{norm}")
    print(f"Existe:  {existe}")
    print()

# Leer secrets para ver qué ruta hay en Sheets
print("=== RUTA EN SHEETS (fotos_urls) ===")
try:
    import toml
    s = toml.load(".streamlit/secrets.toml")
    print("secrets.toml encontrado")
except Exception as e:
    print(f"No se pudo leer secrets: {e}")

# Intentar conectar a Sheets y leer la columna Fotos URLs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    import toml

    s      = toml.load(".streamlit/secrets.toml")
    creds  = Credentials.from_service_account_info(
        s["gcp_service_account"],
        scopes=["https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"])
    gc     = gspread.authorize(creds)
    sh     = gc.open("jjgt_gestion")
    ws     = sh.worksheet("📋 PUBLICACIONES")
    rows   = ws.get_all_records()
    print(f"\nFilas en PUBLICACIONES: {len(rows)}")
    for row in rows:
        pid  = row.get("ID Publicación", row.get("ID", "?"))
        furl = row.get("Fotos URLs", "")
        vurl = row.get("Video URL", "")
        print(f"\nID: {pid}")
        print(f"Fotos URLs: [{furl}]")
        print(f"Video URL:  [{vurl}]")
        if furl:
            primera = furl.split(",")[0].strip()
            print(f"Existe primera foto: {os.path.isfile(primera)}")
            print(f"Normpath: {os.path.normpath(primera)}")
            print(f"Existe normpath: {os.path.isfile(os.path.normpath(primera))}")
except Exception as e:
    print(f"Error leyendo Sheets: {e}")

print("\n=== FIN ===")
