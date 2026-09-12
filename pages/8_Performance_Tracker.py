import streamlit as st
import pandas as pd
from performance_intelligence import fetch_performance
st.set_page_config(page_title="Performance Tracker | MarketPilot", page_icon="📈", layout="wide")
st.markdown("""<style>.stApp{background:#070b12;color:#e7edf5}.block-container{padding-top:1.5rem;max-width:1500px}.mp-title{font-size:2rem;font-weight:800;letter-spacing:-.03em}.mp-sub{color:#8d9aab;margin-bottom:1.2rem}.card{background:#0d131d;border:1px solid #202b3a;border-radius:14px;padding:16px;min-height:105px}.label{color:#8290a3;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}.value{font-size:1.55rem;font-weight:750;margin-top:5px}</style>""",unsafe_allow_html=True)
st.markdown('<div class="mp-title">📈 Thesis Performance</div>',unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Did MarketPilot\'s directional framework actually work? · Historical accuracy · Outcome tracking · Calibration</div>',unsafe_allow_html=True)
if st.button("↻ Refresh performance"): st.cache_data.clear()
data=fetch_performance()
if not data.get("available"):
    st.info("No completed MarketPilot theses are stored yet. Performance tracking will begin automatically once daily intelligence reports accumulate.")
    st.markdown("### How it works")
    st.markdown("1. MarketPilot records its thesis without editing it later.\n2. The next NSE session is measured from open to close.\n3. Bullish/Bearish calls are marked correct when direction agrees with the session move.\n4. Neutral/Wait calls are treated as correct only when the move stays within ±0.75%.\n5. Accuracy is reported only after an outcome is observable.")
    st.caption("This page does not backfill missing history or manufacture a track record.")
    st.stop()
cols=st.columns(5)
metrics=[("TOTAL THESES",data["total_theses"]),("EVALUATED",data["evaluated"]),("PENDING",data["pending"]),("ACCURACY",f"{data['accuracy_pct']:.1f}%" if data["accuracy_pct"] is not None else "—"),("AVG NEXT SESSION",f"{data['avg_next_session_return_pct']:.2f}%" if data["avg_next_session_return_pct"] is not None else "—")]
for col,(label,value) in zip(cols,metrics): col.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)
st.markdown("### Thesis ledger")
table=pd.DataFrame(data["rows"])
if not table.empty:
    table=table.rename(columns={"date":"Date","bias":"Thesis","score":"Decision Score","next_session_return_pct":"Next Session %","result":"Result","status":"Status"})
    st.dataframe(table,use_container_width=True,hide_index=True)
st.markdown("### Methodology")
st.caption("Performance is measured against the next observable NIFTY session. It is a research-quality scorecard, not a backtest, and does not represent trading returns, slippage, costs, or execution quality.")
st.caption(f"Source: {data['source']} · As of {data['as_of']}")
