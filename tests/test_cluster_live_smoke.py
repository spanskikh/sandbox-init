from __future__ import annotations

import os
import socket
import struct
from pathlib import Path

import httpx
import pytest

from sandbox_init.store import AuditStore
from sandbox_init.telemetry import collect_memory_snapshot
from sandbox_init.topology import resolve_topology_config

TOPOLOGY = resolve_topology_config()
PG_HOST = TOPOLOGY.pg_host
PG_PORT = TOPOLOGY.pg_port
OLLAMA_URL = TOPOLOGY.ollama_url
MIN_HEADROOM_GB = float(os.getenv("MIN_HEADROOM_GB", "4.0"))


def _pg_wire_handshake(host: str, port: int, user: str = "postgres", timeout: float = 2.0) -> bytes:
    """Send PostgreSQL v3 StartupMessage and read server response tag ('R', 'E', etc.)."""
    payload = b"\x00\x03\x00\x00user\x00" + user.encode("utf-8") + b"\x00\x00"
    packet = struct.pack("!I", len(payload) + 4) + payload
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(packet)
        header = sock.recv(5)
    return header[:1]


@pytest.mark.integration
def test_rhino_pg_tunnel_reachable() -> None:
    tag = _pg_wire_handshake(PG_HOST, PG_PORT)
    assert tag in {b"R", b"E"}, (
        f"Unexpected PostgreSQL wire response from {PG_HOST}:{PG_PORT}: {tag!r}"
    )


@pytest.mark.integration
def test_hippo_ollama_headroom_and_duckdb_audit(tmp_path: Path) -> None:
    resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("models"), list)

    snap = collect_memory_snapshot(node="hippo", min_headroom_gb=MIN_HEADROOM_GB)
    assert snap.within_budget, (
        f"Headroom breach on hippo: available={snap.available_gb} GiB < {MIN_HEADROOM_GB} GiB"
    )

    store = AuditStore(tmp_path / "smoke_audit.duckdb")
    store.record_snapshot(snap)
    store.close()
    
