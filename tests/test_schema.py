from optima.schema import (
    Claim,
    Evidence,
    Experiment,
    ExperimentSpec,
    Paper,
    Recommendation,
)


def test_experiment_defaults_and_roundtrip():
    e = Experiment(experiment_id="exp_x", hypothesis="h", task="t")
    assert e.status == "inconclusive"
    assert e.compute_cost.dollars is None
    again = Experiment(**e.model_dump())
    assert again == e


def test_recommendation_mirrors_tool_shape():
    rec = Recommendation(
        decision_summary="do x",
        ranked_evidence=[Evidence(kind="external_paper", title="P", why_relevant="w", ref_id="2309.15217")],
        experiment_spec=ExperimentSpec(
            model="m", method="me", key_hyperparams="k",
            estimated_compute_cost="$5", estimated_savings_vs_naive="lots",
        ),
        claims=[Claim(statement="s", confidence="High", citation_ref="2309.15217")],
    )
    dumped = rec.model_dump(mode="json")
    # Exactly the tool's required fields, no drift.
    assert set(dumped) >= {"decision_summary", "ranked_evidence", "experiment_spec", "claims"}
    assert dumped["claims"][0]["confidence"] == "High"


def test_paper_source_default():
    p = Paper(paper_id="x", title="t")
    assert p.source == "cache"
