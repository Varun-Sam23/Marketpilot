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

from news_intelligence import enrich_news

st.set_page_config(page_title="MarketPilot", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
DATA_FILE=Path("data/latest.json")
WATCHLIST_FILE=Path("data/watchlist.json")
HISTORY_FILE=Path("data/history.json")
IST=ZoneInfo("Asia/Kolkata")
NSE_CALENDAR=mcal.get_calendar("NSE")
DEFAULT_WATCHLIST=["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","INFY.NS","TCS.NS","TATAMOTORS.NS","ITC.NS"]
NEWS_FEEDS=[
 ("India Markets","https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
 ("RBI / Economy","https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
 ("Indian Companies","https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
 ("Global Markets","https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b;--green:#59b987;--red:#e27a75;--shadow:0 14px 34px rgba(0,0,0,.22)}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 27%),radial-gradient(circle at 0% 30%,rgba(84,123,155,.08),transparent 30%),var(--bg)}
[data-testid="stHeader"]{background:transparent}[data-testid="stMainBlockContainer"]{max-width:1460px!important;padding-top:.45rem!important}.main .block-container{max-width:1460px;padding:.45rem 2.1rem 4rem}
.mp-brand{display:flex;align-items:center;gap:.8rem}.mp-orb{width:40px;height:40px;border:1px solid rgba(201,168,91,.55);border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--gold);font-size:1.35rem;background:rgba(201,168,91,.06)}.mp-title{font-family:Georgia,"Times New Roman",serif;font-size:2.75rem;font-weight:600;letter-spacing:-.035em;color:var(--ink)}.mp-sub{margin:.35rem 0 .7rem 3.2rem;color:var(--muted);font-size:.72rem;letter-spacing:.18em;text-transform:uppercase}.mp-rule{height:1px;background:linear-gradient(90deg,var(--gold),transparent 70%);opacity:.55;margin:.3rem 0 .7rem}.mp-meta{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;margin-bottom:.45rem}.mp-status{display:inline-flex;align-items:center;gap:.42rem;padding:.3rem .65rem;border:1px solid var(--line);border-radius:999px;font-size:.67rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink)}.mp-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px rgba(89,185,135,.65)}.mp-dot.closed{background:#707985;box-shadow:none}.mp-clock{font-size:.73rem;color:var(--muted)}
.mp-command-deck{display:grid;grid-template-columns:1.15fr 1fr 1fr 1fr;gap:.65rem;margin:.65rem 0 .9rem;padding:.65rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(100deg,rgba(201,168,91,.09),rgba(255,255,255,.018) 52%,rgba(84,123,155,.055));box-shadow:0 12px 30px rgba(0,0,0,.16)}.mp-command-item{min-height:58px;padding:.62rem .8rem;border-right:1px solid var(--line)}.mp-command-item:last-child{border-right:0}.mp-command-label{font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted)}.mp-command-value{font-family:Georgia,"Times New Roman",serif;font-size:1rem;color:var(--ink);margin-top:.18rem}.mp-command-meta{font-size:.62rem;color:var(--muted);margin-top:.12rem}
.mp-wire{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:.65rem}.mp-ticker{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:linear-gradient(90deg,rgba(201,168,91,.06),rgba(255,255,255,.018));padding:9px 0;box-shadow:var(--shadow)}.mp-track{display:inline-block;white-space:nowrap;padding-left:100%;animation:mp-scroll 180s linear infinite;font-size:.82rem;color:var(--ink)}.mp-track:hover{animation-play-state:paused}.mp-news-item{display:inline-block;margin-right:30px}.mp-news-item small{color:var(--muted)}@keyframes mp-scroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
.mp-card,.dc-card{background:linear-gradient(180deg,rgba(255,255,255,.032),rgba(255,255,255,.018));border:1px solid var(--line);border-radius:17px;padding:1rem;box-shadow:0 9px 28px rgba(0,0,0,.14)}.mp-kicker,.dc-label{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.mp-price{font-family:Georgia,"Times New Roman",serif;font-size:1.55rem;color:var(--ink);margin:.25rem 0 .15rem}.mp-change{font-size:.75rem;color:var(--muted)}.mp-section,.dc-section{font-family:Georgia,"Times New Roman",serif;color:var(--ink);font-size:1.55rem;margin:1.55rem 0 .7rem}.mp-hero{background:linear-gradient(135deg,rgba(201,168,91,.11),rgba(255,255,255,.015) 42%,rgba(99,130,159,.06));border:1px solid var(--line);border-radius:22px;padding:1.2rem;box-shadow:var(--shadow)}.mp-eyebrow{font-size:.65rem;letter-spacing:.16em;text-transform:uppercase;color:var(--gold)}.mp-big{font-family:Georgia,"Times New Roman",serif;font-size:2rem;color:var(--ink);line-height:1.1;margin:.35rem 0 .45rem}.mp-muted{color:var(--muted);font-size:.8rem;line-height:1.5}.mp-chip{display:inline-flex;padding:.25rem .55rem;border-radius:999px;border:1px solid var(--line);font-size:.68rem;color:var(--muted);margin:.35rem .3rem 0 0}.mp-scenario{border:1px solid var(--line);border-radius:15px;background:rgba(255,255,255,.018);padding:1rem;min-height:145px}.mp-scenario h4,.dc-case h4{font-family:Georgia,"Times New Roman",serif;color:var(--ink)}.mp-scenario p,.dc-case p{color:#c5cbd3;line-height:1.5;font-size:.82rem}.dc-sub{color:var(--muted);font-size:.82rem;margin:.35rem 0 1.2rem}.dc-score{font-family:Georgia,"Times New Roman",serif;font-size:4.8rem;line-height:1;color:var(--ink)}.dc-scorebar{height:10px;border-radius:999px;background:linear-gradient(90deg,#a44f49 0%,#a44f49 35%,#9a7b35 35%,#9a7b35 65%,#2f6f52 65%,#2f6f52 100%);overflow:hidden}.dc-marker{height:100%;width:3px;background:#f5f1e8}.dc-case{min-height:150px}.dc-bull{border-top:2px solid #2f6f52}.dc-base{border-top:2px solid #9a7b35}.dc-bear{border-top:2px solid #a44f49}.dc-foot{border-top:1px solid var(--line);margin-top:2rem;padding-top:.8rem;color:#687280;font-size:.68rem;text-align:center}
.news-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:.65rem;margin:.9rem 0 1.1rem}.news-stat{border:1px solid var(--line);border-radius:14px;padding:.8rem 1rem;background:rgba(255,255,255,.018)}.news-stat-label{font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}.news-stat-value{font-family:Georgia,serif;font-size:1.35rem;color:var(--ink);margin-top:.15rem}.news-evidence{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.018);padding:1rem;margin-top:.85rem}.news-evidence-title{font-size:.63rem;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}.news-evidence-head{font-family:Georgia,serif;color:var(--ink);font-size:1.05rem;margin:.3rem 0}.news-evidence-meta{font-size:.75rem;color:var(--muted);line-height:1.6}
button[data-baseweb="tab"]{font-size:.75rem;letter-spacing:.05em}.mp-foot{border-top:1px solid var(--line);margin-top:2.2rem;padding-top:.9rem;color:#687280;font-size:.68rem;text-align:center}
@media(max-width:900px){[data-testid="stMainBlockContainer"]{padding-top:.2rem!important}.main .block-container{padding:.2rem .9rem 3rem}.mp-title{font-size:2.15rem}.mp-sub{margin-left:2.8rem;font-size:.61rem}.mp-big{font-size:1.65rem}.mp-section,.dc-section{font-size:1.35rem}.news-summary{grid-template-columns:1fr 1fr}.mp-command-deck{grid-template-columns:1fr 1fr}.mp-command-item:nth-child(2n){border-right:0}.mp-command-item:nth-child(-n+2){border-bottom:1px solid var(--line)}}
</style>
""",unsafe_allow_html=True)

def load_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def is_trading_day(day=None):
    day=day or datetime.now(IST).date();return not NSE_CALENDAR.schedule(start_date=day,end_date=day).empty

def market_status():
    now=datetime.now(IST)
    if not is_trading_day(now.date()):return "MARKET CLOSED"
    return "MARKET LIVE" if time(9,15)<=now.time()<=time(15,30) else "MARKET CLOSED"

@st.cache_data(ttl=60,show_spinner=False)
def index_snapshot():
    rows=[]
    for ticker in ("^NSEI","^NSEBANK","^BSESN","^INDIAVIX"):
        try:
            h=yf.Ticker(ticker).history(period="1d",interval="5m",auto_adjust=False)
            if not h.empty:
                last=float(h["Close"].iloc[-1]);first=float(h["Open"].iloc[0]);rows.append({"ticker":ticker,"last":last,"change_pct":((last/first)-1)*100 if first else 0})
        except Exception:pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=60,show_spinner=False)
def watchlist_data(tickers):
    rows=[]
    for ticker in tickers:
        try:
            h=yf.Ticker(ticker).history(period="3mo",interval="1d",auto_adjust=False)
            if len(h)>=22:
                last=float(h["Close"].iloc[-1]);prev=float(h["Close"].iloc[-2]);sma20=float(h["Close"].tail(20).mean());avgvol=float(h["Volume"].tail(20).mean())
                rows.append({"Stock":ticker.replace(".NS",""),"Last":round(last,2),"1D %":round(((last/prev)-1)*100,2),"20D %":round(((last/float(h["Close"].iloc[-21]))-1)*100,2),"vs 20D SMA %":round(((last/sma20)-1)*100,2),"Vol / 20D":round(float(h["Volume"].iloc[-1])/avgvol,2) if avgvol else None})
        except Exception:pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=60,show_spinner=False)
def live_news():
    items=[]
    for group,url in NEWS_FEEDS:
        try:
            feed=feedparser.parse(url)
            for entry in feed.entries[:8]:
                title=entry.get("title","").strip();publisher="";src=entry.get("source")
                if isinstance(src,dict):publisher=str(src.get("title") or src.get("name") or "").strip()
                if not publisher:
                    m=re.search(r"\s+-\s+([^-]+)$",title)
                    if m:publisher=m.group(1).strip()
                if not publisher or publisher.lower()=="news.google.com":publisher="Unknown publisher"
                clean=re.sub(r"\s+-\s+([^-]+)$","",title).strip() if publisher!="Unknown publisher" else title
                items.append({"title":clean,"publisher":publisher,"source":publisher,"feed_group":group,"published":entry.get("published",""),"link":entry.get("link","")})
        except Exception:pass
    return items[:28]

def verification_badge(value):
    return {"CROSS_CHECKED":"🔎 CROSS-CHECKED","CONFLICTING":"⚠️ CONFLICTING","CORROBORATED":"✓ CORROBORATED","SINGLE_SOURCE":"⚠ SINGLE SOURCE","UNVERIFIED":"? UNVERIFIED"}.get(value,"? UNVERIFIED")

def claim_badge(value):
    return {"SUPPORTED":"🟢 SUPPORTED","DISPUTED":"🔴 DISPUTED","INSUFFICIENT EVIDENCE":"🟡 INSUFFICIENT EVIDENCE"}.get(value,"🟡 INSUFFICIENT EVIDENCE")

def impact_icon(value):return {"POSITIVE":"↗","NEGATIVE":"↘","NEUTRAL":"→","UNKNOWN":"?"}.get(value,"→")

def evidence_label(score):
    if score>=75:return "STRONG"
    if score>=55:return "MODERATE"
    if score>=35:return "LIMITED / CONFLICTING"
    return "WEAK"

def decision_score(report):
    levels=report.get("levels",{});sectors=report.get("sectors",[]);score=50;evidence=[]
    if levels:
        close=levels.get("NIFTY close");sma20=levels.get("20D SMA")
        if close is not None and sma20 is not None:
            if close>sma20:score+=12;evidence.append(("+12","NIFTY above 20-day average"))
            else:score-=12;evidence.append(("-12","NIFTY below 20-day average"))
        ret20=levels.get("20D return %",0)
        if ret20>0:score+=10;evidence.append(("+10","Positive 20-day momentum"))
        elif ret20<0:score-=10;evidence.append(("-10","Negative 20-day momentum"))
        rsi=levels.get("RSI14")
        if rsi is not None:
            if rsi>=60:score+=8;evidence.append(("+8",f"RSI is constructive ({rsi:.0f})"))
            elif rsi<=40:score-=8;evidence.append(("-8",f"RSI is weak ({rsi:.0f})"))
    if sectors:
        avg=sum(float(s.get("avg_change_pct",0)) for s in sectors)/len(sectors)
        if avg>.5:score+=10;evidence.append(("+10","Sector pulse broadly positive"))
        elif avg<-.5:score-=10;evidence.append(("-10","Sector pulse broadly negative"))
    score=max(0,min(100,score))
    if score>=68:bias,regime="BULLISH","Positive trend"
    elif score>=56:bias,regime="BULLISH LEAN","Constructive / mixed"
    elif score<=32:bias,regime="BEARISH","Negative trend"
    elif score<=44:bias,regime="BEARISH LEAN","Weak / mixed"
    else:bias,regime="NEUTRAL","Mixed / range"
    confidence="HIGH" if abs(score-50)>=25 else "MEDIUM" if abs(score-50)>=12 else "LOW"
    return score,bias,regime,confidence,evidence

report=load_json(DATA_FILE,{})
status=market_status();now=datetime.now(IST);raw_news=live_news();news_intel=enrich_news(raw_news);indices=index_snapshot();watchlist=load_json(WATCHLIST_FILE,DEFAULT_WATCHLIST)
st_autorefresh(interval=60_000,key="marketpilot_refresh")

st.markdown('<div class="mp-brand"><div class="mp-orb">◈</div><div class="mp-title">MarketPilot</div></div>',unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Indian markets · intelligence before action · decision support</div>',unsafe_allow_html=True)
dot="mp-dot" if status=="MARKET LIVE" else "mp-dot closed";label="LIVE" if status=="MARKET LIVE" else "CLOSED"
st.markdown(f'<div class="mp-meta"><span class="mp-status"><span class="{dot}"></span>{label}</span><span class="mp-clock">{now.strftime("%A · %d %B %Y · %H:%M:%S IST")}</span></div><div class="mp-rule"></div>',unsafe_allow_html=True)

verified_count=sum(1 for x in news_intel if x.get("claim_status")=="SUPPORTED")
strong_count=sum(1 for x in news_intel if int(x.get("evidence_score",10))>=75)
conflict_count=sum(1 for x in news_intel if x.get("claim_status")=="DISPUTED")
st.markdown(f'''<div class="mp-command-deck"><div class="mp-command-item"><div class="mp-command-label">Market state</div><div class="mp-command-value">{'LIVE SESSION' if status=="MARKET LIVE" else 'MARKET CLOSED'}</div><div class="mp-command-meta">NSE calendar aware</div></div><div class="mp-command-item"><div class="mp-command-label">News coverage</div><div class="mp-command-value">{len(news_intel)} live stories</div><div class="mp-command-meta">Public feeds · 60s refresh</div></div><div class="mp-command-item"><div class="mp-command-label">Evidence desk</div><div class="mp-command-value">{strong_count} strong · {verified_count} supported</div><div class="mp-command-meta">{conflict_count} disputed claims</div></div><div class="mp-command-item"><div class="mp-command-label">Intelligence mode</div><div class="mp-command-value">Evidence first</div><div class="mp-command-meta">No headline treated as fact by default</div></div></div>''',unsafe_allow_html=True)

st.markdown('<div class="mp-wire">Live wire · public feeds · 180s · pauses on hover</div>',unsafe_allow_html=True)
if news_intel:
    parts=[]
    for item in news_intel[:12]:
        score=item.get("evidence_score",10);parts.append(f'<span class="mp-news-item"><b>{claim_badge(item.get("claim_status"))}</b> {html.escape(item.get("title","").replace("🟢 SUPPORTED · ","").replace("🔴 DISPUTED · ","").replace("🟡 INSUFFICIENT EVIDENCE · ",""))} <small>• {html.escape(item.get("publisher","Unknown publisher"))} • Evidence {score}/100 • {html.escape(item.get("impact","NEUTRAL"))}</small></span>')
    st.markdown('<div class="mp-ticker"><div class="mp-track">'+' &nbsp; ◆ &nbsp; '.join(parts)+'</div></div>',unsafe_allow_html=True)
else:st.info("Live news is temporarily unavailable.")

lookup={r["ticker"]:r for _,r in indices.iterrows()} if not indices.empty else {};card_defs=[("NIFTY 50","^NSEI"),("BANK NIFTY","^NSEBANK"),("SENSEX","^BSESN"),("INDIA VIX","^INDIAVIX")];cols=st.columns(4)
for col,(name,ticker) in zip(cols,card_defs):
    row=lookup.get(ticker);last=f'{row["last"]:,.2f}' if row is not None else "—";chg=f'{row["change_pct"]:+.2f}%' if row is not None else "—";label2="From open" if status=="MARKET LIVE" else "Last session"
    col.markdown(f'<div class="mp-card"><div class="mp-kicker">{name}</div><div class="mp-price">{last}</div><div class="mp-change">{label2} · {chg}</div></div>',unsafe_allow_html=True)

morning,decision,live,news_tab,performance=st.tabs(["🌅 MORNING INTELLIGENCE","🎯 DECISION CENTER","⚡ LIVE MARKET","📰 NEWS INTELLIGENCE","📓 PERFORMANCE"])

with morning:
    ai=report.get("ai_analysis",{});verdict=report.get("verdict","WAIT")
    st.markdown('<div class="mp-section">The morning ledger</div>',unsafe_allow_html=True)
    if ai.get("enabled"):
        st.markdown(f'<div class="mp-hero"><div class="mp-eyebrow">AI Market Brief</div><div class="mp-big">{html.escape(ai.get("bias","UNKNOWN"))} · {html.escape(ai.get("market_regime","UNKNOWN"))}</div><div class="mp-muted">{html.escape(ai.get("thesis","No thesis recorded yet."))}</div><span class="mp-chip">Confidence · {html.escape(ai.get("confidence","LOW"))}</span><span class="mp-chip">Rule framework · {html.escape(verdict)}</span></div>',unsafe_allow_html=True)
        x,y,z=st.columns(3)
        for c,title,key in ((x,"🟢 Bull case","bull_case"),(y,"🟡 Base case","base_case"),(z,"🔴 Bear case","bear_case")):c.markdown(f'<div class="mp-scenario"><h4>{title}</h4><p>{html.escape(ai.get(key,""))}</p></div>',unsafe_allow_html=True)
        st.markdown('<div class="mp-section">Levels & invalidation</div>',unsafe_allow_html=True);l1,l2=st.columns([1.6,1])
        with l1:
            for level in ai.get("key_levels",[]):st.write("•",level)
        with l2:
            if ai.get("invalidation"):st.warning(ai.get("invalidation"))
        d1,d2=st.columns(2)
        with d1:
            st.markdown('<div class="mp-section">Drivers</div>',unsafe_allow_html=True)
            for item in ai.get("drivers",[]):st.write("•",item)
        with d2:
            st.markdown('<div class="mp-section">Risks</div>',unsafe_allow_html=True)
            for item in ai.get("risks",[]):st.write("•",item)
    else:
        st.markdown('<div class="mp-hero"><div class="mp-eyebrow">AI Market Brief</div><div class="mp-big">Waiting for the next trading-day analysis</div><div class="mp-muted">The report engine will populate the morning thesis on an NSE trading day. MarketPilot will not invent a view when the market is closed or fresh evidence is unavailable.</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="mp-section">Market structure</div>',unsafe_allow_html=True);levels=report.get("levels",{})
    if levels:st.dataframe(pd.DataFrame([levels]),use_container_width=True,hide_index=True)
    else:st.caption("Technical structure will populate after the next scheduled pre-market run.")
    st.markdown('<div class="mp-section">Sector pulse</div>',unsafe_allow_html=True);sectors=report.get("sectors",[])
    if sectors:st.dataframe(pd.DataFrame(sectors).rename(columns={"sector":"Sector","avg_change_pct":"Avg 1D %","members":"Members"}),use_container_width=True,hide_index=True)
    else:st.caption("Sector pulse will populate after the next trading-day run.")

with decision:
    score,bias,regime,confidence,evidence=decision_score(report)
    st.markdown('<div class="dc-section">Decision Center</div>',unsafe_allow_html=True);st.markdown('<div class="dc-sub">Evidence-first framework beneath the AI thesis. This is decision support, not a trading instruction.</div>',unsafe_allow_html=True)
    a,b=st.columns([1.05,2])
    with a:
        st.markdown('<div class="dc-card"><div class="dc-label">Day setup score</div>',unsafe_allow_html=True);st.markdown(f'<div class="dc-score">{score}<span style="font-size:1rem;color:#7d8790"> / 100</span></div>',unsafe_allow_html=True);st.markdown(f'<div style="font-weight:700;margin:.35rem 0 .7rem">{html.escape(bias)}</div>',unsafe_allow_html=True);st.markdown(f'<div class="dc-scorebar"><div style="margin-left:{score}%;height:100%;position:relative"><div class="dc-marker"></div></div></div><div style="margin-top:.7rem;color:#c5cbd3;font-size:.78rem">Regime · {html.escape(regime)}<br>Confidence · {html.escape(confidence)}</div></div>',unsafe_allow_html=True)
    with b:
        c1,c2,c3=st.columns(3);c1.metric("AI bias",ai.get("bias","WAIT"));c2.metric("AI confidence",ai.get("confidence","N/A"));c3.metric("Rule bias",report.get("verdict","WAIT"));st.markdown(f'<div class="dc-card" style="margin-top:.9rem"><div class="dc-label">Core thesis</div><div style="font-family:Georgia,serif;font-size:1.1rem;line-height:1.5;color:#f2eee5;margin-top:.35rem">{html.escape(ai.get("thesis") or report.get("summary") or "No thesis available yet.")}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="dc-section">Scenario map</div>',unsafe_allow_html=True);x,y,z=st.columns(3)
    for c,title,key,cls in ((x,"🟢 Bull case","bull_case","dc-bull"),(y,"🟡 Base case","base_case","dc-base"),(z,"🔴 Bear case","bear_case","dc-bear")):c.markdown(f'<div class="dc-card dc-case {cls}"><h4>{title}</h4><p>{html.escape(ai.get(key) or "Not available")}</p></div>',unsafe_allow_html=True)
    st.markdown('<div class="dc-section">Evidence ledger</div>',unsafe_allow_html=True)
    if evidence:st.dataframe(pd.DataFrame(evidence,columns=["Weight","Evidence"]),use_container_width=True,hide_index=True)
    else:st.info("Evidence will populate after the next trading-day analysis.")
    if report.get("levels"):st.markdown('<div class="dc-section">Market structure</div>',unsafe_allow_html=True);st.dataframe(pd.DataFrame([report["levels"]]),use_container_width=True,hide_index=True)
    st.markdown('<div class="dc-foot">Score = transparent evidence weighting. It is not a probability, guarantee or trade recommendation.</div>',unsafe_allow_html=True)

with live:
    st.markdown('<div class="mp-section">Live market monitor</div>',unsafe_allow_html=True)
    if indices.empty:st.warning("Live market data is unavailable from the public feed right now.")
    else:
        ldf=indices.copy();ldf["ticker"]=ldf["ticker"].replace({"^NSEI":"NIFTY 50","^NSEBANK":"BANK NIFTY","^BSESN":"SENSEX","^INDIAVIX":"INDIA VIX"});ldf["last"]=ldf["last"].round(2);ldf["change_pct"]=ldf["change_pct"].round(2);st.dataframe(ldf.rename(columns={"ticker":"Index","last":"Last","change_pct":"Session %"}),use_container_width=True,hide_index=True)
    st.markdown('<div class="mp-section">Watchlist</div>',unsafe_allow_html=True);wdf=watchlist_data(tuple(watchlist));st.dataframe(wdf.sort_values("1D %",ascending=False),use_container_width=True,hide_index=True) if not wdf.empty else st.caption("Watchlist data is temporarily unavailable.")

with news_tab:
    st.markdown('<div class="mp-section">News intelligence</div>',unsafe_allow_html=True)
    st.markdown('<div class="mp-note">Evidence Strength is a corroboration-strength indicator (10–90), not a probability that a claim is true. Google News is the collection layer; independent publisher coverage is used as supporting evidence. Conflicts are deliberately penalized.</div>',unsafe_allow_html=True)
    if news_intel:
        checked=[x for x in news_intel if "evidence_score" in x];scores=[int(x.get("evidence_score",10)) for x in checked];avg_score=round(sum(scores)/len(scores)) if scores else 0;strong=sum(s>=75 for s in scores);conflicts=sum(x.get("verification")=="CONFLICTING" for x in checked);supported=sum(x.get("claim_status")=="SUPPORTED" for x in checked);disputed=sum(x.get("claim_status")=="DISPUTED" for x in checked);insufficient=sum(x.get("claim_status")=="INSUFFICIENT EVIDENCE" for x in checked)
        st.markdown(f'<div class="news-summary"><div class="news-stat"><div class="news-stat-label">Avg evidence</div><div class="news-stat-value">{avg_score}/100</div></div><div class="news-stat"><div class="news-stat-label">Supported</div><div class="news-stat-value">{supported}</div></div><div class="news-stat"><div class="news-stat-label">Disputed</div><div class="news-stat-value">{disputed}</div></div><div class="news-stat"><div class="news-stat-label">Insufficient</div><div class="news-stat-value">{insufficient}</div></div><div class="news-stat"><div class="news-stat-label">Strong evidence</div><div class="news-stat-value">{strong}</div></div></div>',unsafe_allow_html=True)
        rows=[]
        for item in news_intel[:20]:
            score=int(item.get("evidence_score",10));count=int(item.get("evidence_count",0));claim=item.get("claim_status","INSUFFICIENT EVIDENCE");title=item.get("title","")
            title=re.sub(r"^(🟢 SUPPORTED|🔴 DISPUTED|🟡 INSUFFICIENT EVIDENCE)\s*·\s*","",title)
            rows.append({"Claim Status":claim_badge(claim),"Headline":title,"Verification":verification_badge(item.get("verification")),"Evidence":f'{score}/100 · {evidence_label(score)}',"Sources":count,"Impact":f'{impact_icon(item.get("impact"))} {item.get("impact","NEUTRAL")}',"Affected":item.get("affected","MARKET"),"Publisher":item.get("publisher","Unknown publisher"),"Published":item.get("published","")})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.markdown('<div class="mp-section">Evidence desk · top stories</div>',unsafe_allow_html=True)
        for i,item in enumerate(news_intel[:8],1):
            score=int(item.get("evidence_score",10));sources=item.get("verification_sources",[]);source_text=" · ".join(sources) if sources else "No independent sources found";claim=item.get("claim_status","INSUFFICIENT EVIDENCE");title=re.sub(r"^(🟢 SUPPORTED|🔴 DISPUTED|🟡 INSUFFICIENT EVIDENCE)\s*·\s*","",item.get("title",""))
            with st.expander(f'{i:02d} · {claim_badge(claim)} · {verification_badge(item.get("verification"))} · Evidence {score}/100 · {title}'):
                st.markdown(f'<div class="news-evidence"><div class="news-evidence-title">Claim status · {html.escape(claim)}</div><div class="news-evidence-head">Evidence strength · {score}/100 · {evidence_label(score)}</div><div class="news-evidence-meta"><b>Publisher:</b> {html.escape(item.get("publisher","Unknown publisher"))}<br><b>Independent sources:</b> {html.escape(source_text)}<br><b>Impact:</b> {html.escape(item.get("impact","NEUTRAL"))} · <b>Affected:</b> {html.escape(item.get("affected","MARKET"))}<br><b>Why:</b> {html.escape(item.get("verification_detail",""))}</div></div>',unsafe_allow_html=True)
    else:st.info("No current headlines available from the public feeds.")

with performance:
    st.markdown('<div class="mp-section">Thesis journal</div>',unsafe_allow_html=True);history=load_json(HISTORY_FILE,[])
    if history:
        hdf=pd.DataFrame([{"Date":x.get("date_ist",""),"Rule Bias":x.get("rule_bias",""),"Rule Confidence":x.get("rule_confidence",""),"AI Bias":x.get("ai",{}).get("bias",""),"AI Confidence":x.get("ai",{}).get("confidence",""),"Regime":x.get("ai",{}).get("market_regime","")} for x in history[-30:]]);st.dataframe(hdf,use_container_width=True,hide_index=True);st.caption("Outcome scoring will be layered onto the journal after enough completed trading sessions are available.")
    else:st.info("No completed trading-day thesis has been journaled yet.")

st.markdown('<div class="mp-foot">MarketPilot uses public/free data feeds which may be delayed, incomplete or unavailable. Research and decision support only · no order execution.</div>',unsafe_allow_html=True)
