"""The Company Context Layer: load, search, and extend internal experiments + docs.

Curated seed records live in ``experiments.json`` (read-only, version-controlled).
Records added via ``optima ingest`` are written to ``ingested.json`` so the curated
seed stays pristine and ingestion is reproducible. Both are merged on load.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..schema import Experiment, InternalDoc
from .scoring import score

_CURATED = "experiments.json"
_INGESTED = "ingested.json"


class InternalStore:
    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.experiments: dict[str, Experiment] = {}
        self.docs: dict[str, InternalDoc] = {}
        self._load()

    # -- loading -------------------------------------------------------------
    def _load(self) -> None:
        for fname in (_CURATED, _INGESTED):
            path = self.store_dir / fname
            if not path.exists():
                continue
            for raw in json.loads(path.read_text()):
                exp = Experiment(**raw)
                self.experiments[exp.experiment_id] = exp  # ingested overrides curated
        docs_dir = self.store_dir / "docs"
        if docs_dir.exists():
            for md in sorted(docs_dir.glob("*.md")):
                self.docs[md.stem] = _parse_doc(md)

    # -- tool surface --------------------------------------------------------
    def search_experiments(self, keywords: str, limit: int = 8) -> list[Experiment]:
        scored = [
            (score(keywords, _searchable_text(e)), e) for e in self.experiments.values()
        ]
        scored = [(s, e) for s, e in scored if s > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self.experiments.get(experiment_id)

    def search_docs(self, keywords: str, limit: int = 3) -> list[InternalDoc]:
        scored = [
            (score(keywords, f"{d.title}\n{d.content}"), d) for d in self.docs.values()
        ]
        scored = [(s, d) for s, d in scored if s > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def get_doc(self, name: str) -> InternalDoc | None:
        # tolerate "foo", "foo.md", or the full title
        key = name[:-3] if name.endswith(".md") else name
        if key in self.docs:
            return self.docs[key]
        for d in self.docs.values():
            if d.title.lower() == name.lower():
                return d
        return None

    # -- compact, cacheable index -------------------------------------------
    def compact_index(self) -> str:
        """A small, stable markdown digest of all experiments + doc titles.

        Injected into the context agent's cached preamble so it can judge which
        records to pull with the search/get tools without us shipping everything.
        """
        lines = ["# Internal experiment index", ""]
        for e in sorted(self.experiments.values(), key=lambda x: x.experiment_id):
            metric = _headline_metric(e)
            rel = ",".join(e.related_experiment_ids) or "-"
            lines.append(
                f"- {e.experiment_id} [{e.status}] task={e.task} | {_clip(e.hypothesis, 90)} "
                f"| method={e.method or '-'} | metric={metric} | "
                f"cost=${_dollars(e)} | parent={e.parent_experiment_id or '-'} | related={rel} "
                f"| tags={','.join(e.tags)}"
            )
        if self.docs:
            lines += ["", "# Internal documents"]
            for d in sorted(self.docs.values(), key=lambda x: x.name):
                lines.append(f"- {d.name}: {d.title}")
        return "\n".join(lines)

    # -- ingestion -----------------------------------------------------------
    def add_experiments(self, new: list[Experiment]) -> tuple[int, int]:
        """Merge experiments into ingested.json. Returns (added, updated)."""
        path = self.store_dir / _INGESTED
        existing: dict[str, dict] = {}
        if path.exists():
            existing = {r["experiment_id"]: r for r in json.loads(path.read_text())}
        added = updated = 0
        for exp in new:
            if exp.experiment_id in existing:
                updated += 1
            else:
                added += 1
            existing[exp.experiment_id] = exp.model_dump(mode="json")
            self.experiments[exp.experiment_id] = exp
        # Atomic write: a crash mid-write can't leave a truncated ingested.json.
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(list(existing.values()), indent=2) + "\n")
        os.replace(tmp, path)
        return added, updated


# -- helpers -----------------------------------------------------------------
def _parse_doc(path: Path) -> InternalDoc:
    text = path.read_text()
    first = text.lstrip().splitlines()[0] if text.strip() else path.stem
    title = first.lstrip("# ").strip() if first.startswith("#") else path.stem
    return InternalDoc(name=path.stem, title=title, content=text)


def _searchable_text(e: Experiment) -> str:
    return " ".join(
        str(x)
        for x in [
            e.experiment_id, e.hypothesis, e.task, e.method, e.model,
            e.dataset_name, e.conclusion, " ".join(e.tags), str(e.metrics),
        ]
        if x
    )


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _headline_metric(e: Experiment) -> str:
    if isinstance(e.metrics, dict) and e.metrics:
        k, v = next(iter(e.metrics.items()))
        return f"{k}={v}"
    return "-"


def _dollars(e: Experiment) -> str:
    d = e.compute_cost.dollars
    return f"{d:g}" if d is not None else "?"
