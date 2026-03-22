"""
reparar_credentials.py
Corrige los saltos de linea reales dentro del private_key en secrets.toml
Ejecutar: python reparar_credentials.py
"""
import os
import re
import json

# ── Buscar secrets.toml ───────────────────────────────────────────────────────
candidates = [
    ".streamlit/secrets.toml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"),
]
toml_path = next((p for p in candidates if os.path.isfile(p)), None)

if not toml_path:
    print("❌ No se encontró .streamlit/secrets.toml")
    exit(1)

print(f"✅ Archivo: {os.path.abspath(toml_path)}")

# ── Leer contenido raw ────────────────────────────────────────────────────────
with open(toml_path, "r", encoding="utf-8") as f:
    content = f.read()

# ── Extraer el valor de GOOGLE_CREDENTIALS como texto plano ──────────────────
# Busca: GOOGLE_CREDENTIALS = '...' o "..." (puede tener saltos reales adentro)
match = re.search(
    r'GOOGLE_CREDENTIALS\s*=\s*([\'"])(.*?)\1',
    content,
    flags=re.DOTALL
)

if not match:
    print("❌ No se encontró GOOGLE_CREDENTIALS en el archivo")
    exit(1)

raw_value = match.group(2)
print(f"📄 Valor extraído ({len(raw_value)} chars)")

# ── Reparar: eliminar saltos de línea REALES que estén dentro del private_key─
# El private_key es la única parte que puede tener \n reales
# Reemplazamos \n reales por el texto literal \n (dos caracteres: \ y n)
fixed_value = raw_value.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")

# ── Verificar que ahora sea JSON válido ───────────────────────────────────────
try:
    creds = json.loads(fixed_value)
    print(f"✅ JSON válido después de la corrección")
    print(f"   client_email : {creds.get('client_email', 'NO ENCONTRADO')}")
    print(f"   project_id   : {creds.get('project_id', 'NO ENCONTRADO')}")
    print(f"   type         : {creds.get('type', 'NO ENCONTRADO')}")
except json.JSONDecodeError as e:
    print(f"❌ Aún inválido: {e}")
    print("\n💡 El JSON tiene otro problema además de los saltos de línea.")
    print("   Abre tu archivo .json original de Google Cloud y ejecuta:")
    print("   python convertir_json.py  (ver instrucciones abajo)")
    exit(1)

# ── Guardar backup y reescribir el archivo ────────────────────────────────────
backup = toml_path + ".bak"
with open(backup, "w", encoding="utf-8") as f:
    f.write(content)
print(f"\n💾 Backup guardado: {backup}")

# Reemplazar en el contenido original
new_content = content.replace(match.group(0),
    f"GOOGLE_CREDENTIALS = '{fixed_value}'")

with open(toml_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"✅ secrets.toml reparado correctamente")
print(f"\n🚀 Ahora ejecuta:")
print(f"   python diagnostico_secrets.py   ← debe mostrar todos ✅")
print(f"   python backup_runner.py          ← debe subir a Drive")
