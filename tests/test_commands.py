"""End-to-end smoke tests for the read-only `status`, `experiments`, `papers` commands."""

from typer.testing import CliRunner

from optima import cli

runner = CliRunner()


def test_status_lists_store_and_keys():
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Optima status" in out
    assert "Store" in out
    assert "Experiments" in out
    assert "Cached papers" in out


def test_experiments_lists_seed_ids():
    """The default demo store ships with exp_001..exp_015 — at least one should show."""
    result = runner.invoke(cli.app, ["experiments", "--limit", "5"])
    assert result.exit_code == 0, result.output
    assert "exp_001" in result.output


def test_experiments_empty_store(tmp_path):
    """Pointing at an empty dir should print a friendly message, not crash."""
    (tmp_path / "experiments.json").write_text("[]")
    result = runner.invoke(cli.app, ["experiments", "--store", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No experiments" in result.output


def test_papers_lists_cache():
    result = runner.invoke(cli.app, ["papers", "--limit", "3"])
    assert result.exit_code == 0, result.output
    # Cache ships with real arXiv IDs — at least one should be present in the table.
    assert "arxiv:" in result.output


def test_papers_missing_cache(tmp_path):
    result = runner.invoke(cli.app, ["papers", "--store", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No paper cache" in result.output
