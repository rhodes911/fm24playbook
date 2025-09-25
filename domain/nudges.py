from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from .models import Context, MatchStage, ScoreState, PlayerReaction


def _get_individual_statement(category: str) -> str:
    """Get a random individual talk statement from JSON configuration."""
    try:
        config_path = Path(__file__).parent.parent / "data" / "rules" / "normalized" / "statements.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        statements = data.get("IndividualTalk", {}).get(category, [])
        return random.choice(statements) if statements else f"[{category} statement needed]"
    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        # Fallback for missing JSON
        fallbacks = {
            "Faith": "I've got faith in you.",
            "Challenge": "I expect more.",
            "Encourage": "You can do it."
        }
        return fallbacks.get(category, f"[{category} statement needed]")

def generate_nudges(ctx: Context) -> List[str]:
    """Produce simple micro-targeting nudges based on available signals.

    Since we don't have full per-player telemetry here, we derive generic, actionable hints.
    """
    hints: List[str] = []
    # Player reactions: quick individual-talk guidance
    if PlayerReaction.NERVOUS in ctx.player_reactions:
        faith_statement = _get_individual_statement("Faith")
        hints.append(f"One looks nervous — speak to them individually with faith: Outstretched Arms • '{faith_statement}'")
        hints.append("Consider Hands Together to reduce pressure on that player.")
    if PlayerReaction.COMPLACENT in ctx.player_reactions:
        challenge_statement = _get_individual_statement("Challenge")
        hints.append(f"If someone is complacent, go assertive to reset standards (Point Finger: '{challenge_statement}').")
    if PlayerReaction.LACKING_BELIEF in ctx.player_reactions:
        encourage_statement = _get_individual_statement("Encourage")
        hints.append(f"Low belief detected — supportive message to individuals can help ('{encourage_statement}').")
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
        encourage_statement = _get_individual_statement("Encourage")
        hints.append(f"Individual ST (composed): Pump Fists — '{encourage_statement}'")
    return hints
