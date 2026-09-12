"""Intraday market-structure intelligence for MarketPilot.

Uses recent 5-minute candles to derive VWAP, opening range, momentum,
volume anomalies, breadth and simple support/resistance context. No synthetic
market values are generated when live data is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")
NIFTY = "^NSEI"
WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
    "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS",
]


def _history(ticker: str) -> pd.DataFrame:
    try:
        h = yf.Ticker(ticker).history(period="2d", interval="5m", auto_adjust=False, prepost=False)
        if h is None or h.empty:
            return pd.DataFrame()
        h = h.copy()
        h.index = pd.to_datetime(h.index)
        return h
    except Exception:
        return pd.DataFrame()


def _today(h: pd.DataFrame) -> pd.DataFrame:
    if h.empty:
        return h
    now = datetime.now(IST)
    idx = h.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert(IST)
    else:
        idx = idx.tz_convert(IST)
    h = h.copy()
    h.index = idx
    return h[h.index.date == now.date()].copy()


def _vwap(h: pd.DataFrame) -> float | None:
    if h.empty:
        return None
    typical = (h["High"] + h["Low"] + h["Close"]) / 3
    vol = pd.to_numeric(h["Volume"], errors="coerce").fillna(0)
    total = vol.sum()
    return float((typical * vol).sum() / total) if total > 0 else None


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _opening_range(h: pd.DataFrame, minutes: int = 15) -> tuple[float | None, float | None]:
    if h.empty:
        return None, None
    start = h.index.min()
    end = start + pd.Timedelta(minutes=minutes)
    r = h[h.index < end]
    if r.empty:
        return None, None
    return float(r["High"].max()), float(r["Low"].min())


def _volume_ratio(h: pd.DataFrame) -> float | None:
    if len(h) < 7:
        return None
    recent = float(h["Volume"].iloc[-1])
    baseline = float(h["Volume"].iloc[:-1].tail(20).mean())
    return round(recent / baseline, 2) if baseline else None


def _momentum(h: pd.DataFrame) -> float:
    if len(h) < 4:
        return 0.0
    return _pct(float(h["Close"].iloc[-1]), float(h["Close"].iloc[-4]))


def _levels(h: pd.DataFrame) -> dict:
    if h.empty:
        return {}
    recent = h.tail(min(24, len(h)))
    last = float(h["Close"].iloc[-1])
    return {
        "session_high": round(float(h["High"].max()), 2),
        "session_low": round(float(h["Low"].min()), 2),
        "recent_resistance": round(float(recent["High"].max()), 2),
        "recent_support": round(float(recent["Low"].min()), 2),
        "last": round(last, 2),
    }


def _breadth() -> dict:
    rows = []
    for ticker in WATCHLIST:
        h = _today(_history(ticker))
        if len(h) >= 2:
            last = float(h["Close"].iloc[-1])
            first = float(h["Open"].iloc[0])
            rows.append({"ticker": ticker.replace(".NS", ""), "change_pct": round(_pct(last, first), 2)})
    adv = sum(x["change_pct"] > 0 for x in rows)
    dec = sum(x["change_pct"] < 0 for x in rows)
    unchanged = len(rows) - adv - dec
    return {"advancers": adv, "decliners": dec, "unchanged": unchanged, "total": len(rows), "breadth_ratio": round(adv / dec, 2) if dec else (float(adv) if adv else 0.0), "rows": rows}


def fetch_intraday() -> dict:
    h = _today(_history(NIFTY))
    if len(h) < 3:
        return {"available": False, "message": "Intraday 5-minute NIFTY data is unavailable from the market-data feed.", "source": "Yahoo Finance market-data feed"}

    last = float(h["Close"].iloc[-1])
    prev_close = None
    try:
        prior = _history(NIFTY)
        prior_day = prior[prior.index.date < datetime.now(IST).date()]
        if not prior_day.empty:
            prev_close = float(prior_day["Close"].iloc[-1])
    except Exception:
        pass

    or_high, or_low = _opening_range(h, 15)
    vwap = _vwap(h)
    vol_ratio = _volume_ratio(h)
    momentum = _momentum(h)
    breadth = _breadth()
    levels = _levels(h)

    points = 50
    reasons = []
    if vwap is not None:
        if last > vwap: points += 15; reasons.append("NIFTY is trading above intraday VWAP.")
        else: points -= 15; reasons.append("NIFTY is trading below intraday VWAP.")
    if or_high is not None and or_low is not None:
        if last > or_high: points += 12; reasons.append("Price is above the 15-minute opening range high.")
        elif last < or_low: points -= 12; reasons.append("Price is below the 15-minute opening range low.")
        else: reasons.append("Price remains inside the 15-minute opening range.")
    if momentum > 0.15: points += 10; reasons.append("Short-term momentum is positive.")
    elif momentum < -0.15: points -= 10; reasons.append("Short-term momentum is negative.")
    if vol_ratio is not None and vol_ratio >= 1.5:
        points += 5 if momentum > 0 else -5
        reasons.append(f"Latest 5-minute volume is {vol_ratio:.1f}x the recent intraday baseline.")
    if breadth["total"]:
        if breadth["advancers"] > breadth["decliners"]: points += 8; reasons.append("Watchlist breadth favours advancers.")
        elif breadth["decliners"] > breadth["advancers"]: points -= 8; reasons.append("Watchlist breadth favours decliners.")

    score = max(0, min(100, points))
    if score >= 70: bias = "BULLISH"
    elif score <= 30: bias = "BEARISH"
    else: bias = "NEUTRAL"
    if score >= 80 or score <= 20: confidence = "HIGH"
    elif score >= 65 or score <= 35: confidence = "MEDIUM"
    else: confidence = "LOW"

    if or_high and last > or_high: or_state = "BREAKOUT ABOVE OR"
    elif or_low and last < or_low: or_state = "BREAKDOWN BELOW OR"
    else: or_state = "INSIDE OPENING RANGE"

    return {
        "available": True,
        "as_of": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "source": "Yahoo Finance market-data feed",
        "source_url": "https://finance.yahoo.com/",
        "last": round(last, 2),
        "session_change_pct": round(_pct(last, prev_close), 2) if prev_close else None,
        "vwap": round(vwap, 2) if vwap is not None else None,
        "opening_range_high": round(or_high, 2) if or_high is not None else None,
        "opening_range_low": round(or_low, 2) if or_low is not None else None,
        "opening_range_state": or_state,
        "volume_ratio": vol_ratio,
        "momentum_15m_pct": round(momentum, 2),
        "breadth": breadth,
        "levels": levels,
        "score": score,
        "bias": bias,
        "confidence": confidence,
        "reasons": reasons,
    }
