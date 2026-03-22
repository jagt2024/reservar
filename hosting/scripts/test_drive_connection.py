"""
test_drive_connection.py
Diagnostica y repara el private_key paso a paso, luego prueba la conexion a Drive.
Ejecutar: python test_drive_connection.py
"""
import os
import json
import sys

print("=" * 60)
print("  TEST CONEXIÓN GOOGLE DRIVE — JAGT Hosting")
print("=" * 60)

# ── 1. Cargar credenciales desde secrets.toml ─────────────────────────────────
def load_creds():
    candidates = [
        ".streamlit/secrets.toml",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".streamlit", "secrets.toml"),
    ]
    toml_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not toml_path:
        print("❌ No se encontró secrets.toml")
        sys.exit(1)

    import toml
    config = toml.load(toml_path)
    raw = config.get("google", {}).get("GOOGLE_CREDENTIALS")
    if not raw:
        print("❌ No se encontró GOOGLE_CREDENTIALS en [google]")
        sys.exit(1)

    return json.loads(raw) if isinstance(raw, str) else dict(raw)

creds_dict = load_creds()
print(f"\n✅ Credenciales cargadas")
print(f"   client_email : {creds_dict.get('client_email')}")
print(f"   project_id   : {creds_dict.get('project_id')}")

# ── 2. Inspeccionar el private_key tal como está ──────────────────────────────
pk = creds_dict.get("private_key", "")
print(f"\n🔍 Inspeccionando private_key...")
print(f"   Longitud total   : {len(pk)} chars")
print(f"   Primeros 80 chars (repr): {repr(pk[:80])}")
print(f"   Últimos  40 chars (repr): {repr(pk[-40:])}")
double_escape = "\\n"
real_newline  = chr(10)
print(f"   Contiene \\\\n (doble escape) : {double_escape in pk}")
print(f"   Contiene salto real (\\n)    : {real_newline in pk}")

# ── 3. Reparar el private_key probando todas las variantes ────────────────────
print(f"\n🔧 Reparando private_key...")

def try_fix(pk_input):
    """Intenta todas las formas conocidas de reparar el private_key."""
    attempts = []

    # A: ya tiene saltos reales → usar tal cual
    attempts.append(("Sin cambios", pk_input))

    # B: \\n (doble barra) → \n (salto real)
    attempts.append(("replace \\\\n → \\n", pk_input.replace("\\n", "\n")))

    # C: \\\\n (cuádruple) → \n
    attempts.append(("replace \\\\\\\\n → \\n", pk_input.replace("\\\\n", "\n")))

    # D: decodificar unicode_escape
    try:
        decoded = pk_input.encode("utf-8").decode("unicode_escape")
        attempts.append(("unicode_escape decode", decoded))
    except Exception:
        pass

    # E: raw_unicode_escape
    try:
        decoded2 = pk_input.encode("raw_unicode_escape").decode("utf-8")
        attempts.append(("raw_unicode_escape", decoded2))
    except Exception:
        pass

    return attempts

attempts = try_fix(pk)

fixed_pk = None
for name, candidate in attempts:
    has_real_newlines = "\n" in candidate
    starts_ok = "-----BEGIN" in candidate
    ends_ok   = "-----END" in candidate
    print(f"   [{name}]")
    print(f"      saltos reales: {has_real_newlines} | BEGIN: {starts_ok} | END: {ends_ok}")
    print(f"      repr inicio: {repr(candidate[:60])}")
    if has_real_newlines and starts_ok and ends_ok and fixed_pk is None:
        fixed_pk = candidate
        print(f"      ★ USANDO ESTA VARIANTE")

if not fixed_pk:
    print("\n❌ No se pudo reparar el private_key automáticamente.")
    print("   Genera uno nuevo desde Google Cloud Console:")
    print("   IAM → Cuentas de servicio → Claves → Agregar clave → JSON")
    sys.exit(1)

# ── 4. Probar autenticación con Google ────────────────────────────────────────
print(f"\n🔐 Probando autenticación con Google Drive...")
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    test_creds = dict(creds_dict)
    test_creds["private_key"] = fixed_pk

    credentials = service_account.Credentials.from_service_account_info(
        test_creds,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    # Listar archivos en la carpeta JAGT-Hosting
    folder_id = "1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn"
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name)",
        pageSize=10
    ).execute()

    files = results.get("files", [])
    print(f"   ✅ Conexión exitosa a Google Drive")
    print(f"   📁 Archivos en JAGT-Hosting ({len(files)}):")
    for f in files:
        print(f"      - {f['name']} ({f['id']})")
    if not files:
        print(f"      (carpeta vacía)")

except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# ── 5. Actualizar secrets.toml con el private_key reparado ───────────────────
print(f"\n💾 Actualizando secrets.toml con private_key reparado...")

candidates = [
    ".streamlit/secrets.toml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".streamlit", "secrets.toml"),
]
toml_path = next((p for p in candidates if os.path.isfile(p)), None)

import toml
config = toml.load(toml_path)

# Reconstruir el dict con la clave reparada
final_creds = dict(creds_dict)
final_creds["private_key"] = fixed_pk

# Serializar con json.dumps que escapa \n → \\n correctamente para TOML
config["google"]["GOOGLE_CREDENTIALS"] = json.dumps(final_creds, ensure_ascii=False)

# Backup
with open(toml_path, "r", encoding="utf-8") as f:
    original = f.read()
with open(toml_path + ".bak2", "w", encoding="utf-8") as f:
    f.write(original)

with open(toml_path, "w", encoding="utf-8") as f:
    toml.dump(config, f)

print(f"   ✅ secrets.toml actualizado")
print(f"   💾 Backup guardado: {toml_path}.bak2")

print(f"""
{'=' * 60}
  ✅ TODO LISTO
{'=' * 60}
  Ahora ejecuta:
    python backup_runner.py
  El archivo se subirá a:
    https://drive.google.com/drive/folders/1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn
{'=' * 60}
""")
