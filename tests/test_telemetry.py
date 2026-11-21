from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from sandbox_init.store import AuditStore
from sandbox_init.telemetry import collect_memory_snapshot


def test_collect_memory_snapshot_and_persist(tmp_path: Path) -> None:
    fake_meminfo = tmp_path / "meminfo"
    fake_meminfo.write_text(
        "MemTotal:       25165824 kB\nMemFree:         4194304 kB\nMemAvailable:   12582912 kB\n",
        encoding="utf-8",
    )
    snap = collect_memory_snapshot(node="hippo", min_headroom_gb=4.0, meminfo_path=fake_meminfo)
    assert snap.total_gb == 24.0
    assert snap.available_gb == 12.0
    assert snap.used_gb == 12.0
    assert snap.within_budget is True

    store = AuditStore(tmp_path / "audit.duckdb")
    try:
        store.record_snapshot(snap)
        assert store.count_snapshots() == 1
    finally:
        store.close()


@given(
    total_gb=st.integers(min_value=8, max_value=64),
    avail_gb=st.integers(min_value=0, max_value=64),
    min_headroom=st.floats(min_value=1.0, max_value=8.0),
)
@settings(max_examples=50)
def test_property_memory_headroom_invariant(
    tmp_path_factory: object,
    total_gb: int,
    avail_gb: int,
    min_headroom: float,
) -> None:
    from tempfile import TemporaryDirectory

    bounded_avail = min(avail_gb, total_gb)
    with TemporaryDirectory() as td:
        p = Path(td) / "meminfo"
        p.write_text(
            f"MemTotal: {total_gb * 1024 * 1024} kB\n"
            f"MemAvailable: {bounded_avail * 1024 * 1024} kB\n",
            encoding="utf-8",
        )
        snap = collect_memory_snapshot(node="rhino", min_headroom_gb=min_headroom, meminfo_path=p)
        assert snap.within_budget == (snap.available_gb >= min_headroom)
        assert round(snap.used_gb + snap.available_gb, 2) == snap.total_gb
