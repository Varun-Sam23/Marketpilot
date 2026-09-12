import html
import json
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import pandas_market_calendars as mcal
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

from news_intelligence import enrich_news

st.set_page_config(page_title="MarketPilot", page_icon="◩", layout="wide", initial_sidebar_state="collapsed")

DATA_FILE = Path("data/latest.json")
WATCHLIST_FILE = Path("data/watchlist.json")
HISTORY_FILE = Path("data/history.json")
IST = ZoneInfo("Asia/Kolkata")
NSE_CALENDAR = mcal.get_calendar("NSE")

DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS",
]

NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown(r'''
<style>
:root {
  --paper:#f3efe7;
  --paper-2:#ebe5da;
  --ink:#202633;
  --muted:#70756f;
  --line:rgba(32,38,51,.13);
  --brass:#9a7b35;
  --green:#2f6f52;
  --red:#a44f49;
  --blue:#3e6078;
  --card:rgba(255,255,255,.80);
}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 90% 0%,rgba(154,123,53,.08),transparent 30%),var(--paper)}
[data-testid="stHeader"]{background:transparent}
.main .block-container{max-width:1460px;padding:2.1rem 2.4rem 4rem}
.mp-brand{display:flex;align-items:flex-end;gap:.8rem}
.mp-glyph{font-size:2.5rem;line-height:1;color:var(--brass)}
.mp-title{font-family:Georgia,"Times New Roman",serif;font-size:2.95rem;line-height:1;font-weight:600;letter-spacing:-.04em;color:var(--ink)}
.mp-sub{font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:.55rem 0 1.2rem 3.35rem}
.mp-rule{border-top:1px solid var(--line);margin:.5rem 0 1rem}
.mp-meta{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;margin-bottom:.8rem}
.mp-status{display:inline-flex;align-items:center;gap:.42rem;border:1px solid var(--line);background:rgba(255,255,255,.55);padding:.34rem .68rem;border-radius:999px;font-size:.7rem;letter-spacing:.1em;text-transform:uppercase}
.mp-dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
.mp-dot.closed{background:#8c8f88}
.mp-time{font-size:.78rem;color:var(--muted)}
.mp-wire{font-size:.67rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:.9rem}
.mp-news{overflow:hidden;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.62);padding:10px 0;box-shadow:0 6px 20px rgba(32,38,51,.025)}
.mp-track{display:inline-block;white-space:nowrap;padding-left:100%;animation:scroll 180s linear infinite;font-size:14px}
.mp-track:hover{animation-play-state:paused}
.mp-news-item{display:inline-block;margin-right:28px}
.mp-news-item small{color:var(--muted)}
@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.mp-card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:1rem 1.1rem;box-shadow:0 8px 26px rgba(32,38,51,.035)}
.mp-kicker{font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.mp-price{font-family:Georgia,"Times New Roman",serif;font-size:1.7rem;font-weight:600;color:var(--ink);margin-top:.25rem}
.mp-caption{font-size:.76rem;color:var(--muted);margin-top:.22rem}
.mp-section{font-family:Georgia,"Times New Roman",serif;font-size:1.72rem;color:var(--ink);margin:1.45rem 0 .65rem}
.mp-callout{border-left:3px solid var(--brass);background:rgba(154,123,53,.07);border-radius:0 14px 14px 0;padding:1rem 1.15rem}
.mp-scenario{border:1px solid var(--line);background:rgba(255,255,255,.58);border-radius:16px;padding:1rem;min-height:145px}
.mp-scenario h4{font-family:Georgia,"Times New Roman",serif;margin:.1rem 0 .5rem}
.mp-scenario p{margin:0;line-height:1.55;color:#444b55}
.mp-foot{border-top:1px solid var(--line);margin-top:2.4rem;padding-top:.9rem;color:var(--muted);font-size:.72rem;text-align:center}
[data-testid="stMetricValue"]{font-family:Georgia,"Times New Roman",serif}
button[data-baseweb="tab"]{font-size:.82rem;letter-spacing:.02em}
</style>
''', unsafe_allow_html=True)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def is_trading_day(day=None):
    day = day or datetime.now(IST).date()
    return not NSE_CALENDAR.schedule(start_date=day, end_date=day).empty


def market_status():
    now = datetime.now(IST)
    if not is_trading_day(now.date()):
        return "MARKET CLOSED"
    if time(9, 15) <= now.time() <= time(15, 30):
        return "MARKET LIVE"
    return "MARKET CLOSED"


@st.cache_data(ttl=60, show_spinner=False)
def index_snapshot(tickers=("^NSEI", "^NSEBANK", "^BSESN", "^INDIAVIX")):
    rows=[]
    for ticker in tickers:
        try:
            h=yf.Ticker(ticker).history(period="1d",interval="5m",auto_adjust=False)
            if not h.empty:
                last=float(h["Close"].iloc[-1]); first=float(h["Open"].iloc[0])
                rows.append({"ticker":ticker,"last":last,"change_pct":((last/first)-1)*100 if first else 0})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def watchlist_data(tickers):
    rows=[]
    for ticker in tickers:
        try:
            h=yf.Ticker(ticker).history(period="3mo",interval="1d",auto_adjust=False)
            if len(h)>=22:
                last=float(h["Close"].iloc[-1]); prev=float(h["Close"].iloc[-2]); sma20=float(h["Close"].tail(20).mean())
                ret20=((last/float(h["Close"].iloc[-21]))-1)*100; vol=float(h["Volume"].iloc[-1]); avgvol=float(h["Volume"].tail(20).mean())
                rows.append({"Stock":ticker.replace(".NS",""),"Last":round(last,2),"1D %":round(((last/prev)-1)*100,2),"20D %":round(ret20,2),"vs 20D SMA %":round(((last/sma20)-1)*100,2),"Vol / 20D":round(vol/avgvol,2) if avgvol else None})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def live_news():
    items=[]
    for feed_group,url in NEWS_FEEDS:
        try:
            feed=feedparser.parse(url)
            for entry in feed.entries[:8]:
                title=entry.get("title","").strip(); publisher=""
                src=entry.get("source")
                if isinstance(src,dict):
                    publisher=str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m=re.search(r"\s+-\s+([^-]+)$",title)
                    if m: publisher=m.group(1).strip()
                if not publisher or publisher.lower()=="news.google.com": publisher="Unknown publisher"
                clean=re.sub(r"\s+-\s+([^-]+)$","",title).strip() if publisher!="Unknown publisher" else title
                items.append({"title":clean,"publisher":publisher,"source":publisher,"feed_group":feed_group,"published":entry.get("published",""),"link":entry.get("link","")})
        except Exception:
            pass
    return items[:28]


def icon(impact):
    return {"POSITIVE":"↗","NEGATIVE":"↘","NEUTRAL":"→","UNKNOWN":"?"}.get(impact,"→")


report=load_json(DATA_FILE,{})
status=market_status(); now=datetime.now(IST)
raw_news=live_news(); news_intel=enrich_news(raw_news)

st_autorefresh(interval=60_000,key="marketpilot_refresh")

st.markdown('<div class="mp-brand"><div class="mp-glyph">◩</div><div class="mp-title">MarketPilot</div></div>',unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Indian markets · intelligence first · research & decision support</div>',unsafe_allow_html=True)
dot_class="mp-dot" if status=="MARKET LIVE" else "mp-dot closed"
label=status.replace("MARKET ","").title()
st.markdown(f'<div class="mp-meta"><span class="mp-status"><span class="{dot_class}"></span> {label}</span><span class="mp-time">{now.strftime("%A, %d %B %Y · %H:%M:%S IST")}</span></div>',unsafe_allow_html=True)
st.markdown('<div class="mp-rule"></div>',unsafe_allow_html=True)

st.markdown('<div class="mp-wire">Live wire · auto-updating public feeds</div>',unsafe_allow_html=True)
if news_intel:
    chunks=[]
    for item in news_intel[:12]:
        v=item.get("verification","UNVERIFIED")
        badge="✅ CORROBORATED" if v=="CORROBORATED" else "⚠️ SINGLE SOURCE" if v=="SINGLE_SOURCE" else "⚠️ UNVERIFIED"
        chunks.append(f'<span class="mp-news-item"><b>{badge}</b> {html.escape(item.get("title",""))} <small>• {html.escape(item.get("publisher","Unknown publisher"))} • {html.escape(item.get("impact","NEUTRAL"))}</small></span>')
    st.markdown('<div class="mp-news"><div class="mp-track">'+' &nbsp; ◆ &nbsp; '.join(chunks)+'</div></div>',unsafe_allow_html=True)
else:
    st.info("Live news temporarily unavailable.")
st.caption("The ticker pauses on hover. Corroborated means similar reporting exists across multiple publisher domains; it is not a guarantee of truth.")

indices=index_snapshot(); lookup={r["ticker"]:r for _,r in indices.iterrows()} if not indices.empty else {}
card_defs=[("NIFTY 50","^NSEI"),("BANK NIFTY","^NSEBANK"),("SENSEX","^BSESN"),("INDIA VIX","^INDIAVIX")]
cols=st.columns(4)
for col,(name,ticker) in zip(cols,card_defs):
    row=lookup.get(ticker); last=f'{row["last"]:,.2f}' if row is not None else "—"; chg=f'{row["change_pct"]:+.2f}%' if row is not None else "—"
    col.markdown(f'<div class="mp-card"><div class="mp-kicker">{name}</div><div class="mp-price">{last}</div><div class="mp-caption">{"From open" if status=="MARKET LIVE" else "Last session"}: {chg}</div></div>',unsafe_allow_html=True)

morning,live,news_tab,performance=st.tabs(["🌅 Morning Intelligence","⚡ Live Market","📰 News Intelligence","📓 Performance"])

with morning:
    st.markdown('<div class="mp-section">Morning brief</div>',unsafe_allow_html=True)
    ai=report.get("ai_analysis",{})
    if ai.get("enabled"):
        a,b,c,d=st.columns(4); a.metric("AI Bias",ai.get("bias","UNKNOWN")); b.metric("Regime",ai.get("market_regime","UNKNOWN")); c.metric("Confidence",ai.get("confidence","LOW")); d.metric("Rule Bias",report.get("verdict","WAIT"))
        st.markdown(f'<div class="mp-callout"><div class="mp-kicker">Core thesis</div><div style="margin-top:.3rem;font-size:1.05rem;line-height:1.55">{html.escape(ai.get("thesis",""))}</div></div>',unsafe_allow_html=True)
        st.write("")
        x,y,z=st.columns(3)
        with x: st.markdown(f'<div class="mp-scenario"><h4>🟢 Bull case</h4><p>{html.escape(ai.get("bull_case",""))}</p></div>',unsafe_allow_html=True)
        with y: st.markdown(f'<div class="mp-scenario"><h4>🟡 Base case</h4><p>{html.escape(ai.get("base_case",""))}</p></div>',unsafe_allow_html=True)
        with z: st.markdown(f'<div class="mp-scenario"><h4>🔴 Bear case</h4><p>{html.escape(ai.get("bear_case",""))}</p></div>',unsafe_allow_html=True)
        st.markdown('<div class="mp-section">Key levels</div>',unsafe_allow_html=True)
        for level in ai.get("key_levels",[]): st.write("•",level)
        if ai.get("invalidation"): st.warning(ai.get("invalidation"))
        x,y=st.columns(2)
        with x:
            st.markdown('<div class="mp-section">Drivers</div>',unsafe_allow_html=True)
            for item in ai.get("drivers",[]): st.write("•",item)
        with y:
            st.markdown('<div class="mp-section">Risks</div>',unsafe_allow_html=True)
            for item in ai.get("risks",[]): st.write("•",item)
    else:
        st.warning(ai.get("status","AI ANALYSIS NOT AVAILABLE"))
    st.markdown('<div class="mp-section">Market structure</div>',unsafe_allow_html=True)
    levels=report.get("levels",{})
    if levels: st.dataframe(pd.DataFrame([levels]),use_container_width=True,hide_index=True)
    else: st.caption("Technical structure will populate on the next trading-day analysis run.")
    st.markdown('<div class="mp-section">Sector pulse</div>',unsafe_allow_html=True)
    sectors=report.get("sectors",[])
    if sectors:
        sdf=pd.DataFrame(sectors).rename(columns={"sector":"Sector","avg_change_pct":"Avg 1D %","members":"Members"}); sdf["Avg 1D %"]=sdf["Avg 1D %"].round(2); st.dataframe(sdf,use_container_width=True,hide_index=True)
    else: st.caption("Sector data will populate on a trading-day run.")

with live:
    st.markdown('<div class="mp-section">Live market monitor</div>',unsafe_allow_html=True)
    if indices.empty: st.warning("Live market data unavailable from the public feed right now.")
    else:
        ldf=indices.copy(); ldf["ticker"]=ldf["ticker"].replace({"^NSEI":"NIFTY 50","^NSEBANK":"BANK NIFTY","^BSESN":"SENSEX","^INDIAVIX":"INDIA VIX"}); ldf["last"]=ldf["last"].round(2); ldf["change_pct"]=ldf["change_pct"].round(2); st.dataframe(ldf.rename(columns={"ticker":"Index","last":"Last","change_pct":"From open %"}),use_container_width=True,hide_index=True)
    st.markdown('<div class="mp-section">Watchlist</div>',unsafe_allow_html=True)
    watchlist=load_json(WATCHLIST_FILE,DEFAULT_WATCHLIST); wdf=watchlist_data(tuple(watchlist))
    if not wdf.empty: st.dataframe(wdf.sort_values("1D %",ascending=False),use_container_width=True,hide_index=True)
    else: st.caption("Watchlist data temporarily unavailable.")

with news_tab:
    st.markdown('<div class="mp-section">News intelligence</div>',unsafe_allow_html=True)
    st.caption("Publisher attribution is separated from Google News aggregation. Verification indicates corroboration, not certainty.")
    if news_intel:
        ndf=pd.DataFrame(news_intel)
        ndf["Verification"]=ndf["verification_label"]
        ndf["Impact"]=ndf["impact"].map(lambda x:f"{icon(x)} {x}")
        ndf["Publisher"]=ndf["publisher"].replace({"":"Unknown publisher"})
        keep=["title","Verification","Impact","affected","Publisher","published","verification_detail","impact_reason"]
        ndf=ndf[keep].rename(columns={"title":"Headline","affected":"Affected","published":"Published","verification_detail":"Evidence","impact_reason":"Impact reasoning"})
        st.dataframe(ndf,use_container_width=True,hide_index=True)
    else: st.info("No live headlines available.")

with performance:
    st.markdown('<div class="mp-section">Thesis journal</div>',unsafe_allow_html=True)
    history=load_json(HISTORY_FILE,[])
    if history:
        hdf=pd.DataFrame([{"Date":x.get("date_ist",""),"Rule Bias":x.get("rule_bias",""),"Rule Confidence":x.get("rule_confidence",""),"AI Bias":x.get("ai",{}).get("bias",""),"AI Confidence":x.get("ai",{}).get("confidence",""),"Regime":x.get("ai",{}).get("market_regime","")} for x in history[-30:]])
        st.dataframe(hdf,use_container_width=True,hide_index=True)
        st.caption("Outcome scoring will be added after enough trading sessions are available.")
    else: st.info("No completed trading-day thesis has been journaled yet.")

st.markdown('<div class="mp-foot">MarketPilot uses public/free data feeds that may be delayed, incomplete or unavailable. Research and decision support only. No order execution.</div>',unsafe_allow_html=True)
