import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

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
data=fetch_intraday()

if not data.get("available"):
    st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">Real-time structure terminal · NIFTY · VWAP · Opening Range · Momentum · Volume · Breadth</div></div><div><div class="status">● MARKET STRUCTURE</div><div class="time">{now.strftime('%d %b %Y · %H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)
    st.warning(data.get("message","Market structure data unavailable."))
    st.caption(f"Source: {data.get('source','Unknown')}. MarketPilot never fabricates missing market values.")
    st.stop()

mode=data.get("mode","LIVE")
mode_label="● LIVE SESSION" if mode=="LIVE" else "● LAST SESSION"
mode_cls="good" if mode=="LIVE" else "neutral"
mode_date=datetime.fromisoformat(data["session_date"]).strftime("%a, %d %b %Y")

st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">NIFTY structure terminal · VWAP · Opening Range · Momentum · Volume · Breadth</div></div><div><div class="status {mode_cls}">{mode_label}</div><div class="time">Viewing {mode_date} · Updated {now.strftime('%H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)

c1,c2=st.columns([1,5])
with c1:
    if st.button("↻ REFRESH",use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with c2:
    if mode=="LIVE":
        st.caption("LIVE mode · Public/free market data may be delayed. Refresh to request the latest feed snapshot.")
    else:
        st.info(f"📌 **LAST SESSION MODE** — NSE is not trading today. The terminal is showing the latest available session ({mode_date}) instead of a blank screen. Nothing here is labelled live.")

bias=data["bias"]
cls="good" if bias=="BULLISH" else "bad" if bias=="BEARISH" else "neutral"
syn=data.get("synthesis",{})

st.markdown(f'''<div class="livebox"><div class="livehead">WHAT IS HAPPENING {"RIGHT NOW" if mode=="LIVE" else "IN THE LAST SESSION"}?</div><div class="headline {cls}">{syn.get('headline','Structure unavailable')}</div><div class="evidence">{syn.get('detail','No synthesis available.')}</div><span class="chip">{mode}</span><span class="chip">Score {data['score']}/100</span><span class="chip">Confidence {data['confidence']}</span><span class="chip">Bull signals {syn.get('bull_count',0)}</span><span class="chip">Bear signals {syn.get('bear_count',0)}</span><span class="chip">Volume {'confirming' if syn.get('volume_confirming') else 'normal'}</span></div>''',unsafe_allow_html=True)

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

st.markdown("### NIFTY structure snapshot")
levels=data.get("levels",{})
level_df=pd.DataFrame({"Level":["Session Low","Recent Support","VWAP","Last","Recent Resistance","Session High"],"Value":[levels.get("session_low"),levels.get("recent_support"),data.get("vwap"),data.get("last"),levels.get("recent_resistance"),levels.get("session_high")]})
level_df=level_df.dropna()
if not level_df.empty:
    st.bar_chart(level_df.set_index("Level"),height=260)
st.caption(f"Structure levels are calculated from the displayed {mode.lower()} session. As of {data['as_of']} · source: {data['source']}.")

st.markdown("### Market structure map")
a,b,c,d=st.columns(4)
a.metric("Opening Range High",f"{data['opening_range_high']:,.2f}" if data.get("opening_range_high") else "—")
a.metric("Opening Range Low",f"{data['opening_range_low']:,.2f}" if data.get("opening_range_low") else "—")
b.metric("Recent Resistance",f"{levels.get('recent_resistance',0):,.2f}")
b.metric("Recent Support",f"{levels.get('recent_support',0):,.2f}")
c.metric("Session High",f"{levels.get('session_high',0):,.2f}")
c.metric("Session Low",f"{levels.get('session_low',0):,.2f}")
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
        st.markdown("**Session ranking**" if mode!="LIVE" else "**Live ranking**")
        leaders=heat.head(3); laggards=heat.tail(3).sort_values("Change %")
        for _,r in leaders.iterrows(): st.markdown(f"🟢 **{r['Stock']}** &nbsp; {r['Change']}")
        st.divider()
        for _,r in laggards.iterrows(): st.markdown(f"🔴 **{r['Stock']}** &nbsp; {r['Change']}")
    st.caption(f"Watchlist breadth: {br['total']} liquid names. This is a MarketPilot watchlist proxy, not exchange-wide breadth.")
else:
    st.info("Watchlist breadth is unavailable from the current market-data feed.")

st.markdown("### Signal engine")
components=data.get("components",{})
component_df=pd.DataFrame([{"Signal":k,"Points":v,"Read":"Positive" if v>0 else "Negative" if v<0 else "Neutral"} for k,v in components.items()])
if not component_df.empty:
    st.dataframe(component_df,use_container_width=True,hide_index=True)

st.markdown("### Evidence ledger")
for reason in data["reasons"]: st.markdown(f"• {reason}")

st.markdown(f"**Source:** {data['source']} · **Session:** {mode_date} · **As of:** {data['as_of']}")
st.caption("Decision-support only. LIVE mode uses the latest available market feed; LAST SESSION mode is historical and is never represented as live. The synthesis is generated exclusively from the displayed VWAP, opening-range, momentum, trend, volume, breadth and level signals. It is not a probability, trade recommendation, or execution signal. Use broker-grade real-time data for execution.")
