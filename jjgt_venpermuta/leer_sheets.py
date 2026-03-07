# Ejecutar en carpeta jjgt_venpermuta: python leer_sheets.py
import os, sys
sys.path.insert(0, os.getcwd())

try:
    import toml
    s = toml.load(".streamlit/secrets.toml")
    print("secrets.toml OK")
    gcp = s.get("gcp_service_account", {})
    print(f"client_email: {gcp.get('client_email','NO ENCONTRADO')}")
except Exception as e:
    print(f"Error leyendo secrets: {e}")
    sys.exit(1)

try:
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        s["gcp_service_account"],
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ])
    gc = gspread.authorize(creds)
    print("Conectado a Google OK")

    sh = gc.open("jjgt_gestion")
    print(f"Hojas disponibles: {[w.title for w in sh.worksheets()]}")

    ws = sh.worksheet("📋 PUBLICACIONES")
    rows = ws.get_all_records()
    print(f"\nPublicaciones encontradas: {len(rows)}")

    for row in rows:
        pid  = row.get("ID Publicación", row.get("ID Pub", row.get("ID", "?")))
        furl = row.get("Fotos URLs", row.get("Fotos_URLs", row.get("fotos_urls", "COLUMNA NO ENCONTRADA")))
        vurl = row.get("Video URL",  row.get("Video_URL",  row.get("video_url",  "")))
        print(f"\n--- Publicacion ---")
        print(f"ID:         [{pid}]")
        print(f"Fotos URLs: [{furl}]")
        print(f"Video URL:  [{vurl}]")

    if rows:
        print(f"\nColumnas disponibles: {list(rows[0].keys())}")

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
