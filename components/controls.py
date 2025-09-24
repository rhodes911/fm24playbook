"""
Sidebar controls component for selecting context.
Stateless: reads/writes state through return values.
"""
from __future__ import annotations

import streamlit as st
from typing import List

from domain.models import (
    Context, MatchStage, FavStatus, Venue, ScoreState, SpecialSituation, PlayerReaction, TalkAudience
)
from domain.rules_engine import detect_fav_status
from services.repository import PlaybookRepository
from services.session import serialize_context, deserialize_context


def _apply_context_to_session(ctx: Context) -> None:
    """Populate Streamlit session_state with values from a Context for all sidebar widgets."""
    st.session_state["stage"] = ctx.stage
    st.session_state["auto_status"] = ctx.auto_fav_status
    st.session_state["fav"] = ctx.fav_status
    st.session_state["venue"] = ctx.venue
    st.session_state["score_state"] = ctx.score_state
    st.session_state["talk_audience"] = ctx.preferred_talk_audience
    # toggles
    st.session_state["use_score"] = bool(ctx.team_goals is not None and ctx.opponent_goals is not None)
    st.session_state["team_goals"] = ctx.team_goals if ctx.team_goals is not None else 0
    st.session_state["opponent_goals"] = ctx.opponent_goals if ctx.opponent_goals is not None else 0
    st.session_state["specials"] = ctx.special_situations
    st.session_state["reactions"] = ctx.player_reactions
    st.session_state["use_positions"] = bool(ctx.team_position is not None or ctx.opponent_position is not None)
    st.session_state["team_position"] = ctx.team_position if ctx.team_position is not None else 1
    st.session_state["opponent_position"] = ctx.opponent_position if ctx.opponent_position is not None else 1
    st.session_state["use_form"] = bool(ctx.team_form or ctx.opponent_form)
    st.session_state["team_form"] = ctx.team_form or ""
    st.session_state["opponent_form"] = ctx.opponent_form or ""


def sidebar_context(default: Context | None = None) -> Context:
    # Handle any pending preset/reset BEFORE instantiating widgets
    if "_pending_ctx" in st.session_state:
        try:
            pending_data = st.session_state.pop("_pending_ctx")
            applied = deserialize_context(pending_data)
            _apply_context_to_session(applied)
        except Exception:
            # Ignore malformed pending state
            st.session_state.pop("_pending_ctx", None)

    st.sidebar.header("Match Context")

    stage = st.sidebar.selectbox(
        "Stage",
        options=[e for e in MatchStage],
        format_func=lambda x: x.value,
        index=list(MatchStage).index(default.stage) if default else 0,
        key="stage",
    )

    auto_status = st.sidebar.checkbox(
        "Auto-detect Favourite/Underdog",
        value=(default.auto_fav_status if default else False),
        help="Use positions, form and venue to infer status."
    , key="auto_status")
    fav = st.sidebar.radio(
        "Status",
        options=[FavStatus.FAVOURITE, FavStatus.UNDERDOG],
        format_func=lambda x: x.value,
        index=[FavStatus.FAVOURITE, FavStatus.UNDERDOG].index(default.fav_status) if default else 0,
        horizontal=True,
        disabled=auto_status,
        key="fav",
    )

    venue = st.sidebar.radio(
        "Venue",
        options=[Venue.HOME, Venue.AWAY],
        format_func=lambda x: x.value,
        index=[Venue.HOME, Venue.AWAY].index(default.venue) if default else 0,
        horizontal=True,
        key="venue",
    )

    score_state = st.sidebar.selectbox(
        "Score State",
        options=[None, ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING],
        format_func=lambda x: "—" if x is None else x.value,
        index=[None, ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING].index(default.score_state) if default else 0,
        key="score_state",
    )

    preferred_talk_audience = None
    if stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        preferred_talk_audience = st.sidebar.selectbox(
            "Talk to",
            options=[None, TalkAudience.TEAM, TalkAudience.DEFENCE, TalkAudience.MIDFIELD, TalkAudience.ATTACK, TalkAudience.INDIVIDUAL],
            format_func=lambda x: "(auto)" if x is None else x.value,
            index=[None, TalkAudience.TEAM, TalkAudience.DEFENCE, TalkAudience.MIDFIELD, TalkAudience.ATTACK, TalkAudience.INDIVIDUAL].index(
                default.preferred_talk_audience) if (default and default.preferred_talk_audience in [TalkAudience.TEAM, TalkAudience.DEFENCE, TalkAudience.MIDFIELD, TalkAudience.ATTACK, TalkAudience.INDIVIDUAL]) else 0,
            help="Optionally target the statement to a line or individual; leave as (auto) to use rule data.",
            key="talk_audience",
        )

    use_score = st.sidebar.checkbox("Enter current score", value=bool(default and (default.team_goals is not None and default.opponent_goals is not None)), key="use_score")
    team_goals = None
    opponent_goals = None
    if use_score:
        c1, c2 = st.sidebar.columns(2)
        with c1:
            team_goals = st.number_input(
                "Your goals",
                min_value=0,
                max_value=20,
                step=1,
                value=default.team_goals if (default and default.team_goals is not None) else 0,
                key="team_goals",
            )
        with c2:
            opponent_goals = st.number_input(
                "Opponent goals",
                min_value=0,
                max_value=20,
                step=1,
                value=default.opponent_goals if (default and default.opponent_goals is not None) else 0,
                key="opponent_goals",
            )

    specials: List[SpecialSituation] = st.sidebar.multiselect(
        "Special Situations",
        options=[
            SpecialSituation.DERBY,
            SpecialSituation.CUP,
            SpecialSituation.PROMOTION,
            SpecialSituation.RELEGATION,
            SpecialSituation.DOWN_TO_10,
            SpecialSituation.OPPONENT_DOWN_TO_10,
        ],
        format_func=lambda x: x.value,
        default=default.special_situations if default else [],
        key="specials",
    )

    reactions: List[PlayerReaction] = st.sidebar.multiselect(
        "Player Reactions",
        options=[
            PlayerReaction.COMPLACENT,
            PlayerReaction.NERVOUS,
            PlayerReaction.LACKING_BELIEF,
            PlayerReaction.FIRED_UP,
            PlayerReaction.SWITCHED_OFF,
        ],
        format_func=lambda x: x.value,
        default=default.player_reactions if default else [],
        key="reactions",
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("League Context (Optional)")
    use_positions = st.sidebar.checkbox(
        "Add league positions",
        value=bool(default and (default.team_position is not None or default.opponent_position is not None)),
        key="use_positions",
    )
    team_position = None
    opponent_position = None
    if use_positions:
        team_position = st.sidebar.number_input(
            "Your League Position",
            min_value=1,
            max_value=100,
            value=default.team_position if (default and default.team_position is not None) else 1,
            step=1,
            help="Enter your current position in the table.",
            key="team_position",
        )
        opponent_position = st.sidebar.number_input(
            "Opponent League Position",
            min_value=1,
            max_value=100,
            value=default.opponent_position if (default and default.opponent_position is not None) else 1,
            step=1,
            key="opponent_position",
        )

    use_form = st.sidebar.checkbox(
        "Add recent form (last 5)",
        value=bool(default and (default.team_form or default.opponent_form)),
        key="use_form",
    )
    team_form = None
    opponent_form = None
    if use_form:
        team_form = st.sidebar.text_input(
            "Your Form (e.g., WWDLD)",
            value=(default.team_form or "") if default else "",
            max_chars=5,
            help="Use letters W/D/L (latest on the right).",
            key="team_form",
        )
        opponent_form = st.sidebar.text_input(
            "Opponent Form (e.g., LWWDL)",
            value=(default.opponent_form or "") if default else "",
            max_chars=5,
            key="opponent_form",
        )

    ctx = Context(
        stage=stage,
        fav_status=fav,
        venue=venue,
        score_state=score_state,
        special_situations=specials,
        player_reactions=reactions,
        team_position=team_position,
        opponent_position=opponent_position,
        team_form=team_form,
        opponent_form=opponent_form,
        team_goals=team_goals,
        opponent_goals=opponent_goals,
        auto_fav_status=auto_status,
        preferred_talk_audience=preferred_talk_audience,
    )
    # Show derived status hint when auto is enabled
    if auto_status:
        derived, expl = detect_fav_status(ctx)
        st.sidebar.caption(f"Detected: {derived.value} • {expl}")
        ctx.fav_status = derived

    # Presets & Reset controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Presets")
    repo = PlaybookRepository()
    presets = repo.load_presets()
    preset_names = [p["name"] for p in presets if isinstance(p, dict) and "name" in p]
    col1, col2 = st.sidebar.columns([2, 1])
    with col1:
        preset_name = st.text_input("Preset name", value=st.session_state.get("preset_name", ""), key="preset_name")
    with col2:
        if st.button("Save", use_container_width=True):
            if preset_name and preset_name.strip():
                payload = serialize_context(ctx)
                # Upsert preset
                try:
                    repo.upsert_preset(preset_name.strip(), payload)
                    st.sidebar.success("Preset saved.")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Failed to save preset: {e}")
            else:
                st.sidebar.warning("Enter a preset name first.")
    sel = st.sidebar.selectbox("Load preset", options=["—"] + preset_names)
    if sel != "—":
        chosen = next((p for p in presets if p.get("name") == sel), None)
        data_preview = chosen.get("data") if isinstance(chosen, dict) else None
        with st.sidebar.expander("Preset details"):
            if data_preview:
                # Basic presence indicators
                has_positions = (data_preview.get("team_position") is not None) or (data_preview.get("opponent_position") is not None)
                has_form = bool(data_preview.get("team_form") or data_preview.get("opponent_form"))
                st.write({
                    "stage": data_preview.get("stage"),
                    "fav_status": data_preview.get("fav_status"),
                    "venue": data_preview.get("venue"),
                    "score_state": data_preview.get("score_state"),
                    "has_positions": has_positions,
                    "has_form": has_form,
                })
                if not has_positions:
                    st.caption("Positions not set in this preset.")
                if not has_form:
                    st.caption("Form not set in this preset.")
    c1, c2 = st.sidebar.columns([1, 1])
    with c1:
        if st.button("Apply", use_container_width=True):
            if sel != "—":
                chosen = next((p for p in presets if p.get("name") == sel), None)
                if chosen and "data" in chosen:
                    # Defer application until next run to avoid touching instantiated widgets
                    st.session_state["_pending_ctx"] = chosen["data"]
                    st.rerun()
    with c2:
        if st.button("Reset", use_container_width=True):
            base = default or Context(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
            st.session_state["_pending_ctx"] = serialize_context(base)
            st.rerun()
    return ctx