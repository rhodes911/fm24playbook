from domain.models import *
from domain.rules_engine import recommend, detect_matchup_tier


def make_ctx(**kwargs):
    defaults = dict(stage=MatchStage.HALF_TIME, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME, score_state=ScoreState.DRAWING)
    defaults.update(kwargs)
    return Context(**defaults)


def test_ht_drawing_strong_fav_remains_assertive():
    ctx = make_ctx()
    # Strong favourite proxy: much better position and form
    ctx.team_position = 2
    ctx.opponent_position = 15
    ctx.team_form = "WWWWW"
    ctx.opponent_form = "LLLLL"
    tier, edge, _ = detect_matchup_tier(ctx)
    assert tier in (FavTier.SLIGHT_FAVOURITE, FavTier.STRONG_FAVOURITE)
    rec = recommend(ctx)
    assert rec is not None
    # Should keep assertive family (Point Finger or Hands on Hips via tier soften)
    assert rec.gesture in ("Point Finger", "Hands on Hips")
    assert rec.shout == Shout.NONE


def test_ht_drawing_slight_fav_soften_to_hands_on_hips():
    ctx = make_ctx()
    # Slight favourite proxy: small pos/form edge
    ctx.team_position = 6
    ctx.opponent_position = 9
    ctx.team_form = "WWDLW"
    ctx.opponent_form = "LDLLD"
    rec = recommend(ctx)
    assert rec is not None
    # Tier-informed tweak may soften to Hands on Hips from Point Finger
    assert rec.gesture in ("Point Finger", "Hands on Hips")
    assert rec.shout == Shout.NONE


def test_ht_drawing_even_with_positive_edge_supportive():
    ctx = make_ctx(fav_status=FavStatus.UNDERDOG)
    # Even-ish but we'll give a small positive edge via shots/xG
    ctx.team_position = 10
    ctx.opponent_position = 11
    ctx.team_form = "WDDLD"
    ctx.opponent_form = "DDLWD"
    ctx.shots_for = 10
    ctx.shots_against = 6
    ctx.xg_for = 0.9
    ctx.xg_against = 0.5
    rec = recommend(ctx)
    assert rec is not None
    # Supportive trajectory preferred
    assert rec.gesture in ("Hands Together", "Hands on Hips")
    assert rec.shout == Shout.NONE


def test_inplay_very_late_drawing_strong_favourite_focus():
    ctx = Context(
        stage=MatchStage.VERY_LATE,
        fav_status=FavStatus.FAVOURITE,
        venue=Venue.HOME,
        score_state=ScoreState.DRAWING,
        team_position=1,
        opponent_position=14,
        team_form="WWWWW",
        opponent_form="LLLLL",
    )
    rec = recommend(ctx)
    assert rec is not None
    assert rec.shout in (Shout.FOCUS, Shout.DEMAND_MORE)