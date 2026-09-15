import html
import json
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import pandas_market_calendars as mcal
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

from menu import render_sidebar
from news_intelligence import enrich_news

st.set_page_config(page_title="MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
render_sidebar()

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = Path("data/latest.json")
WATCHLIST_FILE = Path("data/watchlist.json")
NSE_CALENDAR = mcal.get_calendar("NSE")
DEFAULT_WATCHLIST = ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "INFY.NS", "TCS.NS", "TATAMOTORS.NS", "ITC.NS"]
NIFTY50_MOVERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BHARTIARTL.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS", "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS", "MAXHEALTH.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]
NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en",
]

st.markdown("""
<style>
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem}
.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:12px}.title{font-family:Georgia,serif;font-size:2.35rem;font-weight:700}.sub{color:#8290a3;letter-spacing:.12em;text-transform:uppercase;font-size:.64rem;margin-top:7px}.time{text-align:right;color:#8290a3;font-size:.72rem}.pill{display:inline-block;border:1px solid #2b3a4d;background:#0d131d;border-radius:999px;padding:5px 10px;font-size:.67rem;font-weight:700}
.deck{display:flex;gap:9px;align-items:center;background:#0b1119;border:1px solid #202c3c;border-radius:12px;padding:8px 10px;margin:8px 0 15px;overflow-x:auto}.deck span{white-space:nowrap;font-size:.72rem;color:#cdd6e0;border-right:1px solid #263344;padding-right:10px}.deck .label{font-size:.61rem;color:#718096;text-transform:uppercase;letter-spacing:.1em}
.box,.change{background:linear-gradient(145deg,#0e151f,#0b1119);border:1px solid #202c3c;border-radius:14px;padding:14px 15px;height:100%;box-sizing:border-box}.label,.change-label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.big{font-family:Georgia,serif;font-size:1.55rem;font-weight:800;margin-top:5px}.muted{color:#8492a4;font-size:.72rem;line-height:1.4}.positive{color:#64d39a}.negative{color:#ff7b83}.neutral{color:#c5ced9}
.verdict{background:linear-gradient(145deg,#101925,#0c131d);border:1px solid #2a394c;border-radius:15px;padding:17px 18px;min-height:145px;height:auto;box-sizing:border-box;overflow:hidden}.verdict-value{font-family:Georgia,serif;font-size:1.85rem;font-weight:800;margin-top:5px;line-height:1.15;overflow-wrap:anywhere}.verdict-copy{color:#b7c1ce;font-size:.84rem;line-height:1.45;margin-top:7px;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.section{font-family:Georgia,serif;font-size:1.18rem;margin:16px 0 8px}.meta{float:right;font-family:Arial,sans-serif;color:#718096;font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;margin-top:5px}
.ticker{height:36px;line-height:18px;overflow:hidden;border:1px solid #202c3c;border-radius:11px;background:#0b1119;padding:9px;white-space:nowrap;margin:8px 0 16px;box-sizing:border-box}.track{display:inline-block;padding-left:100%;animation:scroll 150s linear infinite}@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.change{min-height:150px}.change-item{padding:7px 0;border-top:1px solid #1d2938;font-size:.76rem;line-height:1.35}.change-item:first-child{border-top:0}.change-value{font-size:.85rem;font-weight:800}.risk-row{padding:7px 0;border-top:1px solid #1d2938}.risk-row:first-child{border-top:0}
.evidence-wrap{border:1px solid #202c3c;border-radius:12px;overflow:hidden;background:#0b1119}.evidence-table{width:100%;border-collapse:collapse;font-size:.72rem;table-layout:fixed}.evidence-table th{text-align:left;padding:9px 10px;background:#171b25;color:#8492a4;font-weight:600;border-bottom:1px solid #263344}.evidence-table td{padding:9px 10px;border-bottom:1px solid #1d2938;color:#dce3ec;vertical-align:top}.evidence-table tr:last-child td{border-bottom:0}.status-supported{color:#64d39a;font-weight:700}.status-disputed{color:#ff7b83;font-weight:700}.status-insufficient{color:#ffd45c;font-weight:700}.status-dot{font-size:.9rem;margin-right:5px;vertical-align:-1px}.status-cell{white-space:nowrap;font-size:.67rem}.evidence-num{font-variant-numeric:tabular-nums;white-space:nowrap}.evidence-headline{line-height:1.35;word-wrap:break-word}.evidence-headline-title{font-size:.76rem;color:#e7edf5;font-weight:600;line-height:1.4}.evidence-gist{color:#91a0b2;font-size:.68rem;line-height:1.45;margin-top:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.evidence-point{display:block}.evidence-point::before{content:"• ";color:#64748b}
.movers-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.mover-card{background:#0b1119;border:1px solid #202c3c;border-radius:12px;padding:11px 13px}.mover-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-top:1px solid #1d2938;font-size:.76rem}.mover-row:first-child{border-top:0}.mover-symbol{font-weight:700;color:#dce3ec}.mover-pct{font-weight:800;font-variant-numeric:tabular-nums}.movers-note{color:#718096;font-size:.62rem;margin-top:7px}
.mover-link,.mover-link:visited,.mover-link:active{color:#f5f7fa!important;-webkit-text-fill-color:#f5f7fa!important;text-decoration:none!important;font-weight:700!important}.mover-link:hover{color:#f5f7fa!important;-webkit-text-fill-color:#f5f7fa!important;text-decoration:underline!important}
@media(max-width:800px){.movers-grid{grid-template-columns:1fr}}
</style>
""", unsafe_allow_html=True)

