"""
JJGT — Componentes HTML reutilizables para Streamlit
"""
from typing import Dict, List, Any

GRAD_COLORS = [
    ("#C41E3A","#1A1A2E"), ("#1A1A2E","#2E2E5A"), ("#00C9A7","#007A65"),
    ("#F5A623","#C47D00"), ("#2979FF","#1A4BAA"), ("#9C27B0","#6A1B9A"),
    ("#FF6B35","#C41E3A"), ("#1A1A2E","#C41E3A"), ("#00897B","#004D40"),
    ("#F5A623","#1A1A2E"), ("#C41E3A","#9B1729"), ("#3F51B5","#1A237E"),
    ("#00C9A7","#1A1A2E"), ("#FF5722","#BF360C"), ("#607D8B","#263238"),
]

def fmt_price(price: int) -> str:
    if price >= 1_000_000:
        return f"${price/1_000_000:.0f} M"
    return f"${price:,}"

def fmt_km(km: int) -> str:
    return f"{km:,} km"

def render_vehicle_card(v: Dict, compact: bool = False) -> str:
    g = v.get("grad", 0)
    c1, c2 = GRAD_COLORS[g % len(GRAD_COLORS)]
    name = v.get("name", v.get("marca",""))
    model = v.get("model", v.get("modelo",""))
    year = v.get("year", v.get("anio",""))
    price = v.get("price", v.get("precio", 0))
    city = v.get("city", v.get("ciudad",""))
    km = v.get("km", 0)
    fuel = v.get("fuel", v.get("comb",""))
    rating = v.get("rating", 0)
    tipo = v.get("type", "venta")
    is_user = v.get("isUserPub", False)

    tipo_labels = {"venta":"Venta","permuta":"Permuta","ambos":"V+P"}
    tipo_colors = {"venta":"#C41E3A","permuta":"#00C9A7","ambos":"#F5A623"}
    tc = tipo_colors.get(tipo, "#C41E3A")
    tl = tipo_labels.get(tipo, tipo)

    stars = "⭐" * int(rating) if rating else ""
    user_badge = '<span style="background:#9C27B0;color:#fff;font-size:9px;padding:2px 6px;border-radius:6px;margin-left:6px;">MIO</span>' if is_user else ""

    fotos = v.get("fotos",[])
    media_html = f"""
    <div style="background:linear-gradient(135deg,{c1},{c2});
                height:{160 if not compact else 120}px;
                display:flex;align-items:center;justify-content:center;
                font-size:{48 if not compact else 36}px;
                border-radius:14px 14px 0 0;">🚗</div>"""

    return f"""
<div style="background:#fff;border-radius:16px;overflow:hidden;
            box-shadow:0 4px 20px rgba(26,26,46,0.08);
            border:1px solid #E0E0EC;margin-bottom:4px;
            transition:transform 0.2s;">
    {media_html}
    <div style="padding:14px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div style="background:{tc}15;color:{tc};font-size:10px;font-weight:700;
                        padding:2px 8px;border-radius:6px;">{tl}</div>
            <div style="font-size:11px;color:#9999BB;">{year}</div>
        </div>
        <div style="font-weight:700;font-size:15px;color:#1A1A2E;margin:4px 0 2px;">
            {name} {model}{user_badge}</div>
        <div style="font-size:12px;color:#6B6B8A;margin-bottom:8px;">
            📍 {city} · {fmt_km(km)}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:22px;font-weight:800;color:#C41E3A;">{fmt_price(price)}</div>
            <div style="font-size:12px;color:#F5A623;">{stars}</div>
        </div>
        <div style="font-size:11px;color:#9999BB;margin-top:4px;">⛽ {fuel}</div>
    </div>
</div>"""


def render_hero_banner(logged_in: bool, user_name: str) -> str:
    if logged_in:
        return ""
    return """
<div style="background:linear-gradient(135deg,#1A1A2E,#2E2E5A);
            border-radius:20px;padding:28px;margin-bottom:20px;
            position:relative;overflow:hidden;color:#fff;">
    <div style="position:absolute;right:-20px;top:-20px;width:120px;height:120px;
                border-radius:60px;background:rgba(196,30,58,0.2);"></div>
    <div style="position:absolute;right:30px;bottom:-30px;width:80px;height:80px;
                border-radius:40px;background:rgba(245,166,35,0.1);"></div>
    <div style="font-size:11px;letter-spacing:2px;font-weight:700;
                color:rgba(255,255,255,0.5);text-transform:uppercase;margin-bottom:8px;">
        JJGT · VEHÍCULOS COLOMBIA</div>
    <div style="font-size:32px;font-weight:900;line-height:1.1;margin-bottom:8px;">
        🚗 Compra y vende<br>sin intermediarios</div>
    <div style="font-size:14px;color:rgba(255,255,255,0.65);line-height:1.5;margin-bottom:20px;">
        Miles de vehículos en toda Colombia.<br>Publica gratis, permuta sin complicaciones.</div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;">
        <div style="text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#F5A623;">15K+</div>
            <div style="font-size:11px;opacity:0.6;">Vehículos</div>
        </div>
        <div style="width:1px;background:rgba(255,255,255,0.15);"></div>
        <div style="text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#00C9A7;">8.2K</div>
            <div style="font-size:11px;opacity:0.6;">Vendedores</div>
        </div>
        <div style="width:1px;background:rgba(255,255,255,0.15);"></div>
        <div style="text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#C41E3A;">4.8★</div>
            <div style="font-size:11px;opacity:0.6;">Rating</div>
        </div>
        <div style="width:1px;background:rgba(255,255,255,0.15);"></div>
        <div style="text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#fff;">100%</div>
            <div style="font-size:11px;opacity:0.6;">Gratis</div>
        </div>
    </div>
</div>"""


def render_stats_row() -> str:
    return """
<div style="display:flex;gap:12px;margin-bottom:20px;overflow-x:auto;">
    <div style="background:#fff;border-radius:14px;padding:16px;flex:1;min-width:120px;
                box-shadow:0 4px 20px rgba(26,26,46,0.06);border:1px solid #E0E0EC;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#C41E3A;">15,234</div>
        <div style="font-size:11px;color:#6B6B8A;margin-top:2px;">🚗 Vehículos</div>
    </div>
    <div style="background:#fff;border-radius:14px;padding:16px;flex:1;min-width:120px;
                box-shadow:0 4px 20px rgba(26,26,46,0.06);border:1px solid #E0E0EC;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#00C9A7;">8,241</div>
        <div style="font-size:11px;color:#6B6B8A;margin-top:2px;">👥 Usuarios</div>
    </div>
    <div style="background:#fff;border-radius:14px;padding:16px;flex:1;min-width:120px;
                box-shadow:0 4px 20px rgba(26,26,46,0.06);border:1px solid #E0E0EC;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#F5A623;">2,847</div>
        <div style="font-size:11px;color:#6B6B8A;margin-top:2px;">🔄 Permutas</div>
    </div>
    <div style="background:#fff;border-radius:14px;padding:16px;flex:1;min-width:120px;
                box-shadow:0 4px 20px rgba(26,26,46,0.06);border:1px solid #E0E0EC;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#2979FF;">4.8⭐</div>
        <div style="font-size:11px;color:#6B6B8A;margin-top:2px;">Rating</div>
    </div>
</div>"""


def render_quick_actions() -> str:
    return ""  # Implemented inline in page_home


def render_vehicle_detail(v: Dict) -> str:
    return ""  # Implemented inline in page_vehicle_detail


def render_notification_item(n: Dict) -> str:
    return ""  # Implemented inline


def render_history_item(h: Dict) -> str:
    return ""  # Implemented inline


def render_permuta_card(v: Dict) -> str:
    g = v.get("grad", 0)
    c1, c2 = GRAD_COLORS[g % len(GRAD_COLORS)]
    name = v.get("name","")
    model = v.get("model","")
    year = v.get("year","")
    price = v.get("price",0)
    city = v.get("city","")
    km = v.get("km",0)

    return f"""
<div style="background:linear-gradient(135deg,{c1},{c2});
            border-radius:16px;padding:20px;margin-bottom:4px;color:#fff;
            position:relative;overflow:hidden;">
    <div style="position:absolute;right:-10px;top:-10px;font-size:60px;opacity:0.1;">🔄</div>
    <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;
                opacity:0.6;text-transform:uppercase;margin-bottom:6px;">Disponible para permuta</div>
    <div style="font-size:20px;font-weight:700;margin-bottom:4px;">{name} {model}</div>
    <div style="font-size:13px;opacity:0.7;margin-bottom:10px;">
        {year} · {city} · {km:,} km</div>
    <div style="font-size:26px;font-weight:900;">{fmt_price(price)}</div>
</div>"""


def render_seller_card(v: Dict) -> str:
    return ""  # Implemented inline


def render_loyalty_card(points: int, level: str) -> str:
    return ""  # Implemented inline


def render_kpi_card(icon: str, value: str, label: str, color: str = "#C41E3A") -> str:
    return f"""
<div style="background:#fff;border-radius:14px;padding:20px;text-align:center;
            box-shadow:0 4px 20px rgba(26,26,46,0.08);border:1px solid #E0E0EC;">
    <div style="font-size:32px;margin-bottom:6px;">{icon}</div>
    <div style="font-size:28px;font-weight:800;color:{color};">{value}</div>
    <div style="font-size:12px;color:#6B6B8A;margin-top:4px;">{label}</div>
</div>"""


def render_chat_bubble(msg: Dict) -> str:
    return ""  # Implemented inline
