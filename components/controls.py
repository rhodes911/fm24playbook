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
from services.repository import Repository
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
    # time and stats
    initial_minute = ctx.minute if ctx.minute is not None else 0
    st.session_state["minute_slider"] = initial_minute
    st.session_state["minute_input"] = initial_minute
    st.session_state["auto_stage_from_minute"] = False
    st.session_state["use_live_stats"] = bool(
        ctx.possession_pct is not None
        or ctx.shots_for is not None
        or ctx.shots_against is not None
        or ctx.shots_on_target_for is not None
        or ctx.shots_on_target_against is not None
        or ctx.xg_for is not None
        or ctx.xg_against is not None
    )
    st.session_state["possession_pct"] = ctx.possession_pct or 0
    st.session_state["shots_for"] = ctx.shots_for or 0
    st.session_state["shots_against"] = ctx.shots_against or 0
    st.session_state["shots_on_target_for"] = ctx.shots_on_target_for or 0
    st.session_state["shots_on_target_against"] = ctx.shots_on_target_against or 0
    st.session_state["xg_for"] = ctx.xg_for or 0.0
    st.session_state["xg_against"] = ctx.xg_against or 0.0
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

    # Minute slider controls stage (optional)
    st.sidebar.subheader("Time")
    c_time1, c_time2, c_time3 = st.sidebar.columns([2, 1, 1])
    with c_time1:
        minute_slider = st.slider(
            "Minute",
            min_value=0,
            max_value=120,
            value=(default.minute if default and isinstance(default.minute, int) else 0),
            step=1,
            key="minute_slider",
        )
    with c_time2:
        minute_input = st.number_input(
            "Type minute",
            min_value=0,
            max_value=120,
            step=1,
            value=(default.minute if default and isinstance(default.minute, int) else 0),
            key="minute_input",
        )
    with c_time3:
        auto_stage_from_minute = st.checkbox("Auto stage", value=True, help="Derive the match stage from the minute slider.", key="auto_stage_from_minute")

    def stage_from_minute(m: int) -> MatchStage:
        # Pre-match exactly at 0
        if m == 0:
            return MatchStage.PRE_MATCH
        # 1-24
        if m < 25:
            return MatchStage.EARLY
        # 25-44
        if m < 45:
            return MatchStage.MID
        # 45
        if m == 45:
            return MatchStage.HALF_TIME
        # 46-64
        if m < 65:
            return MatchStage.MID
        # 65-84
        if m < 85:
            return MatchStage.LATE
        # 85-89
        if m < 90:
            return MatchStage.VERY_LATE
        # 90
        if m == 90:
            return MatchStage.FULL_TIME
        # 91-104
        if m < 105:
            return MatchStage.ET_FIRST_HALF
        # 105
        if m == 105:
            return MatchStage.ET_HALF_TIME
        # 106-119
        if m < 120:
            return MatchStage.ET_SECOND_HALF
        # 120
        return MatchStage.FULL_TIME

    # Resolve minute from inputs (typed value takes precedence)
    minute = int(minute_input) if isinstance(minute_input, int) else int(minute_slider)

    # Stage selection with optional auto mapping
    if auto_stage_from_minute:
        stage = stage_from_minute(minute)
        st.sidebar.caption(f"Auto stage: {stage.value}")
    else:
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

    # Optional live match stats
    st.sidebar.markdown("---")
    st.sidebar.subheader("Live Stats (Optional)")
    use_live_stats = st.sidebar.checkbox("Add possession/shots/xG", value=False, key="use_live_stats")
    possession_pct = None
    shots_for = shots_against = shots_on_target_for = shots_on_target_against = None
    xg_for = xg_against = None
    if use_live_stats:
        c_s1, c_s2 = st.sidebar.columns(2)
        with c_s1:
            possession_pct = st.number_input("Possession %", min_value=0, max_value=100, value=int(default.possession_pct) if (default and isinstance(default.possession_pct, (int, float))) else 50, step=1, key="possession_pct")
            shots_for = st.number_input("Shots For", min_value=0, max_value=50, value=default.shots_for or 0, step=1, key="shots_for")
            shots_on_target_for = st.number_input("On Target For", min_value=0, max_value=50, value=default.shots_on_target_for or 0, step=1, key="shots_on_target_for")
            xg_for = st.number_input("xG For", min_value=0.0, max_value=10.0, value=float(default.xg_for or 0.0), step=0.05, key="xg_for")
        with c_s2:
            shots_against = st.number_input("Shots Against", min_value=0, max_value=50, value=default.shots_against or 0, step=1, key="shots_against")
            shots_on_target_against = st.number_input("On Target Against", min_value=0, max_value=50, value=default.shots_on_target_against or 0, step=1, key="shots_on_target_against")
            xg_against = st.number_input("xG Against", min_value=0.0, max_value=10.0, value=float(default.xg_against or 0.0), step=0.05, key="xg_against")

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
        minute=minute,
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
        possession_pct=possession_pct,
        shots_for=shots_for,
        shots_against=shots_against,
        shots_on_target_for=shots_on_target_for,
        shots_on_target_against=shots_on_target_against,
        xg_for=xg_for,
        xg_against=xg_against,
    )
    # Show derived status hint when auto is enabled
    if auto_status:
        derived, expl = detect_fav_status(ctx)
        st.sidebar.caption(f"Detected: {derived.value} • {expl}")
        ctx.fav_status = derived

    # Presets & Reset controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Presets")
    repo = Repository()
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