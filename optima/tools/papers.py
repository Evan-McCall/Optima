"""The Knowledge Gathering Layer: published-research search.

Tries live arXiv + Semantic Scholar, then ALWAYS falls back to a local curated
cache (``papers_cache.json``) on any failure / 403 / empty result, so the demo
never depends on those APIs being reachable. (In sandboxed environments arXiv and
S2 return 403, so the cache path is what runs — by design.)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from .. import config
from ..schema import Paper
from .scoring import score

_ARXIV_API = "https://export.arxiv.org/api/query"
_S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_UA = {"User-Agent": "Optima/0.1 (experiment-intelligence; mailto:team@optima.dev)"}
_TIMEOUT = 8.0


class PaperSearch:
    def __init__(self, store_dir: Path, allow_live: bool = True):
        self.store_dir = Path(store_dir)
        self.allow_live = allow_live
        self._cache: list[Paper] | None = None

    def search(self, query: str, max_results: int = 8) -> list[Paper]:
        if self.allow_live:
            live: list[Paper] = []
            try:
                live += _arxiv(query, max_results)
            except Exception:
                pass
            try:
                live += _semantic_scholar(query, max_results)
            except Exception:
                pass
            live = _dedupe(live)
            if live:
                return live[:max_results]
        return self._cache_search(query, max_results)

    # -- cache ---------------------------------------------------------------
    def _load_cache(self) -> list[Paper]:
        if self._cache is None:
            path = self.store_dir / "papers_cache.json"
            raw = json.loads(path.read_text()) if path.exists() else []
            self._cache = [Paper(**p) for p in raw]
        return self._cache

    def _cache_search(self, query: str, max_results: int) -> list[Paper]:
        scored = []
        for p in self._load_cache():
            text = f"{p.title} {p.abstract or ''} {' '.join(p.tags)} {' '.join(p.keywords)}"
            s = score(query, text)
            if s > 0:
                p = p.model_copy(update={"source": "cache", "relevance_score": round(s, 2)})
                scored.append((s, p))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [p for _, p in scored[:max_results]]


# -- live clients ------------------------------------------------------------
def _arxiv(query: str, max_results: int) -> list[Paper]:
    import feedparser

    r = httpx.get(
        _ARXIV_API,
        params={"search_query": f"all:{query}", "start": 0, "max_results": max_results},
        headers=_UA,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    papers: list[Paper] = []
    for e in feed.entries:
        eid = getattr(e, "id", "")
        arxiv_id = _arxiv_id(eid)
        # Use the entry URL as a unique fallback id; skip entries with no stable id
        # rather than collapsing them onto a shared placeholder (breaks dedupe/citation).
        paper_id = f"arxiv:{arxiv_id}" if arxiv_id else eid
        if not paper_id:
            continue
        papers.append(
            Paper(
                paper_id=paper_id,
                title=re.sub(r"\s+", " ", getattr(e, "title", "")).strip(),
                authors=[a.name for a in getattr(e, "authors", [])],
                year=_year(getattr(e, "published", "")),
                arxiv_id=arxiv_id,
                abstract=re.sub(r"\s+", " ", getattr(e, "summary", "")).strip() or None,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None,
                url=getattr(e, "link", None),
                source="arxiv",
            )
        )
    return papers


def _semantic_scholar(query: str, max_results: int) -> list[Paper]:
    headers = dict(_UA)
    if config.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY
    r = httpx.get(
        _S2_API,
        params={
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,year,authors,citationCount,externalIds,url,venue",
        },
        headers=headers,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    papers: list[Paper] = []
    for d in r.json().get("data", []) or []:
        ext = d.get("externalIds") or {}
        arxiv_id = ext.get("ArXiv")
        papers.append(
            Paper(
                paper_id=f"s2:{d.get('paperId')}",
                title=d.get("title") or "",
                authors=[a.get("name", "") for a in d.get("authors") or []],
                year=d.get("year"),
                arxiv_id=arxiv_id,
                abstract=d.get("abstract"),
                citation_count=d.get("citationCount"),
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None,
                url=d.get("url"),
                venue=d.get("venue") or None,
                source="semantic_scholar",
            )
        )
    return papers


# -- helpers -----------------------------------------------------------------
def _arxiv_id(raw: str) -> str | None:
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", raw or "")
    return m.group(1) if m else None


def _year(raw: str) -> int | None:
    m = re.search(r"(\d{4})", raw or "")
    return int(m.group(1)) if m else None


def _dedupe(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    out: list[Paper] = []
    for p in papers:
        key = p.arxiv_id or p.title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
