"""Canonical data models for Optima.

Two families live here:

1. **Store models** (`Experiment`, `Paper`) — the canonical, machine-readable
   schema for internal experiments and external papers. Rich, with relationships.

2. **Output models** (`Evidence`, `ExperimentSpec`, `Claim`, `Recommendation`) —
   these MIRROR the ``submit_recommendation`` tool schema in
   ``optima/tools/registry.py`` EXACTLY (field names + enum casing) so the
   synthesis tool output validates and renders with zero field drift.
   If you change a field here, change it in the tool schema too (and vice versa).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Store models — the canonical internal schema (Company Context Layer)
# ============================================================================


class ComputeCost(BaseModel):
    """Estimated cost of an experiment. Either field may be unknown."""

    gpu_hours: Optional[float] = None
    dollars: Optional[float] = None


ExperimentStatus = Literal["success", "failed", "inconclusive"]


class Experiment(BaseModel):
    """A single past experiment, connected to the whole — not an isolated record.

    Relationships (`parent_experiment_id`, `related_experiment_ids`) are what let
    the context agent trace lineages ("Exp_003 followed up on Exp_001") instead of
    treating history as a bag of disconnected runs.
    """

    experiment_id: str
    hypothesis: str
    task: str
    dataset_name: Optional[str] = None
    model: Optional[str] = None
    method: Optional[str] = None
    hyperparams: dict | str | None = None
    metrics: dict | str | None = None
    status: ExperimentStatus = "inconclusive"
    compute_cost: ComputeCost = Field(default_factory=ComputeCost)
    date: Optional[str] = None
    conclusion: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    parent_experiment_id: Optional[str] = None
    related_experiment_ids: list[str] = Field(default_factory=list)
    repo: Optional[str] = None
    commit: Optional[str] = None
    owner: Optional[str] = None


PaperSource = Literal["arxiv", "semantic_scholar", "cache"]


class Paper(BaseModel):
    """A published paper or external source (Knowledge Gathering Layer)."""

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    arxiv_id: Optional[str] = None
    abstract: Optional[str] = None
    citation_count: Optional[int] = None
    pdf_url: Optional[str] = None
    url: Optional[str] = None
    venue: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source: PaperSource = "cache"
    relevance_score: Optional[float] = None


class InternalDoc(BaseModel):
    """A free-text internal report / postmortem referenced by experiments."""

    name: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


# ============================================================================
# Output models — MIRROR the submit_recommendation tool schema EXACTLY
# ============================================================================

EvidenceKind = Literal["internal_experiment", "external_paper", "internal_doc"]
Confidence = Literal["High", "Medium", "Low"]


class Evidence(BaseModel):
    """One ranked piece of supporting evidence in the final recommendation."""

    kind: EvidenceKind
    title: str
    why_relevant: str
    ref_id: str
    # Resolved at render time from ref_id (paper url / arxiv link); not produced
    # by the model, so optional and excluded from the firewall check.
    link: Optional[str] = None


class ExperimentSpec(BaseModel):
    """Concrete, actionable configuration for the suggested next experiment."""

    model: str
    method: str
    key_hyperparams: str
    estimated_compute_cost: str
    estimated_savings_vs_naive: str


class Claim(BaseModel):
    """A factual claim with a confidence level and a citation back to evidence."""

    statement: str
    confidence: Confidence
    citation_ref: str


class Recommendation(BaseModel):
    """The Output Layer payload. Core fields mirror submit_recommendation; the
    trailing fields are metadata attached by the orchestrator after the call."""

    decision_summary: str
    ranked_evidence: list[Evidence]
    experiment_spec: ExperimentSpec
    claims: list[Claim]
    # --- orchestrator metadata (not emitted by the model) ---
    query: Optional[str] = None
    generated_at: Optional[str] = None

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================================
# Intent routing (orchestrator's cheap Haiku pass)
# ============================================================================


class IntentPlan(BaseModel):
    """Output of the intent pass: what the user wants + which agents to run."""

    domain: str
    goal: str
    needs_research: bool = True
    needs_context: bool = True
    search_terms: list[str] = Field(default_factory=list)
