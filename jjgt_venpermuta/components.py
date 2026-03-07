"""
JJGT — components.py
Helpers visuales compartidos entre páginas.
Las tarjetas de vehículos se renderizan con st.container() nativo
para evitar que el HTML se muestre como texto plano.
"""

# Paleta de gradientes para las tarjetas
GRAD_COLORS = [
    ("#C41E3A", "#1A1A2E"), ("#1A1A2E", "#2E2E5A"), ("#00C9A7", "#007A65"),
    ("#F5A623", "#C47D00"), ("#2979FF", "#1A4BAA"), ("#9C27B0", "#6A1B9A"),
    ("#FF6B35", "#C41E3A"), ("#1A1A2E", "#C41E3A"), ("#00897B", "#004D40"),
    ("#F5A623", "#1A1A2E"), ("#C41E3A", "#9B1729"), ("#3F51B5", "#1A237E"),
    ("#00C9A7", "#1A1A2E"), ("#FF5722", "#BF360C"), ("#607D8B", "#263238"),
]

def grad(index: int):
    return GRAD_COLORS[index % len(GRAD_COLORS)]


def fmt_price(p: int) -> str:
    if p >= 1_000_000:
        return f"${p / 1_000_000:.0f} M"
    return f"${p:,}"


def permuta_card_html(v: dict) -> str:
    """HTML para tarjeta de permuta (usada con unsafe_allow_html=True)."""
    c1, c2 = grad(v.get("grad", 0))
    name  = v.get("name", "")
    model = v.get("model", "")
    year  = v.get("year", "")
    price = v.get("price", 0)
    city  = v.get("city", "")
    km    = v.get("km", 0)
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
