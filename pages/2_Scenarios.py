import streamlit as st
from services.repository import PlaybookRepository
from domain.presets import builtin_presets
from components.cards import recommendation_card
from domain.rules_engine import recommend

st.set_page_config(page_title="Scenarios", page_icon="🎯")

repo = PlaybookRepository()

st.title("🎯 Quick Scenarios")

presets = builtin_presets()

cols = st.columns(3)
for i, preset in enumerate(presets):
    with cols[i % 3]:
        if st.button(preset.name, help=preset.description):
            try:
                playbook = repo.load_playbook()
                rec = recommend(preset.context, playbook)
                if rec:
                    st.session_state["last_rec"] = rec
            except Exception as e:
                st.error(f"Error: {e}")

if "last_rec" in st.session_state:
    st.subheader("Last Recommendation")
    recommendation_card(st.session_state["last_rec"])