import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_FILE = Path("data/latest.json")

st.set_page_config(page_title="Decision Center · MarketPilot", page_icon="🎯", layout="wide")


def load_report():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clamp(value, low=0, high=100):
    return max(low, min(high, int(round(value))))


def decision_score(report):
    levels = report.get("levels", {})
    sectors = report.get("sectors", [])
    signals = report.get("signals", [])
    score = 50
    evidence = []

    if levels:
        if levels.get("NIFTY close", 0) > levels.get("20D SMA", float("inf")):
            score += 10
            evidence.append(("+10", "NIFTY above 20-day average"))
        elif levels.get("NIFTY close") is not None:
            score -= 10
            evidence.append(("-10", "NIFTY below 20-day average"))

        if levels.get("20D return %", 0) > 0:
            score += 8
            evidence.append(("+8", "Positive 20-day momentum"))
        else:
            score -= 8
            evidence.append(("-8", "Negative 20-day momentum"))

        rsi = levels.get("RSI14")
        if rsi is not None:
            if rsi >= 60:
                score += 7
                evidence.append(("+7", f"RSI momentum is constructive ({rsi:.0f})"))
            elif rsi <= 40:
                score -= 7
                evidence.append(("-7", f"RSI momentum is weak ({rsi:.0f})"))

    if sectors:
        avg = sum(float(s.get("avg_change_pct", 0)) for s in sectors) / len(sectors)
        if avg > 0.5:
            score += 8
            evidence.append(("+8", "Sector pulse is broadly positive"))
        elif avg < -0.5:
            score -= 8
            evidence.append(("-8", "Sector pulse is broadly negative"))

    score = clamp(score)
    if score >= 68:
        bias = "BULLISH"
        regime = "Positive trend"
    elif score >= 56:
        bias = "BULLISH LEAN"
        regime = "Constructive / mixed"
    elif score <= 32:
        bias = "BEARISH"
        regime = "Negative trend"
    elif score <= 44:
        bias = "BEARISH LEAN"
        regime = "Weak / mixed"
    else:
        bias = "NEUTRAL"
        regime = "Mixed / range"

    confidence = "HIGH" if abs(score - 50) >= 25 else "MEDIUM" if abs(score - 50) >= 12 else "LOW"
    return score, bias, regime, confidence, evidence


report = load_report()
ai = report.get("ai_analysis", {})
score, bias, regime, confidence, evidence = decision_score(report)

st.markdown("# 🎯 Decision Center")
st.caption("Evidence-first market framework • no order execution")

if report.get("market_status") == "MARKET CLOSED":
    st.info("Market is currently closed. The Decision Center is showing the latest stored evidence and will refresh with the next trading-day report.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Day Setup", f"{score}/100")
c2.metric("Framework Bias", bias)
c3.metric("Regime", regime)
c4.metric("Confidence", confidence)

st.progress(score / 100)

st.markdown("## Morning Thesis")
thesis = ai.get("thesis") or report.get("summary") or "No thesis is available yet."
st.info(thesis)

x, y, z = st.columns(3)
with x:
    st.markdown("### 🟢 Bull case")
    st.write(ai.get("bull_case") or "Not available")
with y:
    st.markdown("### 🟡 Base case")
    st.write(ai.get("base_case") or "Not available")
with z:
    st.markdown("### 🔴 Bear case")
    st.write(ai.get("bear_case") or "Not available")

st.markdown("## Evidence Ledger")
if evidence:
    edf = pd.DataFrame(evidence, columns=["Weight", "Evidence"])
    st.dataframe(edf, use_container_width=True, hide_index=True)
else:
    st.caption("Evidence will populate after the next trading-day analysis.")

st.markdown("## Key Levels & Invalidation")
levels = ai.get("key_levels", [])
if levels:
    for level in levels:
        st.write("•", level)
else:
    stored = report.get("levels", {})
    if stored:
        st.dataframe(pd.DataFrame([stored]), use_container_width=True, hide_index=True)
    else:
        st.caption("No key levels are stored yet.")

if ai.get("invalidation"):
    st.warning(ai.get("invalidation"))

st.markdown("## Drivers & Risks")
d1, d2 = st.columns(2)
with d1:
    for item in ai.get("drivers", []):
        st.write("•", item)
with d2:
    for item in ai.get("risks", []):
        st.write("•", item)

st.caption("The score is a transparent evidence-weighting framework, not a probability or a trading recommendation.")
