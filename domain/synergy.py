from __future__ import annotations

from typing import List

from .models import Context, FavStatus, MatchStage

# Local gesture→tone mapping to avoid circular deps
_GESTURE_TONE = {
    "Hands Together": "calm",
    "Outstretched Arms": "calm",
    "Point Finger": "assertive",
    "Hands on Hips": "assertive",
    "Thrash Arms": "angry",
    "Throw water bottle": "angry",
    "Pump Fists": "motivational",
    "Hands in Pockets": "relaxed",
}

_TONE_GESTURES = {
    "calm": ["Hands Together", "Outstretched Arms"],
    "assertive": ["Point Finger", "Hands on Hips"],
    "angry": ["Thrash Arms", "Throw water bottle"],
    "motivational": ["Pump Fists"],
    "relaxed": ["Hands in Pockets"],
    # "encourage" maps best to calm gestures in FM UI framing
    "encourage": ["Outstretched Arms", "Hands Together"],
}


def gesture_tone(gesture: str) -> str:
    return _GESTURE_TONE.get(gesture, "calm")


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
    return _TONE_GESTURES.get(target_tone, ["Hands Together"])
