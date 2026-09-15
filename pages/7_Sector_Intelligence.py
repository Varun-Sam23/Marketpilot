import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from sector_intelligence import fetch_sector_intelligence
from nifty_impact import fetch_nifty_impact
from menu import render_sidebar

st.set_page_config(page_title="Sector Intelligence | MarketPilot", page_icon="🏭", layout="wide")
render_sidebar()
st_autorefresh(interval=30000, key="nifty-impact-refresh")

st.markdown("""
<style>
.stApp { background:#070b12; color:#e7edf5; }
.block-container { padding-top:1.5rem; max-width:1500px; }
.mp-title { font-size:2rem; font-weight:800; letter-spacing:-.03em; }
.mp-sub { color:#8d9aab; margin-bottom:1.2rem; }
.card { background:#0d131d; border:1px solid #202b3a; border-radius:14px; padding:16px; min-height:105px; }
.label { color:#8290a3; font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }
.value { font-size:1.55rem; font-weight:750; margin-top:5px; }
.impact { background:#0b1119; border:1px solid #202c3c; border-radius:14px; padding:16px; margin:10px 0 16px; }
.impact-title { font-size:1.15rem; font-weight:800; }
.impact-note { color:#7f8da0; font-size:.72rem; margin-top:8px; line-height:1.45; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mp-title">🏭 Sector Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Nifty direction · sector attribution · stock drivers · relative strength · participation</div>', unsafe_allow_html=True)

if st.button("↻ Refresh sector data"):
    st.cache_data.clear()

impact = fetch_nifty_impact()
if impact.get("available"):
    direction = impact["direction"]
    nifty_move = impact.get("nifty_move")
    direction_cls = "#58d68d" if direction == "RISING" else "#ff6b6b" if direction == "FALLING" else "#c5ced9"
    direction_text = f"NIFTY 50 {direction} · {nifty_move:+.2f}%" if nifty_move is not None else f"NIFTY 50 {direction}"
    st.markdown(f'<div class="impact"><div class="label">NIFTY IMPACT MAP · CURRENT SESSION</div><div class="impact-title" style="color:{direction_cls}">{direction_text}</div><div class="impact-note">Shows which sectors and constituent stocks are exerting the strongest upward/downward pressure. The pressure figure is a transparent attribution proxy, not an official real-time index-point contribution.</div></div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("### Sectors affecting Nifty")
        dominant = impact["dominant_sectors"]
        if not dominant.empty:
            view = dominant[["Sector", "Weight %", "Sector 1D %", "Pressure %", "Participation %"]].copy()
            st.dataframe(view, use_container_width=True, hide_index=True)
        else:
            st.info("Nifty is flat or sector return data is insufficient.")
    with d2:
        title = "Stocks driving the fall" if direction == "FALLING" else "Stocks driving the rise" if direction == "RISING" else "Largest stock pressures"
        st.markdown(f"### {title}")
        drivers = impact["stock_drivers"]
        if not drivers.empty:
            view = drivers[["Stock", "Sector", "1D %", "Pressure %", "Proxy Weight %"]].copy()
            st.dataframe(view, use_container_width=True, hide_index=True)
        else:
            st.info("No dominant stock drivers detected.")

    with st.expander("See all sector pressure"):
        all_sectors = impact["sectors"][["Sector", "Weight %", "Sector 1D %", "Pressure %", "Participation %", "Stocks"]]
        st.dataframe(all_sectors, use_container_width=True, hide_index=True)

    with st.expander("See all Nifty stock pressure"):
        all_stocks = impact["all_stocks"]
        if not all_stocks.empty:
            st.dataframe(all_stocks[["Stock", "Sector", "Price", "1D %", "Pressure %", "Proxy Weight %"]], use_container_width=True, hide_index=True)

    st.caption(f"{impact['source']} · As of {impact['as_of']}. {impact['weight_note']}")
else:
    st.warning(impact.get("message", "Nifty impact data is unavailable. MarketPilot does not fabricate attribution."))

st.markdown("---")

data = fetch_sector_intelligence()
if not data.get("available"):
    st.warning("Sector market data is currently unavailable. MarketPilot does not fabricate sector values.")
    st.stop()

leaders = ", ".join(data["leaders"]) if data["leaders"] else "None"
laggards = ", ".join(data["laggards"]) if data["laggards"] else "None"

c1, c2, c3 = st.columns(3)
c1.markdown(f'<div class="card"><div class="label">TOP LEADERS</div><div class="value">{leaders}</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="card"><div class="label">TOP LAGGARDS</div><div class="value">{laggards}</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="card"><div class="label">SECTORS COVERED</div><div class="value">{len(data["rows"])}</div></div>', unsafe_allow_html=True)

st.markdown("### Sector ranking")
table = pd.DataFrame([{
    "Rank": i + 1, "Sector": r["sector"], "Score": r["score"], "Status": r["label"],
    "1D %": r["day_pct"], "5D %": r["5d_pct"], "20D %": r["20d_pct"],
    "vs 20D SMA %": r["vs_sma20_pct"], "Participation %": r["breadth_pct"], "Stocks": r["members"]
} for i, r in enumerate(data["rows"])])
st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown("### Sector evidence")
for r in data["rows"]:
    with st.expander(f"{r['sector']} · {r['label']} · {r['score']}/100"):
        if r["reasons"]:
            st.markdown("**Why:** " + " · ".join(r["reasons"]))
        else:
            st.caption("No strong directional factor detected.")
        detail = pd.DataFrame(r["members_detail"])
        st.dataframe(detail, use_container_width=True, hide_index=True)

st.caption(f"Source: {data['source']} · As of {data['as_of']}. Sector scores are descriptive research signals, not guaranteed trade signals.")
