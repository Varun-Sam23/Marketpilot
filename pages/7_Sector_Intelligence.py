import streamlit as st
import pandas as pd

from sector_intelligence import fetch_sector_intelligence
from menu import render_sidebar

st.set_page_config(page_title="Sector Intelligence | MarketPilot", page_icon="🏭", layout="wide")
render_sidebar()

st.markdown("""
<style>
.stApp { background:#070b12; color:#e7edf5; }
.block-container { padding-top:1.5rem; max-width:1500px; }
.mp-title { font-size:2rem; font-weight:800; letter-spacing:-.03em; }
.mp-sub { color:#8d9aab; margin-bottom:1.2rem; }
.card { background:#0d131d; border:1px solid #202b3a; border-radius:14px; padding:16px; min-height:105px; }
.label { color:#8290a3; font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }
.value { font-size:1.55rem; font-weight:750; margin-top:5px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mp-title">🏭 Sector Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Relative strength · Momentum · Trend position · Participation · Sector leadership</div>', unsafe_allow_html=True)

if st.button("↻ Refresh sector data"):
    st.cache_data.clear()

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
