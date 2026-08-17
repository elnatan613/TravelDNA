"""
דמו בסיסי ב-Streamlit - מחבר בין חלק ה-NLP לחלק ההתאמה.
זה השלד שמאפשר לבדוק end-to-end מוקדם, גם עם ערכי דמה בשני הצדדים.

הרצה: streamlit run app/demo.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config import AXES, IMPORTANCE_ANCHORS
from nlp.profile_extractor import extract_profile, extract_importance_weights
from matching.matcher import rank_destinations, load_destinations

st.title("TravelDNA - מצא את היעד המושלם בשבילך")

st.subheader("ספר לנו על הטיול המושלם בשבילך")
answer1 = st.text_area("תאר טיול שהיה בשבילך מושלם")
answer2 = st.text_area("מה הדבר שהכי היית רוצה להימנע ממנו?")

st.subheader("כמה כל דבר חשוב לך?")
slider_values = {}
for axis in AXES:
    slider_values[axis] = st.slider(axis, 1, 5, 3)

if st.button("מצא לי יעד"):
    profile = extract_profile([answer1, answer2])
    weights = extract_importance_weights(slider_values)

    try:
        destinations = load_destinations()
    except FileNotFoundError:
        st.error("לא נמצא data/processed/destinations.json - הרץ קודם את scripts/destination_scraper.py")
        destinations = []

    if destinations:
        results = rank_destinations(profile, weights, destinations)
        st.subheader("היעדים המומלצים בשבילך:")
        for r in results[:5]:
            st.write(f"**{r['city']}** ({r.get('country', '')}) - ציון התאמה: {r['distance']}")
