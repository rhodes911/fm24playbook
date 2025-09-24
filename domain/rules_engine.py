"""
Rules Engine: maps Context → Recommendation using data/playbook.json
This module has no Streamlit/UI code and can be tested independently.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import replace

from .models import (
    Context, Recommendation,
    Mentality, Shout,
    MatchStage, FavStatus, Venue, ScoreState, SpecialSituation,
    PlaybookData, PlaybookRule, ReactionRule, SpecialRule
)

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

# Talk templates chosen by stage/score and tone to ensure valid FM combos
_TALK_TEMPLATES = {
    MatchStage.PRE_MATCH: {
        "calm": "All the best out there tonight, have fun!",
        "assertive": "I expect nothing but a win — go out and show your quality.",
        "motivational": "We can make this ours today — believe and go deliver.",
        "relaxed": "No pressure today — enjoy your football.",
        "angry": "I expect better — do not let standards drop.",
    },
    MatchStage.HALF_TIME: {
        ScoreState.WINNING: {
            "calm": "I'm happy with your performance so far, keep it up.",
            "assertive": "Don't get complacent — stay focused and finish the job.",
            "motivational": "You’ve got them — keep pushing!",
            "relaxed": "Stay composed and keep doing the basics.",
            "angry": "That dropped off — raise it second half.",
        },
        ScoreState.DRAWING: {
            "calm": "You can go out there and play without pressure now.",
            "assertive": "I expect more — we can improve.",
            "motivational": "This game is there for you — go and take it.",
            "relaxed": "No pressure — play your natural game.",
            "angry": "Not enough out there — demand higher standards.",
        },
        ScoreState.LOSING: {
            "calm": "Keep your heads — we can still get back into this.",
            "assertive": "That wasn't good enough — I expect a reaction.",
            "motivational": "You can still turn this around — believe.",
            "relaxed": "Reset, trust your game and take the next chance.",
            "angry": "Unacceptable first half — show me a response.",
        },
    },
    MatchStage.FULL_TIME: {
        ScoreState.WINNING: {
            "calm": "Well done — a good win.",
            "assertive": "Good — but don’t let standards slip next match.",
            "motivational": "Brilliant — enjoy it and build on it.",
            "relaxed": "Enjoy the moment — you earned it.",
            "angry": "We won, but the standards weren’t there.",
        },
        ScoreState.DRAWING: {
            "calm": "A fair result — take the point and move on.",
            "assertive": "We should have done more — be sharper next time.",
            "motivational": "Plenty to build on — take this into the next one.",
            "relaxed": "Take the positives and recover well.",
            "angry": "Not the level we expect.",
        },
        ScoreState.LOSING: {
            "calm": "Keep your heads up — learn and go again.",
            "assertive": "That wasn’t good enough — expect a reaction next time.",
            "motivational": "We’ll put it right — together.",
            "relaxed": "Recover well and we go again.",
            "angry": "Unacceptable — we must be better.",
        },
    },
}


def _gesture_tone(gesture: str) -> str:
    return _GESTURE_TONE.get(gesture, "calm")


def _select_talk_phrase(stage: MatchStage, score_state: Optional[ScoreState], tone: str) -> Optional[str]:
    tbl = _TALK_TEMPLATES.get(stage)
    if not tbl:
        return None
    if stage == MatchStage.PRE_MATCH:
        return tbl.get(tone)  # type: ignore[attr-defined]
    if score_state is None:
        return None
    stage_tbl = tbl.get(score_state)  # type: ignore[index]
    if not stage_tbl:
        return None
    return stage_tbl.get(tone)


def harmonize_talk_with_gesture(context: Context, rec: Recommendation) -> Recommendation:
    """Ensure the team talk phrase matches the tone implied by the chosen gesture.

    This avoids recommending combos that don’t exist in FM’s UI (tone drives available lines).
    """
    if context.stage not in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME):
        return rec
    tone = _gesture_tone(rec.gesture)
    phrase = _select_talk_phrase(context.stage, context.score_state, tone)
    if phrase:
        return replace(rec, team_talk=phrase)
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
    final = apply_reaction_adjustments(context, with_time, playbook.reactions)
    final = harmonize_talk_with_gesture(context, final)
    final = enforce_prematch_mentality_cap(context, final)
    # If user selected a preferred talk audience at talk stages, override
    if context.stage in (MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME) and context.preferred_talk_audience:
        final.talk_audience = context.preferred_talk_audience
    return final