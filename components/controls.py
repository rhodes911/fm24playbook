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


def sidebar_context(default: Context | None = None) -> Context:
    st.sidebar.header("Match Context")

    stage = st.sidebar.selectbox(
        "Stage",
        options=[e for e in MatchStage],
        format_func=lambda x: x.value,
        index=list(MatchStage).index(default.stage) if default else 0,
    )

    auto_status = st.sidebar.checkbox(
        "Auto-detect Favourite/Underdog",
        value=(default.auto_fav_status if default else False),
        help="Use positions, form and venue to infer status."
    )
    fav = st.sidebar.radio(
        "Status",
        options=[FavStatus.FAVOURITE, FavStatus.UNDERDOG],
        format_func=lambda x: x.value,
        index=[FavStatus.FAVOURITE, FavStatus.UNDERDOG].index(default.fav_status) if default else 0,
        horizontal=True,
        disabled=auto_status,
    )

    venue = st.sidebar.radio(
        "Venue",
        options=[Venue.HOME, Venue.AWAY],
        format_func=lambda x: x.value,
        index=[Venue.HOME, Venue.AWAY].index(default.venue) if default else 0,
        horizontal=True,
    )

    score_state = st.sidebar.selectbox(
        "Score State",
        options=[None, ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING],
        format_func=lambda x: "—" if x is None else x.value,
        index=[None, ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING].index(default.score_state) if default else 0,
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
        )

    use_score = st.sidebar.checkbox("Enter current score", value=bool(default and (default.team_goals is not None and default.opponent_goals is not None)))
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
            )
        with c2:
            opponent_goals = st.number_input(
                "Opponent goals",
                min_value=0,
                max_value=20,
                step=1,
                value=default.opponent_goals if (default and default.opponent_goals is not None) else 0,
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
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("League Context (Optional)")
    use_positions = st.sidebar.checkbox(
        "Add league positions",
        value=bool(default and (default.team_position is not None or default.opponent_position is not None)),
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
    )
    team_form = None
    opponent_form = None
    if use_form:
        team_form = st.sidebar.text_input(
            "Your Form (e.g., WWDLD)",
            value=(default.team_form or "") if default else "",
            max_chars=5,
            help="Use letters W/D/L (latest on the right).",
        )
        opponent_form = st.sidebar.text_input(
            "Opponent Form (e.g., LWWDL)",
            value=(default.opponent_form or "") if default else "",
            max_chars=5,
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
    return ctx