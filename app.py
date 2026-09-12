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

st.set_page_config(
    page_title="MarketPilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown(
    """
    <style>
    :root {
        --bg:#0b1017;
        --panel:#111923;
        --panel-2:#151f2b;
        --ink:#edf1f5;
        --muted:#8f9baa;
        --line:rgba(255,255,255,.085);
        --gold:#c9a85b;
        --gold-soft:rgba(201,168,91,.10);
        --green:#59b987;
        --red:#e27a75;
        --blue:#7fa7c9;
        --shadow:0 14px 34px rgba(0,0,0,.22);
    }
    [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at 85% 0%, rgba(201,168,91,.10), transparent 27%),
          radial-gradient(circle at 0% 30%, rgba(84,123,155,.08), transparent 30%),
          var(--bg);
    }
    [data-testid="stHeader"]{background:transparent;}
    .main .block-container{max-width:1460px;padding:1.6rem 2.2rem 4rem;}
    .mp-brand{display:flex;align-items:center;gap:.8rem;}
    .mp-orb{width:38px;height:38px;border:1px solid rgba(201,168,91,.55);border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--gold);font-size:1.35rem;background:rgba(201,168,91,.06);box-shadow:0 0 0 5px rgba(201,168,91,.03);}
    .mp-title{font-family:Georgia,"Times New Roman",serif;font-size:2.75rem;line-height:1;font-weight:600;letter-spacing:-.035em;color:var(--ink);}
    .mp-sub{margin:.45rem 0 1rem 3.15rem;color:var(--muted);font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;}
    .mp-rule{height:1px;background:linear-gradient(90deg,var(--gold),transparent 70%);opacity:.55;margin:.35rem 0 1.0rem;}
    .mp-meta{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;margin-bottom:.7rem;}
    .mp-status{display:inline-flex;align-items:center;gap:.42rem;padding:.32rem .68rem;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.025);font-size:.67rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink);}
    .mp-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px rgba(89,185,135,.65);}
    .mp-dot.closed{background:#707985;box-shadow:none;}
    .mp-clock{font-size:.73rem;color:var(--muted);}
    .mp-wire{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:.85rem;}
    .mp-ticker{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:linear-gradient(90deg,rgba(201,168,91,.06),rgba(255,255,255,.018));padding:9px 0;box-shadow:var(--shadow);}
    .mp-track{display:inline-block;white-space:nowrap;padding-left:100%;animation:mp-scroll 180s linear infinite;font-size:.82rem;color:var(--ink);}
    .mp-track:hover{animation-play-state:paused;}
    .mp-news-item{display:inline-block;margin-right:30px;}
    .mp-news-item small{color:var(--muted);}
    @keyframes mp-scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
    .mp-hero{background:linear-gradient(135deg,rgba(201,168,91,.11),rgba(255,255,255,.015) 42%,rgba(99,130,159,.06));border:1px solid var(--line);border-radius:22px;padding:1.15rem 1.25rem;box-shadow:var(--shadow);position:relative;overflow:hidden;}
    .mp-hero:before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:28px 28px;opacity:.35;pointer-events:none;}
    .mp-hero-inner{position:relative;z-index:1;}
    .mp-eyebrow{font-size:.65rem;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);}
    .mp-big{font-family:Georgia,"Times New Roman",serif;font-size:2rem;color:var(--ink);line-height:1.1;margin:.35rem 0 .45rem;}
    .mp-muted{color:var(--muted);font-size:.77rem;line-height:1.5;}
    .mp-chip{display:inline-flex;gap:.3rem;align-items:center;padding:.26rem .55rem;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.025);font-size:.68rem;color:var(--muted);margin:.35rem .3rem 0 0;}
    .mp-card{background:linear-gradient(180deg,rgba(255,255,255,.032),rgba(255,255,255,.018));border:1px solid var(--line);border-radius:17px;padding:.95rem 1rem;box-shadow:0 9px 28px rgba(0,0,0,.14);}
    .mp-kicker{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
    .mp-price{font-family:Georgia,"Times New Roman",serif;font-size:1.55rem;color:var(--ink);margin:.25rem 0 .15rem;}
    .mp-change{font-size:.75rem;color:var(--muted);}
    .mp-section{font-family:Georgia,"Times New Roman",serif;color:var(--ink);font-size:1.55rem;margin:1.55rem 0 .7rem;}
    .mp-callout{border:1px solid rgba(201,168,91,.22);background:linear-gradient(90deg,var(--gold-soft),rgba(255,255,255,.015));border-radius:15px;padding:1rem 1.1rem;}
    .mp-scenario{border:1px solid var(--line);border-radius:15px;background:rgba(255,255,255,.018);padding:1rem;min-height:150px;}
    .mp-scenario h4{font-family:Georgia,"Times New Roman",serif;margin:.05rem 0 .45rem;color:var(--ink);}
    .mp-scenario p{color:#c5cbd3;line-height:1.5;font-size:.82rem;margin:0;}
    .mp-note{font-size:.7rem;color:var(--muted);}
    .mp-badge{font-weight:700;}
    .mp-divider{height:1px;background:var(--line);margin:1rem 0;}
    .mp-foot{border-top:1px solid var(--line);margin-top:2.4rem;padding-top:.9rem;color:#687280;font-size:.68rem;text-align:center;}
    [data-testid="stMetricValue"]{font-family:Georgia,"Times New Roman",serif;color:var(--ink);}
    [data-testid="stMetricLabel"]{color:var(--muted);}
    [data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:14px;overflow:hidden;}
    button[data-baseweb="tab"]{font-size:.76rem;letter-spacing:.05em;}
    @media (max-width: 900px){.main .block-container{padding:1rem .9rem 3rem}.mp-title{font-size:2.15rem}.mp-sub{margin-left:2.85rem;font-size:.61rem}.mp-big{font-size:1.65rem}.mp-section{font-size:1.35rem}}
    </style>
    """,
    unsafe_allow_html=True,
)


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
    rows = []
    for ticker in tickers:
        try:
            h = yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
            if not h.empty:
                last = float(h["Close"].iloc[-1])
                first = float(h["Open"].iloc[0])
                rows.append({"ticker": ticker, "last": last, "change_pct": ((last / first) - 1) * 100 if first else 0})
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
                last = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2])
                sma20 = float(h["Close"].tail(20).mean())
                ret20 = ((last / float(h["Close"].iloc[-21])) - 1) * 100
                vol = float(h["Volume"].iloc[-1])
                avgvol = float(h["Volume"].tail(20).mean())
                rows.append({
                    "Stock": ticker.replace(".NS", ""),
                    "Last": round(last, 2),
                    "1D %": round(((last / prev) - 1) * 100, 2),
                    "20D %": round(ret20, 2),
                    "vs 20D SMA %": round(((last / sma20) - 1) * 100, 2),
                    "Vol / 20D": round(vol / avgvol, 2) if avgvol else None,
                })
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def live_news():
    items = []
    for feed_group, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                publisher = ""
                src = entry.get("source")
                if isinstance(src, dict):
                    publisher = str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m = re.search(r"\s+-\s+([^-]+)$", title)
                    if m:
                        publisher = m.group(1).strip()
                if not publisher or publisher.lower() == "news.google.com":
                    publisher = "Unknown publisher"
                clean = re.sub(r"\s+-\s+([^-]+)$", "", title).strip() if publisher != "Unknown publisher" else title
                items.append({
                    "title": clean,
                    "publisher": publisher,
                    "source": publisher,
                    "feed_group": feed_group,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception:
            pass
    return items[:28]


def impact_icon(impact):
    return {"POSITIVE": "↗", "NEGATIVE": "↘", "NEUTRAL": "→", "UNKNOWN": "?"}.get(impact, "→")


def verification_badge(value):
    return {
        "CORROBORATED": "✅ CORROBORATED",
        "SINGLE_SOURCE": "⚠️ SINGLE SOURCE",
        "UNVERIFIED": "⚠️ UNVERIFIED",
    }.get(value, "⚠️ UNVERIFIED")


report = load_json(DATA_FILE, {})
status = market_status()
now = datetime.now(IST)
raw_news = live_news()
news_intel = enrich_news(raw_news)

st_autorefresh(interval=60_000, key="marketpilot_refresh")

# Header / masthead
st.markdown('<div class="mp-brand"><div class="mp-orb">◈</div><div class="mp-title">MarketPilot</div></div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Indian markets · intelligence before action · decision support</div>', unsafe_allow_html=True)
dot_class = "mp-dot" if status == "MARKET LIVE" else "mp-dot closed"
status_label = "LIVE" if status == "MARKET LIVE" else "CLOSED"
st.markdown(
    f'<div class="mp-meta"><span class="mp-status"><span class="{dot_class}"></span>{status_label}</span><span class="mp-clock">{now.strftime("%A · %d %B %Y · %H:%M:%S IST")}</span></div><div class="mp-rule"></div>',
    unsafe_allow_html=True,
)

# Live wire
st.markdown('<div class="mp-wire">Live wire · public feeds · pauses on hover</div>', unsafe_allow_html=True)
if news_intel:
    chunks = []
    for item in news_intel[:12]:
        badge = verification_badge(item.get("verification"))
        title = html.escape(item.get("title", ""))
        publisher = html.escape(item.get("publisher", "Unknown publisher"))
        impact = html.escape(item.get("impact", "NEUTRAL"))
        chunks.append(f'<span class="mp-news-item"><b>{badge}</b> {title} <small>• {publisher} • {impact}</small></span>')
    st.markdown('<div class="mp-ticker"><div class="mp-track">' + ' &nbsp; ◆ &nbsp; '.join(chunks) + '</div></div>', unsafe_allow_html=True)
else:
    st.info("Live news is temporarily unavailable.")

st.write("")

# Snapshot row
indices = index_snapshot()
lookup = {r["ticker"]: r for _, r in indices.iterrows()} if not indices.empty else {}
card_defs = [("NIFTY 50", "^NSEI"), ("BANK NIFTY", "^NSEBANK"), ("SENSEX", "^BSESN"), ("INDIA VIX", "^INDIAVIX")]
cols = st.columns(4)
for col, (name, ticker) in zip(cols, card_defs):
    row = lookup.get(ticker)
    last = f'{row["last"]:,.2f}' if row is not None else "—"
    chg = f'{row["change_pct"]:+.2f}%' if row is not None else "—"
    label = "From open" if status == "MARKET LIVE" else "Last session"
    col.markdown(f'<div class="mp-card"><div class="mp-kicker">{name}</div><div class="mp-price">{last}</div><div class="mp-change">{label} · {chg}</div></div>', unsafe_allow_html=True)

morning, live, news_tab, performance = st.tabs(["🌅 MORNING INTELLIGENCE", "⚡ LIVE MARKET", "📰 NEWS INTELLIGENCE", "📓 PERFORMANCE"])

with morning:
    ai = report.get("ai_analysis", {})
    verdict = report.get("verdict", "WAIT")
    st.markdown('<div class="mp-section">The morning ledger</div>', unsafe_allow_html=True)
    if ai.get("enabled"):
        hero_text = html.escape(ai.get("thesis", "No thesis recorded yet."))
        bias = html.escape(ai.get("bias", "UNKNOWN"))
        regime = html.escape(ai.get("market_regime", "UNKNOWN"))
        confidence = html.escape(ai.get("confidence", "LOW"))
        st.markdown(
            f'<div class="mp-hero"><div class="mp-hero-inner"><div class="mp-eyebrow">AI Market Brief</div><div class="mp-big">{bias} · {regime}</div><div class="mp-muted">{hero_text}</div><span class="mp-chip">Confidence · {confidence}</span><span class="mp-chip">Rule framework · {html.escape(verdict)}</span></div></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        x, y, z = st.columns(3)
        with x:
            st.markdown(f'<div class="mp-scenario"><h4>🟢 Bull case</h4><p>{html.escape(ai.get("bull_case", ""))}</p></div>', unsafe_allow_html=True)
        with y:
            st.markdown(f'<div class="mp-scenario"><h4>🟡 Base case</h4><p>{html.escape(ai.get("base_case", ""))}</p></div>', unsafe_allow_html=True)
        with z:
            st.markdown(f'<div class="mp-scenario"><h4>🔴 Bear case</h4><p>{html.escape(ai.get("bear_case", ""))}</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="mp-section">Levels & invalidation</div>', unsafe_allow_html=True)
        l1, l2 = st.columns([1.55, 1])
        with l1:
            levels = ai.get("key_levels", [])
            if levels:
                for level in levels:
                    st.write("•", level)
            else:
                st.caption("No AI levels recorded.")
        with l2:
            if ai.get("invalidation"):
                st.warning(ai.get("invalidation"))
        d1, d2 = st.columns(2)
        with d1:
            st.markdown('<div class="mp-section">Drivers</div>', unsafe_allow_html=True)
            for item in ai.get("drivers", []):
                st.write("•", item)
        with d2:
            st.markdown('<div class="mp-section">Risks</div>', unsafe_allow_html=True)
            for item in ai.get("risks", []):
                st.write("•", item)
    else:
        st.markdown('<div class="mp-hero"><div class="mp-hero-inner"><div class="mp-eyebrow">AI Market Brief</div><div class="mp-big">Waiting for the next trading-day analysis</div><div class="mp-muted">The report engine will populate the morning thesis on an NSE trading day. This page does not invent a view when the market is closed or fresh evidence is unavailable.</div></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="mp-section">Market structure</div>', unsafe_allow_html=True)
    levels = report.get("levels", {})
    if levels:
        st.dataframe(pd.DataFrame([levels]), use_container_width=True, hide_index=True)
    else:
        st.caption("Technical structure will populate after the next scheduled pre-market run.")

    st.markdown('<div class="mp-section">Sector pulse</div>', unsafe_allow_html=True)
    sectors = report.get("sectors", [])
    if sectors:
        sdf = pd.DataFrame(sectors).rename(columns={"sector": "Sector", "avg_change_pct": "Avg 1D %", "members": "Members"})
        if "Avg 1D %" in sdf:
            sdf["Avg 1D %"] = sdf["Avg 1D %"].round(2)
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    else:
        st.caption("Sector pulse will populate after the next trading-day run.")

with live:
    st.markdown('<div class="mp-section">Live market monitor</div>', unsafe_allow_html=True)
    if indices.empty:
        st.warning("Live market data is unavailable from the public feed right now.")
    else:
        ldf = indices.copy()
        ldf["ticker"] = ldf["ticker"].replace({"^NSEI": "NIFTY 50", "^NSEBANK": "BANK NIFTY", "^BSESN": "SENSEX", "^INDIAVIX": "INDIA VIX"})
        ldf["last"] = ldf["last"].round(2)
        ldf["change_pct"] = ldf["change_pct"].round(2)
        st.dataframe(ldf.rename(columns={"ticker": "Index", "last": "Last", "change_pct": "Session %"}), use_container_width=True, hide_index=True)

    st.markdown('<div class="mp-section">Watchlist</div>', unsafe_allow_html=True)
    watchlist = load_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
    wdf = watchlist_data(tuple(watchlist))
    if not wdf.empty:
        st.dataframe(wdf.sort_values("1D %", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.caption("Watchlist data is temporarily unavailable.")

with news_tab:
    st.markdown('<div class="mp-section">News intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="mp-note">Google News is only the collection layer. Publisher identity is taken from source metadata or headline attribution. Corroborated means similar reporting across independent publisher identities — it does not prove the underlying claim is true.</div>', unsafe_allow_html=True)
    if news_intel:
        rows = []
        for item in news_intel[:20]:
            rows.append({
                "Headline": item.get("title", ""),
                "Verification": verification_badge(item.get("verification")),
                "Impact": f'{impact_icon(item.get("impact"))} {item.get("impact", "NEUTRAL")}',
                "Affected": item.get("affected", "MARKET"),
                "Publisher": item.get("publisher", "Unknown publisher"),
                "Published": item.get("published", ""),
                "Evidence": item.get("verification_detail", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No current headlines available from the public feeds.")

with performance:
    st.markdown('<div class="mp-section">Thesis journal</div>', unsafe_allow_html=True)
    history = load_json(HISTORY_FILE, [])
    if history:
        hdf = pd.DataFrame([
            {
                "Date": item.get("date_ist", ""),
                "Rule Bias": item.get("rule_bias", ""),
                "Rule Confidence": item.get("rule_confidence", ""),
                "AI Bias": item.get("ai", {}).get("bias", ""),
                "AI Confidence": item.get("ai", {}).get("confidence", ""),
                "Regime": item.get("ai", {}).get("market_regime", ""),
            }
            for item in history[-30:]
        ])
        st.dataframe(hdf, use_container_width=True, hide_index=True)
        st.caption("Outcome scoring will be layered onto the journal after enough completed trading sessions are available.")
    else:
        st.info("No completed trading-day thesis has been journaled yet.")

st.markdown('<div class="mp-foot">MarketPilot uses public/free data feeds which may be delayed, incomplete or unavailable. Research and decision support only · no order execution.</div>', unsafe_allow_html=True)
