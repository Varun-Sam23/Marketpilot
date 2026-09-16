import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

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
.feed{background:#09141a;border:1px solid #1d3a31;border-radius:10px;padding:9px 12px;margin:8px 0;font-size:.7rem;color:#8ea19a}.feed strong{color:#62d69a}
.terminal{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:12px 14px;margin:14px 0 8px}.terminal-head{display:flex;justify-content:space-between;align-items:center}.terminal-title{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#8492a4}.terminal-price{font-size:1.65rem;font-weight:850}
.chart-wrap{background:#070c13;border:1px solid #1f2d3d;border-radius:14px;padding:10px 14px 4px;margin:0 0 8px;overflow:hidden}.chart-wrap svg{display:block;width:100%;height:430px}.chart-grid{stroke:#1b2735;stroke-width:1}.chart-wick-up,.chart-body-up{stroke:#58d68d;fill:#58d68d}.chart-wick-down,.chart-body-down{stroke:#ff6b6b;fill:#ff6b6b}.chart-label{fill:#718096;font-size:12px;font-family:Arial,sans-serif}.chart-last{stroke:#8fa4bb;stroke-width:1;stroke-dasharray:4 4}.chart-last-label{fill:#c7d1de;font-size:12px;font-family:Arial,sans-serif}
.card{background:linear-gradient(180deg,#0d141e,#0a1018);border:1px solid #1e2a39;border-radius:12px;padding:14px;min-height:94px}.label{color:#77869a;font-size:.68rem;text-transform:uppercase;letter-spacing:.1em}.value{font-size:1.42rem;font-weight:800;margin-top:5px}.good{color:#58d68d}.bad{color:#ff6b6b}.neutral{color:#f4c95d}
</style>
""",unsafe_allow_html=True)

IST=ZoneInfo("Asia/Kolkata")
selected=str(st.query_params.get("terminal", "NIFTY")).upper()
ticker="^NSEI" if selected=="NIFTY" else f"{selected}.NS"
data=fetch_intraday(ticker)

if not data.get("available"):
    st.error(data.get("message","Market structure data unavailable."))
    st.caption(f"Source: {data.get('source','Unknown')}. MarketPilot never fabricates missing values.")
    st.stop()

mode=data.get("mode","LIVE")
name=data.get("name",selected)
symbol=data.get("symbol",selected)
feed=data.get("live_feed",{}) or {}
feed_live=str(feed.get("status",""))=="LIVE"

st.markdown(f'''<div class="hero"><div><div class="mp-title">⚡ LIVE MARKET</div><div class="mp-sub">{html.escape(name)} terminal · Upstox V3 · VWAP · Opening Range · Momentum · Volume</div></div><div><div class="{'good' if mode=='LIVE' else 'neutral'}">● {'LIVE SESSION' if mode=='LIVE' else 'LAST SESSION'}</div><div>{datetime.now(IST).strftime('%d %b %Y · %H:%M:%S IST')}</div></div></div>''',unsafe_allow_html=True)

if feed_live:
    st.markdown(f'<div class="feed"><strong>● REAL-TIME WEBSOCKET CONNECTED</strong> · Upstox V3 · {feed.get("quote_count",0)} instruments · {feed.get("ticks",0)} feed updates · last tick {html.escape(str(feed.get("last_tick_at","—")))}</div>',unsafe_allow_html=True)
elif feed.get("status")=="NOT_CONFIGURED":
    st.warning("Upstox WebSocket is not configured. The Live Market terminal requires UPSTOX_ACCESS_TOKEN.")
else:
    st.warning(f'Upstox WebSocket status: {feed.get("status","UNKNOWN")}')

# Keep the interval control OUTSIDE the live fragment. Its value therefore
# cannot be reset by the live update cycle.
chart_interval=st.radio("Chart interval",["1m","5m","15m","30m"],index=0,horizontal=True,label_visibility="collapsed",key="live-chart-interval")
interval_minutes=int(chart_interval[:-1])

@st.cache_data(ttl=1,show_spinner=False)
def terminal_candles(stock_symbol,minutes):
    rows=upstox_intraday_candles(stock_symbol,minutes)
    if not rows:return pd.DataFrame()
    try:
        df=pd.DataFrame(rows)
        if df.shape[1]<5:return pd.DataFrame()
        df.columns=["Timestamp","Open","High","Low","Close","Volume","OI"][:df.shape[1]]
        df["Timestamp"]=pd.to_datetime(df["Timestamp"],errors="coerce",utc=True).dt.tz_convert(IST)
        for c in ["Open","High","Low","Close","Volume","OI"]:
            if c in df:df[c]=pd.to_numeric(df[c],errors="coerce")
        return df.dropna(subset=["Timestamp","Open","High","Low","Close"]).sort_values("Timestamp").drop_duplicates("Timestamp").tail(120).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

def render_chart(df,live_price):
    if df.empty:return
    work=df.copy()
    if live_price is not None and mode=="LIVE":
        i=work.index[-1]
        work.loc[i,"Close"]=live_price
        work.loc[i,"High"]=max(float(work.loc[i,"High"]),live_price)
        work.loc[i,"Low"]=min(float(work.loc[i,"Low"]),live_price)
    view=work.tail(72).reset_index(drop=True)
    lo=float(view.Low.min());hi=float(view.High.max())
    if hi==lo:lo-=.5;hi+=.5
    W,H=1280,420;L,R,T,B=64,22,24,46;PW=W-L-R;PH=H-T-B;n=len(view);step=PW/max(n,1);body=max(3,min(10,step*.62))
    def y(v):return T+(hi-float(v))/(hi-lo)*PH
    grid=[]
    for f in (0,.25,.5,.75,1):
        yy=T+f*PH;val=hi-f*(hi-lo);grid.append(f'<line class="chart-grid" x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}"/><text class="chart-label" x="{L-8}" y="{yy+4:.1f}" text-anchor="end">{val:,.2f}</text>')
    shapes=[]
    for i,row in view.iterrows():
        x=L+(i+.5)*step;o,h,l,c=[float(row[k]) for k in ("Open","High","Low","Close")];yo,yc=y(o),y(c);up=c>=o;wc='chart-wick-up' if up else 'chart-wick-down';bc='chart-body-up' if up else 'chart-body-down';bt=min(yo,yc);bh=max(abs(yc-yo),1.5);shapes.append(f'<line class="{wc}" x1="{x:.2f}" y1="{y(h):.2f}" x2="{x:.2f}" y2="{y(l):.2f}" stroke-width="1.5"/><rect class="{bc}" x="{x-body/2:.2f}" y="{bt:.2f}" width="{body:.2f}" height="{bh:.2f}" rx="1"/>')
    last=float(view.Close.iloc[-1]);ly=y(last);first=view.Timestamp.iloc[0].strftime('%H:%M');lastt=view.Timestamp.iloc[-1].strftime('%H:%M')
    svg=f'<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="{chart_interval} Upstox candlestick chart">{"".join(grid)}{"".join(shapes)}<line class="chart-last" x1="{L}" y1="{ly:.1f}" x2="{W-R}" y2="{ly:.1f}"/><text class="chart-last-label" x="{W-R-4}" y="{ly-6:.1f}" text-anchor="end">₹{last:,.2f}</text><text class="chart-label" x="{L}" y="{H-12}">{first}</text><text class="chart-label" x="{W-R}" y="{H-12}" text-anchor="end">{lastt}</text></svg></div>'
    st.markdown(svg,unsafe_allow_html=True)

@st.fragment(run_every="1s")
def live_terminal():
    quote=live_quote(symbol) if feed_live else None
    live_price=float(quote["ltp"]) if quote and quote.get("ltp") is not None else None
    candles=terminal_candles(symbol,interval_minutes)
    fallback=float(data["last"])
    price=live_price if live_price is not None else fallback
    st.markdown(f'<div class="terminal"><div class="terminal-head"><div class="terminal-title">◉ UPSTOX LIVE TERMINAL · {html.escape(name)} · {chart_interval} CANDLES</div><div class="terminal-price">₹{price:,.2f}</div></div></div>',unsafe_allow_html=True)
    if not candles.empty:
        render_chart(candles,live_price)
        st.caption(f'Upstox V3 · {chart_interval} candles · live LTP overlay · last tick {html.escape(str(feed.get("last_tick_at","—")))}')
    else:
        st.warning("Upstox intraday candle data is unavailable for this instrument. No other chart provider is used.")

live_terminal()

# Non-live structural metrics are rendered once per normal page load.
bias=data.get("bias","NEUTRAL");syn=data.get("synthesis",{}) or {};cls="good" if bias=="BULLISH" else "bad" if bias=="BEARISH" else "neutral"
st.markdown(f'<div style="margin-top:14px"><h3 class="{cls}">{html.escape(str(syn.get("headline","Market structure")))}</h3><p>{html.escape(str(syn.get("detail","No synthesis available.")))}</p></div>',unsafe_allow_html=True)

cols=st.columns(6)
metrics=[(name,f'₹{data["last"]:,.2f}'),("SESSION CHANGE",f'{data["session_change_pct"]:+.2f}%' if data.get("session_change_pct") is not None else "—"),("VWAP",f'{data["vwap"]:,.2f}' if data.get("vwap") is not None else "—"),("OR STATUS",data.get("opening_range_state","—")),("15M MOMENTUM",f'{data["momentum_15m_pct"]:+.2f}%' if data.get("momentum_15m_pct") is not None else "—"),("VOLUME",f'{data["volume_ratio"]:.2f}x' if data.get("volume_ratio") is not None else "—")]
for c,(label,value) in zip(cols,metrics):c.markdown(f'<div class="card"><div class="label">{html.escape(str(label))}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)

st.markdown("### Market structure map")
levels=data.get("levels",{})
a,b,c,d=st.columns(4)
a.metric("Opening Range High",f'{data["opening_range_high"]:,.2f}' if data.get("opening_range_high") else "—");a.metric("Opening Range Low",f'{data["opening_range_low"]:,.2f}' if data.get("opening_range_low") else "—")
b.metric("Recent Resistance",f'{levels.get("recent_resistance",0):,.2f}');b.metric("Recent Support",f'{levels.get("recent_support",0):,.2f}')
c.metric("Session High",f'{levels.get("session_high",0):,.2f}');c.metric("Session Low",f'{levels.get("session_low",0):,.2f}')
d.metric("VWAP Distance",f'{data["vwap_distance_pct"]:+.2f}%' if data.get("vwap_distance_pct") is not None else "—");d.metric("Trend",data.get("trend","—"))

st.caption("MarketPilot uses Upstox for the live terminal and does not fabricate missing market values.")
