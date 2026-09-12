import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
import pandas as pd

from intraday_intelligence import fetch_intraday

st.set_page_config(page_title="Intraday Market Structure | MarketPilot", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.stApp{background:#070b12;color:#e7edf5}.block-container{padding-top:1.4rem;max-width:1500px}
.mp-title{font-size:2rem;font-weight:800;letter-spacing:-.03em}.mp-sub{color:#8d9aab;margin-bottom:1rem}
.card{background:#0d131d;border:1px solid #202b3a;border-radius:14px;padding:15px;min-height:100px}
.label{color:#8290a3;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em}.value{font-size:1.45rem;font-weight:750;margin-top:5px}
.good{color:#58d68d}.bad{color:#ff6b6b}.neutral{color:#f4c95d}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mp-title">⚡ Intraday Market Structure</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">NIFTY 5-minute structure · VWAP · Opening Range · Momentum · Trend · Volume · Breadth · Support/Resistance</div>', unsafe_allow_html=True)

if st.button("↻ Refresh intraday data"):
    st.cache_data.clear()

IST=ZoneInfo("Asia/Kolkata")
now=datetime.now(IST)
nse=mcal.get_calendar("NSE")
if nse.schedule(start_date=now.date(),end_date=now.date()).empty:
    st.info(f"🏁 **NSE market is closed today — {now.strftime('%A, %d %B %Y')}.** Intraday 5-minute analysis will resume on the next trading session.")
    st.caption("Market status comes from the NSE trading calendar; a closed exchange is not treated as a broken data feed.")
    st.stop()

data=fetch_intraday()
if not data.get("available"):
    st.warning(data.get("message","Intraday data unavailable."))
    st.caption(f"Source: {data.get('source','Unknown')}. MarketPilot never fabricates missing intraday values.")
    st.stop()

bias=data["bias"]
cls="good" if bias=="BULLISH" else "bad" if bias=="BEARISH" else "neutral"
st.markdown(f"**INTRADAY STRENGTH: <span class='{cls}'>{bias}</span>** · **{data['score']}/100** · Confidence **{data['confidence']}** · As of {data['as_of']}",unsafe_allow_html=True)

cols=st.columns(6)
metrics=[
    ("NIFTY",f"{data['last']:,.2f}"),
    ("SESSION CHANGE",f"{data['session_change_pct']:+.2f}%" if data.get("session_change_pct") is not None else "—"),
    ("VWAP",f"{data['vwap']:,.2f}" if data.get("vwap") is not None else "—"),
    ("OR STATUS",data["opening_range_state"]),
    ("15M MOMENTUM",f"{data['momentum_15m_pct']:+.2f}%"),
    ("LATEST VOLUME",f"{data['volume_ratio']:.2f}x" if data.get("volume_ratio") is not None else "—"),
]
for c,(label,value) in zip(cols,metrics):
    c.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)

st.markdown("### Structure map")
a,b,c,d=st.columns(4)
a.metric("Opening Range High",f"{data['opening_range_high']:,.2f}" if data.get("opening_range_high") else "—")
a.metric("Opening Range Low",f"{data['opening_range_low']:,.2f}" if data.get("opening_range_low") else "—")
b.metric("Recent Resistance",f"{data['levels'].get('recent_resistance',0):,.2f}")
b.metric("Recent Support",f"{data['levels'].get('recent_support',0):,.2f}")
c.metric("Session High",f"{data['levels'].get('session_high',0):,.2f}")
c.metric("Session Low",f"{data['levels'].get('session_low',0):,.2f}")
d.metric("VWAP Distance",f"{data['vwap_distance_pct']:+.2f}%" if data.get("vwap_distance_pct") is not None else "—")
d.metric("Trend",data.get("trend","—"))

st.markdown("### Signal components")
components=data.get("components",{})
component_df=pd.DataFrame([{"Signal":k,"Points":v} for k,v in components.items()])
if not component_df.empty:
    st.dataframe(component_df,use_container_width=True,hide_index=True)

st.markdown("### Breadth")
br=data["breadth"]
q1,q2,q3,q4=st.columns(4)
q1.metric("Advancers",br["advancers"]);q2.metric("Decliners",br["decliners"]);q3.metric("Unchanged",br["unchanged"]);q4.metric("Advance / Decline",f"{br['breadth_ratio']:.2f}")
if br["total"]:
    st.caption(f"Watchlist breadth: {br['total']} liquid names. This is a watchlist breadth proxy, not exchange-wide market breadth.")
    st.dataframe(pd.DataFrame(br["rows"]),use_container_width=True,hide_index=True)

st.markdown("### Evidence ledger")
for reason in data["reasons"]: st.markdown(f"• {reason}")

st.markdown(f"**Source:** {data['source']}")
st.caption("Signals are descriptive decision-support metrics. Volume is compared with a recent intraday baseline; breadth uses the MarketPilot watchlist. Public/free data may be delayed or incomplete. Use broker-grade real-time data for execution.")
