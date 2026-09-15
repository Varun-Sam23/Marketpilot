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

IST=ZoneInfo("Asia/Kolkata")
DATA_FILE=Path("data/latest.json")
WATCHLIST_FILE=Path("data/watchlist.json")
NSE_CALENDAR=mcal.get_calendar("NSE")
DEFAULT_WATCHLIST=["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","INFY.NS","TCS.NS","TATAMOTORS.NS","ITC.NS"]
NEWS_FEEDS=[
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
.box,.change{background:linear-gradient(145deg,#0e151f,#0b1119);border:1px solid #202c3c;border-radius:14px;padding:14px 15px;height:100%}.label,.change-label{color:#7f8da0;font-size:.61rem;text-transform:uppercase;letter-spacing:.12em}.big{font-family:Georgia,serif;font-size:1.55rem;font-weight:800;margin-top:5px}.muted{color:#8492a4;font-size:.72rem;line-height:1.4}.positive{color:#64d39a}.negative{color:#ff7b83}.neutral{color:#c5ced9}
.verdict{background:linear-gradient(145deg,#101925,#0c131d);border:1px solid #2a394c;border-radius:15px;padding:17px 18px;min-height:145px;height:auto;box-sizing:border-box;overflow:hidden}.verdict-value{font-family:Georgia,serif;font-size:1.85rem;font-weight:800;margin-top:5px;line-height:1.15;overflow-wrap:anywhere}.verdict-copy{color:#b7c1ce;font-size:.84rem;line-height:1.45;margin-top:7px;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.section{font-family:Georgia,serif;font-size:1.18rem;margin:16px 0 8px}.meta{float:right;font-family:Arial,sans-serif;color:#718096;font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;margin-top:5px}
.ticker{overflow:hidden;border:1px solid #202c3c;border-radius:11px;background:#0b1119;padding:9px;white-space:nowrap;margin:8px 0 16px}.track{display:inline-block;padding-left:100%;animation:scroll 150s linear infinite}@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.change{min-height:150px}.change-item{padding:7px 0;border-top:1px solid #1d2938;font-size:.76rem;line-height:1.35}.change-item:first-child{border-top:0}.change-value{font-size:.85rem;font-weight:800}.risk-row{padding:7px 0;border-top:1px solid #1d2938}.risk-row:first-child{border-top:0}
.evidence-wrap{border:1px solid #202c3c;border-radius:12px;overflow:hidden;background:#0b1119}.evidence-table{width:100%;border-collapse:collapse;font-size:.72rem;table-layout:fixed}.evidence-table th{text-align:left;padding:9px 10px;background:#171b25;color:#8492a4;font-weight:600;border-bottom:1px solid #263344}.evidence-table td{padding:9px 10px;border-bottom:1px solid #1d2938;color:#dce3ec;vertical-align:top}.evidence-table tr:last-child td{border-bottom:0}.status-supported{color:#64d39a;font-weight:700}.status-disputed{color:#ff7b83;font-weight:700}.status-insufficient{color:#ffd45c;font-weight:700}.status-dot{font-size:.9rem;margin-right:5px;vertical-align:-1px}.status-cell{white-space:nowrap;font-size:.67rem}.evidence-num{font-variant-numeric:tabular-nums;white-space:nowrap}.evidence-headline{line-height:1.35;word-wrap:break-word}.evidence-headline-title{font-size:.76rem;color:#e7edf5;font-weight:600;line-height:1.4}.evidence-gist{color:#91a0b2;font-size:.68rem;line-height:1.45;margin-top:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.evidence-point{display:block}.evidence-point::before{content:"• ";color:#64748b}
</style>
""",unsafe_allow_html=True)

def load_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def score_num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def market_status():
    now=datetime.now(IST)
    try: trading=not NSE_CALENDAR.schedule(start_date=now.date(),end_date=now.date()).empty
    except Exception: trading=now.weekday()<5
    return "MARKET LIVE" if trading and time(9,15)<=now.time()<=time(15,30) else "MARKET CLOSED"

@st.cache_data(ttl=60,show_spinner=False)
def indices_data():
    rows=[]
    for ticker,name in [("^NSEI","NIFTY 50"),("^NSEBANK","BANK NIFTY"),("^BSESN","SENSEX"),("^INDIAVIX","INDIA VIX")]:
        try:
            h=yf.Ticker(ticker).history(period="1d",interval="5m",auto_adjust=False)
            if not h.empty:
                last=float(h.Close.iloc[-1]);first=float(h.Open.iloc[0]);rows.append({"Index":name,"Last":last,"Session %":((last/first)-1)*100 if first else 0})
        except Exception:pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=60,show_spinner=False)
def watch_data(tickers):
    rows=[]
    for ticker in tickers:
        try:
            h=yf.Ticker(ticker).history(period="3mo",interval="1d",auto_adjust=False)
            if len(h)>=22:
                c=h.Close;last=float(c.iloc[-1]);prev=float(c.iloc[-2]);sma=float(c.tail(20).mean())
                rows.append({"Stock":ticker.replace(".NS",""),"1D %":(last/prev-1)*100,"5D %":(last/float(c.iloc[-6])-1)*100,"20D %":(last/float(c.iloc[-21])-1)*100,"vs 20D SMA %":(last/sma-1)*100})
        except Exception:pass
    return pd.DataFrame(rows)

def clean_news_text(value):
    text=re.sub(r"<[^>]+>"," ",str(value or ""))
    text=html.unescape(text)
    return re.sub(r"\s+"," ",text).strip()

def key_news_points(summary,headline):
    text=clean_news_text(summary)
    if not text or text.lower()==clean_news_text(headline).lower():
        return []
    normalized=text.lower()
    if "comprehensive up-to-date news coverage" in normalized or "comprehensive up to date news coverage" in normalized or "aggregated from sources all over the world by google news" in normalized:
        return []
    text=re.sub(r"^(?:\s*[-–—|]\s*)+","",text).strip()
    sentences=re.split(r"(?<=[.!?])\s+",text)
    points=[]
    for sentence in sentences:
        sentence=sentence.strip(" -–—|")
        if sentence and sentence.lower()!=headline.lower():
            points.append(sentence)
        if len(points)==2:break
    if not points and text:
        points=[text]
    return [p[:210].rstrip(" .") + ("…" if len(p)>210 else ".") for p in points[:2]]

@st.cache_data(ttl=60,show_spinner=False)
def raw_news():
    items=[]
    for url in NEWS_FEEDS:
        try:
            feed=feedparser.parse(url)
            for e in feed.entries[:8]:
                title=e.get("title","").strip();publisher="";src=e.get("source")
                if isinstance(src,dict):publisher=str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m=re.search(r"\s+-\s+([^-]+)$",title);publisher=m.group(1).strip() if m else "Unknown publisher"
                title=re.sub(r"\s+-\s+([^-]+)$","",title).strip()
                items.append({"title":title,"publisher":publisher,"published":e.get("published","") or e.get("updated","") ,"summary":e.get("summary") or e.get("description") or "","link":e.get("link") or ""})
        except Exception:pass
    return items[:28]

status=market_status();now=datetime.now(IST);report=load_json(DATA_FILE,{})
news=enrich_news(raw_news());indices=indices_data();tickers=load_json(WATCHLIST_FILE,DEFAULT_WATCHLIST);wl=watch_data(tuple(tickers))
st_autorefresh(interval=60_000,key="main_dashboard_refresh")
ai=report.get("ai_analysis",{}) or {};decision=report.get("decision",{}) or {}
bias=decision.get("bias") or ai.get("bias") or report.get("verdict") or "WAIT";confidence=decision.get("confidence") or ai.get("confidence") or report.get("confidence") or "N/A";regime=decision.get("market_regime") or ai.get("market_regime") or "—";raw_score=decision.get("score","—");score=score_num(raw_score);thesis=ai.get("thesis") or report.get("summary") or "No current market thesis is recorded."
supported=sum(x.get("claim_status")=="SUPPORTED" for x in news);disputed=sum(x.get("claim_status")=="DISPUTED" for x in news);insufficient=sum(x.get("claim_status")=="INSUFFICIENT EVIDENCE" for x in news);strong=sum((score_num(x.get("evidence_score",10)) or 10)>=75 for x in news)

current={"bias":str(bias),"score":score,"confidence":str(confidence),"regime":str(regime),"indices":{str(r["Index"]):float(r["Session %"]) for _,r in indices.iterrows()} if not indices.empty else {},"news":{f'{x.get("title","")}|{x.get("publisher","")}' for x in news[:20]},"watch":{str(r["Stock"]):float(r["1D %"]) for _,r in wl.iterrows()} if not wl.empty else {}}
previous=st.session_state.get("mp_dashboard_snapshot");changes=[]
if previous:
    if current["bias"]!=previous.get("bias"):changes.append(("DECISION",f'{previous.get("bias")} → {current["bias"]}',"neutral"))
    if current["score"] is not None and previous.get("score") is not None and abs(current["score"]-previous["score"])>=1:changes.append(("SCORE",f'{previous["score"]:.0f} → {current["score"]:.0f}',"positive" if current["score"]>previous["score"] else "negative"))
    for name,new in current["indices"].items():
        old=previous.get("indices",{}).get(name)
        if old is not None and abs(new-old)>=.10:changes.append((name,f'{new:+.2f}% session move',"positive" if new>old else "negative"))
    new_news=current["news"]-set(previous.get("news",set()))
    if new_news:changes.append(("NEWS",f'{len(new_news)} new headline(s) surfaced',"positive"))
    for stock,new in current["watch"].items():
        old=previous.get("watch",{}).get(stock)
        if old is not None and abs(new-old)>=.50:changes.append((stock,f'1D move {new:+.2f}%','positive' if new>old else 'negative'))
st.session_state["mp_dashboard_snapshot"]=current

st.markdown(f'<div class="hero"><div><div class="title">◈ MarketPilot</div><div class="sub">Indian markets · intelligence before action · evidence-first decision support</div></div><div class="time"><span class="pill">{"● LIVE" if status=="MARKET LIVE" else "○ CLOSED"}</span><br>{now.strftime("%A · %d %B %Y")}<br>{now.strftime("%H:%M:%S")} IST</div></div>',unsafe_allow_html=True)
st.markdown(f'<div class="deck"><span class="label">COMMAND DECK</span><span>{"🟢" if status=="MARKET LIVE" else "⚪"} {status}</span><span>BIAS <b>{html.escape(str(bias))}</b></span><span>SCORE <b>{html.escape(str(raw_score))}</b></span><span>CONFIDENCE <b>{html.escape(str(confidence))}</b></span><span>REGIME <b>{html.escape(str(regime))}</b></span><span>AUTO REFRESH <b>60s</b></span></div>',unsafe_allow_html=True)

cls="positive" if str(bias).upper()=="BULLISH" else "negative" if str(bias).upper()=="BEARISH" else "neutral";score_label=f"{score:.0f}/100" if score is not None else "N/A"
a,b=st.columns([1.7,1])
with a:
    st.markdown(f'<div class="verdict"><div class="label">AI MARKET VERDICT · EVIDENCE WEIGHTED</div><div class="verdict-value {cls}">{html.escape(str(bias))} · {score_label}</div><div class="verdict-copy">{html.escape(str(thesis))}</div></div>',unsafe_allow_html=True)
with b:
    st.markdown(f'<div class="verdict"><div class="label">RISK POSTURE</div><div class="verdict-value" style="font-size:1.35rem">{html.escape(str(regime))}</div><div class="verdict-copy">Confidence: <b>{html.escape(str(confidence))}</b> · Supported: <b>{supported}</b> · Disputed: <b>{disputed}</b></div></div>',unsafe_allow_html=True)

k=st.columns(4)
for col,(label,val,sub,c) in zip(k,[("Decision Score",raw_score,"Evidence-weighted","neutral"),("Supported Claims",supported,f"of {len(news)} stories","positive"),("Disputed Claims",disputed,"requires caution","negative" if disputed else "neutral"),("Strong Evidence",strong,"score ≥ 75","positive" if strong else "neutral")]):col.markdown(f'<div class="box"><div class="label">{label}</div><div class="big {c}">{html.escape(str(val))}</div><div class="muted">{html.escape(str(sub))}</div></div>',unsafe_allow_html=True)

if news:
    parts=[]
    for x in news[:14]:
        s=x.get("claim_status","INSUFFICIENT EVIDENCE");dot={"SUPPORTED":"🟢","DISPUTED":"🔴","INSUFFICIENT EVIDENCE":"🟡"}.get(s,"🟡")
        title=re.sub(r"^(🟢|🔴|🟡)\s*(SUPPORTED|DISPUTED|INSUFFICIENT EVIDENCE)\s*·\s*","",str(x.get("title", "")))
        parts.append(f'{dot} {html.escape(s)} · {html.escape(title)} · {html.escape(x.get("publisher","Unknown"))}')
    st.markdown('<div class="ticker"><div class="track">'+' &nbsp; ◆ &nbsp; '.join(parts)+'</div></div>',unsafe_allow_html=True)

st.markdown('<div class="section">Market Pulse <span class="meta">Public feed · refresh 60s</span></div>',unsafe_allow_html=True)
if not indices.empty:
    cols=st.columns(len(indices))
    for col,(_,r) in zip(cols,indices.iterrows()):
        pct=float(r["Session %"]);c="positive" if pct>0 else "negative" if pct<0 else "neutral";col.markdown(f'<div class="box"><div class="label">{html.escape(r["Index"])}</div><div class="big">{float(r["Last"]):,.2f}</div><div class="muted {c}">Session {pct:+.2f}%</div></div>',unsafe_allow_html=True)
else:st.info("Public index feed unavailable. No values are estimated.")

st.markdown('<div class="section">What Changed <span class="meta">Compared with previous refresh</span></div>',unsafe_allow_html=True)
c1,c2,c3=st.columns([1.15,1.35,1.0])
with c1:
    if not previous:body='<div class="change-value neutral">INITIAL SNAPSHOT</div><div class="muted">Baseline captured. The next refresh will compare decision, indices, watchlist and news.</div>'
    elif changes:body=f'<div class="change-value positive">{len(changes)} CHANGE(S)</div><div class="muted">Only material moves are shown.</div>'+''.join(f'<div class="change-item"><b>{html.escape(str(x[0]))}</b> <span class="{x[2]}">{html.escape(str(x[1]))}</span></div>' for x in changes[:5])
    else:body='<div class="change-value neutral">NO MATERIAL CHANGE</div><div class="muted">No tracked metric crossed the change threshold.</div>'
    st.markdown(f'<div class="change">{body}</div>',unsafe_allow_html=True)
with c2:
    movers=sorted(current["watch"].items(),key=lambda z:z[1],reverse=True);rows=''.join(f'<div class="change-item"><b>{html.escape(s)}</b> <span class="{"positive" if v>0 else "negative" if v<0 else "neutral"}">{v:+.2f}%</span></div>' for s,v in movers[:5]);st.markdown(f'<div class="change"><div class="change-label">WATCHLIST MOMENTUM</div>{rows or "<div class=muted>No watchlist data.</div>"}</div>',unsafe_allow_html=True)
with c3:
    vix=None
    if not indices.empty and "INDIA VIX" in indices["Index"].values:vix=float(indices.loc[indices["Index"]=="INDIA VIX","Session %"].iloc[0])
    vix_cls="negative" if vix is not None and vix>0 else "neutral";dis_cls="negative" if disputed else "positive"
    st.markdown(f'<div class="change"><div class="change-label">RISK MONITOR</div><div class="risk-row"><div class="muted">News disputes</div><b class="{dis_cls}">{disputed}</b></div><div class="risk-row"><div class="muted">Evidence gaps</div><b>{insufficient}</b></div><div class="risk-row"><div class="muted">India VIX move</div><b class="{vix_cls}">{f"{vix:+.2f}%" if vix is not None else "N/A"}</b></div></div>',unsafe_allow_html=True)

t1,t2,t3=st.tabs(["⚡ INTELLIGENCE CORE","📈 MARKET BOARD","📰 EVIDENCE MONITOR"])
with t1:
    x,y=st.columns([1.0,1.5])
    with x:
        fill=max(0,min(100,score)) if score is not None else 0
        st.markdown(f'<div class="box"><div class="label">DECISION RADAR</div><div class="big">{html.escape(str(bias))}</div><div class="muted">Confidence: {html.escape(str(confidence))} · Regime: {html.escape(str(regime))}</div><div style="height:5px;background:#202b39;border-radius:5px;margin-top:10px"><div style="height:100%;width:{fill}%;background:#8090a4;border-radius:5px"></div></div><div class="muted" style="margin-top:6px">Decision score <b>{score_label}</b></div></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="box" style="margin-top:9px"><div class="label">THESIS</div><div style="margin-top:7px;font-size:.82rem;line-height:1.45">{html.escape(str(thesis))}</div></div>',unsafe_allow_html=True)
    with y:
        s1,s2,s3=st.columns(3);s1.info("🟢 Bull case\n\n"+str(ai.get("bull_case","Not available")));s2.warning("🟡 Base case\n\n"+str(ai.get("base_case","Not available")));s3.error("🔴 Bear case\n\n"+str(ai.get("bear_case","Not available")))
with t2:
    if not wl.empty:st.dataframe(wl.sort_values("1D %",ascending=False),use_container_width=True,hide_index=True)
    else:st.info("Watchlist data unavailable from the public feed.")
with t3:
    rows=[]
    for x in news[:24]:
        status_value=x.get("claim_status","INSUFFICIENT EVIDENCE");dot={"SUPPORTED":"🟢","DISPUTED":"🔴","INSUFFICIENT EVIDENCE":"🟡"}.get(status_value,"🟡");title=re.sub(r"^(🟢|🔴|🟡)\s*(SUPPORTED|DISPUTED|INSUFFICIENT EVIDENCE)\s*·\s*","",str(x.get("title","")))
        points=key_news_points(x.get("summary",""),title)
        rows.append({"dot":dot,"status":status_value,"headline":title,"points":points,"verification":x.get("verification","UNVERIFIED"),"evidence":x.get("evidence_score",10),"sources":x.get("evidence_count",0),"publisher":x.get("publisher","Unknown")})
    if rows:
        trs=[]
        for r in rows:
            cls={"SUPPORTED":"status-supported","DISPUTED":"status-disputed","INSUFFICIENT EVIDENCE":"status-insufficient"}.get(r["status"],"neutral")
            points_html=''.join(f'<span class="evidence-point">{html.escape(p)}</span>' for p in r["points"]) or '<span class="evidence-point">Article facts unavailable; open the publisher for full context.</span>'
            headline_html=f'<div class="evidence-headline-title">{html.escape(str(r["headline"]))}</div><div class="evidence-gist">{points_html}</div>'
            trs.append(f'<tr><td class="{cls} status-cell"><span class="status-dot">{r["dot"]}</span>{html.escape(str(r["status"]))}</td><td class="evidence-headline">{headline_html}</td><td>{html.escape(str(r["verification"]))}</td><td class="evidence-num">{html.escape(str(r["evidence"]))}</td><td class="evidence-num">{html.escape(str(r["sources"]))}</td><td>{html.escape(str(r["publisher"]))}</td></tr>')
        table='<div class="evidence-wrap"><table class="evidence-table"><colgroup><col style="width:170px"><col style="width:52%"><col style="width:125px"><col style="width:72px"><col style="width:72px"><col style="width:125px"></colgroup><thead><tr><th>Status</th><th>Headline · Key Points</th><th>Verification</th><th>Evidence</th><th>Sources</th><th>Publisher</th></tr></thead><tbody>'+''.join(trs)+'</tbody></table></div>'
        st.markdown(table,unsafe_allow_html=True)
    else:st.info("No current headlines available.")

st.caption("MarketPilot uses public/free feeds which may be delayed, incomplete or unavailable. Change tracking is session-based. Research and decision support only — no order execution.")