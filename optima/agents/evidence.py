"""Shared parsing of a submit_evidence tool call into validated Evidence items."""

from __future__ import annotations

from ..schema import Evidence


def parse_evidence(terminal_input: dict | None) -> list[Evidence]:
    if not terminal_input:
        return []
    items: list[Evidence] = []
    for raw in terminal_input.get("evidence", []):
        try:
            items.append(Evidence(**raw))
        except Exception:
            continue  # skip malformed items rather than failing the whole run
    return items
