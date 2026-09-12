import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

from intraday_intelligence import fetch_intraday

st.set_page_config(page_title="Intraday Market Structure | MarketPilot", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.stApp { background:#070b12; color:#e7edf5; }
.block-container { padding-top:1.5rem; max-width:1500px; }
.mp-title { font-size:2rem; font-weight:800; letter-spacing:-.03em; }
.mp-sub { color:#8d9aab; margin-bottom:1.2rem; }
.card { background:#0d131d; border:1px solid #202b3a; border-radius:14px; padding:16px; min-height:105px; }
.label { color:#8290a3; font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }
.value { font-size:1.55rem; font-weight:750; margin-top:5px; }
.good { color:#58d68d; } .bad { color:#ff6b6b; } .neutral { color:#f4c95d; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mp-title">⚡ Intraday Market Structure</div>', unsafe_allow_html=True)
st.markdown('<div class="mp-sub">NIFTY 5-minute structure · VWAP · Opening Range · Momentum · Volume · Breadth · Support/Resistance</div>', unsafe_allow_html=True)

if st.button("↻ Refresh intraday data"):
    st.cache_data.clear()

# Do not confuse a normal exchange closure with a broken market-data feed.
# NSE equities do not trade on Saturdays, Sundays or declared exchange holidays.
IST = ZoneInfo("Asia/Kolkata")
now = datetime.now(IST)
nse = mcal.get_calendar("NSE")
is_trading_day = not nse.schedule(start_date=now.date(), end_date=now.date()).empty

if not is_trading_day:
    st.info(
        f"🏁 **NSE market is closed today — {now.strftime('%A, %d %B %Y')}.** "
        "Intraday 5-minute data is therefore not expected. MarketPilot will resume intraday analysis on the next NSE trading session."
    )
    st.caption("Market status is determined from the NSE trading calendar; this is not a market-data feed error.")
    st.stop()

data = fetch_intraday()

if not data.get("available"):
    st.warning(data.get("message", "Intraday data unavailable."))
    st.caption(f"Source: {data.get('source', 'Unknown')}. MarketPilot does not fabricate missing intraday values.")
    st.stop()

bias = data["bias"]
cls = "good" if bias == "BULLISH" else "bad" if bias == "BEARISH" else "neutral"

st.markdown(f"**INTRADAY STRENGTH: <span class='{cls}'>{bias}</span>** · Score {data['score']}/100 · Confidence {data['confidence']} · As of {data['as_of']}", unsafe_allow_html=True)

cols = st.columns(6)
metrics = [
    ("NIFTY", f"{data['last']:,.2f}"),
    ("SESSION CHANGE", f"{data['session_change_pct']:.2f}%" if data.get("session_change_pct") is not None else "—"),
    ("VWAP", f"{data['vwap']:,.2f}" if data.get("vwap") is not None else "—"),
    ("OPENING RANGE", data["opening_range_state"]),
    ("15M MOMENTUM", f"{data['momentum_15m_pct']:.2f}%"),
    ("VOLUME", f"{data['volume_ratio']:.2f}x" if data.get("volume_ratio") is not None else "—"),
]
for col, (label, value) in zip(cols, metrics):
    col.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)

st.markdown("### Market structure")
a, b, c = st.columns(3)
a.metric("Opening Range High", f"{data['opening_range_high']:,.2f}" if data.get("opening_range_high") else "—")
a.metric("Opening Range Low", f"{data['opening_range_low']:,.2f}" if data.get("opening_range_low") else "—")
b.metric("Recent Resistance", f"{data['levels'].get('recent_resistance', 0):,.2f}")
b.metric("Recent Support", f"{data['levels'].get('recent_support', 0):,.2f}")
c.metric("Session High", f"{data['levels'].get('session_high', 0):,.2f}")
c.metric("Session Low", f"{data['levels'].get('session_low', 0):,.2f}")

st.markdown("### Breadth")
br = data["breadth"]
q1, q2, q3, q4 = st.columns(4)
q1.metric("Advancers", br["advancers"])
q2.metric("Decliners", br["decliners"])
q3.metric("Unchanged", br["unchanged"])
q4.metric("Advance / Decline", f"{br['breadth_ratio']:.2f}")

st.markdown("### Evidence ledger")
for reason in data["reasons"]:
    st.markdown(f"• {reason}")

if br["rows"]:
    st.markdown("### Watchlist breadth detail")
    st.dataframe(br["rows"], use_container_width=True, hide_index=True)

st.markdown(f"**Source:** {data['source']}  ")
st.caption("Intraday data may be delayed or incomplete. VWAP, opening range and volume signals are descriptive decision-support metrics, not guaranteed trade signals. Use broker-grade real-time data for execution.")
