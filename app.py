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

st.set_page_config(page_title="MarketPilot", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

DATA_FILE = Path("data/latest.json")
WATCHLIST_FILE = Path("data/watchlist.json")
HISTORY_FILE = Path("data/history.json")
IST = ZoneInfo("Asia/Kolkata")
NSE_CALENDAR = mcal.get_calendar("NSE")

DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS"
]

NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown("""
<style>
.main .block-container {padding-top: 1.4rem; max-width: 1400px;}
.mp-title {font-size: 2.2rem; font-weight: 800; letter-spacing: -0.04em; margin-bottom: 0;}
.mp-sub {color: #6b7280; margin-top: 0.15rem; margin-bottom: 1.1rem;}
.mp-card {padding: 1rem 1.1rem; border: 1px solid rgba(128,128,128,.22); border-radius: 16px; min-height: 112px;}
.mp-kicker {font-size: .76rem; text-transform: uppercase; letter-spacing: .08em; color: #6b7280;}
.mp-value {font-size: 1.45rem; font-weight: 750; margin-top: .2rem;}
.mp-small {font-size: .82rem; color: #6b7280;}
.mp-pill {display:inline-block; padding:.25rem .55rem; border-radius:999px; border:1px solid rgba(128,128,128,.25); font-size:.78rem; margin-right:.35rem;}
</style>
""", unsafe_allow_html=True)


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
def quote_snapshot(tickers):
    rows = []
    for ticker in tickers:
        try:
            h = yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
            if not h.empty:
                last = float(h["Close"].iloc[-1])
                first = float(h["Open"].iloc[0])
                rows.append({"ticker": ticker, "last": last, "from_open_pct": ((last / first) - 1) * 100 if first else 0})
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
                return20 = ((last / float(h["Close"].iloc[-21])) - 1) * 100
                vol = float(h["Volume"].iloc[-1])
                avgvol = float(h["Volume"].tail(20).mean())
                rows.append({
                    "Stock": ticker.replace(".NS", ""),
                    "Last": round(last, 2),
                    "1D %": round(((last / prev) - 1) * 100, 2),
                    "20D %": round(return20, 2),
                    "vs 20D SMA %": round(((last / sma20) - 1) * 100, 2),
                    "Vol / 20D": round(vol / avgvol, 2) if avgvol else None,
                })
        except Exception:
            pass
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def live_news():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:7]:
                items.append({
                    "title": entry.get("title", "").strip(),
                    "source": source,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception:
            pass
    return items[:24]


def fmt_change(x):
    if x is None:
        return ""
    return f"{x:+.2f}%"


report = load_json(DATA_FILE, {})
ai = report.get("ai_analysis", {})
status = market_status_text()
now = datetime.now(IST)

st.markdown('<div class="mp-title">📈 MarketPilot</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Your Indian-market intelligence command center • research & decision support only</div>', unsafe_allow_html=True)

# ─────────────── top pulse ───────────────
indices = quote_snapshot(["^NSEI", "^NSEBANK", "^BSESN", "^INDIAVIX"])
lookup = {r["ticker"]: r for _, r in indices.iterrows()} if not indices.empty else {}

cards = [
    ("NIFTY 50", "^NSEI"),
    ("BANK NIFTY", "^NSEBANK"),
    ("SENSEX", "^BSESN"),
    ("INDIA VIX", "^INDIAVIX"),
]

st.caption(f"{status} • {now.strftime('%d %b %Y, %H:%M:%S IST')}")
c1, c2, c3, c4 = st.columns(4)
for col, (name, ticker) in zip([c1, c2, c3, c4], cards):
    row = lookup.get(ticker)
    last = f"{row['last']:,.2f}" if row is not None else "—"
    chg = fmt_change(row["from_open_pct"]) if row is not None else "—"
    col.markdown(f'<div class="mp-card"><div class="mp-kicker">{name}</div><div class="mp-value">{last}</div><div class="mp-small">From open: {chg}</div></div>', unsafe_allow_html=True)

st.write("")

# ─────────────── navigation ───────────────
tab_morning, tab_live, tab_history = st.tabs(["🌅 Morning Intelligence", "⚡ Live Market", "📓 Performance"])

with tab_morning:
    st.subheader("AI Market Brief")
    if ai.get("enabled"):
        a, b, c, d = st.columns(4)
        a.metric("AI Bias", ai.get("bias", "UNKNOWN"))
        b.metric("Regime", ai.get("market_regime", "UNKNOWN"))
        c.metric("Confidence", ai.get("confidence", "LOW"))
        d.metric("Rule Bias", report.get("verdict", "WAIT"))

        st.info(ai.get("thesis", ""))
        x, y, z = st.columns(3)
        with x:
            st.markdown("### 🟢 Bull case")
            st.write(ai.get("bull_case", ""))
        with y:
            st.markdown("### 🟡 Base case")
            st.write(ai.get("base_case", ""))
        with z:
            st.markdown("### 🔴 Bear case")
            st.write(ai.get("bear_case", ""))

        st.markdown("### 🎯 Key levels & invalidation")
        for level in ai.get("key_levels", []):
            st.write("•", level)
        st.warning(ai.get("invalidation", ""))

        x, y = st.columns(2)
        with x:
            st.markdown("### Drivers")
            for item in ai.get("drivers", []):
                st.write("•", item)
        with y:
            st.markdown("### Risks")
            for item in ai.get("risks", []):
                st.write("•", item)
    else:
        st.warning(ai.get("status", "AI ANALYSIS NOT AVAILABLE"))

    st.subheader("📊 Technical snapshot")
    levels = report.get("levels", {})
    if levels:
        st.dataframe(pd.DataFrame([levels]), use_container_width=True, hide_index=True)
    else:
        st.caption("No technical snapshot is stored for today yet.")

    st.subheader("🏭 Sector pulse")
    sectors = report.get("sectors", [])
    if sectors:
        sdf = pd.DataFrame(sectors).rename(columns={"sector": "Sector", "avg_change_pct": "Avg 1D %", "members": "Members"})
        sdf["Avg 1D %"] = sdf["Avg 1D %"].round(2)
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    else:
        st.caption("Sector data will appear after the next trading-day report.")

    st.subheader("📰 Overnight / pre-market news")
    pre_news = report.get("news", [])
    if pre_news:
        for item in pre_news[:12]:
            title = item.get("title", "")
            link = item.get("link", "")
            if link:
                st.markdown(f"**[{title}]({link})** — {item.get('source','')}")
            else:
                st.markdown(f"**{title}** — {item.get('source','')}")
    else:
        st.caption("No cached pre-market headlines.")

with tab_live:
    st.subheader("⚡ Live market monitor")
    if indices.empty:
        st.warning("Live market snapshot unavailable from the free feed right now.")
    else:
        ldf = indices.copy()
        ldf["ticker"] = ldf["ticker"].replace({"^NSEI": "NIFTY 50", "^NSEBANK": "BANK NIFTY", "^BSESN": "SENSEX", "^INDIAVIX": "INDIA VIX"})
        ldf["last"] = ldf["last"].round(2)
        ldf["from_open_pct"] = ldf["from_open_pct"].round(2)
        st.dataframe(ldf, use_container_width=True, hide_index=True)

    st.subheader("👀 Watchlist")
    watchlist = load_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
    wdf = watchlist_data(tuple(watchlist))
    if not wdf.empty:
        st.dataframe(wdf.sort_values("1D %", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.caption("Watchlist data unavailable right now.")

    st.subheader("📰 Live news")
    news = live_news()
    st.caption(f"Last refresh: {now.strftime('%H:%M:%S IST')}")
    if news:
        for item in news[:18]:
            title = item.get("title", "")
            link = item.get("link", "")
            if link:
                st.markdown(f"**[{title}]({link})**  \n{item.get('source','')} — {item.get('published','')}")
            else:
                st.markdown(f"**{title}**  \n{item.get('source','')} — {item.get('published','')}")
    else:
        st.caption("Live news unavailable from the free feeds right now.")

with tab_history:
    st.subheader("📓 MarketPilot journal")
    history = load_json(HISTORY_FILE, [])
    if history:
        rows = []
        for item in history:
            ai_item = item.get("ai", {}) or {}
            rows.append({
                "Date": item.get("date_ist", ""),
                "Rule bias": item.get("rule_bias", ""),
                "AI bias": ai_item.get("bias", ""),
                "Regime": ai_item.get("market_regime", ""),
                "Confidence": ai_item.get("confidence", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("This journal records the morning thesis. Outcome scoring will be added once we build the end-of-day evaluator.")
    else:
        st.info("No trading-day history yet. The first trading-day run will create the first journal entry.")

st.divider()
st.caption("Free/public data can be delayed, incomplete, or temporarily unavailable. MarketPilot never places orders and is not financial advice.")

st_autorefresh(interval=60_000, key="marketpilot_refresh")
