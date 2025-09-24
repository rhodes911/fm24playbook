"""
Domain Models for FM24 Matchday Playbook

These are pure data models with no Streamlit dependencies.
They define the core domain language and data structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MatchStage(str, Enum):
    """Match stages with time ranges"""
    PRE_MATCH = "PreMatch"
    EARLY = "Early"           # 0-25 minutes
    MID = "Mid"              # 25-65 minutes
    HALF_TIME = "HalfTime"
    LATE = "Late"            # 65-85 minutes
    VERY_LATE = "VeryLate"   # 85+ minutes
    FULL_TIME = "FullTime"
    # Extra time phases and shootout prep
    ET_FIRST_HALF = "ET_FirstHalf"
    ET_HALF_TIME = "ET_HalfTime"
    ET_SECOND_HALF = "ET_SecondHalf"
    PRE_SHOOTOUT = "PreShootout"


class FavStatus(str, Enum):
    """Team favoritism status"""
    FAVOURITE = "Favourite"
    UNDERDOG = "Underdog"


class Venue(str, Enum):
    """Match venue"""
    HOME = "Home"
    AWAY = "Away"


class ScoreState(str, Enum):
    """Current score situation"""
    WINNING = "Winning"
    DRAWING = "Drawing"
    LOSING = "Losing"


class SpecialSituation(str, Enum):
    """Special match situations"""
    DERBY = "Derby"
    CUP = "Cup"
    FINAL = "Final"
    PROMOTION = "Promotion"
    RELEGATION = "Relegation"
    DOWN_TO_10 = "DownTo10"
    OPPONENT_DOWN_TO_10 = "OpponentDownTo10"
    NONE = "None"


class Mentality(str, Enum):
    """Team mentality options"""
    DEFENSIVE = "Defensive"           # -2
    CAUTIOUS = "Cautious"            # -1
    BALANCED = "Balanced"            #  0
    POSITIVE = "Positive"            # +1
    ATTACKING = "Attacking"          # +2
    VERY_ATTACKING = "Very Attacking" # +3


class Shout(str, Enum):
    """Available team shouts"""
    ENCOURAGE = "Encourage"
    DEMAND_MORE = "Demand More"
    FOCUS = "Focus"
    FIRE_UP = "Fire Up"
    PRAISE = "Praise"
    NONE = "None"


class PlayerReaction(str, Enum):
    """Player reaction states"""
    COMPLACENT = "Complacent"
    NERVOUS = "Nervous"
    LACKING_BELIEF = "LackingBelief"
    FIRED_UP = "FiredUp"
    SWITCHED_OFF = "SwitchedOff"


class TalkAudience(str, Enum):
    """Audience for team talks/statements at pre/half/full time."""
    TEAM = "Team"
    DEFENCE = "Defence"
    MIDFIELD = "Midfield"
    ATTACK = "Attack"
    INDIVIDUAL = "Individual"
    BENCH = "Bench"
    LEADERS = "Leaders"


@dataclass
class Context:
    """Match context that drives recommendations"""
    stage: MatchStage
    fav_status: FavStatus
    venue: Venue
    score_state: Optional[ScoreState] = None
    special_situations: List[SpecialSituation] = field(default_factory=list)
    player_reactions: List[PlayerReaction] = field(default_factory=list)
    # Optional league/table context
    team_position: Optional[int] = None
    opponent_position: Optional[int] = None
    # Optional recent form (up to 5 chars of W/D/L)
    team_form: Optional[str] = None
    opponent_form: Optional[str] = None
    # Optional current score
    team_goals: Optional[int] = None
    opponent_goals: Optional[int] = None
    # Auto-detect favourite/underdog based on positions/form/venue
    auto_fav_status: bool = False
    # Optional: user-preferred team talk audience at talk stages
    preferred_talk_audience: Optional[TalkAudience] = None
    # New advanced inputs
    morale_trend: Optional[int] = None  # -2 (slumping) .. +2 (surging)
    ht_score_delta: Optional[int] = None  # team_goals - opp_goals at HT
    xthreat_delta: Optional[float] = None  # momentum proxy: -1.0..+1.0
    cards_yellow: int = 0
    cards_red: int = 0
    injuries: int = 0
    # Optional unit average ratings for audience segmentation
    unit_ratings: Optional[Dict[str, float]] = None  # keys: Defence, Midfield, Attack
    
    def __str__(self) -> str:
        """Human-readable context description"""
        parts = [self.fav_status.value, self.venue.value]
        if self.score_state:
            parts.append(self.score_state.value)
        if self.special_situations and self.special_situations != [SpecialSituation.NONE]:
            parts.extend([s.value for s in self.special_situations if s != SpecialSituation.NONE])
        # Scoreline if available
        if self.team_goals is not None and self.opponent_goals is not None:
            parts.insert(0, f"{self.team_goals}–{self.opponent_goals}")
        # Append compact league context if provided
        pos = []
        if self.team_position is not None:
            pos.append(str(self.team_position))
        if self.opponent_position is not None:
            pos.append(str(self.opponent_position))
        if pos:
            parts.append(f"Pos {pos[0]} vs {pos[1] if len(pos)>1 else '?'}")
        # Append compact form if provided
        if self.team_form or self.opponent_form:
            tf = (self.team_form or '').upper()
            of = (self.opponent_form or '').upper()
            parts.append(f"Form {tf or '?'} vs {of or '?'}")
        return " • ".join(parts)


@dataclass
class Recommendation:
    """Complete tactical recommendation"""
    mentality: Mentality
    team_talk: str
    gesture: str
    shout: Shout
    talk_audience: Optional[TalkAudience] = None
    notes: List[str] = field(default_factory=list)
    # Additional metadata for rationale and options
    confidence: float = 0.0  # 0..1 confidence in primary talk+gesture
    risk: str = "neutral"  # safe | neutral | bold
    # Safer/bolder alternatives with simple dict entries
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    # Micro-targeted nudges (per-player or unit guidance)
    nudges: List[str] = field(default_factory=list)
    # Optional unit-level notes (e.g., "DEF: sympathise")
    unit_notes: Dict[str, str] = field(default_factory=dict)
    
    @property
    def mentality_value(self) -> int:
        """Get numeric value for mentality calculations"""
        mentality_values = {
            Mentality.DEFENSIVE: -2,
            Mentality.CAUTIOUS: -1,
            Mentality.BALANCED: 0,
            Mentality.POSITIVE: 1,
            Mentality.ATTACKING: 2,
            Mentality.VERY_ATTACKING: 3
        }
        return mentality_values[self.mentality]


class RuleCondition(BaseModel):
    """Condition that triggers a rule"""
    stage: MatchStage
    favStatus: Optional[FavStatus] = None
    venue: Optional[Venue] = None
    scoreState: Optional[ScoreState] = None
    special: Optional[List[SpecialSituation]] = None


class RuleRecommendation(BaseModel):
    """Recommendation part of a rule"""
    mentality: Mentality
    teamTalk: str
    gesture: str
    shout: Shout
    audience: Optional[TalkAudience] = None
    notes: List[str] = Field(default_factory=list)


class PlaybookRule(BaseModel):
    """Complete playbook rule"""
    when: RuleCondition
    recommendation: RuleRecommendation


class ReactionAdjustment(BaseModel):
    """Adjustment to apply for player reactions"""
    teamTalk: Optional[str] = None
    gesture: Optional[str] = None
    shout: Optional[Shout] = None
    mentalityDelta: int = 0
    notes: List[str] = Field(default_factory=list)


class ReactionRule(BaseModel):
    """Rule for handling player reactions"""
    reaction: PlayerReaction
    adjustment: ReactionAdjustment


class SpecialOverride(BaseModel):
    """Override for special situations"""
    teamTalk: Optional[str] = None
    gesture: Optional[str] = None
    shout: Optional[Shout] = None
    mentality: Optional[Mentality] = None


class SpecialRule(BaseModel):
    """Special situation rule"""
    tag: SpecialSituation
    overrides: Dict[str, SpecialOverride]


class PlaybookData(BaseModel):
    """Complete playbook data structure"""
    schema_: str = Field(alias="$schema")
    version: str
    gestures: List[str]
    rules: List[PlaybookRule]
    reactions: List[ReactionRule]
    special: List[SpecialRule]


@dataclass
class PresetScenario:
    """Predefined scenario for quick selection"""
    name: str
    description: str
    context: Context
    tags: List[str] = field(default_factory=list)