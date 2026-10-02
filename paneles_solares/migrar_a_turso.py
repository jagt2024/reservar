#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
# migrar_a_turso.py — MIGRACIÓN DE UNA SOLA VEZ: SQLite local → Turso (libSQL)
# ------------------------------------------------------------------------
# Copia TODAS las tablas y filas de tu archivo .db local (proyectos, cargas,
# clientes, fotos del sitio con sus BLOBs, etc.) a una base de datos Turso,
# recreando el mismo esquema (CREATE TABLE) y preservando los IDs originales
# para que las relaciones entre tablas (proyecto_id, foto_id, etc.) sigan
# siendo correctas.
#
# Es seguro ejecutarlo más de una vez: usa INSERT OR IGNORE, así que las
# filas que ya existan en Turso (mismo ID) simplemente se saltan.
#
# USO:
#   1) Instala la dependencia (una vez):
#        pip install libsql-client
#   2) Define las credenciales de tu base de Turso, por variable de entorno:
#        export TURSO_DATABASE_URL="libsql://tu-base-xxxx.turso.io"   (Linux/Mac)
#        setx TURSO_DATABASE_URL "libsql://tu-base-xxxx.turso.io"     (Windows)
#        export TURSO_AUTH_TOKEN="tu-token-aqui"
#      … o pásalas directamente como argumentos (ver --url / --token abajo).
#   3) Ejecuta:
#        python migrar_a_turso.py --local solar_calc.db
#
#      Para solo comparar conteos sin escribir nada:
#        python migrar_a_turso.py --local solar_calc.db --solo-verificar
# ══════════════════════════════════════════════════════════════════════════

import argparse
import os
import sqlite3
import sys
import time

TURSO_DATABASE_URL= "libsql://solarcalc-josegar.aws-sa-east-1.turso.io"


try:
    import libsql_client
except ImportError:
    print("❌ Falta el paquete 'libsql-client'. Instálalo con:\n    pip install libsql-client")
    sys.exit(1)


TABLAS_INTERNAS_EXCLUIR = {"sqlite_sequence"}  # las maneja SQLite/libSQL internamente
LOTE = 25  # filas por tanda al insertar (evita payloads de red demasiado grandes)


# ─── Argumentos de línea de comandos ────────────────────────────────────────
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Migra una base SQLite local a Turso (libSQL), una sola vez.")
    p.add_argument("--local", default="solar_calc.db",
                    help="Ruta al archivo .db local a migrar (default: solar_calc.db)")
    p.add_argument("--url", default=os.environ.get("libsql://solarcalc-josegar.aws-sa-east-1.turso.io"),
                    help="URL de la base de Turso (o variable de entorno TURSO_DATABASE_URL)")
    p.add_argument("--token", default=os.environ.get("TURSO_AUTH_TOKEN"),
                    help="Auth token de Turso (o variable de entorno TURSO_AUTH_TOKEN)")
    p.add_argument("--tablas", default=None,
                    help="Lista opcional separada por comas para migrar solo esas tablas "
                         "(por defecto: todas)")
    p.add_argument("--incluir-tablas-internas", action="store_true",
                    help="Incluye tablas que empiezan con '_' (normalmente de pruebas internas)")
    p.add_argument("--solo-verificar", action="store_true",
                    help="No escribe nada: solo compara cuántas filas hay en local vs. Turso")
    return p.parse_args(argv)


# ─── Conexión local (sqlite3 estándar) ──────────────────────────────────────
def conectar_local(ruta):
    if not os.path.isfile(ruta):
        print(f"❌ No se encontró el archivo local '{ruta}'.")
        sys.exit(1)
    return sqlite3.connect(ruta)


# ─── Conexión a Turso (inyectable para pruebas, ver tests) ──────────────────
def conectar_turso(url, token):
    if not url:
        print("❌ Falta la URL de Turso. Pásala con --url o define TURSO_DATABASE_URL.")
        sys.exit(1)
    return libsql_client.create_client_sync(url=url, auth_token=token)


# ─── Esquema y filtrado de tablas ───────────────────────────────────────────
def listar_tablas_locales(conn_local, filtro_nombres=None, incluir_internas=False):
    cur = conn_local.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name")
    tablas = []
    for nombre, sql in cur.fetchall():
        if nombre in TABLAS_INTERNAS_EXCLUIR:
            continue
        if not incluir_internas and nombre.startswith("_"):
            continue
        if filtro_nombres and nombre not in filtro_nombres:
            continue
        tablas.append((nombre, sql))
    return tablas


def tabla_existe_en_turso(cliente, nombre):
    r = cliente.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [nombre])
    return len(r.rows) > 0


def crear_tabla_en_turso(cliente, nombre, sql_create):
    if tabla_existe_en_turso(cliente, nombre):
        return False
    cliente.execute(sql_create)
    return True


# ─── Copia de filas (por lotes, con INSERT OR IGNORE para poder re-ejecutar) ─
def contar_filas(conn, nombre, es_turso):
    if es_turso:
        r = conn.execute(f'SELECT COUNT(*) FROM "{nombre}"')
        return r.rows[0][0] if r.rows else 0
    else:
        return conn.execute(f'SELECT COUNT(*) FROM "{nombre}"').fetchone()[0]


def copiar_tabla(conn_local, cliente_turso, nombre):
    cur = conn_local.execute(f'SELECT * FROM "{nombre}"')
    columnas = [d[0] for d in cur.description]
    filas = cur.fetchall()
    total = len(filas)
    if total == 0:
        return 0

    cols_sql = ", ".join(f'"{c}"' for c in columnas)
    placeholders = ", ".join("?" for _ in columnas)
    sql_insert = f'INSERT OR IGNORE INTO "{nombre}" ({cols_sql}) VALUES ({placeholders})'

    copiadas = 0
    for inicio in range(0, total, LOTE):
        lote_filas = filas[inicio:inicio + LOTE]
        statements = [(sql_insert, list(fila)) for fila in lote_filas]
        cliente_turso.batch(statements)
        copiadas += len(lote_filas)
        print(f"    … {copiadas}/{total} filas", end="\r")
    print(f"    ✓ {copiadas}/{total} filas enviadas" + " " * 10)
    return copiadas


# ─── Programa principal ─────────────────────────────────────────────────────
def main(argv=None):
    args = parse_args(argv)
    filtro = set(t.strip() for t in args.tablas.split(",")) if args.tablas else None

    print(f"📂 Base de datos local: {os.path.abspath(args.local)}")
    conn_local = conectar_local(args.local)

    tablas = listar_tablas_locales(conn_local, filtro, args.incluir_tablas_internas)
    if not tablas:
        print("⚠ No se encontraron tablas para migrar (revisa --tablas si lo usaste).")
        return

    if args.solo_verificar:
        print("🔎 Modo verificación: no se escribirá nada.\n")
    else:
        print(f"🌐 Conectando a Turso ({args.url})...")
    cliente_turso = conectar_turso(args.url, args.token)

    print(f"\n{'Tabla':30s} {'Local':>8s} {'Turso (antes)':>14s}")
    print("-" * 56)

    resumen = []
    t0 = time.time()
    for nombre, sql_create in tablas:
        n_local = contar_filas(conn_local, nombre, es_turso=False)

        if args.solo_verificar:
            existe = tabla_existe_en_turso(cliente_turso, nombre)
            n_turso_antes = contar_filas(cliente_turso, nombre, es_turso=True) if existe else 0
            print(f"{nombre:30s} {n_local:>8d} {n_turso_antes:>14d}")
            resumen.append((nombre, n_local, n_turso_antes, n_turso_antes))
            continue

        creada = crear_tabla_en_turso(cliente_turso, nombre, sql_create)
        n_turso_antes = 0 if creada else contar_filas(cliente_turso, nombre, es_turso=True)
        print(f"{nombre:30s} {n_local:>8d} {n_turso_antes:>14d}"
              + ("  (tabla nueva)" if creada else ""))

        if n_local > 0:
            copiar_tabla(conn_local, cliente_turso, nombre)

        n_turso_despues = contar_filas(cliente_turso, nombre, es_turso=True)
        resumen.append((nombre, n_local, n_turso_antes, n_turso_despues))

    conn_local.close()
    cliente_turso.close()

    # ── Resumen final ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESUMEN" + (" (solo verificación, nada se escribió)" if args.solo_verificar else ""))
    print("=" * 70)
    hubo_problema = False
    for nombre, n_local, n_antes, n_despues in resumen:
        if args.solo_verificar:
            estado = "✅ coincide" if n_despues >= n_local else f"⚠ faltan {n_local - n_despues}"
        else:
            estado = "✅ completa" if n_despues >= n_local else f"⚠ faltan {n_local - n_despues}"
        if "⚠" in estado:
            hubo_problema = True
        print(f"  {nombre:30s} local={n_local:<6d} turso={n_despues:<6d} {estado}")

    print("-" * 70)
    print(f"Tiempo total: {time.time() - t0:.1f} s")
    if hubo_problema:
        print("⚠ Algunas tablas no quedaron completas. Vuelve a ejecutar el script "
              "(es seguro hacerlo varias veces) o revisa los mensajes de error arriba.")
    elif not args.solo_verificar:
        print("✅ Migración completa. Ya puedes configurar TURSO_DATABASE_URL / "
              "TURSO_AUTH_TOKEN en tu app (Settings → Secrets) y usar db_conn.py.")


if __name__ == "__main__":
    main()
