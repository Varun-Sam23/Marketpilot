"""MarketPilot market-intelligence engine.

Builds a pre-market evidence pack from prior-session data and overnight news,
then asks the AI layer for a structured decision-support thesis.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf

from ai_brain import analyze
from decision_engine import score_setup
from news_intelligence import enrich_news

OUT = Path("data/latest.json")
HISTORY = Path("data/history.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

IST = ZoneInfo("Asia/Kolkata")
NSE_CALENDAR = mcal.get_calendar("NSE")

INDEXES = {
    "NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX", "S&P 500": "^GSPC", "NASDAQ": "^IXIC",
    "NIKKEI": "^N225", "HANG SENG": "^HSI", "USD/INR": "INR=X",
    "CRUDE": "CL=F", "GOLD": "GC=F",
}

SECTORS = {
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS"],
    "IT": ["INFY.NS", "TCS.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS"],
    "Auto": ["TATAMOTORS.NS", "M&M.NS"],
    "FMCG": ["ITC.NS", "HINDUNILVR.NS"],
    "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS"],
}

WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS",
]

NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]


def is_nse_trading_day(day=None):
    day = day or datetime.now(IST).date()
    return not NSE_CALENDAR.schedule(start_date=day, end_date=day).empty


def write_closed_report(reason):
    now = datetime.now(IST)
    report = {
        "date_ist": now.strftime("%Y-%m-%d"),
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_status": "MARKET CLOSED", "verdict": "WAIT", "confidence": "N/A",
        "summary": reason, "signals": [], "levels": {}, "global": [], "news": [],
        "watchlist": [], "sectors": [], "decision": {
            "score": 50, "bias": "WAIT", "confidence": "N/A", "regime": "MARKET CLOSED",
            "positive_factors": 0, "negative_factors": 0, "evidence": [],
            "bull_trigger": "", "bear_trigger": "", "invalidation": "",
            "methodology": "No score is produced while the market is closed.",
        },
        "ai_analysis": {"enabled": False, "status": "MARKET CLOSED", "bias": "WAIT", "confidence": "N/A",
                        "market_regime": "UNKNOWN", "thesis": "No market thesis generated because the NSE cash market is closed.",
                        "bull_case": "", "base_case": "", "bear_case": "", "key_levels": [],
                        "invalidation": "", "drivers": [], "risks": [], "watchlist_focus": [], "news_impact": []},
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def hist(ticker, period="6mo", interval="1d"):
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame()


def pct(a, b):
    return (a / b - 1) * 100 if b else 0.0


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    if len(series) < period + 1:
        return None
    rs = gain / loss.replace(0, pd.NA)
    value = (100 - (100 / (1 + rs))).iloc[-1]
    return float(value) if pd.notna(value) else None


def market_snapshot():
    out = []
    for name, ticker in INDEXES.items():
        h = hist(ticker, "10d", "1d")
        if len(h) >= 2:
            close, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
            out.append({"name": name, "ticker": ticker, "last": round(close, 2), "change_pct": round(pct(close, prev), 2)})
    return out


def nifty_technicals():
    h = hist("^NSEI")
    if len(h) < 55:
        return {}
    c = h["Close"]
    last = float(c.iloc[-1])
    sma5 = float(c.tail(5).mean())
    sma20 = float(c.tail(20).mean())
    sma50 = float(c.tail(50).mean())
    high20 = float(h["High"].tail(20).max())
    low20 = float(h["Low"].tail(20).min())
    rng = high20 - low20
    r = rsi(c)
    return {
        "NIFTY close": round(last, 2), "Previous close": round(float(c.iloc[-2]), 2),
        "5D return %": round(pct(last, float(c.iloc[-6])), 2),
        "20D return %": round(pct(last, float(c.iloc[-21])), 2),
        "5D SMA": round(sma5, 2), "20D SMA": round(sma20, 2), "50D SMA": round(sma50, 2),
        "20D high": round(high20, 2), "20D low": round(low20, 2),
        "RSI14": round(r, 2) if r is not None else None,
        "range_position_%": round(((last - low20) / rng) * 100, 1) if rng else 50.0,
    }


def watchlist_snapshot():
    rows = []
    for ticker in WATCHLIST:
        h = hist(ticker, "3mo", "1d")
        if len(h) >= 22:
            last, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
            sma20 = float(h["Close"].tail(20).mean())
            vol, avgvol = float(h["Volume"].iloc[-1]), float(h["Volume"].tail(20).mean())
            r = rsi(h["Close"])
            rows.append({
                "ticker": ticker.replace(".NS", ""), "last": round(last, 2),
                "change_pct": round(pct(last, prev), 2),
                "20D_return_pct": round(pct(last, float(h["Close"].iloc[-21])), 2),
                "vs_20D_SMA_pct": round(pct(last, sma20), 2),
                "volume_vs_20D": round(vol / avgvol, 2) if avgvol else None,
                "RSI14": round(r, 2) if r is not None else None,
            })
    return rows


def sector_snapshot():
    out = []
    for sector, tickers in SECTORS.items():
        changes = []
        for ticker in tickers:
            h = hist(ticker, "10d", "1d")
            if len(h) >= 2:
                changes.append(pct(float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])))
        if changes:
            out.append({"sector": sector, "avg_change_pct": round(sum(changes) / len(changes), 2), "members": len(changes)})
    return sorted(out, key=lambda x: x["avg_change_pct"], reverse=True)


def news_items():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                source_name = entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else ""
                items.append({
                    "title": entry.get("title", ""),
                    "source": source,
                    "publisher": source_name,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception:
            pass
    return enrich_news(items[:24])


def rule_bias(levels, snapshots):
    by = {x["name"]: x for x in snapshots}
    n, b, v = by.get("NIFTY 50", {}), by.get("BANK NIFTY", {}), by.get("INDIA VIX", {})
    score, reasons = 0, []
    if levels:
        if levels["NIFTY close"] > levels["20D SMA"]: score += 1; reasons.append("NIFTY is above the 20-day average.")
        else: score -= 1; reasons.append("NIFTY is below the 20-day average.")
        if levels.get("20D return %", 0) > 0: score += 1; reasons.append("NIFTY has positive 20-day momentum.")
        else: score -= 1; reasons.append("NIFTY has negative 20-day momentum.")
        if levels.get("RSI14") is not None:
            if levels["RSI14"] > 60: score += 1; reasons.append("NIFTY RSI shows positive momentum.")
            elif levels["RSI14"] < 40: score -= 1; reasons.append("NIFTY RSI shows weak momentum.")
    if n and b and b.get("change_pct", 0) > n.get("change_pct", 0): score += 1; reasons.append("Bank Nifty outperformed NIFTY in the latest session.")
    if v and v.get("change_pct", 0) > 5: score -= 1; reasons.append("India VIX rose sharply; volatility risk is elevated.")
    verdict = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"
    confidence = "HIGH" if abs(score) >= 4 else "MEDIUM" if abs(score) >= 2 else "LOW"
    return verdict, confidence, reasons


def append_history(report):
    try:
        history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
        history = [x for x in history if x.get("date_ist") != report.get("date_ist")]
        history.append({
            "date_ist": report.get("date_ist"), "generated_at": report.get("generated_at"),
            "rule_bias": report.get("verdict"), "rule_confidence": report.get("confidence"),
            "ai": report.get("ai_analysis", {}), "decision": report.get("decision", {}),
            "levels": report.get("levels", {}),
        })
        HISTORY.write_text(json.dumps(history[-90:], indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run():
    now = datetime.now(IST)
    force_test = os.getenv("FORCE_MARKET_ANALYSIS", "0").strip() == "1"

    if not is_nse_trading_day(now.date()) and not force_test:
        write_closed_report(f"NSE cash market is closed today ({now.strftime('%A, %d %B %Y')}). No pre-market trading analysis was generated.")
        return

    snapshots = market_snapshot()
    levels = nifty_technicals()
    verdict, confidence, reasons = rule_bias(levels, snapshots)
    news = news_items()
    watchlist = watchlist_snapshot()
    sectors = sector_snapshot()
    decision = score_setup(levels, snapshots, sectors, news)

    payload = {
        "date_ist": now.strftime("%Y-%m-%d"), "test_mode": force_test,
        "rule_bias": verdict, "rule_confidence": confidence, "signals": reasons,
        "levels": levels, "market_snapshot": snapshots, "sectors": sectors,
        "news": news, "watchlist": watchlist, "decision": decision,
    }
    ai_result = analyze(payload)
    if force_test:
        ai_result["test_mode"] = True
        ai_result["status"] = "AI TEST ANALYSIS"

    report = {
        "date_ist": now.strftime("%Y-%m-%d"), "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_status": "AI TEST MODE" if force_test else "PRE-MARKET INTELLIGENCE",
        "verdict": verdict, "confidence": confidence,
        "summary": f"Rule-based evidence suggests a {verdict.lower()} starting framework. The Decision Engine scores the evidence separately.",
        "signals": reasons, "levels": levels, "global": snapshots, "news": news,
        "watchlist": watchlist, "sectors": sectors, "decision": decision, "ai_analysis": ai_result,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not force_test:
        append_history(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
