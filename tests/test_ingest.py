from optima import config
from optima.ingest import csv_loader
from optima.tools.internal_store import InternalStore

from _fakes import factory, response, tool_use

_MESSY_CSV = (
    "Exp ID,what we tried,Task,Model used,$ spent,When,Notes\n"
    "EXP-100,try QLoRA,finetune finance,Llama-3-8B,96 dollars,03/15/2026,worked great acc 0.83\n"
)


def _handler(kwargs):
    # Always asked (forced) to emit record_experiment.
    return response([tool_use("record_experiment", {
        "experiment_id": "exp_100",
        "hypothesis": "try QLoRA",
        "task": "finetune finance",
        "model": "Llama-3-8B",
        "status": "success",
        "compute_cost": {"dollars": 96},
        "date": "2026-03-15",
        "conclusion": "worked great acc 0.83",
    })])


async def test_ingest_csv_with_mocked_haiku(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(csv_loader, "AsyncAnthropic", factory(_handler))

    csv_path = tmp_path / "in.csv"
    csv_path.write_text(_MESSY_CSV)

    result = await csv_loader.ingest_csv(csv_path, store_dir=tmp_path)
    assert result.rows == 1
    assert result.parsed == 1
    assert (result.added, result.updated) == (1, 0)

    # the normalized record is in the store and parsed costs into a number
    store = InternalStore(tmp_path)
    exp = store.get_experiment("exp_100")
    assert exp is not None
    assert exp.status == "success"
    assert exp.compute_cost.dollars == 96
