from domain.reactions import get_reaction_hint
from domain.models import PlayerReaction


def test_reaction_hint_exists():
    assert get_reaction_hint(PlayerReaction.COMPLACENT)
