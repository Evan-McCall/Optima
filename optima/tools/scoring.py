"""Tiny keyword-relevance scorer shared by the cache fallback and internal store.

Deliberately not embeddings — the corpus is tens of records, so lexical overlap
with light term-coverage weighting is plenty and keeps the demo dependency-free.
"""

from __future__ import annotations

import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common words that add noise to lexical matching.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "be", "by", "at", "as", "it", "this", "that", "we", "our", "my", "i",
    "how", "what", "which", "can", "do", "does", "help", "set", "up", "next",
    "want", "need", "use", "using", "from", "so", "but", "not", "no",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 2]


def score(query: str, text: str) -> float:
    """Relevance of `text` to `query`. Rewards both raw hits and term coverage."""
    q_terms = set(tokenize(query))
    if not q_terms:
        return 0.0
    counts = Counter(tokenize(text))
    if not counts:
        return 0.0
    hits = sum(counts[t] for t in q_terms)
    coverage = len(q_terms & counts.keys()) / len(q_terms)
    return hits + coverage * 5.0
