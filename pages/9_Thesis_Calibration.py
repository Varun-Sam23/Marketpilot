import streamlit as st
import pandas as pd
from calibration_intelligence import fetch_calibration
st.set_page_config(page_title="Thesis Calibration | MarketPilot", page_icon="🎯", layout="wide")
st.markdown("""<style>.stApp{background:#070b12;color:#e7edf5}.block-container{padding-top:1.5rem;max-width:1500px}.mp-title{font-size:2rem;font-weight:800;letter-spacing:-.03em}.mp-sub{color:#8d9aab;margin-bottom:1.2rem}.card{background:#0d131d;border:1px solid #202b3a;border-radius:14px;padding:16px;min-height:105px}.label{color:#8290a3;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}.value{font-size:1.55rem;font-weight:750;margin-top:5px}</style>""",unsafe_allow_html=True)
st.markdown('<div class="mp-title">🎯 Thesis Calibration</div>',unsafe_allow_html=True)
st.markdown('<div class="mp-sub">Accuracy by confidence · bias · market regime · honest sample-size tracking</div>',unsafe_allow_html=True)
if st.button("↻ Refresh calibration"): st.cache_data.clear()
data=fetch_calibration()
if not data.get("available"):
    st.info("Calibration is waiting for MarketPilot to accumulate evaluated historical theses. No historical accuracy is assumed.")
    st.stop()
acc=data.get("overall_accuracy_pct")
c1,c2,c3,c4=st.columns(4)
c1.markdown(f'<div class="card"><div class="label">OVERALL ACCURACY</div><div class="value">{acc:.1f}%</div></div>' if acc is not None else '<div class="card"><div class="label">OVERALL ACCURACY</div><div class="value">—</div></div>',unsafe_allow_html=True)
c2.markdown(f'<div class="card"><div class="label">EVALUATED</div><div class="value">{data["evaluated"]}</div></div>',unsafe_allow_html=True)
c3.markdown(f'<div class="card"><div class="label">TOTAL THESES</div><div class="value">{data["total_theses"]}</div></div>',unsafe_allow_html=True)
c4.markdown('<div class="card"><div class="label">CALIBRATION STATUS</div><div class="value">BUILDING SAMPLE</div></div>',unsafe_allow_html=True)
def section(title,key):
    st.markdown(f"### {title}"); rows=data.get(key,[])
    if not rows: st.caption("Not enough evaluated observations yet."); return
    df=pd.DataFrame(rows).rename(columns={"segment":"Segment","evaluated":"Evaluated","correct":"Correct","accuracy_pct":"Accuracy %","avg_next_session_return_pct":"Avg next-session %"})
    st.dataframe(df,use_container_width=True,hide_index=True)
section("Accuracy by confidence","confidence"); section("Accuracy by directional bias","bias"); section("Accuracy by market regime","regime")
st.info(data["calibration_note"])
st.caption("Calibration uses only previously recorded theses and the next completed NIFTY session. It does not alter historical calls after the outcome is known.")
