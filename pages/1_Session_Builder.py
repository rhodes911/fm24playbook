import streamlit as st
from datetime import datetime
from typing import Optional

from domain.models import Context, MatchStage, FavStatus, Venue, ScoreState
from services.session import SessionManager


def stage_from_minute(minute: Optional[int]) -> MatchStage:
    if minute is None:
        return MatchStage.PRE_MATCH
    if minute <= 0:
        return MatchStage.PRE_MATCH
    if minute < 25:
        return MatchStage.EARLY
    if minute < 65:
        return MatchStage.MID
    if minute < 85:
        return MatchStage.LATE
    if minute < 90:
        return MatchStage.VERY_LATE
    return MatchStage.FULL_TIME


st.title("🧱 Session Builder")
st.caption("Log snapshots and build a match session on a single page. Submit once per match.")

sm = SessionManager()
active = sm.get_active()

with st.container():
    st.subheader("Match meta")
    col1, col2, col3 = st.columns(3)
    with col1:
        opponent = st.text_input("Opponent", value=(active or {}).get("name", ""))
    with col2:
        venue = st.selectbox("Venue", options=[v.value for v in Venue], index=1 if (active and active.get("context", {}).get("venue") == "Away") else 0)
    with col3:
        is_fav = st.selectbox("Status", options=[FavStatus.FAVOURITE.value, FavStatus.UNDERDOG.value], index=0)

    start_col, resume_col = st.columns([1, 1])
    with start_col:
        if st.button("Start New Session", type="primary", disabled=bool(active) or not opponent.strip()):
            ctx = Context(
                stage=MatchStage.PRE_MATCH,
                fav_status=FavStatus.FAVOURITE if is_fav == FavStatus.FAVOURITE.value else FavStatus.UNDERDOG,
                venue=Venue(venue),
                minute=0,
            )
            st.session_state["_session"] = sm.start(ctx, name=opponent.strip())
            st.experimental_rerun()
    with resume_col:
        if active and st.button("Resume Active Session"):
            st.session_state["_session"] = active
            st.experimental_rerun()


active = sm.get_active()
if not active:
    st.info("No active session. Enter opponent and click 'Start New Session'.")
    st.stop()

# Snapshot form
st.divider()
st.subheader("Add Snapshot")
c1, c2, c3, c4 = st.columns(4)
with c1:
    minute = st.number_input("Minute", min_value=0, max_value=120, value=25, step=1)
with c2:
    team_goals = st.number_input("Goals For", min_value=0, max_value=20, value=0, step=1)
with c3:
    opp_goals = st.number_input("Goals Against", min_value=0, max_value=20, value=0, step=1)
with c4:
    possession = st.number_input("Possession %", min_value=0, max_value=100, value=50, step=1)

c5, c6, c7, c8 = st.columns(4)
with c5:
    shots_for = st.number_input("Shots For", min_value=0, max_value=50, value=0, step=1)
with c6:
    shots_against = st.number_input("Shots Against", min_value=0, max_value=50, value=0, step=1)
with c7:
    sot_for = st.number_input("On Target For", min_value=0, max_value=50, value=0, step=1)
with c8:
    sot_against = st.number_input("On Target Against", min_value=0, max_value=50, value=0, step=1)

c9, c10 = st.columns(2)
with c9:
    xg_for = st.number_input("xG For", min_value=0.0, max_value=15.0, value=0.0, step=0.05, format="%.2f")
with c10:
    xg_against = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=0.0, step=0.05, format="%.2f")

if st.button("Add Snapshot"):
    # derive score_state for quick reference
    score_state = None
    if team_goals > opp_goals:
        score_state = ScoreState.WINNING.value
    elif team_goals < opp_goals:
        score_state = ScoreState.LOSING.value
    else:
        score_state = ScoreState.DRAWING.value
    sm.append_event({
        "type": "snapshot",
        "minute": int(minute),
        "payload": {
            "minute": int(minute),
            "score_for": int(team_goals),
            "score_against": int(opp_goals),
            "score_state": score_state,
            "possession_pct": float(possession),
            "shots_for": int(shots_for),
            "shots_against": int(shots_against),
            "shots_on_target_for": int(sot_for),
            "shots_on_target_against": int(sot_against),
            "xg_for": float(xg_for),
            "xg_against": float(xg_against),
        }
    })
    st.success(f"Snapshot added for {minute}'")


# Timeline
st.divider()
st.subheader("Timeline")
active = sm.get_active() or {}
events = active.get("events", [])
if not events:
    st.caption("No events yet. Add your first snapshot above.")
else:
    for e in sorted(events, key=lambda x: (x.get("minute", 0), x.get("ts", ""))):
        minute_label = f"{e.get('minute', 0)}'" if e.get("minute") is not None else "—"
        if e.get("type") == "snapshot":
            p = e.get("payload", {})
            score = f"{p.get('score_for', 0)}–{p.get('score_against', 0)}"
            stats = f"Poss {int(p.get('possession_pct', 0))}% | Shots {p.get('shots_for', 0)}({p.get('shots_on_target_for', 0)}) vs {p.get('shots_against', 0)}({p.get('shots_on_target_against', 0)}) | xG {p.get('xg_for', 0.0):.2f} vs {p.get('xg_against', 0.0):.2f}"
            st.write(f"- {minute_label} Snapshot — {score} • {stats}")
        else:
            st.write(f"- {minute_label} {e.get('type').title()} — {e.get('payload', {})}")


# Complete session
st.divider()
st.subheader("Submit Session")
notes = st.text_area("Notes (optional)")
cols = st.columns([1, 1, 2])
with cols[0]:
    if st.button("Submit & Archive", type="primary"):
        session = sm.complete(notes=notes)
        st.success(f"Session {session.get('id')} archived at {datetime.utcnow().isoformat()}Z")
        st.info("You can start a new session above.")
with cols[1]:
    if st.button("Cancel Active Session", type="secondary"):
        from services.session import ACTIVE_FILE
        if ACTIVE_FILE.exists():
            ACTIVE_FILE.unlink(missing_ok=True)
        st.warning("Active session cancelled.")
        st.experimental_rerun()
