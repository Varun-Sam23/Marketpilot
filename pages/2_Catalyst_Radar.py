import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import pandas as pd
import streamlit as st
import yfinance as yf

from menu import render_sidebar

st.set_page_config(page_title="MarketPilot · Catalyst Radar", page_icon="⚡", layout="wide")
render_sidebar()

DATA_FILE = Path("data/latest.json")
WATCHLIST = {
    "RELIANCE.NS": "RELIANCE", "HDFCBANK.NS": "HDFCBANK", "ICICIBANK.NS": "ICICIBANK", "SBIN.NS": "SBIN",
    "INFY.NS": "INFY", "TCS.NS": "TCS", "TATAMOTORS.NS": "TATAMOTORS", "ITC.NS": "ITC",
}
CATALYST_FEEDS = [
    ("Earnings", "https://news.google.com/rss/search?q=India%20stocks%20earnings%20results%20guidance&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Macro", "https://news.google.com/rss/search?q=RBI%20India%20inflation%20GDP%20policy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global", "https://news.google.com/rss/search?q=Fed%20oil%20tariffs%20geopolitics%20global%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Corporate", "https://news.google.com/rss/search?q=India%20stocks%20dividend%20buyback%20merger%20order%20approval&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 28%),var(--bg)}
.main .block-container{max-width:1460px;padding:1.1rem 2.1rem 4rem}.cr-k{font-size:.63rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gold)}.cr-title{font-family:Georgia,serif;font-size:2.5rem;color:var(--ink);margin:.25rem 0}.cr-sub{color:var(--muted);font-size:.8rem;line-height:1.5;max-width:900px}.cr-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.2rem 0}.cr-card{border:1px solid var(--line);border-radius:16px;padding:.9rem 1rem;background:rgba(255,255,255,.018)}.cr-label{font-size:.57rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.cr-value{font-family:Georgia,serif;font-size:1.45rem;color:var(--ink);margin-top:.2rem}.cr-hero{border:1px solid var(--line);border-radius:19px;padding:1.1rem;background:linear-gradient(115deg,rgba(201,168,91,.10),rgba(255,255,255,.018));margin:1rem 0}.cr-head{font-family:Georgia,serif;font-size:1.25rem;color:var(--ink)}.cr-meta{font-size:.73rem;color:var(--muted);line-height:1.6}.cr-score{font-family:Georgia,serif;font-size:2.4rem;color:var(--ink)}.cr-divider{height:1px;background:var(--line);margin:.9rem 0}.cr-news-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem;margin-top:.8rem}.cr-news{border:1px solid var(--line);border-radius:16px;padding:1rem;background:rgba(255,255,255,.018);min-height:175px}.cr-news-head{font-family:Georgia,serif;font-size:1rem;line-height:1.4;color:var(--ink);margin:.45rem 0}.cr-gist{color:#b4beca;font-size:.78rem;line-height:1.5;margin:.5rem 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.cr-source{color:var(--muted);font-size:.66rem;line-height:1.5}.impact-high{color:#ff7b83}.impact-medium{color:#ffd45c}.impact-low{color:#8fa0b3}
</style>
""", unsafe_allow_html=True)

def load_report():
    try:return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:return {}

def parse_dt(value):
    try:
        dt=parsedate_to_datetime(value)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:return None

def clean_gist(value, headline=""):
    text=re.sub(r"<[^>]+>"," ",str(value or ""))
    text=re.sub(r"\s+"," ",text).strip()
    text=re.sub(r"^(?:\s*[-–—|]\s*)+", "", text)
    if text and text.lower()!=headline.lower(): return text[:360].rstrip(" .") + ("…" if len(text)>360 else ".")
    return "The report highlights a market-relevant development that may affect investor sentiment, sector expectations or the stock-specific outlook. Review the source for the full context."

def catalyst_type(text):
    t=text.lower()
    if any(k in t for k in ("earnings","results","profit","revenue","guidance")):return "EARNINGS"
    if any(k in t for k in ("rbi","repo rate","monetary policy","inflation","gdp")):return "MACRO / RBI"
    if any(k in t for k in ("fed","federal reserve","tariff","oil","crude","geopolit")):return "GLOBAL MACRO"
    if any(k in t for k in ("dividend","buyback","merger","acquisition","order","approval","stake")):return "CORPORATE ACTION"
    return "MARKET"

def impact(text):
    t=text.lower()
    high=("rate hike","rate cut","earnings","guidance","merger","acquisition","buyback","war","tariff","sanction","crude oil","rbi")
    medium=("order","approval","dividend","inflation","gdp","upgrade","downgrade")
    if any(k in t for k in high):return "HIGH"
    if any(k in t for k in medium):return "MEDIUM"
    return "LOW"

def related_stock(text):
    t=text.upper()
    for ticker,name in WATCHLIST.items():
        if name in t:return name
    return "MARKET"

@st.cache_data(ttl=900,show_spinner=False)
def scheduled_earnings():
    rows=[]
    today=datetime.now(timezone.utc).date(); horizon=today+timedelta(days=14)
    for ticker,name in WATCHLIST.items():
        try:
            cal=yf.Ticker(ticker).calendar
            dates=[]
            if isinstance(cal,dict): dates=cal.get("Earnings Date",[]) or []
            elif hasattr(cal,"columns") and "Earnings Date" in cal.columns: dates=list(cal["Earnings Date"])
            for d in dates:
                if hasattr(d,"date"): d=d.date()
                else:
                    try:d=datetime.fromisoformat(str(d)).date()
                    except Exception:continue
                if today<=d<=horizon:rows.append({"Date":d.isoformat(),"Event":"Earnings","Stock":name,"Impact":"HIGH","Source":"Yahoo Finance calendar"})
        except Exception:pass
    return sorted(rows,key=lambda x:(x["Date"],x["Stock"]))

@st.cache_data(ttl=900,show_spinner=False)
def catalyst_news():
    rows=[];now=datetime.now(timezone.utc)
    for group,url in CATALYST_FEEDS:
        try:
            feed=feedparser.parse(url)
            for e in feed.entries[:8]:
                title=e.get("title","").strip();dt=parse_dt(e.get("published","") or e.get("updated","") or "")
                if not title or not dt or now-dt>timedelta(days=4):continue
                publisher=(e.get("source",{}).get("title","") if isinstance(e.get("source"),dict) else "")
                summary=e.get("summary") or e.get("description") or ""
                rows.append({"Published":dt.strftime("%d %b %H:%M UTC"),"Type":catalyst_type(title),"Impact":impact(title),"Affected":related_stock(title),"Headline":title,"Gist":clean_gist(summary,title),"Publisher":publisher,"Link":e.get("link","")})
        except Exception:pass
    seen=set();out=[]
    for r in sorted(rows,key=lambda x:(x["Impact"]!="HIGH",x["Impact"]!="MEDIUM",x["Published"]),reverse=False):
        key=r["Headline"].lower()
        if key in seen:continue
        seen.add(key);out.append(r)
    return out[:30]

report=load_report();earnings=scheduled_earnings();news=catalyst_news()
all_events=[{"Date":x["Date"],"Event":x["Event"],"Stock":x["Stock"],"Impact":x["Impact"],"Source":x["Source"]} for x in earnings]
high=sum(x["Impact"]=="HIGH" for x in news)+sum(x["Impact"]=="HIGH" for x in earnings)
market=sum(x["Affected"]=="MARKET" for x in news)
watch=sum(x["Affected"]!="MARKET" for x in news)

st.markdown('<div class="cr-k">MarketPilot forward-looking layer</div><div class="cr-title">Catalyst Radar</div><div class="cr-sub">Upcoming scheduled catalysts plus recent catalyst-driven headlines. Impact is a screening heuristic, not a prediction of price direction. Scheduled events are only shown when the public data source exposes a date.</div>',unsafe_allow_html=True)
st.markdown(f'<div class="cr-grid"><div class="cr-card"><div class="cr-label">High-impact catalysts</div><div class="cr-value">{high}</div></div><div class="cr-card"><div class="cr-label">Scheduled earnings</div><div class="cr-value">{len(earnings)}</div></div><div class="cr-card"><div class="cr-label">Stock-linked news</div><div class="cr-value">{watch}</div></div><div class="cr-card"><div class="cr-label">Market-wide news</div><div class="cr-value">{market}</div></div></div>',unsafe_allow_html=True)

if earnings:
    top=earnings[0]
    st.markdown('<div class="cr-k">Next scheduled event</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="cr-hero"><div style="display:flex;justify-content:space-between;align-items:center;gap:1rem"><div><div class="cr-head">{top["Stock"]} · Earnings</div><div class="cr-meta">{top["Date"]} · Expected corporate reporting event · Impact screen: HIGH</div></div><div class="cr-score">⚡</div></div><div class="cr-divider"></div><div class="cr-meta">MarketPilot surfaces the event so the research process can account for event risk before interpreting technical signals.</div></div>',unsafe_allow_html=True)

st.markdown('<div class="cr-k">Upcoming scheduled events · next 14 days</div>',unsafe_allow_html=True)
if all_events:st.dataframe(pd.DataFrame(all_events),use_container_width=True,hide_index=True)
else:st.info("No dated earnings events were exposed by the public calendar for the next 14 days.")

st.markdown('<div class="cr-k" style="margin-top:1.5rem">Live catalyst feed · last 4 days</div>',unsafe_allow_html=True)
if news:
    st.markdown('<div class="cr-news-grid">',unsafe_allow_html=True)
    for x in news[:12]:
        impact_cls={"HIGH":"impact-high","MEDIUM":"impact-medium","LOW":"impact-low"}.get(x["Impact"],"impact-low")
        publisher=html.escape(x["Publisher"] or "Unknown")
        headline=html.escape(x["Headline"])
        gist=html.escape(x["Gist"])
        meta=f'{html.escape(x["Type"])} · {html.escape(x["Affected"])} · {html.escape(x["Published"])}'
        st.markdown(f'<div class="cr-news"><div class="cr-k {impact_cls}">{html.escape(x["Impact"])} · {meta}</div><div class="cr-news-head">{headline}</div><div class="cr-gist">{gist}</div><div class="cr-source">{publisher} · <a href="{html.escape(x["Link"])}" target="_blank">Open source ↗</a></div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
else:st.info("No recent catalyst headlines were available from the public feeds.")

st.caption("Catalyst Radar is a research filter. It does not estimate the probability or magnitude of a stock move and should be combined with price structure, valuation and primary-source confirmation.")
