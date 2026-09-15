"""NSE-listed equity universe for MarketPilot stock search.

Source: NSE India's official Securities available for Trading equity CSV.
The list is cached in-process for 24 hours and only EQ-series equities are
returned for the stock search. No prices are fabricated or stored here.
"""
from __future__ import annotations

import io
import threading
import time
from typing import Any

import pandas as pd
import requests

NSE_EQUITY_CSV = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (MarketPilot; NSE equity universe)",
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.nseindia.com/",
}
_CACHE_TTL = 24 * 60 * 60
_lock = threading.RLock()
_cache: tuple[float, pd.DataFrame] | None = None


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["SYMBOL", "COMPANY", "ISIN", "SERIES"])


def load_nse_equities(force: bool = False) -> pd.DataFrame:
    global _cache
    with _lock:
        if not force and _cache and time.time() - _cache[0] < _CACHE_TTL:
            return _cache[1].copy()
    try:
        response = requests.get(NSE_EQUITY_CSV, headers=_HEADERS, timeout=12)
        response.raise_for_status()
        raw = pd.read_csv(io.BytesIO(response.content), dtype=str).fillna("")
        raw.columns = [str(c).strip().upper() for c in raw.columns]
        symbol_col = next((c for c in raw.columns if c == "SYMBOL"), None)
        company_col = next((c for c in raw.columns if c in {"NAME OF COMPANY", "COMPANY NAME"}), None)
        isin_col = next((c for c in raw.columns if c in {"ISIN NUMBER", "ISIN"}), None)
        series_col = next((c for c in raw.columns if c == "SERIES"), None)
        if not symbol_col or not company_col:
            return _empty()
        out = pd.DataFrame({
            "SYMBOL": raw[symbol_col].astype(str).str.strip(),
            "COMPANY": raw[company_col].astype(str).str.strip(),
            "ISIN": raw[isin_col].astype(str).str.strip() if isin_col else "",
            "SERIES": raw[series_col].astype(str).str.strip().str.upper() if series_col else "EQ",
        })
        out = out[(out["SYMBOL"] != "") & (out["COMPANY"] != "")]
        out = out[out["SERIES"].eq("EQ")]
        out = out.drop_duplicates("SYMBOL").sort_values("SYMBOL").reset_index(drop=True)
        with _lock:
            _cache = (time.time(), out.copy())
        return out
    except Exception:
        with _lock:
            return _cache[1].copy() if _cache else _empty()


def search_nse_equities(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").strip().casefold()
    if not q:
        return []
    df = load_nse_equities()
    if df.empty:
        return []
    symbol = df["SYMBOL"].str.casefold()
    company = df["COMPANY"].str.casefold()
    exact = df[(symbol == q) | (company == q)]
    starts = df[(symbol.str.startswith(q)) | (company.str.startswith(q))]
    contains = df[symbol.str.contains(q, regex=False) | company.str.contains(q, regex=False)]
    result = pd.concat([exact, starts, contains]).drop_duplicates("SYMBOL").head(limit)
    return result.to_dict("records")


def nse_instrument_key(symbol: str) -> str | None:
    q = str(symbol or "").strip().upper()
    df = load_nse_equities()
    if df.empty:
        return None
    rows = df[df["SYMBOL"].eq(q)]
    if rows.empty:
        return None
    isin = str(rows.iloc[0]["ISIN"]).strip()
    return f"NSE_EQ|{isin}" if isin else None
