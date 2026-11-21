from __future__ import annotations

from pathlib import Path
from typing import Literal

from sandbox_init.contracts import NodeMemorySnapshot


def parse_proc_meminfo(raw_text: str) -> tuple[float, float]:
    """Parse MemTotal and MemAvailable from /proc/meminfo content into GiB."""
    values_kb: dict[str, int] = {}
    for line in raw_text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.strip().split()
        if parts and parts[0].isdigit():
            values_kb[key.strip()] = int(parts[0])
    if "MemTotal" not in values_kb or "MemAvailable" not in values_kb:
        raise ValueError("Missing MemTotal or MemAvailable in meminfo payload")
    total_gb = round(values_kb["MemTotal"] / (1024 * 1024), 2)
    available_gb = round(values_kb["MemAvailable"] / (1024 * 1024), 2)
    return total_gb, available_gb


def collect_memory_snapshot(
    node: Literal["hippo", "rhino"],
    min_headroom_gb: float = 4.0,
    meminfo_path: str | Path = "/proc/meminfo",
) -> NodeMemorySnapshot:
    """Collect live host RAM metrics and evaluate against minimum headroom budget."""
    raw = Path(meminfo_path).read_text(encoding="utf-8")
    total_gb, available_gb = parse_proc_meminfo(raw)
    used_gb = round(max(0.0, total_gb - available_gb), 2)
    return NodeMemorySnapshot(
        node=node,
        total_gb=total_gb,
        available_gb=available_gb,
        used_gb=used_gb,
        min_headroom_gb=min_headroom_gb,
        within_budget=available_gb >= min_headroom_gb,
    )
