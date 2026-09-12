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
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1.1rem;padding-bottom:2rem}
.mp-hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:12px}.mp-title{font-family:Georgia,serif;font-size:2.35rem;font-weight:700;line-height:1}.mp-sub{color:#8290a3;letter-spacing:.13em;text-transform:uppercase;font-size:.64rem;margin-top:8px}.mp-time{text-align:right;color:#8290a3;font-size:.72rem}.mp-status{display:inline-block;border:1px solid #2b3a4d;background:#0d131d;border-radius:999px;padding:5px 10px;color:#dce5ef;font-size:.68rem;font-weight:700;letter-spacing:.08em}
.deck{display:flex;gap:8px;align-items:center;background:#0b1119;border:1px solid #202c3c;border-radius:12px;padding:8px 10px;margin:8px 0 13px;overflow-x:auto}.deck-label{font-size:.61rem;letter-spacing:.11em;color:#718096;text-transform:uppercase;margin-right:5px}.deck-item{font-size:.72rem;color:#cdd6e0;border-right:1px solid #263344;padding-right:10px;white-space:nowrap}.deck-item:last-child{border:0}
.ticker{overflow:hidden;border:1px solid #202c3c;border-radius:11px;background:#0b1119;padding:9px;white-space:nowrap;margin:7px 0 17px}.track{display:inline-block;padding-left:100%;animation:scroll 150s linear infinite}@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.section-head{display:flex;justify-content:space-between;align-items:center;margin:7px 0 9px}.section-title{font-family:Georgia,serif;font-size:1.15rem}.section-meta{font-size:.64rem;color:#718096;letter-spacing:.09em;text-transform:uppercase}
.card{background:linear-gradient(145deg,#0e151f,#0b1119);border:1px solid #202c3c;border-radius:14px;padding:14px 15px}.card-label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.card-value{font-family:Georgia,serif;font-size:1.42rem;margin-top:5px}.muted{color:#8492a4;font-size:.72rem}.positive{color:#64d39a}.negative{color:#ff7b83}.neutral{color:#c5ced9}
.verdict{background:linear-gradient(145deg,#101925,#0c131d);border:1px solid #2a394c;border-radius:15px;padding:17px 18px;min-height:125px}.verdict-label{font-size:.62rem;color:#7f8da0;text-transform:uppercase;letter-spacing:.12em}.verdict-value{font-family:Georgia,serif;font-size:1.8rem;font-weight:800;margin-top:5px}.verdict-copy{color:#b7c1ce;font-size:.84rem;line-height:1.45;margin-top:5px}.mini-card{background:#0d141e;border:1px solid #202c3c;border-radius:13px;padding:14px 15px;height:100%}.mini-title{font-size:.61rem;color:#7f8da0;text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px}.mini-value{font-size:1.05rem;font-weight:800}.mini-row{margin-top:9px}.mini-row-label{font-size:.65rem;color:#718096}.mini-row-value{font-size:.8rem;font-weight:700;margin-top:2px}
.pulse-item{padding:8px 0;border-top:1px solid #1d2938}.pulse-item:first-child{border-top:0;padding-top:0}.pulse-title{font-size:.78rem;font-weight:700;line-height:1.35;color:#dce3ec}.pulse-meta{font-size:.64rem;color:#738195;margin-top:4px}
.signal{background:#0d141e;border:1px solid #202c3c;border-radius:12px;padding:13px}.signal-big{font-family:Georgia,serif;font-size:1.55rem}.bar{height:5px;background:#202b39;border-radius:5px;margin-top:9px;overflow:hidden}.bar-fill{height:100%;background:#8090a4;border-radius:5px}
[data-testid="stDataFrame"]{border:1px solid #202c3c;border-radius:10px}.stTabs [data-baseweb="tab-list"]{gap:4px}.stTabs [data-baseweb="tab"]{font-size:.75rem}.stTabs [aria-selected="true"]{font-weight:700}
</style>
""", unsafe_allow_html=True)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_score(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def market_status():
    now = datetime.now(IST)
    try:
        is_trading_day = not NSE_CALENDAR.schedule(start_date=now.date(), end_date=now.date()).empty
    except Exception:
        is_trading_day = now.weekday() < 5
    if not is_trading_day:
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
                rows.append({"Index": name, "Last": last, "Session %": ((last / first) - 1) * 100 if first else 0})
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
                close = h["Close"]
                last = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                sma20 = float(close.tail(20).mean())
                rows.append({"Stock": ticker.replace(".NS", ""), "1D %": (last / prev - 1) * 100, "5D %": (last / float(close.iloc[-6]) - 1) * 100, "20D %": (last / float(close.iloc[-21]) - 1) * 100, "vs 20D SMA %": (last / sma20 - 1) * 100})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def news_data():
    items = []
    for group, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                publisher = ""
                source = entry.get("source")
                if isinstance(source, dict):
                    publisher = str(source.get("title") or source.get("name") or "").strip()
                if not publisher:
                    match = re.search(r"\s+-\s+([^-]+)$", title)
                    publisher = match.group(1).strip() if match else "Unknown publisher"
                clean = re.sub(r"\s+-\s+([^-]+)$", "", title).strip()
                items.append({"title": clean, "publisher": publisher, "feed_group": group, "published": entry.get("published", ""), "link": entry.get("link", "")})
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

ai = report.get("ai_analysis", {}) or {}
decision = report.get("decision", {}) or {}
bias = decision.get("bias") or ai.get("bias") or report.get("verdict") or "WAIT"
confidence = decision.get("confidence") or ai.get("confidence") or report.get("confidence") or "N/A"
regime = decision.get("market_regime") or ai.get("market_regime") or "—"
score = decision.get("score", "—")
score_num = safe_score(score)
thesis = ai.get("thesis") or report.get("summary") or "No current market thesis is recorded."

supported = sum(x.get("claim_status") == "SUPPORTED" for x in news_intel)
disputed = sum(x.get("claim_status") == "DISPUTED" for x in news_intel)
insufficient = sum(x.get("claim_status") == "INSUFFICIENT EVIDENCE" for x in news_intel)
strong = sum((safe_score(x.get("evidence_score", 10)) or 10) >= 75 for x in news_intel)

# Header
st.markdown(f"""
<div class="mp-hero">
  <div><div class="mp-title">◈ MarketPilot</div><div class="mp-sub">Indian markets · intelligence before action · evidence-first decision support</div></div>
  <div class="mp-time"><span class="mp-status">{'● LIVE' if status == 'MARKET LIVE' else '○ CLOSED'}</span><br>{now.strftime('%A · %d %B %Y')}<br>{now.strftime('%H:%M:%S')} IST</div>
</div>
<div class="deck"><span class="deck-label">COMMAND DECK</span><span class="deck-item">{'🟢' if status == 'MARKET LIVE' else '⚪'} {status}</span><span class="deck-item">BIAS <b>{html.escape(str(bias))}</b></span><span class="deck-item">SCORE <b>{html.escape(str(score))}</b></span><span class="deck-item">CONFIDENCE <b>{html.escape(str(confidence))}</b></span><span class="deck-item">REGIME <b>{html.escape(str(regime))}</b></span><span class="deck-item">AUTO REFRESH <b>60s</b></span></div>
""", unsafe_allow_html=True)

# Decision headline
headline_cls = "positive" if str(bias).upper() == "BULLISH" else "negative" if str(bias).upper() == "BEARISH" else "neutral"
score_label = f"{score_num:.0f}/100" if score_num is not None else "N/A"
left, right = st.columns([1.7, 1])
with left:
    st.markdown(f'<div class="verdict"><div class="verdict-label">AI MARKET VERDICT · EVIDENCE WEIGHTED</div><div class="verdict-value {headline_cls}">{html.escape(str(bias))} · {score_label}</div><div class="verdict-copy">{html.escape(str(thesis))}</div></div>', unsafe_allow_html=True)
with right:
    st.markdown(f'<div class="verdict"><div class="verdict-label">RISK POSTURE</div><div class="verdict-value" style="font-size:1.35rem">{html.escape(str(regime))}</div><div class="verdict-copy">Confidence: <b>{html.escape(str(confidence))}</b> · Supported: <b>{supported}</b> · Disputed: <b>{disputed}</b></div></div>', unsafe_allow_html=True)

# Evidence KPIs
kpis = [("Decision Score", score, "Evidence-weighted"), ("Supported Claims", supported, f"of {len(news_intel)} stories"), ("Disputed Claims", disputed, "requires caution"), ("Strong Evidence", strong, "score ≥ 75")]
cols = st.columns(4)
for col, (label, value, sub) in zip(cols, kpis):
    cls = "negative" if label == "Disputed Claims" and disputed else "positive" if label in {"Supported Claims", "Strong Evidence"} else "neutral"
    col.markdown(f'<div class="card"><div class="card-label">{label}</div><div class="card-value {cls}">{html.escape(str(value))}</div><div class="muted">{html.escape(str(sub))}</div></div>', unsafe_allow_html=True)

# Verified news ticker
if news_intel:
    parts = []
    for item in news_intel[:14]:
        badge = {"SUPPORTED":"🟢", "DISPUTED":"🔴", "INSUFFICIENT EVIDENCE":"🟡"}.get(item.get("claim_status"), "🟡")
        parts.append(f'{badge} {html.escape(item.get("title", ""))} · {html.escape(item.get("publisher", "Unknown"))}')
    st.markdown('<div class="ticker"><div class="track">' + ' &nbsp; ◆ &nbsp; '.join(parts) + '</div></div>', unsafe_allow_html=True)

# Market pulse
st.markdown('<div class="section-head"><div class="section-title">Market Pulse</div><div class="section-meta">Public market feed · refresh 60s</div></div>', unsafe_allow_html=True)
if not indices.empty:
    cols = st.columns(len(indices))
    for col, (_, row) in zip(cols, indices.iterrows()):
        pct = float(row["Session %"])
        cls = "positive" if pct > 0 else "negative" if pct < 0 else "neutral"
        col.markdown(f'<div class="card"><div class="card-label">{html.escape(row["Index"])}</div><div class="card-value">{float(row["Last"]):,.2f}</div><div class="muted {cls}">Session {pct:+.2f}%</div></div>', unsafe_allow_html=True)
else:
    st.info("Public index feed is currently unavailable. No values are estimated.")

# Intelligence pulse — each card is a single HTML block so content cannot escape its container.
st.markdown('<div class="section-head"><div class="section-title">Intelligence Pulse</div><div class="section-meta">What changed · catalysts · risk</div></div>', unsafe_allow_html=True)
current_keys = [f'{x.get("title","")}|{x.get("publisher","")}' for x in news_intel[:20]]
previous_keys = st.session_state.get("mp_previous_news", [])
new_items = [x for x in news_intel[:20] if f'{x.get("title","")}|{x.get("publisher","")}' not in previous_keys]
st.session_state["mp_previous_news"] = current_keys

if not previous_keys:
    change_html = '<div class="mini-title">SINCE LAST REFRESH</div><div class="mini-value neutral">INITIAL SNAPSHOT</div><div class="muted" style="margin-top:5px">Baseline captured. New headlines will be highlighted on the next refresh.</div>'
elif new_items:
    lines = ''.join(f'<div class="pulse-item"><div class="pulse-title">{html.escape(x.get("title", ""))[:115]}</div></div>' for x in new_items[:3])
    change_html = f'<div class="mini-title">SINCE LAST REFRESH</div><div class="mini-value positive">{len(new_items)} NEW</div><div class="muted" style="margin-top:4px">Newly surfaced headlines</div>{lines}'
else:
    change_html = '<div class="mini-title">SINCE LAST REFRESH</div><div class="mini-value neutral">NO CHANGE</div><div class="muted" style="margin-top:5px">No new headline in the current feed set.</div>'

catalysts = sorted(news_intel, key=lambda x: safe_score(x.get("evidence_score", 0)) or 0, reverse=True)[:4]
if catalysts:
    catalyst_lines = []
    for x in catalysts:
        badge = {"SUPPORTED":"🟢", "DISPUTED":"🔴", "INSUFFICIENT EVIDENCE":"🟡"}.get(x.get("claim_status"), "🟡")
        catalyst_lines.append(f'<div class="pulse-item"><div class="pulse-title">{badge} {html.escape(x.get("title", ""))[:120]}</div><div class="pulse-meta">{html.escape(x.get("publisher", "Unknown"))} · evidence {x.get("evidence_score", 10)}/100</div></div>')
    catalyst_html = '<div class="mini-title">TOP CATALYSTS</div>' + ''.join(catalyst_lines)
else:
    catalyst_html = '<div class="mini-title">TOP CATALYSTS</div><div class="muted">No catalyst headlines available.</div>'

vix = None
if not indices.empty and "INDIA VIX" in indices["Index"].values:
    vix = float(indices.loc[indices["Index"] == "INDIA VIX", "Session %"].iloc[0])
risk_vix = f"{vix:+.2f}%" if vix is not None else "N/A"
risk_cls = "negative" if vix is not None and vix > 0 else "neutral"
risk_html = f'''<div class="mini-title">RISK MONITOR</div><div class="mini-row"><div class="mini-row-label">News dispute</div><div class="mini-row-value {'negative' if disputed else 'positive'}">{disputed} claims</div></div><div class="mini-row"><div class="mini-row-label">Evidence gap</div><div class="mini-row-value neutral">{insufficient} claims</div></div><div class="mini-row"><div class="mini-row-label">India VIX move</div><div class="mini-row-value {risk_cls}">{risk_vix}</div></div>'''

p1, p2, p3 = st.columns([1.15, 1.45, 1.0])
p1.markdown(f'<div class="mini-card">{change_html}</div>', unsafe_allow_html=True)
p2.markdown(f'<div class="mini-card">{catalyst_html}</div>', unsafe_allow_html=True)
p3.markdown(f'<div class="mini-card">{risk_html}</div>', unsafe_allow_html=True)

# Main intelligence tabs
tab1, tab2, tab3 = st.tabs(["⚡ INTELLIGENCE CORE", "📈 MARKET BOARD", "📰 EVIDENCE MONITOR"])
with tab1:
    a, b = st.columns([1.05, 1.45])
    with a:
        st.markdown('<div class="section-head"><div class="section-title">Decision Radar</div><div class="section-meta">Current thesis</div></div>', unsafe_allow_html=True)
        fill = max(0, min(100, score_num)) if score_num is not None else 0
        st.markdown(f'<div class="signal"><div class="muted">MARKET BIAS</div><div class="signal-big">{html.escape(str(bias))}</div><div class="muted">Confidence: {html.escape(str(confidence))} · Regime: {html.escape(str(regime))}</div><div class="bar"><div class="bar-fill" style="width:{fill}%"></div></div><div class="muted" style="margin-top:5px">Decision score <b>{score_label}</b></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card" style="margin-top:9px"><div class="card-label">THESIS</div><div style="margin-top:7px;font-size:.82rem;line-height:1.45">{html.escape(str(thesis))}</div></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="section-head"><div class="section-title">Scenario Matrix</div><div class="section-meta">Evidence constrained</div></div>', unsafe_allow_html=True)
        s1, s2, s3 = st.columns(3)
        s1.info("🟢 Bull case\n\n" + str(ai.get("bull_case", "Not available")))
        s2.warning("🟡 Base case\n\n" + str(ai.get("base_case", "Not available")))
        s3.error("🔴 Bear case\n\n" + str(ai.get("bear_case", "Not available")))

with tab2:
    if not wl.empty:
        leaders = wl.sort_values("1D %", ascending=False).head(3)
        laggards = wl.sort_values("1D %", ascending=True).head(3)
        g, l = st.columns(2)
        with g:
            st.markdown('<div class="section-head"><div class="section-title">Leaders</div><div class="section-meta">1D</div></div>', unsafe_allow_html=True)
            st.dataframe(leaders.round(2), use_container_width=True, hide_index=True)
        with l:
            st.markdown('<div class="section-head"><div class="section-title">Laggards</div><div class="section-meta">1D</div></div>', unsafe_allow_html=True)
            st.dataframe(laggards.round(2), use_container_width=True, hide_index=True)
        st.markdown('<div class="section-head"><div class="section-title">Watchlist Board</div><div class="section-meta">1D · 5D · 20D · trend context</div></div>', unsafe_allow_html=True)
        st.dataframe(wl.sort_values("1D %", ascending=False).round(2), use_container_width=True, hide_index=True)
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

st.caption("MarketPilot uses public/free data feeds which may be delayed, incomplete or unavailable. Research and decision support only — no order execution.")
