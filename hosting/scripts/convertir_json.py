"""
convertir_json.py
Lee el archivo .json original descargado de Google Cloud Console
y escribe el secrets.toml correctamente, sin problemas de saltos de linea.

USO:
  1. Pon este script en la misma carpeta que tu archivo .json de Google
  2. Ejecuta: python convertir_json.py
  3. Te preguntara el nombre del archivo .json si hay varios
"""

import os
import json
import glob

print("=" * 60)
print("  CONVERTIR JSON DE GOOGLE → secrets.toml")
print("=" * 60)

# ── 1. Buscar archivos .json en la carpeta actual ─────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
json_files  = glob.glob(os.path.join(current_dir, "*.json"))

# Filtrar solo los que parecen credenciales de Google (tienen "type" y "private_key")
cred_files = []
for jf in json_files:
    try:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "private_key" in data and "client_email" in data:
            cred_files.append((jf, data))
    except Exception:
        pass

if not cred_files:
    print("\n❌ No se encontró ningún archivo .json de credenciales en esta carpeta.")
    print(f"   Carpeta buscada: {current_dir}")
    print("\n💡 Solución:")
    print("   1. Descarga el JSON desde Google Cloud Console:")
    print("      IAM → Cuentas de servicio → tu cuenta → Claves → Agregar clave → JSON")
    print("   2. Copia el archivo .json a esta carpeta:")
    print(f"      {current_dir}")
    print("   3. Vuelve a ejecutar este script")
    exit(1)

# ── 2. Seleccionar el archivo si hay varios ───────────────────────────────────
if len(cred_files) == 1:
    json_path, creds = cred_files[0]
    print(f"\n✅ Archivo encontrado: {os.path.basename(json_path)}")
else:
    print(f"\n📋 Se encontraron {len(cred_files)} archivos de credenciales:")
    for i, (jf, _) in enumerate(cred_files, 1):
        print(f"   {i}. {os.path.basename(jf)}")
    while True:
        try:
            choice = int(input("\nElige el número del archivo a usar: ")) - 1
            if 0 <= choice < len(cred_files):
                json_path, creds = cred_files[choice]
                break
            print("   Número inválido, intenta de nuevo")
        except ValueError:
            print("   Ingresa solo el número")

print(f"\n📄 Credenciales cargadas:")
print(f"   type         : {creds.get('type')}")
print(f"   project_id   : {creds.get('project_id')}")
print(f"   client_email : {creds.get('client_email')}")
print(f"   private_key  : {'✅ presente' if creds.get('private_key') else '❌ falta'}")

# ── 3. Serializar el JSON en una sola línea (sin saltos reales) ───────────────
# json.dumps garantiza que los \n del private_key queden como \\n (escapados)
json_one_line = json.dumps(creds, ensure_ascii=False)

# Verificar que se puede parsear de vuelta
try:
    test = json.loads(json_one_line)
    assert "private_key" in test
    print(f"\n✅ JSON serializado correctamente ({len(json_one_line)} chars)")
except Exception as e:
    print(f"\n❌ Error al serializar: {e}")
    exit(1)

# ── 4. Leer el secrets.toml actual si existe ──────────────────────────────────
toml_candidates = [
    os.path.join(current_dir, ".streamlit", "secrets.toml"),
    ".streamlit/secrets.toml",
]
toml_path = next((p for p in toml_candidates if os.path.isfile(p)), None)

DRIVE_FOLDER_ID = "1ueiD9ERvgFF9fZ7aMQUBtCuSGW1R4nSn"

if toml_path:
    # Hacer backup del archivo actual
    with open(toml_path, "r", encoding="utf-8") as f:
        old_content = f.read()
    backup_path = toml_path + ".bak"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(old_content)
    print(f"\n💾 Backup del secrets.toml anterior: {backup_path}")

    # Extraer el DRIVE_FOLDER_ID si ya estaba en el archivo
    import re
    match = re.search(r'DRIVE_FOLDER_ID\s*=\s*["\']?([^\s"\']+)["\']?', old_content)
    if match:
        DRIVE_FOLDER_ID = match.group(1)
        print(f"   DRIVE_FOLDER_ID encontrado: {DRIVE_FOLDER_ID}")
else:
    # Crear la carpeta .streamlit si no existe
    streamlit_dir = os.path.join(current_dir, ".streamlit")
    os.makedirs(streamlit_dir, exist_ok=True)
    toml_path = os.path.join(streamlit_dir, "secrets.toml")
    print(f"\n📁 Creando: {toml_path}")

# ── 5. Escribir el secrets.toml nuevo y correcto ──────────────────────────────
# Usamos comillas simples para el JSON para evitar conflictos con las dobles del JSON
# Si el JSON contiene comillas simples (raro pero posible), usamos comillas dobles
quote = "'" if "'" not in json_one_line else '"'

new_toml = f"""# secrets.toml — JAGT Hosting
# Generado automaticamente por convertir_json.py
# NO subir este archivo a GitHub (.gitignore)

[google]
GOOGLE_CREDENTIALS = {quote}{json_one_line}{quote}
DRIVE_FOLDER_ID = "{DRIVE_FOLDER_ID}"
"""

with open(toml_path, "w", encoding="utf-8") as f:
    f.write(new_toml)

print(f"\n✅ secrets.toml generado: {toml_path}")

# ── 6. Verificación final ─────────────────────────────────────────────────────
print("\n🔄 Verificación final...")
try:
    import toml
    config  = toml.load(toml_path)
    raw     = config["google"]["GOOGLE_CREDENTIALS"]
    parsed  = json.loads(raw) if isinstance(raw, str) else dict(raw)
    assert "private_key" in parsed and "client_email" in parsed
    print(f"   ✅ secrets.toml válido y listo")
    print(f"   client_email     : {parsed['client_email']}")
    print(f"   DRIVE_FOLDER_ID  : {config['google']['DRIVE_FOLDER_ID']}")
except ImportError:
    print("   ⚠️  'toml' no instalado para verificar, pero el archivo fue generado")
    print("      Instala con: pip install toml")
except Exception as e:
    print(f"   ❌ Error en verificación: {e}")
    exit(1)

print(f"""
{'=' * 60}
  ✅ LISTO — Próximos pasos:
{'=' * 60}
  1. Verifica:   python diagnostico_secrets.py
  2. Ejecuta:    python backup_runner.py
  3. Revisa tu carpeta Drive:
     https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}
{'=' * 60}
""")
