from domain.models import *
from domain.rules_engine import detect_matchup_tier, recommend
from services.session import SessionManager


def make_ctx(**kwargs):
    defaults = dict(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME)
    defaults.update(kwargs)
    return Context(**defaults)


def test_detect_matchup_tier_even_band():
    # Close positions and forms, neutral stats should fall in EVEN band
    ctx = make_ctx(
        team_position=8, opponent_position=9, team_form="WDLDD", opponent_form="DLDDW",
        possession_pct=50, shots_for=5, shots_against=5
    )
    tier, edge, expl = detect_matchup_tier(ctx)
    assert tier in (FavTier.EVEN, FavTier.SLIGHT_FAVOURITE, FavTier.SLIGHT_UNDERDOG)
    assert isinstance(expl, str) and expl


def test_recommend_trace_present_and_serializable(tmp_path, monkeypatch):
    # Start a session and ensure we can append an event carrying trace/tier/edge fields
    sm = SessionManager()
    # Point the session files to a temp dir
    import services.session as sess
    sess.DATA_DIR = tmp_path
    sess.ACTIVE_FILE = tmp_path / "active.json"
    sess.ARCHIVE_FILE = tmp_path / "sessions.jsonl"
    sm = SessionManager()

    ctx = make_ctx(team_position=3, opponent_position=13, team_form="WWWDD", opponent_form="LDLLD")
    sm.start(ctx, name="Test Match")
    rec = recommend(ctx)
    assert rec is not None
    event = {
        "type": "decision",
        "payload": {
            "fav_status": ctx.fav_status.value,
            "auto_fav_status": ctx.auto_fav_status,
            "tier": detect_matchup_tier(ctx)[0].value,
            "edge": detect_matchup_tier(ctx)[1],
            "trace": rec.trace,
        }
    }
    sm.append_event(event)
    data = sm.get_active()
    assert data is not None
    assert data["events"], "event not saved"
    saved = data["events"][-1]["payload"]
    assert isinstance(saved.get("trace", []), list)
    assert isinstance(saved.get("edge", 0.0), (float, int))


def test_venue_asymmetry_in_tier_edge():
    # With all else equal, home should have a higher edge than away per config weights
    base = dict(team_position=6, opponent_position=10, team_form="WDDWW", opponent_form="DLDDL")
    ctx_home = make_ctx(venue=Venue.HOME, **base)
    ctx_away = make_ctx(venue=Venue.AWAY, **base)
    tier_h, edge_h, _ = detect_matchup_tier(ctx_home)
    tier_a, edge_a, _ = detect_matchup_tier(ctx_away)
    assert edge_h > edge_a