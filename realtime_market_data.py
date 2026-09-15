"""Live market-data layer for MarketPilot.

Primary feed: Upstox MarketDataStreamerV3 over WebSocket.
Fallback: the existing yfinance polling path remains available when no
UPSTOX_ACCESS_TOKEN is configured. No synthetic prices are generated.

The WebSocket is intentionally read-only. This module never places orders.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")

INSTRUMENTS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "INDIA_VIX": "NSE_INDEX|India VIX",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "INFY": "NSE_EQ|INE009A01021",
    "TCS": "NSE_EQ|INE467B01029",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "ITC": "NSE_EQ|INE154A01025",
}

_lock = threading.RLock()
_state: dict[str, Any] = {
    "provider": "NONE",
    "status": "NOT_CONFIGURED",
    "connected_at": None,
    "last_tick_at": None,
    "ticks": 0,
    "errors": [],
    "quotes": {},
}
_started = False
_streamer = None


def _set_error(message: str) -> None:
    with _lock:
        _state["status"] = "ERROR"
        _state["errors"] = ([str(message)] + list(_state.get("errors", [])))[:5]


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _walk(value)


def _decode(message: Any) -> Any:
    if isinstance(message, (bytes, bytearray)):
        try:
            return json.loads(message.decode("utf-8"))
        except Exception:
            return message
    if isinstance(message, str):
        try:
            return json.loads(message)
        except Exception:
            return message
    return message


def _extract_quote(payload: Any, instrument_key: str) -> dict[str, Any] | None:
    payload = _decode(payload)
    root = payload if isinstance(payload, dict) else {}
    feeds = root.get("feeds") if isinstance(root, dict) else None
    if not isinstance(feeds, dict):
        return None
    raw = feeds.get(instrument_key)
    if raw is None:
        return None

    ltpc = None
    market = None
    for node in _walk(raw):
        if isinstance(node, dict):
            if isinstance(node.get("ltpc"), dict):
                ltpc = node["ltpc"]
            if isinstance(node.get("marketOHLC"), dict):
                market = node["marketOHLC"]

    if not ltpc:
        return None
    ltp = _number(ltpc.get("ltp"))
    if ltp is None:
        return None
    quote = {
        "ltp": ltp,
        "last_trade_time": ltpc.get("ltt"),
        "last_trade_qty": _number(ltpc.get("ltq")),
        "prev_close": _number(ltpc.get("cp")),
        "received_at": datetime.now(IST).isoformat(),
    }

    if isinstance(market, dict):
        candles = market.get("ohlc", [])
        if isinstance(candles, list):
            for candle in candles:
                if not isinstance(candle, dict):
                    continue
                interval = candle.get("interval")
                if interval in {"I1", "I30", "1d"}:
                    quote[f"ohlc_{interval}"] = {
                        "open": _number(candle.get("open")),
                        "high": _number(candle.get("high")),
                        "low": _number(candle.get("low")),
                        "close": _number(candle.get("close")),
                        "volume": _number(candle.get("vol")),
                        "ts": candle.get("ts"),
                    }
    for node in _walk(raw):
        if isinstance(node, dict):
            details = node.get("eFeedDetails")
            if isinstance(details, dict):
                quote["volume_today"] = _number(details.get("vtt"))
                quote["avg_traded_price"] = _number(details.get("atp"))
                quote["total_buy_qty"] = _number(details.get("tbq"))
                quote["total_sell_qty"] = _number(details.get("tsq"))
                break
    return quote


def _on_message(message: Any) -> None:
    payload = _decode(message)
    updated = 0
    with _lock:
        for name, key in INSTRUMENTS.items():
            quote = _extract_quote(payload, key)
            if quote:
                _state["quotes"][name] = quote
                updated += 1
        if updated:
            _state["ticks"] += 1
            _state["last_tick_at"] = datetime.now(IST).isoformat()
            _state["status"] = "LIVE"


def _on_open() -> None:
    with _lock:
        _state["status"] = "CONNECTED"
        _state["connected_at"] = datetime.now(IST).isoformat()
    try:
        _streamer.subscribe(list(INSTRUMENTS.values()), "full")
    except Exception as exc:
        _set_error(f"Subscription failed: {exc}")


def _on_error(message: Any) -> None:
    _set_error(f"WebSocket error: {message}")


def _on_close(*args: Any) -> None:
    with _lock:
        if _state.get("status") != "ERROR":
            _state["status"] = "DISCONNECTED"


def start() -> dict[str, Any]:
    """Start the read-only Upstox V3 WebSocket once per process."""
    global _started, _streamer
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    with _lock:
        if _started:
            return status()
        if not token:
            _state["provider"] = "yfinance-fallback"
            _state["status"] = "NOT_CONFIGURED"
            return status()
        _started = True
        _state["provider"] = "Upstox MarketDataStreamerV3"
        _state["status"] = "STARTING"
    try:
        import upstox_client

        configuration = upstox_client.Configuration()
        configuration.access_token = token
        _streamer = upstox_client.MarketDataStreamerV3(
            upstox_client.ApiClient(configuration), list(INSTRUMENTS.values()), "full"
        )
        _streamer.on("open", _on_open)
        _streamer.on("message", _on_message)
        _streamer.on("error", _on_error)
        _streamer.on("close", _on_close)
        _streamer.auto_reconnect(True, 5, 20)
        threading.Thread(target=_connect, name="marketpilot-upstox", daemon=True).start()
    except Exception as exc:
        _set_error(f"Upstox initialization failed: {exc}")
    return status()


def _connect() -> None:
    try:
        _streamer.connect()
    except Exception as exc:
        _set_error(f"WebSocket connection failed: {exc}")


def status() -> dict[str, Any]:
    with _lock:
        return {
            "provider": _state["provider"],
            "status": _state["status"],
            "connected_at": _state["connected_at"],
            "last_tick_at": _state["last_tick_at"],
            "ticks": _state["ticks"],
            "quote_count": len(_state["quotes"]),
            "errors": list(_state.get("errors", [])),
        }


def snapshot() -> dict[str, Any]:
    """Return a safe copy of the current live quote cache."""
    with _lock:
        return {"status": status(), "quotes": json.loads(json.dumps(_state["quotes"]))}


def live_quote(symbol: str) -> dict[str, Any] | None:
    start()
    with _lock:
        quote = _state["quotes"].get(symbol.upper())
        return dict(quote) if quote else None


def upstox_intraday_candles(symbol: str, interval: int) -> list[list[Any]]:
    """Fetch current-session candles directly from Upstox V3.

    Supported intervals are 1, 5, 15 and 30 minutes. This is the chart-data
    path for LIVE MARKET; it deliberately does not fall back to Yahoo Finance.
    """
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        return []
    if interval not in {1, 5, 15, 30}:
        return []
    instrument_key = INSTRUMENTS.get(symbol.upper())
    if not instrument_key:
        return []
    url = f"https://api.upstox.com/v3/historical-candle/intraday/{requests.utils.quote(instrument_key, safe='')}/minutes/{interval}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        payload = response.json()
        candles = payload.get("data", {}).get("candles", [])
        return candles if isinstance(candles, list) else []
    except Exception:
        return []
