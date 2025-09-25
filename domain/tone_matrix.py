"""
Tone Matrix: compute ranked tones with weights and a disallow list for risky options
given a match context.

Tones used here correspond to talk "tones" (mapped indirectly via gesture categories):
- calm, assertive, motivational, relaxed, aggressive

Inputs considered:
- venue (home/away/neutral)
- favourite/underdog
- importance (league/cup/derby/final)
- morale trend last 5 (-2..+2)
- HT score delta and xThreat proxy (-1..+1)
- card state (reds/yellows)
- injuries count

Output:
- weights: dict[tone] = weight (normalized to sum 1)
- disallow: list of tones considered risky for the current context
"""
from __future__ import annotations

from typing import Dict, List, Tuple
from pathlib import Path
import json

from .models import Context, SpecialSituation, Venue, FavStatus, MatchStage


def _get_supported_tones() -> List[str]:
    """Get supported tones from JSON configuration."""
    try:
        fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "catalogs.json"
        if fp.exists():
            catalogs = json.loads(fp.read_text(encoding="utf-8"))
            gestures_by_tone = catalogs.get("gestures", {})
            return list(gestures_by_tone.keys())
    except Exception:
        pass
    # Fallback list if JSON not available - using JSON-driven tone names
    return ["calm", "assertive", "motivational", "relaxed", "aggressive"]


def _base_weights(ctx: Context) -> Dict[str, float]:
    # Start with neutral baseline using JSON-driven tones
    supported_tones = _get_supported_tones()
    w = {t: 1.0 for t in supported_tones}
    # Venue: away/neutral favor calm/motivational over assertive/aggressive
    if ctx.venue in (Venue.AWAY,):
        w["calm"] += 0.3
        w["motivational"] += 0.2
        w["assertive"] -= 0.15
        w["aggressive"] -= 0.25
        w["relaxed"] += 0.1
    elif ctx.venue == Venue.HOME:
        w["assertive"] += 0.2
        w["motivational"] += 0.2
    # Status: favourite can lean assertive/motivational; underdog calm/motivational
    if ctx.fav_status == FavStatus.FAVOURITE:
        w["assertive"] += 0.2
        w["motivational"] += 0.1
    else:
        w["calm"] += 0.2
        w["motivational"] += 0.2
    # Importance: derby/final raise risk of aggressive being volatile; cup a bit more motivational
    if SpecialSituation.DERBY in ctx.special_situations:
        w["motivational"] += 0.2
        w["aggressive"] -= 0.2
    if SpecialSituation.FINAL in ctx.special_situations:
        w["calm"] += 0.2
        w["relaxed"] += 0.1
        w["assertive"] -= 0.1
        w["aggressive"] -= 0.2
    if SpecialSituation.CUP in ctx.special_situations:
        w["motivational"] += 0.15
    return w


def _apply_dynamic_signals(ctx: Context, w: Dict[str, float]) -> None:
    # Morale trend
    if ctx.morale_trend is not None:
        if ctx.morale_trend <= -1:
            w["motivational"] += 0.3
            w["calm"] += 0.2
            w["assertive"] -= 0.1
        elif ctx.morale_trend >= 1:
            w["assertive"] += 0.15
            w["motivational"] += 0.15
    # HT score delta and stage-specific momentum
    if ctx.stage in (MatchStage.HALF_TIME, MatchStage.PRE_MATCH, MatchStage.FULL_TIME):
        delta = ctx.ht_score_delta
    else:
        # If in-play, fallback to live score delta when available
        if ctx.team_goals is not None and ctx.opponent_goals is not None:
            delta = ctx.team_goals - ctx.opponent_goals
        else:
            delta = None
    if delta is not None:
        if delta < 0:
            w["motivational"] += 0.2
            w["calm"] += 0.1
            w["assertive"] += 0.05
            # If we're away and the favourite while trailing at HT, avoid "praise" vibes:
            # reduce motivational and lean into calm/assertive guidance.
            if ctx.stage == MatchStage.HALF_TIME and ctx.venue == Venue.AWAY and ctx.fav_status == FavStatus.FAVOURITE:
                w["motivational"] -= 0.1
                w["calm"] += 0.2
                w["assertive"] += 0.05
        elif delta > 0:
            w["calm"] += 0.2
            w["relaxed"] += 0.1
    # xThreat proxy: push assertive/motivational when on top; calm/motivational when under
    if ctx.xthreat_delta is not None:
        if ctx.xthreat_delta >= 0.25:
            w["assertive"] += 0.2
            w["motivational"] += 0.2
        elif ctx.xthreat_delta <= -0.25:
            w["calm"] += 0.2
            w["motivational"] += 0.2
    # Discipline and availability
    if ctx.cards_red > 0:
        w["calm"] += 0.3
        w["motivational"] += 0.2
        w["aggressive"] -= 0.3
    if ctx.cards_yellow >= 3:
        w["calm"] += 0.1
        w["assertive"] -= 0.05
        w["aggressive"] -= 0.1
    if ctx.injuries >= 2:
        w["motivational"] += 0.2
        w["calm"] += 0.1


def _disallow(ctx: Context, weights: Dict[str, float]) -> List[str]:
    dis: List[str] = []
    # Generic guardrails by stage
    if ctx.stage == MatchStage.PRE_MATCH:
        # Avoid aggressive pre-match unless extreme scenario
        dis.append("aggressive")
    if ctx.stage == MatchStage.FULL_TIME:
        # Avoid aggressive if underdog drew/won away
        if ctx.fav_status == FavStatus.UNDERDOG and ctx.venue == Venue.AWAY and (ctx.team_goals or 0) >= (ctx.opponent_goals or 0):
            dis.append("aggressive")
    # Discipline-related blocks
    if ctx.cards_red > 0:
        if "aggressive" not in dis:
            dis.append("aggressive")
    # Away underdog at half-time and not leading -> avoid aggressive hairdryer risk
    if ctx.stage == MatchStage.HALF_TIME and ctx.venue == Venue.AWAY and ctx.fav_status == FavStatus.UNDERDOG:
        # Conservative: avoid aggressive hairdryer away at HT for underdogs regardless of margin
        if "aggressive" not in dis:
            dis.append("aggressive")
    # Away favourite trailing at half-time -> avoid "motivational" (can read as praise)
    if ctx.stage == MatchStage.HALF_TIME and ctx.venue == Venue.AWAY and ctx.fav_status == FavStatus.FAVOURITE:
        delta = ctx.ht_score_delta
        if delta is not None and delta < 0:
            if "motivational" not in dis:
                dis.append("motivational")
    # General safety: as an underdog at HT, avoid aggressive hairdryer unless exceptional
    if ctx.stage == MatchStage.HALF_TIME and ctx.fav_status == FavStatus.UNDERDOG:
        if "aggressive" not in dis:
            dis.append("aggressive")
    # Final/Derby caution
    if SpecialSituation.FINAL in ctx.special_situations:
        if "aggressive" not in dis:
            dis.append("aggressive")
    return dis


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    # clamp negatives to a small floor
    clamped = {k: max(v, 0.01) for k, v in weights.items()}
    s = sum(clamped.values())
    return {k: round(v / s, 3) for k, v in clamped.items()}


def select_tones(ctx: Context) -> Tuple[Dict[str, float], List[str]]:
    """Compute tone weights and disallowed tones for the given context.

    Returns (weights, disallow).
    """
    w = _base_weights(ctx)
    _apply_dynamic_signals(ctx, w)
    weights = _normalize(w)
    dis = _disallow(ctx, weights)
    # ensure disallowed tones get zero weight in final consumer if desired; leave as-is here
    return weights, dis
