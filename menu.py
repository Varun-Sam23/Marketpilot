import html
import streamlit as st
from urllib.parse import quote

from nse_universe import search_nse_equities

NAV = [
    ("app.py", "Main Dashboard", "🏠"),
    ("pages/1_Stock_Intelligence.py", "Stock Intelligence", "📊"),
    ("pages/2_Catalyst_Radar.py", "Catalyst Radar", "⚡"),
    ("pages/3_Market_Regime.py", "Market Regime", "🌐"),
    ("pages/4_Institutional_Flow.py", "Institutional Flow", "🏦"),
    ("pages/5_Options_Intelligence.py", "Options Intelligence", "📐"),
    ("pages/6_Live_Market.py", "LIVE MARKET", "⚡"),
    ("pages/7_Sector_Intelligence.py", "Sector Intelligence", "🏭"),
    ("pages/8_Performance_Tracker.py", "Performance Tracker", "📈"),
    ("pages/9_Thesis_Calibration.py", "Thesis Calibration", "🎯"),
    ("pages/10_Agent_Command_Center.py", "Agent Command Center", "🤖"),
]

_ORIGINAL_ST_BUTTON = st.button


def _market_mover_button(label, *args, **kwargs):
    key = str(kwargs.get("key", ""))
    if key.startswith(("gainer_", "loser_")):
        stock = str(label)
        href = f"/Live_Market?terminal={quote(stock)}"
        st.markdown(f'<a class="mp-mover-link" href="{html.escape(href, quote=True)}">{html.escape(stock)}</a>', unsafe_allow_html=True)
        return False
    return _ORIGINAL_ST_BUTTON(label, *args, **kwargs)


st.button = _market_mover_button


def _render_stock_search():
    """Render the NSE-wide searchable stock bar only on Main Dashboard."""
    try:
        url = st.context.url
        pathname = getattr(url, "path", None) or str(url).split("?", 1)[0]
    except Exception:
        pathname = ""
    pathname = str(pathname).rstrip("/")
    if pathname and not (pathname.endswith("/Main_Dashboard") or pathname.endswith("/app") or pathname == ""):
        return

    st.markdown("""
    <style>
    .mp-search-wrap{background:linear-gradient(145deg,#0d151f,#0a1018);border:1px solid #263446;border-radius:13px;padding:10px 12px 8px;margin:0 0 13px}
    .mp-search-title{color:#8d9bad;font-size:.61rem;letter-spacing:.13em;text-transform:uppercase;margin:0 0 5px}
    .mp-search-hint{color:#64748b;font-size:.65rem;margin-top:4px}
    .mp-search-result{display:flex;align-items:center;justify-content:space-between;border-top:1px solid #1d2938;padding:8px 4px;margin-top:7px}
    .mp-search-result a{color:#e7edf5!important;text-decoration:none!important;font-weight:750;font-size:.78rem}
    .mp-search-result a:hover{text-decoration:underline!important;color:#7dd3fc!important}
    .mp-search-symbol{color:#718096;font-size:.65rem;margin-left:8px}
    .mp-search-count{color:#64748b;font-size:.62rem;margin-top:4px}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="mp-search-wrap"><div class="mp-search-title">◈ NSE STOCK SEARCH</div>', unsafe_allow_html=True)
    query = st.text_input("Search stock", placeholder="Search any NSE stock by company name or symbol…", label_visibility="collapsed", key="marketpilot-stock-search")
    query = str(query or "").strip()
    if query:
        matches = search_nse_equities(query, limit=8)
        if matches:
            for row in matches:
                symbol = str(row.get("SYMBOL", ""))
                name = str(row.get("COMPANY", ""))
                href = f"/Live_Market?terminal={quote(symbol)}"
                st.markdown(f'<div class="mp-search-result"><a href="{html.escape(href, quote=True)}">{html.escape(name)} <span class="mp-search-symbol">{html.escape(symbol)}</span></a><span class="mp-search-symbol">OPEN LIVE MARKET →</span></div>', unsafe_allow_html=True)
            st.markdown('<div class="mp-search-count">Source: NSE official equity securities list · EQ series</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="mp-search-hint">No NSE equity match found. Try the company name or NSE symbol.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="mp-search-hint">Search the full NSE equity universe · results open directly in LIVE MARKET.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_sidebar():
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"]{display:none}
    [data-testid="stSidebar"]{background:#111a24}
    [data-testid="stSidebarContent"]{padding-top:.55rem}
    .mp-brand{font-family:Georgia,"Times New Roman",serif;font-size:17px;font-weight:700;color:#e7edf5;line-height:1.15;margin:0 0 17px 1px}
    .mp-section{font-family:Arial,sans-serif;font-size:10px;font-weight:500;letter-spacing:.10em;color:#8994a3;margin:0 0 9px 1px}
    [data-testid="stSidebar"] .stPageLink{margin:0!important;padding:0!important}
    [data-testid="stSidebar"] .stPageLink > a{min-height:30px!important;height:30px!important;padding:4px 8px!important;border-radius:8px!important;font-family:Arial,sans-serif!important;font-size:14px!important;font-weight:500!important;line-height:21px!important;color:#dce3ec!important;gap:7px!important}
    [data-testid="stSidebar"] .stPageLink > a:hover{background:#1b2736!important;color:#fff!important}
    [data-testid="stSidebar"] .stPageLink > a[aria-current="page"]{background:#344255!important;color:#fff!important;font-weight:700!important}
    [data-testid="stSidebar"] .stPageLink > a > span:first-child{font-size:16px!important;line-height:18px!important}

    .movers-grid{display:grid!important;grid-template-columns:1fr 1fr!important;gap:10px!important}
    [data-testid="stColumn"]:has(.mover-card){background:#0b1119!important;border:1px solid #202c3c!important;border-radius:12px!important;padding:11px 13px!important;box-sizing:border-box!important}
    [data-testid="stColumn"]:has(.mover-card) .mover-card{background:transparent!important;border:0!important;border-radius:0!important;padding:0!important;height:0!important;overflow:visible!important}
    [data-testid="stColumn"]:has(.mover-card) .change-label{display:block!important;padding:0 0 9px!important}
    [data-testid="stColumn"]:has(.mover-card) [data-testid="stHorizontalBlock"]{border-top:1px solid #1d2938!important;align-items:center!important;padding:1px 0!important;margin:0!important}
    [data-testid="stColumn"]:has(.mover-card) .stButton{margin:0!important;padding:0!important}
    [data-testid="stColumn"]:has(.mover-card) .stButton > button{display:none!important}
    .mp-mover-link,.mp-mover-link:visited,.mp-mover-link:active{display:block!important;padding:6px 0!important;color:#dce3ec!important;-webkit-text-fill-color:#dce3ec!important;text-decoration:none!important;font-weight:700!important;font-size:.76rem!important;line-height:1.2!important}
    .mp-mover-link:hover{color:#7dd3fc!important;-webkit-text-fill-color:#7dd3fc!important;text-decoration:underline!important}
    [data-testid="stColumn"]:has(.mover-card) .mover-price,[data-testid="stColumn"]:has(.mover-card) .mover-pct{padding-top:6px!important;padding-bottom:6px!important}
    [data-testid="stColumn"]:has(.mover-card) .movers-note{padding:8px 0 0!important;margin-top:2px!important;border-top:1px solid #1d2938!important}
    @media(max-width:800px){.movers-grid{grid-template-columns:1fr!important}}
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="mp-brand">◈ MarketPilot</div>', unsafe_allow_html=True)
        st.markdown('<div class="mp-section">INTELLIGENCE SUITE</div>', unsafe_allow_html=True)
        for page, label, icon in NAV:
            st.page_link(page, label=label, icon=icon, width="stretch")
    _render_stock_search()
