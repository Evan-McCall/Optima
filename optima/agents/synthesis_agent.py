"""Synthesis Agent (Sonnet): fuses evidence into one forced-JSON Recommendation.

Enforces the citation firewall in CODE as well as in the prompt: after the tool call,
any ranked_evidence / claim whose ref points at an ID not actually present in the
gathered evidence is dropped — a hallucinated ID can never reach the rendered output.
"""

from __future__ import annotations

import re

from anthropic import AsyncAnthropic

from .. import config
from ..schema import Evidence, Recommendation
from ..tools.registry import ToolRegistry
from .runner import AgentResult, run_agent

# Matches both modern arXiv IDs ("2407.10793") and the pre-2007 archive form
# ("cs/0509001", "cs.AI/0512001"). Tolerates a trailing version ("v3").
# Note: _norm() lowercases before this matches, which is fine — arxiv.org
# accepts the lowercased subject form and resolves to the canonical page.
_ARXIV_RE = re.compile(r"^(?:[a-z\-]+(?:\.[a-z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?$")


async def synthesize(
    client: AsyncAnthropic,
    query: str,
    research_evidence: list[Evidence],
    context_evidence: list[Evidence],
) -> tuple[Recommendation | None, AgentResult]:
    system = config.load_prompt("synthesis")
    tools = ToolRegistry.schemas_for(["submit_recommendation"])
    digest = _build_digest(query, research_evidence, context_evidence)

    result = await run_agent(
        client,
        model_key="synthesis",
        system_prompt=system,
        tools=tools,
        user_content=digest,
        terminal_tool="submit_recommendation",
        force_terminal=True,
    )
    if not result.terminal_input:
        return None, result

    rec = Recommendation(
        **result.terminal_input,
        query=query,
        generated_at=Recommendation.now_iso(),
    )
    _apply_firewall(rec, research_evidence + context_evidence)
    _resolve_links(rec)
    return rec, result


def _build_digest(query: str, research: list[Evidence], context: list[Evidence]) -> str:
    def fmt(items: list[Evidence]) -> str:
        return (
            "\n".join(
                f"- [{e.kind}] ref_id={e.ref_id} | {e.title} :: {e.why_relevant}" for e in items
            )
            or "(none found)"
        )

    return (
        f"Engineer's query:\n{query}\n\n"
        f"INTERNAL EVIDENCE (the team's past experiments & docs):\n{fmt(context)}\n\n"
        f"EXTERNAL EVIDENCE (published papers):\n{fmt(research)}\n\n"
        "Synthesize ONE actionable, compute-lean next experiment and call "
        "submit_recommendation. Cite only the exact ref_ids listed above."
    )


def _norm(ref: str | None) -> str:
    # Strip source prefixes so a model citing "2309.15217" matches a gathered
    # "arxiv:2309.15217" / "s2:...". Safe because papers.py constructs ids as
    # "arxiv:<id>", "s2:<id>", or the raw arXiv URL, so the trailing key is unique
    # per source within a single query's gathered evidence set.
    ref = (ref or "").strip().lower()
    return ref.removeprefix("arxiv:").removeprefix("s2:")


def _apply_firewall(rec: Recommendation, evidence: list[Evidence]) -> None:
    # Only refs actually GATHERED this run are citable. An experiment that merely
    # exists in the store but wasn't surfaced as evidence is intentionally dropped —
    # the recommendation must not cite something the agents never actually saw.
    valid = {_norm(e.ref_id) for e in evidence}
    rec.ranked_evidence = [e for e in rec.ranked_evidence if _norm(e.ref_id) in valid]
    rec.claims = [c for c in rec.claims if _norm(c.citation_ref) in valid]


def _resolve_links(rec: Recommendation) -> None:
    """Populate ``Evidence.link`` for every external paper we can identify.

    Modern + old-style arXiv IDs map to arxiv.org/abs/<id>. Refs prefixed
    ``s2:`` (Semantic Scholar paperIds) map to the S2 abstract page so a paper
    with no arXiv mirror still gets a clickable destination.
    """
    for e in rec.ranked_evidence:
        if e.kind != "external_paper":
            continue
        raw = (e.ref_id or "").strip()
        rid = _norm(raw)
        if _ARXIV_RE.match(rid):
            e.link = f"https://arxiv.org/abs/{rid}"
        elif raw.lower().startswith("s2:"):
            e.link = f"https://www.semanticscholar.org/paper/{raw[3:]}"
