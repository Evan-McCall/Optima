"""Tests for the citation firewall's link-resolution pass.

These exercise `_resolve_links` directly because it's pure: no LLM call, no I/O.
"""

from optima.agents.synthesis_agent import _resolve_links
from optima.schema import Claim, Evidence, ExperimentSpec, Recommendation


def _rec(evidence: list[Evidence]) -> Recommendation:
    """Minimal Recommendation that satisfies pydantic for the test fixture."""
    return Recommendation(
        decision_summary="x",
        ranked_evidence=evidence,
        experiment_spec=ExperimentSpec(
            model="m", method="m", key_hyperparams="-",
            estimated_compute_cost="-", estimated_savings_vs_naive="-",
        ),
        claims=[Claim(statement="x", confidence="High", citation_ref="x")],
    )


def test_modern_arxiv_id_gets_link():
    rec = _rec([Evidence(kind="external_paper", title="t", why_relevant="w", ref_id="2407.10793")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link == "https://arxiv.org/abs/2407.10793"


def test_arxiv_prefixed_id_gets_link():
    """The model often emits "arxiv:<id>" (matching how the store keys them)."""
    rec = _rec([Evidence(kind="external_paper", title="t", why_relevant="w", ref_id="arxiv:2309.15217")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link == "https://arxiv.org/abs/2309.15217"


def test_old_style_arxiv_id_gets_link():
    """Pre-2007 IDs like ``cs/0509001`` were dropped by the original regex."""
    rec = _rec([Evidence(kind="external_paper", title="t", why_relevant="w", ref_id="cs/0509001")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link == "https://arxiv.org/abs/cs/0509001"


def test_semantic_scholar_id_falls_back_to_s2_url():
    """A paper without an arXiv mirror should still get a clickable destination."""
    rec = _rec([Evidence(kind="external_paper", title="t", why_relevant="w", ref_id="s2:f3b2c4abc123")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link == "https://www.semanticscholar.org/paper/f3b2c4abc123"


def test_internal_experiment_gets_no_external_link():
    rec = _rec([Evidence(kind="internal_experiment", title="t", why_relevant="w", ref_id="exp_004")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link is None


def test_unparseable_external_ref_is_left_unlinked():
    """Don't fabricate a URL if we can't recognize the id shape — fail safe."""
    rec = _rec([Evidence(kind="external_paper", title="t", why_relevant="w", ref_id="not-an-id")])
    _resolve_links(rec)
    assert rec.ranked_evidence[0].link is None
