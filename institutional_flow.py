from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


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


def fetch_fii_dii(timeout: int = 12) -> FlowResult:
    """Fetch the latest available NSE FII/DII cash-market activity.

    The function is deliberately conservative: if NSE cannot be reached or the
    response cannot be parsed, it returns an unavailable result rather than
    inventing or silently reusing stale numbers.
    """
    if requests is None:
        return FlowResult(False, message="requests is unavailable in this environment.")

    try:
        session = requests.Session()
        session.headers.update(_headers())
        session.get("https://www.nseindia.com/", timeout=timeout)
        response = session.get(NSE_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return FlowResult(False, message=f"NSE flow data unavailable: {exc}")

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        return FlowResult(False, message="NSE returned no FII/DII records.")

    rows: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        date = item.get("date") or item.get("Date") or item.get("tradeDate")
        fii_buy = item.get("fiiBuyValue") or item.get("buyValueFII") or item.get("FII BUY")
        fii_sell = item.get("fiiSellValue") or item.get("sellValueFII") or item.get("FII SELL")
        fii_net = item.get("fiiNetValue") or item.get("netValueFII") or item.get("FII NET")
        dii_buy = item.get("diiBuyValue") or item.get("buyValueDII") or item.get("DII BUY")
        dii_sell = item.get("diiSellValue") or item.get("sellValueDII") or item.get("DII SELL")
        dii_net = item.get("diiNetValue") or item.get("netValueDII") or item.get("DII NET")

        def number(value: Any) -> float | None:
            try:
                if value is None or value == "":
                    return None
                return float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                return None

        row = {
            "date": str(date or ""),
            "fii_buy": number(fii_buy), "fii_sell": number(fii_sell), "fii_net": number(fii_net),
            "dii_buy": number(dii_buy), "dii_sell": number(dii_sell), "dii_net": number(dii_net),
        }
        if any(row[k] is not None for k in row if k != "date"):
            rows.append(row)

    if not rows:
        return FlowResult(False, message="NSE response format changed; no usable FII/DII values found.")

    df = pd.DataFrame(rows)
    if "date" in df:
        parsed = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
        df = df.assign(_date=parsed).sort_values("_date", ascending=False, na_position="last")
        rows = df.drop(columns=["_date"]).to_dict("records")

    latest_date = rows[0].get("date", "")
    freshness = None
    try:
        latest = pd.to_datetime(latest_date, errors="coerce", dayfirst=True)
        if pd.notna(latest):
            freshness = max(0, (pd.Timestamp.now().normalize() - latest.normalize()).days)
    except Exception:
        pass

    return FlowResult(True, date=str(latest_date), rows=rows, freshness_days=freshness)


def summarize_flow(result: FlowResult) -> dict[str, Any]:
    if not result.available or not result.rows:
        return {"available": False, "message": result.message}

    df = pd.DataFrame(result.rows)
    numeric = ["fii_net", "dii_net"]
    for col in numeric:
        if col not in df:
            df[col] = pd.NA
    df["combined_net"] = df["fii_net"].fillna(0) + df["dii_net"].fillna(0)

    recent = df.head(5)
    fii_5d = recent["fii_net"].sum(min_count=1)
    dii_5d = recent["dii_net"].sum(min_count=1)
    combined_5d = recent["combined_net"].sum(min_count=1)

    fii_today = df.iloc[0]["fii_net"]
    dii_today = df.iloc[0]["dii_net"]
    combined_today = df.iloc[0]["combined_net"]

    def tone(value: Any) -> str:
        if pd.isna(value) or value == 0:
            return "NEUTRAL"
        return "BUYING" if value > 0 else "SELLING"

    if pd.isna(combined_5d):
        regime = "INSUFFICIENT DATA"
    elif combined_5d > 0 and fii_5d > 0:
        regime = "INSTITUTIONAL ACCUMULATION"
    elif combined_5d < 0 and fii_5d < 0:
        regime = "INSTITUTIONAL DISTRIBUTION"
    else:
        regime = "DIVERGENT FLOWS"

    return {
        "available": True,
        "date": result.date,
        "freshness_days": result.freshness_days,
        "today": {"fii_net": fii_today, "dii_net": dii_today, "combined_net": combined_today},
        "five_day": {"fii_net": fii_5d, "dii_net": dii_5d, "combined_net": combined_5d},
        "fii_tone": tone(fii_today), "dii_tone": tone(dii_today),
        "regime": regime,
        "rows": result.rows[:10],
    }
