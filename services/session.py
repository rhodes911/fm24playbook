"""
Session management for match lifecycle: start → log events → complete.

Enforces a single active session. Stores active snapshot in JSON and archives
completed sessions to JSONL for later analysis.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from domain.models import (
    Context,
    MatchStage, FavStatus, Venue, ScoreState, SpecialSituation, PlayerReaction, TalkAudience,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
ACTIVE_FILE = DATA_DIR / "active.json"
ARCHIVE_FILE = DATA_DIR / "sessions.jsonl"


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _enum_val(e):
    return e.value if hasattr(e, "value") else e


def serialize_context(ctx: Context) -> Dict[str, Any]:
    return {
        "stage": _enum_val(ctx.stage),
        "fav_status": _enum_val(ctx.fav_status),
        "venue": _enum_val(ctx.venue),
        "score_state": _enum_val(ctx.score_state) if ctx.score_state else None,
        "special_situations": [_enum_val(s) for s in ctx.special_situations],
        "player_reactions": [_enum_val(r) for r in ctx.player_reactions],
        "team_position": ctx.team_position,
        "opponent_position": ctx.opponent_position,
        "team_form": ctx.team_form,
        "opponent_form": ctx.opponent_form,
        "team_goals": ctx.team_goals,
        "opponent_goals": ctx.opponent_goals,
        "auto_fav_status": ctx.auto_fav_status,
        "preferred_talk_audience": _enum_val(ctx.preferred_talk_audience) if ctx.preferred_talk_audience else None,
    }


def deserialize_context(d: Dict[str, Any]) -> Context:
    def maybe(v, enum):
        return enum(v) if v is not None else None
    return Context(
        stage=MatchStage(d["stage"]),
        fav_status=FavStatus(d["fav_status"]),
        venue=Venue(d["venue"]),
        score_state=maybe(d.get("score_state"), ScoreState),
        special_situations=[SpecialSituation(x) for x in d.get("special_situations", [])],
        player_reactions=[PlayerReaction(x) for x in d.get("player_reactions", [])],
        team_position=d.get("team_position"),
        opponent_position=d.get("opponent_position"),
        team_form=d.get("team_form"),
        opponent_form=d.get("opponent_form"),
        team_goals=d.get("team_goals"),
        opponent_goals=d.get("opponent_goals"),
        auto_fav_status=bool(d.get("auto_fav_status", False)),
        preferred_talk_audience=maybe(d.get("preferred_talk_audience"), TalkAudience),
    )


class SessionManager:
    def __init__(self) -> None:
        _ensure_dirs()

    def get_active(self) -> Optional[Dict[str, Any]]:
        if ACTIVE_FILE.exists():
            return json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
        return None

    def start(self, context: Context, name: str) -> Dict[str, Any]:
        if ACTIVE_FILE.exists():
            raise RuntimeError("A session is already active. Complete it before starting a new one.")
        if not name or not name.strip():
            raise ValueError("Session name is required.")
        session = {
            "id": str(uuid.uuid4())[:8],
            "started_at": datetime.utcnow().isoformat() + "Z",
            "status": "active",
            "name": name.strip(),
            "context": serialize_context(context),
            "events": [],
        }
        ACTIVE_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        return session

    def append_event(self, event: Dict[str, Any]) -> None:
        if not ACTIVE_FILE.exists():
            raise RuntimeError("No active session to log event.")
        session = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
        event["ts"] = datetime.utcnow().isoformat() + "Z"
        session["events"].append(event)
        ACTIVE_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    def complete(self, outcome: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        if not ACTIVE_FILE.exists():
            raise RuntimeError("No active session to complete.")
        session = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
        session["completed_at"] = datetime.utcnow().isoformat() + "Z"
        session["status"] = "completed"
        session["outcome"] = outcome
        session["notes"] = notes
        # Append to archive and remove active file
        with ARCHIVE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(session, ensure_ascii=False) + "\n")
        ACTIVE_FILE.unlink(missing_ok=True)
        return session

    def cancel(self) -> None:
        ACTIVE_FILE.unlink(missing_ok=True)
