# ══════════════════════════════════════════════════════════════════════════════
# pqrs.py — Módulo de Peticiones, Quejas, Reclamos y Sugerencias (PQRS)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Archivo independiente que se importa, carga y ejecuta desde pagos.py
#  (mismo patrón que facturacion_cartera.py: set_context(globals()) inyecta
#  las funciones y constantes del host, y este módulo las consume vía _g()).
#
#  Funcionalidad:
#    · Crear   — registrar una nueva PQRS (basado en el formato PQRS-001 de
#                 Suite Salitre VIP S.A.S.: tipo de solicitud, datos del
#                 cliente, información del servicio/reserva, descripción,
#                 pretensión, prioridad, etc.)
#    · Listar / filtrar — por estado, tipo, prioridad o texto libre.
#    · Modificar — estado, prioridad, área/funcionario responsable, respuesta,
#                 decisión.
#    · Borrar    — con confirmación explícita.
#    · Responder — envía la respuesta por correo electrónico al cliente
#                 solicitante (reutiliza el mecanismo de envío de correo del
#                 host — yagmail / secrets.toml → [emails]) y deja constancia
#                 en la propia PQRS (fecha, medio y texto de la respuesta).
#
#  Requiere que pagos.py inyecte, vía set_context(globals()), al menos:
#    _pg_exec, get_config, set_config, ahora_col, fmt_cop,
#    NEGOCIO, DIRECCION, TELEFONO, NIT, EMAIL,
#    YAGMAIL_AVAILABLE, enviar_factura_email, smtp_disponible,
#    gs_escribir_log, get_active_client
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st

# ── Inyección de contexto (mismo patrón que facturacion_cartera.py) ─────────
_ctx = {}


def set_context(ctx: dict):
    global _ctx
    _ctx = ctx


def _g(name, default=None):
    """Obtiene un símbolo del contexto inyectado por el host (pagos.py).
    Si no está y no se dio default, lanza un error claro."""
    if name in _ctx and _ctx[name] is not None:
        return _ctx[name]
    if default is not None:
        return default
    raise RuntimeError(
        f"pqrs.py: símbolo '{name}' no está en el contexto. "
        "¿Se llamó a pqrs.set_context(globals()) desde pagos.py?"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CAPA DE DATOS — tabla propia en PostgreSQL (misma base que usa pagos.py)
# ══════════════════════════════════════════════════════════════════════════════

_CREATE_TABLE_PQRS = """
CREATE TABLE IF NOT EXISTS pqrs (
    id_pqrs                  TEXT PRIMARY KEY,
    creado_en                TEXT,
    actualizado_en           TEXT,
    tipo                     TEXT,
    medio_recepcion          TEXT,
    cliente_nombre           TEXT,
    tipo_doc                 TEXT,
    documento                TEXT,
    telefono                 TEXT,
    email                    TEXT,
    ciudad                   TEXT,
    empresa                  TEXT,
    numero_reserva           TEXT,
    num_factura               TEXT,
    cubiculo                 TEXT,
    medio_pago                TEXT,
    descripcion               TEXT,
    pretension                TEXT,
    prioridad                 TEXT DEFAULT 'Media',
    area_responsable          TEXT,
    estado                    TEXT DEFAULT 'Recibida',
    funcionario_responsable   TEXT,
    respuesta                 TEXT,
    fecha_respuesta           TEXT,
    medio_respuesta           TEXT,
    medio_pref_respuesta      TEXT,
    decision                  TEXT,
    operador                  TEXT
);
"""

_TABLA_LISTA = False


def _ensure_tabla():
    """Crea la tabla `pqrs` si no existe. Se ejecuta una sola vez por sesión."""
    global _TABLA_LISTA
    if _TABLA_LISTA:
        return
    _pg_exec = _g("_pg_exec")
    try:
        _pg_exec(_CREATE_TABLE_PQRS)
        _TABLA_LISTA = True
    except Exception as e:
        st.error(f"❌ Error creando la tabla `pqrs`: {e}")


TIPOS_PQRS      = ["Petición", "Queja", "Reclamo", "Sugerencia", "Felicitación", "Otro"]
MEDIOS_RECEPCION = ["Formulario web", "Correo electrónico", "Presencial", "Teléfono",
                    "WhatsApp", "Redes sociales", "Buzón de PQRS", "Otro"]
PRIORIDADES     = ["Baja", "Media", "Alta", "Crítica"]
ESTADOS         = ["Recibida", "En revisión", "En gestión",
                    "Pendiente de información del cliente", "Respondida", "Cerrada"]
AREAS           = ["Servicio al Cliente", "Administración", "Operaciones",
                    "Contabilidad", "Facturación", "Gerencia", "Jurídica",
                    "Tecnología", "Otra"]
MEDIOS_PAGO     = ["Efectivo", "Tarjeta", "Transferencia", "PSE", "Convenio empresarial", "Otro"]
MEDIOS_RESPUESTA = ["Correo electrónico", "WhatsApp", "Teléfono", "Presencial", "Carta", "Otro"]
DECISIONES = [
    "Solicitud atendida favorablemente", "Solicitud atendida parcialmente",
    "Solicitud no favorable", "Información suministrada",
    "Reclamo aceptado", "Reclamo parcialmente aceptado", "Reclamo no aceptado",
    "Queja atendida", "Sugerencia recibida y trasladada al área correspondiente",
    "No procede", "Requiere gestión adicional", "Otro",
]


def generar_numero_pqrs() -> str:
    """Folio con formato PQRS-<año>-<secuencial de 4 dígitos>."""
    _ensure_tabla()
    _pg_exec = _g("_pg_exec")
    ahora_col = _g("ahora_col")
    year = ahora_col().year
    try:
        row = _pg_exec(
            "SELECT COUNT(*) AS n FROM pqrs WHERE id_pqrs LIKE %s",
            (f"PQRS-{year}-%",), fetch="one",
        )
        n = int(row["n"]) + 1 if row else 1
    except Exception:
        n = 1
    return f"PQRS-{year}-{n:04d}"


def crear_pqrs(datos: dict) -> str:
    """Inserta una nueva PQRS. Retorna el folio (id_pqrs) generado."""
    _ensure_tabla()
    _pg_exec  = _g("_pg_exec")
    ahora_col = _g("ahora_col")
    folio = generar_numero_pqrs()
    ahora = ahora_col().isoformat()
    _pg_exec(
        """
        INSERT INTO pqrs (
            id_pqrs, creado_en, actualizado_en, tipo, medio_recepcion,
            cliente_nombre, tipo_doc, documento, telefono, email, ciudad, empresa,
            numero_reserva, num_factura, cubiculo, medio_pago,
            descripcion, pretension, prioridad, area_responsable, estado,
            funcionario_responsable, medio_pref_respuesta, operador
        ) VALUES (
            %s,%s,%s,%s,%s, %s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,
            %s,%s,%s,%s,%s, %s,%s,%s
        )
        """,
        (
            folio, ahora, ahora, datos.get("tipo",""), datos.get("medio_recepcion",""),
            datos.get("cliente_nombre",""), datos.get("tipo_doc",""), datos.get("documento",""),
            datos.get("telefono",""), datos.get("email",""), datos.get("ciudad",""),
            datos.get("empresa",""),
            datos.get("numero_reserva",""), datos.get("num_factura",""),
            datos.get("cubiculo",""), datos.get("medio_pago",""),
            datos.get("descripcion",""), datos.get("pretension",""),
            datos.get("prioridad","Media"), datos.get("area_responsable",""),
            datos.get("estado","Recibida"),
            datos.get("funcionario_responsable",""),
            datos.get("medio_pref_respuesta",""), datos.get("operador",""),
        ),
    )
    try:
        sh_log = _g("get_active_client")()[1]
        _g("gs_escribir_log")(
            sh_log, "pqrs_creada", folio, "-",
            datos.get("operador","sistema"),
            f"PQRS {folio} creada ({datos.get('tipo','')}) — {datos.get('cliente_nombre','')}",
        )
    except Exception:
        pass
    return folio


def listar_pqrs(estado: str = "Todos", tipo: str = "Todos", busqueda: str = "") -> list:
    """Lista PQRS con filtros opcionales, más recientes primero."""
    _ensure_tabla()
    _pg_exec = _g("_pg_exec")
    sql = "SELECT * FROM pqrs WHERE 1=1"
    params = []
    if estado and estado != "Todos":
        sql += " AND estado = %s"
        params.append(estado)
    if tipo and tipo != "Todos":
        sql += " AND tipo = %s"
        params.append(tipo)
    if busqueda:
        sql += (" AND (id_pqrs ILIKE %s OR cliente_nombre ILIKE %s OR documento ILIKE %s "
                "OR numero_reserva ILIKE %s OR num_factura ILIKE %s OR email ILIKE %s "
                "OR telefono ILIKE %s)")
        like = f"%{busqueda}%"
        params += [like] * 7
    sql += " ORDER BY creado_en DESC"
    try:
        return _pg_exec(sql, tuple(params) if params else None, fetch="all") or []
    except Exception as e:
        st.error(f"❌ Error consultando PQRS: {e}")
        return []


def obtener_pqrs(id_pqrs: str) -> dict:
    _ensure_tabla()
    _pg_exec = _g("_pg_exec")
    try:
        return _pg_exec("SELECT * FROM pqrs WHERE id_pqrs = %s", (id_pqrs,), fetch="one")
    except Exception:
        return None


def actualizar_pqrs(id_pqrs: str, cambios: dict, operador: str = "") -> bool:
    """Actualiza cualquier subconjunto de columnas de una PQRS existente."""
    if not cambios:
        return True
    _ensure_tabla()
    _pg_exec  = _g("_pg_exec")
    ahora_col = _g("ahora_col")
    cambios = dict(cambios)
    cambios["actualizado_en"] = ahora_col().isoformat()
    set_clause = ", ".join(f"{col} = %s" for col in cambios.keys())
    params = list(cambios.values()) + [id_pqrs]
    try:
        _pg_exec(f"UPDATE pqrs SET {set_clause} WHERE id_pqrs = %s", tuple(params))
        try:
            sh_log = _g("get_active_client")()[1]
            _g("gs_escribir_log")(
                sh_log, "pqrs_actualizada", id_pqrs, "-", operador or "sistema",
                f"PQRS {id_pqrs} actualizada: {', '.join(cambios.keys())}",
            )
        except Exception:
            pass
        return True
    except Exception as e:
        st.error(f"❌ Error actualizando PQRS: {e}")
        return False


def eliminar_pqrs(id_pqrs: str, operador: str = "") -> bool:
    _ensure_tabla()
    _pg_exec = _g("_pg_exec")
    try:
        _pg_exec("DELETE FROM pqrs WHERE id_pqrs = %s", (id_pqrs,))
        try:
            sh_log = _g("get_active_client")()[1]
            _g("gs_escribir_log")(
                sh_log, "pqrs_eliminada", id_pqrs, "-", operador or "sistema",
                f"PQRS {id_pqrs} eliminada", estado="exito",
            )
        except Exception:
            pass
        return True
    except Exception as e:
        st.error(f"❌ Error eliminando PQRS: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# RESPUESTA POR CORREO ELECTRÓNICO AL CLIENTE
# ══════════════════════════════════════════════════════════════════════════════

def enviar_respuesta_pqrs(pqrs: dict, texto_respuesta: str, operador: str = "") -> tuple:
    """
    Envía la respuesta de una PQRS por correo electrónico al cliente solicitante
    (reutiliza el mismo mecanismo de envío — yagmail — que usa el resto de la
    suite), y deja constancia de la respuesta en la propia PQRS.
    Retorna (exito: bool, mensaje: str).
    """
    destinatario = (pqrs.get("email") or "").strip()
    if not destinatario or "@" not in destinatario:
        return False, "El cliente no tiene un correo electrónico válido registrado en la PQRS."
    if not texto_respuesta.strip():
        return False, "Escribe el contenido de la respuesta antes de enviarla."

    YAGMAIL_AVAILABLE = _g("YAGMAIL_AVAILABLE", False)
    if not YAGMAIL_AVAILABLE:
        return False, "Falta instalar la librería `yagmail` (pip install yagmail)."
    if not _g("smtp_disponible")():
        return False, ("Falta configurar el correo remitente en "
                        "`.streamlit/secrets.toml` → sección [emails] "
                        "(smtp_user / smtp_password).")

    NEGOCIO   = _g("NEGOCIO", "")
    DIRECCION = _g("DIRECCION", "")
    TELEFONO  = _g("TELEFONO", "")
    NIT       = _g("NIT", "")
    ahora_col = _g("ahora_col")
    enviar_factura_email = _g("enviar_factura_email")
    _smtp_config = _g("_smtp_config")

    asunto = f"Respuesta a su {pqrs.get('tipo','PQRS')} {pqrs.get('id_pqrs','')} · {NEGOCIO}"
    cuerpo = (
        f"Estimado(a) {pqrs.get('cliente_nombre','')},\n\n"
        f"En relación con su {pqrs.get('tipo','solicitud').lower()} radicada con el número "
        f"{pqrs.get('id_pqrs','')} el {(pqrs.get('creado_en') or '')[:10]}, nos permitimos informarle "
        f"lo siguiente:\n\n"
        f"{texto_respuesta.strip()}\n\n"
        f"Si tiene alguna inquietud adicional, no dude en contactarnos.\n\n"
        f"Atentamente,\n"
        f"{NEGOCIO}\n{DIRECCION} · Tel: {TELEFONO} · {NIT}"
    )

    cfg = _smtp_config()
    enviado = enviar_factura_email(
        destinatario=destinatario,
        asunto=asunto,
        cuerpo=cuerpo,
        pdf_bytes=b"",  # respuesta de PQRS: sin adjunto
        nombre_pdf="",
        email_from=cfg["email_from"],
        nombre_from=cfg["nombre_from"],
    )

    if not enviado:
        return False, f"❌ Error enviando la respuesta a {destinatario} (revisa la consola/logs)."

    actualizar_pqrs(pqrs["id_pqrs"], {
        "respuesta":       texto_respuesta.strip(),
        "fecha_respuesta": ahora_col().isoformat(),
        "medio_respuesta": "Correo electrónico",
        "estado":          "Respondida",
    }, operador=operador)

    return True, f"✅ Respuesta enviada por correo a {destinatario} y PQRS marcada como Respondida."


# ══════════════════════════════════════════════════════════════════════════════
# INTERFAZ — PANEL PQRS (Streamlit)
# ══════════════════════════════════════════════════════════════════════════════

def _badge_estado(estado: str) -> str:
    colores = {
        "Recibida": "#94a3b8", "En revisión": "#f59e0b", "En gestión": "#3b82f6",
        "Pendiente de información del cliente": "#a855f7",
        "Respondida": "#22c55e", "Cerrada": "#64748b",
    }
    c = colores.get(estado, "#94a3b8")
    return (f'<span style="background:{c}22;border:1px solid {c};color:{c};'
            f'padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600">{estado}</span>')


def _badge_prioridad(prioridad: str) -> str:
    colores = {"Baja": "#22c55e", "Media": "#3b82f6", "Alta": "#f59e0b", "Crítica": "#ef4444"}
    c = colores.get(prioridad, "#94a3b8")
    return (f'<span style="background:{c}22;border:1px solid {c};color:{c};'
            f'padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600">{prioridad}</span>')


def render_panel_pqrs():
    """Punto de entrada del módulo — se llama desde pagos.py (_op_pqrs)."""
    _ensure_tabla()

    st.markdown("### 📮 PQRS — Peticiones, Quejas, Reclamos y Sugerencias")
    st.caption("Registro, gestión y respuesta de PQRS de acuerdo con el formato "
               "PQRS-001 de Suite Salitre VIP S.A.S.")

    op_info = st.session_state.get("operador_info", {})
    operador_actual = op_info.get("nombre", "sistema")

    tab_lista, tab_nueva = st.tabs(["📋 Gestión de PQRS", "➕ Nueva PQRS"])

    # ── TAB: NUEVA PQRS ──────────────────────────────────────────────────
    with tab_nueva:
        st.markdown("#### Registrar nueva PQRS")
        with st.form("form_nueva_pqrs", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                tipo = st.selectbox("Tipo de solicitud *", TIPOS_PQRS)
                medio_recepcion = st.selectbox("Medio de recepción", MEDIOS_RECEPCION)
                prioridad = st.selectbox("Prioridad", PRIORIDADES, index=1)
            with c2:
                area_responsable = st.selectbox("Área responsable", AREAS)
                medio_pref_respuesta = st.selectbox("Medio preferido de respuesta", MEDIOS_RESPUESTA)
                medio_pago = st.selectbox("Medio de pago (si aplica)", [""] + MEDIOS_PAGO)
            with c3:
                numero_reserva = st.text_input("N° de reserva (si aplica)")
                num_factura    = st.text_input("N° de factura (si aplica)")
                cubiculo       = st.text_input("Cubículo / espacio (si aplica)")

            st.markdown("**Datos del cliente**")
            c4, c5, c6 = st.columns(3)
            with c4:
                cliente_nombre = st.text_input("Nombre completo *")
                tipo_doc       = st.selectbox("Tipo de documento", ["C.C.", "C.E.", "NIT", "Pasaporte", "Otro"])
            with c5:
                documento = st.text_input("Número de documento")
                telefono  = st.text_input("Teléfono")
            with c6:
                email   = st.text_input("Correo electrónico *")
                ciudad  = st.text_input("Ciudad")
            empresa = st.text_input("Empresa (si aplica — convenio empresarial)")

            st.markdown("**Descripción de la PQRS**")
            descripcion = st.text_area("Describa la situación (hechos, fecha, hora, lugar, personas involucradas)", height=120)
            pretension  = st.text_area("¿Qué solución, respuesta o actuación solicita?", height=80)

            enviar = st.form_submit_button("📮 Registrar PQRS", type="primary", use_container_width=True)

            if enviar:
                if not cliente_nombre.strip():
                    st.error("El nombre del cliente es obligatorio.")
                elif not email.strip() or "@" not in email:
                    st.error("Ingresa un correo electrónico válido del cliente (necesario para poder responderle).")
                elif not descripcion.strip():
                    st.error("Describe la situación de la PQRS.")
                else:
                    folio = crear_pqrs({
                        "tipo": tipo, "medio_recepcion": medio_recepcion,
                        "cliente_nombre": cliente_nombre.strip(), "tipo_doc": tipo_doc,
                        "documento": documento.strip(), "telefono": telefono.strip(),
                        "email": email.strip(), "ciudad": ciudad.strip(), "empresa": empresa.strip(),
                        "numero_reserva": numero_reserva.strip(), "num_factura": num_factura.strip(),
                        "cubiculo": cubiculo.strip(), "medio_pago": medio_pago,
                        "descripcion": descripcion.strip(), "pretension": pretension.strip(),
                        "prioridad": prioridad, "area_responsable": area_responsable,
                        "estado": "Recibida", "medio_pref_respuesta": medio_pref_respuesta,
                        "operador": operador_actual,
                    })
                    st.success(f"✅ PQRS registrada con folio **{folio}**")

    # ── TAB: GESTIÓN / LISTADO ───────────────────────────────────────────
    with tab_lista:
        c_f1, c_f2, c_f3 = st.columns([1, 1, 2])
        with c_f1:
            f_estado = st.selectbox("Estado", ["Todos"] + ESTADOS, key="pqrs_f_estado")
        with c_f2:
            f_tipo = st.selectbox("Tipo", ["Todos"] + TIPOS_PQRS, key="pqrs_f_tipo")
        with c_f3:
            f_busqueda = st.text_input(
                "Buscar (folio, cliente, documento, reserva, factura, correo, teléfono)",
                key="pqrs_f_busqueda",
            )

        filas = listar_pqrs(f_estado, f_tipo, f_busqueda)
        st.caption(f"{len(filas)} PQRS encontradas")

        if not filas:
            st.info("No hay PQRS que coincidan con los filtros seleccionados.")
            return

        opciones = {
            f"{r['id_pqrs']} · {r.get('tipo','')} · {r.get('cliente_nombre','')} · "
            f"{r.get('estado','')} · {(r.get('creado_en') or '')[:10]}": r
            for r in filas[:200]
        }
        etiqueta_sel = st.selectbox("Selecciona una PQRS", list(opciones.keys()), key="pqrs_sel")
        pqrs = opciones[etiqueta_sel]

        st.divider()
        col_izq, col_der = st.columns([1, 1])

        with col_izq:
            st.markdown(f"#### 🧾 {pqrs['id_pqrs']}")
            st.markdown(
                f"{_badge_estado(pqrs.get('estado',''))} &nbsp; {_badge_prioridad(pqrs.get('prioridad',''))}",
                unsafe_allow_html=True,
            )
            st.markdown(f"""
            <div style="background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.25);
                        border-radius:12px;padding:14px;font-size:14px;margin-top:8px">
              <div><b>Tipo:</b> {pqrs.get('tipo','')} · <b>Medio:</b> {pqrs.get('medio_recepcion','')}</div>
              <div><b>Cliente:</b> {pqrs.get('cliente_nombre','')} · {pqrs.get('tipo_doc','')} {pqrs.get('documento','')}</div>
              <div><b>Contacto:</b> {pqrs.get('email','')} · {pqrs.get('telefono','')}</div>
              <div><b>Empresa:</b> {pqrs.get('empresa','') or '—'}</div>
              <div><b>Reserva:</b> {pqrs.get('numero_reserva','') or '—'} · <b>Factura:</b> {pqrs.get('num_factura','') or '—'} · <b>Cubículo:</b> {pqrs.get('cubiculo','') or '—'}</div>
              <div><b>Creado:</b> {(pqrs.get('creado_en') or '')[:19].replace('T',' ')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**Descripción**")
            st.write(pqrs.get("descripcion", "") or "—")
            st.markdown("**Pretensión del cliente**")
            st.write(pqrs.get("pretension", "") or "—")

            if pqrs.get("respuesta"):
                st.markdown("**Última respuesta enviada**")
                st.success(pqrs["respuesta"])
                st.caption(f"Enviada el {(pqrs.get('fecha_respuesta') or '')[:19].replace('T',' ')} "
                           f"por {pqrs.get('medio_respuesta','')}")

        with col_der:
            st.markdown("#### ✏️ Gestionar")
            n_estado = st.selectbox("Estado", ESTADOS,
                                     index=ESTADOS.index(pqrs["estado"]) if pqrs.get("estado") in ESTADOS else 0,
                                     key=f"pqrs_estado_{pqrs['id_pqrs']}")
            n_prioridad = st.selectbox("Prioridad", PRIORIDADES,
                                        index=PRIORIDADES.index(pqrs["prioridad"]) if pqrs.get("prioridad") in PRIORIDADES else 1,
                                        key=f"pqrs_prio_{pqrs['id_pqrs']}")
            n_area = st.selectbox("Área responsable", AREAS,
                                   index=AREAS.index(pqrs["area_responsable"]) if pqrs.get("area_responsable") in AREAS else 0,
                                   key=f"pqrs_area_{pqrs['id_pqrs']}")
            n_funcionario = st.text_input("Funcionario responsable",
                                           value=pqrs.get("funcionario_responsable", "") or "",
                                           key=f"pqrs_func_{pqrs['id_pqrs']}")
            n_decision = st.selectbox("Decisión / resultado", [""] + DECISIONES,
                                       index=(([""] + DECISIONES).index(pqrs["decision"])
                                              if pqrs.get("decision") in DECISIONES else 0),
                                       key=f"pqrs_decision_{pqrs['id_pqrs']}")

            if st.button("💾 Guardar cambios", use_container_width=True, key=f"pqrs_save_{pqrs['id_pqrs']}"):
                ok = actualizar_pqrs(pqrs["id_pqrs"], {
                    "estado": n_estado, "prioridad": n_prioridad,
                    "area_responsable": n_area, "funcionario_responsable": n_funcionario,
                    "decision": n_decision,
                }, operador=operador_actual)
                if ok:
                    st.success("✅ PQRS actualizada")
                    st.rerun()

            st.divider()
            st.markdown("#### 📧 Responder por correo electrónico")
            texto_resp = st.text_area("Contenido de la respuesta para el cliente",
                                       value=pqrs.get("respuesta", "") or "",
                                       height=140, key=f"pqrs_resp_{pqrs['id_pqrs']}")
            smtp_ok = _g("smtp_disponible")()
            if not smtp_ok:
                st.caption("⚠️ Correo no configurado (ver ⚙️ Configuración → 📧 Envíos en pagos.py).")
            if st.button("✉️ Enviar respuesta al cliente", type="primary",
                          use_container_width=True, disabled=not smtp_ok,
                          key=f"pqrs_send_{pqrs['id_pqrs']}"):
                ok, mensaje = enviar_respuesta_pqrs(pqrs, texto_resp, operador=operador_actual)
                (st.success if ok else st.error)(mensaje)
                if ok:
                    st.rerun()

            st.divider()
            st.markdown("#### 🗑️ Eliminar PQRS")
            confirm_key = f"pqrs_confirm_del_{pqrs['id_pqrs']}"
            confirmar = st.checkbox(f"Confirmo que deseo eliminar {pqrs['id_pqrs']} permanentemente",
                                     key=confirm_key)
            if st.button("🗑️ Eliminar definitivamente", use_container_width=True,
                          disabled=not confirmar, key=f"pqrs_del_{pqrs['id_pqrs']}"):
                if eliminar_pqrs(pqrs["id_pqrs"], operador=operador_actual):
                    st.success(f"✅ {pqrs['id_pqrs']} eliminada")
                    st.rerun()
