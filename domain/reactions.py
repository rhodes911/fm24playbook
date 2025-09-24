"""
Reaction helpers for FM24 Matchday Playbook
"""
from typing import Dict
from .models import PlayerReaction

DEFAULT_REACTION_HINTS: Dict[PlayerReaction, str] = {
    PlayerReaction.COMPLACENT: "Challenge effort without tearing confidence.",
    PlayerReaction.NERVOUS: "Reduce pressure; supportive tone.",
    PlayerReaction.LACKING_BELIEF: "Show faith and outline a simple plan.",
    PlayerReaction.FIRED_UP: "Avoid over-agitating; watch for recklessness.",
    PlayerReaction.SWITCHED_OFF: "Refocus individuals with clear instructions.",
}

def get_reaction_hint(reaction: PlayerReaction) -> str:
    return DEFAULT_REACTION_HINTS.get(reaction, "")