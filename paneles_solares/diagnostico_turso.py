"""
diagnostico_turso.py — Revisa, sin exponer el token completo, qué valores
de TURSO_DATABASE_URL y TURSO_AUTH_TOKEN está viendo Python en esta terminal.

USO:
    python diagnostico_turso.py
"""
import os

url = os.environ.get("TURSO_DATABASE_URL", "libsql://solarcalc-josegar.aws-sa-east-1.turso.io")
token = os.environ.get("TURSO_AUTH_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTA5OTY3NDYsImlkIjoiMDFhMGY5NjMtMGIwMS03ZWYyLTk5MTItZGVkODFiNzEyZmE1Iiwia2lkIjoibW1hYjA0SVQ4WlZWWFJhaWpqUjZXTGkwemtUR2ljNm1DZmtYU2YySTFRQSIsInJpZCI6IjQxM2I5NWRlLTU3NjktNGYxMS04ZGRkLThhNTIzMThhNDg4ZSJ9._71MXe_7gbjudqLMhztMFRT-UpuK2l2-5TRW_l5gO0JQeDoGJ93laATedD6__pBi1Yc7jT63839j-zQQgHlqBw")

print("=" * 60)
print("DIAGNÓSTICO DE CREDENCIALES DE TURSO")
print("=" * 60)

print(f"\nTURSO_DATABASE_URL: {url!r}")
if not url:
    print("  ⚠ No está definida en esta terminal.")
elif url != url.strip():
    print("  ⚠ Tiene espacios o saltos de línea pegados (se verá en las comillas arriba).")
else:
    print("  ✓ Parece correcta (sin espacios extra).")

print(f"\nTURSO_AUTH_TOKEN:")
if not token:
    print("  ⚠ No está definida en esta terminal.")
else:
    print(f"  Longitud total: {len(token)} caracteres (lo normal: 300+)")
    print(f"  Número de partes separadas por '.': {token.count('.') + 1} (debe ser 3)")
    print(f"  Primeros 15 caracteres: {token[:15]!r}")
    print(f"  Últimos 10 caracteres:  {token[-10:]!r}")
    if token != token.strip():
        print("  ⚠ Tiene espacios o saltos de línea pegados al principio/final.")
    else:
        print("  ✓ Sin espacios extra.")

print("\n" + "=" * 60)
print("Copia y pega TODO lo de arriba en el chat (es seguro: no se")
print("muestra el token completo, solo su longitud y algunos caracteres).")
print("=" * 60)
