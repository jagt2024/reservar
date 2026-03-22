"""
diagnostico_secrets.py — Diagnóstico de credenciales Google
Ejecutar en la misma carpeta que backup_runner.py:
  python diagnostico_secrets.py
"""

import os
import json

print("=" * 60)
print("  DIAGNÓSTICO DE CREDENCIALES — JAGT Hosting")
print("=" * 60)

# ── 1. Ubicación actual ───────────────────────────────────────────────────────
print(f"\n📁 Carpeta actual         : {os.getcwd()}")
print(f"📄 Este script está en    : {os.path.abspath(__file__)}")

# ── 2. Buscar el archivo secrets.toml en todas las rutas posibles ─────────────
print("\n🔍 Buscando secrets.toml...")
toml_candidates = [
    ".streamlit/secrets.toml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"),
    os.path.expanduser("~/.streamlit/secrets.toml"),
]

found_toml = None
for path in toml_candidates:
    exists = os.path.isfile(path)
    print(f"   {'✅' if exists else '❌'} {os.path.abspath(path)}")
    if exists and not found_toml:
        found_toml = path

if not found_toml:
    print("\n⛔ No se encontró ningún secrets.toml.")
    print("   Crea el archivo en: .streamlit/secrets.toml")
    exit(1)

print(f"\n✅ Usando: {os.path.abspath(found_toml)}")

# ── 3. Leer el archivo con distintas librerías ────────────────────────────────
print("\n📖 Leyendo el archivo...")
config = None

# Intentar con toml
try:
    import toml
    config = toml.load(found_toml)
    print("   Leído con: toml")
except ImportError:
    print("   ⚠️  'toml' no instalado")
except Exception as e:
    print(f"   ❌ Error leyendo con toml: {e}")

# Intentar con tomllib / tomli si toml falló
if config is None:
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(found_toml, "rb") as f:
            config = tomllib.load(f)
        print("   Leído con: tomllib/tomli")
    except ImportError:
        print("   ⚠️  tomllib/tomli tampoco disponible")
    except Exception as e:
        print(f"   ❌ Error leyendo con tomllib: {e}")

if config is None:
    print("\n⛔ No se pudo leer el archivo. Instala toml:")
    print("   pip install toml")
    exit(1)

# ── 4. Mostrar secciones presentes ───────────────────────────────────────────
print(f"\n📋 Secciones encontradas en secrets.toml:")
for key in config.keys():
    print(f"   [{key}]")
    if isinstance(config[key], dict):
        for subkey in config[key].keys():
            val = config[key][subkey]
            preview = str(val)[:60] + "..." if len(str(val)) > 60 else str(val)
            print(f"      {subkey} = {preview}")

# ── 5. Verificar sección [google] ─────────────────────────────────────────────
print("\n🔑 Verificando sección [google]...")
google_section = config.get("google")
if not google_section:
    print("   ❌ No existe la sección [google]")
    print(f"   Las secciones disponibles son: {list(config.keys())}")
    exit(1)
else:
    print(f"   ✅ Sección [google] encontrada con claves: {list(google_section.keys())}")

# ── 6. Verificar clave GOOGLE_CREDENTIALS ────────────────────────────────────
print("\n🔑 Verificando GOOGLE_CREDENTIALS...")
raw = google_section.get("GOOGLE_CREDENTIALS")
if raw is None:
    print("   ❌ No existe la clave 'GOOGLE_CREDENTIALS' dentro de [google]")
    print(f"   Claves disponibles: {list(google_section.keys())}")
    exit(1)

print(f"   ✅ Clave encontrada")
print(f"   Tipo    : {type(raw).__name__}")
print(f"   Preview : {str(raw)[:80]}...")

# ── 7. Parsear como JSON ──────────────────────────────────────────────────────
print("\n🔄 Parseando como JSON...")
try:
    if isinstance(raw, str):
        creds = json.loads(raw)
        print("   ✅ Parseado desde string JSON")
    else:
        creds = dict(raw)
        print("   ✅ Convertido desde objeto TOML")
except json.JSONDecodeError as e:
    print(f"   ❌ Error de JSON: {e}")
    print("\n   💡 Verifica que el JSON en secrets.toml esté bien formado.")
    print("   El formato correcto es:")
    print("""
   [google]
   GOOGLE_CREDENTIALS = '''
   {
     "type": "service_account",
     "private_key": "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\\n",
     ...
   }
   '''
   """)
    exit(1)

# ── 8. Validar campos obligatorios ───────────────────────────────────────────
print("\n✅ Validando campos de la cuenta de servicio...")
required = ["type", "project_id", "private_key", "client_email"]
all_ok = True
for field in required:
    present = field in creds
    print(f"   {'✅' if present else '❌'} {field}: {str(creds.get(field,'FALTA'))[:50]}")
    if not present:
        all_ok = False

# ── 9. Resultado final ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if all_ok:
    print("  ✅ Credenciales válidas — backup_runner.py debería funcionar")
    print(f"  Client email: {creds.get('client_email')}")
    print(f"  Project ID  : {creds.get('project_id')}")
else:
    print("  ❌ Credenciales incompletas — revisa el JSON")
print("=" * 60 + "\n")
