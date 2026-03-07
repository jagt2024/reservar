# python leer_acceso.py
import os, sys, toml
sys.path.insert(0, os.getcwd())

s = toml.load(".streamlit/secrets.toml")
creds_dict = dict(s["sheets"]["credentials_sheet"])

import gspread
from google.oauth2.service_account import Credentials
creds = Credentials.from_service_account_info(creds_dict,
    scopes=["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"])
gc  = gspread.authorize(creds)
archivos = gc.list_spreadsheet_files()

for a in archivos:
    if "jjgt" in a["name"].lower():
        sh = gc.open_by_key(a["id"])
        for ws_name in ["🔐 ACCESO", "📊 DASHBOARD"]:
            try:
                ws   = sh.worksheet(ws_name)
                rows = ws.get_all_values()
                print(f"\n=== {ws_name} ({len(rows)} filas) ===")
                for r in rows[:30]:
                    print(r)
            except Exception as e:
                print(f"Error {ws_name}: {e}")
        break
