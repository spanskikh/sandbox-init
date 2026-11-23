from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sandbox_init.topology import (
    build_topology_env,
    detect_runtime_topology,
    main,
    resolve_topology_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "run_integration.sh"


def test_host_mode_rewrites_container_endpoints(tmp_path: Path) -> None:
    container_env = {
        "OLLAMA_URL": "http://ollama:11434",
        "CLUSTER_PG_HOST": "host.docker.internal",
        "CLUSTER_PG_PORT": "15432",
        "POSTGRES_DSN": (
            "postgresql://dev:devpass@host.docker.internal:15432/interview_ops"
        ),
        "HOSTEL_PG_DSN": (
            "postgresql://dev:devpass@host.docker.internal:15432/hostel_ops"
        ),
        "AUDIT_DB_PATH": "/app/data/hostel_analytics.duckdb",
    }
    cfg = resolve_topology_config(
        env=container_env, repo_root=tmp_path, in_container=False
    )
    assert cfg.mode == "host"
    assert cfg.ollama_url == "http://127.0.0.1:11434"
    assert cfg.pg_host == "127.0.0.1"
    assert cfg.pg_port == 15432
    assert cfg.postgres_dsn == (
        "postgresql://dev:devpass@127.0.0.1:15432/interview_ops"
    )
    assert cfg.hostel_pg_dsn == (
        "postgresql://dev:devpass@127.0.0.1:15432/hostel_ops"
    )
    assert cfg.audit_db_path == tmp_path / "data" / "hostel_analytics.duckdb"


def test_host_mode_preserves_explicit_non_container_overrides(
    tmp_path: Path,
) -> None:
    custom_db = tmp_path / "custom_audit.duckdb"
    custom_env = {
        "CLUSTER_TOPOLOGY": "host",
        "OLLAMA_URL": "http://192.168.50.10:11435",
        "CLUSTER_PG_HOST": "10.10.0.12",
        "CLUSTER_PG_PORT": "25432",
        "POSTGRES_DSN": "postgresql://alice:secret@10.10.0.12:25432/custom_rag",
        "HOSTEL_PG_DSN": "postgresql://bob:secret@10.10.0.12:25432/custom_hostel",
        "AUDIT_DB_PATH": str(custom_db),
    }
    cfg = resolve_topology_config(
        env=custom_env, repo_root=tmp_path, in_container=True
    )
    assert cfg.mode == "host"
    assert cfg.ollama_url == "http://192.168.50.10:11435"
    assert cfg.pg_host == "10.10.0.12"
    assert cfg.pg_port == 25432
    assert cfg.postgres_dsn == (
        "postgresql://alice:secret@10.10.0.12:25432/custom_rag"
    )
    assert cfg.hostel_pg_dsn == (
        "postgresql://bob:secret@10.10.0.12:25432/custom_hostel"
    )
    assert cfg.audit_db_path == custom_db


def test_container_mode_preserves_container_defaults(tmp_path: Path) -> None:
    cfg = resolve_topology_config(
        env={}, repo_root=tmp_path, in_container=True
    )
    assert cfg.mode == "container"
    assert cfg.ollama_url == "http://ollama:11434"
    assert cfg.pg_host == "host.docker.internal"
    assert cfg.pg_port == 15432
    assert cfg.postgres_dsn == (
        "postgresql://dev:devpass@host.docker.internal:15432/interview_ops"
    )
    assert cfg.hostel_pg_dsn == (
        "postgresql://dev:devpass@host.docker.internal:15432/hostel_ops"
    )
    assert cfg.audit_db_path == Path("/app/data/audit.duckdb")

    exported = build_topology_env(
        env={"CLUSTER_TOPOLOGY": "container"}, repo_root=tmp_path
    )
    assert exported["CLUSTER_TOPOLOGY"] == "container"
    assert exported["OLLAMA_URL"] == "http://ollama:11434"
    assert exported["OLLAMA_BASE_URL"] == "http://ollama:11434"
    assert exported["AUDIT_DB_PATH"] == "/app/data/audit.duckdb"


def test_detect_runtime_topology_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError, match="Invalid CLUSTER_TOPOLOGY"):
        detect_runtime_topology({"CLUSTER_TOPOLOGY": "invalid-mode"})


def test_cli_json_and_env_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc_json = main(
        ["--format", "json", "--mode", "host", "--repo-root", str(tmp_path)]
    )
    assert rc_json == 0
    out_json = capsys.readouterr().out
    payload = json.loads(out_json)
    assert payload["CLUSTER_TOPOLOGY"] == "host"
    assert payload["OLLAMA_URL"] == "http://127.0.0.1:11434"
    assert payload["CLUSTER_PG_HOST"] == "127.0.0.1"
    assert payload["AUDIT_DB_PATH"] == str(tmp_path / "data" / "audit.duckdb")

    rc_env = main(
        ["--format", "env", "--mode", "container", "--repo-root", str(tmp_path)]
    )
    assert rc_env == 0
    out_env = capsys.readouterr().out
    assert "export CLUSTER_TOPOLOGY=" in out_env
    assert "http://ollama:11434" in out_env


def test_run_integration_script_dry_run() -> None:
    assert RUNNER_SCRIPT.is_file(), "Missing scripts/run_integration.sh"
    py_dir = str(Path(sys.executable).resolve().parent)
    proc = subprocess.run(
        ["bash", str(RUNNER_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{py_dir}:/usr/bin:/bin",
            "PYTHON_BIN": sys.executable,
            "OLLAMA_URL": "http://ollama:11434",
            "POSTGRES_DSN": (
                "postgresql://dev:devpass@host.docker.internal:15432/interview_ops"
            ),
            "AUDIT_DB_PATH": "/app/data/audit.duckdb",
        },
    )
    assert proc.returncode == 0, f"Dry-run failed: {proc.stderr}"
    assert "=== DRY-RUN TOPOLOGY (sandbox-init) ===" in proc.stdout
    assert "CLUSTER_TOPOLOGY=host" in proc.stdout
    assert "OLLAMA_URL=http://127.0.0.1:11434" in proc.stdout
    assert "CLUSTER_PG_HOST=127.0.0.1:15432" in proc.stdout
    assert (
        "CMD: ./scripts/run_logged.sh cr024_integration_sandbox_init -- "
        ".venv/bin/pytest -v -m integration"
    ) in proc.stdout

    sub_env = dict(os.environ)
    sub_env["PYTHONPATH"] = str(REPO_ROOT / "src")
    sub_cli = subprocess.run(
        [sys.executable, "-m", "sandbox_init.topology", "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=sub_env,
    )
    cli_data = json.loads(sub_cli.stdout)
    assert cli_data["CLUSTER_TOPOLOGY"] in {"host", "container"}
