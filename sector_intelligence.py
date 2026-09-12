"""Sector intelligence for MarketPilot.

Ranks Indian market sectors using price momentum, trend position, relative
strength and breadth across a small liquid representative basket. Missing
market data is excluded rather than fabricated.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")
SECTORS = {
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS"],
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS"],
    "Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS"],
    "FMCG": ["ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS"],
    "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS"],
    "Metals": ["TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS"],
    "Financials": ["AXISBANK.NS", "KOTAKBANK.NS", "BAJFINANCE.NS"],
}


def _history(ticker: str) -> pd.DataFrame:
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d", auto_adjust=False)
        return h if h is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    value = (100 - 100 / (1 + rs)).iloc[-1]
    return float(value) if pd.notna(value) else None


def _member(ticker: str) -> dict | None:
    h = _history(ticker)
    if len(h) < 22:
        return None
    close = pd.to_numeric(h["Close"], errors="coerce").dropna()
    if len(close) < 22:
        return None
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    ret5 = _pct(last, float(close.iloc[-6])) if len(close) >= 6 else 0.0
    ret20 = _pct(last, float(close.iloc[-21]))
    sma20 = float(close.tail(20).mean())
    rsi = _rsi(close)
    return {
        "ticker": ticker.replace(".NS", ""),
        "last": round(last, 2),
        "day_pct": round(_pct(last, prev), 2),
        "5d_pct": round(ret5, 2),
        "20d_pct": round(ret20, 2),
        "vs_sma20_pct": round(_pct(last, sma20), 2),
        "rsi14": round(rsi, 1) if rsi is not None else None,
    }


def _score(row: dict) -> float:
    score = 50.0
    score += max(-15, min(15, row["day_pct"] * 4))
    score += max(-12, min(12, row["5d_pct"] * 1.5))
    score += max(-12, min(12, row["20d_pct"] * 0.7))
    score += max(-8, min(8, row["vs_sma20_pct"] * 2))
    if row["rsi14"] is not None:
        if row["rsi14"] >= 60:
            score += 5
        elif row["rsi14"] <= 40:
            score -= 5
    return max(0, min(100, round(score)))


def fetch_sector_intelligence() -> dict:
    rows = []
    for sector, tickers in SECTORS.items():
        members = [m for t in tickers if (m := _member(t))]
        if not members:
            continue
        avg_day = sum(x["day_pct"] for x in members) / len(members)
        avg5 = sum(x["5d_pct"] for x in members) / len(members)
        avg20 = sum(x["20d_pct"] for x in members) / len(members)
        avg_sma = sum(x["vs_sma20_pct"] for x in members) / len(members)
        breadth = sum(x["day_pct"] > 0 for x in members) / len(members) * 100
        score = round(sum(_score(x) for x in members) / len(members))
        if score >= 65:
            label = "LEADING"
        elif score <= 35:
            label = "LAGGING"
        else:
            label = "NEUTRAL"
        reasons = []
        if avg_day > 0.3:
            reasons.append("positive daily momentum")
        elif avg_day < -0.3:
            reasons.append("negative daily momentum")
        if avg20 > 1:
            reasons.append("positive 20-day trend")
        elif avg20 < -1:
            reasons.append("negative 20-day trend")
        if avg_sma > 0.5:
            reasons.append("trading above 20-day average")
        elif avg_sma < -0.5:
            reasons.append("trading below 20-day average")
        if breadth >= 67:
            reasons.append("broad participation")
        elif breadth <= 33:
            reasons.append("weak participation")
        rows.append({
            "sector": sector, "score": score, "label": label,
            "day_pct": round(avg_day, 2), "5d_pct": round(avg5, 2),
            "20d_pct": round(avg20, 2), "vs_sma20_pct": round(avg_sma, 2),
            "breadth_pct": round(breadth, 0), "members": len(members),
            "members_detail": members, "reasons": reasons,
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    leaders = [x["sector"] for x in rows if x["label"] == "LEADING"][:3]
    laggards = [x["sector"] for x in reversed(rows) if x["label"] == "LAGGING"][:3]
    return {
        "available": bool(rows),
        "as_of": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "rows": rows,
        "leaders": leaders,
        "laggards": laggards,
        "source": "Yahoo Finance daily market-data feed",
        "source_url": "https://finance.yahoo.com/",
    }
