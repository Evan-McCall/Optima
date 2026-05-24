from optima import config
from optima.tools import papers as papers_mod
from optima.tools.papers import PaperSearch


def test_cache_search_offline():
    ps = PaperSearch(config.STORE_DIR, allow_live=False)
    results = ps.search("reduce RAG hallucination faithfulness evaluation", max_results=4)
    assert results, "cache search should return relevant papers"
    assert all(p.source == "cache" for p in results)
    titles = " ".join(p.title for p in results).lower()
    assert "ragas" in titles or "hallucination" in titles


def test_live_failure_falls_back_to_cache(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("403 simulated")

    monkeypatch.setattr(papers_mod, "_arxiv", boom)
    monkeypatch.setattr(papers_mod, "_semantic_scholar", boom)

    ps = PaperSearch(config.STORE_DIR, allow_live=True)  # live attempted, both fail
    results = ps.search("LoRA QLoRA parameter efficient fine-tuning", max_results=3)
    assert results
    assert all(p.source == "cache" for p in results)


def test_industry_appended_to_search_query(monkeypatch):
    """The team's industry (from `optima init`) is folded into the DB query."""
    seen = {}
    monkeypatch.setattr(papers_mod, "_arxiv", lambda q, n: seen.__setitem__("arxiv", q) or [])
    monkeypatch.setattr(papers_mod, "_semantic_scholar", lambda q, n: seen.__setitem__("s2", q) or [])

    ps = PaperSearch(config.STORE_DIR, allow_live=True, industry="legal tech")
    ps.search("hallucination evaluation", max_results=3)

    assert seen["arxiv"] == "hallucination evaluation legal tech"
    assert seen["s2"] == "hallucination evaluation legal tech"


def test_no_industry_leaves_query_unchanged(monkeypatch):
    seen = {}
    monkeypatch.setattr(papers_mod, "_arxiv", lambda q, n: seen.__setitem__("arxiv", q) or [])
    monkeypatch.setattr(papers_mod, "_semantic_scholar", lambda q, n: [])

    PaperSearch(config.STORE_DIR, allow_live=True).search("foo bar", max_results=2)
    assert seen["arxiv"] == "foo bar"
