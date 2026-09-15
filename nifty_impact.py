"""Nifty 50 movement attribution.

Explains which sectors and stocks are putting upward/downward pressure on Nifty.
The sector contribution is explicitly a transparent attribution proxy using the
latest available stock returns and a published Nifty sector-weight snapshot;
it is not presented as an official real-time index-point contribution.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")
NIFTY50_SECTORS = {
    "Financial Services": ["AXISBANK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "JIOFIN.NS", "KOTAKBANK.NS", "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS"],
    "Oil, Gas & Consumable Fuels": ["COALINDIA.NS", "ONGC.NS", "RELIANCE.NS"],
    "Information Technology": ["HCLTECH.NS", "INFY.NS", "TCS.NS", "TECHM.NS", "WIPRO.NS"],
    "Automobile & Auto Components": ["BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "M&M.NS", "MARUTI.NS", "TATAMOTORS.NS"],
    "Fast Moving Consumer Goods": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "TATACONSUM.NS"],
    "Telecommunication": ["BHARTIARTL.NS"],
    "Construction": ["LT.NS"],
    "Healthcare": ["APOLLOHOSP.NS", "CIPLA.NS", "DRREDDY.NS", "MAXHEALTH.NS", "SUNPHARMA.NS"],
    "Metals & Mining": ["ADANIENT.NS", "HINDALCO.NS", "JSWSTEEL.NS", "TATASTEEL.NS"],
    "Power": ["NTPC.NS", "POWERGRID.NS"],
    "Consumer Durables": ["ASIANPAINT.NS", "TITAN.NS"],
    "Consumer Services": ["ETERNAL.NS", "TRENT.NS"],
    "Construction Materials": ["GRASIM.NS", "ULTRACEMCO.NS"],
    "Services": ["ADANIPORTS.NS"],
    "Capital Goods": ["BEL.NS"],
}
SECTOR_WEIGHTS = {
    "Financial Services": 35.15, "Oil, Gas & Consumable Fuels": 10.19,
    "Information Technology": 8.48, "Automobile & Auto Components": 6.87,
    "Fast Moving Consumer Goods": 5.99, "Telecommunication": 5.20,
    "Metals & Mining": 4.99, "Healthcare": 4.68, "Construction": 4.43,
    "Power": 2.92, "Consumer Durables": 2.68, "Consumer Services": 2.54,
    "Construction Materials": 2.36, "Services": 2.16, "Capital Goods": 1.36,
}


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _download_prices(tickers: list[str]) -> pd.DataFrame:
    try:
        raw = yf.download(tickers, period="5d", interval="1d", auto_adjust=False, progress=False, threads=True)
        if raw is None or raw.empty:
            return pd.DataFrame()
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) and "Close" in raw.columns.get_level_values(0) else raw
        if isinstance(close, pd.Series):
            close = close.to_frame()
        return close
    except Exception:
        return pd.DataFrame()


def fetch_nifty_impact() -> dict:
    tickers = [t for members in NIFTY50_SECTORS.values() for t in members]
    close = _download_prices(tickers)
    if close.empty:
        return {"available": False, "message": "Nifty constituent price data is unavailable."}

    rows = []
    for sector, members in NIFTY50_SECTORS.items():
        for ticker in members:
            if ticker not in close.columns:
                continue
            series = pd.to_numeric(close[ticker], errors="coerce").dropna()
            if len(series) < 2:
                continue
            last, prev = float(series.iloc[-1]), float(series.iloc[-2])
            rows.append({"Stock": ticker.replace(".NS", ""), "Sector": sector, "Price": round(last, 2), "1D %": round(_pct(last, prev), 2)})
    stocks = pd.DataFrame(rows)
    if stocks.empty:
        return {"available": False, "message": "No usable Nifty constituent returns are available."}

    sector_rows = []
    for sector in NIFTY50_SECTORS:
        part = stocks[stocks["Sector"] == sector]
        if part.empty:
            continue
        weight = float(SECTOR_WEIGHTS.get(sector, 0.0))
        avg_return = float(part["1D %"].mean())
        sector_rows.append({"Sector": sector, "Weight %": round(weight, 2), "Sector 1D %": round(avg_return, 2), "Pressure %": round(weight * avg_return / 100.0, 3), "Participation %": round(float((part["1D %"] > 0).mean() * 100), 0), "Stocks": len(part)})
    sectors = pd.DataFrame(sector_rows).sort_values("Pressure %", ascending=False)

    stock_rows = []
    for sector, part in stocks.groupby("Sector"):
        weight = float(SECTOR_WEIGHTS.get(sector, 0.0))
        per_stock_weight = weight / len(part) if len(part) else 0.0
        for _, row in part.iterrows():
            pressure = per_stock_weight * float(row["1D %"]) / 100.0
            stock_rows.append({**row.to_dict(), "Pressure %": round(pressure, 3), "Proxy Weight %": round(per_stock_weight, 2)})
    all_stocks = pd.DataFrame(stock_rows).sort_values("Pressure %", ascending=False)

    try:
        idx = yf.Ticker("^NSEI").history(period="5d", interval="1d", auto_adjust=False)
        nifty_move = round(_pct(float(idx["Close"].iloc[-1]), float(idx["Close"].iloc[-2])), 2) if idx is not None and len(idx) >= 2 else None
    except Exception:
        nifty_move = None

    direction = "RISING" if nifty_move is not None and nifty_move > 0 else "FALLING" if nifty_move is not None and nifty_move < 0 else "FLAT"
    if direction == "FALLING":
        dominant = sectors[sectors["Pressure %"] < 0].sort_values("Pressure %").head(3)
        drivers = all_stocks.sort_values("Pressure %").head(8)
    elif direction == "RISING":
        dominant = sectors[sectors["Pressure %"] > 0].sort_values("Pressure %", ascending=False).head(3)
        drivers = all_stocks.head(8)
    else:
        dominant = pd.DataFrame(columns=sectors.columns)
        drivers = all_stocks.head(8)

    return {
        "available": True, "nifty_move": nifty_move, "direction": direction,
        "sectors": sectors, "dominant_sectors": dominant,
        "stock_drivers": drivers, "all_stocks": all_stocks,
        "as_of": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "source": "Yahoo Finance constituent prices + Nifty Indices sector-weight snapshot (May 2026)",
        "weight_note": "Pressure is an attribution proxy, not an official real-time index-point contribution. Sector weights are a May 2026 snapshot.",
    }
