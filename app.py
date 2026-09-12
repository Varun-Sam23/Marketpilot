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

st.set_page_config(page_title="MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = Path("data/latest.json")
HISTORY_FILE = Path("data/history.json")
WATCHLIST_FILE = Path("data/watchlist.json")
NSE_CALENDAR = mcal.get_calendar("NSE")
DEFAULT_WATCHLIST = ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS"]
NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown("""
<style>
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1.2rem}
.mp-title{font-family:Georgia,serif;font-size:2.7rem;font-weight:700}.mp-sub{color:#8d9aab;letter-spacing:.12em;text-transform:uppercase;font-size:.7rem}
.card{background:#0d131d;border:1px solid #202b3a;border-radius:15px;padding:16px;min-height:105px}.label{color:#8290a3;font-size:.65rem;text-transform:uppercase;letter-spacing:.12em}.value{font-family:Georgia,serif;font-size:1.5rem;margin-top:5px}.muted{color:#8d9aab}.ticker{overflow:hidden;border:1px solid #202b3a;border-radius:12px;background:#0d131d;padding:10px;white-space:nowrap}.track{display:inline-block;padding-left:100%;animation:scroll 180s linear infinite}@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
/* Hide Streamlit's automatic page list. MarketPilot uses the branded Intelligence Suite navigation below. */
[data-testid="stSidebarNav"]{display:none}
.mp-nav-title{font-family:Arial,sans-serif;font-size:.70rem;color:#8290a3;letter-spacing:.10em;font-weight:600;margin:17px 0 10px 0}
section[data-testid="stSidebar"]{font-family:Arial,sans-serif}
section[data-testid="stSidebar"] [data-testid="stPageLink"]{margin:0 !important;padding:0 !important}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a{min-height:30px !important;height:30px !important;padding:4px 10px !important;margin:1px 0 !important;border-radius:7px !important;font-family:Arial,sans-serif !important;font-size:14px !important;font-weight:500 !important;line-height:21px !important;color:#c7d0dc !important;text-decoration:none !important;gap:8px !important}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover{background:#182231 !important;color:#f0f4f8 !important}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"]{background:#334154 !important;color:#f4f7fa !important;font-weight:600 !important}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a span{font-size:16px !important}
.mp-brand{font-family:Georgia,serif;font-size:17px;font-weight:700;color:#e7edf5;margin:0 0 0 0}
</style>
""", unsafe_allow_html=True)

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def trading_day(day=None):
    day = day or datetime.now(IST).date()
    return not NSE_CALENDAR.schedule(start_date=day, end_date=day).empty

def market_status():
    now = datetime.now(IST)
    if not trading_day(now.date()):
        return "MARKET CLOSED"
    return "MARKET LIVE" if time(9, 15) <= now.time() <= time(15, 30) else "MARKET CLOSED"

@st.cache_data(ttl=60, show_spinner=False)
def index_data():
    rows=[]
    for ticker, name in [("^NSEI","NIFTY 50"),("^NSEBANK","BANK NIFTY"),("^BSESN","SENSEX"),("^INDIAVIX","INDIA VIX")]:
        try:
            h=yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
            if not h.empty:
                last=float(h["Close"].iloc[-1]); first=float(h["Open"].iloc[0])
                rows.append({"Index":name,"Last":round(last,2),"Session %":round((last/first-1)*100,2) if first else 0})
        except Exception:
            pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=60, show_spinner=False)
def news_data():
    items=[]
    for group,url in NEWS_FEEDS:
        try:
            feed=feedparser.parse(url)
            for e in feed.entries[:8]:
                title=e.get("title","").strip()
                publisher=""
                src=e.get("source")
                if isinstance(src,dict): publisher=str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m=re.search(r"\s+-\s+([^-]+)$",title)
                    publisher=m.group(1).strip() if m else "Unknown publisher"
                clean=re.sub(r"\s+-\s+([^-]+)$","",title).strip()
                items.append({"title":clean,"publisher":publisher,"feed_group":group,"published":e.get("published",""),"link":e.get("link","")})
        except Exception:
            pass
    return items[:28]

# Branded navigation: intentionally replaces Streamlit's automatic page menu.
with st.sidebar:
    st.markdown('<div class="mp-brand">◈ MarketPilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="mp-nav-title">INTELLIGENCE SUITE</div>', unsafe_allow_html=True)
    st.page_link("app.py", label="Main Dashboard", icon="🏠")
    st.page_link("pages/1_Stock_Intelligence.py", label="Stock Intelligence", icon="📊")
    st.page_link("pages/2_Catalyst_Radar.py", label="Catalyst Radar", icon="⚡")
    st.page_link("pages/3_Market_Regime.py", label="Market Regime", icon="🌐")
    st.page_link("pages/4_Institutional_Flow.py", label="Institutional Flow", icon="🏦")
    st.page_link("pages/5_Options_Intelligence.py", label="Options Intelligence", icon="📐")
    st.page_link("pages/6_Intraday_Market_Structure.py", label="Intraday Market Structure", icon="⚡")
    st.page_link("pages/7_Sector_Intelligence.py", label="Sector Intelligence", icon="🏭")
    st.page_link("pages/8_Performance_Tracker.py", label="Performance Tracker", icon="📈")
    st.page_link("pages/9_Thesis_Calibration.py", label="Thesis Calibration", icon="🎯")

status=market_status(); now=datetime.now(IST); report=load_json(DATA_FILE,{})
raw_news=news_data(); news_intel=enrich_news(raw_news); indices=index_data(); watchlist=load_json(WATCHLIST_FILE,DEFAULT_WATCHLIST)
st_autorefresh(interval=60_000, key="marketpilot_refresh")

st.markdown('<div class="mp-title">◈ MarketPilot</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Indian markets · intelligence before action · evidence-first decision support</div>', unsafe_allow_html=True)
st.write(f"**{'🟢' if status=='MARKET LIVE' else '⚪'} {status}** · {now.strftime('%A · %d %B %Y · %H:%M:%S IST')}")

verified=sum(x.get("claim_status")=="SUPPORTED" for x in news_intel)
strong=sum(int(x.get("evidence_score",10))>=75 for x in news_intel)
c1,c2,c3,c4=st.columns(4)
for c,label,value in [(c1,"Market",status),(c2,"Live stories",len(news_intel)),(c3,"Supported claims",verified),(c4,"Strong evidence",strong)]:
    c.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)

if news_intel:
    parts=[]
    for x in news_intel[:12]:
        badge={"SUPPORTED":"🟢","DISPUTED":"🔴","INSUFFICIENT EVIDENCE":"🟡"}.get(x.get("claim_status"),"🟡")
        parts.append(f"{badge} {html.escape(x.get('title',''))} · {html.escape(x.get('publisher','Unknown'))}")
    st.markdown('<div class="ticker"><div class="track">'+' &nbsp; ◆ &nbsp; '.join(parts)+'</div></div>', unsafe_allow_html=True)

if not indices.empty:
    cols=st.columns(len(indices))
    for c,(_,r) in zip(cols,indices.iterrows()):
        c.markdown(f'<div class="card"><div class="label">{html.escape(r["Index"])}</div><div class="value">{r["Last"]:,.2f}</div><div class="muted">Session {r["Session %"]:+.2f}%</div></div>',unsafe_allow_html=True)

morning,decision,live,news_tab,performance=st.tabs(["🌅 MORNING INTELLIGENCE","🎯 DECISION CENTER","⚡ LIVE MARKET","📰 NEWS INTELLIGENCE","📓 PERFORMANCE"])

with morning:
    ai=report.get("ai_analysis",{})
    st.subheader("Morning Intelligence")
    if ai.get("enabled"):
        st.markdown(f"### {ai.get('bias','UNKNOWN')} · {ai.get('market_regime','UNKNOWN')}")
        st.write(ai.get("thesis","No thesis recorded."))
        a,b,c=st.columns(3)
        a.info("🟢 Bull case\n\n"+str(ai.get("bull_case","Not available")))
        b.warning("🟡 Base case\n\n"+str(ai.get("base_case","Not available")))
        c.error("🔴 Bear case\n\n"+str(ai.get("bear_case","Not available")))
    else:
        st.info("No fresh morning thesis is available. MarketPilot does not invent a view on closed sessions.")
    levels=report.get("levels",{})
    if levels: st.dataframe(pd.DataFrame([levels]),use_container_width=True,hide_index=True)

with decision:
    st.subheader("Decision Center")
    decision_obj=report.get("decision",{})
    if decision_obj:
        d1,d2,d3=st.columns(3)
        d1.metric("Decision score",decision_obj.get("score","—"))
        d2.metric("Bias",decision_obj.get("bias",report.get("verdict","WAIT")))
        d3.metric("Confidence",decision_obj.get("confidence","—"))
        st.write(decision_obj.get("methodology","Evidence-weighted decision support."))
    else:
        st.info("Decision framework will populate after the next intelligence run.")

with live:
    st.subheader("Live Market")
    if indices.empty: st.warning("Market data is unavailable from the public feed.")
    else: st.dataframe(indices,use_container_width=True,hide_index=True)
    st.subheader("Watchlist")
    rows=[]
    for ticker in watchlist:
        try:
            h=yf.Ticker(ticker).history(period="3mo",interval="1d",auto_adjust=False)
            if len(h)>=22:
                last=float(h.Close.iloc[-1]);prev=float(h.Close.iloc[-2]);sma=float(h.Close.tail(20).mean())
                rows.append({"Stock":ticker.replace('.NS',''),"1D %":round((last/prev-1)*100,2),"20D %":round((last/float(h.Close.iloc[-21])-1)*100,2),"vs 20D SMA %":round((last/sma-1)*100,2)})
        except Exception: pass
    if rows: st.dataframe(pd.DataFrame(rows).sort_values("1D %",ascending=False),use_container_width=True,hide_index=True)

with news_tab:
    st.subheader("News Intelligence")
    if news_intel:
        rows=[]
        for x in news_intel[:20]:
            title=re.sub(r"^(🟢 SUPPORTED|🔴 DISPUTED|🟡 INSUFFICIENT EVIDENCE)\s*·\s*","",x.get("title",""))
            rows.append({"Claim Status":x.get("claim_status","INSUFFICIENT EVIDENCE"),"Headline":title,"Verification":x.get("verification","UNVERIFIED"),"Evidence":x.get("evidence_score",10),"Sources":x.get("evidence_count",0),"Impact":x.get("impact","NEUTRAL"),"Publisher":x.get("publisher","Unknown")})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else: st.info("No current headlines available.")

with performance:
    st.subheader("Thesis Journal")
    history=load_json(HISTORY_FILE,[])
    if history:
        st.dataframe(pd.DataFrame(history[-30:]),use_container_width=True,hide_index=True)
    else:
        st.info("No completed trading-day thesis has been journaled yet. Use Performance Tracker for outcome evaluation and Thesis Calibration for confidence accuracy.")

st.caption("MarketPilot uses public/free data feeds which may be delayed, incomplete or unavailable. Research and decision support only — no order execution.")
