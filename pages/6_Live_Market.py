import html
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from streamlit_autorefresh import st_autorefresh

from intraday_intelligence import fetch_intraday
from realtime_market_data import live_quote, upstox_intraday_candles
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
.terminal{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:12px 14px;margin:14px 0 8px}.terminal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.terminal-title{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#8492a4}.terminal-price{font-size:1.65rem;font-weight:850}.terminal-note{color:#718096;font-size:.65rem;margin-top:5px}
.chart-wrap{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:10px 14px 4px;margin:0 0 8px;overflow:hidden}.chart-wrap svg{display:block;width:100%;height:430px}.chart-grid{stroke:#1b2735;stroke-width:1}.chart-wick-up,.chart-body-up{stroke:#58d68d;fill:#58d68d}.chart-wick-down,.chart-body-down{stroke:#ff6b6b;fill:#ff6b6b}.chart-label{fill:#718096;font-size:12px;font-family:Arial,sans-serif}.chart-last{stroke:#8fa4bb;stroke-width:1;stroke-dasharray:4 4}.chart-last-label{fill:#c7d1de;font-size:12px;font-family:Arial,sans-serif}
.interval-row{margin:0 0 8px}
</style>
""",unsafe_allow_html=True)

IST=ZoneInfo("Asia/Kolkata")
# Upstox streams continuously in the background; Streamlit only repaints on rerun.
# 500ms keeps the displayed LTP/candle close near the incoming feed without
# pretending the browser itself receives every WebSocket tick.
st_autorefresh(interval=500, key="live-market-refresh")
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
symbol=data.get("symbol",selected.upper())

st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">{html.escape(name)} terminal · VWAP · Opening Range · Momentum · Volume · Breadth</div></div><div><div class="{status_cls}">{status}</div><div>{mode_date} · Updated {now.strftime('%H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)

if st.button("↻ REFRESH NOW",use_container_width=False):
    st.rerun()
if mode!="LIVE":
    st.info(f"📌 **LAST SESSION MODE** — NSE is closed. Showing the latest available trading session for **{name}**: {mode_date}. Historical values are never labelled live.")

if feed_live:
    st.markdown(f'<div class="feed"><strong>● REAL-TIME WEBSOCKET CONNECTED</strong> · Upstox V3 · {feed.get("quote_count",0)} instruments streaming · {feed.get("ticks",0)} feed updates · last tick {html.escape(str(feed.get("last_tick_at","—")))} </div>',unsafe_allow_html=True)
elif feed.get("status")=="NOT_CONFIGURED":
    st.info("Real-time WebSocket is installed but not configured yet. Add UPSTOX_ACCESS_TOKEN to the deployment secrets to activate tick-level updates. Historical candles remain the safe fallback for the structure engine; the Live Market chart requires the Upstox feed.")
else:
    st.warning(f"Real-time WebSocket status: {feed.get('status','UNKNOWN')}. The Live Market chart remains Upstox-only and will appear when the authenticated feed is healthy.")

chart_interval=st.radio("Chart interval",["1m","5m","15m","30m"],index=1,horizontal=True,label_visibility="collapsed",key="live-chart-interval")
interval_minutes=int(chart_interval[:-1])

@st.cache_data(ttl=1,show_spinner=False)
def terminal_candles(stock_symbol: str, minutes: int):
    rows=upstox_intraday_candles(stock_symbol,minutes)
    if not rows:
        return pd.DataFrame()
    try:
        df=pd.DataFrame(rows)
        if df.shape[1] < 5:
            return pd.DataFrame()
        names=["Timestamp","Open","High","Low","Close","Volume","OI"][:df.shape[1]]
        df.columns=names
        df["Timestamp"]=pd.to_datetime(df["Timestamp"],errors="coerce",utc=True).dt.tz_convert(IST)
        for col in ["Open","High","Low","Close","Volume","OI"]:
            if col in df.columns:
                df[col]=pd.to_numeric(df[col],errors="coerce")
        df=df.dropna(subset=["Timestamp","Open","High","Low","Close"]).sort_values("Timestamp").drop_duplicates("Timestamp")
        return df.tail(120).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def render_candlestick_chart(df: pd.DataFrame, live_price: float | None = None):
    if df.empty:
        return
    work=df.copy()
    if live_price is not None and mode=="LIVE":
        idx=work.index[-1]
        work.loc[idx,"Close"]=float(live_price)
        work.loc[idx,"High"]=max(float(work.loc[idx,"High"]),float(live_price))
        work.loc[idx,"Low"]=min(float(work.loc[idx,"Low"]),float(live_price))

    view=work.tail(72).reset_index(drop=True)
    lo=float(view["Low"].min())
    hi=float(view["High"].max())
    if hi==lo:
        pad=max(abs(hi)*0.001,0.5)
        lo,hi=lo-pad,hi+pad
    width,height=1280,420
    left,right,top,bottom=64,22,24,46
    plot_w=width-left-right
    plot_h=height-top-bottom
    n=len(view)
    step=plot_w/max(n,1)
    body_w=max(3.0,min(10.0,step*0.62))

    def y(v):
        return top+(hi-float(v))/(hi-lo)*plot_h

    grid=[]
    for frac in (0,0.25,0.5,0.75,1):
        yy=top+frac*plot_h
        val=hi-frac*(hi-lo)
        grid.append(f'<line class="chart-grid" x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}"/><text class="chart-label" x="{left-8}" y="{yy+4:.1f}" text-anchor="end">{val:,.2f}</text>')

    shapes=[]
    for i,row in view.iterrows():
        x=left+(i+0.5)*step
        open_,high_,low_,close_=[float(row[c]) for c in ("Open","High","Low","Close")]
        yy_high,yy_low=y(high_),y(low_)
        yy_open,yy_close=y(open_),y(close_)
        up=close_>=open_
        wick_cls="chart-wick-up" if up else "chart-wick-down"
        body_cls="chart-body-up" if up else "chart-body-down"
        body_top=min(yy_open,yy_close)
        body_h=max(abs(yy_close-yy_open),1.5)
        shapes.append(f'<line class="{wick_cls}" x1="{x:.2f}" y1="{yy_high:.2f}" x2="{x:.2f}" y2="{yy_low:.2f}" stroke-width="1.5"/><rect class="{body_cls}" x="{x-body_w/2:.2f}" y="{body_top:.2f}" width="{body_w:.2f}" height="{body_h:.2f}" rx="1"/>')

    first_label=view["Timestamp"].iloc[0].strftime("%H:%M")
    last_label=view["Timestamp"].iloc[-1].strftime("%H:%M")
    last_close=float(view["Close"].iloc[-1])
    last_y=y(last_close)
    svg=f'''<div class="chart-wrap"><svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="{chart_interval} Upstox candlestick chart">{''.join(grid)}{''.join(shapes)}<line class="chart-last" x1="{left}" y1="{last_y:.1f}" x2="{width-right}" y2="{last_y:.1f}"/><text class="chart-last-label" x="{width-right-4}" y="{last_y-6:.1f}" text-anchor="end">₹{last_close:,.2f}</text><text class="chart-label" x="{left}" y="{height-12}">{html.escape(first_label)}</text><text class="chart-label" x="{width-right}" y="{height-12}" text-anchor="end">{html.escape(last_label)}</text></svg></div>'''
    st.markdown(svg,unsafe_allow_html=True)

chart=terminal_candles(symbol,interval_minutes)
quote=live_quote(symbol) if feed_live else None
live_price=float(quote["ltp"]) if quote and quote.get("ltp") is not None else None

st.markdown(f'''<div class="terminal"><div class="terminal-head"><div class="terminal-title">◉ UPSTOX LIVE TERMINAL · {html.escape(name)} · {chart_interval} CANDLES</div><div class="terminal-price">₹{float(live_price if live_price is not None else data["last"]):,.2f}</div></div></div>''',unsafe_allow_html=True)
if not chart.empty:
    render_candlestick_chart(chart,live_price)
    st.caption(f"Upstox V3 intraday candles · {chart_interval} interval · live LTP overlays the current candle when the WebSocket is healthy. No Yahoo Finance chart data is used here.")
else:
    st.warning("Upstox intraday candle data is currently unavailable for this instrument. The chart is intentionally not falling back to another provider.")

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
heat=pd.DataFrame(br.get("stocks",[]))
if not heat.empty:
    st.dataframe(heat,width="stretch",hide_index=True)

st.caption("MarketPilot is an evidence and decision-support system, not an order-execution system. Always verify broker/exchange data before acting.")
