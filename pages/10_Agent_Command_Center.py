import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from menu import render_sidebar

st.set_page_config(page_title="Agent Command Center · MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
render_sidebar()

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = Path("data/latest.json")
HISTORY_FILE = Path("data/history.json")
AGENT_ORDER = [
    "Market Agent", "Technical Agent", "News Agent", "Institutional Agent",
    "Options Agent", "Intraday Agent", "Sector Agent", "Watchlist Agent", "Risk Agent",
]
AGENT_ROLE = {
    "Market Agent": "Index and global market snapshot",
    "Technical Agent": "Trend, momentum and market structure",
    "News Agent": "Article evidence and catalyst intelligence",
    "Institutional Agent": "FII / DII positioning evidence",
    "Options Agent": "NIFTY options positioning and OI",
    "Intraday Agent": "VWAP, opening range and volume",
    "Sector Agent": "Sector leadership and rotation",
    "Watchlist Agent": "Stock-level intelligence and ranking",
    "Risk Agent": "Conflicts, volatility and risk flags",
}

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

report = load(DATA_FILE, {})
specialists = report.get("specialists", {}) or {}
agents = specialists.get("agents", {}) or {}
ai = report.get("ai_analysis", {}) or {}
history = load(HISTORY_FILE, [])
now = datetime.now(IST)
market_status = str(report.get("market_status", "UNKNOWN"))
closed = "CLOSED" in market_status.upper()

last_run = None
if isinstance(history, list):
    for item in reversed(history):
        if item.get("date_ist") != now.strftime("%Y-%m-%d"):
            last_run = item
            break

st.markdown("""
<style>
.stApp{background:#070b12;color:#e7edf5}.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem}
.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}.title{font-family:Georgia,serif;font-size:2.25rem;font-weight:700}.sub{color:#8290a3;letter-spacing:.12em;text-transform:uppercase;font-size:.64rem;margin-top:7px}.time{text-align:right;color:#8290a3;font-size:.72rem}
.pill{display:inline-block;border:1px solid #2b3a4d;background:#0d131d;border-radius:999px;padding:5px 10px;font-size:.67rem;font-weight:700}
.banner,.agent,.chief,.metric,.ledger,.debate{background:linear-gradient(145deg,#101925,#0b1119);border:1px solid #202c3c;border-radius:14px}.banner{padding:13px 16px;margin-bottom:15px}.metric{padding:12px 14px}.label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.value{font-family:Georgia,serif;font-size:1.45rem;font-weight:800;margin-top:5px}.muted{color:#8492a4;font-size:.72rem;line-height:1.45}.green{color:#64d39a}.red{color:#ff7b83}.yellow{color:#ffd45c}.blue{color:#8eb7ff}
.section{font-family:Georgia,serif;font-size:1.18rem;margin:18px 0 9px}.agent{padding:12px 13px;min-height:122px;margin-bottom:10px}.agent-head{display:flex;justify-content:space-between;align-items:center}.agent-name{font-size:.78rem;font-weight:700}.agent-status{font-size:.61rem;font-weight:800;letter-spacing:.08em}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}.ready{background:#64d39a}.error{background:#ff7b83}.pending{background:#ffd45c}.agent-detail{margin-top:9px;color:#8290a3;font-size:.66rem;line-height:1.45}.chief{padding:18px;margin-top:12px;border-color:#33445b}.chief-title{font-family:Georgia,serif;font-size:1.5rem;font-weight:800}.chief-thesis{font-size:.86rem;line-height:1.55;color:#c4ceda;margin-top:7px}.tag{display:inline-block;border:1px solid #29384b;background:#0c131d;border-radius:999px;padding:4px 8px;margin:4px 4px 0 0;font-size:.61rem;color:#aeb9c7}.list{padding:8px 0;border-top:1px solid #1d2938;font-size:.72rem;line-height:1.45}.list:first-child{border-top:0}
.debate{padding:14px 15px;margin-bottom:10px;border-color:#39475b}.debate-route{font-size:.72rem;font-weight:800}.arrow{color:#ffd45c;padding:0 7px}.debate-issue{font-size:.74rem;color:#c4ceda;line-height:1.5;margin-top:8px}.debate-meta{font-size:.61rem;color:#7f8da0;margin-top:8px}.severity-high{color:#ff7b83}.severity-medium{color:#ffd45c}.severity-low{color:#8eb7ff}
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="hero"><div><div class="title">◈ Agent Command Center</div><div class="sub">Specialist intelligence · evidence flow · chief adjudication</div></div><div class="time"><span class="pill">● ORCHESTRATION ONLINE</span><br>{now.strftime("%d %b %Y · %H:%M:%S IST")}</div></div>', unsafe_allow_html=True)

if closed:
    st.markdown('<div class="banner"><div class="label">CURRENT RUN STATE</div><div style="font-weight:800;margin-top:5px" class="yellow">MARKET CLOSED · AGENTS ON STANDBY</div><div class="muted" style="margin-top:4px">No specialist run is fabricated while the NSE cash market is closed. The network is registered and ready for the next valid market session.</div></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="banner"><div class="label">CURRENT RUN STATE</div><div style="font-weight:800;margin-top:5px" class="green">{html.escape(market_status)} · AGENT NETWORK ACTIVE</div><div class="muted" style="margin-top:4px">Agent cards below reflect the latest completed evidence run.</div></div>', unsafe_allow_html=True)

executed = [a for a in AGENT_ORDER if agents.get(a, {}).get("status") == "READY"]
errors = [a for a in AGENT_ORDER if agents.get(a, {}).get("status") == "ERROR"]
run_state = specialists.get("execution", "NO CURRENT RUN") if specialists else ("STANDBY" if closed else "NO CURRENT RUN")

cols = st.columns(4)
metrics = [("Registered Agents", len(AGENT_ORDER), "blue"), ("READY · LAST RUN", len(executed), "green"), ("ERROR · LAST RUN", len(errors), "red"), ("NETWORK STATE", run_state, "yellow")]
for col, (label, value, cls) in zip(cols, metrics):
    col.markdown(f'<div class="metric"><div class="label">{label}</div><div class="value {cls}">{html.escape(str(value))}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section">SPECIALIST NETWORK · 9 REGISTERED AGENTS</div>', unsafe_allow_html=True)
rows = st.columns(3)
for i, name in enumerate(AGENT_ORDER):
    result = agents.get(name, {}) or {}
    raw_status = str(result.get("status", "NOT RUN")).upper()
    if closed and not result:
        status, cls, status_cls = "STANDBY", "pending", "yellow"
        detail = AGENT_ROLE[name] + " · awaiting next valid market run."
    else:
        status = raw_status
        cls = "ready" if status == "READY" else "error" if status == "ERROR" else "pending"
        status_cls = "green" if status == "READY" else "red" if status == "ERROR" else "yellow"
        detail = AGENT_ROLE[name]
        if status == "READY":
            data = result.get("data", {}) or {}
            if name == "News Agent": detail += f" · {len(data) if isinstance(data, list) else 'Evidence'} records packaged."
            elif name == "Market Agent": detail += f" · {len(data.get('snapshot', []))} instruments."
            elif name == "Technical Agent": detail += f" · 20D trend: {data.get('trend_vs_20d', 'UNKNOWN')} · RSI: {data.get('rsi14', '—')}"
            elif name == "Sector Agent": detail += f" · {len(data.get('sectors', []))} sectors evaluated."
            elif name == "Risk Agent": detail += f" · {len(data.get('flags', []))} risk flags."
            elif name == "Options Agent": detail += f" · PCR OI: {data.get('pcr_oi', '—')} · bias: {data.get('oi_bias', '—')}"
            elif name == "Watchlist Agent": detail += f" · {len(data) if isinstance(data, list) else 'Watchlist'} records."
        elif status == "ERROR":
            detail += " · " + str(result.get("error", "Agent error"))[:150]
    elapsed = result.get("elapsed_ms")
    timing = f" · {float(elapsed):.0f} ms" if elapsed is not None else ""
    rows[i % 3].markdown(f'<div class="agent"><div class="agent-head"><span class="agent-name"><span class="dot {cls}"></span>{html.escape(name)}</span><span class="agent-status {status_cls}">{html.escape(status)}{timing}</span></div><div class="agent-detail">{html.escape(detail)}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section">⚔️ AGENT DEBATE ARENA</div>', unsafe_allow_html=True)
challenges = specialists.get("challenges", []) or []
challenge_count = specialists.get("challenge_count", len(challenges)) if specialists else 0
if challenges:
    st.markdown(f'<div class="banner"><div class="label">LIVE EVIDENCE CHALLENGES</div><div style="font-weight:800;margin-top:5px" class="yellow">{challenge_count} CHALLENGE{"S" if challenge_count != 1 else ""} · CHIEF ADJUDICATION REQUIRED</div><div class="muted" style="margin-top:4px">These are evidence conflicts detected before the Chief Intelligence Agent forms the final verdict.</div></div>', unsafe_allow_html=True)
    for challenge in challenges[:5]:
        agents_text = str(challenge.get("agents", "Agent challenge"))
        parts = [x.strip() for x in agents_text.replace("↔", "|").split("|") if x.strip()]
        route = f'{html.escape(parts[0])}<span class="arrow">⚔</span>{html.escape(parts[1])}' if len(parts) >= 2 else html.escape(agents_text)
        issue = html.escape(str(challenge.get("issue", "Evidence conflict detected.")))
        resolution = html.escape(str(challenge.get("resolution", "Chief must adjudicate.")))
        severity = str(challenge.get("severity", "MEDIUM")).upper()
        sev_cls = "severity-high" if severity == "HIGH" else "severity-low" if severity == "LOW" else "severity-medium"
        st.markdown(f'<div class="debate"><div class="debate-route">{route}</div><div class="debate-issue">{issue}</div><div class="debate-meta"><span class="{sev_cls}">● {html.escape(severity)} PRIORITY</span> · {resolution}</div></div>', unsafe_allow_html=True)
else:
    if closed:
        msg = "No debate executed because the market is closed. Challenges will appear automatically on the next valid intelligence run."
    else:
        msg = "No cross-agent conflict was detected in the latest completed run."
    st.markdown(f'<div class="banner"><div class="label">DEBATE STATUS</div><div style="font-weight:700;margin-top:5px">NO ACTIVE CHALLENGES</div><div class="muted" style="margin-top:4px">{html.escape(msg)}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section">CHIEF INTELLIGENCE</div>', unsafe_allow_html=True)
bias = ai.get("bias", report.get("verdict", "UNKNOWN")); confidence = ai.get("confidence", report.get("confidence", "—")); regime = ai.get("market_regime", "UNKNOWN"); score = ai.get("decision_score", report.get("decision", {}).get("score", "—")); thesis = ai.get("thesis", "No Chief analysis is available for the current run.")
color = "green" if str(bias).upper() == "BULLISH" else "red" if str(bias).upper() == "BEARISH" else "yellow"
left, right = st.columns([1.6, 1])
left.markdown(f'<div class="chief"><div class="label">FINAL ADJUDICATION</div><div class="chief-title {color}">{html.escape(str(bias))} · {html.escape(str(score))}/100</div><div class="chief-thesis">{html.escape(str(thesis))}</div><div style="margin-top:9px"><span class="tag">CONFIDENCE · {html.escape(str(confidence))}</span><span class="tag">REGIME · {html.escape(str(regime))}</span><span class="tag">EVIDENCE · {html.escape(str(ai.get("evidence_quality", "INSUFFICIENT")))}</span></div></div>', unsafe_allow_html=True)
right.markdown(f'<div class="chief"><div class="label">GOVERNANCE</div><div class="list">Conflicts reported: <b>{"YES" if ai.get("conflicts") else "NONE REPORTED"}</b></div><div class="list">Debate challenges: <b>{challenge_count}</b></div><div class="list">No order execution: <b>ENFORCED</b></div><div class="list">AI status: <b>{html.escape(str(ai.get("status", "NOT RUN")))}</b></div><div class="list">Current market state: <b>{html.escape(market_status)}</b></div></div>', unsafe_allow_html=True)

if last_run:
    st.markdown('<div class="section">LAST COMPLETED INTELLIGENCE RUN</div>', unsafe_allow_html=True)
    last_ai = last_run.get("ai", {}) or {}
    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.markdown(f'<div class="metric"><div class="label">DATE</div><div class="value blue">{html.escape(str(last_run.get("date_ist", "—")))}</div></div>', unsafe_allow_html=True)
    lc2.markdown(f'<div class="metric"><div class="label">BIAS</div><div class="value {"green" if str(last_ai.get("bias", "")).upper()=="BULLISH" else "red" if str(last_ai.get("bias", "")).upper()=="BEARISH" else "yellow"}">{html.escape(str(last_ai.get("bias", last_run.get("rule_bias", "—"))))}</div></div>', unsafe_allow_html=True)
    lc3.markdown(f'<div class="metric"><div class="label">CONFIDENCE</div><div class="value yellow">{html.escape(str(last_ai.get("confidence", last_run.get("rule_confidence", "—"))))}</div></div>', unsafe_allow_html=True)
    lc4.markdown(f'<div class="metric"><div class="label">SCORE</div><div class="value blue">{html.escape(str(last_run.get("decision", {}).get("score", "—")))}</div></div>', unsafe_allow_html=True)

bull, base, bear = st.columns(3)
for col, title, key, cls in [(bull, "BULL CASE", "bull_case", "green"), (base, "BASE CASE", "base_case", "blue"), (bear, "BEAR CASE", "bear_case", "red")]:
    col.markdown(f'<div class="banner"><div class="label">{title}</div><div class="muted" style="margin-top:7px">{html.escape(str(ai.get(key, "Unavailable")))}</div></div>', unsafe_allow_html=True)

conflicts = ai.get("conflicts", []) or []; risks = ai.get("risks", []) or []; drivers = ai.get("drivers", []) or []
if conflicts or risks or drivers:
    st.markdown('<div class="section">INTELLIGENCE LEDGER</div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    for col, title, values, cls in [(a, "CONFLICTS", conflicts, "yellow"), (b, "KEY RISKS", risks, "red"), (c, "DRIVERS", drivers, "green")]:
        body = ''.join(f'<div class="list">{html.escape(str(v))}</div>' for v in values[:6]) or '<div class="muted">None reported.</div>'
        col.markdown(f'<div class="ledger"><div class="label {cls}">{title}</div>{body}</div>', unsafe_allow_html=True)

st.caption("MarketPilot Agent Command Center · 9 specialist agents · research + debate + Chief adjudication · no order execution.")
