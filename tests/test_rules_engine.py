from domain.models import *
from domain.rules_engine import recommend, detect_fav_status


def make_ctx(**kwargs):
    defaults = dict(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    defaults.update(kwargs)
    return Context(**defaults)


def test_base_recommendation_loaded():
    ctx = make_ctx()
    rec = recommend(ctx)
    assert rec is not None
    assert rec.team_talk


def test_reaction_adjustment_changes_shout():
    ctx = make_ctx(player_reactions=[PlayerReaction.NERVOUS])
    rec = recommend(ctx)
    assert rec is not None
    assert rec.shout == Shout.ENCOURAGE


def test_form_position_home_advantage_adjusts_mentality():
    # Base rule for prematch favourite home yields Positive
    ctx = make_ctx(
        stage=MatchStage.PRE_MATCH,
        fav_status=FavStatus.FAVOURITE,
        venue=Venue.HOME,
    )
    # Strong advantage: better position by 10, better form by >=2, at home
    ctx.team_position = 3
    ctx.opponent_position = 13
    ctx.team_form = "WWDLW"  # score 3
    ctx.opponent_form = "LDLLD"  # score -3
    rec = recommend(ctx)
    assert rec is not None
    # With pre-match cap enabled in the engine, mentality should be capped to Positive
    assert rec.mentality == Mentality.POSITIVE
    # If shout was None, it should lean to Demand More
    assert rec.shout in (Shout.DEMAND_MORE, Shout.NONE)


def test_numeric_score_derives_score_state():
    ctx = make_ctx(stage=MatchStage.EARLY, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    ctx.team_goals = 1
    ctx.opponent_goals = 0
    rec = recommend(ctx)
    assert rec is not None
    # Early Winning path selects Focus + Balanced
    assert rec.shout == Shout.FOCUS


def test_favourite_detection_away_is_stricter():
    # Bristol Rovers case: Away, slightly worse position (7 vs 5), slightly better recent form.
    # With config: away penalty + require both pos and form to be favourite away, expect Underdog.
    ctx = Context(
        stage=MatchStage.PRE_MATCH,
        fav_status=FavStatus.FAVOURITE,  # initial value should be ignored by detect
        venue=Venue.AWAY,
        team_position=7,
        opponent_position=5,
        team_form="LWLDW",
        opponent_form="LLLWD",
    )
    fav, _ = detect_fav_status(ctx)
    assert fav == FavStatus.UNDERDOG


def test_halftime_losing_favourite_away_tone_and_gesture():
    # Away favourite losing at HT should be firm but constructive (Point Finger)
    ctx = Context(
        stage=MatchStage.HALF_TIME,
        fav_status=FavStatus.FAVOURITE,
        venue=Venue.AWAY,
        score_state=ScoreState.LOSING,
        ht_score_delta=-1,
    )
    rec = recommend(ctx)
    assert rec is not None
    assert rec.gesture in ("Point Finger", "Thrash Arms")  # thrash if -2 or worse per engine
    assert rec.shout == Shout.NONE


def test_halftime_drawing_favourite_vs_underdog_tier_aware_is_stable():
    # These should remain consistent with base rules even as tiers are considered
    ctx_fav = Context(stage=MatchStage.HALF_TIME, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME, score_state=ScoreState.DRAWING)
    ctx_dog = Context(stage=MatchStage.HALF_TIME, fav_status=FavStatus.UNDERDOG, venue=Venue.AWAY, score_state=ScoreState.DRAWING)
    rec_f = recommend(ctx_fav)
    rec_d = recommend(ctx_dog)
    assert rec_f is not None and rec_d is not None
    assert rec_f.shout == Shout.NONE and rec_d.shout == Shout.NONE
