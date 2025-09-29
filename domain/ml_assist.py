from __future__ import annotations

from typing import Dict, Any, Optional, List
from pathlib import Path
import json

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None  # type: ignore


# Fixed feature order for training and inference
FEATURE_COLUMNS: List[str] = [
    "stage",  # categorical encoded as int
    "venue",  # 0=Away, 1=Home
    "fav_status",  # 0=Underdog, 1=Favourite
    "score_state",  # -1,0,1
    "minute",  # int or 0
    "team_pos",  # int or 0
    "opp_pos",  # int or 0
    "pos_delta",  # opp - team
    "form_team",  # int
    "form_opp",   # int
    "form_delta", # int
    "xg_for",
    "xg_against",
    "xg_delta",
    "shots_for",
    "shots_against",
    "shots_delta",
    "possession",  # 0..100
    "tier_edge",   # float
]


def _enum_to_int(val: Any, mapping: Dict[str, int], default: int = 0) -> int:
    v = getattr(val, "value", val)
    return mapping.get(str(v), default)


def _score_form(s: Optional[str]) -> int:
    if not s:
        return 0
    pts = 0
    for c in str(s)[:5].upper():
        pts += 3 if c == "W" else (1 if c == "D" else 0)
    return pts


def extract_features(context, tier: Optional[str], edge: Optional[float]) -> Dict[str, Any]:
    # Enum encodings
    stage_map = {
        "PreMatch": 0,
        "Early": 1,
        "Mid": 2,
        "Late": 3,
        "VeryLate": 4,
        "HalfTime": 5,
        "FullTime": 6,
    }
    venue_map = {"Home": 1, "Away": 0}
    fav_map = {"Underdog": 0, "Favourite": 1}
    score_map = {None: 0, "Losing": -1, "Drawing": 0, "Winning": 1}

    team_pos = context.team_position or 0
    opp_pos = context.opponent_position or 0
    pos_delta = (context.opponent_position - context.team_position) if (context.team_position is not None and context.opponent_position is not None) else 0
    ft = _score_form(context.team_form)
    fo = _score_form(context.opponent_form)
    fd = ft - fo
    xf = context.xg_for or 0.0
    xa = context.xg_against or 0.0
    xd = xf - xa
    sf = context.shots_for or 0
    sa = context.shots_against or 0
    sd = sf - sa
    poss = context.possession_pct or 0

    feats = {
        "stage": _enum_to_int(context.stage, stage_map, 0),
        "venue": _enum_to_int(context.venue, venue_map, 0),
        "fav_status": _enum_to_int(context.fav_status, fav_map, 0),
        "score_state": _enum_to_int(getattr(context, "score_state", None), score_map, 0),
        "minute": getattr(context, "minute", 0) or 0,
        "team_pos": team_pos,
        "opp_pos": opp_pos,
        "pos_delta": pos_delta,
        "form_team": ft,
        "form_opp": fo,
        "form_delta": fd,
        "xg_for": xf,
        "xg_against": xa,
        "xg_delta": xd,
        "shots_for": sf,
        "shots_against": sa,
        "shots_delta": sd,
        "possession": poss,
        "tier_edge": edge if edge is not None else 0.0,
    }
    return feats


def to_vector_row(features: Dict[str, Any]) -> List[float]:
    return [float(features.get(k, 0)) for k in FEATURE_COLUMNS]


def load_model(model_dir: Path, name: str):
    if joblib is None:
        return None
    fp = model_dir / f"{name}.joblib"
    if not fp.exists():
        return None
    try:
        return joblib.load(fp)
    except Exception:
        return None


def predict_proba(model, vector: List[float]) -> Optional[Dict[str, float]]:
    try:
        import numpy as np  # type: ignore
        X = np.array([vector], dtype=float)
        probs = model.predict_proba(X)[0]
        classes = list(getattr(model, "classes_", []))
        return {str(c): float(p) for c, p in zip(classes, probs)}
    except Exception:
        return None
