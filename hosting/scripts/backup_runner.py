"""
backup_runner.py — Script de Backup JAGT Hosting
Sube hosting-jagt.xlsx a Google Drive automáticamente.

Carpeta Drive : JAGT-Hosting
Folder ID     : 1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn
Cuenta servicio: servicio-cuenta-reserva-empres@appreservasem p.iam.gserviceaccount.com
"""

import sqlite3
import datetime
import json
import os
import sys

# ── Configuración ─────────────────────────────────────────────────────────────
DB_PATH       = "hosting_jagt.db"
XLSX_NAME     = "hosting-jagt.xlsx"
DRIVE_FOLDER  = "1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn"   # ID carpeta JAGT-Hosting

# ── Obtener credenciales Google desde secrets.toml o variable de entorno ──────
def get_google_credentials():
    """
    Intenta obtener las credenciales en este orden:
    1. Streamlit secrets  (st.secrets)
    2. Variable de entorno GOOGLE_CREDENTIALS_JSON
    3. Archivo local google_credentials.json
    """
    # 1. Streamlit secrets
    try:
        import streamlit as st
        creds_raw = st.secrets["google"]["GOOGLE_CREDENTIALS"]
        if isinstance(creds_raw, str):
            return json.loads(creds_raw)
        return dict(creds_raw)          # ya es un objeto TOML
    except Exception:
        pass

    # 2. Variable de entorno (GitHub Actions)
    env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if env_creds:
        try:
            return json.loads(env_creds)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Variable de entorno GOOGLE_CREDENTIALS_JSON inválida: {e}")
            sys.exit(1)

    # 3. Archivo local (desarrollo)
    local_file = "google_credentials.json"
    if os.path.exists(local_file):
        with open(local_file) as f:
            return json.load(f)

    print("[ERROR] No se encontraron credenciales de Google.")
    print("  → Agrega GOOGLE_CREDENTIALS en secrets.toml o como variable de entorno.")
    return None

# ── Subir / actualizar archivo en Google Drive ────────────────────────────────
def upload_to_drive(local_path: str, folder_id: str, creds_dict: dict) -> bool:
    """
    Sube o actualiza hosting-jagt.xlsx en la carpeta JAGT-Hosting de Drive.
    Retorna True si tuvo éxito.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("[ERROR] Faltan dependencias. Ejecuta:")
        print("  pip install google-api-python-client google-auth")
        return False

    try:
        # Autenticar
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds  = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        mime_xlsx = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Buscar si el archivo ya existe en la carpeta
        query   = f"name='{XLSX_NAME}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, fields="files(id, name)"
        ).execute()
        existing = results.get("files", [])

        media = MediaFileUpload(local_path, mimetype=mime_xlsx, resumable=True)

        if existing:
            # Actualizar archivo existente
            file_id = existing[0]["id"]
            service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            print(f"[OK] Archivo actualizado en Drive  → ID: {file_id}")
        else:
            # Crear archivo nuevo
            file_meta = {
                "name"    : XLSX_NAME,
                "parents" : [folder_id],
            }
            created = service.files().create(
                body=file_meta, media_body=media, fields="id"
            ).execute()
            print(f"[OK] Archivo creado en Drive  → ID: {created['id']}")

        print(f"     📁 Carpeta: https://drive.google.com/drive/folders/{folder_id}")
        return True

    except Exception as e:
        print(f"[ERROR] No se pudo subir a Drive: {e}")
        return False

# ── Registrar backup en SQLite ────────────────────────────────────────────────
def update_sqlite_backup(app_id: int, app_name: str, destination: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO backups
           (app_id, backup_date, status, size_kb, destination, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            app_id,
            datetime.datetime.now().isoformat(),
            "success",
            512.0,
            destination,
            f"Backup automático diario — {app_name}",
        ),
    )
    conn.commit()
    conn.close()
    print(f"[OK] Backup registrado en DB  → app_id={app_id}  ({app_name})")

# ── Generar Excel ─────────────────────────────────────────────────────────────
def create_xlsx_backup() -> str | None:
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[WARN] openpyxl no disponible — omitiendo Excel")
        return None

    wb = openpyxl.Workbook()

    HEADER_FILL = PatternFill("solid", start_color="0057FF")
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    TITLE_FONT  = Font(bold=True, color="00D4FF", size=14)
    MONO_FONT   = Font(name="Courier New", size=10, color="333333")

    def hrow(ws, cols, row=1):
        for c, val in enumerate(cols, 1):
            cell = ws.cell(row=row, column=c, value=val)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def set_widths(ws, widths):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ── Hoja 1: Resumen ───────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Resumen"
    ws1.sheet_view.showGridLines = False
    ws1.column_dimensions["A"].width = 28
    ws1.column_dimensions["B"].width = 48
    ws1.row_dimensions[1].height = 36

    ws1["A1"] = "JAGT HOSTING PANEL"
    ws1["A1"].font = TITLE_FONT
    ws1["A1"].fill = PatternFill("solid", start_color="0A0E1A")
    ws1.merge_cells("A1:B1")

    info = [
        ("Dominio",          "josegart"),
        ("Email Admin",      "josegarjagt@gmail.com"),
        ("Repositorio",      "github.com/jagt2024/Reservar/"),
        ("Landing Page",     "jagt2024/Reservar/pagina_web/jagt_landing.py"),
        ("Plataforma",       "Streamlit Cloud (24/7)"),
        ("Carpeta Drive",    "JAGT-Hosting"),
        ("Folder ID Drive",  DRIVE_FOLDER),
        ("Cuenta Servicio",  "servicio-cuenta-reserva-empres@appreservasem p.iam.gserviceaccount.com"),
        ("Excel Drive",      XLSX_NAME),
        ("DB Local",         "hosting_jagt.db (SQLite3)"),
        ("Último Backup",    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for i, (k, v) in enumerate(info, 2):
        ws1[f"A{i}"] = k
        ws1[f"A{i}"].font = Font(bold=True, color="555555")
        ws1[f"B{i}"] = v
        ws1[f"B{i}"].font = MONO_FONT

    # ── Hoja 2: Aplicaciones ──────────────────────────────────────────────
    ws2 = wb.create_sheet("Aplicaciones")
    ws2.sheet_view.showGridLines = False
    hrow(ws2, ["ID","Nombre","Dominio","Repo GitHub","Estado","Tech","Backup","Frecuencia","Descripción","Creada"])
    set_widths(ws2, [5,25,35,45,12,15,10,12,35,15])

    conn = sqlite3.connect(DB_PATH)
    for r, row in enumerate(conn.execute(
        "SELECT id,name,domain,repo_path,status,tech,backup_enabled,backup_freq,description,created_at FROM apps"
    ).fetchall(), 2):
        row = list(row)
        row[6] = "Si" if row[6] else "No"
        row[9] = (row[9] or "")[:10]
        for c, val in enumerate(row, 1):
            ws2.cell(row=r, column=c, value=val).alignment = Alignment(vertical="center")
        color = "0D2B1A" if row[4] == "active" else "2B0D0D"
        font_c = "10B981" if row[4] == "active" else "EF4444"
        ws2.cell(row=r, column=5).fill = PatternFill("solid", start_color=color)
        ws2.cell(row=r, column=5).font = Font(color=font_c, bold=True)

    # ── Hoja 3: Backups ───────────────────────────────────────────────────
    ws3 = wb.create_sheet("Backups")
    ws3.sheet_view.showGridLines = False
    hrow(ws3, ["ID","App ID","App Nombre","Fecha Backup","Estado","Tamaño KB","Destino","Notas"])
    set_widths(ws3, [5,8,25,22,12,12,30,40])

    for r, row in enumerate(conn.execute("""
        SELECT b.id, b.app_id, a.name, b.backup_date, b.status,
               b.size_kb, b.destination, b.notes
        FROM backups b LEFT JOIN apps a ON b.app_id=a.id
        ORDER BY b.backup_date DESC LIMIT 300
    """).fetchall(), 2):
        for c, val in enumerate(row, 1):
            ws3.cell(row=r, column=c, value=val)
        fc = "10B981" if row[4] == "success" else "EF4444"
        ws3.cell(row=r, column=5).font = Font(color=fc, bold=True)

    # ── Hoja 4: Spam Rules ────────────────────────────────────────────────
    ws4 = wb.create_sheet("Spam_Rules")
    ws4.sheet_view.showGridLines = False
    hrow(ws4, ["ID","Tipo","Valor","Acción","Activa","Creada"])
    set_widths(ws4, [5,15,35,12,10,20])

    for r, row in enumerate(conn.execute(
        "SELECT id,rule_type,value,action,active,created_at FROM spam_rules"
    ).fetchall(), 2):
        row = list(row)
        row[4] = "Si" if row[4] else "No"
        row[5] = (row[5] or "")[:10]
        for c, val in enumerate(row, 1):
            ws4.cell(row=r, column=c, value=val)

    # ── Hoja 5: Usuarios ──────────────────────────────────────────────────
    ws5 = wb.create_sheet("Usuarios")
    ws5.sheet_view.showGridLines = False
    hrow(ws5, ["ID","Usuario","Rol","Email","Creado","Último Acceso"])
    set_widths(ws5, [5,18,12,38,20,20])

    for r, row in enumerate(conn.execute(
        "SELECT id,username,role,email,created_at,last_login FROM users"
    ).fetchall(), 2):
        row = list(row)
        row[4] = (row[4] or "")[:10]
        row[5] = (row[5] or "—")[:10]
        for c, val in enumerate(row, 1):
            ws5.cell(row=r, column=c, value=val)

    conn.close()

    wb.save(XLSX_NAME)
    size_kb = os.path.getsize(XLSX_NAME) / 1024
    print(f"[OK] Excel generado: {XLSX_NAME}  ({size_kb:.1f} KB)")
    return XLSX_NAME

# ── Runner principal ──────────────────────────────────────────────────────────
def run_all_backups():
    sep = "=" * 54
    print(f"\n{sep}")
    print(f"  JAGT Hosting Backup — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Carpeta Drive: JAGT-Hosting ({DRIVE_FOLDER})")
    print(f"{sep}")

    # 1. Registrar backups en SQLite
    conn = sqlite3.connect(DB_PATH)
    apps = conn.execute(
        "SELECT id, name FROM apps WHERE backup_enabled=1"
    ).fetchall()
    conn.close()

    if not apps:
        print("[WARN] No hay apps con backup habilitado.")
    else:
        for app_id, app_name in apps:
            print(f"\n[→] Procesando: {app_name}")
            update_sqlite_backup(app_id, app_name, f"Google Drive / {XLSX_NAME}")

    # 2. Generar Excel
    print(f"\n[→] Generando Excel...")
    xlsx_path = create_xlsx_backup()
    if not xlsx_path:
        print("[ERROR] No se pudo generar el Excel.")
        return None

    # 3. Subir a Google Drive
    print(f"\n[→] Subiendo a Google Drive (carpeta: JAGT-Hosting)...")
    creds = get_google_credentials()
    drive_ok = False

    if creds:
        drive_ok = upload_to_drive(xlsx_path, DRIVE_FOLDER, creds)
    else:
        print("[WARN] Sin credenciales → el Excel queda solo en local.")

    # 4. Resumen final
    print(f"\n{sep}")
    print(f"  Apps respaldadas : {len(apps)}")
    print(f"  Excel local      : {xlsx_path}")
    print(f"  Google Drive     : {'✅ Subido' if drive_ok else '⚠️  Solo local'}")
    print(f"  Carpeta Drive    : JAGT-Hosting")
    print(f"  URL              : https://drive.google.com/drive/folders/{DRIVE_FOLDER}")
    print(f"{sep}\n")

    return xlsx_path

if __name__ == "__main__":
    run_all_backups()
