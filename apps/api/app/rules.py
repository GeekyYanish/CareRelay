from __future__ import annotations

import re
from pathlib import Path

import yaml

from .core import get_settings
from .schemas import RedFlagMatch, Urgency


class RedFlagEngine:
    def __init__(self, path: str | None = None):
        settings = get_settings()
        rule_path = Path(path or settings.clinical_rules_path)
        if not rule_path.is_absolute():
            rule_path = (Path(__file__).parent / rule_path).resolve()
        with rule_path.open() as handle:
            content = yaml.safe_load(handle)
        self.version = content["version"]
        self.disclaimer = content["disclaimer"]
        self.rules = content["rules"]

    def scan(self, text: str) -> list[RedFlagMatch]:
        normalized = " ".join(text.lower().split())
        matches: list[RedFlagMatch] = []
        for rule in self.rules:
            for pattern in rule["patterns"]:
                if re.search(rf"\b{re.escape(pattern.lower())}\b", normalized):
                    matches.append(
                        RedFlagMatch(
                            rule_id=rule["id"],
                            rule_version=self.version,
                            severity=Urgency(rule["severity"]),
                            matched_evidence=pattern,
                            recommended_action=rule["action"],
                        )
                    )
                    break
        return matches

