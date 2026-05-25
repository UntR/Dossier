from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

PERSON_MATCH_THRESHOLD = 80


def person_matches_text(name: str | None, aliases: Any, text: str) -> bool:
    for candidate in _person_candidates(name, aliases):
        if candidate in text:
            return True
        if fuzz.token_sort_ratio(candidate, text) >= PERSON_MATCH_THRESHOLD:
            return True
        if _matches_token_window(candidate, text):
            return True
    return False


def _person_candidates(name: str | None, aliases: Any) -> list[str]:
    values = []
    if name:
        values.append(name)
    values.extend(_alias_values(aliases))
    seen = set()
    return [value for value in values if value and not (value in seen or seen.add(value))]


def _alias_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for alias in value for item in _alias_values(alias)]
    if isinstance(value, dict):
        return [item for alias in value.values() for item in _alias_values(alias)]
    return [str(value)]


def _matches_token_window(candidate: str, text: str) -> bool:
    candidate_token_count = len(candidate.split())
    if candidate_token_count < 2:
        return False
    tokens = text.split()
    for index in range(0, len(tokens) - candidate_token_count + 1):
        window = " ".join(tokens[index : index + candidate_token_count])
        if fuzz.token_sort_ratio(candidate, window) >= PERSON_MATCH_THRESHOLD:
            return True
    return False
