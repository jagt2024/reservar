"""
JJGT — components.py
Helpers visuales compartidos entre páginas.

Las tarjetas de vehículos se renderizan con st.container() nativo
para evitar que el HTML se muestre como texto plano.

Paleta de marca:
    --jjgt-red:   #C41E3A
    --jjgt-gold:  #F5A623
    --jjgt-navy:  #1A1A2E
"""

# ── Paleta de gradientes para tarjetas ────────────────────────────────────────
GRAD_COLORS = [
    ("#C41E3A", "#1A1A2E"), ("#1A1A2E", "#2E2E5A"), ("#00C9A7", "#007A65"),
    ("#F5A623", "#C47D00"), ("#2979FF", "#1A4BAA"), ("#9C27B0", "#6A1B9A"),
    ("#FF6B35", "#C41E3A"), ("#1A1A2E", "#C41E3A"), ("#00897B", "#004D40"),
    ("#F5A623", "#1A1A2E"), ("#C41E3A", "#9B1729"), ("#3F51B5", "#1A237E"),
    ("#00C9A7", "#1A1A2E"), ("#FF5722", "#BF360C"), ("#607D8B", "#263238"),
]


def grad(index: int) -> tuple[str, str]:
    """Retorna el par de colores (inicio, fin) para el gradiente en `index`."""
    return GRAD_COLORS[index % len(GRAD_COLORS)]


# ── Formateo de precios ───────────────────────────────────────────────────────
def fmt_price(p: int | float) -> str:
    """
    Formatea un precio en pesos colombianos.
    - Valores >= 1.000.000 → "$X M"
    - Valores menores     → "$X,XXX" con separador de miles
    """
    try:
        p = int(p)
    except (TypeError, ValueError):
        return "$0"
    if p >= 1_000_000:
        return f"${p / 1_000_000:.1f} M".replace(".0 ", " ")
    return f"${p:,}"


# ── Tarjeta de permuta ────────────────────────────────────────────────────────
def permuta_card_html(v: dict) -> str:
    """
    Genera HTML para tarjeta de permuta.
    Se usa con `st.markdown(..., unsafe_allow_html=True)`.

    Campos esperados en `v`:
        grad   (int)  — índice de gradiente
        name   (str)  — marca del vehículo
        model  (str)  — modelo
        year   (int)  — año
        price  (int)  — precio COP
        city   (str)  — ciudad
        km     (int)  — kilometraje
    """
    c1, c2 = grad(v.get("grad", 0))
    name  = v.get("name",  "")
    model = v.get("model", "")
    year  = v.get("year",  "")
    price = v.get("price", 0)
    city  = v.get("city",  "")
    km    = v.get("km",    0)
    return f"""
<div style="background:linear-gradient(135deg,{c1},{c2});border-radius:16px;
            padding:20px;margin-bottom:4px;color:#fff;position:relative;overflow:hidden;">
    <div style="position:absolute;right:-10px;top:-10px;font-size:60px;opacity:0.1;">🔄</div>
    <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;opacity:0.6;
                text-transform:uppercase;margin-bottom:6px;">Disponible para permuta</div>
    <div style="font-size:20px;font-weight:700;margin-bottom:4px;">{name} {model}</div>
    <div style="font-size:13px;opacity:0.7;margin-bottom:10px;">
        {year} · {city} · {km:,} km</div>
    <div style="font-size:26px;font-weight:900;">{fmt_price(price)}</div>
</div>"""


# ── Tarjeta de vehículo compacta (HTML) ───────────────────────────────────────
def vehicle_card_html(v: dict) -> str:
    """
    Genera HTML para tarjeta compacta de vehículo en listas/explorador.
    Se usa con `st.markdown(..., unsafe_allow_html=True)`.

    Campos esperados en `v`:
        grad       (int)  — índice de gradiente
        name       (str)  — marca
        model      (str)  — modelo
        year       (int)  — año
        price      (int)  — precio COP
        city       (str)  — ciudad
        km         (int)  — kilometraje
        type       (str)  — "venta" | "permuta" | "ambos"
        verificado (bool) — badge verificado
    """
    c1, c2    = grad(v.get("grad", 0))
    name      = v.get("name",  "")
    model     = v.get("model", "")
    year      = v.get("year",  "")
    price     = v.get("price", 0)
    city      = v.get("city",  "")
    km        = v.get("km",    0)
    vtype     = v.get("type",  "venta")
    verif     = v.get("verificado", False)

    tipo_label = {"venta": "Venta", "permuta": "Permuta", "ambos": "Venta · Permuta"}.get(vtype, "Venta")
    verif_html = '<span style="font-size:10px;background:#00C9A7;color:#fff;padding:2px 6px;border-radius:4px;margin-left:6px;">✓ Verificado</span>' if verif else ""

    return f"""
<div style="background:linear-gradient(135deg,{c1},{c2});border-radius:14px;
            padding:16px;margin-bottom:4px;color:#fff;position:relative;overflow:hidden;">
    <div style="position:absolute;right:-8px;top:-8px;font-size:50px;opacity:0.08;">🚗</div>
    <div style="font-size:10px;font-weight:700;letter-spacing:1.2px;opacity:0.65;
                text-transform:uppercase;margin-bottom:4px;">{tipo_label}{verif_html}</div>
    <div style="font-size:17px;font-weight:700;margin-bottom:2px;">{name} {model}</div>
    <div style="font-size:12px;opacity:0.7;margin-bottom:8px;">{year} · {city} · {km:,} km</div>
    <div style="font-size:22px;font-weight:900;">{fmt_price(price)}</div>
</div>"""


# ── Badge de estado de publicación ────────────────────────────────────────────
def status_badge_html(status: str) -> str:
    """
    Retorna un span HTML con el badge de estado de una publicación.

    Estados soportados: activa, pausada, completado, eliminado
    """
    paleta = {
        "activa":     ("#00C9A7", "✅ Activa"),
        "pausada":    ("#F5A623", "⏸️ Pausada"),
        "completado": ("#6B6B8A", "✔️ Completado"),
        "eliminado":  ("#C41E3A", "🗑️ Eliminado"),
    }
    color, label = paleta.get(status.lower(), ("#6B6B8A", status.capitalize()))
    return (
        f'<span style="background:{color};color:#fff;font-size:11px;font-weight:700;'
        f'padding:3px 8px;border-radius:6px;">{label}</span>'
    )
