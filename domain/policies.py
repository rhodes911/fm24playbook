"""
Engine policy model with defaults; kept pure (no file IO here).
"""
from __future__ import annotations

from dataclasses import dataclass
from .models import Mentality


@dataclass
class EnginePolicies:
    version: str = "1.0.0"
    preMatchMaxMentality: Mentality = Mentality.POSITIVE
    positionGapBucket: int = 8
    formDiffBucket: int = 2
    homeAdvantageBonus: int = 1
    inPlayShoutHeuristic: bool = True
