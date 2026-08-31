"""
modulo_backup_proyecto.py — Exportar / Importar Proyecto completo
SolarCalc Pro · Módulo externo

Permite descargar TODA la información de un proyecto (datos generales,
cargas, panel, resultados guardados, recibos, baterías, y cualquier otra
tabla que otro módulo haya vinculado a `proyecto_id`) en un archivo Excel
o en un paquete de CSV, y volver a cargar ese archivo más adelante —en
esta misma instalación o en otra— para recrear el proyecto completo sin
tener que capturar la información de nuevo.

Las tablas relacionadas se descubren dinámicamente (vía `PRAGMA
table_info`) buscando cualquier tabla con una columna `proyecto_id`, en
vez de tener una lista fija — así el backup no deja nada por fuera aunque
otro módulo (cableado, checklist, presupuesto, etc.) agregue su propia
tabla más adelante.
"""
import io
import zipfile
import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime

from db_utils import get_conn


# ═══════════════════════════════════════════════════════════════════════════
# DESCUBRIMIENTO DINÁMICO DE TABLAS RELACIONADAS A UN PROYECTO
# ═══════════════════════════════════════════════════════════════════════════
def _columnas_tabla(conn, tabla: str) -> list:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]


def _tablas_relacionadas_proyecto() -> list:
    """Devuelve los nombres de todas las tablas que tienen una columna
    `proyecto_id` (cargas, paneles, resultados, recibos, baterias, y
    cualquier otra que exista), excluyendo la propia tabla `proyectos`."""
    conn = get_conn()
    tablas = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    con_proyecto = []
    for t in tablas:
        if t == "proyectos":
            continue
        try:
            if "proyecto_id" in _columnas_tabla(conn, t):
                con_proyecto.append(t)
        except Exception:
            continue
    conn.close()
    return sorted(con_proyecto)


# ═══════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ═══════════════════════════════════════════════════════════════════════════
def obtener_datos_proyecto(proyecto_id: int) -> dict:
    """Trae el proyecto y TODAS sus tablas relacionadas como DataFrames.
    Devuelve {} si el proyecto no existe. La clave 'proyecto' (minúscula)
    siempre está presente si el proyecto existe; el resto de claves son
    los nombres reales de las tablas relacionadas."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    p = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    conn.close()
    if not p:
        return {}

    datos = {"proyecto": pd.DataFrame([dict(p)])}
    conn = get_conn()
    for tabla in _tablas_relacionadas_proyecto():
        try:
            datos[tabla] = pd.read_sql(
                f"SELECT * FROM {tabla} WHERE proyecto_id=?", conn, params=(proyecto_id,))
        except Exception:
            datos[tabla] = pd.DataFrame()
    conn.close()
    return datos


def exportar_excel(proyecto_id: int) -> bytes:
    """Arma un .xlsx con una hoja 'Proyecto' y una hoja por cada tabla
    relacionada, con TODAS sus columnas (incluye 'id', útil para
    referencia; al importar se ignora y se asignan ids nuevos)."""
    datos = obtener_datos_proyecto(proyecto_id)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        datos.get("proyecto", pd.DataFrame()).to_excel(
            writer, sheet_name="Proyecto", index=False)
        for tabla, df in datos.items():
            if tabla == "proyecto":
                continue
            (df if not df.empty else pd.DataFrame(columns=["id", "proyecto_id"])).to_excel(
                writer, sheet_name=tabla[:31], index=False)
    return buffer.getvalue()


def exportar_csv_zip(proyecto_id: int) -> bytes:
    """Arma un .zip con un .csv por cada tabla (proyecto.csv, cargas.csv,
    etc.) — un solo archivo .csv no puede contener varias tablas a la vez."""
    datos = obtener_datos_proyecto(proyecto_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("proyecto.csv",
                     datos.get("proyecto", pd.DataFrame()).to_csv(index=False))
        for tabla, df in datos.items():
            if tabla == "proyecto":
                continue
            zf.writestr(f"{tabla}.csv", df.to_csv(index=False))
    return buffer.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
# IMPORTAR
# ═══════════════════════════════════════════════════════════════════════════
def leer_excel_subido(archivo) -> dict:
    xls = pd.ExcelFile(archivo)
    return {hoja: pd.read_excel(xls, sheet_name=hoja) for hoja in xls.sheet_names}


def leer_zip_csv_subido(archivo) -> dict:
    hojas = {}
    with zipfile.ZipFile(archivo) as zf:
        for nombre in zf.namelist():
            if not nombre.lower().endswith(".csv"):
                continue
            with zf.open(nombre) as f:
                clave = nombre.rsplit(".", 1)[0]
                hojas[clave] = pd.read_csv(f)
    return hojas


def _insertar_dataframe(conn, tabla: str, df: pd.DataFrame, nuevo_proyecto_id: int) -> int:
    """Inserta las filas de `df` en `tabla`, reemplazando su proyecto_id
    por `nuevo_proyecto_id` y dejando que la base de datos asigne un `id`
    nuevo a cada fila (para no chocar con ids ya existentes). Solo usa las
    columnas que realmente existen en la tabla — tolera archivos con
    columnas de más o de menos."""
    if df is None or df.empty:
        return 0
    columnas_reales = _columnas_tabla(conn, tabla)
    columnas_datos = [c for c in df.columns if c in columnas_reales and c != "id"]
    if not columnas_datos:
        return 0
    insertadas = 0
    placeholders = ",".join("?" * len(columnas_datos))
    for _, fila in df.iterrows():
        valores = []
        for col in columnas_datos:
            v = fila[col]
            if col == "proyecto_id":
                v = nuevo_proyecto_id
            valores.append(None if pd.isna(v) else v)
        conn.execute(
            f"INSERT INTO {tabla}({','.join(columnas_datos)}) VALUES ({placeholders})",
            valores)
        insertadas += 1
    return insertadas


def importar_proyecto(hojas: dict, usuario: dict, nombre_override: str = "") -> dict:
    """Recrea un proyecto completo a partir de un diccionario
    {nombre_tabla: DataFrame} — típicamente leído con `leer_excel_subido`
    o `leer_zip_csv_subido`. SIEMPRE crea un proyecto NUEVO (nunca
    sobreescribe uno existente), asignado al usuario que importa. Devuelve
    un resumen con el nuevo id y cuántas filas se insertaron en cada tabla,
    o {'error': ...} si el archivo no trae los datos mínimos."""
    df_proy = hojas.get("proyecto")
    if df_proy is None:
        df_proy = hojas.get("Proyecto")
    if df_proy is None or df_proy.empty:
        return {"error": "El archivo no tiene una hoja/CSV 'Proyecto' con datos. "
                          "Usa un archivo exportado desde este mismo módulo."}

    fila_p = df_proy.iloc[0].to_dict()
    nombre_final = (nombre_override or "").strip() or \
        f"{fila_p.get('nombre', 'Proyecto importado')} (importado)"

    conn = get_conn()
    columnas_proy = _columnas_tabla(conn, "proyectos")

    # No se copian: id (se asigna uno nuevo), creado_por_id/creado_por
    # (pasan a ser de quien importa), creado (fecha de hoy) y cliente_id
    # (no tiene sentido re-vincular a un cliente que puede ni siquiera
    # existir en esta instalación).
    campos = {}
    for col in columnas_proy:
        if col in ("id", "creado_por_id", "creado_por", "creado", "cliente_id"):
            continue
        if col in fila_p and not pd.isna(fila_p[col]):
            campos[col] = fila_p[col]
    campos["nombre"] = nombre_final
    if "creado_por_id" in columnas_proy:
        campos["creado_por_id"] = usuario.get("id")
    if "creado_por" in columnas_proy:
        campos["creado_por"] = usuario.get("username")

    cols_sql = ",".join(campos.keys())
    placeholders = ",".join("?" * len(campos))
    conn.execute(f"INSERT INTO proyectos({cols_sql}) VALUES ({placeholders})",
                 list(campos.values()))
    conn.commit()
    nuevo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    resumen = {"proyecto_id": nuevo_id, "nombre": nombre_final, "tablas": {}}
    for tabla, df in hojas.items():
        if tabla.lower() == "proyecto":
            continue
        try:
            n = _insertar_dataframe(conn, tabla.lower(), df, nuevo_id)
            if n:
                resumen["tablas"][tabla] = n
        except Exception as e:
            resumen.setdefault("errores", []).append(f"{tabla}: {e}")
    conn.commit()
    conn.close()
    return resumen


# ═══════════════════════════════════════════════════════════════════════════
# INTERFAZ
# ═══════════════════════════════════════════════════════════════════════════
def mostrar_backup_proyecto(proyecto_id=None):
    from modulo_seguridad import usuario_activo, registrar_auditoria

    _u = usuario_activo()
    if not _u:
        st.warning("Debes iniciar sesión para exportar o importar un proyecto.")
        return

    st.markdown("""
    <div class='hero-header'>
        <div class='hero-title'>📦 EXPORTAR / IMPORTAR PROYECTO</div>
        <div class='hero-sub'>RESPALDO COMPLETO · TRASLADO ENTRE INSTALACIONES</div>
    </div>""", unsafe_allow_html=True)

    tab_exp, tab_imp = st.tabs(["⬇ Exportar proyecto", "⬆ Importar proyecto"])

    # ── Exportar ─────────────────────────────────────────────────────────────
    with tab_exp:
        if not proyecto_id:
            st.info("Selecciona un proyecto en el panel lateral para poder exportarlo. "
                     "Para importar uno nuevo no hace falta tener uno seleccionado — "
                     "usa la pestaña “⬆ Importar proyecto”.")
        else:
            conn = get_conn()
            p = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
            conn.close()
            if not p:
                st.error("El proyecto seleccionado ya no existe.")
            else:
                datos = obtener_datos_proyecto(proyecto_id)
                st.markdown(f"**Proyecto:** {p[1]}  ·  **Municipio:** {p[2] or '—'}")
                resumen_tablas = ", ".join(
                    f"{t}: {len(df)}" for t, df in datos.items()
                    if t != "proyecto" and not df.empty)
                st.caption(f"Incluye: {resumen_tablas or 'solo los datos generales del proyecto'}.")

                colx1, colx2 = st.columns(2)
                with colx1:
                    st.download_button(
                        "📊 Descargar todo en Excel (.xlsx)",
                        data=exportar_excel(proyecto_id),
                        file_name=f"SolarCalc_Proyecto_{p[1].replace(' ','_')}_"
                                  f"{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="dl_backup_excel")
                with colx2:
                    st.download_button(
                        "📄 Descargar todo en CSV (.zip)",
                        data=exportar_csv_zip(proyecto_id),
                        file_name=f"SolarCalc_Proyecto_{p[1].replace(' ','_')}_"
                                  f"{datetime.now().strftime('%Y%m%d')}.zip",
                        mime="application/zip",
                        use_container_width=True, key="dl_backup_zip")
                st.caption("El .zip trae un archivo .csv por cada tabla del proyecto — "
                           "un solo .csv no puede contener varias tablas a la vez.")

    # ── Importar ─────────────────────────────────────────────────────────────
    with tab_imp:
        st.caption(
            "Sube un archivo .xlsx o .zip exportado desde aquí (de este proyecto, de otro, "
            "o incluso de otra instalación de SolarCalc Pro) para recrear el proyecto "
            "completo — datos generales, cargas, panel, resultados, recibos y baterías — "
            "sin tener que volver a capturar nada. Siempre se crea un proyecto **nuevo**, "
            "nunca se sobreescribe uno existente.")

        archivo = st.file_uploader("Archivo .xlsx o .zip", type=["xlsx", "zip"],
                                    key="backup_uploader")
        nombre_nuevo = st.text_input(
            "Nombre del proyecto importado (opcional — vacío usa el nombre "
            "original + \"(importado)\")", key="backup_nombre_override")

        if archivo is not None:
            hojas = None
            try:
                if archivo.name.lower().endswith(".zip"):
                    hojas = leer_zip_csv_subido(archivo)
                else:
                    hojas = leer_excel_subido(archivo)
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")

            if hojas:
                clave_proy = "proyecto" if "proyecto" in hojas else (
                    "Proyecto" if "Proyecto" in hojas else None)
                if not clave_proy or hojas[clave_proy].empty:
                    st.error("El archivo no contiene una tabla 'Proyecto' con datos — "
                             "asegúrate de subir un archivo exportado desde aquí.")
                else:
                    st.markdown("**Vista previa del proyecto a importar:**")
                    st.dataframe(hojas[clave_proy], use_container_width=True, hide_index=True)
                    resumen_prev = ", ".join(
                        f"{t}: {len(df)} fila(s)" for t, df in hojas.items()
                        if t.lower() != "proyecto" and not df.empty)
                    if resumen_prev:
                        st.caption(f"También incluye: {resumen_prev}")

                    if st.button("⬆ Confirmar importación", use_container_width=True,
                                 key="btn_confirmar_import_proy"):
                        resultado = importar_proyecto(hojas, _u, nombre_nuevo)
                        if resultado.get("error"):
                            st.error(resultado["error"])
                        else:
                            registrar_auditoria(
                                _u["id"], _u["username"], "IMPORTAR_PROYECTO",
                                f"Proyecto #{resultado['proyecto_id']} "
                                f"'{resultado['nombre']}' importado "
                                f"({resultado['tablas']})", "backup_proyecto")
                            if resultado.get("errores"):
                                for err in resultado["errores"]:
                                    st.warning(f"⚠ {err}")
                            st.success(
                                f"✓ Proyecto '{resultado['nombre']}' creado "
                                f"(#{resultado['proyecto_id']}).")
                            st.session_state["sel_proyecto"] = \
                                f"{resultado['proyecto_id']} | {resultado['nombre']}"
                            st.rerun()
