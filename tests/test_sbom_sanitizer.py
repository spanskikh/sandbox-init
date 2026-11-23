from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sandbox_init.sbom import (
    main,
    sanitize_cyclonedx_bom,
    sanitize_sbom_file,
    verify_sanitized_bom,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "sanitize_sbom.sh"


def _build_sample_dirty_bom() -> dict[str, Any]:
    local_root_uri = "file://" + "/home/" + "runner/work/sandbox-init"
    local_nested_uri = "file://" + "/Users/" + "dev/projects/sandbox-init"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "externalReferences": [
            {"type": "distribution", "url": local_root_uri},
            {
                "type": "vcs",
                "url": "https://github.com/spanskikh/sandbox-init",
            },
        ],
        "metadata": {
            "component": {
                "name": "sandbox-init",
                "version": "0.8.0",
                "externalReferences": [
                    {"type": "build-system", "url": local_root_uri}
                ],
            }
        },
        "components": [
            {
                "name": "sandbox-init",
                "version": "0.8.0",
                "purl": "pkg:pypi/sandbox-init@0.8.0",
                "externalReferences": [
                    {"type": "distribution", "url": local_root_uri},
                    {
                        "type": "website",
                        "url": "https://github.com/spanskikh/sandbox-init",
                    },
                ],
                "components": [
                    {
                        "name": "nested-editable",
                        "version": "0.1.0",
                        "externalReferences": [
                            {"type": "distribution", "url": local_nested_uri}
                        ],
                    }
                ],
            },
            {
                "name": "pydantic",
                "version": "2.9.2",
                "purl": "pkg:pypi/pydantic@2.9.2",
            },
            {
                "name": "z3-solver",
                "version": "4.13.3.0",
                "purl": "pkg:pypi/z3-solver@4.13.3.0",
            },
        ],
    }


def test_sanitize_cyclonedx_bom_strips_all_file_refs_and_keeps_https() -> None:
    dirty = _build_sample_dirty_bom()
    sanitized, removed, remaining = sanitize_cyclonedx_bom(dirty)

    assert removed == 4
    assert remaining == 2
    serialized = json.dumps(sanitized, sort_keys=True)
    assert "file://" not in serialized
    assert "/home/" not in serialized
    assert "/Users/" not in serialized
    assert "https://github.com/spanskikh/sandbox-init" in serialized

    fingerprints = verify_sanitized_bom(sanitized)
    assert len(fingerprints) == 3
    assert ("pydantic", "2.9.2", "pkg:pypi/pydantic@2.9.2") in fingerprints


def test_sanitize_sbom_file_idempotency_and_determinism(
    tmp_path: Path,
) -> None:
    sbom_path = tmp_path / "sbom.cdx.json"
    sbom_path.write_text(
        json.dumps(_build_sample_dirty_bom(), indent=2), encoding="utf-8"
    )

    first_report = sanitize_sbom_file(sbom_path, verify=True)
    first_bytes = sbom_path.read_text(encoding="utf-8")
    assert first_report.removed_file_refs == 4
    assert first_report.remaining_external_refs == 2
    assert first_report.verified is True

    second_report = sanitize_sbom_file(sbom_path, verify=True)
    second_bytes = sbom_path.read_text(encoding="utf-8")
    assert second_report.removed_file_refs == 0
    assert second_report.remaining_external_refs == 2
    assert first_bytes == second_bytes
    assert (
        first_report.component_fingerprints
        == second_report.component_fingerprints
    )


def test_verify_sanitized_bom_rejects_violations() -> None:
    with pytest.raises(ValueError, match="Invalid bomFormat"):
        verify_sanitized_bom({"bomFormat": "SPDX", "components": []})

    with pytest.raises(ValueError, match="forbidden 'file://' URI"):
        verify_sanitized_bom(
            {
                "bomFormat": "CycloneDX",
                "components": [
                    {
                        "name": "z3-solver",
                        "externalReferences": [{"url": "file:///opt/pkg"}],
                    }
                ],
            }
        )

    leaked_home = "/home/" + "runner/leak"
    with pytest.raises(ValueError, match="leaked host path token"):
        verify_sanitized_bom(
            {
                "bomFormat": "CycloneDX",
                "components": [{"name": "z3-solver", "description": leaked_home}],
            }
        )

    with pytest.raises(ValueError, match="missing required packages"):
        verify_sanitized_bom(
            {
                "bomFormat": "CycloneDX",
                "components": [{"name": "pydantic", "version": "2.9.2"}],
            },
            required_packages=("pydantic", "z3-solver"),
        )


def test_cli_json_and_summary_modes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    in_file = tmp_path / "raw_sbom.cdx.json"
    out_file = tmp_path / "clean_sbom.cdx.json"
    in_file.write_text(
        json.dumps(_build_sample_dirty_bom()), encoding="utf-8"
    )

    rc_json = main(
        [
            "--input",
            str(in_file),
            "--output",
            str(out_file),
            "--verify",
            "--require-pkg",
            "pydantic",
            "--require-pkg",
            "z3-solver",
            "--format",
            "json",
        ]
    )
    assert rc_json == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verified"] is True
    assert payload["removed_file_refs"] == 4
    assert payload["component_count"] == 3

    rc_summary = main(
        [
            "--input",
            str(out_file),
            "--verify",
            "--format",
            "summary",
        ]
    )
    assert rc_summary == 0
    summary_line = capsys.readouterr().out.strip()
    assert "[sbom] file=clean_sbom.cdx.json format=CycloneDX" in summary_line
    assert "removed_file_refs=0" in summary_line
    assert "verified=True" in summary_line


def test_sanitize_sbom_script_dry_run() -> None:
    assert RUNNER_SCRIPT.is_file(), "Missing scripts/sanitize_sbom.sh"
    proc = subprocess.run(
        ["bash", str(RUNNER_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Dry-run failed: {proc.stderr}"
    assert "=== DRY-RUN SBOM SANITIZER (CR-026) ===" in proc.stdout
    assert "REPOS=sandbox-init" in proc.stdout
    assert "sandbox_init.sbom" in proc.stdout
