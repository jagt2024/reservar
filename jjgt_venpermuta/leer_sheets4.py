# python leer_sheets4.py
import os, sys, toml
sys.path.insert(0, os.getcwd())

s = toml.load(".streamlit/secrets.toml")
creds_dict = dict(s["sheets"]["credentials_sheet"])
print(f"client_email: {creds_dict.get('client_email','?')}")

import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"])
gc  = gspread.authorize(creds)
sh  = gc.open("jjgt_gestion")
ws  = sh.worksheet("📋 PUBLICACIONES")
rows = ws.get_all_records()
print(f"Publicaciones: {len(rows)}")
for row in rows:
    pid  = row.get("ID Publicacion", row.get("ID Pub", row.get("ID","")))
    furl = row.get("Fotos URLs","")
    vurl = row.get("Video URL","")
    print(f"\nID:         [{pid}]")
    print(f"Fotos URLs: [{furl}]")
    print(f"Video URL:  [{vurl}]")
if rows:
    print(f"\nColumnas: {list(rows[0].keys())}")
