import streamlit as st
from domain.models import Context, MatchStage, FavStatus, Venue
from services.repository import PlaybookRepository
from services.session import SessionManager, deserialize_context, serialize_context
from domain.rules_engine import recommend
from components.controls import sidebar_context
from components.cards import recommendation_card

st.set_page_config(page_title="Match Session", page_icon="⏱️")
st.title("⏱️ Match Session (single active)")

repo = PlaybookRepository()
sm = SessionManager()
active = sm.get_active()

if active is None:
    st.info("No active session. Configure your context and start a new one.")
    _default_ctx = Context(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    ctx = sidebar_context(default=_default_ctx)
    sess_name = st.text_input("Session name (e.g., 'League vs Halifax 2025-12-31')")
    if st.button("Start Session", type="primary"):
        if not sess_name or not sess_name.strip():
            st.error("Please enter a session name before starting.")
        else:
            try:
                sm.start(ctx, name=sess_name)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start session: {e}")
else:
    st.success(f"Active session: {active['id']} (started {active['started_at']})")
    locked_ctx = deserialize_context(active["context"])
    st.caption("Context locked for this session:")
    st.code(serialize_context(locked_ctx))
    try:
        playbook = repo.load_playbook()
    except Exception as e:
        st.error(f"Failed to load playbook: {e}")
        st.stop()

    rec = recommend(locked_ctx, playbook)
    if rec is None:
        st.warning("No recommendation found for this context.")
    else:
        recommendation_card(rec)
        st.markdown("### Stage action confirmation")
        st.caption("Confirm only what you actually performed in-game.")
        # Explicit stage action submission flow
        action_col1, action_col2, action_col3 = st.columns([1,1,2])
        with action_col1:
            if st.button(f"Confirm: {locked_ctx.stage.value}"):
                sm.append_event({
                    "type": "stage_action",
                    "stage": locked_ctx.stage.value,
                    "mentality": rec.mentality.value,
                    "gesture": rec.gesture,
                    "talk": rec.team_talk,
                    "audience": rec.talk_audience.value if rec.talk_audience else None,
                    "shout": rec.shout.value,
                })
        with action_col2:
            if st.button("Worked 👍"):
                sm.append_event({"type": "worked", "stage": locked_ctx.stage.value})
            if st.button("Didn’t work 👎"):
                sm.append_event({"type": "didnt_work", "stage": locked_ctx.stage.value})
        with action_col3:
            note = st.text_input("Add note for this stage")
            if st.button("Save note"):
                sm.append_event({"type": "note", "stage": locked_ctx.stage.value, "text": note})

    st.markdown("---")
    oc = st.selectbox("Final outcome", options=[None, "win", "draw", "loss"], format_func=lambda x: "—" if x is None else x)
    summary = st.text_area("Session summary (optional)")
    if st.button("Complete Session", type="primary"):
        sm.complete(outcome=oc, notes=summary)
        st.rerun()
