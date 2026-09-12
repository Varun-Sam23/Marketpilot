import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="MarketPilot", page_icon="📈", layout="wide")

DATA_FILE = Path("data/latest.json")
WATCHLIST_FILE = Path("data/watchlist.json")

DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS"
]

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

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
    })

report = load_morning_report()

st.title("📈 MarketPilot")
st.caption("Pre-market intelligence + live market/news monitoring • No order execution")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Market status", "NSE / BSE")
col2.metric("Morning report", report.get("verdict", "WAIT"))
col3.metric("Report time", report.get("generated_at", "Not generated"))
col4.metric("Mode", "Decision support only")

st.info(
    "The morning report is designed to form a hypothesis from previous sessions and overnight information. "
    "Live values below are refreshed while this page is open."
)

st.subheader("🧠 Morning Intelligence")
a, b = st.columns([1, 2])
with a:
    st.metric("Bias", report.get("verdict", "WAIT"))
    st.write("Confidence:", report.get("confidence", "Low"))
with b:
    st.write(report.get("summary", ""))

if report.get("signals"):
    st.subheader("Key signals")
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

st.subheader("📰 News")
news = report.get("news", [])
if news:
    for item in news[:12]:
        st.markdown(f"**{item.get('title','')}**  \n{item.get('source','')} — {item.get('published','')}")
else:
    st.caption("No cached news yet.")

st.subheader("📊 Live market snapshot")
indices = ["^NSEI", "^NSEBANK", "^BSESN", "^INDIAVIX"]
live = intraday_snapshot(indices)
if not live.empty:
    live["ticker"] = live["ticker"].replace({
        "^NSEI": "NIFTY 50", "^NSEBANK": "BANK NIFTY",
        "^BSESN": "SENSEX", "^INDIAVIX": "INDIA VIX"
    })
    st.dataframe(live, use_container_width=True, hide_index=True)
else:
    st.warning("Live snapshot unavailable from the free data source right now.")

st.subheader("👀 Watchlist")
watchlist = load_json(WATCHLIST_FILE, DEFAULT_WATCHLIST)
watch = market_data(watchlist)
if not watch.empty:
    watch["ticker"] = watch["ticker"].str.replace(".NS", "", regex=False)
    st.dataframe(watch.sort_values("change_pct", ascending=False), use_container_width=True, hide_index=True)
else:
    st.caption("Watchlist data unavailable right now.")

st.divider()
st.caption(
    "Data from free/public sources can be delayed, incomplete, or temporarily unavailable. "
    "This dashboard is for research and education, not financial advice."
)

# Refresh every 60 seconds while the browser tab is open.
st_autorefresh(interval=60_000, key="marketpilot_refresh")
