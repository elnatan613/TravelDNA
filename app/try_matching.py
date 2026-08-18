"""
כלי ניסוי ידני למנוע ההתאמה - לא תלוי ב-nlp/ (הצד של דין) בכלל.
מאפשר להזין וקטור מטייל ישירות (סליידר לכל ציר), ולראות דירוג ישירות
מתוך data/processed/destinations.json האמיתי.

זה לא app/demo.py (שם הוקטור מגיע מ-nlp.profile_extractor) - זה כלי צד
שלנו בלבד, לבדוק את matching/matcher.py + הדאטה האמיתי בלי תלות בדין.

הרצה:
    streamlit run app/try_matching.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config import AXES
from matching.matcher import rank_destinations, load_destinations

st.title("TravelDNA - ניסוי ידני למנוע ההתאמה")
st.caption("מזינים וקטור מטייל ישירות (בלי NLP) ורואים דירוג אמיתי מתוך destinations.json")

st.subheader("וקטור המטייל - כל ציר בין 0 ל-1")
traveler_vector = {}
weights = {}
cols = st.columns(2)
for i, axis in enumerate(AXES):
    with cols[0]:
        traveler_vector[axis] = st.slider(axis, 0.0, 1.0, 0.5, 0.05, key=f"val_{axis}")
    with cols[1]:
        weights[axis] = st.slider(f"חשיבות {axis}", 0.0, 3.0, 1.0, 0.5, key=f"w_{axis}")

try:
    destinations = load_destinations()
except FileNotFoundError:
    st.error("לא נמצא data/processed/destinations.json - הרץ קודם python scripts/destination_scraper.py")
    destinations = []

if destinations:
    ranked = rank_destinations(traveler_vector, weights, destinations)
    st.subheader(f"דירוג ({len(ranked)} ערים)")
    for r in ranked:
        with st.expander(f"{r['city']} ({r.get('country', '')}) - מרחק: {r['distance']}"):
            st.json(r["axes"])
            st.write(f"kosher_availability: {r.get('kosher_availability', 'N/A')}")
