from domain.models import Context, MatchStage, FavStatus, Venue, SpecialSituation
from domain.tone_matrix import select_tones


def make_ctx(**kw):
    d = dict(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    d.update(kw)
    return Context(**d)


def test_prematch_home_favourite_no_risk_is_not_angry():
    ctx = make_ctx()
    weights, dis = select_tones(ctx)
    assert set(weights.keys()) >= {"calm", "encourage", "assertive", "angry"}
    assert "angry" in dis  # avoid angry pre-match by default
    assert 0.0 < weights["assertive"] <= 1.0


def test_halftime_losing_underdog_encourage_rises():
    ctx = make_ctx(stage=MatchStage.HALF_TIME, fav_status=FavStatus.UNDERDOG, venue=Venue.AWAY, ht_score_delta=-1)
    weights, dis = select_tones(ctx)
    assert weights["encourage"] > weights["assertive"]
    assert "angry" in dis  # discipline risk when away/underdog


def test_derby_boosts_motivational_and_blocks_angry():
    ctx = make_ctx(special_situations=[SpecialSituation.DERBY], stage=MatchStage.HALF_TIME, ht_score_delta=0)
    w, dis = select_tones(ctx)
    assert w["motivational"] > 0.1
    assert "angry" in dis or w["angry"] < 0.2


def test_cards_and_injuries_push_calm_encourage():
    ctx = make_ctx(stage=MatchStage.MID, cards_red=1, cards_yellow=3, injuries=2)
    w, _ = select_tones(ctx)
    assert w["calm"] > 0.15 and w["encourage"] > 0.15
