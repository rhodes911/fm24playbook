"""
Telemetry service: logs play recommendations and outcomes to JSONL files.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from domain.models import Context, Recommendation


LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_FILE = LOG_DIR / "plays.jsonl"


def _ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _enum_to_value(obj: Any) -> Any:
    try:
        # Enums in our domain inherit from Enum with .value
        return obj.value  # type: ignore[attr-defined]
    except Exception:
        return obj


def _dataclass_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        data = {}
        for k, v in obj.__dict__.items():
            data[k] = _serialize(v)
        return data
    return obj


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    # Enums
    if hasattr(obj, "value") and not isinstance(obj, (str, bytes)):
        try:
            return _enum_to_value(obj)
        except Exception:
            pass
    # Dataclasses
    if hasattr(obj, "__dataclass_fields__"):
        return _dataclass_to_dict(obj)
    # Lists
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    # Dicts
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def make_play_id(context: Context, rec: Recommendation) -> str:
    """Deterministic fingerprint for a recommendation + context."""
    payload = {
        "context": _serialize(context),
        "recommendation": _serialize(rec),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def log_event(
    event: str,
    context: Context,
    recommendation: Recommendation,
    playbook_version: Optional[str] = None,
    note: Optional[str] = None,
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a log entry to the JSONL file and return the record."""
    _ensure_dirs()
    now = datetime.utcnow().isoformat() + "Z"
    rec: Dict[str, Any] = {
        "ts": now,
        "event": event,  # view | applied | worked | didnt_work
        "play_id": make_play_id(context, recommendation),
        "context": _serialize(context),
        "recommendation": _serialize(recommendation),
        "playbook_version": playbook_version,
        "note": note,
        "outcome": outcome,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
