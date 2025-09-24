from __future__ import annotations

from typing import List

from .models import Context, MatchStage, ScoreState, PlayerReaction


def generate_nudges(ctx: Context) -> List[str]:
    """Produce simple micro-targeting nudges based on available signals.

    Since we don't have full per-player telemetry here, we derive generic, actionable hints.
    """
    hints: List[str] = []
    # Player reactions: quick individual-talk guidance
    if PlayerReaction.NERVOUS in ctx.player_reactions:
        hints.append("One looks nervous — speak to them individually with faith: Outstretched Arms • 'I've got faith in you.'")
        hints.append("Consider Hands Together to reduce pressure on that player.")
    if PlayerReaction.COMPLACENT in ctx.player_reactions:
        hints.append("If someone is complacent, go assertive to reset standards (Point Finger: 'I expect more.').")
    if PlayerReaction.LACKING_BELIEF in ctx.player_reactions:
        hints.append("Low belief detected — supportive message to individuals can help ('You can do it.').")
    # Discipline cautions
    if ctx.cards_yellow >= 3:
        hints.append("Warn booked defenders about tackles.")
    if ctx.cards_red > 0:
        hints.append("Reinforce shape after the red card; encourage composure.")
    # Injuries/workload
    if ctx.injuries >= 1:
        hints.append("Check stamina on key runners; plan early sub if fading.")
    # Form/momentum proxy
    if ctx.xthreat_delta is not None:
        if ctx.xthreat_delta >= 0.25:
            hints.append("Praise high performers; keep pressing triggers.")
        elif ctx.xthreat_delta <= -0.25:
            hints.append("Encourage low‑confidence attackers; simplify instructions.")
    # Morale trend
    if ctx.morale_trend is not None and ctx.morale_trend <= -1:
        hints.append("Use supportive tone with youngsters and fringe players.")

    # Role-specific nudge (common FM pattern): striker motivation
    if ctx.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME) and (
        ctx.score_state in (ScoreState.DRAWING, ScoreState.LOSING) or ctx.score_state is None
    ):
        hints.append("Individual ST (composed): Pump Fists — 'You can make the difference.'")
    return hints
