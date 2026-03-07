# python check_dup2.py
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
gc  = gspread.authorize(creds)
archivos = gc.list_spreadsheet_files()

for a in archivos:
    if "jjgt" in a["name"].lower():
        sh = gc.open_by_key(a["id"])

        # Ver fila completa de VEHÍCULOS
        ws = sh.worksheet("🚗 VEHÍCULOS")
        rows = ws.get_all_records()
        print("=== VEHÍCULOS ===")
        for r in rows:
            print(dict(r))

        # Ver fila completa de PUBLICACIONES
        ws2 = sh.worksheet("📋 PUBLICACIONES")
        rows2 = ws2.get_all_records()
        print("\n=== PUBLICACIONES ===")
        for r in rows2:
            print(dict(r))
        break
