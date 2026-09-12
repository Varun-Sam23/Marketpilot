import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
import pandas as pd

from intraday_intelligence import fetch_intraday
from menu import render_sidebar

st.set_page_config(page_title="Live Market | MarketPilot", page_icon="⚡", layout="wide")
render_sidebar()

st.markdown("""
<style>
.stApp{background:#060a10;color:#e8edf5}.block-container{padding-top:1.1rem;max-width:1550px}
.hero{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid #202b38;padding-bottom:14px;margin-bottom:14px}
.mp-title{font-size:2.15rem;font-weight:850;letter-spacing:-.04em}.mp-sub{color:#8290a3;margin-top:3px}
.status{font-size:.72rem;letter-spacing:.12em;color:#64d89a;text-align:right}.time{font-size:.8rem;color:#8d9aab;text-align:right;margin-top:4px}
.card{background:linear-gradient(180deg,#0d141e,#0a1018);border:1px solid #1e2a39;border-radius:12px;padding:14px;min-height:94px}
.label{color:#77869a;font-size:.68rem;text-transform:uppercase;letter-spacing:.1em}.value{font-size:1.42rem;font-weight:800;margin-top:5px}.muted{color:#8290a3}.good{color:#58d68d}.bad{color:#ff6b6b}.neutral{color:#f4c95d}
.livebox{background:#0b121b;border:1px solid #263446;border-radius:14px;padding:18px;margin:14px 0}.livehead{font-size:.7rem;color:#7e8da1;letter-spacing:.13em;text-transform:uppercase}.headline{font-size:1.5rem;font-weight:850;margin:6px 0}.evidence{color:#aab5c3;font-size:.9rem}.chip{display:inline-block;border:1px solid #29384a;border-radius:20px;padding:4px 9px;margin:8px 6px 0 0;font-size:.72rem;color:#9daaba}
</style>
""", unsafe_allow_html=True)

IST=ZoneInfo("Asia/Kolkata")
now=datetime.now(IST)
st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">Real-time structure terminal · NIFTY · VWAP · Opening Range · Momentum · Volume · Breadth</div></div><div><div class="status">● MARKET STRUCTURE</div><div class="time">{now.strftime('%d %b %Y · %H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)

c1,c2=st.columns([1,5])
with c1:
    if st.button("↻ REFRESH",use_container_width=True): st.cache_data.clear()
with c2:
    st.caption("Auto-refresh is controlled by the dashboard refresh cycle. Public/free market data may be delayed.")

nse=mcal.get_calendar("NSE")
if nse.schedule(start_date=now.date(),end_date=now.date()).empty:
    st.info(f"🏁 **NSE market is closed today — {now.strftime('%A, %d %B %Y')}.** Live structure will resume on the next trading session.")
    st.caption("The exchange calendar is checked first, so a holiday/weekend is never presented as a data-feed failure.")
    st.stop()

data=fetch_intraday()
if not data.get("available"):
    st.warning(data.get("message","Intraday data unavailable."))
    st.caption(f"Source: {data.get('source','Unknown')}. MarketPilot never fabricates missing intraday values.")
    st.stop()

bias=data["bias"]
cls="good" if bias=="BULLISH" else "bad" if bias=="BEARISH" else "neutral"
syn=data.get("synthesis",{})

st.markdown(f'''<div class="livebox"><div class="livehead">WHAT IS HAPPENING RIGHT NOW?</div><div class="headline {cls}">{syn.get('headline','Structure unavailable')}</div><div class="evidence">{syn.get('detail','No synthesis available.')}</div><span class="chip">Score {data['score']}/100</span><span class="chip">Confidence {data['confidence']}</span><span class="chip">Bull signals {syn.get('bull_count',0)}</span><span class="chip">Bear signals {syn.get('bear_count',0)}</span><span class="chip">Volume {'confirming' if syn.get('volume_confirming') else 'normal'}</span></div>''',unsafe_allow_html=True)

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

st.markdown("### Market structure map")
a,b,c,d=st.columns(4)
a.metric("Opening Range High",f"{data['opening_range_high']:,.2f}" if data.get("opening_range_high") else "—")
a.metric("Opening Range Low",f"{data['opening_range_low']:,.2f}" if data.get("opening_range_low") else "—")
b.metric("Recent Resistance",f"{data['levels'].get('recent_resistance',0):,.2f}")
b.metric("Recent Support",f"{data['levels'].get('recent_support',0):,.2f}")
c.metric("Session High",f"{data['levels'].get('session_high',0):,.2f}")
c.metric("Session Low",f"{data['levels'].get('session_low',0):,.2f}")
d.metric("VWAP Distance",f"{data['vwap_distance_pct']:+.2f}%" if data.get("vwap_distance_pct") is not None else "—")
d.metric("Trend",data.get("trend","—"))

st.markdown("### Watchlist heatmap")
br=data["breadth"]
q1,q2,q3,q4=st.columns(4)
q1.metric("Advancers",br["advancers"]);q2.metric("Decliners",br["decliners"]);q3.metric("Unchanged",br["unchanged"]);q4.metric("Advance / Decline",f"{br['breadth_ratio']:.2f}")
if br["total"]:
    heat=pd.DataFrame(br["rows"])
    heat["Signal"] = heat["Change %"].apply(lambda x: "UP" if x>0 else "DOWN" if x<0 else "FLAT")
    heat["Change"] = heat["Change %"].map(lambda x:f"{x:+.2f}%")
    left,right=st.columns([1.4,1])
    with left:
        st.dataframe(heat[["Stock","Change","Signal"]],use_container_width=True,hide_index=True,height=310)
    with right:
        st.markdown("**Live ranking**")
        leaders=heat.head(3)
        laggards=heat.tail(3).sort_values("Change %")
        for _,r in leaders.iterrows(): st.markdown(f"🟢 **{r['Stock']}** &nbsp; {r['Change']}")
        st.divider()
        for _,r in laggards.iterrows(): st.markdown(f"🔴 **{r['Stock']}** &nbsp; {r['Change']}")
    st.caption(f"Watchlist breadth: {br['total']} liquid names. This is a MarketPilot watchlist proxy, not exchange-wide breadth.")
else:
    st.info("Watchlist breadth is unavailable from the current intraday feed.")

st.markdown("### Signal engine")
components=data.get("components",{})
component_df=pd.DataFrame([{"Signal":k,"Points":v,"Read":"Positive" if v>0 else "Negative" if v<0 else "Neutral"} for k,v in components.items()])
if not component_df.empty:
    st.dataframe(component_df,use_container_width=True,hide_index=True)

st.markdown("### Evidence ledger")
for reason in data["reasons"]: st.markdown(f"• {reason}")

st.markdown(f"**Source:** {data['source']} · **As of:** {data['as_of']}")
st.caption("Decision-support only. The live synthesis is generated exclusively from the displayed VWAP, opening-range, momentum, trend, volume, breadth and level signals. It is not a probability, trade recommendation, or execution signal. Use broker-grade real-time data for execution.")
