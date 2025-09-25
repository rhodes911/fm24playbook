"""
Reaction helpers for FM24 Matchday Playbook
"""
import json
from pathlib import Path
from typing import Dict
from .models import PlayerReaction

def _load_reaction_hints() -> Dict[str, str]:
    """Load reaction hints from JSON configuration."""
    try:
        config_path = Path(__file__).parent.parent / "data" / "rules" / "normalized" / "reaction_hints.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback if JSON not available
        return {
            "COMPLACENT": "Challenge effort without tearing confidence.",
            "NERVOUS": "Reduce pressure; supportive tone.",
            "LACKING_BELIEF": "Show faith and outline a simple plan.",
            "FIRED_UP": "Avoid over-agitating; watch for recklessness.",
            "SWITCHED_OFF": "Refocus individuals with clear instructions.",
        }

def get_reaction_hint(reaction: PlayerReaction) -> str:
    """Get reaction hint from JSON configuration."""
    hints = _load_reaction_hints()
    return hints.get(reaction.name, "")