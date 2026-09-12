from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

NSE_URL = "https://www.nseindia.com/api/fiidiiTradeReact"

@dataclass
class FlowResult:
    available: bool
    date: str = ""
    rows: list[dict[str, Any]] | None = None
    message: str = ""
    freshness_days: int | None = None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nseindia.com/",
    }


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_fii_dii(timeout: int = 12) -> FlowResult:
    """Fetch NSE's latest FII/FPI and DII cash-market activity.

    NSE currently returns one record per category, with fields such as
    category, date, buyValue, sellValue and netValue. Older variants may expose
    combined FII/DII fields, so both shapes are supported.
    """
    try:
        session = requests.Session()
        session.headers.update(_headers())
        home = session.get("https://www.nseindia.com/", timeout=timeout)
        home.raise_for_status()
        response = session.get(NSE_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return FlowResult(False, message=f"NSE flow data unavailable: {exc}")

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        return FlowResult(False, message="NSE returned no FII/DII records.")

    rows: list[dict[str, Any]] = []
    # Current NSE shape: [{category: 'FII/FPI', date, buyValue, sellValue, netValue}, ...]
    current: dict[str, dict[str, Any]] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or item.get("Category") or "").upper()
        date = item.get("date") or item.get("Date") or item.get("tradeDate")
        if category in {"FII/FPI", "FII", "FPI"}:
            current["fii"] = {
                "date": str(date or ""), "fii_buy": _number(item.get("buyValue")),
                "fii_sell": _number(item.get("sellValue")), "fii_net": _number(item.get("netValue")),
            }
        elif category == "DII":
            current["dii"] = {
                "date": str(date or ""), "dii_buy": _number(item.get("buyValue")),
                "dii_sell": _number(item.get("sellValue")), "dii_net": _number(item.get("netValue")),
            }

    if current.get("fii") or current.get("dii"):
        base = current.get("fii", {}).copy()
        base.update(current.get("dii", {}))
        base.setdefault("date", current.get("dii", {}).get("date", ""))
        base.setdefault("fii_buy", None); base.setdefault("fii_sell", None); base.setdefault("fii_net", None)
        base.setdefault("dii_buy", None); base.setdefault("dii_sell", None); base.setdefault("dii_net", None)
        rows = [base]
    else:
        # Legacy/alternate shape with one row containing FII/DII fields.
        for item in records:
            if not isinstance(item, dict):
                continue
            row = {
                "date": str(item.get("date") or item.get("Date") or item.get("tradeDate") or ""),
                "fii_buy": _number(item.get("fiibuy") or item.get("fiiBuy") or item.get("fiiBuyValue")),
                "fii_sell": _number(item.get("fiisell") or item.get("fiiSell") or item.get("fiiSellValue")),
                "fii_net": _number(item.get("fiinet") or item.get("fiiNet") or item.get("fiiNetValue")),
                "dii_buy": _number(item.get("diibuy") or item.get("diiBuy") or item.get("diiBuyValue")),
                "dii_sell": _number(item.get("diisell") or item.get("diiSell") or item.get("diiSellValue")),
                "dii_net": _number(item.get("diinet") or item.get("diiNet") or item.get("diiNetValue")),
            }
            if any(row[k] is not None for k in row if k != "date"):
                rows.append(row)

    if not rows:
        return FlowResult(False, message="NSE response contained no recognizable FII/FPI or DII values.")

    df = pd.DataFrame(rows)
    parsed = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.assign(_date=parsed).sort_values("_date", ascending=False, na_position="last")
    rows = df.drop(columns=["_date"]).to_dict("records")
    latest_date = str(rows[0].get("date", ""))

    freshness = None
    latest = pd.to_datetime(latest_date, errors="coerce", dayfirst=True)
    if pd.notna(latest):
        freshness = max(0, (pd.Timestamp.now().normalize() - latest.normalize()).days)

    return FlowResult(True, date=latest_date, rows=rows, freshness_days=freshness)


def summarize_flow(result: FlowResult) -> dict[str, Any]:
    if not result.available or not result.rows:
        return {"available": False, "message": result.message}

    df = pd.DataFrame(result.rows)
    for col in ["fii_net", "dii_net"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["combined_net"] = df["fii_net"].fillna(0) + df["dii_net"].fillna(0)
    recent = df.head(5)
    fii_5d = recent["fii_net"].sum(min_count=1)
    dii_5d = recent["dii_net"].sum(min_count=1)
    combined_5d = recent["combined_net"].sum(min_count=1)
    fii_today, dii_today = df.iloc[0]["fii_net"], df.iloc[0]["dii_net"]

    if pd.isna(combined_5d):
        regime = "INSUFFICIENT DATA"
    elif combined_5d > 0 and fii_5d > 0:
        regime = "INSTITUTIONAL ACCUMULATION"
    elif combined_5d < 0 and fii_5d < 0:
        regime = "INSTITUTIONAL DISTRIBUTION"
    else:
        regime = "DIVERGENT FLOWS"

    def tone(value: Any) -> str:
        if pd.isna(value) or value == 0:
            return "NEUTRAL"
        return "BUYING" if value > 0 else "SELLING"

    return {
        "available": True, "date": result.date, "freshness_days": result.freshness_days,
        "today": {"fii_net": fii_today, "dii_net": dii_today, "combined_net": df.iloc[0]["combined_net"]},
        "five_day": {"fii_net": fii_5d, "dii_net": dii_5d, "combined_net": combined_5d},
        "fii_tone": tone(fii_today), "dii_tone": tone(dii_today), "regime": regime,
        "rows": result.rows[:10],
    }
