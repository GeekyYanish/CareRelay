from __future__ import annotations

import re


PATTERNS = [
    (re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"), "[NAME]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)"), "[PHONE]"),
    (re.compile(r"\b(?:MRN|record|patient id)[:#\s-]*[A-Za-z0-9-]{4,}\b", re.I), "[RECORD_ID]"),
]


def mask_phi(text: str) -> str:
    masked = text
    for pattern, replacement in PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked

