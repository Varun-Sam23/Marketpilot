import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import pandas_market_calendars as mcal
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="MarketPilot", page_icon="📈", layout="wide")

DATA_FILE = Path("data/latest.json")
WATCHLIST_FILE = Path("data/watchlist.json")
IST = ZoneInfo("Asia/Kolkata")
NSE_CALENDAR = mcal.get_calendar("NSE")

DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS"
]

NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
]


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def nse_is_trading_day(day=None):
    day = day or datetime.now(IST).date()
    return not NSE_CALENDAR.schedule(start_date=day, end_date=day).empty


def market_status_text():
    now = datetime.now(IST)
    if not nse_is_trading_day(now.date()):
        return "MARKET CLOSED"
    if time(9, 15) <= now.time() <= time(15, 30):
        return "MARKET LIVE"
    return "MARKET CLOSED"


@st.cache_data(ttl=60, show_spinner=False)
def market_data(tickers):
    rows = []
    for ticker in tickers:
        try:
            h = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            if len(h) >= 2:
                prev = float(h["Close"].iloc[-2])
                last = float(h["Close"].iloc[-1])
                pct = (last / prev - 1) * 100
                rows.append({"ticker": ticker, "last": last, "change_pct": pct})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def intraday_snapshot(tickers):
    rows = []
    for ticker in tickers:
        try:
            h = yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
            if len(h):
                last = float(h["Close"].iloc[-1])
                first = float(h["Open"].iloc[0])
                pct = (last / first - 1) * 100 if first else 0
                rows.append({"ticker": ticker, "last": last, "from_open_pct": pct})
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def live_news():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                items.append({
                    "title": entry.get("title", ""),
                    "source": source,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception:
            pass
    return items[:20]


def load_morning_report():
    return load_json(DATA_FILE, {
        "generated_at": None,
        "market_status": "No pre-market report has been generated yet.",
        "verdict": "WAIT",
        "confidence": "Low",
        "summary": "Run the GitHub Action or refresh after the first scheduled run.",
        "signals": [],
        "levels": {},
        "global": [],
        "news": [],
        "watchlist": [],
        "ai_analysis": {},
    })


report = load_morning_report()
current_status = market_status_text()
now = datetime.now(IST)

st.title("📈 MarketPilot")
st.caption("Pre-market intelligence + live market/news monitoring • No order execution")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Market status", current_status)
col2.metric("Morning report", report.get("verdict", "WAIT"))
col3.metric("Report time", report.get("generated_at", "Not generated"))
col4.metric("Mode", "Decision support only")

st.info(
    "The morning report forms a hypothesis from previous sessions and overnight information. "
    "Live market values and news below refresh approximately every 60 seconds while this page is open."
)

st.subheader("🧠 MarketPilot AI Brain")
ai = report.get("ai_analysis", {})
if ai.get("enabled"):
    st.success(f"AI analysis ready • {ai.get('provider', 'Gemini')} {ai.get('model', '')}")
    a, b, c = st.columns(3)
    a.metric("AI bias", ai.get("bias", "UNKNOWN"))
    b.metric("Market regime", ai.get("market_regime", "UNKNOWN"))
    c.metric("AI confidence", ai.get("confidence", "LOW"))

    st.write("**Thesis**")
    st.write(ai.get("thesis", ""))

    x, y, z = st.columns(3)
    with x:
        st.write("**🟢 Bull case**")
        st.write(ai.get("bull_case", ""))
    with y:
        st.write("**🟡 Base case**")
        st.write(ai.get("base_case", ""))
    with z:
        st.write("**🔴 Bear case**")
        st.write(ai.get("bear_case", ""))

    st.write("**Key levels**")
    for level in ai.get("key_levels", []):
        st.write("•", level)

    st.write("**Invalidation**")
    st.write(ai.get("invalidation", ""))

    d1, d2 = st.columns(2)
    with d1:
        st.write("**Drivers**")
        for item in ai.get("drivers", []):
            st.write("•", item)
    with d2:
        st.write("**Risks**")
        for item in ai.get("risks", []):
            st.write("•", item)
else:
    status = ai.get("status", "AI KEY NOT CONFIGURED")
    st.warning(
        f"{status}. Add the GEMINI_API_KEY GitHub secret to enable the AI Market Brain. "
        "Until then, MarketPilot continues using the deterministic framework."
    )

st.subheader("📌 Morning framework")
a, b = st.columns([1, 2])
with a:
    st.metric("Rule-based bias", report.get("verdict", "WAIT"))
    st.write("Confidence:", report.get("confidence", "Low"))
with b:
    st.write(report.get("summary", ""))

if report.get("signals"):
    st.write("**Key signals**")
    for s in report["signals"]:
        st.write("•", s)

st.subheader("🎯 Key levels")
levels = report.get("levels", {})
if levels:
    st.dataframe(pd.DataFrame([levels]), use_container_width=True, hide_index=True)
else:
    st.caption("Levels will appear after the scheduled pre-market analysis runs.")

st.subheader("🌍 Global cues")
global_items = report.get("global", [])
if global_items:
    st.dataframe(pd.DataFrame(global_items), use_container_width=True, hide_index=True)
else:
    st.caption("No cached global snapshot yet.")

st.subheader("📰 Live news")
news = live_news()
st.caption(f"News refresh: {now.strftime('%H:%M:%S IST')}")
if news:
    for item in news[:15]:
        title = item.get("title", "").strip()
        source = item.get("source", "")
        published = item.get("published", "")
        link = item.get("link", "")
        if link:
            st.markdown(f"**[{title}]({link})**  \n{source} — {published}")
        else:
            st.markdown(f"**{title}**  \n{source} — {published}")
else:
    st.caption("Live news unavailable from the free feeds right now.")

st.subheader("📊 Live market snapshot")
indices = ["^NSEI", "^NSEBANK", "^BSESN", "^INDIAVIX"]
live = intraday_snapshot(indices)
if not live.empty:
    live["ticker"] = live["ticker"].replace({
        "^NSEI": "NIFTY 50", "^NSEBANK": "BANK NIFTY",
        "^BSESN": "SENSEX", "^INDIAVIX": "INDIA VIX"
    })
    live["last"] = live["last"].round(2)
    live["from_open_pct"] = live["from_open_pct"].round(2)
    st.dataframe(live, use_container_width=True, hide_index=True)
else:
    st.warning("Live snapshot unavailable from the free data source right now.")

st.subheader("👀 Watchlist")
watchlist = load_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
watch = market_data(watchlist)
if not watch.empty:
    watch["ticker"] = watch["ticker"].str.replace(".NS", "", regex=False)
    watch["last"] = watch["last"].round(2)
    watch["change_pct"] = watch["change_pct"].round(2)
    st.dataframe(watch.sort_values("change_pct", ascending=False), use_container_width=True, hide_index=True)
else:
    st.caption("Watchlist data unavailable right now.")

st.divider()
st.caption(
    "Data from free/public sources can be delayed, incomplete, or temporarily unavailable. "
    "This dashboard is for research and education, not financial advice."
)

st_autorefresh(interval=60_000, key="marketpilot_refresh")
