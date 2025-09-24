from __future__ import annotations

from typing import Dict

from .models import Context


def analyze_units(ctx: Context) -> Dict[str, str]:
    """Return unit-level notes based on average ratings divergence.

    Heuristics:
    - If DEF < 6.5 and ATT > 7.0: DEF -> sympathise, ATT -> praise
    - If unit < 6.5: encourage/sympathise
    - If unit > 7.2: praise
    - MID acts as balancer; if MID low while others high, encourage MID
    """
    notes: Dict[str, str] = {}
    ratings = ctx.unit_ratings or {}
    d = ratings.get("Defence") or ratings.get("DEF")
    m = ratings.get("Midfield") or ratings.get("MID")
    a = ratings.get("Attack") or ratings.get("ATT")

    def tag_for(val: float | None) -> str | None:
        if val is None:
            return None
        if val >= 7.2:
            return "praise"
        if val < 6.5:
            return "encourage"
        return None

    # Divergence case
    if d is not None and a is not None and d < 6.5 and a > 7.0:
        notes["Defence"] = "sympathise (stay solid, reset focus)"
        notes["Attack"] = "praise (keep being brave)"
    # Generic tags
    for unit, val in ("Defence", d), ("Midfield", m), ("Attack", a):
        t = tag_for(val)
        if t and unit not in notes:
            notes[unit] = t
    return notes
