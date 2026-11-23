# Target: src/sandbox_init/topology.py
from __future__ import annotations

import argparse
import json
import os
import shlex
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, Field

TopologyMode = Literal["host", "container"]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
CONTAINER_HOSTNAMES = frozenset(
    {"ollama", "host.docker.internal", "pgvector", "postgres", "rhino-pg"}
)
CONTAINER_OLLAMA_URL = "http://ollama:11434"
HOST_OLLAMA_URL = "http://127.0.0.1:11434"
CONTAINER_PG_HOST = "host.docker.internal"
HOST_PG_HOST = "127.0.0.1"
DEFAULT_PG_PORT = 15432
CONTAINER_AUDIT_DB = Path("/app/data/audit.duckdb")


class TopologyConfig(BaseModel):
    """Resolved host or container endpoint configuration for cluster services."""

    model_config = ConfigDict(frozen=True)

    mode: TopologyMode
    ollama_url: str = Field(min_length=1)
    pg_host: str = Field(min_length=1)
    pg_port: int = Field(ge=1, le=65535)
    postgres_dsn: str = Field(min_length=1)
    hostel_pg_dsn: str = Field(min_length=1)
    audit_db_path: Path


def detect_runtime_topology(
    env: Mapping[str, str] | None = None,
    *,
    in_container: bool | None = None,
) -> TopologyMode:
    """Detect whether execution runs on the host or inside a container."""
    source_env = os.environ if env is None else env
    explicit = source_env.get("CLUSTER_TOPOLOGY", "").strip().lower()
    if explicit == "host":
        return "host"
    if explicit == "container":
        return "container"
    if explicit:
        msg = f"Invalid CLUSTER_TOPOLOGY={explicit!r}; expected 'host' or 'container'"
        raise ValueError(msg)
    if in_container is not None:
        return "container" if in_container else "host"
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return "container"
    return "host"


def _rewrite_url_host_for_mode(raw_url: str, mode: TopologyMode, target_host: str) -> str:
    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()
    if mode != "host" or hostname not in CONTAINER_HOSTNAMES:
        return raw_url
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    port_part = f":{parsed.port}" if parsed.port is not None else ""
    netloc = f"{userinfo}{target_host}{port_part}"
    return urlunparse(parsed._replace(netloc=netloc))


def _resolve_ollama_url(source_env: Mapping[str, str], mode: TopologyMode) -> str:
    raw = (
        source_env.get("OLLAMA_URL", "").strip()
        or source_env.get("OLLAMA_BASE_URL", "").strip()
    )
    if not raw:
        return HOST_OLLAMA_URL if mode == "host" else CONTAINER_OLLAMA_URL
    return _rewrite_url_host_for_mode(raw, mode, HOST_PG_HOST)


def _resolve_pg_host_and_port(
    source_env: Mapping[str, str], mode: TopologyMode
) -> tuple[str, int]:
    raw_host = source_env.get("CLUSTER_PG_HOST", "").strip()
    raw_port = source_env.get("CLUSTER_PG_PORT", "").strip()
    port = int(raw_port) if raw_port else DEFAULT_PG_PORT
    if not raw_host:
        host = HOST_PG_HOST if mode == "host" else CONTAINER_PG_HOST
    elif mode == "host" and raw_host.lower() in CONTAINER_HOSTNAMES:
        host = HOST_PG_HOST
    else:
        host = raw_host
    return host, port


def _resolve_dsn(
    source_env: Mapping[str, str],
    key: str,
    db_name: str,
    mode: TopologyMode,
    pg_host: str,
    pg_port: int,
) -> str:
    raw_dsn = source_env.get(key, "").strip()
    if not raw_dsn:
        default_host = pg_host if mode == "host" else CONTAINER_PG_HOST
        return f"postgresql://dev:devpass@{default_host}:{pg_port}/{db_name}"
    return _rewrite_url_host_for_mode(raw_dsn, mode, pg_host)


def _resolve_audit_db_path(
    source_env: Mapping[str, str],
    mode: TopologyMode,
    repo_root: Path,
) -> Path:
    raw_db = source_env.get("AUDIT_DB_PATH", "").strip()
    if mode == "container":
        return Path(raw_db) if raw_db else CONTAINER_AUDIT_DB
    if not raw_db:
        return repo_root / "data" / "audit.duckdb"
    if raw_db == "/app/data":
        return repo_root / "data" / "audit.duckdb"
    if raw_db.startswith("/app/data/"):
        rel = Path(raw_db).relative_to("/app/data")
        return repo_root / "data" / rel
    return Path(raw_db)


def resolve_topology_config(
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    *,
    in_container: bool | None = None,
) -> TopologyConfig:
    """Resolve host or container service endpoints and local DuckDB paths."""
    source_env = os.environ if env is None else env
    base_root = (DEFAULT_REPO_ROOT if repo_root is None else repo_root).resolve()
    mode = detect_runtime_topology(source_env, in_container=in_container)
    ollama_url = _resolve_ollama_url(source_env, mode)
    pg_host, pg_port = _resolve_pg_host_and_port(source_env, mode)
    postgres_dsn = _resolve_dsn(
        source_env, "POSTGRES_DSN", "interview_ops", mode, pg_host, pg_port
    )
    hostel_pg_dsn = _resolve_dsn(
        source_env, "HOSTEL_PG_DSN", "hostel_ops", mode, pg_host, pg_port
    )
    audit_db_path = _resolve_audit_db_path(source_env, mode, base_root)
    return TopologyConfig(
        mode=mode,
        ollama_url=ollama_url,
        pg_host=pg_host,
        pg_port=pg_port,
        postgres_dsn=postgres_dsn,
        hostel_pg_dsn=hostel_pg_dsn,
        audit_db_path=audit_db_path,
    )


def build_topology_env(
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    *,
    in_container: bool | None = None,
) -> dict[str, str]:
    """Build normalized environment variables for host or container test runners."""
    cfg = resolve_topology_config(
        env=env, repo_root=repo_root, in_container=in_container
    )
    return {
        "CLUSTER_TOPOLOGY": cfg.mode,
        "OLLAMA_URL": cfg.ollama_url,
        "OLLAMA_BASE_URL": cfg.ollama_url,
        "CLUSTER_PG_HOST": cfg.pg_host,
        "CLUSTER_PG_PORT": str(cfg.pg_port),
        "POSTGRES_DSN": cfg.postgres_dsn,
        "HOSTEL_PG_DSN": cfg.hostel_pg_dsn,
        "AUDIT_DB_PATH": str(cfg.audit_db_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint exporting resolved topology settings as JSON or shell env."""
    parser = argparse.ArgumentParser(
        description="Resolve host vs container endpoints for cluster integration."
    )
    parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="json",
        help="Output format: 'json' or shell 'env' exports.",
    )
    parser.add_argument(
        "--mode",
        choices=("host", "container"),
        default=None,
        help="Optional explicit topology mode override.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional repository root for relative data directory resolution.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    in_container: bool | None = None
    if args.mode is not None:
        in_container = args.mode == "container"
    resolved = build_topology_env(
        repo_root=args.repo_root, in_container=in_container
    )
    if args.format == "json":
        print(json.dumps(resolved, indent=2, sort_keys=True))
    else:
        for key, value in resolved.items():
            print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
