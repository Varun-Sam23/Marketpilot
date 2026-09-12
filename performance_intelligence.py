"""Evaluate MarketPilot's historical directional theses without hindsight edits."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

HISTORY = Path("data/history.json")
IST = ZoneInfo("Asia/Kolkata")


def _load_history() -> list[dict]:
    try:
        value = json.loads(HISTORY.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _session_after(date_str: str) -> pd.DataFrame:
    try:
        start = pd.Timestamp(date_str) + pd.Timedelta(days=1)
        end = start + pd.Timedelta(days=7)
        return yf.Ticker("^NSEI").history(start=start, end=end, interval="1d", auto_adjust=False)
    except Exception:
        return pd.DataFrame()


def _evaluate(item: dict) -> dict:
    date = item.get("date_ist", "")
    decision = item.get("decision", {}) or {}
    bias = str(decision.get("bias") or item.get("rule_bias") or "").upper()
    score = decision.get("score")
    if not date or not bias:
        return {"date": date, "bias": bias or "UNKNOWN", "score": score, "status": "NOT EVALUABLE"}
    h = _session_after(date)
    if h.empty:
        return {"date": date, "bias": bias, "score": score, "status": "PENDING"}
    row = h.iloc[0]
    open_px = float(row["Open"])
    close_px = float(row["Close"])
    day_return = (close_px / open_px - 1) * 100 if open_px else 0.0
    aligned = (bias == "BULLISH" and day_return > 0) or (bias == "BEARISH" and day_return < 0)
    neutral_ok = bias in {"NEUTRAL", "WAIT"} and abs(day_return) <= 0.75
    return {
        "date": date,
        "bias": bias,
        "score": score,
        "next_session_return_pct": round(day_return, 2),
        "result": "CORRECT" if aligned or neutral_ok else "WRONG",
        "status": "EVALUATED",
    }


def fetch_performance() -> dict:
    history = _load_history()
    rows = [_evaluate(x) for x in history]
    evaluated = [x for x in rows if x.get("status") == "EVALUATED"]
    correct = sum(x.get("result") == "CORRECT" for x in evaluated)
    accuracy = round(correct / len(evaluated) * 100, 1) if evaluated else None
    avg_return = round(sum(x.get("next_session_return_pct", 0) for x in evaluated) / len(evaluated), 2) if evaluated else None
    return {
        "available": bool(history),
        "as_of": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "total_theses": len(rows),
        "evaluated": len(evaluated),
        "pending": sum(x.get("status") == "PENDING" for x in rows),
        "accuracy_pct": accuracy,
        "avg_next_session_return_pct": avg_return,
        "rows": list(reversed(rows)),
        "source": "MarketPilot historical thesis + Yahoo Finance NIFTY daily data",
    }
