"""Shared parsing of a submit_evidence tool call into validated Evidence items."""

from __future__ import annotations

from ..schema import Evidence


def parse_evidence(terminal_input: dict | None) -> tuple[list[Evidence], int]:
    """Parse a submit_evidence call into validated Evidence items.

    Returns ``(items, dropped)`` where ``dropped`` counts malformed items skipped,
    so the caller can surface the loss (in result.notes) instead of it vanishing.
    """
    if not terminal_input:
        return [], 0
    items: list[Evidence] = []
    dropped = 0
    for raw in terminal_input.get("evidence", []):
        try:
            items.append(Evidence(**raw))
        except Exception:
            dropped += 1  # skip malformed items rather than failing the whole run
    return items, dropped
