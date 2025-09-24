"""
Preset scenarios to drive the Scenarios page.
This module can also load presets from data/presets.json via services.repository.
"""
from typing import List
from .models import (
    Context, PresetScenario,
    MatchStage, FavStatus, Venue, ScoreState, SpecialSituation, PlayerReaction
)


def builtin_presets() -> List[PresetScenario]:
    return [
        PresetScenario(
            name="Pre-Match Favourite Home",
            description="You are favourites at home before kickoff.",
            context=Context(
                stage=MatchStage.PRE_MATCH,
                fav_status=FavStatus.FAVOURITE,
                venue=Venue.HOME,
                score_state=None,
                special_situations=[],
                player_reactions=[]
            ),
            tags=["PreMatch", "Favourite", "Home"],
        ),
        PresetScenario(
            name="Early Underdog Away Drawing",
            description="Underdog away, early stage, drawing.",
            context=Context(
                stage=MatchStage.EARLY,
                fav_status=FavStatus.UNDERDOG,
                venue=Venue.AWAY,
                score_state=ScoreState.DRAWING,
                special_situations=[],
                player_reactions=[]
            ),
            tags=["Early", "Underdog", "Away", "Drawing"],
        ),
        PresetScenario(
            name="Half-Time Winning (Derby)",
            description="Leading at half-time in a derby.",
            context=Context(
                stage=MatchStage.HALF_TIME,
                fav_status=FavStatus.FAVOURITE,
                venue=Venue.HOME,
                score_state=ScoreState.WINNING,
                special_situations=[SpecialSituation.DERBY],
                player_reactions=[]
            ),
            tags=["HalfTime", "Winning", "Derby"],
        ),
    ]