import html
import streamlit as st
from urllib.parse import quote

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


def _market_mover_button(label, *args, **kwargs):
    """Render Market Movers stock actions as real navigation links, not buttons."""
    key = str(kwargs.get("key", ""))
    if key.startswith(("gainer_", "loser_")):
        stock = str(label)
        href = f"/Live_Market?terminal={quote(stock)}"
        st.markdown(
            f'<a class="mp-mover-link" href="{html.escape(href, quote=True)}">'
            f'{html.escape(stock)}</a>',
            unsafe_allow_html=True,
        )
        return False
    return _ORIGINAL_ST_BUTTON(label, *args, **kwargs)


_ORIGINAL_ST_BUTTON = st.button
st.button = _market_mover_button


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

    /* Market Movers: flat table rows with genuine navigation hyperlinks. */
    .movers-grid{display:grid!important;grid-template-columns:1fr 1fr!important;gap:18px!important}
    .mover-card{background:#0b1119!important;border:1px solid #202c3c!important;border-radius:10px!important;padding:0 12px!important;overflow:hidden!important}
    .mover-card .change-label{display:block!important;padding:10px 2px 8px!important;border-bottom:1px solid #263344!important}
    .mover-card [data-testid="stHorizontalBlock"]{border-top:1px solid #1d2938!important;align-items:center!important;padding:2px 0!important;margin:0!important}
    .mover-card [data-testid="stHorizontalBlock"]:first-of-type{border-top:0!important}
    .mover-card .stButton{margin:0!important;padding:0!important}
    .mover-card .stButton > button{display:none!important}
    .mp-mover-link{display:block!important;padding:8px 2px!important;color:#dce3ec!important;text-decoration:none!important;font-weight:700!important;font-size:.76rem!important;line-height:1.2!important}
    .mp-mover-link:hover{color:#7dd3fc!important;text-decoration:underline!important}
    .mover-card .mover-price,.mover-card .mover-pct{padding-top:6px!important;padding-bottom:6px!important}
    .mover-card .movers-note{padding:8px 2px!important;border-top:1px solid #1d2938!important}
    @media(max-width:800px){.movers-grid{grid-template-columns:1fr!important}}
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="mp-brand">◈ MarketPilot</div>', unsafe_allow_html=True)
        st.markdown('<div class="mp-section">INTELLIGENCE SUITE</div>', unsafe_allow_html=True)
        for page, label, icon in NAV:
            st.page_link(page, label=label, icon=icon, width="stretch")
