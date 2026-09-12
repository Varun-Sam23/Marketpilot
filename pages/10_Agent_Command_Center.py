import html
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from menu import render_sidebar

st.set_page_config(page_title="Agent Command Center · MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
render_sidebar()

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = Path("data/latest.json")
report = {}
try:
    report = json.loads(DATA_FILE.read_text(encoding="utf-8"))
except Exception:
    report = {}

specialists = report.get("specialists", {}) or {}
agents = specialists.get("agents", {}) or {}
ai = report.get("ai_analysis", {}) or {}
now = datetime.now(IST)

st.markdown("""
<style>
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem}
.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}.title{font-family:Georgia,serif;font-size:2.25rem;font-weight:700}.sub{color:#8290a3;letter-spacing:.12em;text-transform:uppercase;font-size:.64rem;margin-top:7px}.time{text-align:right;color:#8290a3;font-size:.72rem}
.pill{display:inline-block;border:1px solid #2b3a4d;background:#0d131d;border-radius:999px;padding:5px 10px;font-size:.67rem;font-weight:700}
.hero-box,.agent,.chief,.metric{background:linear-gradient(145deg,#101925,#0b1119);border:1px solid #202c3c;border-radius:14px}.hero-box{padding:14px 16px;margin-bottom:15px}.metric{padding:12px 14px}.label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.value{font-family:Georgia,serif;font-size:1.45rem;font-weight:800;margin-top:5px}.muted{color:#8492a4;font-size:.72rem;line-height:1.45}.green{color:#64d39a}.red{color:#ff7b83}.yellow{color:#ffd45c}.blue{color:#8eb7ff}
.section{font-family:Georgia,serif;font-size:1.18rem;margin:18px 0 9px}.agent{padding:12px 13px;min-height:125px;margin-bottom:10px}.agent-head{display:flex;justify-content:space-between;align-items:center}.agent-name{font-size:.78rem;font-weight:700}.agent-status{font-size:.61rem;font-weight:800;letter-spacing:.08em}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}.ready{background:#64d39a}.error{background:#ff7b83}.pending{background:#ffd45c}.agent-detail{margin-top:9px;color:#8290a3;font-size:.66rem;line-height:1.45}.chief{padding:18px;margin-top:12px;border-color:#33445b}.chief-title{font-family:Georgia,serif;font-size:1.5rem;font-weight:800}.chief-thesis{font-size:.86rem;line-height:1.55;color:#c4ceda;margin-top:7px}.tag{display:inline-block;border:1px solid #29384b;background:#0c131d;border-radius:999px;padding:4px 8px;margin:4px 4px 0 0;font-size:.61rem;color:#aeb9c7}.list{padding:8px 0;border-top:1px solid #1d2938;font-size:.72rem;line-height:1.45}.list:first-child{border-top:0}
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="hero"><div><div class="title">◈ Agent Command Center</div><div class="sub">Specialist intelligence · evidence flow · chief adjudication</div></div><div class="time"><span class="pill">● ORCHESTRATION ONLINE</span><br>{now.strftime("%d %b %Y · %H:%M:%S IST")}</div></div>', unsafe_allow_html=True)

ready = specialists.get("ready_count", sum(v.get("status") == "READY" for v in agents.values()))
errors = specialists.get("error_count", sum(v.get("status") == "ERROR" for v in agents.values()))
count = specialists.get("agent_count", len(agents))
exec_mode = specialists.get("execution", "—")

cols = st.columns(4)
for col, label, value, cls in zip(cols, ["Specialist Agents", "READY", "ERROR", "Execution"], [count, ready, errors, exec_mode], ["blue", "green", "red", "yellow"]):
    col.markdown(f'<div class="metric"><div class="label">{label}</div><div class="value {cls}">{html.escape(str(value))}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section">SPECIALIST NETWORK</div>', unsafe_allow_html=True)
order = ["Market Agent","Technical Agent","News Agent","Institutional Agent","Options Agent","Intraday Agent","Sector Agent","Watchlist Agent","Risk Agent"]
rows = st.columns(3)
for i, name in enumerate(order):
    result = agents.get(name, {})
    status = str(result.get("status", "NOT RUN")).upper()
    cls = "ready" if status == "READY" else "error" if status == "ERROR" else "pending"
    status_cls = "green" if status == "READY" else "red" if status == "ERROR" else "yellow"
    elapsed = result.get("elapsed_ms")
    detail = "Agent did not return a result yet."
    if status == "READY":
        data = result.get("data", {}) or {}
        if name == "News Agent": detail = f'{len(data)} news intelligence records packaged.' if isinstance(data, list) else "News evidence packaged."
        elif name == "Sector Agent": detail = f'{len(data.get("sectors", []))} sector groups evaluated.'
        elif name == "Market Agent": detail = f'{len(data.get("snapshot", []))} market instruments in snapshot.'
        elif name == "Technical Agent": detail = f'Trend 20D: {data.get("trend_vs_20d", "UNKNOWN")} · RSI: {data.get("rsi14", "—")}'
        elif name == "Risk Agent": detail = f'{len(data.get("flags", []))} risk flags · sector participation {data.get("sector_positive_share", "—")}'
        elif name == "Institutional Agent": detail = "FII/DII evidence packaged from available source chain."
        elif name == "Options Agent": detail = f'PCR OI: {data.get("pcr_oi", "—")} · OI bias: {data.get("oi_bias", "—")}'
        elif name == "Intraday Agent": detail = "VWAP / opening range / momentum evidence packaged."
        elif name == "Watchlist Agent": detail = f'{len(data) if isinstance(data, list) else "Watchlist"} stock intelligence records.'
    elif status == "ERROR": detail = result.get("error", "Agent error")
    timing = f' · {float(elapsed):.0f} ms' if elapsed is not None else ''
    rows[i % 3].markdown(f'<div class="agent"><div class="agent-head"><span class="agent-name"><span class="dot {cls}"></span>{html.escape(name)}</span><span class="agent-status {status_cls}">{html.escape(status)}{timing}</span></div><div class="agent-detail">{html.escape(str(detail)[:240])}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section">CHIEF INTELLIGENCE</div>', unsafe_allow_html=True)
bias = ai.get("bias", report.get("verdict", "UNKNOWN")); confidence = ai.get("confidence", report.get("confidence", "—")); regime = ai.get("market_regime", "UNKNOWN"); score = ai.get("decision_score", report.get("decision", {}).get("score", "—")); thesis = ai.get("thesis", "Chief analysis unavailable for the current evidence pack.")
color = "green" if str(bias).upper() == "BULLISH" else "red" if str(bias).upper() == "BEARISH" else "yellow"
left,right = st.columns([1.6,1])
left.markdown(f'<div class="chief"><div class="label">FINAL ADJUDICATION</div><div class="chief-title {color}">{html.escape(str(bias))} · {html.escape(str(score))}/100</div><div class="chief-thesis">{html.escape(str(thesis))}</div><div style="margin-top:9px"><span class="tag">CONFIDENCE · {html.escape(str(confidence))}</span><span class="tag">REGIME · {html.escape(str(regime))}</span><span class="tag">EVIDENCE · {html.escape(str(ai.get("evidence_quality", "INSUFFICIENT")))}</span></div></div>', unsafe_allow_html=True)
right.markdown(f'<div class="chief"><div class="label">GOVERNANCE</div><div class="list">Conflicts reported: <b>{"YES" if ai.get("conflicts") else "NONE REPORTED"}</b></div><div class="list">No order execution: <b>ENFORCED</b></div><div class="list">AI status: <b>{html.escape(str(ai.get("status", "NOT RUN")))}</b></div><div class="list">Specialists: <b>{ready}/{count} ready</b></div></div>', unsafe_allow_html=True)

bull,base,bear = st.columns(3)
for col, title, key, cls in [(bull,"BULL CASE","bull_case","green"),(base,"BASE CASE","base_case","blue"),(bear,"BEAR CASE","bear_case","red")]:
    col.markdown(f'<div class="hero-box"><div class="label">{title}</div><div class="muted" style="margin-top:7px">{html.escape(str(ai.get(key, "Unavailable")))}</div></div>', unsafe_allow_html=True)

conflicts = ai.get("conflicts", []) or []
risks = ai.get("risks", []) or []
drivers = ai.get("drivers", []) or []
if conflicts or risks or drivers:
    st.markdown('<div class="section">INTELLIGENCE LEDGER</div>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    for col, title, values, cls in [(a,"CONFLICTS",conflicts,"yellow"),(b,"KEY RISKS",risks,"red"),(c,"DRIVERS",drivers,"green")]:
        body=''.join(f'<div class="list">{html.escape(str(v))}</div>' for v in values[:6]) or '<div class="muted">None reported.</div>'
        col.markdown(f'<div class="hero-box"><div class="label {cls}">{title}</div>{body}</div>', unsafe_allow_html=True)

st.caption("MarketPilot Agent Command Center · Specialist calculations remain deterministic; AI interprets supplied evidence only. Not investment advice.")
