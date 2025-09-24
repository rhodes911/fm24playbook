from __future__ import annotations

from typing import Dict, List

from .models import MatchStage


LADDERS: Dict[str, List[str]] = {
    "PreMatch": ["calm", "encourage", "assertive"],
    "HalfTime": ["calm", "encourage", "assertive", "angry"],  # hairdryer last
    "FullTime": ["calm", "praise", "disappointed"],  # conceptual; mapped to gestures later
}


def next_tone(stage: MatchStage, underperformed: bool) -> List[str]:
    """Return the ladder order for the stage; caller can pick a higher rung when underperformed.

    We keep it as metadata; mapping to gestures/phrases is handled elsewhere.
    """
    base = LADDERS.get(stage.value, ["calm", "encourage", "assertive"])
    if underperformed:
        return base  # caller will choose a higher rung than last used
    return base
