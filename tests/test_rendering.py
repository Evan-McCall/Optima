from optima.orchestrator import RunResult
from optima.schema import Claim, Evidence, ExperimentSpec, IntentPlan, Recommendation
from optima import rendering


def _rec():
    return Recommendation(
        query="reduce hallucinations",
        decision_summary="Build on the CoVe result.",
        ranked_evidence=[
            Evidence(kind="internal_experiment", title="CoVe win", why_relevant="best prior", ref_id="exp_004"),
            Evidence(kind="external_paper", title="RAGAS", why_relevant="eval", ref_id="2309.15217", link="https://arxiv.org/abs/2309.15217"),
        ],
        experiment_spec=ExperimentSpec(
            model="Claude Sonnet 4.5", method="constrained decoding", key_hyperparams="top_k=8",
            estimated_compute_cost="$50", estimated_savings_vs_naive="skips a re-tune",
        ),
        claims=[Claim(statement="hallucination at 7%", confidence="High", citation_ref="exp_004")],
    )


def test_to_markdown_has_all_sections():
    md = rendering.to_markdown(RunResult(recommendation=_rec(), intent=None))
    for section in ("# Optima", "Decision Summary", "Recommended Next Experiment",
                    "Ranked Evidence", "Claims & Confidence"):
        assert section in md
    assert "exp_004" in md
    # Link text is the URL itself (sans scheme) so it's visible AND clickable —
    # not the bare word "link" which carries no information.
    assert "[arxiv.org/abs/2309.15217](https://arxiv.org/abs/2309.15217)" in md
    assert " — [link](" not in md  # explicit guard against the old format
    assert "🟢 High" in md
    assert "heuristic estimates" in md


def test_render_runs_without_error():
    res = RunResult(
        recommendation=_rec(),
        intent=IntentPlan(domain="eval", goal="g", search_terms=["a", "b"]),
        research_evidence=[], context_evidence=[],
        usage={"input": 100, "output": 20, "cache_read": 50, "cache_write": 60},
    )
    rendering.render(res, verbose=True)  # should not raise
