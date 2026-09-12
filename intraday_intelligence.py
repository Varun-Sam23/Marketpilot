"""Intraday market-structure intelligence for MarketPilot.

Derives transparent, descriptive structure signals from recent NIFTY 5-minute
candles and an 8-stock watchlist. No synthetic market values are generated.
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
        h = yf.Ticker(ticker).history(period="5d", interval="5m", auto_adjust=False, prepost=False)
        if h is None or h.empty:
            return pd.DataFrame()
        h = h.copy()
        h.index = pd.to_datetime(h.index)
        return h
    except Exception:
        return pd.DataFrame()


def _ist(h: pd.DataFrame) -> pd.DataFrame:
    if h.empty:
        return h
    idx = h.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    idx = idx.tz_convert(IST)
    out = h.copy()
    out.index = idx
    return out


def _today(h: pd.DataFrame) -> pd.DataFrame:
    h = _ist(h)
    if h.empty:
        return h
    return h[h.index.date == datetime.now(IST).date()].copy()


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _vwap(h: pd.DataFrame) -> float | None:
    if h.empty:
        return None
    typical = (h["High"] + h["Low"] + h["Close"]) / 3
    vol = pd.to_numeric(h["Volume"], errors="coerce").fillna(0)
    total = vol.sum()
    return float((typical * vol).sum() / total) if total > 0 else None


def _opening_range(h: pd.DataFrame, minutes: int = 15) -> tuple[float | None, float | None]:
    if h.empty:
        return None, None
    start = h.index.min()
    r = h[h.index < start + pd.Timedelta(minutes=minutes)]
    if r.empty:
        return None, None
    return float(r["High"].max()), float(r["Low"].min())


def _volume_stats(h: pd.DataFrame) -> tuple[float | None, float | None]:
    if len(h) < 7:
        return None, None
    recent = float(h["Volume"].iloc[-1])
    baseline = float(h["Volume"].iloc[:-1].tail(20).mean())
    ratio = round(recent / baseline, 2) if baseline else None
    spike = round(float(h["Volume"].tail(6).mean()) / baseline, 2) if baseline else None
    return ratio, spike


def _momentum(h: pd.DataFrame, bars: int = 3) -> float:
    if len(h) <= bars:
        return 0.0
    return _pct(float(h["Close"].iloc[-1]), float(h["Close"].iloc[-1 - bars]))


def _trend(h: pd.DataFrame) -> str:
    if len(h) < 12:
        return "INSUFFICIENT DATA"
    close = h["Close"]
    fast = float(close.tail(6).mean())
    slow = float(close.tail(12).mean())
    if fast > slow * 1.0005:
        return "UPTREND"
    if fast < slow * 0.9995:
        return "DOWNTREND"
    return "SIDEWAYS"


def _levels(h: pd.DataFrame) -> dict:
    if h.empty:
        return {}
    recent = h.tail(min(24, len(h)))
    return {
        "session_high": round(float(h["High"].max()), 2),
        "session_low": round(float(h["Low"].min()), 2),
        "recent_resistance": round(float(recent["High"].max()), 2),
        "recent_support": round(float(recent["Low"].min()), 2),
        "last": round(float(h["Close"].iloc[-1]), 2),
    }


def _breadth() -> dict:
    rows = []
    for ticker in WATCHLIST:
        h = _today(_history(ticker))
        if len(h) >= 2:
            last = float(h["Close"].iloc[-1])
            first = float(h["Open"].iloc[0])
            rows.append({"Stock": ticker.replace(".NS", ""), "Change %": round(_pct(last, first), 2)})
    adv = sum(x["Change %"] > 0 for x in rows)
    dec = sum(x["Change %"] < 0 for x in rows)
    unchanged = len(rows) - adv - dec
    ratio = round(adv / dec, 2) if dec else (float(adv) if adv else 0.0)
    rows.sort(key=lambda x: x["Change %"], reverse=True)
    return {"advancers": adv, "decliners": dec, "unchanged": unchanged, "total": len(rows), "breadth_ratio": ratio, "rows": rows}


def _synthesis(score: int, bias: str, vwap: float | None, last: float, or_state: str,
               momentum: float, trend: str, vol_ratio: float | None, breadth: dict,
               levels: dict) -> dict:
    """Translate computed signals into a concise, evidence-only live read."""
    bull = 0
    bear = 0
    evidence = []
    if vwap is not None:
        if last > vwap: bull += 1; evidence.append("price above VWAP")
        else: bear += 1; evidence.append("price below VWAP")
    if "BREAKOUT" in or_state: bull += 2; evidence.append("opening-range breakout")
    elif "BREAKDOWN" in or_state: bear += 2; evidence.append("opening-range breakdown")
    if momentum > 0.15: bull += 1; evidence.append("positive 15m momentum")
    elif momentum < -0.15: bear += 1; evidence.append("negative 15m momentum")
    if trend == "UPTREND": bull += 1; evidence.append("rising short-term trend")
    elif trend == "DOWNTREND": bear += 1; evidence.append("falling short-term trend")
    if breadth["advancers"] > breadth["decliners"]: bull += 1; evidence.append("watchlist breadth positive")
    elif breadth["decliners"] > breadth["advancers"]: bear += 1; evidence.append("watchlist breadth negative")

    if bias == "BULLISH": headline = "Buyers are in control"
    elif bias == "BEARISH": headline = "Sellers are in control"
    else: headline = "Market is in balance"

    if abs(bull - bear) <= 1:
        headline = "Signals are mixed — wait for confirmation"
    elif bias == "NEUTRAL":
        headline = "Direction is developing — confirmation needed"

    nearest = None
    if levels:
        candidates = [x for x in (levels.get("recent_resistance"), levels.get("recent_support")) if x]
        if candidates:
            nearest = min(candidates, key=lambda x: abs(x - last))
    return {
        "headline": headline,
        "detail": "; ".join(evidence[:5]) if evidence else "Not enough independent structure signals.",
        "bull_count": bull,
        "bear_count": bear,
        "nearest_level": nearest,
        "volume_confirming": bool(vol_ratio is not None and vol_ratio >= 1.5),
    }


def fetch_intraday() -> dict:
    h = _today(_history(NIFTY))
    if len(h) < 3:
        return {"available": False, "message": "Intraday 5-minute NIFTY data is unavailable from the market-data feed.", "source": "Yahoo Finance market-data feed"}

    last = float(h["Close"].iloc[-1])
    prev_close = None
    try:
        all_h = _ist(_history(NIFTY))
        prior = all_h[all_h.index.date < datetime.now(IST).date()]
        if not prior.empty:
            prev_close = float(prior["Close"].iloc[-1])
    except Exception:
        pass

    or_high, or_low = _opening_range(h)
    vwap = _vwap(h)
    vol_ratio, volume_spike = _volume_stats(h)
    momentum = _momentum(h, 3)
    trend = _trend(h)
    breadth = _breadth()
    levels = _levels(h)

    points = 50
    reasons = []
    components = {}

    if vwap is not None:
        vwap_points = 12 if last > vwap else -12
        points += vwap_points
        components["VWAP"] = vwap_points
        reasons.append(f"Price is {abs(_pct(last, vwap)):.2f}% {'above' if last > vwap else 'below'} VWAP.")

    if or_high is not None and or_low is not None:
        if last > or_high:
            points += 14; components["Opening Range"] = 14; reasons.append("NIFTY is above the 15-minute opening-range high: breakout structure.")
        elif last < or_low:
            points -= 14; components["Opening Range"] = -14; reasons.append("NIFTY is below the 15-minute opening-range low: breakdown structure.")
        else:
            components["Opening Range"] = 0; reasons.append("NIFTY remains inside the 15-minute opening range.")

    if momentum > 0.15:
        points += 9; components["Momentum"] = 9; reasons.append(f"15-minute momentum is positive at {momentum:.2f}%.")
    elif momentum < -0.15:
        points -= 9; components["Momentum"] = -9; reasons.append(f"15-minute momentum is negative at {momentum:.2f}%.")
    else:
        components["Momentum"] = 0; reasons.append(f"15-minute momentum is muted at {momentum:.2f}%.")

    if trend == "UPTREND":
        points += 8; components["Trend"] = 8; reasons.append("Short-term moving-average structure is rising.")
    elif trend == "DOWNTREND":
        points -= 8; components["Trend"] = -8; reasons.append("Short-term moving-average structure is falling.")
    else:
        components["Trend"] = 0; reasons.append("Short-term moving-average structure is sideways.")

    if vol_ratio is not None and vol_ratio >= 1.5:
        volume_points = 5 if momentum > 0 else -5 if momentum < 0 else 0
        points += volume_points; components["Volume"] = volume_points
        reasons.append(f"Latest 5-minute volume is {vol_ratio:.2f}x the recent baseline.")
    else:
        components["Volume"] = 0

    if breadth["total"]:
        breadth_points = 7 if breadth["advancers"] > breadth["decliners"] else -7 if breadth["decliners"] > breadth["advancers"] else 0
        points += breadth_points; components["Breadth"] = breadth_points
        reasons.append(f"Watchlist breadth is {breadth['advancers']} advancing vs {breadth['decliners']} declining.")
    else:
        components["Breadth"] = 0

    score = max(0, min(100, int(round(points))))
    bias = "BULLISH" if score >= 70 else "BEARISH" if score <= 30 else "NEUTRAL"
    confidence = "HIGH" if score >= 82 or score <= 18 else "MEDIUM" if score >= 65 or score <= 35 else "LOW"
    if or_high and last > or_high: or_state = "BREAKOUT ABOVE OR"
    elif or_low and last < or_low: or_state = "BREAKDOWN BELOW OR"
    else: or_state = "INSIDE OPENING RANGE"

    synthesis = _synthesis(score, bias, vwap, last, or_state, momentum, trend, vol_ratio, breadth, levels)
    return {
        "available": True,
        "as_of": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "source": "Yahoo Finance market-data feed",
        "source_url": "https://finance.yahoo.com/",
        "last": round(last, 2),
        "session_change_pct": round(_pct(last, prev_close), 2) if prev_close else None,
        "vwap": round(vwap, 2) if vwap is not None else None,
        "vwap_distance_pct": round(_pct(last, vwap), 2) if vwap else None,
        "opening_range_high": round(or_high, 2) if or_high is not None else None,
        "opening_range_low": round(or_low, 2) if or_low is not None else None,
        "opening_range_state": or_state,
        "volume_ratio": vol_ratio,
        "volume_spike_6bar": volume_spike,
        "momentum_15m_pct": round(momentum, 2),
        "trend": trend,
        "breadth": breadth,
        "levels": levels,
        "components": components,
        "score": score,
        "bias": bias,
        "confidence": confidence,
        "reasons": reasons,
        "synthesis": synthesis,
    }
