import json
from pathlib import Path

import pandas as pd
import streamlit as st

from watchlist_intelligence import rank_watchlist
from menu import render_sidebar

st.set_page_config(page_title="MarketPilot · Stock Intelligence", page_icon="🎯", layout="wide")
render_sidebar()

DATA_FILE = Path("data/latest.json")


def load_report():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def badge(label):
    return {"TOP OPPORTUNITY": "🟢 TOP OPPORTUNITY", "WATCH": "🟡 WATCH", "RISK": "🔴 RISK", "NEUTRAL": "⚪ NEUTRAL"}.get(label, label)

st.markdown("""
<style>
:root{--bg:#0b1017;--ink:#edf1f5;--muted:#8f9baa;--line:rgba(255,255,255,.085);--gold:#c9a85b}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 85% 0%,rgba(201,168,91,.10),transparent 28%),var(--bg)}
.main .block-container{max-width:1460px;padding:1.1rem 2.1rem 4rem}
.si-kicker{font-size:.63rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gold)}
.si-title{font-family:Georgia,"Times New Roman",serif;font-size:2.5rem;color:var(--ink);margin:.25rem 0}.si-sub{color:var(--muted);font-size:.8rem;line-height:1.5;max-width:850px}
.si-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.2rem 0}.si-card{border:1px solid var(--line);border-radius:16px;padding:.9rem 1rem;background:rgba(255,255,255,.018)}.si-label{font-size:.57rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.si-value{font-family:Georgia,serif;font-size:1.45rem;color:var(--ink);margin-top:.2rem}
.si-hero{border:1px solid var(--line);border-radius:19px;padding:1rem 1.1rem;background:linear-gradient(115deg,rgba(201,168,91,.09),rgba(255,255,255,.018));margin:1rem 0}.si-score{font-family:Georgia,serif;font-size:2.6rem;color:var(--ink)}.si-reason{color:#c5cbd3;font-size:.76rem;line-height:1.55}.si-divider{height:1px;background:var(--line);margin:1.4rem 0}
</style>
""", unsafe_allow_html=True)

report = load_report()
base_rows = report.get("watchlist", [])
news = report.get("news", [])
ranked = rank_watchlist(base_rows, news)

st.markdown('<div class="si-kicker">MarketPilot research layer</div><div class="si-title">Stock Intelligence</div><div class="si-sub">A ranked watchlist built from trend, momentum, volume, RSI and evidence-aware company news. The labels are research heuristics — not buy/sell calls or price targets.</div>', unsafe_allow_html=True)

if not ranked:
    st.info("Stock intelligence will populate after the next market-data run.")
    st.stop()

top = ranked[0]
supported = sum(x["research_label"] == "TOP OPPORTUNITY" for x in ranked)
watch = sum(x["research_label"] == "WATCH" for x in ranked)
risk = sum(x["research_label"] == "RISK" for x in ranked)
avg = round(sum(x["research_score"] for x in ranked) / len(ranked), 1)

st.markdown(f'<div class="si-grid"><div class="si-card"><div class="si-label">Top ranked</div><div class="si-value">{top["ticker"]}</div></div><div class="si-card"><div class="si-label">Average score</div><div class="si-value">{avg}/100</div></div><div class="si-card"><div class="si-label">Watch / opportunity</div><div class="si-value">{watch + supported}</div></div><div class="si-card"><div class="si-label">Risk candidates</div><div class="si-value">{risk}</div></div></div>', unsafe_allow_html=True)

st.markdown('<div class="si-kicker">Highest ranked setup</div>', unsafe_allow_html=True)
st.markdown(f'<div class="si-hero"><div style="display:flex;justify-content:space-between;gap:1rem;align-items:center"><div><div style="font-family:Georgia,serif;font-size:1.45rem;color:var(--ink)">{top["ticker"]} · {badge(top["research_label"])}</div><div class="si-reason">Confidence · {top["research_confidence"]} · Linked news {top["linked_news"]} · Supported/corroborated news {top["supported_news"]}</div></div><div class="si-score">{top["research_score"]}</div></div><div class="si-divider"></div><div class="si-reason"><b>Why it ranks here:</b> {' · '.join(top["research_reasons"])}</div></div>', unsafe_allow_html=True)

rows=[]
for i, x in enumerate(ranked, 1):
    rows.append({
        "Rank": i,
        "Stock": x["ticker"],
        "Research Score": x["research_score"],
        "Classification": badge(x["research_label"]),
        "Confidence": x["research_confidence"],
        "1D %": x.get("change_pct", x.get("1D %")),
        "20D %": x.get("20D_return_pct", x.get("20D %")),
        "vs 20D SMA %": x.get("vs_20D_SMA_pct", x.get("vs 20D SMA %")),
        "Vol / 20D": x.get("volume_vs_20D", x.get("Vol / 20D")),
        "RSI": x.get("RSI14"),
        "News": x["linked_news"],
    })

st.markdown('<div class="si-kicker">Ranked watchlist</div>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.markdown('<div class="si-kicker" style="margin-top:1.5rem">Research notes</div>', unsafe_allow_html=True)
for x in ranked:
    with st.expander(f'{x["ticker"]} · {badge(x["research_label"])} · {x["research_score"]}/100'):
        st.write(" · ".join(x["research_reasons"]))
        st.caption("Evidence-aware news weighting: disputed items are ignored, insufficient-evidence items receive reduced weight, and supported/corroborated items receive stronger weight.")
