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

st.set_page_config(page_title="MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
DATA_FILE=Path("data/latest.json")
WATCHLIST_FILE=Path("data/watchlist.json")
HISTORY_FILE=Path("data/history.json")
IST=ZoneInfo("Asia/Kolkata")
NSE_CALENDAR=mcal.get_calendar("NSE")
DEFAULT_WATCHLIST=["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","INFY.NS","TCS.NS","TATAMOTORS.NS","ITC.NS"]
NEWS_FEEDS=[
 ("India Markets","https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
 ("RBI / Economy","https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
 ("Indian Companies","https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
 ("Global Markets","https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

# Explicit navigation for the research pages. Streamlit normally discovers these
# automatically, but direct links keep the full intelligence suite visible after
# deployments and page-cache refreshes.
with st.sidebar:
    st.markdown("### MarketPilot Intelligence")
    st.page_link("pages/1_Stock_Intelligence.py", label="Stock Intelligence", icon="📊")
    st.page_link("pages/2_Catalyst_Radar.py", label="Catalyst Radar", icon="⚡")
    st.page_link("pages/3_Market_Regime.py", label="Market Regime", icon="🌐")
    st.page_link("pages/4_Institutional_Flow.py", label="Institutional Flow", icon="🏦")
    st.page_link("pages/5_Options_Intelligence.py", label="Options Intelligence", icon="📐")
    st.page_link("pages/6_Intraday_Market_Structure.py", label="Intraday Market Structure", icon="⚡")
    st.page_link("pages/7_Sector_Intelligence.py", label="Sector Intelligence", icon="🏭")
    st.page_link("pages/8_Performance_Tracker.py", label="Performance Tracker", icon="📈")
    st.page_link("pages/9_Thesis_Calibration.py", label="Thesis Calibration", icon="🎯")

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b;--green:#59b987;--red:#e27a75;--shadow:0 14px 34px rgba(0,0,0,.22)}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 27%),radial-gradient(circle at 0% 30%,rgba(84,123,155,.08),transparent 30%),var(--bg)}
[data-testid="stHeader"]{background:transparent}[data-testid="stMainBlockContainer"]{max-width:1460px!important;padding-top:.45rem!important}.main .block-container{max-width:1460px;padding:.45rem 2.1rem 4rem}
.mp-brand{display:flex;align-items:center;gap:.8rem}.mp-orb{width:40px;height:40px;border:1px solid rgba(201,168,91,.55);border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--gold);font-size:1.35rem;background:rgba(201,168,91,.06)}.mp-title{font-family:Georgia,"Times New Roman",serif;font-size:2.75rem;font-weight:600;letter-spacing:-.035em;color:var(--ink)}.mp-sub{margin:.35rem 0 .7rem 3.2rem;color:var(--muted);font-size:.72rem;letter-spacing:.18em;text-transform:uppercase}.mp-rule{height:1px;background:linear-gradient(90deg,var(--gold),transparent 70%);opacity:.55;margin:.3rem 0 .7rem}.mp-meta{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;margin-bottom:.45rem}.mp-status{display:inline-flex;align-items:center;gap:.42rem;padding:.3rem .65rem;border:1px solid var(--line);border-radius:999px;font-size:.67rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink)}.mp-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px rgba(89,185,135,.65)}.mp-dot.closed{background:#707985;box-shadow:none}.mp-clock{font-size:.73rem;color:var(--muted)}
.mp-command-deck{display:grid;grid-template-columns:1.15fr 1fr 1fr 1fr;gap:.65rem;margin:.65rem 0 .9rem;padding:.65rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(100deg,rgba(201,168,91,.09),rgba(255,255,255,.018) 52%,rgba(84,123,155,.055));box-shadow:0 12px 30px rgba(0,0,0,.16)}.mp-command-item{min-height:58px;padding:.62rem .8rem;border-right:1px solid var(--line)}.mp-command-item:last-child{border-right:0}.mp-command-label{font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted)}.mp-command-value{font-family:Georgia,"Times New Roman",serif;font-size:1rem;color:var(--ink);margin-top:.18rem}.mp-command-meta{font-size:.62rem;color:var(--muted);margin-top:.12rem}
.mp-wire{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:.65rem}.mp-ticker{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:linear-gradient(90deg,rgba(201,168,91,.06),rgba(255,255,255,.018));padding:9px 0;box-shadow:var(--shadow)}.mp-track{display:inline-block;white-space:nowrap;padding-left:100%;animation:mp-scroll 180s linear infinite;font-size:.82rem;color:var(--ink)}.mp-track:hover{animation-play-state:paused}.mp-news-item{display:inline-block;margin-right:30px}.mp-news-item small{color:var(--muted)}@keyframes mp-scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.mp-card,.dc-card{background:linear-gradient(180deg,rgba(255,255,255,.032),rgba(255,255,255,.018));border:1px solid var(--line);border-radius:17px;padding:1rem;box-shadow:0 9px 28px rgba(0,0,0,.14)}.mp-kicker,.dc-label{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.mp-price{font-family:Georgia,"Times New Roman",serif;font-size:1.55rem;color:var(--ink);margin:.25rem 0 .15rem}.mp-change{font-size:.75rem;color:var(--muted)}.mp-section,.dc-section{font-family:Georgia,"Times New Roman",serif;color:var(--ink);font-size:1.55rem;margin:1.55rem 0 .7rem}.mp-hero{background:linear-gradient(135deg,rgba(201,168,91,.11),rgba(255,255,255,.015) 42%,rgba(99,130,159,.06));border:1px solid var(--line);border-radius:22px;padding:1.2rem;box-shadow:var(--shadow)}.mp-eyebrow{font-size:.65rem;letter-spacing:.16em;text-transform:uppercase;color:var(--gold)}.mp-big{font-family:Georgia,"Times New Roman",serif;font-size:2rem;color:var(--ink);line-height:1.1;margin:.35rem 0 .45rem}.mp-muted{color:var(--muted);font-size:.8rem;line-height:1.5}.mp-chip{display:inline-flex;padding:.25rem .55rem;border-radius:999px;border:1px solid var(--line);font-size:.68rem;color:var(--muted);margin:.35rem .3rem 0 0}.mp-scenario{border:1px solid var(--line);border-radius:15px;background:rgba(255,255,255,.018);padding:1rem;min-height:145px}.mp-scenario h4,.dc-case h4{font-family:Georgia,"Times New Roman",serif;color:var(--ink)}.mp-scenario p,.dc-case p{color:#c5cbd3;line-height:1.5;font-size:.82rem}.dc-sub{color:var(--muted);font-size:.82rem;margin:.35rem 0 1.2rem}.dc-score{font-family:Georgia,"Times New Roman",serif;font-size:4.8rem;line-height:1;color:var(--ink)}.dc-scorebar{height:10px;border-radius:999px;background:linear-gradient(90deg,#a44f49 0%,#a44f49 35%,#9a7b35 35%,#9a7b35 65%,#2f6f52 65%,#2f6f52 100%);overflow:hidden}.dc-marker{height:100%;width:3px;background:#f5f1e8}.dc-case{min-height:150px}.dc-bull{border-top:2px solid #2f6f52}.dc-base{border-top:2px solid #9a7b35}.dc-bear{border-top:2px solid #a44f49}.dc-foot{border-top:1px solid var(--line);margin-top:2rem;padding-top:.8rem;color:#687280;font-size:.68rem;text-align:center}.news-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:.65rem;margin:.9rem 0 1.1rem}.news-stat{border:1px solid var(--line);border-radius:14px;padding:.8rem 1rem;background:rgba(255,255,255,.018)}.news-stat-label{font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}.news-stat-value{font-family:Georgia,serif;font-size:1.35rem;color:var(--ink);margin-top:.15rem}.news-evidence{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.018);padding:1rem;margin-top:.85rem}.news-evidence-title{font-size:.63rem;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}.news-evidence-head{font-family:Georgia,serif;color:var(--ink);font-size:1.05rem;margin:.3rem 0}.news-evidence-meta{font-size:.75rem;color:var(--muted);line-height:1.6}button[data-baseweb="tab"]{font-size:.75rem;letter-spacing:.05em}.mp-foot{border-top:1px solid var(--line);margin-top:2.2rem;padding-top:.9rem;color:#687280;font-size:.68rem;text-align:center}
@media(max-width:900px){[data-testid="stMainBlockContainer"]{padding-top:.2rem!important}.main .block-container{padding:.2rem .9rem 3rem}.mp-title{font-size:2.15rem}.mp-sub{margin-left:2.8rem;font-size:.61rem}.mp-big{font-size:1.65rem}.mp-section,.dc-section{font-size:1.35rem}.news-summary{grid-template-columns:1fr 1fr}.mp-command-deck{grid-template-columns:1fr 1fr}.mp-command-item:nth-child(2n){border-right:0}.mp-command-item:nth-child(-n+2){border-bottom:1px solid var(--line)}}
</style>
""")

def load_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def is_trading_day(day=None):
    day=day or datetime.now(IST).date();return not NSE_CALENDAR.schedule(start_date=day,end_date=day).empty

def market_status():
    now=datetime.now(IST)
    if not is_trading_day(now.date()):return "MARKET CLOSED"
    return "MARKET LIVE" if time(9,15)<=now.time()<=time(15,30) else "MARKET CLOSED"

@st.cache_data(ttl=60,show_spinner=False)
def index_snapshot():
    rows=[]
    for ticker in ("^NSEI","^NSEBANK","^BSESN","^INDIAVIX"):
        try:
            h=yf.Ticker(ticker).history(period="1d",interval="5m",auto_adjust=False)
            if not h.empty:
                last=float(h["Close"].iloc[-1]);first=float(h["Open"].iloc[0]);rows.append({"ticker":ticker,"last":last,"change_pct":((last/first)-1)*100 if first else 0})
        except Exception:pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=60,show_spinner=False)
def watchlist_data(tickers):
    rows=[]
    for ticker in tickers:
        try:
            h=yf.Ticker(ticker).history(period="3mo",interval="1d",auto_adjust=False)
            if len(h)>=22:
                last=float(h["Close"].iloc[-1]);prev=float(h["Close"].iloc[-2]);sma20=float(h["Close"].tail(20).mean());avgvol=float(h["Volume"].tail(20).mean())
                rows.append({"Stock":ticker.replace(".NS",""),"Last":round(last,2),"1D %":round(((last/prev)-1)*100,2),"20D %":round(((last/float(h["Close"].iloc[-21]))-1)*100,2),"vs 20D SMA %":round(((last/sma20)-1)*100,2),"Vol / 20D":round(float(h["Volume"].iloc[-1])/avgvol,2) if avgvol else None})
        except Exception:pass
    return pd.DataFrame(rows)
