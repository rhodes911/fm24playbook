from domain.models import *
from domain.rules_engine import recommend
from services.repository import PlaybookRepository


def make_ctx(**kwargs):
    defaults = dict(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    defaults.update(kwargs)
    return Context(**defaults)


def test_base_recommendation_loaded():
    repo = PlaybookRepository()
    pb = repo.load_playbook()
    ctx = make_ctx()
    rec = recommend(ctx, pb)
    assert rec is not None
    assert rec.team_talk


def test_reaction_adjustment_changes_shout():
    repo = PlaybookRepository()
    pb = repo.load_playbook()
    ctx = make_ctx(player_reactions=[PlayerReaction.NERVOUS])
    rec = recommend(ctx, pb)
    assert rec is not None
    assert rec.shout == Shout.ENCOURAGE


def test_form_position_home_advantage_adjusts_mentality():
    repo = PlaybookRepository()
    pb = repo.load_playbook()
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
    rec = recommend(ctx, pb)
    assert rec is not None
    # With pre-match cap enabled in the engine, mentality should be capped to Positive
    assert rec.mentality == Mentality.POSITIVE
    # If shout was None, it should lean to Demand More
    assert rec.shout in (Shout.DEMAND_MORE, Shout.NONE)


def test_numeric_score_derives_score_state():
    repo = PlaybookRepository()
    pb = repo.load_playbook()
    ctx = make_ctx(stage=MatchStage.EARLY, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    ctx.team_goals = 1
    ctx.opponent_goals = 0
    rec = recommend(ctx, pb)
    assert rec is not None
    # Early Winning path selects Focus + Balanced
    assert rec.shout == Shout.FOCUS
