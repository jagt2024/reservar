"""
backup_runner.py — JAGT Hosting Backup Completo
================================================
Flujo:
  PASO 0 · Inicializa / migra la base de datos
  PASO 1 · Genera hosting-jagt.xlsx con estructura del hosting
  PASO 2 · Conecta a Google Drive
  PASO 3 · Sube hosting-jagt.xlsx a Drive (crea o actualiza)
  PASO 4 · Lee apps con sheet_id registrado en la DB
  PASO 5 · Por cada app con Sheet ID:
             - Exporta el Google Sheet como .xlsx
             - Sube NombreApp.xlsx          (versión actual, sobreescribe)
             - Sube NombreApp_backup_FECHA  (copia histórica nueva)
             - Registra ambas operaciones en hosting_jagt.db
  PASO 6 · Hace backup de archivos .xlsx que ya existen en Drive
           (archivos subidos manualmente, no desde Sheets)

Carpeta Drive  : JAGT-Hosting
Folder ID      : 1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn
Cuenta servicio: servicio-cuenta-reserva-empres@appreservasem p.iam.gserviceaccount.com

Uso:
  python backup_runner.py            # backup completo
  python backup_runner.py --dry-run  # listar sin ejecutar
"""

import sqlite3
import datetime
import json
import os
import sys
import io
from typing import Optional

# ── Configuración ─────────────────────────────────────────────────────────────
DB_PATH      = "hosting_jagt.db"
XLSX_NAME    = "hosting-jagt.xlsx"
DRIVE_FOLDER = "1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn"
MIME_XLSX    = ("application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet")


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(os.path.abspath(DB_PATH), timeout=30,
                           check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    """Crea tablas si no existen y migra columnas nuevas."""
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS apps (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            domain         TEXT DEFAULT '',
            repo_path      TEXT DEFAULT '',
            status         TEXT DEFAULT 'active',
            tech           TEXT DEFAULT 'streamlit',
            description    TEXT DEFAULT '',
            created_at     TEXT,
            backup_enabled INTEGER DEFAULT 1,
            backup_freq    TEXT DEFAULT 'daily',
            sheet_id       TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT DEFAULT 'viewer',
            email         TEXT DEFAULT '',
            created_at    TEXT,
            last_login    TEXT
        );
        CREATE TABLE IF NOT EXISTS backups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id      INTEGER,
            backup_date TEXT,
            status      TEXT,
            size_kb     REAL DEFAULT 0,
            destination TEXT DEFAULT '',
            notes       TEXT DEFAULT '',
            FOREIGN KEY(app_id) REFERENCES apps(id)
        );
        CREATE TABLE IF NOT EXISTS spam_rules (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type  TEXT, value TEXT,
            action     TEXT DEFAULT 'block',
            created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS access_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, path TEXT, action TEXT,
            timestamp TEXT, blocked INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS secrets_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT, key_name TEXT,
            key_value TEXT, updated_at TEXT
        );
        """)
        conn.commit()

        # Migraciones seguras (agregan columnas si no existen)
        for migration in [
            "ALTER TABLE apps ADD COLUMN sheet_id TEXT DEFAULT ''",
        ]:
            try:
                conn.execute(migration)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Columna ya existe

        # Seed admin
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            import hashlib
            pw = hashlib.sha256("jagt2024!".encode()).hexdigest()
            conn.execute(
                "INSERT INTO users(username,password_hash,role,email,created_at)"
                " VALUES(?,?,?,?,?)",
                ("josegart", pw, "admin", "josegarjagt@gmail.com",
                 datetime.datetime.now().isoformat())
            )
            conn.commit()
            print("[OK] Usuario admin creado: josegart")

        # Seed apps
        if conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0] == 0:
            now = datetime.datetime.now().isoformat()
            conn.executemany(
                "INSERT INTO apps(name,domain,repo_path,status,tech,"
                "description,created_at,backup_enabled,backup_freq,sheet_id)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                [
                    ("JAGT Landing Page",
                     "josegart-landing.streamlit.app",
                     "jagt2024/Reservar/pagina_web/jagt_landing.py",
                     "active","streamlit","Página web personal",now,1,"daily",""),
                    ("Reservar App",
                     "josegart-reservar.streamlit.app",
                     "jagt2024/Reservar/",
                     "active","streamlit","Sistema de reservas",now,1,"daily",""),
                    ("Panel Hosting",
                     "josegart-hosting.streamlit.app",
                     "jagt2024/Reservar/hosting_panel/app.py",
                     "active","streamlit","Panel de control",now,1,"daily",""),
                ]
            )
            conn.commit()
            print("[OK] 3 apps iniciales registradas")

    finally:
        conn.close()

    print(f"[OK] DB lista: {os.path.abspath(DB_PATH)}")


def register_backup(app_id: int, status: str, size_kb: float,
                    destination: str, notes: str):
    """Registra un evento de backup en la tabla backups."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO backups(app_id,backup_date,status,size_kb,destination,notes)"
            " VALUES(?,?,?,?,?,?)",
            (app_id, datetime.datetime.now().isoformat(),
             status, round(size_kb, 2), destination, notes)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# CREDENCIALES Y CONEXIÓN GOOGLE DRIVE
# ══════════════════════════════════════════════════════════════════════════════

def get_google_credentials() -> Optional[dict]:
    """
    Carga credenciales en este orden:
    1. st.secrets["google"]["GOOGLE_CREDENTIALS"]
    2. .streamlit/secrets.toml  (lectura directa con toml)
    3. Variable de entorno GOOGLE_CREDENTIALS_JSON
    """
    def _parse(raw) -> Optional[dict]:
        creds = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if "private_key" not in creds or "client_email" not in creds:
            return None
        pk = creds["private_key"]
        # Normalizar saltos de línea del private_key
        pk = pk.replace("\\\\n", "\n").replace("\\n", "\n")
        creds["private_key"] = pk
        return creds

    # 1. st.secrets
    try:
        import streamlit as st
        c = _parse(st.secrets["google"]["GOOGLE_CREDENTIALS"])
        if c:
            print("[OK] Credenciales: st.secrets")
            return c
    except Exception:
        pass

    # 2. secrets.toml manual
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, ".streamlit", "secrets.toml"),
        ".streamlit/secrets.toml",
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            import toml
            cfg = toml.load(path)
            raw = cfg.get("google", {}).get("GOOGLE_CREDENTIALS")
            if raw:
                c = _parse(raw)
                if c:
                    print(f"[OK] Credenciales: {path}")
                    return c
        except ImportError:
            try:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib
                with open(path, "rb") as f:
                    cfg = tomllib.load(f)
                raw = cfg.get("google", {}).get("GOOGLE_CREDENTIALS")
                if raw:
                    c = _parse(raw)
                    if c:
                        print(f"[OK] Credenciales: {path} (tomllib)")
                        return c
            except Exception:
                pass
        except Exception:
            continue

    # 3. Variable de entorno
    env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if env:
        try:
            c = _parse(env)
            if c:
                print("[OK] Credenciales: variable de entorno")
                return c
        except Exception as e:
            print(f"[ERROR] Variable de entorno inválida: {e}")

    print("[WARN] No se encontraron credenciales de Google.")
    return None


def build_drive_service(creds_dict: dict):
    """Crea el cliente autenticado de Google Drive API."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        print(f"[ERROR] Autenticación Drive fallida: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# OPERACIONES EN GOOGLE DRIVE
# ══════════════════════════════════════════════════════════════════════════════

def drive_find_file(service, name: str, folder_id: str) -> Optional[str]:
    """Busca un archivo por nombre en la carpeta. Retorna file_id o None."""
    try:
        q = (f"name='{name}' and '{folder_id}' in parents "
             f"and trashed=false")
        res = service.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None
    except Exception:
        return None


def drive_upload(service, data: bytes, name: str,
                 folder_id: str, overwrite: bool = False) -> Optional[str]:
    """
    Sube bytes a Drive como archivo xlsx.
    Si overwrite=True y el archivo existe, lo actualiza.
    Retorna file_id o None si falla.
    """
    from googleapiclient.http import MediaIoBaseUpload
    try:
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=MIME_XLSX,
                                  resumable=False)
        if overwrite:
            existing_id = drive_find_file(service, name, folder_id)
            if existing_id:
                service.files().update(
                    fileId=existing_id, media_body=media
                ).execute()
                return existing_id

        meta = {"name": name, "parents": [folder_id]}
        created = service.files().create(
            body=meta, media_body=media, fields="id"
        ).execute()
        return created["id"]
    except Exception as e:
        print(f"    [ERROR] drive_upload '{name}': {e}")
        return None


def drive_export_sheet(service, sheet_id: str) -> Optional[bytes]:
    """Exporta un Google Sheet como bytes xlsx. Retorna None si falla."""
    from googleapiclient.http import MediaIoBaseDownload
    try:
        request = service.files().export_media(
            fileId=sheet_id, mimeType=MIME_XLSX
        )
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()
    except Exception as e:
        print(f"    [ERROR] export_sheet '{sheet_id}': {e}")
        return None


def drive_download_file(service, file_id: str) -> Optional[bytes]:
    """Descarga un archivo de Drive por file_id. Retorna bytes o None."""
    from googleapiclient.http import MediaIoBaseDownload
    try:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()
    except Exception as e:
        print(f"    [ERROR] drive_download '{file_id}': {e}")
        return None


def drive_list_xlsx(service, folder_id: str) -> list:
    """Lista todos los .xlsx en la carpeta. Retorna lista de dicts."""
    try:
        q = (f"'{folder_id}' in parents "
             f"and mimeType='{MIME_XLSX}' "
             f"and trashed=false")
        res = service.files().list(
            q=q,
            fields="files(id,name,size,modifiedTime)",
            orderBy="name",
            pageSize=200
        ).execute()
        return res.get("files", [])
    except Exception as e:
        print(f"[ERROR] drive_list_xlsx: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# GENERAR EXCEL DE ESTRUCTURA
# ══════════════════════════════════════════════════════════════════════════════

def create_structure_xlsx() -> Optional[str]:
    """Genera hosting-jagt.xlsx con todas las tablas de la DB."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[WARN] openpyxl no instalado — omitiendo Excel de estructura")
        return None

    wb = openpyxl.Workbook()
    H_FILL = PatternFill("solid", start_color="0057FF")
    H_FONT = Font(bold=True, color="FFFFFF", size=11)
    T_FONT = Font(bold=True, color="00D4FF", size=14)
    M_FONT = Font(name="Courier New", size=10, color="333333")

    def hrow(ws, cols):
        for c, v in enumerate(cols, 1):
            cell = ws.cell(row=1, column=c, value=v)
            cell.fill = H_FILL
            cell.font = H_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def widths(ws, ws_list):
        for i, w in enumerate(ws_list, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # Hoja 1: Resumen
    ws1 = wb.active
    ws1.title = "Resumen"
    ws1.sheet_view.showGridLines = False
    ws1["A1"] = "JAGT HOSTING PANEL"
    ws1["A1"].font = T_FONT
    ws1["A1"].fill = PatternFill("solid", start_color="0A0E1A")
    ws1.merge_cells("A1:B1")
    ws1.row_dimensions[1].height = 36
    ws1.column_dimensions["A"].width = 28
    ws1.column_dimensions["B"].width = 50
    for i, (k, v) in enumerate([
        ("Dominio",        "josegart"),
        ("Email Admin",    "josegarjagt@gmail.com"),
        ("Repositorio",    "github.com/jagt2024/Reservar/"),
        ("Plataforma",     "Streamlit Cloud (24/7)"),
        ("Carpeta Drive",  "JAGT-Hosting"),
        ("Folder ID",      DRIVE_FOLDER),
        ("Excel Hosting",  XLSX_NAME),
        ("DB Local",       "hosting_jagt.db"),
        ("Último Backup",  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ], 2):
        ws1[f"A{i}"] = k
        ws1[f"A{i}"].font = Font(bold=True, color="555555")
        ws1[f"B{i}"] = v
        ws1[f"B{i}"].font = M_FONT

    conn = get_db()
    try:
        # Hoja 2: Apps
        ws2 = wb.create_sheet("Aplicaciones")
        ws2.sheet_view.showGridLines = False
        hrow(ws2, ["ID","Nombre","Dominio","Repo","Estado","Tech",
                   "Backup","Frec","Sheet ID","Descripción","Creada"])
        widths(ws2, [5,22,32,40,10,12,8,10,35,30,12])
        for r, row in enumerate(conn.execute(
            "SELECT id,name,domain,repo_path,status,tech,"
            "backup_enabled,backup_freq,sheet_id,description,created_at"
            " FROM apps"
        ).fetchall(), 2):
            row = list(row)
            row[6] = "Si" if row[6] else "No"
            row[10] = (row[10] or "")[:10]
            for c, val in enumerate(row, 1):
                ws2.cell(row=r, column=c, value=val)
            fc = "10B981" if row[4] == "active" else "EF4444"
            ws2.cell(row=r, column=5).font = Font(color=fc, bold=True)
            # Marcar en verde si tiene Sheet ID
            if row[8]:
                ws2.cell(row=r, column=9).font = Font(color="10B981")

        # Hoja 3: Backups
        ws3 = wb.create_sheet("Backups")
        ws3.sheet_view.showGridLines = False
        hrow(ws3, ["ID","App ID","App Nombre","Fecha","Estado","KB","Destino","Notas"])
        widths(ws3, [5,8,22,22,10,10,40,50])
        for r, row in enumerate(conn.execute("""
            SELECT b.id,b.app_id,COALESCE(a.name,'—'),b.backup_date,
                   b.status,b.size_kb,b.destination,b.notes
            FROM backups b LEFT JOIN apps a ON b.app_id=a.id
            ORDER BY b.backup_date DESC LIMIT 500
        """).fetchall(), 2):
            for c, val in enumerate(row, 1):
                ws3.cell(row=r, column=c, value=val)
            fc = "10B981" if row[4] == "success" else "EF4444"
            ws3.cell(row=r, column=5).font = Font(color=fc, bold=True)

        # Hoja 4: Spam Rules
        ws4 = wb.create_sheet("Spam_Rules")
        ws4.sheet_view.showGridLines = False
        hrow(ws4, ["ID","Tipo","Valor","Acción","Activa","Creada"])
        widths(ws4, [5,15,35,12,10,20])
        for r, row in enumerate(conn.execute(
            "SELECT id,rule_type,value,action,active,created_at FROM spam_rules"
        ).fetchall(), 2):
            row = list(row)
            row[4] = "Si" if row[4] else "No"
            row[5] = (row[5] or "")[:10]
            for c, val in enumerate(row, 1):
                ws4.cell(row=r, column=c, value=val)

        # Hoja 5: Usuarios
        ws5 = wb.create_sheet("Usuarios")
        ws5.sheet_view.showGridLines = False
        hrow(ws5, ["ID","Usuario","Rol","Email","Creado","Último Acceso"])
        widths(ws5, [5,18,12,38,20,20])
        for r, row in enumerate(conn.execute(
            "SELECT id,username,role,email,created_at,last_login FROM users"
        ).fetchall(), 2):
            row = list(row)
            row[4] = (row[4] or "")[:10]
            row[5] = (row[5] or "—")[:10]
            for c, val in enumerate(row, 1):
                ws5.cell(row=r, column=c, value=val)

    finally:
        conn.close()

    wb.save(XLSX_NAME)
    size_kb = os.path.getsize(XLSX_NAME) / 1024
    print(f"[OK] Excel generado: {XLSX_NAME}  ({size_kb:.1f} KB)")
    return XLSX_NAME


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run_all_backups(dry_run: bool = False):
    sep      = "=" * 60
    now_str  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    now_disp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{sep}")
    print(f"  JAGT Hosting — Backup Completo")
    print(f"  {now_disp}{' [DRY-RUN]' if dry_run else ''}")
    print(f"  Drive: JAGT-Hosting ({DRIVE_FOLDER})")
    print(f"{sep}")

    # ── PASO 0: DB ────────────────────────────────────────────────────────────
    sep2 = "─" * 44
    print(f"\n{sep2}\n  PASO 0 · Base de datos\n{sep2}")
    init_db()

    # Leer apps con backup habilitado
    conn = get_db()
    try:
        apps_db = conn.execute(
            "SELECT id, name, sheet_id FROM apps WHERE backup_enabled=1"
        ).fetchall()
    finally:
        conn.close()

    apps_with_sheet    = [(i, n, s.strip()) for i, n, s in apps_db
                          if s and s.strip()]
    apps_without_sheet = [(i, n) for i, n, s in apps_db
                          if not s or not s.strip()]

    print(f"[OK] {len(apps_db)} app(s) con backup habilitado")
    print(f"     Con Sheet ID   : {len(apps_with_sheet)}")
    print(f"     Sin Sheet ID   : {len(apps_without_sheet)}")
    if apps_without_sheet:
        for _, n in apps_without_sheet:
            print(f"       ⚠️  {n}  ← sin Sheet ID")

    # ── PASO 1: Generar Excel de estructura ───────────────────────────────────
    print(f"\n{sep2}\n  PASO 1 · Generar {XLSX_NAME}\n{sep2}")
    xlsx_path = create_structure_xlsx()
    if not xlsx_path:
        print("[ERROR] No se pudo generar el Excel. Continuando sin él.")

    # ── PASO 2: Conectar a Drive ──────────────────────────────────────────────
    print(f"\n{sep2}\n  PASO 2 · Conectar a Google Drive\n{sep2}")
    creds   = get_google_credentials()
    service = build_drive_service(creds) if creds else None

    if not service:
        print("[WARN] Sin conexión a Drive.")
        print("       Los registros de backup se guardarán solo en la DB local.")
        drive_ok = False
    else:
        print("[OK] Conexión a Google Drive establecida")
        drive_ok = True

    results = []   # lista de (nombre_archivo, estado, app_nombre)

    # ── PASO 3: Subir hosting-jagt.xlsx ───────────────────────────────────────
    print(f"\n{sep2}\n  PASO 3 · Subir {XLSX_NAME}\n{sep2}")
    if not drive_ok or not xlsx_path:
        print("[SKIP] Sin Drive o sin Excel — omitido")
    elif dry_run:
        print(f"[DRY] Omitiría subir: {XLSX_NAME}")
    else:
        with open(xlsx_path, "rb") as f:
            data = f.read()
        fid = drive_upload(service, data, XLSX_NAME, DRIVE_FOLDER,
                           overwrite=True)
        if fid:
            print(f"[OK] {XLSX_NAME} subido/actualizado en Drive (ID: {fid})")
            # Registrar para cada app
            for app_id, app_name, _ in apps_db:
                register_backup(
                    app_id, "success",
                    os.path.getsize(xlsx_path) / 1024,
                    f"Google Drive/JAGT-Hosting/{XLSX_NAME}",
                    f"Estructura hosting exportada — {app_name}"
                )
        else:
            print(f"[ERROR] No se pudo subir {XLSX_NAME}")

    # ── PASO 4 + 5: Exportar Google Sheets de cada app ────────────────────────
    print(f"\n{sep2}\n  PASO 4·5 · Exportar Google Sheets de cada app\n{sep2}")

    if not drive_ok:
        print("[SKIP] Sin conexión a Drive")
    elif not apps_with_sheet:
        print("[WARN] Ninguna app tiene Sheet ID configurado.")
        print("       Ve a: Panel → Aplicaciones → (expandir app) → campo Sheet ID")
    else:
        for app_id, app_name, sheet_id in apps_with_sheet:
            # Normalizar: aceptar URL completa o solo el ID
            sid = sheet_id
            if "spreadsheets/d/" in sid:
                sid = sid.split("spreadsheets/d/")[1].split("/")[0]
            sid = sid.split("?")[0].strip()  # quitar parámetros si los hay

            safe_name    = app_name.replace(" ", "_").replace("/", "-")
            current_file = f"{safe_name}.xlsx"
            backup_file  = f"{safe_name}_backup_{now_str}.xlsx"

            print(f"\n  App: {app_name}")
            print(f"    Sheet ID      : {sid}")
            print(f"    Archivo actual: {current_file}")
            print(f"    Copia backup  : {backup_file}")

            if dry_run:
                print(f"    [DRY] Omitiría exportar y subir")
                results.append((current_file, "dry_run", app_name))
                continue

            # Exportar el Sheet como xlsx
            print(f"    [→] Exportando desde Google Sheets...")
            data = drive_export_sheet(service, sid)

            if not data:
                print(f"    [ERROR] No se pudo exportar el Sheet")
                print(f"            Verifica que el Sheet ID sea correcto: {sid}")
                print(f"            Y que la cuenta de servicio tenga acceso al Sheet")
                register_backup(
                    app_id, "error", 0,
                    f"Google Drive/JAGT-Hosting/{backup_file}",
                    f"ERROR exportando Sheet {sid} — verifica permisos"
                )
                results.append((current_file, "error", app_name))
                continue

            size_kb = len(data) / 1024
            print(f"    [OK] Exportado: {size_kb:.1f} KB")

            # Subir versión actual (sobreescribir si existe)
            print(f"    [→] Subiendo versión actual: {current_file}")
            fid_current = drive_upload(service, data, current_file,
                                       DRIVE_FOLDER, overwrite=True)
            if fid_current:
                print(f"    [OK] {current_file} en Drive (ID: {fid_current})")
                register_backup(
                    app_id, "success", size_kb,
                    f"Google Drive/JAGT-Hosting/{current_file}",
                    f"Versión actual exportada desde Google Sheet ({sid})"
                )
            else:
                print(f"    [ERROR] No se pudo subir {current_file}")

            # Subir copia de backup (siempre nueva)
            print(f"    [→] Subiendo copia de respaldo: {backup_file}")
            fid_backup = drive_upload(service, data, backup_file,
                                      DRIVE_FOLDER, overwrite=False)
            if fid_backup:
                print(f"    [OK] {backup_file} en Drive (ID: {fid_backup})")
                register_backup(
                    app_id, "success", size_kb,
                    f"Google Drive/JAGT-Hosting/{backup_file}",
                    f"Copia histórica — backup {now_str}"
                )
            else:
                print(f"    [ERROR] No se pudo subir {backup_file}")

            status = "ok" if (fid_current or fid_backup) else "error"
            results.append((current_file, status, app_name))

    # ── PASO 6: Backup de .xlsx ya existentes en Drive (subidos manualmente) ──
    print(f"\n{sep2}\n  PASO 6 · Backup de .xlsx existentes en Drive\n{sep2}")

    if not drive_ok:
        print("[SKIP] Sin conexión a Drive")
    else:
        existing_files = drive_list_xlsx(service, DRIVE_FOLDER)
        # Nombres que ya fueron generados en PASO 5 (no re-procesar)
        generated = {
            f"{n.replace(' ','_').replace('/','_')}.xlsx"
            for _, n, _ in apps_with_sheet
        }
        generated.add(XLSX_NAME)

        to_backup = [
            f for f in existing_files
            if "_backup_" not in f["name"]
            and f["name"] not in generated
        ]

        if not to_backup:
            print("[OK] No hay archivos manuales adicionales para respaldar")
        else:
            print(f"[OK] {len(to_backup)} archivo(s) manual(es) encontrado(s):")
            # Mapa app_name normalizado → (id, name)
            apps_map = {
                n.lower().replace(" ", ""): (i, n)
                for i, n, _ in apps_db
            }
            for f in to_backup:
                fid   = f["id"]
                fname = f["name"]
                bname = fname.replace(".xlsx", f"_backup_{now_str}.xlsx")
                size_kb = int(f.get("size", 0)) / 1024

                print(f"\n  Archivo: {fname}  ({size_kb:.1f} KB)")
                print(f"    [→] Creando copia: {bname}")

                # Asociar con app por nombre
                app_id, app_name = 0, "General"
                fn = fname.lower().replace(" ","").replace(".xlsx","")
                for key, (aid, aname) in apps_map.items():
                    if key in fn or fn in key:
                        app_id, app_name = aid, aname
                        break

                if dry_run:
                    print(f"    [DRY] Omitiría backup de {fname}")
                    results.append((fname, "dry_run", app_name))
                    continue

                data = drive_download_file(service, fid)
                if not data:
                    print(f"    [ERROR] No se pudo descargar {fname}")
                    results.append((fname, "error", app_name))
                    continue

                fid_b = drive_upload(service, data, bname,
                                     DRIVE_FOLDER, overwrite=False)
                if fid_b:
                    print(f"    [OK] {bname} creado en Drive")
                    register_backup(
                        app_id, "success", len(data)/1024,
                        f"Google Drive/JAGT-Hosting/{bname}",
                        f"Backup de archivo manual: {fname}"
                    )
                    results.append((fname, "ok", app_name))
                else:
                    print(f"    [ERROR] No se pudo crear la copia")
                    results.append((fname, "error", app_name))

    # ── Resumen final ─────────────────────────────────────────────────────────
    ok_count  = sum(1 for _, s, _ in results if s == "ok")
    err_count = sum(1 for _, s, _ in results if s == "error")
    dry_count = sum(1 for _, s, _ in results if s == "dry_run")

    print(f"\n{sep}")
    print(f"  RESUMEN — {now_disp}")
    print(f"{sep}")
    print(f"  Apps con backup habilitado : {len(apps_db)}")
    print(f"  Apps con Sheet ID          : {len(apps_with_sheet)}")
    print(f"  Operaciones exitosas       : {ok_count}")
    if err_count:
        print(f"  Errores                    : {err_count}")
    if dry_count:
        print(f"  Omitidos (dry-run)         : {dry_count}")
    print(f"  URL Drive                  : "
          f"https://drive.google.com/drive/folders/{DRIVE_FOLDER}")
    print(f"{sep}")

    if results:
        print("\n  Detalle:")
        for fname, status, aname in results:
            icon = {"ok": "✅", "error": "❌", "dry_run": "🔵"}.get(status, "❓")
            print(f"    {icon}  {fname:<45} → {aname}")
    print()


if __name__ == "__main__":
    run_all_backups(dry_run="--dry-run" in sys.argv)
