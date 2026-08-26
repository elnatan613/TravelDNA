"""
דמו בסיסי ב-Streamlit - מחבר בין חלק ה-NLP לחלק ההתאמה.
זה השלד שמאפשר לבדוק end-to-end מוקדם, גם עם ערכי דמה בשני הצדדים.

הרצה: streamlit run app/demo.py
"""

import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config import AXES
from nlp.profile_extractor import build_travel_profile, extract_importance_weights
from matching.matcher import rank_destinations, load_destinations

AXIS_LABELS = {
    "urban": "סביבה עירונית",
    "culture": "תרבות ואתרים",
    "nightlife": "בילויים בערב",
    "social": "פעילויות חברתיות",
    "activity_density": "קצב ועמוס הפעילויות",
    "food": "אוכל וקולינריה",
    "price_sensitivity": "רגישות למחיר",
}

AXIS_ENDPOINTS = {
    "urban": "1 = טבע וכפר | 5 = עיר",
    "culture": "1 = מעט עניין | 5 = עניין רב",
    "nightlife": "1 = ערב שקט | 5 = חיי לילה",
    "social": "1 = עצמאי ושקט | 5 = חברתי",
    "activity_density": "1 = רגוע | 5 = ימים עמוסים",
    "food": "1 = לא מרכזי | 5 = חשוב מאוד",
    "price_sensitivity": "1 = פתוח ליוקרה | 5 = חשוב לחסוך",
}

st.set_page_config(page_title="TravelDNA", page_icon="✈️")
st.markdown(
    """
    <style>
        .stApp { direction: rtl; }
        .block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 3rem; }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 { text-align: right; }
        .stTextArea textarea { text-align: right; }
        [data-testid="stSlider"] { direction: ltr; }
        [data-testid="stSlider"] label { direction: rtl; text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("TravelDNA - מצא את היעד המושלם בשבילך")

st.subheader("ספר לנו על הטיול המושלם בשבילך")
answer1 = st.text_area("תאר טיול שהיה בשבילך מושלם")
answer2 = st.text_area("מה הדבר שהכי היית רוצה להימנע ממנו?")

st.subheader("מה אתה מעדיף בטיול?")
st.caption("בחר בין 1 ל־5 בכל תחום לפי מה שמתאים לך.")
preference_values = {}
for axis in AXES:
    preference_values[axis] = st.slider(
        AXIS_LABELS[axis], 1, 5, 3
    )
    st.caption(AXIS_ENDPOINTS[axis])

st.subheader("כמה כל דבר חשוב לך?")
st.caption("1 = לא משנה לי בכלל | 5 = קריטי לי")
slider_values = {}
for axis in AXES:
    slider_values[axis] = st.slider(
        f"חשיבות: {AXIS_LABELS[axis]}", 1, 5, 3
    )

requires_kosher = st.checkbox("חשובה לי זמינות כשרות ביעד")

if st.button("מצא לי יעד"):
    open_text = "\n".join(text for text in (answer1, answer2) if text.strip())
    try:
        profile = build_travel_profile(preference_values, open_text)
    except RuntimeError as error:
        st.error(f"לא ניתן לנתח את הטקסט החופשי: {error}")
        st.stop()

    weights = extract_importance_weights(slider_values)

    try:
        destinations = load_destinations()
    except FileNotFoundError:
        st.error("לא נמצא data/processed/destinations.json - הרץ קודם את scripts/destination_scraper.py")
        destinations = []

    if destinations:
        results = rank_destinations(
            profile, weights, destinations, requires_kosher=requires_kosher
        )
        st.subheader("היעדים המומלצים בשבילך:")
        if not results:
            st.info("לא נמצאו יעדים שעומדים בדרישת הכשרות שבחרת.")

        max_distance = math.sqrt(sum(weights.values()))
        for r in results[:5]:
            match_percent = round(100 * max(0, 1 - r["distance"] / max_distance))
            st.write(
                f"**{r['city']}** ({r.get('country', '')}) — "
                f"ציון התאמה: {match_percent}%"
            )
