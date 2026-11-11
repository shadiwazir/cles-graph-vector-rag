import json

import pytest

from cles import cli
from cles.config import ConfigError, Settings
from cles.observability.logging import redact
from cles.stage import parse_args, stage_main


def test_parse_args_defaults():
    ctx = parse_args([])
    assert ctx.limit is None and not ctx.dry_run and ctx.run_id


def test_stage_main_prints_json_summary(capsys):
    stage_main("demo", lambda ctx: {"count": 3}, argv=["--run-id", "r1", "--dry-run"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out == {"stage": "demo", "run_id": "r1", "dry_run": True, "status": "ok", "count": 3}


def test_stage_main_exits_nonzero_on_failure(capsys):
    def boom(ctx):
        raise RuntimeError("bad")

    with pytest.raises(SystemExit) as exc:
        stage_main("demo", boom, argv=[])
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out.strip())["status"] == "failed"


def test_runner_runs_validate_pack(monkeypatch):
    summary = cli.run_stage("cles.domain.check", ["--run-id", "t1"])
    assert summary["status"] == "ok" and summary["pack"] == "legal_ca_on"


def test_missing_password_fails_clearly():
    settings = Settings(_env_file=None, postgres_password=None)
    with pytest.raises(ConfigError, match="POSTGRES_PASSWORD"):
        settings.postgres_dsn()


def test_redact_modes():
    assert redact("secret", "full") == "secret"
    assert redact("secret", "none") == ""
    assert "secret" not in redact("secret", "redacted")
