# python leer_cols.py
import os, sys, toml
sys.path.insert(0, os.getcwd())

s = toml.load(".streamlit/secrets.toml")
creds_dict = dict(s["sheets"]["credentials_sheet"])

import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"])
gc = gspread.authorize(creds)

# Listar todos los archivos accesibles
archivos = gc.list_spreadsheet_files()
print("Archivos accesibles por esta cuenta:")
for a in archivos:
    print(f"  - {a['name']} (id: {a['id']})")

# Intentar abrir por ID si el nombre falla
for a in archivos:
    if "jjgt" in a["name"].lower(): #or "gestion" in a["name"].lower():
        print(f"\nAbriendo: {a['name']}")
        sh = gc.open_by_key(a["id"])
        for ws in sh.worksheets():
            print(f"  Hoja: [{ws.title}]")
            try:
                fila1 = ws.row_values(1)
                print(f"    Columnas: {fila1}")
                if len(ws.get_all_values()) > 1:
                    fila2 = ws.row_values(2)
                    print(f"    Fila 2:   {fila2[:6]}")
            except Exception as e:
                print(f"    Error: {e}")
