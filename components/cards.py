"""
Recommendation card component.
"""
from __future__ import annotations

import streamlit as st
from domain.models import Recommendation


def recommendation_card(rec: Recommendation) -> None:
    st.markdown("<div class='recommendation-card'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        st.subheader("Mentality")
        st.markdown(f"**{rec.mentality.value}**")
    with c2:
        st.subheader("Shout")
        st.markdown(f"{rec.shout.value}")
    with c3:
        st.subheader("Gesture")
        st.markdown(f"{rec.gesture}")

    st.subheader("Team Talk")
    if rec.talk_audience:
        st.caption(f"Audience: {rec.talk_audience.value}")
    st.info(rec.team_talk)

    if rec.notes:
        st.subheader("Notes")
        for n in rec.notes:
            st.write(f"- {n}")

    st.markdown("</div>", unsafe_allow_html=True)