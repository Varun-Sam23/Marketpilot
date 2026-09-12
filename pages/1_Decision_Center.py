import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_FILE = Path("data/latest.json")

st.set_page_config(page_title="MarketPilot · Decision Center", page_icon="🎯", layout="wide")

st.markdown(r'''
<style>
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 10% 0%,rgba(62,96,120,.15),transparent 28%),#11151b}
.main .block-container{max-width:1380px;padding:2rem 2.2rem 4rem}
.dc-eyebrow{font-size:.68rem;letter-spacing:.18em;text-transform:uppercase;color:#9ca7b2;margin-bottom:.35rem}
.dc-title{font-family:Georgia,"Times New Roman",serif;font-size:2.7rem;line-height:1;color:#f5f1e8;font-weight:600;letter-spacing:-.035em}
.dc-sub{color:#aeb7bf;font-size:.88rem;margin:.55rem 0 1.3rem}
.dc-card{background:rgba(25,31,39,.82);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:1.1rem 1.2rem;box-shadow:0 14px 45px rgba(0,0,0,.18)}
.dc-label{font-size:.67rem;letter-spacing:.13em;text-transform:uppercase;color:#8e9aa5}
.dc-value{font-family:Georgia,"Times New Roman",serif;font-size:2rem;color:#f5f1e8;margin-top:.2rem}
.dc-note{color:#9fa9b3;font-size:.78rem;margin-top:.3rem;line-height:1.4}
.dc-score{font-family:Georgia,"Times New Roman",serif;font-size:5.1rem;line-height:1;color:#f5f1e8}
.dc-score-denom{color:#7d8790;font-size:1rem;margin-left:.25rem}
.dc-meter{height:11px;border-radius:99px;background:linear-gradient(90deg,#9a4f47 0%,#9a4f47 35%,#9a7b35 35%,#9a7b35 65%,#2f6f52 65%,#2f6f52 100%);overflow:hidden;position:relative}
.dc-meter-marker{position:relative;height:100%;width:3px;background:#f5f1e8;box-shadow:0 0 0 2px rgba(245,241,232,.14)}
.dc-regime{display:inline-block;margin-top:.75rem;padding:.34rem .68rem;border-radius:999px;border:1px solid rgba(255,255,255,.12);color:#e6e0d3;background:rgba(255,255,255,.04);font-size:.72rem;letter-spacing:.1em;text-transform:uppercase}
.dc-section{font-family:Georgia,"Times New Roman",serif;font-size:1.65rem;color:#f5f1e8;margin:1.55rem 0 .7rem}
.dc-case{min-height:155px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:1rem}
.dc-case h4{font-family:Georgia,"Times New Roman",serif;color:#f5f1e8;margin:.1rem 0 .45rem}
.dc-case p{color:#b9c0c6;line-height:1.5;margin:0}
.dc-bull{border-top:2px solid #2f6f52}.dc-base{border-top:2px solid #9a7b35}.dc-bear{border-top:2px solid #a44f49}
.dc-list{color:#bcc4ca;line-height:1.55}
.dc-foot{border-top:1px solid rgba(255,255,255,.08);margin-top:2.2rem;padding-top:.85rem;color:#7f8993;font-size:.72rem}
</style>
''', unsafe_allow_html=True)


def load():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def score_color(score):
    if score >= 65:
        return "#5f9b78"
    if score <= 35:
        return "#c16b63"
    return "#b69a55"


def safe(value):
    return html.escape(str(value or ""))


report = load()
decision = report.get("decision", {})
ai = report.get("ai_analysis", {})
score = float(decision.get("score", 50) or 50)
score = max(0, min(100, score))
bias = decision.get("bias", report.get("verdict", "WAIT"))
regime = decision.get("regime", "UNKNOWN")
confidence = decision.get("confidence", "LOW")
marker = max(0, min(100, score))

st.markdown('<div class="dc-eyebrow">MarketPilot · decision layer</div>', unsafe_allow_html=True)
st.markdown('<div class="dc-title">Decision Center</div>', unsafe_allow_html=True)
st.markdown('<div class="dc-sub">A transparent evidence score sits beneath the AI thesis — so you can see what is driving the morning view.</div>', unsafe_allow_html=True)

left, right = st.columns([1.15, 2.0])
with left:
    st.markdown('<div class="dc-card">', unsafe_allow_html=True)
    st.markdown('<div class="dc-label">Day setup score</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dc-score">{score:.0f}<span class="dc-score-denom">/100</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:{score_color(score)};font-weight:700;font-size:.86rem;margin:.45rem 0 .7rem">{safe(bias)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dc-meter"><div style="margin-left:{marker}%;height:100%;position:absolute"><div class="dc-meter-marker"></div></div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dc-regime">{safe(regime)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dc-note">Confidence: <b style="color:#e7e2d8">{safe(confidence)}</b><br>{safe(decision.get("methodology", ""))}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    a, b, c = st.columns(3)
    a.metric("AI bias", ai.get("bias", "WAIT"))
    b.metric("AI confidence", ai.get("confidence", "N/A"))
    c.metric("Rule bias", report.get("verdict", "WAIT"))

    st.markdown('<div class="dc-card" style="margin-top:.9rem">', unsafe_allow_html=True)
    st.markdown('<div class="dc-label">Core thesis</div>', unsafe_allow_html=True)
    thesis = ai.get("thesis") or report.get("summary") or "No thesis available yet."
    st.markdown(f'<div style="font-family:Georgia,serif;font-size:1.2rem;line-height:1.5;color:#f2eee5;margin-top:.35rem">{safe(thesis)}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="dc-section">Scenario map</div>', unsafe_allow_html=True)
x, y, z = st.columns(3)
with x:
    st.markdown(f'<div class="dc-card dc-case dc-bull"><h4>🟢 Bull case</h4><p>{safe(ai.get("bull_case") or decision.get("bull_trigger"))}</p></div>', unsafe_allow_html=True)
with y:
    st.markdown(f'<div class="dc-card dc-case dc-base"><h4>🟡 Base case</h4><p>{safe(ai.get("base_case") or "Remain neutral until price action confirms a stronger direction.")}</p></div>', unsafe_allow_html=True)
with z:
    st.markdown(f'<div class="dc-card dc-case dc-bear"><h4>🔴 Bear case</h4><p>{safe(ai.get("bear_case") or decision.get("bear_trigger"))}</p></div>', unsafe_allow_html=True)

st.markdown('<div class="dc-section">What is driving the score?</div>', unsafe_allow_html=True)
positive = decision.get("positive_factors", 0)
negative = decision.get("negative_factors", 0)
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f'<div class="dc-card"><div class="dc-label">Positive evidence</div><div class="dc-value">{positive}</div><div class="dc-note">Signals currently supporting the setup.</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="dc-card"><div class="dc-label">Negative evidence</div><div class="dc-value">{negative}</div><div class="dc-note">Signals currently working against the setup.</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="dc-card"><div class="dc-label">Invalidation</div><div class="dc-note" style="font-size:.88rem;color:#d6d9dc;margin-top:.55rem">{safe(ai.get("invalidation") or decision.get("invalidation"))}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="dc-section">Evidence ledger</div>', unsafe_allow_html=True)
factors = decision.get("evidence", [])
if factors:
    rows = [{"Evidence": f"• {item}"} for item in factors]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("The evidence ledger will populate on the next trading-day analysis run.")

levels = report.get("levels", {})
if levels:
    st.markdown('<div class="dc-section">Market structure</div>', unsafe_allow_html=True)
    cols = ["NIFTY close", "Previous close", "5D return %", "20D return %", "20D SMA", "50D SMA", "20D high", "20D low", "RSI14"]
    present = {k: levels.get(k) for k in cols if k in levels}
    st.dataframe(pd.DataFrame([present]), use_container_width=True, hide_index=True)

st.markdown('<div class="dc-section">Operating rule</div>', unsafe_allow_html=True)
st.markdown('<div class="dc-card"><div class="dc-note" style="font-size:.9rem">MarketPilot is a research and decision-support system. The score is a transparent evidence-weighting framework, not a probability, trade instruction, or guarantee. The regular NSE equity session opens at 09:15 IST after the pre-open session.</div></div>', unsafe_allow_html=True)
st.markdown('<div class="dc-foot">Free/public feeds can be delayed, incomplete or temporarily unavailable. Use the original sources and your own judgement before acting.</div>', unsafe_allow_html=True)
