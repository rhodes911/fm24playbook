"""
Rules Engine: maps Context → Recommendation using the JSON-driven Rules Admin system.
This module has no Streamlit/UI code and can be tested independently.
"""
from __future__ import annotations

from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
import json
from dataclasses import replace
import csv
from datetime import datetime, timezone

from .models import (
    Context, Recommendation,
    Mentality, Shout,
    MatchStage, FavStatus, Venue, ScoreState, SpecialSituation, TalkAudience,
    FavTier,
    PlayerReaction,
    PlaybookRule, ReactionRule, SpecialRule
)
from .tone_matrix import select_tones
from .segmentation import analyze_units
from .nudges import generate_nudges
from .synergy import score_synergy, suggest_gestures
from .ml_assist import extract_features, to_vector_row, load_model, predict_proba

MENTALITY_ORDER = [
    Mentality.DEFENSIVE,
    Mentality.CAUTIOUS,
    Mentality.BALANCED,
    Mentality.POSITIVE,
    Mentality.ATTACKING,
    Mentality.VERY_ATTACKING,
]

MENTALITY_TO_VALUE = {
    Mentality.DEFENSIVE: -2,
    Mentality.CAUTIOUS: -1,
    Mentality.BALANCED: 0,
    Mentality.POSITIVE: 1,
    Mentality.ATTACKING: 2,
    Mentality.VERY_ATTACKING: 3,
}

VALUE_TO_MENTALITY = {v: k for k, v in MENTALITY_TO_VALUE.items()}


def clamp_mentality(value: int) -> Mentality:
    value = max(min(value, 3), -2)
    return VALUE_TO_MENTALITY[value]


# JSON Configuration Loaders - Replace All Hardcoded Templates
def _load_config_json(filename: str, default: dict = None) -> dict:
    """Load JSON configuration file with fallback to default."""
    if default is None:
        default = {}
    try:
        fp = Path(__file__).resolve().parent.parent / "data" / filename
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _get_catalogs() -> dict:
    """Load catalogs (tones, gestures) from normalized catalogs.json."""
    try:
        fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "catalogs.json"
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _get_statements() -> dict:
    """Load statements from normalized statements.json."""
    try:
        fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "statements.json"
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _load_base_rules() -> List[PlaybookRule]:
    """Load base rules from JSON configuration - replaces playbook.rules."""
    from domain.models import PlaybookRule
    
    rules_json = _load_config_json("rules/normalized/base_rules.json", [])
    return [PlaybookRule(**rule) for rule in rules_json]

def _load_special_overrides() -> List[SpecialRule]:
    """Load special overrides from JSON configuration - replaces playbook.special."""
    from domain.models import SpecialRule
    
    special_json = _load_config_json("rules/normalized/special_overrides.json", [])
    return [SpecialRule(**rule) for rule in special_json]

def _load_reaction_rules() -> List[ReactionRule]:
    """Load reaction rules from JSON configuration - replaces playbook.reactions."""
    from domain.models import ReactionRule
    
    reactions_json = _load_config_json("rules/normalized/reaction_rules.json", [])
    return [ReactionRule(**rule) for rule in reactions_json]

def _gesture_tone(gesture: str) -> str:
    """Get tone for gesture from catalogs.json configuration - REPLACES _GESTURE_TONE dict."""
    catalogs = _get_catalogs()
    gestures_by_tone = catalogs.get("gestures", {})
    
    # Find which tone this gesture belongs to
    for tone, gesture_list in gestures_by_tone.items():
        if gesture in gesture_list:
            return tone
    
    # Fallback to calm for unknown gestures
    return "calm"

def _get_gesture_statements(stage: MatchStage, score_state: Optional[ScoreState], gesture: str) -> List[str]:
    """Get available statements for a gesture at a specific stage/score - REPLACES _GESTURE_TEMPLATES."""
    statements_data = _get_statements()
    
    # Map stage to JSON key
    stage_key = {
        MatchStage.PRE_MATCH: "PreMatch",
        MatchStage.HALF_TIME: "HalfTime", 
        MatchStage.FULL_TIME: "FullTime"
    }.get(stage, "PreMatch")
    
    stage_data = statements_data.get(stage_key, {})
    
    # For PreMatch, no score state subdivision
    if stage == MatchStage.PRE_MATCH:
        return stage_data.get(gesture, [])
    
    # For HalfTime/FullTime, check score state
    score_key = {
        ScoreState.WINNING: "Winning",
        ScoreState.DRAWING: "Drawing", 
        ScoreState.LOSING: "Losing"
    }.get(score_state, "Drawing")
    
    score_data = stage_data.get(score_key, {})
    return score_data.get(gesture, [])

def _get_tone_statements(stage: MatchStage, score_state: Optional[ScoreState], tone: str) -> List[str]:
    """Get fallback tone-based statements - REPLACES _TALK_TEMPLATES."""
    # Get all gestures that match this tone
    catalogs = _get_catalogs()
    matching_gestures = catalogs.get("gestures", {}).get(tone, [])
    
    # Collect all statements from those gestures
    all_statements = []
    for gesture in matching_gestures:
        statements = _get_gesture_statements(stage, score_state, gesture)
        all_statements.extend(statements)
    
    return all_statements

def _get_stats_overlay_phrase(overlay_key: str, tone: str) -> Optional[str]:
    """Get stats-based overlay phrase from JSON statements - NO MORE HARDCODED OVERLAYS."""
    # Use JSON-driven statements instead of hardcoded overlays
    # Get tone-based statements which are already authentic FM24 phrases
    statements = _get_tone_statements(MatchStage.HALF_TIME, ScoreState.DRAWING, tone)
    if statements:
        # Return first available statement for the tone
        return statements[0]
    
    # Fallback to calm tone if specific tone not available
    calm_statements = _get_tone_statements(MatchStage.HALF_TIME, ScoreState.DRAWING, "calm")
    return calm_statements[0] if calm_statements else None


# REMOVED: _GESTURE_TONE - now using _gesture_tone() function with JSON data

# REMOVED: _GESTURE_TEMPLATES - replaced with JSON-driven _get_gesture_statements() function



# Tone-aware overlays for stats-driven phrasing at talk stages
# REMOVED: _STATS_OVERLAY_TEMPLATES - replaced with JSON-driven _get_stats_overlay_phrase() function

# Talk templates chosen by stage/score and tone to ensure valid FM combos
# REMOVED: _TALK_TEMPLATES - replaced with JSON-driven _get_tone_statements() function

# Optional normalized mapping from UI: which statements are allowed for each gesture.
# Structure (indices into the statements lists):
# {
#   "PreMatch": { gesture: { tone: [idx, ...] } },
#   "HalfTime": { "Winning": { gesture: { tone: [idx] } }, ... },
#   "FullTime": { "Winning": { gesture: { tone: [idx] } }, ... }
# }
_GESTURE_STATEMENTS_MAP: Dict[str, Dict] = {}
try:
    _norm_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "gesture_statements.json"
    if _norm_fp.exists():
        _GESTURE_STATEMENTS_MAP = json.loads(_norm_fp.read_text(encoding="utf-8"))
except Exception:
    _GESTURE_STATEMENTS_MAP = {}

def _allowed_statement_indices(stage: MatchStage, score_state: Optional[ScoreState], gesture: Optional[str], tone: str) -> Optional[List[int]]:
    if not gesture:
        return None
    try:
        if stage == MatchStage.PRE_MATCH:
            node = _GESTURE_STATEMENTS_MAP.get("PreMatch", {}).get(gesture, {})
            return list(node.get(tone, [])) or None
        key = "HalfTime" if stage == MatchStage.HALF_TIME else ("FullTime" if stage == MatchStage.FULL_TIME else None)
        if not key or score_state is None:
            return None
        node = (((_GESTURE_STATEMENTS_MAP.get(key, {}) or {}).get(score_state.value, {}) or {}).get(gesture, {}) or {})
        vals = node.get(tone, [])
        return list(vals) if vals else None
    except Exception:
        return None


def _select_talk_phrase(context: Context, tone: str, gesture: Optional[str] = None) -> Optional[str]:
    """Select appropriate team talk phrase using JSON-driven statements - REPLACES hardcoded templates."""
    stage = context.stage
    score_state = context.score_state
    
    # Primary: Try to get gesture-specific statement from JSON
    if gesture:
        statements = _get_gesture_statements(stage, score_state, gesture)
        if statements:
            # Use context heuristics to pick the best statement
            if (stage == MatchStage.HALF_TIME and score_state == ScoreState.LOSING and 
                gesture == "Outstretched Arms" and context.venue == Venue.AWAY and len(statements) >= 2):
                # Prefer supportive approach for away underdogs
                return statements[0] if context.fav_status == FavStatus.FAVOURITE else statements[1]
            # Default to first statement
            return statements[0] if statements else None
    
    # Fallback: Get tone-based statements from JSON
    statements = _get_tone_statements(stage, score_state, tone)
    if not statements:
        return None
    
    # Apply context heuristics for tone-based selection
    if stage == MatchStage.PRE_MATCH and tone == "assertive":
        if context.fav_status == FavStatus.FAVOURITE and context.venue == Venue.HOME and len(statements) >= 2:
            # Prefer home-flavoured assertive line
            return statements[1] if len(statements) > 1 else statements[0]
        if context.fav_status == FavStatus.FAVOURITE and context.venue == Venue.AWAY and len(statements) >= 3:
            # Prefer away-flavoured assertive line
            return statements[2] if len(statements) > 2 else statements[0]
    
    # Apply additional context heuristics
    if statements:
        # Favor anti-complacency lines when favourite and leading
        if score_state == ScoreState.WINNING and context.fav_status == FavStatus.FAVOURITE and tone == "assertive":
            return statements[0]
        
        # Away losing: prefer supportive phrasing in calm/motivational
        if score_state == ScoreState.LOSING and context.venue == Venue.AWAY:
            if tone in ("calm", "motivational"):
                # Prefer the second calm line which maps to "dig in and give everything" wording
                if tone == "calm" and len(statements) >= 2:
                    return statements[1]
                return statements[0]
        
        # Half-time losing and either favourite or 2+ down: prefer assertive first option
        if stage == MatchStage.HALF_TIME and score_state == ScoreState.LOSING and tone == "assertive":
            if context.fav_status == FavStatus.FAVOURITE or (context.ht_score_delta is not None and context.ht_score_delta <= -2):
                return statements[0]
        
        # Default to first statement
            return items[0]
        # Legacy single-string path
        return items
    if score_state is None:
        return None
    stage_tbl = tbl.get(score_state)  # type: ignore[index]
    if not stage_tbl:
        return None
    items = stage_tbl.get(tone)
    if items is None:
        return None
    # Choose from list if available using light heuristics
    if isinstance(items, list):
        # Apply normalized allowed indices when present
        allowed = _allowed_statement_indices(stage, score_state, gesture, tone)
        if allowed:
            for idx in allowed:
                if 0 <= idx < len(items):
                    return items[idx]
        # Favor anti-complacency lines when favourite and leading
        if score_state == ScoreState.WINNING and context.fav_status == FavStatus.FAVOURITE and tone == "assertive":
            return items[0]
        # Away losing: prefer supportive phrasing in calm/motivational
        if score_state == ScoreState.LOSING and context.venue == Venue.AWAY:
            if tone in ("calm", "motivational"):
                # Prefer the second calm line which maps to "dig in and give everything" wording
                if tone == "calm" and len(items) >= 2:
                    return items[1]
                return items[0]
        # Half-time losing and either favourite or 2+ down: prefer assertive first option
        if stage == MatchStage.HALF_TIME and score_state == ScoreState.LOSING and tone == "assertive":
            if context.fav_status == FavStatus.FAVOURITE or (context.ht_score_delta is not None and context.ht_score_delta <= -2):
                return items[0]
        # Default to first paraphrase
        return items[0]
    return items


def harmonize_talk_with_gesture(context: Context, rec: Recommendation) -> Recommendation:
    """Ensure the team talk phrase matches the tone implied by the chosen gesture.

    This avoids recommending combos that donâ€™t exist in FMâ€™s UI (tone drives available lines).
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    # If a special override has already provided a concrete phrase, keep it.
    if rec.team_talk and rec.team_talk.strip():
        return rec
    tone = _gesture_tone(rec.gesture)
    phrase = _select_talk_phrase(context, tone, rec.gesture)
    if phrase:
        out = replace(rec, team_talk=phrase)
        try:
            tone = _gesture_tone(out.gesture)
            out.trace.append(f"Phrase harmonized to gesture tone: tone={tone}")
        except Exception:
            pass
        return out
    return rec


def adapt_talk_phrase_with_stats(context: Context, rec: Recommendation) -> Recommendation:
    """Rewrite the team talk phrase itself based on live stats in a tone-aware way.

    Applies only at talk stages (PreMatch/HalfTime/FullTime) and only when stats are present.
    Priority:
      1) Out-shooting/xG advantage but drawing/losing â†’ push_on
      2) Being out-shot and protecting a lead late â†’ see_it_out
      3) Low possession (<40) as favourites and not winning â†’ take_control
    Avoid overriding explicit Promotion overrides at FullTime.
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    # Respect Promotion celebration at FT
    if context.stage == MatchStage.FULL_TIME and SpecialSituation.PROMOTION in context.special_situations:
        return rec
    # Require at least one stat present
    has_stats = any([
        context.possession_pct is not None,
        context.shots_for is not None, context.shots_against is not None,
        context.shots_on_target_for is not None, context.shots_on_target_against is not None,
        context.xg_for is not None, context.xg_against is not None,
    ])
    if not has_stats:
        return rec
    tone = _gesture_tone(rec.gesture)
    sf = context.shots_for or 0
    sa = context.shots_against or 0
    sof = context.shots_on_target_for or 0
    soa = context.shots_on_target_against or 0
    poss = context.possession_pct if context.possession_pct is not None else None
    xg_for = context.xg_for or 0.0
    xg_against = context.xg_against or 0.0
    xg_delta = xg_for - xg_against

    # Determine overlay key by priority
    overlay_key: Optional[str] = None
    if context.score_state in (ScoreState.DRAWING, ScoreState.LOSING) and (
        sf > sa + 3 or sof > soa + 1 or xg_delta > 0.6
    ):
        overlay_key = "push_on"
    elif context.score_state == ScoreState.WINNING and context.stage in (MatchStage.LATE, MatchStage.VERY_LATE) and (
        sa > sf + 4 or soa > sof + 2
    ):
        overlay_key = "see_it_out"
    elif poss is not None and poss < 40 and context.fav_status == FavStatus.FAVOURITE and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        overlay_key = "take_control"

    if not overlay_key:
        return rec
    # Tier-informed tone bias: when evenly matched or slight underdog but with positive edge,
    # prefer calm "push on" phrasing rather than assertive.
    try:
        _tier_now, _edge_now, _ = detect_matchup_tier(context)
    except Exception:
        _tier_now, _edge_now = None, None
    tone_to_use = tone
    if overlay_key == "push_on" and _tier_now in (FavTier.EVEN, FavTier.SLIGHT_UNDERDOG):
        if (_edge_now is not None and _edge_now > 0.2):
            tone_to_use = "calm"
    # Pick tone-specific phrase from JSON; fallback to calm if tone not present  
    new_phrase = _get_stats_overlay_phrase(overlay_key, tone_to_use)
    if not new_phrase:
        return rec
    # Replace the phrase with the overlay version
    out = replace(rec, team_talk=new_phrase)
    out.trace.append(f"Stats overlay applied: key={overlay_key}, tone={tone_to_use}")
    if tone_to_use != tone and overlay_key == "push_on":
        out.trace.append("Tier-informed: calm push-on phrasing (even/slight underdog with positive edge)")
    return out


def _is_praise_context(context: Context) -> bool:
    """Rough heuristic for when praise-style calm talk is appropriate.

    - Winning (any stage) or
    - FullTime when underdog draws/wins away.
    """
    if context.score_state == ScoreState.WINNING:
        return True
    if context.stage == MatchStage.FULL_TIME and context.venue == Venue.AWAY and context.fav_status == FavStatus.UNDERDOG:
        if context.score_state in (ScoreState.DRAWING, ScoreState.WINNING):
            return True
    # Promotion/title clinched: celebratory tone regardless of venue/fav
    if SpecialSituation.PROMOTION in context.special_situations and context.stage == MatchStage.FULL_TIME:
        return True
    return False


def adjust_gesture_for_context(context: Context, rec: Recommendation) -> Recommendation:
    """Decision matrix for gestures at talk stages, aligned with FM availability.

    Core principles:
    - Outstretched Arms (OA) is reserved for praise/faith messages; avoid when trailing.
    - Point Finger / Hands on Hips carry assertive lines (demand more / show me more).
    - Hands Together is the safe calm-supportive option when behind.

    Matrix (talk stages only):
    - PreMatch:
        * Favourite â†’ Point Finger
        * Underdog â†’ Hands Together (avoid OA framing pre-match)
    - HalfTime:
        * Losing â†’ Favourite: Point Finger (if <= -2: Thrash Arms)
                  â†’ Underdog: Hands Together
        * Drawing â†’ Favourite: Point Finger; Underdog: Hands Together
        * Winning â†’ Hands Together (if complacent reaction present then Point Finger)
    - FullTime:
        * Winning â†’ Hands Together
        * Drawing â†’ Favourite: Hands on Hips; Underdog: Outstretched Arms
        * Losing â†’ Favourite: Thrash Arms; Underdog: Hands Together
    Additionally, if a resulting gesture is OA in a nonâ€‘praise context, switch to Hands Together.
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec

    g = rec.gesture
    # PreMatch
    if context.stage == MatchStage.PRE_MATCH:
        # Favourites: assertive setup; Underdogs: OA is valid pre-match for removing pressure
        g = "Point Finger" if context.fav_status == FavStatus.FAVOURITE else "Outstretched Arms"

    # HalfTime
    elif context.stage == MatchStage.HALF_TIME:
        if context.score_state == ScoreState.LOSING:
            if context.fav_status == FavStatus.FAVOURITE:
                if context.ht_score_delta is not None and context.ht_score_delta <= -2:
                    g = "Thrash Arms"
                else:
                    g = "Point Finger"
            else:
                g = "Hands Together"
        elif context.score_state == ScoreState.DRAWING:
            g = "Point Finger" if context.fav_status == FavStatus.FAVOURITE else "Hands Together"
        elif context.score_state == ScoreState.WINNING:
            # Default praise; if complacent in reactions, go assertive
            if "Complacent" in context.player_reactions:
                g = "Point Finger"
            else:
                g = "Hands Together"

    # FullTime
    elif context.stage == MatchStage.FULL_TIME:
        if context.score_state == ScoreState.WINNING:
            g = "Hands Together"
        elif context.score_state == ScoreState.DRAWING:
            g = "Hands on Hips" if context.fav_status == FavStatus.FAVOURITE else "Outstretched Arms"
        elif context.score_state == ScoreState.LOSING:
            g = "Thrash Arms" if context.fav_status == FavStatus.FAVOURITE else "Hands Together"

    # Avoid OA when it isn't clearly a praise/faith context
    if g == "Outstretched Arms" and not _is_praise_context(context):
        g = "Hands Together"

    if g != rec.gesture:
        out = replace(rec, gesture=g)
        try:
            out.trace.append(f"Gesture adjusted for context: {rec.gesture} -> {g}")
        except Exception:
            pass
        return out
    return rec


def enforce_prematch_mentality_cap(context: Context, rec: Recommendation) -> Recommendation:
    """Never start a game higher than Positive; cap Attacking/Very Attacking at PreMatch.

    If capped, append an explanatory note.
    """
    if context.stage != MatchStage.PRE_MATCH:
        return rec
    if rec.mentality in (Mentality.ATTACKING, Mentality.VERY_ATTACKING):
        capped = replace(rec, mentality=Mentality.POSITIVE)
        capped.notes.append("Pre-match cap: start no higher than Positive.")
        try:
            capped.trace.append("Pre-match mentality capped to Positive")
        except Exception:
            pass
        return capped
    return rec


def choose_inplay_shout(context: Context, rec: Recommendation) -> Recommendation:
    """Heuristic shout selector for in-play stages when none specified by rules.

    - Winning:
      - Underdog â†’ Praise
      - Favourite at Late/VeryLate â†’ Focus
    - Drawing:
      - Favourite â†’ Demand More
      - Underdog â†’ Encourage
    - Losing:
      - Favourite â†’ Fire Up (Early/Mid), Demand More (Late/VeryLate)
      - Underdog â†’ Encourage
    """
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    if rec.shout != Shout.NONE:
        return rec
    result = replace(rec)
    if context.score_state == ScoreState.WINNING:
        if context.fav_status == FavStatus.UNDERDOG:
            result.shout = Shout.PRAISE
            result.notes.append("Underdog winning: Praise to reinforce confidence.")
            try:
                result.trace.append("In-play shout set: Praise (underdog winning)")
            except Exception:
                pass
        elif context.stage in (MatchStage.LATE, MatchStage.VERY_LATE):
            result.shout = Shout.FOCUS
            result.notes.append("Protect the lead late: Focus.")
            try:
                result.trace.append("In-play shout set: Focus (protect late lead)")
            except Exception:
                pass
    elif context.score_state == ScoreState.DRAWING:
        if context.fav_status == FavStatus.FAVOURITE:
            # Tier-informed nuance: if we're a strong favourite and it's very late, composure > push
            try:
                _tier, _, _ = detect_matchup_tier(context)
            except Exception:
                _tier = None
            if context.stage == MatchStage.VERY_LATE and _tier == FavTier.STRONG_FAVOURITE:
                result.shout = Shout.FOCUS
                result.notes.append("Strong favourite drawing very late: Focus to stay composed for the moment.")
                try:
                    result.trace.append("Tier-aware in-play shout: Focus (strong favourite drawing very late)")
                except Exception:
                    pass
            else:
                result.shout = Shout.DEMAND_MORE
                result.notes.append("Favourite drawing: Demand More to push on.")
                try:
                    result.trace.append("In-play shout set: Demand More (favourite drawing)")
                except Exception:
                    pass
        else:
            result.shout = Shout.ENCOURAGE
            result.notes.append("Underdog drawing: Encourage to keep belief.")
            try:
                result.trace.append("In-play shout set: Encourage (underdog drawing)")
            except Exception:
                pass
    elif context.score_state == ScoreState.LOSING:
        if context.fav_status == FavStatus.FAVOURITE:
            if context.stage in (MatchStage.EARLY, MatchStage.MID):
                result.shout = Shout.FIRE_UP
                result.notes.append("Favourite losing early: Fire Up for reaction.")
                try:
                    result.trace.append("In-play shout set: Fire Up (favourite losing early)")
                except Exception:
                    pass
            else:
                result.shout = Shout.DEMAND_MORE
                result.notes.append("Favourite losing late: Demand More to chase.")
                try:
                    result.trace.append("In-play shout set: Demand More (favourite losing late)")
                except Exception:
                    pass
        else:
            result.shout = Shout.ENCOURAGE
            result.notes.append("Underdog losing: Encourage to avoid collapse.")
            try:
                result.trace.append("In-play shout set: Encourage (underdog losing)")
            except Exception:
                pass
    return result


def _goal_diff(context: Context) -> Optional[int]:
    if context.team_goals is None or context.opponent_goals is None:
        return None
    return context.team_goals - context.opponent_goals


def apply_time_score_heuristics(context: Context, rec: Recommendation) -> Recommendation:
    """Adjust mentality for late-game scenarios based on score and favourite status.

    - Late/VeryLate and Losing:
      - Favourite: +1 mentality
      - Underdog: +1 if margin is -1, else 0
    - Late/VeryLate and Drawing:
      - Favourite: +1 mentality
    - Late/VeryLate and Winning:
      - If margin is +1: -1 mentality (see the game out)
    """
    if context.stage not in (MatchStage.LATE, MatchStage.VERY_LATE):
        return rec
    gd = _goal_diff(context)
    delta = 0
    if context.score_state == ScoreState.LOSING:
        if context.fav_status == FavStatus.FAVOURITE:
            delta = 1
        else:
            if gd is not None and gd == -1:
                delta = 1
    elif context.score_state == ScoreState.DRAWING:
        if context.fav_status == FavStatus.FAVOURITE:
            delta = 1
    elif context.score_state == ScoreState.WINNING:
        if gd is not None and gd == 1:
            delta = -1
    if delta == 0:
        return rec
    mval = MENTALITY_TO_VALUE[rec.mentality] + delta
    new_mentality = clamp_mentality(mval)
    result = replace(rec, mentality=new_mentality)
    if delta > 0:
        result.notes.append("Late-game push based on scoreline and status.")
        try:
            result.trace.append("Late-game mentality +1 applied")
        except Exception:
            pass
    else:
        result.notes.append("Late-game control: tighten up with a narrow lead.")
        try:
            result.trace.append("Late-game mentality -1 applied (protect 1-goal lead)")
        except Exception:
            pass
    return result


def apply_tier_informed_talk_adjustments(context: Context, rec: Recommendation) -> Recommendation:
    """Modulate talk gesture/phrasing intensity by matchup tier and edge.

    Goals:
    - SlightFavourite drawing at HT → slightly softer than strong favourite (Hands on Hips vs Point Finger).
    - Even/SlightUnderdog with positive edge at HT → supportive perseverance (Hands Together) and push-on vibe.
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    try:
        tier, edge, _ = detect_matchup_tier(context)
    except Exception:
        return rec
    result = replace(rec)
    # Half-time only for these tweaks
    if context.stage == MatchStage.HALF_TIME:
        if context.score_state == ScoreState.DRAWING:
            # Slight favourite: moderate assertiveness
            if tier == FavTier.SLIGHT_FAVOURITE and result.gesture == "Point Finger":
                result.gesture = "Hands on Hips"
                try:
                    result.trace.append("Tier-informed: slight favourite at HT drawing → soften to Hands on Hips")
                except Exception:
                    pass
            # Even or slight underdog: if edge positive, go supportive perseverance
            if tier in (FavTier.EVEN, FavTier.SLIGHT_UNDERDOG) and (edge is not None and edge > 0.2):
                if result.gesture != "Hands Together":
                    result.gesture = "Hands Together"
                    try:
                        result.trace.append("Tier-informed: even/slight underdog with positive edge → Hands Together (supportive)")
                    except Exception:
                        pass
                # Add a light note to nudge phrasing
                result.notes.append("Even but on top: keep belief and push on.")
    return result


def apply_live_stats_heuristics(context: Context, rec: Recommendation) -> Recommendation:
    """Use optional live stats to add notes and make subtle tweaks.

    Principles:
    - If out-shooting but behind/drawing: encourage/motivate to keep belief (notes only unless shout is NONE)
    - If being out-shot heavily and winning late: suggest Focus (if shout is NONE)
    - If possession is <40% and favourite while drawing/losing: add note to calm and simplify (no tone change)
    - If xG delta > 0.6 in your favour but score not reflecting, add 'keep going' note.
    No changes are applied when stats are not present, keeping tests stable.
    """
    if (
        context.possession_pct is None
        and context.shots_for is None and context.shots_against is None
        and context.shots_on_target_for is None and context.shots_on_target_against is None
        and context.xg_for is None and context.xg_against is None
    ):
        return rec
    result = replace(rec)
    sf = context.shots_for or 0
    sa = context.shots_against or 0
    sof = context.shots_on_target_for or 0
    soa = context.shots_on_target_against or 0
    poss = context.possession_pct if context.possession_pct is not None else None
    xg_for = context.xg_for or 0.0
    xg_against = context.xg_against or 0.0

    # Out-shooting but not leading
    if (sf > sa + 3 or sof > soa + 1) and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        result.notes.append("We're creating more â€” keep belief and maintain intensity.")
        if result.shout == Shout.NONE and context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
            result.shout = Shout.ENCOURAGE
            try:
                result.trace.append("Live stats: outshooting → Encourage")
            except Exception:
                pass

    # Being out-shot and protecting a lead late
    if context.score_state == ScoreState.WINNING and (sa > sf + 4 or soa > sof + 2) and context.stage in (MatchStage.LATE, MatchStage.VERY_LATE):
        result.notes.append("They're peppering us â€” tighten up and concentrate.")
        if result.shout == Shout.NONE:
            result.shout = Shout.FOCUS
            try:
                result.trace.append("Live stats: under siege late → Focus")
            except Exception:
                pass

    # Low possession while favourite and not winning
    if poss is not None and poss < 40 and context.fav_status == FavStatus.FAVOURITE and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        result.notes.append("Possession low for a favourite â€” consider calming it down and keeping it simple.")
        try:
            result.trace.append("Live stats note: low possession as favourite")
        except Exception:
            pass

    # Big xG delta in our favour but not leading
    if (xg_for - xg_against) > 0.6 and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        result.notes.append("xG says we're on top â€” keep pushing, the goal should come.")
        try:
            result.trace.append("Live stats note: big xG delta in favour")
        except Exception:
            pass

    return result


def detect_fav_status(context: Context) -> Tuple[FavStatus, str]:
    """Infer Favourite/Underdog using config-driven weights and thresholds.

    Config file: data/rules/normalized/engine_config.json
    Structure:
      {
        "favourite_detection": {
          "pos_gap_threshold": int,
          "pos_weight": int,
          "form_diff_threshold": int,
          "form_weight": int,
          "home_bonus": int,
          "away_penalty": int,
          "favourite_threshold": int,
          "special_rules": {
            "require_both_pos_and_form_to_be_favourite_away": bool,
            "never_favourite_away_if_pos_gap_disadvantage_ge": int
          }
        }
      }
    """
    # Load config once per call (file IO is fine here; could be cached later)
    try:
        cfg_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "engine_config.json"
        cfg = json.loads(cfg_fp.read_text(encoding="utf-8")) if cfg_fp.exists() else {}
        fav_cfg = cfg.get("favourite_detection", {})
    except Exception:
        fav_cfg = {}

    pos_gap_threshold = int(fav_cfg.get("pos_gap_threshold", 3))
    pos_weight = int(fav_cfg.get("pos_weight", 1))
    form_diff_threshold = int(fav_cfg.get("form_diff_threshold", 2))
    form_weight = int(fav_cfg.get("form_weight", 1))
    home_bonus = int(fav_cfg.get("home_bonus", 1))
    away_penalty = int(fav_cfg.get("away_penalty", 0))
    favourite_threshold = int(fav_cfg.get("favourite_threshold", 2))
    specials = fav_cfg.get("special_rules", {}) or {}
    require_both_away = bool(specials.get("require_both_pos_and_form_to_be_favourite_away", False))
    never_fav_away_if_pos_gap_disadv_ge = int(specials.get("never_favourite_away_if_pos_gap_disadvantage_ge", 0))

    score = 0
    parts: List[str] = []

    # Position component: positive if team significantly above opponent
    if context.team_position is not None and context.opponent_position is not None:
        pos_delta = context.opponent_position - context.team_position
        if pos_delta >= pos_gap_threshold:
            score += pos_weight
            parts.append(f"pos +{pos_weight}")
        elif pos_delta <= -pos_gap_threshold:
            score -= pos_weight
            parts.append(f"pos -{pos_weight}")
        else:
            parts.append("pos 0")
    else:
        parts.append("pos ?")

    # Form component
    form_delta = _score_form(context.team_form) - _score_form(context.opponent_form)
    if form_delta >= form_diff_threshold:
        score += form_weight
        parts.append(f"form +{form_weight}")
    elif form_delta <= -form_diff_threshold:
        score -= form_weight
        parts.append(f"form -{form_weight}")
    else:
        parts.append("form 0")

    # Venue component
    if context.venue == Venue.HOME:
        score += home_bonus
        parts.append(f"home +{home_bonus}")
    else:
        score -= away_penalty
        parts.append(f"away -{away_penalty}")

    # Special away constraints
    if context.venue == Venue.AWAY and context.team_position is not None and context.opponent_position is not None:
        pos_delta = context.opponent_position - context.team_position
        # If we're worse by N+ positions away, never favourite
        if never_fav_away_if_pos_gap_disadv_ge and (-pos_delta) >= never_fav_away_if_pos_gap_disadv_ge:
            fav = FavStatus.UNDERDOG
            explanation = f"{fav.value} (forced: away and {abs(pos_delta)} places worse)"
            return fav, explanation
        # If require both pos and form advantages to be favourite away
        if require_both_away:
            has_pos_adv = pos_delta >= pos_gap_threshold
            has_form_adv = form_delta >= form_diff_threshold
            if not (has_pos_adv and has_form_adv):
                fav = FavStatus.UNDERDOG
                explanation = f"{fav.value} (away: need both pos and form advantages; got pos={'Y' if has_pos_adv else 'N'}, form={'Y' if has_form_adv else 'N'})"
                return fav, explanation

    fav = FavStatus.FAVOURITE if score >= favourite_threshold else FavStatus.UNDERDOG
    explanation = f"{fav.value} (score {score}: " + ", ".join(parts) + ")"
    return fav, explanation


def detect_matchup_tier(context: Context) -> Tuple[FavTier, float, str]:
    """Compute a granular advantage score and map to a FavTier.

    Uses advantage_model from engine_config.json combining table context and live stats.
    Returns (tier, score, explanation).
    """
    # Load model config
    try:
        cfg_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "engine_config.json"
        cfg = json.loads(cfg_fp.read_text(encoding="utf-8")) if cfg_fp.exists() else {}
        m = cfg.get("advantage_model", {})
    except Exception:
        m = {}
    # Weights
    w_pos = float(m.get("pos_weight", 1.0))
    w_form = float(m.get("form_weight", 0.8))
    w_home = float(m.get("venue_home", 0.6))
    w_away = float(m.get("venue_away", -0.6))
    w_xg = float(m.get("xg_weight", 0.8))
    w_shots = float(m.get("shots_weight", 0.4))
    w_poss = float(m.get("possession_weight", 0.3))
    cap = float(m.get("cap", 5.0))
    tiers = m.get("tiers", {})
    thr_strong_fav = float(tiers.get("strong_fav", 2.5))
    thr_slight_fav = float(tiers.get("slight_fav", 0.8))
    thr_even_hi = float(tiers.get("even_hi", 0.8))
    thr_even_lo = float(tiers.get("even_lo", -0.8))
    thr_slight_dog = float(tiers.get("slight_dog", -0.8))
    thr_strong_dog = float(tiers.get("strong_dog", -2.5))

    parts: List[str] = []
    score = 0.0

    # Table position differential (positive if we're better placed)
    if context.team_position is not None and context.opponent_position is not None:
        pos_delta = context.opponent_position - context.team_position
        score += w_pos * (pos_delta / 4.0)  # scale: 4 places ≈ 1 point
        parts.append(f"posΔ {pos_delta}×{w_pos}")
    # Form differential: W=3, D=1, L=0
    def _form_points(s: Optional[str]) -> int:
        if not s:
            return 0
        pts = 0
        for c in s[:5].upper():
            pts += 3 if c == 'W' else (1 if c == 'D' else 0)
        return pts
    form_delta = _form_points(context.team_form) - _form_points(context.opponent_form)
    score += w_form * (form_delta / 5.0)  # scale: 5 pts ≈ 1 point
    parts.append(f"formΔ {form_delta}×{w_form}")

    # Venue factor
    if context.venue == Venue.HOME:
        score += w_home
        parts.append(f"home +{w_home}")
    else:
        score += w_away
        parts.append(f"away {w_away}")

    # Live stats (if present)
    if context.xg_for is not None and context.xg_against is not None:
        xg_delta = (context.xg_for - context.xg_against)
        score += w_xg * xg_delta
        parts.append(f"xgΔ {round(xg_delta,2)}×{w_xg}")
    if context.shots_for is not None and context.shots_against is not None:
        shots_delta = (context.shots_for - context.shots_against) / 5.0
        score += w_shots * shots_delta
        parts.append(f"shotsΔ {context.shots_for - context.shots_against}×{w_shots}/5")
    if context.possession_pct is not None:
        poss_delta = (context.possession_pct - 50.0) / 20.0
        score += w_poss * poss_delta
        parts.append(f"possΔ {int(context.possession_pct)-50}%×{w_poss}/20")

    # Clamp
    score = max(-cap, min(cap, score))

    # Map to tier
    if score >= thr_strong_fav:
        tier = FavTier.STRONG_FAVOURITE
    elif score >= thr_slight_fav:
        tier = FavTier.SLIGHT_FAVOURITE
    elif thr_even_lo < score < thr_even_hi:
        tier = FavTier.EVEN
    elif score <= thr_strong_dog:
        tier = FavTier.STRONG_UNDERDOG
    elif score <= thr_slight_dog:
        tier = FavTier.SLIGHT_UNDERDOG
    else:
        # Between even_lo and even_hi inclusive
        tier = FavTier.EVEN

    explanation = f"{tier.value} (score {round(score,2)}: " + ", ".join(parts) + ")"
    return tier, score, explanation


def pick_base_rule(context: Context, rules: List[PlaybookRule]) -> Optional[Recommendation]:
    """Pick the most specific matching rule with fallback from rules list."""
    candidates: List[Tuple[int, PlaybookRule]] = []

    for rule in rules:
        w = rule.when
        score = 0
        # Stage must match
        if w.stage != context.stage:
            continue
        score += 1
        # Optional tier matching: when present, require current tier in the set
        if getattr(w, 'tier', None):
            try:
                _tier, _, _ = detect_matchup_tier(context)
            except Exception:
                _tier = None
            if _tier is None or _tier not in w.tier:
                continue
            score += 1
        # Optional fields increase specificity
        if w.favStatus is not None:
            if context.auto_fav_status:
                # In auto mode, allow either favStatus to match and reduce specificity
                if w.favStatus == context.fav_status:
                    score += 1
            else:
                if w.favStatus != context.fav_status:
                    continue
                score += 1
        if w.venue is not None:
            if w.venue != context.venue:
                continue
            score += 1
        if w.scoreState is not None:
            if context.score_state is None or w.scoreState != context.score_state:
                continue
            score += 1
        # Special matching is any-overlap if specified
        if w.special is not None and len(w.special) > 0:
            if not any(s in context.special_situations for s in w.special):
                continue
            score += 1

        candidates.append((score, rule))

    if not candidates:
        return None

    # pick highest score (most specific)
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[0][1]
    rec = top.recommendation
    base = Recommendation(
        mentality=rec.mentality,
        team_talk=rec.teamTalk,
        gesture=rec.gesture,
        shout=rec.shout,
        talk_audience=rec.audience,
        notes=list(rec.notes),
    )
    try:
        t, _, _ = detect_matchup_tier(context)
        tier_str = t.value
    except Exception:
        tier_str = "?"
    base.trace.append(
        f"Base rule matched: stage={top.when.stage.value} fav={getattr(top.when.favStatus,'value',None)} venue={getattr(top.when.venue,'value',None)} score={getattr(top.when.scoreState,'value',None)} tier_req={(','.join([x.value for x in (top.when.tier or [])]) if getattr(top.when,'tier',None) else '-')}, tier_now={tier_str}"
    )
    return base


def _score_form(form: Optional[str]) -> int:
    if not form:
        return 0
    m = {"W": 1, "D": 0, "L": -1}
    return sum(m.get(ch.upper(), 0) for ch in form[:5])


def apply_context_stats_adjustments(context: Context, rec: Recommendation) -> Recommendation:
    """Adjust mentality (Â±1) and optionally shout based on league positions, recent form, and venue.

    Heuristic:
    - Position gap: >=8 places advantage â†’ +1; <=-8 disadvantage â†’ -1
    - Form diff: score(team) - score(opp). >=2 â†’ +1; <=-2 â†’ -1
    - Home adds +1 to the combined score (away adds 0)
    Mapping: total >= 2 â†’ mentality +1; total <= -2 â†’ mentality -1; else 0
    If base shout is None, suggest Demand More for +1, Encourage for -1.
    """
    total = 0
    parts: List[str] = []
    # Position bucket
    if context.team_position is not None and context.opponent_position is not None:
        pos_diff = context.opponent_position - context.team_position
        if pos_diff >= 8:
            total += 1
            parts.append("pos +1 (≥8 better)")
        elif pos_diff <= -8:
            total -= 1
            parts.append("pos -1 (≤-8 worse)")
        else:
            parts.append("pos 0")
    # Form bucket
    form_diff = _score_form(context.team_form) - _score_form(context.opponent_form)
    if form_diff >= 2:
        total += 1
        parts.append("form +1 (≥2)")
    elif form_diff <= -2:
        total -= 1
        parts.append("form -1 (≤-2)")
    else:
        parts.append("form 0")
    # Home advantage
    if context.venue == Venue.HOME:
        total += 1
        parts.append("home +1")
    else:
        parts.append("away +0")

    delta = 0
    if total >= 2:
        delta = 1
    elif total <= -2:
        delta = -1

    if delta == 0:
        # Still add a trace breadcrumb for transparency
        try:
            rec.trace.append("Context stats check: no mentality change (" + ", ".join(parts) + ")")
        except Exception:
            pass
        return rec

    # Apply mentality delta
    mval = MENTALITY_TO_VALUE[rec.mentality] + delta
    new_mentality = clamp_mentality(mval)
    result = replace(rec, mentality=new_mentality)

    # Suggest shout only for in-play stages and if none already set
    if result.shout == Shout.NONE and context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        result.shout = Shout.DEMAND_MORE if delta > 0 else Shout.ENCOURAGE

    # Add explanatory note
    if delta > 0:
        result.notes.append("Favorable position/form and home advantage suggest a more assertive approach.")
        try:
            result.trace.append("Context stats: mentality +1 (" + ", ".join(parts) + ")")
        except Exception:
            pass
    else:
        result.notes.append("Position/form context suggests caution (especially away).")
        try:
            result.trace.append("Context stats: mentality -1 (" + ", ".join(parts) + ")")
        except Exception:
            pass

    return result


def apply_special_overrides(context: Context, rec: Recommendation, specials: List[SpecialRule]) -> Recommendation:
    """Apply overrides for special situations (merge, non-destructive)."""
    result = replace(rec)
    for s in specials:
        if s.tag not in context.special_situations:
            continue
        # Determine override key by basic context synopsis
        key = None
        if context.stage == MatchStage.PRE_MATCH:
            if context.fav_status == FavStatus.UNDERDOG:
                key = "preMatchUnderdog"
            else:
                key = "preMatch"
        elif context.stage == MatchStage.HALF_TIME:
            if context.score_state == ScoreState.WINNING:
                key = "halfTimeLead"
            elif context.score_state == ScoreState.LOSING:
                key = "halfTimeLosing"
        elif context.stage == MatchStage.FULL_TIME:
            if context.score_state == ScoreState.WINNING:
                key = "fullTimeWin"
            elif context.score_state == ScoreState.DRAWING:
                key = "fullTimeDraw"
            elif context.score_state == ScoreState.LOSING:
                key = "fullTimeLoss"
        
        if key and key in s.overrides:
            ov = s.overrides[key]
            before = {
                "team_talk": result.team_talk,
                "gesture": result.gesture,
                "shout": result.shout,
                "mentality": result.mentality,
            }
            if ov.teamTalk:
                result.team_talk = ov.teamTalk
            if ov.gesture:
                result.gesture = ov.gesture
            if ov.shout:
                result.shout = ov.shout
            if ov.mentality:
                result.mentality = ov.mentality
            # Trace what changed
            try:
                after = {
                    "team_talk": result.team_talk,
                    "gesture": result.gesture,
                    "shout": result.shout,
                    "mentality": result.mentality,
                }
                changed = [k for k in after if after[k] != before[k]]
                if changed:
                    result.trace.append(
                        f"Special override applied: {s.tag.value} • key={key} • changed={','.join(changed)}"
                    )
            except Exception:
                pass
    return result


def apply_reaction_adjustments(context: Context, rec: Recommendation, reactions: List[ReactionRule]) -> Recommendation:
    """Apply all reaction adjustments: teamTalk/gesture/shout overwrites if present, notes merged, mentality delta summed."""
    result = replace(rec)
    start_mentality_val = MENTALITY_TO_VALUE[result.mentality]
    mentality_value = start_mentality_val

    for r in reactions:
        if r.reaction in context.player_reactions:
            adj = r.adjustment
            if adj.teamTalk:
                result.team_talk = adj.teamTalk
            if adj.gesture:
                result.gesture = adj.gesture
            if adj.shout:
                result.shout = adj.shout
            if adj.notes:
                result.notes.extend(adj.notes)
            mentality_value += adj.mentalityDelta
            # Trace for each reaction hit
            try:
                result.trace.append(
                    f"Reaction applied: {r.reaction.value} • Δmentality={adj.mentalityDelta}"
                )
            except Exception:
                pass

    # clamp mentality
    result.mentality = clamp_mentality(mentality_value)
    # Trace overall mentality change if any
    try:
        end_val = MENTALITY_TO_VALUE[result.mentality]
        if end_val != start_mentality_val:
            delta_total = end_val - start_mentality_val
            result.trace.append(f"Reactions total mentality change: {delta_total}")
    except Exception:
        pass
    # dedupe notes while preserving order
    seen = set()
    deduped = []
    for n in result.notes:
        if n not in seen:
            deduped.append(n)
            seen.add(n)
    result.notes = deduped
    return result


def recommend(context: Context) -> Optional[Recommendation]:
    """Compute recommendation end-to-end using JSON-driven configuration."""
    # If numeric score provided, derive score_state for rule matching
    if context.team_goals is not None and context.opponent_goals is not None:
        if context.team_goals > context.opponent_goals:
            context.score_state = ScoreState.WINNING
        elif context.team_goals < context.opponent_goals:
            context.score_state = ScoreState.LOSING
        else:
            context.score_state = ScoreState.DRAWING

    # Auto-detect favourite/underdog based on simple heuristic
    fav_explanation: Optional[str] = None
    if context.auto_fav_status:
        fav, fav_explanation = detect_fav_status(context)
        context.fav_status = fav
    # Compute matchup tier/edge upfront for transparency (used in traces/notes)
    try:
        _tier_now, _edge_now, _tier_expl = detect_matchup_tier(context)
    except Exception:
        _tier_now, _edge_now, _tier_expl = None, None, None
    
    # Load JSON configuration for rules processing
    base_rules = _load_base_rules()
    special_overrides = _load_special_overrides()
    
    base = pick_base_rule(context, base_rules)
    if base is None:
        return None
    # Log tier/edge explanation early
    try:
        if _tier_now is not None:
            base.trace.append(f"Tier detected: {_tier_now.value} (edge {round(_edge_now,2)})")
        if _tier_expl:
            base.trace.append("Tier explain: " + _tier_expl)
    except Exception:
        pass
    with_specials = apply_special_overrides(context, base, special_overrides)
    # No shouts at PreMatch, HalfTime, FullTime â€” convert to statements
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        with_specials.shout = Shout.NONE
    with_stats = apply_context_stats_adjustments(context, with_specials)
    if fav_explanation:
        with_stats.notes.append(f"Auto status: {fav_explanation}")
        try:
            with_stats.trace.append("Auto favourite detection: " + fav_explanation)
        except Exception:
            pass
    # In-play shout selection if none set yet
    with_shout = choose_inplay_shout(context, with_stats)
    with_time = apply_time_score_heuristics(context, with_shout)
    with_stats_live = apply_live_stats_heuristics(context, with_time)
    
    # Load reaction adjustments from JSON
    reaction_rules = _load_reaction_rules()
    final = apply_reaction_adjustments(context, with_stats_live, reaction_rules)
    # Post-adjust gesture to avoid praise-coded OA when behind and pick assertive for favourites
    final = adjust_gesture_for_context(context, final)
    # Tier-informed talk intensity and supportive bias
    final = apply_tier_informed_talk_adjustments(context, final)
    final = harmonize_talk_with_gesture(context, final)
    # Tone-aware stats overlays for the phrase itself
    final = adapt_talk_phrase_with_stats(context, final)
    final = enforce_prematch_mentality_cap(context, final)
    # If user selected a preferred talk audience at talk stages, override
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME) and context.preferred_talk_audience:
        final.talk_audience = context.preferred_talk_audience
    # Tone matrix metadata (ranked tones and disallow list)
    try:
        tone_weights, disallow = select_tones(context)
        # Derive a simple confidence from top tone weight; map risk by aggressiveness
        if tone_weights:
            top_tone, top_w = max(tone_weights.items(), key=lambda x: x[1])
            # Combine tone certainty and gesture synergy for confidence
            syn = score_synergy(top_tone, final.gesture, context)
            final.confidence = round(min(1.0, 0.6 * top_w + 0.4 * syn), 3)
            # risk: bold if assertive/angry top and weight >= 0.45, safe if calm/encourage top
            if top_tone in ("assertive", "angry") and final.confidence >= 0.45:
                final.risk = "bold"
            elif top_tone in ("calm", "encourage", "relaxed"):
                final.risk = "safe"
            else:
                final.risk = "neutral"
            # Suggest safer/bolder gesture-tone alternatives (metadata only)
            # Trailing at half-time as a favourite (esp. away): avoid suggesting Encourage to prevent "praise" vibes.
            safer_candidates = ("calm", "encourage")
            if context.stage == MatchStage.HALF_TIME and context.score_state == ScoreState.LOSING and context.fav_status == FavStatus.FAVOURITE:
                safer_candidates = ("calm",)
            safer = [
                {"tone": t, "gestures": suggest_gestures(t)} for t in safer_candidates if t not in disallow
            ]
            bolder = [
                {"tone": t, "gestures": suggest_gestures(t)} for t in ("assertive", "angry") if t not in disallow
            ]
            # Filter OA when not a praise context
            if not _is_praise_context(context):
                for group in (safer, bolder):
                    for entry in group:
                        entry["gestures"] = [g for g in entry["gestures"] if g != "Outstretched Arms"]
            if safer:
                final.alternatives.append({"type": "safer", "tones": safer})
            if bolder:
                final.alternatives.append({"type": "bolder", "tones": bolder})
            # Add a brief rationale preview
            final.notes.append(f"Tone mix: {', '.join(f'{k}:{v}' for k,v in sorted(tone_weights.items()))}")
            if disallow:
                final.notes.append("Disallow: " + ", ".join(disallow))
            # Clarify why Encourage is blocked in a common case users question
            if (
                context.stage == MatchStage.HALF_TIME
                and context.venue == Venue.AWAY
                and context.fav_status == FavStatus.FAVOURITE
                and context.ht_score_delta is not None and context.ht_score_delta < 0
                and "encourage" in disallow
            ):
                final.notes.append("Away favourite trailing at HT: avoid praise/encourage â€” go calm/supportive or firm.")
    except Exception:
        # Non-fatal: metadata only
        pass
    # Populate unit segmentation and nudges metadata
    try:
        final.unit_notes = analyze_units(context)
        final.nudges = generate_nudges(context)
    except Exception:
        pass
    # Reaction-aware extra notes (explicit callouts for assertive HT losing scenarios)
    if (
        (context.stage == MatchStage.HALF_TIME and context.score_state == ScoreState.LOSING and final.gesture in ("Point Finger", "Hands on Hips"))
        or ("Show me something else in the second half." in final.team_talk)
    ):
        if any(r in context.player_reactions for r in (PlayerReaction.NERVOUS,)):
            final.notes.append("Nervous player: consider a quick individual faith talk (OA: 'I've got faith in you.') to settle them.")
        final.notes.append("For your composed striker: Pump Fists â€” 'You can make the difference.'")
    # Default talk audience to Team at talk stages if not set
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME) and not final.talk_audience:
        final.talk_audience = TalkAudience.TEAM
    # Optional ML feature logging (pre-ML)
    try:
        _maybe_log_ml_features(context, final, ab_stage="pre-ml")
    except Exception:
        pass
    # Optional ML inference re-ranking (guardrailed)
    try:
        final = _maybe_apply_ml_inference(context, final, _edge_now)
    except Exception:
        pass
    # Optional ML feature logging (post-ML, with suggestion metadata if any)
    try:
        _maybe_log_ml_features(context, final, ab_stage="post-ml")
    except Exception:
        pass
    return final


def _maybe_log_ml_features(context: Context, rec: Recommendation, ab_stage: str = "") -> None:
    """If enabled in config, append a CSV row of features/outcomes for offline ML.

    Config (engine_config.json):
    {
      "ml_assist": {
        "log_features": false,
        "path": "data/logs/ml/features.csv"
      }
    }
    """
    cfg_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "engine_config.json"
    cfg = json.loads(cfg_fp.read_text(encoding="utf-8")) if cfg_fp.exists() else {}
    ml = cfg.get("ml_assist", {}) or {}
    if not bool(ml.get("log_features", False)):
        return
    rel_path = ml.get("path", "data/logs/ml/features.csv")
    out_fp = Path(__file__).resolve().parent.parent / rel_path
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    # Build a minimal, safe feature set
    try:
        tier, edge, _ = detect_matchup_tier(context)
        tier_val = tier.value
    except Exception:
        tier_val, edge = "?", None
    # Try to retrieve ML suggestion meta (if any was computed)
    ml_meta = None
    for alt in getattr(rec, "alternatives", []) or []:
        if isinstance(alt, dict) and alt.get("type") == "ml-meta":
            ml_meta = alt
            break

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": context.stage.value,
        "venue": context.venue.value,
        "fav_status": context.fav_status.value,
        "score_state": getattr(context.score_state, "value", ""),
        "team_pos": context.team_position or "",
        "opp_pos": context.opponent_position or "",
        "team_form": context.team_form or "",
        "opp_form": context.opponent_form or "",
        "xg_for": context.xg_for or "",
        "xg_against": context.xg_against or "",
        "shots_for": context.shots_for or "",
        "shots_against": context.shots_against or "",
        "possession": context.possession_pct or "",
        "tier": tier_val,
        "edge": edge if edge is not None else "",
        "mentality": rec.mentality.value,
        "gesture": rec.gesture,
        "shout": rec.shout.value if hasattr(rec.shout, 'value') else str(rec.shout),
        "talk": rec.team_talk or "",
        "ab_stage": ab_stage,
        # ML metadata (may be empty on pre-ml)
        "ml_g_suggested": (ml_meta or {}).get("g_suggested", ""),
        "ml_g_p": (ml_meta or {}).get("g_p", ""),
        "ml_g_applied": (ml_meta or {}).get("g_applied", ""),
        "ml_s_suggested": (ml_meta or {}).get("s_suggested", ""),
        "ml_s_p": (ml_meta or {}).get("s_p", ""),
        "ml_s_applied": (ml_meta or {}).get("s_applied", ""),
    }
    write_header = not out_fp.exists()
    with out_fp.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


def _maybe_apply_ml_inference(context: Context, rec: Recommendation, edge: Optional[float]) -> Recommendation:
    """If enabled, load gesture/shout models and softly re-rank outputs without breaking guardrails.

    Uses engine_config.json/ml_assist:
      - inference_enabled: bool
      - model_dir: directory with gesture.joblib and/or shout.joblib
      - weight: blending factor [0..1] determining how much to trust ML suggestion
    Guardrails:
      - Never change talk stages' shout (remains NONE)
      - Only consider gestures present in catalogs; avoid Outstretched Arms in non-praise contexts
      - If model missing or low confidence (<0.4), skip
    """
    cfg_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "engine_config.json"
    cfg = json.loads(cfg_fp.read_text(encoding="utf-8")) if cfg_fp.exists() else {}
    ml = cfg.get("ml_assist", {}) or {}
    if not bool(ml.get("inference_enabled", False)):
        return rec
    # Stage toggle
    stages = ml.get("stages", {}) or {}
    allow_stage = bool(stages.get(context.stage.value, True))
    if not allow_stage:
        return rec
    weight = float(ml.get("weight", 0.25))
    model_dir = Path(__file__).resolve().parent.parent / str(ml.get("model_dir", "data/ml"))
    # Prepare features vector
    try:
        tier, _, _ = detect_matchup_tier(context)
        tier_val = tier.value
    except Exception:
        tier_val = None
    feats = extract_features(context, tier_val, edge)
    vec = to_vector_row(feats)
    out = replace(rec)
    # Gesture inference
    g_model = load_model(model_dir, "gesture")
    g_probs = predict_proba(g_model, vec) if g_model is not None else None
    ml_meta: Dict[str, Any] = {}
    if g_probs:
        # pick best non-OA in non-praise contexts
        sorted_g = sorted(g_probs.items(), key=lambda kv: kv[1], reverse=True)
        best_gesture, best_p = sorted_g[0]
        if not _is_praise_context(context) and best_gesture == "Outstretched Arms":
            # find next best
            for g, p in sorted_g[1:]:
                if g != "Outstretched Arms":
                    best_gesture, best_p = g, p
                    break
        if best_p >= 0.4 and best_gesture and best_gesture != out.gesture:
            # blend by weight through alternatives metadata as a nudge
            if weight >= 0.5:
                out.gesture = best_gesture
                try:
                    out.trace.append(f"ML re-rank: gesture → {best_gesture} (p={best_p:.2f}, w={weight})")
                except Exception:
                    pass
            else:
                out.alternatives.append({"type": "ml-suggested", "gesture": best_gesture, "p": round(best_p,2)})
            ml_meta.update({"g_suggested": best_gesture, "g_p": round(best_p,2), "g_applied": weight >= 0.5})
    # Shout inference (in-play only)
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        s_model = load_model(model_dir, "shout")
        s_probs = predict_proba(s_model, vec) if s_model is not None else None
        if s_probs:
            sorted_s = sorted(s_probs.items(), key=lambda kv: kv[1], reverse=True)
            best_shout, sp = sorted_s[0]
            # Never override guardrails like Praise when losing, etc. Keep simple: only suggest if NONE
            if sp >= 0.45 and out.shout == Shout.NONE:
                try:
                    out.shout = Shout(best_shout)
                    out.trace.append(f"ML re-rank: shout → {best_shout} (p={sp:.2f}, w={weight})")
                except Exception:
                    pass
                ml_meta.update({"s_suggested": best_shout, "s_p": round(sp,2), "s_applied": True})
            else:
                ml_meta.update({"s_suggested": best_shout, "s_p": round(sp,2), "s_applied": False})
    # Attach ML meta for logging
    if ml_meta:
        out.alternatives.append({"type": "ml-meta", **ml_meta})
    return out
