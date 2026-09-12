import streamlit as st
import pandas as pd

from institutional_flow import fetch_fii_dii, summarize_flow

st.set_page_config(page_title="Institutional Flow | MarketPilot", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.stApp { background: #070b12; color: #e7edf5; }
.block-container { padding-top: 1.5rem; max-width: 1400px; }
.flow-card { background: #0d131d; border: 1px solid #202b3a; border-radius: 14px; padding: 18px; min-height: 110px; }
.flow-label { color: #7f8da3; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.flow-value { font-size: 27px; font-weight: 700; margin-top: 8px; }
.flow-sub { color: #8d9bad; font-size: 12px; margin-top: 5px; }
.source-strip { background:#111a27; border:1px solid #26364b; border-radius:12px; padding:12px 16px; color:#aebbd0; }
</style>
""", unsafe_allow_html=True)

st.title("🏦 Institutional Flow")
st.caption("FII/DII cash-market activity — evidence-led institutional positioning")

result = fetch_fii_dii()
summary = summarize_flow(result)

if not summary.get("available"):
    st.warning(summary.get("message", "Institutional flow data is currently unavailable."))
    st.info("MarketPilot does not fabricate or silently substitute missing flow data.")
    st.stop()

fresh = summary.get("freshness_days")
fresh_label = "fresh" if fresh is not None and fresh <= 1 else f"{fresh} days old" if fresh is not None else "freshness unknown"
source = summary.get("source", "Unknown")
source_url = summary.get("source_url", "")
st.caption(f"Latest available record: {summary['date']} · Data status: **{fresh_label}**")
st.markdown(f'<div class="source-strip">SOURCE <b>{source}</b> · Provenance is shown explicitly because NSE can block hosted server requests. The dashboard will never hide a fallback source.</div>', unsafe_allow_html=True)
if source_url:
    st.caption(f"Source reference: {source_url}")


def fmt(v):
    try:
        return f"₹{float(v):,.0f} Cr"
    except Exception:
        return "N/A"


today = summary["today"]
five = summary["five_day"]
cols = st.columns(4)
metrics = [
    ("FII NET · TODAY", fmt(today["fii_net"]), summary["fii_tone"]),
    ("DII NET · TODAY", fmt(today["dii_net"]), summary["dii_tone"]),
    ("COMBINED · TODAY", fmt(today["combined_net"]), "NET FLOW"),
    ("5-DAY COMBINED", fmt(five["combined_net"]), summary["regime"]),
]
for col, (label, value, sub) in zip(cols, metrics):
    col.markdown(f'<div class="flow-card"><div class="flow-label">{label}</div><div class="flow-value">{value}</div><div class="flow-sub">{sub}</div></div>', unsafe_allow_html=True)

st.divider()

left, right = st.columns([1, 1])
with left:
    st.subheader("Institutional regime")
    regime = summary["regime"]
    if regime == "INSTITUTIONAL ACCUMULATION":
        st.success("🟢 Institutional accumulation")
    elif regime == "INSTITUTIONAL DISTRIBUTION":
        st.error("🔴 Institutional distribution")
    else:
        st.warning(f"🟡 {regime.title()}")
    st.write("5-day FII net:", fmt(five["fii_net"]))
    st.write("5-day DII net:", fmt(five["dii_net"]))

with right:
    st.subheader("Flow interpretation")
    st.markdown("- **FII positive:** foreign institutions are net buyers in cash equities.")
    st.markdown("- **FII negative:** foreign institutions are net sellers in cash equities.")
    st.markdown("- **DII positive:** domestic institutions are providing net buying support.")
    st.markdown("- **Divergence:** FII and DII positioning disagrees; combine with Market Regime and price structure.")

st.divider()
st.subheader("Recent institutional flow")

df = pd.DataFrame(summary["rows"])
if not df.empty:
    display_cols = {
        "date": "Date", "fii_buy": "FII Buy", "fii_sell": "FII Sell", "fii_net": "FII Net",
        "dii_buy": "DII Buy", "dii_sell": "DII Sell", "dii_net": "DII Net"
    }
    out = df[[c for c in display_cols if c in df]].rename(columns=display_cols)
    for c in out.columns:
        if c != "Date":
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
    st.dataframe(out, use_container_width=True, hide_index=True)

st.caption("Research tool only. Institutional flow is one input; it is not a standalone buy/sell signal. NSE data availability and publication timing can vary.")
