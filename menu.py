import streamlit as st

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
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="mp-brand">◈ MarketPilot</div>', unsafe_allow_html=True)
        st.markdown('<div class="mp-section">INTELLIGENCE SUITE</div>', unsafe_allow_html=True)
        for page, label, icon in NAV:
            st.page_link(page, label=label, icon=icon, width="stretch")
