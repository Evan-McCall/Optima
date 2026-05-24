from typer.testing import CliRunner

from optima import cli
from optima.cli import _parse_env, _upsert_env

runner = CliRunner()


def test_parse_env_ignores_comments_and_blanks(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\nFOO=bar\nBAZ = qux \n")
    assert _parse_env(env) == {"FOO": "bar", "BAZ": "qux"}


def test_parse_env_missing_file(tmp_path):
    assert _parse_env(tmp_path / "nope.env") == {}


def test_upsert_env_updates_in_place_and_preserves_rest(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# keep me\nANTHROPIC_API_KEY=old\nUNRELATED=stay\n")

    _upsert_env(env, {"ANTHROPIC_API_KEY": "new", "OPTIMA_INDUSTRY": "legal tech"})

    text = env.read_text()
    assert "# keep me" in text          # comment preserved
    assert "UNRELATED=stay" in text     # unrelated key preserved
    assert "ANTHROPIC_API_KEY=new" in text and "old" not in text  # updated in place
    assert "OPTIMA_INDUSTRY=legal tech" in text  # new key appended


def test_upsert_env_creates_file(tmp_path):
    env = tmp_path / ".env"
    _upsert_env(env, {"ANTHROPIC_API_KEY": "k"})
    assert env.read_text() == "ANTHROPIC_API_KEY=k\n"


def test_init_writes_env_and_skips_optional_s2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "_PROJECT_ROOT", tmp_path)

    # industry, anthropic key, then Enter to skip Semantic Scholar
    result = runner.invoke(cli.app, ["init"], input="legal tech\nsk-ant-test\n\n")
    assert result.exit_code == 0, result.output

    env = _parse_env(tmp_path / ".env")
    assert env["OPTIMA_INDUSTRY"] == "legal tech"
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert "SEMANTIC_SCHOLAR_API_KEY" not in env  # skipped -> not written
    assert "optima ingest" in result.output       # how-to printed
