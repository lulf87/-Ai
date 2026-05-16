from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.config import OBLIGATION_LIBRARY_PATH, RULE_CONFIG_PATH


@dataclass(frozen=True)
class Obligation:
    id: str
    module: str
    title: str
    applies_when: list[str]
    evidence_required: list[str]
    authority_level: str
    source_title: str
    suggested_owner: str
    risk_if_missing: str


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_obligations() -> list[Obligation]:
    payload = _load_json(OBLIGATION_LIBRARY_PATH, {"obligations": []})
    return [Obligation(**item) for item in payload.get("obligations", [])]


def load_rule_config() -> dict[str, Any]:
    return _load_json(RULE_CONFIG_PATH, {"version": "local", "rules": []})


def matching_obligations(triggers: dict[str, bool]) -> list[Obligation]:
    matches: list[Obligation] = []
    for obligation in load_obligations():
        if all(triggers.get(key, False) for key in obligation.applies_when):
            matches.append(obligation)
    return matches
