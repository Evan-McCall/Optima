"""Render a Recommendation as the Output Layer — terminal markdown (rich) or a file."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from .schema import Evidence, Recommendation

_CONF_BADGE = {"High": "🟢 High", "Medium": "🟡 Medium", "Low": "🔴 Low"}
_KIND_LABEL = {
    "internal_experiment": "internal experiment",
    "external_paper": "paper",
    "internal_doc": "internal doc",
}

_DISCLAIMER = (
    "_Compute/cost/savings figures are heuristic estimates derived from experiment "
    "metadata, not measurements._"
)


def to_markdown(result) -> str:
    """Full recommendation as a standalone markdown document (used for --export)."""
    rec: Recommendation = result.recommendation
    out: list[str] = ["# Optima — Experiment Recommendation", ""]
    if rec.query:
        out += [f"> {rec.query}", ""]

    out += ["## Decision Summary", "", rec.decision_summary, ""]

    spec = rec.experiment_spec
    out += [
        "## Recommended Next Experiment",
        "",
        f"- **Model:** {spec.model}",
        f"- **Method:** {spec.method}",
        f"- **Key hyperparameters:** {spec.key_hyperparams}",
        f"- **Estimated compute cost:** {spec.estimated_compute_cost}",
        f"- **Estimated savings vs. naive:** {spec.estimated_savings_vs_naive}",
        "",
    ]

    out += ["## Ranked Evidence", ""]
    if rec.ranked_evidence:
        for i, e in enumerate(rec.ranked_evidence, 1):
            out.append(f"{i}. {_evidence_line(e)}")
            out.append(f"   {e.why_relevant}")
    else:
        out.append("_No evidence survived citation validation._")
    out.append("")

    out += ["## Claims & Confidence", ""]
    if rec.claims:
        for c in rec.claims:
            badge = _CONF_BADGE.get(c.confidence, c.confidence)
            out.append(f"- {badge} — {c.statement} _(`{c.citation_ref}`)_")
    else:
        out.append("_No citation-backed claims._")
    out += ["", "---", "", _DISCLAIMER]
    if rec.generated_at:
        out.append(f"_Generated {rec.generated_at}._")
    return "\n".join(out) + "\n"


def render(result, *, verbose: bool = False) -> None:
    """Print the recommendation (and optional verbose diagnostics) to the terminal."""
    console = Console()
    if verbose:
        _render_verbose(console, result)
    console.print(Markdown(to_markdown(result)))


def _evidence_line(e: Evidence) -> str:
    label = _KIND_LABEL.get(e.kind, e.kind)
    head = f"**[{label}] {e.title}** · `{e.ref_id}`"
    if e.link:
        head += f" — [link]({e.link})"
    return head


def _render_verbose(console: Console, result) -> None:
    lines = ["### Run diagnostics", ""]
    intent = result.intent
    if intent:
        lines += [
            f"- **Intent:** {intent.domain} — {intent.goal}",
            f"- **Search terms:** {', '.join(intent.search_terms) or '-'}",
            f"- **Routed to:** "
            + ", ".join(
                [n for n, on in (("research", intent.needs_research), ("context", intent.needs_context)) if on]
            ),
        ]
    lines += [
        f"- **Evidence gathered:** {len(result.context_evidence)} internal, "
        f"{len(result.research_evidence)} papers",
    ]
    u = result.usage
    lines.append(
        f"- **Tokens:** in {u['input']:,} / out {u['output']:,} · "
        f"cache read {u['cache_read']:,}, write {u['cache_write']:,}"
    )
    if result.notes:
        lines.append(f"- **Notes:** {'; '.join(result.notes)}")
    lines.append("")
    console.print(Markdown("\n".join(lines)))
