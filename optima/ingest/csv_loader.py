"""Haiku-powered CSV ingestion into the canonical Experiment schema.

Each row is normalized by a cheap Haiku call (forced to emit `record_experiment`),
so messy human formatting — odd column names, free-text metrics, "55 dollars",
mixed date formats — is mapped by the model instead of brittle Python parsing.
Results are validated through pydantic and merged into the store (deduped on id).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from anthropic import AsyncAnthropic

from .. import config
from ..agents.runner import run_agent
from ..schema import Experiment
from ..tools.internal_store import InternalStore

_SYSTEM = (
    "You normalize one messy CSV row describing a single ML experiment into the "
    "canonical schema. Map columns sensibly even when names are odd. Infer `status` "
    "(success / failed / inconclusive) from the results and notes. Parse costs into "
    "numbers (e.g. '55 dollars' -> dollars: 55) and normalize dates to YYYY-MM-DD when "
    "possible. Preserve the experiment id as given. Put free-text results into `metrics` "
    "and `conclusion`. You MUST respond only by calling record_experiment."
)

RECORD_EXPERIMENT = {
    "name": "record_experiment",
    "description": "Record one experiment in the canonical schema.",
    "input_schema": {
        "type": "object",
        "properties": {
            "experiment_id": {"type": "string"},
            "hypothesis": {"type": "string"},
            "task": {"type": "string"},
            "dataset_name": {"type": "string"},
            "model": {"type": "string"},
            "method": {"type": "string"},
            "hyperparams": {"type": "string", "description": "Free-text or 'k=v, k=v' hyperparameters."},
            "metrics": {"type": "string", "description": "Free-text results/metrics."},
            "status": {"type": "string", "enum": ["success", "failed", "inconclusive"]},
            "compute_cost": {
                "type": "object",
                "properties": {
                    "gpu_hours": {"type": "number"},
                    "dollars": {"type": "number"},
                },
            },
            "date": {"type": "string", "description": "YYYY-MM-DD if determinable."},
            "conclusion": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "parent_experiment_id": {"type": "string"},
            "related_experiment_ids": {"type": "array", "items": {"type": "string"}},
            "owner": {"type": "string"},
        },
        "required": ["experiment_id", "hypothesis", "task", "status"],
    },
}


@dataclass
class IngestResult:
    rows: int = 0
    parsed: int = 0
    added: int = 0
    updated: int = 0
    failures: list[str] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)


async def ingest_csv(path: str | Path, *, store_dir: Path | None = None) -> IngestResult:
    config.require_api_key()
    store_dir = store_dir or config.STORE_DIR
    store = InternalStore(store_dir)

    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    out = IngestResult(rows=len(rows))
    async with AsyncAnthropic(api_key=config.require_api_key()) as client:
        for idx, row in enumerate(rows):
            exp = await _row_to_experiment(client, row)
            if exp is None:
                out.failures.append(f"row {idx + 1}")
            else:
                out.experiments.append(exp)
    out.parsed = len(out.experiments)
    out.added, out.updated = store.add_experiments(out.experiments)
    return out


async def _row_to_experiment(client: AsyncAnthropic, row: dict) -> Experiment | None:
    body = "\n".join(f"{k}: {v}" for k, v in row.items() if v not in (None, ""))
    result = await run_agent(
        client,
        model_key="ingest",
        system_prompt=_SYSTEM,
        tools=[RECORD_EXPERIMENT],
        user_content=f"CSV row:\n{body}",
        terminal_tool="record_experiment",
        force_terminal=True,
    )
    if not result.terminal_input:
        return None
    try:
        return Experiment(**result.terminal_input)
    except Exception:
        return None
