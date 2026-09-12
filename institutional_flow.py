from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

NSE_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
MRCHARTIST_HISTORY_URL = "https://fii-diidata.mrchartist.com/api/history"
MONEYCONTROL_URL = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/"


@dataclass
class FlowResult:
    available: bool
    date: str = ""
    rows: list[dict[str, Any]] | None = None
    message: str = ""
    freshness_days: int | None = None
    source: str = ""
    source_url: str = ""


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
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None


def _finish(rows: list[dict[str, Any]], source: str, source_url: str) -> FlowResult:
    if not rows:
        return FlowResult(False, message="No usable institutional-flow records were found.")
    df = pd.DataFrame(rows)
    if "date" not in df:
        return FlowResult(False, message="Institutional-flow source returned no dates.")
    parsed = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.assign(_date=parsed).sort_values("_date", ascending=False, na_position="last")
    rows = df.drop(columns=["_date"]).to_dict("records")
    latest_date = str(rows[0].get("date", ""))
    freshness = None
    latest = pd.to_datetime(latest_date, errors="coerce", dayfirst=True)
    if pd.notna(latest):
        freshness = max(0, (pd.Timestamp.now().normalize() - latest.normalize()).days)
    return FlowResult(True, date=latest_date, rows=rows, freshness_days=freshness, source=source, source_url=source_url)


def _fetch_nse(timeout: int) -> FlowResult:
    """Try NSE directly. Do not require the NSE homepage cookie: some hosted
    environments receive a 403 on the homepage while the report endpoint is
    still accessible."""
    try:
        session = requests.Session()
        session.headers.update(_headers())
        response = session.get(NSE_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return FlowResult(False, message=f"NSE direct request failed: {exc}")

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return FlowResult(False, message="NSE returned an unexpected response shape.")

    current: dict[str, dict[str, Any]] = {}
    legacy: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or item.get("Category") or "").upper()
        date = item.get("date") or item.get("Date") or item.get("tradeDate")
        if category in {"FII/FPI", "FII", "FPI"}:
            current["fii"] = {"date": str(date or ""), "fii_buy": _number(item.get("buyValue")), "fii_sell": _number(item.get("sellValue")), "fii_net": _number(item.get("netValue"))}
        elif category == "DII":
            current["dii"] = {"date": str(date or ""), "dii_buy": _number(item.get("buyValue")), "dii_sell": _number(item.get("sellValue")), "dii_net": _number(item.get("netValue"))}
        else:
            row = {
                "date": str(date or ""),
                "fii_buy": _number(item.get("fiibuy") or item.get("fiiBuy") or item.get("fiiBuyValue")),
                "fii_sell": _number(item.get("fiisell") or item.get("fiiSell") or item.get("fiiSellValue")),
                "fii_net": _number(item.get("fiinet") or item.get("fiiNet") or item.get("fiiNetValue")),
                "dii_buy": _number(item.get("diibuy") or item.get("diiBuy") or item.get("diiBuyValue")),
                "dii_sell": _number(item.get("diisell") or item.get("diiSell") or item.get("diiSellValue")),
                "dii_net": _number(item.get("diinet") or item.get("diiNet") or item.get("diiNetValue")),
            }
            if any(row[k] is not None for k in row if k != "date"):
                legacy.append(row)

    if current:
        row = current.get("fii", {}).copy()
        row.update(current.get("dii", {}))
        for key in ("fii_buy", "fii_sell", "fii_net", "dii_buy", "dii_sell", "dii_net"):
            row.setdefault(key, None)
        row.setdefault("date", current.get("dii", {}).get("date", ""))
        legacy = [row]
    return _finish(legacy, "NSE India", "https://www.nseindia.com/reports/fii-dii")


def _fetch_mrchartist(timeout: int) -> FlowResult:
    """Fallback mirror whose documented pipeline sources daily cash data from NSE.
    Reject seeded/estimated rows so MarketPilot never presents them as facts."""
    try:
        response = requests.get(MRCHARTIST_HISTORY_URL, headers={"User-Agent": "MarketPilot/1.0"}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return FlowResult(False, message=f"Mr Chartist fallback unavailable: {exc}")

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return FlowResult(False, message="Mr Chartist returned an unexpected response shape.")
    rows: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if item.get("_source") not in {None, "fetch-pipeline"}:
            continue
        row = {
            "date": str(item.get("date") or item.get("d") or ""),
            "fii_buy": _number(item.get("fii_buy") or item.get("fb")),
            "fii_sell": _number(item.get("fii_sell") or item.get("fs")),
            "fii_net": _number(item.get("fii_net") or item.get("fn")),
            "dii_buy": _number(item.get("dii_buy") or item.get("db")),
            "dii_sell": _number(item.get("dii_sell") or item.get("ds")),
            "dii_net": _number(item.get("dii_net") or item.get("dn")),
        }
        if row["date"] and any(row[k] is not None for k in row if k != "date"):
            rows.append(row)
    return _finish(rows, "NSE-derived mirror (Mr Chartist)", "https://fii-diidata.mrchartist.com/data-api.html")


def _fetch_moneycontrol(timeout: int) -> FlowResult:
    """Last-resort HTML fallback. Moneycontrol publishes the same daily cash-flow
    fields; source is explicitly labelled so provenance remains visible."""
    try:
        tables = pd.read_html(MONEYCONTROL_URL)
    except Exception as exc:
        return FlowResult(False, message=f"Moneycontrol fallback unavailable: {exc}")
    rows: list[dict[str, Any]] = []
    for table in tables:
        if table.empty:
            continue
        cols = [str(c).lower() for c in table.columns]
        if not any("gross purchase" in c for c in cols):
            continue
        table = table.copy()
        for _, values in table.iterrows():
            vals = list(values)
            text = " ".join(str(v) for v in vals)
            if "Month till date" in text or "Date" in text and len(vals) < 7:
                continue
            if len(vals) < 7:
                continue
            rows.append({
                "date": str(vals[0]),
                "fii_buy": _number(vals[1]), "fii_sell": _number(vals[2]), "fii_net": _number(vals[3]),
                "dii_buy": _number(vals[4]), "dii_sell": _number(vals[5]), "dii_net": _number(vals[6]),
            })
        if rows:
            break
    return _finish(rows, "Moneycontrol", MONEYCONTROL_URL)


def fetch_fii_dii(timeout: int = 12) -> FlowResult:
    for fetcher in (_fetch_nse, _fetch_mrchartist, _fetch_moneycontrol):
        result = fetcher(timeout)
        if result.available:
            return result
    return FlowResult(False, message="Institutional flow data unavailable from NSE and validated fallbacks.")


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
        "available": True,
        "date": result.date,
        "freshness_days": result.freshness_days,
        "source": result.source,
        "source_url": result.source_url,
        "today": {"fii_net": fii_today, "dii_net": dii_today, "combined_net": df.iloc[0]["combined_net"]},
        "five_day": {"fii_net": fii_5d, "dii_net": dii_5d, "combined_net": combined_5d},
        "fii_tone": tone(fii_today), "dii_tone": tone(dii_today),
        "regime": regime,
        "rows": result.rows[:10],
    }
