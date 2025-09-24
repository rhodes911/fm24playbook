"""
Repository layer for reading/writing JSON data files for the playbook.
Abstracts file IO to enable future switch to API/DB without UI changes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from domain.validators import validate_playbook
from domain.models import PlaybookData
from domain.policies import EnginePolicies

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class PlaybookRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_playbook(self) -> PlaybookData:
        fp = self.data_dir / "playbook.json"
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return validate_playbook(data)

    def save_playbook(self, playbook: PlaybookData) -> None:
        fp = self.data_dir / "playbook.json"
        with fp.open("w", encoding="utf-8") as f:
            json.dump(playbook.model_dump(by_alias=True), f, indent=2, ensure_ascii=False)

    def load_gestures(self) -> Dict[str, List[str]]:
        fp = self.data_dir / "gestures.json"
        with fp.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_presets(self) -> List[Dict[str, Any]]:
        fp = self.data_dir / "presets.json"
        if fp.exists():
            with fp.open("r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def load_policies(self) -> EnginePolicies:
        fp = self.data_dir / "policies.json"
        if not fp.exists():
            return EnginePolicies()
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return EnginePolicies()
        pol = EnginePolicies()
        pol.version = raw.get("version", pol.version)
        # Map string to Mentality for preMatchMaxMentality if present
        try:
            from domain.models import Mentality
            if "preMatchMaxMentality" in raw:
                pol.preMatchMaxMentality = Mentality(raw["preMatchMaxMentality"])
        except Exception:
            pass
        pol.positionGapBucket = int(raw.get("positionGapBucket", pol.positionGapBucket))
        pol.formDiffBucket = int(raw.get("formDiffBucket", pol.formDiffBucket))
        pol.homeAdvantageBonus = int(raw.get("homeAdvantageBonus", pol.homeAdvantageBonus))
        pol.inPlayShoutHeuristic = bool(raw.get("inPlayShoutHeuristic", pol.inPlayShoutHeuristic))
        return pol