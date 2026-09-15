import html
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

from intraday_intelligence import fetch_intraday
from menu import render_sidebar

st.set_page_config(page_title="Live Market | MarketPilot", page_icon="⚡", layout="wide")
render_sidebar()

st.markdown("""
<style>
.stApp{background:#060a10;color:#e8edf5}.block-container{padding-top:1.1rem;max-width:1550px}
.hero{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid #202b38;padding-bottom:14px;margin-bottom:14px}
.mp-title{font-size:2.15rem;font-weight:850;letter-spacing:-.04em}.mp-sub{color:#8290a3;margin-top:3px}
.card{background:linear-gradient(180deg,#0d141e,#0a1018);border:1px solid #1e2a39;border-radius:12px;padding:14px;min-height:94px}
.label{color:#77869a;font-size:.68rem;text-transform:uppercase;letter-spacing:.1em}.value{font-size:1.42rem;font-weight:800;margin-top:5px}.good{color:#58d68d}.bad{color:#ff6b6b}.neutral{color:#f4c95d}
.livebox{background:#0b121b;border:1px solid #263446;border-radius:14px;padding:18px;margin:14px 0}.livehead{font-size:.7rem;color:#7e8da1;letter-spacing:.13em;text-transform:uppercase}.headline{font-size:1.5rem;font-weight:850;margin:6px 0}.evidence{color:#aab5c3;font-size:.9rem}.chip{display:inline-block;border:1px solid #29384a;border-radius:20px;padding:4px 9px;margin:8px 6px 0 0;font-size:.72rem;color:#9daaba}
.feed{background:#09141a;border:1px solid #1d3a31;border-radius:10px;padding:9px 12px;margin:8px 0;font-size:.7rem;color:#8ea19a}.feed strong{color:#62d69a}
.terminal{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:12px 14px;margin:14px 0}.terminal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.terminal-title{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#8492a4}.terminal-price{font-size:1.65rem;font-weight:850}.terminal-note{color:#718096;font-size:.65rem;margin-top:5px}
.market-chart{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:10px 14px 4px;margin:0 0 8px;overflow:hidden}.market-chart svg{display:block;width:100%;height:390px}.chart-grid{stroke:#1b2735;stroke-width:1}.chart-line{fill:none;stroke:#8fa4bb;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}.chart-dot{fill:#8fa4bb}.chart-label{fill:#718096;font-size:12px;font-family:Arial,sans-serif}
</style>
""",unsafe_allow_html=True)

IST=ZoneInfo("Asia/Kolkata")
st_autorefresh(interval=2000, key="live-market-refresh")
now=datetime.now(IST)
selected=st.query_params.get("terminal", "NIFTY")
ticker="^NSEI" if selected.upper()=="NIFTY" else f"{selected.upper()}.NS"
data=fetch_intraday(ticker)
if not data.get("available"):
    st.error(data.get("message","Market structure data unavailable."))
    st.caption(f"Source: {data.get('source','Unknown')}. MarketPilot never fabricates missing values.")
    st.stop()

mode=data.get("mode","LIVE")
mode_date=datetime.fromisoformat(data["session_date"]).strftime("%a, %d %b %Y")
status="● LIVE SESSION" if mode=="LIVE" else "● LAST SESSION"
status_cls="good" if mode=="LIVE" else "neutral"
feed=data.get("live_feed",{}) or {}
feed_live=str(feed.get("status","")) == "LIVE"
name=data.get("name",selected.upper())

st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">{html.escape(name)} terminal · VWAP · Opening Range · Momentum · Volume · Breadth</div></div><div><div class="{status_cls}">{status}</div><div>{mode_date} · Updated {now.strftime('%H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)

if st.button("↻ REFRESH NOW",use_container_width=False):
    st.rerun()
if mode!="LIVE":
    st.info(f"📌 **LAST SESSION MODE** — NSE is closed. Showing the latest available trading session for **{name}**: {mode_date}. Historical values are never labelled live.")

if feed_live:
    st.markdown(f'<div class="feed"><strong>● REAL-TIME WEBSOCKET CONNECTED</strong> · Upstox V3 · {feed.get("quote_count",0)} instruments streaming · {feed.get("ticks",0)} feed updates · last tick {html.escape(str(feed.get("last_tick_at","—")))} </div>',unsafe_allow_html=True)
elif feed.get("status")=="NOT_CONFIGURED":
    st.info("Real-time WebSocket is installed but not configured yet. Add UPSTOX_ACCESS_TOKEN to the deployment secrets to activate tick-level updates. Historical candles remain the safe fallback.")
else:
    st.warning(f"Real-time WebSocket status: {feed.get('status','UNKNOWN')}. MarketPilot is using the safe fallback until the live stream is healthy.")

@st.cache_data(ttl=5,show_spinner=False)
def terminal_chart(t: str):
    try:
        h=yf.Ticker(t).history(period="1d",interval="5m",auto_adjust=False,prepost=False)
        if h is None or h.empty:
            return pd.DataFrame()
        h=h.copy();h.index=pd.to_datetime(h.index)
        if h.index.tz is None:h.index=h.index.tz_localize("UTC")
        h.index=h.index.tz_convert(IST)
        h=h[[c for c in ["Open","High","Low","Close","Volume"] if c in h.columns]].dropna(subset=["Close"])
        return h
    except Exception:
        return pd.DataFrame()

def render_price_chart(series: pd.Series):
    values=pd.to_numeric(series,errors="coerce").dropna().tolist()
    if not values:
        return
    width,height=1200,360
    left,right,top,bottom=52,18,22,42
    plot_w=width-left-right
    plot_h=height-top-bottom
    lo,hi=min(values),max(values)
    if hi==lo:
        pad=max(abs(hi)*0.001,0.5)
        lo,hi=lo-pad,hi+pad
    def xy(i,v):
        x=left+(i/(max(len(values)-1,1)))*plot_w
        y=top+(hi-v)/(hi-lo)*plot_h
        return x,y
    pts=[xy(i,v) for i,v in enumerate(values)]
    path=" ".join(("M" if i==0 else "L")+f" {x:.2f},{y:.2f}" for i,(x,y) in enumerate(pts))
    grid=[]
    for frac in (0,0.25,0.5,0.75,1):
        y=top+frac*plot_h
        val=hi-frac*(hi-lo)
        grid.append(f'<line class="chart-grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"/><text class="chart-label" x="{left-8}" y="{y+4:.1f}" text-anchor="end">{val:,.2f}</text>')
    start_label=series.index[0].strftime("%H:%M") if hasattr(series.index[0],"strftime") else ""
    end_label=series.index[-1].strftime("%H:%M") if hasattr(series.index[-1],"strftime") else ""
    svg=f'''<div class="market-chart"><svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="Intraday price chart">{''.join(grid)}<path class="chart-line" d="{path}"/><circle class="chart-dot" cx="{pts[-1][0]:.2f}" cy="{pts[-1][1]:.2f}" r="4"/><text class="chart-label" x="{left}" y="{height-12}">{html.escape(start_label)}</text><text class="chart-label" x="{width-right}" y="{height-12}" text-anchor="end">{html.escape(end_label)}</text></svg></div>'''
    st.markdown(svg,unsafe_allow_html=True)

chart=terminal_chart(ticker)
if not chart.empty:
    display_close=chart["Close"].copy()
    if feed_live and data.get("last") is not None:
        display_close.iloc[-1]=float(data["last"])
    st.markdown(f'<div class="terminal"><div class="terminal-head"><div class="terminal-title">◉ LIVE TERMINAL · {html.escape(name)}</div><div class="terminal-price">₹{float(data["last"]):,.2f}</div></div></div>',unsafe_allow_html=True)
    render_price_chart(display_close)
    st.caption("5-minute intraday candles · latest displayed price uses the live WebSocket when available; otherwise the latest public candle is shown.")
else:
    st.warning(f"Intraday chart data is currently unavailable for {name}. No chart values are estimated.")

bias=data["bias"]
cls="good" if bias=="BULLISH" else "bad" if bias=="BEARISH" else "neutral"
syn=data.get("synthesis",{})

st.markdown(f'''<div class="livebox"><div class="livehead">WHAT IS HAPPENING {"RIGHT NOW" if mode=="LIVE" else "IN THE LAST SESSION"}?</div><div class="headline {cls}">{syn.get('headline','Structure unavailable')}</div><div class="evidence">{syn.get('detail','No synthesis available.')}</div><span class="chip">{mode}</span><span class="chip">Score {data['score']}/100</span><span class="chip">Confidence {data['confidence']}</span><span class="chip">Bull {syn.get('bull_count',0)}</span><span class="chip">Bear {syn.get('bear_count',0)}</span><span class="chip">Volume {'confirming' if syn.get('volume_confirming') else 'normal'}</span></div>''',unsafe_allow_html=True)

cols=st.columns(6)
metrics=[(name,f"₹{data['last']:,.2f}"),("SESSION CHANGE",f"{data['session_change_pct']:+.2f}%" if data.get('session_change_pct') is not None else "—"),("VWAP",f"{data['vwap']:,.2f}" if data.get('vwap') is not None else "—"),("OR STATUS",data['opening_range_state']),("15M MOMENTUM",f"{data['momentum_15m_pct']:+.2f}%"),("LATEST VOLUME",f"{data['volume_ratio']:.2f}x" if data.get('volume_ratio') is not None else "—")]
for c,(label,value) in zip(cols,metrics): c.markdown(f'<div class="card"><div class="label">{html.escape(str(label))}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)

st.markdown(f"### {html.escape(name)} structure snapshot")
levels=data.get("levels",{})
level_df=pd.DataFrame([{"Level":"Session Low","Value":levels.get("session_low")},{"Level":"Recent Support","Value":levels.get("recent_support")},{"Level":"VWAP","Value":data.get("vwap")},{"Level":"Last","Value":data.get("last")},{"Level":"Recent Resistance","Value":levels.get("recent_resistance")},{"Level":"Session High","Value":levels.get("session_high")}]).dropna()
if not level_df.empty: st.dataframe(level_df,width="stretch",hide_index=True)
st.caption(f"Structure levels from the displayed {mode.lower()} session · as of {data['as_of']} · {data['source']}.")

st.markdown("### Market structure map")
a,b,c,d=st.columns(4)
a.metric("Opening Range High",f"{data['opening_range_high']:,.2f}" if data.get('opening_range_high') else "—"); a.metric("Opening Range Low",f"{data['opening_range_low']:,.2f}" if data.get('opening_range_low') else "—")
b.metric("Recent Resistance",f"{levels.get('recent_resistance',0):,.2f}"); b.metric("Recent Support",f"{levels.get('recent_support',0):,.2f}")
c.metric("Session High",f"{levels.get('session_high',0):,.2f}"); c.metric("Session Low",f"{levels.get('session_low',0):,.2f}")
d.metric("VWAP Distance",f"{data['vwap_distance_pct']:+.2f}%" if data.get('vwap_distance_pct') is not None else "—"); d.metric("Trend",data.get('trend','—'))

st.markdown("### Watchlist heatmap")
br=data["breadth"]
q1,q2,q3,q4=st.columns(4)
q1.metric("Advancers",br["advancers"]);q2.metric("Decliners",br["decliners"]);q3.metric("Unchanged",br["unchanged"]);q4.metric("Advance / Decline",f"{br['breadth_ratio']:.2f}")
if br["total"]:
    heat=pd.DataFrame(br["rows"]); heat["Signal"]=heat["Change %"].apply(lambda x:"UP" if x>0 else "DOWN" if x<0 else "FLAT"); heat["Change"]=heat["Change %"].map(lambda x:f"{x:+.2f}%")
    left,right=st.columns([1.4,1])
    with left: st.dataframe(heat[["Stock","Change","Signal"]],width="stretch",hide_index=True,height=310)
    with right:
        st.markdown("**Session ranking**" if mode!="LIVE" else "**Live ranking**")
        for _,r in heat.head(3).iterrows(): st.markdown(f"🟢 **{r['Stock']}** &nbsp; {r['Change']}")
        st.divider()
        for _,r in heat.tail(3).sort_values("Change %").iterrows(): st.markdown(f"🔴 **{r['Stock']}** &nbsp; {r['Change']}")
    st.caption(f"Watchlist breadth: {br['total']} liquid names. MarketPilot watchlist proxy, not exchange-wide breadth.")

st.markdown("### Signal engine")
components=data.get("components",{}); component_df=pd.DataFrame([{"Signal":k,"Points":v,"Read":"Positive" if v>0 else "Negative" if v<0 else "Neutral"} for k,v in components.items()])
if not component_df.empty: st.dataframe(component_df,width="stretch",hide_index=True)

st.markdown("### Evidence ledger")
for reason in data.get("reasons",[]): st.markdown(f"• {reason}")
st.markdown(f"**Source:** {data['source']} · **Session:** {mode_date} · **As of:** {data['as_of']}")
st.caption("Decision-support only. LAST SESSION is historical; LIVE mode uses the latest available market feed. The synthesis is based only on displayed structure signals and is not a trade recommendation or execution signal.")
