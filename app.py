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

from menu import render_sidebar
from news_intelligence import enrich_news

st.set_page_config(page_title="MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
render_sidebar()

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
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem}
.mp-hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:12px}.mp-title{font-family:Georgia,serif;font-size:2.35rem;font-weight:700;line-height:1}.mp-sub{color:#8290a3;letter-spacing:.13em;text-transform:uppercase;font-size:.64rem;margin-top:8px}.mp-time{text-align:right;color:#8290a3;font-size:.72rem}.mp-status{display:inline-block;border:1px solid #2b3a4d;background:#0d131d;border-radius:999px;padding:5px 10px;color:#dce5ef;font-size:.68rem;font-weight:700;letter-spacing:.08em}
.card{background:linear-gradient(145deg,#0e151f,#0b1119);border:1px solid #202c3c;border-radius:14px;padding:14px 15px;min-height:94px}.card:hover{border-color:#35465d}.label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.value{font-family:Georgia,serif;font-size:1.42rem;margin-top:5px}.muted{color:#8492a4;font-size:.72rem}.positive{color:#64d39a}.negative{color:#ff7b83}.neutral{color:#c5ced9}
.deck{display:flex;gap:8px;align-items:center;background:#0b1119;border:1px solid #202c3c;border-radius:12px;padding:7px 10px;margin:8px 0 12px}.deck-label{font-size:.61rem;letter-spacing:.11em;color:#718096;text-transform:uppercase;margin-right:5px}.deck-item{font-size:.72rem;color:#cdd6e0;border-right:1px solid #263344;padding-right:10px}.deck-item:last-child{border:0}.dot{font-size:.7rem}
.ticker{overflow:hidden;border:1px solid #202c3c;border-radius:11px;background:#0b1119;padding:9px;white-space:nowrap;margin:7px 0 15px}.track{display:inline-block;padding-left:100%;animation:scroll 150s linear infinite}@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.section-head{display:flex;justify-content:space-between;align-items:center;margin:5px 0 8px}.section-title{font-family:Georgia,serif;font-size:1.12rem}.section-meta{font-size:.65rem;color:#718096;letter-spacing:.08em;text-transform:uppercase}.signal{background:#0d141e;border:1px solid #202c3c;border-radius:12px;padding:12px}.signal .big{font-family:Georgia,serif;font-size:1.65rem}.signal .small{font-size:.68rem;color:#8290a3;text-transform:uppercase;letter-spacing:.1em}.bar{height:5px;background:#202b39;border-radius:5px;margin-top:9px;overflow:hidden}.bar>div{height:100%;background:#8090a4;border-radius:5px}.insight{background:#0d141e;border-left:3px solid #66788f;border-radius:9px;padding:11px 13px;margin-bottom:8px}.newsrow{padding:8px 0;border-bottom:1px solid #1b2634}.newsstatus{font-size:.64rem;font-weight:700;letter-spacing:.06em}.newstitle{font-size:.79rem;color:#dce3ec}.newssource{font-size:.64rem;color:#738195;margin-top:3px}
[data-testid="stDataFrame"]{border:1px solid #202c3c;border-radius:10px}.stTabs [data-baseweb="tab-list"]{gap:4px}.stTabs [data-baseweb="tab"]{font-size:.75rem}.stTabs [aria-selected="true"]{font-weight:700}
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
    rows = []
    for ticker, name in [("^NSEI", "NIFTY 50"), ("^NSEBANK", "BANK NIFTY"), ("^BSESN", "SENSEX"), ("^INDIAVIX", "INDIA VIX")]:
        try:
            h = yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
            if not h.empty:
                last = float(h["Close"].iloc[-1])
                first = float(h["Open"].iloc[0])
                rows.append({"Index": name, "Last": round(last, 2), "Session %": round((last / first - 1) * 100, 2) if first else 0})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def watchlist_data(tickers):
    rows = []
    for ticker in tickers:
        try:
            h = yf.Ticker(ticker).history(period="3mo", interval="1d", auto_adjust=False)
            if len(h) >= 22:
                last = float(h.Close.iloc[-1])
                prev = float(h.Close.iloc[-2])
                sma20 = float(h.Close.tail(20).mean())
                rows.append({"Stock": ticker.replace(".NS", ""), "1D %": round((last / prev - 1) * 100, 2), "5D %": round((last / float(h.Close.iloc[-6]) - 1) * 100, 2), "20D %": round((last / float(h.Close.iloc[-21]) - 1) * 100, 2), "vs 20D SMA %": round((last / sma20 - 1) * 100, 2)})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def news_data():
    items = []
    for group, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:8]:
                title = e.get("title", "").strip()
                publisher = ""
                src = e.get("source")
                if isinstance(src, dict):
                    publisher = str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m = re.search(r"\s+-\s+([^-]+)$", title)
                    publisher = m.group(1).strip() if m else "Unknown publisher"
                clean = re.sub(r"\s+-\s+([^-]+)$", "", title).strip()
                items.append({"title": clean, "publisher": publisher, "feed_group": group, "published": e.get("published", ""), "link": e.get("link", "")})
        except Exception:
            pass
    return items[:28]


status = market_status()
now = datetime.now(IST)
report = load_json(DATA_FILE, {})
raw_news = news_data()
news_intel = enrich_news(raw_news)
indices = index_data()
watchlist = load_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
wl = watchlist_data(tuple(watchlist))
st_autorefresh(interval=60_000, key="marketpilot_refresh")

# ── Header / command deck ─────────────────────────────────────────────────────
st.markdown(f"""
<div class="mp-hero">
  <div><div class="mp-title">◈ MarketPilot</div><div class="mp-sub">Indian markets · intelligence before action · evidence-first decision support</div></div>
  <div class="mp-time"><span class="mp-status">{'● LIVE' if status == 'MARKET LIVE' else '○ CLOSED'}</span><br>{now.strftime('%A · %d %B %Y')}<br>{now.strftime('%H:%M:%S')} IST</div>
</div>
""", unsafe_allow_html=True)

ai = report.get("ai_analysis", {}) or {}
decision = report.get("decision", {}) or {}
bias = decision.get("bias") or ai.get("bias") or report.get("verdict") or "WAIT"
confidence = decision.get("confidence") or ai.get("confidence") or report.get("confidence") or "N/A"
regime = decision.get("market_regime") or ai.get("market_regime") or "—"
score = decision.get("score", "—")

st.markdown(f"""
<div class="deck"><span class="deck-label">COMMAND DECK</span>
<span class="deck-item"><span class="dot">{'🟢' if status=='MARKET LIVE' else '⚪'}</span> {status}</span>
<span class="deck-item">BIAS <b>{html.escape(str(bias))}</b></span>
<span class="deck-item">SCORE <b>{html.escape(str(score))}</b></span>
<span class="deck-item">CONFIDENCE <b>{html.escape(str(confidence))}</b></span>
<span class="deck-item">REGIME <b>{html.escape(str(regime))}</b></span>
<span class="deck-item">AUTO REFRESH <b>60s</b></span></div>
""", unsafe_allow_html=True)

# ── KPI strip ──────────────────────────────────────────────────────────────────
supported = sum(x.get("claim_status") == "SUPPORTED" for x in news_intel)
disputed = sum(x.get("claim_status") == "DISPUTED" for x in news_intel)
insufficient = sum(x.get("claim_status") == "INSUFFICIENT EVIDENCE" for x in news_intel)
strong = sum(int(x.get("evidence_score", 10)) >= 75 for x in news_intel)

kpis = [
    ("Decision Score", score, "Evidence-weighted", "neutral"),
    ("Supported Claims", supported, f"of {len(news_intel)} stories", "positive"),
    ("Disputed Claims", disputed, "requires caution", "negative" if disputed else "neutral"),
    ("Strong Evidence", strong, "score ≥ 75", "positive" if strong else "neutral"),
]
cols = st.columns(4)
for c, (label, value, sub, cls) in zip(cols, kpis):
    c.markdown(f'<div class="card"><div class="label">{label}</div><div class="value {cls}">{html.escape(str(value))}</div><div class="muted">{html.escape(str(sub))}</div></div>', unsafe_allow_html=True)

# ── Live ticker ────────────────────────────────────────────────────────────────
if news_intel:
    parts = []
    for x in news_intel[:14]:
        badge = {"SUPPORTED": "🟢", "DISPUTED": "🔴", "INSUFFICIENT EVIDENCE": "🟡"}.get(x.get("claim_status"), "🟡")
        parts.append(f"{badge} {html.escape(x.get('title', ''))} · {html.escape(x.get('publisher', 'Unknown'))}")
    st.markdown('<div class="ticker"><div class="track">' + ' &nbsp; ◆ &nbsp; '.join(parts) + '</div></div>', unsafe_allow_html=True)

# ── Market pulse ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-head"><div class="section-title">Market Pulse</div><div class="section-meta">Live public feed · 60s refresh</div></div>', unsafe_allow_html=True)
if not indices.empty:
    cols = st.columns(len(indices))
    for c, (_, r) in zip(cols, indices.iterrows()):
        pct = float(r["Session %"])
        cls = "positive" if pct > 0 else "negative" if pct < 0 else "neutral"
        c.markdown(f'<div class="card"><div class="label">{html.escape(r["Index"])}</div><div class="value">{r["Last"]:,.2f}</div><div class="muted {cls}">Session {pct:+.2f}%</div></div>', unsafe_allow_html=True)
else:
    st.info("Public index feed is currently unavailable. No values are estimated.")

# ── Intelligence core ─────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡ INTELLIGENCE CORE", "📈 MARKET BOARD", "📰 EVIDENCE MONITOR"])

with tab1:
    left, right = st.columns([1.05, 1.45])
    with left:
        st.markdown('<div class="section-head"><div class="section-title">Decision Radar</div><div class="section-meta">Current thesis</div></div>', unsafe_allow_html=True)
        score_num = None
        try:
            score_num = max(0, min(100, float(score)))
        except (TypeError, ValueError):
            pass
        display_score = f"{score_num:.0f}" if score_num is not None else "—"
        fill = score_num if score_num is not None else 0
        st.markdown(f'<div class="signal"><div class="small">Market Bias</div><div class="big">{html.escape(str(bias))}</div><div class="muted">Confidence: {html.escape(str(confidence))} · Regime: {html.escape(str(regime))}</div><div class="bar"><div style="width:{fill}%"></div></div><div class="muted" style="margin-top:5px">Decision score <b>{display_score}/100</b></div></div>', unsafe_allow_html=True)
        thesis = ai.get("thesis") or report.get("summary") or "No current thesis is recorded."
        st.markdown(f'<div class="insight"><b>Thesis</b><br><span class="muted">{html.escape(str(thesis))}</span></div>', unsafe_allow_html=True)
        levels = report.get("levels", {}) or {}
        if levels:
            st.markdown('<div class="insight"><b>Key Levels</b><br><span class="muted">' + html.escape(" · ".join(f"{k}: {v}" for k, v in levels.items())) + '</span></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-head"><div class="section-title">Scenario Matrix</div><div class="section-meta">AI thesis · evidence constrained</div></div>', unsafe_allow_html=True)
        a, b, c = st.columns(3)
        a.info("🟢 Bull case\n\n" + str(ai.get("bull_case", "Not available")))
        b.warning("🟡 Base case\n\n" + str(ai.get("base_case", "Not available")))
        c.error("🔴 Bear case\n\n" + str(ai.get("bear_case", "Not available")))

with tab2:
    if not wl.empty:
        gainers = wl.sort_values("1D %", ascending=False).head(3)
        losers = wl.sort_values("1D %", ascending=True).head(3)
        g, l = st.columns(2)
        with g:
            st.markdown('<div class="section-head"><div class="section-title">Leaders</div><div class="section-meta">Watchlist · 1D</div></div>', unsafe_allow_html=True)
            st.dataframe(gainers, use_container_width=True, hide_index=True)
        with l:
            st.markdown('<div class="section-head"><div class="section-title">Laggards</div><div class="section-meta">Watchlist · 1D</div></div>', unsafe_allow_html=True)
            st.dataframe(losers, use_container_width=True, hide_index=True)
        st.markdown('<div class="section-head"><div class="section-title">Watchlist Board</div><div class="section-meta">1D · 5D · 20D · trend context</div></div>', unsafe_allow_html=True)
        st.dataframe(wl.sort_values("1D %", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Watchlist data is currently unavailable from the public feed.")

with tab3:
    st.markdown('<div class="section-head"><div class="section-title">Evidence Monitor</div><div class="section-meta">Truth layer · no silent upgrades</div></div>', unsafe_allow_html=True)
    e1, e2, e3 = st.columns(3)
    e1.metric("Supported", supported)
    e2.metric("Disputed", disputed)
    e3.metric("Insufficient", insufficient)
    if news_intel:
        rows = []
        for x in news_intel[:24]:
            title = re.sub(r"^(🟢 SUPPORTED|🔴 DISPUTED|🟡 INSUFFICIENT EVIDENCE)\s*·\s*", "", x.get("title", ""))
            rows.append({"Status": x.get("claim_status", "INSUFFICIENT EVIDENCE"), "Headline": title, "Verification": x.get("verification", "UNVERIFIED"), "Evidence": x.get("evidence_score", 10), "Sources": x.get("evidence_count", 0), "Impact": x.get("impact", "NEUTRAL"), "Publisher": x.get("publisher", "Unknown")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No current headlines available.")

# ── Legacy-compatible deep tabs ────────────────────────────────────────────────
with st.expander("Morning Intelligence", expanded=False):
    if ai.get("enabled"):
        st.write(ai.get("thesis", "No thesis recorded."))
    else:
        st.info("No fresh morning thesis is available for the current market state.")

with st.expander("Performance Snapshot", expanded=False):
    history = load_json(HISTORY_FILE, [])
    if history:
        st.dataframe(pd.DataFrame(history[-15:]), use_container_width=True, hide_index=True)
    else:
        st.info("No completed trading-day thesis has been journaled yet.")

st.caption("MarketPilot uses public/free data feeds which may be delayed, incomplete or unavailable. Research and decision support only — no order execution.")
