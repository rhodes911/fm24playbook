"""
Rules Engine: maps Context → Recommendation using data/playbook.json
This module has no Streamlit/UI code and can be tested independently.
"""
from __future__ import annotations

from typing import List, Optional, Tuple, Dict
from pathlib import Path
import json
from dataclasses import replace

from .models import (
    Context, Recommendation,
    Mentality, Shout,
    MatchStage, FavStatus, Venue, ScoreState, SpecialSituation, TalkAudience,
    PlayerReaction,
    PlaybookData, PlaybookRule, ReactionRule, SpecialRule
)
from .tone_matrix import select_tones
from .segmentation import analyze_units
from .nudges import generate_nudges
from .synergy import score_synergy, suggest_gestures

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


# Gesture → tone mapping (aligned with gestures.json categories)
_GESTURE_TONE = {
    # calm
    "Hands Together": "calm",
    "Outstretched Arms": "calm",
    # assertive
    "Point Finger": "assertive",
    "Hands on Hips": "assertive",
    # angry
    "Thrash Arms": "angry",
    "Throw water bottle": "angry",
    # motivational
    "Pump Fists": "motivational",
    # relaxed
    "Hands in Pockets": "relaxed",
}

# Gesture-specific templates for scenarios where FM limits lines by gesture.
# Only populate where we know the sets; otherwise fall back to tone-based.
_GESTURE_TEMPLATES: Dict[Tuple[MatchStage, Optional[ScoreState]], Dict[str, List[str]]] = {
    # Pre-Match (gesture-limited lines exist in FM; especially OA for underdogs)
    (MatchStage.PRE_MATCH, None): {
        "Outstretched Arms": [
            "Nobody expects anything from us today — go out there and enjoy it.",
            "We're the underdogs here — show everyone what we're capable of.",
            "No pressure — play your football and have fun out there.",
            "Good luck out there — we’ll need it, so give the fans a performance to cheer for.",
        ],
        "Hands Together": [
            "No pressure here — relax and play your natural game.",
            "Stay calm and trust your shape — the performance will come.",
        ],
    },
    # Half-Time, losing
    (MatchStage.HALF_TIME, ScoreState.LOSING): {
        # Outstretched Arms: supportive/praise/faith (no hard admonishments)
        "Outstretched Arms": [
            "It’s time to dig in and give everything — we deserve something from this.",
            "I know there’s more in here — show what you’re about in the second half.",
            "You’ve been a bit unlucky so far — keep going and the chance will come.",
            "Go out there and give these fans their money’s worth.",
            "You can go out there and play without pressure now.",
            "The media have given you a lot of credit — go put on a worthy display.",
            "I’ve got faith in you.",
        ],
        # Point Finger: firm/critical prompts
        "Point Finger": [
            "Show me something else in the second half.",
            "Not acceptable so far — sort it out.",
            "Our shooting hasn’t been good enough — it must improve.",
            "I’m disappointed — not creative enough and not positive enough.",
            "Lift the intensity — win more duels and second balls.",
        ],
        # Hands Together: calm supportive
        "Hands Together": [
            "Stay composed and trust your shape — the chance will come.",
            "Keep your focus — we’ll turn this if we do the basics well.",
            "Be brave on the ball but keep our structure.",
        ],
        # Hands on Hips: assertive expectations
        "Hands on Hips": [
            "I expect more — raise the level.",
            "You’re better than this — prove it now.",
        ],
        # Pump Fists: motivational push
        "Pump Fists": [
            "You can turn this around — believe.",
            "One big effort — go and change it.",
        ],
        # Thrash Arms: angry hairdryer (use sparingly)
        "Thrash Arms": [
            "Unacceptable — show me a response.",
        ],
    }
}

# Tone-aware overlays for stats-driven phrasing at talk stages
_STATS_OVERLAY_TEMPLATES: Dict[str, Dict[str, str]] = {
    # When on top but not ahead (out-shooting or big xG delta)
    "push_on": {
        "calm": "We're on top — keep going and the goal will come.",
        "assertive": "We've had the chances — be sharper and make it count.",
        "motivational": "This is there for you — keep pushing and believe.",
        "relaxed": "Stay composed — our moment will come.",
        "angry": "We should be ahead — raise the standard in the box.",
    },
    # When under pressure while ahead late
    "see_it_out": {
        "calm": "Stay switched on and manage the game.",
        "assertive": "Concentrate — see it out.",
        "motivational": "Dig in together — finish the job.",
        "relaxed": "Keep it tidy and close it out.",
        "angry": "Cut out the chances we're gifting them.",
    },
    # When low possession as favourites and not winning
    "take_control": {
        "calm": "Keep it simple, secure possession, and build.",
        "assertive": "Be braver in possession — take control.",
        "motivational": "Show for the ball and impose yourselves.",
        "relaxed": "Settle down and keep the ball.",
        "angry": "Stop forcing it — take care of the ball.",
    },
}

# Talk templates chosen by stage/score and tone to ensure valid FM combos
_TALK_TEMPLATES = {
    MatchStage.PRE_MATCH: {
        # Use short, FM-style paraphrases (not verbatim) grouped by tone.
        "calm": [
            "All the best out there today, have fun!",
            "No pressure here — play your football and the result will take care of itself.",
            "Just go out there, relax and play your natural game.",
        ],
        "assertive": [
            "We’re favourites for a reason — make sure they’re left in no doubt.",
            "We’re favourites here and I want us to play like it.",
            "Go out there and give the supporters a performance to cheer for.",
        ],
        "motivational": [
            "Be bold and give the fans something to shout about.",
            "Play with belief and intensity from the first whistle.",
        ],
        "relaxed": [
            "The pressure’s off — play your natural game.",
            "Ignore the recent praise in the media and just play your natural game.",
        ],
        "angry": [
            "Standards must be higher — do not let them drop.",
        ],
    },
    MatchStage.HALF_TIME: {
        ScoreState.WINNING: {
            "calm": [
                "I’m pleased so far — keep it going.",
                "Good first half — stay focused and do the basics well.",
            ],
            "assertive": [
                "Don’t get complacent — see the job through.",
                "We set the standard — maintain it and finish the job.",
            ],
            "motivational": [
                "You’ve got them — keep pushing!",
                "One big effort — squeeze the game in our favour.",
            ],
            "relaxed": [
                "Stay composed and do the basics.",
            ],
            "angry": [
                "We dropped off — raise it second half.",
            ],
        },
        ScoreState.DRAWING: {
            "calm": [
                "No pressure — play without fear.",
                "Keep your shape and trust your game.",
            ],
            "assertive": [
                "I expect more — we can improve.",
                "Be sharper — take care in the final action.",
            ],
            "motivational": [
                "This game is there for you — go and take it.",
                "Believe — the breakthrough is coming.",
            ],
            "relaxed": [
                "Relax and play your natural game.",
            ],
            "angry": [
                "Not enough — standards higher.",
            ],
        },
        ScoreState.LOSING: {
            "calm": [
                "I know there’s more in here — show what you’re about in the second half.",
                "It’s time to dig in and give everything — we deserve something from this.",
                "You’ve been a bit unlucky so far — keep going and the chance will come.",
            ],
            "assertive": [
                "Show me something else in the second half.",
                "Not acceptable so far — sort it out.",
                "Finishing hasn’t been good enough — it must improve.",
                "I’m disappointed — not creative enough and not positive enough.",
                "That wasn’t good enough — I expect a reaction.",
                "Lift the intensity — win more duels and second balls.",
            ],
            "motivational": [
                "You can turn this around — believe.",
                "This is there for you — go and change it.",
            ],
            "relaxed": [
                "Reset, trust your game and take the next chance.",
            ],
            "angry": [
                "Unacceptable first half — show me a response.",
            ],
        },
    },
    MatchStage.FULL_TIME: {
        ScoreState.WINNING: {
            "calm": [
                "Well done — a good win.",
                "Solid win — take the positives and recover well.",
            ],
            "assertive": [
                "Good — but don’t let standards slip next time.",
                "Job done — standards stay high for the next one.",
            ],
            "motivational": [
                "Brilliant — enjoy it and build on it.",
                "Great performance — take this momentum forward.",
            ],
            "relaxed": [
                "Enjoy the moment — you earned it.",
            ],
            "angry": [
                "We won, but the standards weren’t there.",
            ],
        },
        ScoreState.DRAWING: {
            "calm": [
                "A fair result — take the point and move on.",
                "Plenty to learn — we move on together.",
            ],
            "assertive": [
                "We should have done more — be sharper next time.",
                "Not the level required — raise it next match.",
            ],
            "motivational": [
                "Plenty to build on — take this into the next one.",
            ],
            "relaxed": [
                "Take the positives and recover well.",
            ],
            "angry": [
                "Not the level we expect.",
            ],
        },
        ScoreState.LOSING: {
            "calm": [
                "Keep your heads up — learn and go again.",
                "Reset and be ready to respond in the next one.",
            ],
            "assertive": [
                "Not good enough — I expect a reaction next time.",
                "That level isn’t acceptable — show a response.",
            ],
            "motivational": [
                "We’ll put it right — together.",
            ],
            "relaxed": [
                "Recover well and we go again.",
            ],
            "angry": [
                "Unacceptable — we must be better.",
            ],
        },
    },
}

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


def _gesture_tone(gesture: str) -> str:
    return _GESTURE_TONE.get(gesture, "calm")


def _select_talk_phrase(context: Context, tone: str, gesture: Optional[str] = None) -> Optional[str]:
    stage = context.stage
    score_state = context.score_state
    # Prefer gesture-specific templates when available for this stage/score
    if gesture:
        gtbl = _GESTURE_TEMPLATES.get((stage, score_state)) or _GESTURE_TEMPLATES.get((stage, None))
        if gtbl is not None and gesture in gtbl:
            items = gtbl[gesture]
            if items:
                # Light heuristic: when away and losing, prefer "dig in" supportive second line for OA
                if stage == MatchStage.HALF_TIME and score_state == ScoreState.LOSING and gesture == "Outstretched Arms" and context.venue == Venue.AWAY and len(items) >= 2:
                    return items[0] if context.fav_status == FavStatus.FAVOURITE else items[1]
                return items[0]
    tbl = _TALK_TEMPLATES.get(stage)
    if not tbl:
        return None
    if stage == MatchStage.PRE_MATCH:
        items = tbl.get(tone)  # type: ignore[attr-defined]
        if not items:
            return None
        if isinstance(items, list):
            # If normalized mapping exists for gesture → allowed indices, use it first
            allowed = _allowed_statement_indices(stage, None, gesture, tone)
            if allowed:
                for idx in allowed:
                    if 0 <= idx < len(items):
                        return items[idx]
            # Heuristic pick inside the tone bucket
            if tone == "assertive":
                if context.fav_status == FavStatus.FAVOURITE and context.venue == Venue.HOME:
                    # Prefer home-flavoured assertive line (index 1)
                    return items[1]
                if context.fav_status == FavStatus.FAVOURITE and context.venue == Venue.AWAY and len(items) >= 3:
                    # Prefer away-flavoured assertive line (index 2)
                    return items[2]
            # Fall back to the first option for the tone
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

    This avoids recommending combos that don’t exist in FM’s UI (tone drives available lines).
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    # If a special override has already provided a concrete phrase, keep it.
    if rec.team_talk and rec.team_talk.strip():
        return rec
    tone = _gesture_tone(rec.gesture)
    phrase = _select_talk_phrase(context, tone, rec.gesture)
    if phrase:
        return replace(rec, team_talk=phrase)
    return rec


def adapt_talk_phrase_with_stats(context: Context, rec: Recommendation) -> Recommendation:
    """Rewrite the team talk phrase itself based on live stats in a tone-aware way.

    Applies only at talk stages (PreMatch/HalfTime/FullTime) and only when stats are present.
    Priority:
      1) Out-shooting/xG advantage but drawing/losing → push_on
      2) Being out-shot and protecting a lead late → see_it_out
      3) Low possession (<40) as favourites and not winning → take_control
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
    # Pick tone-specific phrase; fallback to calm if tone not present
    tbl = _STATS_OVERLAY_TEMPLATES.get(overlay_key, {})
    new_phrase = tbl.get(tone) or tbl.get("calm")
    if not new_phrase:
        return rec
    # Replace the phrase with the overlay version
    return replace(rec, team_talk=new_phrase)


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
        * Favourite → Point Finger
        * Underdog → Hands Together (avoid OA framing pre-match)
    - HalfTime:
        * Losing → Favourite: Point Finger (if <= -2: Thrash Arms)
                  → Underdog: Hands Together
        * Drawing → Favourite: Point Finger; Underdog: Hands Together
        * Winning → Hands Together (if complacent reaction present then Point Finger)
    - FullTime:
        * Winning → Hands Together
        * Drawing → Favourite: Hands on Hips; Underdog: Outstretched Arms
        * Losing → Favourite: Thrash Arms; Underdog: Hands Together
    Additionally, if a resulting gesture is OA in a non‑praise context, switch to Hands Together.
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
        return replace(rec, gesture=g)
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
        return capped
    return rec


def choose_inplay_shout(context: Context, rec: Recommendation) -> Recommendation:
    """Heuristic shout selector for in-play stages when none specified by rules.

    - Winning:
      - Underdog → Praise
      - Favourite at Late/VeryLate → Focus
    - Drawing:
      - Favourite → Demand More
      - Underdog → Encourage
    - Losing:
      - Favourite → Fire Up (Early/Mid), Demand More (Late/VeryLate)
      - Underdog → Encourage
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
        elif context.stage in (MatchStage.LATE, MatchStage.VERY_LATE):
            result.shout = Shout.FOCUS
            result.notes.append("Protect the lead late: Focus.")
    elif context.score_state == ScoreState.DRAWING:
        if context.fav_status == FavStatus.FAVOURITE:
            result.shout = Shout.DEMAND_MORE
            result.notes.append("Favourite drawing: Demand More to push on.")
        else:
            result.shout = Shout.ENCOURAGE
            result.notes.append("Underdog drawing: Encourage to keep belief.")
    elif context.score_state == ScoreState.LOSING:
        if context.fav_status == FavStatus.FAVOURITE:
            if context.stage in (MatchStage.EARLY, MatchStage.MID):
                result.shout = Shout.FIRE_UP
                result.notes.append("Favourite losing early: Fire Up for reaction.")
            else:
                result.shout = Shout.DEMAND_MORE
                result.notes.append("Favourite losing late: Demand More to chase.")
        else:
            result.shout = Shout.ENCOURAGE
            result.notes.append("Underdog losing: Encourage to avoid collapse.")
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
    else:
        result.notes.append("Late-game control: tighten up with a narrow lead.")
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
        result.notes.append("We're creating more — keep belief and maintain intensity.")
        if result.shout == Shout.NONE and context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
            result.shout = Shout.ENCOURAGE

    # Being out-shot and protecting a lead late
    if context.score_state == ScoreState.WINNING and (sa > sf + 4 or soa > sof + 2) and context.stage in (MatchStage.LATE, MatchStage.VERY_LATE):
        result.notes.append("They're peppering us — tighten up and concentrate.")
        if result.shout == Shout.NONE:
            result.shout = Shout.FOCUS

    # Low possession while favourite and not winning
    if poss is not None and poss < 40 and context.fav_status == FavStatus.FAVOURITE and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        result.notes.append("Possession low for a favourite — consider calming it down and keeping it simple.")

    # Big xG delta in our favour but not leading
    if (xg_for - xg_against) > 0.6 and context.score_state in (ScoreState.DRAWING, ScoreState.LOSING):
        result.notes.append("xG says we're on top — keep pushing, the goal should come.")

    return result


def detect_fav_status(context: Context) -> Tuple[FavStatus, str]:
    """Heuristic to infer Favourite/Underdog with a short explanation string.

    Scoring: position (±1 if gap >=3), form (±1 if diff >=2), home (+1 if home).
    """
    score = 0
    parts: List[str] = []
    if context.team_position is not None and context.opponent_position is not None:
        pos_delta = context.opponent_position - context.team_position
        if pos_delta >= 3:
            score += 1
            parts.append("pos +1")
        elif pos_delta <= -3:
            score -= 1
            parts.append("pos -1")
        else:
            parts.append("pos 0")
    else:
        parts.append("pos ?")

    form_delta = _score_form(context.team_form) - _score_form(context.opponent_form)
    if form_delta >= 2:
        score += 1
        parts.append("form +1")
    elif form_delta <= -2:
        score -= 1
        parts.append("form -1")
    else:
        parts.append("form 0")

    if context.venue == Venue.HOME:
        score += 1
        parts.append("home +1")
    else:
        parts.append("away 0")

    fav = FavStatus.FAVOURITE if score >= 1 else FavStatus.UNDERDOG
    explanation = f"{fav.value} (score {score}: " + ", ".join(parts) + ")"
    return fav, explanation


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
    return Recommendation(
        mentality=rec.mentality,
        team_talk=rec.teamTalk,
        gesture=rec.gesture,
        shout=rec.shout,
        talk_audience=rec.audience,
        notes=list(rec.notes),
    )


def _score_form(form: Optional[str]) -> int:
    if not form:
        return 0
    m = {"W": 1, "D": 0, "L": -1}
    return sum(m.get(ch.upper(), 0) for ch in form[:5])


def apply_context_stats_adjustments(context: Context, rec: Recommendation) -> Recommendation:
    """Adjust mentality (±1) and optionally shout based on league positions, recent form, and venue.

    Heuristic:
    - Position gap: >=8 places advantage → +1; <=-8 disadvantage → -1
    - Form diff: score(team) - score(opp). >=2 → +1; <=-2 → -1
    - Home adds +1 to the combined score (away adds 0)
    Mapping: total >= 2 → mentality +1; total <= -2 → mentality -1; else 0
    If base shout is None, suggest Demand More for +1, Encourage for -1.
    """
    total = 0
    # Position bucket
    if context.team_position is not None and context.opponent_position is not None:
        pos_diff = context.opponent_position - context.team_position
        if pos_diff >= 8:
            total += 1
        elif pos_diff <= -8:
            total -= 1
    # Form bucket
    form_diff = _score_form(context.team_form) - _score_form(context.opponent_form)
    if form_diff >= 2:
        total += 1
    elif form_diff <= -2:
        total -= 1
    # Home advantage
    if context.venue == Venue.HOME:
        total += 1

    delta = 0
    if total >= 2:
        delta = 1
    elif total <= -2:
        delta = -1

    if delta == 0:
        return rec

    # Apply mentality delta
    mval = MENTALITY_TO_VALUE[rec.mentality] + delta
    new_mentality = clamp_mentality(mval)
    result = replace(rec, mentality=new_mentality)

    # Suggest shout only if none already set
    if result.shout == Shout.NONE:
        result.shout = Shout.DEMAND_MORE if delta > 0 else Shout.ENCOURAGE

    # Add explanatory note
    if delta > 0:
        result.notes.append("Favorable position/form and home advantage suggest a more assertive approach.")
    else:
        result.notes.append("Position/form context suggests caution (especially away).")

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
            if ov.teamTalk:
                result.team_talk = ov.teamTalk
            if ov.gesture:
                result.gesture = ov.gesture
            if ov.shout:
                result.shout = ov.shout
            if ov.mentality:
                result.mentality = ov.mentality
    return result


def apply_reaction_adjustments(context: Context, rec: Recommendation, reactions: List[ReactionRule]) -> Recommendation:
    """Apply all reaction adjustments: teamTalk/gesture/shout overwrites if present, notes merged, mentality delta summed."""
    result = replace(rec)
    mentality_value = MENTALITY_TO_VALUE[result.mentality]

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

    # clamp mentality
    result.mentality = clamp_mentality(mentality_value)
    # dedupe notes while preserving order
    seen = set()
    deduped = []
    for n in result.notes:
        if n not in seen:
            deduped.append(n)
            seen.add(n)
    result.notes = deduped
    return result


def recommend(context: Context, playbook: PlaybookData) -> Optional[Recommendation]:
    """Compute recommendation end-to-end."""
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
    base = pick_base_rule(context, playbook.rules)
    if base is None:
        return None
    with_specials = apply_special_overrides(context, base, playbook.special)
    # No shouts at PreMatch, HalfTime, FullTime — convert to statements
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        with_specials.shout = Shout.NONE
    with_stats = apply_context_stats_adjustments(context, with_specials)
    if fav_explanation:
        with_stats.notes.append(f"Auto status: {fav_explanation}")
    # In-play shout selection if none set yet
    with_shout = choose_inplay_shout(context, with_stats)
    with_time = apply_time_score_heuristics(context, with_shout)
    with_stats_live = apply_live_stats_heuristics(context, with_time)
    final = apply_reaction_adjustments(context, with_stats_live, playbook.reactions)
    # Post-adjust gesture to avoid praise-coded OA when behind and pick assertive for favourites
    final = adjust_gesture_for_context(context, final)
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
                final.notes.append("Away favourite trailing at HT: avoid praise/encourage — go calm/supportive or firm.")
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
        final.notes.append("For your composed striker: Pump Fists — 'You can make the difference.'")
    # Default talk audience to Team at talk stages if not set
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME) and not final.talk_audience:
        final.talk_audience = TalkAudience.TEAM
    return final