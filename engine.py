"""
MarketPilot pre-market engine V1.1.1.

Adds:
- India Standard Time timestamps
- NSE trading-day/holiday detection
- A clear MARKET CLOSED report on non-trading days
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf

OUT = Path("data/latest.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

IST = ZoneInfo("Asia/Kolkata")
NSE_CALENDAR = mcal.get_calendar("NSE")

INDEXES = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX",
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "NIKKEI": "^N225",
    "HANG SENG": "^HSI",
    "USD/INR": "INR=X",
    "CRUDE": "CL=F",
    "GOLD": "GC=F",
}

NEWS_FEEDS = [
    (
        "Google News - India Markets",
        "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News - RBI",
        "https://news.google.com/rss/search?q=RBI%20India%20economy&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News - Companies",
        "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20companies&hl=en-IN&gl=IN&ceid=IN:en",
    ),
]

WATCHLIST = [
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "INFY.NS",
    "TCS.NS",
    "TATAMOTORS.NS",
    "ITC.NS",
]


def is_nse_trading_day(day=None):
    """Return True when day is an NSE cash-market trading session."""
    day = day or datetime.now(IST).date()
    schedule = NSE_CALENDAR.schedule(start_date=day, end_date=day)
    return not schedule.empty


def write_closed_report(reason):
    now = datetime.now(IST)
    report = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_status": "MARKET CLOSED",
        "verdict": "WAIT",
        "confidence": "N/A",
        "summary": reason,
        "signals": [],
        "levels": {},
        "global": [],
        "news": [],
        "watchlist": [],
    }
    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def hist(ticker, period="3mo", interval="1d"):
    try:
        return yf.Ticker(ticker).history(
            period=period,
            interval=interval,
            auto_adjust=False,
        )
    except Exception:
        return pd.DataFrame()


def pct(a, b):
    return (a / b - 1) * 100 if b else 0.0


def index_snapshot():
    out = []
    for name, ticker in INDEXES.items():
        h = hist(ticker, "10d", "1d")
        if len(h) >= 2:
            close = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2])
            out.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "last": round(close, 2),
                    "change_pct": round(pct(close, prev), 2),
                }
            )
    return out


def nifty_levels():
    h = hist("^NSEI", "3mo", "1d")
    if len(h) < 10:
        return {}

    c = h["Close"]
    last = float(c.iloc[-1])
    prior = float(c.iloc[-2])

    return {
        "NIFTY close": round(last, 2),
        "Previous close": round(prior, 2),
        "20D SMA": round(float(c.tail(20).mean()), 2),
        "50D SMA": round(
            float(c.tail(50).mean()) if len(c) >= 50 else float(c.mean()),
            2,
        ),
        "20D high": round(float(h["High"].tail(20).max()), 2),
        "20D low": round(float(h["Low"].tail(20).min()), 2),
    }


def make_verdict(levels, snapshots):
    by = {x["name"]: x for x in snapshots}
    n = by.get("NIFTY 50", {})
    b = by.get("BANK NIFTY", {})
    v = by.get("INDIA VIX", {})

    score = 0
    reasons = []

    if n and n.get("change_pct", 0) > 0:
        score += 1
        reasons.append("NIFTY closed higher than the previous session.")
    elif n:
        score -= 1
        reasons.append("NIFTY closed lower than the previous session.")

    if levels:
        if levels["NIFTY close"] > levels["20D SMA"]:
            score += 1
            reasons.append("NIFTY is above its 20-day average.")
        else:
            score -= 1
            reasons.append("NIFTY is below its 20-day average.")

    if b and b.get("change_pct", 0) > (n.get("change_pct", 0) if n else 0):
        score += 1
        reasons.append("Bank Nifty showed relative strength.")
    elif b:
        reasons.append("Bank Nifty did not outperform NIFTY in the last session.")

    if v:
        if v.get("change_pct", 0) > 5:
            score -= 1
            reasons.append("India VIX rose sharply; volatility risk is elevated.")
        elif v.get("change_pct", 0) < -5:
            score += 1
            reasons.append("India VIX fell sharply; volatility pressure eased.")

    verdict = (
        "BULLISH" if score >= 2
        else "BEARISH" if score <= -2
        else "NEUTRAL"
    )

    confidence = (
        "Higher" if abs(score) >= 3
        else "Moderate" if abs(score) == 2
        else "Low"
    )

    summary = (
        f"Current evidence points to a {verdict.lower()} starting hypothesis. "
        "This is a pre-market framework, not a prediction or trade signal. "
        "The thesis should be re-evaluated when the live market confirms or rejects key levels."
    )

    return verdict, confidence, summary, reasons


def news_items():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                items.append(
                    {
                        "title": entry.get("title", ""),
                        "source": source,
                        "published": entry.get("published", ""),
                        "link": entry.get("link", ""),
                    }
                )
        except Exception:
            pass
    return items[:15]


def watchlist_snapshot():
    rows = []
    for ticker in WATCHLIST:
        h = hist(ticker, "10d", "1d")
        if len(h) >= 2:
            last = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2])
            vol = float(h["Volume"].iloc[-1])
            avgvol = float(h["Volume"].tail(5).mean())

            rows.append(
                {
                    "ticker": ticker,
                    "last": round(last, 2),
                    "change_pct": round(pct(last, prev), 2),
                    "volume_vs_5d_avg": round(vol / avgvol, 2) if avgvol else None,
                }
            )
    return rows


def run():
    now = datetime.now(IST)

    if not is_nse_trading_day(now.date()):
        write_closed_report(
            f"NSE cash market is closed today "
            f"({now.strftime('%A, %d %B %Y')}). "
            "No pre-market trading analysis was generated."
        )
        return

    snapshots = index_snapshot()
    levels = nifty_levels()
    verdict, confidence, summary, reasons = make_verdict(levels, snapshots)

    report = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_status": "Pre-market intelligence report",
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "signals": reasons,
        "levels": levels,
        "global": snapshots,
        "news": news_items(),
        "watchlist": watchlist_snapshot(),
    }

    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
