import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import streamlit as st

from news_intelligence import enrich_news

IST = ZoneInfo("Asia/Kolkata")

NEWS_FEEDS = [
    ("India Markets", "https://news.google.com/rss/search?q=India%20stock%20market%20NSE%20Nifty&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RBI / Economy", "https://news.google.com/rss/search?q=RBI%20India%20economy%20markets&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Indian Companies", "https://news.google.com/rss/search?q=Indian%20stocks%20earnings%20results%20companies&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Global Markets", "https://news.google.com/rss/search?q=US%20markets%20Asia%20markets%20Fed%20oil%20geopolitics&hl=en-IN&gl=IN&ceid=IN:en"),
]

st.set_page_config(page_title="MarketPilot • News Intelligence", page_icon="📰", layout="wide")

st.title("📰 News Intelligence")
st.caption("Live headline stream with cautious cross-source corroboration and market-impact tagging.")


@st.cache_data(ttl=60, show_spinner=False)
def load_news():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                pub = entry.get("source", {})
                pub_name = pub.get("title", "") if isinstance(pub, dict) else ""
                items.append({
                    "title": entry.get("title", "").strip(),
                    "source": source,
                    "publisher": pub_name,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception:
            pass
    return enrich_news(items[:32])


news = load_news()
now = datetime.now(IST)
st.caption(f"Updated {now.strftime('%d %b %Y, %H:%M:%S IST')} • auto-refresh every 60 seconds")

if news:
    verified = sum(1 for n in news if n.get("verification") == "CORROBORATED")
    single = sum(1 for n in news if n.get("verification") == "SINGLE_SOURCE")
    c1, c2, c3 = st.columns(3)
    c1.metric("Headlines", len(news))
    c2.metric("Corroborated", verified)
    c3.metric("Single source", single)

    st.subheader("⚡ Live stream")
    ticker = []
    for item in news[:16]:
        label = item.get("verification_label", "⚠️ UNVERIFIED")
        impact = item.get("impact", "NEUTRAL")
        affected = item.get("affected", "MARKET")
        title = html.escape(item.get("title", ""))
        ticker.append(f"<span style='margin-right:36px'><b>{html.escape(label)}</b> <b>{html.escape(impact)}</b> [{html.escape(affected)}] {title}</span>")
    st.markdown(
        "<div style='width:100%;overflow:hidden;border:1px solid rgba(128,128,128,.22);border-radius:14px;padding:12px 0;background:rgba(128,128,128,.08)'>"
        "<div style='display:inline-block;white-space:nowrap;padding-left:100%;animation:mpNews 180s linear infinite;font-size:15px'>"
        + " • ".join(ticker)
        + "</div></div>"
        "<style>@keyframes mpNews {from{transform:translateX(0)}to{transform:translateX(-100%)}}</style>",
        unsafe_allow_html=True,
    )
    st.caption("Corroborated = similar reporting found across at least two publisher domains. This is evidence of corroboration, not proof of truth. Hovering may not pause this secondary page ticker on all browsers.")

    st.subheader("🔎 Headline intelligence")
    for item in news[:20]:
        label = item.get("verification_label", "⚠️ UNVERIFIED")
        impact = item.get("impact", "NEUTRAL")
        affected = item.get("affected", "MARKET")
        publisher = item.get("publisher") or item.get("source", "")
        title = item.get("title", "")
        link = item.get("link", "")
        headline = f"[{title}]({link})" if link else title
        st.markdown(f"### {label}  •  {impact}  •  {affected}")
        st.markdown(f"**{headline}**")
        st.caption(f"{publisher} • {item.get('published','')}")
        st.write(item.get("verification_detail", ""))
        st.write(item.get("impact_reason", ""))
        st.divider()
else:
    st.warning("No live news was retrieved from the free feeds right now.")
