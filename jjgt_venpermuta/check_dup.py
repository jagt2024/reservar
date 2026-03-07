# python check_dup.py
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

archivos = gc.list_spreadsheet_files()
for a in archivos:
    if "jjgt" in a["name"].lower():
        sh = gc.open_by_key(a["id"])
        for ws in sh.worksheets():
            rows = ws.get_all_values()
            print(f"Hoja [{ws.title}]: {len(rows)-1} filas de datos")
            if rows:
                print(f"  Cols: {rows[0][:5]}")
            if len(rows) > 1:
                print(f"  Fila2: {rows[1][:5]}")
        break
