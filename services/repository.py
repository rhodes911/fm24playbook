"""
Repository helpers for reading/writing JSON data files used by the app
(gestures, presets, policies, etc.).
Playbook.json has been removed in favor of the JSON-driven Rules Admin system.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from domain.policies import EnginePolicies

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Repository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_gestures(self) -> Dict[str, List[str]]:
        fp = self.data_dir / "gestures.json"
        with fp.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_presets(self) -> List[Dict[str, Any]]:
        fp = self.data_dir / "presets.json"
        if fp.exists():
            with fp.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            # Normalize possible legacy/manual shapes
            norm: List[Dict[str, Any]] = []
            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    data = item.get("data") or item.get("context")
                    if name and isinstance(data, dict):
                        norm.append({"name": name, "data": data})
            return norm
        return []

    def upsert_preset(self, name: str, data: Dict[str, Any]) -> None:
        fp = self.data_dir / "presets.json"
        presets: List[Dict[str, Any]] = []
        if fp.exists():
            try:
                with fp.open("r", encoding="utf-8") as f:
                    presets = json.load(f)
            except Exception:
                presets = []
        # Remove any with same name
        sanitized: List[Dict[str, Any]] = []
        for p in presets:
            if not isinstance(p, dict):
                continue
            if "name" not in p:
                continue
            if p.get("name") == name:
                continue  # drop old entry with same name
            # Keep only fields we understand
            item = {"name": p.get("name"), "data": p.get("data") or p.get("context")}
            sanitized.append(item)
        sanitized.append({"name": name, "data": data})
        presets = sanitized
        with fp.open("w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)

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