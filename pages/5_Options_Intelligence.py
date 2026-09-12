import pandas as pd
import streamlit as st

from options_intelligence import analyse_option_chain, fetch_option_chain
from menu import render_sidebar

st.set_page_config(page_title="MarketPilot · Options Intelligence", page_icon="⛓️", layout="wide")
render_sidebar()

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 28%),var(--bg)}
.main .block-container{max-width:1460px;padding:1.1rem 2.1rem 4rem}
.oi-kicker{font-size:.63rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gold)}
.oi-title{font-family:Georgia,"Times New Roman",serif;font-size:2.5rem;color:var(--ink);margin:.25rem 0}.oi-sub{color:var(--muted);font-size:.8rem;line-height:1.5;max-width:950px}
.oi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:.65rem;margin:1.2rem 0}.oi-card{border:1px solid var(--line);border-radius:16px;padding:.8rem 1rem;background:rgba(255,255,255,.018)}.oi-label{font-size:.56rem;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}.oi-value{font-family:Georgia,serif;font-size:1.3rem;color:var(--ink);margin-top:.2rem}
.oi-hero{border:1px solid var(--line);border-radius:19px;padding:1rem 1.1rem;background:linear-gradient(115deg,rgba(201,168,91,.09),rgba(255,255,255,.018));margin:1rem 0}.oi-note{color:#c5cbd3;font-size:.76rem;line-height:1.55}.oi-source{border:1px solid var(--line);border-radius:14px;padding:.75rem 1rem;color:var(--muted);font-size:.7rem;background:rgba(255,255,255,.014);margin:1rem 0}
@media(max-width:1000px){.oi-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){.oi-grid{grid-template-columns:1fr 1fr}.main .block-container{padding:.6rem .8rem 3rem}}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="oi-kicker">MarketPilot derivatives research</div><div class="oi-title">Options Intelligence</div><div class="oi-sub">Strike-level open interest, OI change, volume, IV, PCR and max-pain context for NIFTY and BANKNIFTY. This is an analytical layer — not an options trade signal.</div>', unsafe_allow_html=True)

symbol = st.selectbox("Underlying", ["NIFTY", "BANKNIFTY"], index=0)

with st.spinner(f"Fetching {symbol} option-chain data…"):
    result = fetch_option_chain(symbol)
analysis = analyse_option_chain(result)

if not analysis.get("available"):
    st.warning(analysis.get("message", "Option-chain data is currently unavailable."))
    st.caption("MarketPilot does not fabricate option-chain values. If the upstream feed is blocked or unavailable, the page stays empty.")
    st.stop()

spot = analysis["spot"]
pcr = analysis["pcr_oi"]
vol_pcr = analysis["pcr_volume"]
max_pain = analysis["max_pain"]

st.markdown(f'<div class="oi-grid"><div class="oi-card"><div class="oi-label">Spot</div><div class="oi-value">{spot:,.2f}</div></div><div class="oi-card"><div class="oi-label">Nearest expiry</div><div class="oi-value">{analysis["expiry"]}</div></div><div class="oi-card"><div class="oi-label">ATM strike</div><div class="oi-value">{analysis["atm"]:,.0f}</div></div><div class="oi-card"><div class="oi-label">PCR · OI</div><div class="oi-value">{pcr:.2f}</div></div><div class="oi-card"><div class="oi-label">Max pain</div><div class="oi-value">{max_pain:,.0f}</div></div><div class="oi-card"><div class="oi-label">OI structure</div><div class="oi-value">{analysis["oi_bias"]}</div></div></div>', unsafe_allow_html=True)

st.markdown(f'<div class="oi-hero"><div class="oi-kicker">Market structure read</div><div style="font-family:Georgia,serif;font-size:1.35rem;color:var(--ink);margin:.25rem 0">{analysis["oi_bias"]} · PCR {pcr:.2f}</div><div class="oi-note">Put/call open-interest ratio is a positioning measure, not a directional certainty. Max pain is an expiry-oriented statistic, not a price target. Use these alongside price structure, volatility, volume and verified catalysts.</div></div>', unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.markdown('<div class="oi-kicker">Largest call OI · potential overhead concentration</div>', unsafe_allow_html=True)
    call_df = analysis["call_resistance"].rename(columns={"strike":"Strike","ce_oi":"Call OI","ce_chg_oi":"Call OI Change"}).copy()
    st.dataframe(call_df, use_container_width=True, hide_index=True)
with right:
    st.markdown('<div class="oi-kicker">Largest put OI · potential downside concentration</div>', unsafe_allow_html=True)
    put_df = analysis["put_support"].rename(columns={"strike":"Strike","pe_oi":"Put OI","pe_chg_oi":"Put OI Change"}).copy()
    st.dataframe(put_df, use_container_width=True, hide_index=True)

st.markdown('<div class="oi-kicker" style="margin-top:1.5rem">ATM option chain</div>', unsafe_allow_html=True)
window = analysis["atm_window"].copy()
window["Strike"] = window["strike"].map(lambda x: f"{x:,.0f}")
window["ATM"] = window["ATM"].map(lambda x: "●" if x else "")
window = window[["ATM","Strike","ce_oi","ce_chg_oi","ce_volume","ce_iv","ce_ltp","pe_ltp","pe_iv","pe_volume","pe_chg_oi","pe_oi"]]
window.columns = ["ATM","Strike","CE OI","CE OI Δ","CE Vol","CE IV","CE LTP","PE LTP","PE IV","PE Vol","PE OI Δ","PE OI"]
st.dataframe(window, use_container_width=True, hide_index=True)

raw = analysis["raw"]
chart = raw[["strike","ce_oi","pe_oi"]].copy().set_index("strike")
chart.columns = ["Call OI", "Put OI"]
st.markdown('<div class="oi-kicker" style="margin-top:1.5rem">Open-interest landscape</div>', unsafe_allow_html=True)
st.line_chart(chart)

st.markdown(f'<div class="oi-source"><b>Source:</b> {analysis["source"]} · {analysis["source_url"]}<br>MarketPilot exposes provenance because option-chain feeds can be blocked or delayed. The public fallback is unofficial and should be independently verified before any trading decision.</div>', unsafe_allow_html=True)
st.caption(f"Volume PCR: {vol_pcr:.2f} · Research only. Option-chain values can change rapidly during market hours. No trade recommendation is generated from PCR, max pain or OI concentration alone.")
