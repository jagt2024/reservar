"""
JJGT — excel_sync.py  v6.0
═══════════════════════════════════════════════════════════════════════════════
Escritura en Google Sheets ("jjgt_gestion") y generación de Excel local.

ESTRATEGIA v6.0 — COLUMNAS PROPIAS, NO DE SHEETS
──────────────────────────────────────────────────
El bug de versiones anteriores: se leían los encabezados de la fila 1 de Sheets
y se intentaba mapear los valores del código a esas columnas. Cualquier diferencia
de codificación (tildes, espacios) hacía que get(header, "") devolviera "" para
casi todas las columnas → solo quedaba el ID.

Solución: las columnas las define SIEMPRE el convertidor del código (_row_*).
Al escribir, la hoja se alinea con el código, no al revés:
  1. Se genera la fila completa con el convertidor → lista ordenada de valores.
  2. Se escribe esa lista en la fila correcta usando A1-notation por número de fila.
  3. El mapeo ID→fila se hace leyendo SOLO la columna del PK (columna A o la que sea).

Esto garantiza que los valores correctos siempre llegan a Sheets sin depender
de que los encabezados coincidan carácter a carácter.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import io, math, time, random
import pandas as pd
import streamlit as st
from datetime import datetime
from typing import Optional

# ════════════════════════════════════════════════════════════════════════════
# RETRY — manejo del error 429 (Quota exceeded para escrituras)
# ════════════════════════════════════════════════════════════════════════════
_MAX_RETRIES = 6
_BASE_DELAY  = 2.0
_MAX_DELAY   = 64.0

def _is_quota_err(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ["429","quota","rate limit","exhausted","too many"])

def _api_call(fn, *args, **kwargs):
    """
    Envuelve cualquier llamada a la API de Sheets con reintentos automáticos.
    Backoff: 2s → 4s → 8s → 16s → 32s → 64s con jitter del 25%.
    """
    delay = _BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            recoverable = _is_quota_err(e) or any(
                c in str(e) for c in ["500","502","503","504"])
            if recoverable:
                jitter = random.uniform(0, delay * 0.25)
                time.sleep(min(delay + jitter, _MAX_DELAY))
                delay  = min(delay * 2, _MAX_DELAY)
            else:
                raise

# ── Constantes ─────────────────────────────────────────────────────────────
SHEET_FILE = "jjgt_gestion"
DATA_START = 2      # fila 1 = encabezados, datos desde fila 2
CHUNK      = 100    # filas por lote en append_rows

WS = {
    "vehiculos":      "🚗 VEHÍCULOS",
    "usuarios":       "👥 USUARIOS",
    "permutas":       "🔄 PERMUTAS",
    "publicaciones":  "📋 PUBLICACIONES",
    "historial":      "📦 HISTORIAL",
    "notificaciones": "🔔 NOTIFICACIONES",
    "resenas":        "⭐ RESEÑAS",
}

PK = {
    "vehiculos":      "ID",
    "usuarios":       "ID",
    "permutas":       "ID",
    "publicaciones":  "ID Pub",
    "historial":      "ID",
    "notificaciones": "ID",
    "resenas":        "ID",
}

# ── A1 notation ────────────────────────────────────────────────────────────
def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _cell(row: int, col: int) -> str:
    return f"{_col_letter(col)}{row}"

def _row_range(row: int, ncols: int) -> str:
    return f"A{row}:{_col_letter(ncols)}{row}"

# ── Limpieza de valores ─────────────────────────────────────────────────────
_SKIP = {"fotos", "video", "pubRef", "isUserPub"}

def _safe(v) -> str | int | float:
    if v is None:                          return ""
    if isinstance(v, bool):               return "Sí" if v else "No"
    if isinstance(v, (bytes, bytearray)): return ""
    if isinstance(v, float):
        return "" if (math.isnan(v) or math.isinf(v)) else round(v, 6)
    if isinstance(v, int):                return v
    s = str(v).strip()
    return "" if s in ("None","nan","NaN","NaT") else s

def _clean(d: dict) -> dict:
    return {k: _safe(v) for k, v in d.items() if k not in _SKIP}

# ═══════════════════════════════════════════════════════════════════════════
# CONVERTIDORES  — devuelven OrderedDict con columnas DEFINITIVAS
# El orden de las claves define el orden de columnas en Sheets.
# ═══════════════════════════════════════════════════════════════════════════
_TIPO   = {"venta":"Venta","permuta":"Permuta","ambos":"Venta/Permuta"}
_STATUS = {"activo":"Activo","pendiente":"Pendiente",
           "completado":"Completado","cancelled":"Cancelado"}

def _row_veh(v: dict) -> dict:
    return {
        "ID":            _safe(v.get("id","")),
        "Nombre":        _safe(v.get("name","")),
        "Modelo":        _safe(v.get("model","")),
        "Año":           _safe(v.get("year","")),
        "Precio (COP)":  _safe(v.get("price",0)),
        "Km":            _safe(v.get("km",0)),
        "Combustible":   _safe(v.get("fuel","")),
        "Transmision":   _safe(v.get("trans","")),
        "Ciudad":        _safe(v.get("city","")),
        "Color":         _safe(v.get("color","")),
        "Tipo Aviso":    _TIPO.get(v.get("type","venta"),"Venta"),
        "Calificacion":  _safe(v.get("rating",0)),
        "Resenas":       _safe(v.get("reviews",0)),
        "Estado":        _safe(v.get("estado","Activo")),
    }

def _row_usr(u: dict) -> dict:
    return {
        "ID":             _safe(u.get("id","")),
        "Nombre":         _safe(u.get("nombre","")),
        "Correo":         _safe(u.get("correo","")),
        "Celular":        _safe(u.get("celular","")),
        "Documento":      _safe(u.get("documento","")),
        "Ciudad":         _safe(u.get("ciudad","")),
        "Rol":            _safe(u.get("rol","")),
        "Publicaciones":  _safe(u.get("publicaciones",0)),
        "Ventas":         _safe(u.get("ventas",0)),
        "Puntos":         _safe(u.get("puntos",0)),
        "Nivel":          _safe(u.get("nivel","Bronze")),
        "Fecha Registro": _safe(u.get("fecha_registro","")),
        "Password Hash":  _safe(u.get("password_hash","")),
    }

def _row_perm(p: dict) -> dict:
    return {
        "ID":                 _safe(p.get("id","")),
        "Veh Ofertado":       _safe(p.get("veh_oferta","")),
        "Vendedor Oferta":    _safe(p.get("vendedor_oferta","")),
        "Veh Solicitado":     _safe(p.get("veh_destino","")),
        "Propietario":        _safe(p.get("propietario","")),
        "Ciudad":             _safe(p.get("ciudad","")),
        "Valor Estimado":     _safe(p.get("valor_oferta",0)),
        "Diferencia":         _safe(p.get("diferencia",0)),
        "Fecha":              _safe(p.get("fecha","")),
        "Estado":             _safe(p.get("estado","Activa")),
        "Mensaje":            _safe(p.get("mensaje","")),
        "Resultado":          _safe(p.get("resultado","Pendiente")),
    }

def _row_pub(p: dict) -> dict:
    nombre = f"{p.get('name','')} {p.get('model','')}".strip()
    return {
        "ID Pub":          _safe(p.get("id","")),
        "ID Veh":          _safe(p.get("id_veh", p.get("id",""))),
        "Vehiculo":        nombre,
        "Año":             _safe(p.get("year","")),
        "Precio":          _safe(p.get("price",0)),
        "Tipo Aviso":      _TIPO.get(p.get("type","venta"),"Venta"),
        "Estado Pub":      _safe(p.get("estado_pub", p.get("estado","Activa"))),
        "Vendedor":        _safe(p.get("seller","")),
        "Correo Vendedor": _safe(p.get("seller_email","")),
        "Celular Vendedor":_safe(p.get("seller_phone", p.get("phone",""))),
        "Ciudad":          _safe(p.get("city","")),
        "Verificado":      "Si" if p.get("verificado") else "No",
        "Fecha Pub":       _safe(p.get("fecha", datetime.now().strftime("%d/%m/%Y"))),
        "Visitas":         _safe(p.get("visitas",0)),
        "Favoritos":       _safe(p.get("favoritos",0)),
        "Descripcion":     _safe(p.get("desc","")),          # Descripción del vehículo
        "Fotos URLs":      _safe(p.get("fotos_urls","")),   # URLs Drive separadas por coma
        "Video URL":       _safe(p.get("video_url","")),    # URL Drive del video
    }

def _row_hist(h: dict) -> dict:
    return {
        "ID":               _safe(h.get("id","")),
        "Vehiculo":         _safe(h.get("name","")),
        "Tipo":             _safe(h.get("type","")),
        "Vendedor":         _safe(h.get("seller","")),
        "Comprador":        _safe(h.get("buyer","—")),
        "Ciudad":           _safe(h.get("city","")),
        "Precio Final":     _safe(h.get("price",0)),
        "Fecha":            _safe(h.get("date","")),
        "Estado":           _STATUS.get(h.get("status","activo"),"Activo"),
        "Puntos":           _safe(h.get("points",0)),
        "Notas":            _safe(h.get("notes","")),
    }

def _row_notif(n: dict) -> dict:
    return {
        "ID":       _safe(n.get("id","")),
        "Tipo":     _safe(n.get("tipo","")),
        "Titulo":   _safe(n.get("title","")),
        "Desc":     _safe(n.get("desc","")),
        "Usuario":  _safe(n.get("user","")),
        "Fecha":    _safe(n.get("date","")),
        "Hora":     _safe(n.get("time","")),
        "Leida":    "No" if n.get("unread") else "Si",
        "Accion":   _safe(n.get("action","")),
    }

def _row_resena(r: dict) -> dict:
    return {
        "ID":            _safe(r.get("id","")),
        "Pub ID":        _safe(r.get("pub_id","")),
        "Vehiculo":      _safe(r.get("vehiculo","")),
        "Vendedor":      _safe(r.get("vendedor","")),
        "Autor":         _safe(r.get("autor","")),
        "Calificacion":  _safe(r.get("rating",0)),
        "Comentario":    _safe(r.get("comentario","")),
        "Fecha":         _safe(r.get("fecha","")),
        "Verificada":    "Si" if r.get("verificada") else "No",
    }

_ROW = {
    "vehiculos":      _row_veh,
    "usuarios":       _row_usr,
    "permutas":       _row_perm,
    "publicaciones":  _row_pub,
    "historial":      _row_hist,
    "notificaciones": _row_notif,
    "resenas":        _row_resena,
}

# ═══════════════════════════════════════════════════════════════════════════
# RECOLECTOR de datos desde session_state
# ═══════════════════════════════════════════════════════════════════════════
def update_dashboard(spreadsheet) -> bool:
    """Actualiza la hoja Dashboard con métricas completas por ciudad y estado."""
    try:
        try:
            ws = spreadsheet.worksheet("📊 DASHBOARD")
        except Exception:
            ws = spreadsheet.add_worksheet("📊 DASHBOARD", rows="80", cols="6")

        vehs  = st.session_state.get("_vehicles", []) + st.session_state.get("user_publications", [])
        users = st.session_state.get("_usuarios", [])
        perms = st.session_state.get("permutas",  [])
        hists = st.session_state.get("history_items", [])
        resenas = st.session_state.get("resenas", [])
        now   = datetime.now().strftime("%d/%m/%Y %H:%M")

        # ── Métricas globales ─────────────────────────────────────────────
        total_vehs  = len(vehs)
        activos     = sum(1 for v in vehs if str(v.get("estado","Activo")).lower() == "activo")
        pausados    = sum(1 for v in vehs if str(v.get("estado","")).lower() == "pausado")
        cerrados    = sum(1 for v in vehs if str(v.get("estado","")).lower() == "cerrado")
        en_venta    = sum(1 for v in vehs if v.get("type") in ("venta","ambos"))
        en_permuta  = sum(1 for v in vehs if v.get("type") in ("permuta","ambos"))

        ventas_ok   = sum(1 for h in hists if h.get("status") == "completado")
        ventas_pend = sum(1 for h in hists if h.get("status") == "pendiente")
        ventas_tot  = len(hists)

        perms_act   = sum(1 for p in perms if p.get("estado") == "Activa")
        perms_comp  = sum(1 for p in perms if p.get("resultado") == "Completada")
        perms_tot   = len(perms)

        total_resenas = len(resenas)
        avg_rating    = round(sum(r.get("rating",0) for r in resenas)/max(len(resenas),1), 1)

        ciudades_set  = sorted({v.get("city","").strip() for v in vehs if v.get("city","").strip()})

        # ── Detalle por ciudad ────────────────────────────────────────────
        ciudad_data = {}
        for v in vehs:
            c = v.get("city","Sin ciudad").strip() or "Sin ciudad"
            if c not in ciudad_data:
                ciudad_data[c] = {"vehs":0,"activos":0,"venta":0,"permuta":0,"ventas_ok":0,"perms_ok":0}
            ciudad_data[c]["vehs"] += 1
            if str(v.get("estado","Activo")).lower() == "activo":
                ciudad_data[c]["activos"] += 1
            if v.get("type") in ("venta","ambos"):
                ciudad_data[c]["venta"] += 1
            if v.get("type") in ("permuta","ambos"):
                ciudad_data[c]["permuta"] += 1

        for h in hists:
            c = h.get("city","Sin ciudad").strip() or "Sin ciudad"
            if c not in ciudad_data:
                ciudad_data[c] = {"vehs":0,"activos":0,"venta":0,"permuta":0,"ventas_ok":0,"perms_ok":0}
            if h.get("status") == "completado":
                ciudad_data[c]["ventas_ok"] += 1

        for p in perms:
            c = p.get("ciudad","Sin ciudad").strip() or "Sin ciudad"
            if c not in ciudad_data:
                ciudad_data[c] = {"vehs":0,"activos":0,"venta":0,"permuta":0,"ventas_ok":0,"perms_ok":0}
            if p.get("resultado") == "Completada":
                ciudad_data[c]["perms_ok"] += 1

        # ── Construir hoja ────────────────────────────────────────────────
        S = lambda x: "" if x == 0 else x
        filas = [
            ["📊 JJGT — DASHBOARD GENERAL · ADMINISTRADOR", "", "", "", "", ""],
            [f"Acceso: josegarjagt@gmail.com  |  Actualizado: {now}", "", "", "", "", ""],
            ["", "", "", "", "", ""],

            ["═══ VEHÍCULOS ═══", "", "", "", "", ""],
            ["MÉTRICA", "VALOR", "DESCRIPCIÓN", "", "", ""],
            ["Total publicaciones",    total_vehs,  "Todos los vehículos en la plataforma", "", "", ""],
            ["Activos",                activos,     "Con estado Activo", "", "", ""],
            ["Pausados",               S(pausados), "Temporalmente desactivados", "", "", ""],
            ["Cerrados",               S(cerrados), "Publicaciones cerradas", "", "", ""],
            ["En venta",               en_venta,    "Tipo Venta o Venta+Permuta", "", "", ""],
            ["En permuta",             en_permuta,  "Tipo Permuta o Venta+Permuta", "", "", ""],
            ["", "", "", "", "", ""],

            ["═══ TRANSACCIONES ═══", "", "", "", "", ""],
            ["MÉTRICA", "VALOR", "DESCRIPCIÓN", "", "", ""],
            ["Historial total",        ventas_tot,  "Total registros en historial", "", "", ""],
            ["Ventas completadas",     ventas_ok,   "Estado = completado", "", "", ""],
            ["Ventas pendientes",      S(ventas_pend), "Estado = pendiente", "", "", ""],
            ["Permutas totales",       perms_tot,   "Total propuestas de permuta", "", "", ""],
            ["Permutas activas",       perms_act,   "Estado = Activa", "", "", ""],
            ["Permutas completadas",   S(perms_comp),"Resultado = Completada", "", "", ""],
            ["", "", "", "", "", ""],

            ["═══ USUARIOS Y RESEÑAS ═══", "", "", "", "", ""],
            ["MÉTRICA", "VALOR", "DESCRIPCIÓN", "", "", ""],
            ["Usuarios registrados",   len(users),  "Cuentas en el sistema", "", "", ""],
            ["Total reseñas",          total_resenas,"Calificaciones publicadas", "", "", ""],
            ["Rating promedio",        avg_rating,  "Promedio de todas las reseñas", "", "", ""],
            ["Ciudades activas",       len(ciudades_set), "Ciudades con publicaciones", "", "", ""],
            ["", "", "", "", "", ""],

            ["═══ DETALLE POR CIUDAD ═══", "", "", "", "", ""],
            ["CIUDAD", "VEHÍCULOS", "ACTIVOS", "EN VENTA", "EN PERMUTA", "VENTAS/PERMUTAS OK"],
        ]
        for c, d in sorted(ciudad_data.items(), key=lambda x: -x[1]["vehs"]):
            ok = d["ventas_ok"] + d["perms_ok"]
            filas.append([c, d["vehs"], d["activos"], d["venta"], d["permuta"], S(ok)])

        _api_call(ws.clear)
        _api_call(ws.update, "A1", filas)
        return True
    except Exception as e:
        return False


def _collect(sections: list) -> dict:
    # Combinar _vehicles + user_publications SIN duplicados (por ID)
    seen_ids = set()
    all_veh  = []
    for v in st.session_state.get("_vehicles", []):
        vid = str(v.get("id",""))
        if vid not in seen_ids:
            seen_ids.add(vid)
            all_veh.append(_clean(v))
    for pub in st.session_state.get("user_publications", []):
        vid = str(pub.get("id",""))
        if vid not in seen_ids:
            seen_ids.add(vid)
            all_veh.append(_clean(pub))

    raw = {
        "vehiculos":      all_veh,
        "usuarios":       [_clean(u) for u in st.session_state.get("_usuarios", [])],
        "permutas":       [_clean(p) for p in st.session_state.get("permutas",
                           st.session_state.get("_permutas_base", []))],
        "publicaciones":  [_clean(p) for p in st.session_state.get("user_publications", [])],
        "historial":      [_clean(h) for h in st.session_state.get("history_items",
                           st.session_state.get("_history_base", []))],
        "notificaciones": [_clean(n) for n in st.session_state.get("notifications",
                           st.session_state.get("_notifs_base", []))],
        "resenas":        [_clean(r) for r in st.session_state.get("resenas", [])],
    }
    return {k: raw[k] for k in sections if k in raw}

# ═══════════════════════════════════════════════════════════════════════════
# OBTENER CLIENTE
# ═══════════════════════════════════════════════════════════════════════════
def _get_client():
    client = st.session_state.get("_gs_client")
    if client is not None:
        return client
    try:
        from data import load_credentials_from_toml, get_google_sheets_connection
        creds, _ = load_credentials_from_toml()
        if not creds:
            st.error("❌ No se encontraron credenciales. "
                     "Verifica [sheetsemp] credentials_sheet en secrets.toml")
            return None
        return get_google_sheets_connection(creds)
    except Exception as e:
        st.error(f"❌ Error conectando: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# UPSERT — v6: columnas del CÓDIGO, no de Sheets
# ═══════════════════════════════════════════════════════════════════════════
def _upsert_ws(spreadsheet, key: str, items: list[dict]) -> tuple[bool, str]:
    """
    Escribe items en la worksheet usando UPSERT.

    DIFERENCIA CLAVE vs versiones anteriores:
    - Los encabezados y el orden de columnas los define el convertidor _row_*
      del código, NO los que están en la fila 1 de Sheets.
    - Esto evita el bug de "solo queda el ID" causado por diferencias de
      codificación entre los encabezados de Sheets y los del código.
    - Para detectar UPDATE vs INSERT, lee SOLO la columna del PK (no toda la hoja).
    """
    import gspread

    ws_name   = WS[key]
    pk_col    = PK[key]
    row_fn    = _ROW[key]

    # Las columnas y su orden son siempre los del convertidor
    # (independiente de lo que haya en Sheets)
    sample_row = row_fn(items[0]) if items else {}
    our_headers = list(sample_row.keys())          # ej: ["ID","Nombre","Modelo",...]
    pk_col_idx  = our_headers.index(pk_col)        # posición del PK en nuestra lista (0-based)
    n_cols      = len(our_headers)

    # ── 1. Abrir o crear la worksheet ────────────────────────────────────────
    try:
        ws = spreadsheet.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title = ws_name,
            rows  = str(max(len(items) + 20, 100)),
            cols  = str(max(n_cols + 2, 20)),
        )
        ws.append_row(our_headers)
        time.sleep(0.8)
        # Hoja recién creada → todo es INSERT
        rows_to_insert = [list(row_fn(item).values()) for item in items]
        if rows_to_insert:
            _append_chunks(ws, rows_to_insert)
        return True, f"'{ws_name}': hoja creada · {len(rows_to_insert)} filas escritas"

    # ── 2. Leer hoja completa ────────────────────────────────────────────────
    try:
        all_vals = _api_call(ws.get_all_values)
    except Exception as e:
        if _is_quota_err(e):
            return False, (f"⚠️ Cuota de lectura excedida en '{ws_name}' (Error 429). "
                           f"Espera ~1 min y vuelve a guardar.")
        return False, f"Error leyendo '{ws_name}': {e}"

    # ── 3. Si la hoja está vacía, escribir encabezados y todos los datos ─────
    if not all_vals:
        _api_call(ws.append_row, our_headers)
        time.sleep(0.4)
        rows_to_insert = [list(row_fn(item).values()) for item in items]
        _append_chunks(ws, rows_to_insert)
        return True, f"'{ws_name}': {len(rows_to_insert)} filas escritas (hoja vacía)"

    # ── 4. Verificar/actualizar fila 1 (encabezados) ─────────────────────────
    existing_headers = all_vals[0]
    if existing_headers != our_headers:
        # Reemplazar solo la fila de encabezados, sin tocar los datos
        _api_call(ws.update, "A1", [our_headers])
        time.sleep(0.3)

    data_rows = all_vals[1:]   # filas 2..N (datos existentes)

    # ── 5. Construir mapa  PK_valor → número_de_fila (1-based en Sheets) ────
    # Leemos la columna PK de data_rows (posición pk_col_idx, 0-based)
    existing: dict[str, int] = {}
    for i, row in enumerate(data_rows):
        val = str(row[pk_col_idx]).strip() if pk_col_idx < len(row) else ""
        if val:
            existing[val] = i + DATA_START   # DATA_START=2

    # ── 6. Clasificar cada item: UPDATE o INSERT ─────────────────────────────
    to_update: list[tuple[int, list]] = []   # (sheet_row_number, values_list)
    to_insert: list[list]             = []

    for item in items:
        # Generar la fila COMPLETA usando el convertidor — valores en orden correcto
        converted  = row_fn(item)
        values     = [_safe(v) for v in converted.values()]   # misma lista, siempre completa
        pk_val     = str(values[pk_col_idx]).strip()

        if pk_val and pk_val in existing:
            to_update.append((existing[pk_val], values))
        else:
            to_insert.append(values)

    # ── 7. Ejecutar UPDATEs ──────────────────────────────────────────────────
    updated = 0
    for sheet_row, values in to_update:
        rng = _row_range(sheet_row, n_cols)   # ej: "A5:N5"
        try:
            _api_call(ws.update, rng, [values])
            updated += 1
            time.sleep(0.12)
        except Exception as e:
            return False, f"Error actualizando fila {sheet_row} en '{ws_name}': {e}"

    # ── 8. Ejecutar INSERTs ──────────────────────────────────────────────────
    inserted = _append_chunks(ws, to_insert)

    msg = f"'{ws_name}': {updated} actualizadas · {inserted} nuevas"
    return True, msg


def _append_chunks(ws, rows: list[list]) -> int:
    """Inserta filas en lotes de CHUNK con reintentos ante 429."""
    inserted = 0
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        try:
            _api_call(ws.append_rows, chunk, value_input_option="USER_ENTERED")
        except TypeError:
            _api_call(ws.append_rows, chunk)   # fallback sin value_input_option
        inserted += len(chunk)
        if i + CHUNK < len(rows):
            time.sleep(0.5)
    return inserted


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════
def save_to_sheets(sections: Optional[list[str]] = None) -> dict[str, dict]:
    import gspread
    keys    = sections if sections else list(WS.keys())
    results = {k: {"ok": False, "msg": "No ejecutado"} for k in keys}

    client = _get_client()
    if not client:
        for k in keys:
            results[k]["msg"] = "Sin cliente Google Sheets — revisa secrets.toml"
        return results

    try:
        spreadsheet = client.open(SHEET_FILE)
    except gspread.exceptions.SpreadsheetNotFound:
        msg = f"Archivo '{SHEET_FILE}' no encontrado. Verifica nombre y permisos."
        for k in keys:
            results[k]["msg"] = msg
        return results
    except Exception as e:
        for k in keys:
            results[k]["msg"] = f"Error abriendo '{SHEET_FILE}': {e}"
        return results

    data = _collect(keys)

    for key in keys:
        if key not in _ROW:
            results[key] = {"ok": False, "msg": f"Clave desconocida: '{key}'"}
            continue
        items = data.get(key, [])
        if not items:
            results[key] = {"ok": True, "msg": f"'{WS.get(key,key)}': sin datos"}
            continue
        try:
            ok, msg = _upsert_ws(spreadsheet, key, items)
            results[key] = {"ok": ok, "msg": msg}
        except Exception as e:
            if _is_quota_err(e):
                results[key] = {
                    "ok": False,
                    "msg": (f"⚠️ Cuota de escritura excedida en '{WS.get(key,key)}' "
                            f"(Error 429 – Quota exceeded). "
                            f"Espera ~1 minuto y vuelve a intentarlo.")
                }
            else:
                results[key] = {"ok": False, "msg": f"Error en '{key}': {e}"}
        time.sleep(0.3)

    return results


# ═══════════════════════════════════════════════════════════════════════════
# EXCEL LOCAL
# ═══════════════════════════════════════════════════════════════════════════
def save_to_excel(sections: Optional[list[str]] = None) -> bytes:
    keys = sections if sections else list(WS.keys())
    data = _collect(keys)
    buf  = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for key in keys:
            fn      = _ROW.get(key)
            items   = data.get(key, [])
            ws_name = WS.get(key, key)
            rows    = [fn(i) for i in items] if (fn and items) else []
            df      = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=ws_name, index=False)
            try:
                from openpyxl.styles import PatternFill, Font, Alignment
                ews = writer.sheets[ws_name]
                for cell in ews[1]:
                    cell.fill      = PatternFill("solid", fgColor="1A1A2E")
                    cell.font      = Font(color="FFFFFF", bold=True, size=10)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                for col in ews.columns:
                    max_w = max((len(str(c.value or "")) for c in col), default=8)
                    ews.column_dimensions[col[0].column_letter].width = min(max_w + 4, 45)
            except Exception:
                pass
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════
def download_button_excel(label:    str                  = "⬇️ Exportar Excel",
                          sections: Optional[list[str]] = None,
                          key:      str                  = "dl_excel"):
    try:
        xlsx  = save_to_excel(sections)
        fname = f"JJGT_Gestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        st.download_button(label=label, data=xlsx, file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=key, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Error generando Excel: {e}")


def save_and_notify(sections:    Optional[list[str]] = None,
                    success_msg: str = "✅ Datos guardados en Google Sheets"):
    with st.spinner("☁️ Guardando en Google Sheets…"):
        results = save_to_sheets(sections)

    ok_all   = all(r["ok"] for r in results.values())
    err_keys = [k for k, r in results.items() if not r["ok"]]

    if ok_all:
        st.success(success_msg)
    else:
        st.error(f"❌ Error en: {', '.join(WS.get(k,k) for k in err_keys)}")

    with st.expander("📋 Detalle por hoja", expanded=not ok_all):
        for k, r in results.items():
            icon = "✅" if r["ok"] else "❌"
            st.markdown(f"{icon} **{WS.get(k,k)}** — {r['msg']}")


def delete_publication_from_sheets(pub_id: str) -> tuple[bool, str]:
    """
    Elimina la fila con pub_id de las hojas de Vehículos y Publicaciones.
    No toca el historial. Retorna (ok, mensaje).
    """
    try:
        import time as _time
        client = _get_client()
        if not client:
            return False, "Sin cliente Google Sheets — revisa secrets.toml"

        sh      = client.open(SHEET_FILE)
        pid_str = str(pub_id).strip()
        results = []

        for ws_key in ("vehiculos", "publicaciones"):
            ws_name = WS[ws_key]          # "🚗 VEHÍCULOS" / "📋 PUBLICACIONES"
            pk_col  = PK[ws_key]          # "ID"
            try:
                ws = sh.worksheet(ws_name)
            except Exception:
                results.append(f"{ws_name}: hoja no encontrada")
                continue

            all_vals = ws.get_all_values()
            if not all_vals:
                results.append(f"{ws_name}: vacía")
                continue

            headers = all_vals[0]
            if pk_col not in headers:
                results.append(f"{ws_name}: sin columna '{pk_col}'")
                continue

            pk_idx = headers.index(pk_col)

            # Buscar fila (recorrer de abajo hacia arriba para no alterar índices al borrar)
            rows_to_delete = []
            for i, row in enumerate(all_vals[1:], start=2):  # 1-based sheet rows
                val = str(row[pk_idx]).strip() if pk_idx < len(row) else ""
                if val == pid_str:
                    rows_to_delete.append(i)

            if not rows_to_delete:
                results.append(f"{ws_name}: ID {pid_str} no encontrado")
                continue

            # Borrar de abajo hacia arriba para no desplazar índices
            for row_num in sorted(rows_to_delete, reverse=True):
                ws.delete_rows(row_num)
                _time.sleep(0.2)

            results.append(f"{ws_name}: {len(rows_to_delete)} fila(s) eliminada(s)")

        return True, " · ".join(results)

    except Exception as e:
        return False, str(e)


def save_password_hash_to_sheets(correo: str, pw_hash: str) -> tuple[bool, str]:
    """
    Escribe el password_hash directamente en la celda correcta de la hoja USUARIOS.
    Busca la fila por correo y actualiza (o crea) la columna 'Password Hash'.
    Retorna (ok, mensaje).
    """
    try:
        client = _get_client()
        if not client:
            return False, "Sin cliente Google Sheets — revisa secrets.toml"

        sh = client.open(SHEET_FILE)
        ws = sh.worksheet(WS["usuarios"])   # "👥 USUARIOS"

        all_vals = ws.get_all_values()
        if not all_vals:
            return False, "Hoja USUARIOS vacía"

        headers = all_vals[0]

        # Buscar o crear columna Password Hash
        PH_COL = "Password Hash"
        if PH_COL in headers:
            ph_idx = headers.index(PH_COL)   # 0-based
        else:
            # Agregar columna al final
            ph_idx = len(headers)
            headers.append(PH_COL)
            ws.update("A1", [headers])
            time.sleep(0.4)

        # Buscar columna Correo
        correo_col_names = ["Correo", "correo", "Email", "email"]
        correo_idx = None
        for name in correo_col_names:
            if name in headers:
                correo_idx = headers.index(name)
                break
        if correo_idx is None:
            return False, "No se encontró columna 'Correo' en USUARIOS"

        # Buscar fila del usuario por correo
        correo_norm = correo.strip().lower()
        target_row  = None   # 1-based sheet row
        for i, row in enumerate(all_vals[1:], start=2):
            cell_val = str(row[correo_idx]).strip().lower() if correo_idx < len(row) else ""
            if cell_val == correo_norm:
                target_row = i
                break

        if target_row is None:
            return False, f"Correo '{correo}' no encontrado en USUARIOS"

        # Calcular letra de columna (A=0, B=1, ...)
        import string as _string
        def _col_letter(idx: int) -> str:
            result = ""
            idx += 1
            while idx:
                idx, rem = divmod(idx - 1, 26)
                result = _string.ascii_uppercase[rem] + result
            return result

        cell_addr = f"{_col_letter(ph_idx)}{target_row}"
        ws.update(cell_addr, [[pw_hash]])
        time.sleep(0.2)
        return True, f"Password Hash actualizado en celda {cell_addr}"

    except Exception as e:
        return False, str(e)


def save_section_silent(sections: list = None, update_dash: bool = True) -> bool:
    try:
        results = save_to_sheets(sections)
        ok = all(r["ok"] for r in results.values())
        # Actualizar dashboard automáticamente
        if ok and update_dash:
            try:
                client = _get_client()
                if client:
                    sh = client.open(SHEET_FILE)
                    update_dashboard(sh)
            except Exception:
                pass
        return ok
    except Exception:
        return False
