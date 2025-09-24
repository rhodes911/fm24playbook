import json
import streamlit as st

from services.repository import PlaybookRepository
from domain.models import Context, MatchStage, FavStatus, Venue
from domain.rules_engine import recommend
from components.controls import sidebar_context
from components.banners import context_banner
from components.cards import recommendation_card

st.set_page_config(page_title="Playbook", page_icon="📘")

repo = PlaybookRepository()

# default context for first load
_default_ctx = Context(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
ctx = sidebar_context(default=_default_ctx)

context_banner(ctx)

try:
    playbook = repo.load_playbook()
except Exception as e:
    st.error(f"Failed to load playbook: {e}")
    st.stop()

rec = recommend(ctx, playbook)

if rec is None:
    st.warning("No recommendation found for this context.")
else:
    recommendation_card(rec)

with st.expander("Debug: Raw Playbook Data"):
    try:
        with open(repo.data_dir / "playbook.json", "r", encoding="utf-8") as f:
            st.json(json.load(f))
    except Exception:
        pass