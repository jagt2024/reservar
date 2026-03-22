"""
fix_secrets.py — Corrige los saltos de linea del private_key en secrets.toml
Ejecutar en la misma carpeta donde esta el secrets.toml (o en scripts/)
  python fix_secrets.py
"""

import os
import json
import re

# ── Buscar secrets.toml ───────────────────────────────────────────────────────
candidates = [
    ".streamlit/secrets.toml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".streamlit", "secrets.toml"),
]

toml_path = None
for p in candidates:
    if os.path.isfile(p):
        toml_path = p
        break

if not toml_path:
    print("❌ No se encontró .streamlit/secrets.toml")
    exit(1)

print(f"✅ Encontrado: {os.path.abspath(toml_path)}")

# ── Leer el contenido raw del archivo ────────────────────────────────────────
with open(toml_path, "r", encoding="utf-8") as f:
    raw_content = f.read()

print(f"\n📄 Contenido original ({len(raw_content)} chars):")
print("-" * 50)
print(raw_content[:300] + "..." if len(raw_content) > 300 else raw_content)
print("-" * 50)

# ── Estrategia: extraer el bloque JSON y repararlo ───────────────────────────
# Buscar todo lo que está entre GOOGLE_CREDENTIALS = y la siguiente clave o EOF
pattern = r'(GOOGLE_CREDENTIALS\s*=\s*)("""|\'\'\')(.*?)("""|\'\'\')|(GOOGLE_CREDENTIALS\s*=\s*)(\{.*?\n\})'

# Método directo: leer línea por línea y reconstruir el JSON
lines = raw_content.splitlines()

in_creds  = False
json_lines = []
before     = []
after      = []
key_line   = ""

i = 0
while i < len(lines):
    line = lines[i]

    # Detectar inicio de GOOGLE_CREDENTIALS
    if re.match(r'\s*GOOGLE_CREDENTIALS\s*=', line):
        key_line = line
        in_creds = True
        # Ver si el JSON empieza en la misma línea
        eq_pos = line.index("=")
        rest = line[eq_pos+1:].strip().strip('"""').strip("'''").strip()
        if rest.startswith("{"):
            json_lines.append(rest)
        i += 1
        continue

    if in_creds:
        stripped = line.strip().strip('"""').strip("'''")
        # Detectar fin del bloque JSON
        if stripped == "}" or line.strip() in ('"""', "'''"):
            if stripped == "}":
                json_lines.append("}")
            in_creds = False
        else:
            json_lines.append(line)
        i += 1
        continue

    if not in_creds and not json_lines:
        before.append(line)
    elif not in_creds and json_lines:
        after.append(line)

    i += 1

print(f"\n🔍 Líneas del JSON extraído: {len(json_lines)}")

# ── Unir y parsear el JSON ────────────────────────────────────────────────────
raw_json = "\n".join(json_lines)
print(f"JSON raw (primeros 200 chars): {raw_json[:200]}")

try:
    creds = json.loads(raw_json)
    print("✅ JSON ya es válido — no necesita corrección")
except json.JSONDecodeError as e:
    print(f"\n⚠️  JSON inválido: {e}")
    print("🔧 Corrigiendo saltos de línea en private_key...")

    # Corregir: reemplazar saltos de línea REALES dentro del valor private_key
    # Técnica: reemplazar \n reales por \\n solo dentro del valor de private_key
    fixed_lines = []
    in_key = False
    key_buffer = []

    for line in json_lines:
        stripped = line.strip()

        if '"private_key"' in line and not in_key:
            if line.count('"') >= 4:
                # Todo en una línea → ya está bien
                fixed_lines.append(line)
            else:
                # El valor continúa en las siguientes líneas
                in_key = True
                key_buffer = [line]
            continue

        if in_key:
            key_buffer.append(line)
            # El valor termina cuando cierra la comilla
            joined = " ".join(key_buffer)
            # Contar comillas para saber si cerró
            content_after_colon = joined.split(':', 1)[-1].strip()
            if content_after_colon.startswith('"'):
                inner = content_after_colon[1:]
                # Buscar la comilla de cierre (no escapada)
                close = re.search(r'(?<!\\)"', inner)
                if close:
                    in_key = False
                    # Reconstruir: unir líneas del buffer con \n escapado
                    full_val = "\n".join(key_buffer)
                    # Extraer el valor entre las comillas externas
                    match = re.search(r'"private_key"\s*:\s*"(.*)"', full_val, re.DOTALL)
                    if match:
                        key_val = match.group(1)
                        # Reemplazar saltos reales por \n escapado
                        key_val_fixed = key_val.replace("\n", "\\n")
                        fixed_lines.append(f'  "private_key": "{key_val_fixed}"')
                    else:
                        fixed_lines.extend(key_buffer)
                    key_buffer = []
            continue

        fixed_lines.append(line)

    raw_json_fixed = "\n".join(fixed_lines)

    try:
        creds = json.loads(raw_json_fixed)
        print("✅ JSON corregido exitosamente")
    except json.JSONDecodeError as e2:
        print(f"❌ No se pudo corregir automáticamente: {e2}")
        print("\n💡 SOLUCIÓN MANUAL:")
        print("   1. Abre el JSON descargado de Google Cloud")
        print("   2. En Python, ejecuta:")
        print("      import json")
        print("      with open('tu_archivo.json') as f:")
        print("          data = json.load(f)")
        print("      print(json.dumps(data))  # esto genera el JSON en UNA sola línea")
        print("   3. Pega ese resultado en secrets.toml así:")
        print("      GOOGLE_CREDENTIALS = '<pega aquí el JSON en una línea>'")
        exit(1)

# ── Serializar el JSON en UNA SOLA LÍNEA (sin saltos reales) ─────────────────
json_one_line = json.dumps(creds, ensure_ascii=False)
print(f"\n✅ JSON serializado en 1 línea ({len(json_one_line)} chars)")
print(f"   client_email : {creds.get('client_email')}")
print(f"   project_id   : {creds.get('project_id')}")

# ── Reescribir el secrets.toml con el JSON corregido ─────────────────────────
# Leer todo el archivo y reemplazar solo el bloque de GOOGLE_CREDENTIALS
with open(toml_path, "r", encoding="utf-8") as f:
    full = f.read()

# Reemplazar el bloque completo de GOOGLE_CREDENTIALS con la versión de 1 línea
# Patrón: desde GOOGLE_CREDENTIALS = hasta el cierre del bloque (} o ''')
new_entry = f'GOOGLE_CREDENTIALS = \'{json_one_line}\''

# Eliminar el bloque antiguo (multilinea o no)
cleaned = re.sub(
    r'GOOGLE_CREDENTIALS\s*=\s*("""|\'\'\').*?("""|\'\'\')|(GOOGLE_CREDENTIALS\s*=\s*\{[^}]*\})',
    '__PLACEHOLDER__',
    full,
    flags=re.DOTALL
)

# Si no encontró con triple quote, buscar el bloque sin comillas
if '__PLACEHOLDER__' not in cleaned:
    # Reemplazar desde la clave hasta la línea que tiene solo "}"
    cleaned = re.sub(
        r'GOOGLE_CREDENTIALS\s*=\s*[\{"].*',
        '__PLACEHOLDER__',
        full,
        flags=re.DOTALL
    )
    # Recortar solo hasta la primera línea que no sea parte del JSON
    # Método más seguro: reconstruir manualmente
    new_lines = []
    skip = False
    brace_count = 0
    for line in full.splitlines():
        if re.match(r'\s*GOOGLE_CREDENTIALS\s*=', line):
            skip = True
            brace_count = line.count('{') - line.count('}')
            new_lines.append(new_entry)
            continue
        if skip:
            brace_count += line.count('{') - line.count('}')
            if brace_count <= 0:
                skip = False
            continue
        new_lines.append(line)
    new_content = "\n".join(new_lines)
else:
    new_content = cleaned.replace('__PLACEHOLDER__', new_entry)

# ── Guardar backup + archivo nuevo ───────────────────────────────────────────
backup_path = toml_path + ".backup"
with open(backup_path, "w", encoding="utf-8") as f:
    f.write(full)
print(f"\n💾 Backup guardado en: {backup_path}")

with open(toml_path, "w", encoding="utf-8") as f:
    f.write(new_content)
print(f"✅ secrets.toml actualizado correctamente")

# ── Verificación final ────────────────────────────────────────────────────────
print("\n🔄 Verificación final...")
import toml
config_verify = toml.load(toml_path)
raw_verify = config_verify.get("google", {}).get("GOOGLE_CREDENTIALS")
try:
    creds_verify = json.loads(raw_verify) if isinstance(raw_verify, str) else dict(raw_verify)
    print(f"   ✅ JSON válido — listo para usar")
    print(f"   client_email : {creds_verify.get('client_email')}")
    print(f"\n🚀 Ahora ejecuta: python backup_runner.py")
except Exception as e:
    print(f"   ❌ Aún hay problema: {e}")
