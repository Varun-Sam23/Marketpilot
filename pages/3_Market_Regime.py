import pandas as pd
import streamlit as st
import yfinance as yf

from market_regime import classify_regime
from menu import render_sidebar

st.set_page_config(page_title="MarketPilot · Market Regime", page_icon="◈", layout="wide")
render_sidebar()

@st.cache_data(ttl=300, show_spinner=False)
def nifty_snapshot():
    try:
        h = yf.Ticker("^NSEI").history(period="6mo", interval="1d", auto_adjust=False)
        if len(h) < 55:
            return {}, 0.0
        c = h["Close"]
        last = float(c.iloc[-1])
        sma20 = float(c.tail(20).mean())
        sma50 = float(c.tail(50).mean())
        ret20 = (last / float(c.iloc[-21]) - 1) * 100
        high20 = float(h["High"].tail(20).max())
        low20 = float(h["Low"].tail(20).min())
        rng = high20 - low20
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        rsi = (100 - 100 / (1 + rs)).iloc[-1]
        v = yf.Ticker("^INDIAVIX").history(period="10d", interval="1d", auto_adjust=False)
        vix_change = 0.0
        if len(v) >= 2:
            vix_change = (float(v["Close"].iloc[-1]) / float(v["Close"].iloc[-2]) - 1) * 100
        return {
            "NIFTY close": round(last, 2), "20D SMA": round(sma20, 2), "50D SMA": round(sma50, 2),
            "20D return %": round(ret20, 2), "RSI14": round(float(rsi), 2) if pd.notna(rsi) else None,
            "20D high": round(high20, 2), "20D low": round(low20, 2),
            "range_position_%": round((last - low20) / rng * 100, 1) if rng else 50.0,
        }, round(vix_change, 2)
    except Exception:
        return {}, 0.0

levels, vix_change = nifty_snapshot()
result = classify_regime(levels, vix_change)

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 28%),var(--bg)}
.main .block-container{max-width:1460px;padding:1.1rem 2.1rem 4rem}
.mr-k{font-size:.63rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gold)}
.mr-title{font-family:Georgia,serif;font-size:2.5rem;color:var(--ink);margin:.25rem 0}.mr-sub{color:var(--muted);font-size:.8rem;line-height:1.5;max-width:900px}
.mr-grid{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:.7rem;margin:1.2rem 0}.mr-card{border:1px solid var(--line);border-radius:16px;padding:1rem;background:rgba(255,255,255,.018)}.mr-label{font-size:.57rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.mr-value{font-family:Georgia,serif;font-size:1.45rem;color:var(--ink);margin-top:.2rem}.mr-hero{border:1px solid var(--line);border-radius:21px;padding:1.2rem;background:linear-gradient(115deg,rgba(201,168,91,.11),rgba(255,255,255,.018));margin:1rem 0}.mr-regime{font-family:Georgia,serif;font-size:2rem;color:var(--ink)}.mr-score{font-family:Georgia,serif;font-size:3rem;color:var(--ink)}.mr-text{font-size:.8rem;color:#c5cbd3;line-height:1.6}.mr-list{border:1px solid var(--line);border-radius:16px;padding:1rem;background:rgba(255,255,255,.018);margin-top:.8rem}.mr-note{font-size:.7rem;color:#687280;border-top:1px solid var(--line);margin-top:2rem;padding-top:.8rem}
@media(max-width:900px){.main .block-container{padding:.8rem .9rem 3rem}.mr-grid{grid-template-columns:1fr 1fr}.mr-regime{font-size:1.6rem}}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mr-k">MarketPilot adaptive layer</div><div class="mr-title">Market Regime</div><div class="mr-sub">A technical-structure classifier designed to tell the rest of MarketPilot what kind of market it is operating in. It combines NIFTY trend alignment, 20-day momentum, range position, RSI and India VIX change.</div>', unsafe_allow_html=True)

if not levels:
    st.warning("Market structure data is temporarily unavailable. The regime engine will populate when the public market feed returns enough history.")
    st.stop()

st.markdown(f'''<div class="mr-hero"><div style="display:flex;justify-content:space-between;gap:1rem;align-items:center"><div><div class="mr-k">Current classification</div><div class="mr-regime">{result["regime"]}</div><div class="mr-text">Confidence · {result["confidence"]} · Trend · {result["trend"]} · Volatility · {result["volatility"]}</div></div><div class="mr-score">{result["score"]}<span style="font-size:1rem;color:var(--muted)"> / 100</span></div></div><div style="height:1px;background:var(--line);margin:1rem 0"></div><div class="mr-text"><b>Adaptive playbook:</b> {result["playbook"]}</div></div>''', unsafe_allow_html=True)

m = result["metrics"]
st.markdown(f'''<div class="mr-grid"><div class="mr-card"><div class="mr-label">NIFTY</div><div class="mr-value">{levels["NIFTY close"]:,.2f}</div><div class="mr-text">20D SMA {levels["20D SMA"]:,.2f} · 50D SMA {levels["50D SMA"]:,.2f}</div></div><div class="mr-card"><div class="mr-label">20D momentum</div><div class="mr-value">{m["20D return %"]:+.2f}%</div></div><div class="mr-card"><div class="mr-label">Range position</div><div class="mr-value">{m["range position %"]:.1f}%</div></div><div class="mr-card"><div class="mr-label">India VIX change</div><div class="mr-value">{m["VIX change %"]:+.2f}%</div></div></div>''', unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.markdown('<div class="mr-k">Evidence ledger</div>', unsafe_allow_html=True)
    st.markdown('<div class="mr-list">' + ''.join(f'<div class="mr-text">• {r}</div>' for r in result["reasons"]) + '</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="mr-k">Market structure</div>', unsafe_allow_html=True)
    structure = pd.DataFrame([{
        "NIFTY": levels["NIFTY close"], "20D SMA": levels["20D SMA"], "50D SMA": levels["50D SMA"],
        "20D High": levels["20D high"], "20D Low": levels["20D low"], "RSI14": levels["RSI14"],
    }])
    st.dataframe(structure, use_container_width=True, hide_index=True)

st.markdown('<div class="mr-note">The regime is a rule-based research classification, not a forecast. A changing regime should lower confidence in signals built for the previous regime.</div>', unsafe_allow_html=True)
