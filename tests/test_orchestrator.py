from optima import config, orchestrator
from optima.agents import synthesis_agent
from optima.schema import Claim, Evidence, Recommendation

from _fakes import factory, response, text_block, tool_use


def _make_handler():
    state = {"context_calls": 0}

    def handler(kwargs):
        tool_names = {t["name"] for t in kwargs.get("tools", [])}
        choice = kwargs.get("tool_choice")

        if choice and choice.get("name") == "record_intent":
            return response([tool_use("record_intent", {
                "domain": "evaluation/hallucination", "goal": "reduce hallucinations",
                "needs_research": True, "needs_context": True,
                "search_terms": ["RAG hallucination", "faithfulness"],
            })])

        if "submit_recommendation" in tool_names:
            return response([tool_use("submit_recommendation", {
                "decision_summary": "Extend CoVe with constrained decoding.",
                "ranked_evidence": [
                    {"kind": "internal_experiment", "title": "CoVe", "why_relevant": "best", "ref_id": "exp_004"},
                    {"kind": "external_paper", "title": "RAGAS", "why_relevant": "eval", "ref_id": "2309.15217"},
                    {"kind": "external_paper", "title": "HALLUCINATED", "why_relevant": "bad", "ref_id": "fake_999"},
                ],
                "experiment_spec": {
                    "model": "Claude Sonnet 4.5", "method": "constrained decoding",
                    "key_hyperparams": "top_k=8", "estimated_compute_cost": "$50",
                    "estimated_savings_vs_naive": "skips re-tune",
                },
                "claims": [
                    {"statement": "CoVe got 7%", "confidence": "High", "citation_ref": "exp_004"},
                    {"statement": "fabricated", "confidence": "Low", "citation_ref": "exp_999"},
                ],
            })])

        if "search_papers" in tool_names:
            return response([tool_use("submit_evidence", {"evidence": [
                {"kind": "external_paper", "title": "RAGAS", "ref_id": "2309.15217", "why_relevant": "eval"},
            ]})])

        if "search_experiments" in tool_names:
            state["context_calls"] += 1
            if state["context_calls"] == 1:
                return response([tool_use("search_experiments", {"keywords": "hallucination"}, _id="s1")])
            return response([tool_use("submit_evidence", {"evidence": [
                {"kind": "internal_experiment", "title": "CoVe", "ref_id": "exp_004", "why_relevant": "22->7"},
            ]})])

        return response([text_block("done")], stop="end_turn")

    return handler


async def test_orchestrator_end_to_end(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(orchestrator, "AsyncAnthropic", factory(_make_handler()))

    result = await orchestrator.run(
        "Help me reduce RAG hallucinations.", allow_live=False, store_dir=config.STORE_DIR
    )
    assert result.intent.domain == "evaluation/hallucination"
    assert [e.ref_id for e in result.research_evidence] == ["2309.15217"]
    assert [e.ref_id for e in result.context_evidence] == ["exp_004"]

    rec = result.recommendation
    assert rec is not None
    # firewall dropped the hallucinated refs
    assert {e.ref_id for e in rec.ranked_evidence} == {"exp_004", "2309.15217"}
    assert {c.citation_ref for c in rec.claims} == {"exp_004"}
    # usage accumulated across all agent calls (don't pin the exact fixture total)
    assert result.usage["input"] >= 25
    assert result.usage["output"] > 0


def _make_handler_no_intent():
    """Like the main handler, but the intent call returns free-form text (no tool),
    exercising the intent=None fallback path."""
    base = _make_handler()

    def handler(kwargs):
        choice = kwargs.get("tool_choice")
        if choice and choice.get("name") == "record_intent":
            return response([text_block("not sure how to route this")], stop="end_turn")
        return base(kwargs)

    return handler


async def test_orchestrator_intent_fallback(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(orchestrator, "AsyncAnthropic", factory(_make_handler_no_intent()))

    result = await orchestrator.run(
        "reduce RAG hallucinations", allow_live=False, store_dir=config.STORE_DIR
    )
    # No intent plan, but defaults still run both agents and produce a recommendation.
    assert result.intent is None
    assert result.research_evidence and result.context_evidence
    assert result.recommendation is not None
    assert any("Intent pass returned no usable plan" in n for n in result.notes)


def test_firewall_unit():
    rec = Recommendation(
        decision_summary="x",
        ranked_evidence=[
            Evidence(kind="external_paper", title="ok", why_relevant="w", ref_id="arxiv:2309.15217"),
            Evidence(kind="external_paper", title="bad", why_relevant="w", ref_id="9999.99999"),
        ],
        experiment_spec={"model": "m", "method": "me", "key_hyperparams": "k",
                         "estimated_compute_cost": "c", "estimated_savings_vs_naive": "s"},
        claims=[
            Claim(statement="valid", confidence="High", citation_ref="2309.15217"),
            Claim(statement="fabricated", confidence="Low", citation_ref="0000.00000"),
        ],
    )
    gathered = [Evidence(kind="external_paper", title="ok", why_relevant="w", ref_id="2309.15217")]
    synthesis_agent._apply_firewall(rec, gathered)
    synthesis_agent._resolve_links(rec)
    # invalid evidence AND invalid claim dropped; valid ones kept in the same rec
    assert [e.ref_id for e in rec.ranked_evidence] == ["arxiv:2309.15217"]
    assert [c.citation_ref for c in rec.claims] == ["2309.15217"]
    assert rec.ranked_evidence[0].link == "https://arxiv.org/abs/2309.15217"
