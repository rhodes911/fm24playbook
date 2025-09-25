from __future__ import annotations

from typing import List
from pathlib import Path
import json

from .models import Context, FavStatus, MatchStage

def _get_catalogs() -> dict:
    """Load catalogs from JSON configuration."""
    try:
        fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "catalogs.json"
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def gesture_tone(gesture: str) -> str:
    """Get tone for gesture from JSON configuration."""
    catalogs = _get_catalogs()
    gestures_by_tone = catalogs.get("gestures", {})
    
    # Find which tone this gesture belongs to
    for tone, gesture_list in gestures_by_tone.items():
        if gesture in gesture_list:
            return tone
    
    # Fallback to calm for unknown gestures
    return "calm"


def score_synergy(target_tone: str, gesture: str, ctx: Context) -> float:
    """Score 0..1 how well the gesture matches the target tone in given context."""
    g_tone = gesture_tone(gesture)
    score = 0.5
    if g_tone == target_tone:
        score += 0.3
    # Opposites penalty: calm vs assertive/angry
    if (g_tone == "calm" and target_tone in ("assertive", "angry")) or (
        target_tone == "calm" and g_tone in ("assertive", "angry")
    ):
        score -= 0.2
    # Context nudges
    if ctx.fav_status == FavStatus.FAVOURITE and target_tone in ("assertive", "motivational"):
        score += 0.05
    if ctx.fav_status == FavStatus.UNDERDOG and target_tone in ("calm", "encourage"):
        score += 0.05
    if ctx.stage == MatchStage.PRE_MATCH and target_tone == "angry":
        score -= 0.2
    # Clamp
    return max(0.0, min(1.0, round(score, 3)))


def suggest_gestures(target_tone: str) -> List[str]:
    """Get gestures for tone from JSON configuration."""
    catalogs = _get_catalogs()
    gestures_by_tone = catalogs.get("gestures", {})
    return gestures_by_tone.get(target_tone, ["Hands Together"])
