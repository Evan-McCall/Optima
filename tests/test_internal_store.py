import json

from optima import config
from optima.schema import Experiment
from optima.tools.internal_store import InternalStore


def test_loads_demo_store():
    store = InternalStore(config.STORE_DIR)
    assert len(store.experiments) >= 15
    assert "exp_004" in store.experiments
    assert store.get_doc("rag_eval_postmortem") is not None


def test_search_ranks_relevant_first():
    store = InternalStore(config.STORE_DIR)
    hits = store.search_experiments("refund hallucination validation agent", limit=3)
    ids = {e.experiment_id for e in hits}
    assert ids & {"exp_006", "exp_007", "exp_008"}


def test_compact_index_is_reasonably_sized():
    store = InternalStore(config.STORE_DIR)
    idx = store.compact_index()
    assert "exp_004" in idx
    assert 500 < len(idx) < 20000  # small enough to cache in-context


def test_add_experiments_writes_ingested(tmp_path):
    # isolated store dir with a single curated experiment
    (tmp_path / "experiments.json").write_text(
        json.dumps([{"experiment_id": "exp_a", "hypothesis": "h", "task": "t"}])
    )
    store = InternalStore(tmp_path)
    added, updated = store.add_experiments(
        [Experiment(experiment_id="exp_b", hypothesis="h2", task="t2")]
    )
    assert (added, updated) == (1, 0)
    assert (tmp_path / "ingested.json").exists()
    # reloading picks up both curated + ingested
    assert set(InternalStore(tmp_path).experiments) == {"exp_a", "exp_b"}
