from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "run_logged.sh"


def test_run_logged_captures_streams_timestamps_and_exit_code(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    target_script = scripts_dir / "run_logged.sh"
    shutil.copy2(SOURCE_SCRIPT, target_script)

    proc = subprocess.run(
        [
            str(target_script),
            "sample_probe",
            "--",
            "python3",
            "-c",
            "import sys; print('OUT_LINE'); print('ERR_LINE', file=sys.stderr); sys.exit(7)",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 7
    assert "OUT_LINE" in proc.stdout
    assert "ERR_LINE" in proc.stderr

    log_dir = tmp_path / "logs"
    out_files = list(log_dir.glob("*_sample_probe.stdout"))
    err_files = list(log_dir.glob("*_sample_probe.stderr"))
    all_files = list(log_dir.glob("*_sample_probe.log"))

    assert len(out_files) == 1
    assert len(err_files) == 1
    assert len(all_files) == 1

    assert "OUT_LINE" in out_files[0].read_text(encoding="utf-8")
    assert "ERR_LINE" in err_files[0].read_text(encoding="utf-8")

    combined = all_files[0].read_text(encoding="utf-8")
    assert "=== RUN START:" in combined
    assert "=== RUN END:" in combined
    assert "EXIT_CODE: 7" in combined
    assert "OUT_LINE" in combined
    assert "ERR_LINE" in combined
