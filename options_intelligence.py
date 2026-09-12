from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import requests

NSE_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
NIFTYTRADER_CHAIN_URL = "https://api.niftytrader.in/api/option/option-chain-data"
NIFTYTRADER_EXPIRY_URL = "https://webapi.niftytrader.in/webapi/Symbol/delta-symbol-expiry-list"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
}


@dataclass
class OptionResult:
    available: bool
    symbol: str
    expiry: str
    spot: float
    rows: pd.DataFrame
    source: str
    source_url: str
    message: str = ""


def _empty(symbol: str, message: str) -> OptionResult:
    return OptionResult(False, symbol, "", 0.0, pd.DataFrame(), "", "", message)


def _normalise_rows(rows: list[dict[str, Any]], symbol: str, expiry: str, spot: float, source: str, source_url: str) -> OptionResult:
    if not rows:
        return _empty(symbol, "No option-chain rows were returned.")
    df = pd.DataFrame(rows)
    if "strike" not in df.columns:
        return _empty(symbol, "Option-chain response did not contain strike data.")
    for col in ["ce_oi", "ce_chg_oi", "ce_volume", "ce_iv", "ce_ltp", "pe_oi", "pe_chg_oi", "pe_volume", "pe_iv", "pe_ltp"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df = df.dropna(subset=["strike"]).sort_values("strike").reset_index(drop=True)
    if df.empty:
        return _empty(symbol, "Option-chain response contained no usable strikes.")
    return OptionResult(True, symbol, expiry, float(spot or 0), df, source, source_url)


def _fetch_nse(symbol: str, timeout: float = 4.0) -> OptionResult:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        response = session.get(NSE_CHAIN_URL, params={"symbol": symbol}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records", {})
        spot = float(records.get("underlyingValue") or 0)
        expiries = records.get("expiryDates") or []
        rows = []
        for item in records.get("data", []):
            ce = item.get("CE") or {}
            pe = item.get("PE") or {}
            rows.append({
                "strike": item.get("strikePrice"),
                "expiry": item.get("expiryDate", ""),
                "ce_oi": ce.get("openInterest", 0),
                "ce_chg_oi": ce.get("changeinOpenInterest", 0),
                "ce_volume": ce.get("totalTradedVolume", 0),
                "ce_iv": ce.get("impliedVolatility", 0),
                "ce_ltp": ce.get("lastPrice", 0),
                "pe_oi": pe.get("openInterest", 0),
                "pe_chg_oi": pe.get("changeinOpenInterest", 0),
                "pe_volume": pe.get("totalTradedVolume", 0),
                "pe_iv": pe.get("impliedVolatility", 0),
                "pe_ltp": pe.get("lastPrice", 0),
            })
        expiry = expiries[0] if expiries else ""
        return _normalise_rows(rows, symbol, expiry, spot, "NSE India", "https://www.nseindia.com/option-chain")
    except Exception as exc:
        return _empty(symbol, f"NSE option-chain request failed: {exc}")


def _fetch_niftytrader(symbol: str, timeout: float = 8.0) -> OptionResult:
    session = requests.Session()
    session.headers.update({**HEADERS, "Content-Type": "application/json", "platform_type": "2"})
    try:
        expiry_response = session.get(NIFTYTRADER_EXPIRY_URL, params={"symbol": symbol}, timeout=timeout)
        expiry_response.raise_for_status()
        expiry_payload = expiry_response.json()
        expiries = []
        for item in expiry_payload.get("resultData") or []:
            raw = item.get("expiry_date") or ""
            if raw:
                expiries.append(raw[:10])
        today = date.today().isoformat()
        upcoming = sorted({x for x in expiries if x >= today})
        expiry = upcoming[0] if upcoming else (sorted(set(expiries))[0] if expiries else "")
        if not expiry:
            return _empty(symbol, "NiftyTrader returned no usable expiry dates.")

        response = session.get(NIFTYTRADER_CHAIN_URL, params={"symbol": symbol, "expiry": expiry}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("resultData") or {}
        rows = []
        spot = 0.0
        for item in result.get("opDatas") or []:
            spot = float(item.get("index_close") or spot)
            rows.append({
                "strike": item.get("strike_price"),
                "expiry": expiry,
                "ce_oi": item.get("calls_oi", 0),
                "ce_chg_oi": item.get("calls_change_oi", 0),
                "ce_volume": item.get("calls_volume", 0),
                "ce_iv": item.get("calls_iv", 0),
                "ce_ltp": item.get("calls_ltp", 0),
                "pe_oi": item.get("puts_oi", 0),
                "pe_chg_oi": item.get("puts_change_oi", 0),
                "pe_volume": item.get("puts_volume", 0),
                "pe_iv": item.get("puts_iv", 0),
                "pe_ltp": item.get("puts_ltp", 0),
            })
        return _normalise_rows(rows, symbol, expiry, spot, "NiftyTrader public API", "https://niftytrader.in/option-chain")
    except Exception as exc:
        return _empty(symbol, f"NiftyTrader fallback failed: {exc}")


def fetch_option_chain(symbol: str = "NIFTY") -> OptionResult:
    symbol = symbol.upper().strip()
    for fetcher in (_fetch_nse, _fetch_niftytrader):
        result = fetcher(symbol)
        if result.available:
            return result
    return _empty(symbol, "Option-chain data unavailable from NSE and validated public fallback.")


def _nearest(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    if df.empty or not spot:
        return df.head(0)
    idx = (df["strike"] - spot).abs().idxmin()
    pos = df.index.get_loc(idx)
    start = max(0, pos - 8)
    end = min(len(df), pos + 9)
    return df.iloc[start:end].copy()


def analyse_option_chain(result: OptionResult) -> dict[str, Any]:
    if not result.available or result.rows.empty:
        return {"available": False, "message": result.message}
    df = result.rows.copy()
    spot = result.spot
    atm = float(df.loc[(df["strike"] - spot).abs().idxmin(), "strike"]) if spot else float(df["strike"].median())

    total_call_oi = float(df["ce_oi"].sum())
    total_put_oi = float(df["pe_oi"].sum())
    total_call_volume = float(df["ce_volume"].sum())
    total_put_volume = float(df["pe_volume"].sum())
    pcr_oi = total_put_oi / total_call_oi if total_call_oi else 0.0
    pcr_volume = total_put_volume / total_call_volume if total_call_volume else 0.0

    pain = []
    strikes = df["strike"].tolist()
    for strike in strikes:
        call_loss = ((strike - df["strike"]) * df["ce_oi"]).clip(lower=0).sum()
        put_loss = ((df["strike"] - strike) * df["pe_oi"]).clip(lower=0).sum()
        pain.append((strike, float(call_loss + put_loss)))
    max_pain = min(pain, key=lambda x: x[1])[0] if pain else None

    call_res = df.sort_values("ce_oi", ascending=False).head(3)[["strike", "ce_oi", "ce_chg_oi"]]
    put_sup = df.sort_values("pe_oi", ascending=False).head(3)[["strike", "pe_oi", "pe_chg_oi"]]
    atm_window = _nearest(df, spot)
    atm_window["ATM"] = atm_window["strike"].eq(atm)

    if pcr_oi >= 1.15:
        bias = "PUT-OI HEAVY"
    elif pcr_oi <= 0.85:
        bias = "CALL-OI HEAVY"
    else:
        bias = "BALANCED OI"

    return {
        "available": True,
        "symbol": result.symbol,
        "expiry": result.expiry,
        "spot": spot,
        "atm": atm,
        "pcr_oi": pcr_oi,
        "pcr_volume": pcr_volume,
        "max_pain": max_pain,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "total_call_volume": total_call_volume,
        "total_put_volume": total_put_volume,
        "oi_bias": bias,
        "call_resistance": call_res,
        "put_support": put_sup,
        "atm_window": atm_window,
        "source": result.source,
        "source_url": result.source_url,
        "raw": df,
    }
