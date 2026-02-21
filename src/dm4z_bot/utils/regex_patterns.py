from __future__ import annotations

import re

NINE_DIGIT_MATCH_ID_PATTERN = re.compile(r"\b\d{9}\b")


def extract_match_id(value: str) -> str | None:
    match = NINE_DIGIT_MATCH_ID_PATTERN.search(value)
    if not match:
        return None
    return match.group(0)

